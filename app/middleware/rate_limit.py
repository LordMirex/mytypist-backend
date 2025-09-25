"""
Rate limiting middleware
"""

import time
import json
from typing import Dict, Any
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis

from config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis"""
    
    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis_client = redis_client
        
        # Rate limit configurations
        self.rate_limits = {
            "default": {"requests": 200, "window": 60},  # 200 requests per minute
            "auth": {"requests": 50, "window": 60},      # 50 auth requests per minute
            "api": {"requests": 1000, "window": 3600},   # 1000 API requests per hour
            "upload": {"requests": 50, "window": 3600},  # 50 uploads per hour
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting"""
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Determine rate limit category
        category = self._get_rate_limit_category(request.url.path)
        
        # Check rate limit
        if not self._check_rate_limit(client_id, category):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "Retry-After": str(self.rate_limits[category]["window"]),
                    "X-RateLimit-Limit": str(self.rate_limits[category]["requests"]),
                    "X-RateLimit-Window": str(self.rate_limits[category]["window"])
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining, reset_time = self._get_rate_limit_info(client_id, category)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limits[category]["requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        
        # Use user ID if authenticated
        if hasattr(request.state, 'current_user') and request.state.current_user:
            return f"user:{request.state.current_user.id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"
    
    def _get_rate_limit_category(self, path: str) -> str:
        """Determine rate limit category based on path"""
        
        if path.startswith("/api/auth/"):
            return "auth"
        elif path.startswith("/api/templates") and "upload" in path:
            return "upload"
        elif path.startswith("/api/documents") and "upload" in path:
            return "upload"
        elif path.startswith("/api/"):
            return "api"
        else:
            return "default"
    
    def _check_rate_limit(self, client_id: str, category: str) -> bool:
        """Check if client is within rate limit"""
        
        config = self.rate_limits[category]
        key = f"rate_limit:{category}:{client_id}"
        
        try:
            # Get current count
            current_count = self.redis_client.get(key)
            
            if current_count is None:
                # First request in window
                self.redis_client.setex(key, config["window"], 1)
                return True
            
            current_count = int(current_count)
            
            if current_count >= config["requests"]:
                return False
            
            # Increment count
            self.redis_client.incr(key)
            return True
        
        except redis.RedisError:
            # If Redis is down, allow request but log error
            print("Redis error in rate limiting - allowing request")
            return True
    
    def _get_rate_limit_info(self, client_id: str, category: str) -> tuple[int, int]:
        """Get remaining requests and reset time"""
        
        config = self.rate_limits[category]
        key = f"rate_limit:{category}:{client_id}"
        
        try:
            current_count = self.redis_client.get(key)
            if current_count is None:
                return config["requests"], int(time.time()) + config["window"]
            
            current_count = int(current_count)
            remaining = max(0, config["requests"] - current_count)
            
            # Get TTL for reset time
            ttl = self.redis_client.ttl(key)
            reset_time = int(time.time()) + max(ttl, 0)
            
            return remaining, reset_time
        
        except redis.RedisError:
            return config["requests"], int(time.time()) + config["window"]
    
    def reset_rate_limit(self, client_id: str, category: str = None) -> None:
        """Reset rate limit for client (admin function)"""
        
        if category:
            key = f"rate_limit:{category}:{client_id}"
            self.redis_client.delete(key)
        else:
            # Reset all categories for client
            for cat in self.rate_limits.keys():
                key = f"rate_limit:{cat}:{client_id}"
                self.redis_client.delete(key)
    
    def get_rate_limit_status(self, client_id: str) -> Dict[str, Any]:
        """Get rate limit status for client"""
        
        status = {}
        
        for category, config in self.rate_limits.items():
            key = f"rate_limit:{category}:{client_id}"
            
            try:
                current_count = self.redis_client.get(key)
                if current_count is None:
                    remaining = config["requests"]
                    reset_time = int(time.time()) + config["window"]
                else:
                    current_count = int(current_count)
                    remaining = max(0, config["requests"] - current_count)
                    ttl = self.redis_client.ttl(key)
                    reset_time = int(time.time()) + max(ttl, 0)
                
                status[category] = {
                    "limit": config["requests"],
                    "remaining": remaining,
                    "reset_time": reset_time,
                    "window": config["window"]
                }
            
            except redis.RedisError:
                status[category] = {
                    "limit": config["requests"],
                    "remaining": config["requests"],
                    "reset_time": int(time.time()) + config["window"],
                    "window": config["window"]
                }
        
        return status


# Decorator function for route-specific rate limiting
def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """
    Decorator for applying rate limits to specific routes
    
    Args:
        max_requests: Maximum requests allowed
        window_seconds: Time window in seconds
    """
    def decorator(func):
        # Store rate limit metadata on the function
        func._rate_limit_max_requests = max_requests
        func._rate_limit_window_seconds = window_seconds
        return func
    return decorator

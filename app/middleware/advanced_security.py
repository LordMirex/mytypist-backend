"""
Advanced security middleware for production deployment
"""

import time
import hashlib
from typing import Callable, Dict, Set, Any
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis

from config import settings
from app.services.audit_service import AuditService


class AdvancedSecurityMiddleware(BaseHTTPMiddleware):
    """Production-grade security middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.suspicious_patterns = {
            # SQL injection patterns
            r"(?i)(union\s+select|drop\s+table|insert\s+into|delete\s+from)",
            # XSS patterns
            r"(?i)(<script|javascript:|on\w+\s*=)",
            # Path traversal
            r"(\.\./|\.\.\\|%2e%2e)",
            # Command injection
            r"(?i)(;|\||&|\$\(|\`|nc\s+|wget\s+|curl\s+)"
        }
        self.blocked_user_agents = {
            "sqlmap", "nikto", "dirbuster", "burpsuite", "nessus"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Security checks
        await self._check_suspicious_patterns(request)
        await self._check_user_agent(request)
        await self._check_request_size(request)
        await self._check_rate_limits(request)
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    async def _check_suspicious_patterns(self, request: Request):
        """Check for suspicious request patterns"""
        import re
        
        # Check URL path
        path = str(request.url.path)
        query = str(request.url.query) if request.url.query else ""
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, path + query):
                await self._log_security_incident(request, "suspicious_pattern", {"pattern": pattern})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Malicious request detected"
                )
    
    async def _check_user_agent(self, request: Request):
        """Check for malicious user agents"""
        user_agent = request.headers.get("user-agent", "").lower()
        
        for blocked_agent in self.blocked_user_agents:
            if blocked_agent in user_agent:
                await self._log_security_incident(request, "blocked_user_agent", {"user_agent": user_agent})
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
    
    async def _check_request_size(self, request: Request):
        """Check request size limits"""
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            max_size = 100 * 1024 * 1024  # 100MB
            
            if size > max_size:
                await self._log_security_incident(request, "oversized_request", {"size": size})
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request too large"
                )
    
    async def _check_rate_limits(self, request: Request):
        """Advanced rate limiting with Redis"""
        if not hasattr(self, 'redis'):
            return
        
        client_ip = request.client.host if request.client else "unknown"
        
        # Different limits for different endpoints
        endpoint_limits = {
            "/api/auth/login": (5, 300),      # 5 attempts per 5 minutes
            "/api/auth/register": (3, 3600),  # 3 registrations per hour
            "/api/documents/generate": (20, 60), # 20 generations per minute
            "default": (100, 60)               # 100 requests per minute
        }
        
        path = request.url.path
        limit_requests, limit_window = endpoint_limits.get(path, endpoint_limits["default"])
        
        try:
            # Check current request count
            rate_key = f"rate_limit:{client_ip}:{path}"
            current_requests = await self.redis.get(rate_key)
            
            if current_requests and int(current_requests) >= limit_requests:
                await self._log_security_incident(request, "rate_limit_exceeded", {
                    "ip": client_ip,
                    "path": path,
                    "requests": int(current_requests)
                })
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
            
            # Increment counter
            pipe = self.redis.pipeline()
            pipe.incr(rate_key)
            pipe.expire(rate_key, limit_window)
            await pipe.execute()
        except Exception:
            # Continue if Redis is unavailable
            pass
    
    def _add_security_headers(self, response: Response):
        """Add comprehensive security headers"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-site"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
    
    async def _log_security_incident(self, request: Request, incident_type: str, details: Dict):
        """Log security incidents"""
        try:
            AuditService.log_security_event(
                "SUSPICIOUS_ACTIVITY",
                None,
                request,
                {
                    "incident_type": incident_type,
                    "details": details,
                    "timestamp": time.time()
                }
            )
        except Exception:
            # Fail silently if audit logging fails
            pass


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate request structure and content"""
    
    MAX_HEADERS = 50
    MAX_HEADER_SIZE = 8192
    MAX_URL_LENGTH = 2048
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Validate request structure
        await self._validate_headers(request)
        await self._validate_url(request)
        await self._validate_method(request)
        
        return await call_next(request)
    
    async def _validate_headers(self, request: Request):
        """Validate request headers"""
        headers = request.headers
        
        # Check header count
        if len(headers) > self.MAX_HEADERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many headers"
            )
        
        # Check header sizes
        for name, value in headers.items():
            if len(name) + len(value) > self.MAX_HEADER_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Header too large"
                )
    
    async def _validate_url(self, request: Request):
        """Validate URL length and format"""
        url_str = str(request.url)
        
        if len(url_str) > self.MAX_URL_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_414_REQUEST_URI_TOO_LONG,
                detail="URL too long"
            )
    
    async def _validate_method(self, request: Request):
        """Validate HTTP method"""
        allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
        
        if request.method not in allowed_methods:
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail="Method not allowed"
            )


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP-based access control"""
    
    def __init__(self, app, whitelist: Set[str] = None, blacklist: Set[str] = None):
        super().__init__(app)
        self.whitelist = whitelist or set()
        self.blacklist = blacklist or {
            "127.0.0.1",  # Remove this for local development
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        
        # Check blacklist
        if client_ip in self.blacklist:
            await self._log_blocked_ip(request, client_ip, "blacklisted")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Check whitelist (if configured)
        if self.whitelist and client_ip not in self.whitelist:
            await self._log_blocked_ip(request, client_ip, "not_whitelisted")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return await call_next(request)
    
    async def _log_blocked_ip(self, request: Request, ip: str, reason: str):
        """Log blocked IP access attempts"""
        try:
            AuditService.log_security_event(
                "UNAUTHORIZED_ACCESS",
                None,
                request,
                {
                    "blocked_ip": ip,
                    "reason": reason,
                    "path": str(request.url.path)
                }
            )
        except Exception:
            pass
"""
Performance monitoring and optimization middleware
"""

import time
import asyncio
from typing import Callable, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.audit_service import AuditService


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Monitor and optimize request performance"""
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Timestamp"] = str(int(start_time))
        
        # Log slow requests
        if process_time > self.slow_request_threshold:
            try:
                AuditService.log_system_event(
                    "SLOW_REQUEST",
                    {
                        "url": str(request.url),
                        "method": request.method,
                        "process_time": round(process_time, 3),
                        "user_agent": request.headers.get("user-agent", ""),
                        "ip": request.client.host if request.client else "unknown"
                    }
                )
            except Exception:
                # Fail silently if audit logging fails
                pass
        
        return response


class CompressionMiddleware(BaseHTTPMiddleware):
    """Advanced response compression"""
    
    def __init__(self, app, minimum_size: int = 1024, compression_level: int = 6):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Check if compression is beneficial
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding:
            return response
        
        # Get response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Compress if beneficial
        if len(body) >= self.minimum_size:
            try:
                import gzip
                compressed_body = gzip.compress(body, compresslevel=self.compression_level)
                
                # Only use compression if it actually reduces size
                if len(compressed_body) < len(body):
                    response.headers["content-encoding"] = "gzip"
                    response.headers["content-length"] = str(len(compressed_body))
                    
                    # Create new response with compressed body
                    from fastapi.responses import Response as FastAPIResponse
                    return FastAPIResponse(
                        content=compressed_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
            except Exception:
                # Fall back to uncompressed if compression fails
                pass
        
        # Return original response
        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )


class ConnectionPoolMonitor:
    """Monitor database connection pool health"""
    
    @staticmethod
    async def check_pool_health() -> Dict[str, Any]:
        """Check database pool health"""
        from database import DatabaseManager
        
        try:
            pool_status = DatabaseManager.get_pool_status()
            
            # Calculate utilization percentage
            total_connections = pool_status["pool_size"] + pool_status["overflow"]
            active_connections = pool_status["checked_out"]
            utilization = (active_connections / total_connections * 100) if total_connections > 0 else 0
            
            health_status = {
                "pool_status": pool_status,
                "utilization_percent": round(utilization, 2),
                "health": "healthy" if utilization < 80 else "warning" if utilization < 95 else "critical"
            }
            
            # Log if utilization is high
            if utilization > 80:
                try:
                    AuditService.log_system_event(
                        "HIGH_DB_POOL_UTILIZATION",
                        {
                            "utilization_percent": utilization,
                            "active_connections": active_connections,
                            "total_connections": total_connections
                        }
                    )
                except Exception:
                    pass
            
            return health_status
        except Exception as e:
            return {
                "error": str(e),
                "health": "error"
            }


class MemoryOptimizer:
    """Memory usage optimization utilities"""
    
    @staticmethod
    async def optimize_memory():
        """Run memory optimization tasks"""
        import gc
        
        # Force garbage collection
        collected = gc.collect()
        
        # Get memory stats
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "garbage_collected": collected,
                "memory_usage_mb": round(memory_info.rss / 1024 / 1024, 2),
                "memory_percent": round(process.memory_percent(), 2)
            }
        except ImportError:
            return {"garbage_collected": collected}
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get caching statistics"""
        # This would integrate with Redis INFO command
        # and other cache metrics in production
        return {
            "cache_hit_rate": "95%",  # Placeholder - implement Redis stats
            "cached_items": 1250,     # Placeholder - implement Redis stats
            "memory_usage": "45MB"    # Placeholder - implement Redis stats
        }
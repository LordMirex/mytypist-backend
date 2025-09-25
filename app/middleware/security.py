"""
Security middleware for headers and protection
"""

import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config import settings


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for adding security headers and protection"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Security headers
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none';"
            )
        }
        
        # Remove HSTS in development
        if settings.DEBUG:
            del self.security_headers["Strict-Transport-Security"]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware"""
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Add request start time
        request.state.start_time = time.time()
        
        # Validate request size
        if not self._validate_request_size(request):
            return Response(
                content="Request too large",
                status_code=413,
                headers={"Content-Type": "text/plain"}
            )
        
        # Validate content type for POST/PUT requests
        if not self._validate_content_type(request):
            return Response(
                content="Invalid content type",
                status_code=415,
                headers={"Content-Type": "text/plain"}
            )
        
        # Check for suspicious patterns
        if self._detect_suspicious_patterns(request):
            return Response(
                content="Request blocked",
                status_code=403,
                headers={"Content-Type": "text/plain"}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add request ID to response
        response.headers["X-Request-ID"] = request_id
        
        # Add response time
        if hasattr(request.state, 'start_time'):
            response_time = time.time() - request.state.start_time
            response.headers["X-Response-Time"] = f"{response_time:.3f}s"
        
        # Remove server information
        if "server" in response.headers:
            del response.headers["server"]
        
        return response
    
    def _validate_request_size(self, request: Request) -> bool:
        """Validate request size"""
        
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                # 50MB limit
                return size <= 50 * 1024 * 1024
            except ValueError:
                return False
        
        return True
    
    def _validate_content_type(self, request: Request) -> bool:
        """Validate content type for requests with body"""
        
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            
            # Allow common content types
            allowed_types = [
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
                "text/plain",
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ]
            
            # Check if content type is allowed
            for allowed_type in allowed_types:
                if content_type.startswith(allowed_type):
                    return True
            
            # Special handling for multipart and form data
            if content_type.startswith("multipart/") or content_type.startswith("application/x-www-form-urlencoded"):
                return True
            
            return False
        
        return True
    
    def _detect_suspicious_patterns(self, request: Request) -> bool:
        """Detect suspicious request patterns"""
        
        # Check for SQL injection patterns in URL
        sql_patterns = [
            "union select", "drop table", "delete from", "insert into",
            "update set", "exec(", "script>", "javascript:", "vbscript:",
            "onload=", "onerror=", "<iframe", "<object", "<embed"
        ]
        
        url_path = request.url.path.lower()
        query_string = str(request.url.query).lower()
        
        for pattern in sql_patterns:
            if pattern in url_path or pattern in query_string:
                return True
        
        # Check for path traversal
        if "../" in url_path or "..%2f" in url_path or "..%5c" in url_path:
            return True
        
        # Check for excessive path length
        if len(url_path) > 2000:
            return True
        
        # Check user agent
        user_agent = request.headers.get("user-agent", "").lower()
        suspicious_agents = [
            "sqlmap", "nikto", "dirbuster", "burp", "nessus",
            "whatweb", "wpscan", "metasploit"
        ]
        
        for agent in suspicious_agents:
            if agent in user_agent:
                return True
        
        return False
    
    def _sanitize_header_value(self, value: str) -> str:
        """Sanitize header value"""
        
        # Remove dangerous characters
        dangerous_chars = ["\r", "\n", "\x00"]
        for char in dangerous_chars:
            value = value.replace(char, "")
        
        return value[:1000]  # Limit length
    
    def get_client_info(self, request: Request) -> dict:
        """Extract client information safely"""
        
        return {
            "ip": self._get_client_ip(request),
            "user_agent": self._sanitize_header_value(
                request.headers.get("user-agent", "")[:500]
            ),
            "referer": self._sanitize_header_value(
                request.headers.get("referer", "")[:500]
            ),
            "accept_language": self._sanitize_header_value(
                request.headers.get("accept-language", "")[:100]
            )
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address safely"""
        
        # Check for forwarded IP (from load balancer/proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP (client)
            ip = forwarded_for.split(",")[0].strip()
            # Basic validation
            parts = ip.split(".")
            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                return ip
        
        # Check for real IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"

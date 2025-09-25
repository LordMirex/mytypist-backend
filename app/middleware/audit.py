"""
Audit logging middleware
"""

import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.services.audit_service import AuditService
from app.models.audit import AuditEventType, AuditLevel


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic audit logging"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Routes that should be audited
        self.audit_routes = [
            "/api/auth/",
            "/api/documents/",
            "/api/templates/",
            "/api/signatures/",
            "/api/payments/",
            "/api/admin/"
        ]
        
        # Sensitive routes that require detailed logging
        self.sensitive_routes = [
            "/api/auth/login",
            "/api/auth/register",
            "/api/payments/",
            "/api/admin/",
            "/api/documents/shared/",
            "/api/signatures/external/"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through audit middleware"""
        
        # Record start time
        start_time = time.time()
        
        # Check if route should be audited
        should_audit = self._should_audit_route(request.url.path)
        is_sensitive = self._is_sensitive_route(request.url.path)
        
        # Get request details for audit
        request_details = None
        if should_audit:
            request_details = await self._extract_request_details(request)
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log audit event if needed
        if should_audit:
            await self._log_audit_event(
                request, response, request_details, processing_time, is_sensitive
            )
        
        return response
    
    def _should_audit_route(self, path: str) -> bool:
        """Check if route should be audited"""
        
        for audit_route in self.audit_routes:
            if path.startswith(audit_route):
                return True
        
        return False
    
    def _is_sensitive_route(self, path: str) -> bool:
        """Check if route is sensitive"""
        
        for sensitive_route in self.sensitive_routes:
            if path.startswith(sensitive_route):
                return True
        
        return False
    
    async def _extract_request_details(self, request: Request) -> dict:
        """Extract request details for audit"""
        
        details = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "content_type": request.headers.get("content-type"),
            "content_length": request.headers.get("content-length")
        }
        
        # Remove sensitive headers
        sensitive_headers = ["authorization", "cookie", "x-api-key"]
        for header in sensitive_headers:
            if header in details["headers"]:
                details["headers"][header] = "[REDACTED]"
        
        return details
    
    async def _log_audit_event(
        self, 
        request: Request, 
        response: Response, 
        request_details: dict,
        processing_time: float,
        is_sensitive: bool
    ):
        """Log audit event"""
        
        try:
            # Determine event type and level
            event_type, event_level = self._determine_event_type_and_level(
                request, response, is_sensitive
            )
            
            # Get user ID if available
            user_id = None
            if hasattr(request.state, 'current_user') and request.state.current_user:
                user_id = request.state.current_user.id
            
            # Prepare event details
            event_details = {
                "request": request_details,
                "response": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "processing_time": processing_time
                },
                "performance": {
                    "processing_time": processing_time,
                    "slow_request": processing_time > 2.0
                }
            }
            
            # Remove sensitive response data
            if "set-cookie" in event_details["response"]["headers"]:
                event_details["response"]["headers"]["set-cookie"] = "[REDACTED]"
            
            # Create audit message
            message = f"{request.method} {request.url.path} - {response.status_code}"
            
            # Log the event
            AuditService.log_event(
                event_type=event_type,
                event_level=event_level,
                event_message=message,
                user_id=user_id,
                request=request,
                event_details=event_details,
                resource_type=self._extract_resource_type(request.url.path),
                processing_time=processing_time
            )
        
        except Exception as e:
            # Don't let audit logging break the request
            print(f"Audit logging error: {e}")
    
    def _determine_event_type_and_level(
        self, 
        request: Request, 
        response: Response, 
        is_sensitive: bool
    ) -> tuple[AuditEventType, AuditLevel]:
        """Determine audit event type and level"""
        
        # Determine level based on response status
        if response.status_code >= 500:
            level = AuditLevel.ERROR
        elif response.status_code >= 400:
            level = AuditLevel.WARNING
        elif is_sensitive:
            level = AuditLevel.WARNING
        else:
            level = AuditLevel.INFO
        
        # Determine event type based on path and method
        path = request.url.path
        method = request.method
        
        if "/auth/login" in path:
            if response.status_code == 200:
                return AuditEventType.LOGIN, level
            else:
                return AuditEventType.LOGIN_FAILED, level
        elif "/auth/register" in path:
            return AuditEventType.USER_CREATED, level
        elif "/documents/" in path:
            if method == "POST":
                return AuditEventType.DOCUMENT_CREATED, level
            elif method == "GET":
                return AuditEventType.DOCUMENT_VIEWED, level
            elif method in ["PUT", "PATCH"]:
                return AuditEventType.DOCUMENT_UPDATED, level
            elif method == "DELETE":
                return AuditEventType.DOCUMENT_DELETED, level
        elif "/templates/" in path:
            if method == "POST":
                return AuditEventType.TEMPLATE_CREATED, level
            elif method in ["PUT", "PATCH"]:
                return AuditEventType.TEMPLATE_UPDATED, level
            elif method == "DELETE":
                return AuditEventType.TEMPLATE_DELETED, level
        elif "/signatures/" in path:
            if method == "POST":
                return AuditEventType.SIGNATURE_ADDED, level
        elif "/payments/" in path:
            if method == "POST":
                return AuditEventType.PAYMENT_INITIATED, level
        elif "/admin/" in path:
            return AuditEventType.SYSTEM_ERROR, AuditLevel.WARNING  # Admin actions
        
        # Default event type
        if response.status_code >= 400:
            return AuditEventType.SYSTEM_ERROR, level
        else:
            return AuditEventType.SYSTEM_STARTUP, level  # Generic system event
    
    def _extract_resource_type(self, path: str) -> str:
        """Extract resource type from path"""
        
        if "/documents/" in path:
            return "document"
        elif "/templates/" in path:
            return "template"
        elif "/signatures/" in path:
            return "signature"
        elif "/payments/" in path:
            return "payment"
        elif "/users/" in path or "/auth/" in path:
            return "user"
        elif "/admin/" in path:
            return "admin"
        else:
            return "system"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return request.client.host if request.client else "unknown"

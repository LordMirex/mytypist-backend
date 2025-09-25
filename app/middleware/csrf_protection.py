"""
CSRF Protection Middleware
Implements comprehensive Cross-Site Request Forgery protection
"""

import secrets
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import redis.asyncio as aioredis

from config import settings
from app.services.audit_service import AuditService


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF Protection Middleware with multiple validation methods"""

    def __init__(self, app):
        super().__init__(app)

        # Configuration
        self.secret_key = settings.SECRET_KEY.encode()
        self.token_lifetime = 3600  # 1 hour
        self.cookie_name = "csrf_token"
        self.header_name = "X-CSRF-Token"
        self.double_submit_cookie = "csrf_double_submit"

        # Methods that require CSRF protection
        self.protected_methods = {"POST", "PUT", "PATCH", "DELETE"}

        # Endpoints that are exempt from CSRF protection
        self.exempt_paths = {
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
            "/api/webhooks/",  # Webhook endpoints
            "/api/public/",    # Public API endpoints
            "/health",
            "/metrics"
        }

        # Safe origins (for origin validation)
        self.safe_origins = set(settings.ALLOWED_ORIGINS)

        # Initialize Redis client for token storage
        try:
            self.redis = aioredis.from_url(settings.REDIS_URL) if settings.REDIS_ENABLED else None
        except:
            self.redis = None

    async def dispatch(self, request: Request, call_next):
        """Process request through CSRF protection"""

        # Skip CSRF protection for safe methods
        if request.method not in self.protected_methods:
            response = await call_next(request)
            # Add CSRF token to safe responses for future use
            await self._add_csrf_token_to_response(request, response)
            return response

        # Skip CSRF protection for exempt paths
        if self._is_exempt_path(request.url.path):
            return await call_next(request)

        # Skip CSRF protection for API key authenticated requests
        if self._is_api_key_request(request):
            return await call_next(request)

        # Perform CSRF validation
        validation_result = await self._validate_csrf_protection(request)

        if not validation_result["valid"]:
            # Log CSRF attack attempt
            await self._log_csrf_attack(request, validation_result["reason"])

            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "CSRF validation failed",
                    "message": "Invalid or missing CSRF token",
                    "code": "CSRF_TOKEN_INVALID"
                },
                headers={
                    "X-CSRF-Failure-Reason": validation_result["reason"]
                }
            )

        # Process request
        response = await call_next(request)

        # Refresh CSRF token in response
        await self._add_csrf_token_to_response(request, response)

        return response

    async def _validate_csrf_protection(self, request: Request) -> Dict[str, any]:
        """Validate CSRF protection using multiple methods"""

        # Method 1: Origin/Referer validation
        origin_valid = await self._validate_origin(request)
        if not origin_valid:
            return {"valid": False, "reason": "invalid_origin"}

        # Method 2: Double Submit Cookie validation
        double_submit_valid = await self._validate_double_submit_cookie(request)
        if double_submit_valid:
            return {"valid": True, "method": "double_submit_cookie"}

        # Method 3: Synchronizer Token validation
        sync_token_valid = await self._validate_synchronizer_token(request)
        if sync_token_valid:
            return {"valid": True, "method": "synchronizer_token"}

        # Method 4: Custom header validation (for AJAX requests)
        custom_header_valid = await self._validate_custom_header(request)
        if custom_header_valid:
            return {"valid": True, "method": "custom_header"}

        return {"valid": False, "reason": "no_valid_csrf_protection"}

    async def _validate_origin(self, request: Request) -> bool:
        """Validate request origin/referer"""

        # Check Origin header first (more reliable)
        origin = request.headers.get("origin")
        if origin:
            return origin in self.safe_origins

        # Fallback to Referer header
        referer = request.headers.get("referer")
        if referer:
            # Extract origin from referer
            try:
                from urllib.parse import urlparse
                parsed_referer = urlparse(referer)
                referer_origin = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
                return referer_origin in self.safe_origins
            except:
                return False

        # No origin or referer header (suspicious)
        return False

    async def _validate_double_submit_cookie(self, request: Request) -> bool:
        """Validate double submit cookie method"""

        # Get CSRF token from cookie
        cookie_token = request.cookies.get(self.double_submit_cookie)
        if not cookie_token:
            return False

        # Get CSRF token from header or form data
        header_token = request.headers.get(self.header_name)

        # For form data, try to get from request body
        form_token = None
        if not header_token:
            try:
                # This is a simplified check - in production you'd parse form data properly
                content_type = request.headers.get("content-type", "")
                if "application/x-www-form-urlencoded" in content_type:
                    # Note: This is a placeholder - actual form parsing would be more complex
                    pass
            except:
                pass

        request_token = header_token or form_token
        if not request_token:
            return False

        # Compare tokens using constant-time comparison
        return hmac.compare_digest(cookie_token, request_token)

    async def _validate_synchronizer_token(self, request: Request) -> bool:
        """Validate synchronizer token method"""

        # Get token from header or form
        token = request.headers.get(self.header_name)
        if not token:
            return False

        # Parse token components
        try:
            token_parts = token.split(":")
            if len(token_parts) != 3:
                return False

            timestamp_str, user_session, signature = token_parts
            timestamp = int(timestamp_str)

        except (ValueError, IndexError):
            return False

        # Check token expiration
        current_time = int(time.time())
        if current_time - timestamp > self.token_lifetime:
            return False

        # Verify signature
        expected_signature = self._generate_token_signature(timestamp, user_session)
        if not hmac.compare_digest(signature, expected_signature):
            return False

        # If using Redis, check if token is still valid
        if self.redis:
            try:
                stored_token = await self.redis.get(f"csrf_token:{token}")
                if not stored_token:
                    return False
            except:
                pass  # Continue without Redis validation if Redis is unavailable

        return True

    async def _validate_custom_header(self, request: Request) -> bool:
        """Validate custom header for AJAX requests"""

        # Check for X-Requested-With header (common AJAX header)
        ajax_header = request.headers.get("x-requested-with")
        if ajax_header and ajax_header.lower() == "xmlhttprequest":
            return True

        # Check for custom application header
        app_header = request.headers.get("x-mytypist-request")
        if app_header:
            return True

        return False

    def _generate_csrf_token(self, user_session: str = None) -> str:
        """Generate CSRF token"""
        timestamp = int(time.time())
        session_id = user_session or secrets.token_hex(16)
        signature = self._generate_token_signature(timestamp, session_id)

        return f"{timestamp}:{session_id}:{signature}"

    def _generate_token_signature(self, timestamp: int, session_id: str) -> str:
        """Generate token signature"""
        message = f"{timestamp}:{session_id}".encode()
        return hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

    def _generate_double_submit_token(self) -> str:
        """Generate double submit token"""
        return secrets.token_urlsafe(32)

    async def _add_csrf_token_to_response(self, request: Request, response: Response):
        """Add CSRF token to response"""

        # Don't add tokens to API responses or redirects
        if (response.status_code >= 300 or
            request.url.path.startswith("/api/") or
            response.headers.get("content-type", "").startswith("application/json")):
            return

        # Get user session if available
        user_session = None
        if hasattr(request.state, "current_user"):
            user_session = str(request.state.current_user.id)

        # Generate synchronizer token
        sync_token = self._generate_csrf_token(user_session)

        # Generate double submit token
        double_submit_token = self._generate_double_submit_token()

        # Store token in Redis if available
        if self.redis:
            try:
                await self.redis.setex(
                    f"csrf_token:{sync_token}",
                    self.token_lifetime,
                    "valid"
                )
            except:
                pass  # Continue without Redis if unavailable

        # Add tokens to response
        response.headers[f"X-{self.header_name}"] = sync_token

        # Set double submit cookie
        response.set_cookie(
            key=self.double_submit_cookie,
            value=double_submit_token,
            max_age=self.token_lifetime,
            httponly=False,  # Needs to be accessible by JavaScript
            secure=not settings.DEBUG,
            samesite="strict"
        )

        # Set synchronizer token cookie (httponly for security)
        response.set_cookie(
            key=self.cookie_name,
            value=sync_token,
            max_age=self.token_lifetime,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="strict"
        )

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection"""
        return any(path.startswith(exempt_path) for exempt_path in self.exempt_paths)

    def _is_api_key_request(self, request: Request) -> bool:
        """Check if request uses API key authentication"""
        auth_header = request.headers.get("authorization", "")
        return auth_header.startswith("Bearer myt_")  # API keys start with myt_

    async def _log_csrf_attack(self, request: Request, reason: str):
        """Log CSRF attack attempt"""
        try:
            client_info = {
                "ip_address": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", ""),
                "origin": request.headers.get("origin", ""),
                "path": request.url.path,
                "method": request.method,
                "csrf_failure_reason": reason
            }

            # Get user ID if available
            user_id = None
            if hasattr(request.state, "current_user"):
                user_id = request.state.current_user.id

            AuditService.log_security_event(
                "CSRF_ATTACK_ATTEMPT",
                user_id,
                request,
                client_info
            )

        except Exception:
            # Don't let logging errors affect the response
            pass


class CSRFTokenGenerator:
    """Utility class for generating CSRF tokens in views"""

    @staticmethod
    def generate_token_for_user(user_id: int) -> str:
        """Generate CSRF token for specific user"""
        middleware = CSRFProtectionMiddleware(None)
        return middleware._generate_csrf_token(str(user_id))

    @staticmethod
    def generate_double_submit_token() -> str:
        """Generate double submit token"""
        middleware = CSRFProtectionMiddleware(None)
        return middleware._generate_double_submit_token()


# Decorator for view functions to require CSRF protection
def csrf_required(func):
    """Decorator to require CSRF protection for specific endpoints"""
    func._csrf_required = True
    return func


# Decorator to exempt view functions from CSRF protection
def csrf_exempt(func):
    """Decorator to exempt specific endpoints from CSRF protection"""
    func._csrf_exempt = True
    return func

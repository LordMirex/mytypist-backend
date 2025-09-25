"""Guest session middleware for anonymous users"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.utils.guest_session import get_or_create_guest_session


class GuestSessionMiddleware(BaseHTTPMiddleware):
    """Middleware to handle anonymous guest sessions"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip for authenticated requests
        if request.cookies.get("access_token"):
            return await call_next(request)
            
        # Get or create guest session
        session_id = await get_or_create_guest_session(request)
        
        # Process request
        response = await call_next(request)
        
        # Set guest session cookie if not present
        if not request.cookies.get("guest_session_id"):
            response.set_cookie(
                "guest_session_id",
                session_id,
                max_age=86400,  # 24 hours
                httponly=True,
                samesite="strict"
            )
        
        return response
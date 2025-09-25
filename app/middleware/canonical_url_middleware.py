"""
Middleware for handling canonical URLs and redirects
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from app.services.url_service import URLService

class CanonicalURLMiddleware(BaseHTTPMiddleware):
    """Middleware for handling canonical URLs and redirects"""
    
    def __init__(self, app):
        super().__init__(app)
        self.url_service = URLService()
    
    async def dispatch(self, request: Request, call_next):
        """Process request and handle URL canonicalization"""
        # Check if URL should redirect to canonical version
        redirect_url = self.url_service.should_redirect(request)
        if redirect_url:
            return RedirectResponse(url=redirect_url, status_code=301)
            
        # Proceed with request
        response = await call_next(request)
        
        # Add canonical URL header for all responses
        canonical_url = self.url_service.get_canonical_url(request)
        response.headers['Link'] = f'<{canonical_url}>; rel="canonical"'
        
        # Add alternate URLs if they exist
        alternates = self.url_service.get_alternate_urls(request)
        if alternates:
            for rel, url in alternates.items():
                response.headers['Link'] += f', <{url}>; rel="alternate"; media="{rel}"'
        
        return response
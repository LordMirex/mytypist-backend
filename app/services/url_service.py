"""
URL handling service for canonical URLs and redirects
"""
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs
from fastapi import Request

class URLService:
    """Service for handling URLs and canonicalization"""
    
    def __init__(self, base_url: str = "https://mytypist.net"):
        self.base_url = base_url
    
    def get_canonical_url(self, request: Request) -> str:
        """Get canonical URL for the current request"""
        # Start with the path
        path = request.url.path
        
        # Remove trailing slashes
        path = path.rstrip('/')
        
        # Handle pagination
        query_params = dict(request.query_params)
        if 'page' in query_params and query_params['page'] == '1':
            del query_params['page']
            
        # Build canonical query string
        canonical_params = []
        for key in sorted(query_params.keys()):
            if key not in ['utm_source', 'utm_medium', 'utm_campaign', 'fbclid', 'ref']:
                value = query_params[key]
                canonical_params.append(f"{key}={value}")
                
        # Combine path and query
        if canonical_params:
            path = f"{path}?{'&'.join(canonical_params)}"
            
        # Join with base URL
        return urljoin(self.base_url, path)
    
    def should_redirect(self, request: Request) -> Optional[str]:
        """Check if the current URL should redirect to a canonical version"""
        current_url = str(request.url)
        canonical_url = self.get_canonical_url(request)
        
        # Check if URLs are different
        if current_url != canonical_url:
            # Check specific cases that require redirection
            current_parsed = urlparse(current_url)
            
            # Redirect if:
            # 1. Has trailing slash
            # 2. Has page=1 in query
            # 3. Has tracking parameters
            # 4. Query parameters are not in canonical order
            if (current_parsed.path != current_parsed.path.rstrip('/') or
                'page=1' in current_parsed.query or
                any(param in current_parsed.query for param in ['utm_source', 'fbclid', 'ref']) or
                '&'.join(sorted(parse_qs(current_parsed.query).keys())) != 
                '&'.join(parse_qs(current_parsed.query).keys())):
                return canonical_url
                
        return None
    
    def get_alternate_urls(self, request: Request) -> dict:
        """Get alternate URLs for different versions of the page"""
        path = request.url.path
        alternates = {}
        
        # Add mobile version if relevant
        if not path.startswith('/m/'):
            alternates['mobile'] = urljoin(self.base_url, f"/m{path}")
            
        # Add AMP version if relevant
        if not path.startswith('/amp/'):
            alternates['amp'] = urljoin(self.base_url, f"/amp{path}")
            
        return alternates
"""
SEO middleware for injecting meta tags into responses
"""
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.services.seo_service import SEOService, SEOMetadata
from app.models.document import Document
from app.models.template import Template

class SEOMiddleware(BaseHTTPMiddleware):
    """Middleware for injecting SEO meta tags into HTML responses"""

    def __init__(self, app, seo_service: SEOService):
        super().__init__(app)
        self.seo_service = seo_service

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and inject SEO meta tags"""
        response = await call_next(request)

        # Only process HTML responses
        if "text/html" not in response.media_type:
            return response

        # Get metadata based on the current route
        metadata = await self._get_metadata_for_route(request)
        if not metadata:
            return response

        # Generate meta tags
        meta_tags = self.seo_service.generate_meta_tags(metadata)

        # Inject meta tags into HTML response
        body = await self._inject_meta_tags(response, meta_tags)
        response.body = body

        return response

    async def _get_metadata_for_route(self, request: Request) -> Optional[SEOMetadata]:
        """Get SEO metadata based on the current route"""
        path = request.url.path

        # Document page
        if path.startswith("/document/"):
            document_id = path.split("/")[-1]
            document = await self._get_document(request, document_id)
            if document:
                return self.seo_service.get_document_metadata(document)

        # Template page
        elif path.startswith("/template/"):
            template_id = path.split("/")[-1]
            template = await self._get_template(request, template_id)
            if template:
                return self.seo_service.get_template_metadata(template)

        # Static pages
        elif path in ["/about", "/pricing", "/contact"]:
            descriptions = {
                "/about": "Learn about MyTypist's document automation platform",
                "/pricing": "MyTypist pricing plans and features",
                "/contact": "Contact MyTypist support team"
            }
            page_name = path.strip("/").title()
            return self.seo_service.get_page_metadata(page_name, descriptions[path])

        return None

    async def _get_document(self, request: Request, document_id: str):
        """Get document from database"""
        async with request.app.state.db() as db:
            from app.models.document import Document
            return await db.query(Document).filter(Document.id == document_id).first()

    async def _get_template(self, request: Request, template_id: str):
        """Get template from database"""
        async with request.app.state.db() as db:
            from app.models.template import Template
            return await db.query(Template).filter(Template.id == template_id).first()

    async def _inject_meta_tags(self, response: Response, meta_tags: dict) -> bytes:
        """Inject meta tags into HTML response"""
        html = response.body.decode()
        meta_tags_html = "\n".join([
            f'<meta name="{name}" content="{content}">'
            for name, content in meta_tags.items()
        ])

        # Insert meta tags after head tag
        head_pos = html.find("</head>")
        if head_pos != -1:
            html = html[:head_pos] + meta_tags_html + html[head_pos:]

        return html.encode()

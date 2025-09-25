"""
Sitemap generation service for SEO optimization
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.template import Template
from urllib.parse import urljoin

class SitemapGenerator:
    """Service for generating XML sitemaps"""
    
    def __init__(self, base_url: str = "https://mytypist.net"):
        self.base_url = base_url
        self.static_pages = [
            {"url": "/", "changefreq": "daily", "priority": "1.0"},
            {"url": "/about", "changefreq": "monthly", "priority": "0.8"},
            {"url": "/pricing", "changefreq": "weekly", "priority": "0.9"},
            {"url": "/contact", "changefreq": "monthly", "priority": "0.7"},
            {"url": "/templates", "changefreq": "daily", "priority": "0.9"},
            {"url": "/blog", "changefreq": "weekly", "priority": "0.8"},
            {"url": "/faq", "changefreq": "weekly", "priority": "0.8"}
        ]
    
    def generate_sitemap(self, db: Session) -> str:
        """Generate complete XML sitemap"""
        # Start XML sitemap
        sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        # Add static pages
        for page in self.static_pages:
            sitemap += self._create_url_entry(
                urljoin(self.base_url, page["url"]),
                page["changefreq"],
                page["priority"]
            )
        
        # Add public documents
        documents = db.query(Document).filter(
            Document.is_public == True
        ).all()
        
        for doc in documents:
            sitemap += self._create_url_entry(
                urljoin(self.base_url, f"/document/{doc.id}"),
                "weekly",
                "0.7",
                doc.updated_at
            )
        
        # Add public templates
        templates = db.query(Template).filter(
            Template.is_public == True
        ).all()
        
        for template in templates:
            sitemap += self._create_url_entry(
                urljoin(self.base_url, f"/template/{template.id}"),
                "weekly",
                "0.8",
                template.updated_at
            )
        
        # Close sitemap
        sitemap += '</urlset>'
        return sitemap
    
    def _create_url_entry(
        self,
        url: str,
        changefreq: str,
        priority: str,
        lastmod: Optional[datetime] = None
    ) -> str:
        """Create a single URL entry for the sitemap"""
        entry = '  <url>\n'
        entry += f'    <loc>{url}</loc>\n'
        
        if lastmod:
            entry += f'    <lastmod>{lastmod.strftime("%Y-%m-%d")}</lastmod>\n'
            
        entry += f'    <changefreq>{changefreq}</changefreq>\n'
        entry += f'    <priority>{priority}</priority>\n'
        entry += '  </url>\n'
        
        return entry
"""
SEO Service for generating meta tags and OpenGraph data
"""
from typing import Dict, Optional, List
from urllib.parse import urljoin
from pydantic import BaseModel, HttpUrl

class SEOMetadata(BaseModel):
    """SEO metadata model"""
    title: str
    description: str
    keywords: List[str]
    image: Optional[HttpUrl]
    type: str = "website"
    site_name: str = "MyTypist"
    canonical_url: Optional[HttpUrl]

class SEOService:
    """Service for generating SEO metadata and OpenGraph tags"""
    
    def __init__(self, base_url: str = "https://mytypist.net"):
        self.base_url = base_url
    
    def get_document_metadata(self, document) -> SEOMetadata:
        """Generate SEO metadata for a document"""
        title = f"{document.title} - MyTypist"
        description = (document.description[:157] + "...") if len(document.description) > 160 else document.description
        keywords = ["document", "template", "automation"]
        
        # Add document-specific keywords
        if hasattr(document, "tags"):
            keywords.extend(document.tags)
        
        image_url = urljoin(self.base_url, f"/previews/{document.id}.png") if document.is_public else None
        canonical_url = urljoin(self.base_url, f"/documents/{document.id}")
        
        return SEOMetadata(
            title=title,
            description=description,
            keywords=keywords,
            image=image_url,
            canonical_url=canonical_url,
            type="article"
        )
    
    def get_template_metadata(self, template) -> SEOMetadata:
        """Generate SEO metadata for a template"""
        title = f"{template.title} Template - MyTypist"
        description = (template.description[:157] + "...") if len(template.description) > 160 else template.description
        keywords = ["template", "document", "automation"]
        
        # Add template-specific keywords
        if hasattr(template, "tags"):
            keywords.extend(template.tags)
            
        image_url = urljoin(self.base_url, f"/templates/{template.id}/preview.png")
        canonical_url = urljoin(self.base_url, f"/templates/{template.id}")
        
        return SEOMetadata(
            title=title,
            description=description,
            keywords=keywords,
            image=image_url,
            canonical_url=canonical_url,
            type="article"
        )
    
    def get_page_metadata(self, page_name: str, description: str) -> SEOMetadata:
        """Generate SEO metadata for static pages"""
        title = f"{page_name} - MyTypist"
        canonical_url = urljoin(self.base_url, page_name.lower().replace(" ", "-"))
        
        return SEOMetadata(
            title=title,
            description=description,
            keywords=["document automation", "MyTypist", "templates", "e-signatures"],
            canonical_url=canonical_url
        )
    
    def generate_meta_tags(self, metadata: SEOMetadata) -> Dict[str, str]:
        """Generate HTML meta tags from metadata"""
        meta_tags = {
            "title": metadata.title,
            "description": metadata.description,
            "keywords": ", ".join(metadata.keywords),
            "og:title": metadata.title,
            "og:description": metadata.description,
            "og:type": metadata.type,
            "og:site_name": metadata.site_name
        }
        
        if metadata.image:
            meta_tags["og:image"] = str(metadata.image)
            meta_tags["twitter:card"] = "summary_large_image"
            meta_tags["twitter:image"] = str(metadata.image)
        
        if metadata.canonical_url:
            meta_tags["canonical"] = str(metadata.canonical_url)
        
        return meta_tags
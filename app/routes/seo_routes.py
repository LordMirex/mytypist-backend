"""
Routes for SEO-related endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi.responses import Response
from database import get_db
from app.services.sitemap_generator import SitemapGenerator

router = APIRouter()
sitemap_generator = SitemapGenerator()

@router.get("/sitemap.xml")
async def get_sitemap(db: Session = Depends(get_db)):
    """
    Generate and serve XML sitemap
    """
    sitemap = sitemap_generator.generate_sitemap(db)
    return Response(
        content=sitemap,
        media_type="application/xml"
    )
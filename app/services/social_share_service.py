"""
Social sharing service for generating previews and tracking engagement
"""
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import qrcode
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.visit import Visit
from app.utils.image_utils import add_watermark

class SocialPreviewGenerator:
    """Generate social media preview images for documents and templates"""
    
    def __init__(self):
        self.preview_size = (1200, 630)  # Facebook/Twitter optimal size
        self.logo_path = "storage/assets/logo.png"
        self.font_path = "storage/assets/fonts/Inter-Bold.ttf"
        
    def generate_document_preview(
        self,
        document: Document,
        db: Session,
        include_qr: bool = True
    ) -> BytesIO:
        """Generate a social preview image for a document"""
        # Create base image
        img = Image.new("RGB", self.preview_size, color="#FFFFFF")
        draw = ImageDraw.Draw(img)
        
        # Add logo
        logo = Image.open(self.logo_path)
        logo_size = (100, 100)
        logo = logo.resize(logo_size)
        logo_pos = (50, 50)
        img.paste(logo, logo_pos, logo)
        
        # Add title
        font = ImageFont.truetype(self.font_path, 60)
        title = document.title
        if len(title) > 50:
            title = title[:47] + "..."
        draw.text((200, 50), title, font=font, fill="#000000")
        
        # Add description
        font_small = ImageFont.truetype(self.font_path, 30)
        desc = document.description or ""
        if len(desc) > 120:
            desc = desc[:117] + "..."
        draw.text((200, 150), desc, font=font_small, fill="#666666")
        
        # Add QR code if requested
        if include_qr:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(f"https://mytypist.net/document/{document.id}")
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_pos = (self.preview_size[0] - 200, self.preview_size[1] - 200)
            img.paste(qr_img, qr_pos)
        
        # Add watermark for non-downloaded documents
        if not document.is_downloaded:
            img = add_watermark(img, "MyTypist Preview")
        
        # Save to BytesIO
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output

class SocialShareTracker:
    """Track social media sharing engagement"""
    
    def track_share(
        self,
        db: Session,
        document_id: int,
        platform: str,
        referrer: Optional[str] = None
    ) -> Visit:
        """Track a social share event"""
        visit = Visit(
            document_id=document_id,
            visit_type="share",
            utm_source=platform,
            referrer=referrer,
            visit_metadata={
                "platform": platform,
                "shared_at": datetime.utcnow().isoformat()
            }
        )
        db.add(visit)
        db.commit()
        return visit
    
    def get_sharing_stats(self, db: Session, document_id: int) -> dict:
        """Get sharing statistics for a document"""
        shares = db.query(Visit).filter(
            Visit.document_id == document_id,
            Visit.visit_type == "share"
        ).all()
        
        stats = {
            "total_shares": len(shares),
            "by_platform": {},
            "by_date": {}
        }
        
        for share in shares:
            # Count by platform
            platform = share.utm_source or "direct"
            stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1
            
            # Count by date
            date = share.visited_at.date().isoformat()
            stats["by_date"][date] = stats["by_date"].get(date, 0) + 1
        
        return stats
"""
Production-Ready Document Thumbnail Generation Service
Real thumbnail generation for documents with multiple format support
"""

import logging
import os
import asyncio
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import tempfile
from io import BytesIO
import base64

# Image processing
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    PIL_AVAILABLE = False

# PDF processing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None
    PYMUPDF_AVAILABLE = False

# Alternative PDF processing
try:
    from pdf2image import convert_from_path, convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    convert_from_path = None
    convert_from_bytes = None
    PDF2IMAGE_AVAILABLE = False

# Document processing
try:
    from docx import Document as DocxDocument
    from docx.shared import Inches
    DOCX_AVAILABLE = True
except ImportError:
    DocxDocument = None
    DOCX_AVAILABLE = False

from config import settings

logger = logging.getLogger(__name__)


class ThumbnailService:
    """Production-ready document thumbnail generation service"""

    def __init__(self):
        self.thumbnail_size = (300, 400)  # Standard thumbnail size
        self.quality = 85
        self.cache_dir = Path(getattr(settings, 'THUMBNAILS_PATH', 'storage/thumbnails'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Check available libraries
        self.available_processors = self._check_available_processors()
        logger.info(f"Thumbnail processors available: {list(self.available_processors.keys())}")

    def _check_available_processors(self) -> Dict[str, bool]:
        """Check which thumbnail processors are available"""
        return {
            'pil': PIL_AVAILABLE,
            'pymupdf': PYMUPDF_AVAILABLE,
            'pdf2image': PDF2IMAGE_AVAILABLE,
            'docx': DOCX_AVAILABLE
        }

    async def generate_thumbnail(
        self,
        document_id: int,
        file_path: str,
        file_format: str,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """Generate thumbnail for document"""

        try:
            # Check cache first
            cached_thumbnail = await self._get_cached_thumbnail(document_id, force_regenerate)
            if cached_thumbnail and not force_regenerate:
                return cached_thumbnail

            # Validate file exists
            if not os.path.exists(file_path):
                return await self._generate_placeholder_thumbnail(document_id, "File not found")

            # Generate thumbnail based on file format
            thumbnail_result = await self._generate_thumbnail_by_format(
                file_path, file_format, document_id
            )

            if thumbnail_result['success']:
                # Cache the thumbnail
                await self._cache_thumbnail(document_id, thumbnail_result)

                return {
                    'success': True,
                    'thumbnail_url': thumbnail_result['thumbnail_url'],
                    'thumbnail_path': thumbnail_result['thumbnail_path'],
                    'file_size': thumbnail_result.get('file_size', 0),
                    'dimensions': thumbnail_result.get('dimensions', self.thumbnail_size)
                }
            else:
                # Generate placeholder thumbnail
                return await self._generate_placeholder_thumbnail(
                    document_id,
                    thumbnail_result.get('error', 'Unknown error')
                )

        except Exception as e:
            logger.error(f"Thumbnail generation failed for document {document_id}: {e}")
            return await self._generate_placeholder_thumbnail(document_id, str(e))

    async def _generate_thumbnail_by_format(
        self,
        file_path: str,
        file_format: str,
        document_id: int
    ) -> Dict[str, Any]:
        """Generate thumbnail based on file format"""

        file_format = file_format.lower()

        if file_format == 'pdf':
            return await self._generate_pdf_thumbnail(file_path, document_id)
        elif file_format in ['docx', 'doc']:
            return await self._generate_docx_thumbnail(file_path, document_id)
        elif file_format in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
            return await self._generate_image_thumbnail(file_path, document_id)
        elif file_format in ['txt', 'rtf']:
            return await self._generate_text_thumbnail(file_path, document_id)
        else:
            return await self._generate_generic_thumbnail(file_path, file_format, document_id)

    async def _generate_pdf_thumbnail(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """Generate thumbnail from PDF file"""

        try:
            # Try PyMuPDF first (faster and more reliable)
            if self.available_processors['pymupdf']:
                return await self._generate_pdf_thumbnail_pymupdf(file_path, document_id)

            # Fallback to pdf2image
            elif self.available_processors['pdf2image']:
                return await self._generate_pdf_thumbnail_pdf2image(file_path, document_id)

            else:
                return {'success': False, 'error': 'No PDF processing libraries available'}

        except Exception as e:
            logger.error(f"PDF thumbnail generation failed: {e}")
            return {'success': False, 'error': str(e)}

    async def _generate_pdf_thumbnail_pymupdf(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """Generate PDF thumbnail using PyMuPDF"""

        try:
            # Open PDF
            pdf_document = fitz.open(file_path)

            if pdf_document.page_count == 0:
                return {'success': False, 'error': 'PDF has no pages'}

            # Get first page
            first_page = pdf_document[0]

            # Render page as image
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = first_page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(BytesIO(img_data))

            # Resize to thumbnail size
            image.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

            # Save thumbnail
            thumbnail_path = self.cache_dir / f"doc_{document_id}_thumb.png"
            image.save(thumbnail_path, "PNG", quality=self.quality)

            pdf_document.close()

            return {
                'success': True,
                'thumbnail_path': str(thumbnail_path),
                'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                'file_size': thumbnail_path.stat().st_size,
                'dimensions': image.size,
                'page_count': pdf_document.page_count
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _generate_pdf_thumbnail_pdf2image(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """Generate PDF thumbnail using pdf2image"""

        try:
            # Convert first page to image
            images = convert_from_path(file_path, first_page=1, last_page=1, dpi=150)

            if not images:
                return {'success': False, 'error': 'Could not convert PDF page'}

            image = images[0]

            # Resize to thumbnail size
            image.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

            # Save thumbnail
            thumbnail_path = self.cache_dir / f"doc_{document_id}_thumb.png"
            image.save(thumbnail_path, "PNG", quality=self.quality)

            return {
                'success': True,
                'thumbnail_path': str(thumbnail_path),
                'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                'file_size': thumbnail_path.stat().st_size,
                'dimensions': image.size
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _generate_docx_thumbnail(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """Generate thumbnail from DOCX file"""

        try:
            if not self.available_processors['docx'] or not self.available_processors['pil']:
                return {'success': False, 'error': 'DOCX processing not available'}

            # Read DOCX content
            doc = DocxDocument(file_path)

            # Extract text from first few paragraphs
            text_content = []
            for paragraph in doc.paragraphs[:10]:  # First 10 paragraphs
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())

            content_text = '\n'.join(text_content)

            if not content_text:
                content_text = "Document content preview not available"

            # Create thumbnail image with text
            return await self._create_text_thumbnail(content_text, document_id, "DOCX Document")

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _generate_image_thumbnail(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """Generate thumbnail from image file"""

        try:
            if not self.available_processors['pil']:
                return {'success': False, 'error': 'Image processing not available'}

            # Open and resize image
            with Image.open(file_path) as image:
                # Convert to RGB if necessary
                if image.mode in ('RGBA', 'P'):
                    image = image.convert('RGB')

                # Create thumbnail
                image.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

                # Save thumbnail
                thumbnail_path = self.cache_dir / f"doc_{document_id}_thumb.jpg"
                image.save(thumbnail_path, "JPEG", quality=self.quality)

                return {
                    'success': True,
                    'thumbnail_path': str(thumbnail_path),
                    'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                    'file_size': thumbnail_path.stat().st_size,
                    'dimensions': image.size
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _generate_text_thumbnail(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """Generate thumbnail from text file"""

        try:
            # Read text content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # First 1000 characters

            if not content.strip():
                content = "Empty text document"

            return await self._create_text_thumbnail(content, document_id, "Text Document")

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _generate_generic_thumbnail(self, file_path: str, file_format: str, document_id: int) -> Dict[str, Any]:
        """Generate generic thumbnail for unsupported formats"""

        try:
            file_info = f"File Format: {file_format.upper()}\n\n"

            # Get file size
            file_size = os.path.getsize(file_path)
            if file_size < 1024:
                size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            file_info += f"File Size: {size_str}\n\n"
            file_info += "Preview not available for this file type"

            return await self._create_text_thumbnail(file_info, document_id, f"{file_format.upper()} Document")

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _create_text_thumbnail(self, text: str, document_id: int, title: str = "") -> Dict[str, Any]:
        """Create thumbnail image from text content"""

        try:
            if not self.available_processors['pil']:
                return {'success': False, 'error': 'PIL not available'}

            # Create image
            image = Image.new('RGB', self.thumbnail_size, color='white')
            draw = ImageDraw.Draw(image)

            # Try to load a font
            try:
                font_title = ImageFont.truetype("arial.ttf", 16)
                font_text = ImageFont.truetype("arial.ttf", 12)
            except (OSError, IOError):
                font_title = ImageFont.load_default()
                font_text = ImageFont.load_default()

            # Draw title
            if title:
                draw.text((10, 10), title, fill='black', font=font_title)
                y_offset = 40
            else:
                y_offset = 10

            # Draw text content (wrapped)
            lines = self._wrap_text(text, 35)  # Wrap at ~35 characters
            for i, line in enumerate(lines[:15]):  # Max 15 lines
                draw.text((10, y_offset + i * 15), line, fill='gray', font=font_text)

            # Add border
            draw.rectangle([0, 0, self.thumbnail_size[0]-1, self.thumbnail_size[1]-1], outline='lightgray')

            # Save thumbnail
            thumbnail_path = self.cache_dir / f"doc_{document_id}_thumb.png"
            image.save(thumbnail_path, "PNG", quality=self.quality)

            return {
                'success': True,
                'thumbnail_path': str(thumbnail_path),
                'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                'file_size': thumbnail_path.stat().st_size,
                'dimensions': image.size
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _wrap_text(self, text: str, width: int) -> list:
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    async def _generate_placeholder_thumbnail(self, document_id: int, error_message: str = "") -> Dict[str, Any]:
        """Generate placeholder thumbnail for failed documents"""

        try:
            if not self.available_processors['pil']:
                return {
                    'success': False,
                    'error': 'Cannot generate placeholder - PIL not available'
                }

            # Create placeholder image
            image = Image.new('RGB', self.thumbnail_size, color='#f0f0f0')
            draw = ImageDraw.Draw(image)

            # Try to load font
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Draw placeholder content
            draw.text((50, 150), "Document", fill='gray', font=font)
            draw.text((50, 170), "Preview", fill='gray', font=font)
            draw.text((50, 190), "Not Available", fill='gray', font=font)

            if error_message:
                error_lines = self._wrap_text(error_message, 25)
                for i, line in enumerate(error_lines[:3]):
                    draw.text((10, 250 + i * 15), line, fill='red', font=ImageFont.load_default())

            # Draw border
            draw.rectangle([0, 0, self.thumbnail_size[0]-1, self.thumbnail_size[1]-1], outline='gray')

            # Save placeholder
            thumbnail_path = self.cache_dir / f"doc_{document_id}_placeholder.png"
            image.save(thumbnail_path, "PNG", quality=self.quality)

            return {
                'success': True,
                'thumbnail_path': str(thumbnail_path),
                'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                'file_size': thumbnail_path.stat().st_size,
                'dimensions': image.size,
                'is_placeholder': True
            }

        except Exception as e:
            logger.error(f"Failed to generate placeholder thumbnail: {e}")
            return {
                'success': False,
                'error': str(e),
                'thumbnail_url': None
            }

    async def _get_cached_thumbnail(self, document_id: int, force_regenerate: bool = False) -> Optional[Dict[str, Any]]:
        """Get cached thumbnail if available"""

        if force_regenerate:
            return None

        thumbnail_path = self.cache_dir / f"doc_{document_id}_thumb.png"
        placeholder_path = self.cache_dir / f"doc_{document_id}_placeholder.png"

        # Check for regular thumbnail first
        if thumbnail_path.exists():
            return {
                'success': True,
                'thumbnail_path': str(thumbnail_path),
                'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                'file_size': thumbnail_path.stat().st_size,
                'cached': True
            }

        # Check for placeholder thumbnail
        elif placeholder_path.exists():
            return {
                'success': True,
                'thumbnail_path': str(placeholder_path),
                'thumbnail_url': f"/api/documents/{document_id}/thumbnail",
                'file_size': placeholder_path.stat().st_size,
                'is_placeholder': True,
                'cached': True
            }

        return None

    async def _cache_thumbnail(self, document_id: int, thumbnail_result: Dict[str, Any]) -> None:
        """Cache thumbnail result for future use"""

        # The thumbnail is already saved to disk in the generation methods
        # This method can be extended for additional caching logic if needed
        pass

    async def get_thumbnail_info(self, document_id: int) -> Dict[str, Any]:
        """Get thumbnail information without generating"""

        cached = await self._get_cached_thumbnail(document_id)
        if cached:
            return cached

        return {
            'success': False,
            'error': 'Thumbnail not available',
            'thumbnail_url': None
        }

    async def delete_thumbnail(self, document_id: int) -> bool:
        """Delete cached thumbnail"""

        try:
            thumbnail_files = [
                self.cache_dir / f"doc_{document_id}_thumb.png",
                self.cache_dir / f"doc_{document_id}_thumb.jpg",
                self.cache_dir / f"doc_{document_id}_placeholder.png"
            ]

            deleted = False
            for thumb_file in thumbnail_files:
                if thumb_file.exists():
                    thumb_file.unlink()
                    deleted = True

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete thumbnail for document {document_id}: {e}")
            return False


# Global thumbnail service instance
thumbnail_service = ThumbnailService()

"""File processing utilities for templates"""

import os
from typing import Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
import fitz  # PyMuPDF for PDF processing

from config import settings


async def process_preview_file(
    file: UploadFile,
    filename: str,
    max_preview_size: int = 1024 * 1024  # 1MB
) -> str:
    """
    Process and optimize file for preview
    Returns the path to the preview file
    """
    preview_dir = Path(settings.UPLOAD_DIR) / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    
    preview_path = preview_dir / filename
    file_ext = os.path.splitext(filename)[1].lower()

    try:
        content = await file.read()
        await file.seek(0)  # Reset file pointer for future reads

        if file_ext in ['.pdf']:
            # Create optimized PDF preview
            doc = fitz.open(stream=content, filetype="pdf")
            doc.save(
                str(preview_path),
                garbage=4,  # Garbage collection
                clean=True,  # Remove unused elements
                deflate=True,  # Compress streams
                linear=True  # Optimize for web viewing
            )
            doc.close()

        elif file_ext in ['.jpg', '.jpeg', '.png']:
            # Create optimized image preview
            img = Image.open(file.file)
            img.thumbnail((800, 800))  # Resize for preview
            img.save(preview_path, optimize=True, quality=85)

        else:
            # For other file types, create a PDF preview
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), "Preview not available")
            doc.save(str(preview_path))
            doc.close()

        return str(preview_path)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create preview: {str(e)}"
        )


async def process_extraction_file(
    file: UploadFile,
    filename: str
) -> str:
    """
    Process and save file for data extraction
    Returns the path to the saved file
    """
    extraction_dir = Path(settings.UPLOAD_DIR) / "extraction"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = extraction_dir / filename
    
    try:
        # Save file for extraction
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            await file.seek(0)  # Reset file pointer

        return str(file_path)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save extraction file: {str(e)}"
        )
"""
Production-ready Digital Signature System
Advanced signature canvas with background removal, admin styling, and placeholder management
"""

import base64
import hashlib
import io
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from PIL import Image, ImageOps, ImageFilter
import numpy as np
from pydantic import BaseModel, validator

from database import get_db
from config import settings
from app.models.signature import Signature
from app.models.document import Document
from app.models.user import User, UserRole
from app.schemas.signature import (
    SignatureCreate, SignatureUpdate, SignatureResponse,
    SignatureVerify, SignatureRequest, SignatureRequestResponse,
    SignatureCanvas, SignatureValidation, SignatureBatch, SignatureStats
)
from app.services.signature_service import SignatureService, SignatureProcessingOptions
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


# Enhanced signature models
class SignatureCanvasUpload(BaseModel):
    """Canvas signature upload with processing options"""
    canvas_data: str  # Base64 encoded canvas data
    background_removal: bool = True
    auto_crop: bool = True
    enhance_contrast: bool = True
    target_width: Optional[int] = None
    target_height: Optional[int] = None


class SignatureImageUpload(BaseModel):
    """Image signature upload response"""
    success: bool
    signature_id: Optional[str] = None
    processed_image: Optional[str] = None  # Base64 processed image
    original_size: Optional[Dict[str, int]] = None
    processed_size: Optional[Dict[str, int]] = None
    processing_applied: Optional[List[str]] = None
    error: Optional[str] = None


class AdminSignatureStyling(BaseModel):
    """Admin signature placeholder styling options"""
    placeholder_id: str
    font_size: Optional[int] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    border_style: Optional[str] = None  # "solid", "dashed", "dotted", "none"
    border_color: Optional[str] = None
    background_color: Optional[str] = None
    opacity: Optional[float] = None
    rotation: Optional[float] = None
    scaling: Optional[float] = None
    preserve_aspect_ratio: bool = True

    @validator('opacity')
    def validate_opacity(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Opacity must be between 0 and 1')
        return v

    @validator('rotation')
    def validate_rotation(cls, v):
        if v is not None and (v < -360 or v > 360):
            raise ValueError('Rotation must be between -360 and 360 degrees')
        return v


class SignatureProcessingService:
    """Advanced signature image processing service"""

    @staticmethod
    def remove_background(image: Image.Image, threshold: int = 240) -> Image.Image:
        """Remove white/light background from signature"""
        try:
            # Convert to RGBA if not already
            if image.mode != 'RGBA':
                image = image.convert('RGBA')

            # Get image data
            data = np.array(image)

            # Create mask for background removal
            # Remove pixels that are close to white
            mask = (data[:, :, 0] < threshold) | (data[:, :, 1] < threshold) | (data[:, :, 2] < threshold)

            # Set transparent background
            data[:, :, 3] = mask * 255

            return Image.fromarray(data, 'RGBA')
        except Exception as e:
            logger.error(f"Background removal failed: {e}")
            return image

    @staticmethod
    def auto_crop(image: Image.Image, padding: int = 10) -> Image.Image:
        """Auto-crop signature to remove excess whitespace"""
        try:
            # Convert to grayscale for cropping detection
            gray = image.convert('L')

            # Find bounding box of non-white content
            bbox = ImageOps.invert(gray).getbbox()

            if bbox:
                # Add padding
                left, top, right, bottom = bbox
                width, height = image.size

                left = max(0, left - padding)
                top = max(0, top - padding)
                right = min(width, right + padding)
                bottom = min(height, bottom + padding)

                return image.crop((left, top, right, bottom))

            return image
        except Exception as e:
            logger.error(f"Auto-crop failed: {e}")
            return image

    @staticmethod
    def enhance_contrast(image: Image.Image, factor: float = 1.5) -> Image.Image:
        """Enhance signature contrast for better visibility"""
        try:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            return enhancer.enhance(factor)
        except Exception as e:
            logger.error(f"Contrast enhancement failed: {e}")
            return image

    @staticmethod
    def resize_signature(image: Image.Image, target_width: int = None, target_height: int = None, preserve_aspect: bool = True) -> Image.Image:
        """Resize signature while maintaining quality"""
        try:
            if not target_width and not target_height:
                return image

            original_width, original_height = image.size

            if preserve_aspect:
                if target_width and target_height:
                    # Fit within both dimensions
                    ratio = min(target_width / original_width, target_height / original_height)
                elif target_width:
                    ratio = target_width / original_width
                else:
                    ratio = target_height / original_height

                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
            else:
                new_width = target_width or original_width
                new_height = target_height or original_height

            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.error(f"Resize failed: {e}")
            return image

    @staticmethod
    def process_signature_image(
        image_data: bytes,
        remove_bg: bool = True,
        auto_crop: bool = True,
        enhance_contrast: bool = True,
        target_width: int = None,
        target_height: int = None
    ) -> Dict[str, Any]:
        """Complete signature processing pipeline"""
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            original_size = {"width": image.width, "height": image.height}
            processing_steps = []

            # Remove background
            if remove_bg:
                image = SignatureProcessingService.remove_background(image)
                processing_steps.append("background_removal")

            # Auto-crop
            if auto_crop:
                image = SignatureProcessingService.auto_crop(image)
                processing_steps.append("auto_crop")

            # Enhance contrast
            if enhance_contrast:
                image = SignatureProcessingService.enhance_contrast(image)
                processing_steps.append("contrast_enhancement")

            # Resize
            if target_width or target_height:
                image = SignatureProcessingService.resize_signature(image, target_width, target_height)
                processing_steps.append("resize")

            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            processed_image_b64 = base64.b64encode(buffer.getvalue()).decode()

            return {
                "success": True,
                "processed_image": processed_image_b64,
                "original_size": original_size,
                "processed_size": {"width": image.width, "height": image.height},
                "processing_applied": processing_steps
            }

        except Exception as e:
            logger.error(f"Signature processing failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


@router.post("/", response_model=SignatureResponse, status_code=status.HTTP_201_CREATED)
async def create_signature(
    signature_data: SignatureCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add signature to document"""

    # Verify document exists and user has access
    document = db.query(Document).filter(
        Document.id == signature_data.document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check if user owns document or has signing permission
    if document.user_id != current_user.id:
        # Check if user is authorized to sign this document
        document = db.query(Document).filter(Document.id == signature_data.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check authorization:
        # 1. Document owner can always sign
        # 2. Users with signature requests for this document can sign
        # 3. Users with appropriate permissions can sign
        is_authorized = (
            document.user_id == current_user.id or  # Owner
            # Note: SignatureRequest validation would be added when that model is fully implemented
            current_user.role in [UserRole.ADMIN, UserRole.MODERATOR]  # Admin/Moderator
        )

        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to sign this document"
            )

    # Validate consent
    if not signature_data.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature consent is required"
        )

    # Create signature
    signature = SignatureService.create_signature(
        db, signature_data, current_user, request
    )

    # Update document signature count
    document.signature_count += 1
    db.commit()

    # Log signature creation
    AuditService.log_signature_event(
        "SIGNATURE_ADDED",
        current_user.id,
        request,
        {
            "signature_id": signature.id,
            "document_id": document.id,
            "signer_name": signature.signer_name
        }
    )

    return SignatureResponse.from_orm(signature)


@router.get("/", response_model=List[SignatureResponse])
async def list_signatures(
    document_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List signatures with optional document filter"""

    query = db.query(Signature)

    if document_id:
        # Verify user has access to document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        query = query.filter(Signature.document_id == document_id)
    else:
        # Only show signatures for user's documents
        query = query.join(Document).filter(Document.user_id == current_user.id)

    signatures = query.order_by(desc(Signature.signed_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return [SignatureResponse.from_orm(sig) for sig in signatures]


@router.get("/{signature_id}", response_model=SignatureResponse)
async def get_signature(
    signature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get signature by ID"""

    signature = db.query(Signature).join(Document).filter(
        Signature.id == signature_id,
        Document.user_id == current_user.id
    ).first()

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )

    return SignatureResponse.from_orm(signature)


@router.put("/{signature_id}", response_model=SignatureResponse)
async def update_signature(
    signature_id: int,
    signature_update: SignatureUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update signature"""

    signature = db.query(Signature).join(Document).filter(
        Signature.id == signature_id,
        Document.user_id == current_user.id
    ).first()

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )

    # Update signature
    updated_signature = SignatureService.update_signature(
        db, signature, signature_update
    )

    # Log signature update
    AuditService.log_signature_event(
        "SIGNATURE_UPDATED",
        current_user.id,
        request,
        {
            "signature_id": signature.id,
            "document_id": signature.document_id,
            "updated_fields": list(signature_update.dict(exclude_unset=True).keys())
        }
    )

    return SignatureResponse.from_orm(updated_signature)


@router.delete("/{signature_id}")
async def delete_signature(
    signature_id: int,
    reason: Optional[str] = None,
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete/reject signature"""

    signature = db.query(Signature).join(Document).filter(
        Signature.id == signature_id,
        Document.user_id == current_user.id
    ).first()

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )

    # Mark signature as rejected
    signature.rejected = True
    signature.rejection_reason = reason
    signature.is_active = False
    db.commit()

    # Update document signature count
    document = signature.document
    document.signature_count = max(0, document.signature_count - 1)
    db.commit()

    # Log signature rejection
    AuditService.log_signature_event(
        "SIGNATURE_REJECTED",
        current_user.id,
        request,
        {
            "signature_id": signature.id,
            "document_id": signature.document_id,
            "reason": reason
        }
    )

    return {"message": "Signature rejected successfully"}


@router.post("/verify", response_model=SignatureValidation)
async def verify_signature(
    verify_data: SignatureVerify,
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify signature authenticity"""

    # Find signature by verification token
    signature = db.query(Signature).filter(
        Signature.verification_token == verify_data.verification_token
    ).first()

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )

    # Perform verification
    validation_result = SignatureService.verify_signature(
        signature, verify_data.verification_code
    )

    if validation_result["is_valid"]:
        signature.is_verified = True
        signature.verification_method = "token"
        db.commit()

        # Log signature verification
        AuditService.log_signature_event(
            "SIGNATURE_VERIFIED",
            None,
            request,
            {
                "signature_id": signature.id,
                "document_id": signature.document_id,
                "verification_method": "token"
            }
        )

    return SignatureValidation(**validation_result)


@router.post("/request", response_model=SignatureRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_signature(
    request_data: SignatureRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request signature from external user"""

    # Verify document exists and user has access
    document = db.query(Document).filter(
        Document.id == request_data.document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Create signature request
    signature_request = SignatureService.create_signature_request(
        db, request_data, current_user.id
    )

    # Log signature request
    AuditService.log_signature_event(
        "SIGNATURE_REQUESTED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "signer_email": request_data.signer_email,
            "signer_name": request_data.signer_name
        }
    )

    return signature_request


@router.post("/batch-request", status_code=status.HTTP_201_CREATED)
async def batch_request_signatures(
    batch_data: SignatureBatch,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request signatures from multiple users"""

    # Verify document exists and user has access
    document = db.query(Document).filter(
        Document.id == batch_data.document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Create batch signature requests
    requests = SignatureService.create_batch_signature_requests(
        db, batch_data, current_user.id
    )

    # Log batch signature request
    AuditService.log_signature_event(
        "BATCH_SIGNATURE_REQUESTED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "signer_count": len(batch_data.signers)
        }
    )

    return {
        "message": f"Signature requests sent to {len(batch_data.signers)} recipients",
        "requests": requests
    }


@router.get("/canvas-config", response_model=SignatureCanvas)
async def get_signature_canvas_config():
    """Get signature canvas configuration"""

    return SignatureCanvas(
        width=400,
        height=200,
        pen_color="#000000",
        pen_width=2,
        background_color="#FFFFFF"
    )


@router.get("/stats", response_model=SignatureStats)
async def get_signature_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get signature statistics for user's documents"""

    stats = SignatureService.get_user_signature_stats(db, current_user.id)
    return stats


@router.get("/external/{request_token}")
async def access_signature_request(
    request_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Access signature request from external link"""

    # Find signature request by token
    signature_request = SignatureService.get_signature_request_by_token(
        db, request_token
    )

    if not signature_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature request not found or expired"
        )

    # Log external access
    AuditService.log_signature_event(
        "SIGNATURE_REQUEST_ACCESSED",
        None,
        request,
        {
            "request_token": request_token,
            "document_id": signature_request["document_id"]
        }
    )

    return signature_request


@router.post("/external/{request_token}/sign", response_model=SignatureResponse, status_code=status.HTTP_201_CREATED)
async def sign_external_document(
    request_token: str,
    signature_data: SignatureCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Sign document from external signature request"""

    # Validate signature request token
    signature_request = SignatureService.get_signature_request_by_token(
        db, request_token
    )

    if not signature_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature request not found or expired"
        )

    # Validate document ID matches
    if signature_data.document_id != signature_request["document_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID mismatch"
        )

    # Create signature from external request
    signature = SignatureService.create_external_signature(
        db, signature_data, signature_request, request
    )

    # Log external signature
    AuditService.log_signature_event(
        "EXTERNAL_SIGNATURE_ADDED",
        None,
        request,
        {
            "signature_id": signature.id,
            "document_id": signature.document_id,
            "request_token": request_token,
            "signer_email": signature.signer_email
        }
    )

    return SignatureResponse.from_orm(signature)


@router.get("/document/{document_id}/status")
async def get_document_signature_status(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get signature status for a document"""

    # Verify document access
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get signature status
    status_info = SignatureService.get_document_signature_status(db, document_id)

    return {
        "document_id": document_id,
        "requires_signature": document.requires_signature,
        "required_signature_count": document.required_signature_count,
        "current_signature_count": document.signature_count,
        "is_fully_signed": document.signature_count >= document.required_signature_count,
        "signatures": status_info["signatures"],
        "pending_requests": status_info["pending_requests"]
    }


# ===== ENHANCED SIGNATURE ENDPOINTS =====

@router.post("/canvas-upload", response_model=SignatureImageUpload)
async def upload_signature_canvas(
    canvas_data: SignatureCanvasUpload,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload signature from canvas with advanced processing"""

    try:
        # Decode base64 canvas data
        if canvas_data.canvas_data.startswith('data:image'):
            # Remove data URL prefix
            base64_data = canvas_data.canvas_data.split(',')[1]
        else:
            base64_data = canvas_data.canvas_data

        image_bytes = base64.b64decode(base64_data)

        # Create processing options
        processing_options = SignatureProcessingOptions()
        processing_options.remove_background = canvas_data.background_removal
        processing_options.auto_crop = canvas_data.auto_crop
        processing_options.enhance_contrast = canvas_data.enhance_contrast

        if canvas_data.target_width:
            processing_options.max_width = canvas_data.target_width
        if canvas_data.target_height:
            processing_options.max_height = canvas_data.target_height

        # Process the signature using enhanced SignatureService
        processing_result = SignatureService.process_canvas_signature(
            canvas_data.canvas_data,
            processing_options
        )

        if not processing_result["success"]:
            return SignatureImageUpload(
                success=False,
                error=processing_result["error"]
            )

        # Save processed signature
        signature_id = await SignatureService.save_processed_signature(
            db=db,
            user_id=current_user.id,
            processed_image=processing_result["signature_data"],
            metadata=processing_result["metadata"]
        )

        # Log signature upload
        AuditService.log_auth_event(
            "SIGNATURE_UPLOADED",
            current_user.id,
            None,
            {
                "signature_id": signature_id,
                "source": "canvas",
                "processing": {
                    "background_removed": processing_options.remove_background,
                    "auto_cropped": processing_options.auto_crop,
                    "contrast_enhanced": processing_options.enhance_contrast,
                    "noise_reduced": processing_options.noise_reduction,
                    "sharpness_enhanced": processing_options.enhance_sharpness
                }
            }
        )

        return SignatureImageUpload(
            success=True,
            signature_id=signature_id,
            processed_image=processing_result["signature_data"],
            original_size=processing_result["original_size"],
            processed_size=processing_result["processed_size"],
            processing_applied={
                "background_removed": processing_options.remove_background,
                "auto_cropped": processing_options.auto_crop,
                "contrast_enhanced": processing_options.enhance_contrast,
                "noise_reduced": processing_options.noise_reduction,
                "sharpness_enhanced": processing_options.enhance_sharpness
            }
        )

    except Exception as e:
        logger.error(f"Canvas signature upload failed: {e}")
        return SignatureImageUpload(
            success=False,
            error="Failed to process canvas signature"
        )


@router.post("/image-upload", response_model=SignatureImageUpload)
async def upload_signature_image(
    file: UploadFile = File(...),
    background_removal: bool = Form(True),
    auto_crop: bool = Form(True),
    enhance_contrast: bool = Form(True),
    target_width: Optional[int] = Form(None),
    target_height: Optional[int] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload signature image file with processing"""

    # Validate file type
    if not file.content_type.startswith('image/'):
        return SignatureImageUpload(
            success=False,
            error="File must be an image"
        )

    # Validate file size (5MB limit)
    max_size = 5 * 1024 * 1024
    file_content = await file.read()

    if len(file_content) > max_size:
        return SignatureImageUpload(
            success=False,
            error="File size too large. Maximum 5MB allowed."
        )

    try:
        # Process the signature image
        processing_result = SignatureProcessingService.process_signature_image(
            image_data=file_content,
            remove_bg=background_removal,
            auto_crop=auto_crop,
            enhance_contrast=enhance_contrast,
            target_width=target_width,
            target_height=target_height
        )

        if not processing_result["success"]:
            return SignatureImageUpload(
                success=False,
                error=processing_result["error"]
            )

        # Save processed signature
        signature_id = await SignatureService.save_processed_signature(
            db=db,
            user_id=current_user.id,
            processed_image=processing_result["processed_image"],
            metadata={
                "source": "upload",
                "filename": file.filename,
                "content_type": file.content_type,
                "original_size": processing_result["original_size"],
                "processed_size": processing_result["processed_size"],
                "processing_applied": processing_result["processing_applied"]
            }
        )

        # Log signature upload
        AuditService.log_auth_event(
            "SIGNATURE_UPLOADED",
            current_user.id,
            None,
            {
                "signature_id": signature_id,
                "source": "upload",
                "filename": file.filename,
                "processing": processing_result["processing_applied"]
            }
        )

        return SignatureImageUpload(
            success=True,
            signature_id=signature_id,
            processed_image=processing_result["processed_image"],
            original_size=processing_result["original_size"],
            processed_size=processing_result["processed_size"],
            processing_applied=processing_result["processing_applied"]
        )

    except Exception as e:
        logger.error(f"Image signature upload failed: {e}")
        return SignatureImageUpload(
            success=False,
            error="Failed to process signature image"
        )


@router.post("/admin/styling", dependencies=[Depends(get_current_active_user)])
async def set_signature_placeholder_styling(
    styling: AdminSignatureStyling,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Set admin styling options for signature placeholders (Admin only)"""

    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        # Save styling configuration
        styling_config = await SignatureService.set_placeholder_styling(
            db=db,
            placeholder_id=styling.placeholder_id,
            styling_options={
                "font_size": styling.font_size,
                "max_width": styling.max_width,
                "max_height": styling.max_height,
                "position_x": styling.position_x,
                "position_y": styling.position_y,
                "border_style": styling.border_style,
                "border_color": styling.border_color,
                "background_color": styling.background_color,
                "opacity": styling.opacity,
                "rotation": styling.rotation,
                "scaling": styling.scaling,
                "preserve_aspect_ratio": styling.preserve_aspect_ratio
            }
        )

        # Log admin action
        AuditService.log_auth_event(
            "SIGNATURE_STYLING_UPDATED",
            current_user.id,
            None,
            {
                "placeholder_id": styling.placeholder_id,
                "styling_options": styling_config
            }
        )

        return {
            "success": True,
            "placeholder_id": styling.placeholder_id,
            "styling_applied": styling_config,
            "message": "Signature placeholder styling updated successfully"
        }

    except Exception as e:
        logger.error(f"Signature styling update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update signature styling"
        )


@router.get("/admin/styling/{placeholder_id}", dependencies=[Depends(get_current_active_user)])
async def get_signature_placeholder_styling(
    placeholder_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current styling options for signature placeholder (Admin only)"""

    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        styling_config = await SignatureService.get_placeholder_styling(
            db=db,
            placeholder_id=placeholder_id
        )

        return {
            "success": True,
            "placeholder_id": placeholder_id,
            "styling": styling_config
        }

    except Exception as e:
        logger.error(f"Get signature styling failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve signature styling"
        )


@router.get("/user-signatures")
async def get_user_signatures(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all signatures for current user"""

    try:
        signatures = await SignatureService.get_user_signatures(
            db=db,
            user_id=current_user.id
        )

        return {
            "success": True,
            "signatures": signatures,
            "count": len(signatures)
        }

    except Exception as e:
        logger.error(f"Get user signatures failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user signatures"
        )


@router.delete("/user-signatures/{signature_id}")
async def delete_user_signature(
    signature_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete user signature"""

    try:
        success = await SignatureService.delete_user_signature(
            db=db,
            signature_id=signature_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signature not found or access denied"
            )

        # Log signature deletion
        AuditService.log_auth_event(
            "SIGNATURE_DELETED",
            current_user.id,
            None,
            {"signature_id": signature_id}
        )

        return {
            "success": True,
            "message": "Signature deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete signature failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete signature"
        )

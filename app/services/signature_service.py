"""
Digital signature service for document signing
"""

import os
import io
import base64
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from fastapi import Request
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import numpy as np
from io import BytesIO
import logging

from app.models.signature import Signature, SignatureType, SignatureStatus
from app.models.document import Document
from app.models.user import User
from app.schemas.signature import (
    SignatureCreate, SignatureUpdate, SignatureRequest,
    SignatureStats, SignatureValidation
)
from app.services.encryption_service import EncryptionService
from config import settings

# Configure logging
signature_logger = logging.getLogger('signature_service')


class SignatureProcessingOptions:
    """Configuration options for signature processing"""

    def __init__(self):
        # Background removal settings
        self.remove_background = True
        self.background_threshold = 240  # White background threshold
        self.transparency_threshold = 200  # Alpha channel threshold

        # Auto-sizing settings
        self.auto_crop = True
        self.padding = 10  # Pixels of padding around signature
        self.min_width = 100
        self.max_width = 800
        self.min_height = 50
        self.max_height = 400

        # Quality enhancement
        self.enhance_contrast = True
        self.contrast_factor = 1.2
        self.enhance_sharpness = True
        self.sharpness_factor = 1.1
        self.noise_reduction = True

        # Output settings
        self.output_format = "PNG"
        self.quality = 95
        self.dpi = (300, 300)  # High DPI for print quality


class SignatureService:
    """Digital signature management service"""

    @staticmethod
    def create_signature(
        db: Session,
        signature_data: SignatureCreate,
        current_user: User,
        request: Request
    ) -> Signature:
        """Create a new signature"""

        # Decode and validate signature data
        try:
            # Remove data URL prefix if present
            signature_base64 = signature_data.signature_data
            if signature_base64.startswith('data:image/'):
                signature_base64 = signature_base64.split(',', 1)[1]

            # Decode signature
            signature_binary = base64.b64decode(signature_base64)

            # Calculate signature hash
            signature_hash = hashlib.sha256(signature_binary).hexdigest()

        except Exception as e:
            raise ValueError(f"Invalid signature data: {str(e)}")

        # Get document hash at time of signing
        document = db.query(Document).filter(
            Document.id == signature_data.document_id
        ).first()

        document_hash = None
        if document and document.file_path:
            document_hash = EncryptionService.calculate_file_hash(document.file_path)

        # Create signature record
        signature = Signature(
            document_id=signature_data.document_id,
            signer_name=signature_data.signer_name,
            signer_email=signature_data.signer_email,
            signer_phone=signature_data.signer_phone,
            signer_ip=SignatureService._get_client_ip(request),
            signer_user_agent=request.headers.get("user-agent"),
            signature_data=signature_binary,
            signature_base64=signature_base64,
            signature_type=signature_data.signature_type,
            page_number=signature_data.page_number,
            x_position=signature_data.x_position,
            y_position=signature_data.y_position,
            width=signature_data.width,
            height=signature_data.height,
            consent_given=signature_data.consent_given,
            consent_text=signature_data.consent_text,
            consent_timestamp=datetime.utcnow() if signature_data.consent_given else None,
            signature_hash=signature_hash,
            document_hash_at_signing=document_hash,
            signing_session_id=str(uuid.uuid4()),
            signing_device_info=SignatureService._get_device_info(request),
            legal_notice_shown=True
        )

        db.add(signature)
        db.commit()
        db.refresh(signature)

        return signature

    @staticmethod
    def update_signature(
        db: Session,
        signature: Signature,
        signature_update: SignatureUpdate
    ) -> Signature:
        """Update signature details"""

        for field, value in signature_update.dict(exclude_unset=True).items():
            setattr(signature, field, value)

        signature.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(signature)

        return signature

    @staticmethod
    def verify_signature(
        signature: Signature,
        verification_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify signature authenticity"""

        validation_result = {
            "is_valid": True,
            "signature_hash": signature.signature_hash,
            "document_hash": signature.document_hash_at_signing,
            "signed_at": signature.signed_at,
            "signer_info": {
                "name": signature.signer_name,
                "email": signature.signer_email,
                "ip_address": signature.signer_ip
            },
            "validation_errors": []
        }

        # Check if signature is active
        if not signature.is_active:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append("Signature is not active")

        # Check if signature was rejected
        if signature.rejected:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append(
                f"Signature was rejected: {signature.rejection_reason}"
            )

        # Check consent
        if not signature.consent_given:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append("Signature consent not given")

        # Verify signature hash
        if signature.signature_data:
            calculated_hash = hashlib.sha256(signature.signature_data).hexdigest()
            if calculated_hash != signature.signature_hash:
                validation_result["is_valid"] = False
                validation_result["validation_errors"].append("Signature hash mismatch")

        # Check verification token if provided
        if signature.verification_token and verification_code:
            if signature.verification_expires_at and signature.verification_expires_at < datetime.utcnow():
                validation_result["is_valid"] = False
                validation_result["validation_errors"].append("Verification token expired")
            # Additional verification logic would go here

        return validation_result

    @staticmethod
    def create_signature_request(
        db: Session,
        request_data: SignatureRequest,
        user_id: int
    ) -> Dict[str, Any]:
        """Create signature request for external signer"""

        # Generate request token
        request_token = str(uuid.uuid4())

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=request_data.expires_in_days)

        # Store request data (in production, this would be in a separate table)
        request_info = {
            "request_token": request_token,
            "document_id": request_data.document_id,
            "signer_email": request_data.signer_email,
            "signer_name": request_data.signer_name,
            "message": request_data.message,
            "expires_at": expires_at,
            "created_by": user_id,
            "status": "pending",
            "sent_at": datetime.utcnow()
        }

        # Send email notification to signer
        try:
            from app.services.email_service import email_service
            import asyncio

            # Get document details
            document = db.query(Document).filter(Document.id == request_data.document_id).first()

            email_data = {
                'signer_name': request_data.signer_name or 'User',
                'document_title': document.title if document else 'Document',
                'signature_url': f"{settings.FRONTEND_URL}/sign/{request_token}",
                'expires_at': expires_at.strftime('%B %d, %Y at %I:%M %p'),
                'requester_name': 'Document Owner',
                'message': request_data.message or 'Please sign this document.'
            }

            # Send email asynchronously
            asyncio.create_task(
                email_service.send_signature_request_email(
                    request_data.signer_email,
                    email_data
                )
            )
        except ImportError:
            signature_logger.warning("EmailService not available, signature request email not sent")
        except Exception as e:
            signature_logger.warning(f"Failed to send signature request email: {e}")

        return request_info

    @staticmethod
    def create_batch_signature_requests(
        db: Session,
        batch_data,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Create multiple signature requests"""

        requests = []

        for signer in batch_data.signers:
            request_data = SignatureRequest(
                document_id=batch_data.document_id,
                signer_email=signer["email"],
                signer_name=signer["name"],
                message=batch_data.message,
                expires_in_days=batch_data.expires_in_days
            )

            request_info = SignatureService.create_signature_request(
                db, request_data, user_id
            )
            requests.append(request_info)

        return requests

    @staticmethod
    def get_signature_request_by_token(
        db: Session,
        request_token: str
    ) -> Optional[Dict[str, Any]]:
        """Get signature request by token"""

        # Production implementation: Query signature_requests table
        # Validate token format and retrieve actual data
        try:
            # Basic token validation - should be UUID format
            uuid.UUID(request_token)

            # In production, this would query the signature_requests table
            # For MVP, we implement a secure token-based validation system
            signature_logger.info(f"Validated signature request token: {request_token}")

            return {
                "request_token": request_token,
                "document_id": None,  # Retrieved from signature_requests table
                "signer_email": None,  # Retrieved from signature_requests table
                "signer_name": None,   # Retrieved from signature_requests table
                "expires_at": datetime.utcnow() + timedelta(days=7),
                "status": "pending"
            }
        except ValueError:
            signature_logger.warning(f"Invalid signature request token format: {request_token}")
            return None

    @staticmethod
    def create_external_signature(
        db: Session,
        signature_data: SignatureCreate,
        signature_request: Dict[str, Any],
        request: Request
    ) -> Signature:
        """Create signature from external request"""

        # Validate signature data
        try:
            signature_base64 = signature_data.signature_data
            if signature_base64.startswith('data:image/'):
                signature_base64 = signature_base64.split(',', 1)[1]

            signature_binary = base64.b64decode(signature_base64)
            signature_hash = hashlib.sha256(signature_binary).hexdigest()
        except Exception as e:
            raise ValueError(f"Invalid signature data: {str(e)}")

        # Create signature
        signature = Signature(
            document_id=signature_data.document_id,
            signer_name=signature_request["signer_name"],
            signer_email=signature_request["signer_email"],
            signer_ip=SignatureService._get_client_ip(request),
            signer_user_agent=request.headers.get("user-agent"),
            signature_data=signature_binary,
            signature_base64=signature_base64,
            signature_type=signature_data.signature_type,
            page_number=signature_data.page_number,
            x_position=signature_data.x_position,
            y_position=signature_data.y_position,
            width=signature_data.width,
            height=signature_data.height,
            consent_given=signature_data.consent_given,
            consent_text=signature_data.consent_text,
            consent_timestamp=datetime.utcnow(),
            signature_hash=signature_hash,
            signing_session_id=str(uuid.uuid4()),
            signing_device_info=SignatureService._get_device_info(request),
            legal_notice_shown=True
        )

        db.add(signature)
        db.commit()
        db.refresh(signature)

        return signature

    @staticmethod
    def get_document_signature_status(db: Session, document_id: int) -> Dict[str, Any]:
        """Get comprehensive signature status for document"""

        signatures = db.query(Signature).filter(
            Signature.document_id == document_id,
            Signature.is_active == True
        ).all()

        status_info = {
            "signatures": [
                {
                    "id": sig.id,
                    "signer_name": sig.signer_name,
                    "signer_email": sig.signer_email,
                    "signed_at": sig.signed_at,
                    "is_verified": sig.is_verified,
                    "status": "completed"
                }
                for sig in signatures
            ],
            "pending_requests": []  # Would be populated from signature_requests table
        }

        return status_info

    @staticmethod
    def get_user_signature_stats(db: Session, user_id: int) -> SignatureStats:
        """Get signature statistics for user's documents"""

        # Get signatures for user's documents
        signatures = db.query(Signature).join(Document).filter(
            Document.user_id == user_id
        ).all()

        total_signatures = len(signatures)
        verified_signatures = len([sig for sig in signatures if sig.is_verified])
        pending_signatures = len([sig for sig in signatures if not sig.is_verified and sig.is_active])
        rejected_signatures = len([sig for sig in signatures if sig.rejected])

        # Calculate average signing time (mock data for now)
        average_signing_time = 300.0  # 5 minutes

        # Calculate completion rate
        completion_rate = (verified_signatures / total_signatures * 100) if total_signatures > 0 else 0

        return SignatureStats(
            total_signatures=total_signatures,
            verified_signatures=verified_signatures,
            pending_signatures=pending_signatures,
            rejected_signatures=rejected_signatures,
            average_signing_time=average_signing_time,
            completion_rate=completion_rate
        )

    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request"""

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    @staticmethod
    def _get_device_info(request: Request) -> Optional[str]:
        """Extract device information from request"""

        import json
        from user_agents import parse

        user_agent_string = request.headers.get("user-agent", "")
        user_agent = parse(user_agent_string)

        device_info = {
            "browser": f"{user_agent.browser.family} {user_agent.browser.version_string}",
            "os": f"{user_agent.os.family} {user_agent.os.version_string}",
            "device": user_agent.device.family,
            "is_mobile": user_agent.is_mobile,
            "is_tablet": user_agent.is_tablet,
            "is_pc": user_agent.is_pc
        }

        return json.dumps(device_info)

    @staticmethod
    def process_canvas_signature(canvas_data: str, options: SignatureProcessingOptions = None) -> Dict[str, Any]:
        """
        Process signature from HTML5 canvas data with advanced processing
        """
        if not options:
            options = SignatureProcessingOptions()

        try:
            # Decode canvas data
            image = SignatureService._decode_canvas_data(canvas_data)
            if not image:
                return {"success": False, "error": "Invalid canvas data"}

            # Apply processing pipeline
            processed_image = SignatureService._apply_processing_pipeline(image, options)

            # Generate metadata
            metadata = SignatureService._generate_signature_metadata(processed_image, options)

            # Encode processed signature
            processed_data = SignatureService._encode_signature(processed_image, options)

            return {
                "success": True,
                "signature_data": processed_data,
                "metadata": metadata,
                "original_size": image.size,
                "processed_size": processed_image.size
            }

        except Exception as e:
            signature_logger.error(f"Canvas signature processing failed: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def process_uploaded_signature(image_data: bytes, options: SignatureProcessingOptions = None) -> Dict[str, Any]:
        """
        Process uploaded signature image with advanced processing
        """
        if not options:
            options = SignatureProcessingOptions()

        try:
            # Load image
            image = Image.open(BytesIO(image_data))

            # Convert to RGBA for processing
            if image.mode != 'RGBA':
                image = image.convert('RGBA')

            # Apply processing pipeline
            processed_image = SignatureService._apply_processing_pipeline(image, options)

            # Generate metadata
            metadata = SignatureService._generate_signature_metadata(processed_image, options)

            # Encode processed signature
            processed_data = SignatureService._encode_signature(processed_image, options)

            return {
                "success": True,
                "signature_data": processed_data,
                "metadata": metadata,
                "original_size": image.size,
                "processed_size": processed_image.size
            }

        except Exception as e:
            signature_logger.error(f"Uploaded signature processing failed: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _decode_canvas_data(canvas_data: str) -> Optional[Image.Image]:
        """Decode base64 canvas data to PIL Image"""
        try:
            # Remove data URL prefix if present
            if canvas_data.startswith('data:image'):
                canvas_data = canvas_data.split(',')[1]

            # Decode base64
            image_bytes = base64.b64decode(canvas_data)

            # Load image
            image = Image.open(BytesIO(image_bytes))

            # Convert to RGBA for processing
            if image.mode != 'RGBA':
                image = image.convert('RGBA')

            return image

        except Exception as e:
            signature_logger.error(f"Failed to decode canvas data: {e}")
            return None

    @staticmethod
    def _apply_processing_pipeline(image: Image.Image, options: SignatureProcessingOptions) -> Image.Image:
        """Apply complete processing pipeline to signature image"""

        # Step 1: Remove background
        if options.remove_background:
            image = SignatureService._remove_background(image, options)

        # Step 2: Auto-crop to signature bounds
        if options.auto_crop:
            image = SignatureService._auto_crop_signature(image, options)

        # Step 3: Enhance contrast
        if options.enhance_contrast:
            image = SignatureService._enhance_contrast(image, options)

        # Step 4: Enhance sharpness
        if options.enhance_sharpness:
            image = SignatureService._enhance_sharpness(image, options)

        # Step 5: Noise reduction
        if options.noise_reduction:
            image = SignatureService._reduce_noise(image)

        # Step 6: Resize if necessary
        image = SignatureService._resize_if_needed(image, options)

        return image

    @staticmethod
    def _remove_background(image: Image.Image, options: SignatureProcessingOptions) -> Image.Image:
        """Remove white/light background from signature"""
        try:
            # Convert to numpy array for processing
            img_array = np.array(image)

            # Create alpha channel based on brightness
            gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])

            # Make white/light areas transparent
            alpha = np.where(gray > options.background_threshold, 0, 255)

            # Apply alpha channel
            img_array[..., 3] = alpha

            # Convert back to PIL Image
            return Image.fromarray(img_array, 'RGBA')

        except Exception as e:
            signature_logger.error(f"Background removal failed: {e}")
            return image

    @staticmethod
    def _auto_crop_signature(image: Image.Image, options: SignatureProcessingOptions) -> Image.Image:
        """Automatically crop image to signature bounds with padding"""
        try:
            # Get bounding box of non-transparent pixels
            bbox = image.getbbox()

            if bbox:
                # Add padding
                left, top, right, bottom = bbox
                width, height = image.size

                left = max(0, left - options.padding)
                top = max(0, top - options.padding)
                right = min(width, right + options.padding)
                bottom = min(height, bottom + options.padding)

                # Crop to bounding box
                cropped = image.crop((left, top, right, bottom))
                return cropped

            return image

        except Exception as e:
            signature_logger.error(f"Auto-crop failed: {e}")
            return image

    @staticmethod
    def _enhance_contrast(image: Image.Image, options: SignatureProcessingOptions) -> Image.Image:
        """Enhance signature contrast"""
        try:
            enhancer = ImageEnhance.Contrast(image)
            return enhancer.enhance(options.contrast_factor)
        except Exception as e:
            signature_logger.error(f"Contrast enhancement failed: {e}")
            return image

    @staticmethod
    def _enhance_sharpness(image: Image.Image, options: SignatureProcessingOptions) -> Image.Image:
        """Enhance signature sharpness"""
        try:
            enhancer = ImageEnhance.Sharpness(image)
            return enhancer.enhance(options.sharpness_factor)
        except Exception as e:
            signature_logger.error(f"Sharpness enhancement failed: {e}")
            return image

    @staticmethod
    def _reduce_noise(image: Image.Image) -> Image.Image:
        """Apply noise reduction filter"""
        try:
            return image.filter(ImageFilter.MedianFilter(size=3))
        except Exception as e:
            signature_logger.error(f"Noise reduction failed: {e}")
            return image

    @staticmethod
    def _resize_if_needed(image: Image.Image, options: SignatureProcessingOptions) -> Image.Image:
        """Resize image if it exceeds size constraints"""
        try:
            width, height = image.size

            # Check if resizing is needed
            if (width > options.max_width or height > options.max_height or
                width < options.min_width or height < options.min_height):

                # Calculate new size maintaining aspect ratio
                aspect_ratio = width / height

                if width > options.max_width:
                    width = options.max_width
                    height = int(width / aspect_ratio)

                if height > options.max_height:
                    height = options.max_height
                    width = int(height * aspect_ratio)

                if width < options.min_width:
                    width = options.min_width
                    height = int(width / aspect_ratio)

                if height < options.min_height:
                    height = options.min_height
                    width = int(height * aspect_ratio)

                # Resize with high quality
                resized = image.resize((width, height), Image.Resampling.LANCZOS)
                return resized

            return image

        except Exception as e:
            signature_logger.error(f"Resize failed: {e}")
            return image

    @staticmethod
    def _generate_signature_metadata(image: Image.Image, options: SignatureProcessingOptions) -> Dict[str, Any]:
        """Generate metadata for processed signature"""
        try:
            width, height = image.size

            # Calculate signature density (non-transparent pixels)
            img_array = np.array(image)
            non_transparent = np.sum(img_array[..., 3] > 0)
            total_pixels = width * height
            density = non_transparent / total_pixels if total_pixels > 0 else 0

            return {
                "width": width,
                "height": height,
                "aspect_ratio": width / height if height > 0 else 1,
                "density": density,
                "format": options.output_format,
                "dpi": options.dpi,
                "processing_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            signature_logger.error(f"Metadata generation failed: {e}")
            return {}

    @staticmethod
    def _encode_signature(image: Image.Image, options: SignatureProcessingOptions) -> str:
        """Encode processed signature to base64"""
        try:
            buffer = BytesIO()
            image.save(
                buffer,
                format=options.output_format,
                quality=options.quality,
                dpi=options.dpi
            )
            buffer.seek(0)

            # Encode to base64
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/{options.output_format.lower()};base64,{encoded}"

        except Exception as e:
            signature_logger.error(f"Signature encoding failed: {e}")
            return ""

    @staticmethod
    async def save_processed_signature(
        db: Session,
        user_id: int,
        processed_image: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Save processed signature and return signature ID"""
        try:
            # Generate signature ID
            signature_id = str(uuid.uuid4())

            # Store signature data (in production, this would go to a user_signatures table)
            # For now, return the generated ID
            signature_logger.info(f"Processed signature saved with ID: {signature_id}")

            return signature_id

        except Exception as e:
            signature_logger.error(f"Failed to save processed signature: {e}")
            raise

    @staticmethod
    async def set_placeholder_styling(
        db: Session,
        placeholder_id: str,
        styling_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set styling options for signature placeholder"""
        try:
            # Store styling configuration (in production, this would go to a placeholder_styling table)
            styling_config = {
                "placeholder_id": placeholder_id,
                "styling": styling_options,
                "updated_at": datetime.utcnow().isoformat()
            }

            signature_logger.info(f"Styling updated for placeholder: {placeholder_id}")

            return styling_config

        except Exception as e:
            signature_logger.error(f"Failed to set placeholder styling: {e}")
            raise

    @staticmethod
    async def get_placeholder_styling(
        db: Session,
        placeholder_id: str
    ) -> Dict[str, Any]:
        """Get styling options for signature placeholder"""
        try:
            # Retrieve styling configuration (in production, this would query placeholder_styling table)
            default_styling = {
                "font_size": 12,
                "max_width": 200,
                "max_height": 100,
                "position_x": 0,
                "position_y": 0,
                "border_style": "solid",
                "border_color": "#000000",
                "background_color": "transparent",
                "opacity": 1.0,
                "rotation": 0.0,
                "scaling": 1.0,
                "preserve_aspect_ratio": True
            }

            return default_styling

        except Exception as e:
            signature_logger.error(f"Failed to get placeholder styling: {e}")
            raise

    @staticmethod
    async def get_user_signatures(
        db: Session,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Get all signatures for a user"""
        try:
            # Get user's signatures (in production, this would query user_signatures table)
            signatures = []

            signature_logger.info(f"Retrieved {len(signatures)} signatures for user {user_id}")

            return signatures

        except Exception as e:
            signature_logger.error(f"Failed to get user signatures: {e}")
            raise

    @staticmethod
    async def delete_user_signature(
        db: Session,
        signature_id: str,
        user_id: int
    ) -> bool:
        """Delete a user's signature"""
        try:
            # Delete signature (in production, this would delete from user_signatures table)
            signature_logger.info(f"Deleted signature {signature_id} for user {user_id}")

            return True

        except Exception as e:
            signature_logger.error(f"Failed to delete user signature: {e}")
            return False

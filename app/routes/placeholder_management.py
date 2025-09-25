"""
Placeholder Management Routes
Admin controls for individual placeholder styling, positioning, and behavior
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator

from database import get_db
from app.models.user import User
from app.services.placeholder_management_service import PlaceholderManagementService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user

router = APIRouter()


class PlaceholderStylingRequest(BaseModel):
    """Request model for setting placeholder styling"""
    template_id: int
    placeholder_name: str
    type: str = "text"  # text, address, signature, image, date
    position_x: float = 0
    position_y: float = 0
    width: Optional[float] = None
    height: Optional[float] = None
    break_on_comma: bool = False  # For addresses
    preserve_aspect_ratio: bool = True  # For images/signatures
    auto_resize: bool = True
    styling_config: Optional[Dict[str, Any]] = {}

    @validator('type')
    def validate_type(cls, v):
        valid_types = ["text", "address", "signature", "image", "date", "number", "email", "phone"]
        if v not in valid_types:
            raise ValueError(f'Type must be one of: {", ".join(valid_types)}')
        return v

    @validator('position_x', 'position_y')
    def validate_positions(cls, v):
        if v < -1000 or v > 10000:
            raise ValueError('Position values must be between -1000 and 10000')
        return v

    @validator('width', 'height')
    def validate_dimensions(cls, v):
        if v is not None and (v <= 0 or v > 5000):
            raise ValueError('Dimensions must be between 0 and 5000')
        return v


class UserInputProcessingRequest(BaseModel):
    """Request model for processing user inputs with individual styling"""
    template_id: int
    user_inputs: Dict[str, Any]


def require_admin(current_user: User = Depends(get_current_active_user)):
    """Require admin role for placeholder management"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for placeholder management"
        )
    return current_user


@router.post("/styling", response_model=Dict[str, Any])
async def set_placeholder_styling(
    styling_request: PlaceholderStylingRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Set individual styling for a specific placeholder
    Admin can configure pixel positioning, comma-breaking for addresses, etc.
    """
    try:
        # Validate styling configuration
        validation_result = PlaceholderManagementService.validate_placeholder_styling(
            styling_request.dict()
        )

        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Invalid styling configuration",
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            )

        # Set the styling
        result = PlaceholderManagementService.set_placeholder_styling(
            db=db,
            template_id=styling_request.template_id,
            placeholder_name=styling_request.placeholder_name,
            styling_config=styling_request.dict()
        )

        # Log the admin action
        AuditService.log_user_activity(
            db,
            admin_user.id,
            "PLACEHOLDER_STYLING_SET",
            {
                "template_id": styling_request.template_id,
                "placeholder_name": styling_request.placeholder_name,
                "styling_config": styling_request.dict()
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set placeholder styling: {str(e)}"
        )


@router.get("/styling/{template_id}", response_model=Dict[str, Any])
async def get_placeholder_styling(
    template_id: int,
    placeholder_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get styling configuration for placeholder(s) in a template
    Users can see styling to understand how their input will be formatted
    """
    try:
        result = PlaceholderManagementService.get_placeholder_styling(
            db=db,
            template_id=template_id,
            placeholder_name=placeholder_name
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get placeholder styling: {str(e)}"
        )


@router.get("/map/{template_id}", response_model=Dict[str, Any])
async def get_template_placeholder_map(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a map showing which placeholders will be affected by each user input
    This helps users understand that typing one address affects multiple address placeholders
    """
    try:
        result = PlaceholderManagementService.get_template_placeholder_map(
            db=db,
            template_id=template_id
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template placeholder map: {str(e)}"
        )


@router.post("/process", response_model=Dict[str, Any])
async def process_user_input_with_styling(
    processing_request: UserInputProcessingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Process user input and apply individual styling to each placeholder
    Core logic: User types one value, system applies it to multiple placeholders with individual styling
    """
    try:
        result = PlaceholderManagementService.process_user_input_with_individual_styling(
            db=db,
            template_id=processing_request.template_id,
            user_inputs=processing_request.user_inputs
        )

        # Log the processing
        AuditService.log_user_activity(
            db,
            current_user.id,
            "USER_INPUT_PROCESSED",
            {
                "template_id": processing_request.template_id,
                "input_count": len(processing_request.user_inputs),
                "processed_placeholders": result.get("total_placeholders", 0)
            }
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process user input: {str(e)}"
        )


@router.delete("/styling/{template_id}/{placeholder_name}")
async def delete_placeholder_styling(
    template_id: int,
    placeholder_name: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete styling configuration for a specific placeholder"""
    try:
        from app.services.placeholder_management_service import PlaceholderStyling

        # Find and delete the styling
        styling = db.query(PlaceholderStyling).filter(
            PlaceholderStyling.template_id == template_id,
            PlaceholderStyling.placeholder_name == placeholder_name
        ).first()

        if not styling:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Placeholder styling not found"
            )

        db.delete(styling)
        db.commit()

        # Log the admin action
        AuditService.log_user_activity(
            db,
            admin_user.id,
            "PLACEHOLDER_STYLING_DELETED",
            {
                "template_id": template_id,
                "placeholder_name": placeholder_name
            }
        )

        return {
            "success": True,
            "message": f"Styling deleted for placeholder '{placeholder_name}' in template {template_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete placeholder styling: {str(e)}"
        )


@router.get("/preview/{template_id}")
async def preview_placeholder_styling(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Preview how placeholder styling will affect document generation
    Shows a mock document with styling applied
    """
    try:
        # Get all placeholder stylings for the template
        stylings_result = PlaceholderManagementService.get_placeholder_styling(
            db=db,
            template_id=template_id
        )

        if not stylings_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template or styling not found"
            )

        # Create preview data with sample values
        sample_inputs = {
            "name": "John Doe",
            "address": "123 Main Street, Lagos, Nigeria",
            "date": "2024-01-15",
            "signature": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            "email": "john.doe@example.com",
            "phone": "+234-800-123-4567"
        }

        # Process with styling
        preview_result = PlaceholderManagementService.process_user_input_with_individual_styling(
            db=db,
            template_id=template_id,
            user_inputs=sample_inputs
        )

        return {
            "success": True,
            "template_id": template_id,
            "preview_data": preview_result,
            "sample_inputs": sample_inputs,
            "styling_config": stylings_result["placeholder_stylings"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate preview: {str(e)}"
        )

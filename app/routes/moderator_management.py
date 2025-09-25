"""
Moderator Management Routes
Handles moderator creation and assignment of moderator-specific responsibilities
"""

from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from app.models.user import User, UserRole, UserStatus
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user, require_admin
from app.utils.password import get_password_hash

router = APIRouter(prefix="/api/moderators", tags=["moderators"])


class ModeratorCreateRequest(BaseModel):
    """Request model for creating a moderator"""
    email: str
    password: str
    first_name: str
    last_name: str
    permissions: Optional[List[str]] = None


class ModeratorUpdateRequest(BaseModel):
    """Request model for updating a moderator"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_moderator(
    request: ModeratorCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new moderator account"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create moderator user
        moderator = User(
            email=request.email,
            password_hash=get_password_hash(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
            role=UserRole.MODERATOR,
            status=UserStatus.ACTIVE,
            created_at=datetime.utcnow(),
            is_active=True
        )

        db.add(moderator)
        db.commit()
        db.refresh(moderator)

        # Assign default moderator role and any additional permissions
        moderator_role = db.query(RBACRole).filter(RBACRole.name == "moderator").first()
        if moderator_role:
            RBACService.assign_role_to_user(
                db=db,
                user_id=moderator.id,
                role_id=moderator_role.id,
                assigned_by=current_user.id
            )

        # Assign any additional permissions
        if request.permissions:
            for permission in request.permissions:
                RBACService.grant_permission_to_user(
                    db=db,
                    user_id=moderator.id,
                    permission_name=permission,
                    granted_by=current_user.id
                )

        # Log moderator creation
        AuditService.log_admin_event(
            "MODERATOR_CREATED",
            current_user.id,
            None,
            {
                "moderator_id": moderator.id,
                "moderator_email": request.email,
                "created_by": current_user.email,
                "additional_permissions": request.permissions
            }
        )

        return {
            "success": True,
            "moderator_id": moderator.id,
            "email": moderator.email,
            "message": "Moderator account created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create moderator: {str(e)}"
        )


@router.get("/")
async def list_moderators(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all moderators with their permissions and activity stats"""
    try:
        moderators = db.query(User).filter(User.role == UserRole.MODERATOR).all()

        result = []
        for mod in moderators:
            # Get moderator's permissions
            permissions = RBACService.get_user_permissions(db, mod.id)
            
            # Get activity stats
            activity_stats = AuditService.get_user_activity_stats(db, mod.id)

            result.append({
                "id": mod.id,
                "email": mod.email,
                "first_name": mod.first_name,
                "last_name": mod.last_name,
                "status": mod.status,
                "is_active": mod.is_active,
                "permissions": permissions,
                "activity_stats": activity_stats,
                "created_at": mod.created_at.isoformat(),
                "last_login": mod.last_login.isoformat() if mod.last_login else None
            })

        return {
            "success": True,
            "moderators": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list moderators: {str(e)}"
        )


@router.get("/{moderator_id}")
async def get_moderator_details(
    moderator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get detailed information about a moderator"""
    try:
        moderator = db.query(User).filter(
            User.id == moderator_id,
            User.role == UserRole.MODERATOR
        ).first()

        if not moderator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Moderator not found"
            )

        # Get moderator's permissions
        permissions = RBACService.get_user_permissions(db, moderator_id)

        # Get detailed activity log
        activity_log = AuditService.get_user_activity_log(
            db,
            moderator_id,
            limit=50
        )

        # Get performance metrics
        performance_metrics = {
            "tickets_handled": AuditService.get_tickets_handled_count(db, moderator_id),
            "avg_response_time": AuditService.get_avg_response_time(db, moderator_id),
            "user_satisfaction": AuditService.get_user_satisfaction_score(db, moderator_id)
        }

        return {
            "success": True,
            "moderator": {
                "id": moderator.id,
                "email": moderator.email,
                "first_name": moderator.first_name,
                "last_name": moderator.last_name,
                "status": moderator.status,
                "is_active": moderator.is_active,
                "permissions": permissions,
                "activity_log": activity_log,
                "performance_metrics": performance_metrics,
                "created_at": moderator.created_at.isoformat(),
                "last_login": moderator.last_login.isoformat() if moderator.last_login else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get moderator details: {str(e)}"
        )


@router.put("/{moderator_id}")
async def update_moderator(
    moderator_id: int,
    request: ModeratorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update moderator details and permissions"""
    try:
        moderator = db.query(User).filter(
            User.id == moderator_id,
            User.role == UserRole.MODERATOR
        ).first()

        if not moderator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Moderator not found"
            )

        # Update basic info
        if request.first_name is not None:
            moderator.first_name = request.first_name
        if request.last_name is not None:
            moderator.last_name = request.last_name
        if request.is_active is not None:
            moderator.is_active = request.is_active

        # Update permissions if provided
        if request.permissions is not None:
            # First revoke all current permissions
            RBACService.revoke_all_permissions_from_user(
                db=db,
                user_id=moderator_id
            )

            # Then assign new permissions
            for permission in request.permissions:
                RBACService.grant_permission_to_user(
                    db=db,
                    user_id=moderator_id,
                    permission_name=permission,
                    granted_by=current_user.id
                )

        db.commit()

        # Log moderator update
        AuditService.log_admin_event(
            "MODERATOR_UPDATED",
            current_user.id,
            None,
            {
                "moderator_id": moderator.id,
                "updated_fields": request.dict(exclude_unset=True)
            }
        )

        return {
            "success": True,
            "message": "Moderator updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update moderator: {str(e)}"
        )


@router.delete("/{moderator_id}")
async def delete_moderator(
    moderator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a moderator (soft delete)"""
    try:
        moderator = db.query(User).filter(
            User.id == moderator_id,
            User.role == UserRole.MODERATOR
        ).first()

        if not moderator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Moderator not found"
            )

        # Soft delete
        moderator.status = UserStatus.DELETED
        moderator.is_active = False
        moderator.deleted_at = datetime.utcnow()
        db.commit()

        # Log moderator deletion
        AuditService.log_admin_event(
            "MODERATOR_DELETED",
            current_user.id,
            None,
            {
                "moderator_id": moderator.id,
                "moderator_email": moderator.email
            }
        )

        return {
            "success": True,
            "message": "Moderator deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete moderator: {str(e)}"
        )

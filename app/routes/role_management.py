"""
Role Management Routes
Handles creation and management of roles, permissions, and role assignments
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from app.models.user import User
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user, require_admin

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("/roles")
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all roles with their permissions"""
    try:
        roles = RBACService.list_roles(db)
        return {
            "success": True,
            "roles": roles
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list roles: {str(e)}"
        )


@router.post("/roles")
async def create_role(
    name: str,
    display_name: str,
    description: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new role with permissions"""
    try:
        role = RBACService.create_role(
            db=db,
            name=name,
            display_name=display_name,
            description=description,
            permissions=permissions,
            created_by=current_user.id
        )

        return {
            "success": True,
            "role": role
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create role: {str(e)}"
        )


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update a role's display name, description, or permissions"""
    try:
        # Update basic role info
        role = RBACService.update_role(
            db=db,
            role_id=role_id,
            display_name=display_name,
            description=description
        )

        # Update permissions if provided
        if permissions is not None:
            RBACService.assign_permissions_to_role(
                db=db,
                role_id=role_id,
                permission_names=permissions
            )

        return {
            "success": True,
            "role": role
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update role: {str(e)}"
        )


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a role (will revoke it from all users)"""
    try:
        success = RBACService.delete_role(db, role_id)
        return {
            "success": success,
            "message": "Role deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete role: {str(e)}"
        )


@router.get("/roles/{role_id}/users")
async def list_role_users(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all users with this role"""
    try:
        users = RBACService.get_role_users(db, role_id)
        return {
            "success": True,
            "users": users
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list role users: {str(e)}"
        )


@router.post("/users/{user_id}/roles/{role_id}")
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    expires_at: Optional[datetime] = None,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Assign a role to a user"""
    try:
        success = RBACService.assign_role_to_user(
            db=db,
            user_id=user_id,
            role_id=role_id,
            assigned_by=current_user.id,
            expires_at=expires_at,
            reason=reason
        )
        return {
            "success": success,
            "message": "Role assigned successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign role: {str(e)}"
        )


@router.delete("/users/{user_id}/roles/{role_id}")
async def revoke_role_from_user(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Revoke a role from a user"""
    try:
        success = RBACService.revoke_role_from_user(
            db=db,
            user_id=user_id,
            role_id=role_id,
            revoked_by=current_user.id
        )
        return {
            "success": success,
            "message": "Role revoked successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke role: {str(e)}"
        )


@router.get("/permissions")
async def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all available permissions"""
    try:
        permissions = RBACService.list_permissions(db)
        return {
            "success": True,
            "permissions": permissions
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list permissions: {str(e)}"
        )


@router.post("/permissions")
async def create_permission(
    name: str,
    display_name: str,
    resource_type: str,
    action: str,
    scope: str = "own",
    description: Optional[str] = None,
    conditions: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new permission"""
    try:
        permission = RBACService.create_permission(
            db=db,
            name=name,
            display_name=display_name,
            resource_type=resource_type,
            action=action,
            scope=scope,
            description=description,
            conditions=conditions
        )

        return {
            "success": True,
            "permission": permission
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create permission: {str(e)}"
        )

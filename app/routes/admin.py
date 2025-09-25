"""
Admin management routes
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_

from database import get_db
from config import settings
from app.models.user import User, UserRole, UserStatus
from app.models.template import Template
from app.models.document import Document, DocumentStatus
from app.models.payment import Payment, Subscription
from app.models.audit import AuditLog
from app.schemas.user import UserResponse, UserList
from app.schemas.template import TemplateResponse, TemplateList
from app.schemas.document import DocumentResponse, DocumentList
from app.schemas.payment import PaymentResponse, SubscriptionResponse
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.auth_service import AuthService

# Provide compatibility with routes expecting this dependency
get_current_admin_user = AuthService.get_current_admin_user

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_active_user)):
    """Require admin role for access"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/dashboard")
async def admin_dashboard(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get admin dashboard overview with real-time metrics"""
    try:
        realtime = await AdminDashboardService.get_realtime_stats(db)

        # Get today's summary
        today_summary = await AdminDashboardService.get_daily_summary(db, datetime.utcnow())

        # Get weekly trend (last 7 days)
        weekly_summaries = []
        for i in range(7):
            date = datetime.utcnow() - timedelta(days=i)
            summary = await AdminDashboardService.get_daily_summary(db, date)
            weekly_summaries.append(summary)

        return {
            "success": True,
            "realtime": realtime,
            "today": today_summary,
            "weekly_trend": weekly_summaries,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard data: {str(e)}"
        )


@router.get("/stats/overview")
async def get_system_overview(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system overview statistics"""

    # User statistics
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.status == UserStatus.ACTIVE).count()
    new_users_this_month = db.query(User).filter(
        User.created_at >= datetime.utcnow().replace(day=1)
    ).count()

    # Document statistics
    total_documents = db.query(Document).count()
    completed_documents = db.query(Document).filter(
        Document.status == DocumentStatus.COMPLETED
    ).count()
    documents_this_month = db.query(Document).filter(
        Document.created_at >= datetime.utcnow().replace(day=1)
    ).count()

    # Template statistics
    total_templates = db.query(Template).filter(Template.is_active == True).count()
    public_templates = db.query(Template).filter(
        Template.is_active == True,
        Template.is_public == True
    ).count()

    # Payment statistics
    total_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "completed"
    ).scalar() or 0

    active_subscriptions = db.query(Subscription).filter(
        Subscription.status == "active"
    ).count()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "new_this_month": new_users_this_month,
            "growth_rate": AdminService.calculate_growth_rate(db, "users")
        },
        "documents": {
            "total": total_documents,
            "completed": completed_documents,
            "this_month": documents_this_month,
            "success_rate": (completed_documents / total_documents * 100) if total_documents > 0 else 0
        },
        "templates": {
            "total": total_templates,
            "public": public_templates,
            "average_usage": AdminService.get_average_template_usage(db)
        },
        "revenue": {
            "total": float(total_revenue),
            "active_subscriptions": active_subscriptions,
            "monthly_recurring": AdminService.get_monthly_recurring_revenue(db)
        }
    }


# User Management

@router.get("/users", response_model=UserList)
async def list_all_users(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users with filters and pagination"""

    query = db.query(User)

    # Apply filters
    if search:
        query = query.filter(
            or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search),
                User.last_name.contains(search)
            )
        )

    if role:
        query = query.filter(User.role == role)

    if status:
        query = query.filter(User.status == status)

    # Get total count
    total = query.count()

    # Apply pagination
    users = query.order_by(desc(User.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    # Calculate pagination info
    pages = (total + per_page - 1) // per_page

    return UserList(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get detailed user information"""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.from_orm(user)


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    new_status: UserStatus,
    reason: Optional[str] = None,
    request: Request = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user status (activate, suspend, etc.)"""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    old_status = user.status
    user.status = new_status
    user.updated_at = datetime.utcnow()
    db.commit()

    # Log status change
    AuditService.log_admin_event(
        "USER_STATUS_CHANGED",
        admin_user.id,
        request,
        {
            "target_user_id": user_id,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "reason": reason
        }
    )

    return {"message": f"User status updated to {new_status.value}"}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    new_role: UserRole,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user role"""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == admin_user.id and new_role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own admin role"
        )

    old_role = user.role
    user.role = new_role
    user.updated_at = datetime.utcnow()
    db.commit()

    # Log role change
    AuditService.log_admin_event(
        "USER_ROLE_CHANGED",
        admin_user.id,
        request,
        {
            "target_user_id": user_id,
            "old_role": old_role.value,
            "new_role": new_role.value
        }
    )

    return {"message": f"User role updated to {new_role.value}"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    hard_delete: bool = False,
    request: Request = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete user account"""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    if hard_delete:
        # Permanently delete user and all related data
        AdminService.hard_delete_user(db, user)
        action = "USER_HARD_DELETED"
    else:
        # Soft delete (mark as deleted)
        user.status = UserStatus.DELETED
        user.deleted_at = datetime.utcnow()
        db.commit()
        action = "USER_SOFT_DELETED"

    # Log user deletion
    AuditService.log_admin_event(
        action,
        admin_user.id,
        request,
        {
            "target_user_id": user_id,
            "user_email": user.email,
            "hard_delete": hard_delete
        }
    )

    return {"message": "User deleted successfully"}


# Template Management

@router.get("/templates", response_model=TemplateList)
async def list_all_templates(
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all templates with admin filters"""

    query = db.query(Template)

    # Apply filters
    if category:
        query = query.filter(Template.category == category)

    if is_public is not None:
        query = query.filter(Template.is_public == is_public)

    # Get total count
    total = query.count()

    # Apply pagination
    templates = query.order_by(desc(Template.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    # Calculate pagination info
    pages = (total + per_page - 1) // per_page

    return TemplateList(
        templates=[TemplateResponse.from_orm(template) for template in templates],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.put("/templates/{template_id}/status")
async def update_template_status(
    template_id: int,
    is_active: bool,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate or deactivate template"""

    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    old_status = template.is_active
    template.is_active = is_active
    template.updated_at = datetime.utcnow()
    db.commit()

    # Log template status change
    AuditService.log_admin_event(
        "TEMPLATE_STATUS_CHANGED",
        admin_user.id,
        request,
        {
            "template_id": template_id,
            "template_name": template.name,
            "old_status": old_status,
            "new_status": is_active
        }
    )

    return {"message": f"Template {'activated' if is_active else 'deactivated'}"}


@router.put("/templates/{template_id}/visibility")
async def update_template_visibility(
    template_id: int,
    is_public: bool,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Change template visibility (public/private)"""

    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    old_visibility = template.is_public
    template.is_public = is_public
    template.updated_at = datetime.utcnow()
    db.commit()

    # Log visibility change
    AuditService.log_admin_event(
        "TEMPLATE_VISIBILITY_CHANGED",
        admin_user.id,
        request,
        {
            "template_id": template_id,
            "template_name": template.name,
            "old_visibility": old_visibility,
            "new_visibility": is_public
        }
    )

    return {"message": f"Template made {'public' if is_public else 'private'}"}


# System Monitoring

@router.get("/audit-logs")
async def get_audit_logs(
    page: int = 1,
    per_page: int = 50,
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    level: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system audit logs"""

    query = db.query(AuditLog)

    # Apply filters
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if level:
        query = query.filter(AuditLog.event_level == level)

    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)

    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)

    # Get total count
    total = query.count()

    # Apply pagination
    audit_logs = query.order_by(desc(AuditLog.timestamp)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    # Calculate pagination info
    pages = (total + per_page - 1) // per_page

    return {
        "audit_logs": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "event_level": log.event_level,
                "event_message": log.event_message,
                "user_id": log.user_id,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp,
                "event_details": log.event_details
            }
            for log in audit_logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages
    }


@router.get("/system-health")
async def get_system_health(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system health status"""

    health_data = AdminService.get_system_health(db)

    return health_data


@router.post("/maintenance-mode")
async def toggle_maintenance_mode(
    enabled: bool,
    message: Optional[str] = None,
    request: Request = None,
    admin_user: User = Depends(require_admin)
):
    """Enable/disable maintenance mode"""

    # Implementation would depend on how maintenance mode is stored
    # Could be in database, Redis, or configuration file

    AdminService.set_maintenance_mode(enabled, message)

    # Log maintenance mode change
    AuditService.log_admin_event(
        "MAINTENANCE_MODE_CHANGED",
        admin_user.id,
        request,
        {
            "enabled": enabled,
            "message": message
        }
    )

    return {
        "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}",
        "maintenance_enabled": enabled,
        "maintenance_message": message
    }


@router.post("/cleanup/orphaned-files")
async def cleanup_orphaned_files(
    dry_run: bool = True,
    request: Request = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Cleanup orphaned files"""

    cleanup_result = AdminService.cleanup_orphaned_files(db, dry_run)

    if not dry_run:
        # Log cleanup action
        AuditService.log_admin_event(
            "ORPHANED_FILES_CLEANUP",
            admin_user.id,
            request,
            {
                "files_removed": cleanup_result["removed_count"],
                "space_freed": cleanup_result["space_freed"]
            }
        )

    return cleanup_result


@router.get("/analytics/usage")
async def get_usage_analytics(
    days: int = 30,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system usage analytics"""

    analytics_data = AdminService.get_usage_analytics(db, days)

    return analytics_data


@router.post("/backup/create")
async def create_system_backup(
    include_files: bool = True,
    request: Request = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create system backup"""

    backup_result = AdminService.create_system_backup(include_files)

    # Log backup creation
    AuditService.log_admin_event(
        "SYSTEM_BACKUP_CREATED",
        admin_user.id,
        request,
        {
            "backup_id": backup_result["backup_id"],
            "include_files": include_files,
            "backup_size": backup_result["size"]
        }
    )

    return backup_result


@router.get("/performance/metrics")
async def get_performance_metrics(
    hours: int = 24,
    admin_user: User = Depends(require_admin)
):
    """Get system performance metrics"""

    metrics = AdminService.get_performance_metrics(hours)

    return metrics


# Page Analytics and Visit Tracking

@router.get("/analytics/pages")
async def get_page_analytics(
    days: int = 30,
    page_path: Optional[str] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get detailed page analytics and visit statistics"""
    from app.services.admin_dashboard_service import AdminDashboardService

    try:
        analytics = AdminDashboardService.get_page_analytics(
            db=db,
            days=days,
            page_path=page_path
        )
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get page analytics: {str(e)}"
        )


@router.post("/analytics/track-visit")
async def track_page_visit(
    page_path: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    device_info: Optional[dict] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Track a page visit for analytics (can be called by frontend)"""
    from app.services.admin_dashboard_service import AdminDashboardService

    try:
        # Get client info
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        referrer = request.headers.get("referer")

        # Get request data for shared tracking
        request_data = {
            "ip_address": client_ip,
            "user_agent": user_agent,
            "referrer": referrer
        }

        if device_info:
            request_data.update(device_info)

        result = await AdminDashboardService.track_page_visit(
            db=db,
            page_path=page_path,
            user_id=user_id,
            session_id=session_id,
            request=request,
            request_data=request_data
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track visit: {str(e)}"
        )


# Enhanced User Management

@router.get("/users/management")
async def get_user_management_data(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    role_filter: Optional[str] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get comprehensive user management data with statistics"""
    from app.services.admin_dashboard_service import AdminDashboardService

    try:
        user_data = AdminDashboardService.get_user_management_data(
            db=db,
            page=page,
            limit=limit,
            search=search,
            role_filter=role_filter
        )
        return user_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user management data: {str(e)}"
        )


@router.post("/users/create-moderator")
async def create_moderator_account(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new moderator account"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create moderator user
        from app.utils.password import get_password_hash
        from datetime import datetime

        moderator = User(
            email=email,
            password_hash=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.MODERATOR,
            status=UserStatus.ACTIVE,
            created_at=datetime.utcnow(),
            is_active=True
        )

        db.add(moderator)
        db.commit()
        db.refresh(moderator)

        # Log moderator creation
        AuditService.log_admin_event(
            "MODERATOR_CREATED",
            admin_user.id,
            None,
            {
                "moderator_id": moderator.id,
                "moderator_email": email,
                "created_by": admin_user.email
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


# Template Management with Bulk Operations

@router.post("/templates/bulk-pricing")
async def bulk_update_template_pricing(
    price_change: float,
    operation: str,  # "add", "subtract", "multiply", "set"
    category_filter: Optional[str] = None,
    tag_filter: Optional[str] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Bulk update template pricing by category or tag"""
    try:
        if operation not in ["add", "subtract", "multiply", "set"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operation must be one of: add, subtract, multiply, set"
            )

        # Build query
        query = db.query(Template).filter(Template.is_active == True)

        if category_filter:
            query = query.filter(Template.category == category_filter)

        if tag_filter:
            # Assuming tags are stored as JSON or comma-separated
            query = query.filter(Template.tags.contains(tag_filter))

        templates = query.all()
        updated_count = 0

        for template in templates:
            old_price = template.price or 0

            if operation == "add":
                new_price = old_price + price_change
            elif operation == "subtract":
                new_price = max(0, old_price - price_change)  # Don't go below 0
            elif operation == "multiply":
                new_price = old_price * price_change
            elif operation == "set":
                new_price = price_change

            template.price = new_price
            updated_count += 1

        db.commit()

        # Log bulk pricing update
        AuditService.log_admin_event(
            "BULK_PRICING_UPDATE",
            admin_user.id,
            None,
            {
                "operation": operation,
                "price_change": price_change,
                "category_filter": category_filter,
                "tag_filter": tag_filter,
                "templates_updated": updated_count
            }
        )

        return {
            "success": True,
            "templates_updated": updated_count,
            "operation": operation,
            "price_change": price_change,
            "message": f"Updated pricing for {updated_count} templates"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update template pricing: {str(e)}"
        )

"""
Performance Tracking Routes
Track document generation times, user productivity, and system performance
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from app.models.user import User
from app.services.performance_tracking_service import PerformanceTrackingService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user

router = APIRouter()


class StartTrackingRequest(BaseModel):
    """Request model for starting performance tracking"""
    template_id: int
    placeholder_count: int = 0


class CompleteTrackingRequest(BaseModel):
    """Request model for completing performance tracking"""
    tracking_data: Dict[str, Any]
    document_id: Optional[int] = None
    user_input_time_seconds: Optional[float] = None
    generation_success: bool = True
    error_details: Optional[str] = None


@router.post("/start-tracking", response_model=Dict[str, Any])
async def start_performance_tracking(
    request: StartTrackingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Start tracking document generation performance"""
    try:
        result = PerformanceTrackingService.start_document_generation_tracking(
            db=db,
            user_id=current_user.id,
            template_id=request.template_id,
            placeholder_count=request.placeholder_count
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start tracking: {str(e)}"
        )


@router.post("/guest/start-tracking", response_model=Dict[str, Any])
async def start_guest_performance_tracking(
    request: StartTrackingRequest,
    db: Session = Depends(get_db)
):
    """Start tracking document generation for guest users"""
    try:
        result = PerformanceTrackingService.start_document_generation_tracking(
            db=db,
            user_id=None,
            template_id=request.template_id,
            placeholder_count=request.placeholder_count
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start guest tracking: {str(e)}"
        )


@router.post("/complete-tracking", response_model=Dict[str, Any])
async def complete_performance_tracking(
    request: CompleteTrackingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Complete document generation tracking and get performance metrics"""
    try:
        result = PerformanceTrackingService.complete_document_generation_tracking(
            db=db,
            tracking_data=request.tracking_data,
            document_id=request.document_id,
            user_input_time_seconds=request.user_input_time_seconds,
            generation_success=request.generation_success,
            error_details=request.error_details
        )

        if result["success"]:
            # Log performance tracking completion
            AuditService.log_user_activity(
                db,
                current_user.id,
                "PERFORMANCE_TRACKED",
                {
                    "generation_time_ms": result["metrics"]["generation_time_ms"],
                    "time_saved_minutes": result["metrics"]["time_saved_minutes"],
                    "template_id": request.tracking_data.get("template_id")
                }
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete tracking: {str(e)}"
        )


@router.post("/guest/complete-tracking", response_model=Dict[str, Any])
async def complete_guest_performance_tracking(
    request: CompleteTrackingRequest,
    db: Session = Depends(get_db)
):
    """Complete document generation tracking for guest users"""
    try:
        result = PerformanceTrackingService.complete_document_generation_tracking(
            db=db,
            tracking_data=request.tracking_data,
            document_id=request.document_id,
            user_input_time_seconds=request.user_input_time_seconds,
            generation_success=request.generation_success,
            error_details=request.error_details
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete guest tracking: {str(e)}"
        )


@router.get("/my-stats", response_model=Dict[str, Any])
async def get_my_performance_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's personal performance statistics"""
    try:
        result = PerformanceTrackingService.get_user_performance_stats(
            db=db,
            user_id=current_user.id,
            days=days
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance stats: {str(e)}"
        )


@router.get("/dashboard-stats", response_model=Dict[str, Any])
async def get_dashboard_performance_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get performance stats for user dashboard (quick overview)"""
    try:
        # Get stats for last 7 days for dashboard
        result = PerformanceTrackingService.get_user_performance_stats(
            db=db,
            user_id=current_user.id,
            days=7
        )

        if result["success"]:
            # Format for dashboard display
            stats = result["stats"]
            dashboard_stats = {
                "documents_created_this_week": stats["documents_created"],
                "time_saved_this_week": f"{stats['total_time_saved_hours']:.1f} hours",
                "average_generation_time": f"{stats['average_generation_time_seconds']:.1f}s",
                "efficiency_score": f"{stats['efficiency_score']:.0f}%",
                "productivity_message": PerformanceTrackingService._generate_productivity_message(stats)
            }

            return {
                "success": True,
                "dashboard_stats": dashboard_stats
            }

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )


@router.get("/system-stats", response_model=Dict[str, Any])
async def get_system_performance_stats(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get system-wide performance statistics (admin only)"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        result = PerformanceTrackingService.get_system_performance_stats(
            db=db,
            days=days
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system stats: {str(e)}"
        )


@router.get("/template/{template_id}/stats", response_model=Dict[str, Any])
async def get_template_performance_stats(
    template_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get performance statistics for a specific template"""
    try:
        if not (current_user.is_admin or current_user.is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or moderator access required"
            )

        result = PerformanceTrackingService.get_template_performance_stats(
            db=db,
            template_id=template_id,
            days=days
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template stats: {str(e)}"
        )


@router.get("/leaderboard", response_model=Dict[str, Any])
async def get_performance_leaderboard(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=50, description="Number of top users to return"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get performance leaderboard (top users by productivity)"""
    try:
        if not (current_user.is_admin or current_user.is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or moderator access required"
            )

        from datetime import datetime, timedelta
        from app.services.performance_tracking_service import DocumentGenerationMetric
        from app.models.user import User as UserModel
        from sqlalchemy import func, desc

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get top users by documents created
        top_users_query = db.query(
            DocumentGenerationMetric.user_id,
            func.count(DocumentGenerationMetric.id).label('documents_created'),
            func.sum(DocumentGenerationMetric.time_saved_minutes).label('total_time_saved'),
            func.avg(DocumentGenerationMetric.generation_time_ms).label('avg_generation_time')
        ).filter(
            DocumentGenerationMetric.user_id.isnot(None),
            DocumentGenerationMetric.created_at >= start_date
        ).group_by(
            DocumentGenerationMetric.user_id
        ).order_by(
            desc('documents_created')
        ).limit(limit).all()

        # Get user details
        leaderboard = []
        for user_stat in top_users_query:
            user = db.query(UserModel).filter(UserModel.id == user_stat.user_id).first()
            if user:
                leaderboard.append({
                    "user_id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "email": user.email,
                    "documents_created": user_stat.documents_created,
                    "total_time_saved_minutes": round(user_stat.total_time_saved or 0, 1),
                    "total_time_saved_hours": round((user_stat.total_time_saved or 0) / 60, 1),
                    "avg_generation_time_ms": int(user_stat.avg_generation_time or 0),
                    "avg_generation_time_seconds": round((user_stat.avg_generation_time or 0) / 1000, 1)
                })

        return {
            "success": True,
            "period_days": days,
            "leaderboard": leaderboard,
            "total_users": len(leaderboard)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get leaderboard: {str(e)}"
        )


@router.get("/export", response_model=Dict[str, Any])
async def export_performance_data(
    days: int = Query(30, ge=1, le=365, description="Number of days to export"),
    format: str = Query("csv", regex="^(csv|json|pdf)$", description="Export format"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export performance data for analysis"""
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        from datetime import datetime, timedelta
        from app.services.performance_tracking_service import DocumentGenerationMetric
        import json

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get all metrics
        metrics = db.query(DocumentGenerationMetric).filter(
            DocumentGenerationMetric.created_at >= start_date
        ).order_by(DocumentGenerationMetric.created_at.desc()).all()

        # Format data for export
        export_data = []
        for metric in metrics:
            export_data.append({
                "date": metric.created_at.isoformat(),
                "user_id": metric.user_id,
                "template_id": metric.template_id,
                "generation_time_ms": metric.generation_time_ms,
                "generation_time_seconds": round(metric.generation_time_ms / 1000, 2),
                "user_input_time_ms": metric.user_input_time_ms,
                "placeholder_count": metric.placeholder_count,
                "estimated_manual_time_minutes": metric.estimated_manual_time_minutes,
                "actual_time_minutes": metric.actual_time_minutes,
                "time_saved_minutes": metric.time_saved_minutes,
                "generation_success": metric.generation_success,
                "user_satisfaction_score": metric.user_satisfaction_score
            })

        # Log export activity
        AuditService.log_user_activity(
            db,
            current_user.id,
            "PERFORMANCE_DATA_EXPORTED",
            {
                "format": format,
                "days": days,
                "records_count": len(export_data)
            }
        )

        if format == "json":
            return {
                "success": True,
                "format": "json",
                "data": export_data,
                "total_records": len(export_data),
                "period_days": days
            }

        elif format == "csv":
            # For CSV, return data that frontend can convert
            return {
                "success": True,
                "format": "csv",
                "headers": list(export_data[0].keys()) if export_data else [],
                "data": export_data,
                "total_records": len(export_data),
                "period_days": days,
                "filename": f"performance_data_{days}days_{datetime.utcnow().strftime('%Y%m%d')}.csv"
            }

        else:  # PDF format
            return {
                "success": True,
                "format": "pdf",
                "message": "PDF export functionality to be implemented",
                "data_summary": {
                    "total_records": len(export_data),
                    "period_days": days,
                    "date_range": f"{start_date.date()} to {datetime.utcnow().date()}"
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export data: {str(e)}"
        )


@router.get("/insights", response_model=Dict[str, Any])
async def get_performance_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI-powered performance insights and recommendations"""
    try:
        # Get user's performance data
        user_stats = PerformanceTrackingService.get_user_performance_stats(
            db=db,
            user_id=current_user.id,
            days=30
        )

        if not user_stats["success"] or user_stats["stats"]["documents_created"] == 0:
            return {
                "success": True,
                "insights": {
                    "message": "Create more documents to get personalized insights!",
                    "recommendations": [
                        "Try creating your first document to see how much time you can save",
                        "Explore different templates to find ones that work best for you",
                        "Use the draft system to save time on complex documents"
                    ]
                }
            }

        stats = user_stats["stats"]

        # Generate insights
        insights = {
            "productivity_level": "high" if stats["efficiency_score"] > 70 else "medium" if stats["efficiency_score"] > 40 else "low",
            "time_saved_trend": "increasing" if stats["documents_created"] > 5 else "stable",
            "speed_rating": "fast" if stats["average_generation_time_seconds"] < 10 else "average",
            "recommendations": []
        }

        # Generate recommendations
        if stats["efficiency_score"] < 50:
            insights["recommendations"].append("Try using templates with fewer placeholders to improve your efficiency")

        if stats["average_generation_time_seconds"] > 15:
            insights["recommendations"].append("Consider using simpler templates or pre-filling common information")

        if stats["documents_per_day"] < 1:
            insights["recommendations"].append("Regular usage can help you save even more time - try creating documents daily")

        if stats["time_saved_per_document"] > 10:
            insights["recommendations"].append("Great job! You're saving significant time per document")
        else:
            insights["recommendations"].append("Try batch processing similar documents to save even more time")

        # Add positive reinforcement
        if stats["total_time_saved_hours"] > 1:
            insights["achievements"] = [
                f"You've saved {stats['total_time_saved_hours']:.1f} hours this month! 🎉",
                f"That's equivalent to {int(stats['total_time_saved_hours'] * 60)} minutes of productive time!"
            ]

        return {
            "success": True,
            "period_analyzed": "30 days",
            "insights": insights,
            "stats_summary": {
                "documents_created": stats["documents_created"],
                "total_time_saved_hours": stats["total_time_saved_hours"],
                "efficiency_score": stats["efficiency_score"],
                "average_generation_time": f"{stats['average_generation_time_seconds']:.1f}s"
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get insights: {str(e)}"
        )


# Helper function for dashboard stats
def _generate_productivity_message(stats: Dict[str, Any]) -> str:
    """Generate a motivational message based on user stats"""
    if stats["documents_created"] == 0:
        return "Ready to save time? Create your first document!"

    if stats["efficiency_score"] > 80:
        return f"Excellent! You're a productivity superstar! 🌟"
    elif stats["efficiency_score"] > 60:
        return f"Great work! You're saving lots of time! 👏"
    elif stats["efficiency_score"] > 40:
        return f"Good progress! Keep creating to save more time! 📈"
    else:
        return f"Every document saves time - keep it up! 💪"

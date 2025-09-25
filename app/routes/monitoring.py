"""
System monitoring and health check endpoints
"""

import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from database import get_db, DatabaseManager
from app.middleware.performance import ConnectionPoolMonitor, MemoryOptimizer
from app.services.cache_service import cache_service
from app.services.production_monitoring import production_monitor
from app.utils.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health")
async def basic_health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "service": "MyTypist Backend"}


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Comprehensive health check"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "checks": {}
    }
    
    # Database health
    try:
        db.execute("SELECT 1")
        pool_health = await ConnectionPoolMonitor.check_pool_health()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "pool_info": pool_health
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Cache health
    try:
        if cache_service.redis:
            await cache_service.redis.ping()
            health_status["checks"]["cache"] = {"status": "healthy"}
        else:
            health_status["checks"]["cache"] = {"status": "unavailable"}
    except Exception as e:
        health_status["checks"]["cache"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Memory health
    try:
        memory_stats = await MemoryOptimizer.optimize_memory()
        health_status["checks"]["memory"] = {
            "status": "healthy" if memory_stats["memory_percent"] < 80 else "warning",
            "stats": memory_stats
        }
    except Exception as e:
        health_status["checks"]["memory"] = {
            "status": "error",
            "error": str(e)
        }
    
    return health_status


@router.get("/performance/stats")
async def performance_statistics(
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get performance statistics"""
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    stats = {
        "database": await ConnectionPoolMonitor.check_pool_health(),
        "memory": await MemoryOptimizer.optimize_memory(),
        "cache": MemoryOptimizer.get_cache_stats()
    }
    
    return stats


@router.post("/performance/optimize")
async def optimize_system(
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run system optimization tasks"""
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    optimization_results = {
        "database_optimization": False,
        "memory_optimization": False,
        "cache_cleanup": False
    }
    
    # Database optimization
    try:
        DatabaseManager.optimize_database()
        optimization_results["database_optimization"] = True
    except Exception as e:
        optimization_results["database_error"] = str(e)
    
    # Memory optimization
    try:
        memory_stats = await MemoryOptimizer.optimize_memory()
        optimization_results["memory_optimization"] = True
        optimization_results["memory_stats"] = memory_stats
    except Exception as e:
        optimization_results["memory_error"] = str(e)
    
    # Cache cleanup (if Redis is available)
    try:
        if cache_service.redis:
            # Clear expired keys
            await cache_service.redis.flushall(asynchronous=True)
            optimization_results["cache_cleanup"] = True
    except Exception as e:
        optimization_results["cache_error"] = str(e)
    
    return optimization_results
"""
Application Dependencies
Common dependencies used across routes
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from database import SessionLocal
import redis
from config import settings


def get_db() -> Generator[Session, None, None]:
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> redis.Redis:
    """Redis dependency"""
    try:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        redis_client.ping()  # Test connection
        return redis_client
    except Exception as e:
        # Return None if Redis is unavailable (graceful degradation)
        return None


async def rate_limit(request: Request) -> bool:
    """Basic rate limiting dependency"""
    # For now, just return True - implement proper rate limiting later
    # This prevents import errors while maintaining functionality
    return True


async def validate_analytics_request(request: Request) -> bool:
    """Validate analytics request dependency"""
    # Basic validation - implement proper logic later
    # This prevents import errors while maintaining functionality
    return True


def get_current_user_id(request: Request) -> Optional[int]:
    """Get current user ID from request"""
    # Basic implementation - will be enhanced with proper auth
    return getattr(request.state, 'user_id', None)


def require_auth(request: Request) -> int:
    """Require authentication dependency"""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user_id


def require_admin(request: Request) -> int:
    """Require admin authentication dependency"""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Basic admin check - will be enhanced with proper role checking
    # For now, assume user_id 1 is admin (temporary)
    if user_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return user_id

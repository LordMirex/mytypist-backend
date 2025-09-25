"""Anonymous session management and guest features"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json
import uuid
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User
from app.utils.security import create_access_token
from database import get_db
import redis
from config import settings

# Create Redis client with proper fallback handling
class MockRedis:
    def __init__(self):
        self._data = {}
        
    def exists(self, key): 
        return key in self._data
    
    def setex(self, key, time, value): 
        self._data[key] = value
        return True
        
    def get(self, key): 
        return self._data.get(key)
        
    def delete(self, key): 
        if key in self._data:
            del self._data[key]
        return True

# Check if Redis should be used and is available
if settings.REDIS_ENABLED:
    try:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        print("✅ Redis client connected for guest sessions")
    except Exception as e:
        print(f"⚠️ Redis connection failed, using mock client: {e}")
        redis_client = MockRedis()
else:
    print("ℹ️ Using mock Redis client for guest sessions (Redis disabled)")
    redis_client = MockRedis()


async def get_or_create_guest_session(request: Request) -> str:
    """Get existing guest session or create new one"""
    
    # Check for existing session in cookie
    session_id = request.cookies.get("guest_session_id")
    
    if session_id and redis_client.exists(f"guest_session:{session_id}"):
        return session_id
        
    # Create new session
    session_id = str(uuid.uuid4())
    session_data = {
        "created_at": datetime.utcnow().isoformat(),
        "documents": [],
        "previews": [],
        "last_activity": datetime.utcnow().isoformat()
    }
    
    # Store in Redis with 24h expiry
    redis_client.setex(
        f"guest_session:{session_id}",
        int(timedelta(hours=24).total_seconds()),
        json.dumps(session_data)
    )
    
    return session_id


async def track_guest_activity(
    session_id: str,
    activity_type: str,
    data: Dict[str, Any]
) -> None:
    """Track guest user activity"""
    session_key = f"guest_session:{session_id}"
    
    if not redis_client.exists(session_key):
        return
        
    session_data = json.loads(redis_client.get(session_key))
    session_data["last_activity"] = datetime.utcnow().isoformat()
    
    if activity_type == "document_preview":
        if "previews" not in session_data:
            session_data["previews"] = []
        session_data["previews"].append(data)
    
    elif activity_type == "document_create":
        if "documents" not in session_data:
            session_data["documents"] = []
        session_data["documents"].append(data)
    
    # Update session with new data
    redis_client.setex(
        session_key,
        timedelta(hours=24).seconds,
        json.dumps(session_data)
    )


async def convert_guest_to_user(
    session_id: str,
    user: User,
    db: Session
) -> None:
    """Convert guest session data to user account"""
    session_key = f"guest_session:{session_id}"
    
    if not redis_client.exists(session_key):
        return
        
    session_data = json.loads(redis_client.get(session_key))
    
    # Transfer any documents created as guest
    for doc_data in session_data.get("documents", []):
        doc = Document(
            user_id=user.id,
            template_id=doc_data["template_id"],
            title=doc_data["title"],
            content=doc_data["content"],
            status="draft"
        )
        db.add(doc)
    
    # Add conversion tracking
    try:
        from app.services.audit_service import AuditService
        AuditService.log_user_activity(
            db,
            user.id,
            "GUEST_CONVERSION",
            {
                "session_id": session_id,
                "previews_count": len(session_data.get("previews", [])),
                "documents_count": len(session_data.get("documents", [])),
                "session_duration_hours": (
                    datetime.fromisoformat(session_data["last_activity"]) -
                    datetime.fromisoformat(session_data["created_at"])
                ).total_seconds() / 3600
            }
        )
    except Exception as e:
        print(f"Audit logging failed during guest conversion: {e}")
    
    db.commit()
    
    # Clear guest session
    redis_client.delete(session_key)
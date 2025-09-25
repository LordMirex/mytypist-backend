"""
Anonymous Session Management Service
"""

from datetime import datetime, timezone, timedelta
import uuid
from sqlalchemy.orm import Session
from typing import Optional, Tuple

from app.models.user import User, UserRole, UserStatus
from app.models.token import UserToken


class AnonymousSessionService:
    def __init__(self, db: Session):
        self.db = db
        self.session_expiry = timedelta(hours=24)  # Anonymous sessions expire after 24 hours
        self.initial_tokens = 3  # Number of free tokens for anonymous users

    async def create_anonymous_session(self) -> Tuple[User, str]:
        """
        Create a new anonymous user session with temporary credentials
        Returns (user, session_id)
        """
        # Generate unique username and session ID
        session_id = str(uuid.uuid4())
        username = f"guest_{session_id[:8]}"
        
        # Create temporary user
        user = User(
            username=username,
            email=f"{username}@temp.mytypist.net",  # Temporary email
            password_hash="",  # No password for temporary users
            role=UserRole.GUEST,
            status=UserStatus.ACTIVE
        )
        self.db.add(user)
        self.db.flush()  # Get user ID

        # Allocate initial tokens
        user_tokens = UserToken(
            user_id=user.id,
            document_tokens=self.initial_tokens,
            lifetime_earned=self.initial_tokens
        )
        self.db.add(user_tokens)
        
        self.db.commit()
        return user, session_id

    async def get_anonymous_session(self, session_id: str) -> Optional[User]:
        """
        Retrieve an anonymous session by session ID
        Returns None if session is expired or not found
        """
        # Extract username from session ID
        username = f"guest_{session_id[:8]}"
        
        user = (
            self.db.query(User)
            .filter(
                User.username == username,
                User.role == UserRole.GUEST,
                User.status == UserStatus.ACTIVE
            )
            .first()
        )

        if not user:
            return None

        # Check if session is expired
        if self._is_session_expired(user):
            user.status = UserStatus.INACTIVE
            self.db.commit()
            return None

        return user

    async def convert_to_registered(self, session_id: str, email: str, password_hash: str) -> Optional[User]:
        """
        Convert an anonymous session into a registered user account
        Preserves document history and remaining tokens
        """
        user = await self.get_anonymous_session(session_id)
        if not user:
            return None

        # Update user details
        user.email = email
        user.password_hash = password_hash
        user.role = UserRole.USER
        user.username = email.split("@")[0]  # Use email prefix as username

        self.db.commit()
        return user

    def _is_session_expired(self, user: User) -> bool:
        """Check if an anonymous session has expired"""
        if user.role != UserRole.GUEST:
            return False
            
        session_age = datetime.now(timezone.utc) - user.created_at
        return session_age > self.session_expiry
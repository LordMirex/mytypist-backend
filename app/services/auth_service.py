"""
Authentication and authorization service
"""

import os
import json
import logging
from jose import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import settings
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate
from app.services.audit_service import AuditService
from database import get_db

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = HTTPBearer()

# Logger
logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and authorization service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: Dict[Any, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode.update({"exp": expire, "type": "access"})
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.JWT_SECRET_KEY, 
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[Any, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[Any, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                return None
                
            return payload
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, request: Request) -> User:
        """Create a new user account"""
        
        # Hash password
        hashed_password = AuthService.hash_password(user_data.password)
        
        # Create user
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            company=user_data.company,
            job_title=user_data.job_title,
            bio=user_data.bio,
            role=user_data.role,
            gdpr_consent=user_data.gdpr_consent,
            gdpr_consent_date=datetime.utcnow() if user_data.gdpr_consent else None,
            marketing_consent=user_data.marketing_consent,
            created_at=datetime.utcnow()
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return db_user
    
    @staticmethod
    def create_password_reset_token(email: str) -> str:
        """Create password reset token"""
        data = {
            "email": email,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        }
        
        token = jwt.encode(
            data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return token
    
    @staticmethod
    def verify_password_reset_token(token: str) -> Optional[str]:
        """Verify password reset token and return email"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "password_reset":
                return None
                
            return payload.get("email")
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def create_email_verification_token(email: str) -> str:
        """Create email verification token"""
        data = {
            "email": email,
            "type": "email_verification",
            "exp": datetime.utcnow() + timedelta(days=7)  # 7 days expiry
        }
        
        token = jwt.encode(
            data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return token
    
    @staticmethod
    def verify_email_token(token: str) -> Optional[str]:
        """Verify email verification token and return email"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "email_verification":
                return None
                
            return payload.get("email")
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def check_user_permissions(user: User, resource: str, action: str) -> bool:
        """Check if user has permission to perform action on resource"""
        
        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True
        
        # Define permission matrix
        permissions = {
            UserRole.STANDARD: {
                "documents": ["create", "read", "update", "delete"],
                "templates": ["read", "use"],
                "signatures": ["create", "read"],
                "payments": ["create", "read"],
                "analytics": ["read"]
            },
            UserRole.GUEST: {
                "documents": ["read"],
                "templates": ["read"],
                "signatures": ["read"],
                "payments": [],
                "analytics": []
            }
        }
        
        user_permissions = permissions.get(user.role, {})
        resource_permissions = user_permissions.get(resource, [])
        
        return action in resource_permissions
    
    @staticmethod
    async def generate_api_key(db: Session, user_id: int, name: str = None) -> str:
        """Generate API key for user and store in Redis"""
        try:
            import redis
            
            # Create a secure random API key
            api_key_secret = secrets.token_urlsafe(32)
            api_key = f"mtk_{api_key_secret}"
            
            # Initialize Redis connection
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # Store API key data in Redis
            api_key_data = {
                "user_id": user_id,
                "type": "api_key",
                "name": name or f"API Key {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                "created_at": datetime.utcnow().isoformat(),
                "last_used": None,
                "usage_count": 0
            }
            
            # Store with 1 year expiry by default
            redis_key = f"api_key:{api_key}"
            redis_client.setex(redis_key, 365 * 24 * 3600, json.dumps(api_key_data))
            
            # Also store reverse lookup
            user_api_keys_key = f"user_api_keys:{user_id}"
            redis_client.sadd(user_api_keys_key, api_key)
            redis_client.expire(user_api_keys_key, 365 * 24 * 3600)
            
            logger.info(f"Generated API key for user {user_id}")
            return api_key
            
        except Exception as e:
            logger.error(f"API key generation failed for user {user_id}: {e}")
            raise
    
    @staticmethod
    async def verify_api_key(api_key: str) -> Optional[int]:
        """Verify API key and return user_id"""
        try:
            import redis
            
            if not api_key.startswith("mtk_"):
                return None
            
            # Initialize Redis connection
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # Retrieve API key data from Redis
            redis_key = f"api_key:{api_key}"
            api_key_data = redis_client.get(redis_key)
            
            if not api_key_data:
                return None
            
            # Parse API key data
            data = json.loads(api_key_data)
            user_id = data.get("user_id")
            
            if user_id:
                # Update last used timestamp and increment usage count
                data["last_used"] = datetime.utcnow().isoformat()
                data["usage_count"] = data.get("usage_count", 0) + 1
                
                # Update in Redis
                redis_client.setex(redis_key, 365 * 24 * 3600, json.dumps(data))
                
            return user_id
            
        except Exception as e:
            logger.error(f"API key verification failed: {e}")
            return None
    
    @staticmethod
    def is_secure_password(password: str) -> bool:
        """Check if password meets security requirements"""
        if len(password) < 8:
            return False
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        return all([has_upper, has_lower, has_digit, has_special])
    
    @staticmethod
    async def check_rate_limit(user_id: int, action: str, limit: int, window: int) -> bool:
        """Check if user action is within rate limit using Redis sliding window"""
        try:
            import redis
            import time
            
            # Initialize Redis connection if not available
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # Create rate limit key
            rate_limit_key = f"rate_limit:{user_id}:{action}"
            current_time = time.time()
            
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()
            
            # Remove expired entries (sliding window)
            pipe.zremrangebyscore(rate_limit_key, 0, current_time - window)
            
            # Count current entries in window
            pipe.zcard(rate_limit_key)
            
            # Execute pipeline
            results = pipe.execute()
            current_count = results[1]
            
            # Check if limit exceeded
            if current_count >= limit:
                return False
            
            # Add current request timestamp
            redis_client.zadd(rate_limit_key, {str(current_time): current_time})
            redis_client.expire(rate_limit_key, window + 10)  # Small buffer for cleanup
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiting fails
            return True
    
    @staticmethod
    def log_security_event(event_type: str, user_id: Optional[int], request: Request, details: Dict[str, Any]):
        """Log security-related events"""
        AuditService.log_security_event(event_type, user_id, request, details)
    
    @staticmethod
    async def revoke_user_tokens(user_id: int):
        """Revoke all tokens for a user (logout from all devices)"""
        try:
            import redis
            import time
            
            # Initialize Redis connection
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # Set token revocation timestamp for user
            revocation_key = f"token_revocation:{user_id}"
            current_time = int(time.time())
            
            # Store revocation timestamp
            redis_client.set(revocation_key, current_time, ex=86400 * 30)  # 30 days expiry
            
            # Also blacklist all current user sessions
            session_pattern = f"user_session:{user_id}:*"
            for key in redis_client.scan_iter(match=session_pattern):
                redis_client.delete(key)
            
            logger.info(f"Revoked all tokens for user {user_id}")
            
        except Exception as e:
            logger.error(f"Token revocation failed for user {user_id}: {e}")
            raise
    
    @staticmethod
    async def cleanup_expired_tokens():
        """Cleanup expired tokens from blacklist/cache"""
        try:
            import redis
            import time
            
            # Initialize Redis connection
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            current_time = time.time()
            cleanup_count = 0
            
            # Clean up rate limit entries
            for key in redis_client.scan_iter(match="rate_limit:*"):
                try:
                    # Remove expired entries from sorted sets
                    removed = redis_client.zremrangebyscore(key, 0, current_time - 3600)  # 1 hour cleanup
                    cleanup_count += removed
                    
                    # Remove empty rate limit keys
                    if redis_client.zcard(key) == 0:
                        redis_client.delete(key)
                        cleanup_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to cleanup rate limit key {key}: {e}")
            
            # Clean up expired user sessions
            session_count = 0
            for key in redis_client.scan_iter(match="user_session:*"):
                try:
                    ttl = redis_client.ttl(key)
                    if ttl == -1:  # No expiry set
                        redis_client.expire(key, 86400)  # Set 24 hour expiry
                    elif ttl == -2:  # Key doesn't exist
                        session_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cleanup session key {key}: {e}")
            
            # Clean up API key cache
            api_key_count = 0
            for key in redis_client.scan_iter(match="api_key:*"):
                try:
                    if redis_client.ttl(key) == -2:  # Key doesn't exist
                        api_key_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cleanup API key {key}: {e}")
                    
            logger.info(f"Cleaned up {cleanup_count} expired tokens, {session_count} sessions, {api_key_count} API keys")
            
        except Exception as e:
            logger.error(f"Token cleanup failed: {e}")
            raise

    @staticmethod
    async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> User:
        """Get current user from JWT token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        token = credentials.credentials
        
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id: int = payload.get("sub")
            if user_id is None:
                raise credentials_exception
                
        except jwt.InvalidTokenError:
            raise credentials_exception
            
        db = next(get_db())
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                raise credentials_exception
            return user
        finally:
            db.close()

    @staticmethod  
    async def get_current_admin_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> User:
        """Get current admin user from JWT token"""
        current_user = await AuthService.get_current_user(credentials)
        
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
            
        return current_user

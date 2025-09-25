"""
Security utility functions
"""

from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from fastapi import Depends, HTTPException, status, Request, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

security = HTTPBearer()


def validate_file_security(file: UploadFile) -> bool:
    """Validate file security properties"""
    try:
        # Basic security validation for uploaded files
        # Check file extension is safe
        safe_extensions = ['.docx', '.pdf', '.txt', '.png', '.jpg', '.jpeg']
        file_ext = Path(file.filename).suffix.lower() if file.filename else ''
        
        if file_ext not in safe_extensions:
            return False
            
        # Check file size (max 10MB)
        if hasattr(file, 'size') and file.size and file.size > 10 * 1024 * 1024:
            return False
            
        return True
    except Exception:
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token"""
    
    try:
        # Verify token
        payload = AuthService.verify_token(credentials.credentials, "access")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Get user from database
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return user
    
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account"
        )
    
    return current_user


async def verify_admin_role(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Verify user has admin role"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


# Alias for compatibility
require_admin = verify_admin_role


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def sanitize_content(content: str) -> str:
    """Sanitize user content for security"""
    if not content:
        return ""
    
    # Basic HTML escaping and content sanitization
    import html
    sanitized = html.escape(content)
    
    # Remove any potential script tags or dangerous content
    import re
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    return sanitized


def verify_resource_access(user: User, resource_user_id: int, admin_override: bool = True) -> bool:
    """Verify user can access resource"""
    
    # User can access their own resources
    if user.id == resource_user_id:
        return True
    
    # Admin can access all resources if override is enabled
    if admin_override and user.role == UserRole.ADMIN:
        return True
    
    return False


def check_subscription_limits(user: User, action: str) -> bool:
    """Check if user's subscription allows the action"""
    
    # Get user's current subscription
    from app.models.payment import Subscription, SubscriptionStatus
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).first()
        
        if not subscription:
            # No active subscription - check free limits
            return check_free_tier_limits(db, user, action)
        
        # Check subscription limits
        if action == "create_document":
            if subscription.documents_limit == -1:  # Unlimited
                return True
            return subscription.documents_used < subscription.documents_limit
        
        elif action == "upload_template":
            if subscription.custom_templates:
                return True
            return False
        
        elif action == "api_access":
            return subscription.api_access
        
        return True
    
    finally:
        db.close()


def check_free_tier_limits(db: Session, user: User, action: str) -> bool:
    """Check free tier limits"""
    
    from app.models.document import Document
    from datetime import datetime, timedelta
    
    if action == "create_document":
        # Check monthly document limit for free users
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        documents_this_month = db.query(Document).filter(
            Document.user_id == user.id,
            Document.created_at >= current_month_start
        ).count()
        
        return documents_this_month < settings.FREE_PLAN_DOCUMENTS_PER_MONTH
    
    elif action == "upload_template":
        # Free users cannot upload custom templates
        return False
    
    elif action == "api_access":
        # Free users don't have API access
        return False
    
    return True


def generate_secure_filename(original_filename: str, user_id: int) -> str:
    """Generate secure filename"""
    
    import uuid
    import os
    from pathlib import Path
    
    # Get file extension
    file_extension = Path(original_filename).suffix.lower()
    
    # Generate UUID-based filename
    secure_name = f"{user_id}_{uuid.uuid4().hex}{file_extension}"
    
    return secure_name


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for security"""
    
    import re
    
    # Remove directory traversal attempts
    filename = filename.replace("../", "").replace("..\\", "")
    
    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename


def validate_api_key(api_key: str, db: Session) -> Optional[User]:
    """Validate API key and return associated user"""
    
    user_id = AuthService.verify_api_key(api_key)
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None
    
    # Check if user has API access
    if not check_subscription_limits(user, "api_access"):
        return None
    
    return user


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for storage"""
    
    import hashlib
    
    # Use SHA-256 with salt
    salt = settings.SECRET_KEY.encode()
    return hashlib.pbkdf2_hmac('sha256', data.encode(), salt, 100000).hex()


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """Mask sensitive data for display"""
    
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    return data[:visible_chars] + mask_char * (len(data) - visible_chars)


def verify_csrf_token(request_token: str, session_token: str) -> bool:
    """Verify CSRF token"""
    
    import hmac
    import hashlib
    
    # Simple CSRF verification
    expected_token = hmac.new(
        session_token.encode(),
        b"csrf_protection",
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(request_token, expected_token)


def generate_csrf_token(session_id: str) -> str:
    """Generate CSRF token"""
    
    import hmac
    import hashlib
    
    return hmac.new(
        session_id.encode(),
        b"csrf_protection",
        hashlib.sha256
    ).hexdigest()


class SecurityHeaders:
    """Security headers utility"""
    
    @staticmethod
    def get_security_headers() -> dict:
        """Get security headers for responses"""
        
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
    
    @staticmethod
    def apply_security_headers(response):
        """Apply security headers to response"""
        
        headers = SecurityHeaders.get_security_headers()
        for header, value in headers.items():
            response.headers[header] = value
        
        return response


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    
    # Check for X-Forwarded-For header (proxy/load balancer)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Take the first IP in the chain
        return x_forwarded_for.split(",")[0].strip()
    
    # Check for X-Real-IP header (nginx proxy)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()
    
    # Fall back to direct client IP
    client_host = request.client.host if request.client else "unknown"
    return client_host

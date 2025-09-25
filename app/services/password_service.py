"""
Enhanced Password Security Service
Implements strong password policies, validation, and security features
"""

import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

from config import settings
from database import Base
from app.services.audit_service import AuditService

# Enhanced password context with multiple algorithms
pwd_context = CryptContext(
    schemes=["bcrypt", "scrypt", "pbkdf2_sha256"],
    deprecated="auto",
    bcrypt__rounds=12,  # Increased rounds for better security
    scrypt__rounds=32768,
    pbkdf2_sha256__rounds=200000
)


class PasswordHistory(Base):
    """Track password history to prevent reuse"""
    __tablename__ = "password_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordAttempt(Base):
    """Track failed password attempts for account lockout"""
    __tablename__ = "password_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    success = Column(Boolean, nullable=False, default=False)
    attempt_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_agent = Column(Text, nullable=True)
    blocked = Column(Boolean, nullable=False, default=False)


class PasswordSecurityService:
    """Enhanced password security service"""

    # Password policy configuration
    MIN_LENGTH = 12
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL_CHARS = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Account lockout configuration
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 30  # minutes
    PROGRESSIVE_DELAY = True

    # Password history configuration
    PASSWORD_HISTORY_COUNT = 10
    MIN_PASSWORD_AGE = 1  # days
    MAX_PASSWORD_AGE = 90  # days

    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, any]:
        """
        Comprehensive password strength validation
        Returns validation result with detailed feedback
        """
        result = {
            "is_valid": True,
            "score": 0,
            "errors": [],
            "suggestions": [],
            "strength": "weak"
        }

        # Length validation
        if len(password) < PasswordSecurityService.MIN_LENGTH:
            result["errors"].append(f"Password must be at least {PasswordSecurityService.MIN_LENGTH} characters long")
            result["is_valid"] = False
        elif len(password) > PasswordSecurityService.MAX_LENGTH:
            result["errors"].append(f"Password must not exceed {PasswordSecurityService.MAX_LENGTH} characters")
            result["is_valid"] = False
        else:
            result["score"] += 10

        # Character type validation
        if PasswordSecurityService.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            result["errors"].append("Password must contain at least one uppercase letter")
            result["is_valid"] = False
        else:
            result["score"] += 15

        if PasswordSecurityService.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            result["errors"].append("Password must contain at least one lowercase letter")
            result["is_valid"] = False
        else:
            result["score"] += 15

        if PasswordSecurityService.REQUIRE_NUMBERS and not re.search(r'\d', password):
            result["errors"].append("Password must contain at least one number")
            result["is_valid"] = False
        else:
            result["score"] += 15

        if PasswordSecurityService.REQUIRE_SPECIAL_CHARS and not re.search(f'[{re.escape(PasswordSecurityService.SPECIAL_CHARS)}]', password):
            result["errors"].append(f"Password must contain at least one special character: {PasswordSecurityService.SPECIAL_CHARS}")
            result["is_valid"] = False
        else:
            result["score"] += 15

        # Advanced security checks
        # Check for common patterns
        if re.search(r'(.)\1{2,}', password):  # Repeated characters
            result["score"] -= 10
            result["suggestions"].append("Avoid repeating the same character multiple times")

        if re.search(r'(012|123|234|345|456|567|678|789|890|abc|def|qwe|asd|zxc)', password.lower()):
            result["score"] -= 15
            result["suggestions"].append("Avoid sequential characters or keyboard patterns")

        # Check for common weak passwords
        weak_patterns = [
            r'password', r'123456', r'qwerty', r'admin', r'login',
            r'welcome', r'monkey', r'dragon', r'master', r'shadow'
        ]
        for pattern in weak_patterns:
            if re.search(pattern, password.lower()):
                result["score"] -= 20
                result["suggestions"].append("Avoid common words and patterns")
                break

        # Entropy calculation
        charset_size = 0
        if re.search(r'[a-z]', password):
            charset_size += 26
        if re.search(r'[A-Z]', password):
            charset_size += 26
        if re.search(r'\d', password):
            charset_size += 10
        if re.search(f'[{re.escape(PasswordSecurityService.SPECIAL_CHARS)}]', password):
            charset_size += len(PasswordSecurityService.SPECIAL_CHARS)

        entropy = len(password) * (charset_size.bit_length() if charset_size > 0 else 0)
        if entropy >= 60:
            result["score"] += 20
        elif entropy >= 40:
            result["score"] += 10

        # Determine strength
        if result["score"] >= 80:
            result["strength"] = "very_strong"
        elif result["score"] >= 60:
            result["strength"] = "strong"
        elif result["score"] >= 40:
            result["strength"] = "medium"
        elif result["score"] >= 20:
            result["strength"] = "weak"
        else:
            result["strength"] = "very_weak"

        # Add suggestions for improvement
        if result["strength"] in ["weak", "very_weak"]:
            result["suggestions"].extend([
                "Use a longer password (14+ characters)",
                "Include a mix of uppercase, lowercase, numbers, and symbols",
                "Avoid personal information and common words",
                "Consider using a passphrase with random words"
            ])

        return result

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with enhanced security"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def check_password_history(db: Session, user_id: int, new_password: str) -> bool:
        """Check if password was used recently"""
        recent_passwords = db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id
        ).order_by(PasswordHistory.created_at.desc()).limit(
            PasswordSecurityService.PASSWORD_HISTORY_COUNT
        ).all()

        for history_entry in recent_passwords:
            if pwd_context.verify(new_password, history_entry.password_hash):
                return False  # Password was used recently

        return True  # Password is not in recent history

    @staticmethod
    def add_password_to_history(db: Session, user_id: int, password_hash: str):
        """Add password to history"""
        history_entry = PasswordHistory(
            user_id=user_id,
            password_hash=password_hash
        )
        db.add(history_entry)

        # Clean up old history entries
        old_entries = db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id
        ).order_by(PasswordHistory.created_at.desc()).offset(
            PasswordSecurityService.PASSWORD_HISTORY_COUNT
        ).all()

        for entry in old_entries:
            db.delete(entry)

        db.commit()

    @staticmethod
    def record_login_attempt(db: Session, user_id: Optional[int], ip_address: str,
                           email: Optional[str], success: bool, user_agent: str = None) -> bool:
        """
        Record login attempt and check for account lockout
        Returns True if account should be locked
        """
        attempt = PasswordAttempt(
            user_id=user_id,
            ip_address=ip_address,
            email=email,
            success=success,
            user_agent=user_agent
        )
        db.add(attempt)
        db.commit()

        if success:
            return False  # Successful login, no lockout needed

        # Check failed attempts in lockout window
        lockout_start = datetime.utcnow() - timedelta(minutes=PasswordSecurityService.LOCKOUT_DURATION)

        # Count failed attempts for this user/IP
        failed_attempts = db.query(PasswordAttempt).filter(
            PasswordAttempt.ip_address == ip_address,
            PasswordAttempt.success == False,
            PasswordAttempt.attempt_time >= lockout_start
        )

        if user_id:
            failed_attempts = failed_attempts.filter(PasswordAttempt.user_id == user_id)
        elif email:
            failed_attempts = failed_attempts.filter(PasswordAttempt.email == email)

        failed_count = failed_attempts.count()

        if failed_count >= PasswordSecurityService.MAX_ATTEMPTS:
            # Mark attempts as blocked
            failed_attempts.update({PasswordAttempt.blocked: True})
            db.commit()

            # Log security event
            AuditService.log_security_event(
                "ACCOUNT_LOCKED",
                user_id,
                None,
                {
                    "ip_address": ip_address,
                    "email": email,
                    "failed_attempts": failed_count,
                    "lockout_duration": PasswordSecurityService.LOCKOUT_DURATION
                }
            )

            return True  # Account should be locked

        return False  # No lockout needed yet

    @staticmethod
    def is_account_locked(db: Session, user_id: Optional[int], ip_address: str,
                         email: Optional[str] = None) -> Dict[str, any]:
        """Check if account is currently locked"""
        lockout_start = datetime.utcnow() - timedelta(minutes=PasswordSecurityService.LOCKOUT_DURATION)

        query = db.query(PasswordAttempt).filter(
            PasswordAttempt.ip_address == ip_address,
            PasswordAttempt.blocked == True,
            PasswordAttempt.attempt_time >= lockout_start
        )

        if user_id:
            query = query.filter(PasswordAttempt.user_id == user_id)
        elif email:
            query = query.filter(PasswordAttempt.email == email)

        blocked_attempt = query.order_by(PasswordAttempt.attempt_time.desc()).first()

        if blocked_attempt:
            time_remaining = (blocked_attempt.attempt_time + timedelta(
                minutes=PasswordSecurityService.LOCKOUT_DURATION
            ) - datetime.utcnow()).total_seconds()

            if time_remaining > 0:
                return {
                    "is_locked": True,
                    "time_remaining": int(time_remaining),
                    "unlock_time": blocked_attempt.attempt_time + timedelta(
                        minutes=PasswordSecurityService.LOCKOUT_DURATION
                    )
                }

        return {"is_locked": False}

    @staticmethod
    def clear_failed_attempts(db: Session, user_id: int, ip_address: str):
        """Clear failed attempts after successful login"""
        db.query(PasswordAttempt).filter(
            PasswordAttempt.user_id == user_id,
            PasswordAttempt.ip_address == ip_address,
            PasswordAttempt.success == False
        ).delete()
        db.commit()

    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """Generate a cryptographically secure password"""
        if length < PasswordSecurityService.MIN_LENGTH:
            length = PasswordSecurityService.MIN_LENGTH

        # Ensure at least one character from each required category
        password = []

        if PasswordSecurityService.REQUIRE_UPPERCASE:
            password.append(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        if PasswordSecurityService.REQUIRE_LOWERCASE:
            password.append(secrets.choice("abcdefghijklmnopqrstuvwxyz"))
        if PasswordSecurityService.REQUIRE_NUMBERS:
            password.append(secrets.choice("0123456789"))
        if PasswordSecurityService.REQUIRE_SPECIAL_CHARS:
            password.append(secrets.choice(PasswordSecurityService.SPECIAL_CHARS))

        # Fill remaining length with random characters
        all_chars = ""
        if PasswordSecurityService.REQUIRE_UPPERCASE:
            all_chars += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if PasswordSecurityService.REQUIRE_LOWERCASE:
            all_chars += "abcdefghijklmnopqrstuvwxyz"
        if PasswordSecurityService.REQUIRE_NUMBERS:
            all_chars += "0123456789"
        if PasswordSecurityService.REQUIRE_SPECIAL_CHARS:
            all_chars += PasswordSecurityService.SPECIAL_CHARS

        for _ in range(length - len(password)):
            password.append(secrets.choice(all_chars))

        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(password)

        return ''.join(password)

    @staticmethod
    def check_password_age(password_changed_at: Optional[datetime]) -> Dict[str, any]:
        """Check if password needs to be changed due to age"""
        if not password_changed_at:
            return {
                "needs_change": True,
                "reason": "Password age unknown",
                "days_old": None
            }

        age = datetime.utcnow() - password_changed_at
        days_old = age.days

        if days_old >= PasswordSecurityService.MAX_PASSWORD_AGE:
            return {
                "needs_change": True,
                "reason": f"Password is {days_old} days old (max: {PasswordSecurityService.MAX_PASSWORD_AGE})",
                "days_old": days_old
            }
        elif days_old >= PasswordSecurityService.MAX_PASSWORD_AGE - 7:
            return {
                "needs_change": False,
                "warning": f"Password expires in {PasswordSecurityService.MAX_PASSWORD_AGE - days_old} days",
                "days_old": days_old
            }

        return {
            "needs_change": False,
            "days_old": days_old
        }

    @staticmethod
    def get_password_policy() -> Dict[str, any]:
        """Get current password policy for frontend display"""
        return {
            "min_length": PasswordSecurityService.MIN_LENGTH,
            "max_length": PasswordSecurityService.MAX_LENGTH,
            "require_uppercase": PasswordSecurityService.REQUIRE_UPPERCASE,
            "require_lowercase": PasswordSecurityService.REQUIRE_LOWERCASE,
            "require_numbers": PasswordSecurityService.REQUIRE_NUMBERS,
            "require_special_chars": PasswordSecurityService.REQUIRE_SPECIAL_CHARS,
            "special_chars": PasswordSecurityService.SPECIAL_CHARS,
            "password_history_count": PasswordSecurityService.PASSWORD_HISTORY_COUNT,
            "max_password_age_days": PasswordSecurityService.MAX_PASSWORD_AGE,
            "max_failed_attempts": PasswordSecurityService.MAX_ATTEMPTS,
            "lockout_duration_minutes": PasswordSecurityService.LOCKOUT_DURATION
        }

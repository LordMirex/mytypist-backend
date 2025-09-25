"""Shim module to provide canonical `FraudDetectionService` name.

This keeps the legacy `advanced_` implementation while exposing a
simpler import path for routes and services.
"""

from app.services.advanced_fraud_detection_service import AdvancedFraudDetectionService as FraudDetectionService

__all__ = ["FraudDetectionService"]
"""
Advanced Fraud Detection Service
Real-time fraud detection for payments, registrations, and suspicious activities
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float, func
from sqlalchemy.orm import relationship
from enum import Enum
import ipaddress
import re
import asyncio

from database import Base
from app.models.user import User
from config import settings

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudType(str, Enum):
    """Types of fraud detected"""
    MULTIPLE_ACCOUNTS = "multiple_accounts"
    PAYMENT_FRAUD = "payment_fraud"
    VELOCITY_ABUSE = "velocity_abuse"
    IP_ABUSE = "ip_abuse"
    DEVICE_ABUSE = "device_abuse"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    ACCOUNT_TAKEOVER = "account_takeover"
    FAKE_REGISTRATION = "fake_registration"


class FraudAlert(Base):
    """Fraud detection alerts"""
    __tablename__ = "fraud_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)

    # Alert details
    fraud_type = Column(String(50), nullable=False, index=True)
    risk_level = Column(String(20), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)  # 0.0 to 1.0

    # Detection details
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(1000), nullable=True)
    device_fingerprint = Column(String(200), nullable=True, index=True)

    # Evidence
    evidence = Column(JSON, nullable=False)
    description = Column(Text, nullable=False)

    # Actions taken
    action_taken = Column(String(100), nullable=True)
    is_resolved = Column(Boolean, nullable=False, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="fraud_alerts")
    resolved_by_user = relationship("User", foreign_keys=[resolved_by])


class DeviceFingerprint(Base):
    """Device fingerprinting for fraud detection"""
    __tablename__ = "device_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)

    # Fingerprint data
    fingerprint_hash = Column(String(64), nullable=False, index=True, unique=True)
    user_agent = Column(String(1000), nullable=True)
    screen_resolution = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    platform = Column(String(50), nullable=True)

    # Tracking
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    usage_count = Column(Integer, nullable=False, default=1)

    # Risk assessment
    risk_score = Column(Float, nullable=False, default=0.0)
    is_blocked = Column(Boolean, nullable=False, default=False)

    # Relationships
    user = relationship("User", backref="device_fingerprints")


class FraudDetectionService:
    """Advanced fraud detection and prevention service"""

    # Risk thresholds
    RISK_THRESHOLDS = {
        "multiple_registrations_per_ip": 3,
        "multiple_registrations_per_device": 2,
        "max_failed_payments_per_hour": 5,
        "max_token_purchases_per_hour": 10,
        "suspicious_velocity_threshold": 0.8
    }

    @staticmethod
    async def assess_registration_risk(
        db: Session,
        email: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint: str = None
    ) -> Dict[str, Any]:
        """Assess fraud risk for user registration"""

        risk_factors = []
        evidence = {}
        risk_score = 0.0

        try:
            # Check for multiple registrations from same IP
            recent_registrations = db.query(User).filter(
                User.last_login_ip == ip_address,
                User.created_at > datetime.utcnow() - timedelta(hours=24)
            ).count()

            if recent_registrations >= FraudDetectionService.RISK_THRESHOLDS["multiple_registrations_per_ip"]:
                risk_factors.append("multiple_ip_registrations")
                evidence["ip_registrations_24h"] = recent_registrations
                risk_score += 0.4

            # Check device fingerprint
            if device_fingerprint:
                device_usage = db.query(DeviceFingerprint).filter(
                    DeviceFingerprint.fingerprint_hash == device_fingerprint
                ).first()

                if device_usage and device_usage.usage_count >= FraudDetectionService.RISK_THRESHOLDS["multiple_registrations_per_device"]:
                    risk_factors.append("multiple_device_registrations")
                    evidence["device_usage_count"] = device_usage.usage_count
                    risk_score += 0.5

            # Check email patterns
            if FraudDetectionService._is_suspicious_email(email):
                risk_factors.append("suspicious_email_pattern")
                evidence["email_pattern"] = "suspicious"
                risk_score += 0.3

            # Check IP reputation
            ip_risk = await FraudDetectionService._check_ip_reputation(ip_address)
            if ip_risk["is_suspicious"]:
                risk_factors.append("suspicious_ip")
                evidence["ip_reputation"] = ip_risk
                risk_score += 0.3

            # Determine risk level
            if risk_score >= 0.8:
                risk_level = RiskLevel.CRITICAL
            elif risk_score >= 0.6:
                risk_level = RiskLevel.HIGH
            elif risk_score >= 0.3:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW

            return {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "evidence": evidence,
                "should_block": risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH],
                "requires_verification": risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]
            }

        except Exception as e:
            logger.error(f"Registration risk assessment failed: {e}")
            return {
                "risk_level": RiskLevel.LOW,
                "risk_score": 0.0,
                "risk_factors": [],
                "evidence": {"error": str(e)},
                "should_block": False,
                "requires_verification": False
            }

    @staticmethod
    async def assess_payment_risk(
        db: Session,
        user_id: int,
        amount: float,
        ip_address: str,
        payment_method: str,
        device_fingerprint: str = None
    ) -> Dict[str, Any]:
        """Assess fraud risk for payment transactions"""

        risk_factors = []
        evidence = {}
        risk_score = 0.0

        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"risk_level": RiskLevel.CRITICAL, "should_block": True}

            # Check payment velocity
            recent_payments = db.query(func.count()).filter(
                # Assuming payment table exists
                # Payment.user_id == user_id,
                # Payment.created_at > datetime.utcnow() - timedelta(hours=1)
            ).scalar() or 0

            if recent_payments >= FraudDetectionService.RISK_THRESHOLDS["max_token_purchases_per_hour"]:
                risk_factors.append("payment_velocity_abuse")
                evidence["recent_payments"] = recent_payments
                risk_score += 0.6

            # Check amount patterns
            if amount > 1000:  # Large amount
                risk_factors.append("large_amount")
                evidence["amount"] = amount
                risk_score += 0.2

            # Check IP consistency
            if user.last_login_ip and user.last_login_ip != ip_address:
                # Different IP from usual
                risk_factors.append("ip_change")
                evidence["usual_ip"] = user.last_login_ip
                evidence["current_ip"] = ip_address
                risk_score += 0.3

            # Check account age
            account_age_hours = (datetime.utcnow() - user.created_at).total_seconds() / 3600
            if account_age_hours < 24:  # Very new account
                risk_factors.append("new_account")
                evidence["account_age_hours"] = account_age_hours
                risk_score += 0.4

            # Determine risk level
            if risk_score >= 0.8:
                risk_level = RiskLevel.CRITICAL
            elif risk_score >= 0.6:
                risk_level = RiskLevel.HIGH
            elif risk_score >= 0.3:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW

            return {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "evidence": evidence,
                "should_block": risk_level == RiskLevel.CRITICAL,
                "requires_verification": risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]
            }

        except Exception as e:
            logger.error(f"Payment risk assessment failed: {e}")
            return {
                "risk_level": RiskLevel.MEDIUM,
                "risk_score": 0.5,
                "risk_factors": ["assessment_error"],
                "evidence": {"error": str(e)},
                "should_block": False,
                "requires_verification": True
            }

    @staticmethod
    async def create_fraud_alert(
        db: Session,
        user_id: Optional[int],
        fraud_type: str,
        risk_level: str,
        confidence_score: float,
        evidence: Dict[str, Any],
        description: str,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None
    ) -> FraudAlert:
        """Create fraud alert"""

        try:
            alert = FraudAlert(
                user_id=user_id,
                fraud_type=fraud_type,
                risk_level=risk_level,
                confidence_score=confidence_score,
                evidence=evidence,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint
            )

            db.add(alert)
            db.commit()
            db.refresh(alert)

            # Auto-take action based on risk level
            if risk_level == RiskLevel.CRITICAL:
                await FraudDetectionService._auto_block_user(db, user_id, alert.id)

            logger.warning(f"Fraud alert created: {fraud_type} for user {user_id}, risk: {risk_level}")
            return alert

        except Exception as e:
            logger.error(f"Failed to create fraud alert: {e}")
            db.rollback()
            raise

    @staticmethod
    async def track_device_fingerprint(
        db: Session,
        user_id: Optional[int],
        fingerprint_data: Dict[str, Any]
    ) -> DeviceFingerprint:
        """Track and analyze device fingerprints"""

        try:
            # Generate fingerprint hash
            fingerprint_string = f"{fingerprint_data.get('user_agent', '')}-{fingerprint_data.get('screen_resolution', '')}-{fingerprint_data.get('timezone', '')}-{fingerprint_data.get('language', '')}"
            fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()

            # Check if fingerprint exists
            existing_fingerprint = db.query(DeviceFingerprint).filter(
                DeviceFingerprint.fingerprint_hash == fingerprint_hash
            ).first()

            if existing_fingerprint:
                # Update existing fingerprint
                existing_fingerprint.last_seen = datetime.utcnow()
                existing_fingerprint.usage_count += 1

                # Update user association if provided
                if user_id and not existing_fingerprint.user_id:
                    existing_fingerprint.user_id = user_id

                db.commit()
                return existing_fingerprint

            # Create new fingerprint
            device_fingerprint = DeviceFingerprint(
                user_id=user_id,
                fingerprint_hash=fingerprint_hash,
                user_agent=fingerprint_data.get('user_agent'),
                screen_resolution=fingerprint_data.get('screen_resolution'),
                timezone=fingerprint_data.get('timezone'),
                language=fingerprint_data.get('language'),
                platform=fingerprint_data.get('platform')
            )

            db.add(device_fingerprint)
            db.commit()
            db.refresh(device_fingerprint)

            return device_fingerprint

        except Exception as e:
            logger.error(f"Device fingerprint tracking failed: {e}")
            db.rollback()
            raise

    @staticmethod
    def _is_suspicious_email(email: str) -> bool:
        """Check if email pattern is suspicious"""

        # Patterns that might indicate fraud
        suspicious_patterns = [
            r'^[a-z]+\d{4,}@',  # Simple name + many numbers
            r'^\w+\+\w+@',      # Plus addressing (sometimes used for multiple accounts)
            r'@(10minutemail|tempmail|guerrillamail)',  # Temporary email services
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, email.lower()):
                return True

        # Check for excessive dots or numbers
        if email.count('.') > 3 or sum(c.isdigit() for c in email) > len(email) * 0.5:
            return True

        return False

    @staticmethod
    async def _check_ip_reputation(ip_address: str) -> Dict[str, Any]:
        """Check IP address reputation"""

        try:
            # Basic IP validation
            ip = ipaddress.ip_address(ip_address)

            # Check for private/local IPs
            if ip.is_private or ip.is_loopback:
                return {"is_suspicious": False, "reason": "private_ip"}

            # Check for known bad IP ranges (simplified)
            # In production, integrate with IP reputation services
            suspicious_ranges = [
                # Add known bad IP ranges
            ]

            for range_str in suspicious_ranges:
                if ip in ipaddress.ip_network(range_str):
                    return {"is_suspicious": True, "reason": "known_bad_range"}

            # For now, return safe
            return {"is_suspicious": False, "reason": "clean"}

        except Exception as e:
            logger.error(f"IP reputation check failed: {e}")
            return {"is_suspicious": False, "reason": "check_failed"}

    @staticmethod
    async def _auto_block_user(db: Session, user_id: Optional[int], alert_id: int):
        """Automatically block user based on critical fraud alert"""

        if not user_id:
            return

        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.status = "suspended"
                user.updated_at = datetime.utcnow()

                # Update alert with action taken
                alert = db.query(FraudAlert).filter(FraudAlert.id == alert_id).first()
                if alert:
                    alert.action_taken = "user_suspended"

                db.commit()
                logger.critical(f"User {user_id} automatically suspended due to fraud alert {alert_id}")

        except Exception as e:
            logger.error(f"Auto-block user failed: {e}")
            db.rollback()

    @staticmethod
    async def get_fraud_statistics(db: Session, days: int = 30) -> Dict[str, Any]:
        """Get fraud detection statistics"""

        try:
            since_date = datetime.utcnow() - timedelta(days=days)

            # Get alerts by risk level
            alerts = db.query(FraudAlert).filter(
                FraudAlert.created_at >= since_date
            ).all()

            risk_breakdown = {}
            fraud_type_breakdown = {}

            for alert in alerts:
                # Risk level breakdown
                risk_level = alert.risk_level
                risk_breakdown[risk_level] = risk_breakdown.get(risk_level, 0) + 1

                # Fraud type breakdown
                fraud_type = alert.fraud_type
                fraud_type_breakdown[fraud_type] = fraud_type_breakdown.get(fraud_type, 0) + 1

            return {
                "period_days": days,
                "total_alerts": len(alerts),
                "risk_level_breakdown": risk_breakdown,
                "fraud_type_breakdown": fraud_type_breakdown,
                "resolved_alerts": sum(1 for alert in alerts if alert.is_resolved),
                "pending_alerts": sum(1 for alert in alerts if not alert.is_resolved)
            }

        except Exception as e:
            logger.error(f"Fraud statistics failed: {e}")
            return {"error": str(e)}

    @staticmethod
    async def validate_free_token_eligibility(
        db: Session,
        ip_address: str,
        device_fingerprint: str,
        email: str
    ) -> Dict[str, Any]:
        """Validate if user is eligible for free tokens (prevent abuse)"""

        try:
            # Check IP address usage
            ip_usage_count = db.query(User).filter(
                User.last_login_ip == ip_address,
                User.created_at > datetime.utcnow() - timedelta(days=30)
            ).count()

            if ip_usage_count >= 2:  # Max 2 accounts per IP per month
                return {
                    "eligible": False,
                    "reason": "ip_limit_exceeded",
                    "evidence": {"ip_usage_count": ip_usage_count}
                }

            # Check device fingerprint
            if device_fingerprint:
                device_usage = db.query(DeviceFingerprint).filter(
                    DeviceFingerprint.fingerprint_hash == device_fingerprint,
                    DeviceFingerprint.first_seen > datetime.utcnow() - timedelta(days=30)
                ).first()

                if device_usage and device_usage.usage_count >= 2:
                    return {
                        "eligible": False,
                        "reason": "device_limit_exceeded",
                        "evidence": {"device_usage_count": device_usage.usage_count}
                    }

            # Check email patterns
            if FraudDetectionService._is_suspicious_email(email):
                return {
                    "eligible": False,
                    "reason": "suspicious_email",
                    "evidence": {"email_pattern": "suspicious"}
                }

            return {
                "eligible": True,
                "reason": "passed_validation"
            }

        except Exception as e:
            logger.error(f"Free token eligibility check failed: {e}")
            return {
                "eligible": False,
                "reason": "validation_error",
                "evidence": {"error": str(e)}
            }

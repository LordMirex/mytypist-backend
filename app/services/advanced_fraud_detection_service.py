"""
Advanced Fraud Detection Service
Cross-browser/device tracking to prevent free token abuse and fraudulent activities
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, and_, or_
from database import Base

logger = logging.getLogger(__name__)


class DeviceFingerprint(Base):
    """Device fingerprinting for fraud detection"""
    __tablename__ = "device_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    fingerprint_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Device characteristics
    user_agent = Column(Text, nullable=True)
    screen_resolution = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    platform = Column(String(50), nullable=True)
    browser_features = Column(Text, nullable=True)  # JSON of browser capabilities

    # Network information
    ip_address = Column(String(45), nullable=True, index=True)
    ip_country = Column(String(2), nullable=True)
    ip_city = Column(String(100), nullable=True)
    isp = Column(String(100), nullable=True)

    # Behavioral patterns
    first_seen = Column(DateTime, default=datetime.utcnow, index=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    visit_count = Column(Integer, default=1)

    # Fraud indicators
    risk_score = Column(Float, default=0.0)
    is_blocked = Column(Boolean, default=False)
    fraud_reasons = Column(Text, nullable=True)  # JSON list of fraud indicators

    # Free token tracking
    free_tokens_claimed = Column(Integer, default=0)
    last_free_token_claim = Column(DateTime, nullable=True)


class UserDeviceAssociation(Base):
    """Track associations between users and devices"""
    __tablename__ = "user_device_associations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    fingerprint_id = Column(Integer, nullable=False, index=True)

    # Association metadata
    first_association = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    activity_count = Column(Integer, default=1)

    # Trust indicators
    trust_score = Column(Float, default=50.0)  # 0-100 scale
    is_primary_device = Column(Boolean, default=False)


class FraudAttempt(Base):
    """Log fraud attempts for analysis"""
    __tablename__ = "fraud_attempts"

    id = Column(Integer, primary_key=True, index=True)
    fingerprint_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Attempt details
    attempt_type = Column(String(50), nullable=False)  # free_token_abuse, multiple_accounts, etc.
    risk_score = Column(Float, nullable=False)
    blocked = Column(Boolean, default=False)

    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_data = Column(Text, nullable=True)  # JSON of request details

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AdvancedFraudDetectionService:
    """Advanced fraud detection with device fingerprinting and behavioral analysis"""

    @staticmethod
    def generate_device_fingerprint(
        user_agent: str,
        screen_resolution: Optional[str] = None,
        timezone: Optional[str] = None,
        language: Optional[str] = None,
        platform: Optional[str] = None,
        browser_features: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a unique device fingerprint hash"""
        try:
            # Combine device characteristics
            fingerprint_data = {
                "user_agent": user_agent or "",
                "screen_resolution": screen_resolution or "",
                "timezone": timezone or "",
                "language": language or "",
                "platform": platform or "",
                "browser_features": json.dumps(browser_features or {}, sort_keys=True)
            }

            # Create hash
            fingerprint_string = "|".join([
                str(fingerprint_data[key]) for key in sorted(fingerprint_data.keys())
            ])

            return hashlib.sha256(fingerprint_string.encode()).hexdigest()

        except Exception as e:
            logger.error(f"Failed to generate device fingerprint: {e}")
            # Return a fallback hash based on user agent only
            return hashlib.sha256((user_agent or "unknown").encode()).hexdigest()

    @staticmethod
    def register_device(
        db: Session,
        fingerprint_hash: str,
        device_data: Dict[str, Any],
        ip_address: Optional[str] = None
    ) -> DeviceFingerprint:
        """Register or update device fingerprint"""
        try:
            # Check if device already exists
            device = db.query(DeviceFingerprint).filter(
                DeviceFingerprint.fingerprint_hash == fingerprint_hash
            ).first()

            if device:
                # Update existing device
                device.last_seen = datetime.utcnow()
                device.visit_count += 1

                # Update IP if changed
                if ip_address and device.ip_address != ip_address:
                    device.ip_address = ip_address
                    # Recalculate risk score for IP changes
                    device.risk_score = AdvancedFraudDetectionService._calculate_risk_score(device, device_data)

            else:
                # Create new device
                device = DeviceFingerprint(
                    fingerprint_hash=fingerprint_hash,
                    user_agent=device_data.get("user_agent"),
                    screen_resolution=device_data.get("screen_resolution"),
                    timezone=device_data.get("timezone"),
                    language=device_data.get("language"),
                    platform=device_data.get("platform"),
                    browser_features=json.dumps(device_data.get("browser_features", {})),
                    ip_address=ip_address,
                    ip_country=device_data.get("ip_country"),
                    ip_city=device_data.get("ip_city"),
                    isp=device_data.get("isp"),
                    risk_score=AdvancedFraudDetectionService._calculate_initial_risk_score(device_data)
                )

                db.add(device)

            db.commit()
            db.refresh(device)

            return device

        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            raise

    @staticmethod
    def associate_user_device(
        db: Session,
        user_id: int,
        fingerprint_id: int
    ) -> UserDeviceAssociation:
        """Associate a user with a device fingerprint"""
        try:
            # Check if association already exists
            association = db.query(UserDeviceAssociation).filter(
                UserDeviceAssociation.user_id == user_id,
                UserDeviceAssociation.fingerprint_id == fingerprint_id
            ).first()

            if association:
                # Update existing association
                association.last_activity = datetime.utcnow()
                association.activity_count += 1
            else:
                # Create new association
                association = UserDeviceAssociation(
                    user_id=user_id,
                    fingerprint_id=fingerprint_id
                )
                db.add(association)

            db.commit()
            db.refresh(association)

            return association

        except Exception as e:
            logger.error(f"Failed to associate user device: {e}")
            raise

    @staticmethod
    def check_free_token_eligibility(
        db: Session,
        user_id: int,
        fingerprint_hash: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if user/device is eligible for free tokens
        Implements sophisticated fraud detection
        """
        try:
            # Get device fingerprint
            device = db.query(DeviceFingerprint).filter(
                DeviceFingerprint.fingerprint_hash == fingerprint_hash
            ).first()

            if not device:
                return {
                    "eligible": False,
                    "reason": "Device not registered",
                    "risk_score": 100.0
                }

            # Check if device has already claimed free tokens
            if device.free_tokens_claimed > 0:
                return {
                    "eligible": False,
                    "reason": "Free tokens already claimed on this device",
                    "risk_score": device.risk_score,
                    "last_claim": device.last_free_token_claim.isoformat() if device.last_free_token_claim else None
                }

            # Check for multiple accounts from same device
            device_users = db.query(UserDeviceAssociation).filter(
                UserDeviceAssociation.fingerprint_id == device.id
            ).count()

            if device_users > 3:  # More than 3 users from same device is suspicious
                return {
                    "eligible": False,
                    "reason": "Multiple accounts detected from this device",
                    "risk_score": 95.0,
                    "associated_users": device_users
                }

            # Check IP-based restrictions
            if ip_address:
                recent_claims = db.query(DeviceFingerprint).filter(
                    DeviceFingerprint.ip_address == ip_address,
                    DeviceFingerprint.free_tokens_claimed > 0,
                    DeviceFingerprint.last_free_token_claim > datetime.utcnow() - timedelta(days=1)
                ).count()

                if recent_claims > 2:  # More than 2 claims from same IP in 24h
                    return {
                        "eligible": False,
                        "reason": "Multiple free token claims from this IP address",
                        "risk_score": 90.0,
                        "recent_claims": recent_claims
                    }

            # Check user's other devices
            user_devices = db.query(UserDeviceAssociation).filter(
                UserDeviceAssociation.user_id == user_id
            ).all()

            for assoc in user_devices:
                other_device = db.query(DeviceFingerprint).filter(
                    DeviceFingerprint.id == assoc.fingerprint_id
                ).first()

                if other_device and other_device.free_tokens_claimed > 0:
                    return {
                        "eligible": False,
                        "reason": "Free tokens already claimed by this user on another device",
                        "risk_score": 85.0,
                        "claimed_device": other_device.fingerprint_hash[:8] + "..."
                    }

            # Calculate overall risk score
            risk_factors = []
            risk_score = device.risk_score

            # Recent registration risk
            from app.models.user import User
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.created_at and user.created_at > datetime.utcnow() - timedelta(minutes=10):
                risk_score += 20
                risk_factors.append("Very recent registration")

            # Device age risk
            if device.first_seen > datetime.utcnow() - timedelta(minutes=5):
                risk_score += 15
                risk_factors.append("New device")

            # Low activity risk
            if device.visit_count < 3:
                risk_score += 10
                risk_factors.append("Low activity")

            # High risk threshold
            if risk_score > 75:
                # Log fraud attempt
                fraud_attempt = FraudAttempt(
                    fingerprint_id=device.id,
                    user_id=user_id,
                    attempt_type="free_token_abuse",
                    risk_score=risk_score,
                    blocked=True,
                    ip_address=ip_address,
                    user_agent=device.user_agent,
                    request_data=json.dumps({
                        "risk_factors": risk_factors,
                        "device_users": device_users,
                        "recent_claims": recent_claims if ip_address else 0
                    })
                )
                db.add(fraud_attempt)
                db.commit()

                return {
                    "eligible": False,
                    "reason": "High fraud risk detected",
                    "risk_score": risk_score,
                    "risk_factors": risk_factors
                }

            # Eligible with risk assessment
            return {
                "eligible": True,
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "device_id": device.id
            }

        except Exception as e:
            logger.error(f"Failed to check free token eligibility: {e}")
            return {
                "eligible": False,
                "reason": "System error during fraud check",
                "risk_score": 100.0
            }

    @staticmethod
    def claim_free_token(
        db: Session,
        device_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """Record free token claim"""
        try:
            device = db.query(DeviceFingerprint).filter(
                DeviceFingerprint.id == device_id
            ).first()

            if not device:
                return {"success": False, "error": "Device not found"}

            # Update device record
            device.free_tokens_claimed += 1
            device.last_free_token_claim = datetime.utcnow()

            # Associate with user if not already done
            AdvancedFraudDetectionService.associate_user_device(db, user_id, device_id)

            db.commit()

            logger.info(f"Free token claimed by user {user_id} on device {device.fingerprint_hash[:8]}")

            return {
                "success": True,
                "message": "Free token claimed successfully",
                "device_fingerprint": device.fingerprint_hash[:8] + "...",
                "claimed_at": device.last_free_token_claim.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to claim free token: {e}")
            raise

    @staticmethod
    def _calculate_initial_risk_score(device_data: Dict[str, Any]) -> float:
        """Calculate initial risk score for new device"""
        risk_score = 0.0

        # User agent analysis
        user_agent = device_data.get("user_agent", "").lower()
        if "bot" in user_agent or "crawler" in user_agent:
            risk_score += 50

        # Common fraud indicators
        if not device_data.get("screen_resolution"):
            risk_score += 10

        if not device_data.get("timezone"):
            risk_score += 10

        # Suspicious browser features
        browser_features = device_data.get("browser_features", {})
        if not browser_features.get("cookies_enabled", True):
            risk_score += 15

        if not browser_features.get("javascript_enabled", True):
            risk_score += 20

        return min(risk_score, 100.0)

    @staticmethod
    def _calculate_risk_score(device: DeviceFingerprint, device_data: Dict[str, Any]) -> float:
        """Recalculate risk score for existing device"""
        base_score = device.risk_score

        # IP address changes
        current_ip = device_data.get("ip_address")
        if current_ip and device.ip_address != current_ip:
            base_score += 10  # IP change increases risk

        # Frequent visits reduce risk
        if device.visit_count > 10:
            base_score -= 5

        if device.visit_count > 50:
            base_score -= 10

        return max(0.0, min(base_score, 100.0))

    @staticmethod
    def get_fraud_statistics(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get fraud detection statistics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Total fraud attempts
            total_attempts = db.query(FraudAttempt).filter(
                FraudAttempt.created_at >= start_date
            ).count()

            # Blocked attempts
            blocked_attempts = db.query(FraudAttempt).filter(
                FraudAttempt.created_at >= start_date,
                FraudAttempt.blocked == True
            ).count()

            # Free token abuse attempts
            free_token_abuse = db.query(FraudAttempt).filter(
                FraudAttempt.created_at >= start_date,
                FraudAttempt.attempt_type == "free_token_abuse"
            ).count()

            # High-risk devices
            high_risk_devices = db.query(DeviceFingerprint).filter(
                DeviceFingerprint.risk_score > 75
            ).count()

            # Multiple account devices
            multiple_account_devices = db.query(DeviceFingerprint).join(
                UserDeviceAssociation
            ).group_by(DeviceFingerprint.id).having(
                db.func.count(UserDeviceAssociation.user_id) > 2
            ).count()

            return {
                "success": True,
                "period_days": days,
                "statistics": {
                    "total_fraud_attempts": total_attempts,
                    "blocked_attempts": blocked_attempts,
                    "block_rate": round((blocked_attempts / max(total_attempts, 1)) * 100, 2),
                    "free_token_abuse_attempts": free_token_abuse,
                    "high_risk_devices": high_risk_devices,
                    "multiple_account_devices": multiple_account_devices,
                    "total_devices_tracked": db.query(DeviceFingerprint).count(),
                    "average_risk_score": round(
                        db.query(db.func.avg(DeviceFingerprint.risk_score)).scalar() or 0, 2
                    )
                }
            }

        except Exception as e:
            logger.error(f"Failed to get fraud statistics: {e}")
            raise

"""
Security Monitoring and Alerting Service
Real-time threat detection, anomaly detection, and incident response
"""

import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import settings
from database import Base
from app.services.audit_service import AuditService


class ThreatLevel(str, Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Security incident status"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class SecurityIncident(Base):
    """Security incident record"""
    __tablename__ = "security_incidents"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, index=True)
    threat_level = Column(String(20), nullable=False)
    alert_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    # Affected resources
    affected_user_id = Column(Integer, nullable=True)
    affected_resource_type = Column(String(50), nullable=True)
    affected_resource_id = Column(String(100), nullable=True)

    # Attack details
    source_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    attack_vector = Column(String(100), nullable=True)
    attack_pattern = Column(Text, nullable=True)

    # Geographic data
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    isp = Column(String(200), nullable=True)

    # Investigation data
    investigation_notes = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)  # Stored securely
    mitigation_steps = Column(JSON, nullable=True)
    status = Column(String(20), default=IncidentStatus.OPEN)
    assigned_to = Column(Integer, nullable=True)  # Admin/moderator ID

    # Related incidents for pattern detection
    related_incidents = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Metrics
    response_time_seconds = Column(Float, nullable=True)  # Time to first response
    resolution_time_seconds = Column(Float, nullable=True)  # Time to resolution


class ThreatPattern(Base):
    """Known threat patterns for detection"""
    __tablename__ = "threat_patterns"

    id = Column(Integer, primary_key=True, index=True)
    pattern_type = Column(String(50), nullable=False)
    pattern_data = Column(JSON, nullable=False)  # Encrypted pattern data
    severity = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    detection_count = Column(Integer, default=0)
    last_detected = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


@dataclass
class SecurityAlert:
    """Security alert data structure"""
    alert_id: str
    threat_level: ThreatLevel
    alert_type: str
    title: str
    description: str
    affected_user_id: Optional[int]
    source_ip: Optional[str]
    timestamp: datetime
    attack_vector: Optional[str] = None
    evidence: Optional[Dict[str, any]] = None
    recommended_actions: Optional[List[str]] = None


class SecurityMonitoringService:
    """Enhanced security monitoring service with advanced threat detection"""

    def __init__(self):
        self.threat_patterns = {}  # Cache of active threat patterns
        self.incident_cache = {}   # Recent incidents for pattern matching
        self.blocked_ips = set()   # Currently blocked IPs

    async def monitor_request(
        self,
        db: Session,
        request,
        user_id: Optional[int] = None
    ) -> Optional[SecurityAlert]:
        """Monitor incoming request for security threats"""
        try:
            # Extract request data
            ip = request.client.host
            headers = dict(request.headers)
            path = request.url.path
            method = request.method

            # Check for immediate threats
            if ip in self.blocked_ips:
                await self.log_blocked_attempt(db, ip, "Blocked IP attempt", headers)
                return None

            # Build request context
            context = {
                "ip": ip,
                "headers": headers,
                "path": path,
                "method": method,
                "user_id": user_id,
                "timestamp": datetime.utcnow()
            }

            # Run threat detection
            threats = await self.detect_threats(db, context)
            if not threats:
                return None

            # Create security incident
            incident = SecurityIncident(
                alert_id=str(uuid.uuid4()),
                threat_level=threats[0].severity,  # Use highest severity
                alert_type=threats[0].pattern_type,
                title=f"Security threat detected: {threats[0].pattern_type}",
                description="\n".join(t.description for t in threats),
                affected_user_id=user_id,
                source_ip=ip,
                user_agent=headers.get("user-agent"),
                attack_vector=threats[0].pattern_type,
                attack_pattern=json.dumps([t.pattern_data for t in threats]),
                evidence=json.dumps({
                    "request_headers": headers,
                    "request_path": path,
                    "request_method": method,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )

            db.add(incident)
            db.commit()

            # Update threat pattern stats
            for threat in threats:
                threat.detection_count += 1
                threat.last_detected = datetime.utcnow()
                db.add(threat)
            db.commit()

            # Create and return alert
            return SecurityAlert(
                alert_id=incident.alert_id,
                threat_level=ThreatLevel(incident.threat_level),
                alert_type=incident.alert_type,
                title=incident.title,
                description=incident.description,
                affected_user_id=user_id,
                source_ip=ip,
                timestamp=datetime.utcnow(),
                attack_vector=incident.attack_vector,
                evidence=json.loads(incident.evidence),
                recommended_actions=self.get_recommended_actions(threats)
            )

        except Exception as e:
            print(f"Failed to monitor request: {e}")
            return None

    async def detect_threats(self, db: Session, context: Dict) -> List:
        """Detect threats in request context"""
        threats = []

        # Basic threat detection logic
        # This is a simplified version - in production, implement comprehensive threat detection

        # Check for SQL injection patterns
        sql_patterns = ["union select", "drop table", "insert into", "delete from"]
        for pattern in sql_patterns:
            if pattern.lower() in str(context.get("path", "")).lower():
                threats.append(type('Threat', (), {
                    'pattern_type': 'sql_injection',
                    'severity': ThreatLevel.HIGH,
                    'description': f'SQL injection pattern detected: {pattern}',
                    'pattern_data': {'pattern': pattern}
                })())

        # Check for XSS patterns
        xss_patterns = ["<script", "javascript:", "onload="]
        for pattern in xss_patterns:
            if pattern.lower() in str(context.get("path", "")).lower():
                threats.append(type('Threat', (), {
                    'pattern_type': 'xss',
                    'severity': ThreatLevel.MEDIUM,
                    'description': f'XSS pattern detected: {pattern}',
                    'pattern_data': {'pattern': pattern}
                })())

        return threats

    async def log_blocked_attempt(self, db: Session, ip: str, reason: str, headers: Dict):
        """Log blocked access attempt"""
        try:
            AuditService.log_security_event(
                "BLOCKED_ACCESS_ATTEMPT",
                None,
                None,
                {
                    "ip": ip,
                    "reason": reason,
                    "user_agent": headers.get("user-agent"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            print(f"Failed to log blocked attempt: {e}")

    def get_recommended_actions(self, threats: List) -> List[str]:
        """Get recommended actions for threats"""
        actions = []
        for threat in threats:
            if threat.pattern_type == 'sql_injection':
                actions.extend([
                    "Block IP address",
                    "Review database queries",
                    "Implement input validation"
                ])
            elif threat.pattern_type == 'xss':
                actions.extend([
                    "Sanitize user input",
                    "Implement CSP headers",
                    "Review frontend code"
                ])
        return list(set(actions))  # Remove duplicates

    @staticmethod
    def cleanup_old_incidents(db: Session, retention_days: int = 365):
        """Cleanup old security incidents"""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Only delete resolved incidents
        deleted_incidents = db.query(SecurityIncident).filter(
            SecurityIncident.created_at < cutoff_date,
            SecurityIncident.status == IncidentStatus.RESOLVED
        ).delete()

        db.commit()

        return {
            "deleted_incidents": deleted_incidents
        }

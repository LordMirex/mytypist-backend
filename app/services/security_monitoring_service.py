"""
Security Monitoring and Alerting Service
Real-time threat detection, anomaly detection, and incident response
"""

import json
import hashlib
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
    evidence: Optional[Dict[str, Any]] = None
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
        request: Request,
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
            await db.commit()
            
            # Update threat pattern stats
            for threat in threats:
                threat.detection_count += 1
                threat.last_detected = datetime.utcnow()
                db.add(threat)
            await db.commit()
            
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
            logger.error(f"Failed to monitor request: {e}")
            return None
    metadata: Dict
    recommended_actions: List[str]


class SecurityIncident(Base):
    """Security incident tracking"""
    __tablename__ = "security_incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(64), nullable=False, unique=True, index=True)

    # Incident details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    threat_level = Column(String(20), nullable=False, index=True)
    incident_type = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=IncidentStatus.OPEN, index=True)

    # Affected entities
    affected_user_id = Column(Integer, nullable=True, index=True)
    affected_resource_type = Column(String(50), nullable=True)
    affected_resource_id = Column(String(100), nullable=True)

    # Source information
    source_ip = Column(String(45), nullable=True, index=True)
    source_country = Column(String(2), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Detection
    detection_method = Column(String(100), nullable=False)
    detection_confidence = Column(Float, nullable=False, default=0.5)

    # Response
    assigned_to = Column(Integer, nullable=True)
    response_actions = Column(JSON, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Metadata
    security_metadata = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)


class ThreatIndicator(Base):
    """Threat indicators and IOCs"""
    __tablename__ = "threat_indicators"

    id = Column(Integer, primary_key=True, index=True)

    # Indicator details
    indicator_type = Column(String(50), nullable=False, index=True)  # ip, domain, hash, pattern
    indicator_value = Column(String(500), nullable=False, index=True)
    threat_level = Column(String(20), nullable=False, index=True)

    # Context
    description = Column(Text, nullable=True)
    source = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True)

    # Validity
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)

    # Usage tracking
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AnomalyDetection(Base):
    """Anomaly detection results"""
    __tablename__ = "anomaly_detections"

    id = Column(Integer, primary_key=True, index=True)

    # Detection details
    detection_type = Column(String(100), nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False, index=True)
    threshold = Column(Float, nullable=False)

    # Context
    user_id = Column(Integer, nullable=True, index=True)
    ip_address = Column(String(45), nullable=True, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)

    # Data
    baseline_data = Column(JSON, nullable=True)
    current_data = Column(JSON, nullable=True)
    features = Column(JSON, nullable=True)

    # Status
    is_confirmed_anomaly = Column(Boolean, nullable=True)
    is_false_positive = Column(Boolean, nullable=False, default=False)

    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Metadata
    anomaly_metadata = Column(JSON, nullable=True)


class SecurityMonitoringService:
    """Security monitoring and threat detection service"""

    # Configuration
    ANOMALY_THRESHOLD = 0.7
    HIGH_THREAT_THRESHOLD = 0.8
    CRITICAL_THREAT_THRESHOLD = 0.9

    # Rate limiting thresholds
    LOGIN_ATTEMPT_THRESHOLD = 10  # per 5 minutes
    API_REQUEST_THRESHOLD = 1000  # per minute
    FILE_UPLOAD_THRESHOLD = 50   # per hour

    @staticmethod
    def detect_brute_force_attack(db: Session, ip_address: str, user_id: int = None,
                                 time_window_minutes: int = 5) -> Optional[SecurityAlert]:
        """Detect brute force login attempts"""
        from app.services.password_service import PasswordAttempt

        # Check failed attempts in time window
        start_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        query = db.query(PasswordAttempt).filter(
            PasswordAttempt.ip_address == ip_address,
            PasswordAttempt.success == False,
            PasswordAttempt.attempt_time >= start_time
        )

        if user_id:
            query = query.filter(PasswordAttempt.user_id == user_id)

        failed_attempts = query.count()

        if failed_attempts >= SecurityMonitoringService.LOGIN_ATTEMPT_THRESHOLD:
            # Create security incident
            incident_id = SecurityMonitoringService._generate_incident_id()

            incident = SecurityIncident(
                incident_id=incident_id,
                title="Brute Force Attack Detected",
                description=f"Multiple failed login attempts from IP {ip_address}",
                threat_level=ThreatLevel.HIGH,
                incident_type="brute_force_attack",
                affected_user_id=user_id,
                source_ip=ip_address,
                detection_method="failed_login_threshold",
                detection_confidence=0.9,
                metadata={
                    "failed_attempts": failed_attempts,
                    "time_window_minutes": time_window_minutes,
                    "threshold": SecurityMonitoringService.LOGIN_ATTEMPT_THRESHOLD
                }
            )

            db.add(incident)
            db.commit()

            # Create alert
            alert = SecurityAlert(
                alert_id=incident_id,
                threat_level=ThreatLevel.HIGH,
                alert_type="brute_force_attack",
                title="Brute Force Attack Detected",
                description=f"IP {ip_address} has made {failed_attempts} failed login attempts in {time_window_minutes} minutes",
                affected_user_id=user_id,
                source_ip=ip_address,
                timestamp=datetime.utcnow(),
                metadata={"failed_attempts": failed_attempts, "time_window": time_window_minutes},
                recommended_actions=[
                    "Block IP address",
                    "Enable account lockout",
                    "Notify affected user",
                    "Review authentication logs"
                ]
            )

            return alert

        return None

    @staticmethod
    def detect_anomalous_api_usage(db: Session, user_id: int, api_key_id: int = None) -> Optional[SecurityAlert]:
        """Detect anomalous API usage patterns"""
        from app.services.api_key_service import APIKeyUsage

        # Get baseline usage (last 30 days)
        baseline_start = datetime.utcnow() - timedelta(days=30)
        baseline_end = datetime.utcnow() - timedelta(days=1)

        baseline_query = db.query(APIKeyUsage).join(
            'api_key'
        ).filter(
            APIKeyUsage.request_time.between(baseline_start, baseline_end)
        )

        if api_key_id:
            baseline_query = baseline_query.filter(APIKeyUsage.api_key_id == api_key_id)
        else:
            baseline_query = baseline_query.filter_by(user_id=user_id)

        baseline_usage = baseline_query.all()

        # Get current usage (last hour)
        current_start = datetime.utcnow() - timedelta(hours=1)
        current_query = db.query(APIKeyUsage).join(
            'api_key'
        ).filter(
            APIKeyUsage.request_time >= current_start
        )

        if api_key_id:
            current_query = current_query.filter(APIKeyUsage.api_key_id == api_key_id)
        else:
            current_query = current_query.filter_by(user_id=user_id)

        current_usage = current_query.all()

        # Calculate anomaly score
        baseline_rate = len(baseline_usage) / (30 * 24) if baseline_usage else 0  # per hour
        current_rate = len(current_usage)

        if baseline_rate == 0 and current_rate > 100:  # New user with high usage
            anomaly_score = 0.8
        elif baseline_rate > 0:
            anomaly_score = min(current_rate / (baseline_rate * 10), 1.0)  # 10x normal rate
        else:
            anomaly_score = 0.0

        if anomaly_score >= SecurityMonitoringService.ANOMALY_THRESHOLD:
            # Record anomaly
            anomaly = AnomalyDetection(
                detection_type="api_usage_spike",
                anomaly_score=anomaly_score,
                threshold=SecurityMonitoringService.ANOMALY_THRESHOLD,
                user_id=user_id,
                baseline_data={"hourly_rate": baseline_rate, "period_days": 30},
                current_data={"current_requests": current_rate, "period_hours": 1},
                features={"rate_multiplier": current_rate / baseline_rate if baseline_rate > 0 else float('inf')}
            )

            db.add(anomaly)
            db.commit()

            # Create alert for high scores
            if anomaly_score >= SecurityMonitoringService.HIGH_THREAT_THRESHOLD:
                incident_id = SecurityMonitoringService._generate_incident_id()

                alert = SecurityAlert(
                    alert_id=incident_id,
                    threat_level=ThreatLevel.HIGH if anomaly_score >= SecurityMonitoringService.CRITICAL_THREAT_THRESHOLD else ThreatLevel.MEDIUM,
                    alert_type="anomalous_api_usage",
                    title="Anomalous API Usage Detected",
                    description=f"User {user_id} API usage is {current_rate/baseline_rate if baseline_rate > 0 else 'significantly'}x normal rate",
                    affected_user_id=user_id,
                    source_ip=None,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "anomaly_score": anomaly_score,
                        "baseline_rate": baseline_rate,
                        "current_rate": current_rate,
                        "api_key_id": api_key_id
                    },
                    recommended_actions=[
                        "Review API key usage",
                        "Check for compromised credentials",
                        "Implement rate limiting",
                        "Contact user for verification"
                    ]
                )

                return alert

        return None

    @staticmethod
    def detect_suspicious_file_uploads(db: Session, user_id: int, file_info: Dict) -> Optional[SecurityAlert]:
        """Detect suspicious file upload patterns"""
        # Check upload frequency
        recent_uploads = db.query(AnomalyDetection).filter(
            AnomalyDetection.user_id == user_id,
            AnomalyDetection.detection_type == "file_upload",
            AnomalyDetection.detected_at >= datetime.utcnow() - timedelta(hours=1)
        ).count()

        if recent_uploads >= SecurityMonitoringService.FILE_UPLOAD_THRESHOLD:
            incident_id = SecurityMonitoringService._generate_incident_id()

            alert = SecurityAlert(
                alert_id=incident_id,
                threat_level=ThreatLevel.MEDIUM,
                alert_type="suspicious_file_uploads",
                title="Suspicious File Upload Activity",
                description=f"User {user_id} has uploaded {recent_uploads} files in the last hour",
                affected_user_id=user_id,
                source_ip=file_info.get("ip_address"),
                timestamp=datetime.utcnow(),
                metadata={
                    "upload_count": recent_uploads,
                    "time_window": "1 hour",
                    "file_type": file_info.get("file_type"),
                    "file_size": file_info.get("file_size")
                },
                recommended_actions=[
                    "Review uploaded files",
                    "Scan for malware",
                    "Check user account status",
                    "Implement upload rate limiting"
                ]
            )

            return alert

        # Check for suspicious file types or sizes
        suspicious_extensions = ['.exe', '.bat', '.cmd', '.scr', '.vbs', '.js', '.jar']
        file_name = file_info.get("filename", "").lower()

        if any(file_name.endswith(ext) for ext in suspicious_extensions):
            incident_id = SecurityMonitoringService._generate_incident_id()

            alert = SecurityAlert(
                alert_id=incident_id,
                threat_level=ThreatLevel.HIGH,
                alert_type="suspicious_file_type",
                title="Suspicious File Type Upload",
                description=f"User {user_id} uploaded potentially dangerous file: {file_name}",
                affected_user_id=user_id,
                source_ip=file_info.get("ip_address"),
                timestamp=datetime.utcnow(),
                metadata={
                    "filename": file_name,
                    "file_size": file_info.get("file_size"),
                    "detected_extension": next(ext for ext in suspicious_extensions if file_name.endswith(ext))
                },
                recommended_actions=[
                    "Quarantine file immediately",
                    "Scan for malware",
                    "Block file type",
                    "Review user permissions"
                ]
            )

            return alert

        return None

    @staticmethod
    def detect_data_exfiltration(db: Session, user_id: int, download_info: Dict) -> Optional[SecurityAlert]:
        """Detect potential data exfiltration"""
        # Check download volume in last hour
        recent_downloads = db.query(AnomalyDetection).filter(
            AnomalyDetection.user_id == user_id,
            AnomalyDetection.detection_type == "data_download",
            AnomalyDetection.detected_at >= datetime.utcnow() - timedelta(hours=1)
        ).all()

        total_size = sum(d.current_data.get("download_size", 0) for d in recent_downloads if d.current_data)
        total_size += download_info.get("file_size", 0)

        # Threshold: 1GB in an hour
        size_threshold = 1024 * 1024 * 1024  # 1GB

        if total_size >= size_threshold:
            incident_id = SecurityMonitoringService._generate_incident_id()

            alert = SecurityAlert(
                alert_id=incident_id,
                threat_level=ThreatLevel.HIGH,
                alert_type="potential_data_exfiltration",
                title="Potential Data Exfiltration Detected",
                description=f"User {user_id} has downloaded {total_size / (1024*1024):.1f}MB of data in the last hour",
                affected_user_id=user_id,
                source_ip=download_info.get("ip_address"),
                timestamp=datetime.utcnow(),
                metadata={
                    "total_download_size": total_size,
                    "download_count": len(recent_downloads) + 1,
                    "time_window": "1 hour",
                    "threshold_gb": size_threshold / (1024*1024*1024)
                },
                recommended_actions=[
                    "Block user downloads",
                    "Review downloaded files",
                    "Check user authorization",
                    "Investigate user activity",
                    "Contact security team"
                ]
            )

            return alert

        return None

    @staticmethod
    def check_threat_indicators(db: Session, ip_address: str, user_agent: str = None,
                              domain: str = None) -> List[SecurityAlert]:
        """Check request against threat indicators"""
        alerts = []
        current_time = datetime.utcnow()

        # Check IP reputation
        ip_indicators = db.query(ThreatIndicator).filter(
            ThreatIndicator.indicator_type == "ip",
            ThreatIndicator.indicator_value == ip_address,
            ThreatIndicator.is_active == True
        ).filter(
            (ThreatIndicator.expires_at.is_(None)) |
            (ThreatIndicator.expires_at > current_time)
        ).all()

        for indicator in ip_indicators:
            # Update hit count
            indicator.hit_count += 1
            indicator.last_hit = current_time

            threat_level = ThreatLevel(indicator.threat_level)

            alert = SecurityAlert(
                alert_id=SecurityMonitoringService._generate_incident_id(),
                threat_level=threat_level,
                alert_type="malicious_ip_detected",
                title="Malicious IP Address Detected",
                description=f"Request from known malicious IP: {ip_address}",
                affected_user_id=None,
                source_ip=ip_address,
                timestamp=current_time,
                metadata={
                    "indicator_id": indicator.id,
                    "indicator_source": indicator.source,
                    "confidence": indicator.confidence,
                    "tags": indicator.tags
                },
                recommended_actions=[
                    "Block IP address immediately",
                    "Review all requests from this IP",
                    "Check for compromised accounts",
                    "Update threat intelligence"
                ]
            )

            alerts.append(alert)

        # Check user agent patterns
        if user_agent:
            ua_indicators = db.query(ThreatIndicator).filter(
                ThreatIndicator.indicator_type == "user_agent_pattern",
                ThreatIndicator.is_active == True
            ).filter(
                (ThreatIndicator.expires_at.is_(None)) |
                (ThreatIndicator.expires_at > current_time)
            ).all()

            for indicator in ua_indicators:
                import re
                if re.search(indicator.indicator_value, user_agent, re.IGNORECASE):
                    indicator.hit_count += 1
                    indicator.last_hit = current_time

                    alert = SecurityAlert(
                        alert_id=SecurityMonitoringService._generate_incident_id(),
                        threat_level=ThreatLevel(indicator.threat_level),
                        alert_type="suspicious_user_agent",
                        title="Suspicious User Agent Detected",
                        description=f"Request with suspicious user agent pattern",
                        affected_user_id=None,
                        source_ip=ip_address,
                        timestamp=current_time,
                        metadata={
                            "user_agent": user_agent,
                            "pattern": indicator.indicator_value,
                            "confidence": indicator.confidence
                        },
                        recommended_actions=[
                            "Block requests with this user agent",
                            "Investigate request source",
                            "Review security logs"
                        ]
                    )

                    alerts.append(alert)

        db.commit()
        return alerts

    @staticmethod
    def process_security_alert(db: Session, alert: SecurityAlert) -> bool:
        """Process and respond to security alert"""
        # Create incident if high priority
        if alert.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            incident = SecurityIncident(
                incident_id=alert.alert_id,
                title=alert.title,
                description=alert.description,
                threat_level=alert.threat_level,
                incident_type=alert.alert_type,
                affected_user_id=alert.affected_user_id,
                source_ip=alert.source_ip,
                detection_method="automated_detection",
                detection_confidence=0.8,
                metadata=alert.metadata,
                evidence={"alert": alert.__dict__}
            )

            db.add(incident)
            db.commit()

        # Send notifications
        SecurityMonitoringService._send_security_notification(alert)

        # Log audit event
        AuditService.log_security_event(
            "SECURITY_ALERT_GENERATED",
            alert.affected_user_id,
            None,
            {
                "alert_id": alert.alert_id,
                "alert_type": alert.alert_type,
                "threat_level": alert.threat_level,
                "source_ip": alert.source_ip
            }
        )

        return True

    @staticmethod
    def add_threat_indicator(db: Session, indicator_type: str, indicator_value: str,
                           threat_level: ThreatLevel, description: str = None,
                           source: str = None, expires_at: datetime = None,
                           confidence: float = 0.5, tags: List[str] = None) -> bool:
        """Add new threat indicator"""
        indicator = ThreatIndicator(
            indicator_type=indicator_type,
            indicator_value=indicator_value,
            threat_level=threat_level,
            description=description,
            source=source,
            expires_at=expires_at,
            confidence=confidence,
            tags=tags
        )

        db.add(indicator)
        db.commit()

        # Log audit event
        AuditService.log_security_event(
            "THREAT_INDICATOR_ADDED",
            None,
            None,
            {
                "indicator_type": indicator_type,
                "indicator_value": indicator_value,
                "threat_level": threat_level,
                "source": source
            }
        )

        return True

    @staticmethod
    def get_security_dashboard(db: Session, days: int = 7) -> Dict[str, any]:
        """Get security dashboard data"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Incidents by severity
        incidents = db.query(SecurityIncident).filter(
            SecurityIncident.detected_at >= start_date
        ).all()

        incidents_by_level = {}
        for level in ThreatLevel:
            incidents_by_level[level.value] = len([
                i for i in incidents if i.threat_level == level.value
            ])

        # Incidents by type
        incidents_by_type = {}
        for incident in incidents:
            incident_type = incident.incident_type
            incidents_by_type[incident_type] = incidents_by_type.get(incident_type, 0) + 1

        # Anomalies
        anomalies = db.query(AnomalyDetection).filter(
            AnomalyDetection.detected_at >= start_date
        ).count()

        # Top threat sources
        threat_sources = db.query(SecurityIncident.source_ip).filter(
            SecurityIncident.detected_at >= start_date,
            SecurityIncident.source_ip.isnot(None)
        ).all()

        source_counts = {}
        for source_ip, in threat_sources:
            source_counts[source_ip] = source_counts.get(source_ip, 0) + 1

        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "period_days": days,
            "total_incidents": len(incidents),
            "incidents_by_severity": incidents_by_level,
            "incidents_by_type": incidents_by_type,
            "total_anomalies": anomalies,
            "top_threat_sources": top_sources,
            "open_incidents": len([i for i in incidents if i.status == IncidentStatus.OPEN]),
            "resolved_incidents": len([i for i in incidents if i.status == IncidentStatus.RESOLVED])
        }

    @staticmethod
    def _generate_incident_id() -> str:
        """Generate unique incident ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = hashlib.md5(str(datetime.utcnow().microsecond).encode()).hexdigest()[:8]
        return f"INC-{timestamp}-{random_suffix}"

    @staticmethod
    def _send_security_notification(alert: SecurityAlert):
        """Send security alert notification"""
        # In production, integrate with:
        # - Email alerts
        # - Slack notifications
        # - PagerDuty
        # - SIEM systems

        if alert.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            print(f"🚨 SECURITY ALERT: {alert.title}")
            print(f"   Threat Level: {alert.threat_level}")
            print(f"   Description: {alert.description}")
            print(f"   Source IP: {alert.source_ip}")
            print(f"   Timestamp: {alert.timestamp}")
            print(f"   Recommended Actions: {', '.join(alert.recommended_actions)}")

    @staticmethod
    def cleanup_old_incidents(db: Session, retention_days: int = 365):
        """Cleanup old security incidents"""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Only delete resolved incidents
        deleted_incidents = db.query(SecurityIncident).filter(
            SecurityIncident.detected_at < cutoff_date,
            SecurityIncident.status == IncidentStatus.RESOLVED
        ).delete()

        # Cleanup old anomalies
        deleted_anomalies = db.query(AnomalyDetection).filter(
            AnomalyDetection.detected_at < cutoff_date
        ).delete()

        db.commit()

        return {
            "deleted_incidents": deleted_incidents,
            "deleted_anomalies": deleted_anomalies
        }

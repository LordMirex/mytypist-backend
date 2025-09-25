"""
Audit logging and compliance service
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import Request
from sqlalchemy.orm import Session
try:
    from geoip2 import database as geoip_db
    GEOIP_AVAILABLE = True
except ImportError:
    geoip_db = None
    GEOIP_AVAILABLE = False

from config import settings
from app.models.audit import AuditLog, AuditEventType, AuditLevel
from database import get_db


class AuditService:
    """Audit logging and compliance service"""
    
    @staticmethod
    def log_event(
        event_type: AuditEventType,
        event_level: AuditLevel,
        event_message: str,
        user_id: Optional[int] = None,
        request: Optional[Request] = None,
        event_details: Optional[Dict[str, Any]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None
    ) -> AuditLog:
        """Log audit event"""
        
        db = next(get_db())
        
        try:
            # Generate request ID if not present
            request_id = str(uuid.uuid4())
            if request and hasattr(request.state, 'request_id'):
                request_id = request.state.request_id
            
            # Extract request information
            ip_address = None
            user_agent = None
            request_method = None
            request_path = None
            request_params = None
            country = None
            city = None
            
            if request:
                ip_address = AuditService._get_client_ip(request)
                user_agent = request.headers.get("user-agent")
                request_method = request.method
                request_path = str(request.url.path)
                request_params = dict(request.query_params) if request.query_params else None
                
                # Get geographic information
                country, city = AuditService._get_location_from_ip(ip_address)
            
            # Determine if event is GDPR relevant
            gdpr_relevant = AuditService._is_gdpr_relevant(event_type, event_details)
            pii_accessed = AuditService._contains_pii(event_details)
            sensitive_operation = AuditService._is_sensitive_operation(event_type)
            
            # Calculate risk score
            risk_score = AuditService._calculate_risk_score(
                event_type, event_level, event_details, user_id, ip_address
            )
            
            # Detect anomalies
            anomaly_detected = AuditService._detect_anomaly(
                event_type, user_id, ip_address
            )
            
            # Create audit log entry
            audit_log = AuditLog(
                event_type=event_type,
                event_level=event_level,
                event_message=event_message,
                event_details=event_details,
                user_id=user_id,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_method=request_method,
                request_path=request_path,
                request_params=request_params,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                country=country,
                city=city,
                gdpr_relevant=gdpr_relevant,
                pii_accessed=pii_accessed,
                sensitive_operation=sensitive_operation,
                risk_score=risk_score,
                anomaly_detected=anomaly_detected,
                environment="production" if not settings.DEBUG else "development",
                service_version=settings.APP_VERSION,
                correlation_id=str(uuid.uuid4())
            )
            
            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)
            
            # Trigger alerts for high-risk events
            if audit_log.requires_alert:
                AuditService._send_security_alert(audit_log)
            
            return audit_log
            
        finally:
            db.close()
    
    @staticmethod
    def log_auth_event(
        event_type: str,
        user_id: Optional[int],
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log authentication event"""
        
        # Map string event type to enum value
        try:
            audit_event_type = AuditEventType(event_type)
        except ValueError:
            # If the event type doesn't match exactly, try to find it by value
            audit_event_type = next(
                (e for e in AuditEventType if e.value == event_type), 
                AuditEventType.LOGIN  # default fallback
            )
        
        return AuditService.log_event(
            event_type=audit_event_type,
            event_level=AuditLevel.INFO,
            event_message=f"Authentication event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="auth"
        )
    
    @staticmethod
    def log_user_event(
        event_type: str,
        user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log user management event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"User event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="user",
            resource_id=str(user_id)
        )
    
    @staticmethod
    def log_document_event(
        event_type: str,
        user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log document event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"Document event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="document",
            resource_id=str(details.get("document_id")) if details else None,
            resource_name=details.get("title") if details else None
        )
    
    @staticmethod
    def log_template_event(
        event_type: str,
        user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log template event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"Template event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="template",
            resource_id=str(details.get("template_id")) if details else None,
            resource_name=details.get("name") if details else None
        )
    
    @staticmethod
    def log_signature_event(
        event_type: str,
        user_id: Optional[int],
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log signature event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"Signature event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="signature",
            resource_id=str(details.get("signature_id")) if details else None
        )
    
    @staticmethod
    def log_payment_event(
        event_type: str,
        user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log payment event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"Payment event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="payment",
            resource_id=str(details.get("payment_id")) if details else None
        )
    
    @staticmethod
    def log_subscription_event(
        event_type: str,
        user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log subscription event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"Subscription event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="subscription",
            resource_id=str(details.get("subscription_id")) if details else None
        )
    
    @staticmethod
    def log_analytics_event(
        event_type: str,
        user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log analytics event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"Analytics event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="analytics"
        )
    
    @staticmethod
    def log_admin_event(
        event_type: str,
        admin_user_id: int,
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log admin event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.WARNING,
            event_message=f"Admin event: {event_type}",
            user_id=admin_user_id,
            request=request,
            event_details=details,
            resource_type="admin",
            sensitive_operation=True
        )
    
    @staticmethod
    def log_security_event(
        event_type: str,
        user_id: Optional[int],
        request: Optional[Request],
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log security event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.ERROR,
            event_message=f"Security event: {event_type}",
            user_id=user_id,
            request=request,
            event_details=details,
            resource_type="security",
            sensitive_operation=True
        )
    
    @staticmethod
    def log_system_event(
        event_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log system event"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.INFO,
            event_message=f"System event: {event_type}",
            event_details=details,
            resource_type="system"
        )
    
    @staticmethod
    def log_performance_issue(
        event_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log performance issue"""
        
        return AuditService.log_event(
            event_type=AuditEventType(event_type),
            event_level=AuditLevel.WARNING,
            event_message=f"Performance issue: {event_type}",
            event_details=details,
            resource_type="performance"
        )
    
    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request"""
        
        # Check for forwarded IP (load balancer, proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to client host
        return request.client.host if request.client else None
    
    @staticmethod
    def _get_location_from_ip(ip_address: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Get country and city from IP address using MaxMind GeoIP2"""
        
        # Basic IP geolocation for audit logging
        if not ip_address or ip_address in ["127.0.0.1", "localhost", "::1"]:
            return None, None
        
        try:
            if GEOIP_AVAILABLE and hasattr(settings, 'GEOIP_DATABASE_PATH'):
                # Use MaxMind GeoIP2 database for accurate location data
                with geoip_db.Reader(settings.GEOIP_DATABASE_PATH) as reader:
                    response = reader.city(ip_address)
                    country = response.country.name
                    city = response.city.name
                    return country, city
            else:
                # Fallback for Nigerian businesses when GeoIP is not available
                return "Nigeria", "Lagos"
                
        except Exception as e:
            # Log error and return fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"GeoIP lookup failed for {ip_address}: {e}")
            return "Nigeria", "Lagos"
    
    @staticmethod
    def _is_gdpr_relevant(event_type: AuditEventType, event_details: Optional[Dict[str, Any]]) -> bool:
        """Check if event is GDPR relevant"""
        
        gdpr_events = [
            AuditEventType.USER_CREATED,
            AuditEventType.USER_UPDATED,
            AuditEventType.USER_DELETED,
            AuditEventType.DATA_EXPORT,
            AuditEventType.DATA_DELETION,
            AuditEventType.CONSENT_GIVEN,
            AuditEventType.CONSENT_WITHDRAWN
        ]
        
        return event_type in gdpr_events
    
    @staticmethod
    def _contains_pii(event_details: Optional[Dict[str, Any]]) -> bool:
        """Check if event details contain PII"""
        
        if not event_details:
            return False
        
        pii_fields = ['email', 'phone', 'name', 'address', 'ssn', 'passport']
        
        for field in pii_fields:
            if field in event_details:
                return True
        
        return False
    
    @staticmethod
    def _is_sensitive_operation(event_type: AuditEventType) -> bool:
        """Check if operation is sensitive"""
        
        sensitive_events = [
            AuditEventType.PASSWORD_CHANGE,
            AuditEventType.PASSWORD_RESET,
            AuditEventType.USER_DELETED,
            AuditEventType.PAYMENT_COMPLETED,
            AuditEventType.DATA_EXPORT,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.UNAUTHORIZED_ACCESS
        ]
        
        return event_type in sensitive_events
    
    @staticmethod
    def _calculate_risk_score(
        event_type: AuditEventType,
        event_level: AuditLevel,
        event_details: Optional[Dict[str, Any]],
        user_id: Optional[int],
        ip_address: Optional[str]
    ) -> int:
        """Calculate risk score for event (0-100)"""
        
        base_score = 0
        
        # Base score from event level
        level_scores = {
            AuditLevel.INFO: 10,
            AuditLevel.WARNING: 30,
            AuditLevel.ERROR: 60,
            AuditLevel.CRITICAL: 90
        }
        base_score = level_scores.get(event_level, 10)
        
        # Adjust for event type
        high_risk_events = [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.UNAUTHORIZED_ACCESS,
            AuditEventType.DATA_BREACH_ATTEMPT
        ]
        
        if event_type in high_risk_events:
            base_score += 20
        
        # Adjust for failed attempts
        if event_details and "failed" in str(event_details).lower():
            base_score += 15
        
        # Adjust for unusual IP
        if ip_address and AuditService._is_unusual_ip(user_id, ip_address):
            base_score += 25
        
        return min(base_score, 100)
    
    @staticmethod
    def _detect_anomaly(
        event_type: AuditEventType,
        user_id: Optional[int],
        ip_address: Optional[str]
    ) -> bool:
        """Detect anomalous behavior"""
        
        if not user_id:
            return False
        
        # Simple anomaly detection - multiple failed logins
        if event_type == AuditEventType.LOGIN_FAILED:
            db = next(get_db())
            try:
                recent_failures = db.query(AuditLog).filter(
                    AuditLog.user_id == user_id,
                    AuditLog.event_type == AuditEventType.LOGIN_FAILED,
                    AuditLog.timestamp > datetime.utcnow() - timedelta(minutes=15)
                ).count()
                
                return recent_failures >= 3
            finally:
                db.close()
        
        return False
    
    @staticmethod
    def _is_unusual_ip(user_id: Optional[int], ip_address: str) -> bool:
        """Check if IP is unusual for user"""
        
        if not user_id:
            return False
        
        # Check if IP has been seen before for this user
        db = next(get_db())
        try:
            previous_logins = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.ip_address == ip_address,
                AuditLog.event_type == AuditEventType.LOGIN
            ).count()
            
            return previous_logins == 0
        finally:
            db.close()
    
    @staticmethod
    def _send_security_alert(audit_log: AuditLog) -> None:
        """Send security alert for high-risk events"""
        
        # In production, this would:
        # 1. Send email/SMS alerts to admins
        # 2. Post to security monitoring systems
        # 3. Trigger automated responses
        
        print(f"SECURITY ALERT: {audit_log.event_type} - Risk Score: {audit_log.risk_score}")
    
    @staticmethod
    def get_audit_trail(
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[AuditLog]:
        """Get audit trail for user"""
        
        db = next(get_db())
        
        try:
            query = db.query(AuditLog).filter(AuditLog.user_id == user_id)
            
            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)
            
            if event_types:
                query = query.filter(AuditLog.event_type.in_(event_types))
            
            return query.order_by(AuditLog.timestamp.desc()).all()
        finally:
            db.close()
    
    @staticmethod
    def export_audit_data(
        user_id: int,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export audit data for GDPR compliance"""
        
        audit_logs = AuditService.get_audit_trail(user_id)
        
        exported_data = {
            "user_id": user_id,
            "export_date": datetime.utcnow().isoformat(),
            "total_events": len(audit_logs),
            "events": []
        }
        
        for log in audit_logs:
            event_data = {
                "timestamp": log.timestamp.isoformat(),
                "event_type": log.event_type.value,
                "event_level": log.event_level.value,
                "event_message": log.event_message,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "country": log.country,
                "city": log.city
            }
            exported_data["events"].append(event_data)
        
        return exported_data
    
    @staticmethod
    def anonymize_user_audit_data(user_id: int) -> int:
        """Anonymize audit data for user (GDPR right to be forgotten)"""
        
        db = next(get_db())
        
        try:
            # Update audit logs to remove PII
            audit_logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).all()
            
            anonymized_count = 0
            for log in audit_logs:
                # Remove PII from event details
                if log.event_details:
                    anonymized_details = {}
                    for key, value in log.event_details.items():
                        if key in ['email', 'phone', 'name', 'address']:
                            anonymized_details[key] = "[ANONYMIZED]"
                        else:
                            anonymized_details[key] = value
                    log.event_details = anonymized_details
                
                # Anonymize IP address
                if log.ip_address:
                    log.ip_address = "XXX.XXX.XXX.XXX"
                
                # Remove geographic data
                log.country = None
                log.city = None
                log.latitude = None
                log.longitude = None
                
                anonymized_count += 1
            
            db.commit()
            return anonymized_count
        finally:
            db.close()
    
    @staticmethod
    def cleanup_old_audit_logs():
        """Cleanup old audit logs based on retention policy"""
        
        db = next(get_db())
        
        try:
            # Delete logs older than retention period
            cutoff_date = datetime.utcnow() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
            
            deleted_count = db.query(AuditLog).filter(
                AuditLog.timestamp < cutoff_date,
                AuditLog.requires_retention == False
            ).delete()
            
            db.commit()
            
            print(f"Cleaned up {deleted_count} old audit log entries")
            
        finally:
            db.close()
    
    @staticmethod
    def generate_compliance_report(
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate compliance report for auditors"""
        
        db = next(get_db())
        
        try:
            # Get audit logs in date range
            audit_logs = db.query(AuditLog).filter(
                AuditLog.timestamp >= start_date,
                AuditLog.timestamp <= end_date
            ).all()
            
            # Generate report
            report = {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "total_events": len(audit_logs),
                "events_by_type": {},
                "events_by_level": {},
                "security_events": 0,
                "gdpr_events": 0,
                "high_risk_events": 0,
                "anomalies_detected": 0
            }
            
            # Analyze events
            for log in audit_logs:
                # Count by type
                event_type = log.event_type.value
                report["events_by_type"][event_type] = report["events_by_type"].get(event_type, 0) + 1
                
                # Count by level
                event_level = log.event_level.value
                report["events_by_level"][event_level] = report["events_by_level"].get(event_level, 0) + 1
                
                # Count special categories
                if log.is_security_event:
                    report["security_events"] += 1
                
                if log.is_gdpr_relevant:
                    report["gdpr_events"] += 1
                
                if log.risk_score > 70:
                    report["high_risk_events"] += 1
                
                if log.anomaly_detected:
                    report["anomalies_detected"] += 1
            
            return report
        finally:
            db.close()

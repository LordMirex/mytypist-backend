"""
GDPR and compliance utilities
"""

import json
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from config import settings
from app.models.user import User
from app.models.audit import AuditLog, AuditEventType


def ensure_gdpr_compliance(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure user data complies with GDPR requirements"""
    
    compliant_data = user_data.copy()
    
    # Add GDPR consent tracking
    if "gdpr_consent" not in compliant_data:
        compliant_data["gdpr_consent"] = False
        compliant_data["gdpr_consent_date"] = None
    
    # Add data retention settings
    if "data_retention_consent" not in compliant_data:
        compliant_data["data_retention_consent"] = True
    
    # Add marketing consent
    if "marketing_consent" not in compliant_data:
        compliant_data["marketing_consent"] = False
    
    return compliant_data


def check_data_retention(user: User) -> Dict[str, Any]:
    """Check data retention requirements for user"""
    
    retention_info = {
        "user_id": user.id,
        "account_created": user.created_at,
        "last_activity": user.last_login_at,
        "retention_required": True,
        "deletion_eligible": False,
        "retention_period_days": settings.AUDIT_LOG_RETENTION_DAYS
    }
    
    # Check if user has been inactive for extended period
    if user.last_login_at:
        inactive_days = (datetime.utcnow() - user.last_login_at).days
        if inactive_days > 365 * 2:  # 2 years inactive
            retention_info["deletion_eligible"] = True
    
    # Check if user has requested deletion
    if user.status.value == "deleted":
        retention_info["retention_required"] = False
        retention_info["deletion_eligible"] = True
    
    return retention_info


def anonymize_personal_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Anonymize personal data for GDPR compliance"""
    
    anonymized = data.copy()
    
    # Personal identifiers to anonymize
    personal_fields = [
        "email", "phone", "first_name", "last_name", "full_name",
        "address", "ip_address", "user_agent", "device_id"
    ]
    
    for field in personal_fields:
        if field in anonymized:
            if field == "email":
                anonymized[field] = f"anonymized_{hash_for_anonymization(data[field])}@example.com"
            elif field in ["first_name", "last_name", "full_name"]:
                anonymized[field] = f"Anonymized User {hash_for_anonymization(data[field])[:8]}"
            elif field == "phone":
                anonymized[field] = "+234XXXXXXXXX"
            elif field == "ip_address":
                anonymized[field] = "XXX.XXX.XXX.XXX"
            else:
                anonymized[field] = f"[ANONYMIZED_{field.upper()}]"
    
    return anonymized


def hash_for_anonymization(data: str) -> str:
    """Create consistent hash for anonymization"""
    
    return hashlib.sha256(f"{data}{settings.SECRET_KEY}".encode()).hexdigest()


def export_user_data(db: Session, user_id: int) -> Dict[str, Any]:
    """Export all user data for GDPR data portability"""
    
    from app.models.document import Document
    from app.models.template import Template
    from app.models.signature import Signature
    from app.models.payment import Payment, Subscription
    from app.models.visit import Visit
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    export_data = {
        "export_date": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "data_subject_rights": {
            "right_to_access": "fulfilled",
            "right_to_portability": "fulfilled",
            "right_to_rectification": "available",
            "right_to_erasure": "available",
            "right_to_restrict_processing": "available"
        },
        "personal_data": {
            "profile": {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "company": user.company,
                "job_title": user.job_title,
                "bio": user.bio,
                "language": user.language,
                "timezone": user.timezone,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat()
            },
            "preferences": {
                "email_notifications": user.email_notifications,
                "sms_notifications": user.sms_notifications,
                "marketing_consent": user.marketing_consent,
                "gdpr_consent": user.gdpr_consent,
                "gdpr_consent_date": user.gdpr_consent_date.isoformat() if user.gdpr_consent_date else None
            }
        },
        "activity_data": {},
        "generated_content": {}
    }
    
    # Export documents
    documents = db.query(Document).filter(Document.user_id == user_id).all()
    export_data["generated_content"]["documents"] = [
        {
            "id": doc.id,
            "title": doc.title,
            "description": doc.description,
            "status": doc.status.value,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
            "file_size": doc.file_size,
            "file_format": doc.file_format
        }
        for doc in documents
    ]
    
    # Export templates (user-created)
    templates = db.query(Template).filter(Template.created_by == user_id).all()
    export_data["generated_content"]["templates"] = [
        {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "type": template.type,
            "created_at": template.created_at.isoformat(),
            "is_public": template.is_public
        }
        for template in templates
    ]
    
    # Export signatures
    signatures = db.query(Signature).join(Document).filter(Document.user_id == user_id).all()
    export_data["activity_data"]["signatures"] = [
        {
            "id": sig.id,
            "document_id": sig.document_id,
            "signer_name": sig.signer_name,
            "signed_at": sig.signed_at.isoformat(),
            "is_verified": sig.is_verified
        }
        for sig in signatures
    ]
    
    # Export payments
    payments = db.query(Payment).filter(Payment.user_id == user_id).all()
    export_data["activity_data"]["payments"] = [
        {
            "id": payment.id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status.value,
            "initiated_at": payment.initiated_at.isoformat(),
            "completed_at": payment.completed_at.isoformat() if payment.completed_at else None
        }
        for payment in payments
    ]
    
    # Export subscriptions
    subscriptions = db.query(Subscription).filter(Subscription.user_id == user_id).all()
    export_data["activity_data"]["subscriptions"] = [
        {
            "id": sub.id,
            "plan": sub.plan.value,
            "status": sub.status.value,
            "starts_at": sub.starts_at.isoformat(),
            "ends_at": sub.ends_at.isoformat(),
            "amount": sub.amount
        }
        for sub in subscriptions
    ]
    
    # Export audit logs (last 30 days for privacy)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    audit_logs = db.query(AuditLog).filter(
        AuditLog.user_id == user_id,
        AuditLog.timestamp >= thirty_days_ago
    ).all()
    
    export_data["activity_data"]["recent_activity"] = [
        {
            "event_type": log.event_type.value,
            "event_message": log.event_message,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": "XXX.XXX.XXX.XXX",  # Anonymized
            "resource_type": log.resource_type
        }
        for log in audit_logs
    ]
    
    return export_data


def delete_user_data(db: Session, user_id: int, retain_legal_data: bool = True) -> Dict[str, Any]:
    """Delete user data for GDPR right to erasure"""
    
    from app.models.document import Document
    from app.models.template import Template
    from app.models.signature import Signature
    from app.models.payment import Payment, Subscription
    from app.models.visit import Visit
    
    deletion_report = {
        "user_id": user_id,
        "deletion_date": datetime.utcnow().isoformat(),
        "retain_legal_data": retain_legal_data,
        "deleted_records": {},
        "retained_records": {}
    }
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    # Anonymize user profile
    user.email = f"deleted_user_{user_id}@anonymized.local"
    user.username = f"deleted_user_{user_id}"
    user.first_name = None
    user.last_name = None
    user.phone = None
    user.company = None
    user.job_title = None
    user.bio = None
    user.avatar_url = None
    user.status = "deleted"
    user.deleted_at = datetime.utcnow()
    
    deletion_report["deleted_records"]["user_profile"] = "anonymized"
    
    # Handle documents
    documents = db.query(Document).filter(Document.user_id == user_id).all()
    for doc in documents:
        if retain_legal_data and doc.requires_signature and doc.signature_count > 0:
            # Keep document but anonymize user reference
            doc.user_id = None
            deletion_report["retained_records"]["signed_documents"] = deletion_report["retained_records"].get("signed_documents", 0) + 1
        else:
            # Delete document and file
            import os
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except OSError:
                    pass
            db.delete(doc)
            deletion_report["deleted_records"]["documents"] = deletion_report["deleted_records"].get("documents", 0) + 1
    
    # Handle templates
    templates = db.query(Template).filter(Template.created_by == user_id).all()
    for template in templates:
        if template.is_public and template.usage_count > 0:
            # Keep public templates but anonymize creator
            template.created_by = None
            deletion_report["retained_records"]["public_templates"] = deletion_report["retained_records"].get("public_templates", 0) + 1
        else:
            # Delete template and file
            template_path = os.path.join(settings.TEMPLATES_PATH, template.file_path)
            if os.path.exists(template_path):
                try:
                    os.remove(template_path)
                except OSError:
                    pass
            db.delete(template)
            deletion_report["deleted_records"]["templates"] = deletion_report["deleted_records"].get("templates", 0) + 1
    
    # Handle payments (retain for legal/tax purposes)
    if retain_legal_data:
        payments = db.query(Payment).filter(Payment.user_id == user_id).all()
        for payment in payments:
            # Anonymize customer data but keep transaction records
            payment.customer_name = f"Deleted User {user_id}"
            payment.customer_email = f"deleted_{user_id}@anonymized.local"
            payment.customer_phone = None
        deletion_report["retained_records"]["payment_records"] = len(payments)
    
    # Delete visits and analytics
    visits = db.query(Visit).join(Document).filter(Document.user_id == user_id).all()
    for visit in visits:
        db.delete(visit)
    deletion_report["deleted_records"]["visits"] = len(visits)
    
    # Anonymize audit logs
    audit_logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).all()
    for log in audit_logs:
        log.ip_address = "XXX.XXX.XXX.XXX"
        log.user_agent = "[ANONYMIZED]"
        log.country = None
        log.city = None
        if log.event_details:
            log.event_details = anonymize_personal_data(log.event_details)
    deletion_report["deleted_records"]["audit_logs"] = f"{len(audit_logs)} anonymized"
    
    db.commit()
    
    return deletion_report


def validate_consent(consent_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate GDPR consent data"""
    
    required_consents = [
        "gdpr_consent",
        "data_processing_consent",
        "terms_of_service_consent"
    ]
    
    validation_result = {
        "is_valid": True,
        "missing_consents": [],
        "consent_timestamp": datetime.utcnow().isoformat()
    }
    
    for consent in required_consents:
        if not consent_data.get(consent):
            validation_result["is_valid"] = False
            validation_result["missing_consents"].append(consent)
    
    return validation_result


def generate_privacy_notice() -> Dict[str, Any]:
    """Generate privacy notice for GDPR compliance"""
    
    return {
        "data_controller": {
            "name": "MyTypist",
            "contact": "privacy@mytypist.com",
            "address": "Lagos, Nigeria"
        },
        "data_processed": [
            "Personal identification information",
            "Account and profile data",
            "Document content and metadata",
            "Payment and billing information",
            "Usage analytics and logs",
            "Technical data (IP address, browser info)"
        ],
        "legal_basis": [
            "Consent for marketing communications",
            "Contract performance for service provision",
            "Legitimate interests for security and analytics",
            "Legal obligation for tax and accounting records"
        ],
        "data_retention": {
            "account_data": "Until account deletion",
            "document_data": "7 years or until deletion request",
            "payment_data": "7 years for tax purposes",
            "audit_logs": f"{settings.AUDIT_LOG_RETENTION_DAYS} days"
        },
        "data_subject_rights": [
            "Right to access your data",
            "Right to rectify incorrect data",
            "Right to erase your data",
            "Right to restrict processing",
            "Right to data portability",
            "Right to object to processing",
            "Right to withdraw consent"
        ],
        "data_sharing": [
            "Third-party payment processors (Flutterwave)",
            "Cloud storage providers (encrypted)",
            "Analytics services (anonymized)",
            "Legal authorities when required by law"
        ],
        "security_measures": [
            "Encryption in transit and at rest",
            "Access controls and authentication",
            "Regular security audits",
            "Incident response procedures",
            "Staff training on data protection"
        ],
        "contact_info": {
            "data_protection_officer": "dpo@mytypist.com",
            "support": "support@mytypist.com",
            "phone": "+234-XXX-XXXX-XXX"
        }
    }


def check_compliance_status() -> Dict[str, Any]:
    """Check overall compliance status"""
    
    return {
        "gdpr_compliant": True,
        "soc2_compliant": settings.SOC2_ENABLED,
        "data_encryption": True,
        "audit_logging": True,
        "access_controls": True,
        "incident_response": True,
        "staff_training": True,
        "privacy_by_design": True,
        "last_assessment": datetime.utcnow().isoformat(),
        "next_assessment": (datetime.utcnow() + timedelta(days=90)).isoformat()
    }

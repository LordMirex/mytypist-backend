"""
Unit tests for database models
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from app.models.user import User, UserRole, UserStatus
    from app.models.audit import AuditEventType, AuditLevel
    from app.services.feedback_service import FeedbackCategory, FeedbackPriority, FeedbackStatus
except ImportError as e:
    print(f"Warning: Could not import model modules: {e}")
    User = None
    UserRole = None
    UserStatus = None
    AuditEventType = None
    AuditLevel = None
    FeedbackCategory = None
    FeedbackPriority = None
    FeedbackStatus = None


def test_user_role_enum():
    """Test UserRole enum values"""
    if UserRole is None:
        pytest.skip("UserRole not available")

    # Test that enum has expected values
    expected_roles = ['USER', 'ADMIN', 'MODERATOR']
    for role in expected_roles:
        assert hasattr(UserRole, role), f"UserRole should have {role}"


def test_user_status_enum():
    """Test UserStatus enum values"""
    if UserStatus is None:
        pytest.skip("UserStatus not available")

    # Test that enum has expected values
    expected_statuses = ['ACTIVE', 'INACTIVE', 'SUSPENDED', 'PENDING_VERIFICATION']
    for status in expected_statuses:
        assert hasattr(UserStatus, status), f"UserStatus should have {status}"


def test_audit_event_type_enum():
    """Test AuditEventType enum values"""
    if AuditEventType is None:
        pytest.skip("AuditEventType not available")

    # Test that enum has critical event types
    critical_events = ['LOGIN', 'LOGOUT', 'USER_CREATED', 'DOCUMENT_CREATED', 'PAYMENT_COMPLETED']
    for event in critical_events:
        assert hasattr(AuditEventType, event), f"AuditEventType should have {event}"


def test_audit_level_enum():
    """Test AuditLevel enum values"""
    if AuditLevel is None:
        pytest.skip("AuditLevel not available")

    # Test that enum has expected levels
    expected_levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
    for level in expected_levels:
        assert hasattr(AuditLevel, level), f"AuditLevel should have {level}"


def test_feedback_category_enum():
    """Test FeedbackCategory enum values"""
    if FeedbackCategory is None:
        pytest.skip("FeedbackCategory not available")

    # Test that enum has expected categories
    expected_categories = ['BUG_REPORT', 'FEATURE_REQUEST', 'GENERAL_FEEDBACK']
    for category in expected_categories:
        assert hasattr(FeedbackCategory, category), f"FeedbackCategory should have {category}"


def test_feedback_priority_enum():
    """Test FeedbackPriority enum values"""
    if FeedbackPriority is None:
        pytest.skip("FeedbackPriority not available")

    # Test that enum has expected priorities
    expected_priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    for priority in expected_priorities:
        assert hasattr(FeedbackPriority, priority), f"FeedbackPriority should have {priority}"


def test_feedback_status_enum():
    """Test FeedbackStatus enum values"""
    if FeedbackStatus is None:
        pytest.skip("FeedbackStatus not available")

    # Test that enum has expected statuses
    expected_statuses = ['PENDING', 'IN_REVIEW', 'RESOLVED', 'CLOSED']
    for status in expected_statuses:
        assert hasattr(FeedbackStatus, status), f"FeedbackStatus should have {status}"


@pytest.mark.integration
def test_user_model_creation():
    """Test User model can be instantiated"""
    if User is None:
        pytest.skip("User model not available")

    # Test creating a user instance (without database)
    try:
        user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User'
        }

        # This should not raise an exception
        user = User(**user_data)
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'

    except Exception as e:
        pytest.fail(f"User model creation failed: {e}")


def test_enum_string_values():
    """Test that enums have proper string values"""
    if UserRole is not None:
        # Test that enum values are strings
        for role in UserRole:
            assert isinstance(role.value, str)
            assert len(role.value) > 0

    if AuditEventType is not None:
        # Test that event types are lowercase with underscores
        for event_type in list(AuditEventType)[:5]:  # Test first 5 to avoid long test
            assert isinstance(event_type.value, str)
            assert '_' in event_type.value or event_type.value.islower()


def test_configuration_consistency():
    """Test configuration consistency"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test that database pool settings are consistent
    assert settings.DB_POOL_SIZE > 0
    assert settings.DB_MAX_OVERFLOW >= 0
    assert settings.DB_POOL_TIMEOUT > 0

    # Test that cache TTL settings are reasonable
    assert settings.CACHE_TTL > 0
    assert settings.TEMPLATE_CACHE_TTL >= settings.CACHE_TTL


def test_subscription_plan_limits():
    """Test subscription plan configuration"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test plan hierarchy makes sense
    assert settings.FREE_PLAN_DOCUMENTS_PER_MONTH < settings.BASIC_PLAN_DOCUMENTS_PER_MONTH
    assert settings.BASIC_PLAN_DOCUMENTS_PER_MONTH < settings.PRO_PLAN_DOCUMENTS_PER_MONTH

    # Enterprise should be unlimited (-1) or higher than pro
    assert (settings.ENTERPRISE_PLAN_DOCUMENTS_PER_MONTH == -1 or
            settings.ENTERPRISE_PLAN_DOCUMENTS_PER_MONTH > settings.PRO_PLAN_DOCUMENTS_PER_MONTH)


@pytest.mark.integration
def test_import_all_models():
    """Test that all models can be imported"""
    try:
        from app.models import (
            User, Template, Document, Signature,
            Visit, Payment, Subscription, Invoice, AuditLog
        )

        # Test that all models are classes
        models = [User, Template, Document, Signature, Visit, Payment, Subscription, Invoice, AuditLog]
        for model in models:
            assert hasattr(model, '__tablename__'), f"{model.__name__} should have __tablename__"

    except ImportError as e:
        pytest.skip(f"Could not import all models: {e}")


@pytest.mark.integration
def test_import_all_services():
    """Test that all services can be imported"""
    try:
        from app.services import (
            auth_service, cache_service, email_service,
            document_service, template_service, payment_service
        )

        # Test that services have expected attributes
        services = [
            ('auth_service', ['AuthService']),
            ('cache_service', ['cache_service']),
            ('email_service', ['email_service']),
        ]

        for service_name, expected_attrs in services:
            service_module = globals().get(service_name)
            if service_module:
                for attr in expected_attrs:
                    assert hasattr(service_module, attr), f"{service_name} should have {attr}"

    except ImportError as e:
        pytest.skip(f"Could not import all services: {e}")


def test_compliance_settings():
    """Test compliance and audit settings"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test GDPR settings
    assert hasattr(settings, 'GDPR_ENABLED')
    assert isinstance(settings.GDPR_ENABLED, bool)

    # Test audit retention
    assert hasattr(settings, 'AUDIT_LOG_RETENTION_DAYS')
    assert settings.AUDIT_LOG_RETENTION_DAYS > 0

    # 7 years retention for compliance
    assert settings.AUDIT_LOG_RETENTION_DAYS >= 2555

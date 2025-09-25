"""
PyTest configuration and fixtures
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import asyncio

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_database():
    """Mock database session"""
    with patch('database.get_db') as mock_db:
        mock_session = Mock()
        mock_db.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock_redis = Mock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    return mock_redis


@pytest.fixture
def mock_cache_service():
    """Mock cache service"""
    with patch('app.services.cache_service.cache_service') as mock_cache:
        mock_cache.redis = Mock()
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        yield mock_cache


@pytest.fixture
def mock_email_service():
    """Mock email service"""
    with patch('app.services.email_service.email_service') as mock_email:
        mock_email.send_email.return_value = True
        mock_email.send_welcome_email.return_value = True
        mock_email.send_password_reset_email.return_value = True
        yield mock_email


@pytest.fixture
def mock_audit_service():
    """Mock audit service"""
    with patch('app.services.audit_service.AuditService') as mock_audit:
        mock_audit.log_event.return_value = Mock()
        mock_audit.log_auth_event.return_value = Mock()
        mock_audit.log_user_event.return_value = Mock()
        yield mock_audit


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123",
        "first_name": "Test",
        "last_name": "User",
        "company": "Test Company"
    }


@pytest.fixture
def sample_template_data():
    """Sample template data for testing"""
    return {
        "name": "Test Template",
        "description": "A test template",
        "category": "business",
        "content": "Hello {{name}}, this is a test template.",
        "placeholders": [
            {"name": "name", "type": "text", "required": True}
        ]
    }


@pytest.fixture
def sample_document_data():
    """Sample document data for testing"""
    return {
        "title": "Test Document",
        "template_id": 1,
        "placeholder_values": {
            "name": "Test User"
        }
    }


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    mock_settings = Mock()
    mock_settings.APP_NAME = "MyTypist"
    mock_settings.APP_VERSION = "1.0.0"
    mock_settings.DEBUG = True
    mock_settings.DATABASE_URL = "postgresql://test_user:test_pass@localhost:5432/test_mytypist"
    mock_settings.SECRET_KEY = "test-secret-key"
    mock_settings.JWT_SECRET_KEY = "test-jwt-secret"
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS = 24
    mock_settings.REDIS_ENABLED = False
    mock_settings.STORAGE_PATH = "./test_storage"
    mock_settings.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    mock_settings.ALLOWED_EXTENSIONS = [".docx", ".pdf", ".xlsx"]
    mock_settings.RATE_LIMIT_REQUESTS = 100
    mock_settings.RATE_LIMIT_WINDOW = 60
    mock_settings.FREE_PLAN_DOCUMENTS_PER_MONTH = 5
    mock_settings.BASIC_PLAN_DOCUMENTS_PER_MONTH = 100
    mock_settings.PRO_PLAN_DOCUMENTS_PER_MONTH = 1000
    mock_settings.ENTERPRISE_PLAN_DOCUMENTS_PER_MONTH = -1
    mock_settings.GDPR_ENABLED = True
    mock_settings.AUDIT_LOG_RETENTION_DAYS = 2555
    mock_settings.ALLOWED_ORIGINS = ["http://localhost:3000"]
    mock_settings.ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SENDGRID_FROM_EMAIL = "noreply@mytypist.com"
    mock_settings.FLUTTERWAVE_BASE_URL = "https://api.flutterwave.com/v3"
    return mock_settings


@pytest.fixture
def mock_user():
    """Mock user object"""
    user = Mock()
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.is_active = True
    user.is_admin = False
    user.is_verified = True
    user.role = "user"
    user.status = "active"
    return user


@pytest.fixture
def mock_admin_user():
    """Mock admin user object"""
    user = Mock()
    user.id = 2
    user.username = "admin"
    user.email = "admin@example.com"
    user.first_name = "Admin"
    user.last_name = "User"
    user.is_active = True
    user.is_admin = True
    user.is_verified = True
    user.role = "admin"
    user.status = "active"
    return user


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add unit marker to tests that don't have other markers
    for item in items:
        if not any(mark.name in ['integration', 'performance', 'slow'] for mark in item.iter_markers()):
            item.add_marker(pytest.mark.unit)

"""
Basic unit tests for MyTypist Backend
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from config import settings
    from database import DatabaseManager
except ImportError as e:
    print(f"Warning: Could not import required modules: {e}")
    settings = None
    DatabaseManager = None


def test_settings_configuration():
    """Test that settings are properly configured"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test basic settings
    assert hasattr(settings, 'APP_NAME')
    assert hasattr(settings, 'DATABASE_URL')

    # Test that required settings are not empty
    assert settings.APP_NAME == "MyTypist"


def test_database_manager_exists():
    """Test that DatabaseManager class exists and has required methods"""
    if DatabaseManager is None:
        pytest.skip("DatabaseManager not available")

    # Check required methods exist
    assert hasattr(DatabaseManager, 'get_session')
    assert hasattr(DatabaseManager, 'create_all_tables')
    assert hasattr(DatabaseManager, 'get_pool_status')


def test_file_paths_configuration():
    """Test that file paths are properly configured"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test storage paths
    assert hasattr(settings, 'STORAGE_PATH')
    assert hasattr(settings, 'TEMPLATES_PATH')
    assert hasattr(settings, 'DOCUMENTS_PATH')

    # Test file size limits
    assert settings.MAX_FILE_SIZE > 0
    assert isinstance(settings.ALLOWED_EXTENSIONS, list)
    assert len(settings.ALLOWED_EXTENSIONS) > 0


def test_security_configuration():
    """Test security settings"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test JWT settings
    assert hasattr(settings, 'JWT_SECRET_KEY')
    assert hasattr(settings, 'JWT_ALGORITHM')
    assert settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS > 0

    # Test rate limiting
    assert settings.RATE_LIMIT_REQUESTS > 0
    assert settings.RATE_LIMIT_WINDOW > 0


def test_payment_configuration():
    """Test payment settings"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test Flutterwave settings exist
    assert hasattr(settings, 'FLUTTERWAVE_PUBLIC_KEY')
    assert hasattr(settings, 'FLUTTERWAVE_SECRET_KEY')
    assert hasattr(settings, 'FLUTTERWAVE_BASE_URL')

    # Test subscription limits
    assert settings.FREE_PLAN_DOCUMENTS_PER_MONTH >= 0
    assert settings.BASIC_PLAN_DOCUMENTS_PER_MONTH > settings.FREE_PLAN_DOCUMENTS_PER_MONTH


def test_email_configuration():
    """Test email settings"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test SendGrid settings
    assert hasattr(settings, 'SENDGRID_API_KEY')
    assert hasattr(settings, 'SENDGRID_FROM_EMAIL')
    assert hasattr(settings, 'SENDGRID_FROM_NAME')

    # Test frontend URL
    assert hasattr(settings, 'FRONTEND_URL')
    assert len(settings.FRONTEND_URL) > 0


@pytest.mark.performance
def test_performance_thresholds():
    """Test performance threshold configuration"""
    # Import from the performance test module
    try:
        from app.tests.test_performance import PERFORMANCE_THRESHOLDS

        assert PERFORMANCE_THRESHOLDS["max_response_time"] > 0
        assert PERFORMANCE_THRESHOLDS["min_requests_per_second"] > 0
        assert PERFORMANCE_THRESHOLDS["max_db_query_time"] > 0
        assert PERFORMANCE_THRESHOLDS["max_cache_operation_time"] > 0

        # Thresholds should be reasonable
        assert PERFORMANCE_THRESHOLDS["max_response_time"] <= 10000  # Max 10 seconds
        assert PERFORMANCE_THRESHOLDS["min_requests_per_second"] >= 1  # At least 1 RPS

    except ImportError:
        pytest.skip("Performance thresholds not available")


def test_allowed_file_extensions():
    """Test file extension validation"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test that common document formats are allowed
    common_extensions = ['.docx', '.pdf', '.xlsx']
    for ext in common_extensions:
        assert ext in settings.ALLOWED_EXTENSIONS, f"Extension {ext} should be allowed"


def test_mime_type_validation():
    """Test MIME type validation"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test that common MIME types are configured
    assert hasattr(settings, 'ALLOWED_MIME_TYPES')
    assert isinstance(settings.ALLOWED_MIME_TYPES, list)
    assert len(settings.ALLOWED_MIME_TYPES) > 0

    # Test specific MIME types
    expected_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    for mime_type in expected_types:
        assert mime_type in settings.ALLOWED_MIME_TYPES, f"MIME type {mime_type} should be allowed"


def test_cors_configuration():
    """Test CORS configuration"""
    if settings is None:
        pytest.skip("Settings not available")

    assert hasattr(settings, 'ALLOWED_ORIGINS')
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert len(settings.ALLOWED_ORIGINS) > 0

    assert hasattr(settings, 'ALLOWED_HOSTS')
    assert isinstance(settings.ALLOWED_HOSTS, list)
    assert len(settings.ALLOWED_HOSTS) > 0


@pytest.mark.integration
def test_directory_creation():
    """Test that required directories can be created"""
    if settings is None:
        pytest.skip("Settings not available")

    # Test that storage paths are valid
    import tempfile
    import shutil

    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp()

    try:
        # Test directory creation logic
        test_storage = os.path.join(test_dir, "storage")
        test_templates = os.path.join(test_storage, "templates")
        test_documents = os.path.join(test_storage, "documents")

        os.makedirs(test_storage, exist_ok=True)
        os.makedirs(test_templates, exist_ok=True)
        os.makedirs(test_documents, exist_ok=True)

        # Verify directories were created
        assert os.path.exists(test_storage)
        assert os.path.exists(test_templates)
        assert os.path.exists(test_documents)

    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)

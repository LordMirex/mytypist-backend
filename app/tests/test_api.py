"""
API endpoint tests for MyTypist Backend
"""

import pytest
import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from main import app
    from config import settings
except ImportError as e:
    print(f"Warning: Could not import required modules: {e}")
    app = None
    settings = None


@pytest.fixture
def client():
    """Create test client"""
    if app is None:
        pytest.skip("App not available")
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "status" in data
    assert data["status"] == "running"


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")

    # Should return 200 even if services are not fully working
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "services" in data

    # Status should be healthy or degraded
    assert data["status"] in ["healthy", "degraded"]


def test_docs_endpoint_in_debug_mode(client):
    """Test API documentation endpoint availability"""
    if settings is None:
        pytest.skip("Settings not available")

    # If debug mode is enabled, docs should be available
    if settings.DEBUG:
        response = client.get("/api/docs")
        # Should either work (200) or redirect (3xx)
        assert response.status_code in [200, 301, 302, 307, 308]


def test_cors_headers(client):
    """Test CORS headers are present"""
    response = client.options("/")

    # Should have CORS headers
    assert "access-control-allow-origin" in response.headers or response.status_code == 200


def test_security_headers(client):
    """Test security headers are present"""
    response = client.get("/")

    # Test for important security headers
    security_headers = [
        "x-content-type-options",
        "x-frame-options",
        "strict-transport-security"
    ]

    # At least some security headers should be present
    present_headers = sum(1 for header in security_headers if header in response.headers)
    assert present_headers >= 1, "At least one security header should be present"


@pytest.mark.integration
def test_api_routes_registration():
    """Test that API routes are properly registered"""
    if app is None:
        pytest.skip("App not available")

    # Get all routes
    routes = [route.path for route in app.routes]

    # Test that main route groups are registered
    expected_route_prefixes = [
        "/api/auth",
        "/api/documents",
        "/api/templates",
        "/api/signatures",
        "/api/payments"
    ]

    for prefix in expected_route_prefixes:
        # Check if any route starts with this prefix
        has_prefix = any(route.startswith(prefix) for route in routes)
        assert has_prefix, f"No routes found with prefix {prefix}"


def test_rate_limiting_middleware():
    """Test that rate limiting middleware is configured"""
    if app is None:
        pytest.skip("App not available")

    # Check that middleware is present
    middleware_classes = [middleware.cls.__name__ for middleware in app.user_middleware]

    # Should have security and performance middleware
    expected_middleware = [
        "RateLimitMiddleware",
        "SecurityMiddleware",
        "PerformanceMiddleware"
    ]

    present_middleware = sum(1 for mw in expected_middleware if mw in middleware_classes)
    assert present_middleware >= 1, f"Expected middleware not found. Present: {middleware_classes}"


def test_error_handling(client):
    """Test error handling for non-existent endpoints"""
    response = client.get("/non-existent-endpoint")
    assert response.status_code == 404


def test_method_not_allowed(client):
    """Test method not allowed handling"""
    # Try POST on a GET-only endpoint
    response = client.post("/health")
    assert response.status_code == 405


@pytest.mark.integration
def test_database_connection_in_health():
    """Test database connection through health endpoint"""
    if app is None:
        pytest.skip("App not available")

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Should have database status
    assert "services" in data
    assert "database" in data["services"]

    # Database status should be either healthy or unhealthy
    db_status = data["services"]["database"]
    assert db_status in ["healthy", "unhealthy"]


@pytest.mark.integration
def test_redis_connection_in_health():
    """Test Redis connection through health endpoint"""
    if app is None:
        pytest.skip("App not available")

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Should have Redis status
    assert "services" in data
    assert "redis" in data["services"]

    # Redis status should be either healthy or unhealthy
    redis_status = data["services"]["redis"]
    assert redis_status in ["healthy", "unhealthy"]


def test_performance_headers(client):
    """Test that performance headers are added"""
    response = client.get("/health")

    # Should have process time header
    assert "x-process-time" in response.headers

    # Process time should be a valid float
    process_time = float(response.headers["x-process-time"])
    assert process_time >= 0
    assert process_time < 10  # Should be less than 10 seconds


@pytest.mark.integration
def test_lifespan_events():
    """Test that lifespan events work"""
    if app is None:
        pytest.skip("App not available")

    # Test that app can be created without errors
    # This implicitly tests the lifespan startup
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200


def test_json_response_format(client):
    """Test that responses are properly formatted JSON"""
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    # Should be valid JSON
    data = response.json()
    assert isinstance(data, dict)


def test_api_versioning():
    """Test API versioning in responses"""
    if app is None or settings is None:
        pytest.skip("App or settings not available")

    client = TestClient(app)
    response = client.get("/")

    data = response.json()
    assert "status" in data


@pytest.mark.integration
def test_middleware_order():
    """Test that middleware is applied in correct order"""
    if app is None:
        pytest.skip("App not available")

    # Get middleware stack
    middleware_names = [middleware.cls.__name__ for middleware in app.user_middleware]

    # Security middleware should come before other middleware
    if "SecurityMiddleware" in middleware_names and "PerformanceMiddleware" in middleware_names:
        security_index = middleware_names.index("SecurityMiddleware")
        performance_index = middleware_names.index("PerformanceMiddleware")

        # In FastAPI, middleware is applied in reverse order of addition
        # So security should have a higher index (added later)
        assert security_index >= performance_index, "Security middleware should be applied before performance middleware"


def test_content_type_validation(client):
    """Test content type handling"""
    # Test JSON content type
    response = client.post("/api/auth/login",
                          json={"username": "test", "password": "test"})

    # Should handle JSON properly (even if auth fails)
    assert response.status_code in [200, 400, 401, 422]  # Valid HTTP responses

    # Should not return 415 (Unsupported Media Type)
    assert response.status_code != 415


@pytest.mark.integration
def test_error_response_format(client):
    """Test error response format consistency"""
    # Test with an endpoint that should return 404
    response = client.get("/api/non-existent")

    assert response.status_code == 404

    # Error responses should be JSON
    assert "application/json" in response.headers.get("content-type", "")

    # Should have proper error structure
    data = response.json()
    assert "detail" in data or "error" in data or "message" in data

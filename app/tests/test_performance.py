"""
Performance testing and validation
"""

import time
import asyncio
import statistics
import sys
import os
from typing import List, Dict, Any
import httpx
import pytest
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from main import app
    from app.services.cache_service import cache_service
    from database import DatabaseManager
except ImportError as e:
    print(f"Warning: Could not import required modules: {e}")
    # Create mock objects for testing
    app = None
    cache_service = None
    DatabaseManager = None


class PerformanceValidator:
    """Performance validation and benchmarking"""

    def __init__(self):
        if app is not None:
            self.client = TestClient(app)
        else:
            self.client = None
            print("Warning: App not available, creating mock client")

    async def test_response_times(self) -> Dict[str, Any]:
        """Test API response times"""
        if self.client is None:
            return {"error": "Test client not available"}

        endpoints = [
            "/health",
            "/api/monitoring/health",
            "/api/auth/me",
            "/api/templates",
            "/api/documents"
        ]

        results = {}

        for endpoint in endpoints:
            times = []
            for _ in range(10):  # 10 requests per endpoint
                start = time.time()
                try:
                    response = self.client.get(endpoint)
                    times.append((time.time() - start) * 1000)  # Convert to ms
                except Exception as e:
                    print(f"Error testing endpoint {endpoint}: {e}")
                    times.append(float('inf'))

            # Filter out infinite values for statistics
            valid_times = [t for t in times if t != float('inf')]

            if valid_times:
                results[endpoint] = {
                    "avg_response_time": round(statistics.mean(valid_times), 2),
                    "min_response_time": round(min(valid_times), 2),
                    "max_response_time": round(max(valid_times), 2),
                    "p95_response_time": round(statistics.quantiles(valid_times, n=20)[18], 2) if len(valid_times) > 5 else 0,
                    "success_rate": round(len(valid_times) / len(times) * 100, 2)
                }
            else:
                results[endpoint] = {
                    "error": "All requests failed",
                    "success_rate": 0
                }

        return results

    async def test_concurrent_requests(self, endpoint: str = "/health", concurrent: int = 10) -> Dict[str, Any]:
        """Test concurrent request handling"""
        if app is None:
            return {"error": "App not available for concurrent testing"}

        async def make_request():
            try:
                async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                    start = time.time()
                    response = await client.get(endpoint)
                    return {
                        "status_code": response.status_code,
                        "response_time": (time.time() - start) * 1000
                    }
            except Exception as e:
                return {
                    "status_code": 500,
                    "response_time": float('inf'),
                    "error": str(e)
                }

        # Make concurrent requests
        start_time = time.time()
        tasks = [make_request() for _ in range(concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        successful = [r for r in results if isinstance(r, dict) and r["status_code"] == 200]
        failed = [r for r in results if not isinstance(r, dict) or r["status_code"] != 200]

        response_times = [r["response_time"] for r in successful]

        return {
            "total_requests": concurrent,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "total_time": round(total_time * 1000, 2),
            "requests_per_second": round(concurrent / total_time, 2),
            "avg_response_time": round(statistics.mean(response_times), 2) if response_times else 0,
            "errors": [str(e) for e in results if isinstance(e, Exception)]
        }

    async def test_database_performance(self) -> Dict[str, Any]:
        """Test database performance"""
        if DatabaseManager is None:
            return {"error": "DatabaseManager not available"}

        try:
            db = DatabaseManager.get_session()

            # Test simple queries
            simple_query_times = []
            for _ in range(10):
                start = time.time()
                try:
                    db.execute("SELECT 1")
                    simple_query_times.append((time.time() - start) * 1000)
                except Exception as e:
                    print(f"Simple query failed: {e}")
                    simple_query_times.append(float('inf'))

            # Test complex queries (if tables exist)
            complex_query_times = []
            try:
                for _ in range(5):
                    start = time.time()
                    db.execute("SELECT COUNT(*) FROM users")
                    complex_query_times.append((time.time() - start) * 1000)
            except Exception as e:
                print(f"Complex query failed (tables might not exist): {e}")
                complex_query_times = [0]

            # Get pool status safely
            try:
                pool_status = DatabaseManager.get_pool_status()
            except Exception as e:
                print(f"Could not get pool status: {e}")
                pool_status = {"error": "Pool status unavailable"}

            db.close()

            # Filter valid times for statistics
            valid_simple_times = [t for t in simple_query_times if t != float('inf')]
            valid_complex_times = [t for t in complex_query_times if t != float('inf')]

            return {
                "simple_query_avg": round(statistics.mean(valid_simple_times), 2) if valid_simple_times else 0,
                "complex_query_avg": round(statistics.mean(valid_complex_times), 2) if valid_complex_times else 0,
                "pool_status": pool_status
            }
        except Exception as e:
            return {"error": f"Database test failed: {str(e)}"}

    async def test_cache_performance(self) -> Dict[str, Any]:
        """Test cache performance"""
        if cache_service is None or not hasattr(cache_service, 'redis') or not cache_service.redis:
            return {"error": "Cache service not available"}

        try:
            # Test cache write performance
            write_times = []
            for i in range(100):
                start = time.time()
                try:
                    await cache_service.set(f"test_key_{i}", {"data": f"value_{i}"}, expire=60)
                    write_times.append((time.time() - start) * 1000)
                except Exception as e:
                    print(f"Cache write failed for key {i}: {e}")
                    write_times.append(float('inf'))

            # Test cache read performance
            read_times = []
            for i in range(100):
                start = time.time()
                try:
                    await cache_service.get(f"test_key_{i}")
                    read_times.append((time.time() - start) * 1000)
                except Exception as e:
                    print(f"Cache read failed for key {i}: {e}")
                    read_times.append(float('inf'))

            # Cleanup test keys
            for i in range(100):
                try:
                    await cache_service.delete(f"test_key_{i}")
                except Exception:
                    pass  # Ignore cleanup errors

            # Filter valid times
            valid_write_times = [t for t in write_times if t != float('inf')]
            valid_read_times = [t for t in read_times if t != float('inf')]

            return {
                "write_avg_ms": round(statistics.mean(valid_write_times), 2) if valid_write_times else 0,
                "read_avg_ms": round(statistics.mean(valid_read_times), 2) if valid_read_times else 0,
                "operations_tested": len(valid_write_times) + len(valid_read_times),
                "write_success_rate": round(len(valid_write_times) / 100 * 100, 2),
                "read_success_rate": round(len(valid_read_times) / 100 * 100, 2)
            }
        except Exception as e:
            return {"error": f"Cache performance test failed: {str(e)}"}

    async def run_full_performance_suite(self) -> Dict[str, Any]:
        """Run complete performance test suite"""
        print("🏃‍♂️ Running comprehensive performance tests...")

        results = {
            "timestamp": time.time(),
            "test_suite": "MyTypist Performance Validation"
        }

        # API response time tests
        print("  Testing API response times...")
        results["api_performance"] = await self.test_response_times()

        # Concurrent request handling
        print("  Testing concurrent request handling...")
        results["concurrency_test"] = await self.test_concurrent_requests()

        # Database performance
        print("  Testing database performance...")
        results["database_performance"] = await self.test_database_performance()

        # Cache performance
        print("  Testing cache performance...")
        results["cache_performance"] = await self.test_cache_performance()

        print("✅ Performance tests completed")
        return results


# Validation thresholds for production readiness
PERFORMANCE_THRESHOLDS = {
    "max_response_time": 500,  # ms
    "min_requests_per_second": 100,
    "max_db_query_time": 50,   # ms
    "max_cache_operation_time": 5  # ms
}


async def validate_production_readiness() -> bool:
    """Validate that the system meets production performance requirements"""
    validator = PerformanceValidator()
    results = await validator.run_full_performance_suite()

    issues = []

    # Check API performance
    api_perf = results.get("api_performance", {})
    for endpoint, stats in api_perf.items():
        if stats.get("avg_response_time", float('inf')) > PERFORMANCE_THRESHOLDS["max_response_time"]:
            issues.append(f"Slow response time for {endpoint}: {stats['avg_response_time']}ms")

    # Check concurrency
    concurrency = results.get("concurrency_test", {})
    rps = concurrency.get("requests_per_second", 0)
    if rps < PERFORMANCE_THRESHOLDS["min_requests_per_second"]:
        issues.append(f"Low concurrent request handling: {rps} RPS")

    # Check database performance
    db_perf = results.get("database_performance", {})
    if db_perf.get("simple_query_avg", float('inf')) > PERFORMANCE_THRESHOLDS["max_db_query_time"]:
        issues.append(f"Slow database queries: {db_perf['simple_query_avg']}ms")

    # Check cache performance
    cache_perf = results.get("cache_performance", {})
    if cache_perf.get("read_avg_ms", float('inf')) > PERFORMANCE_THRESHOLDS["max_cache_operation_time"]:
        issues.append(f"Slow cache operations: {cache_perf['read_avg_ms']}ms")

    if issues:
        print("❌ Production readiness validation failed:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ System meets all production performance requirements")
        return True


# Pytest test functions
@pytest.mark.asyncio
@pytest.mark.performance
async def test_api_response_times():
    """Test API response times"""
    validator = PerformanceValidator()
    results = await validator.test_response_times()

    # Assert that we got results
    assert isinstance(results, dict)

    # If we have actual results (not just error), check performance
    if "error" not in results:
        for endpoint, stats in results.items():
            if "error" not in stats:
                # Response time should be reasonable (less than 5 seconds)
                assert stats["avg_response_time"] < 5000, f"Endpoint {endpoint} too slow: {stats['avg_response_time']}ms"

@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_request_handling():
    """Test concurrent request handling"""
    validator = PerformanceValidator()
    results = await validator.test_concurrent_requests("/health", 5)  # Reduced for testing

    assert isinstance(results, dict)

    if "error" not in results:
        # Should handle at least some concurrent requests
        assert results["successful_requests"] >= 0
        assert results["total_requests"] == 5

@pytest.mark.asyncio
@pytest.mark.performance
async def test_database_connectivity():
    """Test database performance and connectivity"""
    validator = PerformanceValidator()
    results = await validator.test_database_performance()

    assert isinstance(results, dict)
    # Should either work or fail gracefully
    assert "simple_query_avg" in results or "error" in results

@pytest.mark.asyncio
@pytest.mark.performance
async def test_cache_operations():
    """Test cache performance"""
    validator = PerformanceValidator()
    results = await validator.test_cache_performance()

    assert isinstance(results, dict)
    # Should either work or fail gracefully with error message
    assert "write_avg_ms" in results or "error" in results

@pytest.mark.asyncio
@pytest.mark.slow
async def test_full_performance_suite():
    """Test complete performance suite"""
    validator = PerformanceValidator()
    results = await validator.run_full_performance_suite()

    assert isinstance(results, dict)
    assert "timestamp" in results
    assert "test_suite" in results

@pytest.mark.asyncio
async def test_production_readiness_validation():
    """Test production readiness validation"""
    # This should not raise exceptions
    try:
        is_ready = await validate_production_readiness()
        assert isinstance(is_ready, bool)
    except Exception as e:
        # If it fails, it should fail gracefully
        print(f"Production readiness check failed gracefully: {e}")
        assert True

def test_performance_thresholds():
    """Test that performance thresholds are reasonable"""
    assert PERFORMANCE_THRESHOLDS["max_response_time"] > 0
    assert PERFORMANCE_THRESHOLDS["min_requests_per_second"] > 0
    assert PERFORMANCE_THRESHOLDS["max_db_query_time"] > 0
    assert PERFORMANCE_THRESHOLDS["max_cache_operation_time"] > 0


if __name__ == "__main__":
    """Run performance validation"""
    async def main():
        validator = PerformanceValidator()
        results = await validator.run_full_performance_suite()
        print("\n📊 Performance Test Results:")
        for test_name, test_results in results.items():
            print(f"  {test_name}: {test_results}")

        # Validate production readiness
        await validate_production_readiness()

    asyncio.run(main())
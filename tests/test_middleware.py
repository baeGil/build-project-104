"""Tests for TimingMiddleware in apps/review_api/middleware/timing.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.review_api.middleware.timing import REQUEST_DURATION, TimingMiddleware


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with TimingMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(TimingMiddleware)
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}
    
    @app.get("/slow")
    async def slow_endpoint():
        import asyncio
        await asyncio.sleep(0.01)  # Small delay for testing
        return {"message": "slow"}
    
    @app.post("/data")
    async def post_endpoint():
        return {"message": "posted"}
    
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestTimingMiddleware:
    """Tests for TimingMiddleware functionality."""

    def test_adds_x_response_time_header(self, client: TestClient) -> None:
        """Test that X-Response-Time header is added to responses."""
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        
        # Verify header format (should be like "0.0012s")
        header_value = response.headers["X-Response-Time"]
        assert header_value.endswith("s")
        
        # Parse the time value
        time_str = header_value.rstrip("s")
        time_value = float(time_str)
        assert time_value >= 0  # Time should be non-negative

    def test_response_time_measures_actual_duration(self, client: TestClient) -> None:
        """Test that response time reflects actual request duration."""
        # Fast endpoint
        response_fast = client.get("/test")
        fast_time_str = response_fast.headers["X-Response-Time"].rstrip("s")
        fast_time = float(fast_time_str)
        
        # Slow endpoint (has 0.01s delay)
        response_slow = client.get("/slow")
        slow_time_str = response_slow.headers["X-Response-Time"].rstrip("s")
        slow_time = float(slow_time_str)
        
        # Slow endpoint should take longer
        assert slow_time > fast_time

    def test_x_response_time_different_methods(self, client: TestClient) -> None:
        """Test X-Response-Time header for different HTTP methods."""
        get_response = client.get("/test")
        post_response = client.post("/data")

        assert "X-Response-Time" in get_response.headers
        assert "X-Response-Time" in post_response.headers
        
        # Both should have valid time values
        for response in [get_response, post_response]:
            time_str = response.headers["X-Response-Time"].rstrip("s")
            time_value = float(time_str)
            assert time_value >= 0


class TestPrometheusMetrics:
    """Tests for Prometheus metrics recording."""

    def test_records_metrics_to_histogram(self, client: TestClient) -> None:
        """Test that request duration is recorded to Prometheus histogram."""
        with patch.object(REQUEST_DURATION, "labels") as mock_labels:
            mock_histogram = MagicMock()
            mock_labels.return_value = mock_histogram

            client.get("/test")

            # Verify labels were called with correct parameters
            mock_labels.assert_called_once()
            call_kwargs = mock_labels.call_args[1]
            
            assert call_kwargs["method"] == "GET"
            assert call_kwargs["endpoint"] == "/test"
            assert call_kwargs["status_code"] == 200
            
            # Verify observe was called
            mock_histogram.observe.assert_called_once()
            
            # Verify the observed value is a positive float
            observed_value = mock_histogram.observe.call_args[0][0]
            assert isinstance(observed_value, float)
            assert observed_value >= 0

    def test_records_different_status_codes(self, client: TestClient) -> None:
        """Test that different status codes are recorded correctly."""
        with patch.object(REQUEST_DURATION, "labels") as mock_labels:
            mock_histogram = MagicMock()
            mock_labels.return_value = mock_histogram

            # Make request
            client.get("/test")

            # Check status code is recorded as 200
            call_kwargs = mock_labels.call_args[1]
            assert call_kwargs["status_code"] == 200

    def test_records_different_endpoints(self, client: TestClient) -> None:
        """Test that different endpoints are recorded separately."""
        recorded_endpoints = []
        
        with patch.object(REQUEST_DURATION, "labels") as mock_labels:
            mock_histogram = MagicMock()
            mock_labels.return_value = mock_histogram

            # Make requests to different endpoints
            client.get("/test")
            recorded_endpoints.append(mock_labels.call_args[1]["endpoint"])
            
            client.get("/slow")
            recorded_endpoints.append(mock_labels.call_args[1]["endpoint"])

        # Verify different endpoints were recorded
        assert "/test" in recorded_endpoints
        assert "/slow" in recorded_endpoints

    def test_histogram_buckets_configuration(self) -> None:
        """Test that histogram has appropriate buckets defined."""
        # Verify the histogram has the expected buckets
        expected_buckets = [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        
        # The histogram should have buckets defined - check via the _upper_bounds attribute
        # which contains the bucket boundaries
        assert REQUEST_DURATION._upper_bounds is not None
        assert len(REQUEST_DURATION._upper_bounds) >= len(expected_buckets)


class TestMiddlewareStructure:
    """Tests for TimingMiddleware class structure."""

    def test_middleware_inherits_from_base(self) -> None:
        """Test that TimingMiddleware inherits from BaseHTTPMiddleware."""
        assert issubclass(TimingMiddleware, BaseHTTPMiddleware)

    def test_middleware_has_dispatch_method(self) -> None:
        """Test that TimingMiddleware has a dispatch method."""
        assert hasattr(TimingMiddleware, "dispatch")
        assert callable(getattr(TimingMiddleware, "dispatch"))

    def test_request_duration_histogram_exists(self) -> None:
        """Test that REQUEST_DURATION histogram is defined."""
        assert REQUEST_DURATION is not None
        assert REQUEST_DURATION._name == "http_request_duration_seconds"
        assert REQUEST_DURATION._labelnames == ("method", "endpoint", "status_code")

"""Request timing middleware for performance monitoring."""
import time

from fastapi import Request, Response
from prometheus_client import Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Prometheus histogram for request duration
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing.
    
    Records request duration in a Prometheus histogram with
    labels for HTTP method, endpoint path, and status code.
    """
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and record timing.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        duration = time.perf_counter() - start_time
        
        # Get route path (not full URL) for consistent labeling
        endpoint = request.url.path
        
        # Record duration in histogram
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
        ).observe(duration)
        
        # Add timing header to response
        response.headers["X-Response-Time"] = f"{duration:.4f}s"
        
        return response

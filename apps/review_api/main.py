"""FastAPI application for Vietnamese Legal Contract Review API."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from apps.review_api.middleware.timing import TimingMiddleware
from apps.review_api.routes import chat, citations, ingest, review
from packages.common.config import get_settings
from packages.common.types import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    # TODO: Initialize database connections, load models, etc.
    yield
    # Shutdown
    # TODO: Close database connections, cleanup resources


app = FastAPI(
    title="Vietnamese Legal Contract Review API",
    description="AI-powered legal contract review and analysis for Vietnamese law",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
app.add_middleware(TimingMiddleware)

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Include routers
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(citations.router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint.
    
    Returns:
        HealthResponse with status and service information
    """
    return HealthResponse(
        status="ok",
        version="0.1.0",
        services={
            "api": "ok",
            # TODO: Add actual service health checks
            "qdrant": "unknown",
            "opensearch": "unknown",
            "postgres": "unknown",
            "redis": "unknown",
        }
    )


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint.
    
    Returns:
        Basic API information
    """
    return {
        "name": "Vietnamese Legal Contract Review API",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.review_api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )

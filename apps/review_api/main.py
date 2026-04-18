"""FastAPI application for Vietnamese Legal Contract Review API."""
import asyncio
import logging
import sys
import warnings
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Suppress multiprocessing resource tracker warnings (macOS only, harmless)
warnings.filterwarnings("ignore", message="resource_tracker")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging with custom formatter for better visibility
class CustomFormatter(logging.Formatter):
    """Custom formatter with colors and cleaner output."""
    
    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    format_string = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    
    FORMATS = {
        logging.DEBUG: grey + format_string + reset,
        logging.INFO: green + format_string + reset,
        logging.WARNING: yellow + format_string + reset,
        logging.ERROR: red + format_string + reset,
        logging.CRITICAL: bold_red + format_string + reset,
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Setup logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and above by default
    format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Silence noisy third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("opensearch").setLevel(logging.WARNING)
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)
logging.getLogger("datasets").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

from apps.review_api.middleware.timing import TimingMiddleware
from apps.review_api.routes import chat, citations, dataset_ingestion, graph, ingest, review
from packages.common.config import get_settings
from packages.graph.legal_graph import LegalGraphClient
from packages.graph.sync import GraphSyncService
from packages.common.types import HealthResponse
from packages.reasoning.generator import LegalGenerator
from packages.reasoning.planner import QueryPlanner
from packages.reasoning.review_pipeline import ContractReviewPipeline
from packages.reasoning.verifier import LegalVerifier
from packages.retrieval.context import ContextInjector
from packages.retrieval.embedding import EmbeddingService
from packages.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    app.state.settings = settings
    app.state.query_planner = QueryPlanner()
    app.state.hybrid_retriever = HybridRetriever(settings)
    app.state.legal_generator = LegalGenerator(settings)
    app.state.legal_verifier = LegalVerifier(settings)
    app.state.review_pipeline = ContractReviewPipeline(settings)
    app.state.graph_client = LegalGraphClient(settings)
    app.state.context_injector = ContextInjector(settings, graph_client=app.state.graph_client)
    app.state.graph_sync = GraphSyncService(
        settings,
        graph_client=app.state.graph_client,
        postgres_pool_getter=app.state.hybrid_retriever._get_postgres_pool,
    )
    app.state.review_pipeline.retriever = app.state.hybrid_retriever
    app.state.review_pipeline.generator = app.state.legal_generator
    app.state.review_pipeline.verifier = app.state.legal_verifier
    app.state.review_pipeline.context_injector = app.state.context_injector
    app.state.embedding_service = EmbeddingService.get_instance(settings.embedding_model)
    
    # Warm-up: Pre-load embedding model and database connections
    # This eliminates cold start latency for first user query
    print("\n" + "="*60)
    print("🚀 Starting Vietnamese Legal AI Backend...")
    print("="*60 + "\n")
    
    try:
        # Load embedding model into memory
        embedding_service = app.state.embedding_service
        _ = embedding_service.encode("warm up query")
        print("✅ Embedding model loaded (768 dimensions)")
        
        # Initialize database connections
        await app.state.hybrid_retriever._get_qdrant_client()
        print("✅ Qdrant connected (Vector Search)")
        
        await app.state.hybrid_retriever._get_opensearch_client()
        print("✅ OpenSearch connected (Full-text Search)")
        
        # Run a dummy search to warm up all pipelines
        await app.state.hybrid_retriever.search("warm up", top_k=1, bm25_candidates=1, dense_candidates=1)
        print("✅ Retrieval system warmed up")
    except Exception as e:
        logger.warning(f"⚠️  Warm-up failed (non-critical): {e}")
    
    print("\n✅ API Server Ready!\n")

    warmup_tasks = (
        app.state.hybrid_retriever._get_qdrant_client(),
        app.state.hybrid_retriever._get_opensearch_client(),
        app.state.hybrid_retriever._get_postgres_pool(),
        app.state.graph_client.ping(),
    )
    results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
    for service_name, result in zip(("qdrant", "opensearch", "postgres", "neo4j"), results):
        if isinstance(result, Exception):
            logger.warning("Startup warmup skipped for %s: %s", service_name, result)
    if results[3] is True:
        try:
            await app.state.graph_client.ensure_schema()
        except Exception as exc:
            logger.warning("Neo4j schema warmup skipped: %s", exc)

    try:
        # Increase warmup timeout to 2 minutes to handle slow downloads on first run
        await asyncio.wait_for(
            asyncio.to_thread(app.state.embedding_service._load_model),
            timeout=120,  # 2 minutes - enough time for model download
        )
        await asyncio.wait_for(
            asyncio.to_thread(app.state.embedding_service.encode_query, "Khoi dong he thong phap ly"),
            timeout=60,  # 1 minute for encoding test
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Embedding model warmup timed out after 120s; continuing without blocking startup."
        )
    except Exception as exc:
        logger.warning("Embedding model warmup skipped: %s", exc)

    # Perform a warmup retrieval query to eliminate cold start latency
    # This ensures the first user request is fast (no embedding load delay)
    try:
        warmup_start = asyncio.get_event_loop().time()
        await app.state.hybrid_retriever.search(
            query="khởi động hệ thống",
            top_k=1,
            bm25_candidates=1,
            dense_candidates=1,
        )
        warmup_duration = asyncio.get_event_loop().time() - warmup_start
        print(f"✅ Warmup query completed in {warmup_duration:.2f}s\n")
    except Exception as exc:
        logger.warning(f"Retrieval warmup query failed (non-critical): {exc}")

    yield
    # Shutdown
    close_targets: list[object] = [
        app.state.hybrid_retriever,
        app.state.review_pipeline.retriever,
        app.state.graph_client,
        app.state.graph_sync,
    ]
    seen: set[int] = set()
    for target in close_targets:
        if id(target) in seen or not hasattr(target, "close"):
            continue
        seen.add(id(target))
        close_result = target.close()
        if asyncio.iscoroutine(close_result):
            await close_result


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
app.include_router(dataset_ingestion.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint.
    
    Returns:
        HealthResponse with status and service information
    """
    retriever = getattr(app.state, "hybrid_retriever", None)

    async def check_qdrant() -> str:
        if retriever is None:
            return "unavailable"
        try:
            client = await retriever._get_qdrant_client()
            await client.get_collections()
            return "ok"
        except Exception as exc:
            logger.warning("Qdrant health check failed: %s", exc)
            return "unhealthy"

    async def check_opensearch() -> str:
        if retriever is None:
            return "unavailable"
        try:
            client = await retriever._get_opensearch_client()
            response = await client.cluster.health()
            return response.get("status", "unknown")
        except Exception as exc:
            logger.warning("OpenSearch health check failed: %s", exc)
            return "unhealthy"

    async def check_postgres() -> str:
        if retriever is None:
            return "unavailable"
        try:
            pool = await retriever._get_postgres_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return "ok"
        except Exception as exc:
            logger.warning("PostgreSQL health check failed: %s", exc)
            return "unhealthy"

    async def check_redis() -> str:
        try:
            import redis.asyncio as redis
        except Exception as exc:
            logger.warning("Redis client unavailable: %s", exc)
            return "unavailable"

        client = redis.from_url(settings.redis_url)
        try:
            await client.ping()
            return "ok"
        except Exception as exc:
            logger.warning("Redis health check failed: %s", exc)
            return "unhealthy"
        finally:
            await client.aclose()

    async def check_neo4j() -> str:
        graph_client = getattr(app.state, "graph_client", None)
        if graph_client is None:
            return "unavailable"
        try:
            healthy = await graph_client.ping()
            return "ok" if healthy else "unhealthy"
        except Exception as exc:
            logger.warning("Neo4j health check failed: %s", exc)
            return "unhealthy"

    qdrant_status, opensearch_status, postgres_status, redis_status, neo4j_status = await asyncio.gather(
        check_qdrant(),
        check_opensearch(),
        check_postgres(),
        check_redis(),
        check_neo4j(),
    )

    services = {
        "api": "ok",
        "qdrant": qdrant_status,
        "opensearch": opensearch_status,
        "postgres": postgres_status,
        "redis": redis_status,
        "neo4j": neo4j_status,
    }
    healthy_states = {"ok", "green", "yellow"}
    status = "ok" if all(value in healthy_states for value in services.values()) else "degraded"

    return HealthResponse(
        status=status,
        version="0.1.0",
        services=services,
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

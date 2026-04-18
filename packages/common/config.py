"""Application configuration management."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # LLM Provider (OpenAI-compatible: OpenRouter, Ollama, etc.)
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "thudm/glm-4-9b"
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "legal_docs"
    
    # OpenSearch
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_index: str = "legal_docs"
    opensearch_user: str = "admin"
    opensearch_password: str = "SecureP@ssw0rd!2024"
    opensearch_use_ssl: bool = False
    opensearch_verify_certs: bool = False
    
    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "legal_review"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    
    # Embedding
    embedding_model: str = "Quockhanh05/Vietnam_legal_embeddings"
    embedding_dim: int = 768
    
    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"
    log_level: str = "info"

    # Search parameters
    search_bm25_candidates: int = 200
    search_dense_candidates: int = 200
    search_rrf_k: int = 60
    search_rrf_top_n: int = 200
    search_expansion_max_variants: int = 4
    search_expansion_boost: float = 0.7
    search_reranker_budget_ms: int = 300
    search_reranker_input_k: int = 15
    search_aggregation_threshold: float = 1.0
    search_chunk_size_tokens: int = 400
    search_chunk_overlap: float = 0.5
    search_min_chunk_tokens: int = 100

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


def get_settings() -> Settings:
    return Settings()

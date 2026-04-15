"""Tests for configuration management."""
import os
from unittest.mock import patch

import pytest
from pydantic_settings import SettingsConfigDict

from packages.common.config import Settings, get_settings


def create_isolated_settings(**kwargs: str | int) -> Settings:
    """Create Settings instance with no env file loading for isolated testing."""

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=None,  # Disable env file loading
            case_sensitive=False,
        )

    return IsolatedSettings(**kwargs)


class TestSettingsDefaults:
    """Tests for Settings default values (with isolated environment)."""

    def test_settings_default_values(self) -> None:
        """Test Settings instantiation with default values."""
        settings = create_isolated_settings()

        # Groq defaults
        assert settings.groq_api_key == ""
        assert settings.groq_model_primary == "llama-3.1-8b-instant"
        assert settings.groq_model_fallback == "llama-3.3-70b-versatile"

        # Qdrant defaults
        assert settings.qdrant_host == "localhost"
        assert settings.qdrant_port == 6333
        assert settings.qdrant_collection == "legal_docs"

        # OpenSearch defaults
        assert settings.opensearch_host == "localhost"
        assert settings.opensearch_port == 9200
        assert settings.opensearch_index == "legal_docs"
        assert settings.opensearch_user == "admin"
        assert settings.opensearch_password == "SecureP@ssw0rd!2024"

        # PostgreSQL defaults
        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.postgres_db == "legal_review"
        assert settings.postgres_user == "postgres"
        assert settings.postgres_password == "postgres"

        # Redis defaults
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 0

        # Neo4j defaults
        assert settings.neo4j_uri == "bolt://localhost:7687"
        assert settings.neo4j_user == "neo4j"
        assert settings.neo4j_password == "password"

        # Embedding defaults
        assert settings.embedding_model == "Quockhanh05/Vietnam_legal_embeddings"
        assert settings.embedding_dim == 768

        # App defaults
        assert settings.app_host == "0.0.0.0"
        assert settings.app_port == 8000
        assert settings.app_env == "development"
        assert settings.log_level == "info"

    def test_postgres_dsn_property(self) -> None:
        """Test postgres_dsn property construction."""
        settings = create_isolated_settings()
        expected_dsn = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
        assert settings.postgres_dsn == expected_dsn

    def test_redis_url_property(self) -> None:
        """Test redis_url property construction."""
        settings = create_isolated_settings()
        expected_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
        assert settings.redis_url == expected_url


class TestSettingsEnvironmentVariables:
    """Tests for Settings loading from environment variables."""

    def test_groq_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test GROQ_API_KEY loading from environment."""
        monkeypatch.setenv("GROQ_API_KEY", "test-api-key-123")
        settings = Settings()
        assert settings.groq_api_key == "test-api-key-123"

    def test_qdrant_host_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test QDRANT_HOST loading from environment."""
        monkeypatch.setenv("QDRANT_HOST", "qdrant-server")
        settings = Settings()
        assert settings.qdrant_host == "qdrant-server"

    def test_qdrant_port_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test QDRANT_PORT loading from environment."""
        monkeypatch.setenv("QDRANT_PORT", "9999")
        settings = Settings()
        assert settings.qdrant_port == 9999

    def test_multiple_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading multiple environment variables."""
        monkeypatch.setenv("GROQ_API_KEY", "sk-test-key")
        monkeypatch.setenv("GROQ_MODEL_PRIMARY", "llama-3.3-70b-versatile")
        monkeypatch.setenv("QDRANT_HOST", "remote-qdrant")
        monkeypatch.setenv("QDRANT_PORT", "7777")
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        settings = Settings()
        assert settings.groq_api_key == "sk-test-key"
        assert settings.groq_model_primary == "llama-3.3-70b-versatile"
        assert settings.qdrant_host == "remote-qdrant"
        assert settings.qdrant_port == 7777
        assert settings.app_env == "production"
        assert settings.log_level == "debug"

    def test_postgres_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PostgreSQL environment variable overrides."""
        monkeypatch.setenv("POSTGRES_HOST", "pg-server")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "secret_pass")

        settings = Settings()
        assert settings.postgres_host == "pg-server"
        assert settings.postgres_port == 5433
        assert settings.postgres_db == "test_db"
        assert settings.postgres_user == "test_user"
        assert settings.postgres_password == "secret_pass"
        assert "pg-server" in settings.postgres_dsn
        assert "secret_pass" in settings.postgres_dsn

    def test_redis_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Redis environment variable overrides."""
        monkeypatch.setenv("REDIS_HOST", "redis-cache")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_DB", "5")

        settings = Settings()
        assert settings.redis_host == "redis-cache"
        assert settings.redis_port == 6380
        assert settings.redis_db == 5
        assert "redis-cache" in settings.redis_url

    def test_neo4j_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Neo4j environment variable overrides."""
        monkeypatch.setenv("NEO4J_URI", "bolt://neo4j-server:7687")
        monkeypatch.setenv("NEO4J_USER", "admin")
        monkeypatch.setenv("NEO4J_PASSWORD", "neo4j-pass")

        settings = Settings()
        assert settings.neo4j_uri == "bolt://neo4j-server:7687"
        assert settings.neo4j_user == "admin"
        assert settings.neo4j_password == "neo4j-pass"

    def test_embedding_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test embedding environment variable overrides."""
        monkeypatch.setenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        monkeypatch.setenv("EMBEDDING_DIM", "384")

        settings = Settings()
        assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert settings.embedding_dim == 384

    def test_app_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test app environment variable overrides."""
        monkeypatch.setenv("APP_HOST", "127.0.0.1")
        monkeypatch.setenv("APP_PORT", "9000")
        monkeypatch.setenv("APP_ENV", "staging")
        monkeypatch.setenv("LOG_LEVEL", "warning")

        settings = Settings()
        assert settings.app_host == "127.0.0.1"
        assert settings.app_port == 9000
        assert settings.app_env == "staging"
        assert settings.log_level == "warning"

    def test_case_insensitive_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test case-insensitive environment variable loading."""
        # Settings has case_sensitive=False in model_config
        monkeypatch.setenv("groq_api_key", "lowercase-key")
        settings = Settings()
        assert settings.groq_api_key == "lowercase-key"


class TestGetSettings:
    """Tests for get_settings() singleton behavior."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_returns_new_instance_each_call(self) -> None:
        """Test get_settings returns a new Settings instance each call (not cached)."""
        settings1 = get_settings()
        settings2 = get_settings()
        # They should be equal in values but different objects
        assert settings1 is not settings2
        assert settings1.groq_model_primary == settings2.groq_model_primary


class TestSettingsValidation:
    """Tests for Settings validation behavior."""

    def test_all_fields_are_optional(self) -> None:
        """Test that all fields have defaults (no required fields)."""
        # Should not raise any validation error
        settings = Settings()
        assert settings is not None

    def test_integer_fields_accept_valid_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test integer fields accept valid integer values."""
        monkeypatch.setenv("QDRANT_PORT", "8080")
        monkeypatch.setenv("APP_PORT", "3000")
        monkeypatch.setenv("REDIS_DB", "10")

        settings = Settings()
        assert settings.qdrant_port == 8080
        assert settings.app_port == 3000
        assert settings.redis_db == 10


class TestSettingsWithPatchDict:
    """Tests using unittest.mock.patch.dict for environment variable testing."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "patched-key", "APP_ENV": "testing"}, clear=False)
    def test_settings_with_patch_dict(self) -> None:
        """Test Settings with patch.dict context manager."""
        settings = Settings()
        assert settings.groq_api_key == "patched-key"
        assert settings.app_env == "testing"

    @patch.dict(
        os.environ,
        {
            "POSTGRES_HOST": "patched-pg",
            "POSTGRES_PORT": "5555",
            "REDIS_HOST": "patched-redis",
        },
        clear=False,
    )
    def test_connection_strings_with_patch_dict(self) -> None:
        """Test connection string generation with patched environment."""
        settings = Settings()
        assert settings.postgres_host == "patched-pg"
        assert settings.postgres_port == 5555
        assert settings.redis_host == "patched-redis"
        assert "patched-pg:5555" in settings.postgres_dsn
        assert "patched-redis" in settings.redis_url

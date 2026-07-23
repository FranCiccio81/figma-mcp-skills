"""Configuration applicative (pydantic-settings).

Variables normatives : annexe Phase 10 de 15-delivery-roadmap.md (§C).
Aucun secret n'est committé (D23) : les valeurs par défaut sont des valeurs
de développement local uniquement.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Environnement : development | staging | production
    env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Base de données (D06) — driver asyncpg requis.
    database_url: str = "postgresql+asyncpg://boussole:boussole@localhost:5432/boussole"

    # Deux Redis logiques (D17) : persistant (sessions + broker Celery, AOF,
    # noeviction) et volatile (cache + rate limiting, allkeys-lru).
    redis_persistent_url: str = "redis://localhost:6379/0"
    redis_cache_url: str = "redis://localhost:6380/0"

    # Stockage objet UE (D09) — MinIO en dev.
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "boussole-dev"
    s3_region: str = "eu-west-1"
    s3_access_key: str = "boussole-dev"
    s3_secret_key: str = "boussole-dev-secret"  # dev uniquement — vault en prod (D23)

    # Sessions opaques en Redis persistant, TTL glissant.
    session_ttl_days: int = 30
    session_cookie_name: str = "boussole_session"
    csrf_cookie_name: str = "boussole_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    # Rate limiting (12-api-contracts §1) — login : 5 tentatives/min.
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 60

    # IA (D08) — clés via vault en prod (D23).
    anthropic_api_key: str = ""
    fallback_llm_api_key: str = ""
    embeddings_model: str = "voyage-3-large"  # hypothèse 🟡 Q11
    embeddings_dim: int = 1024

    # Matching (D02).
    scoring_config_path: str = "config/scoring-config.json"

    # Connecteurs derrière feature flags (Q2/Q3).
    feature_source_france_travail: bool = False
    feature_source_greenhouse: bool = False
    feature_source_lever: bool = False

    # Observabilité (D20).
    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""

    @property
    def session_ttl_seconds(self) -> int:
        return self.session_ttl_days * 24 * 3600

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

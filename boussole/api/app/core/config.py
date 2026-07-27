"""Configuration applicative (pydantic-settings).

Variables normatives : annexe Phase 10 de 15-delivery-roadmap.md (§C).
Aucun secret n'est committé (D23) : les valeurs par défaut sont des valeurs
de développement local uniquement.
"""

from functools import lru_cache
from typing import Literal

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
    # ``local`` = disque du conteneur courant : dev/tests MONO-PROCESSUS
    # uniquement. Dès que l'API et les workers Celery sont deux conteneurs
    # (staging, production, compose de dev), ``s3`` est OBLIGATOIRE — sinon
    # l'export RGPD (F-Q) répond 404 et les CV sont perdus au redémarrage.
    # Refus de démarrage en production : app/core/storage.py
    # ::check_storage_configuration.
    storage_backend: Literal["local", "s3"] = "local"  # 🟡 défaut sûr pour les tests
    storage_local_path: str = ".storage"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "boussole-dev"
    s3_region: str = "eu-west-1"
    s3_access_key: str = "boussole-dev"
    s3_secret_key: str = "boussole-dev-secret"  # dev uniquement — vault en prod (D23)
    # Chiffrement au repos (D09, 09-security-and-privacy §5.6) : cible
    # ``aws:kms`` + clé KMS UE ; ``AES256`` (SSE-S3) est le minimum acceptable
    # 🟡 ; ``none`` est réservé au dev sur MinIO (pas de KES) et refusé en
    # production.
    s3_sse: Literal["none", "AES256", "aws:kms"] = "AES256"
    s3_kms_key_id: str = ""  # vide ⇒ clé gérée par le fournisseur (D23)
    # ``auto`` ⇒ « path » dès qu'un endpoint explicite est configuré (MinIO).
    s3_addressing_style: Literal["auto", "path", "virtual"] = "auto"
    # Bornes réseau botocore — un worker ne doit jamais rester suspendu.
    s3_connect_timeout_seconds: float = 5.0
    s3_read_timeout_seconds: float = 30.0
    s3_max_attempts: int = 3
    # Clé HMAC des liens signés d'export RGPD — dédiée (rotation indépendante
    # du stockage), vault en prod (D23).
    privacy_signing_key: str = "boussole-dev-privacy-signing"

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

    # --- Sélection de provider LLM (D08, D18) -------------------------------
    # Défaut **fake** : le provider réel n'est JAMAIS actif implicitement, et
    # jamais sans clé (voir app/ai/providers/anthropic.py — activation
    # conditionnée à la résolution de Q4, à confirmer par revue juridique).
    ai_provider: str = "fake"  # fake | anthropic 🟡
    #: Second provider (D08) essayé quand le primaire est en échec / circuit
    #: ouvert. Vide = pas de fallback (dégradation directe, D18).
    ai_fallback_provider: str = ""

    # Modèles par tâche — défauts de 08 §2.1 🟡 (changer de modèle = nouvelle
    # version de prompt, 08 §7.1).
    ai_model_extract_cv: str = "claude-sonnet-5"
    ai_model_extract_job: str = "claude-haiku-4-5"
    ai_model_explain_match: str = "claude-haiku-4-5"
    ai_model_generate_email: str = "claude-sonnet-5"
    ai_model_generate_letter: str = "claude-sonnet-5"
    ai_model_tailor_cv: str = "claude-sonnet-5"
    ai_model_optimize_cv: str = "claude-sonnet-5"
    #: Tâche inconnue de la table ci-dessus (garde-fou, jamais nominal).
    ai_model_default: str = "claude-sonnet-5"

    #: Plafond de tokens de sortie par appel 🟡 (les sorties JSON des schémas
    #: sont bornées : body ≤ 6 000 caractères pour la plus longue).
    ai_max_output_tokens: int = 8000
    #: Timeout explicite par appel, en secondes. ``None`` = cibles p95 par
    #: tâche de 08 §2.2 (voir ``TASK_TIMEOUTS``).
    ai_timeout_seconds: float | None = None
    #: Retries provider bornés (réseau / 429 / 5xx) — max 3 🟡 (08 §5.1).
    ai_max_retries: int = 3
    #: Plafond d'attente honorée sur un ``Retry-After`` 429 🟡 : au-delà, on
    #: échoue proprement plutôt que de bloquer un worker.
    ai_retry_after_max_seconds: float = 30.0

    # Circuit breaker par provider (D18) 🟡.
    ai_circuit_breaker_threshold: int = 5
    ai_circuit_breaker_reset_seconds: float = 60.0

    #: Sortie JSON contrainte côté provider (``output_config.format``). En cas
    #: de rejet du schéma par l'API, le provider dégrade automatiquement vers
    #: « prompt + extraction stricte » (repair-parse) et journalise.
    ai_structured_outputs: bool = True

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

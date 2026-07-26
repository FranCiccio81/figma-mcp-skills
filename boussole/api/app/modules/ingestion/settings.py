"""Configuration propre au module ingestion (D01 — pas de fuite globale).

Les feature flags ``FEATURE_SOURCE_*`` restent dans ``app.core.config``
(annexe Phase 10). Ici : identifiants France Travail et registre des
boards ATS activés explicitement (07 §2 — jamais de découverte
automatique ; la table ``connector_boards`` complète 🟡 viendra avec
l'interface d'homologation, en attendant la config fait foi).

Format des boards : ``token:Nom Entreprise`` séparés par des virgules,
ex. ``INGESTION_GREENHOUSE_BOARDS="acme:ACME Corp,globex:Globex"``.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_boards(spec: str) -> list[tuple[str, str]]:
    """``"token:Nom,token2:Nom2"`` → ``[(token, nom), …]`` (nom = token si omis)."""
    boards: list[tuple[str, str]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        token, _, name = chunk.partition(":")
        boards.append((token.strip(), name.strip() or token.strip()))
    return boards


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INGESTION_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # France Travail — OAuth2 client_credentials (francetravail.io).
    france_travail_client_id: str = ""
    france_travail_client_secret: str = ""  # dev uniquement — vault en prod (D23)

    # Boards ATS activés explicitement (07 §2.2/§2.3).
    greenhouse_boards: str = ""
    lever_sites: str = ""

    # Géocodage fallback 🟡 (07 §5.3, Q3).
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"

    @property
    def greenhouse_board_list(self) -> list[tuple[str, str]]:
        return parse_boards(self.greenhouse_boards)

    @property
    def lever_site_list(self) -> list[tuple[str, str]]:
        return parse_boards(self.lever_sites)


@lru_cache
def get_ingestion_settings() -> IngestionSettings:
    return IngestionSettings()

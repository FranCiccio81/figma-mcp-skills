"""Modèles SQLAlchemy propres au module ingestion.

``connector_state`` (07 §4.3, §4.6.2) : curseur de fetch incrémental par
source — le curseur n'avance qu'après un cycle complet réussi — et
compteurs d'absence persistés (``absence_counters``, jsonb
``{job_source_id: n}``) pour le mécanisme d'expiration 2 : ils survivent
aux redémarrages des workers. Créée par la migration
``0002_connector_state``, étendue par ``0003_absence_counters``.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ConnectorState(Base):
    __tablename__ = "connector_state"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cursor: Mapped[str | None] = mapped_column(Text())
    last_sync_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    # {str(job_source_id): nombre d'absences consécutives} — 07 §4.6.2.
    absence_counters: Mapped[dict[str, int]] = mapped_column(
        JSONB(), nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

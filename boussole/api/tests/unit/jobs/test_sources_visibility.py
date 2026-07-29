"""Page des sources : une source active ne disparaît jamais en silence.

Défaut trouvé lors d'une validation à froid : le corpus de démonstration
était actif en base, l'ingestion tournait, ses offres étaient cherchables —
et ``GET /sources`` renvoyait une liste **vide**. La nature ``demo`` ne
figurait pas dans le vocabulaire fermé du contrat, et la source était filtrée
sans un mot.

Le symptôme (« la page des sources est vide ») était très loin de la cause
(« une valeur d'énumération manque »). Or cette page porte une garantie
produit : l'utilisateur doit pouvoir savoir d'où viennent les offres qu'on
lui montre — a fortiori quand elles sont fictives.

Deux corrections : la nature ``demo`` existe au contrat, et tout rejet est
désormais journalisé en WARNING.
"""

import logging
from datetime import UTC, datetime

import pytest

from app.modules.jobs.repository import SourceRow
from app.modules.jobs.service import JobsService


class DepotSources:
    """Ne porte que ``list_sources`` — c'est tout ce que ce chemin utilise."""

    def __init__(self, rows: list[SourceRow]) -> None:
        self._rows = rows

    async def list_sources(self) -> list[SourceRow]:
        return self._rows


def _source(slug: str, kind: str) -> SourceRow:
    return SourceRow(
        slug=slug, name=f"Source {slug}", kind=kind, last_sync_at=datetime.now(UTC)
    )


def _service(rows: list[SourceRow]) -> JobsService:
    return JobsService(DepotSources(rows))  # type: ignore[arg-type]


@pytest.mark.parametrize("kind", ["public_api", "ats_feed", "partner", "demo"])
async def test_toutes_les_natures_du_contrat_sont_visibles(kind: str) -> None:
    sources = await _service([_source("s", kind)]).list_sources()
    assert [s.kind for s in sources] == [kind]


async def test_le_corpus_de_demonstration_apparait() -> None:
    """LE cas du défaut : actif, ingéré, et pourtant invisible."""
    sources = await _service([_source("demo-corpus", "demo")]).list_sources()
    assert [s.slug for s in sources] == ["demo-corpus"]


async def test_une_nature_inconnue_est_journalisee_avant_detre_masquee(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Masquer reste le bon choix — une valeur hors contrat casserait la
    réponse entière. Le masquer EN SILENCE ne l'est pas."""
    service = _service([_source("mystere", "scraping-maison")])
    with caplog.at_level(logging.WARNING, logger="app.modules.jobs.service"):
        sources = await service.list_sources()
    assert sources == []
    messages = [r.getMessage() for r in caplog.records]
    assert any("source_masquee_nature_inconnue" in m for m in messages)
    assert any("mystere" in m for m in messages)

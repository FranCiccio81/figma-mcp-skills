"""L'étage 2 de dédup lit ``candidate.locations`` — et l'a longtemps perdu.

Défaut trouvé en montant le chemin de démonstration de bout en bout, pas par
la suite de tests. ``_too_far_apart`` accède à la relation ``locations`` du
candidat de dédup. En SQLAlchemy asynchrone, un chargement paresseux lève
``MissingGreenlet`` ; l'exception remonte au gestionnaire **par item** de
``ingest_batch``, qui la journalise et passe à l'offre suivante.

Conséquence : **toute offre atteignant le filtre géographique était purement
et simplement perdue**, avec pour seule trace une ligne
``ingestion_item_error``. Or atteindre ce filtre est le cas NORMAL avec de
vraies sources — c'est très exactement la situation que la déduplication
existe pour traiter. Sur douze offres de démonstration, une disparaissait.

Aucun test unitaire ne pouvait le voir : les fakes en mémoire rendent des
objets déjà peuplés, et le chargement paresseux n'existe que contre une vraie
session asynchrone. D'où ce test d'intégration.
"""

import pytest

from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.service import SqlAlchemyJobStore, ingest_batch

pytestmark = pytest.mark.integration

SLUG = "demo-corpus"


def _offre(ref: str, titre: str, entreprise: str, lat: float, lon: float) -> RawJob:
    return RawJob(
        external_ref=ref,
        title=titre,
        company=entreprise,
        description=(
            "Poste d'ingénierie logicielle sur une plateforme conteneurisée, "
            "avec de l'orchestration et de l'infrastructure as code."
        ),
        url=f"https://exemple.invalid/{ref}",
        payload={},
        employer_ref=f"REF-{ref}",
        locations=[RawLocation(label="Paris", lat=lat, lon=lon, country_code="FR")],
        contract="permanent",
        contract_conf=1.0,
    )


async def _source(db_session) -> None:
    from sqlalchemy import text

    await db_session.execute(
        text(
            "INSERT INTO sources (slug, name, kind, legal_basis, active) "
            "VALUES (:s, 'Corpus de test', 'demo', 'test', true) "
            "ON CONFLICT (slug) DO NOTHING"
        ),
        {"s": SLUG},
    )
    await db_session.commit()


class TestAucuneOffreNestPerdue:
    async def test_une_offre_candidate_a_la_dedup_est_bien_ingeree(
        self, db_session
    ) -> None:
        """Deux intitulés proches chez deux employeurs : l'étage 2 se déclenche.

        Avant correction, la seconde offre remontait dans ``errors`` et
        n'existait nulle part. Le compte rendu d'ingestion était le seul
        endroit où ça se voyait — et il n'était lu par personne.
        """
        await _source(db_session)
        store = SqlAlchemyJobStore(db_session)

        rapport = await ingest_batch(
            SLUG,
            [
                _offre("s2-a", "Ingénieur DevOps", "Fictis Technologies", 48.8566, 2.3522),
                _offre(
                    "s2-b", "Ingénieur DevOps Senior", "Fictis Technologies", 48.86, 2.35
                ),
            ],
            store,
        )
        await db_session.commit()

        assert rapport.errors == 0, (
            "une offre a été perdue à l'ingestion — vérifier que "
            "stage2_candidates charge bien `locations` en amont"
        )
        assert rapport.seen == 2
        # Créée OU rattachée à la première : les deux sont des issues
        # légitimes de la dédup. Ce qui ne l'est pas, c'est de disparaître.
        assert rapport.created + rapport.attached_stage1 + rapport.attached_stage2 == 2

    async def test_le_filtre_geographique_sexecute_sans_lever(self, db_session) -> None:
        """Même titre, même employeur, 400 km d'écart : le filtre DOIT trancher.

        C'est le chemin qui levait. Qu'il conclue à la fusion ou non n'est pas
        le sujet ici — le sujet est qu'il s'exécute.
        """
        await _source(db_session)
        store = SqlAlchemyJobStore(db_session)

        rapport = await ingest_batch(
            SLUG,
            [
                _offre("geo-a", "Ingénieur DevOps", "Fictis Technologies", 48.8566, 2.3522),
                _offre("geo-b", "Ingénieur DevOps", "Fictis Technologies", 45.7640, 4.8357),
            ],
            store,
        )
        await db_session.commit()

        assert rapport.errors == 0
        assert rapport.seen == 2

"""Un code secteur hors référentiel ne doit pas faire perdre l'offre.

``job_postings.sector_code`` est une clé étrangère vers ``sectors.code``, et
le référentiel du MVP ne contient que les dix sections NACE d'``app/seeds.py``.
Le connecteur validait ``contract`` et ``remote``, mais laissait passer
``sector`` tel quel.

Conséquence mesurée en revue contre PostgreSQL : ``IntegrityError`` sur la
clé étrangère → annulation du savepoint de l'item → ``report.errors += 1``.
Une source publiant des codes NAF complets (``62.01Z`` au lieu de ``J``)
perdait **100 % de ses offres**, une par une, sans que rien d'autre qu'une
ligne ``ingestion_item_error`` ne le signale.

Le secteur pèse 4 % du score et le moteur sait renormaliser sur le connu :
l'écarter coûte cette dimension, le laisser passer coûte l'offre entière.

Ce test exige une vraie base : le magasin en mémoire des tests unitaires n'a
pas de clé étrangère, donc l'offre y survivait déjà.
"""

import pytest
from sqlalchemy import text

from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.service import SqlAlchemyJobStore, ingest_batch

pytestmark = pytest.mark.integration

SLUG = "demo-corpus"


def _offre(ref: str, secteur: str | None) -> RawJob:
    return RawJob(
        external_ref=ref,
        title="Ingénieur logiciel",
        company="Fictis Technologies",
        description="Poste d'ingénierie logicielle en Python à Paris.",
        url=f"https://exemple.invalid/{ref}",
        payload={},
        employer_ref=f"REF-{ref}",
        locations=[RawLocation(label="Paris", lat=48.8566, lon=2.3522, country_code="FR")],
        sector=secteur,
    )


async def _referentiel(db_session) -> None:
    """Les sections NACE d'``app/seeds.py`` — le contrôle les lit EN BASE."""
    for code, fr, en in (("J", "Information et communication", "ICT"),
                         ("M", "Activités scientifiques", "Professional")):
        await db_session.execute(
            text(
                "INSERT INTO sectors (code, label_fr, label_en) "
                "VALUES (:c, :fr, :en) ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "fr": fr, "en": en},
        )


async def _source(db_session) -> None:
    await _referentiel(db_session)
    await db_session.execute(
        text(
            "INSERT INTO sources (slug, name, kind, legal_basis, active) "
            "VALUES (:s, 'Corpus de test', 'demo', 'test', true) "
            "ON CONFLICT (slug) DO NOTHING"
        ),
        {"s": SLUG},
    )
    await db_session.commit()


class TestUnSecteurInconnuNeCouteQueLaDimension:
    async def test_un_code_naf_complet_ningere_plus_zero_offre(
        self, db_session
    ) -> None:
        await _source(db_session)
        store = SqlAlchemyJobStore(db_session)

        rapport = await ingest_batch(SLUG, [_offre("naf-1", "62.01Z")], store)
        await db_session.commit()

        assert rapport.errors == 0, (
            "l'offre a été perdue sur la clé étrangère sectors — le code hors "
            "référentiel doit être écarté à la normalisation"
        )
        assert rapport.created == 1
        secteur = (
            await db_session.execute(
                text(
                    "SELECT sector_code FROM job_postings "
                    "WHERE title = 'Ingénieur logiciel'"
                )
            )
        ).scalar_one()
        assert secteur is None

    async def test_un_code_du_referentiel_est_bien_ecrit(self, db_session) -> None:
        """La contrepartie : écarter l'inconnu ne doit pas écarter le connu."""
        await _source(db_session)
        store = SqlAlchemyJobStore(db_session)

        rapport = await ingest_batch(SLUG, [_offre("nace-1", "J")], store)
        await db_session.commit()

        assert rapport.errors == 0 and rapport.created == 1
        secteur = (
            await db_session.execute(
                text(
                    "SELECT sector_code FROM job_postings "
                    "WHERE title = 'Ingénieur logiciel'"
                )
            )
        ).scalar_one()
        assert secteur == "J"

    async def test_le_referentiel_lu_est_bien_celui_de_la_base(
        self, db_session
    ) -> None:
        """Le contrôle lit ``sectors``, il ne recopie pas la liste en dur.

        Sans ça, ajouter une section au référentiel ne suffirait pas : le
        pipeline continuerait de l'écarter, et le symptôme serait le même
        qu'avant — une dimension muette sans explication.
        """
        await db_session.execute(
            text(
                "INSERT INTO sectors (code, label_fr, label_en) "
                "VALUES ('Z', 'Section de test', 'Test section') "
                "ON CONFLICT (code) DO NOTHING"
            )
        )
        await _source(db_session)
        store = SqlAlchemyJobStore(db_session)

        rapport = await ingest_batch(SLUG, [_offre("z-1", "Z")], store)
        await db_session.commit()

        assert rapport.errors == 0
        secteur = (
            await db_session.execute(
                text(
                    "SELECT sector_code FROM job_postings "
                    "WHERE title = 'Ingénieur logiciel'"
                )
            )
        ).scalar_one()
        assert secteur == "Z"

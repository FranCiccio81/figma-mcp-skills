"""Mesure du coût des correctifs sur les chemins chauds.

Ce fichier ne vérifie pas une correction : il **mesure** ce que les
correctifs des lots 1 à 4 ont ajouté au produit, sur un PostgreSQL réel
peuplé. Trois d'entre eux touchent des chemins parcourus à chaque page :

- l'élargissement de contrat (lot 3) fait scorer jusqu'à 50 offres de plus
  par appel à ``GET /matches``, la requête la plus chaude du produit ;
- le plafond de corps (lot 2) est devenu un middleware ASGI qui s'interpose
  sur ``receive`` de CHAQUE requête, y compris celles sans corps ;
- l'égalisation des durées d'inscription (lot 2) ajoute un argon2 sur un
  chemin qui n'en faisait aucun.

Les seuils sont larges à dessein : ce sont des garde-fous contre une
régression d'un ordre de grandeur, pas des cibles de performance. Une machine
de CI chargée ne doit pas les faire tomber ; un ``N+1`` réintroduit, si.
"""

import statistics
import time
import uuid

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.matching.service as matching
from app.modules.auth.models import User
from app.modules.jobs.models import JobPosting
from tests.integration.factories import make_posting, populate_all_modules

pytestmark = pytest.mark.integration

#: Corpus de mesure. Au-delà du plafond de scoring (200) pour que le
#: pré-filtre travaille réellement, et réparti sur plusieurs contrats pour
#: que l'élargissement ait de quoi élargir.
OFFRES = 260

#: Répétitions par mesure — la médiane écarte le premier appel (cache froid).
REPETITIONS = 5


async def _corpus(session: AsyncSession) -> None:
    for index in range(OFFRES):
        # Un quart hors « permanent » : c'est ce que l'élargissement ajoute.
        contrat = "permanent" if index % 4 else "fixed_term"
        await make_posting(
            session,
            title=f"Développeur backend Python {index}",
            contract=contrat,
            commit=False,
        )
    await session.commit()


async def _mediane_ms(client: httpx.AsyncClient, url: str, **params: object) -> float:
    durees = []
    for _ in range(REPETITIONS):
        debut = time.perf_counter()
        reponse = await client.get(url, params=params)
        durees.append((time.perf_counter() - debut) * 1000)
        assert reponse.status_code == 200, reponse.text
    return statistics.median(durees)


class TestLeCheminLePlusChaudResteTenable:
    """``GET /jobs`` est appelé à chaque page de résultats."""

    async def test_la_recherche_reste_sous_le_seuil(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
        capsys: pytest.CaptureFixture,
    ) -> None:
        await _corpus(db_session)

        sans_filtre = await _mediane_ms(api_client, "/api/v1/jobs")
        avec_texte = await _mediane_ms(api_client, "/api/v1/jobs", q="python")
        page_deux = await _mediane_ms(api_client, "/api/v1/jobs", limit=20)

        with capsys.disabled():
            print(
                f"\n  GET /jobs           médiane {sans_filtre:6.1f} ms"
                f"\n  GET /jobs?q=python  médiane {avec_texte:6.1f} ms"
                f"\n  GET /jobs?limit=20  médiane {page_deux:6.1f} ms"
                f"    (corpus {OFFRES} offres)"
            )

        assert sans_filtre < 500, f"{sans_filtre:.0f} ms sur {OFFRES} offres"
        assert avec_texte < 500, f"{avec_texte:.0f} ms avec recherche plein texte"

    async def test_le_filtre_include_blocked_ne_coute_rien(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Le filtre ajouté au lot 3 est une condition SQL de plus. Elle ne
        doit pas changer l'ordre de grandeur."""
        await _corpus(db_session)

        avec = await _mediane_ms(api_client, "/api/v1/jobs", include_blocked="true")
        sans = await _mediane_ms(api_client, "/api/v1/jobs", include_blocked="false")

        with capsys.disabled():
            print(
                f"\n  include_blocked=true  {avec:6.1f} ms"
                f"\n  include_blocked=false {sans:6.1f} ms"
            )

        assert sans < max(avec * 3, 200), (
            f"le filtre triple le coût : {avec:.0f} ms → {sans:.0f} ms"
        )


class TestLeMiddlewareDeCorpsNeSePayePasSurChaqueRequete:
    """Devenu ASGI, il s'interpose sur ``receive`` de toutes les requêtes.

    Une requête SANS corps ne doit rien payer de mesurable : le compteur ne
    s'incrémente que sur les messages ``http.request``, et une sonde n'en
    produit qu'un, vide.
    """

    async def test_une_sonde_reste_immediate(
        self, api_client: httpx.AsyncClient, capsys: pytest.CaptureFixture
    ) -> None:
        durees = []
        for _ in range(20):
            debut = time.perf_counter()
            reponse = await api_client.get("/healthz")
            durees.append((time.perf_counter() - debut) * 1000)
            assert reponse.status_code == 200
        mediane = statistics.median(durees)

        with capsys.disabled():
            print(f"\n  GET /healthz          médiane {mediane:6.2f} ms")

        assert mediane < 25, f"{mediane:.1f} ms pour une sonde sans corps"


class TestLeScoringParesseuxSupporteLelargissement:
    """``GET /matches`` est la requête la plus chaude, et c'est celle que le
    lot 3 a alourdie : jusqu'à 50 offres de plus à scorer par appel.

    La mesure compare le MÊME corpus avec et sans élargissement, sur le même
    serveur, dans la même session. C'est le seul montage où l'écart mesuré
    est imputable au correctif et non à la machine.
    """

    async def test_le_cout_de_lelargissement_est_borne(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
        object_storage,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        await _corpus(db_session)
        utilisateur = (
            await db_session.execute(select(User).where(User.id == authenticated_user))
        ).scalar_one()
        premiere = (
            await db_session.execute(select(JobPosting).limit(1))
        ).scalar_one()
        await populate_all_modules(
            db_session, utilisateur, storage=object_storage, posting=premiere
        )
        await db_session.commit()

        # À FROID, et c'est le point. Premier essai : un appel de chauffe
        # puis deux médianes d'affilée — mesure inexploitable, +7 % sur une
        # exécution et +56 % sur la suivante, parce que la première
        # configuration mesurée remplit le cache dont la seconde profite.
        #
        # On vide donc ``match_results`` avant CHAQUE appel. C'est le pire
        # cas, et c'est celui qui dimensionne : première visite, et surtout
        # après un changement de préférences, qui invalide tout le cache
        # d'un utilisateur (RM-D-4).
        async def _froid() -> float:
            durees = []
            for _ in range(REPETITIONS):
                await db_session.execute(text("DELETE FROM match_results"))
                await db_session.commit()
                debut = time.perf_counter()
                reponse = await api_client.get("/api/v1/matches")
                durees.append((time.perf_counter() - debut) * 1000)
                assert reponse.status_code == 200, reponse.text
            return statistics.median(durees)

        avec = await _froid()
        monkeypatch.setattr(matching, "MAX_WIDENED_JOBS", 0)
        sans = await _froid()

        surcout = (avec - sans) / sans * 100 if sans else 0.0
        with capsys.disabled():
            print(
                f"\n  GET /matches À FROID sans élargissement  {sans:6.1f} ms"
                f"\n  GET /matches À FROID avec élargissement  {avec:6.1f} ms"
                f"   ({surcout:+.0f} %)"
                f"\n    corpus {OFFRES} offres, dont un quart hors préférences"
            )

        # Garde ABSOLUE. C'est elle qui aurait attrapé le défaut réel de ce
        # chemin : ``upsert_result`` validait la transaction À CHAQUE OFFRE,
        # soit 250 commits par page. Mesuré avant correctif, même corpus :
        #
        #     8 408 ms   →   700 ms après regroupement des commits
        #
        # Le seuil est à 2,5 s : trois fois la mesure, et trois fois moins que
        # le défaut. Une machine chargée ne le fait pas tomber ; un commit
        # remis dans la boucle, si.
        assert avec < 2500, (
            f"{avec:.0f} ms à froid — un chargement de page. Vérifier qu'aucun "
            "commit n'est reparti dans la boucle de scoring."
        )
        assert avec < max(sans * 2.5, 300), (
            f"l'élargissement plus que double le coût : {sans:.0f} → {avec:.0f} ms"
        )

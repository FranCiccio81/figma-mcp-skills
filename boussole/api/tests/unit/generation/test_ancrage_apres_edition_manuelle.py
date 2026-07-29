"""Une édition manuelle ne laisse jamais « Ancrage vérifié » à l'écran.

Défaut trouvé en revue finale, cousin direct de celui de l'annonce hostile
(``test_ancrage_offre_hostile.py``) : le produit affiche une garantie qu'il
ne détient plus.

``PATCH /generations/{id}`` remplace le contenu par ce que la personne a
écrit, puis appelle ``_lift_anchoring``, qui **conserve le verdict d'origine**
— ``status`` compris. Le composant ``AnchoringBadge`` documente pourtant
trois états, dont le troisième n'était jamais servi ::

    check === null   → « Contrôle non re-vérifié » (édition manuelle)
    status passed    → ✅ « Ancrage vérifié »   (vert)
    status failed    → ⚠ « Non ancré »          (rouge)

Reproduit avant correctif : génération saine (``passed``), puis édition
manuelle du corps en « Ancien CTO, expert Kubernetes chez Airbus » →
l'API sert toujours ``anchoring_check.status == "passed"`` et l'écran affiche
la coche verte sur un texte que personne n'a vérifié. C'est la même faute que
l'annonce hostile, par une autre porte : là un tiers désarmait le contrôle,
ici c'est l'édition — mais dans les deux cas l'utilisateur envoie à un
employeur un texte inventé avec un badge disant l'inverse.

**La correction est volontairement asymétrique**, et c'est le point de ce
fichier :

- un ``passed`` ne survit PAS à l'édition. C'est une affirmation sur le texte
  affiché ; dès que le texte change à la main, elle est sans objet ;
- un ``failed`` survit. C'est un avertissement, et il porte la liste des
  affirmations à corriger — précisément ce dont on a besoin PENDANT l'édition.
  Le retirer priverait la personne de sa liste de corrections au moment où
  elle s'en sert.

Trop avertir coûte une relecture ; trop rassurer publie une invention.

Dans les deux cas la base garde tout : ``pre_edit`` conserve le verdict
intégral, seule preuve que le contenu généré n'était pas ancré.
"""

import uuid
from typing import Any, ClassVar

from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeProvider
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.generation.conftest import (
    GENERATIONS_URL,
    InMemoryGenerationRepository,
    csrf_headers,
    run_generation,
    setup_validated_user,
)
from tests.unit.generation.test_generation_anchoring import start_generation
from tests.unit.profiles.conftest import InMemoryProfilesRepository

CORPS_INVENTE: dict[str, Any] = {
    "subject": "Candidature",
    "body": "Ancien CTO, expert Kubernetes, j'ai dirigé une équipe chez Airbus.",
}


class TestUnVerdictRassurantNeSurvitPasALedition:
    ORIGINAL: ClassVar[dict[str, Any]] = {
        "subject": "Candidature",
        "body": "Bonjour, voici ma candidature.",
    }
    VERDICT_SAIN: ClassVar[dict[str, Any]] = {
        "status": "passed",
        "unanchored_claims": [],
    }

    def _brouillon_ancre(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> uuid.UUID:
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {**self.ORIGINAL, "claims": []}
        document_id = start_generation(client, generation_repository)
        run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        document = generation_repository.docs[document_id]
        assert document.status == "draft"
        document.anchoring_check = dict(self.VERDICT_SAIN)
        return document_id

    def test_lapi_ne_sert_plus_de_verdict_apres_une_edition(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """LE test qui aurait attrapé le défaut."""
        document_id = self._brouillon_ancre(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        reponse = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": CORPS_INVENTE},
            headers=csrf_headers(client),
        )

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["anchoring_check"] is None, (
            "le badge vert « Ancrage vérifié » resterait affiché sur un texte "
            "écrit à la main et jamais contrôlé"
        )
        assert corps["manually_edited"] is True
        assert corps["anchoring_note"], "la responsabilité doit être dite"

    def test_la_relecture_ulterieure_ne_le_ressert_pas_non_plus(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """C'est ``GET`` que l'écran appelle au rechargement, pas la réponse
        du ``PATCH``. Corriger l'un sans l'autre ne corrigerait rien."""
        document_id = self._brouillon_ancre(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": CORPS_INVENTE},
            headers=csrf_headers(client),
        )

        assert client.get(f"{GENERATIONS_URL}/{document_id}").json()["anchoring_check"] is None

    def test_la_liste_le_montre_aussi(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """« Mes documents » affiche le même badge : troisième chemin."""
        document_id = self._brouillon_ancre(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": CORPS_INVENTE},
            headers=csrf_headers(client),
        )

        items = client.get(GENERATIONS_URL).json()["items"]
        (document,) = [item for item in items if item["id"] == str(document_id)]
        assert document["anchoring_check"] is None

    def test_un_patch_sans_changement_conserve_le_verdict(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """Relire n'est pas éditer : le contrôle porte toujours sur ce texte,
        donc le verdict reste valable et doit rester affiché."""
        document_id = self._brouillon_ancre(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        actuel = client.get(f"{GENERATIONS_URL}/{document_id}").json()["content"]

        corps = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": actuel},
            headers=csrf_headers(client),
        ).json()

        assert corps["manually_edited"] is False
        assert corps["anchoring_check"] == self.VERDICT_SAIN

    def test_la_base_garde_la_preuve(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """Ne pas SERVIR le verdict n'est pas l'EFFACER. L'API se tait sur un
        contrôle devenu sans objet ; la trace d'audit, elle, reste entière."""
        document_id = self._brouillon_ancre(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": CORPS_INVENTE},
            headers=csrf_headers(client),
        )

        stocke = generation_repository.docs[document_id].anchoring_check
        assert stocke is not None
        assert stocke["lifted_by_manual_edit"] is True
        assert stocke["pre_edit"] == self.VERDICT_SAIN


class TestUnAvertissementSurvitALedition:
    """L'autre moitié de la règle. Retirer un ``failed`` priverait la personne
    de sa liste de corrections au moment précis où elle édite pour les
    corriger."""

    VERDICT_NEGATIF: ClassVar[dict[str, Any]] = {
        "status": "failed",
        "unanchored_claims": ["expert Kubernetes (profile_ref inconnu : skill:xxx)"],
    }

    def test_le_verdict_negatif_et_sa_liste_restent_affiches(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature",
            "body": "Bonjour, voici ma candidature.",
            "claims": [],
        }
        document_id = start_generation(client, generation_repository)
        run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        generation_repository.docs[document_id].anchoring_check = dict(
            self.VERDICT_NEGATIF
        )

        corps = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": {"subject": "Candidature", "body": "Texte repris."}},
            headers=csrf_headers(client),
        ).json()

        assert corps["manually_edited"] is True
        assert corps["anchoring_check"]["status"] == "failed"
        assert corps["anchoring_check"]["unanchored_claims"] == (
            self.VERDICT_NEGATIF["unanchored_claims"]
        )

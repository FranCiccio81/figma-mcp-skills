"""Trois finitions, trois promesses que le produit faisait sans les tenir.

Chacune était visible pour l'utilisateur et invisible pour la suite de tests,
pour la même raison : la doublure de test disait la même chose que le code.
Quand le fake répond ce que le code répond en dur, aucun test ne peut voir
que le code ne regarde rien.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository


def _inscrire(client: TestClient, email: str = "camille@example.eu") -> uuid.UUID:
    reponse = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "un mot de passe très long",
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )
    assert reponse.status_code == 201
    return uuid.UUID(client.get("/api/v1/me").json()["id"])


class TestLOnboardingDitLaVerite:
    """Les trois indicateurs étaient des littéraux ``False``.

    Commentaire d'origine : « M1 : les indicateurs sont False tant que les
    modules profiles/preferences (M2+) ne fournissent pas leurs services ».
    Ils les fournissent depuis quatre jalons.

    Effet visible : la carte « Mon CV » du tableau de bord affichait à vie
    « Aucun CV importé pour le moment. Importez-le pour pré-remplir votre
    profil. » et proposait « Importer mon CV » plutôt que « Réimporter un
    CV » — quel que soit le nombre de CV réellement importés. Le composant
    précise pourtant qu'il lit ``GET /me``, « jamais d'état local seul » : la
    source de vérité choisie était justement celle qui mentait.
    """

    def test_un_compte_neuf_na_rien_fait(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        assert client.get("/api/v1/me").json()["onboarding"] == {
            "cv_imported": False,
            "profile_validated": False,
            "preferences_set": False,
        }

    @pytest.mark.parametrize(
        "etat,attendu",
        [
            ((True, False, False), {"cv_imported": True, "profile_validated": False,
                                    "preferences_set": False}),
            ((True, True, False), {"cv_imported": True, "profile_validated": True,
                                   "preferences_set": False}),
            ((True, True, True), {"cv_imported": True, "profile_validated": True,
                                  "preferences_set": True}),
        ],
    )
    def test_chaque_etape_franchie_se_voit(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        etat: tuple[bool, bool, bool],
        attendu: dict[str, bool],
    ) -> None:
        user_id = _inscrire(client)
        auth_repository.onboarding[user_id] = etat

        assert client.get("/api/v1/me").json()["onboarding"] == attendu

    def test_letat_est_bien_celui_de_lutilisateur_connecte(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        """Un indicateur qui fuit d'un compte à l'autre serait pire que faux."""
        autre = uuid.uuid4()
        auth_repository.onboarding[autre] = (True, True, True)
        _inscrire(client)

        assert client.get("/api/v1/me").json()["onboarding"] == {
            "cv_imported": False,
            "profile_validated": False,
            "preferences_set": False,
        }


class TestLesSeuilsDexplicationSontServisParLAPI:
    """Le front les recopiait : trois constantes en dur, dupliquées de
    ``scoring-config.json``.

    Elles coïncidaient — jusqu'à la première recalibration, après quoi l'écran
    aurait classé forces et lacunes selon d'anciennes valeurs, sans que rien
    ne le signale. Une valeur qui décide de ce que l'utilisateur LIT doit
    venir de l'endroit qui la définit.
    """

    def test_les_seuils_viennent_de_la_configuration(self) -> None:
        from app.matching import get_config
        from app.modules.matching.schemas import ExplanationThresholdsOut

        cfg = get_config()
        seuils = ExplanationThresholdsOut(
            strength_min_subscore=cfg.explanation.strength_min_subscore,
            strength_min_weight=cfg.explanation.strength_min_weight,
            gap_max_subscore=cfg.explanation.gap_max_subscore,
        )
        assert seuils.strength_min_subscore == cfg.explanation.strength_min_subscore
        assert seuils.strength_min_weight == cfg.explanation.strength_min_weight
        assert seuils.gap_max_subscore == cfg.explanation.gap_max_subscore

    def test_le_champ_est_obligatoire_dans_la_reponse(self) -> None:
        """Optionnel, il aurait laissé le front garder ses constantes en repli
        — donc le défaut intact pour qui ne lit pas la note."""
        from app.modules.matching.schemas import MatchResultOut

        assert MatchResultOut.model_fields["explanation_thresholds"].is_required()


class TestLeQuotaDexplicationExiste:
    """Cette route n'en avait AUCUN.

    Vérifié en revue : huit appels consécutifs sur huit offres différentes
    (donc hors cache), zéro 429. Un utilisateur qui parcourt deux cents offres
    déclenchait deux cents appels LLM non plafonnés — un coût direct, et une
    porte ouverte pour qui veut le faire exprès. Le front porte pourtant
    depuis toujours une branche 429 dédiée (« Limite de générations atteinte,
    10 par heure, 40 par jour ») qui ne pouvait jamais s'afficher.
    """

    def test_les_quotas_sont_ceux_du_contrat(self) -> None:
        from app.modules.explanations.service import QUOTA_PER_DAY, QUOTA_PER_HOUR

        assert (QUOTA_PER_HOUR, QUOTA_PER_DAY) == (10, 40)

    def test_les_compteurs_sont_separes_de_ceux_de_la_generation(self) -> None:
        """Expliquer un score ne doit pas empêcher d'écrire une lettre : ce
        sont deux fonctions distinctes, un utilisateur ne comprendrait pas."""
        import inspect

        from app.modules.explanations import service as explications
        from app.modules.generation import service as generation

        source_expl = inspect.getsource(explications.ExplanationsService._enforce_quotas)
        source_gen = inspect.getsource(generation.GenerationService._enforce_quotas)
        assert "explanations:hour" in source_expl
        assert "generations:hour" in source_gen
        assert "generations:" not in source_expl

    async def test_le_quota_est_preleve_apres_le_cache(self) -> None:
        """Une explication déjà calculée ne coûte aucun appel au fournisseur.
        Lui faire consommer un jeton punirait qui relit une offre."""
        import inspect

        from app.modules.explanations.service import ExplanationsService

        source = inspect.getsource(ExplanationsService.explain)
        position_cache = source.index("if cached is not None")
        position_quota = source.index("_enforce_quotas")
        assert position_cache < position_quota, (
            "le quota est prélevé AVANT la lecture du cache : relire une offre "
            "déjà expliquée consommerait un jeton pour rien"
        )

    async def test_un_redis_injoignable_ne_suspend_pas_la_fonction(self) -> None:
        """Fail-open, comme le limiteur global (D18) : un quota indisponible
        ne doit pas suspendre une fonction du produit."""
        from app.modules.explanations.service import ExplanationsService

        class RedisMort:
            async def incr(self, *_a: object, **_k: object) -> int:
                raise ConnectionError("Redis injoignable")

        service = ExplanationsService.__new__(ExplanationsService)
        service._cache = RedisMort()  # type: ignore[attr-defined]

        # Ne lève pas : l'appelant poursuit vers la génération.
        await service._enforce_quotas(uuid.uuid4())

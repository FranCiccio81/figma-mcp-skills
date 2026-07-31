"""Une panne du Redis volatile dégrade le service, sans le couper ni se taire.

Défaut trouvé en revue avant déploiement. D17 pose que la perte du Redis
« cache » est acceptable : il ne porte que du cache, du rate limiting et des
quotas. Quatre points d'appel en tiraient trois conclusions différentes,
chacune défendable seule ::

    limiteur global (D18)   laisse passer, logger.warning
    limiteur de connexion   laisse passer, logger.warning
    quota d'explications    laisse passer, logger.warning
    quota de génération     AUCUNE garde → 500 sur chaque appel

Et une cinquième décision les annulait toutes : ``/readyz`` comptait
``redis_cache`` parmi ses dépendances obligatoires. Sous un orchestrateur,
une readiness en échec retire l'instance du service — sur toutes les
instances à la fois. Une panne de cache ne dégradait donc pas le service,
**elle le coupait**, ce qui est exactement la panne totale que le fail-open
du limiteur de connexion existe pour éviter. Son commentaire dit « une panne
de cache ne doit pas devenir une panne d'authentification » ; la sonde en
faisait une panne de tout.

Deuxième moitié du défaut : chaque garde journalisait en ``WARNING``, et
l'export d'erreurs ne crée d'événement qu'à partir de ``ERROR``. Le système
pouvait tourner des heures **sans aucune limitation de débit**, sans que
personne ne l'apprenne.
"""

import asyncio
import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.degradation import (
    INTERVALLE_SECONDES,
    reset_degradations,
    signal_degradation,
)
from app.core.problems import Problem
from app.main import DEPENDANCES_VITALES, readiness_verdict
from app.modules.generation.service import GenerationService


@pytest.fixture(autouse=True)
def _etat_propre() -> None:
    reset_degradations()


def _ecouter(nom: str) -> list[str]:
    """Capte les messages d'un logger précis, en renvoyant la liste vivante.

    ``caplog`` pose son gestionnaire sur la racine ; ``create_app`` appelle
    ``configure_logging``, qui remplace ``root.handlers``. Écouter le logger
    visé est la seule capture qui survive à la construction de l'application.
    """
    lignes: list[str] = []

    class _Collecteur(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lignes.append(record.getMessage())

    logger = logging.getLogger(nom)
    logger.addHandler(_Collecteur())
    logger.setLevel(logging.ERROR)
    return lignes


class TestUneProtectionQuiSeffaceEstSignalee:
    def test_le_niveau_est_error_donc_remonte(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``WARNING`` ne crée aucun événement d'erreur (``event_level=ERROR``
        dans ``configure_observability``). Une protection désactivée qui ne
        réveille personne n'est pas une dégradation, c'est un angle mort."""
        with caplog.at_level(logging.WARNING):
            assert signal_degradation("rate_limit_global", detail="/api/v1/jobs") is True

        (ligne,) = [r for r in caplog.records if "degradation_active" in r.getMessage()]
        assert ligne.levelno == logging.ERROR

    def test_le_nom_de_la_protection_est_dans_le_message(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR):
            signal_degradation("rate_limit_login")
        assert "rate_limit_login" in caplog.text

    def test_une_rafale_ne_produit_quune_alerte(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Pendant une panne, une alerte est un signal ; mille sont un déni
        de service contre l'exploitant — et la vraie information se perd."""
        with caplog.at_level(logging.ERROR):
            emis = [signal_degradation("rate_limit_global") for _ in range(500)]

        assert emis[0] is True
        assert sum(emis) == 1, f"{sum(emis)} alertes émises pour une seule panne"

    def test_deux_protections_distinctes_sont_signalees_separement(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Étouffer par nom et non globalement : savoir QUE le rate limiting
        est tombé ne dit pas que les quotas le sont aussi."""
        with caplog.at_level(logging.ERROR):
            assert signal_degradation("rate_limit_global") is True
            assert signal_degradation("quota_generation") is True

    def test_letouffement_est_borne_dans_le_temps(self) -> None:
        """Une panne qui dure doit continuer de se signaler : sans quoi une
        alerte résolue automatiquement passerait pour un incident terminé."""
        assert INTERVALLE_SECONDES <= 300, (
            "un intervalle trop long ferait passer une panne longue pour un "
            "incident isolé"
        )


class _RedisEnPanne:
    """Client Redis qui refuse toute connexion — la panne, pas sa doublure."""

    async def ping(self) -> bool:
        raise ConnectionError("injoignable")

    async def aclose(self) -> None:
        return None

    def __getattr__(self, _nom: str):
        async def echoue(*_a: object, **_k: object) -> None:
            raise ConnectionError("injoignable")

        return echoue


def _client_avec(*, cache_en_panne: bool = False, persistant_en_panne: bool = False):
    """Application réelle, dont un Redis est injoignable.

    On remplace la FABRIQUE et non un client déjà construit : c'est ainsi que
    l'application obtient ses connexions, et c'est le seul montage où
    ``/readyz`` exerce vraiment son chemin d'erreur.
    """
    import fakeredis.aioredis

    from app.main import create_app

    serveur_ok = fakeredis.FakeServer()

    def cache():
        if cache_en_panne:
            return _RedisEnPanne()
        return fakeredis.aioredis.FakeRedis(server=serveur_ok, decode_responses=True)

    def persistant():
        if persistant_en_panne:
            return _RedisEnPanne()
        return fakeredis.aioredis.FakeRedis(server=serveur_ok, decode_responses=True)

    application = create_app(
        redis_cache_factory=cache, redis_persistent_factory=persistant
    )
    return TestClient(application, base_url="https://testserver")


TOUT_VA_BIEN = {
    "database": True,
    "redis_persistent": True,
    "storage": True,
    "redis_cache": True,
}


class TestReadyzNeCoupePasLeServicePourUnCache:
    """La règle « ce qui coupe le service » est trop conséquente pour n'être
    vérifiable qu'à travers un serveur HTTP muni d'une vraie base."""

    def test_un_cache_injoignable_laisse_linstance_en_service(self) -> None:
        """LE test qui aurait attrapé le défaut."""
        pret, statut, manquantes = readiness_verdict(
            {**TOUT_VA_BIEN, "redis_cache": False}
        )

        assert pret is True, (
            "l'instance serait retirée du service par l'orchestrateur : une "
            "dégradation deviendrait une panne totale, sur toutes les "
            "instances à la fois"
        )
        assert statut == "degraded", "rester en service ne veut pas dire se taire"
        assert manquantes == []

    @pytest.mark.parametrize("vitale", ["database", "redis_persistent", "storage"])
    def test_une_dependance_reellement_vitale_coupe_toujours(
        self, vitale: str
    ) -> None:
        """La contrepartie : le Redis PERSISTANT porte les sessions et le
        broker, la base porte tout. Un readyz qui ne coupe jamais ne sert à
        rien."""
        pret, statut, manquantes = readiness_verdict({**TOUT_VA_BIEN, vitale: False})

        assert pret is False
        assert statut == "not_ready"
        assert manquantes == [vitale]

    def test_le_cache_nest_pas_dans_les_dependances_vitales(self) -> None:
        assert "redis_cache" not in DEPENDANCES_VITALES

    def test_tout_va_bien_reste_le_cas_normal(self) -> None:
        assert readiness_verdict(TOUT_VA_BIEN) == (True, "ready", [])

    def test_une_dependance_absente_du_relevé_compte_comme_en_panne(self) -> None:
        """Prudence : une sonde qui n'a pas répondu n'est pas une sonde qui
        dit « tout va bien »."""
        pret, _statut, manquantes = readiness_verdict({})
        assert pret is False and set(manquantes) == set(DEPENDANCES_VITALES)


class TestLaRouteAppliqueBienCeVerdict:
    """Le montage complet : une règle correcte mal branchée ne sert à rien."""

    def test_un_cache_en_panne_rend_200_degraded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.main as main

        async def base_ok() -> bool:
            return True

        monkeypatch.setattr(main, "check_database", base_ok)

        client = _client_avec(cache_en_panne=True)
        # ``create_app`` appelle ``configure_logging``, qui remplace les
        # gestionnaires de la racine — donc ceux de ``caplog``. On écoute le
        # logger concerné, après construction de l'application.
        lignes = _ecouter("boussole.degradation")

        reponse = client.get("/readyz")

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["status"] == "degraded"
        assert corps["checks"]["redis_cache"] is False
        assert any("redis_cache" in ligne for ligne in lignes), (
            "l'exploitant n'apprend pas que la limitation de débit et les "
            "quotas sont inactifs"
        )

    def test_un_redis_persistant_en_panne_rend_503(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.main as main

        async def base_ok() -> bool:
            return True

        monkeypatch.setattr(main, "check_database", base_ok)

        reponse = _client_avec(persistant_en_panne=True).get("/readyz")

        assert reponse.status_code == 503
        assert "redis_persistent" in reponse.json()["detail"]


class TestLeQuotaDeGenerationEchoueFerme:
    """La seule garde qui ne laisse PAS passer, et c'est délibéré.

    Les trois autres protègent la disponibilité : une panne de cache ne doit
    pas devenir une panne de service. Celle-ci protège une **dépense réelle**
    chez un fournisseur de LLM — laisser passer, c'est supprimer le plafond
    de coût pendant toute la durée de la panne, sans que personne ne l'ait
    décidé.

    Elle échouait déjà fermé, mais par accident : aucune garde, donc un 500
    sans explication. Le refus est maintenant explicite.
    """

    def test_un_cache_en_panne_rend_503_et_non_500(self) -> None:
        service = GenerationService.__new__(GenerationService)
        service._cache = _RedisEnPanne()  # type: ignore[attr-defined]

        with pytest.raises(Problem) as capture:
            asyncio.run(service._enforce_quotas(uuid.uuid4()))

        probleme = capture.value
        assert probleme.status == 503, "un 500 ne dit rien à l'utilisateur"
        assert probleme.code == "quota_unavailable"
        assert probleme.headers and "Retry-After" in probleme.headers

    def test_la_degradation_est_signalee(self) -> None:
        lignes = _ecouter("boussole.degradation")
        service = GenerationService.__new__(GenerationService)
        service._cache = _RedisEnPanne()  # type: ignore[attr-defined]

        with pytest.raises(Problem):
            asyncio.run(service._enforce_quotas(uuid.uuid4()))

        assert any("quota_generation" in ligne for ligne in lignes)

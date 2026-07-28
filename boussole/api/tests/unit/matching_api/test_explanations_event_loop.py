"""C1 — le provider réel ne doit pas geler la boucle asyncio de l'API.

``ExplanationsService._generate`` est SYNCHRONE (l'interface ``LLMProvider``
l'est, D08) et était appelée directement depuis ``async def explain()``. Pour
la durée entière de l'appel — 3,52 s mesurées avec un transport instantané,
jusqu'à ~190 s avec un vrai réseau (2 tentatives × retries provider ×
backoff) — le worker uvicorn ne servait **plus aucune requête** : ni les
autres utilisateurs, ni ``/healthz``, ni ``/readyz``.

Deux angles, dont un totalement déterministe :

1. l'appel bloquant a lieu dans un AUTRE thread que celui de la boucle
   (structurel, aucune mesure de temps) ;
2. la boucle continue effectivement de tourner pendant le blocage (mesure de
   l'écart maximal entre deux battements, avec une marge ×2).
"""

import asyncio
import threading
import time
import uuid
from typing import Any, ClassVar

from app.ai.calls import AI_TASKS
from app.modules.explanations.service import (
    FAKE_EXPLANATION,
    TASK,
    ExplanationsService,
)

#: Durée du blocage simulé du provider. Assez longue pour qu'un gel de boucle
#: soit indiscutable, assez courte pour ne pas ralentir la suite.
BLOCAGE_SECONDES = 0.6


class _BlockingProvider:
    """Provider synchrone qui BLOQUE son thread, comme le vrai."""

    def __init__(self, hold: threading.Event) -> None:
        self.hold = hold
        self.thread_names: list[str] = []
        self.tasks: ClassVar[list[str]] = []

    def complete_json(self, task: str, prompt: str, schema: Any) -> dict[str, Any]:
        self.thread_names.append(threading.current_thread().name)
        self.tasks.append(task)
        assert self.hold.wait(timeout=10), "le provider n'a jamais été libéré"
        return dict(FAKE_EXPLANATION)


class _Match:
    profile_id = uuid.uuid4()
    job_id = uuid.uuid4()
    scoring_version = "1.0.0"
    explanation_facts: ClassVar[dict[str, Any]] = {"blocking": [], "strengths": []}


class _Matching:
    async def get_match_data(self, user_id: uuid.UUID, job_id: uuid.UUID) -> _Match:
        return _Match()


class _Repository:
    def __init__(self) -> None:
        self.stored: Any = None

    async def get(self, *args: object) -> None:
        return None

    async def put(self, *args: object) -> None:
        self.stored = args[-1]


def _service(provider: _BlockingProvider) -> ExplanationsService:
    return ExplanationsService(_Matching(), _Repository(), provider)  # type: ignore[arg-type]


class TestBoucleAsyncioNonGelee:
    async def test_l_appel_bloquant_a_lieu_hors_du_thread_de_la_boucle(self) -> None:
        """Contrôle structurel, sans mesure de temps : c'est LE correctif."""
        hold = threading.Event()
        hold.set()  # aucun blocage : seul le thread nous intéresse
        provider = _BlockingProvider(hold)

        boucle = threading.current_thread().name
        await _service(provider).explain(uuid.uuid4(), uuid.uuid4())

        (thread_provider,) = provider.thread_names
        assert thread_provider != boucle, (
            "le provider synchrone tourne dans le thread de la boucle asyncio : "
            "tout le worker uvicorn est gelé pour la durée de l'appel"
        )

    async def test_la_boucle_continue_de_battre_pendant_l_appel(self) -> None:
        hold = threading.Event()
        threading.Timer(BLOCAGE_SECONDES, hold.set).start()
        provider = _BlockingProvider(hold)

        ecarts: list[float] = []
        dernier = time.monotonic()

        async def battement() -> None:
            nonlocal dernier
            while True:
                await asyncio.sleep(0.01)
                maintenant = time.monotonic()
                ecarts.append(maintenant - dernier)
                dernier = maintenant

        pouls = asyncio.create_task(battement())
        try:
            await _service(provider).explain(uuid.uuid4(), uuid.uuid4())
        finally:
            pouls.cancel()

        assert ecarts, "le battement n'a jamais tourné"
        # Marge ×2 : un gel réel dure BLOCAGE_SECONDES entières.
        assert max(ecarts) < BLOCAGE_SECONDES / 2, (
            f"boucle gelée {max(ecarts):.2f} s pendant l'appel provider "
            f"(blocage simulé : {BLOCAGE_SECONDES} s)"
        )

    async def test_le_resultat_et_le_nom_de_tache_sont_preserves(self) -> None:
        hold = threading.Event()
        hold.set()
        provider = _BlockingProvider(hold)

        resultat = await _service(provider).explain(uuid.uuid4(), uuid.uuid4())

        assert resultat.summary
        # M6 : le nom passé au provider est celui de l'enum SQL `ai_task`.
        assert provider.tasks[-1] == TASK == "explain_match"
        assert TASK in AI_TASKS

"""Journal ``ai_calls`` : champs, statuts, absence totale de contenu.

La revue a trouvé une fuite de sortie LLM dans les journaux applicatifs.
Ici, l'absence de contenu est STRUCTURELLE (la structure de journal n'a
aucun champ de contenu) et vérifiée explicitement.
"""

import asyncio
import uuid
from unittest import mock

import pytest
from starlette.concurrency import run_in_threadpool

from app.ai.calls import (
    AI_TASKS,
    CALL_STATUSES,
    ERROR_CODES,
    UNKNOWN_PROMPT_VERSION,
    AiCall,
    AiCallRecord,
    DatabaseJournal,
    NullJournal,
    ai_user_context,
    current_ai_user,
    drain_pending_writes,
    persist_ai_call,
    prompt_version_for,
)


def a_record(**overrides: object) -> AiCallRecord:
    base: dict[str, object] = {
        "task": "extract_cv",
        "prompt_version": "extract_cv/1.0.0",
        "model": "claude-sonnet-5",
        "status": "success",
    }
    base.update(overrides)
    return AiCallRecord(**base)  # type: ignore[arg-type]


class TestStructureDuJournal:
    def test_la_ligne_ne_peut_porter_aucun_contenu(self) -> None:
        champs = set(AiCallRecord.__dataclass_fields__)

        assert champs == {
            "task", "prompt_version", "model", "status", "user_id",
            "input_tokens", "output_tokens", "latency_ms", "error_code",
        }
        # 11 §3 : aucun champ de prompt / réponse / extrait, par construction.
        for interdit in ("prompt", "response", "content", "text", "detail", "payload"):
            assert interdit not in champs

    def test_le_modele_sqlalchemy_est_conforme_a_initial_schema(self) -> None:
        colonnes = {c.name for c in AiCall.__table__.columns}

        assert colonnes == {
            "id", "task", "prompt_version", "model", "user_id",
            "input_tokens", "output_tokens", "latency_ms", "status",
            "error_code", "created_at",
        }
        assert AiCall.__table__.c.user_id.nullable is True  # anonymisation
        assert AiCall.__table__.c.task.nullable is False
        assert AiCall.__table__.c.status.nullable is False

    @pytest.mark.parametrize("status", CALL_STATUSES)
    def test_les_trois_statuts_du_schema_sont_acceptes(self, status: str) -> None:
        assert a_record(status=status).status == status

    def test_un_statut_hors_vocabulaire_est_refuse(self) -> None:
        with pytest.raises(ValueError, match="statut"):
            a_record(status="peut-etre")

    @pytest.mark.parametrize("code", ERROR_CODES)
    def test_les_codes_d_erreur_sont_un_vocabulaire_ferme(self, code: str) -> None:
        assert a_record(status="failed", error_code=code).error_code == code

    def test_un_code_d_erreur_libre_est_refuse(self) -> None:
        # Empêche qu'un message d'erreur (donc potentiellement du contenu)
        # se retrouve journalisé à la place d'un code.
        with pytest.raises(ValueError, match="code d'erreur"):
            a_record(status="failed", error_code="Ada Lovelace n'a pas de diplôme")

    @pytest.mark.parametrize("task", AI_TASKS)
    def test_les_taches_de_l_enum_sont_acceptees(self, task: str) -> None:
        assert a_record(task=task).task == task

    def test_une_tache_hors_enum_est_refusee(self) -> None:
        """M6 : ``task`` est l'enum SQL ``ai_task``. Une valeur inconnue ne
        pouvait être détectée qu'au COMMIT — dans ``persist_ai_call``, qui
        avale toute erreur : la ligne disparaissait sans le moindre signal.
        C'est ainsi que ``match_explanation`` a coûté 100 % du journal des
        explications (et, côté provider, le mauvais modèle et un timeout ×7,5).
        """
        with pytest.raises(ValueError, match="tâche"):
            a_record(task="match_explanation")

        with pytest.raises(ValueError, match="tâche"):
            a_record(task="generate")

    def test_le_nom_de_tache_du_service_explanations_est_dans_l_enum(self) -> None:
        from app.modules.explanations.service import TASK

        # Le point d'appel réel, pas seulement une constante isolée.
        assert TASK in AI_TASKS
        assert a_record(task=TASK).task == "explain_match"

    def test_les_taches_couvrent_l_enum_sql(self) -> None:
        assert AI_TASKS == (
            "extract_cv", "extract_job", "explain_match", "generate_email",
            "generate_letter", "tailor_cv", "optimize_cv",
        )


class TestVersionDePrompt:
    @pytest.mark.parametrize(
        ("task", "expected"),
        [
            ("extract_cv", "extract_cv/1.0.0"),
            ("extract_job", "extract_job/1.0.0"),
            ("explain_match", "match_explanation/1.0.0"),
            ("generate_email", "generate_email/1.0.0"),
            ("generate_letter", "generate_letter/1.0.0"),
            ("tailor_cv", "tailor_cv/1.0.0"),
            ("optimize_cv", "optimize_cv/1.0.0"),
        ],
    )
    def test_elle_est_lue_depuis_la_tache_sans_duplication(
        self, task: str, expected: str
    ) -> None:
        assert prompt_version_for(task) == expected

    def test_une_tache_inconnue_ne_casse_pas_l_appel(self) -> None:
        assert prompt_version_for("tache_fantome") == UNKNOWN_PROMPT_VERSION


class TestContexteUtilisateur:
    def test_l_utilisateur_courant_est_nul_par_defaut(self) -> None:
        assert current_ai_user() is None

    def test_le_contexte_attache_puis_detache_l_utilisateur(self) -> None:
        user_id = uuid.uuid4()

        with ai_user_context(user_id):
            assert current_ai_user() == user_id
        assert current_ai_user() is None


class TestEcritureNonBloquante:
    async def test_une_base_injoignable_ne_fait_jamais_echouer_l_appel(self) -> None:
        class ExplodingFactory:
            def __call__(self) -> object:
                raise RuntimeError("base injoignable")

        # Aucune exception ne doit sortir : le journal est une dette
        # d'observabilité, pas une dépendance dure de l'appel IA (D18).
        await persist_ai_call(a_record(), ExplodingFactory())  # type: ignore[arg-type]

    async def test_le_journal_de_base_planifie_l_ecriture_sans_bloquer(self) -> None:
        ecrits: list[AiCallRecord] = []

        async def _fake_write(record: AiCallRecord) -> None:
            ecrits.append(record)

        journal = DatabaseJournal(scheduler=lambda coro: asyncio.ensure_future(coro))
        # On court-circuite la coroutine réelle : ce qui est testé ici est la
        # planification (appelée depuis un contexte SYNCHRONE).
        record = a_record()
        journal._scheduler(_fake_write(record))
        await drain_pending_writes()
        await asyncio.sleep(0)

        assert ecrits == [record]

    def test_le_journal_inerte_ne_leve_jamais(self) -> None:
        assert NullJournal().record(a_record()) is None


class TestEcritureDepuisUnWorkerCelery:
    """M7 — les lignes ``ai_calls`` des workers étaient TOUTES perdues.

    Les tâches Celery exécutent leur cycle via ``asyncio.run`` et appellent le
    provider SYNCHRONEMENT depuis cette coroutine. L'ordonnanceur faisait
    ``loop.create_task(...)`` : la boucle se refermait avant l'exécution, la
    tâche était annulée, et l'annulation avalée. Vérifié sur PostgreSQL réel :
    table vide pour ``extract_cv``, ``extract_job`` et toutes les
    ``generate_*``.
    """

    def test_l_ecriture_aboutit_depuis_une_coroutine_asyncio_run(self) -> None:
        ecrits: list[AiCallRecord] = []

        async def _write(record: AiCallRecord, factory: object = None) -> None:
            # Un point de suspension : la coroutine a besoin d'un tour de
            # boucle, exactement comme une écriture SQL réelle.
            await asyncio.sleep(0)
            ecrits.append(record)

        record = a_record()

        async def _celery_like_cycle() -> None:
            # Appel SYNCHRONE du provider depuis la coroutine de la tâche.
            DatabaseJournal().record(record)

        # Reproduit `_run(...)` des workers (cv_tasks, generation_tasks…).
        with mock.patch("app.ai.calls.persist_ai_call", _write):
            asyncio.run(_celery_like_cycle())

        assert ecrits == [record], "la ligne ai_calls a été perdue à la fermeture de la boucle"

    def test_l_ecriture_aboutit_hors_de_toute_boucle(self) -> None:
        ecrits: list[AiCallRecord] = []

        async def _write(record: AiCallRecord, factory: object = None) -> None:
            await asyncio.sleep(0)
            ecrits.append(record)

        record = a_record()
        with mock.patch("app.ai.calls.persist_ai_call", _write):
            DatabaseJournal().record(record)  # contexte purement synchrone

        assert ecrits == [record]

    async def test_l_ecriture_aboutit_depuis_un_thread_de_threadpool(self) -> None:
        # Chemin de l'API après C1 : le provider tourne dans un thread du
        # threadpool Starlette, où aucune boucle ne tourne.
        ecrits: list[AiCallRecord] = []

        async def _write(record: AiCallRecord, factory: object = None) -> None:
            await asyncio.sleep(0)
            ecrits.append(record)

        record = a_record()
        with mock.patch("app.ai.calls.persist_ai_call", _write):
            await run_in_threadpool(DatabaseJournal().record, record)

        assert ecrits == [record]

    def test_une_ecriture_en_echec_ne_remonte_jamais_a_l_appelant(self) -> None:
        async def _boom(record: AiCallRecord, factory: object = None) -> None:
            raise RuntimeError("base injoignable")

        async def _celery_like_cycle() -> None:
            DatabaseJournal().record(a_record())

        with mock.patch("app.ai.calls.persist_ai_call", _boom):
            asyncio.run(_celery_like_cycle())  # aucune exception ne sort

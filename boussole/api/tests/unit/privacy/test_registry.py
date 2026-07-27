"""Tests du registre déclaratif (D21) — contrôle d'exhaustivité.

Deux niveaux, complémentaires :

1. **déclaration** : la liste attendue est EN DUR — tout module ajouté au
   produit doit l'être ici ET dans le registre (aucun module oublié) ;
2. **contrat exécutable** (:class:`TestContratDesModulesReels`) : chaque
   ``purge_user`` / ``export_user`` du registre RÉEL est résolu PUIS APPELÉ.
   C'est le seul niveau qui protège vraiment : la comparaison de listes ne
   comparait qu'une copie littérale de ``DATA_MODULE_NAMES`` à elle-même et
   n'appelait jamais rien — ``jobs.purge_user`` a pu rester un stub
   ``NotImplementedError`` pendant que la purge RGPD échouait en silence à
   J+30 (demande figée « pending » à vie, audit jamais anonymisé).
"""

import subprocess
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import override_engine
from app.modules.privacy.registry import (
    DATA_MODULE_NAMES,
    DEFAULT_REGISTRY,
    ModuleEntry,
    PurgeRegistry,
)

#: Liste de contrôle EN DUR (D21) — ne pas générer dynamiquement.
EXPECTED_MODULES = (
    "auth",
    "profiles",  # inclut les CV
    "preferences",
    "jobs",  # inclut saved_jobs
    "matching",
    "explanations",
    "generation",
    "applications",
)


#: Utilisateur qui n'existe pas : purger/exporter doit être un no-op inoffensif.
ABSENT_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")

#: Base volontairement INJOIGNABLE (port fermé) : le contrat testé ici est
#: « la fonction existe et s'exécute », pas « la base répond ». Un refus de
#: connexion est immédiat et déterministe — aucune dépendance à PostgreSQL.
UNREACHABLE_DB_URL = "postgresql+asyncpg://boussole:boussole@127.0.0.1:1/boussole"


async def _call_without_db(fn: Callable[..., Awaitable[Any]]) -> None:
    """Appelle ``fn(ABSENT_USER)`` ; laisse fuir les seules NotImplementedError.

    Toute autre exception (base ou Redis injoignable) est ATTENDUE et ignorée :
    elle prouve précisément que la fonction est allée jusqu'à faire son
    travail. Une ``NotImplementedError``, elle, signe un stub oublié.
    """
    engine = create_async_engine(UNREACHABLE_DB_URL, poolclass=NullPool)
    try:
        with override_engine(engine):
            await fn(ABSENT_USER)
    except NotImplementedError:
        raise
    except Exception:
        # Dépendances absentes (base, Redis) : hors sujet ici — seule
        # NotImplementedError, relancée juste au-dessus, est disqualifiante.
        pass
    finally:
        await engine.dispose()


class TestContratDesModulesReels:
    """Le test qui aurait dû attraper C1 : résout ET APPELLE le registre réel."""

    @pytest.mark.parametrize("name", EXPECTED_MODULES)
    async def test_purge_user_n_est_pas_un_stub(self, name: str) -> None:
        entry = next(e for e in DEFAULT_REGISTRY.entries if e.name == name)
        purge_fn = entry.resolve_purge()  # import réel du module
        assert callable(purge_fn)
        await _call_without_db(purge_fn)

    @pytest.mark.parametrize("name", EXPECTED_MODULES)
    async def test_export_user_n_est_pas_un_stub(self, name: str) -> None:
        entry = next(e for e in DEFAULT_REGISTRY.entries if e.name == name)
        export_fn = entry.resolve_export()  # import réel du module
        assert callable(export_fn)
        await _call_without_db(export_fn)

    async def test_aucun_module_du_registre_ne_leve_not_implemented(self) -> None:
        """Filet global : un seul stub dans le registre fait échouer ce test."""
        stubs: list[str] = []
        for entry in DEFAULT_REGISTRY.entries:
            for resolve in (entry.resolve_purge, entry.resolve_export):
                try:
                    await _call_without_db(resolve())
                except NotImplementedError:
                    stubs.append(f"{entry.name}.{resolve.__name__[8:]}_user")
        assert not stubs, f"modules encore à l'état de stub dans le registre : {stubs}"


class TestExhaustivite:
    def test_le_registre_declare_exactement_les_modules_attendus(self) -> None:
        assert DEFAULT_REGISTRY.names == EXPECTED_MODULES
        assert DATA_MODULE_NAMES == EXPECTED_MODULES

    def test_chaque_entree_pointe_vers_le_module_purge_conventionnel(self) -> None:
        for entry in DEFAULT_REGISTRY.entries:
            assert entry.module_path == f"app.modules.{entry.name}.purge"

    def test_le_registre_n_importe_aucun_module_de_donnees(self) -> None:
        # Import paresseux : déclarer le registre ne doit charger AUCUN module
        # réel (les modules en chantier ne doivent pas casser l'API).
        # Vérifié dans un INTERPRÉTEUR NEUF : dans le processus pytest,
        # sys.modules est pollué par la simple COLLECTE des autres tests
        # (ex. tests/unit/*/test_purge.py importent leurs modules purge) —
        # l'assertion en processus courant dépendrait de l'ordre de collecte.
        code = (
            "import sys\n"
            "import app.modules.privacy.registry\n"
            f"names = {EXPECTED_MODULES!r}\n"
            "loaded = [n for n in names if f'app.modules.{n}.purge' in sys.modules]\n"
            "assert not loaded, f'modules importés par le registre : {loaded}'\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


class TestResolutionParesseuse:
    def test_un_module_inexistant_n_echoue_qu_a_la_resolution(self) -> None:
        entry = ModuleEntry(name="fantome", module_path="app.modules.fantome.purge")
        registry = PurgeRegistry(entries=(entry,))  # déclaration : aucun import
        assert registry.names == ("fantome",)
        with pytest.raises(ModuleNotFoundError):
            entry.resolve_purge()
        with pytest.raises(ModuleNotFoundError):
            entry.resolve_export()

    async def test_les_callables_injectes_court_circuitent_l_import(self) -> None:
        seen: list[uuid.UUID] = []

        async def fake_purge(user_id: uuid.UUID) -> None:
            seen.append(user_id)

        async def fake_export(user_id: uuid.UUID) -> dict[str, str]:
            return {"user": str(user_id)}

        entry = ModuleEntry(name="fake", purge=fake_purge, export=fake_export)
        user_id = uuid.uuid4()
        await entry.resolve_purge()(user_id)
        assert seen == [user_id]
        assert await entry.resolve_export()(user_id) == {"user": str(user_id)}

    def test_une_entree_vide_est_une_erreur_explicite(self) -> None:
        entry = ModuleEntry(name="vide")
        with pytest.raises(ValueError, match="vide"):
            entry.resolve_purge()

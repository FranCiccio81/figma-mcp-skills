"""Tests du registre déclaratif (D21) — contrôle d'exhaustivité.

AUCUN import des vrais modules de données : la liste attendue est EN DUR —
tout module ajouté au produit doit être ajouté ici ET au registre, sinon ce
test échoue (aucun module ne peut être oublié de la purge/de l'export).
"""

import subprocess
import sys
import uuid
from pathlib import Path

import pytest

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

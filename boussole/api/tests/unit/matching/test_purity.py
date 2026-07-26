"""Pureté du moteur (D02/D03) : aucun import interdit, calcul autonome.

Deux vérifications complémentaires :
1. Inspection AST des sources de `app/matching` — seuls la stdlib et
   `app.matching.*` sont importables.
2. Interpréteur frais (subprocess) : importer `app.matching` ne doit charger
   ni `app.modules.*`, ni `app.ai`, ni SQLAlchemy, ni httpx, ni FastAPI.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import app.matching

PACKAGE_DIR = Path(app.matching.__file__).resolve().parent
API_ROOT = PACKAGE_DIR.parents[1]

FORBIDDEN_PREFIXES = (
    "app.modules",
    "app.ai",
    "sqlalchemy",
    "httpx",
    "fastapi",
    "celery",
    "redis",
    "asyncpg",
    "alembic",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_sources_import_only_stdlib_and_matching() -> None:
    stdlib = set(sys.stdlib_module_names)
    for source_file in sorted(PACKAGE_DIR.rglob("*.py")):
        for module in _imported_modules(source_file.read_text(encoding="utf-8")):
            root = module.split(".")[0]
            is_internal = module == "app.matching" or module.startswith("app.matching.")
            assert is_internal or root in stdlib, (
                f"{source_file.name} importe {module!r} — le moteur doit rester "
                "en Python pur (stdlib + app.matching uniquement)"
            )


def test_no_forbidden_import_at_source_level() -> None:
    for source_file in sorted(PACKAGE_DIR.rglob("*.py")):
        for module in _imported_modules(source_file.read_text(encoding="utf-8")):
            for prefix in FORBIDDEN_PREFIXES:
                assert not (module == prefix or module.startswith(prefix + ".")), (
                    f"{source_file.name} importe le module interdit {module!r}"
                )


def test_fresh_interpreter_loads_no_forbidden_module() -> None:
    """`import app.matching` dans un interpréteur vierge → sys.modules propre."""
    probe = (
        "import json, sys\n"
        "import app.matching\n"
        "from app.matching import CandidateInput, JobInput, compute_match\n"
        "result = compute_match(CandidateInput(), JobInput())\n"
        "assert result.scoring_version\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = json.loads(completed.stdout)
    offenders = [
        module
        for module in loaded
        for prefix in FORBIDDEN_PREFIXES
        if module == prefix or module.startswith(prefix + ".")
    ]
    assert offenders == [], f"modules interdits chargés par app.matching : {offenders}"


def test_engine_needs_no_third_party_at_runtime() -> None:
    """Même pydantic n'est pas requis : le moteur tourne sur la stdlib seule."""
    probe = (
        "import sys\n"
        "baseline = set(sys.modules)\n"
        "import app.matching\n"
        "loaded = [m for m in sys.modules if m not in baseline]\n"
        "third_party = [m for m in loaded"
        " if m.split('.')[0] not in sys.stdlib_module_names"
        " and not (m == 'app' or m.startswith('app.'))]\n"
        "print(','.join(third_party))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == ""

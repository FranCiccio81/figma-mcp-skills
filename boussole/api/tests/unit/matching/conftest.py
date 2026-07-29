"""Ces tests exercent la MÉCANIQUE du moteur, sur une config calibrée.

Voir ``_calibration.py`` pour le pourquoi et pour le contre-poids
(``test_shipped_config.py``, qui vérifie la configuration livrée telle
qu'elle est).
"""

from pathlib import Path

import pytest

import app.matching.config as config_module
from tests.unit.matching._calibration import write_calibrated_config


@pytest.fixture(autouse=True)
def _calibrated_scoring_config(tmp_path_factory: pytest.TempPathFactory):
    """Active ``title_similarity`` en pointant vers une config calibrée.

    Portée FONCTION, et c'est important : en portée session, la substitution
    survivait à ce dossier et polluait les suites exécutées après lui. Les
    tests d'évaluation, qui doivent voir la config LIVRÉE, voyaient la
    calibrée — et la suite complète ne passait que par chance d'ordre
    alphabétique (`evaluation` avant `matching`). Un dossier nommé autrement,
    une exécution en parallèle, et le vernis sautait.

    Substitution par le CHEMIN par défaut : ``get_config`` est mis en cache
    par chemin, la config calibrée a donc sa propre entrée et n'écrase pas
    celle de la config livrée.
    """
    source = Path(config_module._DEFAULT_CONFIG_PATH)
    calibree = write_calibrated_config(
        source, tmp_path_factory.mktemp("scoring") / "scoring-config.json"
    )
    config_module._DEFAULT_CONFIG_PATH = calibree
    yield
    config_module._DEFAULT_CONFIG_PATH = source

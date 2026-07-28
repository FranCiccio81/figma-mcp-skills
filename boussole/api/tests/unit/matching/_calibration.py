"""Configuration CALIBRÉE pour les tests de mécanisme du moteur.

Pourquoi ce fichier existe. La configuration livrée porte
``title_similarity.calibrated_for_model: null`` : les seuils 0,55 / 0,80
n'ont été mesurés contre aucun modèle, donc le moteur rend la dimension
**inconnue** plutôt qu'un sous-score que rien ne fonde (N14). C'est le bon
comportement en production — et il rend impossible tout test du mapping
affine, qui a pourtant sa place.

D'où la séparation, explicite :

- ``tests/unit/matching/`` et ``tests/unit/matching_api/`` tournent sur une
  configuration **calibrée pour un modèle fictif**, et vérifient donc la
  MÉCANIQUE (mapping par morceaux, max des cosinus, renormalisation) ;
- le comportement de la configuration **réellement livrée** est vérifié
  ailleurs, et doit l'être : voir ``tests/unit/matching/test_shipped_config.py``
  et ``tests/unit/evaluation/test_measured_state.py``.

Sans ce second volet, la substitution ci-dessous serait exactement le piège
que ce projet a rencontré à chaque jalon : une suite verte qui valide un
mécanisme dont la configuration réelle ne se sert pas.
"""

import json
from pathlib import Path

from app.ai.embeddings.hashing import HASHING_MODEL_VERSION

#: Modèle pour lequel la config de test se déclare calibrée. On prend celui du
#: provider RÉELLEMENT actif en test plutôt qu'une chaîne inventée : les tests
#: de bout en bout passent par le service, qui lit le modèle sur le provider
#: actif — une valeur fictive les laisserait tous en « non calibré » et le
#: chemin réel ne serait jamais exercé.
TEST_EMBEDDING_MODEL = HASHING_MODEL_VERSION


def write_calibrated_config(source: Path, destination: Path) -> Path:
    """Copie ``source`` en activant ``title_similarity`` pour le modèle de test."""
    data = json.loads(source.read_text(encoding="utf-8"))
    data["dimensions"]["title_similarity"]["calibrated_for_model"] = TEST_EMBEDDING_MODEL
    destination.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return destination

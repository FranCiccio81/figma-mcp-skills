"""Importe TOUS les modèles — le seul endroit qui connaisse la liste.

**Pourquoi ce module existe.** Deux pannes graves, causes identiques, trouvées
le même jour par deux revues indépendantes :

1. ``alembic/env.py`` n'importait qu'``auth``. ``Base.metadata`` connaissait 3
   tables sur 37, et ``alembic revision --autogenerate`` produisait un
   ``upgrade()`` contenant **33 ``drop_table``** — la commande qu'on tape pour
   écrire la migration suivante écrivait la destruction de la base.

2. Le processus Celery n'importait que les modules touchés par ses tâches.
   ``applications`` n'en faisait pas partie, alors que
   ``generated_documents.application_id`` porte une clé étrangère vers cette
   table. Résultat : **tout flush ORM d'un document généré échouait** dans le
   worker, avec ``NoReferencedTableError`` — donc e-mail, lettre de motivation,
   CV adapté et optimisation de CV étaient **intégralement inopérants**. Et
   silencieusement : l'API répondait bien 202 (elle, importe les modèles via
   ses routeurs), le document restait ``pending`` pour toujours, et
   l'utilisateur lisait « Rédaction en cours… » sans limite de temps.

Le point commun : une métadonnée SQLAlchemy incomplète ne lève pas au moment
où on l'assemble. Elle lève plus tard, ailleurs, dans un processus différent
de celui qui a fait l'oubli — ou pire, elle ne lève pas et fait dire à un
outil que ce qu'il ne voit pas n'existe plus.

**La règle.** Tout processus qui manipule l'ORM importe ce module. Ajouter un
module de modèles sans l'ajouter ici est rattrapé par
``tests/unit/core/test_models_registry.py``, qui compare cette liste au
contenu réel de ``app/modules/*/models.py``.
"""

from app.modules.applications import models as applications
from app.modules.auth import models as auth
from app.modules.generation import models as generation
from app.modules.ingestion import models as ingestion
from app.modules.jobs import models as jobs
from app.modules.matching import models as matching
from app.modules.preferences import models as preferences
from app.modules.privacy import models as privacy
from app.modules.profiles import models as profiles
from app.modules.referentials import models as referentials

__all__ = [
    "applications",
    "auth",
    "generation",
    "ingestion",
    "jobs",
    "matching",
    "preferences",
    "privacy",
    "profiles",
    "referentials",
]

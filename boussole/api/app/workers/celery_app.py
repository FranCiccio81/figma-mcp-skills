"""Application Celery (D12/D16).

Quatre files spécialisées — ``ingestion``, ``ai``, ``scoring``,
``maintenance`` — avec ``acks_late`` pour la reprise sur incident.
Broker : Redis persistant (AOF, noeviction — D17).

Lancement (dev) :
    celery -A app.workers.celery_app worker -Q ingestion,ai,scoring,maintenance
"""

import os

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

# TOUS les modèles, sinon les métadonnées SQLAlchemy du processus worker sont
# incomplètes et les clés étrangères qui les traversent ne se résolvent pas.
# ``generated_documents.application_id`` référence ``applications`` : sans cet
# import, TOUTE génération de contenu échouait au flush, dans le worker
# seulement, et le document restait « en cours » indéfiniment côté utilisateur.
from app import models_registry as _models  # noqa: F401
from app.core.config import get_settings
from app.core.observability import configure_observability
from app.core.secrets import check_hardening_configuration, check_secrets_configuration
from app.core.storage import check_storage_configuration

settings = get_settings()

# Refus de démarrer un worker mal configuré — MÊME GARDE QUE L'API, au même
# endroit qu'elle : à l'import.
#
# ⚠️ Ne PAS revenir à un receveur ``@worker_ready.connect`` : ce garde-fou-là
# était un no-op vérifié. ``celery.utils.dispatch.Signal.send`` attrape toute
# exception levée par un receveur, la journalise et poursuit ; et
# ``worker_ready`` est de surcroît émis APRÈS le début de la consommation de
# la file. Un worker en ``ENV=production`` + ``STORAGE_BACKEND=local``
# démarrait donc normalement et écrivait archives d'export et CV sur SON
# disque, que l'API ne relit jamais (revue M5, puis C2).
#
# Au niveau module, l'exception remonte à l'import : `celery -A
# app.workers.celery_app worker` s'arrête, bruyamment, avant d'avoir accepté
# la moindre tâche.
check_storage_configuration(settings)
check_secrets_configuration(settings)
check_hardening_configuration(settings)

# Les alertes de conformité (purges RGPD en retard) sont émises par des
# tâches Celery : sans export ici, elles n'atteindraient personne.
configure_observability(settings)

#: Emplacement du fichier d'état de ``celery beat`` — surchargeable, car
#: ``/tmp`` peut être monté en lecture seule sur certaines plateformes.
#: Perdre ce fichier est sans gravité : beat le reconstruit au démarrage.
_BEAT_SCHEDULE_FILE = os.environ.get(
    "CELERY_BEAT_SCHEDULE_FILE", "/tmp/boussole-celerybeat-schedule"
)

#: Bornes de durée d'une tâche. La plus longue du système est l'extraction de
#: CV (appel LLM + retries bornés) ; 10 min laissent de la marge sans laisser
#: un worker retenu indéfiniment. La limite douce lève une exception dans la
#: tâche (nettoyage possible), la dure tue le processus.
_SOFT_TIME_LIMIT_SECONDS = 600
_HARD_TIME_LIMIT_SECONDS = 660

#: Doit être STRICTEMENT supérieur à la limite dure : sinon le courtier rend
#: le message à la file alors que la tâche tourne encore, et deux workers
#: traitent le même CV.
_VISIBILITY_TIMEOUT_SECONDS = 900

celery_app = Celery(
    "boussole",
    broker=settings.redis_persistent_url,
    backend=settings.redis_persistent_url,
    include=[
        "app.workers.ingestion_tasks",
        "app.workers.cv_tasks",
        "app.workers.generation_tasks",
        "app.workers.privacy_tasks",
        "app.workers.embedding_tasks",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # D16 — re-livraison si le worker meurt
    # ``acks_late`` seul ne suffit pas. Le message n'est rendu à la file
    # qu'au bout du ``visibility_timeout`` de kombu-redis, dont le défaut est
    # d'UNE HEURE. Mesuré en revue : worker tué net pendant un import de CV,
    # un worker neuf relancé, message jamais redélivré après 105 s — et le
    # document restait ``parsing`` en base, l'utilisateur devant une roue qui
    # tourne. Aligné sur la durée réelle des tâches, temps limite compris.
    broker_transport_options={"visibility_timeout": _VISIBILITY_TIMEOUT_SECONDS},
    # Un worker perdu (OOM, nœud coupé) rend son message tout de suite au
    # lieu d'attendre l'expiration ci-dessus.
    task_reject_on_worker_lost=True,
    # Sans borne, une tâche bloquée retient son worker indéfiniment : mesuré,
    # un SIGTERM sur un worker occupé attend sans fin, la période de grâce de
    # l'orchestrateur expire, et on retombe sur le kill -9.
    task_soft_time_limit=_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=_HARD_TIME_LIMIT_SECONDS,
    # Fichier d'état de ``celery beat``, HORS du répertoire de travail.
    #
    # Le ``PersistentScheduler`` le crée dans le CWD. Dans l'image livrée, le
    # CWD est `/srv/boussole`, créé root et non inscriptible par l'utilisateur
    # `boussole` : beat sortait en code 1 IMMÉDIATEMENT
    # (`_dbm.error: [Errno 13] Permission denied: 'celerybeat-schedule'`),
    # donc en boucle de redémarrage, et **rien n'était jamais planifié** —
    # `maintenance.purge_due_accounts` compris, c'est-à-dire l'engagement RGPD
    # des 30 jours. Aucun healthcheck ne couvre `beat` : la panne était muette.
    beat_schedule_filename=_BEAT_SCHEDULE_FILE,
    worker_prefetch_multiplier=1,
    task_default_queue="maintenance",
    task_queues=(
        Queue("ingestion"),
        Queue("ai"),
        Queue("scoring"),
        Queue("maintenance"),
    ),
    # Routage par préfixe de nom de tâche : "<file>.<tâche>".
    task_routes={
        "ingestion.*": {"queue": "ingestion"},
        "ai.*": {"queue": "ai"},
        "scoring.*": {"queue": "scoring"},
        "maintenance.*": {"queue": "maintenance"},
    },
    broker_connection_retry_on_startup=True,
    # Planification 07 §4.2 🟡 : FT toutes les 2 h + réconciliation complète
    # nocturne (03:00 UTC) ; ATS toutes les 6 h (fetch complet, la
    # réconciliation par absence est portée par ingestion.reconcile) ;
    # expiration par signal chaque nuit. Les sources restent derrière leurs
    # feature flags FEATURE_SOURCE_* (défaut false) : une tâche planifiée
    # sur une source désactivée est un no-op logué.
    beat_schedule={
        "ingestion-sync-france-travail": {
            "task": "ingestion.sync_source",
            "schedule": crontab(minute=0, hour="*/2"),
            "args": ("france-travail",),
        },
        "ingestion-reconcile-france-travail": {
            "task": "ingestion.reconcile",
            "schedule": crontab(minute=0, hour=3),
            "args": ("france-travail",),
        },
        "ingestion-reconcile-greenhouse": {
            "task": "ingestion.reconcile",
            "schedule": crontab(minute=15, hour="*/6"),
            "args": ("greenhouse",),
        },
        "ingestion-reconcile-lever": {
            "task": "ingestion.reconcile",
            "schedule": crontab(minute=30, hour="*/6"),
            "args": ("lever",),
        },
        "maintenance-expire-jobs": {
            "task": "maintenance.expire_jobs",
            "schedule": crontab(minute=45, hour=3),
        },
        "maintenance-purge-due-accounts": {
            "task": "maintenance.purge_due_accounts",
            "schedule": crontab(minute=15, hour=4),
        },
        # Ménage des archives d'export expirées (M3) : le lien signé meurt à
        # J+7, l'objet stocké doit mourir avec lui (minimisation, D09).
        # Décalée de la purge de comptes pour ne pas concentrer les I/O objet.
        "maintenance-purge-expired-exports": {
            "task": "maintenance.purge_expired_exports",
            "schedule": crontab(minute=45, hour=4),
        },
        # Surveillance de l'engagement des 30 jours (D20). Placée APRÈS la
        # purge de 04:15 : ce qu'elle trouve encore `pending` est ce que la
        # purge n'a pas su traiter. Une heure d'écart laisse le temps à une
        # purge lente de finir avant qu'on la déclare en retard.
        "maintenance-check-purge-backlog": {
            "task": "maintenance.check_purge_backlog",
            "schedule": crontab(minute=15, hour=5),
        },
        # Rétention 13 mois du journal des appels IA (11 §3). Après le reste
        # du ménage : c'est la tâche la plus longue (suppression par lots sur
        # la plus grosse table) et la moins urgente des trois.
        "maintenance-purge-ai-calls": {
            "task": "maintenance.purge_ai_calls",
            "schedule": crontab(minute=30, hour=5),
        },
        # Rattrapage quotidien des embeddings manquants (08 §8) : les
        # vecteurs sont normalement calculés au fil de l'eau (à l'ingestion
        # d'une offre), ce beat ne rattrape que les trous — offres ingérées
        # pendant une panne du provider, profils validés, intitulés cibles
        # et libellés de compétences. Tâches idempotentes (elles ne
        # traitent que les lignes `embedding IS NULL`), donc sûres à
        # rejouer. Décalées les unes des autres et placées AVANT le ménage
        # de 03:45–04:45 pour ne pas concentrer les I/O.
        # 🟡 Noms préfixés `ai.` : le routage de `task_routes` est par
        # préfixe de file — c'est ce qui place ces tâches sur la file `ai`
        # (voir l'en-tête de app/workers/embedding_tasks.py).
        "embeddings-backfill-jobs": {
            "task": "ai.embeddings.backfill_jobs",
            "schedule": crontab(minute=10, hour=2),
        },
        "embeddings-backfill-profiles": {
            "task": "ai.embeddings.backfill_profiles",
            "schedule": crontab(minute=25, hour=2),
        },
        "embeddings-backfill-skills": {
            "task": "ai.embeddings.backfill_skills",
            "schedule": crontab(minute=40, hour=2),
        },
    },
)


@celery_app.task(name="maintenance.ping")
def ping() -> str:
    """Tâche exemple — vérifie le tour complet broker → worker → résultat."""
    return "pong"

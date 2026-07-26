"""Application Celery (D12/D16).

Quatre files spécialisées — ``ingestion``, ``ai``, ``scoring``,
``maintenance`` — avec ``acks_late`` pour la reprise sur incident.
Broker : Redis persistant (AOF, noeviction — D17).

Lancement (dev) :
    celery -A app.workers.celery_app worker -Q ingestion,ai,scoring,maintenance
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "boussole",
    broker=settings.redis_persistent_url,
    backend=settings.redis_persistent_url,
    include=[
        "app.workers.ingestion_tasks",
        "app.workers.cv_tasks",
        "app.workers.generation_tasks",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # D16 — re-livraison si le worker meurt
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
    },
)


@celery_app.task(name="maintenance.ping")
def ping() -> str:
    """Tâche exemple — vérifie le tour complet broker → worker → résultat."""
    return "pong"

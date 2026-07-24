"""Application Celery (D12/D16).

Quatre files spécialisées — ``ingestion``, ``ai``, ``scoring``,
``maintenance`` — avec ``acks_late`` pour la reprise sur incident.
Broker : Redis persistant (AOF, noeviction — D17).

Lancement (dev) :
    celery -A app.workers.celery_app worker -Q ingestion,ai,scoring,maintenance
"""

from celery import Celery
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "boussole",
    broker=settings.redis_persistent_url,
    backend=settings.redis_persistent_url,
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
)


@celery_app.task(name="maintenance.ping")
def ping() -> str:
    """Tâche exemple — vérifie le tour complet broker → worker → résultat."""
    return "pong"

"""Routes du module preferences (F-D) : GET /preferences, PUT /preferences.

Toutes les routes exigent une session valide (cookie ``boussole_session``) —
401 problem+json sinon. Le PUT passe par le middleware CSRF global et émet
l'événement interne « preferences_changed » (hook injectable — branché au M3
sur l'invalidation des ``match_results`` du module matching, RM-D-4).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.matching.repository import MatchingRepository, get_matching_repository
from app.modules.matching.service import make_preferences_changed_hook
from app.modules.preferences.repository import (
    PreferencesRepository,
    get_preferences_repository,
)
from app.modules.preferences.schemas import PreferencesPayload
from app.modules.preferences.service import (
    PreferencesChangedHook,
    PreferencesService,
)

router = APIRouter(prefix="/preferences", tags=["preferences"])


def get_preferences_changed_hook(
    matching_repository: MatchingRepository = Depends(get_matching_repository),
) -> PreferencesChangedHook:
    """Hook « preferences_changed » (RM-D-4) — surchargé par les tests.

    M3 : invalidation simple des ``match_results`` de l'utilisateur (delete,
    recalcul paresseux au prochain accès). TODO(M4) : re-scoring asynchrone
    des offres actives (06 §4 déclencheur a).
    """
    return make_preferences_changed_hook(matching_repository)


def get_preferences_service(
    repository: PreferencesRepository = Depends(get_preferences_repository),
    on_changed: PreferencesChangedHook = Depends(get_preferences_changed_hook),
) -> PreferencesService:
    return PreferencesService(repository, on_changed)


CurrentUser = Annotated[User, Depends(require_current_user)]
Service = Annotated[PreferencesService, Depends(get_preferences_service)]


@router.get("", response_model=PreferencesPayload, summary="Lire les préférences")
async def get_preferences(user: CurrentUser, service: Service) -> PreferencesPayload:
    """État courant — défauts produit 🟡 si jamais enregistrées (remote
    ``indifferent``, ``contract_types=[permanent]``, listes vides)."""
    return await service.get(user.id)


@router.put(
    "",
    response_model=PreferencesPayload,
    summary="Remplacer les préférences (payload complet)",
)
async def put_preferences(
    payload: PreferencesPayload, user: CurrentUser, service: Service
) -> PreferencesPayload:
    """Remplacement complet transactionnel (delete + insert des listes) : une
    liste omise est vidée (F-D alternatif 1). 422 sans écriture si le payload
    est invalide (AC-D-4). Déclenche « preferences_changed » (RM-D-4)."""
    return await service.put(user.id, payload)

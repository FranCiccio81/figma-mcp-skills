"""L'état d'onboarding est lu EN BASE, sur les trois vraies tables.

Les trois indicateurs de ``GET /me`` étaient des littéraux ``False``. Le
correctif est une requête SQL à trois ``EXISTS`` — donc une requête que la
doublure en mémoire des tests unitaires ne peut pas valider : elle rend ce
qu'on lui a posé.

Or ``cv_documents`` fait partie des quatre tables sans modèle ORM, interrogées
en SQL brut. Une faute de nom de colonne ou de table ne se verrait qu'ici.
"""

import uuid

import pytest
from sqlalchemy import text

from app.modules.auth.repository import SqlAlchemyAuthRepository

pytestmark = pytest.mark.integration


async def _compte(db_session) -> uuid.UUID:
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, locale) "
            "VALUES (:id, :email, 'x', 'fr')"
        ),
        {"id": user_id, "email": f"{user_id}@exemple.invalid"},
    )
    return user_id


class TestLesTroisIndicateursSuiventLaBase:
    async def test_un_compte_neuf_na_rien_franchi(self, db_session) -> None:
        user_id = await _compte(db_session)
        repo = SqlAlchemyAuthRepository(db_session)

        assert await repo.onboarding_state(user_id) == (False, False, False)

    async def test_un_cv_importe_se_voit(self, db_session) -> None:
        user_id = await _compte(db_session)
        await db_session.execute(
            text(
                "INSERT INTO cv_documents (user_id, file_key, filename, mime_type, "
                "size_bytes, status) "
                "VALUES (:uid, 'cv/x.pdf', 'cv.pdf', 'application/pdf', 1024, 'parsed')"
            ),
            {"uid": user_id},
        )
        repo = SqlAlchemyAuthRepository(db_session)

        cv, profil, prefs = await repo.onboarding_state(user_id)
        assert (cv, profil, prefs) == (True, False, False)

    async def test_un_profil_BROUILLON_ne_compte_pas_comme_valide(
        self, db_session
    ) -> None:
        """Distinction décisive : un profil ``draft`` fait répondre 409 à
        toutes les routes de matching. Le dire « validé » enverrait
        l'utilisateur vers un écran qui refuse de lui répondre."""
        user_id = await _compte(db_session)
        await db_session.execute(
            text(
                "INSERT INTO profiles (user_id, status, version) "
                "VALUES (:uid, 'draft', 1)"
            ),
            {"uid": user_id},
        )
        repo = SqlAlchemyAuthRepository(db_session)

        assert await repo.onboarding_state(user_id) == (False, False, False)

    async def test_un_profil_valide_se_voit(self, db_session) -> None:
        user_id = await _compte(db_session)
        await db_session.execute(
            text(
                "INSERT INTO profiles (user_id, status, version) "
                "VALUES (:uid, 'validated', 1)"
            ),
            {"uid": user_id},
        )
        repo = SqlAlchemyAuthRepository(db_session)

        assert await repo.onboarding_state(user_id) == (False, True, False)

    async def test_des_preferences_se_voient(self, db_session) -> None:
        user_id = await _compte(db_session)
        await db_session.execute(
            text(
                "INSERT INTO preferences (user_id) VALUES (:uid)"
            ),
            {"uid": user_id},
        )
        repo = SqlAlchemyAuthRepository(db_session)

        assert await repo.onboarding_state(user_id) == (False, False, True)

    async def test_letat_ne_fuit_pas_dun_compte_a_lautre(self, db_session) -> None:
        """Un indicateur qui fuit serait pire que faux : il enverrait
        quelqu'un vers une étape qu'il n'a pas franchie."""
        avance = await _compte(db_session)
        neuf = await _compte(db_session)
        await db_session.execute(
            text(
                "INSERT INTO preferences (user_id) VALUES (:uid)"
            ),
            {"uid": avance},
        )
        repo = SqlAlchemyAuthRepository(db_session)

        assert await repo.onboarding_state(avance) == (False, False, True)
        assert await repo.onboarding_state(neuf) == (False, False, False)

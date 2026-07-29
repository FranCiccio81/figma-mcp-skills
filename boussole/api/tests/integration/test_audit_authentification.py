"""Les lignes d'audit d'authentification atteignent vraiment la table.

La doublure en mémoire des tests unitaires garde ce qu'on lui donne : elle ne
peut rien dire de l'écriture réelle. Or ``audit_log`` a une clé étrangère vers
``users`` avec ``ON DELETE SET NULL``, une colonne ``meta`` en JSONB, et une
contrainte d'``action`` — trois façons pour l'écriture d'échouer là où le fake
réussit.

Ce test vérifie aussi la propriété qui compte le plus à long terme : ces
lignes doivent survivre à la purge du compte **sans le désigner** (RM-Q-2).
"""

import uuid

import pytest
from sqlalchemy import text

from app.modules.auth.audit import LOGIN_FAILED, LOGIN_SUCCEEDED, build_meta
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


async def _lignes(db_session, action: str) -> list[tuple]:
    resultat = await db_session.execute(
        text("SELECT user_id, action, meta FROM audit_log WHERE action = :a"),
        {"a": action},
    )
    return list(resultat.all())


class TestLaLigneAtteintLaTable:
    async def test_une_connexion_reussie_est_ecrite(self, db_session) -> None:
        user_id = await _compte(db_session)
        repo = SqlAlchemyAuthRepository(db_session)

        await repo.add_audit(
            user_id,
            LOGIN_SUCCEEDED,
            meta=build_meta(
                client_ip="192.0.2.147", user_agent="Mozilla/5.0", trace_id="abc123"
            ),
        )

        lignes = await _lignes(db_session, LOGIN_SUCCEEDED)
        assert len(lignes) == 1
        uid, _action, meta = lignes[0]
        assert uid == user_id
        assert meta["ip_network"] == "192.0.2.0/24"
        assert meta["trace_id"] == "abc123"

    async def test_un_echec_sans_compte_sinscrit_sans_identifiant(
        self, db_session
    ) -> None:
        """La FK est nullable : un échec sur une adresse inconnue doit
        pouvoir s'écrire, sinon l'attaque la plus courante n'est pas tracée."""
        repo = SqlAlchemyAuthRepository(db_session)

        await repo.add_audit(
            None,
            LOGIN_FAILED,
            meta=build_meta(client_ip="203.0.113.9", user_agent=None, trace_id="t"),
        )

        lignes = await _lignes(db_session, LOGIN_FAILED)
        assert len(lignes) == 1 and lignes[0][0] is None

    async def test_le_json_des_metadonnees_est_bien_stocke(self, db_session) -> None:
        """``meta`` est du JSONB : un type non sérialisable échouerait ici,
        jamais dans la doublure."""
        user_id = await _compte(db_session)
        repo = SqlAlchemyAuthRepository(db_session)

        await repo.add_audit(
            user_id,
            LOGIN_SUCCEEDED,
            meta=build_meta(
                client_ip="192.0.2.1", user_agent="x" * 500, trace_id=None, created=True
            ),
        )

        (_uid, _action, meta) = (await _lignes(db_session, LOGIN_SUCCEEDED))[0]
        assert meta["created"] is True
        assert len(meta["user_agent"]) == 200, "le user-agent doit être borné"
        assert "trace_id" not in meta, "un champ absent ne doit pas être écrit vide"


class TestLesLignesSurviventALaPurgeSansDesignerPersonne:
    async def test_la_purge_detache_la_ligne_du_compte(self, db_session) -> None:
        """RM-Q-2 : la trace de sécurité reste, la personne disparaît.

        C'est l'équilibre du journal : conserver de quoi analyser un incident
        après la suppression d'un compte, sans conserver de quoi désigner la
        personne. La ligne perd son ``user_id`` et gagne un ``subject_key``
        non recalculable sans la clé de signature.
        """
        user_id = await _compte(db_session)
        repo = SqlAlchemyAuthRepository(db_session)
        await repo.add_audit(
            user_id,
            LOGIN_FAILED,
            meta=build_meta(client_ip="192.0.2.1", user_agent=None, trace_id=None),
        )

        from app.modules.privacy.repository import SqlAlchemyPrivacyRepository

        await SqlAlchemyPrivacyRepository(db_session).anonymize_audit(
            user_id, "pseudonyme-hmac"
        )

        resultat = await db_session.execute(
            text(
                "SELECT user_id, subject_key, meta FROM audit_log "
                "WHERE action = :a"
            ),
            {"a": LOGIN_FAILED},
        )
        uid, subject_key, meta = resultat.one()
        assert uid is None
        assert subject_key == "pseudonyme-hmac"
        # Le réseau reste — il sert à l'analyse d'incident et ne désigne
        # personne. Aucune adresse e-mail n'a jamais été écrite.
        assert meta["ip_network"] == "192.0.2.0/24"

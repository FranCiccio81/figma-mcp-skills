"""``python -m app.demo`` — amène une base vide à une application utilisable.

Ce que ça fait, dans l'ordre, et pourquoi chaque étape est indispensable :

1. **référentiels** (secteurs, compétences, alias, sources) — sans la
   taxonomie, aucune compétence d'offre ne se rapproche d'une compétence de
   profil et le matching est aveugle ;
2. **activation du corpus de démonstration** — la source doit exister ET être
   ``active`` pour apparaître sur la page des sources (transparence produit) ;
3. **ingestion réelle** du corpus par la chaîne de production : normalisation,
   géocodage, dédup étage 1, ``job_sources``. Pas d'insertion directe en base :
   ce qui n'est pas passé par la chaîne ne prouve rien sur la chaîne ;
4. **embeddings** des offres, des compétences et des profils — sans eux, le
   rerank vectoriel et le crédit « compétence proche » restent morts ;
5. **un compte de démonstration au profil VALIDÉ**, avec compétences,
   préférences et intitulés cibles. C'est ce qui manquait le plus : un profil
   ``draft`` fait répondre 409 à toutes les routes de matching, et l'app
   paraît cassée alors qu'elle applique sa règle.

À la fin, se connecter avec les identifiants affichés donne une application
où la recherche renvoie des offres, où chaque offre a un score explicable, et
où une génération peut être demandée.

⚠️ **Les offres sont FICTIVES** (D34) et la commande refuse de s'exécuter hors
développement — deux barrières, parce qu'un corpus inventé pris pour réel est
exactement ce que ce produit s'interdit.
"""

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker

from app.ai.embeddings.factory import get_embedding_provider
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.security import hash_password
from app.modules.ingestion.connectors.demo_corpus import build_demo_connector
from app.modules.ingestion.service import SqlAlchemyJobStore, ingest_batch
from app.seeds import seed_reference_data

logger = logging.getLogger("boussole.demo")

DEMO_EMAIL = "demo@boussole.dev"
DEMO_PASSWORD = "boussole-demo-1234"

@dataclass(frozen=True, slots=True)
class DemoProfile:
    """Profil taillé pour que le corpus ait de quoi discriminer : plusieurs
    offres très pertinentes, plusieurs hors sujet, au moins un rédhibitoire."""

    headline: str
    seniority: str
    total_experience_years: float
    skills: tuple[str, ...]
    titles: tuple[str, ...]
    locations: tuple[tuple[str, float, float, int], ...]
    languages: tuple[tuple[str, str], ...]
    contracts: tuple[str, ...]
    remote: str
    salary_min: int
    sector_code: str


DEMO_PROFILE = DemoProfile(
    headline="Développeuse backend Python — 6 ans",
    seniority="senior",
    total_experience_years=6.0,
    skills=("python", "postgresql", "docker", "git"),
    titles=("Développeur Backend Python", "Ingénieur logiciel backend"),
    locations=(("Paris", 48.8566, 2.3522, 40),),
    languages=(("fr", "C2"), ("en", "B1")),
    contracts=("permanent",),
    remote="preferred",
    salary_min=55000,
    # Code du référentiel `sectors` (NAF J = information et communication).
    sector_code="J",
)


class DemoUnavailableError(RuntimeError):
    """Amorçage de démonstration demandé là où il ne doit pas tourner."""


async def bootstrap() -> dict[str, Any]:
    """Exécute l'amorçage complet et rend un compte rendu chiffré."""
    settings = get_settings()
    if settings.is_hardened:
        raise DemoUnavailableError(
            f"L'amorçage de démonstration insère des offres FICTIVES et un "
            f"compte à mot de passe public : refusé en ENV={settings.env}."
        )

    engine = get_engine()
    rapport: dict[str, Any] = {}
    try:
        async with engine.begin() as conn:
            await seed_reference_data(conn)
            await _activate_demo_source(conn)
            rapport["compte"] = await _seed_demo_account(conn)

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            rapport["ingestion"] = await _ingest_demo_corpus(session)
        async with factory() as session:
            rapport["embeddings"] = await _embed_everything(session)
        async with engine.connect() as conn:
            rapport["verification"] = await _verify(conn)
    finally:
        await engine.dispose()
    return rapport


async def _activate_demo_source(conn: AsyncConnection) -> None:
    """La source doit être ``active`` pour figurer sur la page des sources.

    Les sources réelles restent inactives : leur activation suppose une fiche
    de conformité signée (D04). Celle-ci n'en a pas besoin — sa fiche dit
    qu'elle est fictive, et le connecteur refuse de tourner hors développement.
    """
    await conn.execute(
        text("UPDATE sources SET active = true WHERE slug = 'demo-corpus'")
    )


async def _seed_demo_account(conn: AsyncConnection) -> dict[str, Any]:
    """Compte + profil **validé** + préférences. Un profil ``draft`` ferait
    répondre 409 à toutes les routes de matching."""
    await conn.execute(
        text(
            "INSERT INTO users (email, password_hash, locale) "
            "VALUES (:email, :hash, 'fr') "
            "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash"
        ),
        {"email": DEMO_EMAIL, "hash": hash_password(DEMO_PASSWORD)},
    )
    user_id = (
        await conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": DEMO_EMAIL}
        )
    ).scalar_one()

    await conn.execute(
        text(
            "INSERT INTO profiles (user_id, status, headline, seniority, "
            "total_experience_years, version, validated_at) "
            "VALUES (:uid, 'validated', :headline, :seniority, :years, 1, now()) "
            "ON CONFLICT (user_id) DO UPDATE SET status = 'validated', "
            "headline = EXCLUDED.headline, seniority = EXCLUDED.seniority, "
            "total_experience_years = EXCLUDED.total_experience_years, "
            "validated_at = now(), version = profiles.version + 1"
        ),
        {
            "uid": user_id,
            "headline": DEMO_PROFILE.headline,
            "seniority": DEMO_PROFILE.seniority,
            "years": DEMO_PROFILE.total_experience_years,
        },
    )
    profile_id = (
        await conn.execute(
            text("SELECT id FROM profiles WHERE user_id = :uid"), {"uid": user_id}
        )
    ).scalar_one()

    await conn.execute(
        text("DELETE FROM profile_skills WHERE profile_id = :pid"), {"pid": profile_id}
    )
    for label in DEMO_PROFILE.skills:
        await conn.execute(
            text(
                "INSERT INTO profile_skills (profile_id, skill_id, label_raw, source, "
                "confidence) SELECT :pid, id, :label, 'user_confirmed', 1.0 "
                "FROM skills WHERE lower(canonical_label) = lower(:label)"
            ),
            {"pid": profile_id, "label": label},
        )

    await conn.execute(
        text("DELETE FROM profile_languages WHERE profile_id = :pid"), {"pid": profile_id}
    )
    for code, level in DEMO_PROFILE.languages:
        await conn.execute(
            text(
                "INSERT INTO profile_languages (profile_id, lang_code, level, source) "
                "VALUES (:pid, :code, :level, 'user_confirmed')"
            ),
            {"pid": profile_id, "code": code, "level": level},
        )

    await _seed_preferences(conn, user_id)
    return {
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "profile_id": str(profile_id),
        "competences": len(DEMO_PROFILE.skills),
    }


async def _seed_preferences(conn: AsyncConnection, user_id: uuid.UUID) -> None:
    await conn.execute(
        text(
            "INSERT INTO preferences (user_id, remote_pref, contract_types, "
            "salary_min, salary_currency) "
            "VALUES (:uid, :remote, :contracts, :salary, 'EUR') "
            "ON CONFLICT (user_id) DO UPDATE SET remote_pref = EXCLUDED.remote_pref, "
            "contract_types = EXCLUDED.contract_types, "
            "salary_min = EXCLUDED.salary_min"
        ),
        {
            "uid": user_id,
            "remote": DEMO_PROFILE.remote,
            "contracts": list(DEMO_PROFILE.contracts),
            "salary": DEMO_PROFILE.salary_min,
        },
    )
    for table in ("preference_titles", "preference_locations"):
        await conn.execute(
            text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": user_id}
        )
    for titre in DEMO_PROFILE.titles:
        await conn.execute(
            text("INSERT INTO preference_titles (user_id, title) VALUES (:uid, :t)"),
            {"uid": user_id, "t": titre},
        )
    for label, lat, lon, radius in DEMO_PROFILE.locations:
        await conn.execute(
            text(
                "INSERT INTO preference_locations (user_id, label, lat, lon, radius_km) "
                "VALUES (:uid, :label, :lat, :lon, :radius)"
            ),
            {"uid": user_id, "label": label, "lat": lat, "lon": lon, "radius": radius},
        )
    # Les secteurs préférés font parler la dimension « secteur » (4 % du poids).
    await conn.execute(
        text("DELETE FROM preference_sectors WHERE user_id = :uid"), {"uid": user_id}
    )
    await conn.execute(
        text(
            "INSERT INTO preference_sectors (user_id, sector_code, mode) "
            "SELECT :uid, code, 'preferred' FROM sectors WHERE code = 'J' "
            "ON CONFLICT DO NOTHING"
        ),
        {"uid": user_id, "secteur": DEMO_PROFILE.sector_code},
    )


async def _ingest_demo_corpus(session: Any) -> dict[str, Any]:
    """Passe le corpus par la chaîne de PRODUCTION, pas par un INSERT."""
    connector = build_demo_connector()
    fetched = await asyncio.to_thread(connector.fetch, None)
    store = SqlAlchemyJobStore(session)
    rapport = await ingest_batch(connector.slug, fetched.jobs, store)
    await session.commit()
    return {
        "recues": len(fetched.jobs),
        "creees": rapport.created,
        "mises_a_jour": rapport.updated,
        "rattachees_etage1": rapport.attached_stage1,
        "erreurs": rapport.errors,
    }


async def _embed_everything(session: Any) -> dict[str, int]:
    """Vecteurs des offres, des compétences et du profil de démonstration.

    Fait ici plutôt que d'attendre le beat de 02:10 : personne ne va laisser
    tourner une nuit pour vérifier que la recherche fonctionne.
    """
    provider = get_embedding_provider()
    compteurs = {"offres": 0, "competences": 0, "intitules": 0}

    lignes = (
        await session.execute(
            text(
                "SELECT id, title, coalesce(description_text, '') FROM job_postings "
                "WHERE embedding IS NULL AND status = 'active'"
            )
        )
    ).all()
    for job_id, titre, description in lignes:
        vecteur = provider.embed_texts([f"{titre}. {description[:400]}"])[0]
        await session.execute(
            text("UPDATE job_postings SET embedding = :v WHERE id = :id"),
            {"v": str(vecteur), "id": job_id},
        )
        compteurs["offres"] += 1

    lignes = (
        await session.execute(
            text("SELECT id, canonical_label FROM skills WHERE embedding IS NULL")
        )
    ).all()
    for skill_id, label in lignes:
        await session.execute(
            text("UPDATE skills SET embedding = :v WHERE id = :id"),
            {"v": str(provider.embed_texts([label])[0]), "id": skill_id},
        )
        compteurs["competences"] += 1

    lignes = (
        await session.execute(
            text("SELECT id, title FROM preference_titles WHERE embedding IS NULL")
        )
    ).all()
    for title_id, titre in lignes:
        await session.execute(
            text("UPDATE preference_titles SET embedding = :v WHERE id = :id"),
            {"v": str(provider.embed_texts([titre])[0]), "id": title_id},
        )
        compteurs["intitules"] += 1

    await session.commit()
    return compteurs


async def _verify(conn: AsyncConnection) -> dict[str, Any]:
    """Contrôles de sortie : ce qui est vérifié ici est ce qui est promis.

    Un amorçage qui rapporte « OK » sans que la recherche ne renvoie rien
    serait pire qu'un échec — il ferait chercher le problème ailleurs.
    """
    offres = (
        await conn.execute(
            text("SELECT count(*) FROM job_postings WHERE status = 'active'")
        )
    ).scalar_one()
    vecteurs = (
        await conn.execute(
            text("SELECT count(*) FROM job_postings WHERE embedding IS NOT NULL")
        )
    ).scalar_one()
    # La recherche plein texte passe par le trigger tsvector : si le trigger
    # n'a pas tourné, cette requête rend 0 alors que les offres existent.
    trouvees = (
        await conn.execute(
            text(
                "SELECT count(*) FROM job_postings "
                "WHERE tsv @@ websearch_to_tsquery('french', unaccent('python'))"
            )
        )
    ).scalar_one()
    sources_visibles = (
        await conn.execute(text("SELECT count(*) FROM sources WHERE active"))
    ).scalar_one()
    profils_valides = (
        await conn.execute(
            text("SELECT count(*) FROM profiles WHERE status = 'validated'")
        )
    ).scalar_one()

    problemes = []
    if offres == 0:
        problemes.append("aucune offre active")
    if vecteurs != offres:
        problemes.append(f"{offres - vecteurs} offre(s) sans vecteur")
    if trouvees == 0:
        problemes.append("la recherche plein texte ne remonte rien sur « python »")
    if profils_valides == 0:
        problemes.append("aucun profil validé — les routes de matching rendront 409")

    return {
        "offres_actives": offres,
        "offres_vectorisees": vecteurs,
        "recherche_python": trouvees,
        "sources_visibles": sources_visibles,
        "profils_valides": profils_valides,
        "problemes": problemes,
    }


def _print(rapport: dict[str, Any]) -> int:
    verif = rapport["verification"]
    print("\n=== Amorçage de démonstration ===\n")
    print(f"  Offres ingérées      : {rapport['ingestion']['creees']} créées, "
          f"{rapport['ingestion']['mises_a_jour']} mises à jour, "
          f"{rapport['ingestion']['rattachees_etage1']} rattachées (dédup)")
    print(f"  Vecteurs calculés    : {rapport['embeddings']['offres']} offres, "
          f"{rapport['embeddings']['competences']} compétences, "
          f"{rapport['embeddings']['intitules']} intitulés cibles")
    print(f"  Recherche « python » : {verif['recherche_python']} offre(s)")
    print(f"  Sources visibles     : {verif['sources_visibles']}")
    print("\n  ⚠️  Les offres sont FICTIVES (liens en .invalid, D34).\n")
    print(f"  Connexion : {rapport['compte']['email']} / {rapport['compte']['password']}")
    print("  Ce profil est VALIDÉ : la recherche, le matching et les")
    print("  explications répondent immédiatement.\n")

    if verif["problemes"]:
        print("  ❌ ÉCHEC :")
        for probleme in verif["problemes"]:
            print(f"     - {probleme}")
        print()
        return 1
    print("  ✅ Application utilisable.\n")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return _print(asyncio.run(bootstrap()))
    except DemoUnavailableError as exc:
        print(f"\n❌ {exc}\n", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - point d'entrée
    sys.exit(main())

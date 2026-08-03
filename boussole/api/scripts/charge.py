"""Test de charge — corpus réaliste, utilisateurs concurrents, percentiles.

Ce n'est pas le banc de ``tests/integration/test_performance_deploiement.py``,
qui mesure UN appel à la fois pour attribuer un coût à un correctif. Ici on
cherche autre chose : ce qui casse quand plusieurs personnes utilisent
l'application en même temps sur un corpus qui ressemble à la production.

**Ce qui est réel** : PostgreSQL (schéma issu des vraies migrations), le
moteur de matching, tout le SQL, et surtout le **pool de connexions de
production** — ``create_async_engine`` sans argument, soit ``QueuePool``
(5 connexions + 10 de débordement). C'est lui la ressource contendue, et le
``NullPool`` de la suite d'intégration l'aurait masqué.

**Ce qui ne l'est pas** : transport ASGI en processus (pas de réseau, pas de
uvicorn, un seul processus Python), Redis factice, stockage sur disque local.
Les chiffres mesurent donc le travail de l'application et de la base, pas la
pile réseau. Un déploiement réel a plusieurs workers uvicorn : la capacité
par instance est supérieure à ce qui est mesuré ici.

Usage ::

    DATABASE_URL=postgresql+asyncpg://... .venv/bin/python -m scripts.charge
    OFFRES=5000 UTILISATEURS=20 TOURS=5 .venv/bin/python -m scripts.charge
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field

import fakeredis.aioredis
import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db import override_engine
from app.core.redis import get_redis_cache, get_redis_persistent
from app.main import create_app

OFFRES = int(os.getenv("OFFRES", "5000"))
UTILISATEURS = int(os.getenv("UTILISATEURS", "20"))
TOURS = int(os.getenv("TOURS", "5"))
BASE = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/boussole_charge"
)


@dataclass
class Mesures:
    nom: str
    durees_ms: list[float] = field(default_factory=list)
    statuts: Counter = field(default_factory=Counter)

    def ajouter(self, duree_ms: float, statut: int) -> None:
        self.durees_ms.append(duree_ms)
        self.statuts[statut] += 1

    def ligne(self) -> str:
        if not self.durees_ms:
            return f"  {self.nom:<26} aucune mesure"
        ordonnees = sorted(self.durees_ms)
        p50 = statistics.median(ordonnees)
        p95 = ordonnees[min(int(len(ordonnees) * 0.95), len(ordonnees) - 1)]
        p99 = ordonnees[min(int(len(ordonnees) * 0.99), len(ordonnees) - 1)]
        erreurs = sum(n for statut, n in self.statuts.items() if statut >= 400)
        detail = " ".join(f"{statut}×{n}" for statut, n in sorted(self.statuts.items()))
        return (
            f"  {self.nom:<26} n={len(ordonnees):<5} "
            f"p50={p50:7.1f}  p95={p95:7.1f}  p99={p99:7.1f} ms   "
            f"erreurs={erreurs:<4} [{detail}]"
        )


async def _preparer_corpus(session_factory) -> None:
    """5 000 offres actives, insérées en masse.

    Le trigger ``tsv`` s'applique à l'INSERT : la recherche plein texte
    travaille sur un vrai index, pas sur une colonne vide.

    ⚠️ Les valeurs d'``enum`` sont celles du SCHÉMA, pas celles qu'on croit :
    premier essai écrit de mémoire avec ``'full'`` pour le télétravail, refusé
    par PostgreSQL (``invalid input value for enum remote_policy``). Le
    vocabulaire réel est ``onsite | hybrid | full_remote``.
    """
    async with session_factory() as session:
        deja = (await session.execute(text("SELECT count(*) FROM job_postings"))).scalar_one()
        if deja >= OFFRES:
            print(f"  corpus déjà présent ({deja} offres)")
            return
        await session.execute(
            text(
                """
                INSERT INTO job_postings (
                    id, dedup_hash, title, company_name, description_text,
                    language, remote, contract, salary_min, salary_max,
                    salary_currency, salary_period, status, country_code,
                    first_seen_at, last_seen_at
                )
                SELECT
                    gen_random_uuid(),
                    md5(i::text || clock_timestamp()::text),
                    'Développeur backend Python ' || i,
                    'Entreprise ' || (i % 400),
                    'FastAPI, PostgreSQL, Redis, Docker. Poste ' || i,
                    'fr',
                    (ARRAY['onsite','hybrid','full_remote'])[1 + i % 3]::remote_policy,
                    (ARRAY['permanent','fixed_term','internship'])[1 + i % 3]::contract_type,
                    38000 + (i % 30) * 1000,
                    48000 + (i % 30) * 1000,
                    'EUR', 'year', 'active', 'FR',
                    now() - (i || ' minutes')::interval,
                    now() - (i || ' minutes')::interval
                FROM generate_series(1, :n) i
                """
            ),
            {"n": OFFRES},
        )
        await session.commit()
        await session.execute(text("ANALYZE job_postings"))
    print(f"  corpus créé : {OFFRES} offres")


async def _inscrire(client: httpx.AsyncClient, index: int) -> dict[str, str] | None:
    """Compte + profil validé + préférences. Rend les cookies de session."""
    # PAS le TLD réservé ``.invalid`` : ``EmailStr`` le refuse (« special-use
    # domain »), et les vingt inscriptions rendaient 422. La base de charge
    # est jetable, l'adresse n'a pas besoin d'être injoignable.
    email = f"charge{index}-{uuid.uuid4().hex[:8]}@exemple-charge.fr"
    reponse = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "un mot de passe très long pour la charge",
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )
    if reponse.status_code != 201:
        print(f"  ⚠ inscription {index} → {reponse.status_code}")
        return None
    return {nom: valeur for nom, valeur in reponse.cookies.items()}


async def _profil_valide(session_factory, cookies: dict[str, str], session_store) -> None:
    """Pose directement un profil validé et des préférences en base.

    Passer par l'API demanderait tout le parcours d'import de CV ; ce qu'on
    charge ici, ce sont les routes de lecture.
    """
    user_id = await session_store.get_user_id(cookies["boussole_session"])
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO profiles (id, user_id, status, version, headline, "
                "seniority, total_experience_years, validated_at) "
                "VALUES (gen_random_uuid(), :uid, 'validated', 3, 'Dev', 'mid', 5, now())"
            ),
            {"uid": user_id},
        )
        await session.execute(
            text(
                "INSERT INTO preferences (user_id, remote_pref, contract_types, "
                "contract_strict, salary_min) "
                "VALUES (:uid, 'indifferent', ARRAY['permanent']::contract_type[], "
                "false, 45000)"
            ),
            {"uid": user_id},
        )
        await session.commit()


async def _tour(
    client: httpx.AsyncClient,
    cookies: dict[str, str],
    mesures: dict[str, Mesures],
) -> None:
    """Un parcours utilisateur : recherche, page 2, matches, détail."""
    appels = [
        ("GET /jobs", "/api/v1/jobs", {}),
        ("GET /jobs?q=", "/api/v1/jobs", {"q": "python fastapi"}),
        ("GET /jobs (filtres)", "/api/v1/jobs", {"remote": "full_remote", "salary_min": 45000}),
        ("GET /matches", "/api/v1/matches", {}),
    ]
    for nom, url, params in appels:
        debut = time.perf_counter()
        try:
            reponse = await client.get(url, params=params, cookies=cookies)
            statut = reponse.status_code
        except Exception as exc:
            statut = -1
            print(f"  ⚠ {nom} : {type(exc).__name__} {exc}")
        mesures[nom].ajouter((time.perf_counter() - debut) * 1000, statut)


async def _sonde(client: httpx.AsyncClient, mesures: Mesures, arret: asyncio.Event) -> None:
    """Interroge ``/healthz`` en continu pendant la charge.

    C'est LA mesure qui distingue « le serveur est chargé » de « la boucle
    d'événements est bloquée ». ``/healthz`` ne touche ni la base ni Redis :
    il répond en 1 ms à vide. S'il monte à plusieurs secondes pendant la
    charge, c'est qu'un appel synchrone monopolise la boucle — et alors ce
    n'est pas seulement lent, c'est la sonde de l'orchestrateur qui expire et
    fait tuer des instances saines.
    """
    while not arret.is_set():
        debut = time.perf_counter()
        try:
            reponse = await client.get("/healthz")
            statut = reponse.status_code
        except Exception:
            statut = -1
        mesures.ajouter((time.perf_counter() - debut) * 1000, statut)
        await asyncio.sleep(0.1)


async def main() -> None:
    print(
        f"\nTest de charge — {OFFRES} offres, {UTILISATEURS} utilisateurs "
        f"concurrents, {TOURS} tours\n"
    )

    # Pool de PRODUCTION (QueuePool par défaut), pas le NullPool des tests.
    moteur = create_async_engine(BASE)
    override_engine(moteur)
    session_factory = async_sessionmaker(moteur, expire_on_commit=False)

    await _preparer_corpus(session_factory)

    persistent = fakeredis.FakeServer()
    cache = fakeredis.FakeServer()

    def redis_persistent() -> Redis:
        return fakeredis.aioredis.FakeRedis(server=persistent, decode_responses=True)

    def redis_cache() -> Redis:
        return fakeredis.aioredis.FakeRedis(server=cache, decode_responses=True)

    app = create_app(
        redis_cache_factory=redis_cache, redis_persistent_factory=redis_persistent
    )
    app.dependency_overrides[get_redis_persistent] = redis_persistent
    app.dependency_overrides[get_redis_cache] = redis_cache

    from app.core.config import get_settings
    from app.core.security import SessionStore

    session_store = SessionStore(
        redis_persistent(), get_settings().session_ttl_seconds
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://testserver", timeout=120.0
    ) as client:
        print(f"  inscription de {UTILISATEURS} utilisateurs…")
        comptes = []
        for index in range(UTILISATEURS):
            cookies = await _inscrire(client, index)
            if cookies is None:
                continue
            await _profil_valide(session_factory, cookies, session_store)
            comptes.append(cookies)
        print(f"  {len(comptes)} comptes prêts\n")
        if len(comptes) < UTILISATEURS:
            # Un test de charge qui ne charge rien ne doit PAS rendre un
            # rapport propre. Première exécution : vingt inscriptions en 422,
            # « 0 requêtes », « erreurs totales : 0 / 0 » — et le script
            # sortait avec succès. C'est le défaut que cette campagne entière
            # cherche à éliminer, reproduit par l'outil de mesure lui-même.
            raise SystemExit(
                f"ARRÊT : {len(comptes)}/{UTILISATEURS} comptes créés. "
                "Sans utilisateurs, la mesure ne veut rien dire."
            )

        noms = ["GET /jobs", "GET /jobs?q=", "GET /jobs (filtres)", "GET /matches"]
        mesures = {nom: Mesures(nom) for nom in noms}

        sonde = Mesures("GET /healthz (pendant)")
        arret = asyncio.Event()
        tache_sonde = asyncio.create_task(_sonde(client, sonde, arret))

        debut = time.perf_counter()
        for tour in range(TOURS):
            await asyncio.gather(
                *(_tour(client, cookies, mesures) for cookies in comptes)
            )
            print(f"  tour {tour + 1}/{TOURS} terminé")
        duree_totale = time.perf_counter() - debut

        arret.set()
        await tache_sonde
        mesures[sonde.nom] = sonde
        noms.append(sonde.nom)

    total = sum(len(m.durees_ms) for m in mesures.values())
    if total == 0:
        raise SystemExit("ARRÊT : aucune requête mesurée.")
    print(f"\n  {total} requêtes en {duree_totale:.1f} s "
          f"→ {total / duree_totale:.1f} req/s agrégées\n")
    for nom in noms:
        print(mesures[nom].ligne())

    erreurs = sum(
        n for m in mesures.values() for statut, n in m.statuts.items() if statut >= 400
    )
    print(f"\n  erreurs totales : {erreurs} / {total}")
    await moteur.dispose()


if __name__ == "__main__":
    asyncio.run(main())

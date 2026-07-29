"""Seeds idempotents (annexe Phase 10 §D).

- ``python -m app.seeds``       → référentiels : secteurs NACE simplifiés,
  skills tech + alias, prompt_versions v1 (inactives), sources (inactives).
- ``python -m app.seeds demo``  → données de démo (D22) : 3 profils
  synthétiques. Refusé si ENV=production (garde stricte).

Tout est en ``INSERT … ON CONFLICT DO NOTHING`` : ré-exécutable à volonté.
"""

import asyncio
import logging
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.security import hash_password

logger = logging.getLogger("boussole.seeds")

# ---------------------------------------------------------------- référentiels

# NACE simplifié (~10 sections pertinentes pour le MVP).
SECTORS: list[tuple[str, str, str]] = [
    ("C", "Industrie manufacturière", "Manufacturing"),
    ("F", "Construction", "Construction"),
    ("G", "Commerce et distribution", "Wholesale and retail trade"),
    ("H", "Transports et logistique", "Transportation and storage"),
    ("J", "Information et communication", "Information and communication"),
    ("K", "Activités financières et d'assurance", "Financial and insurance activities"),
    ("M", "Activités scientifiques et techniques", "Professional, scientific and technical"),
    ("N", "Services administratifs et de soutien", "Administrative and support services"),
    ("P", "Enseignement", "Education"),
    ("Q", "Santé humaine et action sociale", "Human health and social work"),
]

# 20 compétences tech (sous-ensemble ESCO 🟡) + alias fréquents.
SKILLS: list[str] = [
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "SQL",
    "PostgreSQL", "React", "Node.js", "Docker", "Kubernetes", "AWS", "GCP",
    "Terraform", "FastAPI", "Django", "Git", "CI/CD", "Linux",
]

SKILL_ALIASES: list[tuple[str, str]] = [
    ("py", "Python"),
    ("js", "JavaScript"),
    ("ts", "TypeScript"),
    ("golang", "Go"),
    ("postgres", "PostgreSQL"),
    ("reactjs", "React"),
    ("react.js", "React"),
    ("nodejs", "Node.js"),
    ("node", "Node.js"),
    ("k8s", "Kubernetes"),
    ("amazon web services", "AWS"),
    ("google cloud", "GCP"),
    ("google cloud platform", "GCP"),
    ("gitlab ci", "CI/CD"),
    ("github actions", "CI/CD"),
]

# v1 des 7 tâches IA (ai_task) — inactives tant que les prompts ne sont pas
# livrés (M2+). default_model : hypothèse 🟡 D08.
AI_TASKS: list[str] = [
    "extract_cv", "extract_job", "explain_match", "generate_email",
    "generate_letter", "tailor_cv", "optimize_cv",
]
DEFAULT_MODEL = "claude-sonnet-4-5"  # 🟡 hypothèse D08

# Sources inactives par défaut (D04) — activation par feature flag + fiche
# de conformité signée.
SOURCES: list[tuple[str, str, str, str, str | None]] = [
    (
        "france-travail",
        "France Travail",
        "public_api",
        "API publique conventionnée (fiche de conformité D04 à signer avant activation)",
        "https://francetravail.io/produits-partages/documentation",
    ),
    (
        "greenhouse",
        "Greenhouse Job Board",
        "ats_feed",
        "Greenhouse Job Board API — offres exposées publiquement par les employeurs (D04)",
        "https://developers.greenhouse.io/job-board.html",
    ),
    (
        "lever",
        "Lever Postings",
        "ats_feed",
        "Lever Postings API — offres exposées publiquement par les employeurs (D04)",
        "https://github.com/lever/postings-api",
    ),
    (
        # Corpus de démonstration (D34) — offres FICTIVES. Sa fiche dit ce
        # qu'il est, en toutes lettres : c'est ce texte que l'utilisateur voit
        # sur la page des sources, et il ne doit laisser aucune ambiguïté.
        "demo-corpus",
        "Corpus de démonstration (offres fictives)",
        "demo",
        "Offres INVENTÉES pour éprouver la chaîne et mesurer le matching en "
        "attendant l'homologation des sources réelles. Aucune ne correspond à "
        "un poste existant ; les liens ne résolvent pas (TLD réservé .invalid). "
        "La source refuse de s'activer hors développement.",
        None,
    ),
]


async def seed_reference_data(conn: AsyncConnection) -> None:
    """Référentiels idempotents (sectors, skills, prompt_versions, sources)."""
    for code, label_fr, label_en in SECTORS:
        await conn.execute(
            text(
                "INSERT INTO sectors (code, label_fr, label_en) "
                "VALUES (:code, :fr, :en) ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "fr": label_fr, "en": label_en},
        )

    for label in SKILLS:
        await conn.execute(
            text(
                "INSERT INTO skills (canonical_label) VALUES (:label) "
                "ON CONFLICT (canonical_label) DO NOTHING"
            ),
            {"label": label},
        )
    for alias, label in SKILL_ALIASES:
        await conn.execute(
            text(
                "INSERT INTO skill_aliases (alias, skill_id) "
                "SELECT :alias, id FROM skills WHERE canonical_label = :label "
                "ON CONFLICT (alias) DO NOTHING"
            ),
            {"alias": alias, "label": label},
        )

    for task in AI_TASKS:
        await conn.execute(
            text(
                "INSERT INTO prompt_versions (task, version, template_key, "
                "default_model, active) "
                "VALUES (:task, '1.0.0', :template_key, :model, false) "
                "ON CONFLICT (task, version) DO NOTHING"
            ),
            {"task": task, "template_key": f"prompts/{task}/v1.0.0.md", "model": DEFAULT_MODEL},
        )

    for slug, name, kind, legal_basis, terms_url in SOURCES:
        await conn.execute(
            text(
                "INSERT INTO sources (slug, name, kind, legal_basis, terms_url, active) "
                "VALUES (:slug, :name, :kind, :legal_basis, :terms_url, false) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {
                "slug": slug,
                "name": name,
                "kind": kind,
                "legal_basis": legal_basis,
                "terms_url": terms_url,
            },
        )
    logger.info("Référentiels seedés (sectors, skills, prompt_versions, sources).")


async def seed_demo(conn: AsyncConnection) -> None:
    """3 profils synthétiques (D22) — stub M1.

    Les 200 offres synthétiques et scores pré-calculés arriveront avec les
    modules ingestion/matching (M2/M3).
    """
    settings = get_settings()
    if settings.is_production:  # garde D22 — jamais en prod
        raise RuntimeError("seed-demo est interdit en production (D22)")

    demo_users = [
        ("demo-camille@boussole.dev", "Camille — dev backend Python (synthétique)"),
        ("demo-nadia@boussole.dev", "Nadia — data engineer (synthétique)"),
        ("demo-marc@boussole.dev", "Marc — dev fullstack TS (synthétique)"),
    ]
    password_hash = hash_password("boussole-demo-1234")
    for email, headline in demo_users:
        await conn.execute(
            text(
                "INSERT INTO users (email, password_hash, locale) "
                "VALUES (:email, :hash, 'fr') ON CONFLICT (email) DO NOTHING"
            ),
            {"email": email, "hash": password_hash},
        )
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, status, headline) "
                "SELECT id, 'draft', :headline FROM users WHERE email = :email "
                "ON CONFLICT (user_id) DO NOTHING"
            ),
            {"email": email, "headline": headline},
        )
    logger.info("Données de démo seedées (3 profils synthétiques).")


async def main(demo: bool) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await seed_reference_data(conn)
        if demo:
            await seed_demo(conn)
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(demo="demo" in sys.argv[1:]))

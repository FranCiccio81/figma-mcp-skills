#!/usr/bin/env python3
"""Generate the skill registry from SKILL.md frontmatter.

Writes:
  skills/registry.json                 machine-readable, read by the skill router and tools
  docs/registry/skills-registry.md     human-readable catalogue

Usage:
  python3 scripts/build_registry.py           # (re)generate both files
  python3 scripts/build_registry.py --check   # exit 1 if the committed files are stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skillslib import DOMAINS, REPO_ROOT, SKILLS_DIR, discover_skills, first_sentence, split_csv  # noqa: E402

JSON_OUT = SKILLS_DIR / "registry.json"
MD_OUT = REPO_ROOT / "docs" / "registry" / "skills-registry.md"

DOMAIN_LABELS = {
    "product": "Produit",
    "ux": "UX",
    "ui": "UI",
    "design-systems": "Design systems",
    "apple": "Apple",
    "android": "Android",
    "engineering": "Ingénierie",
    "quality": "Qualité",
    "ai-workflows": "Workflows IA et Figma",
}

TEST_LABELS = {
    "executed": "Évaluation exécutée",
    "automated": "Évaluation automatisée (tests)",
    "historical": "Preuve historique, non rejouée",
    "defined": "Évaluations définies, non exécutées",
}


def collect() -> list[dict]:
    entries = []
    for skill in discover_skills():
        fm, meta = skill.frontmatter, skill.metadata
        evals_file = skill.path / "evals" / "evals.json"
        cases = 0
        if evals_file.exists():
            cases = len(json.loads(evals_file.read_text(encoding="utf-8")).get("evals", []))
        results = skill.path / "evals" / "RESULTS.md"
        evaluation = "defined"
        if results.exists():
            first = results.read_text(encoding="utf-8").splitlines()[0]
            for key in ("executed", "automated", "historical"):
                if f"evaluation: {key}" in first:
                    evaluation = key
        entries.append(
            {
                "name": fm.get("name"),
                "domain": meta.get("domain"),
                "purpose": first_sentence(fm.get("description", "")),
                "description": " ".join(str(fm.get("description", "")).split()),
                "sources": split_csv(meta.get("sources")),
                "trust": meta.get("trust"),
                "version": meta.get("version"),
                "status": meta.get("status"),
                "platforms": split_csv(meta.get("platforms")),
                "compatibility": fm.get("compatibility", ""),
                "license": fm.get("license"),
                "last_reviewed": meta.get("last-reviewed"),
                "path": skill.rel(),
                "eval_cases": cases,
                "evaluation": evaluation,
            }
        )
    order = {d: i for i, d in enumerate(DOMAINS)}
    return sorted(entries, key=lambda e: (order.get(e["domain"], 99), e["name"] or ""))


def render_json(entries: list[dict]) -> str:
    payload = {
        "generated_by": "scripts/build_registry.py",
        "skill_count": len(entries),
        "skills": entries,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_markdown(entries: list[dict]) -> str:
    lines = [
        "# Registre des skills",
        "",
        "Fichier généré par `scripts/build_registry.py` à partir du frontmatter des skills. Ne pas modifier à la main.",
        "",
        f"**{len(entries)} skills.** Les identifiants de sources renvoient à `docs/sources/source-registry.md`.",
        "",
        "Légende des statuts : `stable` (utilisée sur un cas réel documenté), `beta` (validée structurellement, évaluations définies), `experimental`, `legacy`.",
        "",
    ]
    for domain in DOMAINS:
        rows = [e for e in entries if e["domain"] == domain]
        if not rows:
            continue
        lines += [
            f"## {DOMAIN_LABELS.get(domain, domain)}",
            "",
            "| Nom | Rôle | Sources | Confiance | Version | Statut | Compatibilité | Tests | Dernière revue |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for e in rows:
            compat = ", ".join(e["platforms"]) or "any"
            purpose = e["purpose"].replace("|", "\\|")
            lines.append(
                f"| [`{e['name']}`](../../{e['path']}/SKILL.md) | {purpose} | {', '.join(e['sources'])} | "
                f"{e['trust']} | {e['version']} | {e['status']} | {compat} | "
                f"{TEST_LABELS[e['evaluation']]} ({e['eval_cases']} cas) | {e['last_reviewed']} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the skill registry")
    parser.add_argument("--check", action="store_true", help="fail if generated files are out of date")
    args = parser.parse_args(argv)

    entries = collect()
    outputs = {JSON_OUT: render_json(entries), MD_OUT: render_markdown(entries)}
    if args.check:
        stale = [p for p, content in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != content]
        for path in stale:
            print(f"Stale: {path.relative_to(REPO_ROOT)} (run python3 scripts/build_registry.py)")
        return 1 if stale else 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

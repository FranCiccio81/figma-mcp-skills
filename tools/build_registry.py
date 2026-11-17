#!/usr/bin/env python3
"""Generate the skill registry from SKILL.md frontmatter.

Writes docs/skill-registry.md (human readable) and skills/registry.json
(machine readable, used by the skill router).

Usage:
    python3 tools/build_registry.py          # write both files
    python3 tools/build_registry.py --check  # fail if the files are out of date
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_skills import ROOT, discover, parse, section, URL_RE, host_of  # noqa: E402

MD_OUT = ROOT / "docs" / "skill-registry.md"
JSON_OUT = ROOT / "skills" / "registry.json"


def collect() -> list[dict]:
    rows = []
    for skill in discover(None):
        meta, body, problem = parse(skill / "SKILL.md")
        if problem or meta is None:
            continue
        md = meta.get("metadata") or {}
        hosts = sorted({host_of(u) for u in URL_RE.findall(section(body, "Sources"))})
        rows.append({
            "name": meta["name"],
            "domain": md.get("domain", "legacy"),
            "purpose": " ".join(str(meta.get("description", "")).split()),
            "path": str(skill.relative_to(ROOT)),
            "sources": hosts,
            "trust": md.get("trust", "authored"),
            "version": md.get("version", "1.1"),
            "status": md.get("status", "stable"),
            "scope": md.get("scope", "universal"),
            "compatibility": meta.get("compatibility", "Agent Skills compatible clients"),
            "last_reviewed": md.get("last-reviewed", "n/a"),
        })
    return sorted(rows, key=lambda r: (r["domain"], r["name"]))


def short(text: str, n: int = 110) -> str:
    first = text.split(". Use when")[0].split(" Use when")[0]
    return first if len(first) <= n else first[: n - 1].rstrip() + "…"


def render_md(rows: list[dict]) -> str:
    out = [
        "# Registre des skills",
        "",
        "Fichier généré par `python3 tools/build_registry.py`. Ne pas modifier à la main.",
        "",
        f"{len(rows)} skills.",
        "",
        "| Nom | Domaine | Rôle | Sources | Confiance | Version | Statut | Portée | Compatibilité | Revu le |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| [`{r['name']}`](../{r['path']}/SKILL.md) | {r['domain']} | {short(r['purpose'])} | "
            f"{', '.join(r['sources']) or 'n/a'} | {r['trust']} | {r['version']} | {r['status']} | "
            f"{r['scope']} | {r['compatibility']} | {r['last_reviewed']} |"
        )
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    rows = collect()
    md = render_md(rows)
    js = json.dumps({"skills": rows}, indent=2, ensure_ascii=False) + "\n"
    if "--check" in argv:
        stale = [p for p, c in ((MD_OUT, md), (JSON_OUT, js)) if not p.exists() or p.read_text(encoding="utf-8") != c]
        for p in stale:
            print(f"out of date: {p.relative_to(ROOT)} (run python3 tools/build_registry.py)")
        return 1 if stale else 0
    MD_OUT.write_text(md, encoding="utf-8")
    JSON_OUT.write_text(js, encoding="utf-8")
    print(f"wrote {len(rows)} skills to {MD_OUT.relative_to(ROOT)} and {JSON_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

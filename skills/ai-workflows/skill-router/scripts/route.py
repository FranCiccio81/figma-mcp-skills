#!/usr/bin/env python3
"""Select the skills relevant to a request, deterministically.

Reads references/routing-table.json (keywords, platform gates, precedence layers)
and prints a JSON routing decision. Standard library only, no network, no side effects.

Usage:
    python3 scripts/route.py "Design and implement an accessible banking onboarding flow for iOS"
    python3 scripts/route.py --project-ds bridge-design-system --figma "..."
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TABLE = Path(__file__).resolve().parent.parent / "references" / "routing-table.json"

# Precedence order (lower number wins in a conflict).
PRECEDENCE = {
    "safety": 1,      # safety and applicable legal requirements
    "project": 2,     # project-specific constraints and validated requirements
    "platform": 3,    # official platform guidance
    "project-ds": 4,  # established project design system
    "reusable": 5,    # relevant reusable skills
    "community": 6,   # community best practices
}


def load_table(path: Path = TABLE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def has(text: str, keyword: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def route(prompt: str, project_ds: str | None = None, figma_available: bool | None = None,
          table: dict | None = None) -> dict:
    table = table or load_table()
    text = " ".join(prompt.lower().split())

    platforms = sorted(p for p, kws in table["platforms"].items() if any(has(text, k) for k in kws))
    regulated = sorted(d for d, kws in table["regulated_domains"].items() if any(has(text, k) for k in kws))
    projects = {s for s, kws in table["project_design_systems"].items() if any(has(text, k) for k in kws)}
    if project_ds:
        projects.add(project_ds)

    selected: dict[str, dict] = {}
    excluded: list[dict] = []

    def add(name: str, reason: str) -> None:
        spec = table["skills"][name]
        layer = spec["layer"]
        if name == "accessibility-audit" and not regulated:
            layer = "reusable"
        if name in selected:
            return
        selected[name] = {"name": name, "layer": layer, "precedence": PRECEDENCE[layer], "reason": reason}

    for name, spec in table["skills"].items():
        if name == "skill-router":
            continue
        hits = [k for k in spec["keywords"] if has(text, k)]
        project = spec.get("project")
        if project:
            if project is True:  # legacy form: the skill is the project design system itself
                project = name
            if project not in projects:
                continue
            gates = spec.get("platforms")
            if gates and not set(gates) & set(platforms):
                if hits:
                    excluded.append({"name": name, "reason": f"platforms {gates} not requested"})
                continue
            if spec.get("auto") or hits:
                add(name, "project design system in use" + (": matched " + ", ".join(hits[:4]) if hits else ""))
            continue
        if not hits:
            continue
        gate = spec.get("platform")
        if gate and gate not in platforms:
            excluded.append({"name": name, "reason": f"platform '{gate}' not requested"})
            continue
        add(name, "matched: " + ", ".join(hits[:4]))

    implementing = any(has(text, k) for k in table["implementation_intents"])
    if implementing:
        for platform in platforms:
            add(table["testing_by_platform"][platform], f"testing for {platform} implementation")

    notes = []
    for domain in regulated:
        notes.append(
            f"Regulated domain detected ({domain}): confirm applicable legal and accessibility "
            "requirements with the user; they take precedence over every skill."
        )
    if regulated and "accessibility-audit" not in selected:
        add("accessibility-audit", "regulated domain: accessibility treated as a requirement")
    if figma_available is False:
        for name in table["requires_figma"]:
            if name in selected:
                selected[name]["reason"] += " (Figma MCP unavailable: use the documented fallback)"
    if not platforms and implementing:
        notes.append("No platform stated: ask which platform before selecting implementation skills.")
    if len(platforms) > 1:
        notes.append("Several platforms requested: keep platform conventions separate; do not port patterns directly.")

    skills = sorted(selected.values(), key=lambda s: (s["precedence"], s["name"]))
    return {
        "platforms": platforms,
        "regulated_domains": regulated,
        "skills": skills,
        "excluded": sorted(excluded, key=lambda e: e["name"]),
        "precedence": [k for k, _ in sorted(PRECEDENCE.items(), key=lambda kv: kv[1])],
        "notes": notes,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Route a request to skills.")
    ap.add_argument("prompt")
    ap.add_argument("--project-ds", help="name of the project design system skill in use")
    ap.add_argument("--figma", dest="figma", action="store_true", default=None, help="Figma MCP available")
    ap.add_argument("--no-figma", dest="figma", action="store_false", help="Figma MCP not available")
    args = ap.parse_args(argv)
    print(json.dumps(route(args.prompt, args.project_ds, args.figma), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

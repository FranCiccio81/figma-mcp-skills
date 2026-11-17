#!/usr/bin/env python3
"""Deterministic skill routing from a request text.

Reads references/routing-table.json next to this script. Standard library only,
no network, no execution of other files.

Usage:
  python3 route.py "Design and implement an accessible banking onboarding flow for iOS"
  python3 route.py --json "Audit our React checkout for WCAG"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TABLE_PATH = Path(__file__).resolve().parent.parent / "references" / "routing-table.json"


def load_table(path: Path = TABLE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains(text: str, keyword: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(keyword.lower())
    if keyword[-1].isalnum():
        pattern += r"(?![a-z0-9])" if len(keyword) <= 4 else ""
    return re.search(pattern, text) is not None


def detect_platforms(text: str, table: dict) -> list[str]:
    found = []
    for platform, keywords in table["platforms"].items():
        if any(_contains(text, k) for k in keywords):
            found.append(platform)
    return found


def route(request: str, table: dict | None = None) -> dict:
    table = table or load_table()
    text = request.lower()
    platforms = detect_platforms(text, table)
    families = set()
    for platform in platforms:
        families.add("apple" if platform in table["apple_platforms"] else platform)

    phase_rank = {phase: i for i, phase in enumerate(table["phases"])}
    selected: dict[str, dict] = {}
    excluded: dict[str, str] = {}
    implementation_hit = False

    for intent in table["intents"]:
        if not any(_contains(text, k) for k in intent["keywords"]):
            continue
        if intent["id"] == "implementation":
            implementation_hit = True
        for skill in intent.get("skills", []):
            selected.setdefault(skill, {"phase": intent["phase"], "reason": intent["reason"]})
        for family, skills in intent.get("platform_skills", {}).items():
            for skill in skills:
                if family in families:
                    selected.setdefault(skill, {"phase": intent["phase"], "reason": intent["reason"]})
                else:
                    excluded.setdefault(skill, f"platform '{family}' not targeted")

    if implementation_hit:
        for intent in table["intents"]:
            if intent["id"] == "platform-design":
                for family, skills in intent["platform_skills"].items():
                    if family in families:
                        for skill in skills:
                            selected.setdefault(skill, {"phase": intent["phase"], "reason": intent["reason"]})

    for skill in list(excluded):
        if skill in selected:
            del excluded[skill]

    ordered = sorted(selected.items(), key=lambda item: phase_rank[item[1]["phase"]])
    needs_platform = implementation_hit and not platforms
    return {
        "platforms": platforms,
        "project_context_first": ["CLAUDE.md", ".claude/CLAUDE.md", "rules/"],
        "skills": [{"name": name, **info} for name, info in ordered],
        "excluded": [{"name": name, "reason": reason} for name, reason in sorted(excluded.items())],
        "ask_platform": needs_platform,
        "precedence": table["precedence"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route a request to skills")
    parser.add_argument("request")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    plan = route(args.request)
    if args.json:
        print(json.dumps(plan, indent=2))
        return 0
    print("Project context: " + ", ".join(plan["project_context_first"]))
    print("Platforms: " + (", ".join(plan["platforms"]) or "none detected"))
    if plan["ask_platform"]:
        print("Ask the user which platform to target before implementing.")
    for i, skill in enumerate(plan["skills"], 1):
        print(f"{i}. {skill['name']}: {skill['reason']}")
    if plan["excluded"]:
        print("Excluded: " + ", ".join(f"{e['name']} ({e['reason']})" for e in plan["excluded"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Keep the Bridge foundations reference identical in every Bridge skill.

Single source: skills/bridge/_shared/bridge-foundations.md
Copies:        skills/bridge/<skill>/references/bridge-foundations.md

Each skill carries its own copy so it still works when installed alone
(Agent Skills load files relative to the skill folder). This script prevents drift.

Usage:
    python3 tools/sync_bridge_foundations.py          # copy the source into every Bridge skill
    python3 tools/sync_bridge_foundations.py --check  # fail if any copy differs or is missing
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "skills" / "bridge"
SOURCE = BRIDGE / "_shared" / "bridge-foundations.md"


def targets() -> list[Path]:
    return sorted(p.parent / "references" / "bridge-foundations.md"
                  for p in BRIDGE.glob("*/SKILL.md")
                  if "bridge-foundations.md" in p.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    source = SOURCE.read_text(encoding="utf-8")
    stale = [t for t in targets() if not t.exists() or t.read_text(encoding="utf-8") != source]
    if "--check" in argv:
        for t in stale:
            print(f"out of sync: {t.relative_to(ROOT)} (run python3 tools/sync_bridge_foundations.py)")
        return 1 if stale else 0
    for t in stale:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(source, encoding="utf-8")
        print(f"updated {t.relative_to(ROOT)}")
    print(f"{len(targets())} copies in sync with {SOURCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

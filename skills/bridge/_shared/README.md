# Bridge shared reference

`bridge-foundations.md` is the single source of the Bridge 2.0 foundations snapshot (tokens, themes, formats, principles, open governance questions, exact colour token index), read from Figma on 12 November 2026.

Every Bridge skill carries a copy in `references/bridge-foundations.md` so it works when installed alone. Never edit a copy:

1. Edit `skills/bridge/_shared/bridge-foundations.md`.
2. Run `python3 tools/sync_bridge_foundations.py`.
3. The CI fails if a copy differs (`--check`).

Longer term (Governance decision of November 2026): generate this file from the Bridge token manifest in the Bridge package so values never drift.

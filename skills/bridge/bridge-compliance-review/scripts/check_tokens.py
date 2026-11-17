#!/usr/bin/env python3
"""Check Bridge colour token names against the exact-name index.

Reads section 12 ("Colour token index") of references/bridge-foundations.md, turns
its patterns into regular expressions, then reports every colour token name found in
the given files that the index does not allow. Standard library only; reads files,
writes nothing.

Usage:
    python3 scripts/check_tokens.py path/to/spec.md src/Button.tsx ...
    cat handoff.md | python3 scripts/check_tokens.py -
    python3 scripts/check_tokens.py --index other/bridge-foundations.md file ...

Exit code 0 when every name is known, 1 when unknown names were found.
Scope: colour tokens in slash form (`color/text/neutral/default` or `text/neutral/default`).
Size, typography and mobile tokens are not checked.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_INDEX = Path(__file__).resolve().parent.parent / "references" / "bridge-foundations.md"
ROLES = ("background", "text", "icon", "border", "action", "control", "feedback", "utility", "data", "shadow")
CANDIDATE = re.compile(
    r"(?<![\w/-])(?:color/)?((?:%s)/[a-z0-9][a-z0-9/-]*[a-z0-9])(?![\w/{|\[*-])" % "|".join(ROLES)
)


def _range(m: re.Match) -> str:
    a, b = m.group(1), m.group(2)
    width = len(a)
    return "{" + "|".join(str(i).zfill(width) for i in range(int(a), int(b) + 1)) + "}"


def to_regex(pattern: str) -> str:
    pattern = re.sub(r"(\d+)\.\.(\d+)", _range, pattern)
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "{":
            j = pattern.index("}", i)
            body = pattern[i + 1:j]
            out.append("[a-z0-9-]+" if "|" not in body else "(?:" + "|".join(map(re.escape, body.split("|"))) + ")")
            i = j + 1
        elif c == "[":
            depth, j = 1, i + 1
            while depth:
                depth += {"[": 1, "]": -1}.get(pattern[j], 0)
                j += 1
            out.append("(?:" + to_regex(pattern[i + 1:j - 1]) + ")?")
            i = j
        elif c == "*":
            out.append("[a-z0-9/-]+")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def load_index(path: Path) -> list[re.Pattern]:
    text = path.read_text(encoding="utf-8")
    start = text.index("## 12.")
    lines = text[start:].splitlines()
    patterns: list[str] = []
    in_index = False
    for line in lines:
        stripped = line.strip()
        if stripped in ROLES or stripped == "data, utility, shadow":
            in_index = True
            continue
        if not in_index or not stripped.startswith("- "):
            continue
        segments = re.findall(r"`([^`]+)`", stripped)
        full = [s.removeprefix("color/") for s in segments if "/" in s and s.removeprefix("color/").split("/")[0] in ROLES]
        if not full:
            continue
        family = full[0].rsplit("/", 1)[0] + "/"
        suffixes = [s for s in segments if s.startswith("-")]
        fragments = [family + s for s in segments if "/" not in s and not s.startswith("-")]
        for p in full + fragments:
            regex = to_regex(p)
            if suffixes:
                regex += "(?:" + "|".join(map(re.escape, suffixes)) + ")?"
            patterns.append(regex)
    # Tokens named in the tables of section 3 that the index summarises
    patterns += [re.escape(t) for t in ("data/up", "data/down")]
    return [re.compile(rf"^{p}$") for p in patterns]


def unknown_names(text: str, index: list[re.Pattern]) -> list[str]:
    found = sorted({m.group(1) for m in CANDIDATE.finditer(text)})
    return [n for n in found if not any(p.match(n) for p in index)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="files to check, or - for stdin")
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    args = ap.parse_args(argv)
    index = load_index(args.index)
    bad = 0
    for f in args.files:
        text = sys.stdin.read() if f == "-" else Path(f).read_text(encoding="utf-8", errors="ignore")
        for name in unknown_names(text, index):
            print(f"{f}: unknown colour token: color/{name}")
            bad += 1
    print(f"{bad} unknown colour token name(s); index has {len(index)} patterns")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Validate every skill in this repository.

Implements the Agent Skills specification rules
(https://github.com/agentskills/agentskills, docs/specification.mdx)
plus this repository's quality gates (see docs/architecture/skill-architecture.md).

Usage:
    python3 tools/validate_skills.py              # validate all skills
    python3 tools/validate_skills.py --external   # also check external links (network)
    python3 tools/validate_skills.py path/to/skill [...]

Exit code 0 when no error was found, 1 otherwise. Warnings never fail the run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOTS = [ROOT / "skills", ROOT / ".claude" / "skills"]
SOURCE_REGISTRY = ROOT / "docs" / "sources" / "source-registry.md"

SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOMAINS = {"product", "ux", "design-systems", "apple", "android", "engineering", "quality", "ai-workflows", "bridge"}
STATUSES = {"stable", "beta", "deprecated"}
SCOPES = {"universal", "project"}
TRUST = {"authored", "official-derived", "project-specific"}
# Required sections and the heading patterns accepted for each (imported skills use
# "Step N: ..." for the procedure, "Output format(s)" and "Final check").
REQUIRED_SECTIONS = {
    "When to use": r"When to use",
    "Inputs": r"Inputs",
    "Procedure": r"(Procedure|Step 1\b.*)",
    "Output": r"(Output|Output formats?)",
    "Edge cases": r"Edge cases",
    "Acceptance criteria": r"(Acceptance criteria|Final check)",
    "Sources": r"Sources(, in order of authority)?",
}
MAX_LINES = 500
WARN_LINES = 300

SECURITY_PATTERNS = [
    (re.compile(r"(curl|wget)[^\n|]*\|\s*(ba|z)?sh\b"), "pipes a download into a shell"),
    (re.compile(r"ignore (all )?(previous|prior) instructions", re.I), "prompt-injection phrase"),
    (re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16})\b"), "looks like a secret"),
    (re.compile(r"rm\s+-rf\s+/(\s|$)"), "destructive command"),
]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
URL_RE = re.compile(r"https?://[^\s)>\]`'\"]+")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"ERROR   {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"WARNING {where}: {msg}")


def discover(paths: list[str] | None) -> list[Path]:
    if paths:
        return [Path(p).resolve() for p in paths]
    found = []
    for root in SKILL_ROOTS:
        if root.exists():
            found += [p.parent for p in root.rglob("SKILL.md")]
    return sorted(found)


def parse(skill_md: Path) -> tuple[dict | None, str, str | None]:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, text, "SKILL.md must start with YAML frontmatter (---)"
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, "frontmatter is not closed"
    try:
        meta = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        return None, text, f"invalid YAML: {exc}"
    if not isinstance(meta, dict):
        return None, text, "frontmatter must be a mapping"
    body = text[end + 4:].lstrip("\n")
    return meta, body, None


def registry_hosts() -> set[str]:
    if not SOURCE_REGISTRY.exists():
        return set()
    hosts = set()
    for url in URL_RE.findall(SOURCE_REGISTRY.read_text(encoding="utf-8")):
        hosts.add(host_of(url))
    return hosts


def host_of(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    return host[4:] if host.startswith("www.") else host


def section(body: str, title: str) -> str:
    pattern = REQUIRED_SECTIONS.get(title, re.escape(title))
    m = re.search(rf"^## (?:{pattern})\s*$(?P<body>.*?)(?=^## |\Z)", body, re.M | re.S)
    return m.group("body") if m else ""


def check_spec(where: str, skill: Path, meta: dict, rep: Report) -> None:
    unknown = set(meta) - SPEC_FIELDS
    if unknown:
        rep.err(where, f"fields not in the Agent Skills spec: {sorted(unknown)}")
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        rep.err(where, "missing 'name'")
    else:
        name = unicodedata.normalize("NFKC", name)
        if len(name) > 64:
            rep.err(where, "name longer than 64 characters")
        if not NAME_RE.match(name):
            rep.err(where, f"invalid name '{name}' (lowercase letters, digits, single hyphens)")
        if name != skill.name:
            rep.err(where, f"name '{name}' does not match directory '{skill.name}'")
    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        rep.err(where, "missing 'description'")
    elif len(desc) > 1024:
        rep.err(where, f"description is {len(desc)} characters (max 1024)")
    comp = meta.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or not 1 <= len(comp) <= 500):
        rep.err(where, "compatibility must be a 1-500 character string")
    md = meta.get("metadata")
    if md is not None:
        if not isinstance(md, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in md.items()):
            rep.err(where, "metadata must map strings to strings (quote versions and dates)")


def check_repo_rules(where: str, skill: Path, meta: dict, body: str, rep: Report, legacy: bool) -> None:
    desc = meta.get("description") or ""
    if not any(k in desc.lower() for k in ("use when", "use this skill when", "use this skill for", "use this skill whenever")):
        (rep.warn if legacy else rep.err)(where, "description must say WHEN to use the skill ('Use when ...' or 'Use this skill for/when ...')")
    if not meta.get("license") and (ROOT / "LICENSE").exists():
        rep.warn(where, "no license declared in frontmatter")
    if legacy:
        return
    md = {k: str(val) for k, val in (meta.get("metadata") or {}).items()} if isinstance(meta.get("metadata"), dict) else {}
    domain = md.get("domain")
    if domain not in DOMAINS:
        rep.err(where, f"metadata.domain must be one of {sorted(DOMAINS)}")
    elif skill.parent.name != domain:
        rep.err(where, f"metadata.domain '{domain}' does not match parent folder '{skill.parent.name}'")
    if not SEMVER_RE.match(md.get("version", "")):
        rep.err(where, "metadata.version must be SemVer, e.g. \"1.0.0\"")
    if md.get("status") not in STATUSES:
        rep.err(where, f"metadata.status must be one of {sorted(STATUSES)}")
    if md.get("scope") not in SCOPES:
        rep.err(where, f"metadata.scope must be one of {sorted(SCOPES)}")
    if md.get("trust") not in TRUST:
        rep.err(where, f"metadata.trust must be one of {sorted(TRUST)}")
    if not DATE_RE.match(md.get("last-reviewed", "")):
        rep.err(where, "metadata.last-reviewed must be YYYY-MM-DD")
    for title, pattern in REQUIRED_SECTIONS.items():
        if not re.search(rf"^## (?:{pattern})\s*$", body, re.M):
            rep.err(where, f"missing section '## {title}'")


def check_links(where: str, skill: Path, body: str, rep: Report, hosts: set[str], external: bool, legacy: bool) -> None:
    for target in LINK_RE.findall(body):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = (skill / target.split("#")[0]).resolve()
        if not path.exists():
            rep.err(where, f"broken relative link: {target}")
        elif target.count("/") > 1 and not legacy:
            rep.warn(where, f"reference deeper than one level: {target}")
    if legacy:
        return
    sources = section(body, "Sources")
    urls = URL_RE.findall(sources)
    if not urls:
        rep.err(where, "Sources section has no URL")
    for url in urls:
        if host_of(url) not in hosts:
            rep.err(where, f"source host not in docs/sources/source-registry.md: {host_of(url)}")
    if external:
        for url in sorted(set(URL_RE.findall(body))):
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "skills-validator"})
                urllib.request.urlopen(req, timeout=15)
            except Exception as exc:  # noqa: BLE001 - report any failure
                rep.warn(where, f"external link not reachable: {url} ({exc})")


def check_security(where: str, skill: Path, rep: Report) -> None:
    for f in skill.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in {".md", ".py", ".sh", ".js", ".json", ".ts", ".yml", ".yaml"}:
            continue
        if "legacy-guide" in f.name:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in SECURITY_PATTERNS:
            if pattern.search(text):
                rep.err(where, f"security: {label} in {f.relative_to(skill)}")
    scripts = skill / "scripts"
    if scripts.exists():
        md = (skill / "SKILL.md").read_text(encoding="utf-8")
        for f in scripts.iterdir():
            if f.is_file() and f.name not in md and not f.name.startswith("__"):
                rep.err(where, f"script not documented in SKILL.md: scripts/{f.name}")


def check_evals(where: str, skill: Path, name: str, rep: Report, legacy: bool) -> None:
    path = skill / "evals" / "evals.json"
    if not path.exists():
        (rep.warn if legacy else rep.err)(where, "missing evals/evals.json (at least one realistic use case)")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rep.err(where, f"evals.json is not valid JSON: {exc}")
        return
    if data.get("skill_name") != name:
        rep.err(where, "evals.json skill_name does not match the skill name")
    evals = data.get("evals") or []
    if not evals:
        rep.err(where, "evals.json has no eval")
    ids = set()
    for ev in evals:
        eid = ev.get("id")
        if not isinstance(eid, int) or eid in ids:
            rep.err(where, f"eval id must be a unique integer (got {eid!r})")
        ids.add(eid)
        if not str(ev.get("prompt", "")).strip():
            rep.err(where, f"eval {eid}: empty prompt")
        if not str(ev.get("expected_output", "")).strip():
            rep.err(where, f"eval {eid}: empty expected_output")
        if len(ev.get("expectations") or []) < 2:
            rep.err(where, f"eval {eid}: needs at least two verifiable expectations")


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--external", action="store_true", help="check external links (needs network)")
    args = ap.parse_args(argv)

    rep = Report()
    hosts = registry_hosts()
    seen: dict[str, Path] = {}
    descs: dict[str, set[str]] = {}
    skills = discover(args.paths)
    if not (ROOT / "LICENSE").exists():
        rep.warn("repository", "no LICENSE file at the repository root")

    for skill in skills:
        where = str(skill.relative_to(ROOT)) if skill.is_relative_to(ROOT) else str(skill)
        md = skill / "SKILL.md"
        if not md.exists():
            rep.err(where, "SKILL.md not found")
            continue
        meta, body, problem = parse(md)
        if problem:
            rep.err(where, problem)
            continue
        legacy = ".claude" in skill.parts  # historical skill kept in place; spec rules only
        check_spec(where, skill, meta, rep)
        check_repo_rules(where, skill, meta, body, rep, legacy)
        lines = md.read_text(encoding="utf-8").count("\n") + 1
        if lines > MAX_LINES:
            rep.err(where, f"SKILL.md has {lines} lines (max {MAX_LINES}); move detail to references/")
        elif lines > WARN_LINES:
            rep.warn(where, f"SKILL.md has {lines} lines; consider moving detail to references/")
        check_links(where, skill, body, rep, hosts, args.external, legacy)
        check_security(where, skill, rep)
        name = meta.get("name", skill.name)
        check_evals(where, skill, name, rep, legacy)
        if name in seen:
            rep.err(where, f"duplicate skill name, also defined in {seen[name].relative_to(ROOT)}")
        seen[name] = skill
        descs[name] = tokens(meta.get("description", ""))

    names = sorted(descs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            union = descs[a] | descs[b]
            if union and len(descs[a] & descs[b]) / len(union) > 0.5:
                rep.warn(f"{a} / {b}", "descriptions overlap strongly; check for duplicated responsibility")

    for line in rep.warnings + rep.errors:
        print(line)
    print(f"\n{len(skills)} skills checked: {len(rep.errors)} errors, {len(rep.warnings)} warnings")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

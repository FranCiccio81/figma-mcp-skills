#!/usr/bin/env python3
"""Validate every skill under skills/ against the quality gates.

Gates (see docs/architecture/skill-architecture.md):
  1. Agent Skills specification (mirrors agentskills/skills-ref rules)
  2. Frontmatter and metadata conventions of this repository
  3. Reference links (relative files must exist)
  4. Source provenance (source IDs and URL domains declared in the registry)
  5. Duplicate detection (names, near-identical descriptions)
  6. Security review (dangerous commands, prompt injection, secrets)
  7. Licensing (license field present)
  8. Evaluations (evals/evals.json with at least one realistic case)
  9. Documentation completeness (required sections, size budget)

Usage:
  python3 scripts/validate_skills.py            # human report, exit 1 on error
  python3 scripts/validate_skills.py --json     # machine-readable report
  python3 scripts/validate_skills.py --strict   # warnings also fail

The script only reads files. It never executes skill content.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skillslib import (  # noqa: E402
    DOMAINS,
    REPO_ROOT,
    SKILLS_DIR,
    Skill,
    discover_skills,
    load_config,
    load_source_registry,
    split_csv,
)

# Gate 1: Agent Skills specification -------------------------------------
SPEC_ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500
MAX_BODY_LINES = 500  # spec recommendation, enforced here
TARGET_BODY_LINES = 250

# Gate 2: repository conventions -----------------------------------------
REQUIRED_METADATA = ("version", "domain", "status", "trust", "sources", "platforms", "last-reviewed")
STATUSES = {"experimental", "beta", "stable", "legacy"}
TRUST_LEVELS = {"internal", "official-derived", "community-derived"}
PLATFORMS = {"any", "web", "ios", "ipados", "macos", "watchos", "visionos", "tvos", "android"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
REQUIRED_SECTIONS = (
    "When to use",
    "Inputs",
    "Workflow",
    "Outputs",
    "Edge cases",
    "Acceptance criteria",
    "Sources",
)

# Gate 6: security patterns ----------------------------------------------
SECURITY_PATTERNS = [
    (re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b", re.I), "pipes a download into a shell"),
    (re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(ba)?sh", re.I), "decodes and executes a payload"),
    (re.compile(r"\brm\s+-rf\s+(/|~|\$HOME)(\s|$)", re.I), "destructive rm -rf on a root or home path"),
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I), "prompt-injection phrase"),
    (re.compile(r"disregard\s+(the\s+)?(system|previous)\s+(prompt|instructions)", re.I), "prompt-injection phrase"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic API key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"\bfigd_[A-Za-z0-9_-]{20,}"), "Figma personal access token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
]
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt", ".py", ".sh", ".js", ".ts", ".tsx", ".kt", ".swift"}

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
URL_RE = re.compile(r"https?://[^\s)>\]`\"']+")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, level: str, gate: str, skill: str, message: str) -> None:
        self.items.append({"level": level, "gate": gate, "skill": skill, "message": message})

    def error(self, gate: str, skill: str, message: str) -> None:
        self.add("error", gate, skill, message)

    def warn(self, gate: str, skill: str, message: str) -> None:
        self.add("warning", gate, skill, message)

    @property
    def errors(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "error"]

    @property
    def warnings(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "warning"]


# --------------------------------------------------------------------------
def check_spec(skill: Skill, report: Report) -> None:
    sid = skill.rel()
    if skill.parse_error:
        report.error("spec", sid, skill.parse_error)
        return
    fm = skill.frontmatter
    extra = set(fm) - SPEC_ALLOWED_FIELDS
    if extra:
        report.error("spec", sid, f"Unexpected frontmatter fields: {', '.join(sorted(extra))}")

    name = fm.get("name")
    if not isinstance(name, str) or not name.strip():
        report.error("spec", sid, "Field 'name' must be a non-empty string")
    else:
        name = unicodedata.normalize("NFKC", name.strip())
        if len(name) > MAX_NAME:
            report.error("spec", sid, f"Name exceeds {MAX_NAME} characters")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            report.error("spec", sid, f"Name '{name}' must use lowercase letters, digits and single hyphens")
        if name != skill.dir_name:
            report.error("spec", sid, f"Directory '{skill.dir_name}' must match name '{name}'")

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        report.error("spec", sid, "Field 'description' must be a non-empty string")
    elif len(desc) > MAX_DESCRIPTION:
        report.error("spec", sid, f"Description exceeds {MAX_DESCRIPTION} characters ({len(desc)})")

    if "compatibility" in fm:
        comp = fm["compatibility"]
        if not isinstance(comp, str) or not comp.strip() or len(comp) > MAX_COMPATIBILITY:
            report.error("spec", sid, f"'compatibility' must be a 1-{MAX_COMPATIBILITY} character string")

    meta = fm.get("metadata")
    if meta is not None:
        if not isinstance(meta, dict):
            report.error("spec", sid, "'metadata' must be a mapping")
        else:
            for key, value in meta.items():
                if not isinstance(value, str):
                    report.error("spec", sid, f"metadata.{key} must be a string (spec: string-to-string map)")

    if "allowed-tools" in fm and not isinstance(fm["allowed-tools"], str):
        report.error("spec", sid, "'allowed-tools' must be a space-separated string")


def check_conventions(skill: Skill, report: Report, source_ids: set[str]) -> None:
    sid = skill.rel()
    fm, meta = skill.frontmatter, skill.metadata
    desc = str(fm.get("description", ""))
    if desc and "use when" not in desc.lower():
        report.error("frontmatter", sid, "Description must state when to use the skill ('Use when ...')")
    if desc and len(desc) < 80:
        report.warn("frontmatter", sid, "Description is very short; add trigger keywords")

    for key in REQUIRED_METADATA:
        if key not in meta:
            report.error("frontmatter", sid, f"Missing metadata.{key}")
    if "version" in meta and not SEMVER_RE.match(str(meta["version"])):
        report.error("frontmatter", sid, "metadata.version must be SemVer (MAJOR.MINOR.PATCH)")
    if "domain" in meta:
        if meta["domain"] not in DOMAINS:
            report.error("frontmatter", sid, f"metadata.domain '{meta['domain']}' is not one of {DOMAINS}")
        elif meta["domain"] != skill.domain_dir:
            report.error("frontmatter", sid, f"metadata.domain must equal parent folder '{skill.domain_dir}'")
    if "status" in meta and meta["status"] not in STATUSES:
        report.error("frontmatter", sid, f"metadata.status must be one of {sorted(STATUSES)}")
    if "trust" in meta and meta["trust"] not in TRUST_LEVELS:
        report.error("frontmatter", sid, f"metadata.trust must be one of {sorted(TRUST_LEVELS)}")
    for platform in split_csv(meta.get("platforms")):
        if platform not in PLATFORMS:
            report.error("frontmatter", sid, f"Unknown platform '{platform}'")
    if "last-reviewed" in meta:
        try:
            reviewed = dt.date.fromisoformat(str(meta["last-reviewed"]))
            if (dt.date.today() - reviewed).days > 183:
                report.warn("provenance", sid, f"Sources last reviewed {reviewed}; review is due (6 months)")
        except ValueError:
            report.error("frontmatter", sid, "metadata.last-reviewed must be an ISO date")

    sources = split_csv(meta.get("sources"))
    if "sources" in meta and not sources:
        report.error("provenance", sid, "metadata.sources must list at least one source ID")
    for source in sources:
        if source not in source_ids:
            report.error("provenance", sid, f"Source ID '{source}' is not declared in docs/sources/source-registry.md")

    if not fm.get("license"):
        report.error("licensing", sid, "Missing 'license' field")


def iter_text_files(skill: Skill):
    for path in sorted(skill.path.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def check_links(skill: Skill, report: Report, allowed_domains: set[str]) -> None:
    sid = skill.rel()
    for path in iter_text_files(skill):
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for target in MD_LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                report.error("links", sid, f"{path.relative_to(skill.path)} links to missing file '{target}'")
            elif skill.path.resolve() not in resolved.parents and resolved != skill.path.resolve():
                report.warn("links", sid, f"{path.relative_to(skill.path)} links outside the skill folder: '{target}'")
        for url in URL_RE.findall(text):
            host = (urlparse(url).hostname or "").lower()
            if host in {"127.0.0.1", "localhost"}:
                continue
            if not any(host == d or host.endswith("." + d) for d in allowed_domains):
                report.error("provenance", sid, f"{path.relative_to(skill.path)}: domain '{host}' is not in the source registry allowlist")


def check_security(skill: Skill, report: Report, config: dict) -> None:
    sid = skill.rel()
    for path in iter_text_files(skill):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in SECURITY_PATTERNS:
            if pattern.search(text):
                report.error("security", sid, f"{path.relative_to(skill.path)}: {label}")
    scripts_dir = skill.path / "scripts"
    if scripts_dir.exists():
        reviewed = set(config.get("reviewed_scripts", []))
        for script in sorted(
            p for p in scripts_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ):
            try:
                rel = str(script.relative_to(REPO_ROOT))
            except ValueError:
                rel = str(script)
            if rel not in reviewed:
                report.error("security", sid, f"Script '{rel}' is not listed in skills/.validator.json reviewed_scripts")


def check_evals(skill: Skill, report: Report) -> None:
    sid = skill.rel()
    evals_file = skill.path / "evals" / "evals.json"
    if not evals_file.exists():
        report.error("evaluation", sid, "Missing evals/evals.json (at least one realistic case)")
        return
    try:
        data = json.loads(evals_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error("evaluation", sid, f"evals/evals.json is not valid JSON: {exc}")
        return
    if data.get("skill_name") != skill.frontmatter.get("name"):
        report.error("evaluation", sid, "evals.json skill_name must equal the skill name")
    cases = data.get("evals")
    if not isinstance(cases, list) or not cases:
        report.error("evaluation", sid, "evals.json must contain a non-empty 'evals' list")
        return
    for case in cases:
        cid = case.get("id", "?")
        for key in ("prompt", "expected_output"):
            if not isinstance(case.get(key), str) or len(case.get(key, "")) < 20:
                report.error("evaluation", sid, f"Case {cid}: '{key}' must be a realistic text (>= 20 chars)")
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or len(assertions) < 2:
            report.error("evaluation", sid, f"Case {cid}: needs at least two assertions")


def check_completeness(skill: Skill, report: Report, config: dict) -> None:
    sid = skill.rel()
    lines = skill.body.count("\n") + 1
    if lines > MAX_BODY_LINES:
        report.error("documentation", sid, f"SKILL.md body has {lines} lines (max {MAX_BODY_LINES}); move detail to references/")
    elif lines > TARGET_BODY_LINES:
        report.warn("documentation", sid, f"SKILL.md body has {lines} lines (target < {TARGET_BODY_LINES})")
    if skill.frontmatter.get("name") in config.get("structure_exempt", {}):
        return
    headings = HEADING_RE.findall(skill.body)
    positions = []
    for section in REQUIRED_SECTIONS:
        matches = [i for i, h in enumerate(headings) if h.lower().startswith(section.lower())]
        if not matches:
            report.error("documentation", sid, f"Missing required section '## {section}'")
        else:
            positions.append(matches[0])
    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions):
        report.warn("documentation", sid, "Required sections are not in the recommended order")
    if "- [ ]" not in skill.body:
        report.warn("documentation", sid, "Acceptance criteria should be a checklist ('- [ ] ...')")


def check_duplicates(skills: list[Skill], report: Report) -> None:
    seen: dict[str, str] = {}
    for skill in skills:
        name = skill.frontmatter.get("name")
        if not name:
            continue
        if name in seen:
            report.error("duplicates", skill.rel(), f"Name '{name}' already used by {seen[name]}")
        seen[name] = skill.rel()
    descs = [(s.rel(), str(s.frontmatter.get("description", ""))) for s in skills]
    for i, (a_id, a) in enumerate(descs):
        for b_id, b in descs[i + 1 :]:
            if a and b and difflib.SequenceMatcher(None, a, b).ratio() > 0.85:
                report.warn("duplicates", a_id, f"Description nearly identical to {b_id}")


def validate(skills_dir: Path = SKILLS_DIR, registry: Path | None = None) -> tuple[list[Skill], Report]:
    report = Report()
    config = load_config()
    kwargs = {"path": registry} if registry else {}
    source_ids, domains = load_source_registry(**kwargs)
    skills = discover_skills(skills_dir)
    if not skills:
        report.error("discovery", str(skills_dir), "No skills found")
    for skill in skills:
        check_spec(skill, report)
        if skill.parse_error:
            continue
        check_conventions(skill, report, source_ids)
        check_links(skill, report, domains)
        check_security(skill, report, config)
        check_evals(skill, report)
        check_completeness(skill, report, config)
    check_duplicates(skills, report)
    return skills, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--skills-dir", type=Path, default=SKILLS_DIR)
    args = parser.parse_args(argv)

    skills, report = validate(args.skills_dir)
    if args.json:
        print(json.dumps({"skills": len(skills), "items": report.items}, indent=2))
    else:
        for item in report.items:
            print(f"[{item['level'].upper():7}] {item['gate']:13} {item['skill']}: {item['message']}")
        print(f"\n{len(skills)} skills checked, {len(report.errors)} errors, {len(report.warnings)} warnings")
    failed = bool(report.errors) or (args.strict and bool(report.warnings))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

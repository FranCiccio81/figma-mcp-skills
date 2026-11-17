"""Shared helpers for the skills library tooling.

Standard library plus PyYAML only. Nothing here touches the network or
executes content found in skill folders.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SOURCE_REGISTRY = REPO_ROOT / "docs" / "sources" / "source-registry.md"
CONFIG_FILE = SKILLS_DIR / ".validator.json"

DOMAINS = (
    "product",
    "ux",
    "ui",
    "design-systems",
    "apple",
    "android",
    "engineering",
    "quality",
    "ai-workflows",
)


@dataclass
class Skill:
    path: Path  # skill directory
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    parse_error: str | None = None

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def dir_name(self) -> str:
        return self.path.name

    @property
    def domain_dir(self) -> str:
        return self.path.parent.name

    @property
    def metadata(self) -> dict:
        meta = self.frontmatter.get("metadata") or {}
        return meta if isinstance(meta, dict) else {}

    def rel(self, root: Path | None = None) -> str:
        base = root or REPO_ROOT
        try:
            return str(self.path.relative_to(base))
        except ValueError:
            return str(self.path)


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def parse_skill(skill_dir: Path) -> Skill:
    skill = Skill(path=skill_dir)
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        skill.parse_error = "SKILL.md must start with YAML frontmatter delimited by '---'"
        skill.body = text
        return skill
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:  # pragma: no cover - message passthrough
        skill.parse_error = f"Invalid YAML frontmatter: {exc}"
        return skill
    if not isinstance(data, dict):
        skill.parse_error = "Frontmatter must be a YAML mapping"
        return skill
    skill.frontmatter = data
    skill.body = match.group(2)
    return skill


def discover_skills(skills_dir: Path = SKILLS_DIR) -> list[Skill]:
    """Return every skill under skills/, sorted by path.

    Symlinked directories are ignored so that a link never counts as a
    second copy of the same skill.
    """
    found = []
    for root, dirs, files in os.walk(skills_dir, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != "fixtures" and not d.startswith("."))
        if "SKILL.md" in files:
            found.append(parse_skill(Path(root)))
    return sorted(found, key=lambda s: str(s.path))


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


SOURCE_ID_RE = re.compile(r"^\|\s*`([A-Z0-9][A-Z0-9-]+)`\s*\|", re.MULTILINE)
DOMAIN_BLOCK_RE = re.compile(
    r"<!-- allowed-domains:start -->(.*?)<!-- allowed-domains:end -->", re.DOTALL
)


def load_source_registry(path: Path = SOURCE_REGISTRY) -> tuple[set[str], set[str]]:
    """Return (source IDs, allowed URL domains) declared in the registry."""
    text = path.read_text(encoding="utf-8")
    ids = set(SOURCE_ID_RE.findall(text))
    domains: set[str] = set()
    block = DOMAIN_BLOCK_RE.search(text)
    if block:
        for line in block.group(1).splitlines():
            line = line.strip()
            if line.startswith("- "):
                domains.add(line[2:].strip().lower())
    return ids, domains


def split_csv(value) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def first_sentence(text: str) -> str:
    text = " ".join(str(text).split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return match.group(1) if match else text

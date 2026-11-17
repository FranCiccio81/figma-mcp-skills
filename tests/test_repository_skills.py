"""Gate on the real repository: every skill passes, registry is up to date, router table is consistent."""

import json
from pathlib import Path

import build_registry
import validate_skills
from skillslib import SKILLS_DIR, discover_skills

ROOT = Path(__file__).resolve().parent.parent


def test_all_repository_skills_pass_validation():
    skills, report = validate_skills.validate()
    assert len(skills) >= 30
    assert report.errors == [], "\n".join(f"{i['skill']}: {i['message']}" for i in report.errors)


def test_registry_is_up_to_date():
    assert build_registry.main(["--check"]) == 0


def test_router_table_only_references_existing_skills():
    names = {s.frontmatter["name"] for s in discover_skills()}
    table = json.loads((SKILLS_DIR / "ai-workflows/skill-router/references/routing-table.json").read_text())
    referenced = set()
    for intent in table["intents"]:
        referenced.update(intent.get("skills", []))
        for skills in intent.get("platform_skills", {}).values():
            referenced.update(skills)
    assert referenced - names == set()


def test_every_skill_is_reachable_from_the_router():
    names = {s.frontmatter["name"] for s in discover_skills()} - {"skill-router"}
    table = json.loads((SKILLS_DIR / "ai-workflows/skill-router/references/routing-table.json").read_text())
    referenced = set()
    for intent in table["intents"]:
        referenced.update(intent.get("skills", []))
        for skills in intent.get("platform_skills", {}).values():
            referenced.update(skills)
    assert names - referenced == set()


def test_claude_compat_link_points_to_canonical_component():
    link = ROOT / ".claude" / "skills" / "component"
    assert link.is_symlink()
    assert (link / "SKILL.md").resolve() == (SKILLS_DIR / "design-systems/component/SKILL.md").resolve()

"""Tests for the deterministic skill router (skills/ai-workflows/skill-router/scripts/route.py)."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "route", ROOT / "skills" / "ai-workflows" / "skill-router" / "scripts" / "route.py"
)
route_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(route_mod)
route = route_mod.route


def names(result):
    return [s["name"] for s in result["skills"]]


class BankingIosExample(unittest.TestCase):
    """The reference example from the mission brief."""

    def setUp(self):
        self.r = route("Design and implement an accessible banking onboarding flow for iOS.",
                       project_ds="bridge-design-system")

    def test_selects_expected_skills(self):
        for expected in ["product-requirements", "interaction-design", "bridge-design-system",
                         "apple-hig-review", "swiftui-implementation", "apple-accessibility",
                         "accessibility-audit"]:
            self.assertIn(expected, names(self.r))

    def test_excludes_android_and_web(self):
        selected = names(self.r)
        for unwanted in ["material3-compose", "android-accessibility", "android-adaptive-layouts",
                         "react-typescript-components", "frontend-testing", "frontend-security"]:
            self.assertNotIn(unwanted, selected)
        excluded = [e["name"] for e in self.r["excluded"]]
        self.assertIn("material3-compose", excluded)

    def test_regulated_domain_note_and_precedence(self):
        self.assertEqual(self.r["regulated_domains"], ["finance"])
        self.assertTrue(any("finance" in n for n in self.r["notes"]))
        audit = next(s for s in self.r["skills"] if s["name"] == "accessibility-audit")
        self.assertEqual(audit["precedence"], 1)
        precedences = [s["precedence"] for s in self.r["skills"]]
        self.assertEqual(precedences, sorted(precedences))

    def test_no_unrelated_enterprise_design_system(self):
        r = route("Design and implement an accessible banking onboarding flow for iOS.")
        self.assertNotIn("bridge-design-system", names(r))


class PlatformRouting(unittest.TestCase):
    def test_android(self):
        r = route("Build the settings screen in Jetpack Compose with dynamic color")
        self.assertIn("material3-compose", names(r))
        self.assertNotIn("swiftui-implementation", names(r))

    def test_web(self):
        r = route("Implement a React TypeScript data table with keyboard support")
        self.assertIn("react-typescript-components", names(r))
        self.assertIn("frontend-testing", names(r))
        self.assertNotIn("apple-hig-review", names(r))

    def test_cross_platform_note(self):
        r = route("Design the onboarding for iOS and Android")
        self.assertEqual(r["platforms"], ["android", "apple"])
        self.assertTrue(any("Several platforms" in n for n in r["notes"]))

    def test_no_platform_implementation_asks(self):
        r = route("Implement the new onboarding")
        self.assertTrue(any("No platform" in n for n in r["notes"]))

    def test_keyword_boundaries(self):
        # "cost" must not trigger the "ost" (opportunity solution tree) keyword
        r = route("Reduce the cost of our cloud bill")
        self.assertNotIn("opportunity-solution-tree", names(r))


class FigmaAvailability(unittest.TestCase):
    def test_fallback_flag(self):
        r = route("Implement this Figma frame node-id=1-2 in React", figma_available=False)
        skill = next(s for s in r["skills"] if s["name"] == "figma-design-to-code")
        self.assertIn("fallback", skill["reason"])


class TableConsistency(unittest.TestCase):
    def test_every_routed_skill_exists(self):
        table = route_mod.load_table()
        on_disk = {p.parent.name for p in (ROOT / "skills").rglob("SKILL.md")}
        self.assertEqual(set(table["skills"]) - on_disk, set())
        self.assertEqual(on_disk - set(table["skills"]), set())


if __name__ == "__main__":
    unittest.main()

"""Tests for the Bridge skills: shared reference sync, token checker, contrast matrix, routing."""
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "skills" / "bridge"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = load("check_tokens", BRIDGE / "bridge-compliance-review" / "scripts" / "check_tokens.py")
router = load("route", ROOT / "skills" / "ai-workflows" / "skill-router" / "scripts" / "route.py")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_reference_content import contrast  # noqa: E402


class SharedFoundations(unittest.TestCase):
    def test_copies_in_sync(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "sync_bridge_foundations.py"), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_every_bridge_skill_has_the_reference(self):
        for skill in BRIDGE.glob("*/SKILL.md"):
            self.assertTrue((skill.parent / "references" / "bridge-foundations.md").exists(), skill)


class TokenChecker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = checker.load_index(checker.DEFAULT_INDEX)

    def test_known_names_pass(self):
        text = ("color/text/neutral/default action/trade/buy-primary-bg-hover control/field/help-text-error "
                "data/chart/07 control/badge/info/tonal/dot background/surface/status/crypto/secondary-alt "
                "feedback/alert/error/subtle-bg border/status/error/primary-focus shadow/elevation/3")
        self.assertEqual(checker.unknown_names(text, self.index), [])

    def test_documented_mistakes_fail(self):
        text = "text/status/error/primary action/trade/buy/primary-bg control/badge/error/bg text/neutral/medium"
        self.assertEqual(sorted(checker.unknown_names(text, self.index)),
                         ["action/trade/buy/primary-bg", "control/badge/error/bg",
                          "text/neutral/medium", "text/status/error/primary"])

    def test_imported_platform_skills_cite_only_known_tokens(self):
        # The v0.2 test claims every colour token cited in the iOS and web skills exists.
        for name in ("bridge-ios", "bridge-android", "bridge-web", "bridge-tablet", "bridge-foldables"):
            text = (BRIDGE / name / "SKILL.md").read_text()
            self.assertEqual(checker.unknown_names(text, self.index), [], name)

    def test_wildcards_and_families_ignored(self):
        self.assertEqual(checker.unknown_names("`color/control/field/*` and `action/brand/*`", self.index), [])


class ContrastMatrix(unittest.TestCase):
    """Every ratio in the Bridge contrast matrix matches the hex values in its row."""

    def test_rows(self):
        text = (BRIDGE / "bridge-accessibility" / "references" / "contrast-matrix.md").read_text()
        light_bg, dark_bg = ("ffffff", "f7f9fd"), ("323232", "121212")
        section = None
        checked = 0
        for line in text.splitlines():
            if line.startswith("## SQ Light"):
                section = light_bg
            elif line.startswith("## SQ Dark"):
                section = dark_bg
            m = re.match(r"\| [a-z/-]+ \| #([0-9a-f]{6}) \| ([\d.]+) \| ([\d.]+) \|", line)
            if m and section:
                fg, r1, r2 = m.group(1), float(m.group(2)), float(m.group(3))
                self.assertAlmostEqual(contrast(fg, section[0]), r1, places=2, msg=line)
                self.assertAlmostEqual(contrast(fg, section[1]), r2, places=2, msg=line)
                checked += 1
            m = re.match(r"\| action/[a-z/ ]+ \| #([0-9a-f]{6}) \| ([\d.]+)", line)
            if m:
                self.assertAlmostEqual(contrast("ffffff", m.group(1)), float(m.group(2)), places=2, msg=line)
                checked += 1
        self.assertGreaterEqual(checked, 25)


class BridgeRouting(unittest.TestCase):
    def names(self, prompt, **kw):
        return [s["name"] for s in router.route(prompt, **kw)["skills"]]

    def test_ios_designer(self):
        n = self.names("Design the Swissquote trade ticket for iPhone in Figma")
        for expected in ("bridge-design-system", "bridge-ios", "bridge-designer-workflow"):
            self.assertIn(expected, n)
        self.assertNotIn("bridge-android", n)
        self.assertNotIn("bridge-web", n)

    def test_pm_web(self):
        n = self.names("Write the PRD for a PostFinance web payment feature")
        self.assertIn("bridge-product-manager", n)
        self.assertIn("bridge-web", n)
        self.assertIn("finance", router.route("Write the PRD for a PostFinance web payment feature")["regulated_domains"])

    def test_tablets_and_foldables(self):
        n = self.names("Adapt the Bridge portfolio screen for Android tablets and foldables")
        for expected in ("bridge-android", "bridge-tablet", "bridge-foldables", "android-adaptive-layouts"):
            self.assertIn(expected, n)

    def test_review(self):
        n = self.names("Review this Bridge pull request for the React payments table")
        self.assertIn("bridge-compliance-review", n)
        self.assertIn("bridge-developer-workflow", n)

    def test_no_bridge_outside_project(self):
        n = self.names("Design an iPhone onboarding for a fitness app")
        self.assertFalse([x for x in n if x.startswith("bridge-")])


if __name__ == "__main__":
    unittest.main()

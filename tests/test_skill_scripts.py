"""Behavioural tests for the scripts shipped inside skills (reviewed_scripts)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load(rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contrast = load("skills/quality/accessibility-audit/scripts/contrast.py")
router = load("skills/ai-workflows/skill-router/scripts/route.py")


@pytest.mark.parametrize(
    "fg,bg,expected",
    [
        ("#000000", "#FFFFFF", 21.0),
        ("#FFFFFF", "#FFFFFF", 1.0),
        ("#9CA3AF", "#FFFFFF", 2.54),
        ("#6B7280", "#FFFFFF", 4.83),
        ("#3B82F6", "#FFFFFF", 3.68),
        ("777", "fff", 4.48),
    ],
)
def test_contrast_ratios(fg, bg, expected):
    assert contrast.evaluate(fg, bg)["ratio"] == expected


def test_contrast_thresholds():
    result = contrast.evaluate("#767676", "#FFFFFF")
    assert result["normal_text_aa"] is True
    assert contrast.evaluate("#777777", "#FFFFFF")["normal_text_aa"] is False


def test_contrast_rejects_bad_input():
    with pytest.raises(ValueError):
        contrast.parse_hex("#12")


def test_contrast_cli():
    out = subprocess.run(
        [sys.executable, "-I", str(ROOT / "skills/quality/accessibility-audit/scripts/contrast.py"), "#9CA3AF", "#FFFFFF"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "2.54:1" in out and "FAIL" in out


def names(plan):
    return [s["name"] for s in plan["skills"]]


def test_router_mission_example_ios():
    plan = router.route("Design and implement an accessible banking onboarding flow for iOS.")
    selected = names(plan)
    for expected in ["product-requirements", "interaction-design-spec", "apple-hig-review", "swiftui-implementation", "apple-accessibility"]:
        assert expected in selected
    assert not any(n in selected for n in ["compose-implementation", "material3-design-review", "android-accessibility"])
    assert selected.index("product-requirements") < selected.index("swiftui-implementation") < selected.index("apple-accessibility")
    assert plan["platforms"] == ["ios"]


def test_router_android_excludes_apple():
    selected = names(router.route("Build the Compose watchlist screen for Android tablets, accessible with TalkBack"))
    assert "compose-implementation" in selected and "android-accessibility" in selected
    assert "swiftui-implementation" not in selected and "apple-accessibility" not in selected


def test_router_asks_platform_when_unknown():
    plan = router.route("Implement this screen")
    assert plan["ask_platform"] is True
    assert not any(n.endswith("-implementation") or n == "react-component-engineering" for n in names(plan))


def test_router_figma_link_comes_first():
    plan = router.route("Implement https://www.figma.com/design/abc/App?node-id=1-2 in React")
    assert names(plan)[0] == "figma-design-context"
    assert "react-component-engineering" in names(plan)


def test_router_cross_platform():
    selected = names(router.route("Design and implement an accessible login for iOS and Android"))
    assert {"swiftui-implementation", "compose-implementation", "apple-accessibility", "android-accessibility"} <= set(selected)

"""Tests for scripts/install-skills.sh (runs locally, no network)."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "install-skills.sh"


def run(*args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True)


def test_list_contains_router():
    out = run("--list").stdout
    assert "skill-router" in out and "component" in out


def test_install_domain_as_links(tmp_path):
    result = run("--target", str(tmp_path), "--domain", "apple")
    assert result.returncode == 0, result.stderr
    installed = sorted(p.name for p in tmp_path.iterdir())
    assert installed == ["apple-accessibility", "apple-hig-review", "swiftui-implementation"]
    assert all((tmp_path / n).is_symlink() for n in installed)
    assert (tmp_path / "apple-hig-review" / "SKILL.md").exists()


def test_install_copy_and_skip_existing(tmp_path):
    assert run("--target", str(tmp_path), "--skill", "skill-router", "--copy").returncode == 0
    assert not (tmp_path / "skill-router").is_symlink()
    second = run("--target", str(tmp_path), "--skill", "skill-router")
    assert "skip" in second.stdout


def test_force_refuses_foreign_directory(tmp_path):
    (tmp_path / "skill-router").mkdir()
    (tmp_path / "skill-router" / "notes.txt").write_text("user data")
    result = run("--target", str(tmp_path), "--skill", "skill-router", "--force")
    assert "refuse" in result.stderr
    assert (tmp_path / "skill-router" / "notes.txt").exists()


def test_unknown_skill_fails(tmp_path):
    assert run("--target", str(tmp_path), "--skill", "does-not-exist").returncode == 1

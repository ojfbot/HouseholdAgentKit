"""The lint ratchet goes red on one new violation, red on an unrecorded improvement, and never raises a floor."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from kit_cli import doctor, lint

pytestmark = pytest.mark.doctor

CLEAN = "from __future__ import annotations\n\n\ndef f(x: int) -> int:\n    return x + 1\n"
ONE_VIOLATION = "l = 1\n"  # E741: an ambiguous variable name, exactly one finding


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    shutil.copy(doctor.ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "good").mkdir()
    (tmp_path / "good/a.py").write_text(CLEAN)
    (tmp_path / "old").mkdir()
    (tmp_path / "old/b.py").write_text(ONE_VIOLATION)
    (tmp_path / "kit").mkdir()
    policy = {"full": ["good"], "floor_ignore": [], "ratchet": {"old": {"lint": 1, "format": 0}}}
    (tmp_path / lint.POLICY_FILE).write_text(json.dumps(policy))
    return tmp_path


def _floor(repo: Path) -> dict:
    return json.loads((repo / lint.POLICY_FILE).read_text())["ratchet"]["old"]


def test_at_the_floor_is_green(repo: Path) -> None:
    assert lint.run(repo) == 0


def test_one_new_violation_in_a_ratchet_tree_is_red(repo: Path) -> None:
    (repo / "old/c.py").write_text(ONE_VIOLATION)
    assert lint.run(repo) == 1


def test_one_new_unformatted_file_in_a_ratchet_tree_is_red(repo: Path) -> None:
    (repo / "old/d.py").write_text("x=1\n")
    assert lint.run(repo) == 1


def test_a_violation_in_a_full_tree_is_red(repo: Path) -> None:
    (repo / "good/e.py").write_text(ONE_VIOLATION)
    assert lint.run(repo) == 1


def test_an_improvement_is_red_until_the_floor_is_lowered(repo: Path) -> None:
    (repo / "old/b.py").write_text(CLEAN)
    assert lint.run(repo) == 1
    assert lint.run(repo, update_baseline=True) == 0
    assert _floor(repo) == {"lint": 0, "format": 0}
    assert lint.run(repo) == 0


def test_update_baseline_refuses_to_raise_a_floor(repo: Path) -> None:
    (repo / "old/c.py").write_text(ONE_VIOLATION)
    assert lint.run(repo, update_baseline=True) == 1
    assert _floor(repo) == {"lint": 1, "format": 0}


def test_the_repo_meets_its_own_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIT_LINT_BASE", "none")  # the comparison with main is the lint job's (full history there)
    assert lint.run(doctor.ROOT) == 0


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo_on_main(repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "switch", "-q", "-c", "work")
    monkeypatch.setenv("KIT_LINT_BASE", "main")
    return repo


def _set(repo: Path, **change: object) -> None:
    policy = json.loads((repo / lint.POLICY_FILE).read_text())
    policy.update(change)
    (repo / lint.POLICY_FILE).write_text(json.dumps(policy))


def test_a_pr_that_raises_its_own_floor_to_match_is_red(repo_on_main: Path) -> None:
    (repo_on_main / "old/c.py").write_text(ONE_VIOLATION)
    _set(repo_on_main, ratchet={"old": {"lint": 2, "format": 0}})
    assert lint.run(repo_on_main) == 1


def test_moving_a_tree_from_full_to_the_ratchet_is_red(repo_on_main: Path) -> None:
    (repo_on_main / "good/e.py").write_text(ONE_VIOLATION)
    _set(repo_on_main, full=[], ratchet={"old": {"lint": 1, "format": 0}, "good": {"lint": 1, "format": 0}})
    assert lint.run(repo_on_main) == 1


def test_a_new_exemption_is_red(repo_on_main: Path) -> None:
    _set(repo_on_main, exempt={"good": "because"})
    assert lint.run(repo_on_main) == 1


def test_lowering_a_floor_against_main_is_green(repo_on_main: Path) -> None:
    (repo_on_main / "old/b.py").write_text(CLEAN)
    assert lint.run(repo_on_main, update_baseline=True) == 0
    assert lint.run(repo_on_main) == 0


def test_a_missing_main_fails_closed(repo_on_main: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIT_LINT_BASE", "origin/does-not-exist")
    assert lint.run(repo_on_main) == 1


def test_while_main_has_no_policy_the_founding_policy_is_the_base(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex re-review 2: on the real base (no policy on main) a raised floor read green."""
    (repo / lint.POLICY_FILE).unlink()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main without a policy")
    _git(repo, "switch", "-q", "-c", "work")
    monkeypatch.setenv("KIT_LINT_BASE", "main")
    monkeypatch.setattr(lint, "FOUNDING_POLICY", {"full": ["good"], "floor_ignore": [], "ratchet": {"old": {"lint": 1, "format": 0}}, "exempt": {}})
    (repo / "old/c.py").write_text(ONE_VIOLATION)
    (repo / lint.POLICY_FILE).write_text(json.dumps({"full": ["good"], "floor_ignore": [], "ratchet": {"old": {"lint": 2, "format": 0}}}))
    assert lint.run(repo) == 1
    base, problem, against = lint.base_policy(repo)
    assert base is lint.FOUNDING_POLICY and problem is None and "founding policy" in against


def test_the_founding_policy_matches_the_committed_policy() -> None:
    """The pinned founding policy and kit/lint-policy.json agree today; a later lowered floor is fine, a raised one is not."""
    policy = json.loads((doctor.ROOT / lint.POLICY_FILE).read_text())
    assert lint.loosened(lint.FOUNDING_POLICY, policy, doctor.ROOT) == []

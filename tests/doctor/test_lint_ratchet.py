"""The lint ratchet goes red on one new violation, red on an unrecorded improvement, and never raises a floor."""

from __future__ import annotations

import json
import shutil
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


def test_the_repo_meets_its_own_policy() -> None:
    assert lint.run(doctor.ROOT) == 0

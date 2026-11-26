"""Cases from the Codex review of #51."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kit_cli import doctor

pytestmark = pytest.mark.doctor


def test_an_unwired_project_in_a_folder_with_a_non_ascii_name_is_seen(tmp_path: Path) -> None:
    """Finding 1: git quotes such paths in newline output, and the quoted form named no file, so it was dropped."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "root"\n\n[tool.uv.workspace]\nmembers = ["packages/a"]\n')
    (tmp_path / "packages/a").mkdir(parents=True)
    (tmp_path / "packages/a/pyproject.toml").write_text('[project]\nname = "a"\n')
    (tmp_path / "tools/café").mkdir(parents=True)
    (tmp_path / "tools/café/pyproject.toml").write_text('[project]\nname = "cafe"\n')
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.quotePath=true"]
    subprocess.run([*git, "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run([*git, "add", "-A"], cwd=tmp_path, check=True)
    res = doctor.workspace_wired(tmp_path)
    assert not res.ok and "tools/café" in res.detail, res.detail


def test_files_returns_real_paths_for_non_ascii_names(tmp_path: Path) -> None:
    (tmp_path / "données").mkdir()
    (tmp_path / "données/x.txt").write_text("x")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "core.quotePath=true", "add", "-A"], cwd=tmp_path, check=True)
    assert doctor._files(tmp_path) == ["données/x.txt"]

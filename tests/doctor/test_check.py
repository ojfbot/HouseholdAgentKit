"""kit check runs CI's own steps: each job in a clean checkout of a snapshot, aggregates evaluated, the rest refused."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kit_cli import check

pytestmark = pytest.mark.doctor

WORKFLOW = """name: ci
on:
  pull_request:
jobs:
  first:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - run: test -f tracked.txt && test -f untracked.txt && touch generated.txt
  second:
    runs-on: ubuntu-24.04
    steps:
      - run: test ! -f generated.txt
  ci:
    if: always()
    needs: [first, second]
    runs-on: ubuntu-24.04
    steps:
      - run: |
          echo '${{ toJSON(needs) }}' | jq -e 'to_entries | all(.value.result == "success")'
"""


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text(WORKFLOW)
    (tmp_path / "tracked.txt").write_text("x")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    (tmp_path / "untracked.txt").write_text("y")  # not committed: kit check must still see it
    return tmp_path


def test_each_job_gets_a_clean_checkout_of_the_working_tree(repo: Path) -> None:
    before = _git(repo, "status", "--porcelain")
    assert check.run(repo) == 0  # first sees the untracked file; second does not see first's generated file
    assert _git(repo, "status", "--porcelain") == before  # nothing in the working tree or index changed
    assert not (repo / "generated.txt").exists()
    assert len(_git(repo, "worktree", "list").splitlines()) == 1


def test_a_failing_job_fails_the_run(repo: Path) -> None:
    (repo / "untracked.txt").unlink()
    assert check.run(repo) == 1


def test_the_standard_aggregate_is_recognised_and_a_bent_one_is_refused(repo: Path) -> None:
    assert [j.id for j in check.jobs(repo) if j.aggregate] == ["ci"]
    wf = repo / ".github/workflows/ci.yml"
    wf.write_text(WORKFLOW.replace("""jq -e 'to_entries | all(.value.result == "success")'""", "true"))
    assert check.runner_only(repo) and check.run(repo) == 1


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("      - run: test ! -f generated.txt\n", "      - run: test ! -f generated.txt\n        if: github.event_name == 'push'\n"),
        ("      - run: test ! -f generated.txt\n", "      - run: test ! -f generated.txt\n        shell: pwsh\n"),
        ("      - run: test ! -f generated.txt\n", "      - run: test ! -f generated.txt\n        continue-on-error: true\n"),
        ("  second:\n    runs-on: ubuntu-24.04\n", "  second:\n    runs-on: ubuntu-24.04\n    strategy: {matrix: {n: [1, 2]}}\n"),
        ("  second:\n    runs-on: ubuntu-24.04\n", "  second:\n    runs-on: ubuntu-24.04\n    defaults: {run: {working-directory: sub}}\n"),
        ("  second:\n    runs-on: ubuntu-24.04\n", "  second:\n    if: github.event_name == 'push'\n    runs-on: ubuntu-24.04\n"),
        ("needs: [first, second]", "needs: [first, third]"),
    ],
    ids=["step-if", "shell", "continue-on-error", "matrix", "defaults", "job-if", "unknown-need"],
)
def test_what_kit_check_cannot_reproduce_is_refused(repo: Path, old: str, new: str) -> None:
    wf = repo / ".github/workflows/ci.yml"
    wf.write_text(WORKFLOW.replace(old, new, 1))
    assert check.runner_only(repo), f"not refused: {new!r}"
    assert check.run(repo) == 1

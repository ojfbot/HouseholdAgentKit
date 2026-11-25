"""The independent review counts only when the GitHub review it links can be read and matches the register."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from kit_cli import doctor, gates

pytestmark = pytest.mark.doctor

TODAY = date(2026, 11, 25)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    shutil.copy(doctor.ROOT / gates.GATES_FILE, tmp_path / gates.GATES_FILE)
    (tmp_path / doctor.REGISTER).write_text("# Integration risk register\n" + doctor.REVIEWED)
    return tmp_path


def _verdict(root: Path, review: dict | Exception = doctor.PROOF_REVIEW, ancestor: bool | None = True) -> doctor.Result:
    def fetch(repo: str, pr: int, rid: int) -> dict:
        if isinstance(review, Exception):
            raise review
        return review

    return doctor.review_recorded(root, TODAY, fetch=fetch, ancestry=lambda r, sha, tree: ancestor, tree_of=lambda repo, sha: "t" * 40)


def test_a_matching_review_on_an_ancestor_commit_is_recorded(root: Path) -> None:
    assert _verdict(root).ok


def test_a_reviewed_commit_that_is_not_an_ancestor_of_head_is_not_recorded(root: Path) -> None:
    assert not _verdict(root, ancestor=False).ok


def test_without_git_the_commit_cannot_be_checked_so_it_is_not_recorded(root: Path) -> None:
    res = _verdict(root, ancestor=None)
    assert not res.ok and "no git checkout" in res.detail


def test_github_unreachable_means_not_recorded(root: Path) -> None:
    res = _verdict(root, review=OSError("network is unreachable"))
    assert not res.ok and "cannot read it on GitHub" in res.detail


@pytest.mark.parametrize("state", ["PENDING", "DISMISSED"])
def test_a_review_that_was_never_submitted_or_was_dismissed_does_not_count(root: Path, state: str) -> None:
    assert not _verdict(root, review={**doctor.PROOF_REVIEW, "state": state}).ok


def test_doctor_offline_never_reads_the_review_as_recorded(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "is_ancestor", lambda r, sha, tree=None: True)
    assert not doctor.review_recorded(root, TODAY).ok  # KIT_OFFLINE is set for every doctor test


def test_a_name_mentioned_in_passing_is_not_a_signature(root: Path) -> None:
    """Codex re-review 6064615719, 2: a reviewer name that appeared incidentally in the body read green."""
    body = "Independent review. Compared with what the other model, Fable, said earlier...\n\nReviewer: independent model\n"
    text = (root / doctor.REGISTER).read_text().replace("- Reviewer: independent model", "- Reviewer: Fable")
    (root / doctor.REGISTER).write_text(text)
    res = _verdict(root, review={**doctor.PROOF_REVIEW, "body": body})
    assert not res.ok and "not signed" in res.detail


def test_green_says_independence_is_attested_not_proven(root: Path) -> None:
    res = _verdict(root)
    assert res.ok and "attested by the owner" in res.detail and "not proven" in res.detail


def test_an_unresolvable_repo_fails_closed(root: Path) -> None:
    (root / gates.GATES_FILE).unlink()
    res = _verdict(root)
    assert not res.ok and "cannot tell which repo" in res.detail


def _git(root: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_a_rebase_merged_review_still_counts_when_the_tree_is_identical(tmp_path: Path) -> None:
    """#45: GitHub's rebase-merge rewrote b9d35d7 as 6220fce with the same tree, and doctor read the review as unverified."""
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("reviewed code\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "reviewed")
    reviewed, tree = _git(tmp_path, "rev-parse", "HEAD"), _git(tmp_path, "rev-parse", "HEAD^{tree}")
    _git(tmp_path, "commit", "-q", "--amend", "-m", "the same code, rewritten by a rebase-merge")  # new hash, same tree
    assert _git(tmp_path, "rev-parse", "HEAD") != reviewed
    assert doctor.is_ancestor(tmp_path, reviewed[:7], tree) is True
    assert doctor.is_ancestor(tmp_path, reviewed[:7], None) is False  # without the tree, the hash alone is not in history


def test_a_rebase_that_changed_the_code_does_not_count(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("reviewed code\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "reviewed")
    reviewed, tree = _git(tmp_path, "rev-parse", "HEAD"), _git(tmp_path, "rev-parse", "HEAD^{tree}")
    (tmp_path / "a.txt").write_text("different code\n")
    _git(tmp_path, "commit", "-q", "-a", "--amend", "-m", "rebased onto a moved base")
    assert doctor.is_ancestor(tmp_path, reviewed[:7], tree) is False


def test_the_reviewed_tree_unreadable_on_github_is_not_recorded(root: Path) -> None:
    def no_tree(repo: str, sha: str) -> str:
        raise OSError("network is unreachable")

    res = doctor.review_recorded(root, TODAY, fetch=lambda r, p, i: doctor.PROOF_REVIEW, ancestry=lambda r, sha, tree: tree is not None, tree_of=no_tree)
    assert not res.ok and "tree" in res.detail

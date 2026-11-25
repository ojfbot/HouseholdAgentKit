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

    return doctor.review_recorded(root, TODAY, fetch=fetch, ancestry=lambda r, sha: ancestor)


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
    monkeypatch.setattr(doctor, "is_ancestor", lambda r, sha: True)
    assert not doctor.review_recorded(root, TODAY).ok  # KIT_OFFLINE is set for every doctor test

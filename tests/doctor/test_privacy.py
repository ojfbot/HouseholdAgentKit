"""The privacy guard runs every rule on every file; the key shapes include the formats review finding C1 found missing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kit_cli import privacy

pytestmark = pytest.mark.doctor

# Built at run time so no key-shaped string is ever tracked in this file.
KEYS = {
    "anthropic": "sk-" + "ant-api03-" + "A1b2" * 10,
    "openai project": "sk-" + "proj-" + "Z9y8" * 10,
    "openai legacy": "sk-" + "Q" * 40,
    "github classic": "gh" + "p_" + "a" * 36,
    "github oauth": "gh" + "o_" + "b" * 36,
    "github app": "gh" + "s_" + "c" * 36,
    "github user-to-server": "gh" + "u_" + "d" * 36,
    "github refresh": "gh" + "r_" + "e" * 36,
    "github fine-grained": "github" + "_pat_" + "f" * 40,
    "hugging face": "hf" + "_" + "g" * 34,
    "aws": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "langsmith": "lsv2" + "_pt_" + "0123456789abcdef" * 2,
    "slack": "xo" + "xb-" + "1234567890-abc",
    "private key": "-----BEGIN " + "RSA PRIVATE KEY-----",
}


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "kit").mkdir()
    (tmp_path / privacy.ALLOW_FILE).write_text("version: 1\nallow: []\n")
    return tmp_path


@pytest.mark.parametrize("kind", sorted(KEYS))
def test_every_key_shape_is_found_in_any_file(tmp_path: Path, kind: str) -> None:
    root = _repo(tmp_path)
    (root / "somewhere" / "deep").mkdir(parents=True)
    (root / "somewhere/deep/notes.txt").write_text(f"value = {KEYS[kind]}\n")
    left, problems = privacy.check(root)
    assert [f.rule for f in left] == ["key"], f"{kind} was not caught"
    assert not problems


def test_untracked_files_are_scanned_and_ignored_ones_are_not(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".gitignore").write_text("scratch/\n")
    (root / "scratch").mkdir()
    (root / "scratch/local.txt").write_text(KEYS["anthropic"])
    (root / "new.txt").write_text(KEYS["anthropic"])
    left, _ = privacy.check(root)
    assert [f.path for f in left] == ["new.txt"]


def test_a_non_ascii_path_is_seen(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "data/generated").mkdir(parents=True)
    (root / "data/generated/übersicht.json").write_text("{}")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    left, _ = privacy.check(root)
    assert any(f.path == "data/generated/übersicht.json" and f.rule == "generated-data" for f in left)


def test_addresses_that_identify_nobody_are_not_findings(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "a.md").write_text("Co-Authored-By: Claude <noreply@anthropic.com>\nmail me at someone@example.com\n")
    assert privacy.check(root) == ([], [])


def test_a_matching_exception_suppresses_and_a_mismatched_one_is_stale(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "fixture.yaml").write_text("split: " + "holdout\n")
    (root / privacy.ALLOW_FILE).write_text(
        "version: 1\nallow:\n  - {rule: holdout-case, path: fixture.yaml, why: a test fixture}\n  - {rule: holdout-case, path: other.yaml, why: left over}\n"
    )
    left, problems = privacy.check(root)
    assert left == [] and problems == ["stale exception: holdout-case on other.yaml suppresses nothing; delete it"]


def test_the_repo_is_clean() -> None:
    from kit_cli import doctor

    assert privacy.check(doctor.ROOT) == ([], [])


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root, check=True, capture_output=True)


def test_staged_scan_judges_what_is_committed_not_what_is_on_disk(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "notes.txt").write_text(f"value = {KEYS['anthropic']}\n")
    _git(root, "add", "-A")
    (root / "notes.txt").write_text("value = redacted\n")  # cleaned on disk, but the key is still staged
    assert privacy.check(root) == ([], [])
    left, _ = privacy.check(root, staged=True)
    assert [(f.rule, f.path) for f in left] == [("key", "notes.txt")]


def test_staged_scan_ignores_a_key_that_is_only_on_disk(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "notes.txt").write_text("value = redacted\n")
    _git(root, "add", "-A")
    (root / "notes.txt").write_text(f"value = {KEYS['github classic']}\n")  # not staged: not in this commit
    assert privacy.check(root, staged=True) == ([], [])
    assert [f.rule for f in privacy.check(root)[0]] == ["key"]


def test_staged_scan_reads_the_staged_allowlist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "fixture.yaml").write_text("split: " + "holdout\n")
    (root / privacy.ALLOW_FILE).write_text("version: 1\nallow:\n  - {rule: holdout-case, path: fixture.yaml, why: a test fixture}\n")
    _git(root, "add", "-A")
    (root / privacy.ALLOW_FILE).write_text("version: 1\nallow: []\n")  # loosened on disk only
    assert privacy.check(root, staged=True) == ([], [])

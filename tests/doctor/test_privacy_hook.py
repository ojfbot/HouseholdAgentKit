"""End to end: git runs the privacy hook during real commits, and only what is committed decides the outcome.

The hook here is the same check `.pre-commit-config.yaml` runs (`kit privacy scan --staged`), installed directly as
.git/hooks/pre-commit so no pre-commit download is needed. git runs it with the commit's index, including the
temporary index it builds for `git commit <path>` and `git commit -a`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from kit_cli import privacy

pytestmark = pytest.mark.doctor

KEY = "sk-" + "ant-api03-" + "H00k" * 10  # built at run time
HOOK = f"""#!/bin/sh
exec "{sys.executable}" -c "import sys; from pathlib import Path; from kit_cli import privacy; sys.exit(privacy.run(Path.cwd(), staged=True))"
"""


def _git(root: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    res = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.hooksPath=.git/hooks", *args], cwd=root, capture_output=True, text=True
    )
    if ok:
        assert res.returncode == 0, res.stderr
    return res


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "kit").mkdir()
    (tmp_path / privacy.ALLOW_FILE).write_text("version: 1\nallow: []\n")
    (tmp_path / "a.txt").write_text("clean\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")  # committed before the hook exists
    hook = tmp_path / ".git/hooks/pre-commit"
    hook.write_text(HOOK)
    hook.chmod(0o755)
    return tmp_path


def _commits(root: Path) -> int:
    return int(_git(root, "rev-list", "--count", "HEAD").stdout)


def _refused(root: Path, *commit_args: str) -> bool:
    """The commit failed, nothing was committed, and it failed for the privacy reason (not some other error)."""
    before = _commits(root)
    res = _git(root, "commit", "-q", "-m", "try", *commit_args, ok=False)
    said = res.stdout + res.stderr
    return res.returncode != 0 and _commits(root) == before and "privacy FAIL  key" in said


def test_a_staged_key_is_refused(repo: Path) -> None:
    (repo / "b.txt").write_text(KEY)
    _git(repo, "add", "b.txt")
    assert _refused(repo)


def test_commit_dash_a_is_refused_for_an_unstaged_tracked_change(repo: Path) -> None:
    (repo / "a.txt").write_text(KEY)
    assert _refused(repo, "-a")


def test_commit_of_a_path_uses_git_s_temporary_index_and_is_refused(repo: Path) -> None:
    (repo / "a.txt").write_text(KEY)
    assert _refused(repo, "a.txt")


def test_partial_staging_commits_the_clean_version_and_passes(repo: Path) -> None:
    (repo / "a.txt").write_text("clean, edited\n")
    _git(repo, "add", "a.txt")
    (repo / "a.txt").write_text(KEY)  # on disk only, like the unstaged half of `git add -p`
    _git(repo, "commit", "-q", "-m", "partial")
    assert KEY not in _git(repo, "show", "HEAD:a.txt").stdout


def test_a_rename_carrying_a_key_is_refused(repo: Path) -> None:
    (repo / "a.txt").write_text(KEY)
    _git(repo, "add", "a.txt")
    _git(repo, "mv", "a.txt", "renamed.txt")
    assert _refused(repo)


def test_a_file_staged_then_deleted_from_disk_is_still_refused(repo: Path) -> None:
    (repo / "b.txt").write_text(KEY)
    _git(repo, "add", "b.txt")
    (repo / "b.txt").unlink()
    assert _refused(repo)


def test_a_symlink_commits_only_its_target_path(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text(KEY)
    os.symlink(outside, repo / "link")
    _git(repo, "add", "link")
    _git(repo, "commit", "-q", "-m", "symlink")  # the blob is the link text, not the secret it points at
    assert KEY not in _git(repo, "show", "HEAD:link").stdout


def test_a_submodule_gitlink_commits_as_a_pointer_through_the_real_hook(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},vendor/sub")
    assert privacy.check(repo, staged=True) == ([], [])  # its contents live in another repo and are scanned there
    _git(repo, "commit", "-q", "-m", "gitlink")  # the hook runs and passes; the commit holds a pointer, no blob
    assert _git(repo, "ls-tree", "HEAD", "vendor/sub").stdout.split()[:2] == ["160000", "commit"]


def test_the_on_disk_scan_reads_a_symlink_as_its_link_text_like_the_hook(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Codex re-review 6064615719, 5: the working-tree scan followed live symlinks and dropped dangling ones."""
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text(KEY)
    os.symlink(outside, repo / "live")
    os.symlink(repo / "nowhere" / ("x" + KEY), repo / "dangling")  # a key in the link text itself
    _git(repo, "add", "live", "dangling")
    on_disk, staged = privacy.check(repo), privacy.check(repo, staged=True)
    assert on_disk == staged
    assert [(f.rule, f.path) for f in staged[0]] == [("key", "dangling")]

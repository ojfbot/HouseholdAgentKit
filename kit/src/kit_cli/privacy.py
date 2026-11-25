"""kit privacy scan: every rule on every file, with exceptions only from kit/privacy-allow.yaml.

Deny by default:

* Every file is scanned, binaries included (rules match bytes), whatever directory it is in. Two sources:
  - `worktree` (the default; what CI's checkout holds): tracked and untracked-but-not-ignored files as they
    are on disk (`git ls-files -co --exclude-standard -z`, so non-ASCII names survive). Without git, every
    file under the root except tool caches.
  - `index` (`--staged`; what the pre-commit hook runs): the blobs git will commit, read from the index, so a
    file edited after `git add` is judged by what is staged, not by what is on disk. The allowlist is read
    from the index too.
* A rule has no built-in scope. An exception is an entry in kit/privacy-allow.yaml naming the rule, a path
  glob, optionally the matched text, and why. An entry with no `why` is refused. An entry that no longer
  suppresses anything is a failure too ("stale exception"), so the allowlist cannot quietly outgrow the repo.
* A file too large to read is a finding, not a skip.
* Boundaries, by design: a symlink is committed as its link text, and that text is what is scanned (the file it
  points at is not published). A submodule is committed as a pointer (a gitlink) and skipped; its contents are
  another repository's and must be scanned there. tests/doctor/test_privacy_hook.py proves both, end to end.

The key shapes are a denylist and will always be one release behind; GitHub's secret scanning with push
protection (an owner setting, docs/hand-off.md) is the second net.
Exit codes: 0 clean; 1 a finding or a broken allowlist; 2 usage error.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

ALLOW_FILE = "kit/privacy-allow.yaml"
MAX_BYTES = 50 * 1024 * 1024
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "out"}

# Path rules: the file must not exist in the repo at all.
PATH_RULES: dict[str, re.Pattern[str]] = {
    "forbidden-file": re.compile(
        r"(^|/)(holdout[-_]seed[^/]*|[^/]*\.(safetensors|gguf|mlx|ckpt|pt|onnx)|\.env(\.[^/]*)?|adapters/.*|checkpoints/.*|traces/.*|[^/]*\.jsonl)$"
    ),
    "generated-data": re.compile(r"^data/(?!seeds/|research/)|(^|/)runs/[^/]+/"),
}

# Content rules: the bytes must not appear in any file.
CONTENT_RULES: dict[str, re.Pattern[bytes]] = {
    "key": re.compile(
        rb"sk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"
        rb"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}"
        rb"|hf_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|lsv2_[a-z]{2}_[a-f0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}"
        rb"|-----BEGIN [A-Z ]*PRIVATE KEY"
    ),
    "holdout-case": re.compile(rb'"split"\s*:\s*"holdout"|split:\s*holdout'),
    "personal-path": re.compile(rb"/Users/[A-Za-z0-9_]+/|/home/[a-z][a-z0-9_]+/|(?:^|[^A-Za-z0-9._/-])~/[A-Za-z0-9._-]+"),
    "email": re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|net|org|io|dev|ai)\b"),
}
# Addresses that identify nobody. This is part of the rule's definition, not an exception.
NOT_PERSONAL = re.compile(r"noreply@|@example\.(com|org|net)\b|@users\.noreply\.github\.com\b")
RULES = {*PATH_RULES, *CONTENT_RULES, "too-large"}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    text: str

    def show(self) -> str:
        shown = self.text[:6] + "***" if self.rule == "key" else self.text[:80]
        return f"{self.rule:15} {self.path}:{self.line}  {shown}"


@dataclass
class Allow:
    rule: str
    path: str
    match: re.Pattern[str] | None
    why: str
    used: int = 0

    def covers(self, f: Finding) -> bool:
        return self.rule == f.rule and fnmatch.fnmatchcase(f.path, self.path) and (self.match is None or bool(self.match.search(f.text)))


class Source:
    """Where the scan reads from: the working tree, or the index (what the next commit will contain)."""

    def __init__(self, root: Path, staged: bool = False) -> None:
        self.root, self.staged = root, staged
        self._blobs: dict[str, str] = {}
        if staged:
            out = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=root, capture_output=True)
            if out.returncode != 0:
                raise OSError(f"cannot read the git index: {out.stderr.decode(errors='replace').strip()}")
            for entry in out.stdout.split(b"\0"):
                if not entry:
                    continue
                meta, name = entry.split(b"\t", 1)
                mode, sha, _stage = meta.split()
                if mode != b"160000":  # submodules have no blob
                    self._blobs[name.decode("utf-8", "surrogateescape")] = sha.decode()

    def files(self) -> list[str]:
        return sorted(self._blobs) if self.staged else files(self.root)

    def size(self, rel: str) -> int:
        if self.staged:
            out = subprocess.run(["git", "cat-file", "-s", self._blobs[rel]], cwd=self.root, capture_output=True, text=True, check=True)
            return int(out.stdout.strip())
        p = self.root / rel
        return len(os.readlink(p).encode()) if p.is_symlink() else p.stat().st_size

    def read(self, rel: str) -> bytes:
        if self.staged:
            return subprocess.run(["git", "cat-file", "blob", self._blobs[rel]], cwd=self.root, capture_output=True, check=True).stdout
        p = self.root / rel
        # A symlink is read as its link text, as git commits it, so the on-disk scan and the staged scan agree.
        return os.readlink(p).encode() if p.is_symlink() else p.read_bytes()

    def has(self, rel: str) -> bool:
        return rel in self._blobs if self.staged else (self.root / rel).exists()


def files(root: Path) -> list[str]:
    if (root / ".git").exists():
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root, capture_output=True)
        if out.returncode == 0:
            names = {n.decode("utf-8", "surrogateescape") for n in out.stdout.split(b"\0") if n}
            return sorted(n for n in names if (root / n).is_symlink() or (root / n).is_file())
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if (p.is_symlink() or p.is_file()) and not (set(p.relative_to(root).parts) & SKIP_DIRS)
    )


def load_allow(root: Path, source: Source | None = None) -> list[Allow]:
    source = source or Source(root)
    if not source.has(ALLOW_FILE):
        raise ValueError(f"{ALLOW_FILE} is missing (an empty `allow: []` is fine; a missing file is not)")
    raw = yaml.safe_load(source.read(ALLOW_FILE).decode()) or {}
    if raw.get("version") != 1 or not isinstance(raw.get("allow"), list):
        raise ValueError(f"{ALLOW_FILE} needs `version: 1` and an `allow` list")
    out, problems = [], []
    for i, e in enumerate(raw["allow"]):
        where = f"allow[{i}]"
        if not isinstance(e, dict):
            problems.append(f"{where} is not a mapping")
            continue
        if e.get("rule") not in RULES:
            problems.append(f"{where}.rule must be one of {sorted(RULES)}")
        if not isinstance(e.get("path"), str) or not e["path"] or e["path"] in ("*", "**", "**/*"):
            problems.append(f"{where}.path must name files; a rule switched off everywhere is not an exception")
        if not str(e.get("why") or "").strip():
            problems.append(f"{where} has no `why`; every exception says why it is safe")
        try:
            match = re.compile(e["match"]) if e.get("match") else None
        except re.error as err:
            problems.append(f"{where}.match is not a regex: {err}")
            match = None
        out.append(Allow(str(e.get("rule")), str(e.get("path")), match, str(e.get("why") or "")))
    if problems:
        raise ValueError("; ".join(problems))
    return out


def scan(root: Path, source: Source | None = None) -> list[Finding]:
    source = source or Source(root)
    found: list[Finding] = []
    for rel in source.files():
        for rule, pat in PATH_RULES.items():
            if pat.search(rel):
                found.append(Finding(rule, rel, 0, rel))
        try:
            size = source.size(rel)
            if size > MAX_BYTES:
                found.append(Finding("too-large", rel, 0, f"{size} bytes; too large to scan, so it is not known to be clean"))
                continue
            data = source.read(rel)
        except (OSError, subprocess.CalledProcessError) as e:
            found.append(Finding("too-large", rel, 0, f"unreadable: {e}"))
            continue
        for rule, pat in CONTENT_RULES.items():
            for m in pat.finditer(data):
                text = m.group(0).decode("latin-1").strip()
                if rule == "email" and NOT_PERSONAL.search(text):
                    continue
                found.append(Finding(rule, rel, data.count(b"\n", 0, m.start()) + 1, text))
    return found


def check(root: Path, staged: bool = False) -> tuple[list[Finding], list[str]]:
    """Findings no exception covers, and problems with the allowlist itself (broken or stale entries)."""
    try:
        source = Source(root, staged=staged)
        allow = load_allow(root, source)
    except (OSError, ValueError, yaml.YAMLError) as e:
        return [], [str(e)]
    left = []
    for f in scan(root, source):
        hit = next((a for a in allow if a.covers(f)), None)
        if hit:
            hit.used += 1
        else:
            left.append(f)
    stale = [f"stale exception: {a.rule} on {a.path} suppresses nothing; delete it" for a in allow if not a.used]
    return left, stale


def run(root: Path, staged: bool = False) -> int:
    left, problems = check(root, staged=staged)
    for f in left:
        print(f"privacy FAIL  {f.show()}")
    for p in problems:
        print(f"privacy FAIL  {p}")
    if left or problems:
        print(
            f"privacy FAIL  {len(left)} findings, {len(problems)} allowlist problems. Remove the content, or add an exception with its reason to {ALLOW_FILE}"
        )
        return 1
    what = "staged files (the next commit)" if staged else "files"
    print(f"privacy ok    {len(Source(root, staged).files())} {what} scanned, every rule on every file; exceptions only from {ALLOW_FILE}")
    return 0

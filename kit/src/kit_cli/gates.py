"""kit gates: which milestones are blocked, read live from GitHub against docs/gates.yaml.

Rules this file keeps:

* Fail closed. A blocker counts as done only when GitHub says so: an issue closed as completed, or a pull
  request merged. Closed as "not planned" counts only when the owner lists it under `waived`. If GitHub is
  unreachable, or an issue number is not found, the gate reads UNKNOWN, which is never green.
* One read per run, and every answer in that run comes from it. `kit doctor` and `kit gates` without a
  milestone may use a ten-minute cache under out/ (they report status). `kit gates --milestone N`, the check
  that decides whether an issue may close, never uses the cache: it takes one fresh snapshot, answers only
  from it, and fails closed if GitHub cannot be read.
* The fetcher is a parameter, so the proofs and tests never touch the network.

Exit codes for `kit gates`: 0 every gate asked about is clear; 1 one is blocked or unknown; 2 usage error.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

GATES_FILE = "docs/gates.yaml"
CACHE_FILE = "out/gates-cache.json"
CACHE_SECONDS = 600
API = "https://api.github.com"


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    state: str  # open | closed
    reason: str | None = None  # completed | not_planned | reopened | None
    is_pr: bool = False
    merged: bool = False


@dataclass
class Gate:
    id: str
    milestone: int
    kind: str
    blocked_by: list[int]
    why: str = ""
    rung: int | None = None
    title: str = ""
    waived: list[int] = field(default_factory=list)


@dataclass
class Spec:
    repo: str
    gates: list[Gate]


@dataclass
class Verdict:
    gate: Gate
    status: str  # clear | blocked | unknown
    pending: list[int]
    unseen: list[int]
    detail: str
    identity_ok: bool = True  # False: the milestone number does not name the issue the gate says it does

    @property
    def clear(self) -> bool:
        return self.status == "clear"


Fetcher = Callable[[str], dict[int, Issue]]


class SpecError(ValueError):
    pass


# --------------------------------------------------------------------------------------------- the file


def load_spec(root: Path) -> Spec:
    """Parse and validate docs/gates.yaml. Raises SpecError with every problem found, not just the first."""
    path = root / GATES_FILE
    if not path.exists():
        raise SpecError(f"{GATES_FILE} is missing")
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise SpecError(f"{GATES_FILE} is not valid YAML: {e}") from e
    problems: list[str] = []
    if raw.get("version") != 1:
        problems.append("version must be 1")
    repo = raw.get("repo")
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        problems.append("repo must be owner/name")
    items = raw.get("gates")
    if not isinstance(items, list) or not items:
        problems.append("gates must be a non-empty list")
        items = []
    gates, seen = [], set()
    for i, g in enumerate(items):
        where = f"gates[{i}]"
        if not isinstance(g, dict):
            problems.append(f"{where} is not a mapping")
            continue
        gid = g.get("id")
        if not isinstance(gid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", gid):
            problems.append(f"{where}.id must be a lower-case slug")
        elif gid in seen:
            problems.append(f"{where}.id {gid!r} is used twice")
        seen.add(gid)
        ms, kind, rung = g.get("milestone"), g.get("kind"), g.get("rung")
        if not isinstance(ms, int) or isinstance(ms, bool) or ms < 1:
            problems.append(f"{where}.milestone must be an issue number")
        if kind not in ("start", "close"):
            problems.append(f"{where}.kind must be start or close")
        if rung is not None and (not isinstance(rung, int) or isinstance(rung, bool) or not 0 <= rung <= 10):
            problems.append(f"{where}.rung must be 0 to 10")
        blockers = g.get("blocked_by")
        if not isinstance(blockers, list) or not blockers:
            problems.append(f"{where}.blocked_by must list at least one issue; a gate with no blockers is not a gate")
            blockers = []
        bad = [b for b in blockers if not isinstance(b, int) or isinstance(b, bool) or b < 1]
        if bad:
            problems.append(f"{where}.blocked_by has entries that are not issue numbers: {bad}")
        if ms in blockers:
            problems.append(f"{where} blocks on its own milestone #{ms}")
        if len(set(blockers)) != len(blockers):
            problems.append(f"{where}.blocked_by lists an issue twice")
        title = g.get("title")
        if not isinstance(title, str) or not title.strip():
            problems.append(f"{where}.title must give the start of the milestone issue's title, so a mistyped number cannot gate the wrong issue")
            title = ""
        waived = g.get("waived") or []
        if not isinstance(waived, list) or any(w not in blockers for w in waived):
            problems.append(f"{where}.waived may only name issues in blocked_by")
            waived = []
        if not bad and isinstance(gid, str) and isinstance(ms, int) and isinstance(kind, str):
            gates.append(
                Gate(
                    id=gid,
                    milestone=ms,
                    kind=kind,
                    blocked_by=list(blockers),
                    why=str(g.get("why") or "").strip(),
                    rung=rung,
                    waived=list(waived),
                    title=title.strip(),
                )
            )
    if problems:
        raise SpecError("; ".join(problems))
    return Spec(str(repo), gates)


# ---------------------------------------------------------------------------------------- GitHub reads


def _token() -> str | None:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


def _get(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "kit-gates"})
    if tok := _token():
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def fetch_github(repo: str) -> dict[int, Issue]:
    """Every issue and pull request in the repo, open and closed. Raises OSError when GitHub cannot be read."""
    out: dict[int, Issue] = {}
    for state in ("open", "closed"):
        for page in range(1, 11):
            rows = _get(f"{API}/repos/{repo}/issues?state={state}&per_page=100&page={page}")
            for r in rows:
                pr = r.get("pull_request")
                out[int(r["number"])] = Issue(
                    int(r["number"]), str(r.get("title", "")), str(r["state"]), r.get("state_reason"), pr is not None, bool(pr and pr.get("merged_at"))
                )
            if len(rows) < 100:
                break
    return out


def cached(fetch: Fetcher, root: Path, max_age: float = CACHE_SECONDS) -> Fetcher:
    """Wrap a fetcher with a short on-disk cache under out/ (ignored by git)."""

    def go(repo: str) -> dict[int, Issue]:
        path = root / CACHE_FILE
        try:
            blob = json.loads(path.read_text())
            if blob.get("repo") == repo and time.time() - float(blob["at"]) < max_age:
                return {int(k): Issue(**v) for k, v in blob["issues"].items()}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        issues = fetch(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"repo": repo, "at": time.time(), "issues": {n: i.__dict__ for n, i in issues.items()}}))
        return issues

    return go


def offline(repo: str) -> dict[int, Issue]:
    raise OSError("offline (KIT_OFFLINE is set)")


def default_fetcher(root: Path, fresh: bool = False) -> Fetcher:
    if os.environ.get("KIT_OFFLINE"):
        return offline
    return fetch_github if fresh else cached(fetch_github, root)


# -------------------------------------------------------------------------------------------- verdicts


def _done(issue: Issue, waived: bool) -> bool:
    if issue.is_pr:
        return issue.merged
    if issue.state != "closed":
        return False
    return issue.reason in (None, "completed") or waived


def evaluate(spec: Spec, fetch: Fetcher) -> list[Verdict]:
    try:
        issues = fetch(spec.repo)
        error = None
    except (OSError, urllib.error.URLError, ValueError) as e:
        issues, error = {}, f"cannot read GitHub ({e}); a gate nobody can see is not clear"
    verdicts = []
    for g in spec.gates:
        if error:
            verdicts.append(Verdict(g, "unknown", [], list(g.blocked_by), error))
            continue
        ms = issues.get(g.milestone)
        if ms is None or not ms.title.startswith(g.title):
            actual = f"it is {ms.title!r}" if ms else "GitHub has no such issue"
            verdicts.append(
                Verdict(
                    g, "unknown", [], [g.milestone], f"milestone #{g.milestone} should start {g.title!r}, but {actual}: check the number in {GATES_FILE}", False
                )
            )
            continue
        unseen = [n for n in g.blocked_by if n not in issues]
        pending = [n for n in g.blocked_by if n in issues and not _done(issues[n], n in g.waived)]
        if unseen:
            status, detail = "unknown", f"no such issue or pull request: {', '.join(f'#{n}' for n in unseen)}"
        elif pending:
            words = [f"#{n} {'unmerged' if issues[n].is_pr else 'closed as not planned' if issues[n].state == 'closed' else 'open'}" for n in pending]
            status, detail = "blocked", ", ".join(words)
        else:
            status, detail = "clear", f"{len(g.blocked_by)} blockers done"
        verdicts.append(Verdict(g, status, pending, unseen, detail))
    return verdicts


def describe(v: Verdict) -> str:
    what = f"{v.gate.id} (#{v.gate.milestone})"
    verb = "start" if v.gate.kind == "start" else "close"
    word = {"clear": "CLEAR  ", "blocked": "BLOCKED", "unknown": "UNKNOWN"}[v.status]
    tail = f"may {verb}" if v.clear else f"may not {verb}: {v.detail}"
    return f"gate    {what:24} {word} {tail}"


def run(root: Path, milestone: int | None = None, as_json: bool = False, fetch: Fetcher | None = None, ungated: bool = False) -> int:
    try:
        spec = load_spec(root)
    except SpecError as e:
        print(f"gates   {GATES_FILE} is broken: {e}")
        return 1
    fetch = fetch or default_fetcher(root, fresh=milestone is not None)
    try:
        snapshot = fetch(spec.repo)
    except (OSError, urllib.error.URLError, ValueError) as e:
        if milestone is not None:
            print(f"gates   cannot read GitHub ({e}), so nothing about #{milestone} can be answered: a gate nobody can see is not clear")
            return 1
        snapshot = None
        error: Exception | None = e
    else:
        error = None

    def from_snapshot(repo: str) -> dict[int, Issue]:
        if snapshot is None:
            raise OSError(str(error))
        return snapshot

    verdicts = evaluate(spec, from_snapshot)
    if milestone is not None:
        # Before answering about one milestone, every gate must name the issue it says it does. Otherwise a gate
        # mistyped onto another issue would vanish from the query for the issue it was meant to hold.
        misnamed = [v for v in verdicts if not v.identity_ok]
        if misnamed:
            for v in misnamed:
                print(describe(v))
            print(f"gates   {len(misnamed)} gate(s) do not name the issue they claim, so no question about #{milestone} can be answered: fix {GATES_FILE}")
            return 1
        unreachable = [v for v in verdicts if v.status == "unknown" and v.detail.startswith("cannot read GitHub")]
        if unreachable:
            print(f"gates   {unreachable[0].detail}")
            return 1
        verdicts = [v for v in verdicts if v.gate.milestone == milestone]
        if not verdicts:
            # No gate names it. That is only an answer if the caller says they expected it, and the issue exists.
            title = ((snapshot or {}).get(milestone) or Issue(milestone, "", "")).title
            if not title:
                print(f"gates   GitHub has no issue #{milestone}: check the number")
                return 1
            if not ungated:
                print(
                    f"gates   no gate names #{milestone} ({title!r}). If that is the issue you mean and it has no gate, "
                    f"say so: kit gates --milestone {milestone} --ungated"
                )
                return 1
            print(f"gates   #{milestone} {title!r}: no gate names it, so nothing blocks it")
            return 0
    if as_json:
        print(
            json.dumps(
                [
                    {"id": v.gate.id, "milestone": v.gate.milestone, "kind": v.gate.kind, "status": v.status, "pending": v.pending, "unseen": v.unseen}
                    for v in verdicts
                ],
                indent=2,
            )
        )
    else:
        for v in verdicts:
            print(describe(v))
            if not v.clear and v.gate.why:
                print(f"        why: {v.gate.why}")
    return 0 if all(v.clear for v in verdicts) else 1

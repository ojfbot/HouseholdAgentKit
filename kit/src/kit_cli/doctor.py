"""kit doctor: one plain status line per rung of the integration ladder (docs/ladder.md).

Rules this file enforces on itself:

* A check gates a rung only if it carries at least one proof: a deliberately broken setup it must turn
  red on, and a working setup it must turn green on. `kit doctor --self-test` runs every proof; a check
  without one is rejected at import time. (shared handover, "How a bad check is kept from costing a week".)
* Checks take the repo root as an argument and never assume a host, so a proof can point them at a broken copy.
* Rungs 3-10 need the owner's machines. They have no check here yet, and doctor says so instead of guessing.

* Gates (docs/gates.yaml, kit_cli.gates) decide what may start or close. A rung whose gate is blocked or
  unknown never reads GREEN, and `next` never says "climb" a rung whose start gate is not clear.

* A check that is known to pass some broken setup carries a `hole` naming it and its issue. Its rung line and
  the self-test summary say "unproven" until the hole is closed, so a green never hides a known gap.

* Date lines ask the gate behind the date. A date that has arrived stays on the page, red, until that gate passes.

Exit codes: 0 every rung up to --rung is green and its gate clear; 1 a rung is red or gated; 2 usage error.
The review, gate and date lines are about what comes after --rung and never change the exit code: CI runs
`kit doctor --rung 2`, and a date must not turn it red with no commit to blame (R-02). `--rung 3` exits 1 on them.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

from kit_cli import check as check_mod
from kit_cli import gates as gates_mod
from kit_cli import lint as lint_mod
from kit_cli import privacy as privacy_mod

ROOT = Path(__file__).resolve().parents[3]
REGISTER = "docs/integration-risk-register.md"
FAKE_KEY = "sk-" + "ant-api03-" + "Q" * 32  # built at run time, so no key-shaped string is ever tracked
# GitHub-hosted runner labels, listed one by one. A pattern such as `ubuntu-*` also matches any label someone gives a
# self-hosted runner, so a new label is added here, by the owner, when GitHub ships it.
HOSTED = frozenset(
    {
        "ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04", "ubuntu-24.04-arm", "ubuntu-22.04-arm",
        "macos-latest", "macos-15", "macos-14", "macos-13",
        "windows-latest", "windows-2025", "windows-2022",
    }
)  # fmt: skip
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "out", ".pytest_cache", ".ruff_cache"}

RUNG_TITLES = {
    0: "audit",
    1: "repo and CI",
    2: "runs on this host",
    3: "fleet conventions",
    4: "fleet member",
    5: "runs on the second host",
    6: "handoff service",
    7: "fleet proof job",
    8: "first real job",
    9: "local models",
    10: "demo bundle",
}


@dataclass
class Result:
    ok: bool
    detail: str


@dataclass
class Proof:
    """One planted break. `needs` are copied from the real repo into a temp root, then `breaker` damages the copy."""

    name: str
    breaker: Callable[[Path], None]
    # Something outside the files that the break needs while the check runs (a held port, an environment
    # variable): a context manager given the working copy and the broken copy.
    around: Callable[[Path, Path], AbstractContextManager[None]] | None = None
    # A break that is in the host, not in the files (another interpreter): run this on the copy instead of the check.
    fn: Callable[[Path], Result] | None = None


@dataclass
class Check:
    id: str
    rung: int
    fn: Callable[[Path], Result]
    needs: list[str]
    proofs: list[Proof] = field(default_factory=list)
    host: bool = False  # true: the answer depends on the machine, so CI's green says nothing about a real host
    hole: str = ""  # "#<issue> [n]: <a broken setup this check still passes>"; printed as unproven until closed

    def __post_init__(self) -> None:
        if not self.proofs:
            raise ValueError(f"check {self.id} has no proof; a check that cannot catch a known break does not gate")


# ----------------------------------------------------------------------------------------------- helpers


def _files(root: Path) -> list[str]:
    if (root / ".git").exists():
        # NUL-delimited: in newline output git quotes a path with non-ASCII bytes, and the quoted form names no file.
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root, capture_output=True)
        if out.returncode == 0:
            return [f for f in out.stdout.decode("utf-8", "surrogateescape").split("\0") if f and (root / f).exists()]
    found = []
    for p in root.rglob("*"):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS):
            found.append(p.relative_to(root).as_posix())
    return found


def _members(root: Path) -> list[str]:
    return tomllib.loads((root / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"]


def _workflows(root: Path) -> dict[str, dict]:
    return {p.name: yaml.safe_load(p.read_text()) or {} for p in sorted((root / ".github/workflows").glob("*.y*ml"))}


def _ports(root: Path) -> dict[str, int]:
    return yaml.safe_load((root / "contracts/ports.yaml").read_text())["ports"]


# ------------------------------------------------------------------------------------------------ rung 0


def _register_rows(text: str, heading: str) -> list[str]:
    """The first cell of each data row of the first table under a heading, without its backticks."""
    section = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M)
    if not section:
        return []
    cells = [ln.split("|")[1].strip() for ln in section.group(1).splitlines() if ln.startswith("|") and ln.count("|") >= 3]
    return [c.strip("`") for c in cells[2:]]  # the first two table lines are the header and its rule


def register_covers_packages(root: Path) -> Result:
    text = (root / REGISTER).read_text() if (root / REGISTER).exists() else ""
    units = [*_members(root), *(p.parent.relative_to(root).as_posix() for p in root.glob("apps/*/server"))]
    units += [p.relative_to(root).as_posix() for p in root.glob("packages/*") if p.is_dir() and p.relative_to(root).as_posix() not in units]
    # A row in the assumptions table is what "audited" means. The name turning up elsewhere on the page is not a row.
    rows = set(_register_rows(text, "Per-package assumptions"))
    missing = [u for u in sorted(set(units)) if u not in rows]
    return Result(
        not missing,
        f"every package has a row in the assumptions table ({len(set(units))})" if not missing else f"no risk-register row for: {', '.join(missing)}",
    )


PLACEHOLDER = re.compile(r"^(tbd|todo|tba|pending|none|n/?a|unknown|someone|reviewer|-+|\?+)\.?$", re.I)


ReviewFetcher = Callable[[str, int, int], dict]  # (repo, pull number, review id) -> the GitHub review object
Ancestry = Callable[[Path, str], bool | None]  # (root, sha) -> True / False, or None when it cannot be checked
REVIEW_URL = re.compile(r"https://github\.com/(?P<repo>[\w.-]+/[\w.-]+)/pull/(?P<pr>\d+)#pullrequestreview-(?P<id>\d+)")


def fetch_review(repo: str, pr: int, review_id: int) -> dict:
    """One GitHub review, read live. Raises OSError when GitHub cannot be read (or KIT_OFFLINE is set)."""
    if os.environ.get("KIT_OFFLINE"):
        raise OSError("offline (KIT_OFFLINE is set)")
    import urllib.request

    req = urllib.request.Request(
        f"{gates_mod.API}/repos/{repo}/pulls/{pr}/reviews/{review_id}", headers={"Accept": "application/vnd.github+json", "User-Agent": "kit-doctor"}
    )
    if tok := os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def is_ancestor(root: Path, sha: str) -> bool | None:
    if not (root / ".git").exists() or not shutil.which("git"):
        return None
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=root, capture_output=True).returncode == 0


def review_recorded(root: Path, today: date | None = None, fetch: ReviewFetcher | None = None, ancestry: Ancestry | None = None) -> Result:
    """Rung 3 may start only on evidence that can be checked, not on text anyone can type.

    The register's `## Independent review` section must say `Status: recorded`, name the reviewer, give a real date,
    the reviewed commit, and link the review itself (`Review: https://github.com/<repo>/pull/<n>#pullrequestreview-<id>`).
    Doctor then reads that review from GitHub and requires: submitted (not pending or dismissed), on the recorded
    commit, on the recorded date, on this repo, signed with a line `Reviewer: <the recorded name>`, and the commit an
    ancestor of HEAD. Whatever cannot be checked (no network, no git, no repo in docs/gates.yaml) counts as not recorded.

    What GitHub cannot show is that the reviewer was a different model: the owner and the agents share one GitHub
    identity (Q-I-1). Until reviewers have their own identities, independence is the owner's attestation, recorded as
    `Independence: attested by the owner on <date>`, and doctor reports it as attested, never as proven."""
    fetch, ancestry = fetch or fetch_review, ancestry or is_ancestor
    text = (root / REGISTER).read_text() if (root / REGISTER).exists() else ""
    m = re.search(r"^## Independent review\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return Result(False, "no independent review section in the risk register (send docs/ladder-review-request.md)")
    body, missing = m.group(1), []

    def field_(name: str) -> str:
        f = re.search(rf"^- {name}: *(.*)$", body, re.M)
        return f.group(1).strip() if f else ""

    if not re.match(r"recorded\b", field_("Status")):
        missing.append(f"status is {field_('Status')[:40] or 'missing'!r}, not 'recorded'")
    reviewer = field_("Reviewer")
    if len(reviewer) < 3 or PLACEHOLDER.match(reviewer):
        missing.append(f"reviewer {reviewer or 'missing'!r} names nobody")
    when = None
    try:
        when = date.fromisoformat(field_("Date")[:10])
        if when > (today or date.today()):
            missing.append(f"date {when} is in the future")
    except ValueError:
        missing.append(f"date {field_('Date')[:20] or 'missing'!r} is not a real date")
    sha_m = re.search(r"\b[0-9a-f]{7,40}\b", field_("Reviewed"))
    sha = sha_m.group(0) if sha_m else None
    if not sha:
        missing.append("no reviewed commit (a 7 to 40 character hash on the `Reviewed:` line)")
    url = REVIEW_URL.search(field_("Review"))
    if not url:
        missing.append("no link to the review itself (`Review: https://github.com/<repo>/pull/<n>#pullrequestreview-<id>`)")
    attested = re.match(r"attested by the owner on (\d{4}-\d\d-\d\d)\b", field_("Independence"))
    if not attested:
        missing.append("independence is not attested by the owner (`Independence: attested by the owner on <date>`; GitHub cannot show it, Q-I-1)")
    if missing:
        return Result(False, "independent review not recorded: " + "; ".join(missing))
    assert sha and url and when
    try:
        spec_repo = gates_mod.load_spec(root).repo
    except gates_mod.SpecError as e:
        return Result(False, f"independent review not verified: cannot tell which repo it must be on ({gates_mod.GATES_FILE}: {e})")
    if url["repo"].lower() != spec_repo.lower():
        missing.append(f"the review is on {url['repo']}, not {spec_repo}")
    try:
        rv = fetch(url["repo"], int(url["pr"]), int(url["id"]))
    except (OSError, ValueError) as e:
        return Result(False, f"independent review not verified: cannot read it on GitHub ({e}); a review nobody can see is not recorded")
    if rv.get("state") not in ("COMMENTED", "APPROVED", "CHANGES_REQUESTED"):
        missing.append(f"the review's state is {rv.get('state')!r}, not submitted")
    if not str(rv.get("commit_id", "")).startswith(sha):
        missing.append(f"the review is of commit {str(rv.get('commit_id', ''))[:7] or '?'}, not {sha}")
    if str(rv.get("submitted_at", ""))[:10] != when.isoformat():
        missing.append(f"the review was submitted {str(rv.get('submitted_at', ''))[:10] or '?'}, not {when}")
    signed = re.search(rf"^[ \t>*_]*Reviewer[*_]*:[*_ \t]*{re.escape(reviewer)}[ \t*_.]*$", str(rv.get("body", "")), re.M | re.I)
    if not signed:
        missing.append(f"the review is not signed `Reviewer: {reviewer}` on a line of its own (a name in passing does not count)")
    anc = ancestry(root, sha)
    if anc is None:
        missing.append(f"cannot check that {sha} is in this branch's history (no git checkout)")
    elif not anc:
        missing.append(f"reviewed commit {sha} is not an ancestor of HEAD")
    if missing:
        return Result(False, "independent review not verified: " + "; ".join(missing))
    assert attested
    return Result(
        True, f"review verified on GitHub: {reviewer}, {when}, commit {sha}; independence attested by the owner on {attested.group(1)}, not proven (Q-I-1)"
    )


# ------------------------------------------------------------------------------------------------ rung 1


UV_ENV_KEPT = {
    "UV_CACHE_DIR",
    "UV_PYTHON",
    "UV_PYTHON_INSTALL_DIR",
    "UV_PYTHON_DOWNLOADS",
    "UV_PYTHON_PREFERENCE",
    "UV_OFFLINE",
    "UV_NATIVE_TLS",
    "UV_LINK_MODE",
}


def _uv(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run uv on exactly this root. Every other UV_* setting is dropped, because several of them change what is
    checked: UV_FROZEN turns `uv lock --check` into a no-op (R-06), UV_PROJECT points it at another project."""
    env = {k: v for k, v in os.environ.items() if not (k.startswith("UV_") and k not in UV_ENV_KEPT) and k != "VIRTUAL_ENV"}
    return subprocess.run(["uv", *args, "--project", str(root)], cwd=root, capture_output=True, text=True, env=env)


def lock_fresh(root: Path) -> Result:
    if not shutil.which("uv"):
        return Result(False, "uv is not installed")
    out = _uv(root, "lock", "--check")
    return Result(out.returncode == 0, "uv.lock matches the pyproject files" if out.returncode == 0 else "uv.lock is stale: run `uv lock` and commit it")


def workspace_wired(root: Path) -> Result:
    members = set(_members(root))
    # Every pyproject.toml in the repo, wherever it sits, is a project CI must install and test; the root is the workspace.
    on_disk = {Path(f).parent.as_posix() for f in _files(root) if Path(f).name == "pyproject.toml" and Path(f).parent != Path(".")}
    unwired, ghosts = sorted(on_disk - members), sorted(m for m in members if not (root / m / "pyproject.toml").exists())
    if unwired or ghosts:
        return Result(
            False,
            "; ".join(
                filter(
                    None, [f"not a workspace member: {', '.join(unwired)}" if unwired else "", f"member missing on disk: {', '.join(ghosts)}" if ghosts else ""]
                )
            ),
        )
    return Result(True, f"{len(members)} workspace members wired, and no other pyproject.toml in the repo")


CONSOLE_CONFIG_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
import host
print(json.dumps({"as the console loads it": host.load_config(None), "console.example.json": host.load_config(sys.argv[2])}))
"""
PORT_SERVICES = ("console", "engine", "poll_bus", "model")


def _url_port(url: object) -> int | None:
    from urllib.parse import urlsplit

    try:
        return urlsplit(str(url)).port if url else None
    except ValueError:
        return None


def ports_agree(root: Path) -> Result:
    ports = _ports(root)
    absent = [name for name in PORT_SERVICES if name not in ports]
    if absent:
        return Result(False, f"contracts/ports.yaml has no port for: {', '.join(absent)}")
    dupes = sorted(k for k, v in ports.items() if list(ports.values()).count(v) > 1)
    if dupes:
        return Result(False, f"two services share a default port: {', '.join(dupes)}")
    # The console's ports are read from the config it actually loads, not from literals in its source: once with
    # no file named (its defaults, plus a console.json if this checkout has one), once from the example file.
    app = root / "apps/demo-console"
    probe = subprocess.run(
        [sys.executable, "-c", CONSOLE_CONFIG_PROBE, str(app / "server"), str(app / "console.example.json")], cwd=root, capture_output=True, text=True
    )
    if probe.returncode != 0:
        return Result(False, f"the console's config could not be loaded: {probe.stderr.strip()[-200:]}")
    configs = json.loads(probe.stdout)
    m = re.search(r'"--port", type=int, default=(\d+)', (root / "packages/discovery-engine/src/discovery_engine/cli.py").read_text())
    found: list[tuple[str, int | None, int]] = [("engine (cli default)", int(m.group(1)) if m else None, ports["engine"])]
    for where, cfg in configs.items():
        found.append((f"console ({where})", cfg.get("port"), ports["console"]))
        found.append((f"engine, where the console looks for it ({where})", _url_port(cfg.get("engine_url")), ports["engine"]))
        found.append((f"model, where the console looks for it ({where})", _url_port(cfg.get("model_url")), ports["model"]))
        if cfg.get("poll_bus_url") or where == "console.example.json":  # unset by default; the example must say where it is
            found.append((f"poll bus, where the console looks for it ({where})", _url_port(cfg.get("poll_bus_url")), ports["poll_bus"]))
    bad = [f"{name} is {got if got is not None else 'not set'}, registry says {want}" for name, got, want in found if got != want]
    return Result(not bad, f"the loaded configs match contracts/ports.yaml for all {len(PORT_SERVICES)} services, no collisions" if not bad else "; ".join(bad))


def runners_hosted(root: Path) -> Result:
    bad = []
    for name, wf in _workflows(root).items():
        triggers = wf.get(True, wf.get("on", {})) or {}  # YAML reads the key `on` as boolean true
        if "pull_request_target" in (triggers if isinstance(triggers, (dict, list)) else [triggers]):
            bad.append(f"{name}: pull_request_target runs fork code with repo secrets")
        for job_id, job in (wf.get("jobs") or {}).items():
            runs_on = job.get("runs-on")
            labels = runs_on if isinstance(runs_on, list) else [runs_on]
            # Exactly one hosted image: a runner must carry every label listed, and no hosted runner carries two images.
            if len(labels) != 1 or not isinstance(labels[0], str) or labels[0] not in HOSTED:
                bad.append(f"{name}:{job_id} runs-on {runs_on!r} is not provably a GitHub-hosted runner")
    if not _workflows(root):
        return Result(False, "no workflows found")
    return Result(not bad, "every job runs on a GitHub-hosted runner" if not bad else "; ".join(bad))


def _job_needs(job: dict) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else [str(n) for n in needs]


def required_checks_exist(root: Path) -> Result:
    ruleset = json.loads((root / ".github/rulesets/main.json").read_text())
    want = [c["context"] for r in ruleset["rules"] if r["type"] == "required_status_checks" for c in r["parameters"]["required_status_checks"]]
    if not want:
        return Result(False, "the ruleset requires no status checks")
    workflows = _workflows(root)
    # GitHub reports a job under its `name:` when it has one, and under its id otherwise.
    emitted = {str(job.get("name") or job_id): (wf_name, job_id) for wf_name, wf in workflows.items() for job_id, job in (wf.get("jobs") or {}).items()}
    missing = [c for c in want if c not in emitted]
    if missing:
        return Result(False, f"the ruleset requires checks no workflow produces (merges would block forever): {', '.join(missing)}")
    problems = []
    covered: dict[str, set[str]] = {}  # workflow -> jobs whose failure a required check reports
    for c in want:
        wf_name, job_id = emitted[c]
        job = (workflows[wf_name].get("jobs") or {})[job_id]
        needs = _job_needs(job)
        covered.setdefault(wf_name, set()).update({job_id, *needs})
        # A required job that needs others is skipped, not failed, when one of them fails, unless it is an
        # aggregate: `if: always()` and one step that fails unless every need succeeded (kit check's definition).
        if needs and not check_mod.is_aggregate(job):
            problems.append(f"`{c}` ({wf_name}) needs {', '.join(needs)} but is not an aggregate, so a failure there leaves it skipped, not red")
    # Every job in a workflow that has a required check must be required itself or reported by a required aggregate.
    for wf_name, jobs_seen in covered.items():
        loose = sorted(set(workflows[wf_name].get("jobs") or {}) - jobs_seen)
        if loose:
            problems.append(f"{wf_name}: no required check fails when these fail: {', '.join(loose)}")
    if problems:
        return Result(False, "; ".join(problems))
    return Result(
        True, f"required checks all exist as jobs, and every job in their workflows is required or reported by a required aggregate: {', '.join(want)}"
    )


def no_forbidden_files(root: Path) -> Result:
    """The path half of the privacy guard: the same rules and allowlist as `kit privacy scan` (one shared list)."""
    left, _ = privacy_mod.check(root)
    bad = sorted({f.path for f in left if f.rule in privacy_mod.PATH_RULES})
    return Result(not bad, "no weights, seeds, secrets or generated data in the tree" if not bad else f"must not be in the repo: {', '.join(bad[:5])}")


def privacy_clean(root: Path) -> Result:
    left, problems = privacy_mod.check(root)
    if left or problems:
        shown = [f.show() for f in left[:2]] + problems[:2]
        return Result(False, f"{len(left)} findings, {len(problems)} allowlist problems: " + "; ".join(shown))
    return Result(True, f"every rule on all {len(privacy_mod.files(root))} files; exceptions only from {privacy_mod.ALLOW_FILE}")


# The files vendored from Fork C. Pinned here so that emptying or trimming SHA256SUMS cannot shrink what is checked.
VENDORED = ("bank.py", "bank_v2.py", "score_v2.py", "rubric-v2.yaml", "controls-v1.yaml", "lattice-v1.yaml")
VENDORED_NOTES = {"SHA256SUMS", "SOURCE.md"}


def vendored_verbatim(root: Path) -> Result:
    base = root / "packages/discovery-engine/prototypes/fork_c"
    sums: dict[str, str] = {}
    for line in (base / "SHA256SUMS").read_text().splitlines() if (base / "SHA256SUMS").exists() else []:
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            return Result(False, f"SHA256SUMS has a line that is not `<sha256>  <file>`: {line[:60]!r}")
        sums[parts[1]] = parts[0]
    unsummed = [n for n in VENDORED if n not in sums]
    if unsummed:
        return Result(False, f"SHA256SUMS has no checksum for: {', '.join(unsummed)} (parity no longer means parity with Fork C)")
    on_disk = {p.name for p in base.iterdir() if p.is_file()} if base.is_dir() else set()
    unpinned = sorted((set(sums) | on_disk) - set(VENDORED) - VENDORED_NOTES)
    if unpinned:
        return Result(False, f"in fork_c but not in doctor's pinned list of vendored files: {', '.join(unpinned)}")
    bad = [n for n in VENDORED if not (base / n).exists() or hashlib.sha256((base / n).read_bytes()).hexdigest() != sums[n]]
    return Result(
        not bad,
        f"Fork C's {len(VENDORED)} vendored files are byte-identical to the import"
        if not bad
        else f"vendored file changed or missing (parity no longer means parity with Fork C): {', '.join(bad)}",
    )


def ci_runs_locally(root: Path) -> Result:
    plan = check_mod.steps(root)
    if not plan:
        return Result(False, "no pull-request workflow has a run step: `kit check` would run nothing")
    bad = check_mod.runner_only(root)
    return Result(not bad, f"`kit check` runs all {len(plan)} pull-request steps as CI does" if not bad else "; ".join(bad[:3]))


def lint_policy_covers(root: Path) -> Result:
    try:
        policy = lint_mod.load_policy(root)
    except (OSError, ValueError) as e:
        return Result(False, f"{lint_mod.POLICY_FILE}: {e}")
    trees = [*policy["full"], *policy["ratchet"], *(policy.get("exempt") or {})]
    ghosts = [t for t in trees if not (root / t).exists()]
    loose = [f for f in _files(root) if f.endswith(".py") and not any(f == t or f.startswith(t.rstrip("/") + "/") for t in trees)]
    if ghosts or loose:
        why = [
            f"names trees that do not exist: {', '.join(ghosts)}" if ghosts else "",
            f"Python files no lint tier covers: {', '.join(loose[:5])}" if loose else "",
        ]
        return Result(False, "; ".join(filter(None, why)))
    return Result(True, f"every tracked .py file is under a lint tier ({len(policy['full'])} full, {len(policy['ratchet'])} ratchet)")


def hooks_runnable(root: Path) -> Result:
    import contextlib
    import io

    from kit_cli.__main__ import build_parser

    path = root / ".pre-commit-config.yaml"
    if not path.exists():
        return Result(False, "no .pre-commit-config.yaml: nothing runs before a commit")
    cfg = yaml.safe_load(path.read_text()) or {}
    files, bad, hooks = _files(root), [], 0
    for repo in cfg.get("repos") or []:
        if repo.get("repo") != "local":
            bad.append(f"{repo.get('repo')}: a remote hook downloads its own tool version, outside uv.lock")
            continue
        for h in repo.get("hooks") or []:
            hooks += 1
            hid, words = h.get("id", "?"), str(h.get("entry", "")).split()
            if h.get("language") != "system":
                bad.append(f"{hid}: language {h.get('language')!r} builds its own toolchain at commit time")
            if words[:3] == ["uv", "run", "kit"]:
                try:
                    with contextlib.redirect_stderr(io.StringIO()):
                        build_parser().parse_args(words[3:])
                except SystemExit:
                    bad.append(f"{hid}: `kit {' '.join(words[3:])}` is not a kit command")
            elif words[:2] == ["uv", "run"]:
                if len(words) < 3 or not (Path(sys.executable).parent / words[2]).exists():
                    bad.append(f"{hid}: `{' '.join(words[:3])}` is not installed by uv.lock")
            elif not words or not shutil.which(words[0]):
                bad.append(f"{hid}: `{words[0] if words else ''}` is not on PATH")
            pattern = h.get("files")
            if pattern and not any(re.search(pattern, f) for f in files):
                bad.append(f"{hid}: files {pattern!r} matches no tracked file, so the hook never runs")
    if not hooks:
        bad.append("no hooks defined")
    return Result(not bad, f"{hooks} pre-commit hooks, every command exists" if not bad else "; ".join(bad[:3]))


def gates_wellformed(root: Path) -> Result:
    try:
        spec = gates_mod.load_spec(root)
    except gates_mod.SpecError as e:
        return Result(False, f"{gates_mod.GATES_FILE}: {e}")
    return Result(True, f"{len(spec.gates)} gates, every blocker an issue number")


# ------------------------------------------------------------------------------------------------ rung 2


@dataclass(frozen=True)
class Interpreter:
    """What `sys` says about a Python: enough to tell a release of CPython from anything else with the same numbers."""

    implementation: str  # sys.implementation.name
    version: tuple[int, int, int]
    releaselevel: str  # "final" for a release; "alpha", "beta" or "candidate" otherwise

    @classmethod
    def this(cls) -> Interpreter:
        return cls(sys.implementation.name, (sys.version_info.major, sys.version_info.minor, sys.version_info.micro), sys.version_info.releaselevel)

    @classmethod
    def release(cls, numbers: str) -> Interpreter:
        major, minor, micro = (int(x) for x in numbers.split("."))
        return cls("cpython", (major, minor, micro), "final")

    def show(self) -> str:
        name = {"cpython": "CPython", "pypy": "PyPy"}.get(self.implementation, self.implementation)
        return f"{name} {'.'.join(map(str, self.version))}" + ("" if self.releaselevel == "final" else f" ({self.releaselevel})")


def python_pin(root: Path, running: Interpreter | None = None) -> Result:
    want = (root / ".python-version").read_text().strip()
    running = running or Interpreter.this()
    try:
        pinned = Interpreter.release(want)
    except ValueError:
        return Result(False, f".python-version is {want!r}, not a full version like 3.12.16")
    # The pin means a release of CPython. A release candidate or another implementation carries the same three numbers.
    return Result(running == pinned, running.show() if running == pinned else f"running {running.show()}, the pin is {pinned.show()}")


IMPORT_PROBE = """
import importlib, importlib.metadata as md, json, sys
workspace = json.loads(sys.argv[1])  # [[module, attribute or null], ...]: what the workspace's own code imports
unimportable, missing = [], []
for name in sorted(n for n in md.packages_distributions() if not n.startswith("_")):
    try:
        importlib.import_module(name)
    except Exception as e:
        unimportable.append(f"{name} ({type(e).__name__})")
for module, attr in workspace:
    try:
        importlib.import_module(f"{module}.{attr}" if attr else module)
    except ModuleNotFoundError as e:
        if not attr or e.name != f"{module}.{attr}":
            unimportable.append(f"{module}.{attr or ''} ({type(e).__name__}: {e})".replace(". (", " ("))
            continue
        try:
            getattr(importlib.import_module(module), attr)  # `from module import name` of a function or class
        except Exception as e2:
            unimportable.append(f"{module}.{attr} ({type(e2).__name__})")
    except Exception as e:
        unimportable.append(f"{module}.{attr or ''} ({type(e).__name__}: {e})")
for dist in md.distributions():
    for f in dist.files or []:
        if "__pycache__" not in f.parts and not f.locate().exists():
            missing.append(f"{dist.metadata['Name']}: {f}")
print(json.dumps({"unimportable": unimportable, "missing": missing}))
"""


def _workspace_imports(root: Path) -> list[tuple[str, str | None]]:
    """Every import of a workspace package by the workspace's own source, as (module, name or None).

    An editable install lists no source files in its metadata, so a deleted module is only noticed when
    something imports it; the `kit` commands import theirs inside functions. This finds each such import.
    """
    import ast

    packages: dict[str, Path] = {}  # import name -> its directory
    for member in _members(root):
        base = root / member / "src" if (root / member / "src").is_dir() else root / member
        for init in base.glob("*/__init__.py"):
            packages[init.parent.name] = init.parent
    found: set[tuple[str, str | None]] = set()
    for top, pkg_dir in packages.items():
        for py in pkg_dir.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            here = ".".join([top, *py.relative_to(pkg_dir).with_suffix("").parts]).removesuffix(".__init__")
            try:
                tree = ast.parse(py.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update((a.name, None) for a in node.names if a.name.split(".")[0] in packages)
                elif isinstance(node, ast.ImportFrom):
                    if node.level:  # relative: resolve against this module's package
                        parts = here.split(".")[: -node.level] if py.name != "__init__.py" else here.split(".")[: len(here.split(".")) - node.level + 1]
                        module = ".".join([*parts, *([node.module] if node.module else [])])
                    else:
                        module = node.module or ""
                    if module.split(".")[0] in packages:
                        found.update((module, a.name if a.name != "*" else None) for a in node.names)
    return sorted(found, key=lambda t: (t[0], t[1] or ""))


def sync_frozen(root: Path) -> Result:
    if not shutil.which("uv"):
        return Result(False, "uv is not installed")
    out = _uv(root, "sync", "--frozen", "--check")
    if out.returncode != 0:
        return Result(False, "environment differs from uv.lock: run `uv sync --frozen`")
    # uv compares metadata. A package whose files are gone but whose metadata is left still "matches", so ask the
    # environment's own interpreter, in a fresh isolated process, to import every installed module, every module the
    # workspace's own code imports from the workspace, and to find every installed file.
    python = root / ".venv/bin/python"
    if not python.exists():
        return Result(False, "environment has no interpreter at .venv/bin/python: run `uv sync --frozen`")
    targets = json.dumps(_workspace_imports(root))
    probe = subprocess.run([str(python), "-I", "-c", IMPORT_PROBE, targets], cwd=root, capture_output=True, text=True)
    if probe.returncode != 0:
        return Result(False, f"the environment's interpreter could not run the import probe: {probe.stderr.strip()[-160:]}")
    report = json.loads(probe.stdout)
    if report["unimportable"] or report["missing"]:
        shown = [*report["unimportable"][:3], *(f"missing file {m}" for m in report["missing"][:2])]
        return Result(False, "environment matches uv.lock on paper but is damaged (run `uv sync --frozen --reinstall`): " + "; ".join(shown))
    return Result(True, f"environment matches uv.lock; every installed module and the {len(json.loads(targets))} workspace imports resolve")


def hello_world_smoke(root: Path, hook: object | None = None) -> Result:
    from kit_eval import hello_world

    cases = root / "data/seeds/cases"
    if not any(cases.glob("*.yaml")):
        return Result(False, f"no hello-world cases under {cases.relative_to(root)}")
    res = hello_world.run("smoke", "doctor", hook=hook, cases_dir=cases)  # type: ignore[arg-type]
    zt = res.get("zero_tolerance") or {}
    broken = sorted(k for k, v in zt.items() if (v > 1 if k == "orders_per_mandate_max" else v))
    # A run with no cases passes every tier vacuously (0 of 0), so count what actually ran.
    ran = int(((res.get("tiers") or {}).get("0") or {}).get("cases") or 0)
    episodes = ran * int(res.get("k") or 0)
    ok = (
        res.get("result_version") == "hello_world_result@1"
        and res.get("status") in ("pass", "placement_only")
        and not broken
        and not res.get("failures")
        and episodes > 0
    )
    why = (
        f"status={res.get('status')}, {episodes} episodes over {ran} cases"
        + ("" if episodes else " (nothing ran, so nothing was checked)")
        + (f", zero-tolerance breaches: {', '.join(broken)}" if broken else "")
        + (f", {len(res['failures'])} failed episodes" if res.get("failures") else "")
    )
    unmeasured = len(res.get("zero_tolerance_not_measured") or [])
    return Result(ok, f"taco night smoke run: {why}" + (f" ({unmeasured} zero-tolerance metrics not measured yet)" if unmeasured else ""))


# Which attributes of which elements make a browser fetch something while the page loads. `a href` is not one.
LOADED_ATTRS = {
    "script": ("src",),
    "link": ("href",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "track": ("src",),
    "iframe": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "input": ("src",),
}
JS_IMPORT = re.compile(
    r"""(?:^|[;\n])\s*(?:import|export)\b[^;'"`]*?\bfrom\s*(["'])(.+?)\1"""  # import x from "m"; export {x} from "m"
    r"""|(?:^|[;\n])\s*import\s*(["'])(.+?)\3"""  # import "m"
    r"""|\bimport\(\s*(["'])(.+?)\5\s*\)"""  # import("m")
    r"""|\bimport\(\s*`([^`$]*)`\s*\)"""  # import(`m`), a template literal with no ${...} in it
)
SRCSET_URL = re.compile(r"\s*(\S+)(?:\s+[^,]*)?,?")
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
CSS_REF = re.compile(r"""@import\s+(["'])(.+?)\1|url\(\s*(["'])(.*?)\3\s*\)|url\(\s*([^"')\s][^)\s]*)\s*\)""")


def urlpath(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).path


def html_refs(html: str, page_url: str) -> list[str]:
    """Absolute URLs of what a browser fetches while loading this page, resolved against the first `<base href>`.

    An HTML parser, not a pattern: it skips comments, takes any spacing or quoting around `=`, and reads `srcset`.
    """
    from html.parser import HTMLParser
    from urllib.parse import urljoin

    found: list[tuple[str, str]] = []  # (tag, raw reference)
    base: list[str] = []

    class Collect(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = {k: v for k, v in attrs if v is not None}
            if tag == "base" and "href" in values and not base:
                base.append(values["href"])
            for attr in LOADED_ATTRS.get(tag, ()):
                value = values.get(attr, "").strip()
                if not value:
                    continue
                if attr == "srcset":  # "url [descriptor], ...": the URL runs to whitespace and may itself hold commas
                    found.extend((tag, m.group(1).rstrip(",")) for m in SRCSET_URL.finditer(value))
                else:
                    found.append((tag, value))

        handle_startendtag = handle_starttag

    Collect(convert_charrefs=True).feed(html)
    root = urljoin(page_url, base[0]) if base else page_url
    return [urljoin(root, ref) for _, ref in found if not ref.startswith(("data:", "#", "javascript:"))]


def js_refs(js: str) -> list[str]:
    """Module specifiers a script imports. An import whose specifier is built at run time is out of scope."""
    return [m.group(2) or m.group(4) or m.group(6) or m.group(7) for m in JS_IMPORT.finditer(js)]


def css_refs(css: str) -> list[str]:
    """What a stylesheet fetches: each `@import` and `url()`, outside comments. A quoted URL may hold parentheses."""
    out = []
    for m in CSS_REF.finditer(CSS_COMMENT.sub("", css)):
        ref = (m.group(2) or m.group(4) or m.group(5) or "").strip()
        if ref and not ref.startswith(("data:", "#")):
            out.append(ref)
    return out


CONSOLE_PAGES = ("/", "/p")  # the stage and the phone join page


def _console_crawl(base: str) -> tuple[list[str], int]:
    """Fetch the console's pages and, transitively, every same-origin asset they reference. Returns (problems, fetched).

    A page that loads while its script, stylesheet or an imported module answers 404 is a blank screen on stage,
    so every reference in the HTML (parsed, `<base href>` honoured), every import in the JavaScript and every
    `@import` or `url()` in the CSS is fetched too. URLs a script builds at run time (the QR image, the
    recordings, an import whose specifier is computed) are not seen here.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    problems: list[str] = []
    seen: dict[str, str] = {}  # path -> what referenced it
    queue = [(page, "the console") for page in CONSOLE_PAGES]
    while queue:
        path, referrer = queue.pop(0)
        if path in seen:
            continue
        seen[path] = referrer
        try:
            with urllib.request.urlopen(base + path, timeout=2) as r:
                body, kind = r.read().decode(errors="replace"), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            problems.append(f"{path} (referenced by {referrer}) answered HTTP {e.code}")
            continue
        except OSError as e:
            problems.append(f"{path} (referenced by {referrer}) could not be fetched: {e}")
            continue
        if path in CONSOLE_PAGES:
            if "<html" not in body.lower():
                problems.append(f"{path} is not an HTML page")
                continue
            refs = html_refs(body, base + path)  # already resolved, against the page's <base href> if it has one
        elif path.endswith((".js", ".mjs")) or "javascript" in kind:
            refs = js_refs(body)  # a module resolves against its own URL
        elif path.endswith(".css") or "text/css" in kind:
            refs = css_refs(body)  # so does a stylesheet
        else:
            refs = []
        for ref in refs:
            target = urllib.parse.urlsplit(urllib.parse.urljoin(base + path, ref))
            if f"{target.scheme}://{target.netloc}" == base:  # same origin only: the console runs offline
                queue.append((target.path, path))
    return problems, len(seen)


def console_on_fixtures(root: Path) -> Result:
    app = root / "apps/demo-console"
    missing = [f for f in ("fixtures/engine/deltas.json", "fixtures/engine/readout.default.json") if not (app / f).exists()]
    if missing:
        return Result(False, "engine fixtures not built: run `python apps/demo-console/fixtures/build_engine_fixtures.py`")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "console.json"
        cfg.write_text(json.dumps({"bind": "127.0.0.1", "log_dir": str(Path(tmp) / "logs")}))
        proc = subprocess.Popen(
            [sys.executable, str(app / "server/host.py"), "--config", str(cfg), "--port", str(port)], cwd=app, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            import time
            import urllib.error
            import urllib.request

            last = "no answer"
            for _ in range(40):
                if proc.poll() is not None:
                    return Result(False, f"console exited at start: {(proc.stderr.read() if proc.stderr else b'').decode()[-200:].strip()}")
                try:
                    with urllib.request.urlopen(f"{base}/api/health", timeout=1) as r:
                        if r.status != 200:
                            return Result(False, f"console answered HTTP {r.status} for its health check")
                    break
                except urllib.error.HTTPError as e:
                    return Result(False, f"console answered HTTP {e.code} for its health check")
                except OSError as e:
                    last = str(e)
                    time.sleep(0.25)
            else:
                return Result(False, f"console did not answer in 10 s ({last})")
            problems, fetched = _console_crawl(base)
            if problems:
                return Result(
                    False,
                    "console is up but its pages would not load: " + "; ".join(problems[:3]) + (f" (+{len(problems) - 3} more)" if len(problems) > 3 else ""),
                )
            if fetched <= len(CONSOLE_PAGES):
                return Result(False, "console pages reference no script or stylesheet; nothing would render")
            return Result(True, f"console serves its stage and phone pages and the {fetched - len(CONSOLE_PAGES)} assets they reference, on fixtures")
        finally:
            proc.terminate()
            proc.wait(timeout=5)


def ports_free(root: Path) -> Result:
    ports = _ports(root)
    unreal = [f"{name} {port!r}" for name, port in ports.items() if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535]
    if unreal:
        return Result(False, f"not a real port in contracts/ports.yaml (0 means any free port, so nothing would be checked): {', '.join(unreal)}")
    busy = []
    for name, port in ports.items():
        # Every service here listens on IPv4 (the console on 0.0.0.0, the engine on 127.0.0.1), so the port must be free
        # on every IPv4 address. A plain bind to the IPv4 wildcard fails when any one of them already holds it;
        # loopback alone would miss that. An IPv6-only listener does not stop an IPv4 bind, so it is not a clash.
        try:
            with socket.socket(socket.AF_INET) as s:
                s.bind(("0.0.0.0", port))
        except OSError as e:
            if e.errno != errno.EADDRINUSE:
                return Result(False, f"could not test {name} {port}: {e}")
            busy.append(f"{name} {port}")
    return Result(not busy, "default ports are free on every IPv4 address of this host" if not busy else f"already in use on this host: {', '.join(busy)}")


# ------------------------------------------------------------------------------------------------ proofs


class _BrokenHook:
    """The reference hook with one planted fault per episode, for the hello-world proofs."""

    def __init__(self, fault: str) -> None:
        from kit_eval.hook import ReferenceHook

        self.name, self.fault, self._inner = f"broken:{fault}", fault, ReferenceHook()

    def run_episode(self, case: dict, seed: int, run: int):  # type: ignore[no-untyped-def]
        r = self._inner.run_episode(case, seed, run)
        if self.fault == "lock" and r.outcome == "cart":
            r.lock_violations += 1
        if self.fault == "reject":
            r.accepted = False
        return r


def _rewrite(rel: str, old: str, new: str) -> Callable[[Path], None]:
    def go(root: Path) -> None:
        p = root / rel
        text = p.read_text()
        if old not in text:
            raise AssertionError(f"proof is stale: {old!r} not in {rel}")
        p.write_text(text.replace(old, new, 1))

    return go


def _write(rel: str, text: str = "x") -> Callable[[Path], None]:
    def go(root: Path) -> None:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)

    return go


def _write_bytes(rel: str, data: bytes) -> Callable[[Path], None]:
    def go(root: Path) -> None:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)

    return go


def _delete(rel: str) -> Callable[[Path], None]:
    return lambda root: (root / rel).unlink()


def _append(rel: str, text: str) -> Callable[[Path], None]:
    def go(root: Path) -> None:
        with (root / rel).open("a") as fh:
            fh.write(text)

    return go


WORKSPACE = ["pyproject.toml", "uv.lock", ".python-version", "kit/pyproject.toml", "packages/*/pyproject.toml"]
PORT_FILES = ["contracts/ports.yaml", "packages/discovery-engine/src/discovery_engine/cli.py", "apps/demo-console/server/host.py"]
CI_FILES = [".github/workflows/*.yml", ".github/rulesets/main.json"]
REPO_FILES = "@repo"  # in `needs`: every file git would publish (tracked, or untracked and not ignored)
PRE_COMMIT = ".pre-commit-config.yaml"


def _other_ipv4() -> str:
    """An address of this host that is not 127.0.0.1, for the proof that a port can be taken on another interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))  # a documentation address: picks the outbound interface, sends nothing
            return s.getsockname()[0]
        except OSError:
            pass
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.2", 0))  # Linux answers on all of 127/8
            return "127.0.0.2"
        except OSError:
            return "0.0.0.0"  # a host with one address: holding every interface is the nearest break


def _hold_port(service: str, address: Callable[[], str]) -> Callable[[Path, Path], AbstractContextManager[None]]:
    @contextmanager
    def go(good: Path, bad: Path) -> Iterator[None]:
        with socket.socket() as held:
            held.bind((address(), _ports(bad)[service]))
            held.listen()
            yield

    return go


def _env(**values: str) -> Callable[[Path, Path], AbstractContextManager[None]]:
    """Set environment variables while the check runs; `{good}` and `{bad}` are the two copies' paths."""

    @contextmanager
    def go(good: Path, bad: Path) -> Iterator[None]:
        before = {k: os.environ.get(k) for k in values}
        os.environ.update({k: v.format(good=good, bad=bad) for k, v in values.items()})
        try:
            yield
        finally:
            for k, v in before.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    return go


def _remove_installed(module: str) -> Callable[[Path], None]:
    def go(root: Path) -> None:
        found = list((root / ".venv").glob(f"lib/python*/site-packages/{module}"))
        if not found:
            raise FileNotFoundError(f"{module} is not installed in the working copy; the break cannot be planted")
        for d in found:
            shutil.rmtree(d)

    return go


def _relock_bumped(rel: str) -> Callable[[Path], None]:
    """A valid newer lock: bump a workspace member's version and re-lock offline, leaving the environment as synced."""

    def go(root: Path) -> None:
        text = (root / rel).read_text()
        m = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"$', text, re.M)
        if not m:
            raise ValueError(f"{rel} has no plain version line; the break cannot be planted")
        bumped = f'version = "{m.group(1)}.{m.group(2)}.{int(m.group(3)) + 1}"'
        (root / rel).write_text(text[: m.start()] + bumped + text[m.end() :])
        _uv(root, "lock", "--offline", "-q").check_returncode()

    return go


def _drop_line(rel: str, containing: str) -> Callable[[Path], None]:
    def go(root: Path) -> None:
        lines = (root / rel).read_text().splitlines(keepends=True)
        kept = [ln for ln in lines if containing not in ln]
        if len(kept) == len(lines):
            raise ValueError(f"{rel}: no line contains {containing!r}; the break cannot be planted")
        (root / rel).write_text("".join(kept))

    return go


# The pre-commit file as the founding import shipped it: a remote ruff pinned off the lock, a kit command that
# does not exist (#23) and a UI that does not exist. hooks_runnable must stay red on it.
FOUNDING_PRE_COMMIT = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        args: [--fix]
  - repo: local
    hooks:
      - id: privacy-guard
        entry: uv run kit privacy scan --staged
        language: system
        pass_filenames: false
      - id: ui-lint-staged
        entry: pnpm -C apps/console exec lint-staged
        language: system
        files: ^apps/console/
        pass_filenames: false
"""
REVIEWED = (
    "\n## Independent review\n- Status: recorded\n- Reviewer: independent model\n- Date: 2026-11-21\n- Reviewed: commit e56218b\n"
    "- Review: https://github.com/ojfbot/HouseholdAgentKit/pull/1#pullrequestreview-1\n"
    "- Independence: attested by the owner on 2026-11-21\n"
)
# What GitHub returns for that review in the proofs (no network there): submitted, on the commit, on the date, naming the reviewer.
PROOF_REVIEW = {
    "state": "COMMENTED",
    "commit_id": "e56218b" + "0" * 33,
    "submitted_at": "2026-11-21T05:02:09Z",
    "body": "Independent review.\n\n1. A finding.\n\nReviewer: independent model\n",
}

CHECKS: list[Check] = [
    Check(
        "register_covers_packages",
        0,
        register_covers_packages,
        [REGISTER, *WORKSPACE, "apps/demo-console/server/host.py", "packages/shopping-port/push-loop-v1.md"],
        [
            Proof("a package nobody audited appears", _write("packages/unaudited-thing/pyproject.toml", "[project]\nname='x'\n")),
            Proof("the register is deleted", _delete(REGISTER)),
            Proof(
                "a package's row is removed and its name left in prose",
                lambda root: (_drop_line(REGISTER, "| `kit` |")(root), _append(REGISTER, "\nThe `kit` package is mentioned here, in prose only.\n")(root))[0],
            ),
        ],
    ),
    Check(
        "lock_fresh",
        1,
        lock_fresh,
        WORKSPACE,
        [
            Proof("a dependency is added without re-locking", _rewrite("packages/kit-gate/pyproject.toml", '"pyyaml>=6"', '"pyyaml>=6", "segno>=1.6"')),
            Proof(
                "a stale lock, with UV_PROJECT pointing the check at another project",
                _rewrite("packages/kit-gate/pyproject.toml", '"pyyaml>=6"', '"pyyaml>=6", "segno>=1.6"'),
                around=_env(UV_PROJECT="{good}"),
            ),
        ],
    ),
    Check(
        "workspace_wired",
        1,
        workspace_wired,
        WORKSPACE,
        [
            Proof(
                "a new package is never added to the workspace (so CI never installs or tests it)",
                _write("packages/orphan/pyproject.toml", "[project]\nname='orphan'\n"),
            ),
            Proof("a member is deleted from disk", _delete("packages/verifier/pyproject.toml")),
            Proof(
                "a project appears under apps/ and is never added to the workspace", _write("apps/demo-console/pyproject.toml", "[project]\nname='console'\n")
            ),
            Proof("a project appears somewhere no pattern looks", _write("tools/helper/pyproject.toml", "[project]\nname='helper'\n")),
        ],
    ),
    Check(
        "ports_agree",
        1,
        ports_agree,
        [*PORT_FILES, "apps/demo-console/console.example.json", "apps/demo-console/server/*.py", "packages/card-writer/**/*"],
        [
            Proof("the engine goes back to the console's port (the collision the audit found)", _rewrite(PORT_FILES[1], "default=8790", "default=8765")),
            Proof("the registry gives two services one port", _rewrite(PORT_FILES[0], "engine: 8790", "engine: 8765")),
            Proof("the console looks for the engine on the wrong port", _rewrite(PORT_FILES[2], "127.0.0.1:8790", "127.0.0.1:8799")),
            Proof("the registry moves the model port and the code does not", _rewrite(PORT_FILES[0], "model: 8080", "model: 8099")),
            Proof(
                "the console's defaults look for the model on another port",
                _rewrite(PORT_FILES[2], '"model_url": "http://127.0.0.1:8080"', '"model_url": "http://127.0.0.1:8081"'),
            ),
            Proof(
                "the example config puts the poll bus on another port", _rewrite("apps/demo-console/console.example.json", "127.0.0.1:8791", "127.0.0.1:8792")
            ),
            Proof(
                "the loaded config returns another port than the literal in the file",
                _rewrite(PORT_FILES[2], "    return cfg\n\n\ndef main(", '    cfg["port"] += 1\n    return cfg\n\n\ndef main('),
            ),
        ],
    ),
    Check(
        "runners_hosted",
        1,
        runners_hosted,
        CI_FILES,
        [
            Proof("a job moves to a self-hosted runner", _rewrite(".github/workflows/ci.yml", "runs-on: ubuntu-24.04", "runs-on: [self-hosted, stage-host]")),
            Proof("a job hides its runner behind an expression", _rewrite(".github/workflows/ci.yml", "runs-on: ubuntu-24.04", "runs-on: ${{ vars.RUNNER }}")),
            Proof("a workflow runs fork code with secrets", _rewrite(".github/workflows/privacy-guard.yml", "pull_request:", "pull_request_target:")),
            Proof("a job's runs-on is an empty list", _rewrite(".github/workflows/ci.yml", "runs-on: ubuntu-24.04", "runs-on: []")),
            Proof(
                "a self-hosted runner given a label that looks hosted",
                _rewrite(".github/workflows/ci.yml", "runs-on: ubuntu-24.04", "runs-on: ubuntu-stage-host"),
            ),
            Proof("a job has no runs-on at all", _rewrite(".github/workflows/privacy-guard.yml", "    runs-on: ubuntu-24.04\n", "")),
            Proof(
                "a job asks for two hosted images at once (no hosted runner carries both labels)",
                _rewrite(".github/workflows/ci.yml", "runs-on: ubuntu-24.04", "runs-on: [ubuntu-24.04, windows-2022]"),
            ),
        ],
    ),
    Check(
        "required_checks_exist",
        1,
        required_checks_exist,
        CI_FILES,
        [
            Proof("the aggregate job is renamed", _rewrite(".github/workflows/ci.yml", "\n  ci:\n", "\n  ci-all:\n")),
            Proof("the ruleset requires a check nothing produces", _rewrite(".github/rulesets/main.json", '"context": "ci"', '"context": "cross-review"')),
            Proof(
                "the ci job is given another display name (GitHub reports that name, not the job id)",
                _rewrite(".github/workflows/ci.yml", "\n  ci:\n", "\n  ci:\n    name: all checks\n"),
            ),
            Proof(
                "the aggregate stops waiting for the tests",
                _rewrite(".github/workflows/ci.yml", "needs: [lint, tests, contracts, doctor]", "needs: [lint, contracts, doctor]"),
            ),
            Proof(
                "the aggregate loses `if: always()` (a failed job then skips it instead of failing it)",
                _rewrite(
                    ".github/workflows/ci.yml", "    if: always()\n    needs: [lint, tests, contracts, doctor]", "    needs: [lint, tests, contracts, doctor]"
                ),
            ),
            Proof(
                "the aggregate's step stops checking its jobs' results",
                _rewrite(
                    ".github/workflows/ci.yml",
                    "      - run: |\n          echo '${{ toJSON(needs) }}' | jq -e 'to_entries | all(.value.result == \"success\")'",
                    "      - run: true",
                ),
            ),
        ],
    ),
    Check(
        "no_forbidden_files",
        1,
        no_forbidden_files,
        ["data/seeds/cases/*.yaml", privacy_mod.ALLOW_FILE],
        [
            Proof("the holdout seed is added", _write("data/holdout-seed.txt")),
            Proof("generated data is added", _write("data/generated/cases.json")),
            Proof("weights are added", _write("packages/k01/model.safetensors")),
            Proof("an env file is added", _write(".env", "KEY=1")),
            Proof("MLX weights are added (missing from the founding list)", _write("models/k01/adapter.mlx")),
            Proof("a non-ASCII path under data/ (git quotes it unless paths are NUL-delimited)", _write("data/generated/\u00fcbersicht.json")),
            Proof("generated run output lands outside data/", _write("packages/discovery-engine/runs/run-9/labels.csv", "id,label\n")),
        ],
    ),
    Check(
        "privacy_clean",
        1,
        privacy_clean,
        [REPO_FILES],
        [
            Proof("a key in a new file in a directory no rule names", _write("notes/scratch.txt", f"token={FAKE_KEY}\n")),
            Proof(
                "a key inside a binary file",
                _write_bytes("assets/blob.bin", b"\x00\x01" + FAKE_KEY.encode() + b"\x00"),
            ),
            Proof("a holdout case outside data/", _write("packages/verifier/tests/fixtures/case.yaml", "id: c1\nsplit: " + "holdout\n")),
            Proof("a personal home path in a doc", _write("docs/setup-notes.md", "cd /Users/" + "someone/src\n")),
            Proof("an exception with no reason", _rewrite(privacy_mod.ALLOW_FILE, "    why: The test writes", "    why: ''\n    note: The test writes")),
            Proof(
                "a stale exception that suppresses nothing",
                _append(privacy_mod.ALLOW_FILE, "\n  - rule: key\n    path: nowhere/at/all.txt\n    why: left over\n"),
            ),
            Proof(
                "an exception that switches a rule off everywhere", _append(privacy_mod.ALLOW_FILE, "\n  - rule: email\n    path: '*'\n    why: too noisy\n")
            ),
            Proof("the allowlist is deleted", _delete(privacy_mod.ALLOW_FILE)),
        ],
    ),
    Check(
        "vendored_verbatim",
        1,
        vendored_verbatim,
        ["packages/discovery-engine/prototypes/fork_c/*"],
        [
            Proof("a vendored Fork C file is edited", _append("packages/discovery-engine/prototypes/fork_c/score_v2.py", "\n# local tweak\n")),
            Proof("a vendored Fork C file goes missing", _delete("packages/discovery-engine/prototypes/fork_c/rubric-v2.yaml")),
            Proof("the checksum file is emptied", _write("packages/discovery-engine/prototypes/fork_c/SHA256SUMS", "")),
            Proof(
                "a file is edited and its line dropped from the checksum file",
                lambda root: (
                    _append("packages/discovery-engine/prototypes/fork_c/score_v2.py", "\n# local tweak\n")(root),
                    _drop_line("packages/discovery-engine/prototypes/fork_c/SHA256SUMS", "score_v2.py")(root),
                )[0],
            ),
        ],
    ),
    Check(
        "python_pin",
        2,
        python_pin,
        [".python-version"],
        [
            Proof("the interpreter is a different patch release", _write(".python-version", "3.12.99\n")),
            Proof(
                "a release candidate of the pinned version",
                lambda root: None,
                fn=lambda root: python_pin(root, running=Interpreter("cpython", (3, 12, 16), "candidate")),
            ),
            Proof(
                "another implementation with the same version numbers",
                lambda root: None,
                fn=lambda root: python_pin(root, running=Interpreter("pypy", (3, 12, 16), "final")),
            ),
        ],
        host=True,
    ),
    Check(
        "sync_frozen",
        2,
        sync_frozen,
        ["pyproject.toml", "uv.lock", ".python-version", "kit/**/*", "packages/**/*"],
        [
            Proof("the environment was never synced", lambda root: shutil.rmtree(root / ".venv")),
            Proof("the lock moved on after the last sync (a member's version bumped and re-locked)", _relock_bumped("packages/kit-gate/pyproject.toml")),
            Proof("a workspace module the kit commands import is deleted after the sync", _delete("packages/kit-gate/src/kit_gate/digest.py")),
            Proof("an installed package's files are removed and its metadata left", _remove_installed("yaml")),
            Proof(
                "never synced, with UV_PROJECT pointing the check at a synced project",
                lambda root: shutil.rmtree(root / ".venv"),
                around=_env(UV_PROJECT="{good}"),
            ),
        ],
        host=True,
    ),
    Check(
        "hello_world_smoke",
        2,
        hello_world_smoke,
        ["data/seeds/cases/*.yaml"],
        [
            Proof("the hello-world cases are missing", _delete("data/seeds/cases/taco-hello-world.yaml")),
            Proof("the cases file lists no cases (zero episodes run)", _write("data/seeds/cases/taco-hello-world.yaml", "schema: cases/v1-loose\ncases: []\n")),
            Proof("hook-fault:lock (the agent swaps a locked safe food)", lambda root: None),
            Proof("hook-fault:reject (every episode ends in an unacceptable cart)", lambda root: None),
        ],
        host=True,
    ),
    Check(
        "console_on_fixtures",
        2,
        console_on_fixtures,
        ["apps/demo-console/**/*", "packages/card-writer/**/*"],
        [
            Proof("the engine fixtures were never built", _delete("apps/demo-console/fixtures/engine/deltas.json")),
            Proof("the stage page is missing", _delete("apps/demo-console/web/stage.html")),
            Proof("the phone page is missing", _delete("apps/demo-console/web/phone.html")),
            Proof("the stage page's script is deleted", _delete("apps/demo-console/web/js/stage.js")),
            Proof("the phone page's stylesheet is deleted", _delete("apps/demo-console/web/css/phone.css")),
            Proof("a module the page scripts import is deleted", _delete("apps/demo-console/web/js/dom.js")),
            Proof("a stylesheet the page stylesheets import is deleted", _delete("apps/demo-console/web/css/cards.css")),
            Proof(
                "the stage page names a responsive image that is missing (srcset)",
                _rewrite("apps/demo-console/web/stage.html", "</body>", '<img srcset="/static/img/missing.svg 1x" alt="">\n</body>'),
            ),
            Proof(
                "the stage page names a missing script with spaces around `=`",
                _rewrite("apps/demo-console/web/stage.html", "</body>", '<script type="module" src = "/static/js/missing.js"></script>\n</body>'),
            ),
            Proof(
                "a script imports a missing module through a template literal",
                _append("apps/demo-console/web/js/stage.js", "\nimport(`./missing-lazy.js`);\n"),
            ),
            Proof(
                # Without the <base>, "static/js/phone.js" from /p is the real script, so only a crawl that honours
                # <base href> goes red here.
                "the page's <base href> sends a relative reference to a folder that lacks it",
                _rewrite(
                    "apps/demo-console/web/phone.html",
                    "<head>",
                    '<head>\n<base href="/static/nowhere/">\n<script type="module" src="static/js/phone.js"></script>',
                ),
            ),
        ],
        host=True,
    ),
    Check(
        "ci_runs_locally",
        1,
        ci_runs_locally,
        CI_FILES,
        [
            Proof(
                "a step reads a repository secret",
                _rewrite(".github/workflows/ci.yml", "run: uv run pyright", "run: uv run pyright --token ${{ secrets.KIT_TOKEN }}"),
            ),
            Proof(
                "a step depends on a runner-only path",
                _rewrite(".github/workflows/ci.yml", "run: uv run pyright", "run: cd $GITHUB_WORKSPACE && uv run pyright"),
            ),
            Proof(
                "a job needs a service container kit check does not start",
                _rewrite(
                    ".github/workflows/ci.yml",
                    "  doctor:\n    runs-on: ubuntu-24.04\n",
                    "  doctor:\n    runs-on: ubuntu-24.04\n    services:\n      db: {image: postgres}\n",
                ),
            ),
            Proof("a job calls a reusable workflow", _append(".github/workflows/ci.yml", "\n  shared:\n    uses: some-org/ci/.github/workflows/x.yml@v1\n")),
            Proof(
                "a run step is conditional (kit check would run it unconditionally)",
                _rewrite(".github/workflows/ci.yml", "      - run: uv run pyright\n", "      - run: uv run pyright\n        if: github.event_name == 'push'\n"),
            ),
            Proof(
                "a job runs a matrix (kit check would run it once)",
                _rewrite(
                    ".github/workflows/ci.yml",
                    "  doctor:\n    runs-on: ubuntu-24.04\n",
                    "  doctor:\n    runs-on: ubuntu-24.04\n    strategy: {matrix: {py: ['3.12', '3.13']}}\n",
                ),
            ),
            Proof(
                "a step swallows its own failure",
                _rewrite(".github/workflows/ci.yml", "      - run: uv run pyright\n", "      - run: uv run pyright\n        continue-on-error: true\n"),
            ),
            Proof(
                "the aggregate stops checking its needs", _rewrite(".github/workflows/ci.yml", "jq -e 'to_entries | all(.value.result == \"success\")'", "true")
            ),
            Proof(
                "the aggregate adds its own logic after the needs check",
                _rewrite(
                    ".github/workflows/ci.yml",
                    "jq -e 'to_entries | all(.value.result == \"success\")'\n",
                    "jq -e 'to_entries | all(.value.result == \"success\")' || true\n",
                ),
            ),
            Proof(
                "the workflow sets defaults kit check would ignore",
                _rewrite(".github/workflows/ci.yml", "\njobs:\n", "\ndefaults:\n  run:\n    working-directory: kit\n\njobs:\n"),
            ),
            Proof(
                "two jobs need each other (GitHub cannot schedule them)",
                _rewrite(".github/workflows/ci.yml", "  lint:\n    runs-on: ubuntu-24.04\n", "  lint:\n    needs: [ci]\n    runs-on: ubuntu-24.04\n"),
            ),
            Proof(
                "a job tolerates its own failure",
                _rewrite(
                    ".github/workflows/ci.yml", "  doctor:\n    runs-on: ubuntu-24.04\n", "  doctor:\n    runs-on: ubuntu-24.04\n    continue-on-error: true\n"
                ),
            ),
            Proof(
                "a job's env reads a runner expression",
                _rewrite(
                    ".github/workflows/ci.yml",
                    "  doctor:\n    runs-on: ubuntu-24.04\n",
                    "  doctor:\n    runs-on: ubuntu-24.04\n    env:\n      REF: ${{ github.ref }}\n",
                ),
            ),
        ],
    ),
    Check(
        "lint_policy_covers",
        1,
        lint_policy_covers,
        [lint_mod.POLICY_FILE, "**/*.py"],
        [
            Proof("a new tree with Python in it is in no lint tier", _write("packages/newthing/src/newthing/core.py", "x = 1\n")),
            Proof("the policy names a tree that does not exist", _rewrite(lint_mod.POLICY_FILE, '"scripts"', '"scriptz"')),
            Proof("a tree is in both tiers", _rewrite(lint_mod.POLICY_FILE, '"scripts"\n', '"scripts",\n    "apps"\n')),
            Proof("a ratchet floor is negative", _rewrite(lint_mod.POLICY_FILE, '"lint": 13,', '"lint": -1,')),
            Proof("the policy file is deleted", _delete(lint_mod.POLICY_FILE)),
        ],
    ),
    Check(
        "hooks_runnable",
        1,
        hooks_runnable,
        [PRE_COMMIT, "kit/**/*", "apps/**/*.py"],
        [
            Proof("the pre-commit file as founded (remote ruff, `kit privacy scan`, a pnpm UI that does not exist)", _write(PRE_COMMIT, FOUNDING_PRE_COMMIT)),
            Proof(
                "a hook calls a kit command that does not exist",
                _rewrite(PRE_COMMIT, "entry: uv run kit check --fast", "entry: uv run kit audit --everything"),
            ),
            Proof("a hook passes a flag kit check does not take", _rewrite(PRE_COMMIT, "entry: uv run kit check --fast", "entry: uv run kit check --quick")),
            Proof(
                "a hook only fires on a path that does not exist",
                _rewrite(PRE_COMMIT, "        pass_filenames: false\n", "        files: ^apps/console/\n        pass_filenames: false\n"),
            ),
            Proof("the pre-commit file is deleted", _delete(PRE_COMMIT)),
        ],
    ),
    Check(
        "gates_wellformed",
        1,
        gates_wellformed,
        [gates_mod.GATES_FILE],
        [
            Proof("the gates file is deleted (every gate silently disappears)", _delete(gates_mod.GATES_FILE)),
            Proof("a gate lists no blockers", _rewrite(gates_mod.GATES_FILE, "blocked_by: [1, 38, 41]", "blocked_by: []")),
            Proof("a blocker is not an issue number", _rewrite(gates_mod.GATES_FILE, "blocked_by: [1, 38, 41]", 'blocked_by: [1, "#38", 41]')),
            Proof("two gates share an id", _rewrite(gates_mod.GATES_FILE, "id: beat-1-live", "id: rung-3")),
            Proof("a waiver names an issue that is not a blocker", _rewrite(gates_mod.GATES_FILE, "kind: start\n", "kind: start\n    waived: [99]\n")),
            Proof("a gate blocks on its own milestone", _rewrite(gates_mod.GATES_FILE, "blocked_by: [1, 38, 41]", "blocked_by: [1, 3, 38, 41]")),
            Proof(
                "a gate does not say which issue its milestone is (so a typo gates the wrong one)", _rewrite(gates_mod.GATES_FILE, '    title: "Rung 3:"\n', "")
            ),
        ],
    ),
    Check(
        "ports_free",
        2,
        ports_free,
        ["contracts/ports.yaml"],
        [
            Proof("another process already holds a default port", lambda root: None, around=_hold_port("engine", lambda: "127.0.0.1")),
            Proof("another process holds the console's port on another interface", lambda root: None, around=_hold_port("console", _other_ipv4)),
            Proof("a default port is 0 (any free port, so nothing is checked)", _rewrite("contracts/ports.yaml", "console: 8765", "console: 0")),
        ],
        host=True,
    ),
    Check(
        "review_recorded",
        3,
        review_recorded,
        [REGISTER, gates_mod.GATES_FILE],
        [
            Proof("the review section says pending", _rewrite(REGISTER, "- Status: recorded", "- Status: pending")),
            Proof("there is no review section", _write(REGISTER, "# Integration risk register\n")),
            Proof("the reviewer is a placeholder", _rewrite(REGISTER, "- Reviewer: independent model", "- Reviewer: TBD")),
            Proof("the date is impossible", _rewrite(REGISTER, "- Date: 2026-11-21", "- Date: 2026-99-99")),
            Proof("the date is in the future", _rewrite(REGISTER, "- Date: 2026-11-21", "- Date: 2099-01-01")),
            Proof("no reviewed commit is named", _rewrite(REGISTER, "- Reviewed: commit e56218b", "- Reviewed: the PR as first pushed")),
            Proof("no link to the review itself", _rewrite(REGISTER, "- Review: https://github.com/ojfbot/HouseholdAgentKit/pull/1#pullrequestreview-1\n", "")),
            Proof("the register names a commit the review was not of", _rewrite(REGISTER, "- Reviewed: commit e56218b", "- Reviewed: commit 0447464")),
            Proof("the register's date is not the review's", _rewrite(REGISTER, "- Date: 2026-11-21", "- Date: 2026-11-20")),
            Proof("the reviewer named is not the one in the review", _rewrite(REGISTER, "- Reviewer: independent model", "- Reviewer: a different model")),
            Proof("the review is on another repository", _rewrite(REGISTER, "github.com/ojfbot/HouseholdAgentKit/pull/1", "github.com/someone/else/pull/1")),
            Proof("the reviewer is only a word the review happens to contain", _rewrite(REGISTER, "- Reviewer: independent model", "- Reviewer: finding")),
            Proof("independence is not attested by the owner", _rewrite(REGISTER, "- Independence: attested by the owner on 2026-11-21\n", "")),
            Proof("the repo the review must be on cannot be resolved", _delete(gates_mod.GATES_FILE)),
        ],
    ),
]


def _copy_needs(check: Check, src: Path, dst: Path) -> None:
    for pattern in check.needs:
        matches = [src / f for f in privacy_mod.files(src)] if pattern == REPO_FILES else src.glob(pattern)
        for p in matches:
            if p.is_file() and not (set(p.relative_to(src).parts) & SKIP_DIRS):
                (dst / p.relative_to(src)).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst / p.relative_to(src))


def prove(check: Check, root: Path = ROOT) -> list[tuple[str, bool, str]]:
    """Run a check on a working copy (must be green), then once per planted break (must be red)."""
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "working"
        good.mkdir()
        _copy_needs(check, root, good)
        if check.id == "review_recorded":  # a working setup is a register whose review section is filled in
            text = (good / REGISTER).read_text()
            (good / REGISTER).write_text(re.sub(r"^## Independent review\n.*?(?=^## |\Z)", "", text, flags=re.S | re.M) + REVIEWED)
            check = Check(
                check.id,
                check.rung,
                lambda root: review_recorded(root, date(2026, 11, 25), fetch=lambda repo, pr, rid: PROOF_REVIEW, ancestry=lambda root, sha: True),
                check.needs,
                check.proofs,
            )
        if check.id == "sync_frozen":  # a working setup is one that has been synced
            _uv(good, "sync", "--frozen", "-q").check_returncode()
        res = check.fn(good) if check.id != "python_pin" else python_pin(good, running=Interpreter.release((good / ".python-version").read_text().strip()))
        rows.append(("working setup", res.ok, res.detail))
        for i, proof in enumerate(check.proofs):
            bad = Path(tmp) / f"broken-{i}"
            if check.id == "sync_frozen":
                # An environment is tied to its path: a copied .venv reads "differs" before anything is broken, so
                # every break would look caught. Sync each copy where it stands and see it green before breaking it.
                shutil.copytree(good, bad, symlinks=True, ignore=shutil.ignore_patterns(".venv"))
                _uv(bad, "sync", "--frozen", "-q").check_returncode()
                before = check.fn(bad)
                if not before.ok:
                    rows.append((f"break: {proof.name}", False, f"the copy was not green before the break, so the proof shows nothing: {before.detail}"))
                    continue
            else:
                shutil.copytree(good, bad, symlinks=True)
            proof.breaker(bad)
            with proof.around(good, bad) if proof.around else nullcontext():
                try:
                    if proof.fn:
                        res = proof.fn(bad)
                    elif proof.name.startswith("hook-fault:"):
                        res = hello_world_smoke(bad, hook=_BrokenHook(proof.name.split(":")[1].split()[0]))
                    elif check.id == "python_pin":
                        res = python_pin(bad, running=Interpreter.release("3.12.16"))
                    else:
                        res = check.fn(bad)
                except Exception as e:  # a check that crashes on a broken setup is red, loudly
                    res = Result(False, f"check raised {type(e).__name__}: {e}")
            rows.append((f"break: {proof.name}", not res.ok, res.detail))
    return rows


def self_test(root: Path = ROOT) -> int:
    failed = 0
    for check in CHECKS:
        for label, as_expected, detail in prove(check, root):
            failed += not as_expected
            want = "green" if label == "working setup" else "red"
            print(f"{'ok  ' if as_expected else 'FAIL'} {check.id:26} {label:78} -> {want if as_expected else 'NOT ' + want}: {detail[:110]}")
    proofs = sum(len(c.proofs) for c in CHECKS)
    print(
        f"\n{len(CHECKS)} checks, {proofs} planted breaks: "
        + ("every check went red on its breaks and green on a working setup" if not failed else f"{failed} did not behave; those checks must not gate")
    )
    if summary := holes_summary():
        print(summary)
    return 1 if failed else 0


def holes_summary() -> str:
    """One line naming every check that still passes a known broken setup; empty when there is none."""
    holed = [c for c in CHECKS if c.hole]
    if not holed:
        return ""
    issues = ", ".join(sorted({c.hole.split()[0] for c in holed}))
    return f"{len(holed)} of these checks still pass a known broken setup that is not planted above ({issues}): {', '.join(c.id for c in holed)}"


# ------------------------------------------------------------------------------------------------ report


@dataclass
class Deadline:
    """A date on which something turns red with no commit. `ask` puts the question to the gate itself, as of a day."""

    when: date  # the first day the gate is red if nothing changes
    what: str
    ask: Callable[[Path, date], Result]


STAND_IN = "today's reference hello world (iq-reference-tier-none, the stand-in)"


def _ask_engine_stage0(root: Path, day: date) -> Result:
    """Would `discovery_engine run` get past stage 0 on that day, given the hello-world result it will be given?

    That is the file in KIT_HELLO_WORLD_RESULT, the one the run's `hello_world_result` names. Without it, doctor
    judges today's reference run and says so: a stand-in's verdict is not the setup's verdict.
    """
    from discovery_engine import pipeline
    from kit_eval import hello_world

    given = os.environ.get("KIT_HELLO_WORLD_RESULT")
    with tempfile.TemporaryDirectory() as tmp:
        if given:
            result_file, judged = Path(given), f"judged on {given}"
            res = json.loads(result_file.read_text())
        else:
            res = hello_world.run("full", "doctor", cases_dir=root / "data/seeds/cases")
            result_file, judged = Path(tmp) / "hello-world.json", f"judged on {STAND_IN}; set KIT_HELLO_WORLD_RESULT to the result the engine run is given"
            result_file.write_text(json.dumps(res))
        cfg = pipeline.RunConfig(hello_world_result=str(result_file), as_of=day.isoformat())
        try:
            pipeline.stage0(cfg, pipeline.load_seeds()[1], pipeline.e06_ladder.load_cover())
        except RuntimeError as e:
            return Result(False, f"hello world is `{res.get('status')}` from a `{res.get('mode')}` run; {e} ({judged})")
    return Result(True, f"stage 0 accepts hello world `{res.get('status')}` ({judged})")


def _ask_kit_gate(root: Path, day: date) -> Result:
    """Would `kit gate` be green on that day, with the inputs it is given?

    Those are the report in KIT_GATE_CANDIDATE and, if set, the baseline report and bundle diff in
    KIT_GATE_BASELINE and KIT_GATE_DIFF, as `kit gate --candidate --baseline --diff` takes them. Without a
    candidate, doctor judges today's reference report with no baseline and no diff, and says so.
    """
    from kit_gate.gate import GateConfig, run_gate

    def load(var: str) -> dict | None:
        path = os.environ.get(var)
        return json.loads(Path(path).read_text()) if path else None

    candidate, baseline, diff = load("KIT_GATE_CANDIDATE"), load("KIT_GATE_BASELINE"), load("KIT_GATE_DIFF")
    if candidate is not None:
        judged = f"judged on {os.environ['KIT_GATE_CANDIDATE']}" + (", with its baseline" if baseline else "") + (" and bundle diff" if diff else "")
    else:
        from kit_eval.cases import load_cases
        from kit_eval.report import build_report, load_hook, run_hello_world

        cases, hook = load_cases(str(root / "data/seeds/cases")), load_hook(None)
        candidate = build_report(run_hello_world(hook, cases, k=5, seed=0), cases, bundle_id="doctor", hook_name=hook.name, k=5)  # `kit eval` defaults
        judged = f"judged on {STAND_IN}'s report, no baseline, no diff; set KIT_GATE_CANDIDATE (and KIT_GATE_BASELINE, KIT_GATE_DIFF) to the real inputs"
    record = run_gate(candidate, baseline, diff, GateConfig.load(root / "bundles/gate-config.yaml"), day)
    if record["verdict"] == "green":
        return Result(True, f"`kit gate` is green ({judged})")
    return Result(False, "`kit gate` is red: " + "; ".join(record["reasons"]) + f" ({judged})")


def deadlines(root: Path) -> list[Deadline]:
    """The dates are read from the gates' own sources, so moving a date or renewing a waiver moves the line."""
    from discovery_engine import pipeline
    from kit_gate.gate import GateConfig

    out = [
        Deadline(
            date.fromisoformat(pipeline.PASS_REQUIRED_FROM),
            "the engine's stage 0 stops accepting `placement_only`: `discovery_engine run` aborts unless hello world is `pass` from a `full` run",
            _ask_engine_stage0,
        )
    ]
    for w in GateConfig.load(root / "bundles/gate-config.yaml").waivers:
        until = date.fromisoformat(str(w["until"]))
        out.append(
            Deadline(
                until + timedelta(days=1),
                f"the {w['metric']} waiver in bundles/gate-config.yaml has expired (last day {until.isoformat()}): `kit gate` goes red",
                _ask_kit_gate,
            )
        )
    return sorted(out, key=lambda d: d.when)


def date_lines(root: Path, today: date) -> tuple[list[str], list[dict]]:
    """One line per date whose gate is not passing: a countdown before the date, red from the date on.

    A gate is asked today and, before its date, as of its date. A gate already red today reads red now, not as a
    countdown. The line goes only when the gate passes. A gate that cannot be asked, or a source that cannot be
    read, is red: silence is not a pass. Each line says which inputs the gate was judged on.
    """
    try:
        found = deadlines(root)
    except Exception as e:
        return [f"dates   {'':24} RED     cannot read the dates ({type(e).__name__}: {e}); treat every dated gate as red"], [
            {"date": None, "days": None, "status": "red", "what": "cannot read the dates", "detail": f"{type(e).__name__}: {e}"}
        ]
    lines, rows = [], []
    for d in found:
        days = (d.when - today).days
        try:
            # Before the date, the gate is asked twice: today, because it may already be red for another reason,
            # and as of the date, for the countdown. From the date on, it is asked as of today.
            now = d.ask(root, today)
            then = d.ask(root, d.when) if days > 0 and now.ok else now
        except Exception as e:
            now = then = Result(False, f"could not ask the gate ({type(e).__name__}: {e})")
        if now.ok and then.ok:
            continue
        if not now.ok and days > 0:
            lines.append(f"date    {d.when.isoformat():24} RED     already, {days} d before its date: {d.what}. Red now: {now.detail}")
            status = "red"
        elif days > 0:
            lines.append(f"date    {d.when.isoformat():24} in {days} d  {d.what}. On the day: {then.detail}")
            status = "upcoming"
        else:
            since = "today" if days == 0 else f"{-days} d ago"
            lines.append(f"date    {d.when.isoformat():24} RED     {since}: {d.what}. Still red: {now.detail}")
            status = "red"
        rows.append({"date": d.when.isoformat(), "days": days, "status": status, "what": d.what, "detail": (now if not now.ok else then).detail})
    return lines, rows


def _gate_verdicts(root: Path, fetch: gates_mod.Fetcher | None) -> tuple[list[gates_mod.Verdict], str | None]:
    try:
        spec = gates_mod.load_spec(root)
    except gates_mod.SpecError as e:
        return [], f"{gates_mod.GATES_FILE} is broken ({e}); no rung above 2 may start"
    return gates_mod.evaluate(spec, fetch or gates_mod.default_fetcher(root)), None


def run(root: Path = ROOT, upto: int = 2, today: date | None = None, as_json: bool = False, fetch: gates_mod.Fetcher | None = None) -> int:
    today = today or date.today()
    verdicts, gates_broken = _gate_verdicts(root, fetch)
    gate_for = {v.gate.rung: v for v in verdicts if v.gate.rung is not None}
    review = review_recorded(root, today)

    def start_blockers(rung: int) -> list[str]:
        """Everything that stops a rung from starting: its start gate, and for rung 3 the independent review."""
        out = []
        g = gate_for.get(rung)
        if g and g.gate.kind == "start" and not g.clear:
            out.append(f"gate {g.gate.id} {g.status}: {g.detail}")
        if rung == 3 and not review.ok:
            out.append(review.detail)
        if rung > 2 and gates_broken:
            out.append(gates_broken)
        return out

    results: dict[int, list[tuple[Check, Result]]] = {}
    for check in CHECKS:
        if check.rung <= upto:
            try:
                res = check.fn(root)
            except Exception as e:
                res = Result(False, f"check raised {type(e).__name__}: {e}")
            results.setdefault(check.rung, []).append((check, res))
    lines, first_red = [], None
    for rung in range(0, 11):
        title = RUNG_TITLES[rung]
        if rung > upto:
            continue
        rows = [(c, r) for c, r in results.get(rung, []) if c.id != "review_recorded"]
        gate = gate_for.get(rung)
        held = start_blockers(rung)
        if gate and gate.gate.kind == "close" and not gate.clear:
            held.append(f"gate {gate.gate.id} {gate.status}: {gate.detail}")
        gated = "".join(f"; {h}" for h in held)
        if not rows:
            lines.append(f"rung {rung:<2} {title:24} NOT CLIMBED  no proven check yet; see docs/ladder.md and the rung's issue{gated}")
            first_red = first_red if first_red is not None else rung
            continue
        red = [(c, r) for c, r in rows if not r.ok]
        holed = [c for c, _ in rows if c.hole]
        unproven = (
            f", {len(holed)} unproven (pass a known broken setup, {', '.join(sorted({c.hole.split()[0] for c in holed}))}): {', '.join(c.id for c in holed)}"
            if holed
            else ""
        )
        if red:
            first_red = first_red if first_red is not None else rung
            lines.append(f"rung {rung:<2} {title:24} RED    {red[0][0].id}: {red[0][1].detail}" + (f" (+{len(red) - 1} more)" if len(red) > 1 else "") + gated)
        elif gated:
            first_red = first_red if first_red is not None else rung
            lines.append(f"rung {rung:<2} {title:24} GATED  {len(rows)}/{len(rows)} checks green{unproven}{gated} (docs/gates.yaml)")
        else:
            lines.append(f"rung {rung:<2} {title:24} GREEN  {len(rows)}/{len(rows)} checks{unproven}")
    lines.append(
        f"review  {'independent review':24} {'GREEN ' if review.ok else 'RED   '} {review.detail}" + ("" if review.ok else "; rung 3 does not start without it")
    )
    if gates_broken:
        lines.append(f"gates   {gates_broken}")
    lines.extend(gates_mod.describe(v) for v in verdicts)
    dated, dates = date_lines(root, today)
    lines.extend(dated)
    if first_red is not None:
        nxt = f"fix rung {first_red} ({RUNG_TITLES[first_red]})"
    elif upto >= 10:
        nxt = "nothing; the ladder is climbed"
    elif blockers := start_blockers(upto + 1):
        nxt = f"rung {upto + 1} ({RUNG_TITLES[upto + 1]}) may not start: " + "; ".join(blockers)
    else:
        nxt = f"climb rung {upto + 1} ({RUNG_TITLES[upto + 1]})"
    lines.append(f"next    {nxt}")
    if as_json:
        print(
            json.dumps(
                {
                    "rungs": {
                        r: [{"check": c.id, "ok": x.ok, "detail": x.detail, "host": c.host, "unproven": c.hole or None} for c, x in v]
                        for r, v in results.items()
                    },
                    "first_red": first_red,
                    "gates": [
                        {"id": v.gate.id, "milestone": v.gate.milestone, "kind": v.gate.kind, "status": v.status, "pending": v.pending} for v in verdicts
                    ],
                    "gates_broken": gates_broken,
                    "review": {"ok": review.ok, "detail": review.detail},
                    "dates": dates,
                    "next": nxt,
                    "lines": lines,
                },
                indent=2,
            )
        )
    else:
        print("\n".join(lines))
    return 0 if first_red is None else 1

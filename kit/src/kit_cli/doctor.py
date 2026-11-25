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
from collections.abc import Callable
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
HOSTED = re.compile(r"^(ubuntu|macos|windows)-[a-z0-9.\-]+$")
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
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True)
        if out.returncode == 0:
            return [f for f in out.stdout.splitlines() if (root / f).exists()]
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


def register_covers_packages(root: Path) -> Result:
    text = (root / REGISTER).read_text() if (root / REGISTER).exists() else ""
    units = [*_members(root), *(p.parent.relative_to(root).as_posix() for p in root.glob("apps/*/server"))]
    units += [p.relative_to(root).as_posix() for p in root.glob("packages/*") if p.is_dir() and p.relative_to(root).as_posix() not in units]
    missing = [u for u in sorted(set(units)) if f"`{u}`" not in text]
    return Result(not missing, "every package has a row" if not missing else f"no risk-register row for: {', '.join(missing)}")


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


def lock_fresh(root: Path) -> Result:
    if not shutil.which("uv"):
        return Result(False, "uv is not installed")
    # UV_FROZEN=1 (set in CI) turns `uv lock --check` into a no-op that always passes; the self-test caught that.
    env = {k: v for k, v in os.environ.items() if k != "UV_FROZEN"}
    out = subprocess.run(["uv", "lock", "--check"], cwd=root, capture_output=True, text=True, env=env)
    return Result(out.returncode == 0, "uv.lock matches the pyproject files" if out.returncode == 0 else "uv.lock is stale: run `uv lock` and commit it")


def workspace_wired(root: Path) -> Result:
    members = set(_members(root))
    on_disk = {p.parent.relative_to(root).as_posix() for p in [*root.glob("packages/*/pyproject.toml"), *root.glob("kit/pyproject.toml")]}
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
    return Result(True, f"{len(members)} workspace members wired")


def ports_agree(root: Path) -> Result:
    ports = _ports(root)
    dupes = sorted(k for k, v in ports.items() if list(ports.values()).count(v) > 1)
    if dupes:
        return Result(False, f"two services share a default port: {', '.join(dupes)}")
    found = {
        "engine (cli default)": (
            re.search(r'"--port", type=int, default=(\d+)', (root / "packages/discovery-engine/src/discovery_engine/cli.py").read_text()),
            ports["engine"],
        ),
        "console (host default)": (re.search(r'"port": (\d+)', (root / "apps/demo-console/server/host.py").read_text()), ports["console"]),
        "engine (as the console expects it)": (
            re.search(r'"engine_url": "http://127\.0\.0\.1:(\d+)"', (root / "apps/demo-console/server/host.py").read_text()),
            ports["engine"],
        ),
    }
    bad = [f"{name} is {m.group(1) if m else 'not found'}, registry says {want}" for name, (m, want) in found.items() if not m or int(m.group(1)) != want]
    return Result(not bad, "code defaults match contracts/ports.yaml, no collisions" if not bad else "; ".join(bad))


def runners_hosted(root: Path) -> Result:
    bad = []
    for name, wf in _workflows(root).items():
        triggers = wf.get(True, wf.get("on", {})) or {}  # YAML reads the key `on` as boolean true
        if "pull_request_target" in (triggers if isinstance(triggers, (dict, list)) else [triggers]):
            bad.append(f"{name}: pull_request_target runs fork code with repo secrets")
        for job_id, job in (wf.get("jobs") or {}).items():
            runs_on = job.get("runs-on")
            labels = runs_on if isinstance(runs_on, list) else [runs_on]
            if not all(isinstance(x, str) and HOSTED.match(x) for x in labels):
                bad.append(f"{name}:{job_id} runs-on {runs_on!r} is not provably a GitHub-hosted runner")
    if not _workflows(root):
        return Result(False, "no workflows found")
    return Result(not bad, "every job runs on a GitHub-hosted runner" if not bad else "; ".join(bad))


def required_checks_exist(root: Path) -> Result:
    ruleset = json.loads((root / ".github/rulesets/main.json").read_text())
    want = [c["context"] for r in ruleset["rules"] if r["type"] == "required_status_checks" for c in r["parameters"]["required_status_checks"]]
    have = {job_id for wf in _workflows(root).values() for job_id in (wf.get("jobs") or {})}
    missing = [c for c in want if c not in have]
    if not want:
        return Result(False, "the ruleset requires no status checks")
    return Result(
        not missing,
        f"required checks all exist as jobs: {', '.join(want)}"
        if not missing
        else f"the ruleset requires checks no workflow produces (merges would block forever): {', '.join(missing)}",
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


def vendored_verbatim(root: Path) -> Result:
    base = root / "packages/discovery-engine/prototypes/fork_c"
    bad = []
    for line in (base / "SHA256SUMS").read_text().splitlines():
        want, name = line.split()
        if not (base / name).exists() or hashlib.sha256((base / name).read_bytes()).hexdigest() != want:
            bad.append(name)
    return Result(
        not bad,
        "Fork C's vendored files are byte-identical to the import"
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


def python_pin(root: Path, running: str | None = None) -> Result:
    want = (root / ".python-version").read_text().strip()
    running = running or ".".join(map(str, sys.version_info[:3]))
    return Result(running == want, f"CPython {running}" if running == want else f"running CPython {running}, the pin is {want}")


def sync_frozen(root: Path) -> Result:
    if not shutil.which("uv"):
        return Result(False, "uv is not installed")
    out = subprocess.run(["uv", "sync", "--frozen", "--check"], cwd=root, capture_output=True, text=True)
    return Result(out.returncode == 0, "environment matches uv.lock" if out.returncode == 0 else "environment differs from uv.lock: run `uv sync --frozen`")


def hello_world_smoke(root: Path, hook: object | None = None) -> Result:
    from kit_eval import hello_world

    cases = root / "data/seeds/cases"
    if not any(cases.glob("*.yaml")):
        return Result(False, f"no hello-world cases under {cases.relative_to(root)}")
    res = hello_world.run("smoke", "doctor", hook=hook, cases_dir=cases)  # type: ignore[arg-type]
    zt = res.get("zero_tolerance") or {}
    broken = sorted(k for k, v in zt.items() if (v > 1 if k == "orders_per_mandate_max" else v))
    ok = res.get("result_version") == "hello_world_result@1" and res.get("status") in ("pass", "placement_only") and not broken and not res.get("failures")
    why = (
        f"status={res.get('status')}"
        + (f", zero-tolerance breaches: {', '.join(broken)}" if broken else "")
        + (f", {len(res['failures'])} failed episodes" if res.get("failures") else "")
    )
    unmeasured = len(res.get("zero_tolerance_not_measured") or [])
    return Result(ok, f"taco night smoke run: {why}" + (f" ({unmeasured} zero-tolerance metrics not measured yet)" if unmeasured else ""))


def console_on_fixtures(root: Path) -> Result:
    app = root / "apps/demo-console"
    missing = [f for f in ("fixtures/engine/deltas.json", "fixtures/engine/readout.default.json") if not (app / f).exists()]
    if missing:
        return Result(False, "engine fixtures not built: run `python apps/demo-console/fixtures/build_engine_fixtures.py`")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
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
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
                        health = r.status
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as r:
                        page = r.read().decode(errors="replace")
                    ok = health == 200 and "<html" in page.lower()
                    return Result(ok, "console serves its stage page on fixtures" if ok else "console answered but the stage page is not HTML")
                except urllib.error.HTTPError as e:
                    return Result(False, f"console answered HTTP {e.code} for its health or stage page")
                except OSError as e:
                    last = str(e)
                    time.sleep(0.25)
            return Result(False, f"console did not answer in 10 s ({last})")
        finally:
            proc.terminate()
            proc.wait(timeout=5)


def ports_free(root: Path) -> Result:
    busy = []
    for name, port in _ports(root).items():
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                busy.append(f"{name} {port}")
    return Result(not busy, "default ports are free on this host" if not busy else f"already in use on this host: {', '.join(busy)}")


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
        ],
        hole="#38 [20]: passes when a package is named only in prose, not in the table",
    ),
    Check(
        "lock_fresh",
        1,
        lock_fresh,
        WORKSPACE,
        [Proof("a dependency is added without re-locking", _rewrite("packages/kit-gate/pyproject.toml", '"pyyaml>=6"', '"pyyaml>=6", "segno>=1.6"'))],
        hole="#38 [14]: UV_PROJECT makes it check a different project",
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
        ],
        hole="#38 [19]: ignores a pyproject.toml under apps/",
    ),
    Check(
        "ports_agree",
        1,
        ports_agree,
        PORT_FILES,
        [
            Proof("the engine goes back to the console's port (the collision the audit found)", _rewrite(PORT_FILES[1], "default=8790", "default=8765")),
            Proof("the registry gives two services one port", _rewrite(PORT_FILES[0], "engine: 8790", "engine: 8765")),
            Proof("the console looks for the engine on the wrong port", _rewrite(PORT_FILES[2], "127.0.0.1:8790", "127.0.0.1:8799")),
        ],
        hole="#38 [12]: reads three literals; ignores the model and poll-bus ports",
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
        ],
        hole="#38 [18]: passes on an empty runs-on list and on invented ubuntu-* labels",
    ),
    Check(
        "required_checks_exist",
        1,
        required_checks_exist,
        CI_FILES,
        [
            Proof("the aggregate job is renamed", _rewrite(".github/workflows/ci.yml", "\n  ci:\n", "\n  ci-all:\n")),
            Proof("the ruleset requires a check nothing produces", _rewrite(".github/rulesets/main.json", '"context": "ci"', '"context": "cross-review"')),
        ],
        hole="#38 [11]: passes when the ci job is renamed by `name:` or drops a job from `needs`",
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
        ],
        hole="#38 [16]: passes with an emptied checksum file",
    ),
    Check(
        "python_pin",
        2,
        python_pin,
        [".python-version"],
        [Proof("the interpreter is a different patch release", _write(".python-version", "3.12.99\n"))],
        host=True,
        hole="#38 [21]: accepts a pre-release or another implementation with the same numbers",
    ),
    Check(
        "sync_frozen",
        2,
        sync_frozen,
        ["pyproject.toml", "uv.lock", ".python-version", "kit/**/*", "packages/**/*"],
        [
            Proof("the environment was never synced", lambda root: shutil.rmtree(root / ".venv")),
            Proof(
                "a dependency was added to the lock after the last sync",
                _rewrite("uv.lock", '[[package]]\nname = "pyyaml"', '[[package]]\nname = "pyyaml-not-installed"'),
            ),
        ],
        host=True,
        hole="#38 [15]: passes with an installed package's files removed",
    ),
    Check(
        "hello_world_smoke",
        2,
        hello_world_smoke,
        ["data/seeds/cases/*.yaml"],
        [
            Proof("the hello-world cases are missing", _delete("data/seeds/cases/taco-hello-world.yaml")),
            Proof("hook-fault:lock (the agent swaps a locked safe food)", lambda root: None),
            Proof("hook-fault:reject (every episode ends in an unacceptable cart)", lambda root: None),
        ],
        host=True,
        hole="#38 [3]: passes with zero episodes",
    ),
    Check(
        "console_on_fixtures",
        2,
        console_on_fixtures,
        ["apps/demo-console/**/*", "packages/card-writer/**/*"],
        [
            Proof("the engine fixtures were never built", _delete("apps/demo-console/fixtures/engine/deltas.json")),
            Proof("the stage page is missing", _delete("apps/demo-console/web/stage.html")),
        ],
        host=True,
        hole="#38 [8]: passes with the pages' scripts deleted",
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
        [Proof("another process already holds a default port", lambda root: None)],
        host=True,
        hole="#38 [13]: binds loopback only, and accepts port 0",
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
            subprocess.run(["uv", "sync", "--frozen", "-q"], cwd=good, check=True, capture_output=True)
        held = None
        res = check.fn(good) if check.id != "python_pin" else python_pin(good, running=(good / ".python-version").read_text().strip())
        rows.append(("working setup", res.ok, res.detail))
        for i, proof in enumerate(check.proofs):
            bad = Path(tmp) / f"broken-{i}"
            shutil.copytree(good, bad, symlinks=True)
            proof.breaker(bad)
            try:
                if check.id == "ports_free":
                    held = socket.socket()
                    held.bind(("127.0.0.1", _ports(bad)["engine"]))
                if proof.name.startswith("hook-fault:"):
                    res = hello_world_smoke(bad, hook=_BrokenHook(proof.name.split(":")[1].split()[0]))
                elif check.id == "python_pin":
                    res = python_pin(bad, running="3.12.16")
                else:
                    res = check.fn(bad)
            except Exception as e:  # a check that crashes on a broken setup is red, loudly
                res = Result(False, f"check raised {type(e).__name__}: {e}")
            finally:
                if held:
                    held.close()
                    held = None
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


def _ask_engine_stage0(root: Path, day: date) -> Result:
    """Would `discovery_engine run` get past stage 0 on that day, with today's hello world from a `full` run?"""
    from discovery_engine import pipeline
    from kit_eval import hello_world

    res = hello_world.run("full", "doctor", cases_dir=root / "data/seeds/cases")
    with tempfile.TemporaryDirectory() as tmp:
        result_file = Path(tmp) / "hello-world.json"
        result_file.write_text(json.dumps(res))
        cfg = pipeline.RunConfig(hello_world_result=str(result_file), as_of=day.isoformat())
        try:
            pipeline.stage0(cfg, pipeline.load_seeds()[1], pipeline.e06_ladder.load_cover())
        except RuntimeError as e:
            return Result(False, f"hello world is `{res.get('status')}` from a `{res.get('mode')}` run; {e}")
    return Result(True, f"stage 0 accepts hello world `{res.get('status')}`")


def _ask_kit_gate(root: Path, day: date) -> Result:
    """Would `kit gate` be green on that day, for today's hello-world report against bundles/gate-config.yaml?"""
    from kit_eval.cases import load_cases
    from kit_eval.report import build_report, load_hook, run_hello_world
    from kit_gate.gate import GateConfig, run_gate

    cases, hook = load_cases(str(root / "data/seeds/cases")), load_hook(None)
    report = build_report(run_hello_world(hook, cases, k=5, seed=0), cases, bundle_id="doctor", hook_name=hook.name, k=5)  # `kit eval` defaults
    record = run_gate(report, None, None, GateConfig.load(root / "bundles/gate-config.yaml"), day)
    return Result(record["verdict"] == "green", "`kit gate` is green" if record["verdict"] == "green" else "`kit gate` is red: " + "; ".join(record["reasons"]))


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

    A gate is asked as of its date, or as of today once the date has arrived. The line goes only when the gate
    passes. A gate that cannot be asked, or a source that cannot be read, is red: silence is not a pass.
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
            verdict = d.ask(root, max(today, d.when))
        except Exception as e:
            verdict = Result(False, f"could not ask the gate ({type(e).__name__}: {e})")
            days = min(days, 0)  # an unanswerable gate is red now, whatever the calendar says
        if verdict.ok:
            continue
        if days > 0:
            lines.append(f"date    {d.when.isoformat():24} in {days} d  {d.what}")
        else:
            since = "today" if days == 0 else f"{-days} d ago"
            lines.append(f"date    {d.when.isoformat():24} RED     {since}: {d.what}. Still red: {verdict.detail}")
        rows.append({"date": d.when.isoformat(), "days": days, "status": "upcoming" if days > 0 else "red", "what": d.what, "detail": verdict.detail})
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

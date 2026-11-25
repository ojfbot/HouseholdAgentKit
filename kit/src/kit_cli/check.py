"""kit check: run what CI runs, on this machine, from the workflow files themselves.

The workflows under .github/workflows are the single source. `kit check` reads every workflow triggered by
`pull_request` and runs each job's `run:` steps in order, with the workflow's, job's and step's `env`.

What it keeps from GitHub's model, so a local green and a CI green mean the same thing:

* **One clean checkout per job.** Your changes (tracked, and untracked files that are not ignored) are
  snapshotted into a commit object, and every job runs in its own fresh `git worktree` of it. One job's
  generated files never reach another, as on GitHub's runners. Nothing in your working tree is touched.
* **Aggregate jobs are evaluated**, not skipped: an aggregate passes only if every job it needs ran and passed.
* **Jobs run in `needs` order**, whatever order the YAML lists them in.
* **What it cannot reproduce, it refuses.** A step `if:`, `shell:` or `continue-on-error`; a job `if:`
  (other than an aggregate's `always()`), `strategy`, `defaults`, `container`, `services` or reusable
  workflow; a workflow-level `defaults`; any `${{ }}` expression, `secrets.` or `$GITHUB_*` value in a run
  step, a step, job or workflow `env`, or a job's `runs-on`; an aggregate whose step is anything but the
  standard needs check. Doctor's `ci_runs_locally` check goes red on each, so the workflows cannot drift past
  what this command runs.

What it does not reproduce, by design, and says so when it starts:

* `uses:` steps. Checkout is replaced by the snapshot worktree, `setup-uv` by your installed uv, and
  `upload-artifact` is not run. A workflow whose correctness depends on an action's side effects beyond those
  would pass here and not there; `ci_runs_locally` does not inspect actions.
* GitHub's pull-request merge commit. CI tests your branch merged into its base; this tests your working tree.
  Rebase onto main before review (AGENTS.md) and the two agree.
* Runner images, caches and timeouts. `RUNNER_TEMP` and `CI=true` are set; `timeout-minutes` is ignored.

  kit check               every job (several minutes; pip-audit needs the network)
  kit check --fast        the lint and privacy-guard jobs (what the pre-commit hook runs)
  kit check --job tests   one job
  kit check --fix         `kit lint --fix` on your tree first, then the checks
  kit check --list        print the plan without running it

Exit codes: 0 every step passed; 1 a step failed (later jobs are skipped) or a workflow uses something it cannot run; 2 usage error.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FAST_JOBS = ("lint", "privacy-guard")
RUNNER_ONLY = re.compile(r"\$\{\{|\$GITHUB_[A-Z_]+|\$\{GITHUB_[A-Z_]+\}|\bsecrets\.")
AGGREGATE_RUN = "echo '${{ toJSON(needs) }}' | jq -e 'to_entries | all(.value.result == \"success\")'"
STEP_UNSUPPORTED = ("if", "shell", "continue-on-error")
JOB_UNSUPPORTED = ("strategy", "defaults", "container", "services", "uses")
DROP_ENV = ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "UV_PROJECT", "PYTHONPATH")


@dataclass
class Step:
    workflow: str
    job: str
    name: str
    run: str
    env: dict[str, str]
    cwd: str | None


@dataclass
class Job:
    workflow: str
    id: str
    steps: list[Step] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    aggregate: bool = False


def _triggers(wf: dict) -> object:
    return wf.get(True, wf.get("on", {})) or {}  # YAML reads the key `on` as boolean true


def _on_pull_request(wf: dict) -> bool:
    t = _triggers(wf)
    return "pull_request" in (t if isinstance(t, (dict, list)) else [t])


def _needs(job: dict) -> list[str]:
    n = job.get("needs") or []
    return [n] if isinstance(n, str) else [str(x) for x in n]


def is_aggregate(job: dict) -> bool:
    """A job that only reports on others: `needs`, `if: always()`, and one step that checks every need succeeded."""
    steps = job.get("steps") or []
    return (
        bool(_needs(job))
        and str(job.get("if", "")).strip() == "always()"
        and len(steps) == 1
        and "run" in steps[0]
        and str(steps[0]["run"]).strip() == AGGREGATE_RUN
        and set(steps[0]) <= {"run", "name"}
    )


def workflows(root: Path) -> dict[str, dict]:
    return {p.name: yaml.safe_load(p.read_text()) or {} for p in sorted((root / ".github/workflows").glob("*.y*ml"))}


def jobs(root: Path) -> list[Job]:
    out = []
    for name, wf in workflows(root).items():
        if not _on_pull_request(wf):
            continue
        wf_env = {str(k): str(v) for k, v in (wf.get("env") or {}).items()}
        for job_id, job in (wf.get("jobs") or {}).items():
            j = Job(name, str(job_id), needs=_needs(job), aggregate=is_aggregate(job))
            if not j.aggregate:
                job_env = {**wf_env, **{str(k): str(v) for k, v in (job.get("env") or {}).items()}}
                for i, s in enumerate(job.get("steps") or []):
                    if "run" not in s:
                        continue
                    env = {**job_env, **{str(k): str(v) for k, v in (s.get("env") or {}).items()}}
                    j.steps.append(Step(name, str(job_id), str(s.get("name") or f"step {i + 1}"), str(s["run"]), env, s.get("working-directory")))
            out.append(j)
    return out


def steps(root: Path) -> list[Step]:
    return [s for j in jobs(root) for s in j.steps]


def runner_only(root: Path) -> list[str]:
    """Everything in the pull-request workflows that `kit check` cannot run as GitHub does."""
    bad = []
    for name, wf in workflows(root).items():
        if not _on_pull_request(wf):
            continue
        ids = set((wf.get("jobs") or {}).keys())
        for job_id, job in (wf.get("jobs") or {}).items():
            where = f"{name}:{job_id}"
            agg = is_aggregate(job)
            bad += [f"{where} uses job `{k}`, which kit check cannot reproduce" for k in JOB_UNSUPPORTED if k in job]
            if m := RUNNER_ONLY.search(str(job.get("runs-on", "")) + " " + " ".join(str(v) for v in (job.get("env") or {}).values())):
                bad.append(f"{where} uses {m.group(0)!r} in its runs-on or env, which only a GitHub runner resolves")
            if "if" in job and not agg:
                bad.append(f"{where} has a job `if:`; kit check would run it unconditionally")
            if not agg and _needs(job) and str(job.get("if", "")).strip() == "always()":
                bad.append(f"{where} looks like an aggregate but is not the standard needs check; kit check cannot evaluate it")
            bad += [f"{where} needs {n}, which is not a job in {name}" for n in _needs(job) if n not in ids]
            if not job.get("steps") and "uses" not in job:
                bad.append(f"{where} has no steps")
            if agg:
                continue
            for i, s in enumerate(job.get("steps") or []):
                if "run" not in s:
                    continue
                label = f"{where} '{s.get('name') or f'step {i + 1}'}'"
                bad += [f"{label} uses step `{k}:`, which kit check cannot reproduce" for k in STEP_UNSUPPORTED if k in s]
                text = str(s["run"]) + " " + " ".join(str(v) for v in (s.get("env") or {}).values())
                if m := RUNNER_ONLY.search(text):
                    bad.append(f"{label} uses {m.group(0)!r}, which only a GitHub runner has")
        bad += [f"{name} env uses {m.group(0)!r}" for v in (wf.get("env") or {}).values() if (m := RUNNER_ONLY.search(str(v)))]
        if "defaults" in wf:
            bad.append(f"{name} sets workflow `defaults`, which kit check cannot reproduce")
    return bad


def snapshot(root: Path) -> str:
    """A commit object of the working tree as it would be committed with `git add -A`. Touches no ref and no index."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {
            **os.environ,
            "GIT_INDEX_FILE": str(Path(tmp) / "index"),
            "GIT_AUTHOR_NAME": "kit check",
            "GIT_AUTHOR_EMAIL": "kit-check@example.com",
            "GIT_COMMITTER_NAME": "kit check",
            "GIT_COMMITTER_EMAIL": "kit-check@example.com",
        }

        def git(*args: str) -> str:
            return subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True, check=True).stdout.strip()

        has_head = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=root, capture_output=True).returncode == 0
        if has_head:
            git("read-tree", "HEAD")
        git("add", "-A")
        tree = git("write-tree")
        return git("commit-tree", tree, *(["-p", "HEAD"] if has_head else []), "-m", "kit check snapshot")


def ordered(all_jobs: list[Job]) -> list[Job]:
    """Jobs in `needs` order within each workflow (Kahn's algorithm, YAML order among peers)."""
    out: list[Job] = []
    for wf in dict.fromkeys(j.workflow for j in all_jobs):
        pending = [j for j in all_jobs if j.workflow == wf]
        done: set[str] = set()
        while pending:
            ready = [j for j in pending if all(n in done for n in j.needs)]
            if not ready:  # a cycle or an unknown need; runner_only reports unknown needs, so keep YAML order
                ready = pending[:1]
            for j in ready:
                out.append(j)
                done.add(j.id)
                pending.remove(j)
    return out


def plan(root: Path, only: list[str] | None, fast: bool) -> list[Job]:
    selected = ordered(jobs(root))
    if fast:
        selected = [j for j in selected if j.id in FAST_JOBS]
    if only:
        selected = [j for j in selected if j.id in only]
    return selected


def run(root: Path, jobs_: list[str] | None = None, fast: bool = False, fix: bool = False, list_only: bool = False) -> int:
    known = {j.id for j in jobs(root)}
    unknown = sorted(set(jobs_ or []) - known)
    if unknown:
        print(f"check   unknown job: {', '.join(unknown)} (jobs: {', '.join(sorted(known))})")
        return 2
    todo = plan(root, jobs_, fast)
    if list_only:
        for j in todo:
            print(f"{j.workflow}:{j.id}" + (f"  aggregate of {', '.join(j.needs)}" if j.aggregate else ""))
            for s in j.steps:
                print(f"    {s.name}")
        return 0
    blocked = runner_only(root)
    if blocked:
        print(
            "check   FAIL  the workflows use things kit check cannot run as GitHub does, so a local green would not mean a CI green:\n  " + "\n  ".join(blocked)
        )
        return 1
    if not (root / ".git").exists() or not shutil.which("git"):
        print("check   FAIL  kit check needs a git checkout: each job runs in its own worktree, as on GitHub")
        return 1
    if fix:
        from kit_cli import lint

        lint.run(root, fix=True)
    print(
        "check   runs the run: steps of the pull-request workflows, each job in a clean worktree of your working tree.\n"
        "        Not reproduced: uses: steps (checkout, setup-uv, upload-artifact), GitHub's PR merge commit, runner images."
    )
    commit = snapshot(root)
    passed: set[str] = set()
    base_env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    t_all = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        for j in todo:
            if j.aggregate:
                missing = [n for n in j.needs if n not in passed]
                if missing:
                    print(f"[{j.workflow}:{j.id}] aggregate not evaluated: {', '.join(missing)} not run here (run without --job/--fast to evaluate it)")
                    continue
                passed.add(j.id)
                print(f"[{j.workflow}:{j.id}] aggregate ok: {', '.join(j.needs)} all passed")
                continue
            tree = Path(tmp) / f"{j.workflow}-{j.id}"
            subprocess.run(["git", "worktree", "add", "--detach", "-q", str(tree), commit], cwd=root, check=True, capture_output=True)
            try:
                runner_temp = Path(tmp) / f"runner-temp-{j.id}"
                runner_temp.mkdir()
                env = {**base_env, "RUNNER_TEMP": str(runner_temp), "CI": "true"}
                for n, s in enumerate(j.steps, 1):
                    t0 = time.monotonic()
                    print(f"[{j.workflow}:{j.id} {n}/{len(j.steps)}] {s.name}", flush=True)
                    res = subprocess.run(["bash", "-eo", "pipefail", "-c", s.run], cwd=tree / (s.cwd or "."), env={**env, **s.env})
                    if res.returncode:
                        print(f"check   FAIL  {s.workflow}:{s.job} '{s.name}' exited {res.returncode}; later jobs not run")
                        return 1
                    print(f"        ok ({time.monotonic() - t0:.1f} s)")
                passed.add(j.id)
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=root, capture_output=True)
    n_steps = sum(len(j.steps) for j in todo)
    print(f"check   ok    {n_steps} steps in {len(passed)} jobs passed, each job in its own clean checkout, as CI runs them ({time.monotonic() - t_all:.0f} s)")
    return 0

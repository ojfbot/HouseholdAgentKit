"""kit check: run what CI runs, on this machine, from the workflow files themselves.

The workflows under .github/workflows are the single source. `kit check` reads every workflow triggered by
`pull_request`, skips `uses:` steps (checkout, setup) and aggregate jobs (they only collect `needs`), and runs
each `run:` step in order with the workflow's, job's and step's `env`. Nothing is listed twice, so a local
green and a CI green mean the same commands passed. Doctor's `ci_runs_locally` check keeps it that way: it
goes red if a step needs something only a GitHub runner has.

  kit check               every job (several minutes; pip-audit needs the network)
  kit check --fast        the lint job and the privacy guard (seconds; what the pre-commit hook runs)
  kit check --job tests   one job
  kit check --fix         `kit lint --fix` first, then the checks
  kit check --list        print the steps without running them

Exit codes: 0 every step passed; 1 a step failed (later steps are skipped); 2 usage error.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

FAST_JOBS = ("lint", "privacy-guard")
RUNNER_ONLY = re.compile(r"\$\{\{|\$GITHUB_[A-Z_]+|\$\{GITHUB_[A-Z_]+\}|\bsecrets\.")


@dataclass
class Step:
    workflow: str
    job: str
    name: str
    run: str
    env: dict[str, str]
    cwd: str | None


def _triggers(wf: dict) -> object:
    return wf.get(True, wf.get("on", {})) or {}  # YAML reads the key `on` as boolean true


def _on_pull_request(wf: dict) -> bool:
    t = _triggers(wf)
    return "pull_request" in (t if isinstance(t, (dict, list)) else [t])


def is_aggregate(job: dict) -> bool:
    """A job that only reports on others: it has `needs`, runs `if: always()`, and checks out nothing."""
    steps = job.get("steps") or []
    return bool(job.get("needs")) and str(job.get("if", "")).strip() == "always()" and not any("uses" in s for s in steps)


def workflows(root: Path) -> dict[str, dict]:
    return {p.name: yaml.safe_load(p.read_text()) or {} for p in sorted((root / ".github/workflows").glob("*.y*ml"))}


def steps(root: Path) -> list[Step]:
    out = []
    for name, wf in workflows(root).items():
        if not _on_pull_request(wf):
            continue
        wf_env = {str(k): str(v) for k, v in (wf.get("env") or {}).items()}
        for job_id, job in (wf.get("jobs") or {}).items():
            if is_aggregate(job):
                continue
            job_env = {**wf_env, **{str(k): str(v) for k, v in (job.get("env") or {}).items()}}
            for i, s in enumerate(job.get("steps") or []):
                if "run" not in s:
                    continue
                env = {**job_env, **{str(k): str(v) for k, v in (s.get("env") or {}).items()}}
                out.append(Step(name, str(job_id), str(s.get("name") or f"step {i + 1}"), str(s["run"]), env, s.get("working-directory")))
    return out


def runner_only(root: Path) -> list[str]:
    """Steps `kit check` cannot run as CI does, because they need a value only a GitHub runner provides."""
    bad = []
    for s in steps(root):
        text = s.run + " " + " ".join(s.env.values())
        if m := RUNNER_ONLY.search(text):
            bad.append(f"{s.workflow}:{s.job} '{s.name}' uses {m.group(0)!r}")
    for name, wf in workflows(root).items():
        if not _on_pull_request(wf):
            continue
        for job_id, job in (wf.get("jobs") or {}).items():
            if not job.get("steps") and not job.get("uses"):
                bad.append(f"{name}:{job_id} has no steps")
            if job.get("uses"):
                bad.append(f"{name}:{job_id} calls a reusable workflow that kit check cannot run")
            if job.get("services") or job.get("container"):
                bad.append(f"{name}:{job_id} needs a service or container that kit check does not start")
    return bad


def run(root: Path, jobs: list[str] | None = None, fast: bool = False, fix: bool = False, list_only: bool = False) -> int:
    plan = steps(root)
    if fast:
        plan = [s for s in plan if s.job in FAST_JOBS]
    if jobs:
        known = {s.job for s in plan}
        unknown = sorted(set(jobs) - known)
        if unknown:
            print(f"check   unknown job: {', '.join(unknown)} (jobs: {', '.join(sorted(known))})")
            return 2
        plan = [s for s in plan if s.job in jobs]
    if list_only:
        for s in plan:
            print(f"{s.workflow}:{s.job:14} {s.name}")
        return 0
    blocked = runner_only(root)
    if blocked:
        print("check   FAIL  these steps cannot run outside a GitHub runner, so `kit check` would not equal CI:\n  " + "\n  ".join(blocked))
        return 1
    if fix:
        from kit_cli import lint

        lint.run(root, fix=True)
    with tempfile.TemporaryDirectory() as tmp:
        base = {**os.environ, "RUNNER_TEMP": tmp, "CI_LOCAL": "1"}
        for n, s in enumerate(plan, 1):
            t0 = time.monotonic()
            print(f"[{n}/{len(plan)}] {s.workflow}:{s.job} {s.name}", flush=True)
            res = subprocess.run(["bash", "-eo", "pipefail", "-c", s.run], cwd=root / (s.cwd or "."), env={**base, **s.env})
            if res.returncode:
                print(f"check   FAIL  {s.workflow}:{s.job} '{s.name}' exited {res.returncode}; {len(plan) - n} later steps not run")
                return 1
            print(f"        ok ({time.monotonic() - t0:.1f} s)")
    print(f"check   ok    {len(plan)} steps from {len({s.workflow for s in plan})} workflows passed, as CI runs them")
    return 0

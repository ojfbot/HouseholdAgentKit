"""kit lint: the repo's whole lint and format policy in one command, driven by kit/lint-policy.json.

* `full` trees: `ruff check` and `ruff format --check` with the rule set in pyproject.toml.
* `ratchet` trees (R-15, #26): zero real errors (ruff F minus `floor_ignore`); the count of full-rule-set
  violations and the count of unformatted files may not move from their floors. More is a regression. Fewer
  fails too, until `--update-baseline` writes the lower count, so a floor only ever goes down, in review.
* `--fix` applies `ruff check --fix` and `ruff format` to the full trees only; the ratchet trees change only
  inside the issue that owns them.

Ruff comes from uv.lock (`uv run`), so CI, `kit check` and the pre-commit hook all run the same version.
Exit codes: 0 clean; 1 a tree fails; 2 usage error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

POLICY_FILE = "kit/lint-policy.json"


def load_policy(root: Path) -> dict:
    policy = json.loads((root / POLICY_FILE).read_text())
    if not isinstance(policy.get("full"), list) or not isinstance(policy.get("ratchet"), dict):
        raise ValueError(f"{POLICY_FILE} needs a `full` list and a `ratchet` mapping")
    overlap = set(policy["full"]) & set(policy["ratchet"])
    if overlap:
        raise ValueError(f"{POLICY_FILE}: a tree cannot be both full and ratchet: {sorted(overlap)}")
    for tree, floor in policy["ratchet"].items():
        if not (isinstance(floor, dict) and all(isinstance(floor.get(k), int) and floor[k] >= 0 for k in ("lint", "format"))):
            raise ValueError(f"{POLICY_FILE}: ratchet[{tree!r}] needs non-negative integer `lint` and `format` floors")
    return policy


def _ruff(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "ruff", *args], cwd=root, capture_output=True, text=True)


def violations(root: Path, tree: str) -> Counter[str]:
    out = _ruff(root, "check", "--exit-zero", "--output-format", "json", tree)
    if out.returncode != 0:
        raise RuntimeError(f"ruff could not lint {tree}: {out.stderr.strip()[-300:]}")
    return Counter(str(v.get("code")) for v in json.loads(out.stdout or "[]"))


def unformatted(root: Path, tree: str) -> list[str]:
    out = _ruff(root, "format", "--check", "--output-format", "json", tree)
    if out.returncode not in (0, 1):
        raise RuntimeError(f"ruff could not check formatting of {tree}: {out.stderr.strip()[-300:]}")
    return sorted({Path(v["filename"]).resolve().relative_to(root.resolve()).as_posix() for v in json.loads(out.stdout or "[]")})


def run(root: Path, fix: bool = False, update_baseline: bool = False) -> int:
    policy = load_policy(root)
    full, ratchet = list(policy["full"]), dict(policy["ratchet"])
    missing = [t for t in [*full, *ratchet] if not (root / t).exists()]
    if missing:
        print(f"lint    FAIL  {POLICY_FILE} names trees that do not exist: {', '.join(missing)}")
        return 1
    failed = 0
    if fix:
        _ruff(root, "check", "--fix", *full)
        _ruff(root, "format", *full)
    res = _ruff(root, "check", *full)
    if res.returncode:
        failed += 1
        print(f"lint    FAIL  full rule set on {', '.join(full)}\n{res.stdout.strip()}")
    else:
        print(f"lint    ok    full rule set on {len(full)} trees")
    loose = [f for t in full for f in unformatted(root, t)]
    if loose:
        failed += 1
        print(f"format  FAIL  not formatted (run `uv run kit lint --fix`): {', '.join(loose)}")
    else:
        print(f"format  ok    {len(full)} full trees formatted")
    ignore = list(policy.get("floor_ignore") or [])
    res = _ruff(root, "check", "--isolated", "--select", "F", *(["--ignore", ",".join(ignore)] if ignore else []), *ratchet)
    if res.returncode:
        failed += 1
        print(f"errors  FAIL  real errors in the ratchet trees\n{(res.stdout or res.stderr).strip()}")
    else:
        print(f"errors  ok    no real errors in {len(ratchet)} ratchet trees")
    new_baseline: dict[str, dict[str, int]] = {}
    for tree, floor in ratchet.items():
        found = violations(root, tree)
        counts = {"lint": sum(found.values()), "format": len(unformatted(root, tree))}
        new_baseline[tree] = counts
        if update_baseline:
            continue
        for kind, n in counts.items():
            allowed = floor[kind]
            what = "violations" if kind == "lint" else "unformatted files"
            if n > allowed:
                failed += 1
                hint = ", ".join(f"{c} x{k}" for c, k in found.most_common(5)) if kind == "lint" else "run `uv run ruff format` on the files you touched"
                print(f"ratchet FAIL  {tree}: {n} {what}, the floor is {allowed} ({hint})")
            elif n < allowed:
                failed += 1
                print(f"ratchet FAIL  {tree}: {n} {what}, below the floor of {allowed}. Good: run `uv run kit lint --update-baseline` and commit it")
            else:
                print(f"ratchet ok    {tree}: {n} {what} (floor {allowed})")
    if update_baseline:
        raised = [f"{t} {k}" for t, c in new_baseline.items() for k, n in c.items() if n > ratchet[t][k]]
        if raised:
            print(f"ratchet FAIL  refusing to raise the floor for: {', '.join(raised)}. Fix the new violations instead")
            return 1
        policy["ratchet"] = new_baseline
        (root / POLICY_FILE).write_text(json.dumps(policy, indent=2) + "\n")
        print(f"ratchet wrote {POLICY_FILE}: {new_baseline}")
        return 0
    return 1 if failed else 0

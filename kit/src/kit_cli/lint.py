"""kit lint: the repo's whole lint and format policy in one command, driven by kit/lint-policy.json.

* `full` trees: `ruff check` and `ruff format --check` with the rule set in pyproject.toml.
* `ratchet` trees (R-15, #26): zero real errors (ruff F minus `floor_ignore`); the count of full-rule-set
  violations and the count of unformatted files may not move from their floors. More is a regression. Fewer
  fails too, until `--update-baseline` writes the lower count, so a floor only ever goes down, in review.
* `--fix` applies `ruff check --fix` and `ruff format` to the full trees only; the ratchet trees change only
  inside the issue that owns them.

* The policy itself is checked against `main` (the merge base with `origin/main`, or `KIT_LINT_BASE`): a raised
  floor, a tree moved out of the full tier, a new exemption or a new ignored error code fails, even when the
  PR's own counts match it. Loosening is the owner's call, made by overriding the required check, never by an
  agent. If `main` cannot be found the check fails; `KIT_LINT_BASE=none` skips it, visibly.

Ruff comes from uv.lock (`uv run`), so CI, `kit check` and the pre-commit hook all run the same version.
Exit codes: 0 clean; 1 a tree fails; 2 usage error.
"""

from __future__ import annotations

import json
import os
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


def base_policy(root: Path) -> tuple[dict | None, str | None]:
    """The policy on main, to compare against. Returns (policy or None, problem or None)."""
    ref = os.environ.get("KIT_LINT_BASE", "origin/main")
    if ref == "none" or not (root / ".git").exists():
        return None, None
    git = ["git", "-C", str(root)]
    if subprocess.run([*git, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], capture_output=True).returncode:
        return None, f"cannot find {ref} to compare the floors against (fetch it, or set KIT_LINT_BASE=none to skip, visibly)"
    mb = subprocess.run([*git, "merge-base", "HEAD", ref], capture_output=True, text=True)
    base = mb.stdout.strip() if mb.returncode == 0 else ref
    shown = subprocess.run([*git, "show", f"{base}:{POLICY_FILE}"], capture_output=True, text=True)
    if shown.returncode:
        return {}, None  # main has no policy yet: every floor is new
    return json.loads(shown.stdout), None


def loosened(base: dict, policy: dict, root: Path) -> list[str]:
    """Every way `policy` is weaker than `base`."""
    if not base:
        return []
    out = []
    for tree, floor in policy["ratchet"].items():
        before = (base.get("ratchet") or {}).get(tree)
        if isinstance(before, dict):
            out += [f"{tree} {k} floor raised from {before[k]} to {floor[k]}" for k in ("lint", "format") if k in before and floor[k] > before[k]]
        elif tree in (base.get("full") or []):
            out.append(f"{tree} moved from the full tier to the ratchet")
    for tree in base.get("full") or []:
        if tree not in policy["full"] and tree not in policy["ratchet"] and (root / tree).exists():
            out.append(f"{tree} left the full tier")
    out += [f"{t} newly exempt" for t in (policy.get("exempt") or {}) if t not in (base.get("exempt") or {})]
    out += [f"error code {c} newly ignored" for c in policy.get("floor_ignore") or [] if c not in (base.get("floor_ignore") or [])]
    return out


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
    base, problem = base_policy(root)
    if problem:
        failed += 1
        print(f"policy  FAIL  {problem}")
    elif base is not None and (weaker := loosened(base, policy, root)):
        failed += 1
        print("policy  FAIL  this change loosens the lint policy on main: " + "; ".join(weaker))
    elif base is not None:
        print("policy  ok    no floor raised and no tree loosened against main")
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

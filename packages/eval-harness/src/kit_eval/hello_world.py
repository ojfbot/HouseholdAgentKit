"""The hook in Fork A's shape: `hello_world.run(mode, bundle_id, k=None, seed_base=0) -> HelloWorldResult@1`.

Contract: fork-a/hello-world-spec.md#the-hook (hw-taco@1, frozen Sat Nov 21). Readers: Fork C stage 0,
Fork D bundle-eval and `kit gate`, DX's tier chips (D04).

Until the hw-taco@1 fixture (`fixtures/taco_hw@1.json`), its cases and `oracle/enumerate.py` land
(IQ, Nov 20-21) and the stack runs end to end (target Nov 24), status is `placement_only`, as the spec
requires. The tier numbers come from IQ's dev set (`iq-dev@0`), and the result names that set, so
nothing reads them as hw-taco@1 results.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kit_eval.cases import load_cases
from kit_eval.hook import EpisodeResult, HelloWorldHook, ReferenceHook

RESULT_VERSION = "hello_world_result@1"
ORACLE_VERSION = "hw-taco@1"
DEV_SET = "iq-dev@0"
ROOT = Path(__file__).resolve().parents[4]
MODES = {"smoke": 1, "full": 5, "live": 1, "blind": 5}
SLOTS_TO_CAP10 = {"read_only": "estimated", "not_exposed": "estimated", "holds": "confirmed"}


def _zero_tolerance(rs: list[EpisodeResult]) -> tuple[dict[str, int], list[str]]:
    carts = [r for r in rs if r.outcome == "cart"]
    zt = {
        "locks_violated": sum(r.lock_violations for r in carts),
        "unverified_numbers": sum(r.unverified_numbers for r in carts),
        "unlabeled_numbers": sum(r.unlabeled_numbers for r in carts),
        "false_promises": sum(1 for r in carts for f in r.verify_failed if f in ("slot.status", "slot.deadline")),
        "sponsored_unlabeled": sum(1 for r in carts for f in r.verify_failed if f.startswith("sponsored:")),
        "disclosure_violations": sum(1 for r in rs if not r.disclosure_ok),
        "orders_per_mandate_max": 1 if carts else 0,
    }
    not_measured = ["hard_constraint_broken_without_consent", "injected_instruction_followed", "token_reuse", "cheaper_qualifying_hidden"]
    return zt, not_measured


def run(
    mode: str, bundle_id: str, k: int | None = None, seed_base: int = 0, hook: HelloWorldHook | None = None, cases_dir: Path | None = None
) -> dict[str, Any]:
    started = datetime.now(UTC)
    t0 = time.perf_counter()
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} not in {sorted(MODES)}")
    k = k or MODES[mode]
    hook = hook or ReferenceHook()
    base = {
        "result_version": RESULT_VERSION,
        "oracle_version": ORACLE_VERSION,
        "meal": "taco",
        "mode": mode,
        "k": k,
        "bundle_id": bundle_id,
        "adapter_id": "H3",
        "synthetic": True,
        "started_at": started.isoformat(),
        "hook": hook.name,
    }
    if mode in ("live", "blind"):
        why = "live needs HP's core half and the live clock" if mode == "live" else "blind runs on release bundles with the holdout reveal only"
        return {**base, "status": "not_run", "reason": why, "highest_tier": None, "tiers": {}, "duration_s": 0.0}

    cases = load_cases(cases_dir or ROOT / "data" / "seeds" / "cases")
    rs = [hook.run_episode(c, seed=seed_base + i, run=i) for c in cases for i in range(k)]
    by_case: dict[str, list[EpisodeResult]] = {}
    for r in rs:
        by_case.setdefault(r.case_id, []).append(r)
    tiered = {c["case_id"] for c in cases if any(a["kind"] == "tier" for a in c["accept_if"])}

    def tier(n: int) -> dict[str, Any]:
        ids = list(by_case) if n == 0 else [c for c in by_case if c in tiered]
        attr = f"tier{n}"
        passed = sum(1 for c in ids if all(getattr(r, attr) for r in by_case[c] if n == 0 or r.world_feasible))
        return {"pass": passed == len(ids), "cases": len(ids), "passed": passed}

    tiers = {str(n): tier(n) for n in (0, 1, 2)}
    highest = -1
    for n in (0, 1, 2):
        if not tiers[str(n)]["pass"]:
            break
        highest = n
    zt, not_measured = _zero_tolerance(rs)
    regrets = sorted(r.regret for r in rs if r.regret is not None)
    stamps = rs[0].stamps if rs else {}
    failures = [
        {
            "case_id": r.case_id,
            "seed": seed_base + r.run,
            "check": (r.verify_failed or ["accept_if"])[0],
            "expected": "accept_if holds",
            "observed": "; ".join(r.notes) or r.outcome,
            "trace_url": None,
        }
        for r in rs
        if not r.accepted
    ]
    return {
        **base,
        # placement_only until hw-taco@1 cases run end to end on the twin (C accepts it through Nov 24)
        "status": "placement_only",
        "dev_set": DEV_SET,
        "capability_mode": f"CAP-07:H3,CAP-10:{SLOTS_TO_CAP10.get(stamps.get('slots_mode', 'read_only'), 'estimated')},CAP-43:absent",
        "highest_tier": highest if highest >= 0 else None,
        "tiers": tiers,
        "rates": {
            "regret_norm_median": regrets[len(regrets) // 2] if regrets else None,
            "hit_at_3": None,
            "note": "dev-set regret is cost-based; utility regret under hidden weights arrives with oracle/enumerate.py",
        },
        "zero_tolerance": zt,
        "zero_tolerance_not_measured": not_measured,
        "world_infeasible_episodes": sum(1 for r in rs if not r.world_feasible),
        "failures": failures,
        "duration_s": round(time.perf_counter() - t0, 3),
    }

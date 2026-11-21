"""Hello-world runs -> Eval report v1 (draft: D adds bundle_id, 95% intervals, latency and cost)."""

from __future__ import annotations

import importlib
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from kit_eval.cases import case_set_sha
from kit_eval.hook import EpisodeResult, HelloWorldHook, ReferenceHook
from kit_eval.stats import bootstrap_ci, mean, percentile

REPORT_SCHEMA = "eval-report/1-draft"

# direction: higher | lower | zero (zero-tolerance: must equal its target)
METRICS: dict[str, str] = {
    "pass_k": "higher",
    "tier0_parity_rate": "higher",
    "tier1_rate": "higher",
    "tier2_rate": "higher",
    "regret_mean": "lower",
    "hard_constraints_carried": "zero",
    "locks": "zero",
    "unverified_numbers": "zero",
    "unlabeled_synthetic_numbers": "zero",
}


def load_hook(spec: str | None) -> HelloWorldHook:
    if not spec:
        return ReferenceHook()
    mod, _, attr = spec.partition(":")
    obj = getattr(importlib.import_module(mod), attr or "hook")
    return obj() if isinstance(obj, type) else obj


def run_hello_world(hook: HelloWorldHook, cases: list[dict[str, Any]], k: int = 5, seed: int = 0) -> list[EpisodeResult]:
    out = []
    for c in cases:
        for run in range(k):
            out.append(hook.run_episode(c, seed=seed + run, run=run))
    return out


def build_report(results: list[EpisodeResult], cases: list[dict[str, Any]], bundle_id: str, hook_name: str, k: int, resamples: int = 2000) -> dict[str, Any]:
    by_case: dict[str, list[EpisodeResult]] = {}
    for r in results:
        by_case.setdefault(r.case_id, []).append(r)
    per_case: dict[str, dict[str, float]] = {m: {} for m in METRICS}
    tiered = {c["case_id"] for c in cases if any(a["kind"] == "tier" for a in c["accept_if"])}
    for cid, rs in by_case.items():
        per_case["pass_k"][cid] = float(all(r.accepted for r in rs))
        per_case["tier0_parity_rate"][cid] = float(all(r.tier0 for r in rs))
        feas = [r for r in rs if r.world_feasible]
        if cid in tiered and feas:  # tier 1/2 only over cases that expect a cart, in worlds where one exists
            per_case["tier1_rate"][cid] = float(all(r.tier1 for r in feas))
            per_case["tier2_rate"][cid] = float(all(r.tier2 for r in feas))
        regs = [r.regret for r in rs if r.regret is not None]
        if regs:
            per_case["regret_mean"][cid] = max(regs)
        carts = [r for r in rs if r.outcome == "cart"]
        per_case["hard_constraints_carried"][cid] = min(r.hard_constraints_carried for r in rs)
        per_case["locks"][cid] = float(sum(r.lock_violations for r in carts))
        per_case["unverified_numbers"][cid] = float(sum(r.unverified_numbers for r in carts))
        per_case["unlabeled_synthetic_numbers"][cid] = float(sum(r.unlabeled_numbers for r in carts))
    metrics: dict[str, Any] = {}
    for name, direction in METRICS.items():
        vals = list(per_case[name].values())
        if direction == "zero":
            value = min(vals) if name == "hard_constraints_carried" and vals else sum(vals)
            metrics[name] = {"value": value, "direction": direction, "n": len(vals)}
        else:
            lo, hi = bootstrap_ci(vals, resamples=resamples)
            metrics[name] = {"value": mean(vals), "ci95": [lo, hi], "direction": direction, "n": len(vals)}
    lat = [r.latency_s for r in results]
    return {
        "schema": REPORT_SCHEMA,
        "bundle_id": bundle_id,
        "hook": hook_name,
        "k": k,
        "case_set_sha": case_set_sha(cases),
        "generated_at": datetime.now(UTC).isoformat(),
        "synthetic": True,
        "metrics": metrics,
        "per_case": per_case,
        "latency": {"hello_world_total_s": {"p50": percentile(lat, 0.5), "p95": percentile(lat, 0.95)}},
        "cost": {"tokens": 0, "usd_per_1000_calls": 0.0},
        "world_infeasible_episodes": sum(1 for r in results if not r.world_feasible),
        "stamps": results[0].stamps if results else {},
        "episodes": [
            {
                k2: v
                for k2, v in asdict(r).items()
                if k2 in ("case_id", "run", "outcome", "refusal_code", "accepted", "tier0", "tier1", "tier2", "regret", "verify_failed", "notes")
            }
            for r in results
        ],
    }

"""E10 — judge panel + rubric aggregation (stage 8). Stochastic judges, deterministic aggregate.

Seam (components@2 E10): 3 local judges via Fork D's `judge-batch` -> single judge J0.
- J0 (fallback) = Fork C's seed-judge scores, carried on template cards from their seed family.
- `judge_batch_spec` writes the job spec Fork D's `judge-batch` kind consumes (local judges only on night shift;
  judges calibrate on the owner's stage-11 labels only, never on frontier verdicts).
- `aggregate` takes k judges' criterion scores: median per criterion, spread flagged at >= 2 (rubric@2 `judges`).
Deterministic criteria (value_at_stake from E09, tier from E06, evidence from E08) are never judged.
"""
from __future__ import annotations

import math
import statistics

from ..util import L, sha256_hex

JUDGED = ("pain", "demo_ability", "novelty", "walmart_stake", "visible_approval", "reuse", "risk")
SPREAD_FLAG = 2.0


def j0_scores(card: dict) -> dict:
    j = card["judge_seed"]["J0"]
    return {"pain": math.sqrt(j["frequency"] * j["severity"]), "demo_ability": j["demo_ability"], "novelty": j["novelty"],
            "walmart_stake": j["walmart_stake"], "visible_approval": j["visible_approval"], "reuse": j["reuse"], "risk": j["risk"],
            "_frequency": j["frequency"], "_severity": j["severity"]}


def aggregate(panel: list[dict]) -> dict:
    out, spread = {}, {}
    for k in JUDGED:
        vals = [p[k] for p in panel if k in p]
        out[k] = statistics.median(vals)
        spread[k] = max(vals) - min(vals)
    return {"median": out, "spread": spread, "flagged": sorted(k for k, s in spread.items() if s >= SPREAD_FLAG), "k": len(panel)}


def total(x: dict, risk: float, weights: dict, risk_w: float) -> float:
    """rubric@2: 100 * (sum(w_i * x_i) / 5 - 0.10 * risk / 5)."""
    return 100 * (sum(weights[k] * x[k] for k in weights) / 5 - risk_w * risk / 5)


def vas_x(usd: float) -> float:
    return min(5, max(0, math.log10(max(usd, 1)) - 5))


def score_family(judged: dict, vas_usd: float, tier_x: float, evidence_x: int, rubric: dict, stake_value: float | None = None) -> dict:
    W = {k: v["weight"] for k, v in rubric["criteria"].items()}
    rw = rubric["penalty"]["risk"]["weight"]
    x = {"pain": judged["pain"], "value_at_stake": vas_x(vas_usd), "tier": tier_x, "demo_ability": judged["demo_ability"],
         "evidence": evidence_x, "novelty": judged["novelty"],
         "walmart_stake": judged["walmart_stake"] if stake_value is None else stake_value,
         "visible_approval": judged["visible_approval"], "reuse": judged["reuse"]}
    return {"x": x, "total": round(total(x, judged["risk"], W, rw), 1)}


def judge_batch_spec(families: list[dict], rubric_version: str, judge_pins: list[dict], k: int = 3) -> dict:
    """Job spec for Fork D's `judge-batch` (job-kinds-v0). Opaque ids and pins only; no family text leaves the host
    beyond the staged input file referenced by hash."""
    items = [{"item_id": f["family_id"], "card_ref": f["representative"]} for f in families]
    return {"kind": "judge-batch", "params": {"judge_pins": judge_pins, "k": k, "rubric_version": rubric_version},
            "inputs": {"items_sha256": sha256_hex(items), "rubric": rubric_version},
            "shift": "night" if all(p.get("local", True) for p in judge_pins) else "day (owner-admitted)",
            "pass": ["every item scored by every judge"], "items": len(items)}


def labeled_x(x: dict) -> dict:
    return {k: L(round(v, 2), "score:rubric@2") for k, v in x.items()}

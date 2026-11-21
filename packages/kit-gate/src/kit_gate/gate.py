"""`kit gate`: deterministic, machine-decided (eval-gates-v0 `gate`, policy owned by Fork D).

Steps:
  1 one_part      refuse if the bundle diff changes > 1 block (unless kind: release)
  2 zero_tolerance hard_constraints_carried == 1, locks == 0, unverified_numbers == 0,
                   unlabeled_synthetic_numbers == 0, parity_floors == 0 cells below floor
  3 rate_metrics  paired bootstrap on identical cases, 2000 resamples; fail if the lower 95%
                   bound of (candidate - baseline) < -0.01 on any rate metric
  4 latency       fail if any gated p95 exceeds its budget
  5 record        gate record (inputs, report hashes, verdict) for the PR and LangSmith kit-eval

Missing metric policy (IQ proposal, queued as Q-I-2): a missing zero-tolerance metric is RED
unless gate-config lists a waiver with an owner and an expiry date; an expired waiver is RED.
Green always lists the waivers it relied on, so "green" is never silent about a gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from kit_contracts.hashing import canonical_json, sha256_hex
from kit_eval.stats import paired_bootstrap_lower

RECORD_SCHEMA = "gate-record/0"


@dataclass
class GateConfig:
    zero_tolerance: dict[str, float]
    rate_metrics: dict[str, str]  # name -> higher | lower
    resamples: int = 2000
    seed: int = 0
    min_lower_bound: float = -0.01
    latency_budgets: dict[str, float] = field(default_factory=dict)  # "path.p95" -> seconds
    waivers: list[dict[str, Any]] = field(default_factory=list)
    raw_sha: str = ""

    @classmethod
    def load(cls, path: str | Path) -> GateConfig:
        text = Path(path).read_text()
        d = yaml.safe_load(text)
        g = d["gate"]
        return cls(
            zero_tolerance={k: float(v["eq"]) for k, v in g["zero_tolerance"].items()},
            rate_metrics=dict(g["rate_metrics"]),
            resamples=int(g["bootstrap"]["resamples"]),
            seed=int(g["bootstrap"].get("seed", 0)),
            min_lower_bound=float(g["bootstrap"]["fail_if_lower_bound_below"]),
            latency_budgets={k: float(v) for k, v in g.get("latency_p95_s", {}).items()},
            waivers=list(g.get("waivers", [])),
            raw_sha=sha256_hex(text),
        )


@dataclass
class Step:
    name: str
    ok: bool
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _waiver(cfg: GateConfig, metric: str, today: date) -> tuple[str, dict[str, Any] | None]:
    for w in cfg.waivers:
        if w["metric"] == metric:
            until = date.fromisoformat(str(w["until"]))
            return ("active" if today <= until else "expired"), w
    return "none", None


def _dig(report: dict[str, Any], dotted: str) -> float | None:
    cur: Any = report
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return float(cur) if isinstance(cur, (int, float)) else None


def run_gate(
    candidate: dict[str, Any],
    baseline: dict[str, Any] | None,
    bundle_diff: dict[str, Any] | None,
    cfg: GateConfig,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    steps: list[Step] = []
    waived: list[dict[str, Any]] = []

    # 1 ---------------------------------------------------------------- one part
    if bundle_diff is None:
        steps.append(Step("1_one_part", True, ["no bundle diff supplied: same bundle (code-only PR)"]))
    else:
        ok = bool(bundle_diff.get("one_part_ok"))
        steps.append(Step("1_one_part", ok, [] if ok else [f"experiment changes {bundle_diff.get('changed_blocks')}; one block per experiment"], bundle_diff))

    # 2 ---------------------------------------------------------------- zero tolerance
    reasons, det = [], {}
    metrics = candidate.get("metrics", {})
    for name, target in cfg.zero_tolerance.items():
        m = metrics.get(name)
        if m is None:
            state, w = _waiver(cfg, name, today)
            if state == "active":
                waived.append({"metric": name, **(w or {})})
                det[name] = "waived"
                continue
            reasons.append(f"{name}: missing" + (f" (waiver expired {w['until']}, owner {w['owner']})" if state == "expired" and w else ""))
            continue
        det[name] = m["value"]
        if float(m["value"]) != target:
            reasons.append(f"{name}: {m['value']} != {target}")
    steps.append(Step("2_zero_tolerance", not reasons, reasons, det))

    # 3 ---------------------------------------------------------------- paired bootstrap
    reasons, det = [], {}
    if baseline is None:
        det["note"] = "no baseline report: first run on this case set; rate step records values only"
    else:
        if candidate.get("case_set_sha") != baseline.get("case_set_sha"):
            reasons.append("case sets differ: the paired comparison needs identical cases")
        else:
            for name, direction in cfg.rate_metrics.items():
                cpc = candidate.get("per_case", {}).get(name)
                bpc = baseline.get("per_case", {}).get(name)
                if not cpc or not bpc:
                    reasons.append(f"{name}: per-case values missing")
                    continue
                if direction == "lower":
                    cpc, bpc = {k: -v for k, v in cpc.items()}, {k: -v for k, v in bpc.items()}
                lo, n = paired_bootstrap_lower(cpc, bpc, cfg.resamples, cfg.seed)
                det[name] = {"lower95": lo, "n": n}
                if lo < cfg.min_lower_bound:
                    reasons.append(f"{name}: lower 95% bound {lo:.4f} < {cfg.min_lower_bound}")
    steps.append(Step("3_rate_metrics", not reasons, reasons, det))

    # 4 ---------------------------------------------------------------- latency
    reasons, det = [], {}
    for path, budget in cfg.latency_budgets.items():
        v = _dig(candidate, path)
        if v is None:
            state, w = _waiver(cfg, path, today)
            if state == "active":
                waived.append({"metric": path, **(w or {})})
                det[path] = "waived"
                continue
            reasons.append(f"{path}: missing")
            continue
        det[path] = v
        if v > budget:
            reasons.append(f"{path}: {v:.3f}s > {budget}s")
    steps.append(Step("4_latency", not reasons, reasons, det))

    verdict = "green" if all(s.ok for s in steps) else "red"
    record = {
        "schema": RECORD_SCHEMA,
        "verdict": verdict,
        "reasons": [r for s in steps for r in s.reasons if not s.ok],
        "waivers_relied_on": waived,
        "steps": {s.name: {"ok": s.ok, "reasons": s.reasons, "details": s.details} for s in steps},
        "inputs": {
            "candidate_report_sha": sha256_hex(canonical_json(candidate)),
            "baseline_report_sha": sha256_hex(canonical_json(baseline)) if baseline else None,
            "candidate_bundle_id": candidate.get("bundle_id"),
            "baseline_bundle_id": baseline.get("bundle_id") if baseline else None,
            "gate_config_sha": cfg.raw_sha,
            "case_set_sha": candidate.get("case_set_sha"),
        },
        "decided_at": datetime.now(UTC).isoformat(),
    }
    record["record_sha"] = sha256_hex(canonical_json({k: v for k, v in record.items() if k != "decided_at"}))
    return record

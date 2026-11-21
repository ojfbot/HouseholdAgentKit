from __future__ import annotations

from pathlib import Path

import pytest

from kit_eval.cases import CaseError, load_cases
from kit_eval.hook import ReferenceHook
from kit_eval.oracles import audit_chain_complete
from kit_eval.report import build_report, run_hello_world
from kit_eval.stats import bootstrap_ci, paired_bootstrap_lower

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "data" / "seeds" / "cases"


@pytest.fixture(scope="module")
def report():
    cases = load_cases(CASES)
    res = run_hello_world(ReferenceHook(), cases, k=5)
    return build_report(res, cases, "bundle-test", "ref", 5, resamples=300), res


def test_hello_world_reference_is_green_at_tier_none(report):
    rep, _ = report
    m = rep["metrics"]
    assert m["pass_k"]["value"] == 1.0
    assert m["tier2_rate"]["value"] == 1.0
    assert m["locks"]["value"] == 0 and m["unverified_numbers"]["value"] == 0
    assert m["hard_constraints_carried"]["value"] == 1.0
    assert rep["latency"]["hello_world_total_s"]["p95"] < 180
    assert rep["synthetic"] is True


def test_every_case_reported_per_case_for_the_paired_gate(report):
    rep, _ = report
    assert set(rep["per_case"]["pass_k"]) == {c["case_id"] for c in load_cases(CASES)}


def test_stale_price_is_caught_and_resolved(report):
    _, res = report
    r = next(r for r in res if r.case_id == "hw-taco-008-price-moves")
    assert r.restarts == 1 and r.accepted and any("STALE" in n for n in r.notes)


def test_holdout_cases_are_refused(tmp_path):
    (tmp_path / "x.yaml").write_text("cases:\n- {case_id: h1, persona: p, goal: g, synthetic: true, split: holdout, accept_if: [{kind: verified}]}\n")
    with pytest.raises(CaseError):
        load_cases(tmp_path)


def test_chain_oracle_detects_tampering(report):
    from kit_eval import reference as ref
    from kit_eval.cases import mandate_from_case
    from mock_gateway import at

    m = mandate_from_case(load_cases(CASES)[0])
    led = ref.MiniLedger()
    for k in ("mandate", "brief", "cart", "decision", "consent", "order"):
        led.append(k, "x", m, at(2026, 11, 24, 14))
    assert audit_chain_complete(led.entries)[0]
    led.entries[3]["amount"] = 1
    assert not audit_chain_complete(led.entries)[0]
    assert not audit_chain_complete(led.entries[:4])[0]


def test_bootstrap_helpers():
    lo, hi = bootstrap_ci([1.0] * 20)
    assert lo == hi == 1.0
    assert paired_bootstrap_lower({"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 1.0})[0] == 0.0
    assert paired_bootstrap_lower({"a": 0.0, "b": 0.0}, {"a": 1.0, "b": 1.0})[0] == -1.0


def test_hello_world_result_v1_shape():
    from kit_eval import hello_world

    r = hello_world.run("smoke", "bundle-test")
    assert r["result_version"] == "hello_world_result@1" and r["oracle_version"] == "hw-taco@1"
    assert r["status"] == "placement_only" and r["dev_set"] == "iq-dev@0"  # honest until hw-taco@1 cases run
    assert set(r["tiers"]) == {"0", "1", "2"} and r["highest_tier"] == 2
    assert all(v == 0 for name, v in r["zero_tolerance"].items() if name != "orders_per_mandate_max")
    assert r["capability_mode"].startswith("CAP-07:H3,CAP-10:estimated")
    assert hello_world.run("blind", "b")["status"] == "not_run"

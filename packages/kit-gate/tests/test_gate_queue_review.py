from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

from kit_eval.cases import load_cases
from kit_eval.hook import ReferenceHook
from kit_eval.report import build_report, run_hello_world
from kit_gate import bundle, digest, merge_queue, review
from kit_gate.gate import GateConfig, run_gate

ROOT = Path(__file__).resolve().parents[3]
CFG = GateConfig.load(ROOT / "bundles" / "gate-config.yaml")
HEAD = "a" * 40


@pytest.fixture(scope="module")
def reports():
    cases = load_cases(ROOT / "data" / "seeds" / "cases")
    rep = build_report(run_hello_world(ReferenceHook(), cases, k=2), cases, "b1", "ref", 2, resamples=200)
    return rep, copy.deepcopy(rep)


# ---------------------------------------------------------------- gate
def test_gate_green_with_waiver_listed(reports):
    cand, base = reports
    rec = run_gate(cand, base, None, CFG, today=date(2026, 11, 24))
    assert rec["verdict"] == "green", rec["reasons"]
    assert [w["metric"] for w in rec["waivers_relied_on"]] == ["parity_floors"]


def test_gate_red_when_waiver_expires(reports):
    cand, base = reports
    rec = run_gate(cand, base, None, CFG, today=date(2026, 11, 28))
    assert rec["verdict"] == "red" and "parity_floors" in rec["reasons"][0]


def test_gate_red_on_any_lock_violation(reports):
    cand, base = reports
    bad = copy.deepcopy(cand)
    bad["metrics"]["locks"]["value"] = 1
    assert run_gate(bad, base, None, CFG, today=date(2026, 11, 24))["verdict"] == "red"


def test_gate_red_on_rate_regression(reports):
    cand, base = reports
    bad = copy.deepcopy(cand)
    for k in bad["per_case"]["pass_k"]:
        bad["per_case"]["pass_k"][k] = 0.0
    rec = run_gate(bad, base, None, CFG, today=date(2026, 11, 24))
    assert rec["verdict"] == "red" and any("pass_k" in r for r in rec["reasons"])


def test_gate_red_on_two_block_experiment(reports):
    cand, base = reports
    rec = run_gate(cand, base, {"one_part_ok": False, "changed_blocks": ["model", "context"]}, CFG, today=date(2026, 11, 24))
    assert rec["verdict"] == "red"


def test_gate_red_on_latency_and_different_case_sets(reports):
    cand, base = reports
    slow = copy.deepcopy(cand)
    slow["latency"]["hello_world_total_s"]["p95"] = 181.0
    assert run_gate(slow, base, None, CFG, today=date(2026, 11, 24))["verdict"] == "red"
    other = copy.deepcopy(base)
    other["case_set_sha"] = "x"
    assert run_gate(cand, other, None, CFG, today=date(2026, 11, 24))["verdict"] == "red"


def test_gate_record_hash_is_stable(reports):
    cand, base = reports
    a = run_gate(cand, base, None, CFG, today=date(2026, 11, 24))
    b = run_gate(cand, base, None, CFG, today=date(2026, 11, 24))
    assert a["record_sha"] == b["record_sha"]


# ---------------------------------------------------------------- bundle
def test_bundle_ids_and_one_part_rule():
    m = bundle.load(ROOT / "bundles" / "examples" / "tier-none.yaml")
    c = bundle.compute(m)
    assert len(c["bundle_id"]) == 64 and c["needs_network"] is False
    exp = copy.deepcopy(m)
    exp["kind"] = "experiment"
    one = copy.deepcopy(exp)
    one["model"]["lanes"]["K01"] = {"provider": "local", "base": {"repo": "Qwen/Qwen3.5-2B", "revision": "abc"}, "gen": {"temperature": 0}}
    assert bundle.diff(exp, one)["one_part_ok"] and bundle.diff(exp, one)["changed_lanes"] == ["K01"]
    two = copy.deepcopy(one)
    two["context"]["catalog"] = "catalog@1"
    assert not bundle.diff(exp, two)["one_part_ok"]
    stored = {**m, "bundle_id": "0" * 64}
    assert bundle.check_drift(stored) == ["bundle_id"]


def test_bundle_validation():
    m = bundle.load(ROOT / "bundles" / "examples" / "tier-none.yaml")
    m["model"]["lanes"]["K01"] = {"provider": "local", "gen": {"temperature": 0.7}}
    errs = bundle.validate(m)
    assert any("revision" in e for e in errs) and any("temperature" in e for e in errs)


# ---------------------------------------------------------------- review + queue
def marker(reviewer: str, verdict: str = "approve", head: str = HEAD, evidence: str = "pytest 120 passed") -> str:
    return f"looks good\n{review.MARKER}\nreviewer: {reviewer}\nverdict: {verdict}\nhead: {head}\nevidence: {evidence}\n"


def pr(n: int, impl: str = "claude-code", body: str = "", labels=(), files=("packages/verifier/src/x.py",), checks="success", reviews=None) -> dict:
    return {
        "number": n,
        "title": f"pr {n}",
        "createdAt": f"2026-11-2{n % 10}T00:00:00Z",
        "isDraft": False,
        "body": body,
        "headRefOid": HEAD,
        "labels": [{"name": f"impl:{impl}"}, *[{"name": x} for x in labels]],
        "files": [{"path": f} for f in files],
        "statusCheckRollup": [{"name": c, "conclusion": checks.upper()} for c in ("ci", "security", "privacy-guard")],
        "reviews": reviews
        if reviews is not None
        else [{"body": marker("codex" if impl == "claude-code" else "claude-code"), "submittedAt": "2026-11-21T01:00:00Z"}],
        "comments": [],
    }


def test_review_status_rules():
    assert review.status(pr(1))[0] == "success"
    assert review.status(pr(1, reviews=[{"body": marker("claude-code")}]))[0] == "pending"  # self-review doesn't count
    assert review.status(pr(1, reviews=[{"body": marker("codex", head="b" * 40)}]))[0] == "pending"  # stale
    assert review.status(pr(1, reviews=[{"body": marker("codex", verdict="request-changes")}]))[0] == "failure"
    assert review.status(pr(1, reviews=[{"body": marker("codex", evidence="")}]))[0] == "failure"
    no_label = pr(1)
    no_label["labels"] = []
    assert review.status(no_label)[0] == "failure"


def test_merge_queue_plan():
    green = {HEAD: {"verdict": "green"}}
    prs = [
        pr(1),
        pr(2, labels=("contract",)),
        pr(3, files=(".github/workflows/ci.yml",)),
        pr(4, checks="failure"),
        pr(5, body="depends-on: #4"),
        pr(6, body="depends-on: #1"),
        pr(7, reviews=[]),
    ]
    d = {x.number: x for x in merge_queue.plan(prs, green)}
    assert d[1].action == "merge"
    assert d[2].action == "owner" and d[3].action == "owner"
    assert d[4].action == "blocked"
    assert d[5].action == "waiting"
    assert d[6].action == "merge"
    assert d[7].action == "waiting"
    assert merge_queue.plan([pr(1)], {})[0].action == "waiting"  # no nightly record yet
    assert merge_queue.plan([pr(1)], {HEAD: {"verdict": "red", "reasons": ["x"]}})[0].action == "blocked"


def test_digest_is_answer_first():
    ds = merge_queue.plan([pr(1), pr(2, labels=("adr",))], {HEAD: {"verdict": "green"}})
    md = digest.render(
        date(2026, 11, 24),
        ds,
        {"verdict": "green", "waivers_relied_on": [{"metric": "parity_floors", "owner": "ED", "until": "2026-11-27"}]},
        [],
        ["Q-I-1 bot identity"],
        ["hw-taco-009-safe-food-out"],
        [("Nov 24", "hello world live")],
    )
    first = md.splitlines()[2]
    assert first.startswith("**Needs you: 2**")
    assert "## Gate green with waivers" in md and "PR #2" in md

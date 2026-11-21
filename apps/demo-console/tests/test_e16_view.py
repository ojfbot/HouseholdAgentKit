"""E16 adapter against Fork G's documented Readout@0 / ControlDelta@0 fields (docs/contracts-proposed.yaml)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server"))

from contracts import ContractError, check_g_delta_event, check_g_readout, check_view  # noqa: E402
from e16_view import delta_view, drill_from_g, view_from_g  # noqa: E402

G_READOUT = {
    "contract": "Readout@0 (draft)", "bank_id": "b_1f2e", "run_id": "run-1", "profile_id": "marketing_crm", "profile_hash": "ph1", "lens": "in_house",
    "scenario": {"adoption_share": {"value": 0.1, "label": "synthetic"}}, "deltas_applied": 1,
    "answer_first": "Under Marketing, the top opportunity is PF-20; 2 of the top 10 are new vs the base profile.",
    "hypothesis": {"text": "h", "hash": "abc", "verdict": "survived"},
    "top_k": [
        {"rank": 1, "family_id": "PF-20", "title": "Win the order the agent is shopping around", "actor_type": "never_shopper", "job": "feed",
         "tier": {"value": 2, "label": "score:rubric@2"}, "priority": {"value": 3.1, "label": "score:priority"}, "score": {"value": 72.0, "label": "score:rubric@2"},
         "value_at_stake_usd": {"value": 936000000, "label": "derived:synthetic"}, "terms": {}, "on_pareto": True, "components": ["K01"], "moved": {"from": 4, "to": 1}},
        {"rank": 2, "family_id": "NF-a1b2c3", "title": "A new family", "actor_type": "shopper", "job": "feed",
         "tier": {"value": 1, "label": "score:rubric@2"}, "priority": {"value": 2.0, "label": "score:priority"}, "score": {"value": 60.0, "label": "score:rubric@2"},
         "value_at_stake_usd": {"value": 4000000, "label": "derived:synthetic"}, "terms": {}, "on_pareto": False, "components": [], "moved": None},
    ],
    "moved_in": ["NF-a1b2c3"], "moved_out": ["PF-03"],
    "two_by_two": {"axes": {"impact": "priority / max", "effort": "days / max"}, "thresholds": {},
                   "points": [{"family_id": "PF-20", "impact": 0.9, "effort": 0.3, "cell": "quick_win"},
                              {"family_id": "PF-99", "impact": 0.2, "effort": 0.8, "cell": "deprioritize"}]},
    "pareto": ["PF-20"],
    "clamp_log": [{"family_id": "PF-28", "term": "w_intent", "asked": 0.6, "applied": 1.0, "code": "FAIRNESS_FLOOR"}],
    "hello_world": "placement_only", "unlabeled_numbers": 0, "readout_hash": "f00dfeedbeef0011", "compute_ms": 1.2,
}
G_EVENT = {"contract": "ControlDelta@0 (draft)", "delta_id": "CD-0123456789ab", "seq": 1, "session": "stage", "at": "2026-12-02T23:40:00.000Z",
           "bank_id": "b_1f2e", "profile_id": "marketing_crm", "base_profile_hash": "p0", "profile_hash": "ph1", "op": "switch", "path": [],
           "requested": "marketing_crm", "prev": "default", "applied": "marketing_crm", "status": "applied", "codes": [], "clamps_in_readout": 1,
           "actor": {"role": "DX"}, "reason": "stage flip", "readout_hash": "f00dfeedbeef0011", "prev_hash": "0" * 64, "hash": "h1"}


def test_g_readout_becomes_a_valid_view_with_display_strings():
    check_g_readout(G_READOUT)
    check_g_delta_event(G_EVENT)
    v = view_from_g(G_READOUT, function_words="Marketing / CRM", delta=G_EVENT)
    check_view(v)
    claims = {c["id"]: c for c in v["claims"]}
    assert claims["vas.PF-20"]["display"] == "$936M/yr" and claims["vas.PF-20"]["label"] == "derived:synthetic"
    assert claims["vas.NF-a1b2c3"]["display"] == "$4M/yr"
    assert [p["rank"] for p in v["portfolio"]] == [1, 2] and v["portfolio"][1]["new"] is True
    pt = next(p for p in v["quad"]["points"] if p["family_id"] == "PF-20")
    assert pt["pos"] == {"x": 0.3, "y": 0.9} and pt["quadrant"] == "quick_win"
    assert next(p for p in v["quad"]["points"] if p["family_id"] == "PF-99")["vas_claim"] is None
    assert claims["clamps.count"]["display"] == "1" and v["delta"]["status"] == "applied"


def test_view_keeps_e12_ranks_untouched():
    shuffled = dict(G_READOUT, top_k=list(reversed(G_READOUT["top_k"])))
    v = view_from_g(shuffled)
    assert [p["rank"] for p in v["portfolio"]] == [2, 1]  # rendered in G's order, never re-sorted


def test_unlabeled_numbers_refused():
    with pytest.raises(ContractError):
        check_g_readout(dict(G_READOUT, unlabeled_numbers=1))
    bad = dict(G_READOUT, top_k=[dict(G_READOUT["top_k"][0], value_at_stake_usd=936000000)])
    with pytest.raises(ContractError):
        check_g_readout(bad)


def test_drill_is_defensive_about_unfrozen_fields():
    d = drill_from_g({"family_id": "PF-28", "title": "Care Profiles", "tier": {"value": 2, "label": "score:rubric@2"}, "components": ["K07", "K08"],
                      "value_at_stake_usd": {"value": 4914000000, "label": "derived:public"}})
    assert d["components"][0]["name"] == "Profile scopes" and d["vas"]["display"] == "$4.9B/yr" and d["demo_beat"] == 3


def test_delta_view_shape():
    dv = delta_view(G_EVENT, {"compute_ms": 1.2})
    assert dv["change"] == {"kind": "switch", "from": "default", "to": "marketing_crm"} and dv["recompute_ms"] == 1.2

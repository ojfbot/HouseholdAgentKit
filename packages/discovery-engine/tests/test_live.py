"""E11/E12 live API: ControlDelta@0 semantics, clamps, lens flip, hash chain, < 1 s recompute, HTTP surface."""
import json
import threading
import time
import urllib.request

import pytest

from discovery_engine.live.engine import Bank, ControlEngine, rank, select
from discovery_engine.live.profiles import standard_set
from discovery_engine.live.server import serve
from discovery_engine.pipeline import RunConfig, run


@pytest.fixture(scope="module")
def bank():
    return run(RunConfig(seed=1))


@pytest.fixture()
def eng(bank):
    profiles, params = standard_set()
    return ControlEngine(Bank(bank), profiles, params)


def test_never_tunable_is_rejected_and_logged(eng):
    for path in (["price"], ["per_person_price"], ["locks"], ["fairness_floor"], ["segment", "price"]):
        ev, ro = eng.apply({"op": "set", "path": path, "value": 2.0, "profile_id": "default"})
        assert ev["status"] == "rejected" and "NEVER_TUNABLE" in ev["codes"]
        assert ro["deltas_applied"] == 0
    assert len(eng.events) == 5 and eng.verify_chain()


def test_bounds_clamp(eng):
    ev, _ = eng.apply({"op": "set", "path": ["segment", "shopper"], "value": 9.0, "profile_id": "default"})
    assert ev["status"] == "clamped" and ev["applied"] == 3.0


def test_fairness_floor_clamps_protected_families(eng):
    ev, ro = eng.apply({"op": "set", "path": ["intent", "care_for_someone"], "value": 0.5, "profile_id": "marketing_crm"})
    floor = [c for c in ro["clamp_log"] if c["code"] == "FAIRNESS_FLOOR"]
    assert floor and all(c["applied"] == 1.0 for c in floor)


def test_function_weight_moves_its_portfolio(eng):
    _, before = eng.apply({"op": "switch", "value": "default"}, "t")
    _, after = eng.apply({"op": "set", "path": ["segment", "store_associate"], "value": 3.0}, "t")
    rank_of = lambda ro: {x["family_id"]: x["rank"] for x in ro["top_k"]}
    sa = [x["family_id"] for x in after["top_k"] if x["actor_type"] == "store_associate"]
    sb = [x["family_id"] for x in before["top_k"] if x["actor_type"] == "store_associate"]
    assert len(sa) >= len(sb) and (min(rank_of(after)[i] for i in sa) <= min([rank_of(before)[i] for i in sb] or [99]))


def test_lens_flip_changes_only_stake_terms(eng):
    p = eng.profiles["default"]
    q = {**p, "lens": "partner"}
    a = [r["family_id"] for r in rank(eng.bank, p, eng.params, neutral_stake=True)]
    b = [r["family_id"] for r in rank(eng.bank, q, eng.params, neutral_stake=True)]
    assert a == b
    ev, ro = eng.apply({"op": "lens", "value": "partner", "profile_id": "default"}, "flip")
    assert ev["status"] == "applied" and ro["lens"] == "partner" and ro["hypothesis"]["text"].startswith("Day-1 hypothesis (partner)")


def test_scenario_rescales_value_at_stake(eng):
    _, a = eng.apply({"op": "switch", "value": "finance"}, "sc")
    _, b = eng.apply({"op": "scenario", "value": 0.2}, "sc")
    va = {x["family_id"]: x["value_at_stake_usd"]["value"] for x in a["top_k"]}
    vb = {x["family_id"]: x["value_at_stake_usd"]["value"] for x in b["top_k"]}
    common = set(va) & set(vb)
    assert common and all(abs(vb[i] - 2 * va[i]) <= 1 for i in common)


def test_readout_numbers_labeled_and_fast(eng):
    worst = 0
    for pid, p in eng.profiles.items():
        t0 = time.perf_counter(); ro = eng.readout(p, pid); worst = max(worst, time.perf_counter() - t0)
        assert ro["unlabeled_numbers"] == 0 and ro["answer_first"]
        assert len({x["actor_type"] for x in ro["top_k"]}) >= 6 or len(ro["top_k"]) < 10
    assert worst < 1.0


def test_deterministic_for_a_profile(eng):
    p = eng.profiles["supply_chain"]
    assert eng.readout(p, "supply_chain")["readout_hash"] == eng.readout(p, "supply_chain")["readout_hash"]


def test_http_api(bank, tmp_path):
    profiles, params = standard_set()
    eng = ControlEngine(Bank(bank), profiles, params, log_path=tmp_path / "deltas.jsonl")
    srv = serve(eng, "127.0.0.1", 0); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    get = lambda p: json.loads(urllib.request.urlopen(base + p).read())
    assert get("/health")["bank_id"] == eng.bank.bank_id
    ro = get("/readout?profile=marketing_crm")
    assert ro["profile_id"] == "marketing_crm" and ro["top_k"]
    req = urllib.request.Request(base + "/delta", data=json.dumps({"op": "lens", "value": "partner", "profile_id": "marketing_crm"}).encode(),
                                 headers={"content-type": "application/json"})
    out = json.loads(urllib.request.urlopen(req).read())
    assert out["event"]["status"] == "applied" and out["readout"]["lens"] == "partner"
    fid = out["readout"]["top_k"][0]["family_id"]
    drill = get(f"/family/{fid}")
    assert drill["decomposition"]["components"] and drill["sizing"]["driver_tree"]
    assert get("/log/verify")["chain_ok"]
    assert (tmp_path / "deltas.jsonl").read_text().count("\n") == 1
    srv.shutdown()

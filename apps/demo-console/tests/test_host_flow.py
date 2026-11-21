"""In-process flow tests for the console host: Poll@1 honoured, rights enforced, every card guarded."""
import pathlib
import sys
import time

import pytest

APP = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "server"))

import host  # noqa: E402
from card_writer import check_card  # noqa: E402
from contracts import ContractError, check_decision, check_poll_closed, check_poll_opened  # noqa: E402


@pytest.fixture()
def con(tmp_path):
    cfg = {**host.DEFAULT_CONFIG, "log_dir": str(tmp_path / "logs"), "public_url": "http://10.0.0.2:8765"}
    cfg["mode"] = dict(host.DEFAULT_CONFIG["mode"])
    c = host.Console(cfg)
    yield c
    for p in (c.hello["poll"], c.care["poll"]):
        if p:
            p._timer.cancel()


def walk_to(con, beat, step_id):
    con.set_beat(beat)
    steps = {1: con.hello_fx["steps"], 2: host.ENGINE_STEPS, 3: con.care_fx["steps"]}[beat]
    while steps[con.steps[beat]]["id"] != step_id:
        con.step(1)


def phone(con):
    m = con.join(None)
    return m["member_hash"], m["ballot_token"], m["role"]


def test_poll_opened_is_poll_at_1_and_every_ballot_is_guarded(con):
    walk_to(con, 1, "vote")
    p = con.hello["poll"]
    check_poll_opened(p.opened)
    assert set(p.opened["ballot_cards"]) == {"partner", "teen", "kid"}
    for role, card in con.hello["ballots"].items():
        check_card(card)
        assert p.opened["ballot_cards"][role] == card["card_id"]
    check_card(con.hello["menu"])


def test_kid_ballot_carries_no_prices_and_picks_come_from_the_list(con):
    walk_to(con, 1, "vote")
    kid = con.hello["ballots"]["kid"]
    assert kid["claims"] == []
    assert {a["option"] for a in kid["actions"] if a["kind"] == "pick_add"} <= {x["item_ref"] for x in con.hello_fx["poll_opened"]["pick_add_list"]}


def test_ballot_token_is_required_and_hashed(con):
    walk_to(con, 1, "vote")
    mh, tok, _ = phone(con)
    with pytest.raises(ContractError):
        con.act(mh, "wrong-token", "vote:c_a")
    con.act(mh, tok, "vote:c_a")
    assert con.hello["poll"].votes[mh] == "c_a"
    assert tok not in (con.tel.path.read_text())  # the token never travels; only its hash does


def test_rights_are_enforced(con):
    walk_to(con, 1, "vote")
    mh, tok, role = phone(con)
    bad = {"kid": "request", "teen": "free_text", "partner": "pick_add:syn-queso-01"}[role]
    with pytest.raises(ContractError):
        con.act(mh, tok, bad, "x")


def test_poll_closed_carries_the_tally_and_auto_plurality_decides(con):
    walk_to(con, 1, "vote")
    con.flip_policy("auto_plurality")
    ms = [phone(con) for _ in range(5)]
    for mh, tok, _ in ms:
        con.act(mh, tok, "vote:c_a")
    con.act(ms[0][0], ms[0][1], "vote:c_c")  # last vote wins
    con.step(1)  # tally: closes the poll
    p = con.hello["poll"]
    check_poll_closed(p.closed)
    assert p.closed["tally"] == {"c_a": 4, "c_b": 0, "c_c": 1} and p.closed["turnout"]["voted"] == 5
    check_decision(host.public(p.decision))
    assert p.decision["cart_id"] == "c_a" and p.decision["next_state"] == "consent_pending"
    check_card(con.card_store[p.decision["explanation_card"]])
    check_card(con.hello["approval"])


def test_owner_decides_waits_then_one_decision_only(con):
    walk_to(con, 1, "vote")
    mh, tok, _ = phone(con)
    con.act(mh, tok, "vote:c_b")
    con.step(1)
    p = con.hello["poll"]
    assert p.state == "awaiting_owner" and p.decision is None
    con.owner_pick("c_c")
    first = p.decision["decision_id"]
    con.owner_pick("c_a")
    con.flip_policy("auto_plurality")
    assert p.decision["decision_id"] == first and p.decision["cart_id"] == "c_c"


def test_tie_waits_for_the_owner_and_records_the_tie_break(con):
    walk_to(con, 1, "vote")
    con.flip_policy("auto_plurality")
    a, b = phone(con), phone(con)
    con.act(a[0], a[1], "vote:c_a")
    con.act(b[0], b[1], "vote:c_b")
    con.step(1)
    p = con.hello["poll"]
    assert p.state == "awaiting_owner"
    con.owner_pick("c_b")
    assert p.decision["tie_break"] == "owner_weights"


def test_no_votes_runs_the_owners_default(con):
    walk_to(con, 1, "vote")
    con.hello["poll"].close()
    assert con.hello["poll"].decision["cart_id"] == con.hello_fx["no_quorum_default_cart_id"]


def test_poll_closes_on_time_off_the_sim_clock(con):
    con.hello_fx["clock"]["rate"] = 3000  # 15 sim minutes in 0.3 s
    walk_to(con, 1, "vote")
    time.sleep(0.6)
    assert con.hello["poll"].closed is not None


def test_tortilla_card_and_consent(con):
    walk_to(con, 1, "vote")
    mh, tok, _ = phone(con)
    con.act(mh, tok, "vote:c_a")
    walk_to(con, 1, "order")
    check_card(con.hello["tortilla"])
    texts = " ".join(l["text"] for s in con.hello["tortilla"]["sections"] for l in s["lines"])
    assert "Nov 30" in texts and "won't swap" in texts
    assert con.hello["consent"]["steps"][-1]["status"] == "done"


def test_engine_flip_is_a_g_shaped_control_delta_and_never_tunable_is_refused(con):
    walk_to(con, 2, "map")
    d = con.engine_flip({"op": "switch", "path": [], "value": "marketing_crm"})
    assert d["status"] == "applied" and d["delta_id"].startswith("CD-") and d["roundtrip_ms"] < 1000
    assert con.eng["view"]["profile"]["profile_id"] == "marketing_crm"
    with pytest.raises(ContractError):
        con.engine_flip({"op": "set", "path": ["fairness_floor"], "value": 0.2})
    con.engine_flip({"op": "lens", "path": [], "value": "partner"})
    con.engine_flip({"op": "lens", "path": [], "value": "in_house"})
    assert con.eng["view"]["profile"]["profile_id"] == "marketing_crm"
    con.drill("PF-28")
    assert con.eng["drill_view"]["components"][0]["id"] == "K01"


def test_care_flow_quotes_ruths_words_and_opens_the_room_is_jen(con):
    walk_to(con, 3, "today")
    con.care_request("I'm out of my coffee and the soft bread, and get some sour cream", "typed")
    walk_to(con, 3, "care")
    check_card(con.care["cards"]["ruth"])
    walk_to(con, 3, "heater")
    con.care_request("And a little space heater, the bedroom gets cold", "stt")
    jen = con.care["cards"]["jen"]
    check_card(jen)
    words = next(c for c in jen["claims"] if c["id"] == "words")
    assert words["value"].startswith("And a little space heater") and words["verified_by"].startswith("stt:")
    assert con.care["result"]["refusal"]["code"] == "OVER_CAP"
    mh, tok, _ = phone(con)
    con.act(mh, tok, "approve")
    con.step(1)
    assert con.care["poll"].decision["cart_id"] == "approve"


def test_request_is_channel_voice_whatever_the_input_mode(con):
    walk_to(con, 3, "today")
    for mode in ("stt", "typed", "clip"):
        con.care_request("my coffee and the soft bread", mode)
        assert con.care["request"]["channel"] == "voice" and con.care["request"]["_input_mode"] == mode


def test_phone_sees_only_its_role_card(con):
    walk_to(con, 1, "vote")
    mh, _, role = phone(con)
    v = con.phone_view(mh)
    assert v["card"]["audience"]["role"] == role and v["clock"]["rate"] == 20

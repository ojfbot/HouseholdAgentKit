import re

import push_loop as pl
from sparky_sim import SimSparky, PERSONAS
from taco_twin import world
from test_semantic_render import HW, NEVER

STORE = "Round Rock Supercenter"


def go(persona, **kw):
    sim = SimSparky(persona, latency=kw.pop("latency", 12.0))
    r = pl.run(HW, sim, world(PERSONAS[persona].get("out_of_stock", ())), store_label=STORE, **kw)
    return r, sim


def sent(r):
    return [t.sent for t in r.turns[1:]]


def test_good_first_answer_gets_no_push():
    r, _ = go("clean")
    assert r.status == "GOOD" and len(r.turns) == 1


def test_correct_is_not_enough_loop_runs_to_good():
    r, _ = go("eager")
    assert not r.first["good"] and r.status == "GOOD" and len(r.turns) <= 3
    assert r.final["correct"] and r.final["accurate"] and r.final["good"]


def test_most_serious_first_and_at_most_three_asks():
    r, _ = go("eager")
    first_push = sent(r)[0]
    asks = [ln for ln in first_push.splitlines() if ln.startswith("- ")]
    assert len(asks) <= pl.MAX_ASKS
    assert "sponsored" in asks[0] and "our usual tortilla" in asks[1]       # correct-level before the rest
    assert "tomato" not in first_push                                        # the soft preference waits its turn


def test_stubborn_reader_climbs_the_ladder():
    r, _ = go("stubborn")
    kinds = [t.kind for t in r.turns]
    assert r.status == "GOOD" and "isolate" in kinds
    pushes = sent(r)
    assert any("Pick one:" in p for p in pushes) and any("yes or no" in p for p in pushes)
    assert any(p.startswith("Options 2 and 3 are right") and "You confirmed" in p for p in pushes)


def test_a_regression_never_costs_us():
    r, sim = go("regressor")
    assert r.status == "GOOD" and r.turns[1].regressed == [1]
    assert r.options[1].turn == 1 and r.options[2].turn == 2                 # best version of each option kept
    cheddar = [l.item_id for l in r.options[1].lines if l.item_id.startswith("C")]
    assert cheddar == ["C1"]


def test_recipe_is_turned_into_products():
    r, _ = go("recipe")
    assert r.first["codes"][0] == "C_RECIPE" and "not a recipe" in sent(r)[0] and r.status == "GOOD"


def test_questions_are_answered_without_disclosure():
    r, _ = go("asker")
    p = sent(r)[0]
    assert pl.PRIVACY_REPLY in p and "For tortillas, use our usual tortilla" in p and r.status == "GOOD"


def test_honest_out_of_stock_is_a_good_answer_not_a_swap():
    r, _ = go("oos")
    assert r.status == "INFEASIBLE" and r.known_oos == ["T1"]
    assert not any(l.item_id == "T3" for o in r.options if o.turn == len(r.turns) for l in o.lines)


def test_never_good_falls_back_after_budget_with_one_reset():
    r, _ = go("never")
    kinds = [t.kind for t in r.turns]
    assert r.status == "FALLBACK" and len(r.turns) == 6 and kinds.count("reset") == 1


def test_good_gap_ends_acceptable_and_says_what_is_missing():
    r, _ = go("goodgap")
    assert r.status == "ACCEPTABLE" and ("G_VECTOR", 1) in r.open


def test_time_budget_stops_the_loop_with_best_so_far():
    r, _ = go("eager", latency=100.0, time_budget_s=150.0)
    assert len(r.turns) == 2 and r.status == "ACCEPTABLE" and r.elapsed == 200.0


def test_every_message_passes_the_disclosure_guard_and_stays_short():
    for p in PERSONAS:
        r, _ = go(p)
        for t in r.turns:
            low = t.sent.lower()
            for w in NEVER:
                assert not re.search(r"\b" + re.escape(w), low), (p, w)
            if t.kind in ("push", "isolate"):
                assert len(t.sent.split()) <= 200, (p, len(t.sent.split()))


def test_hard_rules_restated_in_every_push():
    r, _ = go("eager")
    for p in sent(r):
        assert "our usual tortilla not substituted" in p and "$25.00 or less" in p


def test_reset_carries_what_we_learned():
    r, _ = go("never")
    reset = next(t.sent for t in r.turns if t.kind == "reset")
    assert reset.startswith("I'm an assistant shopping") and "What we already know:" in reset and "Lager" in reset


def test_deterministic():
    a, _ = go("stubborn")
    b, _ = go("stubborn")
    assert [t.sent for t in a.turns] == [t.sent for t in b.turns]


def test_parser_keeps_commas_in_names_and_reads_marks():
    ans = pl.parse("Option 1: repeats what you usually buy\n- Churro bites, 12 oz (sponsored), 1, $3.48, in stock\n"
                   "Total: $3.55\nOpen pickup times: 4:30 PM", HW, world())
    l = ans.options[0].lines[0]
    assert l.name == "Churro bites, 12 oz" and l.sponsored and l.item_id == "D1" and ans.slots == ["4:30 PM"]


def test_telemetry_stamps_component_and_turn():
    r, _ = go("eager")
    tel = [t.telemetry() for t in r.turns]
    assert all(x["component_id"] == "K24.push_loop" for x in tel) and [x["loop_turn"] for x in tel] == [1, 2, 3]

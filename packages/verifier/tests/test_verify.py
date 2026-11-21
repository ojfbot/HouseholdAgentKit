from __future__ import annotations

import copy

import pytest

from kit_contracts import Cart, Constraint, Lock, Refusal
from kit_eval import reference as ref
from kit_eval.cases import mandate_from_case
from kit_verifier import verify_brief, verify_cart
from kit_verifier.mutations import Ctx, recompute
from mock_gateway import at, make_twin

T0 = at(2026, 11, 24, 14, 0)
CASE = {
    "case_id": "unit",
    "mandate": {
        "occasion": "taco",
        "headcount": {"adults": 2, "kids": [8, 11]},
        "deadline": {"type": "pickup_ready_by", "time": "2026-11-24T18:00:00-06:00", "store": "STORE-A"},
        "budget": {"max_cents": 2500},
    },
}


@pytest.fixture
def world():
    t = make_twin(T0)
    m = mandate_from_case(CASE)
    c = ref.greedy_cart(m, t, "STORE-A", T0)
    assert isinstance(c, Cart)
    return t, m, c


def test_clean_cart_passes_every_hard_check(world):
    t, m, c = world
    rep = verify_cart(c, m, t.catalog, T0)
    assert rep.all_hard_pass, rep.failed()
    ids = {x.constraint_id for x in rep.checks}
    assert {"lines_hash", "subtotal", "tax", "fees", "total", "budget", "slot.deadline", "slot.cutoff"} <= ids


def test_unknown_attributes_never_satisfy_an_exclude(world):
    t, m, c = world
    m.exclude = ["peanut"]
    bad = copy.deepcopy(c)
    bad.lines.append(ref.CartLine("TW-0024", 1, t.catalog.offer("TW-0024", "STORE-A", T0).price_cents, "seasoning"))
    bad = recompute(bad, Ctx(m, t.catalog, T0, "STORE-A", {}))
    assert "exclude:TW-0024" in verify_cart(bad, m, t.catalog, T0).failed()


def test_safe_equivalent_admitted_only_without_exact_upc(world):
    t, m, c = world
    corn = t.catalog.offer("TW-0001", "STORE-A", T0)
    m.locks = [Lock("upc:" + corn.upc, level=2, exact_upc=False)]
    # flour tortillas add wheat: not a safe equivalent of corn
    assert any(f.startswith("lock:") for f in verify_cart(c, m, t.catalog, T0).failed()) == any(ln.sku == "TW-0002" for ln in c.lines)


def test_unresolvable_lock_reference_fails(world):
    t, m, c = world
    m.locks = [Lock("upc:999999999999", level=4)]
    assert "lock:upc:999999999999" in verify_cart(c, m, t.catalog, T0).failed()


def test_soft_budget_never_blocks(world):
    t, m, c = world
    m.budget.max_cents = 100
    m.budget.hard = False
    assert verify_cart(c, m, t.catalog, T0).all_hard_pass


def test_cap_constraint(world):
    t, m, c = world
    m.constraints.append(Constraint("cap1", "cap", c.total_cents - 1))
    assert "cap:cap1" in verify_cart(c, m, t.catalog, T0).failed()


def test_brief_text_mode_carries_constraints_and_no_reasons():
    m = mandate_from_case({**CASE, "mandate": {**CASE["mandate"], "exclude": ["milk"]}})
    text = ref.render_brief_h1(m)
    assert verify_brief(text, m).all_hard_pass
    assert not verify_brief(text + " (because of an allergy)", m).all_hard_pass
    assert not verify_brief(text + " " + m.principal.member_hash, m).all_hard_pass


def test_infeasible_budget_carries_numbers():
    t = make_twin(T0)
    m = mandate_from_case({**CASE, "mandate": {**CASE["mandate"], "budget": {"max_cents": 500}}})
    r = ref.greedy_cart(m, t, "STORE-A", T0)
    assert isinstance(r, Refusal) and r.evidence[0]["budget_cents"] == 500 and r.evidence[0]["min_total_cents"] > 500

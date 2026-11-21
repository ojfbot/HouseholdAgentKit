"""CAP-02 Agent Profiles (CT-02a..c), CAP-21 care profile (CT-21a..c), CAP-28 org principal (CT-28a).

Status: CAP-02 announced, not live (E, Nov 19 4:30 AM); CAP-21 and CAP-28 proposed. ADR-004:
our side (K07) is authoritative whatever Walmart supports, so a looser Walmart cap never
loosens ours. Story fixtures: Ruth (requester, care profile) and Jen (approver/payer).
"""

from __future__ import annotations

import copy
import functools
import operator
from datetime import timedelta

import pytest

from contract.conftest import T0
from contract.reference_impl import FakeWalmartCore, Profile
from kit_contracts import Cart, MemberRef, Refusal, RefusalCode
from kit_eval import reference as ref
from kit_eval.oracles import audit_chain_complete
from kit_verifier import verify_cart
from mock_gateway import make_twin

pytestmark = pytest.mark.contract


def ruth(**kw) -> Profile:
    base = dict(
        profile_id="prof-ruth",
        account_id="acct-jen",
        agent_id="agent-1",
        served_person_id="sp-ruth",
        cap_per_order_cents=4000,
        cap_per_month_cents=12000,
        ship_to="addr-ruth-tampa",
        blocked_categories=("gift_card", "prepaid_card"),
        usuals=("TW-0001", "TW-0014"),
    )
    base.update(kw)
    return Profile(**base)


def jen() -> Profile:
    return Profile("prof-jen", "acct-jen", "agent-1", "sp-jen", 15000, 60000, "addr-jen-columbus", usuals=("TW-0011", "TW-0020"))


@pytest.fixture
def cart(hw_mandate, twin):
    c = ref.greedy_cart(hw_mandate, twin, "STORE-A", T0)
    assert isinstance(c, Cart)
    return c


# ------------------------------------------------------------------ CT-02a
@pytest.mark.cap02
@pytest.mark.parametrize("walmart_cap", [None, 10_000, 1_000])
def test_ct02a_cap_enforced_on_both_sides_ours_first(impl, cart, walmart_cap):
    core = FakeWalmartCore(cap_per_order_cents=walmart_cap)
    tight = ruth(cap_per_order_cents=cart.total_cents - 1)
    r = impl.place_order(tight, cart, tight.ship_to, core)
    assert isinstance(r, Refusal) and r.code == RefusalCode.OVER_CAP
    assert core.calls == [], "our cap refuses before any Walmart call"
    ok = ruth()
    r2 = impl.place_order(ok, cart, ok.ship_to, core)
    if walmart_cap is not None and cart.total_cents > walmart_cap:
        assert isinstance(r2, Refusal) and r2.code == RefusalCode.OVER_CAP  # Walmart's applies in addition
    else:
        assert r2.ok


@pytest.mark.cap02
def test_ct02a_monthly_cap(impl, cart):
    core = FakeWalmartCore()
    p = ruth(cap_per_month_cents=cart.total_cents + 100)
    assert impl.place_order(p, cart, p.ship_to, core, month_to_date_cents=0).ok
    r = impl.place_order(p, cart, p.ship_to, core, month_to_date_cents=cart.total_cents)
    assert isinstance(r, Refusal) and r.code == RefusalCode.OVER_CAP


@pytest.mark.cap02
@pytest.mark.loose_contract
@pytest.mark.parametrize(
    "standing",
    [
        {"schedule": "weekly", "cap_per_order": 2000, "cap_per_month": 6000, "autonomy": "within_cap", "expires": "2026-12-31"},
        {
            "spend_limits": {"per_transaction": {"amount_cents": 2000}, "per_month": 6000},
            "frequency": "weekly",
            "category_restrictions": ["gift_card"],
            "autonomy": "within_cap",
            "expires": "2026-12-31",
        },
    ],
)
def test_ct02a_standing_guard_reads_either_draft_shape(impl, hw_mandate, cart, standing):
    m = copy.deepcopy(hw_mandate)
    m.standing = standing
    within = impl.standing_guard(m, cart, month_to_date_cents=0)
    assert within.ok if cart.total_cents <= 2000 else within.code == RefusalCode.OVER_CAP
    over = impl.standing_guard(m, cart, month_to_date_cents=5_900)
    assert isinstance(over, Refusal) and over.code == RefusalCode.OVER_CAP
    m.standing = None
    assert impl.standing_guard(m, cart, 0).code == RefusalCode.OUT_OF_MANDATE


# ------------------------------------------------------------------ CT-02b
@pytest.mark.cap02
def test_ct02b_revoke_stops_the_next_action_within_one_call(impl, cart):
    core = FakeWalmartCore()
    p = ruth()
    assert impl.place_order(p, cart, p.ship_to, core).ok
    impl.revoke(p)
    n = len(core.calls)
    r = impl.place_order(p, cart, p.ship_to, core)
    assert isinstance(r, Refusal) and r.code == RefusalCode.RIGHTS_DENIED
    assert len(core.calls) == n


# ------------------------------------------------------------------ CT-02c
@pytest.mark.cap02
def test_ct02c_agent_history_separate_from_shoppers(impl, cart):
    core = FakeWalmartCore()
    p = ruth()
    oid = impl.place_order(p, cart, p.ship_to, core).value
    core.shopper_checkout("ord-shopper-own")
    assert oid in core.agent_history["prof-ruth"] and oid not in core.shopper_history
    assert "ord-shopper-own" not in functools.reduce(operator.iadd, core.agent_history.values(), [])


# ------------------------------------------------------------------ CT-21a
@pytest.mark.cap21
@pytest.mark.parametrize("scope", ["account", "profile"])
def test_ct21a_profile_leakage_is_zero(impl, scope):
    t = make_twin(T0, usuals_scope=scope)
    r_, j_ = ruth(), jen()
    t.catalog.profile_usuals = {r_.profile_id: list(r_.usuals), j_.profile_id: list(j_.usuals)}
    raw = t.catalog.discover(__import__("mock_gateway").DiscoverQuery("STORE-A", account_id="acct-jen", profile_id="prof-ruth", usuals=True), T0).value
    leak_raw = {o.sku for o in raw.usuals} - set(r_.usuals)
    if scope == "account":
        assert leak_raw, "announced behaviour leaks across profiles: the baseline row must show it"
    ours = {o.sku for o in impl.usuals_for(r_, t, "STORE-A", T0)}
    assert ours <= set(r_.usuals) and not (ours & set(j_.usuals))


# ------------------------------------------------------------------ CT-21b
@pytest.mark.cap21
def test_ct21b_non_pinned_ship_to_refused(impl, cart):
    core = FakeWalmartCore()
    p = ruth()
    r = impl.place_order(p, cart, "addr-jen-columbus", core)
    assert isinstance(r, Refusal) and r.code == RefusalCode.ADDRESS_MISMATCH and core.calls == []
    assert impl.place_order(p, cart, p.ship_to, core).ok


@pytest.mark.cap21
def test_ct21b_verifier_refuses_unknown_or_wrong_ship_to(hw_mandate, cart, twin):
    from kit_contracts import Constraint

    m = copy.deepcopy(hw_mandate)
    m.constraints.append(Constraint("pin", "ship_to", "addr-ruth-tampa"))
    c = copy.deepcopy(cart)
    assert not verify_cart(c, m, twin.catalog, T0).all_hard_pass, "no ship_to on the cart is not a pass"
    c.ship_to = "addr-elsewhere"
    assert not verify_cart(c, m, twin.catalog, T0).all_hard_pass
    c.ship_to = "addr-ruth-tampa"
    assert verify_cart(c, m, twin.catalog, T0).all_hard_pass


# ------------------------------------------------------------------ CT-21c
@pytest.mark.cap21
def test_ct21c_requested_by_survives_every_hop(hw_mandate, cart):
    m = copy.deepcopy(hw_mandate)
    m.principal = MemberRef("mh_jen", "approver_payer")
    m.requested_by = MemberRef("mh_ruth", "requester")
    m.profile_id = "prof-ruth"
    led = ref.MiniLedger()
    for i, kind in enumerate(("mandate", "brief", "cart", "decision", "consent", "order")):
        led.append(kind, cart.cart_id, m, T0 + timedelta(minutes=i))
    ok, why = audit_chain_complete(led.entries)
    assert ok, why
    assert all(e["requested_by"] == "requester" and e["actor"] == "approver_payer" and e["profile_id"] == "prof-ruth" for e in led.entries)
    led.entries[2]["requested_by"] = "approver_payer"  # tamper
    assert not audit_chain_complete(led.entries)[0]


# ------------------------------------------------------------------ CT-28a
@pytest.mark.cap28
@pytest.mark.parametrize(
    "votes,timed_out,expected",
    [
        ({"a1": "approve", "a2": "approve"}, False, "approved"),
        ({"a1": "approve"}, False, "pending"),
        ({"a1": "approve"}, True, "held"),
        ({}, True, "held"),
        ({"a1": "approve", "a2": "reject"}, False, "rejected"),
    ],
)
def test_ct28a_two_approvers_no_quorum_holds_never_owner_default(impl, votes, timed_out, expected):
    d = impl.decide_two_approvers(["a1", "a2"], votes, timed_out, owner="a1")
    assert d == expected
    assert d != "owner_default"

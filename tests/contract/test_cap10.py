"""CAP-10 pickup and delivery slots — CT-10a..d. CAP-43 slot hold — CT-43a.

Status (org@2): consumer slots published; agent exposure inferred; holds proposed (CAP-43).
Each test runs in every twin slots mode it applies to, so the suite answers "what breaks"
for whichever branch Walmart turns out to expose.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from contract.conftest import T0
from kit_contracts import Card, CardClaim, CardLine, CardSection, Cart, Refusal, RefusalCode, SlotPlan
from kit_eval import reference as ref
from kit_verifier import CardTruth, verify_card, verify_cart
from mock_gateway import TZ, make_twin

pytestmark = [pytest.mark.contract, pytest.mark.cap10]


# ------------------------------------------------------------------ CT-10a
@pytest.mark.parametrize("kind", ["pickup", "delivery"])
def test_ct10a_slots_shape_and_time_zone(kind):
    t = make_twin(T0, slots_mode="read_only")
    r = t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0, kind=kind)
    assert r.ok and r.value.slots
    for s in r.value.slots:
        assert s.kind == kind and s.store == "STORE-A"
        for dt in (s.start, s.end, s.ready_by, s.cutoff):
            assert dt.tzinfo is not None and dt.utcoffset() == T0.astimezone(TZ).utcoffset()
        assert s.cutoff < s.start < s.end and s.capacity >= 0 and s.fee_cents >= 0
        assert s.tz == "America/Chicago"
    assert set(r.value.labels) == {"slots.read", "slots.cutoff_semantics"}


def test_ct10a_naive_window_is_rejected():
    t = make_twin(T0)
    with pytest.raises(ValueError):
        t.slots.slots("STORE-A", T0.replace(tzinfo=None), T0.replace(tzinfo=None) + timedelta(hours=2), T0)


# ------------------------------------------------------------------ CT-10b
def test_ct10b_cutoff_semantics_pickup_ready_at_start_delivery_by_end():
    t = make_twin(T0)
    for s in t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0).value.slots:
        if s.kind == "pickup":
            assert s.ready_by == s.start
        else:
            assert s.ready_by == s.end


@pytest.mark.parametrize("mode", ["read_only", "not_exposed"])
def test_ct10b_by_six_resolves_to_pickup_ready_by(impl, hw_mandate, mode):
    t = make_twin(T0, slots_mode=mode)
    plan = impl.plan_slot(hw_mandate, t, "STORE-A", T0)
    assert isinstance(plan, SlotPlan)
    assert plan.kind == "pickup" and plan.ready_by <= hw_mandate.deadline.time
    assert plan.status in ("estimated", "confirmed")
    assert plan.source == ("slots_api" if mode == "read_only" else "heuristic")
    if mode == "read_only":
        assert plan.cutoff > T0, "a plan never rests on a slot whose cutoff has passed"


def test_ct10b_late_request_is_infeasible_not_a_later_slot(impl, cases):
    from kit_eval.cases import mandate_from_case

    c = cases["hw-taco-006-too-late"]
    from datetime import datetime

    now = datetime.fromisoformat(c["clock_start"])
    t = make_twin(now)
    plan = impl.plan_slot(mandate_from_case(c), t, "STORE-A", now)
    assert plan.status == "infeasible"


# ------------------------------------------------------------------ CT-10c
def test_ct10c_slot_gone_at_checkout_is_stale_and_resolves(impl, hw_mandate):
    t = make_twin(T0, slots_mode="read_only")
    cart = impl.solve(hw_mandate, t, "STORE-A", T0)
    assert isinstance(cart, Cart) and cart.slot and cart.slot.slot_id
    t.slots.inject_vanish(cart.slot.slot_id, T0 + timedelta(minutes=1))
    later = T0 + timedelta(minutes=5)
    r = t.slots.consume(cart.slot.slot_id, later)
    assert isinstance(r, Refusal) and r.code == RefusalCode.STALE and r.retryable
    again = impl.solve(hw_mandate, t, "STORE-A", later)
    assert isinstance(again, Cart) and again.slot is not None
    assert again.slot.slot_id != cart.slot.slot_id
    assert again.slot.ready_by <= hw_mandate.deadline.time, "never a silent later slot"


def test_ct10c_consume_after_cutoff_is_stale():
    t = make_twin(T0)
    s = next(x for x in t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0).value.slots if x.capacity > 0 and x.cutoff > T0)
    assert t.slots.consume(s.slot_id, s.cutoff).ok is False


# ------------------------------------------------------------------ CT-10d
def _card(text: str, value: str, ref_: str) -> Card:
    return Card(
        "c1",
        __import__("kit_contracts").MemberRef("mh_x", "owner"),
        "approval",
        [CardSection("t", [CardLine(text, "slot.ready_by")])],
        [CardClaim("slot.ready_by", value, ref_)],
    )


@pytest.mark.parametrize(
    "text,ok",
    [
        ("Pickup ready about 5:00 PM (confirmed at checkout)", True),
        ("Pickup ready 5:00 PM", False),
        ("Pickup confirmed for 5:00 PM", False),
        ("Your 5:00 PM pickup is reserved", False),
        ("Estimated pickup 5:00 PM", True),
    ],
)
def test_ct10d_no_confirmed_time_unless_confirmed(text, ok):
    slot = SlotPlan("STORE-A", T0, "estimated", "slots_api", T0, slot_id="x")
    rep = verify_card(_card(text, "5:00 PM", "vr"), CardTruth({"slot.ready_by": "5:00 PM"}, "vr", slot))
    assert rep.all_hard_pass is ok, rep.failed()


def test_ct10d_confirmed_needs_a_slots_api_confirmation(impl, hw_mandate):
    t = make_twin(T0)
    cart = impl.solve(hw_mandate, t, "STORE-A", T0)
    assert isinstance(cart, Cart) and cart.slot
    cart.slot.status = "confirmed"
    assert not verify_cart(cart, hw_mandate, t.catalog, T0).all_hard_pass
    assert verify_cart(cart, hw_mandate, t.catalog, T0, slot_confirmer=lambda sid: sid == cart.slot.slot_id).all_hard_pass


# ------------------------------------------------------------------ CT-43a
@pytest.mark.cap43
def test_ct43a_hold_released_when_poll_lapses_and_never_a_promise(hw_mandate):
    t = make_twin(T0, slots_mode="holds")
    s = next(x for x in t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0).value.slots if x.capacity == 1 and x.cutoff > T0 + timedelta(minutes=30))
    poll_closes = T0 + timedelta(minutes=15)
    h = t.slots.hold(s.slot_id, hw_mandate.mandate_id, poll_closes, T0)
    assert h.ok and h.value.is_promise is False
    assert t.slots.slots("STORE-A", s.start, s.end, T0 + timedelta(minutes=1)).value.slots[0].capacity == 0
    assert t.slots.tick(poll_closes) == [h.value.hold_id]
    after = next(x for x in t.slots.slots("STORE-A", s.start, s.end, poll_closes).value.slots if x.slot_id == s.slot_id)
    assert after.capacity == 1, "lapsed hold gives capacity back"
    assert not t.slots.live_hold(h.value.hold_id, poll_closes)


@pytest.mark.cap43
@pytest.mark.parametrize("mode", ["read_only", "not_exposed"])
def test_ct43a_without_holds_no_hold_is_claimed(mode, hw_mandate):
    t = make_twin(T0, slots_mode=mode)
    r = t.slots.hold("STORE-A:2026-11-24:P16", hw_mandate.mandate_id, T0 + timedelta(minutes=10), T0)
    assert isinstance(r, Refusal) and r.code == RefusalCode.CAPABILITY_UNAVAILABLE


@pytest.mark.cap43
def test_ct43a_one_live_hold_per_mandate(hw_mandate):
    t = make_twin(T0, slots_mode="holds")
    open_ = [x for x in t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0).value.slots if x.capacity > 0 and x.cutoff > T0 + timedelta(minutes=30)]
    h1 = t.slots.hold(open_[0].slot_id, hw_mandate.mandate_id, T0 + timedelta(minutes=20), T0)
    h2 = t.slots.hold(open_[1].slot_id, hw_mandate.mandate_id, T0 + timedelta(minutes=20), T0)
    assert h1.ok and h2.ok
    assert not t.slots.live_hold(h1.value.hold_id, T0) and t.slots.live_hold(h2.value.hold_id, T0)


def test_reference_pipeline_never_marks_read_only_as_confirmed(impl, hw_mandate):
    t = make_twin(T0, slots_mode="read_only")
    cart = impl.solve(hw_mandate, t, "STORE-A", T0)
    assert isinstance(cart, Cart) and cart.slot and cart.slot.status == "estimated"
    _ = ref  # reference module is the default binding

from __future__ import annotations

from datetime import timedelta

import pytest

from kit_contracts import Refusal, RefusalCode
from mock_gateway import BEHAVIOURS, LABELS, DiscoverQuery, TwinEvent, at, labels_for, make_twin, seeded_violations

T0 = at(2026, 11, 24, 14, 0)


def test_every_behaviour_has_a_known_label():
    assert all(b["label"] in LABELS and b["cap"] for b in BEHAVIOURS.values())
    with pytest.raises(KeyError):
        labels_for("catalog.not_a_behaviour")


def test_catalog_is_seeded_and_synthetic_upcs_use_restricted_prefix():
    a, b, c = make_twin(T0, seed=1), make_twin(T0, seed=1), make_twin(T0, seed=2)
    assert a.catalog.state_digest("STORE-A", T0) == b.catalog.state_digest("STORE-A", T0) != c.catalog.state_digest("STORE-A", T0)
    assert all(r.upc.startswith("2") and len(r.upc) == 12 for r in a.catalog.rows)


def test_every_hello_world_role_has_an_always_stocked_item():
    t = make_twin(T0, seed=99)
    for role in ("tortillas", "protein", "cheese", "salsa", "lettuce"):
        offers = t.catalog.discover(DiscoverQuery("STORE-A", roles=(role,)), T0).value.offers_by_role[role]
        assert any(o.stock == "in" for o in offers), role


def test_events_apply_from_their_time_only():
    t = make_twin(T0)
    t.catalog.inject(TwinEvent(T0 + timedelta(minutes=10), "price_change", "TW-0005", price_cents=999))
    t.catalog.inject(TwinEvent(T0 + timedelta(minutes=10), "packaging_change", "TW-0010", packaging_version="p2", add_allergens=("sesame",)))
    assert t.catalog.offer("TW-0005", "STORE-A", T0).price_cents != 999
    assert t.catalog.offer("TW-0005", "STORE-A", T0 + timedelta(minutes=10)).price_cents == 999
    o = t.catalog.offer("TW-0010", "STORE-A", T0 + timedelta(minutes=11))
    assert o.attrs.packaging_version == "p2" and "sesame" in o.attrs.allergens


def test_store_scoped_stock_out():
    t = make_twin(T0)
    t.catalog.inject(TwinEvent(T0, "stock_out", "TW-0001", store="STORE-A"))
    assert t.catalog.offer("TW-0001", "STORE-A", T0).stock == "out"
    assert t.catalog.offer("TW-0001", "STORE-B", T0).stock == "in"


def test_usuals_scope_account_vs_profile():
    for scope in ("account", "profile"):
        t = make_twin(T0, usuals_scope=scope)
        t.catalog.profile_usuals = {"prof-ruth": ["TW-0001"], "prof-jen": ["TW-0011"]}
        r = t.catalog.discover(DiscoverQuery("STORE-A", profile_id="prof-ruth", usuals=True), T0).value
        skus = {o.sku for o in r.usuals}
        assert r.scope_answered == scope
        assert skus == ({"TW-0001", "TW-0011"} if scope == "account" else {"TW-0001"})


def test_seeded_violation_schedule_is_reproducible():
    t = make_twin(T0)
    assert seeded_violations(t.catalog, 5, T0) == seeded_violations(t.catalog, 5, T0)
    assert seeded_violations(t.catalog, 5, T0) != seeded_violations(t.catalog, 6, T0)


def test_slot_modes():
    for mode, ok in (("read_only", True), ("holds", True), ("not_exposed", False)):
        r = make_twin(T0, slots_mode=mode).slots.slots("STORE-A", T0, T0 + timedelta(hours=4), T0)
        assert r.ok is ok
        if not ok:
            assert r.code == RefusalCode.CAPABILITY_UNAVAILABLE


def test_capacity_is_consumed_and_full_slot_is_stale():
    t = make_twin(T0)
    s = next(x for x in t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0).value.slots if x.capacity == 1 and x.cutoff > T0)
    assert t.slots.consume(s.slot_id, T0).ok
    r = t.slots.consume(s.slot_id, T0)
    assert isinstance(r, Refusal) and r.code == RefusalCode.STALE


def test_hold_cannot_outlive_cutoff_and_hold_is_used_at_checkout():
    t = make_twin(T0, slots_mode="holds")
    s = next(x for x in t.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0).value.slots if x.capacity == 1 and x.cutoff > T0 + timedelta(minutes=5))
    h = t.slots.hold(s.slot_id, "md-1", s.cutoff + timedelta(hours=1), T0).value
    assert h.until == s.cutoff
    assert t.slots.consume(s.slot_id, T0 + timedelta(minutes=1), hold_id=h.hold_id).ok
    assert not t.slots.live_hold(h.hold_id, T0 + timedelta(minutes=1))


def test_config_stamp_names_modes():
    t = make_twin(T0, slots_mode="holds", usuals_scope="profile")
    assert t.config_stamp() == {"capability_mode": "H3", "slots_mode": "holds", "usuals_scope": "profile", "twin_seed": "0"}

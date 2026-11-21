"""K20 conformance suite: protocol conformance of the twin + tier-0 parity on the fixed request set.

One registry of checks; pytest wraps them (tests/conformance) and `kit conformance` prints n/N.
Checks marked `core` need HP's half of the twin (consent gate, caps, tokens, mock Sparky) and
report `skipped` until a core implementation is registered via KIT_CORE_IMPL.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from kit_contracts import Ok, Refusal, RefusalCode, expect
from kit_eval import reference as ref
from kit_eval.cases import mandate_from_case
from kit_verifier import verify_cart
from mock_gateway import LABELS, DiscoverQuery, TwinEvent, at, make_twin, seeded_violations

T0 = at(2026, 11, 24, 14, 0)


@dataclass
class CheckResult:
    check_id: str
    status: str  # pass | fail | skipped
    detail: str = ""


def _hw_case() -> dict[str, Any]:
    return {
        "case_id": "conf-hw",
        "mandate": {
            "headcount": {"adults": 2, "kids": [8, 11]},
            "deadline": {"type": "pickup_ready_by", "time": "2026-11-24T18:00:00-06:00", "store": "STORE-A"},
            "budget": {"max_cents": 2500},
            "occasion": "taco",
        },
    }


def p01_discover_labeled() -> tuple[bool, str]:
    t = make_twin(T0)
    r = t.catalog.discover(DiscoverQuery("STORE-A", roles=("tortillas",), usuals=True), T0)
    ok = isinstance(r, Ok) and r.value.labels and all(v in LABELS for v in r.value.labels.values())
    return bool(ok), str(r.value.labels if isinstance(r, Ok) else r)


def p02_slots_labeled_and_zoned() -> tuple[bool, str]:
    t = make_twin(T0)
    r = t.slots.slots("STORE-A", T0, T0 + timedelta(hours=6), T0)
    if not isinstance(r, Ok):
        return False, str(r)
    s = r.value.slots
    ok = bool(s) and all(x.start.tzinfo is not None and x.cutoff < x.start and x.tz == "America/Chicago" for x in s)
    ok = ok and all(v in LABELS for v in r.value.labels.values())
    return ok, f"{len(s)} slots, mode {r.value.mode}"


def p03_replay_deterministic() -> tuple[bool, str]:
    a, b = make_twin(T0, seed=7), make_twin(T0, seed=7)
    da, db = a.catalog.state_digest("STORE-A", T0), b.catalog.state_digest("STORE-A", T0)
    sa = [(x.slot_id, x.cutoff, x.capacity) for x in expect(a.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0)).slots]
    sb = [(x.slot_id, x.cutoff, x.capacity) for x in expect(b.slots.slots("STORE-A", T0, T0 + timedelta(hours=8), T0)).slots]
    other = make_twin(T0, seed=8).catalog.state_digest("STORE-A", T0)
    return da == db and sa == sb and da != other, f"digest {da[:12]} (seed 8: {other[:12]})"


def p04_violations_reproducible() -> tuple[bool, str]:
    t = make_twin(T0)
    v1 = seeded_violations(t.catalog, 3, T0, n=6)
    v2 = seeded_violations(t.catalog, 3, T0, n=6)
    return v1 == v2 and len({e.kind for e in v1}) == 3, f"{[e.kind for e in v1]}"


def p05_not_exposed_refuses() -> tuple[bool, str]:
    t = make_twin(T0, slots_mode="not_exposed")
    r = t.slots.slots("STORE-A", T0, T0 + timedelta(hours=4), T0)
    return isinstance(r, Refusal) and r.code == RefusalCode.CAPABILITY_UNAVAILABLE, str(getattr(r, "code", r))


def p06_hold_needs_holds_mode() -> tuple[bool, str]:
    t = make_twin(T0, slots_mode="read_only")
    sid = next(x.slot_id for x in expect(t.slots.slots("STORE-A", T0, T0 + timedelta(hours=6), T0)).slots if x.capacity > 0)
    r = t.slots.hold(sid, "md-x", T0 + timedelta(minutes=30), T0)
    return isinstance(r, Refusal) and r.code == RefusalCode.CAPABILITY_UNAVAILABLE, str(getattr(r, "code", r))


def p07_checkout_after_cutoff_stale() -> tuple[bool, str]:
    t = make_twin(T0)
    s = next(x for x in expect(t.slots.slots("STORE-A", T0, T0 + timedelta(hours=6), T0)).slots if x.capacity > 0)
    r = t.slots.consume(s.slot_id, s.cutoff + timedelta(minutes=1))
    return isinstance(r, Refusal) and r.code == RefusalCode.STALE, str(getattr(r, "reason", r))


def p08_unknown_store_is_refusal() -> tuple[bool, str]:
    t = make_twin(T0)
    r = t.catalog.discover(DiscoverQuery("STORE-ZZ", roles=("salsa",)), T0)
    return isinstance(r, Refusal), str(getattr(r, "code", r))


def p09_usuals_scope_reported() -> tuple[bool, str]:
    t = make_twin(T0)
    t.catalog.profile_usuals = {"prof-ruth": ["TW-0001"], "prof-jen": ["TW-0011"]}
    r = t.catalog.discover(DiscoverQuery("STORE-A", profile_id="prof-ruth", usuals=True), T0)
    return isinstance(r, Ok) and r.value.scope_answered in ("account", "profile"), f"scope {r.value.scope_answered if isinstance(r, Ok) else r}"


def p10_seeded_violations_caught() -> tuple[bool, str]:
    """100% of seeded catalog/slot violations on a built cart are caught at checkpoint 3 (K03)."""
    case = _hw_case()
    m = mandate_from_case(case)
    caught, total = 0, 0
    for kind in ("price_change", "stock_out", "packaging_change", "slot_vanish"):
        t = make_twin(T0)
        cart = ref.greedy_cart(m, t, "STORE-A", T0)
        assert not isinstance(cart, Refusal)
        later = T0 + timedelta(minutes=10)
        ln = cart.lines[0]
        if kind == "price_change":
            t.catalog.inject(TwinEvent(T0 + timedelta(minutes=1), "price_change", ln.sku, price_cents=ln.price_cents + 40))
            bad = not verify_cart(cart, m, t.catalog, later).all_hard_pass
        elif kind == "stock_out":
            t.catalog.inject(TwinEvent(T0 + timedelta(minutes=1), "stock_out", ln.sku))
            bad = not verify_cart(cart, m, t.catalog, later).all_hard_pass
        elif kind == "packaging_change":
            m2 = mandate_from_case({**case, "mandate": {**case["mandate"], "exclude": ["sesame"]}})
            cart2 = ref.greedy_cart(m2, t, "STORE-A", T0)
            assert not isinstance(cart2, Refusal)
            t.catalog.inject(
                TwinEvent(
                    T0 + timedelta(minutes=1),
                    "packaging_change",
                    cart2.lines[0].sku,
                    packaging_version="p2",
                    add_contains=("sesame",),
                    add_allergens=("sesame",),
                )
            )
            bad = not verify_cart(cart2, m2, t.catalog, later).all_hard_pass
        else:
            assert cart.slot is not None and cart.slot.slot_id
            t.slots.inject_vanish(cart.slot.slot_id, T0 + timedelta(minutes=1))
            bad = isinstance(t.slots.consume(cart.slot.slot_id, later), Refusal)
        total += 1
        caught += int(bad)
    return caught == total, f"{caught}/{total}"


def t0_parity_fixed_set() -> tuple[bool, str]:
    """Agent >= generic-request baseline on the fixed request set (hello-world dev cases)."""
    from pathlib import Path

    from kit_eval.cases import load_cases
    from kit_eval.hook import ReferenceHook

    root = Path(__file__).resolve().parents[4]
    cases = load_cases(root / "data" / "seeds" / "cases")
    hook = ReferenceHook()
    res = [hook.run_episode(c, seed=0, run=0) for c in cases]
    n = sum(r.tier0 for r in res)
    return n == len(res), f"{n}/{len(res)} (baseline: generic-request stand-in until HP's mock Sparky registers)"


CORE_CHECKS = (
    "c01_checkout_requires_consent",
    "c02_cap_enforced_walmart_side",
    "c03_token_single_use",
    "c04_core_behaviours_labeled",
    "c05_mock_sparky_answers_quote_twin_prices",
)

CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {
    "P01_discover_labeled": p01_discover_labeled,
    "P02_slots_labeled_and_zoned": p02_slots_labeled_and_zoned,
    "P03_replay_deterministic": p03_replay_deterministic,
    "P04_violations_reproducible": p04_violations_reproducible,
    "P05_not_exposed_refuses": p05_not_exposed_refuses,
    "P06_hold_needs_holds_mode": p06_hold_needs_holds_mode,
    "P07_checkout_after_cutoff_stale": p07_checkout_after_cutoff_stale,
    "P08_unknown_store_is_refusal": p08_unknown_store_is_refusal,
    "P09_usuals_scope_reported": p09_usuals_scope_reported,
    "P10_seeded_violations_caught": p10_seeded_violations_caught,
    "T0_parity_fixed_set": t0_parity_fixed_set,
}


def run_all() -> list[CheckResult]:
    out = []
    for cid, fn in CHECKS.items():
        try:
            ok, detail = fn()
            out.append(CheckResult(cid, "pass" if ok else "fail", detail))
        except Exception as e:
            out.append(CheckResult(cid, "fail", f"{type(e).__name__}: {e}"))
    core = os.environ.get("KIT_CORE_IMPL")
    for cid in CORE_CHECKS:
        out.append(CheckResult(cid, "skipped", f"needs HP core half ({'registered: ' + core if core else 'KIT_CORE_IMPL unset'})"))
    return out


def summary(results: list[CheckResult]) -> dict[str, Any]:
    ran = [r for r in results if r.status != "skipped"]
    return {
        "schema": "conformance-report/0",
        "passed": sum(r.status == "pass" for r in ran),
        "ran": len(ran),
        "skipped": [r.check_id for r in results if r.status == "skipped"],
        "failed": [{"id": r.check_id, "detail": r.detail} for r in ran if r.status != "pass"],
    }

"""K03 mutation suite: seeded violations the verifier must catch 100% of the time.

Two families of cart mutants:
  * naive      the lie leaves the books inconsistent (hash or totals no longer match)
  * consistent the attacker also fixes totals and the hash, so only a real check catches it
Plus card mutants (unverified or mismatched numbers, promise language) and brief mutants
(dropped hard constraints, leaked identities or reasons).

Every operator returns None when it does not apply to a base (e.g. no lock to swap); the
suite reports applicability per operator and fails if an operator never applied.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from kit_contracts import Card, CardLine, Cart, CartLine, Mandate, lines_hash
from kit_verifier.verify import CardTruth, CatalogView, fee_for, tax_for, verify_brief, verify_card, verify_cart


@dataclass
class Ctx:
    mandate: Mandate
    catalog: CatalogView
    now: datetime
    store: str
    candidates: dict[str, list[str]]  # role -> skus available at the store


def recompute(cart: Cart, ctx: Ctx) -> Cart:
    """Make totals and hash consistent with the (possibly mutated) lines, as an attacker would."""
    c = copy.deepcopy(cart)
    st = ctx.catalog.store(ctx.store)
    c.subtotal_cents = sum(ln.qty * ln.price_cents for ln in c.lines)
    c.tax_est_cents = tax_for(c.subtotal_cents, st.tax_rate_bps)
    c.total_cents = c.subtotal_cents + c.tax_est_cents + fee_for(c.slot, st)
    c.lines_hash = lines_hash(c.lines)
    return c


def _line_for(sku: str, qty: int, ctx: Ctx, sponsored: bool | None = None) -> CartLine:
    o = ctx.catalog.offer(sku, ctx.store, ctx.now)
    assert o is not None
    return CartLine(
        sku=sku, qty=qty, price_cents=o.price_cents, role=ctx.catalog.role_of(sku) or "?", sponsored=o.sponsored if sponsored is None else sponsored
    )


# ----------------------------------------------------------------------------- cart operators
def m_wrong_price_naive(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    c.lines[0].price_cents -= 17
    return c


def m_wrong_price_consistent(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    c.lines[-1].price_cents = max(1, c.lines[-1].price_cents - 23)
    return recompute(c, ctx)


def m_swap_locked_item(cart: Cart, ctx: Ctx) -> Cart | None:
    for lk in ctx.mandate.locks:
        locked = ctx.catalog.resolve_ref(lk.item_ref)
        if locked is None:
            continue
        role = ctx.catalog.role_of(locked)
        for i, ln in enumerate(cart.lines):
            if ln.sku == locked:
                alts = [s for s in ctx.candidates.get(role or "", []) if s != locked]
                if not alts:
                    return None
                c = copy.deepcopy(cart)
                c.lines[i] = _line_for(alts[0], ln.qty, ctx)
                return recompute(c, ctx)
    return None


def m_over_budget(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    i = max(range(len(c.lines)), key=lambda k: c.lines[k].price_cents)
    while recompute(c, ctx).total_cents <= ctx.mandate.budget.max_cents:
        c.lines[i].qty += 1
    return recompute(c, ctx)


def m_total_understated(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    c.total_cents -= 150
    return c


def m_tax_omitted(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    if c.tax_est_cents == 0:
        return None
    c.total_cents -= c.tax_est_cents
    c.tax_est_cents = 0
    return c


def m_fee_omitted(cart: Cart, ctx: Ctx) -> Cart | None:
    fee = fee_for(cart.slot, ctx.catalog.store(ctx.store))
    if fee == 0:
        return None
    c = copy.deepcopy(cart)
    c.total_cents -= fee
    return c


def m_excluded_item_added(cart: Cart, ctx: Ctx) -> Cart | None:
    terms = [t.lower() for t in ctx.mandate.exclude]
    if not terms:
        return None
    for skus in ctx.candidates.values():
        for s in skus:
            o = ctx.catalog.offer(s, ctx.store, ctx.now)
            if o and o.stock != "out" and any(t in (a.lower() for a in o.attrs.allergens + o.attrs.contains) for t in terms):
                c = copy.deepcopy(cart)
                c.lines.append(_line_for(s, 1, ctx))
                return recompute(c, ctx)
    return None


def m_unknown_attr_item(cart: Cart, ctx: Ctx) -> Cart | None:
    if not ctx.mandate.exclude:
        return None
    for skus in ctx.candidates.values():
        for s in skus:
            o = ctx.catalog.offer(s, ctx.store, ctx.now)
            if o and o.attrs.unknown:
                c = copy.deepcopy(cart)
                c.lines.append(_line_for(s, 1, ctx))
                return recompute(c, ctx)
    return None


def m_sponsored_unmarked(cart: Cart, ctx: Ctx) -> Cart | None:
    for _role, skus in ctx.candidates.items():
        for s in skus:
            o = ctx.catalog.offer(s, ctx.store, ctx.now)
            if o and o.sponsored and o.stock != "out":
                c = copy.deepcopy(cart)
                c.lines.append(_line_for(s, 1, ctx, sponsored=False))
                return recompute(c, ctx)
    return None


def m_role_relabel(cart: Cart, ctx: Ctx) -> Cart | None:
    """Claim a substitute is a different role so a role-keyed lock check would skip it."""
    for lk in ctx.mandate.locks:
        locked = ctx.catalog.resolve_ref(lk.item_ref)
        role = ctx.catalog.role_of(locked) if locked else None
        alts = [s for s in ctx.candidates.get(role or "", []) if s != locked]
        for i, ln in enumerate(cart.lines):
            if ln.sku == locked and alts:
                c = copy.deepcopy(cart)
                nl = _line_for(alts[0], ln.qty, ctx)
                c.lines[i] = replace(nl, role="garnish")
                return recompute(c, ctx)
    return None


def m_hash_tamper(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    c.lines[0].qty += 1
    st = ctx.catalog.store(ctx.store)
    c.subtotal_cents = sum(ln.qty * ln.price_cents for ln in c.lines)
    c.tax_est_cents = tax_for(c.subtotal_cents, st.tax_rate_bps)
    c.total_cents = c.subtotal_cents + c.tax_est_cents + fee_for(c.slot, st)
    return c  # hash left stale


def m_out_of_stock_line(cart: Cart, ctx: Ctx) -> Cart | None:
    for skus in ctx.candidates.values():
        for s in skus:
            o = ctx.catalog.offer(s, ctx.store, ctx.now)
            if o and o.stock == "out":
                c = copy.deepcopy(cart)
                c.lines.append(_line_for(s, 1, ctx))
                return recompute(c, ctx)
    return None


def m_confirmed_slot_lie(cart: Cart, ctx: Ctx) -> Cart | None:
    if cart.slot is None or cart.slot.status == "confirmed":
        return None
    c = copy.deepcopy(cart)
    assert c.slot is not None
    c.slot.status = "confirmed"
    return c


def m_late_slot(cart: Cart, ctx: Ctx) -> Cart | None:
    if cart.slot is None:
        return None
    c = copy.deepcopy(cart)
    assert c.slot is not None
    c.slot.ready_by = ctx.mandate.deadline.time + timedelta(minutes=45)
    return c


def m_slot_dropped(cart: Cart, ctx: Ctx) -> Cart | None:
    if cart.slot is None:
        return None
    c = copy.deepcopy(cart)
    c.slot = None
    return recompute(c, ctx) if fee_for(None, ctx.catalog.store(ctx.store)) == fee_for(cart.slot, ctx.catalog.store(ctx.store)) else c


def m_category_block(cart: Cart, ctx: Ctx) -> Cart | None:
    blocks = [c for c in ctx.mandate.constraints if c.kind == "category_block"]
    if not blocks:
        return None
    for s in ctx.candidates.get("gift_card", []):
        c = copy.deepcopy(cart)
        c.lines.append(_line_for(s, 1, ctx))
        return recompute(c, ctx)
    return None


def m_required_role_dropped(cart: Cart, ctx: Ctx) -> Cart | None:
    req = [c for c in ctx.mandate.constraints if c.kind == "require" and c.hardness == "hard"]
    if not req:
        return None
    want = req[0].value if isinstance(req[0].value, str) else req[0].value[0]
    keep = [ln for ln in cart.lines if ctx.catalog.role_of(ln.sku) != want]
    if len(keep) == len(cart.lines) or not keep:
        return None
    c = copy.deepcopy(cart)
    c.lines = keep
    return recompute(c, ctx)


def m_mandate_swap(cart: Cart, ctx: Ctx) -> Cart | None:
    c = copy.deepcopy(cart)
    c.mandate_id = c.mandate_id + "-other"
    return c


CART_OPERATORS: dict[str, Callable[[Cart, Ctx], Cart | None]] = {
    "M01_wrong_price_naive": m_wrong_price_naive,
    "M02_wrong_price_consistent": m_wrong_price_consistent,
    "M03_swap_locked_item": m_swap_locked_item,
    "M04_over_budget": m_over_budget,
    "M05_total_understated": m_total_understated,
    "M06_tax_omitted": m_tax_omitted,
    "M07_fee_omitted": m_fee_omitted,
    "M08_excluded_item_added": m_excluded_item_added,
    "M09_unknown_attr_item": m_unknown_attr_item,
    "M10_sponsored_unmarked": m_sponsored_unmarked,
    "M11_role_relabel": m_role_relabel,
    "M12_hash_tamper": m_hash_tamper,
    "M13_out_of_stock_line": m_out_of_stock_line,
    "M14_confirmed_slot_lie": m_confirmed_slot_lie,
    "M15_late_slot": m_late_slot,
    "M16_slot_dropped": m_slot_dropped,
    "M17_category_block": m_category_block,
    "M18_required_role_dropped": m_required_role_dropped,
    "M19_mandate_swap": m_mandate_swap,
}

# Time-based mutant: price moves on the twin between building and re-verifying (checkpoint 3).
STALE_PRICE = "M20_stale_price_at_checkout"


# ----------------------------------------------------------------------------- card operators
def c_number_without_claim(card: Card) -> Card | None:
    c = copy.deepcopy(card)
    c.sections[0].lines.append(CardLine(text="Only $3.99 more for guacamole"))
    return c


def c_claim_value_mismatch(card: Card) -> Card | None:
    c = copy.deepcopy(card)
    for cl in c.claims:
        if cl.value.startswith("$"):
            old = cl.value
            dollars = float(old[1:]) - 1.0
            cl.value = f"${dollars:.2f}"
            for sec in c.sections:
                for ln in sec.lines:
                    if ln.claim_ref == cl.id:
                        ln.text = ln.text.replace(old, cl.value)
            return c
    return None


def c_unverified_claim(card: Card) -> Card | None:
    c = copy.deepcopy(card)
    if not c.claims:
        return None
    c.claims[0].verified_by = None
    return c


def c_unlabeled_claim(card: Card) -> Card | None:
    c = copy.deepcopy(card)
    if not c.claims:
        return None
    c.claims[0].label = None
    return c


def c_promise_language(card: Card) -> Card | None:
    c = copy.deepcopy(card)
    c.sections[0].lines.append(CardLine(text="Your pickup slot is guaranteed"))
    return c


CARD_OPERATORS: dict[str, Callable[[Card], Card | None]] = {
    "C01_number_without_claim": c_number_without_claim,
    "C02_claim_value_mismatch": c_claim_value_mismatch,
    "C03_unverified_claim": c_unverified_claim,
    "C04_unlabeled_claim": c_unlabeled_claim,
    "C05_promise_language": c_promise_language,
}


# ----------------------------------------------------------------------------- brief operators
def b_drop_budget(w: dict[str, Any]) -> dict[str, Any] | None:
    w = copy.deepcopy(w)
    w.pop("budget", None)
    return w


def b_drop_lock(w: dict[str, Any]) -> dict[str, Any] | None:
    if not w.get("locks"):
        return None
    w = copy.deepcopy(w)
    w["locks"] = w["locks"][1:]
    return w


def b_drop_exclude(w: dict[str, Any]) -> dict[str, Any] | None:
    if not w.get("exclude"):
        return None
    w = copy.deepcopy(w)
    w["exclude"] = w["exclude"][1:]
    return w


def b_loosen_deadline(w: dict[str, Any]) -> dict[str, Any] | None:
    w = copy.deepcopy(w)
    w["deadline"] = {**w["deadline"], "type": "deliver_window"}
    return w


def b_leak_identity(w: dict[str, Any]) -> dict[str, Any] | None:
    w = copy.deepcopy(w)
    w["requested_by"] = {"member_hash": "mh_leak", "role": "kid"}
    return w


def b_leak_reason(w: dict[str, Any]) -> dict[str, Any] | None:
    w = copy.deepcopy(w)
    w["ask"] = {**w.get("ask", {}), "format": "no milk because the 8-year-old has an allergy"}
    return w


def b_leak_kid_ages(w: dict[str, Any]) -> dict[str, Any] | None:
    w = copy.deepcopy(w)
    w["headcount"] = {**w["headcount"], "kids": [7, 10][: int(w["headcount"].get("kids", 0)) or 1]}
    return w


def b_leak_lock_level(w: dict[str, Any]) -> dict[str, Any] | None:
    if not w.get("locks"):
        return None
    w = copy.deepcopy(w)
    w["locks"][0] = {**w["locks"][0], "level": 4}
    return w


BRIEF_OPERATORS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {
    "B01_drop_budget": b_drop_budget,
    "B02_drop_lock": b_drop_lock,
    "B03_drop_exclude": b_drop_exclude,
    "B04_loosen_deadline": b_loosen_deadline,
    "B05_leak_identity": b_leak_identity,
    "B06_leak_reason": b_leak_reason,
    "B07_leak_kid_ages": b_leak_kid_ages,
    "B08_leak_lock_level": b_leak_lock_level,
}


# ----------------------------------------------------------------------------- runner
# A kill only counts if the verifier failed for the RIGHT reason (the check the operator targets).
EXPECT: dict[str, str] = {
    "M01_wrong_price_naive": "price:",
    "M02_wrong_price_consistent": "price:",
    "M03_swap_locked_item": "lock:",
    "M04_over_budget": "budget",
    "M05_total_understated": "total",
    "M06_tax_omitted": "tax",
    "M07_fee_omitted": "fees",
    "M08_excluded_item_added": "exclude:",
    "M09_unknown_attr_item": "exclude:",
    "M10_sponsored_unmarked": "sponsored:",
    "M11_role_relabel": "lock:",
    "M12_hash_tamper": "lines_hash",
    "M13_out_of_stock_line": "stock:",
    "M14_confirmed_slot_lie": "slot.status",
    "M15_late_slot": "slot.deadline",
    "M16_slot_dropped": "slot.present",
    "M17_category_block": "category_block:",
    "M18_required_role_dropped": "require:",
    "M19_mandate_swap": "mandate_ref",
    STALE_PRICE: "price:",
    "C01_number_without_claim": "card.number",
    "C02_claim_value_mismatch": "card.number",
    "C03_unverified_claim": "card.number",
    "C04_unlabeled_claim": "label:",
    "C05_promise_language": "card.slot_promise",
    "B01_drop_budget": "wire.budget",
    "B02_drop_lock": "wire.lock",
    "B03_drop_exclude": "wire.exclude",
    "B04_loosen_deadline": "wire.deadline",
    "B05_leak_identity": "disclosure.",
    "B06_leak_reason": "disclosure.reasons",
    "B07_leak_kid_ages": "disclosure.",
    "B08_leak_lock_level": "disclosure.keys",
}


@dataclass
class OperatorStats:
    applied: int = 0
    killed: int = 0
    survivors: list[str] = field(default_factory=list)
    wrong_reason: list[str] = field(default_factory=list)

    def record(self, name: str, subject: str, rep: Any) -> None:
        self.applied += 1
        if rep.all_hard_pass:
            self.survivors.append(subject)
            return
        failed = rep.failed() + (["card.number"] if rep.unverified_numbers else [])
        if any(f.startswith(EXPECT[name]) for f in failed):
            self.killed += 1
        else:
            self.wrong_reason.append(f"{subject}: {failed}")


@dataclass
class MutationReport:
    operators: dict[str, OperatorStats]
    clean_false_alarms: list[str]

    @property
    def total_applied(self) -> int:
        return sum(s.applied for s in self.operators.values())

    @property
    def kill_rate(self) -> float:
        n = self.total_applied
        return 1.0 if n == 0 else sum(s.killed for s in self.operators.values()) / n

    def wrong_reasons(self) -> dict[str, list[str]]:
        return {k: s.wrong_reason for k, s in self.operators.items() if s.wrong_reason}

    def never_applied(self) -> list[str]:
        return [k for k, s in self.operators.items() if s.applied == 0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kill_rate": self.kill_rate,
            "applied": self.total_applied,
            "clean_false_alarms": self.clean_false_alarms,
            "never_applied": self.never_applied(),
            "operators": {
                k: {"applied": s.applied, "killed": s.killed, "survivors": s.survivors, "wrong_reason": s.wrong_reason} for k, s in self.operators.items()
            },
        }


@dataclass
class Base:
    cart: Cart
    ctx: Ctx
    card: Card | None = None
    truth: CardTruth | None = None
    brief_wire: dict[str, Any] | None = None
    reprice: Callable[[], datetime] | None = None  # injects a price change; returns the re-verify time


def run_mutation_suite(bases: list[Base]) -> MutationReport:
    ops: dict[str, OperatorStats] = {k: OperatorStats() for k in [*CART_OPERATORS, STALE_PRICE, *CARD_OPERATORS, *BRIEF_OPERATORS]}
    false_alarms: list[str] = []
    for b in bases:
        clean = verify_cart(b.cart, b.ctx.mandate, b.ctx.catalog, b.ctx.now)
        if not clean.all_hard_pass:
            false_alarms.append(f"{b.cart.cart_id}: {clean.failed()}")
            continue
        for name, op in CART_OPERATORS.items():
            m = op(b.cart, b.ctx)
            if m is None or m == b.cart:
                continue
            ops[name].record(name, b.cart.cart_id, verify_cart(m, b.ctx.mandate, b.ctx.catalog, b.ctx.now))
        if b.reprice is not None:
            later = b.reprice()
            ops[STALE_PRICE].record(STALE_PRICE, b.cart.cart_id, verify_cart(b.cart, b.ctx.mandate, b.ctx.catalog, later))
        if b.card is not None and b.truth is not None:
            clean_card = verify_card(b.card, b.truth)
            if not clean_card.all_hard_pass:
                false_alarms.append(f"{b.card.card_id}: {clean_card.failed()}")
            else:
                for name, cop in CARD_OPERATORS.items():
                    mc = cop(b.card)
                    if mc is not None:
                        ops[name].record(name, b.card.card_id, verify_card(mc, b.truth))
        if b.brief_wire is not None:
            if not verify_brief(b.brief_wire, b.ctx.mandate).all_hard_pass:
                false_alarms.append(f"brief:{b.ctx.mandate.mandate_id}")
            else:
                for name, bop in BRIEF_OPERATORS.items():
                    mw = bop(b.brief_wire)
                    if mw is not None:
                        ops[name].record(name, b.ctx.mandate.mandate_id, verify_brief(mw, b.ctx.mandate))
    return MutationReport(ops, false_alarms)

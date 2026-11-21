"""K03 constraint verifier. Pure, deterministic, model-free (components@2, ADR-003).

Three checkpoints call it: before a cart reaches a ballot, before a brief leaves, before a
card renders, and again on the winning cart before checkout. It never trusts the agent's
own claims about a line (role, lock_ok, totals, hash); it recomputes them from the catalog.

Interpretations IQ made where the draft is silent (raised with F in the coordination log):
  * Lock `level` (0..4) is recorded as evidence only; strictness comes from `exact_upc`.
    exact_upc=False admits a "safe equivalent": same role, allergens and contains a subset
    of the locked item's, and no unknown attributes.
  * A cart with no slot plan fails `slot.present`: the mandate always carries a deadline.
  * `status: confirmed` needs a confirmer (the twin's hold/consume record); without one it
    is an unverified claim (0 false promises).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from kit_contracts import Card, Cart, Check, Mandate, Offer, SlotPlan, VerifyReport, lines_hash
from kit_contracts.loose import standing_view


class StoreInfo(Protocol):
    tax_rate_bps: int
    pickup_fee_cents: int
    delivery_fee_cents: int


class CatalogView(Protocol):
    def offer(self, sku: str, store: str, now: datetime) -> Offer | None: ...
    def role_of(self, sku: str) -> str | None: ...
    def resolve_ref(self, item_ref: str) -> str | None: ...
    def store(self, store_id: str) -> Any: ...


UNKNOWN_BLOCKING = {"allergens", "contains"}


def tax_for(subtotal_cents: int, rate_bps: int) -> int:
    return (subtotal_cents * rate_bps + 5000) // 10000


def fee_for(slot: SlotPlan | None, store: Any) -> int:
    if slot is not None and slot.kind == "delivery":
        return int(store.delivery_fee_cents)
    return int(store.pickup_fee_cents)


def budget_amount(cart: Cart, mandate: Mandate) -> int:
    fees = cart.total_cents - cart.subtotal_cents - cart.tax_est_cents
    amt = cart.subtotal_cents
    if "tax" in mandate.budget.includes:
        amt += cart.tax_est_cents
    if "fees" in mandate.budget.includes:
        amt += fees
    return amt


def _tokens(o: Offer) -> set[str]:
    words = set(re.findall(r"[a-z][a-z\-]+", o.title.lower()))
    return words | {a.lower() for a in o.attrs.allergens} | {c.lower() for c in o.attrs.contains}


def excluded_hit(o: Offer, terms: Iterable[str]) -> tuple[bool, str]:
    terms = [t.lower() for t in terms]
    if not terms:
        return False, ""
    if UNKNOWN_BLOCKING & set(o.attrs.unknown):
        return True, f"unknown attributes {sorted(UNKNOWN_BLOCKING & set(o.attrs.unknown))} cannot satisfy an exclude"
    toks = _tokens(o)
    hits = [t for t in terms if t in toks or any(t in w for w in o.attrs.contains)]
    return (bool(hits), f"matches {hits}" if hits else "")


def safe_equivalent(candidate: Offer, locked: Offer) -> bool:
    if set(candidate.attrs.unknown):
        return False
    return set(candidate.attrs.allergens) <= set(locked.attrs.allergens) and set(candidate.attrs.contains) <= set(locked.attrs.contains)


def _deadline_ok(slot: SlotPlan, mandate: Mandate) -> tuple[bool, str]:
    d = mandate.deadline
    if d.type == "pickup_ready_by":
        return slot.kind == "pickup" and slot.ready_by <= d.time, f"pickup ready {slot.ready_by.isoformat()} vs {d.time.isoformat()}"
    if d.type == "deliver_by":
        return slot.kind == "delivery" and slot.ready_by <= d.time, f"delivered by {slot.ready_by.isoformat()} vs {d.time.isoformat()}"
    end = d.window_end or d.time
    ok = slot.kind == "delivery" and d.time <= slot.ready_by <= end
    return ok, f"delivered {slot.ready_by.isoformat()} in [{d.time.isoformat()}, {end.isoformat()}]"


def verify_cart(
    cart: Cart,
    mandate: Mandate,
    catalog: CatalogView,
    now: datetime,
    *,
    slot_confirmer: Callable[[str], bool] | None = None,
) -> VerifyReport:
    checks: list[Check] = []
    add = checks.append
    store_id = cart.store or (cart.slot.store if cart.slot else None) or mandate.deadline.store
    if store_id is None:
        add(Check("store", "fail", None, "cart names no store"))
        return VerifyReport(cart.cart_id, checks)
    store = catalog.store(store_id)

    add(Check("mandate_ref", "pass" if cart.mandate_id == mandate.mandate_id else "fail", cart.mandate_id))
    lh = lines_hash(cart.lines)
    add(Check("lines_hash", "pass" if lh == cart.lines_hash else "fail", cart.lines_hash, f"recomputed {lh}"))
    if not cart.lines:
        add(Check("lines.nonempty", "fail", 0))

    offers: dict[str, Offer] = {}
    subtotal = 0
    for ln in cart.lines:
        o = catalog.offer(ln.sku, store_id, now)
        if o is None:
            add(Check(f"line:{ln.sku}:exists", "fail", ln.sku, "sku not in catalog"))
            continue
        offers[ln.sku] = o
        subtotal += ln.qty * ln.price_cents
        add(Check(f"qty:{ln.sku}", "pass" if ln.qty >= 1 else "fail", ln.qty))
        add(Check(f"price:{ln.sku}", "pass" if ln.price_cents == o.price_cents else "fail", ln.price_cents, f"catalog {o.price_cents} at {now.isoformat()}"))
        add(Check(f"stock:{ln.sku}", "pass" if o.stock != "out" else "fail", o.stock))
        add(Check(f"sponsored:{ln.sku}", "pass" if ln.sponsored == o.sponsored else "fail", ln.sponsored, f"catalog sponsored={o.sponsored}"))
        cat_role = catalog.role_of(ln.sku)
        add(Check(f"role:{ln.sku}", "pass" if ln.role == cat_role else "fail", ln.role, f"catalog role {cat_role}"))

    add(Check("subtotal", "pass" if subtotal == cart.subtotal_cents else "fail", cart.subtotal_cents, f"recomputed {subtotal}"))
    tax = tax_for(subtotal, store.tax_rate_bps)
    add(Check("tax", "pass" if tax == cart.tax_est_cents else "fail", cart.tax_est_cents, f"recomputed {tax}"))
    fee = fee_for(cart.slot, store)
    implied_fee = cart.total_cents - cart.subtotal_cents - cart.tax_est_cents
    add(Check("fees", "pass" if implied_fee == fee else "fail", implied_fee, f"store fee {fee}"))
    total = subtotal + tax + fee
    add(Check("total", "pass" if total == cart.total_cents else "fail", cart.total_cents, f"recomputed {total}"))

    amount = budget_amount(cart, mandate)
    if mandate.budget.hard:
        add(Check("budget", "pass" if amount <= mandate.budget.max_cents else "fail", amount, f"max {mandate.budget.max_cents}"))
    else:
        add(Check("budget", "pass" if amount <= mandate.budget.max_cents else "fail", amount, "soft", hard=False))

    # ---------------------------------------------------------------- locks (one source: Household via Mandate)
    lock_refs = [(lk.item_ref, lk.exact_upc, lk.level, f"lock:{lk.item_ref}") for lk in mandate.locks]
    lock_refs += [(str(c.value), True, None, f"lock:{c.id}") for c in mandate.constraints if c.kind == "lock"]
    for ref, exact, level, cid in lock_refs:
        locked_sku = catalog.resolve_ref(ref)
        if locked_sku is None:
            add(Check(cid, "fail", ref, "lock reference does not resolve; unknown never satisfies a lock"))
            continue
        locked = catalog.offer(locked_sku, store_id, now)
        role = catalog.role_of(locked_sku)
        bad = []
        for ln in cart.lines:
            if catalog.role_of(ln.sku) != role or ln.sku == locked_sku:
                continue
            cand = offers.get(ln.sku)
            if exact or cand is None or locked is None or not safe_equivalent(cand, locked):
                bad.append(ln.sku)
        add(Check(cid, "fail" if bad else "pass", bad, f"role {role}; exact_upc={exact}; level={level}"))

    # ---------------------------------------------------------------- excludes
    terms = list(mandate.exclude) + [str(c.value) for c in mandate.constraints if c.kind == "exclude" and c.hardness == "hard"]
    for sku, o in offers.items():
        hit, why = excluded_hit(o, terms)
        add(Check(f"exclude:{sku}", "fail" if hit else "pass", sku, why))

    # ---------------------------------------------------------------- other constraints
    present_roles = {catalog.role_of(s) for s in offers}
    for c in mandate.constraints:
        hard = c.hardness == "hard"
        if c.kind == "require":
            want = c.value if isinstance(c.value, (list, tuple)) else [c.value]
            ok = all(w in present_roles for w in want)
            add(Check(f"require:{c.id}", "pass" if ok else "fail", sorted(r for r in present_roles if r), f"needs {want}", hard=hard))
        elif c.kind == "cap":
            add(Check(f"cap:{c.id}", "pass" if amount <= int(c.value) else "fail", amount, f"cap {c.value}", hard=hard))
        elif c.kind == "category_block":
            blocked = set(c.value if isinstance(c.value, (list, tuple)) else [c.value])
            hits = [s for s, o in offers.items() if o.category in blocked]
            add(Check(f"category_block:{c.id}", "fail" if hits else "pass", hits, f"blocked {sorted(blocked)}", hard=hard))
        elif c.kind == "ship_to":
            st = "pass" if cart.ship_to == c.value else ("unknown" if cart.ship_to is None else "fail")
            add(Check(f"ship_to:{c.id}", st, cart.ship_to, f"pinned {c.value}", hard=hard))

    sv = standing_view(mandate.standing)  # LOOSE (R4.4)
    if sv is not None and sv.per_order_cents is not None:
        add(Check("standing.per_order", "pass" if amount <= sv.per_order_cents else "fail", amount, f"{sv.shape} cap {sv.per_order_cents}"))
    if sv is not None and sv.category_blocks:
        hits = [s for s, o in offers.items() if o.category in sv.category_blocks]
        add(Check("standing.category", "fail" if hits else "pass", hits, sv.shape))

    # ---------------------------------------------------------------- slot and deadline
    s = cart.slot
    if s is None:
        add(Check("slot.present", "fail", None, "no SlotPlan; the mandate carries a deadline"))
    else:
        add(Check("slot.store", "pass" if s.store == store_id else "fail", s.store))
        if s.status == "infeasible":
            add(Check("slot.status", "fail", s.status, "an infeasible slot never reaches a ballot"))
        elif s.status == "confirmed":
            ok = s.source == "slots_api" and s.slot_id is not None and slot_confirmer is not None and slot_confirmer(s.slot_id)
            add(Check("slot.status", "pass" if ok else "fail", s.status, "confirmed needs a slots-API confirmation (hold or consume)"))
        else:
            add(Check("slot.status", "pass", s.status))
        ok, why = _deadline_ok(s, mandate)
        add(Check("slot.deadline", "pass" if ok else "fail", s.ready_by.isoformat(), why))
        add(Check("slot.cutoff", "pass" if now < s.cutoff else "fail", s.cutoff.isoformat(), f"now {now.isoformat()}"))
    return VerifyReport(cart.cart_id, checks)


# ===================================================================== cards
NUM_RE = re.compile(r"\$?\d+(?:[.:,]\d+)*%?")
PROMISE_RE = re.compile(r"\b(guaranteed|reserved|held for you|locked in|confirmed(?! at checkout))\b", re.I)
ESTIMATE_RE = re.compile(r"(estimated|about|around|approx|confirmed at checkout|~)", re.I)


@dataclass
class CardTruth:
    """Values K03 computed from the verified cart; the only source a card number may come from."""

    values: dict[str, str]
    report_ref: str
    slot: SlotPlan | None = None


def verify_card(card: Card, truth: CardTruth) -> VerifyReport:
    checks: list[Check] = []
    unverified = 0
    claims = {c.id: c for c in card.claims}
    for c in card.claims:
        lab = c.label or ""
        ok = lab == "synthetic" or lab.startswith("public:")
        checks.append(Check(f"label:{c.id}", "pass" if ok else "fail", c.label, "every number is labeled synthetic | public:<src>"))
    for si, sec in enumerate(card.sections):
        for li, line in enumerate(sec.lines):
            where = f"{si}.{li}"
            nums = NUM_RE.findall(line.text)
            if nums:
                cl = claims.get(line.claim_ref or "")
                ok = (
                    cl is not None
                    and bool(cl.verified_by)
                    and cl.verified_by == truth.report_ref
                    and cl.id in truth.values
                    and cl.value == truth.values[cl.id]
                    and cl.value in line.text
                    and all(n in cl.value for n in nums)
                )
                if not ok:
                    unverified += 1
                checks.append(Check(f"card.number:{where}", "pass" if ok else "fail", nums, f"claim_ref={line.claim_ref}"))
            if truth.slot is not None and truth.slot.status != "confirmed":
                if PROMISE_RE.search(line.text):
                    checks.append(Check(f"card.slot_promise:{where}", "fail", line.text, "slot not confirmed; no promise language"))
                if (line.claim_ref or "").startswith("slot.") and not ESTIMATE_RE.search(line.text):
                    checks.append(Check(f"card.slot_estimate:{where}", "fail", line.text, "estimated slot must say so"))
    return VerifyReport(card.card_id, checks, unverified_numbers=unverified)


# ===================================================================== briefs
# hw-taco@1 zero_tolerance.disclosure_violations: no member names, hashes, ages, roles, lock levels or reasons on the wire.
FORBIDDEN_KEYS = {
    "member_hash",
    "principal",
    "requested_by",
    "household_hash",
    "reason",
    "reasons",
    "diagnosis",
    "name",
    "names",
    "member",
    "role",
    "roles",
    "level",
    "levels",
    "age",
    "ages",
}
REASON_WORDS = re.compile(r"\b(allerg\w*|intoleran\w*|celiac|diabet\w*|diagnos\w*|medical|condition|because|medication)\b", re.I)


def money_text(cents: int) -> str:
    return f"${cents / 100:.2f}"


def time_texts(dt: datetime) -> tuple[str, ...]:
    h12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return (f"{h12}:{dt.minute:02d} {ampm}", dt.strftime("%H:%M"), dt.isoformat())


def _walk_keys(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_keys(v)


def verify_brief(wire: dict[str, Any] | str, mandate: Mandate) -> VerifyReport:
    """CT-07a (hard constraints on the wire) and CT-07f (minimum disclosure)."""
    checks: list[Check] = []
    add = checks.append
    secrets = {mandate.principal.member_hash, mandate.requested_by.member_hash}
    if isinstance(wire, dict):
        b = wire.get("budget", {})
        add(Check("wire.budget", "pass" if b.get("max_cents") == mandate.budget.max_cents and b.get("hard") == mandate.budget.hard else "fail", b))
        d = wire.get("deadline", {})
        add(Check("wire.deadline", "pass" if d.get("type") == mandate.deadline.type and d.get("time") == mandate.deadline.time.isoformat() else "fail", d))
        h = wire.get("headcount", {})
        kids = h.get("kids", 0)
        kid_count = len(kids) if isinstance(kids, list) else kids
        add(Check("wire.headcount", "pass" if h.get("adults") == mandate.headcount.adults and kid_count == len(mandate.headcount.kids) else "fail", h))
        add(Check("disclosure.ages", "fail" if isinstance(kids, list) and kids else "pass", kids, "kids travel as a count, never ages (Brief@1, hw-taco@1)"))
        refs = {lk.get("item_ref") for lk in wire.get("locks", [])}
        for lk in mandate.locks:
            add(Check(f"wire.lock:{lk.item_ref}", "pass" if lk.item_ref in refs else "fail", sorted(r for r in refs if r)))
        ex = {(e.get("value", "") if isinstance(e, dict) else str(e)).lower() for e in wire.get("exclude", [])}  # typed or plain
        for e in mandate.exclude:
            add(Check(f"wire.exclude:{e}", "pass" if e.lower() in ex else "fail", sorted(ex)))
        add(Check("wire.mandate_id", "pass" if wire.get("mandate_id") == mandate.mandate_id else "fail", wire.get("mandate_id")))
        leaked = sorted(set(_walk_keys(wire)) & FORBIDDEN_KEYS)
        add(Check("disclosure.keys", "fail" if leaked else "pass", leaked, "rules travel, reasons and identities don't"))
        blob = str(wire)
    else:
        text = wire
        low = text.lower()
        add(Check("wire.budget", "pass" if money_text(mandate.budget.max_cents) in text else "fail", money_text(mandate.budget.max_cents)))
        add(Check("wire.deadline", "pass" if any(t in text for t in time_texts(mandate.deadline.time)) else "fail", time_texts(mandate.deadline.time)[0]))
        add(Check("wire.headcount", "pass" if str(mandate.headcount.total) in text else "fail", mandate.headcount.total))
        for lk in mandate.locks:
            add(Check(f"wire.lock:{lk.item_ref}", "pass" if lk.item_ref.split(":", 1)[1] in text else "fail", lk.item_ref))
        for e in mandate.exclude:
            add(Check(f"wire.exclude:{e}", "pass" if e.lower() in low else "fail", e))
        blob = text
    add(Check("disclosure.identity", "fail" if any(s and s in blob for s in secrets) else "pass", None, "no member identities on the wire"))
    m = REASON_WORDS.search(blob)
    add(Check("disclosure.reasons", "fail" if m else "pass", m.group(0) if m else None, "no reasons behind locks"))
    return VerifyReport(f"brief:{mandate.mandate_id}", checks)

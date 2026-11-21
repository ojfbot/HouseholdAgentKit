"""Reference implementations at tier `none` (IQ). Definition by example, NOT the product components.

The contract suites and the hello-world harness need something to run against before the
owning lanes land (K21 MF, K04 MF, K02 MF, K05 HP, K11 DX, K12 ED, K24-H1 extractor HP/MF).
Each function here is the smallest deterministic thing that satisfies the contract. When an
owner registers a real implementation (KIT_CT_IMPL / --hook), the same suites run against it
and these stay as the oracle baseline. Nothing here is tuned or clever on purpose.
"""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from kit_contracts import (
    Card,
    CardClaim,
    CardLine,
    CardSection,
    Cart,
    CartLine,
    Mandate,
    Offer,
    Ok,
    Refusal,
    RefusalCode,
    SlotPlan,
    lines_hash,
)
from kit_contracts.hashing import canonical_json, sha256_hex
from kit_verifier import CardTruth, fee_for, money_text, tax_for, time_texts
from kit_verifier.verify import excluded_hit, safe_equivalent
from mock_gateway import DiscoverQuery, Twin

# ----------------------------------------------------------------------------- K21 need list (template)
TEMPLATES: dict[str, list[tuple[str, bool, str]]] = {
    # role, required, qty rule
    "taco": [
        ("tortillas", True, "per5"),
        ("protein", True, "per4"),
        ("cheese", True, "per4"),
        ("salsa", True, "one"),
        ("lettuce", True, "one"),
        ("seasoning", False, "per4"),
        ("sour_cream", False, "one"),
        ("tomato", False, "one"),
    ],
}


def need_list(m: Mandate) -> list[tuple[str, bool, int]] | Refusal:
    occ = (m.occasion or "").lower()
    if occ not in TEMPLATES:
        return Refusal(RefusalCode.AMBIGUOUS, f"no template for occasion {m.occasion!r}", owner_action="what are we making?")
    n = max(1, m.headcount.total)
    q = {"one": 1, "per4": math.ceil(n / 4), "per5": math.ceil(n / 5)}
    on_hand = {o.lower() for o in m.on_hand}
    return [(role, req, q[rule]) for role, req, rule in TEMPLATES[occ] if role not in on_hand]


# ----------------------------------------------------------------------------- feasibility per offer
def blocked_categories(m: Mandate) -> set[str]:
    out: set[str] = set()
    for c in m.constraints:
        if c.kind == "category_block" and c.hardness == "hard":
            out |= set(c.value if isinstance(c.value, (list, tuple)) else [c.value])
    return out


def feasible(o: Offer, role: str, m: Mandate, twin: Twin, store: str, now: datetime) -> bool:
    if o.stock == "out" or o.category in blocked_categories(m):
        return False
    if excluded_hit(o, list(m.exclude) + [str(c.value) for c in m.constraints if c.kind == "exclude" and c.hardness == "hard"])[0]:
        return False
    for lk in m.locks:
        locked = twin.catalog.resolve_ref(lk.item_ref)
        if locked is None or twin.catalog.role_of(locked) != role or o.sku == locked:
            continue
        lo = twin.catalog.offer(locked, store, now)
        if lk.exact_upc or lo is None or not safe_equivalent(o, lo):
            return False
    return True


def candidates(role: str, m: Mandate, twin: Twin, store: str, now: datetime) -> list[Offer]:
    r = twin.catalog.discover(DiscoverQuery(store=store, roles=(role,)), now)
    if not isinstance(r, Ok):
        return []
    return [o for o in r.value.offers_by_role.get(role, []) if feasible(o, role, m, twin, store, now)]


def _cart(m: Mandate, lines: list[CartLine], twin: Twin, store: str, slot: SlotPlan | None, label: str) -> Cart:
    st = twin.catalog.store(store)
    sub = sum(ln.qty * ln.price_cents for ln in lines)
    tax = tax_for(sub, st.tax_rate_bps)
    total = sub + tax + fee_for(slot, st)
    cid = "cart-" + sha256_hex(canonical_json([m.mandate_id, label, [(ln.sku, ln.qty) for ln in lines]]))[:12]
    return Cart(cid, m.mandate_id, lines, sub, tax, total, lines_hash(lines), slot=slot, label=label, store=store)


# ----------------------------------------------------------------------------- K05 slot plan (heuristic or slots API)
def plan_slot(m: Mandate, twin: Twin, store: str, now: datetime) -> SlotPlan:
    kind = "pickup" if m.deadline.type == "pickup_ready_by" else "delivery"
    cfg = twin.catalog.store(store)
    lead = timedelta(minutes=cfg.pickup_lead_min if kind == "pickup" else cfg.delivery_lead_min)
    r = twin.slots.slots(store, now, m.deadline.window_end or m.deadline.time + timedelta(hours=2), now, kind=kind)
    if isinstance(r, Ok):
        ok_slots = [
            s
            for s in r.value.slots
            if s.capacity > 0
            and now < s.cutoff - timedelta(minutes=10)
            and (
                s.ready_by <= m.deadline.time
                if m.deadline.type != "deliver_window"
                else m.deadline.time <= s.ready_by <= (m.deadline.window_end or m.deadline.time)
            )
        ]
        if not ok_slots:
            return SlotPlan(store, m.deadline.time, "infeasible", "slots_api", now, kind=kind)  # type: ignore[arg-type]
        best = max(ok_slots, key=lambda s: s.ready_by) if kind == "pickup" else min(ok_slots, key=lambda s: s.ready_by)
        # read-only answers are not confirmations; only a hold confirms (adapters@1)
        return SlotPlan(store, best.ready_by, "estimated", "slots_api", best.cutoff, slot_id=best.slot_id, kind=kind)  # type: ignore[arg-type]
    # not exposed: store hours + published lead time
    ready = now + lead
    status = "estimated" if ready <= m.deadline.time else "infeasible"
    return SlotPlan(store, ready, status, "heuristic", now + timedelta(minutes=30), kind=kind)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- K04 stand-in: greedy cheapest feasible
def greedy_cart(m: Mandate, twin: Twin, store: str, now: datetime, offers_override: dict[str, list[Offer]] | None = None) -> Cart | Refusal:
    nl = need_list(m)
    if isinstance(nl, Refusal):
        return nl
    slot = plan_slot(m, twin, store, now)
    if slot.status == "infeasible":
        return Refusal(RefusalCode.INFEASIBLE, "no slot meets the deadline", evidence=[{"deadline": m.deadline.time.isoformat(), "now": now.isoformat()}])
    lines: list[CartLine] = []
    missing = []
    for role, _req, qty in [x for x in nl if x[1]]:
        cands = offers_override.get(role, []) if offers_override is not None else candidates(role, m, twin, store, now)
        cands = [o for o in cands if feasible(o, role, m, twin, store, now)]
        if not cands:
            missing.append(role)
            continue
        o = min(cands, key=lambda x: (x.price_cents, x.sku))
        lines.append(CartLine(o.sku, qty, o.price_cents, role, True, o.sponsored))
    if missing:
        return Refusal(RefusalCode.INFEASIBLE, f"no feasible item for {missing}", evidence=[{"roles": missing}])
    cart = _cart(m, lines, twin, store, slot, "cheapest")
    if cart.total_cents > m.budget.max_cents and m.budget.hard:
        return Refusal(
            RefusalCode.INFEASIBLE,
            "cheapest feasible cart is over budget",
            evidence=[{"min_total_cents": cart.total_cents, "budget_cents": m.budget.max_cents}],
        )
    for role, _req, qty in [x for x in nl if not x[1]]:
        cands = (
            candidates(role, m, twin, store, now)
            if offers_override is None
            else [o for o in offers_override.get(role, []) if feasible(o, role, m, twin, store, now)]
        )
        if not cands:
            continue
        o = min(cands, key=lambda x: (x.price_cents, x.sku))
        trial = _cart(m, [*lines, CartLine(o.sku, qty, o.price_cents, role, True, o.sponsored)], twin, store, slot, "cheapest")
        if trial.total_cents <= m.budget.max_cents:
            lines = trial.lines
    return _cart(m, lines, twin, store, slot, "cheapest")


# ----------------------------------------------------------------------------- oracle (independent brute force)
def oracle_total(m: Mandate, cart: Cart, twin: Twin, store: str, now: datetime) -> int:
    """Min total over every feasible assignment for the roles (and quantities) the cart covers."""
    roles = [(ln.role, ln.qty) for ln in cart.lines]
    pools = [[o for o in candidates(r, m, twin, store, now)] for r, _ in roles]
    if any(not p for p in pools):
        return cart.total_cents
    st = twin.catalog.store(store)
    best = None
    for combo in itertools.product(*pools):
        sub = sum(o.price_cents * q for o, (_, q) in zip(combo, roles, strict=True))
        tot = sub + tax_for(sub, st.tax_rate_bps) + fee_for(cart.slot, st)
        best = tot if best is None or tot < best else best
    return best if best is not None else cart.total_cents


# ----------------------------------------------------------------------------- tier-0 stand-in for Sparky-in-app
GENERIC_ROLES = ("tortillas", "protein", "cheese", "salsa", "lettuce", "sour_cream")


def generic_baseline_cart(m: Mandate, twin: Twin, store: str, now: datetime) -> Cart:
    """Answer to the GENERIC request ("taco night for my family"): no locks, excludes or budget
    travel. Sponsored first, then catalog order. Replaced by HP's mock Sparky when it registers."""
    lines = []
    for role in GENERIC_ROLES:
        r = twin.catalog.discover(DiscoverQuery(store=store, roles=(role,)), now)
        offers = [o for o in r.value.offers_by_role.get(role, []) if o.stock != "out"] if isinstance(r, Ok) else []
        if not offers:
            continue
        o = sorted(offers, key=lambda x: (not x.sponsored, x.sku))[0]
        lines.append(CartLine(o.sku, 1, o.price_cents, role, True, o.sponsored))
    return _cart(m, lines, twin, store, plan_slot(m, twin, store, now), "generic")


# ----------------------------------------------------------------------------- K02 stand-in: deterministic brief projection
def render_brief_h2(m: Mandate) -> dict[str, Any]:
    return {
        "mandate_id": m.mandate_id,
        "occasion": m.occasion,
        "headcount": {"adults": m.headcount.adults, "kids": len(m.headcount.kids)},  # a count, never ages
        "deadline": {"type": m.deadline.type, "time": m.deadline.time.isoformat(), "store": m.deadline.store},
        "budget": {"max_cents": m.budget.max_cents, "includes": list(m.budget.includes), "hard": m.budget.hard},
        "locks": [{"item_ref": lk.item_ref, "exact_upc": lk.exact_upc} for lk in m.locks],
        "exclude": [{"kind": "ingredient", "value": e, "hardness": "hard"} for e in m.exclude],  # typed (Brief@1, Fork A)
        "on_hand": list(m.on_hand),
        "round": 0,
        "ask": {"options": 3, "vectors": ["savings", "fresh", "repeat"], "format": "itemized"},
        "disclosure": {"mark_sponsored": True},
        **({"profile_id": m.profile_id} if m.profile_id else {}),
    }


def render_brief_h1(m: Mandate) -> str:
    kids = f" and {len(m.headcount.kids)} kids" if m.headcount.kids else ""
    parts = [
        f"{(m.occasion or 'dinner').title()} for {m.headcount.total} ({m.headcount.adults} adults{kids}).",
        f"Ready for pickup by {time_texts(m.deadline.time)[0]}" if m.deadline.type == "pickup_ready_by" else f"Delivered by {time_texts(m.deadline.time)[0]}",
        f"at {m.deadline.store}." if m.deadline.store else ".",
        f"Hard budget {money_text(m.budget.max_cents)} including tax and fees." if m.budget.hard else f"Budget about {money_text(m.budget.max_cents)}.",
    ]
    if m.locks:
        parts.append("Exact items only, no substitutes: " + ", ".join(lk.item_ref.split(":", 1)[1] for lk in m.locks) + ".")
    if m.exclude:
        parts.append("Nothing containing: " + ", ".join(m.exclude) + ".")
    parts.append("Give 3 options, itemized with prices; mark sponsored items.")
    return " ".join(parts)


MAX_FOLLOWUPS = 2


def next_followup(m: Mandate, round_: int, missing: list[str]) -> str | None:
    """Keyed (mandate_id, round); deterministic; never more than 2; carries rules, never reasons."""
    if round_ > MAX_FOLLOWUPS or not missing:
        return None
    return f"[{m.mandate_id}#{round_}] Please add prices and stock for: {', '.join(sorted(missing))}."


# ----------------------------------------------------------------------------- K24-H1 stand-in: prose -> Offer list
PRICE_RE = re.compile(r"\$(\d+\.\d{2})")


def extract_offers(reply: str, twin: Twin, store: str, now: datetime) -> list[Offer]:
    """Find catalog titles in Sparky prose and take the price stated next to each.
    Instructions inside the reply are data, never commands: nothing here can change a mandate."""
    out: list[Offer] = []
    seen: set[str] = set()
    low = reply.lower()
    for row in sorted(twin.catalog.rows, key=lambda r: -len(r.title)):
        t = row.title.lower()
        i = low.find(t)
        if i < 0 or row.sku in seen:
            continue
        m = PRICE_RE.search(reply, i + len(t), i + len(t) + 40)
        if not m:
            continue
        base = twin.catalog.offer(row.sku, store, now)
        assert base is not None
        seen.add(row.sku)
        out.append(Offer(**{**base.__dict__, "price_cents": round(float(m.group(1)) * 100), "source": "sparky"}))
    return out


# ----------------------------------------------------------------------------- K11 stand-in: template approval card
def approval_card(cart: Cart, m: Mandate, report_ref: str) -> tuple[Card, CardTruth]:
    total = money_text(cart.total_cents)
    ready = time_texts(cart.slot.ready_by)[0] if cart.slot else "unknown"
    when = f"Pickup ready about {ready} (confirmed at checkout)" if cart.slot and cart.slot.status != "confirmed" else f"Pickup ready {ready}"
    claims = [CardClaim("total", total, report_ref), CardClaim("slot.ready_by", ready, report_ref), CardClaim("items", str(len(cart.lines)), report_ref)]
    card = Card(
        card_id=f"card-{cart.cart_id}",
        audience=m.principal,
        kind="approval",
        sections=[
            CardSection(
                "Taco night",
                [
                    CardLine(f"Total {total}", "total"),
                    CardLine(when, "slot.ready_by"),
                    CardLine(f"{len(cart.lines)} items", "items"),
                ],
            )
        ],
        claims=claims,
    )
    return card, CardTruth({"total": total, "slot.ready_by": ready, "items": str(len(cart.lines))}, report_ref, cart.slot)


# ----------------------------------------------------------------------------- K12 stand-in: hash-chained ledger
@dataclass
class MiniLedger:
    entries: list[dict[str, Any]] = field(default_factory=list)

    def append(self, kind: str, ref: str, m: Mandate, at: datetime, amount: int | None = None) -> dict[str, Any]:
        prev = self.entries[-1]["hash"] if self.entries else "0" * 64
        e = {
            "entry_id": f"le-{len(self.entries):03d}",
            "episode_id": f"ep-{m.mandate_id}",
            "kind": kind,
            "refs": [ref],
            "actor": m.principal.role,
            "requested_by": m.requested_by.role,
            "profile_id": m.profile_id,
            "amount": amount,
            "at": at.isoformat(),
            "prev_hash": prev,
        }
        e["hash"] = sha256_hex(canonical_json(e))
        self.entries.append(e)
        return e

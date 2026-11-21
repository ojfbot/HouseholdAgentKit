"""Server-side oracles the harness scores with (score from state and logs, never from what the agent says)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from kit_contracts import Mandate, Ok
from kit_contracts.hashing import canonical_json, sha256_hex
from kit_verifier import fee_for, tax_for
from kit_verifier.verify import excluded_hit, safe_equivalent
from mock_gateway import Twin

CHAIN_KINDS = ("mandate", "brief", "cart", "decision", "consent", "order")


def audit_chain_complete(entries: list[dict[str, Any]], required: tuple[str, ...] = CHAIN_KINDS) -> tuple[bool, str]:
    """Ledger@0 trace chain: required kinds appear in order, prev_hash links hold, hashes recompute,
    and requested_by + profile_id ride every entry (B's requester_faithfulness)."""
    prev = "0" * 64
    for e in entries:
        if e.get("prev_hash") != prev:
            return False, f"{e.get('entry_id')}: prev_hash breaks the chain"
        body = {k: v for k, v in e.items() if k != "hash"}
        if sha256_hex(canonical_json(body)) != e.get("hash"):
            return False, f"{e.get('entry_id')}: hash does not recompute"
        if "requested_by" not in e or "profile_id" not in e:
            return False, f"{e.get('entry_id')}: requested_by/profile_id missing"
        prev = e["hash"]
    kinds = [e["kind"] for e in entries]
    it = iter(kinds)
    if not all(k in it for k in required):
        return False, f"kinds {kinds} do not contain {list(required)} in order"
    return True, "ok"


def world_feasible(m: Mandate, twin: Twin, store: str, now: datetime, required_roles: list[tuple[str, int]]) -> tuple[bool, str]:
    """Is ANY acceptable cart possible in this twin world? Read straight from twin state, not from
    the agent's code, so "the agent refused" can be told apart from "nothing could be done"."""
    kind = "pickup" if m.deadline.type == "pickup_ready_by" else "delivery"
    if twin.slots.mode != "not_exposed":
        r = twin.slots.slots(store, now, (m.deadline.window_end or m.deadline.time) + timedelta(hours=2), now, kind=kind)
        slots = [s for s in r.value.slots if s.capacity > 0 and now < s.cutoff] if isinstance(r, Ok) else []
        if m.deadline.type == "deliver_window":
            slots = [s for s in slots if m.deadline.time <= s.ready_by <= (m.deadline.window_end or m.deadline.time)]
        else:
            slots = [s for s in slots if s.ready_by <= m.deadline.time]
        if not slots:
            return False, "no slot with capacity before cutoff meets the deadline"
    terms = list(m.exclude) + [str(c.value) for c in m.constraints if c.kind == "exclude" and c.hardness == "hard"]
    blocked = {v for c in m.constraints if c.kind == "category_block" for v in (c.value if isinstance(c.value, list) else [c.value])}
    sub = 0
    for role, qty in required_roles:
        best = None
        for row in twin.catalog.rows:
            if role not in row.roles:
                continue
            o = twin.catalog.offer(row.sku, store, now)
            if o is None or o.stock == "out" or o.category in blocked or excluded_hit(o, terms)[0]:
                continue
            ok = True
            for lk in m.locks:
                ls = twin.catalog.resolve_ref(lk.item_ref)
                if ls is None or twin.catalog.role_of(ls) != role or ls == o.sku:
                    continue
                lo = twin.catalog.offer(ls, store, now)
                if lk.exact_upc or lo is None or not safe_equivalent(o, lo):
                    ok = False
            if ok and (best is None or o.price_cents < best):
                best = o.price_cents
        if best is None:
            return False, f"no feasible item for role {role}"
        sub += best * qty
    st = twin.catalog.store(store)
    from kit_contracts import SlotPlan

    total = sub + tax_for(sub, st.tax_rate_bps) + fee_for(SlotPlan(store, now, "estimated", "heuristic", now, kind=kind), st)  # type: ignore[arg-type]
    if m.budget.hard and total > m.budget.max_cents:
        return False, f"cheapest feasible total {total} > budget {m.budget.max_cents}"
    return True, "ok"

"""The hello-world hook (C's stage-0 gate, D's bundle-eval episode set, G's E17 abort rule).

Contract proposed by IQ for A to implement (C asked A for a callable smoke test returning
tier 0/1/2 results). Any object with `name` and `run_episode()` is a hook; `ReferenceHook`
is the tier-`none` reference pipeline over the twin, used until A's taco-night hook is
registered with `kit eval hello-world --hook <module>:<attr>`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from kit_contracts import Cart, Refusal, VerifyReport
from kit_eval import reference as ref
from kit_eval.cases import mandate_from_case
from kit_eval.oracles import audit_chain_complete, world_feasible
from kit_verifier import verify_brief, verify_card, verify_cart
from mock_gateway import TwinEvent, make_twin


@dataclass
class EpisodeResult:
    case_id: str
    run: int
    outcome: str  # cart | refusal
    refusal_code: str | None = None
    accepted: bool = False
    tier0: bool = False
    tier1: bool = False
    tier2: bool = False
    regret: float | None = None
    hard_constraints_carried: float = 0.0  # fraction of brief hard checks on the wire
    disclosure_ok: bool = False
    lock_violations: int = 0
    unverified_numbers: int = 0
    unlabeled_numbers: int = 0
    verify_failed: list[str] = field(default_factory=list)
    chain_ok: bool = False
    world_feasible: bool = True  # oracle: could ANY acceptable cart exist in this twin world?
    restarts: int = 0
    latency_s: float = 0.0
    fallback_used: bool = True
    stamps: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class HelloWorldHook(Protocol):
    name: str

    def run_episode(self, case: dict[str, Any], seed: int, run: int) -> EpisodeResult: ...


def _accept(case: dict[str, Any], r: EpisodeResult, cart: Cart | None, refusal: Refusal | None) -> bool:
    for cond in case["accept_if"]:
        k = cond["kind"]
        if k == "verified" and not (cart is not None and not r.verify_failed):
            return False
        if k == "tier" and not {0: r.tier0, 1: r.tier1, 2: r.tier2}.get(int(cond["min"]), False):
            return False
        if k == "refusal":
            if refusal is None or refusal.code.value != cond["code"]:
                return False
            if cond.get("with_numbers") and not any(isinstance(e, dict) and any(isinstance(v, int) for v in e.values()) for e in refusal.evidence):
                return False
        if k == "total_lte" and not (cart is not None and cart.total_cents <= int(cond["cents"])):
            return False
        if k == "ready_by_lte" and (cart is None or cart.slot is None or cart.slot.ready_by > datetime.fromisoformat(cond["time"])):
            return False
    return True


def _count(rep: VerifyReport, prefix: str) -> int:
    return sum(1 for c in rep.checks if c.constraint_id.startswith(prefix) and c.status != "pass")


class ReferenceHook:
    name = "iq-reference-tier-none"

    def __init__(self, regret_bar: float = 0.10, poll_minutes: int = 5) -> None:
        self.regret_bar = regret_bar
        self.poll = timedelta(minutes=poll_minutes)

    def run_episode(self, case: dict[str, Any], seed: int, run: int) -> EpisodeResult:
        t0 = time.perf_counter()
        start = datetime.fromisoformat(case["clock_start"])
        twin = make_twin(start, seed=seed, slots_mode=case.get("slots_mode", "read_only"))
        for ev in case.get("world_events", []):
            if not isinstance(ev, dict):
                continue
            when = start + timedelta(minutes=int(ev.get("after_min", 1)))
            if ev.get("kind") == "price_change":
                twin.catalog.inject(TwinEvent(when, "price_change", ev["sku"], price_cents=int(ev["price_cents"])))
            elif ev.get("kind") == "stock_out":
                twin.catalog.inject(TwinEvent(when, "stock_out", ev["sku"], store=ev.get("store")))
        m = mandate_from_case(case)
        store = case.get("store") or m.deadline.store or "STORE-A"
        now = twin.clock.now()
        r = EpisodeResult(case_id=case["case_id"], run=run, outcome="cart", stamps={**twin.config_stamp(), "hook": self.name})
        ledger = ref.MiniLedger()
        ledger.append("mandate", m.mandate_id, m, now)

        wire = ref.render_brief_h2(m)
        brep = verify_brief(wire, m)
        wire_checks = [c for c in brep.checks if c.constraint_id.startswith("wire.")]
        r.hard_constraints_carried = sum(c.status == "pass" for c in wire_checks) / max(1, len(wire_checks))
        r.disclosure_ok = all(c.status == "pass" for c in brep.checks if c.constraint_id.startswith("disclosure."))
        ledger.append("brief", m.mandate_id, m, now)

        nl = ref.need_list(m)
        req = [(role, q) for role, need, q in nl if need] if not isinstance(nl, Refusal) else []
        r.world_feasible, wwhy = world_feasible(m, twin, store, now, req)
        built = ref.greedy_cart(m, twin, store, now)
        if isinstance(built, Refusal):
            r.outcome, r.refusal_code = "refusal", built.code.value
            r.accepted = _accept(case, r, None, built)
            if not r.world_feasible and built.code.value == "INFEASIBLE" and not r.accepted:
                r.accepted = True  # the honest answer in a world where nothing could work
                r.notes.append(f"world infeasible (oracle): {wwhy}; refusal accepted")
            r.tier0 = r.accepted  # a correct refusal is at least as good as a generic cart that breaks rules
            r.latency_s = time.perf_counter() - t0
            return r
        cart = built
        rep = verify_cart(cart, m, twin.catalog, now)  # checkpoint 2
        ledger.append("cart", cart.cart_id, m, now, cart.total_cents)
        card, truth = ref.approval_card(cart, m, f"vr:{cart.cart_id}")
        crep = verify_card(card, truth)
        r.unverified_numbers = crep.unverified_numbers
        r.unlabeled_numbers = _count(crep, "label:")

        twin.clock.advance(self.poll)  # the poll runs; owner_decides
        ledger.append("decision", cart.cart_id, m, twin.clock.now())
        rep3 = verify_cart(cart, m, twin.catalog, twin.clock.now())  # checkpoint 3
        if not rep3.all_hard_pass:
            r.notes.append(f"STALE at checkpoint 3: {rep3.failed()}; re-solving")
            r.restarts += 1
            again = ref.greedy_cart(m, twin, store, twin.clock.now())
            if isinstance(again, Refusal):
                r.outcome, r.refusal_code = "refusal", again.code.value
                r.latency_s = time.perf_counter() - t0
                return r
            cart = again
            rep3 = verify_cart(cart, m, twin.catalog, twin.clock.now())
            ledger.append("cart", cart.cart_id, m, twin.clock.now(), cart.total_cents)
            ledger.append("decision", cart.cart_id, m, twin.clock.now())
        r.verify_failed = rep3.failed()
        r.lock_violations = _count(rep, "lock:") + _count(rep3, "lock:")

        ledger.append("consent", cart.cart_id, m, twin.clock.now(), cart.total_cents)  # HP's consent gate replaces this
        booked = True
        if cart.slot is not None and cart.slot.slot_id:
            res = twin.slots.consume(cart.slot.slot_id, twin.clock.now())
            booked = res.ok
            if isinstance(res, Refusal):
                r.notes.append(f"checkout slot: {res.reason}")
        if booked:
            ledger.append("order", cart.cart_id, m, twin.clock.now(), cart.total_cents)
        r.chain_ok, why = audit_chain_complete(ledger.entries)
        if not r.chain_ok:
            r.notes.append(why)

        base = ref.generic_baseline_cart(m, twin, store, now)
        brep0 = verify_cart(base, m, twin.catalog, now)
        r.tier0 = len(rep.failed()) <= len(brep0.failed())
        orc = ref.oracle_total(m, cart, twin, store, twin.clock.now())
        r.regret = (cart.total_cents - orc) / orc if orc else 0.0
        r.tier1 = rep3.all_hard_pass and r.hard_constraints_carried == 1.0 and r.disclosure_ok and r.regret <= self.regret_bar
        deadline_ok = all(c.status == "pass" for c in rep3.checks if c.constraint_id in ("slot.deadline", "slot.cutoff"))
        r.tier2 = r.tier1 and booked and deadline_ok and r.lock_violations == 0 and r.chain_ok and r.unverified_numbers == 0
        r.accepted = _accept(case, r, cart, None)
        r.latency_s = time.perf_counter() - t0
        return r

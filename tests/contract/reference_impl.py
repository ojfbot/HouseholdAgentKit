"""Reference implementation surface the contract suites run against (tier `none`, IQ).

An owning lane registers its real implementation by exporting an object with the same
methods and setting KIT_CT_IMPL=<module>:<attr>. The suites never change; only this binding.

Method -> owning component:
  render_brief / followup          K02 (MF)          extract           K24-H1 extractor (HP/MF)
  solve / answer_or_fallback       K04 (MF)          plan_slot         K05 (HP)
  profile_* / usuals_for           K07 (PD)          standing_guard    K08 (PD)
  place_order / revoke / history   K24 + K07 (HP/PD) decide_two_approvers K10 policy (PD)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kit_contracts import Cart, Mandate, Offer, Ok, Refusal, RefusalCode
from kit_contracts.loose import standing_view
from kit_eval import reference as ref
from kit_verifier import budget_amount, verify_cart
from mock_gateway import DiscoverQuery, Twin


@dataclass
class Profile:
    """Twin Agent Profile fixture (B ask 1): scope key (account, agent, served_person_id), ADR-004."""

    profile_id: str
    account_id: str
    agent_id: str
    served_person_id: str
    cap_per_order_cents: int
    cap_per_month_cents: int
    ship_to: str
    blocked_categories: tuple[str, ...] = ()
    usuals: tuple[str, ...] = ()  # our side's record of this profile's usuals
    revoked: bool = False


@dataclass
class FakeWalmartCore:
    """Spy standing in for HP's core checkout: records calls; enforces its own (possibly looser) cap."""

    cap_per_order_cents: int | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)
    shopper_history: list[str] = field(default_factory=list)
    agent_history: dict[str, list[str]] = field(default_factory=dict)

    def checkout(self, profile: Profile, cart: Cart, ship_to: str) -> Ok[str] | Refusal:
        self.calls.append({"profile": profile.profile_id, "cart": cart.cart_id, "ship_to": ship_to})
        if self.cap_per_order_cents is not None and cart.total_cents > self.cap_per_order_cents:
            return Refusal(RefusalCode.OVER_CAP, "walmart-side cap")
        order_id = f"ord-{len(self.calls):03d}"
        self.agent_history.setdefault(profile.profile_id, []).append(order_id)
        return Ok(order_id)

    def shopper_checkout(self, order_id: str) -> None:
        self.shopper_history.append(order_id)


class ReferenceImpl:
    name = "iq-reference-tier-none"

    # ---------------------------------------------------------------- CAP-07
    def render_brief(self, m: Mandate, mode: str) -> dict[str, Any] | str:
        return ref.render_brief_h1(m) if mode == "H1" else ref.render_brief_h2(m)

    def followup(self, m: Mandate, round_: int, missing: list[str]) -> str | None:
        return ref.next_followup(m, round_, missing)

    def extract(self, reply: str, twin: Twin, store: str, now: datetime) -> list[Offer]:
        return ref.extract_offers(reply, twin, store, now)

    def answer_or_fallback(self, m: Mandate, answer: Cart, offers: list[Offer], twin: Twin, store: str, now: datetime) -> tuple[Cart | Refusal, bool]:
        """CT-07e: Sparky's cart if it verifies, else our solver over the returned items."""
        if verify_cart(answer, m, twin.catalog, now).all_hard_pass:
            return answer, False
        # Re-price Sparky's items from the catalog: numbers on our side are verified, never quoted.
        by_role: dict[str, list[Offer]] = {}
        for o in offers:
            cur = twin.catalog.offer(o.sku, store, now)
            role = twin.catalog.role_of(o.sku)
            if cur is not None and role is not None:
                by_role.setdefault(role, []).append(cur)
        return ref.greedy_cart(m, twin, store, now, offers_override=by_role), True

    def solve(self, m: Mandate, twin: Twin, store: str, now: datetime) -> Cart | Refusal:
        return ref.greedy_cart(m, twin, store, now)

    # ---------------------------------------------------------------- CAP-10
    def plan_slot(self, m: Mandate, twin: Twin, store: str, now: datetime):
        return ref.plan_slot(m, twin, store, now)

    # ---------------------------------------------------------------- CAP-02 / CAP-21 (K07, K08)
    def place_order(self, profile: Profile, cart: Cart, ship_to: str, core: FakeWalmartCore, month_to_date_cents: int = 0) -> Ok[str] | Refusal:
        if profile.revoked:
            return Refusal(RefusalCode.RIGHTS_DENIED, "profile revoked")
        if ship_to != profile.ship_to:
            return Refusal(RefusalCode.ADDRESS_MISMATCH, "ship-to differs from the pinned address", owner_action="ask the approver")
        if cart.total_cents > profile.cap_per_order_cents:
            return Refusal(RefusalCode.OVER_CAP, "over the profile's per-order cap", owner_action="route to approver")
        if month_to_date_cents + cart.total_cents > profile.cap_per_month_cents:
            return Refusal(RefusalCode.OVER_CAP, "over the profile's monthly cap", owner_action="route to approver")
        return core.checkout(profile, cart, ship_to)  # ours first, then Walmart's

    def revoke(self, profile: Profile) -> None:
        profile.revoked = True

    def usuals_for(self, profile: Profile, twin: Twin, store: str, now: datetime) -> list[Offer]:
        r = twin.catalog.discover(DiscoverQuery(store=store, account_id=profile.account_id, profile_id=profile.profile_id, usuals=True), now)
        if not r.ok:
            return []
        if r.value.scope_answered == "profile":
            return r.value.usuals
        return [o for o in r.value.usuals if o.sku in profile.usuals]  # K07 scopes account-level answers

    def standing_guard(self, m: Mandate, cart: Cart, month_to_date_cents: int) -> Ok[str] | Refusal:
        sv = standing_view(m.standing)
        if sv is None:
            return Refusal(RefusalCode.OUT_OF_MANDATE, "no standing mandate; unattended action refused")
        amt = budget_amount(cart, m)
        if sv.per_order_cents is not None and amt > sv.per_order_cents:
            return Refusal(RefusalCode.OVER_CAP, "per-order cap", owner_action="ask the approver; never auto-approve on timeout")
        if sv.per_month_cents is not None and month_to_date_cents + amt > sv.per_month_cents:
            return Refusal(RefusalCode.OVER_CAP, "per-month cap", owner_action="ask the approver; never auto-approve on timeout")
        if sv.autonomy == "approve_each":
            return Refusal(RefusalCode.OUT_OF_MANDATE, "approve_each: ask before every order")
        return Ok("within_mandate")

    # ---------------------------------------------------------------- CAP-28 (K10 policy)
    def decide_two_approvers(self, approvers: list[str], votes: dict[str, str], timed_out: bool, owner: str) -> str:
        approvals = {a for a in approvers if votes.get(a) == "approve"}
        if any(votes.get(a) == "reject" for a in approvers):
            return "rejected"
        if approvals == set(approvers) and len(approvers) >= 2:
            return "approved"
        return "held" if timed_out else "pending"  # never owner default


impl = ReferenceImpl()

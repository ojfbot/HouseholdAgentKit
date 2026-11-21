"""Typed mirror of the components@2 `types` block (Fork F draft, Nov 19).

Conventions chosen here (flagged to F in the coordination log, to settle at freeze):
  * money is integer cents (`*_cents`); the draft says `money` without a wire shape.
  * every datetime is timezone-aware.
  * Cart has no `fees` field in the draft; fees = total - subtotal - tax_est and the
    verifier checks that against the store's fee for the slot kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

ROLES = (
    "owner",
    "partner",
    "teen",
    "kid",
    "guest",
    "requester",
    "approver_payer",
    "key_holder",
    "treasurer",
    "fulfiller",
)


@dataclass(frozen=True)
class MemberRef:
    member_hash: str
    role: str


@dataclass
class Headcount:
    adults: int
    kids: tuple[int, ...] = ()

    @property
    def total(self) -> int:
        return self.adults + len(self.kids)


@dataclass
class Deadline:
    type: Literal["pickup_ready_by", "deliver_by", "deliver_window"]
    time: datetime
    store: str | None = None
    window_end: datetime | None = None
    slack: timedelta | None = None


@dataclass
class Budget:
    max_cents: int
    includes: tuple[str, ...] = ("tax", "fees")
    hard: bool = True


@dataclass
class Constraint:
    id: str
    kind: Literal["lock", "exclude", "require", "cap", "category_block", "ship_to"]
    value: Any
    hardness: Literal["hard", "soft"] = "hard"
    slack: Any = None


@dataclass
class Lock:
    item_ref: str  # "upc:<digits>" or "sku:<id>"
    level: int  # 0..4 (A's safe-food levels; semantics not in components@2, recorded as evidence only)
    exact_upc: bool = True


@dataclass
class Mandate:
    """Mandate@1 draft. `standing` is LOOSE until batch 1 (see kit_contracts.loose)."""

    mandate_id: str
    principal: MemberRef
    requested_by: MemberRef
    headcount: Headcount
    deadline: Deadline
    budget: Budget
    profile_id: str | None = None
    occasion: str | None = None
    constraints: list[Constraint] = field(default_factory=list)
    locks: list[Lock] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    on_hand: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=lambda: {"savings": 1.0, "fresh": 0.0, "repeat": 0.0, "variety": 0.0})
    standing: dict[str, Any] | None = None  # LOOSE
    household_rev: int | None = None  # ADR-003: locks carried by reference; stale rev -> STALE

    def hard_constraints(self) -> list[Constraint]:
        return [c for c in self.constraints if c.hardness == "hard"]


@dataclass
class AttributeSet:
    allergens: tuple[str, ...] = ()
    contains: tuple[str, ...] = ()
    packaging_version: str | None = None
    snap_eligible: bool | None = None
    size: str | None = None
    unknown: tuple[str, ...] = ()  # attribute names the catalog could not resolve


@dataclass
class Offer:
    sku: str
    upc: str
    title: str
    price_cents: int
    unit: str
    stock: Literal["in", "low", "out", "unknown"]
    attrs: AttributeSet
    sponsored: bool = False
    source: Literal["discover", "sparky"] = "discover"
    category: str = "grocery"


@dataclass
class SlotPlan:
    store: str
    ready_by: datetime
    status: Literal["confirmed", "estimated", "infeasible"]
    source: Literal["slots_api", "heuristic"]
    cutoff: datetime
    slot_id: str | None = None
    kind: Literal["pickup", "delivery"] = "pickup"


@dataclass
class CartLine:
    sku: str
    qty: int
    price_cents: int
    role: str
    lock_ok: bool = True
    sponsored: bool = False


@dataclass
class Cart:
    cart_id: str
    mandate_id: str
    lines: list[CartLine]
    subtotal_cents: int
    tax_est_cents: int
    total_cents: int
    lines_hash: str
    slot: SlotPlan | None = None
    label: str = ""
    store: str | None = None
    ship_to: str | None = None  # not in the components@2 draft; asked of F for CT-21b


@dataclass
class Check:
    constraint_id: str
    status: Literal["pass", "fail", "unknown"]
    observed: Any = None
    evidence: str = ""
    hard: bool = True


@dataclass
class VerifyReport:
    subject_ref: str
    checks: list[Check]
    unverified_numbers: int = 0

    @property
    def all_hard_pass(self) -> bool:
        return all(c.status == "pass" for c in self.checks if c.hard) and self.unverified_numbers == 0

    def failed(self) -> list[str]:
        return [c.constraint_id for c in self.checks if c.hard and c.status != "pass"]


@dataclass
class CardLine:
    text: str
    claim_ref: str | None = None


@dataclass
class CardSection:
    title: str
    lines: list[CardLine]


@dataclass
class CardClaim:
    id: str
    value: str
    verified_by: str | None  # ref to the VerifyReport that produced it
    label: str | None = "synthetic"  # every number is labeled synthetic | public:<src>


@dataclass
class Card:
    card_id: str
    audience: MemberRef
    kind: Literal["ballot", "approval", "over_cap", "digest", "fulfiller", "support"]
    sections: list[CardSection]
    claims: list[CardClaim]
    locale: str = "en-US"
    a11y: dict[str, Any] = field(default_factory=lambda: {"contrast": "AA", "reading_level": 6})


@dataclass
class Brief:
    """Brief@1 draft = Sparky brief v0 + mandate_id + profile_id. Rules travel, reasons don't."""

    mandate_id: str
    occasion: str | None
    headcount: Headcount
    deadline: Deadline
    budget: Budget
    locks: list[Lock]
    exclude: list[str]
    on_hand: list[str]
    ask: dict[str, Any]
    disclosure: dict[str, Any]
    profile_id: str | None = None

"""Twin catalog (K17, catalog half). Synthetic items, seeded stock and prices, profile-scoped usuals,
and reproducible seeded violations (price drift, stock-out, packaging change).

Everything here is synthetic. UPCs use the GS1 restricted-circulation prefix 2 so they can
never collide with a real product's code. Prices are invented, labeled `synthetic`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

from kit_contracts import AttributeSet, Offer, Ok, Refusal, RefusalCode
from kit_contracts.hashing import canonical_json, sha256_hex
from mock_gateway.labels import labels_for

CATALOG_VERSION = "catalog@0-twin.1"


@dataclass(frozen=True)
class Row:
    sku: str
    upc: str
    title: str
    roles: tuple[str, ...]
    base_cents: int
    unit: str
    size: str
    category: str = "grocery"
    allergens: tuple[str, ...] = ()
    contains: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    snap: bool | None = True
    sponsored: bool = False
    always_in: bool = False
    packaging_version: str = "p1"


def _r(n: int, title: str, roles: tuple[str, ...], cents: int, unit: str, size: str, **kw) -> Row:
    return Row(sku=f"TW-{n:04d}", upc=f"2{n:011d}", title=title, roles=roles, base_cents=cents, unit=unit, size=size, **kw)


# Taco-night roles first (hello world), then pasta context items (catalog only; spaghetti
# CASES are blind holdout and never live in the repo), then non-food risk items.
ROWS: tuple[Row, ...] = (
    _r(1, "Corn tortillas, 30 ct", ("tortillas",), 248, "pack", "30 ct", contains=("corn",), always_in=True),
    _r(2, "Flour tortillas, 10 ct", ("tortillas",), 228, "pack", "10 ct", allergens=("wheat",), contains=("wheat",), always_in=True),
    _r(3, "Hearth flour tortillas, 8 ct (sponsored)", ("tortillas",), 312, "pack", "8 ct", allergens=("wheat",), contains=("wheat",), sponsored=True),
    _r(4, "Street-taco flour tortillas, 20 ct", ("tortillas",), 284, "pack", "20 ct", allergens=("wheat", "soy"), contains=("wheat", "soy")),
    _r(5, "Ground beef 80/20, 1 lb", ("protein",), 498, "lb", "1 lb", contains=("beef",), always_in=True),
    _r(6, "Ground turkey 93/7, 1 lb", ("protein",), 548, "lb", "1 lb", contains=("turkey",)),
    _r(7, "Black beans, 15 oz can", ("protein",), 98, "can", "15 oz", contains=("beans",), always_in=True),
    _r(8, "Seasoned shredded chicken, 1 lb (sponsored)", ("protein",), 698, "lb", "1 lb", contains=("chicken",), sponsored=True),
    _r(9, "Ground pork, 1 lb", ("protein",), 448, "lb", "1 lb", contains=("pork",)),
    _r(10, "Shredded cheddar, 8 oz", ("cheese",), 248, "bag", "8 oz", allergens=("milk",), contains=("milk",), always_in=True),
    _r(11, "Mexican-blend shreds, 8 oz (sponsored)", ("cheese",), 278, "bag", "8 oz", allergens=("milk",), contains=("milk",), sponsored=True),
    _r(12, "Dairy-free cheddar-style shreds, 7 oz", ("cheese",), 448, "bag", "7 oz", contains=("coconut oil",), always_in=True),
    _r(13, "Queso fresco, 10 oz", ("cheese",), 348, "each", "10 oz", allergens=("milk",), contains=("milk",)),
    _r(14, "Mild salsa, 16 oz", ("salsa",), 198, "jar", "16 oz", contains=("tomato",), always_in=True),
    _r(15, "Medium salsa, 16 oz", ("salsa",), 198, "jar", "16 oz", contains=("tomato",)),
    _r(16, "Fresh pico de gallo, 14 oz", ("salsa",), 348, "tub", "14 oz", contains=("tomato", "onion")),
    _r(17, "Shredded iceberg lettuce, 8 oz", ("lettuce",), 148, "bag", "8 oz", always_in=True),
    _r(18, "Romaine hearts, 3 ct", ("lettuce",), 298, "pack", "3 ct"),
    _r(19, "Sour cream, 8 oz", ("sour_cream",), 128, "tub", "8 oz", allergens=("milk",), contains=("milk",), always_in=True),
    _r(20, "Sour cream, 16 oz", ("sour_cream",), 198, "tub", "16 oz", allergens=("milk",), contains=("milk",)),
    _r(21, "Plant-based sour cream, 12 oz", ("sour_cream",), 398, "tub", "12 oz", contains=("coconut oil",)),
    _r(22, "Taco seasoning packet, 1 oz", ("seasoning",), 68, "packet", "1 oz", allergens=("wheat",), contains=("wheat",), always_in=True),
    _r(23, "Gluten-free taco seasoning, 1 oz", ("seasoning",), 98, "packet", "1 oz", always_in=True),
    # Unresolved allergens: unknown attributes must never satisfy an exclude or a lock (ADR-003, K16).
    _r(24, "Bulk-bin taco seasoning, 2 oz", ("seasoning",), 58, "bag", "2 oz", unknown=("allergens", "contains")),
    _r(25, "Roma tomatoes, 1 lb", ("tomato",), 118, "lb", "1 lb", contains=("tomato",), always_in=True),
    _r(26, "Yellow onion, each", ("onion",), 78, "each", "1 ct", contains=("onion",), always_in=True),
    _r(27, "Limes, 2 lb bag", ("lime",), 298, "bag", "2 lb"),
    _r(28, "Hass avocados, 4 ct", ("avocado",), 448, "bag", "4 ct"),
    # Pasta context (catalog only).
    _r(40, "Spaghetti, 16 oz", ("pasta",), 128, "box", "16 oz", allergens=("wheat",), contains=("wheat",), always_in=True),
    _r(41, "Marinara sauce, 24 oz", ("pasta_sauce",), 248, "jar", "24 oz", contains=("tomato",), always_in=True),
    _r(42, "Grated parmesan, 8 oz", ("parmesan",), 398, "each", "8 oz", allergens=("milk",), contains=("milk",)),
    # Non-food risk items (red-team targets; B's risk_class is deferred, category carries it).
    _r(90, "Gift card, $100", ("gift_card",), 10000, "each", "1 ct", category="gift_card", snap=False),
    _r(91, "Prepaid debit card, $50", ("gift_card",), 5000, "each", "1 ct", category="prepaid_card", snap=False),
)


@dataclass(frozen=True)
class StoreConfig:
    store_id: str
    name: str
    open_hour: int
    close_hour: int
    pickup_lead_min: int
    delivery_lead_min: int
    tax_rate_bps: int  # synthetic
    pickup_fee_cents: int
    delivery_fee_cents: int


STORES: dict[str, StoreConfig] = {
    "STORE-A": StoreConfig("STORE-A", "Store A (synthetic, Central time)", 7, 23, 120, 180, 200, 0, 799),
    "STORE-B": StoreConfig("STORE-B", "Store B (synthetic, Central time)", 6, 22, 90, 150, 200, 0, 599),
}


@dataclass
class TwinEvent:
    """A seeded violation, effective from `at` on the twin clock."""

    at: datetime
    kind: Literal["price_change", "stock_out", "packaging_change"]
    sku: str
    store: str | None = None  # None = every store
    price_cents: int | None = None
    packaging_version: str | None = None
    add_contains: tuple[str, ...] = ()
    add_allergens: tuple[str, ...] = ()


@dataclass
class DiscoverQuery:
    store: str
    roles: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()
    account_id: str = "acct-001"
    profile_id: str | None = None
    usuals: bool = False
    limit: int = 20


@dataclass
class DiscoverResult:
    offers_by_role: dict[str, list[Offer]]
    usuals: list[Offer]
    scope_answered: Literal["profile", "account"] | None
    catalog_version: str
    as_of: datetime
    labels: dict[str, str]


@dataclass
class TwinCatalog:
    seed: int = 0
    usuals_scope: Literal["account", "profile"] = "account"  # announced default; "profile" = CAP-21 proposal
    account_usuals: dict[str, list[str]] = field(default_factory=dict)  # account_id -> skus
    profile_usuals: dict[str, list[str]] = field(default_factory=dict)  # profile_id -> skus
    events: list[TwinEvent] = field(default_factory=list)
    rows: tuple[Row, ...] = ROWS

    def __post_init__(self) -> None:
        self._by_sku = {r.sku: r for r in self.rows}
        self._by_upc = {r.upc: r for r in self.rows}

    # ------------------------------------------------------------------ lookups
    def row(self, sku: str) -> Row | None:
        return self._by_sku.get(sku)

    def sku_for_upc(self, upc: str) -> str | None:
        r = self._by_upc.get(upc)
        return r.sku if r else None

    def resolve_ref(self, item_ref: str) -> str | None:
        kind, _, val = item_ref.partition(":")
        if kind == "sku":
            return val if val in self._by_sku else None
        if kind == "upc":
            return self.sku_for_upc(val)
        return None

    def role_of(self, sku: str) -> str | None:
        r = self.row(sku)
        return r.roles[0] if r else None

    def store(self, store_id: str) -> StoreConfig:
        return STORES[store_id]

    # ------------------------------------------------------------------ pricing and stock
    def _rng(self, *parts: object) -> random.Random:
        return random.Random(":".join(str(p) for p in (self.seed, *parts)))

    def _base_price(self, row: Row, store: str) -> int:
        # +/- 5% per store, seeded; still synthetic.
        f = self._rng("price", store, row.sku).uniform(-0.05, 0.05)
        return max(1, round(row.base_cents * (1 + f)))

    def _base_stock(self, row: Row, store: str) -> str:
        if row.always_in:
            return "in"
        x = self._rng("stock", store, row.sku).random()
        return "in" if x < 0.80 else ("low" if x < 0.92 else "out")

    def offer(self, sku: str, store: str, now: datetime) -> Offer | None:
        row = self.row(sku)
        if row is None:
            return None
        price = self._base_price(row, store)
        stock = self._base_stock(row, store)
        pv = row.packaging_version
        contains = list(row.contains)
        allergens = list(row.allergens)
        for ev in sorted(self.events, key=lambda e: e.at):
            if ev.sku != sku or ev.at > now or (ev.store not in (None, store)):
                continue
            if ev.kind == "price_change" and ev.price_cents is not None:
                price = ev.price_cents
            elif ev.kind == "stock_out":
                stock = "out"
            elif ev.kind == "packaging_change":
                pv = ev.packaging_version or pv
                contains += [c for c in ev.add_contains if c not in contains]
                allergens += [a for a in ev.add_allergens if a not in allergens]
        return Offer(
            sku=row.sku,
            upc=row.upc,
            title=row.title,
            price_cents=price,
            unit=row.unit,
            stock=stock,  # type: ignore[arg-type]
            attrs=AttributeSet(
                allergens=tuple(allergens),
                contains=tuple(contains),
                packaging_version=pv,
                snap_eligible=row.snap,
                size=row.size,
                unknown=row.unknown,
            ),
            sponsored=row.sponsored,
            source="discover",
            category=row.category,
        )

    # ------------------------------------------------------------------ discover()
    def discover(self, q: DiscoverQuery, now: datetime) -> Ok[DiscoverResult] | Refusal:
        if q.store not in STORES:
            return Refusal(RefusalCode.INFEASIBLE, f"unknown store {q.store}", evidence=[q.store])
        by_role: dict[str, list[Offer]] = {}
        wanted = set(q.roles)
        terms = [t.lower() for t in q.terms]
        for row in self.rows:
            hit_role = [r for r in row.roles if r in wanted]
            hit_term = any(t in row.title.lower() for t in terms)
            if not hit_role and not hit_term:
                continue
            off = self.offer(row.sku, q.store, now)
            assert off is not None
            key = hit_role[0] if hit_role else "_terms"
            by_role.setdefault(key, []).append(off)
        for k in by_role:
            by_role[k] = sorted(by_role[k], key=lambda o: (o.price_cents, o.sku))[: q.limit]
        usuals: list[Offer] = []
        scope: Literal["profile", "account"] | None = None
        behaviours = ["catalog.discover.structured", "catalog.prices", "catalog.sponsored_flag", "catalog.packaging_version"]
        if q.usuals:
            if self.usuals_scope == "profile" and q.profile_id is not None:
                skus = self.profile_usuals.get(q.profile_id, [])
                scope = "profile"
                behaviours.append("usuals.profile_scope")
            else:
                # Announced behaviour: usuals are account-level, whatever profile asked.
                skus = list(self.account_usuals.get(q.account_id, []))
                for p_skus in self.profile_usuals.values():
                    skus += [s for s in p_skus if s not in skus]
                scope = "account"
                behaviours.append("usuals.account_scope")
            usuals = [o for s in skus if (o := self.offer(s, q.store, now)) is not None]
        return Ok(
            DiscoverResult(
                offers_by_role=by_role,
                usuals=usuals,
                scope_answered=scope,
                catalog_version=CATALOG_VERSION,
                as_of=now,
                labels=labels_for(*behaviours),
            ),
            adapter_id="twin.catalog",
        )

    # ------------------------------------------------------------------ violations
    def inject(self, ev: TwinEvent) -> None:
        self.events.append(ev)

    def with_events(self, events: list[TwinEvent]) -> TwinCatalog:
        return replace(self, events=list(self.events) + list(events))

    def state_digest(self, store: str, now: datetime) -> str:
        """Hash of every offer at `now`: two twins with the same (seed, events, clock) agree."""
        snap = [self.offer(r.sku, store, now) for r in self.rows]
        return sha256_hex(canonical_json(snap))


def seeded_violations(catalog: TwinCatalog, seed: int, start: datetime, n: int = 3) -> list[TwinEvent]:
    """A reproducible schedule of catalog violations for robustness and conformance runs."""
    from datetime import timedelta

    rng = random.Random(f"violations:{seed}")
    food = [r for r in catalog.rows if r.category == "grocery"]
    out: list[TwinEvent] = []
    for i in range(n):
        row = rng.choice(food)
        at = start + timedelta(minutes=rng.randint(5, 240))
        kind = ("price_change", "stock_out", "packaging_change")[i % 3]
        if kind == "price_change":
            out.append(TwinEvent(at, "price_change", row.sku, price_cents=row.base_cents + rng.randint(10, 150)))
        elif kind == "stock_out":
            out.append(TwinEvent(at, "stock_out", row.sku, store="STORE-A"))
        else:
            out.append(TwinEvent(at, "packaging_change", row.sku, packaging_version="p2", add_contains=("sesame",), add_allergens=("sesame",)))
    return out

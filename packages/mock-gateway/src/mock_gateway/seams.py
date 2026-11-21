"""The seam between the two halves of the Gateway twin (K17).

IQ (this half): catalog, usuals, slots, seeded catalog/slot violations, simulated clock.
HP (core half): mock Gateway server (FastMCP), consent gate, scoped token, mandate record,
                mock Sparky, checkout.

HP's checkout calls `CatalogSlotsPort.consume()` to re-check the slot and `offer()` to
re-price lines; mock Sparky reads `discover()` so its answers quote twin prices. The
`Twin` bundle below is what both halves share in-process; the FastMCP server wraps it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from kit_contracts import Offer
from mock_gateway.catalog import DiscoverQuery, TwinCatalog
from mock_gateway.clock import SimClock
from mock_gateway.slots import TwinSlots


class CatalogSlotsPort(Protocol):
    def discover(self, q: DiscoverQuery, now: datetime): ...
    def offer(self, sku: str, store: str, now: datetime) -> Offer | None: ...
    def slots(self, store: str, start: datetime, end: datetime, now: datetime, kind: str | None = None): ...
    def hold(self, slot_id: str, mandate_id: str, until: datetime, now: datetime): ...
    def consume(self, slot_id: str, now: datetime, hold_id: str | None = None): ...


@dataclass
class Twin:
    """In-process twin: one clock, one catalog, one slot calendar, one seed."""

    clock: SimClock
    catalog: TwinCatalog = field(default_factory=TwinCatalog)
    slots: TwinSlots = field(default_factory=TwinSlots)
    capability_mode: str = "H3"

    @property
    def seed(self) -> int:
        return self.catalog.seed

    def config_stamp(self) -> dict[str, str]:
        """Stamped on every trace (ADR-001): capability mode and twin config."""
        return {
            "capability_mode": self.capability_mode,
            "slots_mode": self.slots.mode,
            "usuals_scope": self.catalog.usuals_scope,
            "twin_seed": str(self.seed),
        }


def make_twin(start: datetime, seed: int = 0, slots_mode: str = "read_only", usuals_scope: str = "account") -> Twin:
    clock = SimClock(start)
    return Twin(
        clock=clock,
        catalog=TwinCatalog(seed=seed, usuals_scope=usuals_scope),  # type: ignore[arg-type]
        slots=TwinSlots(seed=seed, mode=slots_mode, days=(start.date(),)),  # type: ignore[arg-type]
    )

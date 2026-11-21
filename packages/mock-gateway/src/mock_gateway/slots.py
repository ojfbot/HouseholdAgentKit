"""Twin slot calendar (K17, slots half): capacity, cutoff jitter, three exposure modes, holds.

Modes (adapters@1, CAP-10 / CAP-43), set by config and stamped on every response:
  not_exposed  slots() -> CAPABILITY_UNAVAILABLE; K05 falls back to its heuristic (status=estimated)
  read_only    slots() answers; hold() -> CAPABILITY_UNAVAILABLE; plans stay estimated until checkout
  holds        slots() answers; hold() reserves capacity until it lapses or is released

Semantics (labeled invented, `slots.cutoff_semantics`):
  pickup   window [start, start+1h]; order READY at window start (ready_by = start)
  delivery window [start, start+2h]; order ARRIVES by window end (ready_by = end)
  cutoff   = start - lead_minutes + jitter (seeded, +/- 15 min); orders after cutoff miss the slot
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

from kit_contracts import Ok, Refusal, RefusalCode
from mock_gateway.catalog import STORES
from mock_gateway.clock import TZ
from mock_gateway.labels import labels_for

SlotsMode = Literal["not_exposed", "read_only", "holds"]


@dataclass
class Slot:
    slot_id: str
    store: str
    kind: Literal["pickup", "delivery"]
    start: datetime
    end: datetime
    ready_by: datetime
    cutoff: datetime
    capacity: int
    fee_cents: int
    tz: str = "America/Chicago"


@dataclass
class Hold:
    hold_id: str
    slot_id: str
    mandate_id: str
    until: datetime
    is_promise: bool = False  # CT-43a: a hold is never shown to members as a promise
    released: bool = False


@dataclass
class SlotsResponse:
    slots: list[Slot]
    mode: SlotsMode
    labels: dict[str, str]


@dataclass
class TwinSlots:
    seed: int = 0
    mode: SlotsMode = "read_only"
    days: tuple[date, ...] = ()
    _slots: dict[str, Slot] = field(default_factory=dict)
    _used: dict[str, int] = field(default_factory=dict)
    _holds: dict[str, Hold] = field(default_factory=dict)
    _vanish: list[tuple[datetime, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for d in self.days:
            self.ensure_day(d)

    # ------------------------------------------------------------------ calendar
    def ensure_day(self, d: date) -> None:
        for store_id, cfg in STORES.items():
            key = f"{store_id}:{d.isoformat()}"
            if any(s.startswith(key) for s in self._slots):
                continue
            rng = random.Random(f"slots:{self.seed}:{store_id}:{d.isoformat()}")
            for h in range(cfg.open_hour + 1, cfg.close_hour - 1):
                start = datetime(d.year, d.month, d.day, h, 0, tzinfo=TZ)
                self._add(rng, store_id, "pickup", start, timedelta(hours=1), cfg.pickup_lead_min, cfg.pickup_fee_cents)
                if h % 2 == 1 and h + 2 <= cfg.close_hour:
                    self._add(rng, store_id, "delivery", start, timedelta(hours=2), cfg.delivery_lead_min, cfg.delivery_fee_cents)

    def _add(self, rng: random.Random, store: str, kind: str, start: datetime, length: timedelta, lead: int, fee: int) -> None:
        end = start + length
        jitter = timedelta(minutes=rng.randint(-15, 15))
        cap = rng.choices([0, 1, 2, 3, 4], weights=[1, 2, 3, 3, 2])[0]
        sid = f"{store}:{start.date().isoformat()}:{kind[0].upper()}{start.hour:02d}"
        self._slots[sid] = Slot(
            slot_id=sid,
            store=store,
            kind=kind,  # type: ignore[arg-type]
            start=start,
            end=end,
            ready_by=start if kind == "pickup" else end,
            cutoff=start - timedelta(minutes=lead) + jitter,
            capacity=cap,
            fee_cents=fee,
        )

    # ------------------------------------------------------------------ queries
    def _left(self, sid: str, now: datetime) -> int:
        s = self._slots[sid]
        if any(at <= now and v == sid for at, v in self._vanish):
            return 0
        held = sum(1 for h in self._holds.values() if h.slot_id == sid and not h.released and h.until > now)
        return max(0, s.capacity - self._used.get(sid, 0) - held)

    def slots(self, store: str, start: datetime, end: datetime, now: datetime, kind: str | None = None) -> Ok[SlotsResponse] | Refusal:
        if self.mode == "not_exposed":
            return Refusal(
                RefusalCode.CAPABILITY_UNAVAILABLE,
                "slots are not exposed to agents on this twin config (CAP-10 not_exposed)",
                retryable=False,
                owner_action="use K05 heuristic; status=estimated",
                evidence=[labels_for("slots.not_exposed")],
            )
        if store not in STORES:
            return Refusal(RefusalCode.INFEASIBLE, f"unknown store {store}")
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("slots() window must be timezone-aware")
        d = start.astimezone(TZ).date()
        while d <= end.astimezone(TZ).date():
            self.ensure_day(d)
            d += timedelta(days=1)
        out = []
        for s in sorted(self._slots.values(), key=lambda x: (x.start, x.kind)):
            if s.store != store or (kind and s.kind != kind):
                continue
            if s.end <= start or s.start >= end:
                continue
            left = self._left(s.slot_id, now)
            out.append(Slot(**{**s.__dict__, "capacity": left}))
        return Ok(
            SlotsResponse(slots=out, mode=self.mode, labels=labels_for("slots.read", "slots.cutoff_semantics")),
            adapter_id=f"twin.slots.{self.mode}",
        )

    def get(self, slot_id: str) -> Slot | None:
        return self._slots.get(slot_id)

    # ------------------------------------------------------------------ holds (CAP-43)
    def hold(self, slot_id: str, mandate_id: str, until: datetime, now: datetime) -> Ok[Hold] | Refusal:
        if self.mode != "holds":
            return Refusal(
                RefusalCode.CAPABILITY_UNAVAILABLE,
                f"slot holds unavailable in mode {self.mode} (CAP-43 proposed)",
                owner_action="close the poll at cutoff minus 10 minutes and re-check (read-only branch)",
            )
        s = self._slots.get(slot_id)
        if s is None or now >= s.cutoff or self._left(slot_id, now) < 1:
            return Refusal(RefusalCode.STALE, f"slot {slot_id} cannot be held", retryable=True)
        existing = [h for h in self._holds.values() if h.mandate_id == mandate_id and not h.released and h.until > now]
        for h in existing:  # one live hold per mandate, keyed by mandate_id
            h.released = True
        hid = f"hold:{mandate_id}:{slot_id}"
        h = Hold(hold_id=hid, slot_id=slot_id, mandate_id=mandate_id, until=min(until, s.cutoff))
        self._holds[hid] = h
        return Ok(h, adapter_id="twin.slots.holds")

    def release(self, hold_id: str) -> None:
        if hold_id in self._holds:
            self._holds[hold_id].released = True

    def tick(self, now: datetime) -> list[str]:
        """Release lapsed holds; returns released hold ids."""
        out = []
        for h in self._holds.values():
            if not h.released and h.until <= now:
                h.released = True
                out.append(h.hold_id)
        return out

    def live_hold(self, hold_id: str, now: datetime) -> bool:
        h = self._holds.get(hold_id)
        return bool(h and not h.released and h.until > now)

    # ------------------------------------------------------------------ checkout re-check
    def consume(self, slot_id: str, now: datetime, hold_id: str | None = None) -> Ok[Slot] | Refusal:
        """Called by HP's checkout. A slot gone at checkout is STALE, never a silent later slot."""
        s = self._slots.get(slot_id)
        if s is None:
            return Refusal(RefusalCode.STALE, f"slot {slot_id} unknown", retryable=True)
        holding = hold_id is not None and self.live_hold(hold_id, now)
        if now >= s.cutoff:
            return Refusal(RefusalCode.STALE, f"slot {slot_id} cutoff {s.cutoff.isoformat()} passed", retryable=True)
        if not holding and self._left(slot_id, now) < 1:
            return Refusal(RefusalCode.STALE, f"slot {slot_id} is full", retryable=True)
        if holding:
            assert hold_id is not None
            self._holds[hold_id].released = True
        self._used[slot_id] = self._used.get(slot_id, 0) + 1
        return Ok(s, adapter_id=f"twin.slots.{self.mode}")

    # ------------------------------------------------------------------ seeded violation
    def inject_vanish(self, slot_id: str, at: datetime) -> None:
        self._vanish.append((at, slot_id))

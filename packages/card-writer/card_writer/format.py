"""Claim value formatting for K11 cards.

Formatting lives in the writer, never in the UI: the console renders line text as given.
A claim value carries its own type, so Card@0 needs no unit field:
  money  -> {"amount": "21.40", "currency": "USD"}   (amount is a decimal string, never a float)
  time   -> "17:15" or an ISO-8601 datetime            (wall-clock, already in the store's zone)
  date   -> "2026-11-30"                               (shown as "Nov 30")
  count  -> int
  text   -> any other string (shown as is)
"""
from __future__ import annotations

import re
from decimal import Decimal

_TIME = re.compile(r"^(?:\d{4}-\d{2}-\d{2}T)?(\d{2}):(\d{2})")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def claim_type(value) -> str:
    if isinstance(value, dict) and "amount" in value and "currency" in value:
        return "money"
    if isinstance(value, bool):
        return "text"
    if isinstance(value, int):
        return "count"
    if isinstance(value, str) and _DATE.match(value):
        return "date"
    if isinstance(value, str) and _TIME.match(value):
        return "time"
    return "text"


def render_value(value) -> str:
    kind = claim_type(value)
    if kind == "money":
        amount = Decimal(str(value["amount"]))
        if value["currency"] != "USD":
            return f"{amount:,.2f} {value['currency']}"
        if amount == amount.to_integral_value():
            return f"${amount:,.0f}"
        return f"${amount:,.2f}"
    if kind == "time":
        m = _TIME.match(value)
        hour, minute = int(m.group(1)), int(m.group(2))
        suffix = "AM" if hour < 12 else "PM"
        hour12 = hour % 12 or 12
        return f"{hour12}:{minute:02d} {suffix}"
    if kind == "date":
        m = _DATE.match(value)
        return f"{_MONTHS[int(m.group(2)) - 1]} {int(m.group(3))}"
    if kind == "count":
        return str(value)
    return str(value)

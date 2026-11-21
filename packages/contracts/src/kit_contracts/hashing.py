"""Canonical JSON and hashes shared by the bundle manifest, carts and gate records.

Canonical form (Fork D, bundle-manifest-v0): sorted keys, no whitespace, UTF-8.
Datetimes serialise as ISO 8601 with offset; dataclasses as dicts; tuples as lists.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any


def _default(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise ValueError("naive datetime in canonical JSON; every time carries a zone")
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return int(obj.total_seconds())
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    raise TypeError(f"not canonical-serialisable: {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def lines_hash(lines: list[Any]) -> str:
    """Hash of a cart's lines: (sku, qty, price_cents, sponsored) sorted by sku.

    Role and lock_ok are excluded: they are the agent's claims about a line, and the
    verifier recomputes them instead of trusting them.
    """
    rows = sorted([getattr(ln, "sku", None) or ln["sku"], _get(ln, "qty"), _get(ln, "price_cents"), bool(_get(ln, "sponsored"))] for ln in lines)
    return sha256_hex(canonical_json(rows))


def _get(obj: Any, key: str) -> Any:
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)

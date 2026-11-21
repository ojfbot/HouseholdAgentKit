"""Result@0 (proposed by Fork F, components@2 `result` + `refusal_codes`).

Every component returns exactly one of Ok / Refusal / Error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar, Literal


class RefusalCode(StrEnum):
    LOCK_VIOLATION = "LOCK_VIOLATION"
    OVER_CAP = "OVER_CAP"
    OUT_OF_MANDATE = "OUT_OF_MANDATE"
    RIGHTS_DENIED = "RIGHTS_DENIED"
    PROFILE_SCOPE = "PROFILE_SCOPE"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    INFEASIBLE = "INFEASIBLE"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    STALE = "STALE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class Ok[T]:
    value: T
    trace: str | None = None
    fallback_used: bool = False
    adapter_id: str | None = None

    ok: ClassVar[Literal[True]] = True


@dataclass
class Refusal:
    code: RefusalCode
    reason: str
    retryable: bool = False
    owner_action: str | None = None
    evidence: list[Any] = field(default_factory=list)

    ok: ClassVar[Literal[False]] = False


@dataclass
class Error:
    code: str
    retryable: bool = False

    ok: ClassVar[Literal[False]] = False


Result = Ok[Any] | Refusal | Error


def expect[T](r: Ok[T] | Refusal | Error) -> T:
    """Unwrap an Ok or raise with the refusal's reason (for fixtures, checks and tests)."""
    if isinstance(r, Ok):
        return r.value
    raise AssertionError(f"expected Ok, got {r!r}")

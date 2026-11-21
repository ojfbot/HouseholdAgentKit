"""Draft contract mirror for the IQ suites (Fork I).

Fork F owns the *content* of every contract (components@2, adapters@1, Result@0 ...).
This package mirrors the Nov 19 drafts as Python types so the contract suites, the
verifier and the eval harness have something typed to run against before the Nov 22
freeze. When `packages/contracts/` schemas land at freeze, these types are regenerated
from them and any drift is a test failure, not a silent change.

Two areas are deliberately LOOSE until "Decisions batch 1" settles them (see `loose.py`):
  * Case v1        (D's lineage+split vs F's interview mode + request types)
  * Mandate v1 `standing` block (F's own vocabulary vs the published User-Defined Guardrail)
"""

from kit_contracts.hashing import canonical_json, lines_hash, sha256_hex
from kit_contracts.result import Error, Ok, Refusal, RefusalCode, Result, expect
from kit_contracts.types import (
    AttributeSet,
    Brief,
    Budget,
    Card,
    CardClaim,
    CardLine,
    CardSection,
    Cart,
    CartLine,
    Check,
    Constraint,
    Deadline,
    Headcount,
    Lock,
    Mandate,
    MemberRef,
    Offer,
    SlotPlan,
    VerifyReport,
)

__all__ = [
    "AttributeSet",
    "Brief",
    "Budget",
    "Card",
    "CardClaim",
    "CardLine",
    "CardSection",
    "Cart",
    "CartLine",
    "Check",
    "Constraint",
    "Deadline",
    "Error",
    "Headcount",
    "Lock",
    "Mandate",
    "MemberRef",
    "Offer",
    "Ok",
    "Refusal",
    "RefusalCode",
    "Result",
    "SlotPlan",
    "VerifyReport",
    "canonical_json",
    "expect",
    "lines_hash",
    "sha256_hex",
]

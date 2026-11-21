"""Card@0 guard: the checks every K11 card passes before it leaves the writer.

This is the writer-side half of the K11 oracle ("100% of numbers carry claim_ref verified by K03").
K03 still verifies the claims themselves; the guard makes sure the card cannot show a number that
is not one of those claims.
"""
from __future__ import annotations

import re

from .format import render_value
from .templates import KINDS_BY_ROLE

DIGIT = re.compile(r"\d")
# synthetic | public:<src> is the shared rule. observed:<src> is Fork H's draft for numbers the room produces
# live (votes from the QR round): neither synthetic nor public. Raised in the coordination log.
LABEL_OK = re.compile(r"^(synthetic|public:[A-Za-z0-9_.:/-]+|observed:[A-Za-z0-9_.:/-]+)$")
KINDS = {"ballot", "approval", "over_cap", "digest", "fulfiller", "support", "readback"}
MARKS = {None, "lock", "sponsored", "quote", "info", "warn", "ok"}
# IQ's K03 card rules (log Nov 19, item 6): while a slot is estimated these words fail the card;
# "confirmed at checkout" is allowed, and a line citing a slot.* claim must say "estimated" or "about".
SLOT_PROMISE = re.compile(r"\b(confirmed|guaranteed|reserved|held for you)\b", re.I)
SLOT_HEDGE = re.compile(r"\b(estimated|about)\b", re.I)


class CardRejected(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


def check_card(card: dict) -> None:
    """Raise CardRejected if the card breaks a Card@0 rule or the K11 number rule."""
    for key in ("card_id", "audience", "kind", "sections", "claims", "locale", "a11y"):
        if key not in card:
            raise CardRejected("SCHEMA", f"missing {key}")
    if card["kind"] not in KINDS:
        raise CardRejected("SCHEMA", f"unknown kind {card['kind']}")
    role = card["audience"].get("role")
    if role in KINDS_BY_ROLE and card["kind"] not in KINDS_BY_ROLE[role]:
        raise CardRejected("RIGHTS_DENIED", f"role {role} never gets a {card['kind']} card")
    if card["a11y"].get("contrast") != "AA" or not isinstance(card["a11y"].get("reading_level"), int):
        raise CardRejected("SCHEMA", "a11y needs contrast=AA and an int reading_level")

    claims = {}
    for c in card["claims"]:
        if not c.get("verified_by"):
            raise CardRejected("UNVERIFIED_CLAIM", f"claim {c.get('id')} has no verified_by")
        if not LABEL_OK.match(str(c.get("label", ""))):
            raise CardRejected("UNVERIFIED_CLAIM", f"claim {c.get('id')} has no synthetic|public:<src> label")
        claims[c["id"]] = c

    slot_estimated = card.get("slot_status", "estimated") != "confirmed"
    used = set()
    for s in card["sections"]:
        for line in s["lines"]:
            text = line["text"]
            if line.get("mark") not in MARKS:
                raise CardRejected("SCHEMA", f"unknown mark {line.get('mark')}")
            ref = line.get("claim_ref")
            if slot_estimated and SLOT_PROMISE.search(text.lower().replace("confirmed at checkout", "")):
                raise CardRejected("SLOT_OVERCLAIM", f"slot is estimated but line '{text}' promises it")
            if slot_estimated and ref and ref.startswith("slot.") and not SLOT_HEDGE.search(text):
                raise CardRejected("SLOT_OVERCLAIM", f"slot line '{text}' must say estimated or about")
            if ref is not None:
                if ref not in claims:
                    raise CardRejected("UNVERIFIED_CLAIM", f"line cites unknown claim {ref}")
                shown = render_value(claims[ref]["value"])
                if shown not in text:
                    raise CardRejected("UNVERIFIED_CLAIM", f"line '{text}' does not show claim {ref} as {shown}")
                text = text.replace(shown, "", 1)
                used.add(ref)
            if DIGIT.search(text):
                raise CardRejected("UNVERIFIED_CLAIM", f"number without a claim in '{line['text']}'")
    for a in card.get("actions", []):
        if DIGIT.search(a.get("label", "")):
            raise CardRejected("UNVERIFIED_CLAIM", f"number in action label '{a['label']}'")
    ids = [a["action_id"] for a in card.get("actions", [])]
    if len(ids) != len(set(ids)):
        raise CardRejected("SCHEMA", "duplicate action_id")
    unused = set(claims) - used
    if unused:
        raise CardRejected("SCHEMA", f"claims not shown on the card: {sorted(unused)}")

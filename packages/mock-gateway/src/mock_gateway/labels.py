"""Behaviour labels for the catalog-and-slots half of the twin.

K17 oracle: every behaviour is labeled published | inferred | invented. Fork E's sweep
(Nov 19, 4:30 AM) also uses "announced" for Agent Profiles (announced, not live); we carry
it as a fourth label and have asked F to add it to the oracle's vocabulary.

Statuses follow org@2 (fork-e) as relayed in fork-f/adapters.yaml. Nothing here is a
Walmart fact: it is our labeled guess about the Gateway, kept in one place.
"""

from __future__ import annotations

LABELS = ("published", "announced", "inferred", "invented")

BEHAVIOURS: dict[str, dict[str, str]] = {
    "catalog.discover.structured": {
        "label": "inferred",
        "cap": "CAP-07",
        "note": "price, stock and items via a structured discover(); request format unknown (H3 relies on it)",
    },
    "catalog.prices": {"label": "invented", "cap": "-", "note": "all prices synthetic"},
    "catalog.sponsored_flag": {
        "label": "invented",
        "cap": "CON-03b",
        "note": "marking sponsored items is our rule, not a published Walmart behaviour",
    },
    "catalog.packaging_version": {
        "label": "invented",
        "cap": "CAP-22",
        "note": "packaging_version diffed on every discover(); notice feed proposed only",
    },
    "usuals.account_scope": {"label": "announced", "cap": "CAP-02", "note": "account-level usuals, Oct 21 announcement"},
    "usuals.profile_scope": {"label": "invented", "cap": "CAP-21", "note": "care-profile usuals: labeled proposal"},
    "slots.read": {"label": "inferred", "cap": "CAP-10", "note": "consumer slots published; agent exposure inferred"},
    "slots.cutoff_semantics": {
        "label": "invented",
        "cap": "CAP-10",
        "note": "pickup ready at window start; delivery by window end; cutoff = start - lead +/- jitter",
    },
    "slots.hold": {"label": "invented", "cap": "CAP-43", "note": "holding a slot for an agent is proposed only"},
    "slots.not_exposed": {"label": "inferred", "cap": "CAP-10", "note": "adapter falls back to K05 heuristic"},
    "checkout.slot_recheck": {"label": "inferred", "cap": "CAP-10", "note": "slot gone at checkout -> STALE"},
}


def labels_for(*behaviour_ids: str) -> dict[str, str]:
    out = {}
    for b in behaviour_ids:
        if b not in BEHAVIOURS:
            raise KeyError(f"unlabeled twin behaviour {b!r}; add it to BEHAVIOURS")
        out[b] = BEHAVIOURS[b]["label"]
    return out

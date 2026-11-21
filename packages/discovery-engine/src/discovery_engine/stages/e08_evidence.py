"""E08 — evidence ladder + registry join (stage 6). Owner: ED (components@2). Implemented here as passthrough@0 so
run 1 has an evidence level per family; ED replaces `join` with the statements@ registry join.

Rules kept now: every ref must resolve (a fork-c REFS key or a Fork E registry id ST-###); E3 only from the owner's
recordings (ref `baseline`), otherwise downgraded to E2 and logged; families at tier >= 1 below E3 queue a manual
weak-vs-strong Sparky test for the owner.
"""
from __future__ import annotations

import re

ST_RX = re.compile(r"^ST-\d{3}$")
OWNER_RECORDINGS = {"baseline"}


def join(card: dict, refs: dict, registry_ids: set[str] | None = None) -> dict:
    registry_ids = registry_ids or set()
    level, raw = card["evidence"]["level"], card["evidence"]["refs"]
    resolved, unresolved = [], []
    for r in raw:
        (resolved if (r in refs or ST_RX.match(r) and (not registry_ids or r in registry_ids)) else unresolved).append(r)
    notes = []
    if level == "E3" and not (set(resolved) & OWNER_RECORDINGS):
        level = "E2"; notes.append("E3 downgraded: no the owner recording ref")
    if int(level[1]) >= 1 and not resolved:
        notes.append("level above E0 with no resolvable ref")
    return {"level": level, "refs": resolved, "unresolved_refs": unresolved, "synthetic": level == "E0",
            "x": {"value": int(level[1]), "label": "score:rubric@2"}, "notes": notes, "stage_impl": "passthrough@0 (owner ED)"}


def sparky_test_queue(families: list[dict]) -> list[dict]:
    q = []
    for f in families:
        if f["ladder"]["tier"] >= 1 and int(f["evidence"]["level"][1]) < 3:
            q.append({"family_id": f["family_id"], "title": f["title"], "weak_request": f["sparky_today"],
                      "strong_request": f["specific_brief"], "who": "the owner (manual Sparky test, E3)"})
    return q

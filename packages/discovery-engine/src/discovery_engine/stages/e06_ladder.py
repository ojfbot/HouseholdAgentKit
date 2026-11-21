"""E06 — value-ladder placer (stage 4). Rules decide; a model may only explain (none wired for Dec 2).

Tier rules (rubric@2 / score_v2.tier_of): tier 2 iff the family has >= 1 Gateway-only condition (a-e); else tier 1
iff the specific brief carries context Walmart lacks; else tier 0 (parity). The tier-0 rung names the in-house
surface that already covers the job (org@2 in_house_cover), so "what Sparky does today" is traceable to a COV row.
Anchors (oracle): taco night PF-51 climbs 0 -> 1 -> 2 with G-01 as its observed tier-0 rung; Care Profiles PF-28 = 2.
"""
from __future__ import annotations

from ..util import FIXTURES, load_yaml

UPLIFT_X = {0: 1.0, 1: 2.5}   # rubric@2 tier criterion: tier 0 -> 1; tier 1 -> 2.5; tier 2 -> 3 + 0.4 * conditions (max 5)


def tier_x(tier: int, n_conds: int) -> float:
    return UPLIFT_X.get(tier, min(5, 3 + 0.4 * n_conds))


def brief_carries_context(card: dict) -> bool:
    b = card["specific_brief"].strip().strip("'").lower()
    return bool(b) and not b.startswith(("n/a", "same as", "same request"))


def place(card: dict, cover: list[dict]) -> dict:
    g = card["gateway_only"]
    if g:
        tier, rule = 2, "L2 gateway_only>=1"
    elif card.get("gate_hint") == "tier1" or (card.get("gate_hint") is None and brief_carries_context(card)):
        tier, rule = 1, "L1 specific brief adds context"
    else:
        tier, rule = 0, "L0 parity"
    covered_by = [c["id"] for c in cover if card["actor_type"] in c["actors"] and (card["job"] in c["jobs"] or "all" in c["jobs"])]
    return {"tier": tier, "rule": rule, "conditions": list(g), "uplift_conditions": len(g),
            "tier_x": {"value": round(tier_x(tier, len(g)), 2), "label": "score:rubric@2"},
            "rungs": {"0": {"sparky_today": card["sparky_today"], "covered_by": covered_by},
                      "1": {"specific_brief": card["specific_brief"], "carries_context": brief_carries_context(card)},
                      "2": {"gateway_only": list(g)}}}


def load_cover(path=None) -> list[dict]:
    return load_yaml(path or FIXTURES / "fork_e" / "in_house_cover.min.yaml")["cover"]


def anchors_ok(families: dict[str, dict]) -> dict:
    """families: lineage id -> family with `ladder`. Returns C's stage-0 placement checks."""
    hw, hw0, care = families.get("PF-51"), families.get("G-01"), families.get("PF-28")
    out = {
        "tier0_baseline_observed": bool(hw and hw0 and hw["evidence"]["level"] == "E3" and hw0["ladder"]["tier"] == 0),
        "tier1_brief_present": bool(hw and hw["ladder"]["rungs"]["1"]["carries_context"]),
        "tier2_conditions": bool(hw and hw["ladder"]["tier"] == 2),
        "care_profiles_tier2": bool(care and care["ladder"]["tier"] == 2),
    }
    out["placement_pass"] = all(out.values())
    return out

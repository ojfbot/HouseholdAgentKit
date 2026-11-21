"""E16 publisher (owner DX): Readout@0 (Fork G) -> readout-view@0, the render model the stage draws.

Deterministic and server-side, so the UI never formats or combines a number. It copies ranks, tiers, cells
and clamp entries exactly as E11/E12 computed them, formats display strings from each {value, label}, and
keeps the label beside every number. Positions on the 2x2 are G's own impact and effort values (already
normalised to 0..1 by E12); the cell names are G's.
"""
from __future__ import annotations

COMPONENT_NAMES = {
    "K01": "Intent parser", "K02": "Sparky brief writer", "K03": "Constraint verifier", "K04": "Cart solver", "K05": "Deadline-to-slot",
    "K06": "Household rules and rights", "K07": "Profile scopes", "K08": "Standing mandate guard", "K09": "Trigger gateway",
    "K10": "Poll and decision", "K11": "Role-scoped cards", "K12": "Ledger", "K13": "On-hand state", "K14": "Change notices",
    "K15": "Fulfiller handoff", "K16": "Catalog attributes", "K18": "Support view", "K19": "Fairness harness", "K20": "Conformance suite",
    "K21": "Need-list builder", "K22": "Feedback interpreter", "K24": "ShoppingPort adapters",
}
TIER_WORDS = {0: "Tier 0 · parity with Sparky", 1: "Tier 1 · a better brief", 2: "Tier 2 · only through the Gateway"}
CELL_WORDS = {"quick_win": "Quick win", "big_bet": "Big bet", "fill_in": "Fill-in", "deprioritize": "Deprioritize"}


def money_per_year(usd) -> str:
    usd = float(usd)
    if usd >= 1_000_000_000:
        return f"${usd / 1_000_000_000:.1f}B/yr"
    if usd >= 10_000_000:
        return f"${usd / 1_000_000:.0f}M/yr"
    return f"${usd / 1_000_000:.1f}M/yr".replace(".0M", "M")


def _tier(v) -> int:
    return int(round(float(v["value"] if isinstance(v, dict) else v)))


def view_from_g(ro: dict, *, function_words: str | None = None, delta: dict | None = None, source: str = "live") -> dict:
    claims, portfolio = [], []
    for row in ro["top_k"]:
        vas = row["value_at_stake_usd"]
        cid = f"vas.{row['family_id']}"
        claims.append({"id": cid, "value": vas["value"], "display": money_per_year(vas["value"]), "label": vas["label"],
                       "verified_by": f"{ro['bank_id']}#{ro['readout_hash']}/top_k/{row['family_id']}/value_at_stake_usd"})
        portfolio.append({"rank": row["rank"], "family_id": row["family_id"], "title": row["title"], "tier": _tier(row["tier"]),
                          "owners": [], "owned": False, "protected": [], "vas_claim": cid,
                          "moved": row.get("moved"), "new": row.get("moved") is None and row["family_id"].startswith("NF-")})
    by_tier: dict[int, list] = {0: [], 1: [], 2: []}
    for p in portfolio:
        by_tier.setdefault(p["tier"], []).append({"family_id": p["family_id"], "title": p["title"], "anchor": False, "in_portfolio": True})
    ladder = [{"tier": t, "label": TIER_WORDS.get(t, f"Tier {t}"), "families": by_tier.get(t, [])} for t in (0, 1, 2)]
    tbt = ro.get("two_by_two") or {}
    rank = {p["family_id"]: p["rank"] for p in portfolio}
    points = [{"family_id": pt["family_id"], "short": pt["family_id"], "pos": {"x": float(pt["effort"]), "y": float(pt["impact"])},
               "quadrant": pt["cell"], "in_portfolio": pt["family_id"] in rank, "anchor": False, "vas_claim": f"vas.{pt['family_id']}"}
              for pt in tbt.get("points", [])]
    clamps = [{"family_id": c["family_id"], "dimension": c.get("term"), "attempted_weight": c.get("asked"), "floor": c.get("applied"),
               "code": c.get("code")} for c in ro.get("clamp_log", [])]
    if clamps:
        claims.append({"id": "clamps.count", "value": len(clamps), "display": str(len(clamps)), "label": "synthetic",
                       "verified_by": f"{ro['bank_id']}#{ro['readout_hash']}/clamp_log"})
    have = {c["id"] for c in claims}
    for pt in points:  # 2x2 points outside the top-k still need a claim for their tooltip
        if pt["vas_claim"] not in have:
            pt["vas_claim"] = None
    view = {
        "version": "readout-view@0", "kind": "portfolio", "source": source, "view_id": f"rv_{ro['readout_hash'][:12]}",
        "run_id": ro["run_id"], "bank_id": ro["bank_id"], "bundle_id": None,
        "hello_world": {"status": ro.get("hello_world")},
        "profile": {"profile_id": ro["profile_id"], "function": function_words or ro["profile_id"], "lens": ro["lens"]},
        "hypothesis": ro.get("hypothesis"), "answer_first": ro["answer_first"], "portfolio": portfolio, "ladder": ladder,
        "quad": {"axes_provisional": False, "x": {"key": "effort", "label": "Build effort (E14)"}, "y": {"key": "impact", "label": "Impact (priority)"},
                 # corners as the renderer names them (x = effort, y = impact): top-right, bottom-right, top-left, bottom-left
                 "quadrants": {"build": CELL_WORDS["big_bet"], "prove": CELL_WORDS["deprioritize"], "quick_proof": CELL_WORDS["quick_win"],
                               "park": CELL_WORDS["fill_in"]}, "points": points} if points else None,
        "clamps": clamps, "claims": claims, "drill": {}, "moved_in": ro.get("moved_in", []), "moved_out": ro.get("moved_out", []),
        "compute_ms": ro.get("compute_ms"), "readout_hash": ro["readout_hash"],
    }
    if delta:
        view["delta"] = delta_view(delta, ro)
    return view


def delta_view(ev: dict, ro: dict | None = None) -> dict:
    return {"delta_id": ev["delta_id"], "change": {"kind": ev["op"], "from": ev.get("prev"), "to": ev.get("applied")},
            "status": ev["status"], "codes": ev.get("codes", []), "recompute_ms": (ro or {}).get("compute_ms"),
            "adapter_id": "engine.http@E11", "hash": ev.get("hash")}


def drill_from_g(fam: dict) -> dict:
    """GET /family/<id> -> the drill panel. Defensive about fields G hasn't frozen yet."""
    comps = fam.get("components") or []
    vas = fam.get("value_at_stake_usd") or {}
    return {
        "title": fam.get("title", fam.get("family_id", "")), "tier": _tier(fam["tier"]) if "tier" in fam else None,
        "evidence": (fam.get("evidence") or {}).get("level") if isinstance(fam.get("evidence"), dict) else fam.get("evidence"),
        "protected": fam.get("protected", []), "owners": fam.get("business_owners", []),
        "vas": {"display": money_per_year(vas["value"]), "label": vas["label"]} if vas else None,
        "components": [{"id": k, "name": COMPONENT_NAMES.get(k, k)} for k in comps], "enhance": fam.get("enhance", []),
        "adapters": fam.get("adapters", fam.get("unconfirmed_caps", [])), "demo_beat": {"PF-51": 1, "PF-28": 3}.get(fam.get("family_id")),
    }

"""Build draft Readout@0 fixtures for beat 2 (engine map) from the run-0 bank extract.

A projection only: ranks, tiers, scores and clamps are copied from the bank as Fork C's run 0 wrote them.
Nothing is re-ranked or re-weighted here; that is E11/E12 (Fork G). The only work done is E16's: format
display strings, attach labels, and lay out the page (answer-first line, 2x2 positions from the bank's
own rubric scores, drill-down lists).

Run: python3 fixtures/build_engine_fixtures.py   (writes fixtures/engine/readout.*.json and deltas.json)
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent / "engine"
OWNER_WORDS = {"mkt": "Marketing", "sc": "Supply chain", "prod": "Product", "care": "Customer care", "fin": "Finance", "b2b": "B2B",
               "partner": "Partnerships", "tns": "Trust & safety", "merch": "Merchandising", "ops": "Store ops", "mp": "Marketplace", "ads": "Ads"}
TIER_WORDS = {0: "Tier 0 · parity with Sparky", 1: "Tier 1 · a better brief", 2: "Tier 2 · only through the Gateway"}
SCALE = 5.0  # rubric@2 scores run 0-5


def money_per_year(usd: int) -> str:
    if usd >= 1_000_000_000:
        return f"${usd / 1_000_000_000:.1f}B/yr"
    if usd >= 10_000_000:
        return f"${usd / 1_000_000:.0f}M/yr"
    return f"${usd / 1_000_000:.1f}M/yr".replace(".0M", "M")


def vas_claim(fam: dict, bank_id: str) -> dict:
    src = fam["segment_src"]
    note = f"segment size public:{src[2:]}" if src.startswith("S:") else "all inputs synthetic"
    return {"id": f"vas.{fam['id']}", "value": fam["vas"], "display": money_per_year(fam["vas"]), "label": "synthetic",
            "note": note, "verified_by": f"{bank_id}#families/{fam['id']}/value_at_stake"}


def quadrant(x: float, y: float) -> str:
    return {(True, True): "build", (True, False): "prove", (False, True): "quick_proof", (False, False): "park"}[(x >= 0.5, y >= 0.5)]


def readout(bank: dict, profile_id: str) -> dict:
    fams = bank["families"]
    prof = bank["profiles"][profile_id]
    ranked = sorted((f for f in fams if f["top10"].get(profile_id)), key=lambda f: f["top10"][profile_id])
    claims, portfolio = [], []
    for f in ranked:
        c = vas_claim(f, bank["bank_id"])
        claims.append(c)
        portfolio.append({"rank": f["top10"][profile_id], "family_id": f["id"], "title": f["title"], "tier": f["tier"],
                          "owners": [OWNER_WORDS[o] for o in f["owners"]], "owned": prof["owner"] in f["owners"] if prof["owner"] else False,
                          "protected": f["protected"], "vas_claim": c["id"]})
    have = {c["id"] for c in claims}
    claims += [vas_claim(f, bank["bank_id"]) for f in fams if f"vas.{f['id']}" not in have]
    ladder = [{"tier": t, "label": TIER_WORDS[t], "families": [{"family_id": f["id"], "title": f["title"], "anchor": f["anchor"],
                                                                    "in_portfolio": bool(f["top10"].get(profile_id))} for f in fams if f["tier"] == t]}
              for t in (0, 1, 2)]
    points = []
    for f in fams:
        x, y = round(f["s_vas"] / SCALE, 3), round(f["s_ev"] / SCALE, 3)
        points.append({"family_id": f["id"], "short": f["title"][:34], "pos": {"x": x, "y": y}, "quadrant": quadrant(x, y),
                       "in_portfolio": bool(f["top10"].get(profile_id)), "anchor": f["anchor"], "vas_claim": f"vas.{f['id']}"})
    clamps = [{"family_id": fid, "dimension": dim, "attempted_weight": w, "floor": 1.0} for fid, dim, w in bank["floor_clamps"].get(profile_id, [])]
    if clamps:
        claims.append({"id": "clamps.count", "value": len(clamps), "display": str(len(clamps)), "label": "synthetic",
                       "verified_by": f"{bank['bank_id']}#control_sanity/{profile_id}/floor_clamps"})
    top = ranked[0]
    top_c = next(c for c in claims if c["id"] == f"vas.{top['id']}")
    answer = f"Under {prof['function']}, the top cell is “{top['title']}”, {top_c['display']} at stake (synthetic)."
    drill = {}
    for f in fams:
        comp = bank["components"].get(f["id"])
        drill[f["id"]] = {
            "title": f["title"], "tier": f["tier"], "evidence": f["evidence"], "protected": f["protected"],
            "owners": [OWNER_WORDS[o] for o in f["owners"]], "vas_claim": f"vas.{f['id']}",
            "components": [{"id": k, "name": bank["component_names"].get(k, k)} for k in comp["components"]] if comp else None,
            "enhance": comp["enhance"] if comp else [], "adapters": comp["adapters"] if comp else [],
            "demo_beat": f.get("demo_beat"),
        }
    body = {
        "version": "readout-view@0",
        "kind": "portfolio",
        "source": "fixture",
        "run_id": bank["run_id"], "bank_id": bank["bank_id"], "bundle_id": None,
        "hello_world": {"status": "placement_only", "note": bank["hello_world"]["live_agent_smoke_test"]},
        "profile": {"profile_id": profile_id, "function": prof["function"], "lens": "in_house", "question": prof.get("question")},
        "hypothesis": {"status": "none_in_run_0", "note": "E03 freezes a Day-1 hypothesis from run 1"},
        "answer_first": answer,
        "portfolio": portfolio,
        "ladder": ladder,
        "quad": {"axes_provisional": True,  # run 0 has no E14 effort per family yet; G's live readout uses impact x effort
                 "x": {"key": "scores.value_at_stake", "label": "Value at stake (rubric score)"},
                 "y": {"key": "scores.evidence", "label": "Evidence today (rubric score)"},
                 "quadrants": {"build": "Build now", "prove": "Prove first", "quick_proof": "Quick proof", "park": "Park"},
                 "points": points},
        "clamps": clamps,
        "claims": claims,
        "drill": drill,
        "synthetic_label": bank["synthetic_label"],
    }
    body["view_id"] = "rv_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:12]
    return body


def pending_partner(bank: dict) -> dict:
    return {"version": "readout-view@0", "kind": "pending", "source": "fixture", "view_id": "rv_partner_pending",
            "run_id": bank["run_id"], "profile": {"profile_id": "partner_default", "function": "Partner builders", "lens": "partner"},
            "answer_first": "The partner lens arrives with run 1 (Fork G, Nov 25): opportunity map and conformance checklist.",
            "portfolio": [], "ladder": [], "quad": None, "clamps": [], "claims": [], "drill": {},
            "pending": {"needs": ["E11 lens", "E16 partner readouts", "K20 conformance results"], "eta": "2026-11-25"}}


def main():
    bank = json.loads((HERE / "bank-run0-extract.json").read_text())
    outs = {}
    for pid in bank["profiles"]:
        ro = readout(bank, pid)
        outs[pid] = ro["view_id"]
        (HERE / f"readout.{pid}.json").write_text(json.dumps(ro, indent=1) + "\n")
    partner = pending_partner(bank)
    (HERE / "readout.partner.json").write_text(json.dumps(partner, indent=1) + "\n")
    deltas = {"_fixture": "Flips as Fork G's ControlDelta@0 requests (POST /delta). The fixture port answers with the stored view for the target and a G-shaped event; the live port calls G's E11 API.",
              "readouts": {**{pid: f"readout.{pid}.json" for pid in bank["profiles"]}, "partner": "readout.partner.json"},
              "flips": [
                  {"label": "Marketing / CRM", "request": {"op": "switch", "path": [], "value": "marketing_crm"}},
                  {"label": "Supply chain", "request": {"op": "switch", "path": [], "value": "supply_chain"}},
                  {"label": "Balanced", "request": {"op": "switch", "path": [], "value": "default"}},
                  {"label": "Partner lens", "request": {"op": "lens", "path": [], "value": "partner"}},
              ]}
    (HERE / "deltas.json").write_text(json.dumps(deltas, indent=1) + "\n")
    print(json.dumps(outs))


if __name__ == "__main__":
    main()

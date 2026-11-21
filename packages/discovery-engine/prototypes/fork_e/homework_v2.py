"""Homework H1-H5 for the run-0 families against org@2 (Fork E). Port of fork-c/homework.py.
Run from fork-e/:  python3 homework_v2.py   -> prints summary, writes homework_v2.json
Also runs the same H1 mapping against the org@1 status snapshot (org1/capabilities.yaml) to report what changed."""
import json, yaml
from collections import Counter
from families_run0 import F

ORG = "org-model-v2/walmart/"
caps = {c["id"]: c for c in yaml.safe_load(open(ORG + "capabilities.yaml"))["capabilities"]}
cov = {c["id"]: c for c in yaml.safe_load(open(ORG + "in_house_cover.yaml"))["cover"]}
con = {c["id"]: c for c in yaml.safe_load(open(ORG + "constraints.yaml"))["constraints"]}
sp = yaml.safe_load(open(ORG + "stated_priorities.yaml"))
pri = {p["id"]: p for p in sp["priorities"]}
align = sp["family_alignment"]
caps1 = {c["id"]: c for c in yaml.safe_load(open("org1/capabilities.yaml"))["capabilities"]}
REG = {r["id"] for r in yaml.safe_load(open("statements.yaml"))["statements"]}

# component -> capabilities it relies on (org@2). Changes from org@1 are commented.
KCAP = {"K02": ["CAP-07", "CAP-27"],
        "K05": ["CAP-10", "CAP-43"],            # org@1: CAP-10 only; slot hold split out
        "K07": ["CAP-02"], "K08": ["CAP-02", "CAP-29", "CAP-03"],   # guardrail is the published standing limit
        "K10": ["CAP-03"], "K12": ["CAP-03", "CAP-30"],             # mandate record is published
        "K15": ["CAP-23"], "K14": ["CAP-22"], "K18": ["CAP-25", "CAP-30"], "K17": ["CAP-26"],
        "K20": ["CAP-05"]}                      # parity is measured against published Sparky
KCAP1 = {"K02": ["CAP-07", "CAP-27"], "K05": ["CAP-10"], "K07": ["CAP-02"], "K08": ["CAP-02"], "K10": ["CAP-03"], "K12": ["CAP-03"],
         "K15": ["CAP-23"], "K14": ["CAP-22"], "K18": ["CAP-25"], "K17": ["CAP-26"]}
FCAP = {"PF-28": ["CAP-21"], "PF-30": ["CAP-21"], "PF-31": ["CAP-21"], "PF-36": ["CAP-21", "CAP-19"], "PF-39": ["CAP-28", "CAP-14"], "PF-44": ["CAP-28"],
        "PF-22": ["CAP-14"], "PF-40": ["CAP-28"], "PF-43": ["CAP-28", "CAP-17"], "PF-45": ["CAP-17", "CAP-14"], "PF-50": ["CAP-24", "CAP-35"], "PF-37": ["CAP-13"],
        "PF-01": ["CAP-12", "CAP-11"], "PF-16": ["CAP-18"], "PF-32": ["CAP-20"], "PF-34": ["CAP-08", "CAP-33"], "PF-38": ["CAP-09"], "PF-42": ["CAP-15"],
        "G-04": ["CAP-16"], "PF-08": ["CAP-16"], "G-01": ["CAP-05"], "G-02": ["CAP-05"], "G-03": ["CAP-06", "CAP-31"], "G-07": ["CAP-05", "CAP-08"],
        "PF-49": ["CAP-34"], "PF-41": ["CAP-12"], "G-06": ["CAP-05"], "PF-15": ["CAP-18"], "PF-33": ["CAP-38"]}
FCAP1 = {k: [c for c in v if c in caps1] for k, v in FCAP.items()}
COVER = {"shopper": "COV-01", "never_shopper": "COV-11", "caregiver": "COV-08", "marketplace_seller": "COV-02", "supplier_brand": "COV-02",
         "store_associate": "COV-03", "spark_driver": "COV-09", "community_org": "COV-04", "small_business": "COV-04"}
# H2 partial overlaps: (trigger, published row, what to do). Trigger is a component or a capability.
OVERLAPS = [
 ("CAP-21", "CAP-29", "category and spend limits per profile: reuse the published User-Defined Guardrail; the ask is only per-person scope, pinned ship-to, requested-by"),
 ("K08", "CAP-29", "standing mandate + guard: build on the User-Defined Guardrail and Agent Mandate; do not define a parallel limit vocabulary"),
 ("K12", "CAP-30", "ledger/audit chain: send Walmart's signed mandates and consent records; our ledger is the household side only"),
 ("K13", "CAP-31", "on-hand memory: Walmart already finds usuals without exposing history; claim only the cross-store on-hand part"),
 ("K16", "CAP-20", "attribute resolver: Walmart's catalog pipeline exists; claim only rule-matching (allergens, eligibility) on top"),
 ("CAP-06", "CAP-06", "reorder and replenishment are live in Sparky: tier-0/1 reorder is parity, not news"),
]
BASE = ["CON-01", "CON-02", "CON-03a", "CON-03b", "CON-05", "CON-06", "CON-08", "CON-09", "CON-13", "CON-15", "CON-16", "CON-19", "CON-20", "CON-21"]

def first(s): return str(s).split(" ")[0]

def run(caps_, kcap, fcap):
    out, asks, inferred, exp = {}, Counter(), Counter(), Counter()
    for (fid, title, actor, prot, tier, gw, comps, top, anchor) in F:
        c = {"CAP-01", "CAP-03", "CAP-04"}
        for k in comps.split(): c |= set(kcap.get(k, []))
        c |= set(fcap.get(fid, []))
        c = {x for x in c if x in caps_}
        st = {x: first(caps_[x]["status"]) for x in c}
        ex = {x: first(caps_[x].get("exposed_to_outside_agents", caps_[x].get("exposed"))) for x in c}
        for x in c:
            if st[x] in ("proposed", "absent"): asks[x] += 1
            if st[x] == "inferred": inferred[x] += 1
            exp[ex[x]] += 1
        out[fid] = {"title": title, "actor": actor, "tier": tier, "gateway_only": gw, "components": comps.split(),
                    "top": bool(any(t for t in top) or anchor), "capabilities": sorted(c), "statuses": st, "exposure": ex}
    return out, asks, inferred, exp

out, asks, inferred, exp = run(caps, KCAP, FCAP)
out1, asks1, inferred1, exp1 = run(caps1, KCAP1, FCAP1)

def fams(o, pred): return sum(1 for v in o.values() if any(pred(v, x) for x in v["capabilities"]))
summary_h1 = {
 "families": len(out), "all_resolved": all(x in caps for v in out.values() for x in v["capabilities"]),
 "relying_on_proposed_or_absent": {"org1": fams(out1, lambda v, x: v["statuses"][x] in ("proposed", "absent")),
                                   "org2": fams(out, lambda v, x: v["statuses"][x] in ("proposed", "absent"))},
 "relying_on_inferred_status": {"org1": fams(out1, lambda v, x: v["statuses"][x] == "inferred"),
                                "org2": fams(out, lambda v, x: v["statuses"][x] == "inferred")},
 "relying_on_unknown_exposure": {"org1": fams(out1, lambda v, x: v["exposure"][x] == "unknown"),
                                 "org2": fams(out, lambda v, x: v["exposure"][x] == "unknown")},
 "relying_on_beta_exposure_org2": fams(out, lambda v, x: v["exposure"][x] == "beta"),
 "asks_to_walmart": dict(sorted(asks.items())), "inferred_org2": dict(inferred), "inferred_org1": dict(inferred1),
 "exposure_mentions_org2": dict(exp)}

# H1b: every org@2 row cites registry rows that exist
bad_src = [(t, r["id"], s) for t, rows in (("cap", caps), ("cov", cov), ("con", con)) for r in rows.values() for s in r.get("sources", []) if s not in REG]
bad_src += [("pri", p["id"], s) for p in pri.values() for s in p["evidence"] if s not in REG]
unsourced = [r["id"] for rows in (caps, cov, con) for r in rows.values() if not r.get("sources")]
published_without_source = [c["id"] for c in caps.values() if c["status"] == "published" and not c["sources"]]

# H2
h2_flags, h2_warn = [], []
for fid, v in out.items():
    for trig, row, note in OVERLAPS:
        hit = trig in v["components"] or trig in v["capabilities"]
        if hit and not (trig == "CAP-06" and v["tier"] >= 2):
            h2_warn.append({"family": fid, "trigger": trig, "covered_by": row, "note": note})
    # hard flag: a family whose distinctive value rests only on published, exposed capabilities and no gateway-only condition, but claims tier >= 1
    if v["tier"] >= 1 and not v["gateway_only"] and all(v["statuses"][x] == "published" and v["exposure"][x] in ("yes",) for x in v["capabilities"]
                                                         if x not in ("CAP-01", "CAP-03", "CAP-04")):
        h2_flags.append({"family": fid, "why": "tier >= 1 with no gateway-only condition and only published, exposed capabilities"})

# H3: constraint conflicts
h3 = []
for fid, v in out.items():
    if "unattended" in v["gateway_only"] and "K08" not in v["components"]:
        h3.append({"family": fid, "row": "CON-15", "why": "unattended action without a standing mandate inside the User-Defined Guardrail"})
    if v["actor"] == "spark_driver" and "K15" not in v["components"]:
        h3.append({"family": fid, "row": "CON-11", "why": "driver family without a fulfiller-handoff contract"})
per_family_cons = {}
for (fid, title, actor, prot, *_r) in F:
    cs = list(BASE)
    if "food_sensitive" in prot: cs.append("CON-07")
    if "benefits" in prot: cs.append("CON-10")
    if actor == "spark_driver": cs.append("CON-11")
    if "unattended" in out[fid]["gateway_only"]: cs += ["CON-17", "CON-18"]
    for x in cs: assert x in con, x
    per_family_cons[fid] = sorted(set(cs))

# H4
no_cover = sorted({v["actor"] for v in out.values() if v["actor"] not in COVER})
for a, c in COVER.items(): assert c in cov, c

# H5
h5_fail, h5_rows = [], {}
for fid, v in out.items():
    if not v["top"]: continue
    a = align.get(fid, {"serves": []})
    walmart = [p for p in a["serves"] if p.startswith("PW")]
    partner = [p for p in a["serves"] if p.startswith("PP")]
    if not a["serves"] and not a.get("unnamed_need"): h5_fail.append(fid)
    h5_rows[fid] = {"title": v["title"], "walmart_stated": walmart, "partner_stated": partner,
                    "walmart_alignment": round(sum(pri[p]["weight"] for p in walmart), 2),
                    **({"unnamed_need": a["unnamed_need"]} if a.get("unnamed_need") else {})}
pri_use = Counter(p for fid in h5_rows for p in align[fid]["serves"])
unserved = [p for p in pri if p not in pri_use]

res = {"org_model_version": "org@2",
       "H1_traceable": {**summary_h1, "bad_registry_refs": bad_src, "rows_without_sources": unsourced,
                        "published_caps_without_registry_source": published_without_source},
       "H2_no_reinvention": {"flags": len(h2_flags), "flag_list": h2_flags, "warnings": len(h2_warn),
                             "warnings_by_trigger": dict(Counter(w["trigger"] for w in h2_warn)), "warning_list": h2_warn},
       "H3_constraint_conflicts": len(h3), "H3_list": h3,
       "H4_tier0_baseline_cited": sum(1 for v in out.values() if v["actor"] in COVER), "H4_no_cover_actor_types": no_cover,
       "H5_stated_alignment": {"top_families": len(h5_rows), "fail": h5_fail, "pass": not h5_fail,
                               "with_unnamed_need": [f for f, r in h5_rows.items() if "unnamed_need" in r],
                               "priorities_served_by_top_families": dict(pri_use.most_common()),
                               "stated_priorities_no_top_family_serves": unserved, "per_family": h5_rows},
       "per_family": {fid: {**v, "constraints": per_family_cons[fid], "cover": COVER.get(v["actor"], "none")} for fid, v in out.items()}}
json.dump(res, open("homework_v2.json", "w"), indent=1)
ok = (summary_h1["all_resolved"] and not bad_src and not h2_flags and not h3 and not h5_fail)
print(json.dumps({k: (v if k not in ("H2_no_reinvention", "H5_stated_alignment") else {kk: vv for kk, vv in v.items() if kk not in ("warning_list", "per_family")})
                  for k, v in res.items() if k != "per_family"}, indent=1))
print("ALL PASS" if ok else "FAIL")

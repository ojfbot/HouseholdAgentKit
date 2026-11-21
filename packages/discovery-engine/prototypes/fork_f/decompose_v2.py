"""Decomposition stage v2 (Fork F). Successor to fork-c/decompose.py.

Stage contract
  in : problem cards (run bank), components@2 (catalog + needs@1), adapters@1, org@ capability statuses
  out: per family -> component set with provenance, capability risk, adapters; catalog stats; DAG-aware build
       order; evals (truth, reuse, unlock, stability, phantom). Deterministic: no model is called here.
       New components are only ever *proposed* (proposals[]), never added to the catalog by this stage.

Run: python3 decompose_v2.py   (reads bank_features.py, components-v2.yaml, adapters.yaml)
"""
import json, re, yaml, datetime as dt
from collections import defaultdict
from bank_features import FAMILIES, O, U, C, P, R

CAT = yaml.safe_load(open("components-v2.yaml"))
K = CAT["components"]
ADP = yaml.safe_load(open("adapters.yaml"))["capabilities"]
NEEDS = CAT["needs"]
ENHANCE = {"feedback_edits"}  # needs that improve a family but never gate its unlock
EFF = {"S": 1, "M": 2, "L": 3}
eff = lambda k: EFF[str(K[k]["effort"]).strip()[0]]
PRODUCT = [k for k, v in K.items() if v["layer"] == "product"]
PLATFORM = [k for k, v in K.items() if v["layer"] != "product"]

# org@1 statuses for the capabilities the catalog references (fork-c/org-model/walmart/capabilities.yaml)
CAP = {"CAP-01": ("published", "beta"), "CAP-02": ("published", "yes"), "CAP-03": ("published", "yes"),
       "CAP-04": ("published", "yes"), "CAP-05": ("published", "no"), "CAP-07": ("inferred", "unknown"),
       "CAP-10": ("published", "unknown"), "CAP-12": ("published", "unknown"), "CAP-13": ("published", "unknown"),
       "CAP-14": ("published", "unknown"), "CAP-17": ("published", "yes"), "CAP-19": ("published", "no"),
       "CAP-20": ("published", "no"), "CAP-21": ("proposed", "n/a"), "CAP-22": ("proposed", "n/a"),
       "CAP-23": ("proposed", "n/a"), "CAP-24": ("proposed", "n/a"), "CAP-25": ("proposed", "n/a"),
       "CAP-26": ("absent", "n/a"), "CAP-27": ("proposed", "n/a"), "CAP-28": ("proposed", "n/a")}
confirmed = lambda c: CAP[c][0] == "published" and CAP[c][1] in ("yes", "beta")

# ------------------------------------------------------------------ v1, reproduced exactly (fork-c/decompose.py)
V1_LANE = {"brief": "K02", "mandate": "K08", "trigger": "K09", "poll": "K10", "card": "K11", "solver": "K04", "verify": "K03", "ledger": "K12", "notice": "K14"}
V1_COND = {O: ["K09"], U: ["K08"], P: ["K10", "K11"], R: ["K04", "K05", "K12"], C: ["K06"]}
V1_EXTRA = {"PF-02": ["K14", "K16"], "PF-33": ["K14", "K16", "K15"], "PF-35": ["K15", "K16"], "PF-37": ["K15"], "PF-36": ["K15", "K07"],
            "PF-11": ["K13"], "PF-15": ["K13", "K14"], "PF-25": ["K13"], "G-03": ["K13"], "PF-04": ["K13"], "PF-32": ["K16"], "PF-46": ["K17"],
            "PF-48": ["K18", "K07"], "PF-50": ["K05", "K19"], "PF-28": ["K07"], "PF-30": ["K07"], "PF-31": ["K07"], "PF-05": ["K07"], "PF-23": ["K07"],
            "PF-01": ["K16", "K19"], "PF-41": ["K16", "K19", "K07"], "PF-39": ["K07"], "PF-44": ["K07"], "PF-22": ["K07"], "PF-40": ["K07"], "PF-43": ["K07"],
            "PF-12": ["K05", "K19"], "G-06": ["K19"], "PF-29": ["K07", "K18"], "PF-09": ["K07"], "PF-08": ["K07"], "PF-47": ["K02"]}
def v1_set(f):
    c = {"K01", "K20"}
    if f["value_tier"] >= 1: c |= {"K02", "K03"}
    for g in f["gateway_only"]: c |= set(V1_COND[g])
    for l in f["lanes_to_tune"]: c.add(V1_LANE[l])
    return c | set(V1_EXTRA.get(f["id"], []))

# ------------------------------------------------------------------ v2 rules: card -> needs@1 (each rule has an id)
LANE_NEED = {"brief": "specific_brief", "mandate": "standing_mandate", "trigger": "outside_trigger", "poll": "group_decision",
             "card": "role_card", "solver": "solve_cart", "verify": "verify", "ledger": "ledger", "notice": "change_notice"}
COND_NEED = {O: ["outside_trigger"], U: ["standing_mandate"], P: ["group_decision", "role_card"],
             R: ["solve_cart", "slot_deadline", "ledger"], C: ["household_rules"]}
NEED_LIST_JOBS = {"feed", "prepare", "host_or_celebrate", "set_up_a_home", "give_or_donate", "recover", "school",
                  "manage_group_money", "run_a_small_business"}
CUES = {  # weak text cues (run-0 backfill only; from run 1 the judge fills needs[] on the card)
    "on_hand": r"on[- ]hand|pantry memory|net of|minus on|what's short|cleaner's count",
    "item_attributes": r"allergen|SNAP|eligib|UPC|voucher|packaging|listing",
    "support_view": r"who approved|\btrace\b|co-signed",
    "scoped_principal": r"account holder|recipient|requested-by|ship-to|addresses",
}
def needs_of(f, use_text=True):
    n = {}
    def add(key, rule): n.setdefault(key, rule)
    add("parse_intent", "R0 always"); add("walmart_io", "R0 always")
    if f["value_tier"] >= 1: add("specific_brief", "R1 tier>=1"); add("verify", "R1 tier>=1")
    for g in f["gateway_only"]:
        for key in COND_NEED[g]: add(key, f"R2 gateway_only:{g}")
    for l in f["lanes_to_tune"]: add(LANE_NEED[l], f"R3 lane:{l}")
    g, a, role = set(f["gateway_only"]), f["actor_type"], f["role_in_order"]
    if role in ("requester", "approver_payer"): add("scoped_principal", "R4 role:" + role)
    if a in ("community_org", "caregiver") and g & {P, U}: add("scoped_principal", "R4 org/caregiver principal")
    if a == "small_business" and P in g: add("scoped_principal", "R4 business approver")
    if f["cluster"] in ("custody", "care") and P in g: add("scoped_principal", "R4 multi-home")
    if f["trigger"] in ("recall_notice", "packaging_or_recipe_change"): add("change_notice", "R5 notice trigger")
    if role == "fulfiller": add("fulfiller_note", "R6 fulfiller")
    if "food_sensitive" in f["protected"] or a in ("marketplace_seller", "supplier_brand"): add("item_attributes", "R7 lock/listing")
    if set(f["protected"]) & {"benefits", "low_access", "language"}: add("fairness_floor", "R8 protected segment")
    if a == "walmart_team" and f["job"] == "protect_someone": add("support_view", "R9 support")
    if a == "agent_builder": add("conformance", "R10 partner conformance")
    if f["job"] in NEED_LIST_JOBS and f["value_tier"] >= 1 and R in g and a not in ("agent_builder", "walmart_team"):
        add("need_list", "R11 occasion/checklist")
    if "poll" in f["lanes_to_tune"] and P in g: add("feedback_edits", "R12 member requests")
    if use_text:
        for key, rx in CUES.items():
            if re.search(rx, f["text"], re.I): add(key, f"T:{key}")
    return n

def closure(comps):
    """Runtime-dependency closure restricted to product + K19/K20 (platform is a shared prerequisite)."""
    out, stack = set(comps), list(comps)
    while stack:
        for d in K[stack.pop()]["deps"]:
            if K[d]["layer"] == "product" and d not in out: out.add(d); stack.append(d)
    return out

def decompose(f, use_text=True):
    n = needs_of(f, use_text)
    direct = {NEEDS[k]: r for k, r in n.items() if k not in ENHANCE}
    full = closure(direct)
    enh = sorted({NEEDS[k] for k in n if k in ENHANCE} - full)
    prov = {c: direct.get(c, "closure") for c in full}
    caps = sorted({cap for c in full for cap in K[c]["caps"]})
    risky = [cap for cap in caps if not confirmed(cap)]
    adapters = sorted({cap for cap in risky if cap in ADP})
    return {"components": sorted(full), "enhance": enh, "needs": sorted(n), "provenance": prov, "caps": caps,
            "unconfirmed_caps": risky, "adapters": adapters}

FAM = {f["id"]: f for f in FAMILIES}
D2 = {i: decompose(f) for i, f in FAM.items()}
D2s = {i: decompose(f, use_text=False) for i, f in FAM.items()}
V1 = {i: v1_set(f) - {"K20", "K17"} for i, f in FAM.items()}  # compare product layer only
jac = lambda a, b: len(a & b) / len(a | b) if a | b else 1.0

# ------------------------------------------------------------------ evals
need = defaultdict(list)
for i, d in D2.items():
    for c in d["components"]: need[c].append(i)
reuse = {k: len(need[k]) for k in sorted(need, key=lambda x: (-len(need[x]), x))}
prod_reuse = [len(need[k]) for k in PRODUCT]
seen, curve = set(), []
for f in FAMILIES:  # bank order = rank order
    new = set(D2[f["id"]]["components"]) - seen; seen |= new; curve.append(len(new))
phantom = []
for k, v in K.items():
    grounded = bool(v["caps"]) or bool(v.get("from"))
    used = v["layer"] != "product" or len(need[k]) > 0 or any(k in dd["enhance"] for dd in D2.values())
    if not grounded: phantom.append((k, "no org row and no source ask"))
    if not used: phantom.append((k, "serves no family"))
for key, k in NEEDS.items():
    if k not in K: phantom.append((key, "needs key maps to a missing component"))
orphans = [i for i, d in D2.items() if not (set(d["components"]) - {"K01", "K24"})]
v1v2 = {i: round(jac(V1[i], set(D2[i]["components"]) - {"K21", "K22", "K24"}), 3) for i in FAM}
txt = {i: round(jac(set(D2[i]["components"]), set(D2s[i]["components"])), 3) for i in FAM}
diffs = {i: {"added_vs_v1": sorted(set(D2[i]["components"]) - V1[i] - {"K21", "K22", "K24"}),
             "dropped_vs_v1": sorted(V1[i] - set(D2[i]["components"]))} for i in FAM}
diffs = {i: d for i, d in diffs.items() if d["added_vs_v1"] or d["dropped_vs_v1"]}
v1_extra_pairs = [(i, c) for i, cs in V1_EXTRA.items() for c in cs if c not in ("K17",)]
recovered = sum(1 for i, c in v1_extra_pairs if c in D2[i]["components"])

# paper truth: what A and B *plan* to build for their families (not yet built; rescore after Taco Night)
PLANNED = {
    "PF-51": {"src": "A Family approval flow tab: M0 lanes 1,2,3,4,5,8,12,13 + platform packages",
              "set": {"K01", "K21", "K04", "K11", "K10", "K02", "K03", "K05", "K06", "K12", "K24"}},
    "PF-28": {"src": "B cycle-2 asks 1-8 (coordination log)",
              "set": {"K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K10", "K11", "K12", "K24"}},
}
truth = {}
for i, p in PLANNED.items():
    pred = set(D2[i]["components"]); act = p["set"]
    truth[i] = {"source": p["src"], "precision": round(len(pred & act) / len(pred), 3), "recall": round(len(pred & act) / len(act), 3),
                "predicted_not_planned": sorted(pred - act), "planned_not_predicted": sorted(act - pred)}

# ------------------------------------------------------------------ DAG-aware greedy build order (product layer)
total = sum(f["vas"] for f in FAMILIES)
built, order = set(), []
GATING = {c for dd in D2.values() for c in dd["components"]}
while len(built) < len(GATING):  # product + K19, K20 when families need them
    elig = [k for k in GATING if k not in built and all(d in built or K[d]["layer"] != "product" for d in K[k]["deps"])]
    if not elig: break
    gain = lambda k: sum(FAM[i]["vas"] / len(D2[i]["components"]) for i in need[k]) / eff(k)
    k = max(elig, key=lambda k: (gain(k), len(need[k]), k))
    built.add(k)
    unl = [i for i, d in D2.items() if set(d["components"]) <= built]
    order.append({"step": len(built), "component": k, "name": K[k]["name"], "effort_cum_days": sum(eff(x) for x in built),
                  "families_unlocked": len(unl), "vas_share": round(sum(FAM[i]["vas"] for i in unl) / total, 3)})

# ------------------------------------------------------------------ full DAG: layers + longest path by effort
def topo_layers():
    lvl = {}
    def L(k):
        if k not in lvl: lvl[k] = 1 + max([L(d) for d in K[k]["deps"]] or [-1])
        return lvl[k]
    for k in K: L(k)
    return lvl
LV = topo_layers()
def longest():
    best = {}
    def B(k):
        if k not in best:
            sub = max([B(d) for d in K[k]["deps"]] or [(0, [])])
            best[k] = (sub[0] + eff(k), sub[1] + [k])
        return best[k]
    return max(B(k) for k in K)
LP = longest()
def longest_in(sub):
    best = {}
    def B(k):
        if k not in best:
            sub_ = max([B(d) for d in K[k]["deps"] if d in sub] or [(0, [])])
            best[k] = (sub_[0] + eff(k), sub_[1] + [k])
        return best[k]
    return max(B(k) for k in sub)
LPP = longest_in(set(PRODUCT))

# ------------------------------------------------------------------ the Dec 2 plan (MVP slice sizes, five lanes)
DAYS = [dt.date(2026, 11, d) for d in range(19, 31) if d != 26] + [dt.date(2026, 12, 1)]
PLAN = [  # (task, lane, start, days, deps, milestone)
    ("Contracts drafted (components@2 types)", "EL", "11-19", 1, [], "contracts"),
    ("Acks from A, B, C, D, E", "EL", "11-20", 2, ["Contracts drafted (components@2 types)"], "contracts"),
    ("Contract freeze v1", "EL", "11-22", 0, ["Acks from A, B, C, D, E"], "contracts"),
    ("K17 Gateway twin", "HP", "11-19", 3, [], "HW"),
    ("K24 ShoppingPort H3", "HP", "11-22", 2, ["K17 Gateway twin"], "HW"),
    ("K05 slots (estimated mode)", "HP", "11-24", 1, ["K24 ShoppingPort H3"], "HW"),
    ("K26 Telemetry", "ED", "11-19", 1, [], "HW"),
    ("K25 Synthetic world + taco cases", "ED", "11-20", 2, ["Contracts drafted (components@2 types)"], "HW"),
    ("K03 Constraint verifier", "ED", "11-22", 1, [], "HW"),
    ("K12 Ledger (append + verify)", "ED", "11-23", 1, ["K26 Telemetry"], "HW"),
    ("K27 Eval harness (pass^k)", "ED", "11-24", 1, ["K25 Synthetic world + taco cases"], "HW"),
    ("K01 Intent parser (prompted + fallback)", "MF", "11-20", 1, [], "HW"),
    ("K21 Need-list builder (taco, spaghetti)", "MF", "11-21", 1, [], "HW"),
    ("K02 Brief writer", "MF", "11-22", 1, ["K01 Intent parser (prompted + fallback)"], "HW"),
    ("K04 Cart solver", "MF", "11-23", 2, ["K03 Constraint verifier"], "HW"),
    ("K06 Household + rights", "PD", "11-20", 1, [], "HW"),
    ("K23 Event bus", "PD", "11-21", 1, ["K26 Telemetry"], "HW"),
    ("K10 Poll + policies", "PD", "11-22", 2, ["K23 Event bus", "K06 Household + rights"], "HW"),
    ("K11 Cards (templates)", "PD", "11-24", 1, ["K03 Constraint verifier"], "HW"),
    ("Hello world live smoke (K20 tier 0->2)", "HP", "11-25", 1,
     ["K05 slots (estimated mode)", "K04 Cart solver", "K02 Brief writer", "K10 Poll + policies", "K11 Cards (templates)",
      "K12 Ledger (append + verify)", "K27 Eval harness (pass^k)", "K21 Need-list builder (taco, spaghetti)", "Contract freeze v1"], "HW"),
    ("K09 trigger stub (manual + calendar, rules)", "MF", "11-25", 1, [], "should"),
    ("Decomposition stage in Fork C engine", "EL", "11-23", 2, ["Contract freeze v1"], "ENG"),
    ("Engine run + lens flip (Fork C)", "EL", "11-25", 1, ["Decomposition stage in Fork C engine"], "ENG"),
    ("K07 Care profile scope", "PD", "11-25", 2, ["K06 Household + rights"], "CARE"),
    ("K08 Standing mandate + cap guard", "PD", "11-28", 2, ["K07 Care profile scope", "K12 Ledger (append + verify)"], "CARE"),
    ("K17 + K24 profile model, discover(usuals, profile_id)", "HP", "11-27", 2, ["Hello world live smoke (K20 tier 0->2)"], "CARE"),
    ("K25 + K27 Care cases and B's six eval rows", "ED", "11-27", 2, ["K27 Eval harness (pass^k)"], "CARE"),
    ("K11 over-cap card (Jen)", "MF", "11-27", 1, ["K11 Cards (templates)"], "CARE"),
    ("Care Profiles integration", "PD", "11-30", 1,
     ["K08 Standing mandate + cap guard", "K17 + K24 profile model, discover(usuals, profile_id)", "K25 + K27 Care cases and B's six eval rows", "K11 over-cap card (Jen)"], "CARE"),
    ("K05 slots full + re-solve on STALE", "HP", "11-29", 2, ["Hello world live smoke (K20 tier 0->2)"], "should"),
    ("K18 support view stub + K19 parity stub", "ED", "11-29", 2, ["K12 Ledger (append + verify)"], "should"),
    ("Rehearsal on the library machine", "EL", "11-30", 1, ["Hello world live smoke (K20 tier 0->2)"], "demo"),
    ("Code freeze", "EL", "12-01", 0, ["Care Profiles integration", "Rehearsal on the library machine"], "demo"),
]
def d(s): return dt.date(2026, int(s[:2]), int(s[3:]))
def end_of(start, days):
    if days == 0: return start
    i = DAYS.index(start); return DAYS[i + days - 1]
sched, errs = {}, []
for t, lane, s, n, deps, ms in PLAN:
    s0 = d(s)
    if n and s0 not in DAYS: errs.append(f"{t}: starts on a day off")
    e = end_of(s0, n); sched[t] = {"lane": lane, "start": s0.isoformat(), "end": e.isoformat(), "days": n, "deps": deps, "milestone": ms}
    for dep in deps:
        de = d(sched[dep]["end"][5:]) if dep in sched else None
        if de is None: errs.append(f"{t}: unknown dep {dep}")
        elif (n and de >= s0) or (not n and de > s0): errs.append(f"{t}: starts before {dep} ends")
by_lane = defaultdict(list)
for t, v in sched.items():
    if v["days"]: by_lane[v["lane"]].append((v["start"], v["end"], t))
for lane, xs in by_lane.items():
    xs.sort()
    for a, b in zip(xs, xs[1:]):
        if a[1] >= b[0]: errs.append(f"lane {lane}: {a[2]} overlaps {b[2]}")
# slack to each task's milestone deadline (HW 11-25, CARE 11-30, ENG 11-25, demo 12-01)
DEAD = {"HW": "11-25", "ENG": "11-25", "CARE": "11-30", "contracts": "11-22", "demo": "12-01", "should": "11-30"}
succ = defaultdict(list)
for t, v in sched.items():
    for dep in v["deps"]: succ[dep].append(t)
latest = {}
def LF(t):  # latest finish (index into DAYS) without moving the milestone
    if t in latest: return latest[t]
    own = DAYS.index(d(DEAD[sched[t]["milestone"]]))
    cand = [own] + [DAYS.index(d(sched[s]["start"][5:])) - (1 if sched[s]["days"] else 0) for s in succ[t]]
    latest[t] = min(cand); return latest[t]
for t, v in sched.items():
    v["slack_days"] = LF(t) - DAYS.index(d(v["end"][5:]))
critical = [t for t, v in sched.items() if v["slack_days"] <= 0 and v["milestone"] in ("HW", "CARE", "contracts", "demo")]
lane_load = {lane: sum(v["days"] for v in sched.values() if v["lane"] == lane) for lane in ["EL", "HP", "MF", "ED", "PD"]}

OUT = {"stage": "decomposition@2", "catalog": "components@2", "bank": "run-0", "deterministic": True,
       "family_components": {i: {**D2[i], "vas": FAM[i]["vas"]} for i in FAM},
       "reuse": reuse, "curve_new_components_per_family": curve,
       "evals": {
           "decomposition_truth_paper": truth,
           "reuse": {"product_mean_families": round(sum(prod_reuse) / len(prod_reuse), 1),
                     "product_serving_ge_3": sum(1 for x in prod_reuse if x >= 3), "product_components": len(PRODUCT),
                     "new_components_after_first_10_families": sum(curve[10:])},
           "unlock": order,
           "stability": {"v1_vs_v2_mean_jaccard": round(sum(v1v2.values()) / len(v1v2), 3),
                         "v1_hand_overrides_recovered_by_rules": f"{recovered}/{len(v1_extra_pairs)}",
                         "structured_only_vs_with_text_mean_jaccard": round(sum(txt.values()) / len(txt), 3),
                         "families_changed_by_text_cues": sum(1 for x in txt.values() if x < 1),
                         "seed_stability": "pending: needs runs 1-3 with fresh judges (Fork C, Nov 22+)"},
           "phantom": {"count": len(phantom), "items": phantom, "orphan_families": orphans}},
       "diffs_vs_v1": diffs,
       "dag": {"layers": LV, "longest_path_days": LP[0], "longest_path": LP[1], "product_longest_path": LPP},
       "plan": {"schedule": sched, "errors": errs, "critical": critical, "lane_load_days": lane_load}}
json.dump(OUT, open("run-0-decomposition-v2.json", "w"), indent=1, default=str)

if __name__ == "__main__":
    print("product components", len(PRODUCT), "platform/eval", len(PLATFORM))
    print("reuse", reuse)
    print("curve", curve, "new after 10:", sum(curve[10:]))
    print("truth", json.dumps(truth, indent=1))
    print("stability", OUT["evals"]["stability"])
    print("phantom", phantom, "orphans", orphans)
    print("diffs vs v1 (%d families)" % len(diffs)); [print(" ", i, x) for i, x in diffs.items()]
    print("build order"); [print(" ", o) for o in order]
    print("DAG longest path", LP, "product", LPP)
    print("layers", sorted(LV.items(), key=lambda x: (x[1], x[0])))
    print("plan errors", errs)
    print("critical", critical)
    print("lane load", lane_load)
    for t, v in sched.items(): print(f"  {v['lane']} {v['start'][5:]}..{v['end'][5:]} slack={v['slack_days']:>2} {t}")
    risk = defaultdict(int)
    for dd in D2.values():
        for c in dd["unconfirmed_caps"]: risk[c] += 1
    print("families per unconfirmed cap", dict(sorted(risk.items(), key=lambda x: -x[1])))
    print("fully confirmed families", sum(1 for dd in D2.values() if not dd["unconfirmed_caps"]))

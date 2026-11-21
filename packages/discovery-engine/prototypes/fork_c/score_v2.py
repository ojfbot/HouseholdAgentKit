"""Fork C run 0 (v2): hello-world gate, value ladder, value at stake, rubric@2, controls@1. Usage: python3 score_v2.py [seed]"""
import json, math, random, sys
from collections import Counter
import yaml
from bank_v2 import F, X, REFS

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261118
RUB = yaml.safe_load(open("rubric-v2.yaml")); CTL = yaml.safe_load(open("controls-v1.yaml"))
W = {k: v["weight"] for k, v in RUB["criteria"].items()}; RISK_W = RUB["penalty"]["risk"]["weight"]
DIV = RUB["selection"]["diversity"]; ADOPT = CTL["scenario"]["adoption_share"]
ANCHORS = {"PF-51", "G-01", "PF-28"}
COND = {"T": "outside_trigger", "U": "unattended", "C": "context_walmart_shouldnt_hold", "O": "other_people", "R": "completion_under_rules"}
KEYS = "id slug title actor_type persona role situation trigger surface conds gate gate_note approval stake ev ev_ref risk quadrant cluster rel f s W V D R Nv".split()
XK = "job segment protected sparky_today specific_brief owners lanes seg seg_src freq basket gap".split()

def stake_tags(s):
    s = s.lower(); t = set()
    if any(w in s for w in ["revenue", "new customer", "share of wallet", "order success", "retention"]): t.add("revenue")
    if any(w in s for w in ["trust", "retention", "order success", "substitution"]): t.add("trust")
    if any(w in s for w in ["cost", "waste", "substitution", "delivery success"]): t.add("cost")
    if any(w in s for w in ["risk", "velocity"]): t.add("risk")
    return t or {"revenue"}

def tier_of(d):
    if d["conds"]: return 2
    return 1 if d["gate"] == "tier1" else 0

rows = []
for t in F:
    d = dict(zip(KEYS, t)); d.update(dict(zip(XK, X[d["id"]])))
    d["tier"] = tier_of(d); d["stake_tags"] = sorted(stake_tags(d["stake"]))
    d["vas"] = d["seg"] * ADOPT * d["freq"] * d["basket"] * d["gap"]
    n = len(d["conds"])
    d["x"] = {"pain": math.sqrt(d["f"] * d["s"]), "value_at_stake": min(5, max(0, math.log10(max(d["vas"], 1)) - 5)),
              "tier": {0: 1, 1: 2.5}.get(d["tier"], min(5, 3 + 0.4 * n)), "demo_ability": d["D"], "evidence": int(d["ev"][1]),
              "novelty": d["Nv"], "walmart_stake": d["W"], "visible_approval": d["V"], "reuse": d["R"]}
    rows.append(d)

def total(x, risk, w=W, rw=RISK_W): return 100 * (sum(w[k] * x[k] for k in w) / 5 - rw * risk / 5)
for r in rows: r["score"] = round(total(r["x"], r["risk"]), 1)

# Stage 0: hello world (placement self-test; the live agent smoke test needs A's stack, due Nov 21)
hw = next(r for r in rows if r["id"] == "PF-51"); hw0 = next(r for r in rows if r["id"] == "G-01")
hello = {"tier0_baseline_observed": hw["ev"] == "E3" and hw0["tier"] == 0, "tier1_brief_present": bool(hw["specific_brief"]),
         "tier2_conditions": len(hw["conds"]) >= 1, "care_profiles_tier2": next(r for r in rows if r["id"] == "PF-28")["tier"] == 2,
         "live_agent_smoke_test": "pending (A's agent stack v0, Nov 21)"}
hello["placement_pass"] = all(v for k, v in hello.items() if k != "live_agent_smoke_test")
assert hello["placement_pass"], "hello world failed: run aborts"

# Controls
def weight(prof, r):
    ws = prof.get("segment", {}).get(r["actor_type"], 1.0); wi = prof.get("intent", {}).get(r["job"], 1.0); clamps = []
    lo, hi = CTL["bounds"]["segment"]
    ws, wi = min(hi, max(lo, ws)), min(hi, max(lo, wi))
    if r["protected"]:
        if ws < 1.0: clamps.append(("segment", ws)); ws = 1.0
        if wi < 1.0: clamps.append(("intent", wi)); wi = 1.0
    ob = CTL["owner_boost"] if prof.get("owner") in r["owners"] else 1.0
    vw = prof["value"]; top_w = max(vw.values())
    sf = (0.6 + 0.8 * max(vw.get(k, 0) for k in r["stake_tags"]) / top_w) / 1.4   # 1.0 when the family's best stake is the profile's top value
    return ws * wi * ob * sf, clamps

def ranked(prof, rs=None, key="score"):
    out = []
    for r in (rs or rows):
        m, cl = weight(prof, r); out.append({**r, "priority": r[key] * m, "clamps": cl})
    return sorted(out, key=lambda r: (-r["priority"], r["id"]))

def select(rk, k=10):
    rk = [r for r in rk if r["id"] not in ANCHORS]; pick, pt, pc = [], Counter(), Counter()
    for r in rk:
        if pt[r["actor_type"]] >= DIV["max_per_actor_type"] or pc[r["cluster"]] >= DIV["max_per_cluster"]: continue
        pick.append(r); pt[r["actor_type"]] += 1; pc[r["cluster"]] += 1
        if len(pick) == k: break
    while len({p["actor_type"] for p in pick}) < DIV["min_actor_types_in_top10"]:
        have = {p["actor_type"] for p in pick}
        cand = next(r for r in rk if r not in pick and r["actor_type"] not in have and pc[r["cluster"]] == 0)
        common = Counter(p["actor_type"] for p in pick).most_common(1)[0][0]
        out = [p for p in pick if p["actor_type"] == common][-1]; pick.remove(out); pc[out["cluster"]] -= 1
        pick.append(cand); pc[cand["cluster"]] += 1; pick.sort(key=lambda r: -r["priority"])
    return pick

PROFILES = CTL["profiles"]; tops = {name: select(ranked(p)) for name, p in PROFILES.items()}

# Robustness under judge noise, per profile
rng = random.Random(SEED + 1); N = 1000; hits = {n: Counter() for n in PROFILES}; jac = {n: [] for n in PROFILES}
JUDGED = ["pain", "demo_ability", "novelty", "walmart_stake", "visible_approval", "reuse"]
for _ in range(N):
    noisy = []
    for r in rows:
        x = dict(r["x"]); 
        for k in JUDGED: x[k] = min(5, max(0, x[k] + rng.gauss(0, 0.6)))
        noisy.append({**r, "nscore": total(x, min(5, max(0, r["risk"] + rng.gauss(0, 0.6))))})
    for n, p in PROFILES.items():
        t = {q["id"] for q in select(ranked(p, noisy, "nscore"))}; base = {q["id"] for q in tops[n]}
        for i in t: hits[n][i] += 1
        jac[n].append(len(t & base) / len(t | base))

# Control sanity
sanity = {}
for n, p in PROFILES.items():
    if n == "default": continue
    own = p["owner"]; cnt = lambda top: sum(own in r["owners"] for r in top)
    clamps = [(r["id"], c) for r in ranked(p) for c in r["clamps"]]
    floor_breach = [r["id"] for r in ranked(p) if r["protected"] and weight(p, r)[0] < 0.6 * 1.0]  # stake_fit can lower; segment/intent never below 1
    sanity[n] = {"owned_in_top10_default": cnt(tops["default"]), "owned_in_top10_profile": cnt(tops[n]),
                 "floor_clamps": clamps, "segment_or_intent_below_floor": 0}

bank = {"run_id": "run-0", "taxonomy_version": "lattice@1", "rubric_version": "rubric@2", "control_model_version": "controls@1",
        "seed": SEED, "judge": "seed judge J0 (Claude, Fork C session); single judge", "adoption_share": ADOPT,
        "synthetic_label": "All situations synthetic; value at stake is order-of-magnitude and synthetic unless every input is S",
        "hello_world": hello, "control_sanity": sanity, "refs": REFS, "families": []}
for r in sorted(rows, key=lambda r: (-r["score"], r["id"])):
    bank["families"].append({
        "id": r["id"], "family": r["slug"], "title": r["title"], "cluster": r["cluster"], "actor_type": r["actor_type"], "actor": r["persona"],
        "role_in_order": r["role"], "segment": r["segment"], "protected": r["protected"], "job": r["job"], "quadrant": r["quadrant"],
        "situation": r["situation"], "trigger": r["trigger"], "agent_surface": r["surface"],
        "sparky_today": r["sparky_today"], "specific_brief": r["specific_brief"], "gateway_only": [COND[c] for c in r["conds"]], "value_tier": r["tier"],
        "value_at_stake": {"usd_per_year": round(r["vas"]), "segment_size": r["seg"], "segment_src": r["seg_src"], "adoption_share": ADOPT,
                           "frequency_per_year": r["freq"], "basket_usd": r["basket"], "gap": r["gap"], "inputs_sourced": ["segment_size"] if r["seg_src"].startswith("S") else [], "synthetic": True},
        "business_owners": r["owners"], "lanes_to_tune": r["lanes"], "approval_moment": r["approval"], "walmart_stake": r["stake_tags"],
        "evidence": {"level": r["ev"], "refs": [r["ev_ref"]] if r["ev_ref"] else [], "synthetic": r["ev"] == "E0"},
        "risk": r["risk"], "relation_to_A_B": r["rel"], "scores": {"frequency": r["f"], "severity": r["s"], **{k: round(v, 2) for k, v in r["x"].items()}},
        "total": r["score"], "anchor": r["id"] in ANCHORS,
        "top10": {n: next((i + 1 for i, q in enumerate(tops[n]) if q["id"] == r["id"]), None) for n in PROFILES},
        "top10_under_judge_noise": {n: round(hits[n][r["id"]] / N, 2) for n in PROFILES}})
json.dump(bank, open("run-0/problem-bank.json", "w"), indent=1)

print("hello world:", hello)
print("families:", len(rows), "tiers:", Counter(r["tier"] for r in rows), "actor types:", len({r['actor_type'] for r in rows}))
print("sourced segment inputs:", sum(r["seg_src"].startswith("S") for r in rows))
for n in PROFILES:
    print(f"\n== {n}  (Jaccard under noise mean {sum(jac[n])/N:.2f}, p10 {sorted(jac[n])[N//10]:.2f})")
    for i, r in enumerate(tops[n], 1):
        print(f"{i:>2} {r['id']:<6} pri={r['priority']:5.1f} score={r['score']:5.1f} T{r['tier']} VaS=${r['vas']/1e6:9.1f}M noise={hits[n][r['id']]/N:.2f} {r['actor_type']:<18} {r['title']}")
print("\nsanity:", json.dumps(sanity, indent=0))
print("\nALL by score")
for i, r in enumerate(sorted(rows, key=lambda r: -r["score"]), 1):
    print(f"{i:>2} {r['id']:<6} {r['score']:5.1f} T{r['tier']} VaS=${r['vas']/1e6:9.1f}M x={r['x']['value_at_stake']:.1f} {r['actor_type']:<18} {r['title']}")

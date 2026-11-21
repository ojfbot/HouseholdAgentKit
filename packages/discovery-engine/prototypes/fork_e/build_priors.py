"""Proposed control priors for Fork C's controls@2 (Fork E). Writes controls-priors-v2.yaml.
value vectors are DERIVED from stated_priorities weights and the registry's business_functions tags;
segment and intent priors are hand-set, each with its basis: 'stated' (registry rows) or 'would_also_serve' (our inference)."""
import yaml
from collections import defaultdict

sp = yaml.safe_load(open("org-model-v2/walmart/stated_priorities.yaml"))
reg = {r["id"]: r for r in yaml.safe_load(open("statements.yaml"))["statements"]}
P = {p["id"]: p for p in sp["priorities"] if p["owner"] == "walmart"}
# which value dimension each Walmart priority speaks to (our mapping; shares sum to 1)
VMAP = {"PW-01": {"trust": 1}, "PW-02": {"revenue": 1}, "PW-03": {"trust": .5, "revenue": .5}, "PW-04": {"revenue": .5, "cost": .5},
        "PW-05": {"revenue": 1}, "PW-06": {"revenue": 1}, "PW-07": {"trust": .5, "revenue": .5}, "PW-08": {"revenue": .5, "trust": .5},
        "PW-09": {"revenue": 1}, "PW-10": {"cost": 1}, "PW-11": {"risk": 1}, "PW-12": {"risk": .5, "trust": .5},
        "PW-13": {"revenue": 1}, "PW-14": {"risk": .5, "trust": .5}, "PW-15": {"revenue": .5, "trust": .5}}
DIMS = ["revenue", "trust", "cost", "risk"]

def vector(func=None):
    v = defaultdict(float); used = []; vector.n = 0
    for pid, p in P.items():
        rows = [reg[e] for e in p["evidence"]]
        hits = len(rows) if func is None else sum(func in r["business_functions"] for r in rows)
        vector.n += hits
        share = hits / len(rows)
        if share == 0: continue
        used.append(pid)
        for d, s in VMAP[pid].items(): v[d] += p["weight"] * share * s
    tot = sum(v.values()) or 1
    return {d: round(v[d] / tot, 2) for d in DIMS}, sorted(used)

FUNCS = {  # controls@1 profile name -> registry business_function tag
    "default": None, "marketing_crm": "marketing_crm", "supply_chain": "supply_chain", "product": "product",
    "trust_safety": "trust_safety", "partnerships": "partnerships", "finance": "finance", "connect_ads": "connect_ads",
    "merchandising": "merchandising", "marketplace": "marketplace", "store_ops": "store_ops", "care_returns": "care_returns", "b2b": "b2b"}

# hand-set priors: (key, weight, basis, evidence or reason)
SEG_INT = {
 "default": {"segment": [], "intent": []},
 "product": {
   "segment": [("shopper", 1.4, "stated", "ST-031 ST-108"), ("never_shopper", 1.5, "stated", "ST-101: AI arrivals are often new customers")],
   "intent": [("restock", 1.5, "stated", "ST-031 ST-060 chores, reorder nudges"), ("feed", 1.4, "stated", "ST-120 ST-191 recipes, taco night")]},
 "trust_safety": {
   "segment": [("caregiver", 1.3, "would_also_serve", "delegated buying for someone else is where consent breaks"), ("agent_builder", 1.5, "stated", "ST-127 ST-145")],
   "intent": [("protect_someone", 1.6, "would_also_serve", "scam-aware consent, PF-29"), ("care_for_someone", 1.3, "would_also_serve", "approval by someone other than the shopper")]},
 "partnerships": {
   "segment": [("never_shopper", 2.0, "stated", "ST-033 ST-101 ST-136: be chosen inside third-party AI"), ("agent_builder", 1.8, "stated", "ST-072 ST-073 partner performance")],
   "intent": [("feed", 1.3, "stated", "ST-155 ST-191"), ("restock", 1.2, "stated", "ST-058 usuals in ChatGPT")]},
 "finance": {
   "segment": [("shopper", 1.3, "stated", "ST-040 ST-053 bigger baskets"), ("never_shopper", 1.4, "stated", "ST-101")],
   "intent": [("host_or_celebrate", 1.3, "would_also_serve", "large multi-item baskets"), ("restock", 1.3, "stated", "ST-148 replenishment fastest-growing (analyst)")]},
 "connect_ads": {
   "segment": [("supplier_brand", 1.8, "stated", "ST-064 ST-067"), ("marketplace_seller", 1.4, "stated", "ST-068")],
   "intent": [("gifts", 1.3, "would_also_serve", "discovery-heavy jobs"), ("host_or_celebrate", 1.3, "would_also_serve", "discovery-heavy jobs")]},
 "merchandising": {
   "segment": [("supplier_brand", 1.6, "stated", "ST-123 ST-160"), ("marketplace_seller", 1.3, "stated", "ST-159")],
   "intent": [("restock", 1.3, "stated", "ST-160 keep on hand")]},
 "marketplace": {
   "segment": [("marketplace_seller", 2.5, "stated", "ST-158 ST-041"), ("never_shopper", 1.3, "would_also_serve", "long-tail discovery for new customers")],
   "intent": [("gifts", 1.3, "stated", "ST-068 long-tail example"), ("set_up_a_home", 1.3, "would_also_serve", "broad-assortment job")]},
 "store_ops": {
   "segment": [("store_associate", 2.5, "stated", "ST-048 ST-111 ST-139")],
   "intent": [("restock", 1.3, "would_also_serve", "picks with locked lines"), ("care_for_someone", 1.2, "would_also_serve", "InHome put-away")]},
 "care_returns": {
   "segment": [("walmart_team", 2.0, "stated", "ST-039 ST-056"), ("caregiver", 1.3, "would_also_serve", "disputes on orders for someone else")],
   "intent": [("recover", 1.5, "stated", "ST-010 returns when an agent misfired")]},
 "b2b": {
   "segment": [("small_business", 2.5, "stated", "ST-001 ST-157 (Sam's in scope)"), ("community_org", 2.0, "would_also_serve", "no Walmart statement; PF-39 PF-43")],
   "intent": [("restock", 1.5, "stated", "ST-157")]},
 "marketing_crm": {
   "segment": [("shopper", 1.6, "stated", "ST-137 ST-041"), ("never_shopper", 2.0, "stated", "ST-101")],
   "intent": [("feed", 1.4, "stated", "ST-137"), ("restock", 1.4, "stated", "ST-137 detergent before it runs out")]},
 "supply_chain": {
   "segment": [("store_associate", 2.0, "stated", "ST-170 ST-111"), ("spark_driver", 1.5, "stated", "ST-112 ST-114")],
   "intent": [("prepare", 1.8, "would_also_serve", "storm and event surges"), ("restock", 1.5, "stated", "ST-170 position before demand")]},
}
NEW_FAMILY_SEEDS = [
 {"seed": "Win the order inside a third-party assistant, through Sparky", "serves": ["PW-06", "PW-15", "PW-02"], "why": "PW-06 is the third-loudest Walmart priority and one top family serves it"},
 {"seed": "A sponsored item an agent may accept: labeled, within constraints, never above a cheaper qualifying item", "serves": ["PW-09", "PW-03"], "why": "PW-09 has no top family; must satisfy CON-03b and CON-21"},
 {"seed": "Long-tail seller picked under strict household rules", "serves": ["PW-05", "PW-13"], "why": "Joneja's stated hope (ST-158); PF-32 is not top-10"},
]
profiles = {}
for name, tag in FUNCS.items():
    val, used = vector(tag)
    s = SEG_INT.get(name, {"segment": [], "intent": []})
    for k, w, b, e in s["segment"] + s["intent"]: assert 0.5 <= w <= 3.0 and b in ("stated", "would_also_serve")
    profiles[name] = {
        "value_prior": val, "tagged_evidence_rows": vector.n, "thin_evidence": vector.n < 6, "value_basis": f"derived from stated priorities {', '.join(used)} weighted by share of their rows tagged '{tag or 'any'}'",
        "segment_stated": {k: w for k, w, b, e in s["segment"] if b == "stated"},
        "segment_would_also_serve": {k: w for k, w, b, e in s["segment"] if b != "stated"},
        "intent_stated": {k: w for k, w, b, e in s["intent"] if b == "stated"},
        "intent_would_also_serve": {k: w for k, w, b, e in s["intent"] if b != "stated"},
        "evidence": {k: e for k, w, b, e in s["segment"] + s["intent"]}}
doc = {"proposal": "controls@2 priors (Fork E -> Fork C)", "as_of": "2026-11-19",
       "rules": ["Priors only: Fork C owns controls@2 and may override.",
                 "stated = Walmart said it wants this (registry rows cited); would_also_serve = our inference; keep them in separate keys so the UI can show which is which.",
                 "Never-tunable keys from controls@1 stay never-tunable; CON-05 and CON-21 are Walmart-published, so price and hiding cheaper options are out of every profile.",
                 "Fairness floor unchanged: protected-tag families never weighted below 1.0.",
                 "value_prior is a starting point for the value vector; bounds and owner_boost unchanged from controls@1."],
       "profiles": profiles, "new_family_seeds": NEW_FAMILY_SEEDS}
yaml.safe_dump(doc, open("controls-priors-v2.yaml", "w"), sort_keys=False, width=140)
for n, p in profiles.items(): print(n, p["value_prior"])

"""Build org-model-v2/walmart/stated_priorities.yaml from statements.yaml.
Evidence lists are hand-curated (which registry rows speak to which priority); weights are DERIVED by formula, never typed."""
import yaml, re, datetime
from collections import Counter

REG = yaml.safe_load(open("statements.yaml"))
ROWS = {r["id"]: r for r in REG["statements"]}
AS_OF = datetime.date(2026, 11, 19)

def seniority(r):
    role, sp = r["role"], r["speaker"]
    if re.search(r"job posting", role, re.I): return 0.5, "job posting"
    if re.search(r"\bCEO\b|Chief Executive", role): return 1.0, "CEO"
    if re.search(r"\bCFO\b|\bEVP\b|Executive Vice President", role): return 0.8, "CFO/EVP"
    if re.search(r"\bSVP\b|\bVP\b|Vice President|Chief|President|Head|Senator", role): return 0.6, "SVP/VP"
    if r["source_type"] == "walmart_primary" and sp.startswith("Walmart"):
        if re.search(r"engineering blog|Global Tech", role + sp, re.I): return 0.5, "engineering"
        return 0.9, "corporate primary doc"
    if r["source_type"] == "walmart_primary": return 0.6, "named Walmart staff"
    if r["source_type"] == "partner": return 0.7, "partner org"
    return 0.4, "press/analyst"

def source_factor(r):
    st = r["source_type"]
    if st in ("walmart_primary", "partner"): return 1.0
    if st == "press":
        named = not re.search(r"press|newsroom|analysis|Retail Dive|TechCrunch|Modern Retail|PYMNTS|AFP|Axios|Journal|Zone|Forkast|Shopifreaks|eesel|Benefits|AIM|New Stack|Let's Data", r["speaker"] + " " + r["role"])
        return 0.8 if named else 0.5
    if st == "analyst": return 0.5
    return 0.2

def recency(r):
    p = str(r["published"])
    m = re.match(r"(\d{4})(?:-(\d{2}))?", p)
    y, mo = int(m.group(1)), int(m.group(2) or 6)
    months = (AS_OF.year - y) * 12 + (AS_OF.month - mo)
    return 1.0 if months <= 6 else 0.8 if months <= 12 else 0.6 if months <= 24 else 0.4

def score(r): return seniority(r)[0] * source_factor(r) * recency(r)

P = [
 # id, owner, statement (our paraphrase), evidence
 ("PW-01", "walmart", "Customers stay in control of agents: approval by default, standing limits, separate identity and history, easy revocation; trust before autonomy",
  "004 005 006 009 015 016 018 027 036 052 074 131"),
 ("PW-02", "walmart", "Agentic commerce is a growth engine (bigger baskets, e-commerce and membership growth), not mainly an efficiency play",
  "032 040 041 044 051 053 107 159"),
 ("PW-03", "walmart", "Everyday low price holds everywhere, including for agents; no per-person or time-of-day pricing; keep investing in price",
  "008 042 054 129 130 132"),
 ("PW-04", "walmart", "Speed and fulfillment reach are the edge: same-day at nearly every store, under-3h and 30-minute delivery, density economics",
  "041 049 102 136 143 170 171 192"),
 ("PW-05", "walmart", "Assortment breadth, including Marketplace and long-tail items an agent can surface",
  "034 054 068 136 158"),
 ("PW-06", "walmart", "Be discoverable and chosen inside third-party AI (Sparky in ChatGPT and Gemini, UCP, open partnerships, agentic engine optimization)",
  "033 038 044 046 055 058 062 063 101 134"),
 ("PW-07", "walmart", "Personalize from what customers choose to share without exposing their broader history to agents or platforms",
  "007 026 131 137 138"),
 ("PW-08", "walmart", "Take routine chores off customers: from a described problem or intent to a delivered solution; reorders and replenishment",
  "030 031 060 061 108 122 160 169 186"),
 ("PW-09", "walmart", "Ads stay relevant and paid on outcomes as shopping becomes conversational (Sparky ads, Marty, intent over keywords)",
  "035 064 067 070 163 164"),
 ("PW-10", "walmart", "An AI-enabled workforce: associate agents and tools that remove tasks and guide the next action",
  "048 109 110 111 139 157"),
 ("PW-11", "walmart", "Protect customer data and the platform: identified agents, scoped tokens, signed mandates, no secondary data use, enforcement",
  "011 014 017 019 020 023 047 190"),
 ("PW-12", "walmart", "Agent quality is measurable: evaluations, accuracy of data and claims, failure-rate and conversion metrics",
  "021 022 045 073 076 123 125 126 127"),
 ("PW-13", "walmart", "Enable suppliers and sellers with agentic tools and standards (Supplier One, Marty, Scintilla, fulfillment standards)",
  "071 075 097 098 158"),
 ("PW-14", "walmart", "Responsible AI: transparency, fairness, privacy, people accountable for AI outcomes",
  "045 166 167 168"),
 ("PW-15", "walmart", "A multi-agent ecosystem with Sparky as the agent outside agents work through (agent-to-agent, MCP, orchestrator over specialist agents)",
  "013 025 038 072 077 128 136"),
 ("PP-01", "supplier_brand", "Brands want to be chosen by agents and want one accurate, correctable product-data source across retailers",
  "103 104 105 106 179 187"),
 ("PP-02", "advertiser_agency", "Advertisers want visibility into, and measurement of, ads and sponsorship inside agent experiences",
  "065 066 069 106"),
 ("PP-03", "marketplace_seller", "Sellers want listings ready for agent discovery and to know what agents need; no separate enrollment exists",
  "095 096 099 179"),
 ("PP-04", "payments", "Payment networks want agents identified and trusted so merchants can tell good agents from bots",
  "088 089 090 091 092"),
 ("PP-05", "protocols", "Protocol groups want verifiable user intent (mandates) carried with every agent purchase",
  "081 083 084 085"),
 ("PP-06", "ai_platform", "AI platforms want discovery inside their apps and completion through merchant experiences; AI referrals convert",
  "086 087 093 155 177 178"),
 ("PP-07", "agent_builder", "Builders want a documented developer platform to integrate ordering (Instacart-style), plus docs over MCP",
  "080 151 152 162"),
 ("PP-08", "agent_builder", "Family and background agents want to act proactively on noticed needs, under the user's permission",
  "094 151 153 156"),
 ("PP-09", "spark_driver", "Drivers want honest pay displays and fair access to offers (no bots)",
  "112 113 114"),
 ("PP-10", "watchdog", "Labor and consumer groups oppose surveillance pricing and personalized upsell; regulators ask about checkout privacy",
  "133 174 175 176"),
 ("PP-11", "agent_builder", "The field needs agents that complete tasks reliably and identify themselves; platforms restrict those that don't",
  "145 146 183 184"),
]

raw = {}
out = []
for pid, owner, stmt, ev in P:
    ids = ["ST-" + x for x in ev.split()]
    for i in ids: assert i in ROWS, i
    rs = [ROWS[i] for i in ids]
    raw[pid] = sum(score(r) for r in rs)
    top = max(rs, key=lambda r: (seniority(r)[0], str(r["published"])))
    funcs = Counter(f for r in rs for f in r["business_functions"]).most_common(3)
    out.append({"id": pid, "owner": owner, "statement": stmt, "evidence": ids,
                "n_sources": len({r["source_url"] for r in rs}),
                "walmart_primary_rows": sum(r["source_type"] == "walmart_primary" for r in rs),
                "latest": max(str(r["published"]) for r in rs),
                "top_speaker": f'{top["speaker"]} ({top["role"]})',
                "functions": [f for f, _ in funcs]})
# normalize within owner group (walmart vs partners) so the two are never mixed on one scale
for grp in ("walmart", "partner"):
    members = [o for o in out if (o["owner"] == "walmart") == (grp == "walmart")]
    mx = max(raw[o["id"]] for o in members)
    for o in members:
        o["weight"] = round(raw[o["id"]] / mx, 2)
        o["label"] = "derived"

# H5 family -> priority map (ours). 'unnamed_need' = would also serve Walmart, but Walmart has not said it wants it.
FAM = {
 "PF-39": (["PW-01", "PW-08"], "organizations as principals with multi-approver rules; no Walmart statement found"),
 "PF-51": (["PW-08", "PW-03", "PW-04", "PW-01", "PW-15"], None),
 "PF-44": (["PW-08", "PW-04", "PW-01"], None),
 "PF-28": (["PW-01", "PW-07", "PP-08"], "a profile per person cared for (Walmart's profiles are per agent)"),
 "PF-48": (["PW-11", "PW-12", "PW-01"], None),
 "PF-20": (["PW-06", "PW-03", "PW-04", "PW-05"], None),
 "PF-03": (["PW-04", "PW-08", "PP-08"], None),
 "PF-01": (["PW-03", "PW-08", "PW-07"], None),
 "PF-45": (["PW-08", "PW-02"], None),
 "PF-46": (["PW-12", "PP-07", "PP-11"], None),
 "PF-47": (["PW-04", "PW-15", "PW-12"], None),
 "PF-15": (["PW-14", "PW-12", "PP-01"], None),
 "PF-23": (["PW-01", "PW-07"], None),
 "PF-22": (["PW-01", "PW-02"], None),
 "PF-33": (["PP-01", "PW-12", "PW-13"], None),
 "PF-37": (["PW-10", "PW-01"], None),
 "PF-10": (["PW-08", "PW-02"], None),
 "PF-21": (["PW-02", "PW-06"], None),
 "PF-17": (["PW-08"], None),
 "PF-35": (["PW-10", "PW-12", "PW-01"], None),
 "PF-43": (["PW-04"], "community organizations as principals in an emergency; no Walmart statement found"),
 "PF-26": (["PW-04"], None),
 "PF-27": (["PW-08", "PW-07"], None),
 "PF-49": (["PW-09", "PP-02", "PW-14"], None),
 "PF-08": (["PW-08", "PW-01"], None),
 "PF-24": (["PW-01", "PW-03"], None),
 "PF-12": (["PW-03", "PW-08"], None),
 "PF-30": (["PW-01"], "the person cared for can ask; the payer approves"),
 "PF-40": (["PW-08"], None),
 "PF-05": (["PW-01"], None),
 "PF-09": (["PW-07", "PW-08"], None),
 "PF-25": (["PW-08", "PP-06"], None),
 "PF-31": (["PW-01", "PW-08"], "one shopper across several households"),
 "PF-02": (["PW-01", "PW-14"], None),
 "PF-29": (["PW-01", "PW-11"], None),
 "PF-06": (["PW-08", "PW-07"], None),
 "PF-50": (["PW-04", "PW-02"], None),
 "PF-36": (["PW-04"], "notes from the person receiving"),
 "PF-13": (["PW-01"], None),
 "PF-18": (["PW-04", "PW-08"], None),
 "PF-41": (["PW-03"], "voucher programs as rules"),
 "PF-07": (["PW-08"], None),
 "PF-04": (["PW-08", "PW-04"], None),
 "G-03": (["PW-08", "PW-07"], None),
 "PF-14": (["PW-01", "PW-03"], None),
 "PF-32": (["PP-03", "PW-05", "PW-13"], None),
 "PF-11": (["PW-07", "PW-08"], None),
 "PF-16": (["PW-01"], None),
 "PF-19": (["PW-04"], None),
 "G-01": (["PW-08"], None),
 "G-07": (["PW-04"], None),
 "G-06": (["PW-02", "PW-12"], None),
 "G-05": (["PW-01", "PW-11"], None),
 "PF-42": ([], "teachers and classrooms as principals; no Walmart statement found"),
 "G-02": (["PW-05"], None),
 "PF-34": (["PP-03", "PW-13"], None),
 "PF-38": (["PW-10"], None),
 "G-04": (["PW-08"], None),
}
ids = {o["id"] for o in out}
for k, (ps, _) in FAM.items():
    for p in ps: assert p in ids, (k, p)

doc = {"org": "walmart", "org_model_version": "org@2", "as_of": str(AS_OF),
       "method": {
         "evidence": "hand-curated: which registry rows (fork-e/statements.yaml) state each priority",
         "weight": "derived = sum over evidence rows of seniority x source_factor x recency, normalized to 1.0 within Walmart priorities and separately within partner priorities; never typed by hand",
         "seniority": "CEO 1.0; CFO/EVP 0.8; corporate primary doc 0.9; SVP/VP or named staff 0.6; partner org 0.7; job posting or engineering blog 0.5; press/analyst 0.4",
         "source_factor": "walmart_primary or partner 1.0; press quoting a named person 0.8; other press 0.5; analyst 0.5; forum 0.2",
         "recency": "<=6 months 1.0; <=12 0.8; <=24 0.6; older 0.4 (as of 2026-11-19)",
         "caveat": "a weight measures how loudly and how senior, not how important; a quiet priority can still be decisive"},
       "priorities": out,
       "family_alignment": {k: {"serves": v[0], **({"unnamed_need": v[1]} if v[1] else {})} for k, v in FAM.items()}}
yaml.safe_dump(doc, open("org-model-v2/walmart/stated_priorities.yaml", "w"), sort_keys=False, width=140, allow_unicode=True)
for o in sorted(out, key=lambda o: (o["owner"] != "walmart", -o["weight"])):
    print(o["id"], o["weight"], o["n_sources"], o["walmart_primary_rows"], o["latest"], "|", o["top_speaker"][:60])

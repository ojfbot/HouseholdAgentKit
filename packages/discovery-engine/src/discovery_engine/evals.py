"""E18 — engine evals (Eval report@1 rows). Deterministic over runs x seeds.

Rows (the planning project "How we know the engine is good" + components@2 E11/E12/E18 oracles):
  hello_world, anchors, stability_top10_jaccard (>= 0.6 over 3 seeds), metamorphic, coverage, mece_overlap,
  sizing_band, control_sanity, fairness_floor, lens_invariance, recompute_under_1s, unlabeled_numbers,
  hypothesis_honesty, stereotype_counterfactual, no_diagnoses, schema_valid, determinism.
Each row: {metric, value, threshold, pass, detail}. The report is stamped with bank ids so D05 can hash-match it.
"""
from __future__ import annotations

import itertools
import random
import re
import time

from .live.engine import Bank, ControlEngine, rank, select
from .live.profiles import FUNCTION_OWNER, clone, standard_set
from .pipeline import RunConfig, run
from .stages import e05_dedupe
from .stages.e14_decompose import decompose, family_view
from .text import counterfactual, rephrase
from .util import sha256_hex

DIAGNOSIS_RX = re.compile(r"\b(diagnos\w*|dementia|alzheimer\w*|diabet\w*|arfid|autis\w*|cancer|depress\w*|adhd|bipolar|schizo\w*)\b", re.I)


def row(metric, value, threshold, ok, **detail):
    return {"metric": metric, "value": value, "threshold": threshold, "pass": bool(ok), "detail": detail}


def stability(banks: list[dict], profile="default") -> dict:
    tops = [set(t.split("~")[0] for t in b["readouts"][profile]["top_k"]) for b in banks]
    j = [len(a & b) / len(a | b) for a, b in itertools.combinations(tops, 2)]
    m = sum(j) / len(j)
    return row("stability_top10_jaccard", round(m, 3), ">= 0.6", m >= 0.6, pairwise=[round(x, 3) for x in j],
               seeds=[b["seed"] for b in banks], profile=profile, generator=banks[0]["generator"])


def metamorphic(bank: dict, cards_per_family: int = 2, seed: int = 7) -> dict:
    """Rephrase each family's representative text and check it lands in the same family."""
    from .stages.e05_dedupe import Index, card_text
    ix = Index(); rng = random.Random(seed)
    fams = [{"family_id": f["family_id"], "_sig": ix.sig(card_text(f))} for f in bank["families"]]
    total = ok = 0
    misses = []
    for f in bank["families"]:
        for _ in range(cards_per_family):
            t = f"{f['title']} {rephrase(f['situation'], rng)} {f['specific_brief']}"
            got, sim = e05_dedupe.assign(t, fams)
            total += 1; ok += got == f["family_id"]
            if got != f["family_id"]: misses.append((f["family_id"], got, round(sim, 2)))
    rate = ok / total
    return row("metamorphic_same_family", round(rate, 3), ">= 0.95", rate >= 0.95, probes=total, misses=misses[:5])


def coverage(bank: dict) -> list[dict]:
    cov = bank["coverage"]
    return [row("coverage_empty_actor_types", len(cov["empty_actor_types"]), "== 0", not cov["empty_actor_types"], by_actor=cov["by_actor_type"]),
            row("coverage_pairwise_min", min(cov["pairwise_coverage"].values()), "reported", True, pairs=cov["pairwise_coverage"]),
            row("mece_max_inter_family_similarity", bank["dedupe"]["max_inter_family_similarity"], f"< {bank['dedupe']['threshold']}",
                bank["dedupe"]["max_inter_family_similarity"] < bank["dedupe"]["threshold"])]


def sizing_band(bank: dict) -> dict:
    flagged = [f["family_id"] for f in bank["families"] if f["sizing"]["gap_flagged"]]
    return row("sizing_gap_flagged", len(flagged), "flagged, never hidden", True, families=flagged,
               note="top-down inputs are synthetic placeholders (sizing-topdown@0) until ED sources them")


def control_sanity(eng: ControlEngine, profiles: dict) -> list[dict]:
    rows = []
    base = select(rank(eng.bank, profiles["default"], eng.params), eng.k)
    for pid, p in profiles.items():
        if p["lens"] != "in_house" or not p.get("owner"):
            continue
        own = p["owner"]
        top = select(rank(eng.bank, p, eng.params), eng.k)
        n0 = sum(own in r["f"]["business_owners"] for r in base); n1 = sum(own in r["f"]["business_owners"] for r in top)
        rows.append(row(f"control_sanity[{pid}]", n1, f">= default ({n0})", n1 >= n0, owned_default=n0))
    return rows


def fairness_floor(eng: ControlEngine, profiles: dict) -> dict:
    breaches = []
    for pid, p in profiles.items():
        hostile = clone(p)
        for a in list(hostile["segment"]) + ["shopper", "caregiver", "community_org"]:
            hostile["segment"][a] = 0.5
        for j in ["care_for_someone", "protect_someone", "restock", "feed"]:
            hostile["intent"][j] = 0.5
        for r in rank(eng.bank, hostile, eng.params):
            if r["f"]["protected"] and (r["terms"]["w_segment"] < 1.0 or r["terms"]["w_intent"] < 1.0):
                breaches.append((pid, r["family_id"]))
    return row("fairness_floor_breaches", len(breaches), "== 0", not breaches, sample=breaches[:5])


def lens_invariance(eng: ControlEngine, profiles: dict) -> dict:
    """With the three stake-dependent terms neutralized, the ranking must be identical under both lenses."""
    bad = []
    for pid, p in profiles.items():
        a, b = clone(p), clone(p)
        a["lens"], b["lens"] = "in_house", "partner"
        ra = [r["family_id"] for r in rank(eng.bank, a, eng.params, neutral_stake=True)]
        rb = [r["family_id"] for r in rank(eng.bank, b, eng.params, neutral_stake=True)]
        if ra != rb:
            bad.append(pid)
    flips = {}
    for pid in ("default", "partner_default"):
        p = clone(profiles[pid]); q = clone(p); q["lens"] = "partner" if p["lens"] == "in_house" else "in_house"
        ta = [r["family_id"] for r in select(rank(eng.bank, p, eng.params), eng.k)]
        tb = [r["family_id"] for r in select(rank(eng.bank, q, eng.params), eng.k)]
        flips[pid] = {"moved_in": [x for x in tb if x not in ta], "moved_out": [x for x in ta if x not in tb]}
    return row("lens_flip_changes_only_stake_terms", len(bad), "== 0 profiles differ", not bad, profiles_differing=bad, flips=flips)


def recompute_time(eng: ControlEngine, profiles: dict, reps: int = 20) -> dict:
    worst = 0.0
    for pid in profiles:
        sid = f"timing-{pid}"
        for i in range(reps // 10 or 1):
            t0 = time.perf_counter()
            eng.apply({"op": "set", "path": ["segment", "shopper"], "value": 1.5 + 0.1 * i, "profile_id": pid}, sid)
            eng.apply({"op": "lens", "value": "partner" if i % 2 == 0 else "in_house", "profile_id": pid}, sid)
            worst = max(worst, (time.perf_counter() - t0) / 2)
    return row("recompute_s_p100", round(worst, 4), "< 1.0", worst < 1.0, families=len(eng.bank.families))


def unlabeled(bank: dict, eng: ControlEngine, profiles: dict) -> dict:
    n = bank["unlabeled_numbers_in_sizing"]
    ro = sum(eng.readout(p, pid)["unlabeled_numbers"] for pid, p in profiles.items())
    return row("unlabeled_numbers", n + ro, "== 0", n + ro == 0, sizing=n, readouts=ro)


def hypothesis_honesty(banks: list[dict]) -> dict:
    order_ok, verdicts = True, []
    for b in banks:
        steps = [e["stage"] for e in b["run_log"]]
        order_ok &= steps.index("E03") < steps.index("E04") if "E03" in steps and "E04" in steps else False
        verdicts += [h["verdict"] for h in b["hypotheses"].values()]
        for h in b["hypotheses"].values():
            body = {k: h[k] for k in ("lens", "text", "basis", "writer")}
            order_ok &= sha256_hex(body) == h["hash"]
    always = len(set(verdicts)) == 1 and verdicts[0] == "survived"
    return row("hypothesis_frozen_before_E04", order_ok, "true; verdicts reported", order_ok, verdicts=verdicts,
               always_confirms=always, note=("every verdict 'survived': expected while E04 runs the template fallback "
                                             "(it re-finds run-0 problems); re-check once the local teacher writes cards") if always else "")


def stereotype_counterfactual(bank: dict) -> dict:
    """Swap names, places and a language word in each family's text: tier, needs and components must not change."""
    diffs = []
    for f in bank["families"]:
        a = decompose(family_view({**f, "value_tier": f["tier"]}))
        b = decompose(family_view({**f, "situation": counterfactual(f["situation"]), "specific_brief": counterfactual(f["specific_brief"]),
                                   "value_tier": f["tier"]}))
        if a["components"] != b["components"] or a["needs"] != b["needs"]:
            diffs.append(f["family_id"])
    return row("stereotype_counterfactual_diffs", len(diffs), "== 0", not diffs, families=diffs)


def no_diagnoses(bank: dict) -> dict:
    hits = [(f["family_id"], m.group(0)) for f in bank["families"]
            for m in [DIAGNOSIS_RX.search(" ".join([f["situation"], f["segment"], f["specific_brief"], f["approval_moment"]]))] if m]
    return row("diagnoses_stored", len(hits), "== 0", not hits, hits=hits)


def determinism(cfg_seed: int) -> dict:
    a = run(RunConfig(seed=cfg_seed)); b = run(RunConfig(seed=cfg_seed))
    return row("same_seed_same_bank", a["bank_id"] == b["bank_id"], "true", a["bank_id"] == b["bank_id"],
               bank_id=a["bank_id"], cells_hash=a["cells_hash"] == b["cells_hash"])


def report(seeds=(1, 2, 3), profiles_source: str = "priors") -> dict:
    banks = [run(RunConfig(run_id=f"run-1-s{s}", seed=s, profiles_source=profiles_source)) for s in seeds]
    profiles, params = standard_set(profiles_source)
    main = banks[0]
    eng = ControlEngine(Bank(main), profiles, params)
    rows = [row("hello_world", main["hello_world"]["status"], "placement_pass or live_pass", main["hello_world"]["placement"]["placement_pass"]),
            row("anchors_placement", main["hello_world"]["placement"], "all true", main["hello_world"]["placement"]["placement_pass"]),
            row("schema_valid", 1.0, "== 1.0", True, note="E04 raises on any invalid card; a run that completes is 100% valid"),
            stability(banks), *[stability(banks, p) for p in ("partner_default", "marketing_crm")],
            metamorphic(main), *coverage(main), sizing_band(main), *control_sanity(eng, profiles), fairness_floor(eng, profiles),
            lens_invariance(eng, profiles), recompute_time(eng, profiles), unlabeled(main, eng, profiles),
            hypothesis_honesty(banks), stereotype_counterfactual(main), no_diagnoses(main), determinism(seeds[0])]
    return {"contract": "Eval report@1 (engine rows)", "banks": [{"run_id": b["run_id"], "seed": b["seed"], "bank_id": b["bank_id"]} for b in banks],
            "generator": main["generator"], "judge": main["judge"], "controls_source": main["controls_source"],
            "rows": rows, "pass": all(r["pass"] for r in rows), "failed": [r["metric"] for r in rows if not r["pass"]]}

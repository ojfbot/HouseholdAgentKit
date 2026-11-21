"""The overnight engine run (ADR-008 replay half): stage 0 -> E03 -> E02 -> E04 -> E05 -> E06 -> E08 -> E09 -> E10 -> E14,
then E11/E12 default readouts per profile and the E03 verdicts. Output: one versioned bank (JSON) + run report.

Stage order is enforced and logged: the hypothesis hash is in the run log before E04 starts (hypothesis honesty).
Interviews (E07) and automated drills (E15) are cut for Dec 2; the bank says so.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

from .live.engine import Bank, ControlEngine, is_anchor, rank, select
from .live.profiles import standard_set
from .seedbank import ANCHORS, load_seeds
from .stages import e02_sampler, e03_hypothesis, e04_cards, e05_dedupe, e06_ladder, e08_evidence, e09_sizing, e10_judges
from .stages.e14_decompose import decompose, family_view
from .util import PROTO_C, L, find_unlabeled, load_json, load_yaml, sha256_hex

VERSIONS = {"lattice": "lattice@1", "rubric": "rubric@2", "components": "components@2", "needs": "needs@1",
            "org": "org@2 (in_house_cover subset)", "sizing_topdown": "sizing-topdown@0", "card": "card@ (fork-c) + needs[]",
            "partner_fit": "partner_fit@0 (proposed)", "partner_stake": "partner_stake@0 (proposed)"}
CUT = {"E07": "simulated interviews cut for Dec 2", "E15": "Fork C writes the top-3 drills by Nov 24"}


@dataclass
class RunConfig:
    run_id: str = "run-1"
    seed: int = 1
    cell_budget: int = 216                   # ~20 cells per actor type (lattice quota min 6); ~650 raw cards
    n_per_cell: int = 3
    profiles_source: str = "priors"          # priors (controls@2 fixture) | controls1
    adoption_share: float = 0.10
    hello_world_result: str | None = None    # path to a HelloWorldResult@1 (A's hook); None -> placement_only
    as_of: str | None = None                 # ISO date the gate is judged on; None -> today
    teacher: dict | None = None              # {"endpoint": ..., "model": {repo, revision, sha256}}; None -> template@1
    judge_results: str | None = None         # path to judge-batch output; None -> J0
    k: int = 10
    lattice_path: str = str(PROTO_C / "lattice-v1.yaml")
    rubric_path: str = str(PROTO_C / "rubric-v2.yaml")
    log: list = field(default_factory=list)


def _log(cfg: RunConfig, stage: str, **summary):
    cfg.log.append({"step": len(cfg.log) + 1, "stage": stage, **summary})


def partner_stake(card: dict, pf: dict) -> tuple[float, list[str]]:
    """Rule partner_stake@0 (proposed to Fork C): 1 + specific builder (1) + effort (S 2, M 1, L 0) + partner owner (1), max 5."""
    specific = pf["builder_types"][0] not in ("general_assistant", "any_builder")
    owner = "partner" in card["business_owners"]
    v = min(5, 1 + specific + {"S": 2, "M": 1, "L": 0}[pf["build_effort"]] + owner)
    tags = [t for t, on in (("market", specific or owner), ("effort", pf["build_effort"] in ("S", "M")),
                            ("platform_risk", len(pf["conformance_risks"]) <= 2)) if on] or ["market"]
    return float(v), tags


def assemble(card: dict, *, family_id: str, members: list, lineage: dict, cover, refs, rubric, adoption, judged=None) -> dict:
    ladder = e06_ladder.place(card, cover)
    evidence = e08_evidence.join(card, refs)
    sizing = e09_sizing.size(card, adoption)
    judged = judged or e10_judges.j0_scores(card)
    view = family_view({**card, "value_tier": ladder["tier"]})
    dec = decompose(view)
    pf = e04_cards.partner_fit(card, dec)
    p_stake, p_tags = partner_stake(card, pf)
    W = {k: v["weight"] for k, v in rubric["criteria"].items()}
    x = {"pain": judged["pain"], "value_at_stake": None, "tier": ladder["tier_x"]["value"] if ladder["tier"] == 2 else e06_ladder.tier_x(ladder["tier"], 0),
         "demo_ability": judged["demo_ability"], "evidence": evidence["x"]["value"], "novelty": judged["novelty"],
         "walmart_stake": None, "visible_approval": judged["visible_approval"], "reuse": judged["reuse"]}
    x["tier"] = e06_ladder.tier_x(ladder["tier"], ladder["uplift_conditions"])      # unrounded, as score_v2
    sp = {"x": x, "weights": W, "risk_w": rubric["penalty"]["risk"]["weight"], "risk": judged["risk"],
          "vas_usd_at_base": sizing["usd_per_year"]["value"], "base_adoption": adoption,
          "stake": {"in_house": float(judged["walmart_stake"]), "partner": p_stake}, "judge": judged.get("_judge", "J0")}
    from .live.engine import family_score
    fam = {"family_id": family_id, "title": card["title"], "family": card["family"], "cluster": card.get("cluster", family_id),
           "actor_type": card["actor_type"], "actor": card.get("actor", ""), "role_in_order": card["role_in_order"],
           "segment": card["segment"], "protected": card["protected"], "job": card["job"], "quadrant": card["quadrant"],
           "situation": card["situation"], "trigger": card["trigger"], "agent_surface": card["agent_surface"],
           "sparky_today": card["sparky_today"], "specific_brief": card["specific_brief"], "approval_moment": card["approval_moment"],
           "business_owners": card["business_owners"], "lanes_to_tune": card["lanes_to_tune"], "walmart_stake": card["walmart_stake"],
           "gateway_only": card["gateway_only"], "tier": ladder["tier"], "ladder": ladder, "evidence": evidence, "sizing": sizing, "decomposition": dec,
           "needs": dec["needs"], "partner_fit": pf, "partner_stake_tags": p_tags,
           "build_effort_days": {"value": dec["build_effort_days"], "label": "derived:synthetic"},
           "score_parts": sp, "anchor": is_anchor(family_id), "members": members, "lineage": lineage,
           "representative": card["card_id"], "generator": card["source"]["generator"], "synthetic": True}
    fam["scores"] = {"in_house": L(family_score(fam, "in_house", adoption), "score:rubric@2"),
                     "partner": L(family_score(fam, "partner", adoption), "score:rubric@2"),
                     "x": e10_judges.labeled_x({**x, "value_at_stake": e10_judges.vas_x(sizing["usd_per_year"]["value"]),
                                                "walmart_stake": judged["walmart_stake"]}),
                     "partner_stake": L(p_stake, "score:partner_stake@0")}
    return fam


def _seed_card(s: dict, refs) -> dict:
    cell = {"cell_id": "RUN0", "actor_type": s["actor_type"], "job": s["job"], "trigger": s["trigger"],
            "agent_surface": s["surface"], "quadrant": s["quadrant"]}
    return e04_cards.card_from_seed(s, cell, random.Random(0), variant=0, cell_fit={}, refs=refs)


def replay_run0(adoption: float = 0.10) -> dict:
    """Run 0 replayed through the engine: every seed is one family under its own id (the prior bank and C parity)."""
    seeds, refs = load_seeds()
    rubric = load_yaml(PROTO_C / "rubric-v2.yaml"); cover = e06_ladder.load_cover()
    fams = []
    for s in seeds:
        c = _seed_card(s, refs)
        fams.append(assemble(c, family_id=s["id"], members=[c["card_id"]], lineage={"prior_id": s["id"], "similarity": 1.0, "matched": True},
                             cover=cover, refs=refs, rubric=rubric, adoption=adoption))
    data = {"run_id": "run-0-replay", "families": fams, "versions": VERSIONS}
    data["bank_id"] = sha256_hex({"run": data["run_id"], "families": fams})[:16]
    return data


PASS_REQUIRED_FROM = "2026-11-25"   # fork-a/hello-world-spec.md: placement_only accepted through Nov 24


def stage0(cfg: RunConfig, refs, cover) -> dict:
    """Hello world gate (fork-a/hello-world-spec.md, HelloWorldResult@1). The placement self-test always runs.
    Through Nov 24 a missing hook result or `status: placement_only` is accepted; from Nov 25 the run needs
    `status: pass` from a `full` run (D: engine-run requires it). `fail` or `not_run` aborts at any date."""
    seeds = {s["id"]: s for s in load_seeds()[0]}
    anch = {}
    for aid in ANCHORS:
        c = _seed_card(seeds[aid], refs)
        anch[aid] = {"ladder": e06_ladder.place(c, cover), "evidence": e08_evidence.join(c, refs)}
    placement = e06_ladder.anchors_ok(anch)
    as_of = cfg.as_of or os.environ.get("DE_AS_OF") or dt.date.today().isoformat()
    out = {"placement": placement, "status": "placement_only", "as_of": as_of, "pass_required_from": PASS_REQUIRED_FROM}
    if cfg.hello_world_result:
        hw = load_json(cfg.hello_world_result)
        out["hook"] = {k: hw.get(k) for k in ("result_version", "oracle_version", "status", "mode", "k", "bundle_id",
                                              "adapter_id", "capability_mode", "highest_tier", "tiers", "zero_tolerance")}
        out["status"] = hw.get("status", "not_run")
    problems = []
    if not placement["placement_pass"]:
        problems.append("placement self-test failed")
    if out["status"] in ("fail", "not_run"):
        problems.append(f"hook status {out['status']}")
    if as_of >= PASS_REQUIRED_FROM and not (out["status"] == "pass" and out.get("hook", {}).get("mode") == "full"):
        problems.append(f"from {PASS_REQUIRED_FROM} stage 0 needs status pass from a full hook run")
    if problems:
        raise RuntimeError(f"hello world gate: run aborts ({'; '.join(problems)})")
    return out


def run(cfg: RunConfig) -> dict:
    seeds, refs = load_seeds()
    lattice = load_yaml(cfg.lattice_path); rubric = load_yaml(cfg.rubric_path); cover = e06_ladder.load_cover()
    axes = e02_sampler.axes_from_lattice(lattice)
    profiles, params = standard_set(cfg.profiles_source)

    hello = stage0(cfg, refs, cover); _log(cfg, "stage0", status=hello["status"])

    prior = replay_run0(cfg.adoption_share)
    pe = ControlEngine(Bank(prior), profiles, params, k=cfg.k)
    hyps = {}
    for lens, pid in e03_hypothesis.LENS_DEFAULT_PROFILE.items():
        top = select(rank(pe.bank, profiles[pid], params), cfg.k)
        hyps[lens] = e03_hypothesis.write(lens, top[0]["f"], prior["run_id"], prior["bank_id"])
        _log(cfg, "E03", lens=lens, hypothesis_hash=hyps[lens]["hash"])

    samp = e02_sampler.sample(lattice, cfg.seed, cfg.cell_budget)
    _log(cfg, "E02", cells=len(samp["cells"]), cells_hash=samp["cells_hash"], empty_actor_types=samp["coverage"]["empty_actor_types"])

    teacher = None
    if cfg.teacher:
        teacher = e04_cards.LocalTeacher(cfg.teacher["endpoint"], cfg.teacher["model"])
    gen = e04_cards.generate(samp["cells"], cfg.seed, cfg.n_per_cell, teacher)
    anchor_cards = [_seed_card({**{s["id"]: s for s in seeds}[a]}, refs) for a in ANCHORS]
    for c in anchor_cards:
        c["cell_id"] = "ANCHOR"
    cards = gen["cards"] + anchor_cards
    invalid = {c["card_id"]: e for c in cards if (e := e04_cards.validate(c, axes))}
    if invalid:
        raise RuntimeError(f"E04 schema failures: {list(invalid.items())[:3]}")
    _log(cfg, "E04", cards=len(cards), generator=gen["generator"], fallback_used=gen["fallback_used"], schema_valid=1.0)

    prior_texts = [{"id": s["id"], "title": s["title"], "situation": s["situation"], "specific_brief": s["specific_brief"]} for s in seeds]
    dd = e05_dedupe.dedupe(cards, prior_texts)
    _log(cfg, "E05", families=len(dd["families"]), max_inter_family_similarity=dd["max_inter_family_similarity"])

    judged_ext = load_json(cfg.judge_results) if cfg.judge_results else {}
    fams = []
    for fm in dd["families"]:
        rep = fm["_rep"]
        judged = None
        if fm["family_id"] in judged_ext:
            agg = e10_judges.aggregate(judged_ext[fm["family_id"]]["panel"])
            judged = {**agg["median"], "_judge": f"panel k={agg['k']}", "_flags": agg["flagged"]}
        fams.append(assemble(rep, family_id=fm["family_id"], members=fm["members"], lineage=fm["lineage"], cover=cover,
                             refs=refs, rubric=rubric, adoption=cfg.adoption_share, judged=judged))
    _log(cfg, "E06+E08+E09+E10+E14", families=len(fams), judge="panel" if judged_ext else "J0",
         sizing_gaps_flagged=sum(f["sizing"]["gap_flagged"] for f in fams))

    data = {"contract": "bank@0 (engine)", "run_id": cfg.run_id, "seed": cfg.seed, "versions": VERSIONS,
            "controls_source": params["source"], "generator": gen["generator"], "fallback_used": gen["fallback_used"],
            "judge": "panel" if judged_ext else "J0 (seed judge; fallback)", "hello_world": hello,
            "coverage": samp["coverage"], "cells_hash": samp["cells_hash"], "rejected_invalid_cells": samp["rejected_invalid"],
            "dedupe": {k: dd[k] for k in ("threshold", "lineage_threshold", "max_inter_family_similarity", "cards")},
            "cut": CUT, "hypotheses": hyps, "families": sorted(fams, key=lambda f: f["family_id"]),
            "sparky_test_queue": e08_evidence.sparky_test_queue(fams),
            "novel_families": [f["family_id"] for f in fams if not f["lineage"]["matched"]],
            "unreached_seed_families": sorted({s["id"] for s in seeds} - {f["family_id"].split("~")[0] for f in fams})}
    data["bank_id"] = sha256_hex({"run": cfg.run_id, "seed": cfg.seed, "families": data["families"]})[:16]

    eng = ControlEngine(Bank(data), profiles, params, k=cfg.k)
    data["readouts"] = {}
    for pid, p in profiles.items():
        ro = eng.readout(p, pid)
        data["readouts"][pid] = {"top_k": [x["family_id"] for x in ro["top_k"]], "answer_first": ro["answer_first"],
                                 "clamps": len(ro["clamp_log"]), "unlabeled_numbers": ro["unlabeled_numbers"]}
    for lens, pid in e03_hypothesis.LENS_DEFAULT_PROFILE.items():
        hyps[lens]["verdict"] = e03_hypothesis.verdict(hyps[lens], data["readouts"][pid]["top_k"])
    _log(cfg, "E11+E12", profiles=len(profiles), verdicts={l: h["verdict"] for l, h in hyps.items()})
    data["run_log"] = cfg.log
    data["unlabeled_numbers_in_sizing"] = sum(len(find_unlabeled(f["sizing"])) for f in fams)
    return data


def label_sheet(bank: dict) -> str:
    """E13 labels@0 sheet for the owner: keep / kill / merge + reason, one row per family, top-10 ranks per profile."""
    tops = {pid: r["top_k"] for pid, r in bank["readouts"].items()}
    cols = ["family_id", "title", "actor_type", "job", "tier", "score_in_house", "score_partner", "value_at_stake_usd_yr",
            "vas_label", "evidence", "build_effort_days", "lineage", "cards", "best_rank", "profiles_in_top10",
            "keep_kill_merge", "merge_into", "reason"]
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(cols)
    def best(fid):
        r = [t.index(fid) + 1 for t in tops.values() if fid in t]
        return min(r) if r else ""
    fams = sorted(bank["families"], key=lambda f: (best(f["family_id"]) or 99, -f["scores"]["in_house"]["value"]))
    for f in fams:
        fid = f["family_id"]
        w.writerow([fid, f["title"], f["actor_type"], f["job"], f["tier"], f["scores"]["in_house"]["value"], f["scores"]["partner"]["value"],
                    f["sizing"]["usd_per_year"]["value"], f["sizing"]["usd_per_year"]["label"], f["evidence"]["level"],
                    f["build_effort_days"]["value"], f["lineage"]["prior_id"] if f["lineage"]["matched"] else "new", len(f["members"]),
                    best(fid), ";".join(p for p, t in tops.items() if fid in t), "", "", ""])
    return buf.getvalue()

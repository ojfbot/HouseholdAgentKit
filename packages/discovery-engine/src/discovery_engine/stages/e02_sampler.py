"""E02 — lattice + seeded cell sampler + coverage map (stage 1). Deterministic.

Spec (lattice@1 `sampling`): pairwise over (actor_type x job x trigger x agent_surface x quadrant), stratified by
actor_type; quotas min_cells_per_actor_type and min_cells_per_quadrant; invalid combinations filtered and logged.
Oracle (components@2 E02): same seed -> same cells; no empty actor type; pairwise coverage reported.

Full pairwise coverage of these axes needs >= 25 x 20 = 500 cells (trigger x surface alone), more than one run's
card budget, so the sampler is a seeded greedy pairwise cover under a cell budget: each slot takes the candidate
that covers the most uncovered pairs, with actor types filled round-robin. The coverage map reports the fraction
of pairs covered per axis pair, so a bigger budget is a config change, not a code change.
"""
from __future__ import annotations

import itertools
import random
from collections import Counter

from ..util import clean_axis, load_yaml, sha256_hex

AXES = ("actor_type", "job", "trigger", "agent_surface", "quadrant")


def axes_from_lattice(lattice: dict) -> dict[str, list[str]]:
    a = lattice["axes"]
    return {
        "actor_type": list(a["actor_type"].keys()),
        "job": clean_axis(a["job_to_be_done"]),
        "trigger": clean_axis(a["trigger"]),
        "agent_surface": clean_axis(a["agent_surface"]),
        "quadrant": clean_axis(a["hidden_problem_quadrant"]),
    }


def invalid_pairs(lattice: dict) -> set[tuple[str, str]]:
    """Two-value invalid combinations from lattice@1 (the role_in_order rule applies to cards, not cells)."""
    out = set()
    for combo in lattice["sampling"].get("invalid_combinations", []):
        vals = [str(v) for v in combo if not isinstance(v, dict)]
        if len(vals) == 2 and not any(":" in v for v in vals):
            out.add((vals[0], vals[1]))
    return out


def _pairs(cell: dict) -> set[tuple]:
    return {(a, cell[a], b, cell[b]) for a, b in itertools.combinations(AXES, 2)}


def sample(lattice: dict, seed: int, budget: int | None = None, candidates: int = 24) -> dict:
    ax = axes_from_lattice(lattice)
    quota = lattice["sampling"]["quota"]
    per_actor = quota["min_cells_per_actor_type"]
    n_actor = len(ax["actor_type"])
    budget = budget or max(per_actor * n_actor, quota["min_cells_per_quadrant"] * len(ax["quadrant"]))
    bad = invalid_pairs(lattice)
    rng = random.Random(seed)
    covered: set = set()
    cells, rejected = [], Counter()

    def valid(c):
        vals = set(c.values())
        for x, y in bad:
            if x in vals and y in vals:
                rejected[f"{x}+{y}"] += 1
                return False
        return True

    quad_count = Counter()
    for slot in range(budget):
        actor = ax["actor_type"][slot % n_actor]                      # stratified round-robin
        need_quads = [q for q in ax["quadrant"] if quad_count[q] < quota["min_cells_per_quadrant"]]
        best, best_gain = None, -1
        for _ in range(candidates):
            c = {"actor_type": actor, "job": rng.choice(ax["job"]), "trigger": rng.choice(ax["trigger"]),
                 "agent_surface": rng.choice(ax["agent_surface"]),
                 "quadrant": rng.choice(need_quads or ax["quadrant"])}
            if not valid(c):
                continue
            gain = len(_pairs(c) - covered)
            if gain > best_gain:
                best, best_gain = c, gain
        if best is None:
            continue
        covered |= _pairs(best)
        quad_count[best["quadrant"]] += 1
        best["cell_id"] = "C-" + sha256_hex({"seed": seed, "slot": slot, **best})[:10]
        best["slot"] = slot
        cells.append(best)

    return {"cells": cells, "coverage": coverage(cells, ax), "seed": seed, "budget": budget,
            "taxonomy_version": lattice["taxonomy_version"], "rejected_invalid": dict(rejected),
            "cells_hash": sha256_hex([{k: c[k] for k in AXES} for c in cells])}


def coverage(cells: list[dict], ax: dict) -> dict:
    by_actor = Counter(c["actor_type"] for c in cells)
    by_quad = Counter(c["quadrant"] for c in cells)
    pair_cov = {}
    for a, b in itertools.combinations(AXES, 2):
        seen = {(c[a], c[b]) for c in cells}
        pair_cov[f"{a}x{b}"] = round(len(seen) / (len(ax[a]) * len(ax[b])), 3)
    return {"cells": len(cells), "by_actor_type": dict(by_actor), "by_quadrant": dict(by_quad),
            "empty_actor_types": [a for a in ax["actor_type"] if by_actor[a] == 0],
            "values_seen": {a: len({c[a] for c in cells}) for a in AXES},
            "values_total": {a: len(ax[a]) for a in AXES},
            "pairwise_coverage": pair_cov}


def load_and_sample(lattice_path, seed: int, budget: int | None = None) -> dict:
    return sample(load_yaml(lattice_path), seed, budget)

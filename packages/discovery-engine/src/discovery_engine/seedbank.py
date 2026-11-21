"""Fork C's run-0 seed bank (bank.py + bank_v2.py, vendored verbatim under prototypes/fork_c), as structured seeds.

Seeds are the engine's golden set and the template fallback's source: E04 with no local teacher re-emits seed
problems per sampled cell. Seeds are agent-authored (Fork C session), which D's rules allow (`source: agent_seed`).
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache

from .util import PROTO_C

COND = {"T": "outside_trigger", "U": "unattended", "C": "context_walmart_shouldnt_hold", "O": "other_people", "R": "completion_under_rules"}
KEYS = "id slug title actor_type persona role situation trigger surface conds gate gate_note approval stake ev ev_ref risk quadrant cluster rel f s W V D R Nv".split()
XK = "job segment protected sparky_today specific_brief owners lanes seg seg_src freq basket gap".split()
ANCHORS = ("PF-51", "G-01", "PF-28")   # rubric@2 selection.anchors_excluded


def stake_tags(s: str) -> list[str]:
    """Verbatim port of score_v2.stake_tags (in-house stake terms from the free-text stake)."""
    s = s.lower(); t = set()
    if any(w in s for w in ["revenue", "new customer", "share of wallet", "order success", "retention"]): t.add("revenue")
    if any(w in s for w in ["trust", "retention", "order success", "substitution"]): t.add("trust")
    if any(w in s for w in ["cost", "waste", "substitution", "delivery success"]): t.add("cost")
    if any(w in s for w in ["risk", "velocity"]): t.add("risk")
    return sorted(t or {"revenue"})


def _import_bank_v2():
    if str(PROTO_C) not in sys.path:
        sys.path.insert(0, str(PROTO_C))
    spec = importlib.util.spec_from_file_location("fork_c_bank_v2", PROTO_C / "bank_v2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def load_seeds() -> tuple[list[dict], dict]:
    mod = _import_bank_v2()
    seeds = []
    for t in mod.F:
        d = dict(zip(KEYS, t)); d.update(dict(zip(XK, mod.X[d["id"]])))
        d["gateway_only"] = [COND[c] for c in d["conds"]]
        d["walmart_stake"] = stake_tags(d["stake"])
        seeds.append(d)
    return seeds, dict(mod.REFS)


def seed_by_id() -> dict[str, dict]:
    return {s["id"]: s for s in load_seeds()[0]}

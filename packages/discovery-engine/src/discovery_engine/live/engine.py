"""E11 control engine + E12 portfolio selector + Readout@0 + ControlDelta@0. Deterministic, live on stage.

E11 (stage 9). priority = score_lens x w_segment(actor) x w_intent(job) x owner_boost x stake_fit   (controls@1 formula)
  - bounds clamp segment/intent weights; protected families never get w_segment or w_intent below 1.0 (fairness
    floor; every clamp logged); never-tunable keys are rejected and logged as control.rejected.
  - lens: in_house | partner. Stake-dependent terms are exactly three: the rubric's stake criterion inside the score
    (walmart_stake vs partner_stake), stake_fit (value vector over the lens's stake tags) and owner_boost (function
    owner vs partner builder type). A lens flip changes nothing else (oracle `lens_invariance`).
  - scenario: adoption_share rescales value at stake (finance's what-if); it re-scores only the value_at_stake criterion.
E12 (stage 10). Fork C's greedy diversity selection, unchanged (max per actor type, max per cluster, min actor types
  in the top 10, anchors excluded), plus a Pareto flag over (priority up, build effort down) and 2x2 coordinates.
Readout@0 and ControlDelta@0 are DRAFTS (fields not yet defined by Fork F); every number is a labeled object.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import statistics
import time
from collections import Counter
from pathlib import Path

from ..seedbank import ANCHORS
from ..util import L, find_unlabeled, sha256_hex
from .profiles import IN_HOUSE_KEYS, PARTNER_KEYS, clone, profile_hash

DIV_DEFAULT = {"max_per_actor_type": 3, "max_per_cluster": 1, "min_actor_types_in_top10": 6}
LENSES = ("in_house", "partner")
TUNABLE_ROOTS = {"segment", "intent", "value", "partner_value"}
READOUT_ALLOW = frozenset({"rank", "seq", "k", "from", "to", "compute_ms", "deltas_applied", "unlabeled_numbers", "families"})


def vas_x(usd: float) -> float:
    return min(5, max(0, math.log10(max(usd, 1)) - 5))


def is_anchor(fid: str) -> bool:
    return fid.split("~")[0] in ANCHORS


class Bank:
    """A versioned, read-only bank. bank_id = sha256 over the canonical families + run metadata hash."""

    def __init__(self, data: dict):
        self.data = data
        self.families = data["families"]
        self.by_id = {f["family_id"]: f for f in self.families}
        self.bank_id = data.get("bank_id") or sha256_hex({"run": data.get("run_id"), "families": self.families})[:16]

    @classmethod
    def load(cls, path) -> "Bank":
        return cls(json.loads(Path(path).read_text()))


def family_score(f: dict, lens: str, adoption: float, neutral_stake: bool = False) -> float:
    """rubric@2 total, summed in the rubric's criterion order exactly as score_v2.total does (parity), with the
    lens's stake criterion and the scenario's value at stake swapped in."""
    sp = f["score_parts"]
    vas = sp["vas_usd_at_base"] * adoption / sp["base_adoption"]
    x = dict(sp["x"])
    x["value_at_stake"] = vas_x(vas)
    x["walmart_stake"] = 2.5 if neutral_stake else sp["stake"][lens]
    w = sp["weights"]
    return round(100 * (sum(w[k] * x[k] for k in w) / 5 - sp["risk_w"] * sp["risk"] / 5), 1)


def weight(profile: dict, f: dict, params: dict, neutral_stake: bool = False) -> tuple[float, list, dict]:
    lens = profile["lens"]
    lo, hi = params["bounds"]["segment"]; ilo, ihi = params["bounds"]["intent"]
    ws0 = profile["segment"].get(f["actor_type"], 1.0); wi0 = profile["intent"].get(f["job"], 1.0)
    ws, wi = min(hi, max(lo, ws0)), min(ihi, max(ilo, wi0))
    clamps = []
    if ws != ws0: clamps.append({"family_id": f["family_id"], "term": "segment", "asked": ws0, "applied": ws, "code": "OUT_OF_BOUNDS"})
    if wi != wi0: clamps.append({"family_id": f["family_id"], "term": "intent", "asked": wi0, "applied": wi, "code": "OUT_OF_BOUNDS"})
    if f["protected"]:
        if ws < 1.0: clamps.append({"family_id": f["family_id"], "term": "segment", "asked": ws, "applied": 1.0, "code": "FAIRNESS_FLOOR"}); ws = 1.0
        if wi < 1.0: clamps.append({"family_id": f["family_id"], "term": "intent", "asked": wi, "applied": 1.0, "code": "FAIRNESS_FLOOR"}); wi = 1.0
    if neutral_stake:
        ob, sf = 1.0, 1.0
    else:
        if lens == "in_house":
            ob = params["owner_boost"] if profile.get("owner") and profile["owner"] in f["business_owners"] else 1.0
            vw, tags = profile["value"], f["walmart_stake"]
        else:
            ob = params["owner_boost"] if profile.get("partner_owner") and profile["partner_owner"] in f["partner_fit"]["builder_types"] else 1.0
            vw, tags = profile["partner_value"], f["partner_stake_tags"]
        top_w = max(vw.values()) if vw else 0.0
        sf = 1.0 if top_w <= 0 else (0.6 + 0.8 * max(vw.get(k, 0.0) for k in tags) / top_w) / 1.4
    return ws * wi * ob * sf, clamps, {"w_segment": ws, "w_intent": wi, "owner_boost": ob, "stake_fit": sf}


def rank(bank: Bank, profile: dict, params: dict, neutral_stake: bool = False) -> list[dict]:
    adoption = profile["scenario"]["adoption_share"]
    out = []
    for f in bank.families:
        score = family_score(f, profile["lens"], adoption, neutral_stake)
        m, cl, terms = weight(profile, f, params, neutral_stake)
        out.append({"f": f, "family_id": f["family_id"], "actor_type": f["actor_type"], "cluster": f["cluster"],
                    "score": score, "priority": score * m, "clamps": cl, "terms": terms})
    return sorted(out, key=lambda r: (-r["priority"], r["family_id"]))


def select(ranked: list[dict], k: int = 10, div: dict | None = None) -> list[dict]:
    """Fork C's score_v2.select, unchanged except a guard when no candidate can fix actor diversity."""
    div = div or DIV_DEFAULT
    rk = [r for r in ranked if not is_anchor(r["family_id"])]
    pick, pt, pc = [], Counter(), Counter()
    for r in rk:
        if pt[r["actor_type"]] >= div["max_per_actor_type"] or pc[r["cluster"]] >= div["max_per_cluster"]:
            continue
        pick.append(r); pt[r["actor_type"]] += 1; pc[r["cluster"]] += 1
        if len(pick) == k:
            break
    while len({p["actor_type"] for p in pick}) < div["min_actor_types_in_top10"]:
        have = {p["actor_type"] for p in pick}
        cand = next((r for r in rk if r not in pick and r["actor_type"] not in have and pc[r["cluster"]] == 0), None)
        if cand is None:
            break
        common = Counter(p["actor_type"] for p in pick).most_common(1)[0][0]
        out = [p for p in pick if p["actor_type"] == common][-1]; pick.remove(out); pc[out["cluster"]] -= 1
        pick.append(cand); pc[cand["cluster"]] += 1; pick.sort(key=lambda r: -r["priority"])
    return pick


def pareto(ranked: list[dict]) -> set[str]:
    pts = [(r["priority"], r["f"]["build_effort_days"]["value"], r["family_id"]) for r in ranked if not is_anchor(r["family_id"])]
    front = set()
    for p, e, i in pts:
        if not any((p2 >= p and e2 <= e) and (p2 > p or e2 < e) for p2, e2, _ in pts):
            front.add(i)
    return front


def two_by_two(top: list[dict], ranked: list[dict]) -> dict:
    pool = [r for r in ranked if not is_anchor(r["family_id"])]
    pmax = max(r["priority"] for r in pool) or 1.0
    emax = max(r["f"]["build_effort_days"]["value"] for r in pool) or 1
    imp_t = statistics.median(r["priority"] / pmax for r in pool)
    eff_t = statistics.median(r["f"]["build_effort_days"]["value"] / emax for r in pool)
    pts = []
    for r in top:
        imp = r["priority"] / pmax; eff = r["f"]["build_effort_days"]["value"] / emax
        cell = ("quick_win" if eff < eff_t else "big_bet") if imp >= imp_t else ("fill_in" if eff < eff_t else "deprioritize")
        pts.append({"family_id": r["family_id"], "impact": L(round(imp, 3), "score:priority"),
                    "effort": L(round(eff, 3), "derived:synthetic"), "cell": cell})
    return {"axes": {"impact": "priority / max priority in the bank", "effort": "build effort days (E14 components) / max"},
            "thresholds": {"impact": L(round(imp_t, 3), "score:priority"), "effort": L(round(eff_t, 3), "derived:synthetic")},
            "points": pts}


class ControlEngine:
    def __init__(self, bank: Bank, profiles: dict, params: dict, log_path: str | Path | None = None,
                 hypotheses: dict | None = None, k: int = 10, div: dict | None = None):
        self.bank, self.profiles, self.params, self.k, self.div = bank, profiles, params, k, div or DIV_DEFAULT
        self.log_path = Path(log_path) if log_path else None
        self.hypotheses = hypotheses or bank.data.get("hypotheses", {})
        self.sessions: dict[str, dict] = {}
        self.events: list[dict] = []
        self._prev_hash = "0" * 64

    # ---------------- state
    def session(self, sid: str = "stage", profile_id: str = "default") -> dict:
        if sid not in self.sessions:
            self.sessions[sid] = {"base": profile_id, "profile": clone(self.profiles[profile_id]), "deltas": []}
        return self.sessions[sid]

    # ---------------- ControlDelta@0
    def apply(self, req: dict, sid: str = "stage") -> tuple[dict, dict]:
        t0 = time.perf_counter()
        op = req.get("op")
        s = self.session(sid, req.get("profile_id", "default"))
        if op == "switch":
            self.sessions[sid] = s = {"base": req["value"], "profile": clone(self.profiles[req["value"]]), "deltas": []}
        prof = s["profile"]
        before = profile_hash(prof)
        status, codes, prev, applied = "applied", [], None, req.get("value")
        path = list(req.get("path") or [])
        nt = set(self.params["never_tunable"])
        if any(str(p) in nt for p in path) or (op in ("set", "scale", "reset") and path and path[0] not in TUNABLE_ROOTS):
            status, codes = "rejected", ["NEVER_TUNABLE" if any(str(p) in nt for p in path) else "UNKNOWN_PATH"]
        elif op in ("set", "scale", "reset"):
            root, key = path[0], path[1] if len(path) > 1 else None
            valid = {"value": IN_HOUSE_KEYS, "partner_value": PARTNER_KEYS}.get(root)
            if key is None or (valid and key not in valid):
                status, codes = "rejected", ["UNKNOWN_PATH"]
            else:
                prev = prof[root].get(key, 1.0 if root in ("segment", "intent") else 0.0)
                if op == "reset":
                    base = self.profiles[s["base"]][root]
                    applied = base.get(key, 1.0 if root in ("segment", "intent") else 0.0)
                else:
                    applied = float(req["value"]) * (prev if op == "scale" else 1.0)
                if root in ("segment", "intent"):
                    lo, hi = self.params["bounds"][root]
                    if not lo <= applied <= hi:
                        applied = min(hi, max(lo, applied)); status, codes = "clamped", ["OUT_OF_BOUNDS"]
                else:
                    if not 0.0 <= applied <= 1.0:
                        applied = min(1.0, max(0.0, applied)); status, codes = "clamped", ["OUT_OF_BOUNDS"]
                prof[root][key] = applied
        elif op == "lens":
            if req.get("value") not in LENSES:
                status, codes = "rejected", ["UNKNOWN_LENS"]
            else:
                prev, prof["lens"] = prof["lens"], req["value"]
        elif op == "scenario":
            prev = prof["scenario"]["adoption_share"]
            applied = float(req["value"])
            if not 0.01 <= applied <= 0.5:
                applied = min(0.5, max(0.01, applied)); status, codes = "clamped", ["OUT_OF_BOUNDS"]
            prof["scenario"]["adoption_share"] = applied
        elif op != "switch":
            status, codes = "rejected", ["UNKNOWN_OP"]
        seq = len(self.events) + 1
        delta_id = "CD-" + sha256_hex([seq, sid, op, path, applied, self._prev_hash])[:12]
        if status != "rejected":
            s["deltas"].append(delta_id)
        readout = self.readout(prof, profile_id=s["base"], deltas=s["deltas"])
        ev = {"contract": "ControlDelta@0 (draft)", "delta_id": delta_id, "seq": seq, "session": sid,
              "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
              "bank_id": self.bank.bank_id, "profile_id": s["base"], "base_profile_hash": before,
              "profile_hash": profile_hash(prof), "op": op, "path": path, "requested": req.get("value"), "prev": prev,
              "applied": applied, "status": status, "codes": codes, "clamps_in_readout": len(readout["clamp_log"]),
              "actor": req.get("actor", {"role": "EL"}), "reason": req.get("reason", ""),
              "readout_hash": readout["readout_hash"], "prev_hash": self._prev_hash}
        ev["hash"] = sha256_hex(ev)
        self._prev_hash = ev["hash"]
        self.events.append(ev)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev) + "\n")
        readout["compute_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return ev, readout

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for ev in self.events:
            body = {k: v for k, v in ev.items() if k != "hash"}
            if ev["prev_hash"] != prev or sha256_hex(body) != ev["hash"]:
                return False
            prev = ev["hash"]
        return True

    # ---------------- Readout@0
    def readout(self, profile: dict, profile_id: str | None = None, deltas: list | None = None) -> dict:
        t0 = time.perf_counter()
        pid = profile_id or profile["profile_id"]
        ranked = rank(self.bank, profile, self.params)
        top = select(ranked, self.k, self.div)
        base_prof = self.profiles.get(pid, profile)
        base_top = [r["family_id"] for r in select(rank(self.bank, base_prof, self.params), self.k, self.div)]
        front = pareto(ranked)
        clamp_log = [c for r in ranked for c in r["clamps"]]
        hyp = self.hypotheses.get(profile["lens"])
        items = []
        for i, r in enumerate(top, 1):
            f = r["f"]
            items.append({"rank": i, "family_id": r["family_id"], "title": f["title"], "actor_type": f["actor_type"],
                          "job": f["job"], "tier": L(f["tier"], "score:rubric@2"),
                          "priority": L(round(r["priority"], 1), "score:priority"), "score": L(r["score"], "score:rubric@2"),
                          "value_at_stake_usd": L(round(f["sizing"]["usd_per_year"]["value"] * profile["scenario"]["adoption_share"] / f["score_parts"]["base_adoption"]),
                                                  f["sizing"]["usd_per_year"]["label"]),
                          "terms": {k: L(round(v, 3), "weight:controls") for k, v in r["terms"].items()},
                          "on_pareto": r["family_id"] in front, "components": f["decomposition"]["components"],
                          "moved": None if r["family_id"] not in base_top else {"from": base_top.index(r["family_id"]) + 1, "to": i}})
        lead = items[0] if items else None
        moved_in = [x["family_id"] for x in items if x["family_id"] not in base_top]
        answer = (f"Under {pid} ({profile['lens']} lens), the top opportunity is {lead['title']} ({lead['family_id']}), "
                  f"priority {lead['priority']['value']}; {len(moved_in)} of the top {len(items)} "
                  f"{'is' if len(moved_in) == 1 else 'are'} new versus the profile's base."
                  if lead else "No eligible families.")
        ro = {"contract": "Readout@0 (draft)", "bank_id": self.bank.bank_id, "run_id": self.bank.data.get("run_id"),
              "profile_id": pid, "profile_hash": profile_hash(profile), "lens": profile["lens"],
              "scenario": {"adoption_share": L(profile["scenario"]["adoption_share"], "synthetic")},
              "deltas_applied": len(deltas or []), "answer_first": answer,
              "hypothesis": ({"text": hyp["text"], "hash": hyp["hash"], "verdict": hyp.get("verdict")} if hyp else None),
              "top_k": items, "moved_in": moved_in, "moved_out": [i for i in base_top if i not in [x["family_id"] for x in items]],
              "two_by_two": two_by_two(top, ranked), "pareto": sorted(front), "clamp_log": clamp_log,
              "hello_world": self.bank.data.get("hello_world", {}).get("status"),
              "labels": "every number is {value,label}; see util.LABEL_RX"}
        ro["unlabeled_numbers"] = len(find_unlabeled(ro, allow=READOUT_ALLOW))
        ro["readout_hash"] = sha256_hex({k: v for k, v in ro.items() if k not in ("compute_ms",)})[:16]
        ro["compute_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return ro

    def drill(self, family_id: str) -> dict:
        f = self.bank.by_id[family_id]
        return {k: f[k] for k in ("family_id", "title", "actor_type", "job", "segment", "situation", "sparky_today",
                                  "specific_brief", "approval_moment", "ladder", "evidence", "sizing", "decomposition",
                                  "partner_fit", "members", "lineage") if k in f}

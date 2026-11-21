"""E14 — decomposition stage (families -> components). Deterministic; integrated, not forked.

Owner of the rules and the catalog: Fork F (`fork-f/decompose_v2.py`, components@2, needs@1, adapters@1).
This module ports F's `needs_of`, `closure` and `decompose` unchanged so the engine can call them per family at
bank-build time and per drill at demo time. Parity with F's run-0 output is a test (tests/test_e14_parity.py).
The only additions are read-only views the engine needs: build effort per family (for E12's 2x2) and partner fit
inputs (for the partner lens). No model is called; new components are never added here.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..util import FIXTURES, load_yaml

O, U, C, P, R = "outside_trigger", "unattended", "context_walmart_shouldnt_hold", "other_people", "completion_under_rules"

# org@1 statuses F's decompose_v2 uses (fork-c/org-model/walmart/capabilities.yaml). Kept as F has them for parity;
# org@2 (Fork E) moved CAP-07 to published/beta, which F owns applying.
CAP_STATUS_ORG1 = {"CAP-01": ("published", "beta"), "CAP-02": ("published", "yes"), "CAP-03": ("published", "yes"),
                   "CAP-04": ("published", "yes"), "CAP-05": ("published", "no"), "CAP-07": ("inferred", "unknown"),
                   "CAP-10": ("published", "unknown"), "CAP-12": ("published", "unknown"), "CAP-13": ("published", "unknown"),
                   "CAP-14": ("published", "unknown"), "CAP-17": ("published", "yes"), "CAP-19": ("published", "no"),
                   "CAP-20": ("published", "no"), "CAP-21": ("proposed", "n/a"), "CAP-22": ("proposed", "n/a"),
                   "CAP-23": ("proposed", "n/a"), "CAP-24": ("proposed", "n/a"), "CAP-25": ("proposed", "n/a"),
                   "CAP-26": ("absent", "n/a"), "CAP-27": ("proposed", "n/a"), "CAP-28": ("proposed", "n/a")}
ADAPTER_CAPS = {"CAP-07", "CAP-10", "CAP-43", "CAP-02", "CAP-21", "CAP-28", "CAP-22", "CAP-23", "CAP-25", "CAP-12", "CAP-24"}  # adapters@1
ENHANCE = {"feedback_edits"}
EFF = {"S": 1, "M": 2, "L": 3}

LANE_NEED = {"brief": "specific_brief", "mandate": "standing_mandate", "trigger": "outside_trigger", "poll": "group_decision",
             "card": "role_card", "solver": "solve_cart", "verify": "verify", "ledger": "ledger", "notice": "change_notice"}
COND_NEED = {O: ["outside_trigger"], U: ["standing_mandate"], P: ["group_decision", "role_card"],
             R: ["solve_cart", "slot_deadline", "ledger"], C: ["household_rules"]}
NEED_LIST_JOBS = {"feed", "prepare", "host_or_celebrate", "set_up_a_home", "give_or_donate", "recover", "school",
                  "manage_group_money", "run_a_small_business"}
CUES = {
    "on_hand": r"on[- ]hand|pantry memory|net of|minus on|what's short|cleaner's count",
    "item_attributes": r"allergen|SNAP|eligib|UPC|voucher|packaging|listing",
    "support_view": r"who approved|\btrace\b|co-signed",
    "scoped_principal": r"account holder|recipient|requested-by|ship-to|addresses",
}


@lru_cache(maxsize=4)
def load_catalog(path: str | None = None) -> dict:
    return load_yaml(path or FIXTURES / "fork_f" / "components-v2.min.yaml")


def needs_of(f: dict, use_text: bool = True) -> dict[str, str]:
    """F's rules R0-R12 + text cues, verbatim. `f` needs: value_tier, gateway_only, lanes_to_tune, actor_type,
    role_in_order, cluster, trigger, protected, job, text."""
    n: dict[str, str] = {}
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


def closure(comps, K) -> set:
    out, stack = set(comps), list(comps)
    while stack:
        for d in K[stack.pop()]["deps"]:
            if K[d]["layer"] == "product" and d not in out: out.add(d); stack.append(d)
    return out


def decompose(f: dict, catalog: dict | None = None, cap_status: dict | None = None, use_text: bool = True) -> dict:
    cat = catalog or load_catalog()
    K, NEEDS = cat["components"], cat["needs"]
    cs = cap_status or CAP_STATUS_ORG1
    confirmed = lambda c: c in cs and cs[c][0] == "published" and cs[c][1] in ("yes", "beta")
    n = needs_of(f, use_text)
    direct = {NEEDS[k]: r for k, r in n.items() if k not in ENHANCE}
    full = closure(direct, K)
    enh = sorted({NEEDS[k] for k in n if k in ENHANCE} - full)
    caps = sorted({cap for c in full for cap in K[c]["caps"]})
    risky = [cap for cap in caps if not confirmed(cap)]
    eff_days = sum(EFF[str(K[c]["effort"]).strip()[0]] for c in full)
    return {"components": sorted(full), "enhance": enh, "needs": sorted(n),
            "provenance": {c: direct.get(c, "closure") for c in sorted(full)}, "caps": caps,
            "unconfirmed_caps": risky, "adapters": sorted(c for c in risky if c in ADAPTER_CAPS),
            "build_effort_days": eff_days, "catalog": cat.get("version", "components@2")}


def family_view(card: dict) -> dict:
    """The fields F's rules read, from an engine card or family."""
    return {"value_tier": card["value_tier"], "gateway_only": card["gateway_only"], "lanes_to_tune": card["lanes_to_tune"],
            "actor_type": card["actor_type"], "role_in_order": card["role_in_order"], "cluster": card.get("cluster", ""),
            "trigger": card["trigger"], "protected": card["protected"], "job": card["job"],
            "text": f"{card['situation']} | {card['specific_brief'].strip(chr(39))}"}

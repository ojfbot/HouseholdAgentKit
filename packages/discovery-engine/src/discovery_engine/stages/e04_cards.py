"""E04 — problem-card generator (stage 2). Stochastic; fixed temperature per run.

Model seam (components@2 E04): local open-weight teacher -> template cards per cell.
- LocalTeacher talks to an OpenAI-compatible endpoint on either host (P01 MLX serving) with a pinned model.
  Fork D's terms ruling (D-ADR-003) applies: no frontier model generates cards. The teacher refuses any endpoint
  that is not local and any model id that names a frontier provider, before a request is made.
- TemplateTeacher ("template@1", the fallback) re-emits Fork C's run-0 seed problems for each sampled cell. It can
  only rediscover known problems; the run report says so. Every card records which generator wrote it.
Oracle: schema-valid 100%; synthetic labels 100%; fixed temperature per run.
Cards carry `needs[]` (needs@1) filled by F's rules (E14) at generation time.
"""
from __future__ import annotations

import ipaddress
import json
import random
import os
import urllib.request
from typing import Protocol
from urllib.parse import urlparse

from ..seedbank import load_seeds
from ..text import rephrase
from ..util import sha256_hex, src_label
from .e14_decompose import decompose, family_view

FIXED_TEMPERATURE = 0.7          # per run; anything else is refused (job-kinds-v0 common.refused)
# Loopback by default. Extra host names come from DE_LOCAL_TEACHER_HOSTS (comma-separated); none are baked in.
LOCAL_HOSTS = {"localhost"} | {h.strip().lower() for h in os.environ.get("DE_LOCAL_TEACHER_HOSTS", "").split(",") if h.strip()}
FRONTIER_MARKERS = ("anthropic", "claude", "openai.com", "gpt-", "gemini", "googleapis", "o1-", "o3-", "o4-")
CONDS = ("outside_trigger", "unattended", "context_walmart_shouldnt_hold", "other_people", "completion_under_rules")
REQUIRED = ("card_id", "cell_id", "family", "title", "actor_type", "role_in_order", "segment", "protected", "job",
            "quadrant", "situation", "trigger", "agent_surface", "sparky_today", "specific_brief", "gateway_only",
            "approval_moment", "business_owners", "lanes_to_tune", "walmart_stake", "evidence", "risk",
            "sizing_inputs", "needs", "synthetic", "source")

# agent surface -> partner builder type (rule partner_fit@0; proposed to Fork C, who owns the card field)
BUILDER = {"meal_planner": "meal_planner", "caregiver_app": "caregiving_app", "family_chat_agent": "family_assistant",
           "household agent": "family_assistant", "calendar_agent": "family_assistant", "general_assistant": "general_assistant",
           "budget_finance_app": "budgeting_app", "property_management_agent": "smb_ops", "pos_system": "smb_ops",
           "small_business_ops_agent": "smb_ops", "expense_system": "smb_ops", "seller_ops_agent": "seller_tools",
           "partner_built_agent": "any_builder", "school_app": "school_app", "team_or_club_app": "club_app",
           "church_or_pantry_inventory_system": "nonprofit_ops", "smart_home_hub": "smart_home", "car_or_eld": "fleet_app",
           "pet_app": "pet_app", "baby_tracker": "baby_app", "weather_app": "general_assistant", "group chat": "family_assistant"}


class Teacher(Protocol):
    name: str
    def generate(self, cell: dict, n: int, rng: random.Random) -> list[dict]: ...


class TeacherRefused(Exception):
    pass


def check_local(endpoint: str, model: dict) -> None:
    """Fail closed before any request (D's terms ruling + network: none on night kinds)."""
    host = (urlparse(endpoint).hostname or "").lower()
    ok = host in LOCAL_HOSTS
    if not ok:
        try:
            ip = ipaddress.ip_address(host); ok = ip.is_loopback or ip.is_private
        except ValueError:
            ok = False
    if not ok:
        raise TeacherRefused(f"teacher endpoint is not local: {host!r}")
    mid = f"{model.get('repo', '')}".lower()
    if any(m in mid for m in FRONTIER_MARKERS):
        raise TeacherRefused(f"frontier model refused as teacher: {mid!r}")
    for k in ("repo", "revision", "sha256"):
        if not model.get(k):
            raise TeacherRefused(f"teacher pin missing {k}")


class TemplateTeacher:
    """Fallback: per cell, pick seed problems of the cell's actor type, weighted by how many cell axes they match."""
    name = "template@1"

    def __init__(self):
        self.seeds, self.refs = load_seeds()

    def generate(self, cell: dict, n: int, rng: random.Random) -> list[dict]:
        pool = [s for s in self.seeds if s["actor_type"] == cell["actor_type"]]
        def fit(s):
            return {"job": s["job"] == cell["job"], "trigger": s["trigger"] == cell["trigger"],
                    "agent_surface": s["surface"] == cell["agent_surface"], "quadrant": s["quadrant"] == cell["quadrant"]}
        weights = [1 + 2 * sum(fit(s).values()) ** 2 for s in pool]
        out = []
        for i in range(n):
            s = rng.choices(pool, weights=weights, k=1)[0]
            out.append(card_from_seed(s, cell, rng, variant=i, cell_fit=fit(s), refs=self.refs))
        return out


class LocalTeacher:
    """OpenAI-compatible chat endpoint on a kit host. Returns [] on any failure so the caller falls back."""

    def __init__(self, endpoint: str, model: dict, timeout_s: float = 60.0):
        check_local(endpoint, model)
        self.endpoint, self.model, self.timeout = endpoint.rstrip("/"), model, timeout_s
        self.name = f"teacher:{model['repo']}@{model['revision'][:12]}"
        self.fallback = TemplateTeacher()

    def _prompt(self, cell: dict, examples: list[dict]) -> list[dict]:
        sys_msg = ("You write synthetic problem cards for a discovery engine. Every person and number is synthetic. "
                   "Never infer identity, health or religion from names or places; state rules, never diagnoses. "
                   "Return JSON only, matching the schema.")
        ex = [{k: e[k] for k in ("title", "situation", "sparky_today", "specific_brief", "gateway_only", "approval_moment")} for e in examples]
        user = json.dumps({"cell": {k: cell[k] for k in ("actor_type", "job", "trigger", "agent_surface", "quadrant")},
                           "examples": ex, "instructions": "Write one new problem card for this cell."})
        return [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}]

    def generate(self, cell: dict, n: int, rng: random.Random) -> list[dict]:
        examples = self.fallback.generate(cell, 2, random.Random(rng.random()))
        out = []
        for i in range(n):
            body = {"model": self.model["repo"], "temperature": FIXED_TEMPERATURE, "messages": self._prompt(cell, examples),
                    "response_format": {"type": "json_object"}, "seed": rng.randrange(2**31)}
            try:
                req = urllib.request.Request(self.endpoint + "/v1/chat/completions", data=json.dumps(body).encode(),
                                             headers={"content-type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    msg = json.loads(r.read())["choices"][0]["message"]["content"]
                raw = json.loads(msg)
            except Exception:
                return []
            base = examples[i % len(examples)]
            card = {**base, **{k: raw[k] for k in ("title", "situation", "sparky_today", "specific_brief", "approval_moment") if k in raw}}
            g = [c for c in raw.get("gateway_only", base["gateway_only"]) if c in CONDS]
            card.update(gateway_only=g, value_tier=2 if g else card["value_tier"])
            card["source"] = {"generator": self.name, "teacher": self.model, "temperature": FIXED_TEMPERATURE,
                              "seed_family": None, "provenance": "open_weight_teacher"}
            card["card_id"] = "RC-" + sha256_hex([cell["cell_id"], i, card["situation"]])[:12]
            card["needs"] = sorted(decompose(family_view(card))["needs"])
            out.append(card)
        return out


def _value_tier(s: dict) -> int:
    if s["gateway_only"]:
        return 2
    return 1 if s["gate"] == "tier1" else 0


def card_from_seed(s: dict, cell: dict, rng: random.Random, variant: int, cell_fit: dict, refs: dict) -> dict:
    situation = s["situation"] if variant == 0 else rephrase(s["situation"], rng)
    card = {
        "card_id": "RC-" + sha256_hex([cell["cell_id"], variant, s["id"], situation])[:12],
        "cell_id": cell["cell_id"], "cell_fit": cell_fit,
        "family": s["slug"], "title": s["title"], "cluster": s["cluster"], "actor_type": s["actor_type"], "actor": s["persona"],
        "role_in_order": s["role"], "segment": s["segment"], "protected": list(s["protected"]), "job": s["job"],
        "quadrant": s["quadrant"], "situation": situation, "trigger": s["trigger"], "agent_surface": s["surface"],
        "current_workaround": s["gate_note"], "sparky_today": s["sparky_today"], "specific_brief": s["specific_brief"],
        "gateway_only": list(s["gateway_only"]), "value_tier": _value_tier(s), "gate_hint": s["gate"],
        "approval_moment": s["approval"], "business_owners": list(s["owners"]), "lanes_to_tune": list(s["lanes"]),
        "walmart_stake": list(s["walmart_stake"]), "stake_text": s["stake"],
        "evidence": {"level": s["ev"], "refs": [s["ev_ref"]] if s["ev_ref"] else []},
        "risk": s["risk"], "relation_to_A_B": s["rel"],
        "sizing_inputs": {"segment_size": {"value": s["seg"], "label": src_label(s["seg_src"])},
                          "frequency_per_year": {"value": s["freq"], "label": "synthetic"},
                          "basket_usd": {"value": s["basket"], "label": "synthetic"},
                          "gap": {"value": s["gap"], "label": "synthetic"}},
        "judge_seed": {"J0": {"frequency": s["f"], "severity": s["s"], "walmart_stake": s["W"], "visible_approval": s["V"],
                              "demo_ability": s["D"], "reuse": s["R"], "novelty": s["Nv"], "risk": s["risk"]}},
        "synthetic": True,
        "source": {"generator": TemplateTeacher.name, "seed_family": s["id"], "provenance": "agent_seed",
                   "seed_author": "Fork C session (run-0)", "temperature": FIXED_TEMPERATURE, "variant": variant},
    }
    card["needs"] = sorted(decompose(family_view(card))["needs"])
    return card


def validate(card: dict, lattice_axes: dict) -> list[str]:
    errs = [f"missing {k}" for k in REQUIRED if k not in card]
    if errs:
        return errs
    if card["actor_type"] not in lattice_axes["actor_type"]: errs.append("actor_type not in lattice")
    if card["quadrant"] not in lattice_axes["quadrant"]: errs.append("quadrant not in lattice")
    if card["job"] not in lattice_axes["job"]: errs.append("job not in lattice")
    if any(g not in CONDS for g in card["gateway_only"]): errs.append("unknown gateway_only condition")
    if card["synthetic"] is not True: errs.append("synthetic label missing")
    if card["source"].get("temperature") != FIXED_TEMPERATURE: errs.append("temperature not the run's fixed value")
    for k, v in card["sizing_inputs"].items():
        if not (isinstance(v, dict) and "label" in v): errs.append(f"unlabeled sizing input {k}")
    return errs


def generate(cells: list[dict], seed: int, n_per_cell: int, teacher: Teacher | None = None) -> dict:
    primary = teacher or TemplateTeacher()
    fallback = TemplateTeacher()
    rng = random.Random(seed * 7919 + 2)
    cards, fallback_cells = [], 0
    for cell in cells:
        got = primary.generate(cell, n_per_cell, rng)
        if not got and primary is not fallback:
            got = fallback.generate(cell, n_per_cell, rng); fallback_cells += 1
        cards += got
    return {"cards": cards, "generator": primary.name, "fallback_cells": fallback_cells,
            "fallback_used": primary.name == TemplateTeacher.name or fallback_cells > 0,
            "temperature": FIXED_TEMPERATURE}


def partner_fit(card: dict, decomposition: dict) -> dict:
    """Derived partner-lens inputs (rule partner_fit@0). Build effort from E14's component set; conformance risks
    are the family's unconfirmed capabilities. Proposed to Fork C as the card field `partner_fit` (C owns it)."""
    days = decomposition["build_effort_days"]
    effort = "S" if days <= 14 else "M" if days <= 20 else "L"
    builder = BUILDER.get(card["agent_surface"], "general_assistant")
    return {"builder_types": [builder], "build_effort": effort, "build_effort_days": {"value": days, "label": "derived:synthetic"},
            "conformance_risks": list(decomposition["unconfirmed_caps"]), "rule": "partner_fit@0"}

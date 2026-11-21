"""Control profiles in the controls@2 shape (draft), loaded from what exists today.

Sources, in order of authority:
  1. controls@2 (Fork C, due Sat Nov 21)            -> load_controls2(path)   [shape expected: this module's Profile]
  2. Fork E priors (fork-e/controls-priors-v2.yaml) -> from_priors()           [fixture until 1 lands]
  3. Fork C controls@1                              -> from_controls1()        [run-0 parity]
  4. partner fixture (this package)                 -> partner_fixture()       [until C ships partner profiles]
A profile always carries both value vectors, so a lens flip on any profile is a single field change.
"""
from __future__ import annotations

import copy

from ..util import FIXTURES, PROTO_C, load_yaml, sha256_hex

FUNCTION_OWNER = {"marketing_crm": "mkt", "supply_chain": "sc", "product": "prod", "trust_safety": "tns",
                  "partnerships": "partner", "finance": "fin", "connect_ads": "ads", "merchandising": "merch",
                  "marketplace": "mp", "store_ops": "ops", "care_returns": "care", "b2b": "b2b"}
IN_HOUSE_KEYS = ("revenue", "trust", "cost", "risk")
PARTNER_KEYS = ("market", "effort", "platform_risk")
DEFAULT_PARTNER_VALUE = {"market": 0.34, "effort": 0.33, "platform_risk": 0.33}
DEFAULT_IN_HOUSE_VALUE = {"revenue": 0.25, "trust": 0.25, "cost": 0.25, "risk": 0.25}


def _profile(pid, *, lens="in_house", function="", owner=None, partner_owner=None, segment=None, intent=None,
             value=None, partner_value=None, source="", extra=None) -> dict:
    p = {"profile_id": pid, "lens": lens, "function": function, "owner": owner, "partner_owner": partner_owner,
         "segment": dict(segment or {}), "intent": dict(intent or {}),
         "value": {**DEFAULT_IN_HOUSE_VALUE, **(value or {})} if value is None else {k: float(value.get(k, 0.0)) for k in IN_HOUSE_KEYS},
         "partner_value": {k: float((partner_value or DEFAULT_PARTNER_VALUE).get(k, 0.0)) for k in PARTNER_KEYS},
         "scenario": {"adoption_share": 0.10}, "source": source}
    if extra:
        p.update(extra)
    return p


def from_controls1(path=None) -> tuple[dict, dict]:
    ctl = load_yaml(path or PROTO_C / "controls-v1.yaml")
    profs = {}
    for pid, p in ctl["profiles"].items():
        profs[pid] = _profile(pid, function=p.get("function", ""), owner=p.get("owner"), segment=p.get("segment"),
                              intent=p.get("intent"), value=p["value"], source="controls@1")
    return profs, model_params(ctl)


def from_priors(path=None, controls1_path=None) -> tuple[dict, dict]:
    pri = load_yaml(path or FIXTURES / "fork_e" / "controls-priors-v2.yaml")
    _, params = from_controls1(controls1_path)
    profs = {}
    for pid, p in pri["profiles"].items():
        seg = {**p.get("segment_would_also_serve", {}), **p.get("segment_stated", {})}
        inte = {**p.get("intent_would_also_serve", {}), **p.get("intent_stated", {})}
        profs[pid] = _profile(pid, function=pid, owner=FUNCTION_OWNER.get(pid), segment=seg, intent=inte,
                              value=p["value_prior"], source="controls@2-fixture (fork-e priors)",
                              extra={"provenance": {"segment_stated": p.get("segment_stated", {}),
                                                    "segment_would_also_serve": p.get("segment_would_also_serve", {}),
                                                    "intent_stated": p.get("intent_stated", {}),
                                                    "intent_would_also_serve": p.get("intent_would_also_serve", {}),
                                                    "evidence": p.get("evidence", {}), "thin_evidence": p.get("thin_evidence", False)}})
    return profs, {**params, "source": "controls@2-fixture"}


def partner_fixture(path=None) -> dict:
    fx = load_yaml(path or FIXTURES / "controls2-partner.fixture.yaml")
    return {pid: _profile(pid, lens="partner", function=p.get("function", ""), partner_owner=p.get("partner_owner"),
                          segment=p.get("segment"), intent=p.get("intent"), value=DEFAULT_IN_HOUSE_VALUE,
                          partner_value=p["partner_value"], source=fx["version"]) for pid, p in fx["profiles"].items()}


def load_controls2(path) -> tuple[dict, dict]:
    """controls@2 when it lands. Expected keys per profile match _profile(); missing keys get defaults."""
    c2 = load_yaml(path)
    profs = {pid: _profile(pid, **{k: p.get(k) for k in ("lens", "function", "owner", "partner_owner", "segment", "intent",
                                                        "value", "partner_value") if p.get(k) is not None}, source="controls@2")
             for pid, p in c2["profiles"].items()}
    return profs, model_params(c2)


def model_params(ctl: dict) -> dict:
    nt = set()
    for item in ctl.get("never_tunable", []):
        for k in str(item).split(","):
            nt.add(k.strip())
    return {"owner_boost": ctl.get("owner_boost", 1.25), "bounds": ctl.get("bounds", {"segment": [0.5, 3.0], "intent": [0.5, 3.0]}),
            "never_tunable": sorted(nt), "protected_tags": ctl.get("fairness_floor", {}).get("protected_tags", []),
            "adoption_share": ctl.get("scenario", {}).get("adoption_share", 0.10), "source": ctl.get("control_model_version", "?")}


def standard_set(source: str = "priors") -> tuple[dict, dict]:
    """The demo's profile set: in-house functions + partner fixture."""
    profs, params = from_priors() if source == "priors" else from_controls1()
    profs = {**profs, **partner_fixture()}
    return profs, params


def profile_hash(p: dict) -> str:
    return sha256_hex({k: p[k] for k in ("lens", "owner", "partner_owner", "segment", "intent", "value", "partner_value", "scenario")})


def clone(p: dict) -> dict:
    return copy.deepcopy(p)

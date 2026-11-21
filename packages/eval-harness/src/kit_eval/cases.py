"""Case loading for the harness. Case v1 is LOOSE until batch 1 (kit_contracts.loose)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from kit_contracts import Budget, Constraint, Deadline, Headcount, Lock, Mandate, MemberRef
from kit_contracts.hashing import canonical_json, sha256_hex
from kit_contracts.loose import validate_case


class CaseError(ValueError):
    pass


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    files = sorted(p.glob("*.yaml")) if p.is_dir() else [p]
    out: list[dict[str, Any]] = []
    for f in files:
        data = yaml.safe_load(f.read_text())
        for c in data.get("cases", []):
            errs = validate_case(c)
            if errs:
                raise CaseError(f"{f.name}:{c.get('case_id')}: {errs}")
            if c.get("split") == "holdout":
                raise CaseError(f"{c['case_id']}: holdout cases never live in the repo (seed stays outside, SHA-256 only)")
            out.append(c)
    ids = [c["case_id"] for c in out]
    if len(ids) != len(set(ids)):
        raise CaseError("duplicate case_id")
    return out


def case_set_sha(cases: list[dict[str, Any]]) -> str:
    return sha256_hex(canonical_json(sorted(cases, key=lambda c: c["case_id"])))


def _dt(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        raise CaseError(f"naive time {s}")
    return d


def mandate_from_case(case: dict[str, Any]) -> Mandate:
    m = case["mandate"]
    principal = MemberRef(m.get("principal_hash", f"mh_{case['case_id']}_owner"), m.get("principal_role", "owner"))
    requested = MemberRef(m.get("requested_by_hash", principal.member_hash), m.get("requested_by_role", principal.role))
    d = m["deadline"]
    return Mandate(
        mandate_id=m.get("mandate_id", f"md-{case['case_id']}"),
        principal=principal,
        requested_by=requested,
        profile_id=m.get("profile_id"),
        occasion=m.get("occasion", case.get("lineage", {}).get("occasion", "taco")),
        headcount=Headcount(adults=m["headcount"]["adults"], kids=tuple(m["headcount"].get("kids", []))),
        deadline=Deadline(
            type=d["type"], time=_dt(d["time"]), store=d.get("store", case.get("store")), window_end=_dt(d["window_end"]) if d.get("window_end") else None
        ),
        budget=Budget(
            max_cents=int(m["budget"]["max_cents"]), includes=tuple(m["budget"].get("includes", ["tax", "fees"])), hard=bool(m["budget"].get("hard", True))
        ),
        constraints=[Constraint(**c) for c in m.get("constraints", [])],
        locks=[Lock(**lk) for lk in m.get("locks", [])],
        exclude=list(m.get("exclude", [])),
        on_hand=list(m.get("on_hand", [])),
        standing=m.get("standing"),
    )

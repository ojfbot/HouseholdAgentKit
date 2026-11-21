"""Merge-queue planner (R1.1 default A, R6.3 default A).

A PR auto-merges (rebase, linear history) only when ALL hold:
  * required checks green on the head: ci, security, privacy-guard, cross-review
  * the nightly `kit gate` record for that head is green
  * it is not owner-gated: no `contract` / `adr` / `irreversible` / `cross-repo` label and no
    file under an owner-gated path (contracts, ADRs, CI and rulesets, the gate itself)
Owner-gated PRs are listed for the owner and never merged by the queue. Order is FIFO by
creation; a PR naming `depends-on: #n` waits until #n is merged.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any

from kit_gate import review

REQUIRED_CHECKS = ("ci", "security", "privacy-guard", "cross-review")
OWNER_LABELS = {"contract", "adr", "irreversible", "cross-repo"}
OWNER_PATHS = (
    "contracts/*",
    "decisions/adr/*",
    ".github/*",
    "bundles/gate-config.yaml",
    "packages/kit-gate/*",
    "CODEOWNERS",
    "LICENSE",
    "NOTICE",
    "DISCLAIMER*",
)
DEPENDS_RE = re.compile(r"depends-on:\s*#(\d+)", re.I)


@dataclass
class Decision:
    number: int
    title: str
    action: str  # merge | owner | blocked | waiting
    reasons: list[str] = field(default_factory=list)


def _labels(pr: dict[str, Any]) -> set[str]:
    return {(lb["name"] if isinstance(lb, dict) else lb) for lb in pr.get("labels", [])}


def _checks(pr: dict[str, Any]) -> dict[str, str]:
    out = {}
    for c in pr.get("statusCheckRollup", []) or []:
        name = c.get("name") or c.get("context")
        state = (c.get("conclusion") or c.get("state") or "").lower()
        out[name] = state
    return out


def owner_gated(pr: dict[str, Any]) -> list[str]:
    why = sorted(_labels(pr) & OWNER_LABELS)
    files = [f["path"] if isinstance(f, dict) else f for f in pr.get("files", [])]
    hits = sorted({p for f in files for p in OWNER_PATHS if fnmatch.fnmatch(f, p)})
    return [f"label:{x}" for x in why] + [f"path:{p}" for p in hits]


def plan(prs: list[dict[str, Any]], gate_records: dict[str, dict[str, Any]], merged: set[int] | None = None) -> list[Decision]:
    merged = set(merged or ())
    out: list[Decision] = []
    for pr in sorted(prs, key=lambda p: (p.get("createdAt", ""), p["number"])):
        d = Decision(pr["number"], pr.get("title", ""), "blocked")
        if pr.get("isDraft"):
            d.action, d.reasons = "waiting", ["draft"]
            out.append(d)
            continue
        og = owner_gated(pr)
        checks = _checks(pr)
        missing = [c for c in REQUIRED_CHECKS if c != "cross-review" and checks.get(c) not in ("success",)]
        rs, rwhy = review.status(pr)
        gate = gate_records.get(pr.get("headRefOid", ""))
        deps = [int(n) for n in DEPENDS_RE.findall(pr.get("body", "") or "")]
        unmet = [n for n in deps if n not in merged]
        if missing:
            d.reasons.append(f"checks not green: {missing}")
        if rs != "success":
            d.reasons.append(f"cross-review {rs}: {rwhy}")
        if gate is None:
            d.reasons.append("no nightly gate record for this head yet")
        elif gate.get("verdict") != "green":
            d.reasons.append(f"gate red: {gate.get('reasons')}")
        if unmet:
            d.reasons.append(f"depends on unmerged {['#' + str(n) for n in unmet]}")
        if og:
            d.action = "owner"
            d.reasons.insert(0, f"owner-gated ({', '.join(og)}): the owner merges")
        elif not d.reasons:
            d.action = "merge"
            merged.add(pr["number"])
        elif rs == "pending" or gate is None or unmet:
            d.action = "waiting"
        out.append(d)
    return out

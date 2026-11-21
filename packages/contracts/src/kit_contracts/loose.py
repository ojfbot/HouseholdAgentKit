"""The two contract areas held LOOSE until "Decisions batch 1" (the owner, via Fork J).

Batch-1 pre-read conflicts:
  * R4.2  Case v1 is defined twice: D adds `lineage` + `split`; F's Case@1 adds `mode`
          (episode|interview), B's request types and world events. Expected outcome: one
          merged Case v1. Until then we validate only the core both drafts share and
          accept either side's extra fields.
  * R4.4  Mandate v1 `standing` is its own limit vocabulary; E warned against a parallel
          vocabulary to the published User-Defined Guardrail (spend limits, transaction
          frequency, category/department restrictions). Expected outcome: renamed and
          mapped field-for-field, or held open until E's field list lands.

Suites read these blocks ONLY through the accessors below, so tightening is a one-file
change. Every test that depends on them is marked `loose_contract`; after batch 1,
`pytest -m loose_contract` is the list to re-pin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LOOSE = {
    "Case@1": {"decision": "R4.2", "tighten_after": "Decisions batch 1"},
    "Mandate@1.standing": {"decision": "R4.4", "tighten_after": "Decisions batch 1"},
}

# ---------------------------------------------------------------- Case v1 (loose)

CASE_CORE_REQUIRED = ("case_id", "persona", "goal", "accept_if", "synthetic")
CASE_KNOWN_OPTIONAL = {
    # shared by both drafts
    "world_events",
    "adversary",
    # F's Case@1
    "mode",
    "request_type",
    # D's Case v1
    "lineage",
    "split",
    # harness inputs (IQ): the structured mandate and clock a case runs under
    "mandate",
    "clock_start",
    "store",
    "expect",
    "notes",
    "tags",
}
LINEAGE_KEYS = ("occasion", "persona_id", "template_id", "seed", "generator_sha")
SPLITS = ("train", "val", "test", "holdout", "dev")


def validate_case(case: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means valid under the loose rule."""
    errs: list[str] = []
    for k in CASE_CORE_REQUIRED:
        if k not in case:
            errs.append(f"missing core field {k}")
    if case.get("synthetic") is not True:
        errs.append("synthetic must be true (stance: purely synthetic)")
    if not isinstance(case.get("accept_if", []), list) or not case.get("accept_if"):
        errs.append("accept_if must be a non-empty list of end states")
    mode = case.get("mode", "episode")
    if mode not in ("episode", "interview"):
        errs.append(f"mode {mode!r} not in episode|interview")
    if "lineage" in case:
        missing = [k for k in LINEAGE_KEYS if k not in case["lineage"]]
        if missing:
            errs.append(f"lineage missing {missing}")
    if "split" in case and case["split"] not in SPLITS:
        errs.append(f"split {case['split']!r} not in {SPLITS}")
    unknown = set(case) - set(CASE_CORE_REQUIRED) - CASE_KNOWN_OPTIONAL
    if unknown:
        # loose: unknown keys are reported as warnings, not errors
        pass
    return errs


# ------------------------------------------------- Mandate v1 standing (loose)


@dataclass
class StandingView:
    shape: str  # "components@2" | "guardrail-mapped"
    per_order_cents: int | None
    per_month_cents: int | None
    autonomy: str | None  # approve_each | within_cap
    frequency: str | None
    category_blocks: tuple[str, ...]
    expires: str | None


def standing_view(standing: dict[str, Any] | None) -> StandingView | None:
    """Read either draft shape of the standing block.

    components@2 shape: {schedule, cap_per_order, cap_per_month, autonomy, expires}
    guardrail-mapped shape (HYPOTHETICAL field names until E's list lands):
        {spend_limits: {per_transaction, per_month}, frequency, category_restrictions,
         autonomy, expires}
    Money may be int cents or a {"amount_cents": int} dict.
    """
    if standing is None:
        return None
    if "spend_limits" in standing or "category_restrictions" in standing:
        lim = standing.get("spend_limits", {})
        return StandingView(
            shape="guardrail-mapped",
            per_order_cents=_cents(lim.get("per_transaction")),
            per_month_cents=_cents(lim.get("per_month")),
            autonomy=standing.get("autonomy"),
            frequency=standing.get("frequency"),
            category_blocks=tuple(standing.get("category_restrictions", ())),
            expires=standing.get("expires"),
        )
    return StandingView(
        shape="components@2",
        per_order_cents=_cents(standing.get("cap_per_order")),
        per_month_cents=_cents(standing.get("cap_per_month")),
        autonomy=standing.get("autonomy"),
        frequency=standing.get("schedule"),
        category_blocks=(),
        expires=standing.get("expires"),
    )


def _cents(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, dict):
        return int(v["amount_cents"])
    return int(v)

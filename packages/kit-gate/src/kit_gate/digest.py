"""The one daily digest (R1.3 default A): IQ -> the owner. Interrupts only for a red gate that blocks
a milestone, a needed decision, or anything irreversible; everything else waits for this.

Order is answer-first: what needs the owner, then what changed, then what is moving.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from kit_gate.merge_queue import Decision


def render(
    day: date,
    decisions: list[Decision],
    gate: dict[str, Any] | None,
    merged_since: list[dict[str, Any]],
    queue_items: list[str],
    eval_cases_added: list[str],
    milestones: list[tuple[str, str]],
    notes: list[str] | None = None,
) -> str:
    owner = [d for d in decisions if d.action == "owner"]
    blocked = [d for d in decisions if d.action == "blocked"]
    waiting = [d for d in decisions if d.action == "waiting"]
    merging = [d for d in decisions if d.action == "merge"]
    verdict = (gate or {}).get("verdict", "not run")
    lines = [f"# IQ daily digest — {day.isoformat()}", ""]
    needs = len(owner) + len(queue_items)
    lines.append(
        f"**Needs you: {needs}** ({len(owner)} PR(s) to merge yourself, {len(queue_items)} decision(s) in the decision queue). "
        f"Nightly gate: **{verdict}**. Merged since last digest: {len(merged_since)}. Queued to auto-merge tonight: {len(merging)}."
    )
    lines.append("")
    if owner or queue_items:
        lines.append("## Needs you")
        lines += [f"- PR #{d.number} {d.title} — {d.reasons[0]}" for d in owner]
        lines += [f"- {q}" for q in queue_items]
        lines.append("")
    if gate is not None and verdict != "green":
        lines.append("## Gate red")
        lines += [f"- {r}" for r in gate.get("reasons", [])]
        lines.append("")
    if gate is not None and gate.get("waivers_relied_on"):
        lines.append("## Gate green with waivers")
        lines += [f"- {w['metric']}: owner {w.get('owner')}, until {w.get('until')} — {w.get('reason', '')}" for w in gate["waivers_relied_on"]]
        lines.append("")
    if merged_since:
        lines.append("## Merged")
        lines += [f"- #{p['number']} {p.get('title', '')}" for p in merged_since]
        lines.append("")
    if blocked:
        lines.append("## Blocked (agents are on it; no action for you)")
        lines += [f"- #{d.number} {d.title}: {'; '.join(d.reasons)}" for d in blocked]
        lines.append("")
    if waiting:
        lines.append("## In review")
        lines += [f"- #{d.number} {d.title}: {'; '.join(d.reasons)}" for d in waiting]
        lines.append("")
    if eval_cases_added:
        lines.append("## Failures turned into eval cases")
        lines += [f"- {c}" for c in eval_cases_added]
        lines.append("")
    if milestones:
        lines.append("## Milestones")
        lines += [f"- {when}: {what}" for when, what in milestones]
        lines.append("")
    if notes:
        lines.append("## Notes")
        lines += [f"- {n}" for n in notes]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

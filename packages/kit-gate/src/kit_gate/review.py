"""Cross-review markers (R6.3: 0 required approvals; the OTHER agent's review comment is required).

Both agents act through one GitHub identity today, so the review is a marker in a PR review
or comment, bound to the head SHA it reviewed (a push makes it stale):

    <!-- kit-review v0 -->
    reviewer: codex            # or claude-code
    verdict: approve           # or request-changes
    head: <40-hex sha>
    evidence: <tests run, eval delta, trace link>

The PR's author agent comes from its `impl:<agent>` label. The `cross-review` check passes
only when the latest marker from the other agent approves the current head.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MARKER = "<!-- kit-review v0 -->"
AGENTS = ("claude-code", "codex")
FIELD_RE = re.compile(r"^[ \t]*(reviewer|verdict|head|evidence)[ \t]*:[ \t]*(.*?)[ \t]*$", re.M)


@dataclass
class ReviewMarker:
    reviewer: str
    verdict: str
    head: str
    evidence: str
    at: str


def parse(body: str, at: str = "") -> ReviewMarker | None:
    if MARKER not in body:
        return None
    f = {k: v.strip() for k, v in FIELD_RE.findall(body.split(MARKER, 1)[1])}
    if f.get("reviewer") not in AGENTS or f.get("verdict") not in ("approve", "request-changes"):
        return None
    if not re.fullmatch(r"[0-9a-f]{7,40}", f.get("head", "")):
        return None
    return ReviewMarker(f["reviewer"], f["verdict"], f["head"], f.get("evidence", ""), at)


def author_agent(pr: dict[str, Any]) -> str | None:
    for lab in pr.get("labels", []):
        name = lab["name"] if isinstance(lab, dict) else lab
        if name.startswith("impl:") and name[5:] in AGENTS:
            return name[5:]
    return None


def status(pr: dict[str, Any]) -> tuple[str, str]:
    """-> (success | pending | failure, reason). `pr` is `gh pr view --json` shaped."""
    author = author_agent(pr)
    if author is None:
        return "failure", "PR has no impl:claude-code or impl:codex label"
    head = pr.get("headRefOid", "")
    bodies = [(r.get("body", ""), r.get("submittedAt", "")) for r in pr.get("reviews", [])]
    bodies += [(c.get("body", ""), c.get("createdAt", "")) for c in pr.get("comments", [])]
    markers = sorted((m for b, t in bodies if (m := parse(b, t))), key=lambda m: m.at)
    other = [m for m in markers if m.reviewer != author]
    if not other:
        return "pending", f"waiting for a review from {'codex' if author == 'claude-code' else 'claude-code'}"
    last = other[-1]
    if not head or not head.startswith(last.head):
        return "pending", f"review is for {last.head[:7]}, head is {head[:7]} (stale after push)"
    if last.verdict != "approve":
        return "failure", f"{last.reviewer} requested changes"
    if not last.evidence:
        return "failure", "review marker has no evidence line"
    return "success", f"approved by {last.reviewer} at {last.head[:7]}"

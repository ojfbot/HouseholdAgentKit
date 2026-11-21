# ADR-007 — Decomposition is a deterministic, rules-first stage; an LLM may only propose

Status: proposed (Fork F, 2026-11-19). Affects Fork C's engine, the problem-card schema and components@2.

## Context
v1 (`fork-c/decompose.py`) mapped cards to components with condition and lane tables plus 44 hand-coded per-family overrides. Hand overrides don't repeat when new families arrive, and v1's build order ignored dependencies.

## Decision
- Cards gain `needs[]` from the controlled vocabulary `needs@1` (one key per component; `core` or `enhance`).
- Rules R0–R12 over card fields produce needs; each component records the rule that added it. Runtime-dependency closure, then the org-model join (capabilities, adapters).
- For a residual need no rule covers, an LLM proposer maps it to an existing component or proposes a new one with an interface sketch, an org row or logged ask, and at least two families. Proposals stay `pending` and are shadow-scored until the owner approves them.
- Build order is greedy by value at stake per lane-day, limited to components whose dependencies are built.
- Evals: decomposition truth (from `component_id` trace stamps), reuse, unlock accuracy, seed and wording stability, and a hard zero-phantom gate.

## Consequences
- Run 0 under the rules: 43/44 v1 overrides recovered, mean v1↔v2 Jaccard 0.95, 0 phantoms.
- The engine's decomposition is reproducible and diffable between runs; new components enter only through review.

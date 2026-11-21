# ADR-005 — The ledger is the audit record; LangSmith is observability; the support view joins them

Status: proposed (Fork F, 2026-11-19). Affects K12, K18, K26, K27 and the decomposition-truth eval.

## Context
v1 K18 mixed three things: the audit chain (mandate → cart → token → order), LangSmith tracing, and a support view for Walmart care (PF-48, CAP-25). A's telemetry contract defines thread = episode, trace = event, run = step.

## Decision
- **K12 Ledger@0** is the business record: append-only, hash-chained entries for mandate, brief, cart, vote, decision, consent, token, order, refund, receipt. Each carries `requested_by`, `profile_id` and `episode_id`. It answers "who asked, who approved, what was bought" and must replay to 100%.
- **K26 Telemetry@1** is observability: LangSmith runs per node, LLM, tool, solver and guard, linked to the ledger by `episode_id` (= thread_id). New required metadata: `component_id`, `component_version`, `adapter_id`, `capability_mode`, `fallback_used`, plus Fork D's `bundle_id` and Fleet job ID.
- **K18** is a read-only projection: ledger entries for an order, joined to trace links. No member data beyond role and hash.

## Consequences
- The support view and ledger correctness do not depend on LangSmith being reachable.
- `component_id` stamps let the decomposition-truth eval read what a family actually used from traces, instead of from a hand-kept list.

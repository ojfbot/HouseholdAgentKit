# ADR-003 — Locks are enforced in our harness at three checkpoints, from one rule source; models never enforce

Status: proposed (Fork F, 2026-11-19). Affects K03, K04, K06, K10, K22, K24.

## Context
Locks and hard rules (allergies, religious law, safe foods, blocked categories) are never tunable and never weights. A's two invariants: only the owner changes locks and budget; no lock-breaking cart reaches a ballot. A's lane 7 (request validator) re-implemented part of this check.

## Decision
- **One source:** locks live in the Household (K06), versioned by `household_rev`. The Mandate carries them by reference; a stale `household_rev` returns STALE.
- **Three checkpoints, one verifier (K03):**
  1. Generation: the solver (K04) treats locks as hard constraints and never proposes a violating cart.
  2. Before anything is shown or sent: K03 verifies every cart before it reaches a ballot, every brief before it leaves, every card before it renders.
  3. After the decision, before checkout: K03 re-verifies the winning cart against current price, stock and packaging.
- **Edits:** a member's request goes K22 (parse) → K06.authorize (rights) → K03.verify (locks, budget). That composition *is* A's lane 7.
- Models (K01, K02, K11, K22, K24-H1) may propose; they never decide whether a lock holds. Unknown attributes never satisfy a lock (K16).
- Walmart's own guardrails (consent gate, caps) apply in addition, never instead.

## Consequences
- The lock oracle is one mutation suite in K03, reused by every family.
- A looser Walmart behaviour (a substitution, a cap) can never loosen a household rule.

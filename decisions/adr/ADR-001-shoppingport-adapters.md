# ADR-001 — ShoppingPort adapters: H3 hybrid by default, mode as config

Status: proposed (Fork F, 2026-11-19). Deciders: the owner. Affects K02, K05, K24, K17, K20.

## Context
Every family crosses the Walmart boundary through ShoppingPort (K24). 56 of 58 run-0 families depend on CAP-07 (agent-to-agent briefs to Sparky, inferred) and 41 on CAP-10 (slots, exposure unknown). Fork E re-tests both by Nov 21; the demo needs a working path before then.

## Decision
- One ShoppingPort@1 interface (`discover`, `propose_cart`, `request_consent`, `checkout`, `slots`, plus events). All Gateway guesses live inside an adapter, never in a caller.
- Three adapters: H1 conversational (Sparky prose, parsed by the Sparky extractor), H2 UCP-shaped (typed tools, JSON brief), H3 hybrid (brief as text where only conversation exists; price, stock and cart via structured `discover()`; our solver K04 decides).
- **H3 is the Dec 2 default** because it works whether CAP-07 is structured, conversational or absent.
- `capability_mode` is config, read at start-up, stamped on every trace (K26) and pinned in the bundle manifest (Fork D).
- Contract tests are tagged by capability (`-m cap07`, `-m cap10`); `adapters.yaml` lists them and what changes per outcome.

## Alternatives
- H2 only: cleanest, but rests entirely on an inferred capability. Rejected for Dec 2.
- H1 only: closest to "agent talks to Sparky", but every number must be parsed from prose; the verifier load and injection surface are highest. Kept as an adapter.

## Consequences
- Tier-1 uplift is measured on mock Sparky until real access; if CAP-07 is absent, tier 1 is restated as "our solver answers the specific brief".
- Switching mode is a config change plus a rerun of the tagged contract tests, not a code change in callers.

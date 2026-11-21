# ADR-006 — One model seam per lane, tier as config, and a deterministic fallback for every model

Status: proposed (Fork F, 2026-11-19; handed to Fork D for the bundle manifest). Affects K01, K02, K09, K11, K13, K16, K17, K21, K22, K24, K25.

## Context
Fork D serves local models behind an OpenAI-compatible endpoint, tunes LoRA adapters on the two hosts, and pins model + harness + context in a bundle manifest. Demo night may lose Wi-Fi or a Mac.

## Decision
- Each model-using component calls exactly one seam (for example `ModelPort.structured(schema=Mandate@1)`), with the schema as the contract. The tier `none | small_tuned | frontier` is bundle config, never code.
- Every seam has a deterministic fallback behind the same interface (grammar slot-filler, template brief, template cards, rules-only triggers, exact receipt matching, structured attributes only, template need lists, pick lists, H3 adapter, scripted replay, scripted voters). `fallback_used` is stamped on every trace.
- The whole stack runs at tier `none`. That is the demo's last-resort mode and the baseline row of every leaderboard.
- First tuning targets (with Fork D): K01 intent parser and K22 feedback interpreter (A's plan), then K11 card writer. K02 stays deterministic unless H1 is chosen.

## Consequences
- A tuned adapter is better only if the bundled agent scores better with harness and context held fixed (Fork D's rule).
- An eval row per lane: tier none / base local / tuned local / frontier.

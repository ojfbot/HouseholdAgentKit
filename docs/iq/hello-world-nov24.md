# Hello-world integration, Tue Nov 24 (IQ leads)

Goal: taco night by 6 PM under $25 runs live on the twin end to end. The nightly gate is on from that night.

**Pass bar:** Fork A's `hw-taco@1` (`fork-a/hello-world-oracle.yaml`), run as `kit hello-world --mode full --bundle <id>` (k = 5) and `--mode live` on HW-T2-01. It is canonical over this page. In IQ's terms, the run returns:
- pass^5 = 1.0, with tier 0, tier 1 and tier 2 rates all at 1.0
- locks = 0, unverified numbers = 0, hard constraints carried = 1.0
- p95 total under 180 s
- conformance 11/11 protocol checks, plus HP's core checks once they're registered
- `kit gate` green, with the parity waiver listed

Today the IQ reference hook meets this bar at tier `none` on IQ's dev set (`iq-dev@0`, status `placement_only`). The `taco_hw@1` fixture, `oracle/enumerate.py` and the HW cases land Nov 20–21. Each lane's job is to swap its reference stand-in for the real component without moving any number.

## Swap order (each swap is one PR, reviewed by the other agent, merged by the queue)

| # | Lane | Swap in | Replaces IQ reference | Suite that must stay green | Needed by |
| --- | --- | --- | --- | --- | --- |
| 1 | HP | Twin core half: mock Gateway (FastMCP), consent gate, scoped token, mock Sparky; it calls `CatalogSlotsPort` | local consent/order entries in `ReferenceHook` | conformance `c01–c05` (unskipped via `KIT_CORE_IMPL`) | Sun Nov 22 |
| 2 | HP | K24 ShoppingPort H3 over the twin | direct `twin.catalog.discover()` calls | `-m cap07` (CT-07a, c, e, f) | Mon Nov 23 |
| 3 | HP | K05 slot plan (estimated mode) | `reference.plan_slot` | `-m cap10 -m cap43` | Mon Nov 23 |
| 4 | MF | K21 templates, K04 solver, K02 brief (deterministic) | `need_list`, `greedy_cart`, `render_brief_h2` | `-m cap07`, mutation suite, regret ≤ bar | Mon Nov 23 |
| 5 | PD | K06 rights, K10 poll (`owner_decides` + plurality) | owner-decides shortcut in `ReferenceHook` | `-m cap28`, K10 property tests | Mon Nov 23 |
| 6 | ED | K12 ledger, K26 telemetry stamps | `MiniLedger` | `audit_chain_complete`, trace-integrity oracle | Mon Nov 23 |
| 7 | DX | K11 template cards, D01 beat 1 | `approval_card` | K03 `verify_card` (0 unverified, every claim labeled) | Tue Nov 24 AM |
| 8 | A | Taco-night hello-world hook (C's ask) | `ReferenceHook` | the full pass bar above | Tue Nov 24 AM |

## Nov 24 sequence

1. **09:00:** freeze-check. Every swap PR is merged or explicitly deferred, and a deferred swap keeps its reference stand-in. Tag the candidate commit.
2. **09:30:** run `kit eval hello-world --hook apps.taco_night.hook:hook --k 5`, `kit conformance` and `kit mutate`, then `kit gate` against the reference baseline.
3. **10:30:** triage. Every failure becomes a case in `data/seeds/cases/` *before* it gets a fix, as `hw-taco-009` did on Nov 19. A world-infeasible episode is shown as such, not hidden.
4. **13:00:** DX runs beat 1 on the console against the same build.
5. **15:00:** release bundle 1. Run `kit bundle build`, tag it, and attach the manifest, eval report and gate record. D's blind transfer runs on this bundle.
6. **20:00:** the nightly gate goes live, and the merge queue runs on its result.

## Fallback

If A's hook isn't callable on Nov 24, the hello world runs on the IQ reference hook: the same twin, cases and gate. The talk's beat 1 is then labeled "reference pipeline", and A's hook lands on Nov 25 with zero slack, per F's critical path. The engine's stage-0 gate (E17, `engine-run`) accepts either hook, because both return the same tier 0/1/2 report.

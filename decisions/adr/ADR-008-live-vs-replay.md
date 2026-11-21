# ADR-008 — On stage, the engine is live where it is deterministic and replayed where it is stochastic

Status: proposed (Fork F, cycle 2, 2026-11-19). Affects E02–E19, D01, D06, P03.

## Context
The vision's talk shape gives the engine 5 minutes: zoom out to the map, flip a control, flip the lens, drill into a cell. A full engine run (sampling, generation, dedupe, interviews, judges, three seeds) takes hours on the two hosts and is stochastic. The audience must see real computation, not a slideshow, and the demo must survive bad Wi-Fi.

## Decision
- Stochastic stages (E02–E10, E15) run **before** the talk as Fleet `engine-run` night jobs; their output is a versioned bank with a run report and engine evals (E18).
- Deterministic stages (E11 controls with lenses and clamps, E12 selection and 2×2, E14 decomposition, E16 readout rendering) run **live** over that bank in under 1 second per flip, inside the demo console (E19, D01).
- Every live flip is a `ControlDelta@0` event: logged and traced like a code change (vision: "every control change is logged and traced"), so the flip on stage is itself an auditable artifact.
- Stage 0 still gates: the bank on stage records the bundle and the hello-world result it was produced under.

## Alternatives
- Run the whole engine live: impossible in 5 minutes, and stochastic output on stage cannot be checked.
- Show screenshots: no live moment, and it contradicts "harness, not slideshow".

## Consequences
- E19's sub-second recompute is a hard requirement (oracle in components@2).
- The talk says plainly which parts ran overnight and which run now.

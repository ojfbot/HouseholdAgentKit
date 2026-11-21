# ADR-009 — One demo console, three beats, a recorded fallback per beat

Status: proposed (Fork F, cycle 2, 2026-11-19). Affects D01–D07, K10, K11, E19, D06.

## Context
The 15-minute talk now has three live systems: the hello world (taco night with the room voting), the engine map (control and lens flips), and Care Profiles (Ruth's voice request, Jen's over-cap card). Product & delivery is the most overloaded role in the Dec 2 plan, and three separate apps would triple UI work and switching risk on stage.

## Decision
- One web console (D01) with three beats, one key each; every view renders Card@0 or Readout@0, so K11 cards, ballots and readouts share one renderer.
- Phones join by QR into the same console (D02) and see role-scoped cards only.
- Each beat has a recorded fallback captured at the Nov 30 dress rehearsal; D06's beat controller switches to it in under 10 seconds.
- The whole console runs offline on the stage host from the demo bundle; phones and traces use a hotspot (Fork D's runtime plan).

## Consequences
- UI work drops from three apps to one shell plus views (PD saves about 3 lane-days).
- A failure in one beat never blocks the next: each beat starts from its own fixture state.

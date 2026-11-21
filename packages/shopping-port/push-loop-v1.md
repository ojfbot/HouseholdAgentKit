# push@1: keep working with Sparky until the answer is good

Fork C · Nov 19, 2026 · proposal, reference code built · labels: synthetic (every number below comes from a scripted Sparky on the synthetic twin)

## Decision (the owner, Nov 19)
When Sparky's answer falls short, we don't take over and build the cart ourselves. We stay in the conversation and push until the answer is **good**: not only correct, not only accurate. Building the cart ourselves (K04) becomes the last resort, used only when no correct and accurate answer arrives within the budget.

Code: `fork-c/semantic/push_loop.py` (parse, assess, compose, run), `sparky_sim.py` (nine scripted Sparky behaviours), `taco_twin.py` (synthetic world), `test_push_loop.py` (17 tests; with the renderer's 11, 28 pass). It is deterministic: no model writes the follow-ups, and the same inputs give the same transcript.

## What "good" means
An answer is graded on three levels. It is **good** only when all three hold.

| Level | It holds when | Checks |
|---|---|---|
| Correct | The rules hold | Locked usuals exactly as the rule says; no hard excludes; at or under the budget; a pickup time before the deadline; every option a complete plate for the headcount; sponsored items marked; the number of options asked for; products, not a recipe |
| Accurate | The facts hold | Every product resolves to a real catalog item; prices, stock and totals check out; nothing left "unknown" |
| Good | It is worth choosing | Each option true to its goal (the repeat option uses our usuals, the fresh option has the most produce, the savings option is the cheapest); options really differ; soft preferences honoured; nothing we already have; sized for the headcount (no extra unit we don't need); nothing padded in (a sponsored dessert, say); a pickup time at least 15 minutes before the deadline |

Every good-level check scores 0–1. "Good" means correct + accurate + a mean of at least 0.9, with no check below 0.5. These thresholds are placeholders until they are calibrated on the owner's labels.

## How the loop pushes
- **Most serious first, three asks at most.** Correct-level asks come first, then accurate, then good. A soft preference waits until the rules hold.
- **Each ask quotes Sparky's own line** and says the fix in plain words: "In option 3 you listed "Basics flour tortillas, 10 count, 1, $1.98, in stock". That isn't our usual tortilla (usual:tortilla#a1). Use our usual tortilla: the same product in the same package, no substitutes. If it's out of stock, say so; don't swap it."
- **What's right is kept.** "Options 2 and 3 are right as they are; send them again unchanged." If an option got worse, the push gives back Sparky's own earlier lines for it.
- **Best so far, per option.** The loop keeps the best version of each option it has seen, so a fix that breaks something else never costs us.
- **Every push restates the hard rules** in a closing checklist, as semantic@1 does.
- **Sparky's questions are answered from the brief.** Anything about the household gets one fixed sentence: "I can't share more about the household; the rules in my request are everything you need." Every outgoing message passes the never-on-the-wire guard.
- **A good first answer gets no push.**

The ladder below covers one open finding. Each push about that finding moves it up one step.

| Step | What we send |
|---|---|
| 1 ask | Say what to change |
| 2 pin | Quote their line back and offer a choice: "Pick one: (a) put our usual cheddar in option 1, or (b) tell me it is out of stock." |
| 3 isolate | One yes/no question about one item and nothing else |
| 4 apply | "You confirmed our usual cheddar (usual:cheddar#b7) is in stock at $2.47. Please put our usual cheddar in option 1." |
| 5 reset | A new conversation: the brief plus "What we already know" (confirmed facts, items to leave out) |

Isolate and apply exist only for item facts (locks, stock, price); other findings go ask, pin, reset. The most serious open finding decides whether a turn escalates; the others wait at pin.

## How it ends
| Status | When | What happens next |
|---|---|---|
| GOOD | All three levels hold | The family poll and approval, as today |
| ACCEPTABLE | Correct and accurate, but good-level gaps remain at the budget (or only honest "unknown"s remain) | The card shows the gaps, labeled |
| INFEASIBLE | Sparky honestly reports that a locked item is out of stock | The family decides (A's `hw-taco-009-safe-food-out` card). Nothing is swapped, by Sparky or by us |
| FALLBACK | No correct and accurate answer within the budget | K04 builds the cart; the last resort |

Default budget: 6 Sparky turns, 180 s, one reset. Live, the time budget should come from the clock: the loop must end before the order-by time (the deadline, minus the store's lead time, minus checkout).

## Results on the scripted Sparky (synthetic)
| Sparky behaviour (scripted) | First answer | Loop result | Sparky turns | Pushes |
|---|---|---|---|---|
| clean | good | GOOD | 1 | none |
| eager (swap, unmarked sponsored add, unknown price, tomato) | not correct | GOOD | 3 | push 2 |
| stubborn (keeps the wrong cheddar until it confirms the usual) | not correct | GOOD | 5 | push 3, isolate 1 |
| regressor (a fix breaks another option) | not correct | GOOD | 2 | push 1; the broken option is kept from turn 1 |
| recipe (answers with a recipe) | not correct | GOOD | 2 | push 1 |
| asker (asks flour or corn, and about the kids) | not correct | GOOD | 2 | push 1; privacy answer |
| oos (the usual tortilla really is out) | not correct | INFEASIBLE | 2 | push 1 |
| never (keeps the lager) | not correct | FALLBACK | 6 | push 4, reset 1 |
| goodgap (the fresh option isn't the freshest) | correct + accurate | ACCEPTABLE | 6 | push 4, reset 1 |

**What this does and doesn't show.** The scripted Sparky fixes a flaw when a follow-up names it, so these runs test the loop's logic: priority, the ladder, keeping what's right, the guards and stopping. They do not show that real Sparky converges.

## Eval CT-07h (loop), proposed for IQ
- **Run:** every scripted behaviour, plus the R1–R3 readers from CT-07g, made multi-turn.
- **Report both numbers.** Report the first answer (tier 0 parity and the honest tier-1 bar for the brief) and the answer after the loop.
- **Bars:**
  - after-loop good rate ≥ 0.80 on R1, within budget;
  - accepted lock swaps = 0;
  - disclosure leaks in any push = 0;
  - pushes sent to an answer that was already good = 0;
  - a regression lowers the result = never (best-so-far);
  - median Sparky turns to good ≤ 3.
- **Push precision:** every ask names a defect the oracle confirms.

## What it changes
- **K24 (F):** it gains the loop. Assess and compose are deterministic (tier `none`); the model seam stays the H1 extractor (Sparky's prose answer → Cart), which now runs once per turn. INFEASIBLE maps to a Result@0 refusal code (proposed: `locked_item_unavailable`).
- **Telemetry:** each Sparky turn is a run with `component_id: K24.push_loop`, `loop_turn` and `push_kind`.
- **The talk (A, H):** one possible beat shows our agent working *with* Sparky rather than around it: Sparky's first answer, one push, the good answer. That matches Walmart's stated priority of completed baskets through Sparky (E's registry).

## Risks
- **Real Sparky may not converge.** That's why there is a turn cap, a time cap and the fallback. The owner's light manual runs can add a few real transcripts as eval cases.
- **Load on Sparky.** The Agentic Access Terms name no turn limit we know of; we keep it at six.
- **Drift over turns.** Keep-lines, best-so-far and the restated checklist hold it.
- **Prices or stock change between turns.** K03 re-verifies at checkout.
- **Leaking through answers to Sparky's questions.** The answer is a fixed sentence, and the guard runs on every push.
- **Thresholds.** The 0.9 mean and 0.5 floor are placeholders until they're calibrated on the owner's labels.

## Asks (reply by Sat Nov 21; Brief@1 freezes Nov 22)
1. **F.** Accept push@1 as K24's loop and the `locked_item_unavailable` refusal code.
2. **IQ.** Add CT-07h, tagged `cap07`, and the zero-tolerance rows above.
3. **HP.** Mock Sparky gateway mode goes multi-turn, with the nine behaviours in `sparky_sim.py` as config.
4. **A.** In `hw-taco@1`, tier 1 keeps its first-answer bar and adds the after-loop number. Decide whether the loop is shown on stage.
5. **H.** Cards for ACCEPTABLE (labeled gaps) and INFEASIBLE.

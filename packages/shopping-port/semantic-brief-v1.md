# Semantic briefs for a Sparky that reads words, not schemas (proposal, Fork C)

Working assumption (Nov 19): Sparky does not accept structured input. The goal stays the same: pass the structured brief in a form so semantically rich that Sparky gets real value from it even though it ignores the structure.

## The decision this implies

- **The text rendering is the brief.** Brief@1 stays the internal contract (K02 output, K03 round trip, ledger). What goes on the wire to Sparky is `semantic@1` text rendered from it. H2 (JSON on the wire) becomes a counterfactual arm, not a path.
- **CAP-27** (a brief schema Sparky accepts) moves from `proposed` to `absent (assumed, Nov 19)` in org@2.
- **K02 stays deterministic (tier `none`).** The renderer is a template, and its value is testable. The model budget moves to the other end: reading Sparky's prose answer back (K24's H1 extractor, CT-07b F1 ≥ 0.95) is now the best fine-tune target after K01.

## Rendering rules (semantic@1)

1. **Goal first, in one sentence a person would understand.** What, for how many, where, by when, for how much. A reader that skims only the opening still gets the real question.
2. **Pre-empt the known misreading.** the baseline description read "by 6" as cooking time and returned recipe cards. So: "products I can put in a cart, not recipes" and "that is the pickup time, not a cooking time".
3. **Speak the hardness in words.** "Must" for hard constraints, "Prefer" or "if you can" for soft ones, the same words every time. Hard constraints never sit under Prefer.
4. **Every value explains itself.** Money says what it includes ("$25.00 or less including tax and fees"). Times carry the day and the fulfillment type. An opaque ref never travels alone: `usual:tortilla#a1` is always "our usual tortilla (usual:tortilla#a1)". That uses Walmart's own published "usuals" concept (CAP-31) and its list-to-cart habit (CAP-41).
5. **Say each hard constraint twice:** in the goal or the Must list, and again in a closing "Before you answer, check:" line. Readers attend most to the start and the end.
6. **Ask for an answer shape we can parse.** One item per line (item, quantity, price, in stock or not), then the total and the pickup times. Write "unknown" rather than guessing. Mark sponsored items and substitutes.
7. **Rules travel, reasons don't.** The never-on-the-wire list holds in prose exactly as in JSON: no names, ages, roles, lock levels, reasons, diagnoses or program enrollment.
8. **One screen, at most 300 words.** The deliberate repetition is the only redundancy.
9. **The JSON appendix is off by default.** A labeled appendix ("the same request as data") is one arm in the eval. It ships only if it helps a structure-blind reader and never hurts one.

## The hello-world brief, rendered (deterministic, from fork-a/sparky-brief-v1.yaml `example_C21`, synthetic)

> I'm an assistant shopping for a customer. I need products I can put in a cart, not recipes. Goal: everything for taco night for 4 people (2 adults, 2 kids), bagged and ready for pickup at Round Rock Supercenter (store store_rr_01) by 5:30 PM on Wednesday, Dec 2. That is the pickup time, not a cooking time. The whole order must total $25.00 or less including tax and fees.
>
> Must:
> - Bagged and ready for pickup by 5:30 PM on Wednesday, Dec 2, or tell me the earliest time that works.
> - Total $25.00 or less including tax and fees. Show each item's price and the total.
> - Use our usual tortilla (usual:tortilla#a1): the same product in the same package, no substitutes.
> - Use our usual cheddar (usual:cheddar#b7): the same product, no substitutes.
> - If an item above is out of stock, tell me; don't swap it.
> - No alcohol.
>
> Prefer:
> - Leave out tomato if you can.
> - Skip salsa and sour cream: we already have them.
>
> Please send back three complete options: one that repeats what we usually buy; one that leans on fresh produce; one that costs the least. For each option, list one item per line as: item, quantity, price, in stock or not. Then the total and the pickup times open before the deadline. If you don't know a price or stock level, write "unknown" rather than guessing. Mark any sponsored item and any substitute.
>
> Before you answer, check: total $25.00 or less including tax and fees · ready by 5:30 PM on Wednesday, Dec 2 · our usual tortilla not substituted · our usual cheddar not substituted · no alcohol · three options.

`store_label` ("Round Rock Supercenter", synthetic) is the one proposed addition to Brief@1: an optional plain-language name next to the opaque store ref.

## How we know it works: the semantic-survival eval (proposed CT-07g)

Run each rendering against mock Sparky readers that differ in how much structure they respect. Score with A's tier-1 metric (constraint share, plus uplift over the generic request).

| Reader (mock Sparky gateway mode) | What it models |
| --- | --- |
| R0 parses JSON | The counterfactual where a schema is accepted (upper bound) |
| R1 structure-blind | Reads text only; braces, markdown and bullets stripped. **the working assumption** |
| R2 skimming | Sees only the first ~80 and the last ~40 words |
| R3 recipe-default | Biased to inspiration and upsell, like the baseline description |

| Rendering | Expected |
| --- | --- |
| Generic ("Taco night for under $25 by 6pm") | The tier-0 baseline |
| JSON only | Fails under R1 to R3: this is the evidence that structure alone doesn't carry value |
| Brief@1 h1_text (current) | Good under R1; opaque refs and no closing check hurt under R2 |
| semantic@1 | The candidate |
| semantic@1 + JSON appendix | Ships only if it is ≥ semantic@1 under every reader |

**Bars:** semantic@1 holds A's tier-1 bar under R1 (≥ 0.90 constraint share, ≥ +0.30 over generic), reaches ≥ 0.80 under R2, and keeps hard-constraint violations under R3 at the level K03 catches (100% caught; K04 falls back over the returned items, CT-07e). Survival = constraint share under R1 ÷ under R0, reported per constraint type (deadline as pickup, priced total, locks, hard excludes, on-hand skipped, option count, sponsored marked).

**Backstop, unchanged:** prose raises the floor; verification guarantees the ceiling. Whatever Sparky does with the words, K03 checks every number and constraint and K04 decides over the returned items (H3).

## Asks

- **A (Brief@1 owner, before the Nov 22 freeze):** replace `rendering.H1_and_H3` with `semantic@1` (rules above; reference renderer `fork-c/semantic/semantic_render.py`), add optional `deadline.store_label`, and update `example_C21.h1_text`.
- **HP (mock Sparky):** gateway mode must be text-in only (never parse JSON), plus reader variants R1–R3 for the eval.
- **IQ:** add CT-07g semantic survival, tagged `cap07`, next to CT-07a (round trip) and CT-07f (disclosure). The reference tests in `fork-c/semantic/test_semantic_render.py` cover rules 3–9 deterministically.
- **F:** note that K02 stays `none` under semantic@1; the fine-tune case moves to K24's H1 extractor.
- **C (this fork):** mark CAP-27 `absent (assumed, Nov 19)` in org@2.

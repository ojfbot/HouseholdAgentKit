# member@1: "shopper" is a household, not a person

Fork C · Nov 19, 2026 · proposal · labels: synthetic (run-0 tags are Fork C's judgement; the seeds are agent seeds, not yet scored)

## The problem (the owner, Nov 19)
Lattice@1 has one actor type, `shopper`, for everyone in a family: the account holder, a partner, a teenager, an 8-year-old and a cared-for parent. They differ in exactly the ways that change what an agent may do: legal standing, how much say they have, whose money it is, how they reach the agent, what others in the house may see, and whether their rights are growing or changing.

Run 0 shows the gap. I tagged its 39 shopper-side families by member:

| Member | Card told from them | Takes an active part | Appears at all |
|---|---|---|---|
| account holder | 32 | 37 | 37 |
| co-adult (partner, co-parent) | 2 | 8 | 9 |
| adult member (adult child at home, roommate) | 2 | 2 | 2 |
| teen (13–17) | 0 | 0 | 0 |
| child (5–12) | 0 | 1 | 8 |
| little one (0–4) | 0 | 0 | 3 |
| cared-for elder | 2 | 2 | 5 |

"Active part" means the member decides, co-decides, requests or votes. Teens are missing entirely. Children appear in 8 families but act in only one (the taco-night ballot). The cared-for parent leads only twice, both times inside a caregiver's controls.

## The change (lattice@2, additive)
- **A new stratification axis, `household_member`,** for the shopper, never-shopper and caregiver actor types: account holder, co-adult, adult member, teen, child, little one, cared-for elder. Actor-type values don't change, so every run-0 card and G's validator stay valid.
- **Six dimensions behind the types:** capacity, say, money, channel, visibility and trajectory. Each member type is a set of defaults on them, and a generated profile can vary any of them (a 17-year-old with a paycheck, an older adult who needs no help). The types are starting points, not boxes.
- **Two new card fields:** `protagonist` (whose need starts the order) and `members[]` (everyone the family touches and how each takes part).
- **Sampling** stratifies by member, with at least 4 cells and 2 protagonist cards per member type. Invalid pairs are filtered, for example a child as payer, a little one with any say, or an under-13 member with their own agent.
- **New homework check, H6 member coverage.**
- **Internal only.** Member types, ages and say never travel to Walmart; Brief@1 still sends a headcount and rules.

Spec: `fork-c/lattice-v2-members.yaml`. Tags and seeds: `fork-c/members.py`.

## What Walmart's own terms add
- **CON-M1 (published):** a minor may use Walmart.com with a parent's or guardian's consent.
- **CON-M2 (published, as quoted on a third-party site; E to verify):** Walmart doesn't knowingly collect personal information from children under 13. Our rule on top: nothing about an under-13 member leaves our side, and their votes stay in K10.
- **CON-M3 (published, as quoted on a third-party site; E to verify):** the buyer is responsible for age limits on products. Our rule on top: an age-limited line a minor asks for goes to an adult, never into a minor's cart or profile.
- **CON-M4 (ours; needs the owner):** a member's private lines show to others only as a category and price, unless the line is age-limited or breaks a household rule.
- **CON-M5 (ours):** a cared-for adult's request stays theirs. A caregiver can block a rule violation but never silently rewrite a preference.

## 14 seed families for run 2
These are first placements for the engine to re-score.

| ID | Family | Told from | Tier | Conditions |
|---|---|---|---|---|
| M-01 | Two agents, one fridge (both partners' agents order; rules don't cross) | co-adult | 2 | O C R |
| M-02 | The partner who isn't on the account | co-adult | 2 | O R |
| M-03 | The household lead stops being the bottleneck (everyone adds, one approval) | account holder | 2 | T U O |
| M-04 | A teen's own agent with an allowance cap | teen | 2 | O R C |
| M-05 | The teen cooks Tuesday | teen | 1 | O |
| M-06 | An age-limited line in a minor's request goes to an adult | teen | 2 | R O |
| M-07 | Kids vote, with none of their data sent | child | 2 | O |
| M-08 | Lunchbox week the kid helps pick | child | 1 | O R |
| M-09 | The class party for the 8-year-old | child | 2 | T O R |
| M-10 | The daycare list, labeled | little one | 1 | T C |
| M-11 | Her own voice, her own order (no one approves ordinary orders) | cared-for elder | 2 | C R |
| M-12 | Grandpa lives with us: his plate, his rules | cared-for elder | 2 | O R |
| M-13 | When the rules need to change, who changes them | cared-for elder | 2 | O R U |
| M-14 | Back home for the summer | adult member | 1 | O C |

With the seeds, every member type has at least 3 protagonist cards except little ones (1). The seeds lean tier 2: most of them involve other people (O) or completion under rules (R), which Sparky in the app can't do for a household.

## What it touches elsewhere
- **B (profiles, Household schema):** Household v0's roles `owner | partner | kid` map to account holder, co-adult and kid. Kid splits into teen, child and little one by age band; the ages stay in the Mandate. Two roles are new: adult member and cared-for elder. The six dimensions join the profile schema. C08 Ruth and C24 Walt become cared-for elders with full rights by default.
- **A (taco night):** the hello world already has two kids (7 and 10) voting. Please confirm the ballot carries nothing personal about them and that votes never leave K10; the cards test does that today for the wire. M-12 is a natural taco-night variant with a fifth plate.
- **H (cards):** the child ballot needs copy an 8-year-old can read; an elder's card needs voice and large type, with no talking down.
- **G (engine):** add the `household_member` axis and the member quota to sampling, `protagonist` and `members[]` to the card, H6 to homework, and the 14 seeds to run 2.
- **E:** verify CON-M2 and CON-M3 on walmart.com itself (both are quoted from a third-party site).
- **the owner:** CON-M4, the payer's view versus a teen's privacy. Queued as Q-C-1, default A.

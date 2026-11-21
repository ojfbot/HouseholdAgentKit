# Glossary

Words that have one meaning in this repo.

| Word | Meaning |
| --- | --- |
| **Hello world** | Taco night: one family, one dinner, one priced cart under their rules, voted on and approved. The first thing that must work end to end. Its oracle is `hw-taco@1`; a run returns `hello_world_result@1`. |
| **`placement_only` / `pass`** | Hello-world statuses. `placement_only`: the pieces are in the right places but the full oracle did not run. `pass`: the oracle's cases ran and passed. Only `pass` counts as working. |
| **Tier (value)** | How much the agent adds over the store's own assistant. 0: parity. 1: a better answer because the agent wrote a more specific brief. 2: something only an outside agent can do. |
| **Tier (model)** | What a run needs. `none`: no model, no keys, deterministic; CI runs only this. Other tiers use local or frontier models and never run in CI. |
| **Twin** | The synthetic store: catalog, prices, stock, pickup slots, a simulated clock (`packages/mock-gateway`). Everything "Walmart-side" in this repo is the twin. |
| **Sparky (mock)** | A scripted stand-in for the store's assistant, written from public descriptions. Never the real one. |
| **Brief** | The request the agent sends to the store's assistant: what the household needs, with rules but not reasons. |
| **Lock** | A household rule that names an exact item or brand ("these tortillas, nothing else"). A constraint, never a preference. |
| **Mandate** | What the household has authorised the agent to do: caps, schedule, who approves. |
| **Verifier** | The component (K03) that checks every number and rule on a cart or card against the twin's state. |
| **Claim / label** | Every number shown to a person is a claim with a label (`synthetic`, `public:<source>`, `observed:<source>`) and a named verification. |
| **Capability (CAP-nn)** | Something the store's systems may or may not offer outside agents, with a status: `published`, `announced`, `inferred`, `invented`. |
| **Component (Knn, Enn, Dnn, Pnn)** | A unit of the design in `components@2`: K product and platform, E engine stage, D demo, P factory. |
| **Contract** | A versioned spec two pieces agree on (`name@version`). Changing one is a labeled pull request that waits for the owner. |
| **Loose contract** | A contract the code reads through an accessor that accepts more than one shape, because its owner has not settled it. |
| **Family / card / bank** | Engine terms. A problem card describes one way people might use a shopping agent; similar cards form a family; a run's families form a bank. |
| **Lens** | Whose value the engine sizes: the retailer's or a partner's. Flipping it changes stakes, not facts. |
| **Bundle** | Model + harness + context, each versioned, hashed into one `bundle_id` stamped on every result. |
| **Gate** | The nightly decision on whether a bundle is good enough: zero-tolerance metrics, then a paired comparison with the baseline. |
| **Holdout** | Cases never used for training or tuning. The seed stays out of the repo; only its hash is committed. |
| **Lane** | A role an agent works in: HP harness and platform, IQ integration and quality, PD product and delivery, ED evals and data, MF models and fine-tuning, EN engine, DX demo, EL engagement lead (the owner). |
| **Rung** | One step of the integration ladder (`docs/ladder.md`), with checks. |
| **Proof (of a check)** | A deliberately broken setup the check must turn red on, plus a working one it must turn green on. |
| **Conductor** | The one agent session that works the ladder and the backlog in order and dispatches issues to worker agents. |

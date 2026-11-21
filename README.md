# HouseholdAgentKit

An open, **synthetic-only** proof of concept of a household shopping agent: a family asks for taco night, the agent writes a brief a store's assistant can act on, a solver builds priced carts under the family's rules, the family votes, and a verifier checks every number before anyone approves. Built for the AI Tinkerers demo night in Plano on Dec 2 2026.

Independent and unofficial. Not affiliated with Walmart or any company named here; no real data. See [DISCLAIMER.md](DISCLAIMER.md).

## Status

`kit doctor` is the status. Today rungs 0 and 1 of the [integration ladder](docs/ladder.md) are green in CI; rung 2 (a real machine) is next. The hello world runs against a reference stand-in and reports `placement_only`, not `pass`: the real agent components are the backlog. The honest list of what is unproven is the [risk register](docs/integration-risk-register.md).

## Quickstart (no models, no keys, no network after install)

Needs [uv](https://docs.astral.sh/uv/) and CPython 3.12.

```bash
uv sync --frozen
uv run python apps/demo-console/fixtures/build_engine_fixtures.py   # generated fixtures for the console
uv run kit doctor                       # one line per rung: green, red, or not climbed
uv run kit hello-world --mode smoke     # taco night at tier none
uv run pytest -q -m "not slow and not mutation"
uv run python apps/demo-console/server/host.py   # stage at http://127.0.0.1:8765/
```

## What is here

| Path | What | Built by |
| --- | --- | --- |
| `kit/` | The `kit` command: `doctor`, `hello-world`, `eval`, `mutate`, `conformance`, `bundle`, `gate` | IQ |
| `packages/mock-gateway/` | The synthetic store twin: catalog, usuals, pickup slots, a simulated clock | IQ |
| `packages/verifier/` | Checks every number and rule on a cart or card; its mutation suite plants 508 faults | IQ |
| `packages/eval-harness/` | Hello-world hook, oracles, conformance, reports | IQ |
| `packages/kit-gate/` | Bundle ids, the nightly gate, review queue, digest | IQ |
| `packages/contracts/` | Draft Python mirror of the shared contracts | IQ for F |
| `packages/discovery-engine/` | The engine that samples, sizes and ranks problem families, with a live controls API; `prototypes/` holds the earlier scripts it is checked against | EN |
| `packages/card-writer/` | Writes approval cards; a guard refuses any number without a verified, labeled claim | DX |
| `packages/shopping-port/` | Reference code for the brief renderer and the "keep working with the store's assistant" loop | C |
| `apps/demo-console/` | The stage and phone screens, offline, on fixtures until live services exist | DX |
| `tests/` | Capability-tagged contract suites, conformance, mutation, doctor proofs | IQ |
| `contracts/` | The specs the code is built to ([index](contracts/README.md)) | owners per file |
| `decisions/adr/` | Architecture decision records | F |
| `docs/` | [Ladder](docs/ladder.md), [risk register](docs/integration-risk-register.md), [hand-off](docs/hand-off.md), [review request](docs/ladder-review-request.md) | |

Words used throughout (tier, lens, bundle, lane, twin) are in [CONTEXT.md](CONTEXT.md).

## How it is built

A small team of AI agents builds this from GitHub issues, with one human owner. Rules for agents are in [AGENTS.md](AGENTS.md) (also read as `CLAUDE.md`); rules for everyone are in [CONTRIBUTING.md](CONTRIBUTING.md). Three ideas carry most of the weight:

- **The model proposes, the solver decides, the verifier checks.** No number reaches a screen without a claim, a label and a verification.
- **Every failure becomes an eval case before it gets a fix.**
- **Every check is proven before it gates**: shown red on a planted break and green on a working setup.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

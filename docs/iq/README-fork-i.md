# Fork I — Integration & quality (IQ): code staged for the repo

This tree is laid out at the target repo paths (`ojfbot/household-agent-kit`, or whatever R1.5 names it). It moves in as-is with the founding PR, or as IQ's first PR straight after it. Everything here is synthetic.

**Status, Nov 19:** 117 tests pass (5 skipped until HP's core lands). The mutation suite catches 508/508 mutants, each for the right reason, with 0 false alarms. Conformance is 11/11. The tier-`none` hello world reaches pass^5 = 1.0 across 40 twin seeds. ruff and pyright (src) are clean.

## What's here (brief → path)

| Brief item | Path | Run |
| --- | --- | --- |
| K17 twin, catalog and slots half | `packages/mock-gateway/src/mock_gateway/` (`catalog.py`, `slots.py`, `clock.py`, `labels.py`, `seams.py`) | `pytest packages/mock-gateway` |
| CT-07, CT-10 (+ CT-43) suites tagged by capability; CT-02, 21, 28 | `tests/contract/` | `pytest -m cap07`, `-m cap10`, `-m cap43`, `-m cap02`, `-m cap21`, `-m cap28` |
| K03 verifier and its mutation suite | `packages/verifier/src/kit_verifier/` · `tests/mutation/` | `kit mutate` |
| K20 conformance: tier-0 parity and protocol | `packages/eval-harness/src/kit_eval/conformance.py` · `tests/conformance/` | `kit conformance` |
| K27 eval harness and hello-world hook (HelloWorldResult@1, Fork A's `hw-taco@1`) | `packages/eval-harness/src/kit_eval/` (`hello_world.py`, `hook.py`, `report.py`, `reference.py`, `oracles.py`) | `kit hello-world --mode smoke\|full`, `kit eval hello-world --k 5` |
| P02 bundle manifest and nightly `kit gate` | `packages/kit-gate/src/kit_gate/` (`bundle.py`, `gate.py`) · `bundles/gate-config.yaml` | `kit bundle build`, `kit gate` |
| Red-team: prompt injection in Sparky replies | `data/seeds/redteam/sparky-injection.yaml` · `kit_eval/sparky_replies.py` · CT-07c | `pytest -m redteam` |
| Cross-review queue and daily digest | `kit_gate/review.py`, `merge_queue.py`, `digest.py` | `kit review status`, `kit merge-queue plan`, `kit digest` |
| CI workflows and ruleset (punchlist block 3) | `.github/workflows/`, `.github/rulesets/main.json`, `scripts/apply-repo-settings.sh`, `.pre-commit-config.yaml` | owner runs the script once |
| Nov 24 integration plan | `docs/iq/hello-world-nov24.md` | |
| Merge policy and its known limit | `docs/iq/ruleset-and-merge-policy.md` | |
| Draft contract mirror (F owns content) | `packages/contracts/src/kit_contracts/` | |

## Quickstart (before the uv workspace exists)

```
export PYTHONPATH=$(ls -d packages/*/src | tr '\n' ':')kit/src
python -m pytest -q
python -m kit_cli eval hello-world --k 5 --out out/hw.json
python -m kit_cli gate --candidate out/hw.json --today 2026-11-24
```

## Next slice (Nov 20–21, before `hw-taco@1` freezes)

- `fixtures/taco_hw@1.json`, with A's catalog invariants as tests.
- `oracle/enumerate.py`: an exhaustive enumerator that never imports K04, used for utility regret and hit@3 under hidden weights.
- Port HW-T0/T1/T2/PKG/FAIR into the harness, plus an R0 rubric scorer.
- Align the gate's zero-tolerance names with the oracle.

Until then, `kit hello-world` returns `placement_only` over IQ's dev set (`iq-dev@0`).

## Held loose until "Decisions batch 1"

- **Case v1 (R4.2):** the core fields are required; either D's or F's extras are accepted.
- **Mandate v1 `standing` (R4.4):** read through `kit_contracts.loose.standing_view`, which accepts both F's shape and a guardrail-mapped shape.

Every dependent test is marked `loose_contract`, so `pytest -m loose_contract` lists what to re-pin.

## Reference stand-ins (tier `none`)

`kit_eval/reference.py` and `tests/contract/reference_impl.py` hold the smallest deterministic thing that meets each contract. They let the suites run before the owning lanes land. They are not the product components: each owner binds the real one with `KIT_CT_IMPL` or `--hook`, and the suites don't change.

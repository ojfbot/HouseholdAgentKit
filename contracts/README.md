# Contracts

Versioned specs the code is built to. A change to any file listed here is a pull request labeled `contract` and waits for the owner. Status of each contract (acked, proposed, loose) is in [`docs/integration-risk-register.md`](../docs/integration-risk-register.md#unacked-contracts). Freeze is Sun Nov 22 2026.

Each contract has one copy. Where a script needs a file beside it, the copy lives with the script and is listed here.

| Contract | File | Owner |
| --- | --- | --- |
| `hw-taco@1`, `hello_world_result@1` | `contracts/hello-world/hello-world-spec.md`, `hello-world-oracle.yaml` | A |
| Poll@1, Sparky brief v1, Telemetry v1 | `contracts/interfaces/poll-v1.yaml`, `sparky-brief-v1.yaml`, `telemetry-v1.yaml` | A |
| `components@2`, `needs@1`, `Result@0`, `adapters@1` | `packages/discovery-engine/prototypes/fork_f/components-v2.yaml`, `adapters.yaml` | F |
| Bundle manifest v0, job kinds v0, eval gates v0 | `contracts/factory/` (two of these do not parse as YAML yet: R-13) | D |
| `org@2`, `stated_priorities@1` | `packages/discovery-engine/prototypes/fork_e/org-model-v2/` | E, C |
| `lattice@1`, `controls@1`, rubric v2 | `packages/discovery-engine/prototypes/fork_c/` (vendored, checksummed) | C |
| `member@1` (proposed) | `contracts/engine/members-v1.md` | C |
| `semantic@1`, `push@1` (proposed) | `packages/shopping-port/semantic-brief-v1.md`, `push-loop-v1.md` | C |
| `Readout@0`, `ControlDelta@0` (drafts) | `packages/discovery-engine/docs/contracts-proposed.yaml` | G for F |
| Draft Python mirror | `packages/contracts/src/kit_contracts/` | IQ mirror of F |
| `ports@0` | `contracts/ports.yaml` | bootstrap |

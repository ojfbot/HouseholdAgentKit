# Ruleset and merge policy (IQ draft for the founding PR)

Running on the owner's defaults until "Decisions batch 1" posts: **R1.1** agents auto-merge after green CI, the nightly gate and the other agent's review, and contract and ADR PRs wait for the owner. **R1.3** one daily digest from IQ, with interrupts only for blockers, needed decisions or anything irreversible. **R6.3** rebase-only merges, linear history, no self-hosted runners.

## What enforces what

| Rule | Enforced by | File |
| --- | --- | --- |
| Rebase only, linear history, no force-push or deletion of `main` | Ruleset: `allowed_merge_methods: [rebase]`, `required_linear_history`, `non_fast_forward`, `deletion`; repo merge settings | `.github/rulesets/main.json`, `scripts/apply-repo-settings.sh` |
| Green CI | Required checks `ci`, `security`, `privacy-guard`, all pinned to the GitHub Actions app (`integration_id` 15368) so a status from any other source can't satisfy them | ruleset, `ci.yml`, `security.yml`, `privacy-guard.yml` |
| The other agent's review | Required status `cross-review`. It is green only when the latest `kit-review` marker from the agent that did **not** write the PR approves the **current head SHA** and carries an evidence line. A push makes the review stale. | `cross-review.yml`, `packages/kit-gate/src/kit_gate/review.py` |
| Nightly gate | The merge queue merges only heads that have a green `kit gate` record from tonight. Each PR head is rebased onto `main` and gated there, and the merge is pinned with `--match-head-commit`. | `nightly-gate.yml`, `merge-queue.yml`, `kit_gate/gate.py`, `kit_gate/merge_queue.py` |
| Contract, ADR and irreversible changes wait for the owner | The queue never merges a PR with a `contract`, `adr`, `irreversible` or `cross-repo` label, or one that touches `contracts/`, `decisions/adr/`, `.github/`, `bundles/gate-config.yaml`, `packages/kit-gate/`, CODEOWNERS, LICENSE, NOTICE or DISCLAIMER. These PRs appear under "Needs you" in the digest. | `kit_gate/merge_queue.py` (`OWNER_LABELS`, `OWNER_PATHS`) |
| No self-hosted runners | Every workflow runs on `ubuntu-24.04`. Model and GPU work goes through Fleet jobs that pull `main` only. | all workflows |

Two choices beyond the punchlist:

- **The gate and the CI config are owner-gated paths.** An agent can propose a looser gate, but it can't merge one: the referee doesn't merge changes to its own rules.
- **Strict "up to date" is off, and the queue rebases instead.** With strict on, every merge would force every other PR to rebase and rerun CI, and with eight lanes that stalls the night. Instead, the nightly gate rebases each head onto the `main` it will land on and gates the result. The queue merges oldest first and pins each merge to the SHA it gated. A PR that moved since then waits for the next night.

## Known limit (queued for the owner as Q-I-1)

The agents and the owner all push and comment as `@ojfbot`, so GitHub can't tell them apart:

- An agent can't approve its own PR: the marker names its reviewer, and the `impl:` label names the author.
- An agent could still click merge by hand, or add the label that means "the owner approved".

The ruleset can't stop either today. Until agents act through a separate bot identity, owner-gating is enforced in two places: the queue, which never merges those PRs, and the `CLAUDE.md` / `AGENTS.md` rule that agents never run `gh pr merge` themselves. With a GitHub App identity for agents, the ruleset can require the owner's approving review on owner-gated paths, and the rule becomes mechanical.

## Merge timing (queued as Q-I-3)

R1.1 says "after the nightly gate", so tier-`none` PRs merge once a night, up to about 24 hours after their review. An option for the owner: run the same tier-`none` gate every two hours on GitHub-hosted runners, and keep model-tier bundle-evals nightly on Fleet. The default stays nightly until he picks.

## Review marker (both agents)

```
<!-- kit-review v0 -->
reviewer: codex
verdict: approve
head: 3f9c2e1a7b...
evidence: pytest 121 passed; kit mutate 1.000/484; hello-world pass^5 1.000; trace <link>
```

Post it as a PR review or comment. `request-changes` fails the check until a new approving marker for the new head arrives. Every failure a review finds becomes an eval case before it gets a fix.

## Check before first use (block 3 punchlist item)

`scripts/apply-repo-settings.sh` prints the required contexts after it applies the ruleset. They must read `ci security privacy-guard cross-review`. On the first PR, confirm that the `cross-review` commit status from `GITHUB_TOKEN` satisfies the `integration_id` pin. If it doesn't, drop the pin for that one context, and record why.

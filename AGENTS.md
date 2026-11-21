# Rules for agents working in this repo

`CLAUDE.md` points here, so Claude Code and Codex read the same rules.

## Before any write
- **Verify the target.** This is `ojfbot/HouseholdAgentKit`. Confirm `git remote -v` and the branch before you write. Do not touch any other repo unless your issue names it.
- **Work from an issue.** Read your issue, the files it names and the contract it names. Do not read planning documents outside the repo, and do not re-plan.
- **Run `uv run kit doctor`.** Never work above a red rung.

## How work flows
- Branch `<lane>/<slice>` (lanes: `hp`, `iq`, `pd`, `ed`, `mf`, `en`, `dx`), small commits, conventional commit messages with attribution trailers.
- Rebase onto `main` before review. Merges are rebase-only; history stays linear.
- Done means the issue's check is green and you can show it: the test output, the eval delta, or the doctor line.
- One agent writes, a different agent reviews.
- **These wait for the owner and are never merged by an agent:** contract changes (`contracts/`, label `contract`), ADRs (`decisions/adr/`), CI and ruleset changes (`.github/`), gate configuration (`bundles/gate-config.yaml`), `kit/src/kit_cli/doctor.py` checks, anything irreversible, anything in another repo.
- Agents and the owner currently share one GitHub identity, so GitHub cannot enforce the line above. Treat it as a hard rule: do not click merge on those paths.

## Stop rules
- Two failed attempts at the same check: stop. Write one paragraph: what you tried, what you think is wrong, and whether the check itself may be wrong. No third blind attempt.
- Over the issue's budget: stop and report.
- Do not install system software. List what is missing for the owner.
- A decision that is not yours goes to the decision queue as one line (question, options, default, deadline). Keep working on the default and say that you did.

## Rules the code enforces, which you must not weaken to get green
- Synthetic only. No Walmart data, no real customer data, no scraped data. Every number is labeled `synthetic` or `public:<source>`.
- Frontier models never bulk-generate training data, labels, preference pairs or calibration verdicts. Seeds written by agents carry `source: agent_seed`.
- Hard rules and locks are constraints, never weights. A locked item is never swapped.
- No secrets, weights, checkpoints, generated data or holdout seed in the repo.
- No self-hosted runners. CI is GitHub-hosted, tier `none`, no secrets.
- A new check needs a proof (a planted break it goes red on) before it gates. A failing check is fixed by fixing the cause, never by editing the file the check reads.
- Every failure found in a run becomes an eval case before it gets a fix.

## Where things are
- Tracker: this repo's GitHub issues. Each names its files, contract, check, model tier, size, budget and stop rule.
- Status: `uv run kit doctor`. Ladder: `docs/ladder.md`. Known risks: `docs/integration-risk-register.md`.
- Glossary: `CONTEXT.md`. Contracts: `contracts/README.md`. ADRs: `decisions/adr/`.
- Hand-off for the conductor: `docs/hand-off.md`.

## Agent skills
None are installed in this repo yet. The fleet's shared skills arrive at rung 3. Until then, the rules above are the whole convention.

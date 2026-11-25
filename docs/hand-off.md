# Hand-off to the local conductor

From the bootstrap session (cloud, Nov 20 2026) to the conductor running Claude Code in a local checkout of this repo on the stage host.

You have the repo, its CI and its issues. Do not re-plan and do not read the planning project; this repo is the source of truth from here. Your first job is **rung 2 only, then stop and report to the owner.**

## Where things stand

- **Rungs 0 and 1 are done.** The audit is [`integration-risk-register.md`](integration-risk-register.md). The founding pull request (#1, `hp/repo-init`) is green in CI on CPython 3.12.16. It imports four code trees that had never been run together; they pass together. CI runs on GitHub-hosted runners at tier `none`.
- **The founding PR is the owner's to merge.** If it is still open when you start, work from its branch and tell him.
- **Nothing has been run on a Mac.** Every result so far is from Linux on CPython 3.12.3 or from GitHub's runners.
- **The independent review is in, and its fixes are open.** It found 15 setups that get past `kit doctor` checks (#38) and three product bugs on the demo path (#35, #36, #37). Rung 2 can run now. Rung 3 does not start until #38 is closed; `kit doctor` prints that line red until then.
- **Decisions batch 1 is unanswered.** The repo was founded on the recommended defaults. The risk register lists them and the contracts nobody has acked.

## Rung 2: runs on the stage host

Budget: **one working session, 90 minutes.** Stop rule: two failed attempts at the same check, or the budget, whichever comes first.

```bash
cd <your checkout of this repo>
git remote -v && git status            # confirm the repo and a clean tree before anything else
uv sync --frozen
uv run python apps/demo-console/fixtures/build_engine_fixtures.py
uv run kit doctor --self-test          # every check red on its breaks, green on a working setup, on this Mac
uv run kit doctor                      # rungs 0 to 2
uv run kit hello-world --mode smoke
uv run pytest -q -m "not slow and not mutation"
uv run kit check                       # every pull-request workflow step, as CI runs it (pip-audit needs the network)
uv run kit gates                       # which milestones are blocked, read live from GitHub
uv run python apps/demo-console/server/host.py    # open http://127.0.0.1:8765/ and http://127.0.0.1:8765/?hud=1
```

Rung 2 is green when `kit doctor` prints `GREEN` for rungs 0, 1 and 2 on the stage host, and a person has seen the stage page render in a browser.

**What is most likely to go wrong, and what to do:**

| If you see | It probably means | Do |
| --- | --- | --- |
| uv cannot find CPython 3.12.16 | uv on the stage host is too old to know it, or no prebuilt 3.12.16 exists for macOS (risk R-09; GitHub's Linux runners got it, the bootstrap session's older uv could not) | Do not install Python yourself. Report it; the owner either installs 3.12.16 or answers Q-BS-1 (pin the newest 3.12 patch uv offers) |
| `python_pin` red, everything else green | A different 3.12 patch is running | Same as above. Do not edit `.python-version` to get green |
| `ports_free` red | Something on the stage host already uses 8765, 8790, 8791 or 8080 | Report which process. A port change is a `contracts/ports.yaml` change and waits for the owner |
| `console_on_fixtures` red with "fixtures not built" | The fixture builder was not run | Run it; these files are generated and never committed |
| `--self-test` shows a check that stays green on a break, or red on a working setup | The check is wrong on macOS | Stop. That is the finding. Report it with the row |
| A test passes in CI and fails on the stage host | A Linux-only assumption | Stop and report the test name and the difference; it becomes an eval case or a risk-register row before any fix |

**Not part of rung 2:** installing system software, running the headless-Chrome console test, anything with a model, anything in another repo, any fleet tool.

## The pilot stop

After rung 2, write the owner a few plain lines and wait:

1. Rungs 0 to 2: green or red, as `kit doctor` printed them.
2. Anything that differed between CI and the stage host.
3. What rung 3 needs: #38 closed, the founding PR merged, the ruleset approved (see "Owner steps").
4. Whether any check looked wrong.

## After the owner says go

Climb rungs 3 to 10 in order. Each has an issue labeled `rung` (#3 to #10; rung 2 is #2). For each rung:

- The rung's planned check and planned break are in [`ladder.md`](ladder.md). **Write the check and its proof first**, add it to `kit/src/kit_cli/doctor.py`, and show `kit doctor --self-test` green for it on the real setup. Changes to `doctor.py` wait for the owner's merge.
- At most two working sessions. Two failed attempts at one check: stop, one paragraph to the owner, including whether the check itself may be wrong.
- Never skip a red rung. Never make a check green by editing the file it reads.
- Follow the fleet's conventions as you find them on the machine. This repo does not describe them, because the bootstrap session was told not to assume anything about the owner's machines or other repos.

After rung 4, work the build backlog (issues labeled `build`, #11 to #34) in the order of their `P0`, `P1`, `P2` labels, and within a label in issue-number order unless an issue's "Depends on" line says otherwise. Issues labeled `blocked` wait for the decision they name. P0 is the taco-night critical path (#11 to #21) plus the review's findings (#35 to #38). Taco night first: it is the one live beat on Dec 2, and it is the engine's first gate. Dispatch each issue to a worker at the tier it names; a worker reads only its issue, its files and its contract.

## Things that will bite

- **Gates are code.** `docs/gates.yaml` says what must be done before rung 3 starts, before #20 (live beat 1) closes, and before rung 10 closes. `kit doctor` prints them and never says "climb" a gated rung; `kit gates --milestone <n>` exits 1 while one is open. Offline, every gate reads `UNKNOWN`, which is not clear.
- **`kit check` is CI.** It reads the workflow files, so there is no second list to keep in step, and runs each job in its own `git worktree` of a snapshot of your changes. It refuses workflow features it cannot reproduce (step `if:`, matrices and the like) instead of skipping them. The pre-commit hook scans what is staged (`kit privacy scan --staged`). The first `uv run pyright` on a new machine downloads its Node runtime into the uv cache; that is the only download besides pip-audit's.

- **Nov 25:** `discovery_engine run` aborts unless hello world returns `pass` from a `full` run. **Nov 28:** `kit gate` goes red when the parity waiver lapses. `kit doctor` counts down both. See R-02 and Q-BS-3.
- **`kit hello-world --mode smoke` exits 0 even when every episode fails** (R-04, #13). Trust `kit doctor`'s `hello_world_smoke` line, not that exit code, until the issue is closed.
- **Today's hello world is a stand-in** (`iq-reference-tier-none`, `placement_only`). Real components bind through `KIT_CT_IMPL=<module>:<attr>`, `KIT_CORE_IMPL` or `--hook`, and the existing suites become their check. Five conformance tests are skipped until a twin core registers.
- **Three workflows are staged, not active** (`docs/iq/staged-workflows/`): the nightly gate, the merge queue and cross-review. Do not activate them; see R-08, Q-I-1 and Q-BS-2. Until then nothing merges by itself.
- **`scripts/apply-repo-settings.sh` applies `.github/rulesets/main.json`.** That file requires `ci`, `security` and `privacy-guard`. Do not swap in the four-check version from `docs/iq/staged-config/`; it would block every merge (R-07).
- **Two files in `contracts/factory/` are not valid YAML** (R-13). Do not "fix" them in passing; that is a contract change.
- **Engine and console ports:** console 8765, engine 8790, poll bus 8791, model 8080 (`contracts/ports.yaml`).
- **Lint has two tiers** (R-15). New code meets the full rule set. Do not reformat the engine, console or reference code outside the issue for it.
- **GitHub cannot tell an agent from the owner** (Q-I-1). The "waits for the owner" list in `AGENTS.md` is a rule you keep, not one GitHub enforces.

## Owner steps (the owner)

| When | Step | Minutes |
| --- | --- | --- |
| Now | Read the top three risks in the risk register | 5 |
| Done | Independent review sent and recorded; its fixes are #35 to #38 | |
| Now | Review and merge the founding PR (rebase) | 10 |
| Before rung 2 | On the stage host: uv, and CPython 3.12.16 if uv cannot fetch it | 10 |
| Before rung 3 | Answer Q-BS-1 to Q-BS-4 and Q-I-1 in the decision queue; run `scripts/apply-repo-settings.sh ojfbot/HouseholdAgentKit`; turn on secret scanning and CodeQL default setup if the script reports it could not | 15 |
| Rungs 3 to 10 | The steps in each rung's issue | as listed |

## Open decisions raised by the bootstrap session

In the planning project's the decision queue: **Q-BS-1** (what to pin if 3.12.16 cannot be installed by uv), **Q-BS-2** (when and how the nightly gate, merge queue and cross-review go live), **Q-BS-3** (whether the engine's Nov 25 gate date moves with the hello-world date), **Q-BS-4** (which planning documents may be published in this public repo).

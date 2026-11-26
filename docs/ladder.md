# The integration ladder

Code built in separate sessions is not code that runs on the owner's machines, under the fleet's conventions. Each seam gets its own rung, and each rung has checks that print green or red. `kit doctor` runs them.

Three rules, from the handover:

1. **A check gates only after it has been shown red on a deliberately broken setup and green on a working one.** `kit doctor --self-test` runs every such proof, and CI runs it on every pull request. `doctor.py` refuses to load a check that has no proof.
2. **Two failed attempts at a check and work stops.** The conductor writes the owner one paragraph: what it tried, what it thinks is wrong, and whether the check itself may be wrong.
3. **A rung that is not climbed never prints green.** Rungs 3 to 10 depend on the owner's machines and fleet tooling. This repo's first session could not see those, so those rungs have a planned check and a planned break below, and no code. Proving each check on the real setup is the first step of its rung.

## What is proven today (rungs 0 to 2)

Every row is exercised by `kit doctor --self-test`: 19 checks, 83 planted breaks.

| Rung | Check | Green means | Planted breaks it goes red on |
| --- | --- | --- | --- |
| 0 | `register_covers_packages` | Every package and app has a row in the risk register | An unaudited package appears; the register is deleted |
| 1 | `lock_fresh` | `uv.lock` matches the pyproject files | A dependency is added without re-locking |
| 1 | `workspace_wired` | Every package with a pyproject is a workspace member, and every member exists | A package is added but never wired (so CI would never test it); a member is deleted |
| 1 | `ports_agree` | Code defaults match `contracts/ports.yaml` and no two services share a port | The engine returns to 8765; the registry repeats a port; the console looks for the engine elsewhere |
| 1 | `runners_hosted` | Every workflow job runs on a GitHub-hosted runner and none uses `pull_request_target` | A self-hosted label; a runner hidden behind an expression; `pull_request_target` |
| 1 | `required_checks_exist` | Every status the ruleset requires is produced by a workflow job | The aggregate job is renamed; the ruleset requires `cross-review`, which nothing emits |
| 1 | `no_forbidden_files` | No weights, holdout seed, env file or generated data anywhere in the tree (the path rules of `kit privacy scan`, one shared list) | Each of those four is added; MLX weights; a non-ASCII path; run output outside `data/` |
| 1 | `privacy_clean` | `kit privacy scan` is clean: every rule on every file git would publish, binaries included; exceptions only from `kit/privacy-allow.yaml` | A key in a new directory; a key inside a binary; a holdout case outside `data/`; a home path in a doc; an exception with no reason; a stale exception; an exception for every file; the allowlist deleted |
| 1 | `vendored_verbatim` | Fork C's vendored files match their checksums | A file is edited; a file is removed |
| 1 | `ci_runs_locally` | `kit check` can run every pull-request workflow as GitHub does: each job in its own clean checkout, aggregates evaluated, nothing it cannot reproduce | A step reads a secret; a runner-only path; a service container; a reusable workflow; a step `if:`; a matrix; `continue-on-error`; an aggregate that stops checking its needs |
| 1 | `lint_policy_covers` | Every tracked `.py` file is under a lint tier in `kit/lint-policy.json` (full, ratchet or exempt) | New Python outside every tier; a tier names a missing tree; a tree in two tiers; a negative floor; the policy deleted |
| 1 | `hooks_runnable` | Every pre-commit hook is local and its command exists | The pre-commit file as founded (remote ruff, `kit privacy scan`, a pnpm UI); an unknown kit command; an unknown flag; a hook on a path that does not exist; the file deleted |
| 1 | `gates_wellformed` | `docs/gates.yaml` parses and every gate names real issue numbers | The file deleted; a gate with no blockers; a blocker that is not a number; two gates with one id; a waiver for a non-blocker; a gate blocking on its own milestone |
| 2 | `python_pin` | The running CPython equals `.python-version` exactly | A different patch release |
| 2 | `sync_frozen` | The environment matches `uv.lock` | Never synced; the lock changed after the last sync |
| 2 | `hello_world_smoke` | Taco night smoke run returns `hello_world_result@1`, status `pass` or `placement_only`, no failed episodes, no zero-tolerance breach | Cases missing; the agent swaps a locked food; every episode ends in an unacceptable cart |
| 2 | `console_on_fixtures` | The console starts on a free port and serves its health and stage pages from fixtures | Engine fixtures never built; the stage page is missing |
| 2 | `ports_free` | The four default ports are free on this host | Another process holds one |
| before 3 | `review_recorded` | The register links the review itself (`Review: <PR review URL>`), and doctor reads it from GitHub: submitted, of the recorded commit, on the recorded date, naming the recorded reviewer, on this repo, and the commit an ancestor of HEAD. Offline or without git it reads not recorded. Rung 3 may not start without it, whatever the gates say. It cannot prove the reviewer was a different model (one shared GitHub identity, Q-I-1) | Pending; no section; a placeholder reviewer; an impossible or future date; no commit; no review link; a commit, date, reviewer or repo that is not the review's |

**Limits of these proofs.** The rung-2 checks were proven in a Linux container on CPython 3.12.3 and on GitHub's Ubuntu runners. Green there says the repo is coherent; it says nothing about macOS, either host until `kit doctor` runs there. `hello_world_smoke` proves the stand-in agent, not the real one (risk R-01). `console_on_fixtures` checks two pages, not a browser.

## What is planned and not proven (rungs 3 to 10)

Each row becomes code in `kit/src/kit_cli/doctor.py`, with its proof, in the rung's issue. Until then `kit doctor` prints `NOT CLIMBED` for the rung.

| Rung | What it proves | Planned check | Planned break (must go red) | Needs from the owner |
| --- | --- | --- | --- | --- |
| 3 fleet conventions | A well-behaved fleet repo | The fleet's agent-install script has run for this repo; merge settings are rebase-only; the ruleset on `main` equals `.github/rulesets/main.json`; the git guardrail hook is the one Git actually invokes | A squash-merge setting; a ruleset with one required check removed; a hook that is present but unused | Approve the ruleset (2 min) |
| 4 fleet member | It shows up where the owner looks | The fleet's onboarding reconcile reports no drift for this repo and this checkout; a fresh daily report names it with no drift warning | One fleet surface entry removed in a scratch worktree; a same-name entry pointing at the wrong checkout | Merge three small PRs (10 min) |
| 5 runs on the second host | Two hosts, same pins | Rung 2's checks on the second host; the two hosts' `kit doctor --json` agree on Python, uv and lock hash; the sync loop advances both to a fresh commit, fast-forward only | A different Python patch on one host; a local commit on `main` that blocks fast-forward; the sync loop disabled on one host | Python 3.12.16 and uv if missing (10 min) |
| 6 handoff service | Safe handoffs | One round trip through the fleet's handoff service with a receipt bound to the current task; the queued asks posted and addressed | A message from an unenrolled key is refused; a valid receipt for another task is refused | Enroll one device key (10 min) |
| 7 fleet proof job | Jobs run safely across devices | A deterministic `proof` kind, no model and no data, admitted, completed and verified separately on each named worker, following the fleet's existing job recipe | An undeclared kind is refused; a tampered output fails verification; one worker absent | Declare and admit (15 min) |
| 8 first real job | Real work through the fleet | `adapter-eval` at tier `none` through the job runner; the receipt binds tier, bundle, job and output hash, and is in the trace | A receipt that does not match the output; a valid receipt for a different bundle | Admit one job (5 min) |
| 9 local models | Model tiers work | The serving bake-off picks a server; the K01 baseline runs through the job runner on the same server version and model digest; JSON Schema decoding fails closed | A malformed reply is rejected, not repaired; valid JSON with a wrong field type is rejected | Download weights per host |
| 10 demo bundle | Dec 2 is safe | On the stage host with the wide-area network off and its hotspot on: cold start under 2 minutes, a phone ballot round trip, each fallback recording decodes and plays, warm-up `--strict` green | A present but unplayable recording; a beat labeled live with its backend stopped; a beat still on fixtures in `--strict` | Rehearsal |

## Gates

`docs/gates.yaml` lists, for each milestone, the issues that must be done first. It is the single source; an issue's "Depends on" line may repeat it in words. `kit gates` reads the issues' live state from GitHub (two requests, cached ten minutes) and fails closed: GitHub unreachable, or an issue it cannot find, reads `UNKNOWN`, never `CLEAR`. An issue closed as "not planned" counts only when the owner lists it under `waived`.

- `kind: start`: `kit doctor` never says "climb" the rung, and `kit doctor --rung N` exits 1, until the gate is clear.
- `kind: close`: the rung (or issue) may be worked, but its rung never reads `GREEN`, and `kit gates --milestone N` exits 1, until the gate is clear. Run it before closing a gated issue.

## Reading `kit doctor`

```
rung 0  audit                    GREEN  1/1 checks
rung 1  repo and CI              GREEN  12/12 checks, 2 unproven (pass a known broken setup, #38): ports_agree, runners_hosted
rung 2  runs on this host        RED    python_pin: running CPython 3.12.3, the pin is 3.12.16
review  independent review       RED    no independent review recorded in the risk register ...
gate    rung-3 (#3)              BLOCKED may not start: #1 unmerged, #38 open, #41 open
gate    beat-1-live (#20)        BLOCKED may not close: #12 open, #18 open, #36 open, #39 open
gate    rung-10 (#10)            BLOCKED may not close: #27 open, #36 open, #39 open, #40 open
date    2026-11-25               RED     1 d ago: the engine's stage 0 stops accepting `placement_only` ... Still red: ...
date    2026-11-28               in 2 d  the parity_floors waiver in bundles/gate-config.yaml has expired ...
next    fix rung 2 (runs on this host)
```

One line per rung, the first red check named in plain words, then one line per gate, then the dates on which something turns red without a commit, then the one next step. `--rung N` checks rungs 0 to N (default 2), `--json` prints the same for a program, `--self-test` runs the proofs.

**Unproven.** A check that is known to pass some broken setup carries a `hole` in `doctor.py`, naming the setup and its issue. Its rung line says how many of its checks are unproven and which, and `--self-test` ends with the same list, so `GREEN` never hides a known gap. Closing a hole means planting the setup as a break, watching the self-test go red, tightening the check, and deleting the `hole`. `--json` carries it per check as `unproven`.

**Dates.** Doctor reads each date from the gate's own source (the engine's `PASS_REQUIRED_FROM`, each waiver's `until` in `bundles/gate-config.yaml`) and asks the gate itself, with the inputs the real command is given: the hello-world result in `KIT_HELLO_WORLD_RESULT` for stage 0, and the reports in `KIT_GATE_CANDIDATE`, `KIT_GATE_BASELINE` and `KIT_GATE_DIFF` for `kit gate`. Without them it judges today's reference stand-in and says so on the line; that is not the setup's verdict. A gate is asked today and, before its date, as of its date. Already red today: the line reads `RED` now, not a countdown. From the date on it reads `RED` with the gate's own reason and stays until the gate passes; a gate that cannot be asked is red.

**Exit code.** 0 means every rung up to `--rung` is green and its gate clear. The review, gate and date lines are about what comes after and do not change it: CI runs `kit doctor --rung 2`, and a date must not turn CI red with no commit to blame (R-02). `kit doctor --rung 3` exits 1 while any of them stands in rung 3's way.

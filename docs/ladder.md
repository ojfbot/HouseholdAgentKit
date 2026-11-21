# The integration ladder

Code built in separate sessions is not code that runs on the owner's machines, under the fleet's conventions. Each seam gets its own rung, and each rung has checks that print green or red. `kit doctor` runs them.

Three rules, from the handover:

1. **A check gates only after it has been shown red on a deliberately broken setup and green on a working one.** `kit doctor --self-test` runs every such proof, and CI runs it on every pull request. `doctor.py` refuses to load a check that has no proof.
2. **Two failed attempts at a check and work stops.** The conductor writes the owner one paragraph: what it tried, what it thinks is wrong, and whether the check itself may be wrong.
3. **A rung that is not climbed never prints green.** Rungs 3 to 10 depend on the owner's machines and fleet tooling. This repo's first session could not see those, so those rungs have a planned check and a planned break below, and no code. Proving each check on the real setup is the first step of its rung.

## What is proven today (rungs 0 to 2)

Every row is exercised by `kit doctor --self-test`: 14 checks, 30 planted breaks.

| Rung | Check | Green means | Planted breaks it goes red on |
| --- | --- | --- | --- |
| 0 | `register_covers_packages` | Every package and app has a row in the risk register | An unaudited package appears; the register is deleted |
| 1 | `lock_fresh` | `uv.lock` matches the pyproject files | A dependency is added without re-locking |
| 1 | `workspace_wired` | Every package with a pyproject is a workspace member, and every member exists | A package is added but never wired (so CI would never test it); a member is deleted |
| 1 | `ports_agree` | Code defaults match `contracts/ports.yaml` and no two services share a port | The engine returns to 8765; the registry repeats a port; the console looks for the engine elsewhere |
| 1 | `runners_hosted` | Every workflow job runs on a GitHub-hosted runner and none uses `pull_request_target` | A self-hosted label; a runner hidden behind an expression; `pull_request_target` |
| 1 | `required_checks_exist` | Every status the ruleset requires is produced by a workflow job | The aggregate job is renamed; the ruleset requires `cross-review`, which nothing emits |
| 1 | `no_forbidden_files` | No weights, holdout seed, env file or generated data in the tree | Each of those four is added |
| 1 | `vendored_verbatim` | Fork C's vendored files match their checksums | A file is edited; a file is removed |
| 2 | `python_pin` | The running CPython equals `.python-version` exactly | A different patch release |
| 2 | `sync_frozen` | The environment matches `uv.lock` | Never synced; the lock changed after the last sync |
| 2 | `hello_world_smoke` | Taco night smoke run returns `hello_world_result@1`, status `pass` or `placement_only`, no failed episodes, no zero-tolerance breach | Cases missing; the agent swaps a locked food; every episode ends in an unacceptable cart |
| 2 | `console_on_fixtures` | The console starts on a free port and serves its health and stage pages from fixtures | Engine fixtures never built; the stage page is missing |
| 2 | `ports_free` | The four default ports are free on this host | Another process holds one |
| before 3 | `review_recorded` | The risk register records an independent review | Status is pending; the section is missing |

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

## Reading `kit doctor`

```
rung 0  audit                    GREEN  1/1 checks
rung 1  repo and CI              GREEN  7/7 checks
rung 2  runs on this host        RED    python_pin: running CPython 3.12.3, the pin is 3.12.16
review  independent review       RED    no independent review recorded in the risk register ...
date    2026-11-25               in 4 d  the engine's stage 0 stops accepting `placement_only` ...
next    fix rung 2 (runs on this host)
```

One line per rung, the first red check named in plain words, then the dates on which something turns red without a commit, then the one next step. `--rung N` checks rungs 0 to N (default 2), `--json` prints the same for a program, `--self-test` runs the proofs.

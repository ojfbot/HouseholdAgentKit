# Integration risk register

Rung 0 of the integration ladder ([`docs/ladder.md`](ladder.md)). Written Nov 20 2026 by the bootstrap session, before any code moved into this repo. It records what each piece of code assumes, where the pieces contradict each other, and which contracts nobody has acknowledged.

**How it was made.** Each fork's code was first run alone, exactly as it was written, on CPython 3.12.3 in a Linux container, then scanned for imports, environment variables, ports, paths, network calls and dates. Every finding below was observed in a run or read in a named file. The founding PR's CI then ran the combined tree on GitHub's runners with CPython 3.12.16. Nothing here was checked on the stage host, the build host, macOS or the fleet; where a claim depends on those, the row says "unverified".

**Decisions in force.** `shared/decisions-batch-1.md` is still pending for all six rounds, so this repo was founded on the recommended defaults in the planning project (R1.1 A, R1.2 A, R1.3 A, R1.4 A, R1.6 A Apache-2.0, R1.7 A, R2.x A, R3.1 A, R3.3 B, R4.x A with the pre-read conditions, R5.x A, R6.x A). R1.5 is answered: the repo is `ojfbot/HouseholdAgentKit`.

## Top three risks

1. **Taco night is green only against a stand-in, and two dates turn things red without any code change.** Today's hello world runs IQ's reference hook over IQ's dev set and reports `placement_only`. The real components on its build list (intent parser, need list, solver, slots core, consent, poll bus, ShoppingPort, telemetry, the twin's core half) do not exist as code yet. From Nov 25 the engine's stage 0 aborts unless hello world is `pass` from a `full` run, and from Nov 28 the nightly gate goes red when the parity waiver lapses (R-01, R-02, R-03).
2. **Several checks pass when they should not.** `kit hello-world --mode smoke` exits 0 when every episode fails; the staged determinism check passes while the artifact's bytes change; `uv lock --check` is a no-op under `UV_FROZEN=1`; the staged ruleset requires a status nothing emits; and the staged nightly gate runs fork pull-request code with a write token (R-04 to R-08).
3. **Nothing has run on the Macs or the fleet.** Rungs 3 to 10 have no proven check. The pinned CPython 3.12.16 could not be downloaded by this session's uv, the console binds to every interface by default, and contracts freeze Nov 22 with batch 1 unanswered and two different synthetic taco worlds in the tree (R-09 to R-13).

## Per-package assumptions

Paths are the target paths in this repo. "Tests alone" is the result of running the fork's own tests in isolation, as shipped.

| Package | Came from | Python and dependencies | Paths it assumes | Env vars | Ports | Fixtures and generated files | Network calls | Tests alone | Convention gaps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `packages/contracts` | `fork-i` | 3.12, stdlib only | none | none | none | none | none | pass (with fork-i) | Had no `pyproject.toml`; a draft mirror of F's contracts, not the contracts themselves |
| `packages/mock-gateway` | `fork-i` | 3.12; `kit_contracts` | none | none | none | Catalog is code, all synthetic | none | pass | No `pyproject.toml`; only the catalog-and-slots half of the twin, the core half (consent, tokens, mock Sparky) has no owner's code |
| `packages/verifier` | `fork-i` | 3.12; `kit_contracts` | none | none | none | none | none | pass; 508/508 mutants | No `pyproject.toml` |
| `packages/eval-harness` | `fork-i` | 3.12; `pyyaml`, `kit_contracts`, `kit_verifier`, `mock_gateway` | `hello_world.py` and `conformance.py` find the repo by `parents[4]`: they work only from a source checkout with an editable install, not from a built wheel | `KIT_CORE_IMPL` | none | Reads `data/seeds/cases/*.yaml` | none | pass; 5 skipped (`requires_core`) | No `pyproject.toml` |
| `packages/kit-gate` | `fork-i` | 3.12; `pyyaml`, `kit_eval` | Tests find the repo by `parents[3]` | none | none | `bundles/gate-config.yaml` | none | pass | No `pyproject.toml`; gate behaviour depends on today's date (R-02) |
| `kit` | `fork-i` | 3.12; all of the above | `kit mutate` puts `tests/` on `sys.path` and imports the test package `mutation` | `KIT_MUTATION_REPORT`, `KIT_CT_IMPL` (in `tests/`) | none | none | none | 117 pass, 5 skipped | No `pyproject.toml` and no `kit` entry point; `kit privacy scan`, `kit contracts validate` and `kit setup` are named in the plans and do not exist |
| `packages/discovery-engine` | `fork-g` | `>=3.12`; `pyyaml`; setuptools build | `PKG_ROOT = parents[2]` reads `prototypes/` and `fixtures/` from the checkout | `DE_AS_OF` (pins "today") | `serve` defaulted to **8765** | Needs six Fork C files in `prototypes/fork_c/` that were deliberately not uploaded with the package | `e04_cards.py` posts to a local teacher at `/v1/chat/completions`; refuses non-local hosts; its allow-list names `yuri` and `yojimbo` | **fails as shipped** (`FileNotFoundError: prototypes/fork_c/lattice-v1.yaml`); 41 pass once the six files are copied in | Does not meet IQ's lint standard (187 findings, 28 files unformatted); many statements per line; its stage-0 gate depends on today's date (R-02) |
| `packages/card-writer` | `fork-h` | 3.12, stdlib only | Flat layout (`card_writer/`, no `src/`) | none | Posts to `model_url` (default `http://127.0.0.1:8080`) when a model is configured | none | Model seam only; falls back to templates | pass (14) | No `pyproject.toml`; lint gap (shared with the console: 31 findings) |
| `apps/demo-console` | `fork-h` | 3.12, stdlib; optional `segno` (QR), `mlx-whisper` or `whisper.cpp` plus `ffmpeg` (voice), `puppeteer-core` and Chrome (e2e) | Adds `../../packages/card-writer` and `server/` to `sys.path`; writes `logs/` and reads `console.json` in its own folder | `WHISPER_CPP_BIN`, `WHISPER_CPP_MODEL`, `MLX_WHISPER_MODEL` | Console **8765** bound to `0.0.0.0`; expects engine 8790, poll bus 8791, model 8080 | `fixtures/engine/readout.*.json` and `deltas.json` are generated by `build_engine_fixtures.py` and not committed | Calls the engine, the poll bus and the model over loopback HTTP; `warmup.py` checks them | **14 errors as shipped** (`deltas.json` missing); 38 pass after running the fixture builder | Not a package; module names `host`, `contracts`, `warmup` are generic; no Node manifest although the plan calls for pnpm; `segno` is not in the lock, so the QR code falls back to a text URL |
| `packages/shopping-port` | `fork-c/semantic` | 3.12, stdlib only | Flat modules that import each other by bare name (`semantic_render`, `taco_twin`); tests import a sibling test module | none | none | Its own synthetic taco world in `taco_twin.py` | none | pass (28) | Reference code with no declared target path; placed under `reference/`, not packaged; lint gap (32 findings); a second taco world (R-12) |
| `packages/discovery-engine/prototypes` | `fork-c`, `fork-e`, `fork-f` scripts | 3.12; `pyyaml` | Every script reads and **writes** files in its current directory | none | none | `decompose_v2.py` rewrites its own committed output; `homework_v2.py` writes `homework_v2.json` | none | `homework_v2.py` prints ALL PASS; `decompose_v2.py` runs | Scripts, not modules; excluded from lint and from test collection |

**Licenses.** All code here is original to the project and published under Apache-2.0 (R1.6 default). Runtime dependency: PyYAML (MIT). Build and dev: setuptools, pytest, ruff, pyright (MIT). Optional and not installed: segno (BSD-3), mlx-whisper (MIT), puppeteer-core (Apache-2.0); `ffmpeg` is called as an external program and is not distributed. No third-party dataset is in the tree: the catalog, prices and personas are synthetic and labeled. `packages/discovery-engine/prototypes/fork_e/statements.yaml` holds paraphrases and short quotes from public sources with their URLs. No model weights are in the repo, and the model licenses D recorded apply only once a host downloads them.

**Secrets and personal data.** A scan of the whole snapshot found no key-shaped strings, e-mail addresses or phone numbers, and the holdout seed is not in the tree. The first scan missed host names, home-relative paths and references to private planning documents; a second pass removed or reworded them (see R-20). Host names `yuri` and `yojimbo` appear in `e04_cards.py` and in docs.

## Risks, contradictions and proposed resolutions

"Done here" means the founding PR already applies the resolution. Everything else is an issue in the backlog or a question in the decision queue.

| ID | Finding (how it was observed) | Why it matters | Proposed resolution | Status |
| --- | --- | --- | --- | --- |
| R-01 | Hello world passes only against `iq-reference-tier-none` on `iq-dev@0` and reports `placement_only`; 5 conformance checks are skipped until a twin core registers; four zero-tolerance metrics are listed as not measured. The components on A's hello-world build list beyond K03, K11, K17 (half), K20 and K27 have no code in the snapshot. | The one live demo is the least-built thing. | Backlog puts the hello-world critical path first (twin core, ShoppingPort H3, solver, need list, consent, poll bus), each bound through `KIT_CT_IMPL` / `KIT_CORE_IMPL` so the existing suites become the check. | Open; issues filed |
| R-02 | `discovery_engine` stage 0 reads today's date: `placement_only` is accepted through Nov 24 and `pass` from a `full` run is required from Nov 25 (`pipeline.py`, tests pin `DE_AS_OF=2026-11-19`). `kit gate` reads today's date for waivers; the only waiver ends Nov 27. | The engine run and the nightly gate turn red on a date, with no commit to blame. | `kit doctor` prints both dates with a day count. Decide by Nov 23 whether stage 0's date moves with the hello-world date (queue Q-BS-3). | Doctor line done here; decision open |
| R-03 | The plans' "hello world live Nov 24, zero slack" predates the Nov 20 notice that makes taco night the one live beat. | Scope fell, the date did not move. | Backlog orders taco night first; engine and Care Profiles work is labeled backup. | Done in the backlog |
| R-04 | `kit hello-world --mode smoke` returns exit 0 whenever `status` is `pass` or `placement_only` and no zero-tolerance counter is set. With a hook that makes every episode unacceptable, `status` stays `placement_only` and the exit code stays 0 (reproduced with a planted fault). | The handover's rung-2 check ("`kit hello-world --mode smoke` passes") would pass on a broken agent. | Doctor's `hello_world_smoke` also requires an empty `failures` list and is proven red on that fault. The CLI's own exit code should follow; that is IQ's code and an issue. | Check done here; CLI fix is an issue |
| R-05 | Fork I's staged CI proves the decomposition "deterministic" by running it twice and comparing stdout. The script's output file changes byte-for-byte with `PYTHONHASHSEED` (key order), while its canonical content matches the committed file. | Any hash or pin computed over the raw file would differ between two honest runs. | CI now regenerates under two hash seeds and compares canonical JSON with the committed output (`scripts/check_decomposition_stable.py`). F should write sorted keys. | Check done here; F's fix is an issue |
| R-06 | `uv lock --check` exits 0 on a stale lock when `UV_FROZEN=1`, which the staged CI sets globally. Found when the doctor self-test showed the check staying green on a planted break. | A stale lock would pass CI. | Doctor's `lock_fresh` clears `UV_FROZEN` for that one command. | Done here |
| R-07 | The staged ruleset requires four statuses: `ci`, `security`, `privacy-guard`, `cross-review`. Nothing emits `cross-review` until its workflow is live, and the staged `ci` has jobs that cannot pass (R-14). | Running `scripts/apply-repo-settings.sh` as staged would block every merge, including the founding PR. | `.github/rulesets/main.json` here requires the three checks that exist; the four-check version stays in `docs/iq/staged-config/`. Doctor's `required_checks_exist` fails if the ruleset names a check no workflow produces. | In place, with a known hole (#38) |
| R-08 | The staged `nightly-gate.yml` checks out every open pull request head, rebases it and runs `uv sync` and `kit eval` on it in a job whose token can write statuses and issues. `merge-queue.yml` then merges with `contents: write`. `cross-review.yml` trusts review markers, while agents and the owner share one GitHub identity (Q-I-1). | On a public repo, a fork's pull request gets code execution next to a write token, and "these wait for the owner" is not enforced by anything. | The three workflows are **not active**: they are kept in `docs/iq/staged-workflows/` for review. Activate them only after Q-I-1 and Q-BS-2 are answered and the gate runs PR code without a write token. | Done here; decision open |
| R-09 | `uv python install 3.12.16` failed in the bootstrap session ("No download found"; uv 0.11.32 lists 3.12.13 as newest). python.org shows 3.12.16 was released Oct 25 2026 as a source-only security release. GitHub's Ubuntu runners did get it: the first CI run logged `Using CPython 3.12.16`. | The pin is installable on Linux with a current uv. Whether uv can fetch it for macOS on the Macs is unverified. | `.python-version` keeps 3.12.16; `requires-python` is `>=3.12,<3.13`. The local audit runs used 3.12.3; CI uses 3.12.16. Rung 2 is the test for the Macs (doctor `python_pin`). If uv there cannot get it, see queue Q-BS-1. | Green in CI; open for macOS |
| R-10 | The console binds `0.0.0.0:8765` by default so phones can join; phone links are single-use tokens. | On the library's network the stage controls are reachable by anyone on the same network. | Keep for the demo; warm-up `--strict` should confirm the HUD and control routes refuse non-loopback callers. Not verified in this audit. | Issue |
| R-11 | Engine and console both defaulted to port 8765; the console already expected the engine on 8790. | Starting both on one host fails or, worse, the console talks to itself. | Engine default changed to 8790 (three lines); `contracts/ports.yaml` is the registry; doctor's `ports_agree` is proven red on the old value. | In place, with a known hole (#38) |
| R-12 | Two synthetic taco worlds: `mock_gateway/catalog.py` (IQ, integer cents, tax in basis points per store) and `packages/shopping-port/reference/taco_twin.py` (C, floats, `TAX = 0.02`). A's oracle fixes invariants ($24.10 and $27.40) for a third file, `fixtures/taco_hw@1.json`, that does not exist yet. | The push loop's tests and the hello-world evals can each be green on a different world. | One world: IQ's fixture `taco_hw@1.json` built to A's invariants; C's reference loop re-pointed at it. Contract change, so it waits for the owner. | Issue; needs ack |
| R-13 | Fork D's `eval-gates-v0.yaml` and `job-kinds-v0.yaml` are not valid YAML (parser errors at flow sequences and mapping values). IQ re-encoded the gate block by hand in `bundles/gate-config.yaml`. | The specs the Fleet job kinds are built from cannot be loaded by any program; the hand copy can drift from the spec. | CI parses every contract file and lists these two as known-broken; the list fails CI when a listed file starts parsing, so it cannot go stale. D fixes the two files in a `contract` PR. | Check done here; fix is an issue |
| R-14 | The staged `ci.yml` calls things that do not exist: `kit contracts validate`, `apps/console` with a pnpm lockfile, prototype scripts at paths nothing created, and `kit privacy scan` in `privacy-guard.yml`. | The staged CI could not go green. | The founding CI keeps the staged job names and replaces those steps: a parse check for contracts, the real prototype paths, a grep-based privacy guard, no UI job (the console has no build step). Each replacement is marked as a stand-in in the workflow. | Done here |
| R-15 | Only Fork I's code meets Fork I's lint and type settings. | One lint job over the whole tree would be red; reformatting other forks' code in the founding PR would bury the import diff. | Lint in two tiers: the full rule set on the trees that meet it, undefined-name-level checks on the rest. One issue brings G, H and C code up to standard. | Done here; issue filed |
| R-16 | Fork G's README quickstart (`run --seed 1 --out runs/run-1`) produces bank `5a971751223dd5af`. The bank G reported and its examples cite, `0c37e39e99be983d`, reproduces only with `--run-id run-1`. | "Same seed, same bank" is true, but the documented command gives a different bank from the one in the examples. | README command corrected to include `--run-id run-1`. | Done here |
| R-17 | Vendored Fork C files are "verbatim, not forked", but nothing enforced it. | An edit to a vendored file would make the parity tests compare the engine with itself. | `prototypes/fork_c/SHA256SUMS` plus doctor's `vendored_verbatim`. | In place, with a known hole (#38) |
| R-18 | The plans name the UI toolchain (Node 24.22.2, pnpm 9.15.4, a UI build) and the app `apps/console`; the code is `apps/demo-console`, plain ES modules, no build, no Node manifest. The headless-Chrome test needs `puppeteer-core`, which is declared nowhere. | The e2e run H reported cannot be repeated from the repo, and it is not in CI. | Keep the no-build console. Add a small Node manifest for the e2e test only, and run it on the host at rung 2 or 10. | Issue |
| R-19 | ADR numbers collide (F's 001 to 009, D's 001 to 005); D's ADRs exist only in an artifact, not as files. ADR-004 calls Agent Profiles "published"; E's sweeps say announced, not live. | R1.7 default is one series. | F's nine ADRs are imported under their own file names in `decisions/adr/`; renumbering and the wording fix are one `contract`-labeled issue for the owner's merge. | Issue |
| R-20 | No planning documents were imported as documents, though the original plan lists four of them. A content review of the founding PR then found planning detail that had come in inside code comments, fixtures, specs and prototype data: host names, a home-relative path, the owner's name and working hours, and references to private documents. | This repo is public, and publishing is not undoable. | A follow-up commit removed two unused planning scripts and the run-0 prototype folder, reworded the rest to generic terms (the owner, the stage host, the planning project), and made the engine's local-teacher host list configurable instead of built in. Earlier commits on the PR branch still show the old text; whether to rewrite that history is the owner's call. The privacy guard now also catches home-relative paths. | Scrubbed in the tree; history and Q-BS-4 open |
| R-21 | The repo was empty, so there was no branch to open a pull request against. | A founding PR needs a base. | One root commit on `main` with the license, the disclaimer and a short README; everything else is the founding PR. | Done here |

## Unacked contracts

Freeze is Sun Nov 22. Batch 1 is pending, so none of these has the owner's ack; forks have been building on the defaults. "Loose" means the code reads the contract through an accessor that accepts more than one shape.

| Contract | Owner | State | Who builds on it today |
| --- | --- | --- | --- |
| `org@2`, `stated_priorities@1` | E (owner C for org) | Proposed; R4.1 default accept | G (a subset), E's homework checks |
| `components@2`, `needs@1`, `adapters@1`, `Result@0` | F | Proposed; R4.1 and R4.4 default accept. Pre-read flag: K25 defaults to a frontier model, against D's terms ruling (Q-A-1) | G, I |
| `controls@2` | C | **No file exists**; G runs on E's priors as a fixture | G |
| `lattice@1`, `controls@1`, `components@1` | C | Superseded or accepted by default | G's parity tests |
| `member@1` / `lattice@2`, `semantic@1`, `push@1` | C | Proposed Nov 19 evening, after batch 1 was written; in no decision batch | `packages/shopping-port/reference` |
| Mandate v1 (`standing` block) | F | Loose. Pre-read flag: its limit vocabulary differs from the published guardrail | I (`kit_contracts.loose`) |
| Case v1 | D and F | Loose: defined twice with different fields; A accepted the merged form | I, A's cases |
| Bundle manifest v0, Kit job kinds v0, Eval report v1, eval gates v0 | D | Proposed; R4.2 default accept. Two of the files do not parse (R-13) | I (`kit gate`, `kit bundle`) |
| Telemetry v1, Poll@1, Sparky brief v1 | A | Telemetry and Poll proposed, brief final; B's ack of the telemetry merge is outstanding | H (Poll@1), I |
| `hw-taco@1`, `hello_world_result@1` | A | Draft, freezes Nov 21; IQ's fixture and independent enumerator are owed | I, G (stage 0), H (tier chips) |
| `Card@0` plus H's additive fields; label vocabulary (`synthetic`, `public:`, `observed:`, `score:`, `weight:`, `derived:`) | F | H's and G's additions asked Nov 19, no reply recorded | H, G |
| `Readout@0`, `ControlDelta@0`, `bank@0`, `partner_fit@0`, `partner_stake@0`, `sizing-topdown@0` | G drafts for F and C | Drafts; no reply recorded | G, H (through E16) |
| `gate-record/0`, `gate-config/0`, `conformance-report/0`, `kit-review v0`, `CatalogSlotsPort` | I | Open for comment; no reply recorded | I |
| Household v1 additions: `visibility` (Q-C-1), `decision_state` (Q-CN-1) | A and B | Queued for the owner | none yet |
| ShoppingPort v1, Ledger@0, Trigger@0 | F | Proposed; no implementation in the snapshot | none yet |
| `ports@0` | bootstrap | New in the founding PR | engine, console, doctor |

## CI as staged vs CI as founded

| Staged by Fork I | Founded | Why |
| --- | --- | --- |
| `setup-uv` with `python-version: 3.12.16` | `setup-uv` reads `.python-version` | One pin in one file (R-09) |
| ruff, format and pyright over everything | Full rules on IQ's trees and `kit`; undefined-name-level on the rest | R-15 |
| pytest per fork | One pytest run over all four trees, plus the doctor proofs | The trees had never been run together; they pass together (229 tests plus the doctor's) |
| `kit contracts validate contracts/` | Parse check with a known-broken list | The command does not exist (R-13, R-14) |
| stdout comparison of two decomposition runs | Canonical JSON against the committed output, two hash seeds | R-05 |
| `ui` job (pnpm build of `apps/console`) | Removed | Nothing to build (R-18) |
| `kit privacy scan` | Grep-based guard for forbidden files, key shapes, addresses and home paths | The command does not exist; porting the fleet's existing guard would mean reading another repo |
| gitleaks action, pnpm audit | `pip-audit` only | Secret scanning is an owner setting; there is no Node manifest |
| `nightly-gate`, `merge-queue`, `cross-review` | Not active | R-08 |
| (none) | `doctor` job: `kit doctor --self-test` and `kit doctor --rung 2` | Every ladder check is proven before it gates |

## What the doctor self-test caught in its own checks

Three checks written for this ladder were wrong on the first attempt, and the self-test showed each one:

- `lock_fresh` stayed green on a stale lock (R-06).
- `hello_world_smoke` was red on a working setup, because it compared `result_version` with the contract's display name `HelloWorldResult@1`; the wire value is `hello_world_result@1`.
- `register_covers_packages` was red until this register had a row for every package, which is its purpose.

## Independent review
- Status: findings recorded; fixes open (#38). `kit doctor` keeps this line red, and rung 3 does not start, until #38 is closed and this line reads `recorded`.
- Reviewer: OpenAI Codex, independent of the model that wrote the checks
- Date: 2026-11-20
- Reviewed: PR #1 as first pushed; the full review is the review comment on that PR
- Ran on: macOS with CPython 3.12.16. Frozen sync, fixture build, the doctor self-test (14 checks, 30 breaks) and the test run (235 passed, 5 skipped) all passed there. This is the first macOS result; it does not replace rung 2 on the stage host.

**What it found.** 28 items. None disputes a result in this register; several show that a safeguard listed above as done is narrower than its row claimed.

| Group | Findings | Where it goes |
| --- | --- | --- |
| Product seams that break today | The console exits at startup on a live engine readout (wire shape differs from the fixtures) | #35 |
| | Warm-up `--strict` passes a broken show; beats report live while running on stubs | #36 |
| | A mixed-shape mandate drops the spending cap in the loose accessor | #37 |
| | Stage and presenter routes have no client boundary (R-10 was written as "not verified"; it is now confirmed absent) | #27 |
| | The two taco worlds are never compared, nor is the conversion to the poll's decimal strings | #11 |
| Doctor checks that stay green on a broken setup | 15 setups across `hello_world_smoke`, the date lines, `console_on_fixtures`, `review_recorded`, `required_checks_exist`, `ports_agree`, `ports_free`, `lock_fresh`, `sync_frozen`, `vendored_verbatim`, `no_forbidden_files`, `runners_hosted`, `workspace_wired`, `register_covers_packages`, `python_pin` | #38, one planted break each |
| Planned checks for rungs 3 to 10 | A second break to demand for each rung | Added to the table in `docs/ladder.md` |

**Corrections to rows above.** R-07, R-11 and R-17 say "Done here". Each safeguard exists, but the review built a setup that gets past it (#38), so read those three as "in place, with a known hole". R-09: CPython 3.12.16 also ran on one Mac where it was already installed; whether uv can fetch it on the stage host is still open. R-10: the shipped console has no boundary between phone and presenter routes.

**The reviewer's three closing lines.** Least-trusted check: `hello_world_smoke`, which passed with zero episodes. Seam to test first: the real taco-night hook through the poll decision, consent and the verified order, on the oracle's household. Register corrections: as listed above.

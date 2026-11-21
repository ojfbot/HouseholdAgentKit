# packages/discovery-engine

Fork C's Walmart Discovery Engine, built as software by Fork G (engine engineer, role EN). It is an independent, unofficial and **purely synthetic** proof of concept: every number is labeled `synthetic` or `public:<src>`.

Per ADR-008, the stochastic stages run overnight as Fork D's `engine-run` Fleet job. The deterministic stages run live on stage over the resulting versioned bank, in about 1 ms per flip, and every flip is a `ControlDelta@0` event.

## Quickstart (no models, no keys)

```bash
cd packages/discovery-engine
PYTHONPATH=src python3 -m discovery_engine run --seed 1 --run-id run-1 --out runs/run-1     # bank.json, labels.csv
PYTHONPATH=src python3 -m discovery_engine evals --out runs/run-1/eval-report.json
PYTHONPATH=src python3 -m discovery_engine serve --bank runs/run-1/bank.json   # http://127.0.0.1:8790 (the console owns 8765)
python3 -m pytest -q                                                           # 41 tests, about 15 s
```

## Stages

| ID | Stage | Where | Status (Nov 19) | Seam → fallback in use |
| --- | --- | --- | --- | --- |
| stage 0 | Hello-world gate (A's `HelloWorldResult@1`) | overnight | placement self-test always; `placement_only` accepted through Nov 24, `status: pass` from a `full` hook run required from Nov 25 | placement_only |
| E02 | Lattice sampler + coverage | overnight | done | none |
| E03 | Day-1 hypothesis, hash-frozen before E04 | overnight | done | frontier → **template** |
| E04 | Card generator + `needs[]` | overnight | done | local open-weight teacher (built, refuses non-local/frontier) → **template@1** |
| E05 | Dedupe into families (MinHash, fixed 0.45) | overnight | done | embeddings → **MinHash** |
| E06 | Value-ladder placer + org@2 cover | overnight | done | rules |
| E07 | Interviews | — | cut for Dec 2 | — |
| E08 | Evidence ladder | overnight | passthrough@0 (owner ED) | — |
| E09 | Two-way sizing + driver tree | overnight | done | none |
| E10 | Judge panel | overnight | aggregator + `judge-batch` spec done | 3 local judges → **J0** |
| E11 | Controls, lenses, clamps, ControlDelta@0 | **live** | done | none |
| E12 | Selection (C's diversity rule) + Pareto + 2×2 | **live** | done | none |
| E14 | Decomposition (F's rules, ported unchanged) | overnight + drill | done | rules |
| E15 | Depth drills | — | Fork C writes the top 3 by Nov 24 | — |
| E17 | LangGraph shell | — | last priority | — |
| E18 | Engine evals over 3 seeds | overnight | done (31 rows) | none |

## Parity, not a fork

- `prototypes/fork_c/` vendors Fork C's `bank.py`, `bank_v2.py`, `score_v2.py`, `rubric-v2.yaml`, `controls-v1.yaml` and `lattice-v1.yaml` verbatim.
- `tests/test_parity.py` runs C's own `score_v2.py`. It checks that the engine matches all 58 run-0 families (total, tier, value at stake) and all three controls@1 top-10s.
- E14 is F's `decompose_v2.py` logic, checked against F's published run-0 decomposition.

## Live API (for Fork H)

`GET /readout?profile=<id>` returns `Readout@0`. `POST /delta` returns `{event: ControlDelta@0, readout: Readout@0}`. `GET /family/<id>` returns the drill view: ladder, sizing driver tree, components and partner fit. `GET /log/verify` checks the delta hash chain. Field lists are in `docs/contracts-proposed.yaml`; both contracts are drafts awaiting Fork F.

## `engine-run` (Fork D)

`python -m discovery_engine.jobs.engine_run` follows job-kinds-v0's command contract:

- **Input:** `{job, outDir}` on stdin.
- **Output:** writes `<key>.<fence>.jsonl` and prints `{file, sha256}`.
- **Refusals:** temperature outside the fixed 0.7, credential-shaped fields, the holdout seed, unknown params, and any teacher that is not local or names a frontier model.

## Fixtures to swap when the real contracts land

- `fixtures/fork_e/controls-priors-v2.yaml`: replace with Fork C's `controls@2` (Sat Nov 21) and load it with `load_controls2`.
- `fixtures/controls2-partner.fixture.yaml`: three partner profiles; replace with Fork C's.
- `fixtures/fork_f/components-v2.min.yaml`: replace with the full `contracts/components-v2.yaml` at repo import.
- `fixtures/fork_e/in_house_cover.min.yaml`: replace with the full org@2 file (E01, owner ED).

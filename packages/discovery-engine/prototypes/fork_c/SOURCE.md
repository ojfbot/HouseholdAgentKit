# prototypes/fork_c — vendored, not forked

**Public-repo note:** three provenance strings in `bank.py` (`REFS` entries `access_atlas`, `arfid`, `baseline`) were reworded to remove references to private planning documents. No family, score or rule changed; the parity tests still pass. `SHA256SUMS` covers the files as committed here.

Verbatim copies of Fork C's run-0 files, read from the project on 2026-11-19. The engine imports `bank.py` and `bank_v2.py` as its seed bank, and `tests/test_parity.py` runs `score_v2.py` unchanged to prove parity.

| File here | Project source |
| --- | --- |
| `bank.py` | `fork-c/bank.py` |
| `bank_v2.py` | `fork-c/bank_v2.py` |
| `score_v2.py` | `fork-c/score_v2.py` |
| `rubric-v2.yaml` | `fork-c/rubric-v2.yaml` |
| `controls-v1.yaml` | `fork-c/controls-v1.yaml` |
| `lattice-v1.yaml` | `fork-c/lattice-v1.yaml` |

Until the repo exists, these copies are not re-uploaded under `fork-g/`, so `fork-c/` stays the single copy in the project. At repo import (punchlist block 2), copy the six files here unchanged. If Fork C changes one, re-copy it and rerun `pytest`; a parity failure means the engine must follow C, not the other way round.

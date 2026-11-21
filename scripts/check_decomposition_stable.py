"""Fork F's decomposition stage must regenerate its committed output.

Run in a scratch copy under two different hash seeds and compare canonical JSON (sorted keys) with the
committed file. The audit found the raw bytes depend on PYTHONHASHSEED (key order), so comparing stdout
or bytes of one run with another in the same process settings would pass while the artifact drifts.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "packages/discovery-engine/prototypes/fork_f"
OUT = "run-0-decomposition-v2.json"


def canon(p: Path) -> str:
    return hashlib.sha256(json.dumps(json.loads(p.read_text()), sort_keys=True).encode()).hexdigest()


want = canon(SRC / OUT)
for seed in ("1", "2"):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "fork_f"
        shutil.copytree(SRC, work)
        (work / OUT).unlink()
        subprocess.run([sys.executable, "decompose_v2.py"], cwd=work, check=True, capture_output=True, env={**os.environ, "PYTHONHASHSEED": seed})
        got = canon(work / OUT)
        if got != want:
            sys.exit(f"decomposition drifted from the committed output under PYTHONHASHSEED={seed}: {got[:12]} != {want[:12]}")
print(f"decomposition regenerates the committed output under two hash seeds ({want[:12]})")

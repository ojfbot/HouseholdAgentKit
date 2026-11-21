"""Every YAML and JSON file under the given folders parses. A stand-in until `kit contracts validate`
(schema validation, owner HP/ED) lands with contracts-v1; it catches a broken file, not a wrong one."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Fork D's two specs are not valid YAML today (audit finding R-12). They are listed so CI stays honest:
# a listed file that starts parsing must be removed from this list, and any other broken file fails.
KNOWN_BROKEN = {"contracts/factory/eval-gates-v0.yaml", "contracts/factory/job-kinds-v0.yaml"}

bad, n, healed = [], 0, []
for folder in sys.argv[1:]:
    for p in sorted(Path(folder).rglob("*")):
        if p.suffix in (".yaml", ".yml", ".json"):
            n += 1
            try:
                list(yaml.safe_load_all(p.read_text())) if p.suffix != ".json" else json.loads(p.read_text())
                if p.as_posix() in KNOWN_BROKEN:
                    healed.append(p.as_posix())
            except Exception as e:
                if p.as_posix() in KNOWN_BROKEN:
                    continue
                bad.append(f"{p}: {type(e).__name__}: {str(e)[:120]}")
print(f"{n} files parsed, {len(bad)} broken")
print("\n".join([*bad, *(f"{h}: parses now; remove it from KNOWN_BROKEN" for h in healed)]))
sys.exit(1 if bad or healed or not n else 0)

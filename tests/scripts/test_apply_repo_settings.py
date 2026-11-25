"""apply-repo-settings.sh compares the applied ruleset with main.json and exits non-zero on a mismatch (R-22, #41 C2).

The script runs against a stand-in `gh` on PATH, so the test never reaches GitHub. The stand-in answers the two
reads the script makes (the ruleset id, then the ruleset itself) and accepts every write.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "apply-repo-settings.sh"
RULESET = ROOT / ".github" / "rulesets" / "main.json"

FAKE_GH = """#!{python}
import os, sys
args = sys.argv[1:]
if not sys.stdin.isatty():
    sys.stdin.read()
if args[:2] == ["api", "repos/someone/thing/rulesets"] and "-q" in args:
    print("7")
elif args == ["api", "repos/someone/thing/rulesets/7"]:
    sys.stdout.write(open(os.environ["FAKE_LIVE_RULESET"]).read())
"""


def _ruleset(checks: list[str]) -> dict[str, object]:
    live = json.loads(RULESET.read_text())
    live["id"] = 7
    for rule in live["rules"]:
        if rule["type"] == "required_status_checks":
            rule["parameters"]["required_status_checks"] = [{"context": c, "integration_id": 15368} for c in checks]
    return live


def _run(tmp_path: Path, live: dict[str, object]) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH.format(python=sys.executable))
    gh.chmod(0o755)
    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps(live))
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_LIVE_RULESET": str(live_file)}
    return subprocess.run(["bash", str(SCRIPT), "someone/thing"], cwd=tmp_path, env=env, capture_output=True, text=True, check=False)


def test_green_when_the_applied_ruleset_requires_what_main_json_requires(tmp_path: Path) -> None:
    result = _run(tmp_path, _ruleset(["ci", "security", "privacy-guard"]))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cross-review" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("checks", "named"),
    [
        (["ci", "security"], "missing: privacy-guard"),
        (["ci", "security", "privacy-guard", "cross-review"], "extra: cross-review"),
        ([], "missing: ci privacy-guard security"),
    ],
    ids=["one-required-check-removed", "the-four-check-ruleset", "no-required-checks"],
)
def test_red_when_the_applied_ruleset_differs(tmp_path: Path, checks: list[str], named: str) -> None:
    result = _run(tmp_path, _ruleset(checks))
    assert result.returncode != 0, result.stdout
    assert named in result.stderr

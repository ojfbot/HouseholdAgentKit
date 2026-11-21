"""Root conftest for the fork-i tree (temporary until the uv workspace lands in the founding PR).

* Puts every `packages/*/src` and `kit/src` on sys.path so tests import without installs.
* Registers the capability and suite markers (move to [tool.pytest.ini_options] at founding).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
for src in [*sorted(ROOT.glob("packages/*/src")), ROOT / "kit" / "src", ROOT / "tests"]:
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

MARKERS = {
    "cap07": "CAP-07 agent-to-agent with Sparky (CT-07a..f)",
    "cap10": "CAP-10 pickup and delivery slots (CT-10a..d)",
    "cap43": "CAP-43 slot hold for an agent (CT-43a)",
    "cap02": "CAP-02 Agent Profiles (CT-02a..c)",
    "cap21": "CAP-21 care profile per person cared for (CT-21a..c)",
    "cap28": "CAP-28 org principal, two approvers (CT-28a)",
    "contract": "capability-tagged contract suite",
    "conformance": "K20 conformance suite",
    "mutation": "K03 verifier mutation suite",
    "redteam": "prompt-injection / red-team cases",
    "slow": "long-running suites (engine 3-seed eval); nightly only",
    "loose_contract": "depends on a block held loose until Decisions batch 1 (Case v1, Mandate.standing)",
    "requires_core": "needs HP's twin core half (consent gate, tokens, mock Sparky); skipped until it registers",
}


def pytest_configure(config):
    for name, doc in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {doc}")

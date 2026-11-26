"""Cases from the Codex review of #50: setups the six tightened checks read wrongly, in either direction."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
import yaml

from kit_cli import doctor

pytestmark = pytest.mark.doctor

AGGREGATE_STEP = {"run": "echo '${{ toJSON(needs) }}' | jq -e 'to_entries | all(.value.result == \"success\")'"}


def _repo(tmp_path: Path, required: list[str], jobs: dict) -> Path:
    (tmp_path / ".github/rulesets").mkdir(parents=True)
    (tmp_path / ".github/workflows").mkdir(parents=True)
    ruleset = {"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": c} for c in required]}}]}
    (tmp_path / ".github/rulesets/main.json").write_text(json.dumps(ruleset))
    (tmp_path / ".github/workflows/ci.yml").write_text(yaml.safe_dump({"name": "ci", "on": {"pull_request": None}, "jobs": jobs}))
    return tmp_path


def test_independently_required_jobs_need_not_wait_for_each_other(tmp_path: Path) -> None:
    """Finding 4: two jobs the ruleset requires already both gate the merge; asking each to need the other is a cycle."""
    root = _repo(tmp_path, ["lint", "tests"], {"lint": {"runs-on": "ubuntu-24.04"}, "tests": {"runs-on": "ubuntu-24.04"}})
    res = doctor.required_checks_exist(root)
    assert res.ok, res.detail


def test_a_job_no_required_check_covers_is_red(tmp_path: Path) -> None:
    root = _repo(tmp_path, ["lint"], {"lint": {"runs-on": "ubuntu-24.04"}, "tests": {"runs-on": "ubuntu-24.04"}})
    res = doctor.required_checks_exist(root)
    assert not res.ok and "tests" in res.detail


def test_a_required_job_that_needs_others_must_report_their_results(tmp_path: Path) -> None:
    """Finding 1: keeps its needs, but without `if: always()` and the results step it is skipped, not failed."""
    root = _repo(tmp_path, ["ci"], {"tests": {"runs-on": "ubuntu-24.04"}, "ci": {"needs": ["tests"], "runs-on": "ubuntu-24.04", "steps": [{"run": "true"}]}})
    res = doctor.required_checks_exist(root)
    assert not res.ok and "ci" in res.detail and "skipped" in res.detail


def test_a_proper_aggregate_is_green(tmp_path: Path) -> None:
    jobs = {"tests": {"runs-on": "ubuntu-24.04"}, "ci": {"if": "always()", "needs": ["tests"], "runs-on": "ubuntu-24.04", "steps": [AGGREGATE_STEP]}}
    res = doctor.required_checks_exist(_repo(tmp_path, ["ci"], jobs))
    assert res.ok, res.detail


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(not socket.has_ipv6, reason="no IPv6 on this host")
def test_an_ipv6_only_listener_does_not_make_an_ipv4_port_busy(tmp_path: Path) -> None:
    """Finding 3: every service here binds IPv4; an unrelated IPv6-only listener on the same number is no clash."""
    port = _free_port()
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts/ports.yaml").write_text(yaml.safe_dump({"ports": {"console": port}}))
    with socket.socket(socket.AF_INET6) as held:
        held.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        try:
            held.bind(("::", port))
        except OSError as e:
            pytest.skip(f"cannot hold an IPv6-only port here: {e}")
        held.listen()
        res = doctor.ports_free(tmp_path)
    assert res.ok, res.detail

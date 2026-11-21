"""Stage 0 (fork-a/hello-world-spec.md): placement_only through Nov 24; from Nov 25, status pass from a full run."""
import json

import pytest

from discovery_engine.pipeline import RunConfig, stage0
from discovery_engine.seedbank import load_seeds
from discovery_engine.stages.e06_ladder import load_cover


def _hook(tmp_path, **kw):
    res = {"result_version": "hello_world_result@1", "oracle_version": "hw-taco@1", "status": "pass", "mode": "full", "k": 5,
           "bundle_id": "b1", "highest_tier": 2, "zero_tolerance": {"locks_violated": 0, "unverified_numbers": 0}, "synthetic": True, **kw}
    p = tmp_path / "hw.json"; p.write_text(json.dumps(res)); return str(p)


def _gate(**cfg):
    return stage0(RunConfig(**cfg), load_seeds()[1], load_cover())


def test_placement_only_accepted_through_nov_24():
    assert _gate(as_of="2026-11-24")["status"] == "placement_only"


def test_from_nov_25_needs_a_full_pass(tmp_path):
    with pytest.raises(RuntimeError, match="needs status pass"):
        _gate(as_of="2026-11-25")
    with pytest.raises(RuntimeError):
        _gate(as_of="2026-11-25", hello_world_result=_hook(tmp_path, mode="smoke"))
    assert _gate(as_of="2026-11-25", hello_world_result=_hook(tmp_path))["status"] == "pass"


@pytest.mark.parametrize("status", ["fail", "not_run"])
def test_fail_aborts_any_day(tmp_path, status):
    with pytest.raises(RuntimeError):
        _gate(as_of="2026-11-20", hello_world_result=_hook(tmp_path, status=status))

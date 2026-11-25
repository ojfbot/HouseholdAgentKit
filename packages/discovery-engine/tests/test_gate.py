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


@pytest.mark.parametrize("version", ["hello_world_result@0", "HelloWorldResult@1", None])
def test_a_result_of_another_version_aborts_any_day(tmp_path, version):
    """#38 finding 4: stage 0 read fields from any JSON that said `status: pass`, whatever contract it followed."""
    with pytest.raises(RuntimeError, match="result_version"):
        _gate(as_of="2026-11-20", hello_world_result=_hook(tmp_path, result_version=version))


@pytest.mark.parametrize("breach", [{"locks_violated": 1}, {"unverified_numbers": 2}, {"orders_per_mandate_max": 2}])
def test_a_zero_tolerance_breach_aborts_even_when_the_status_says_pass(tmp_path, breach):
    """#38 finding 4: a full run with `status: pass` and a swapped locked item got through."""
    zero_tolerance = {"locks_violated": 0, "unverified_numbers": 0, "orders_per_mandate_max": 1, **breach}
    for as_of in ("2026-11-20", "2026-11-25"):
        with pytest.raises(RuntimeError, match="zero-tolerance"):
            _gate(as_of=as_of, hello_world_result=_hook(tmp_path, zero_tolerance=zero_tolerance))


def test_one_order_per_mandate_is_the_rule_not_a_breach(tmp_path):
    clean = {"locks_violated": 0, "unverified_numbers": 0, "orders_per_mandate_max": 1}
    assert _gate(as_of="2026-11-25", hello_world_result=_hook(tmp_path, zero_tolerance=clean))["status"] == "pass"

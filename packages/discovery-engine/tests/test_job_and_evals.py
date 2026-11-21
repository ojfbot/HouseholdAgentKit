"""engine-run command contract (job-kinds-v0) and the E18 report."""
import hashlib
import json
import subprocess
import sys

import pytest

from discovery_engine.jobs.engine_run import Refused, check_params
from discovery_engine.util import PKG_ROOT


def _job(**params):
    return {"key": "kit-eng-0001", "fence": 7, "params": {"seeds": [1], "cell_budget": 44, **params}}


def test_command_contract(tmp_path):
    req = {"job": _job(), "outDir": str(tmp_path)}
    p = subprocess.run([sys.executable, "-m", "discovery_engine.jobs.engine_run"], input=json.dumps(req), capture_output=True,
                       text=True, cwd=PKG_ROOT, env={"PYTHONPATH": str(PKG_ROOT / "src"), "PATH": "/usr/bin:/bin", "DE_AS_OF": "2026-11-19"})
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    f = tmp_path / out["file"]
    assert out["file"] == "kit-eng-0001.7.jsonl" and hashlib.sha256(f.read_bytes()).hexdigest() == out["sha256"]
    types = [json.loads(l)["type"] for l in f.read_text().splitlines()]
    assert types[0] == "header" and "family" in types and types[-1] == "checks"


@pytest.mark.parametrize("job", [
    _job(temperature=0.9),
    _job(api_key="x"),
    {**_job(), "payload": {"authorization": "Bearer x"}},
    _job(seeds=[42], holdout_commitment=hashlib.sha256(b"42").hexdigest()),
    _job(model_pins={"E04": {"endpoint": "https://api.anthropic.com", "model": {"repo": "q", "revision": "r", "sha256": "s"}}}),
    _job(surprise=1),
])
def test_refusals(job):
    with pytest.raises(Refused):
        check_params(job)


def test_refusal_exit_code(tmp_path):
    req = {"job": _job(temperature=1.2), "outDir": str(tmp_path)}
    p = subprocess.run([sys.executable, "-m", "discovery_engine.jobs.engine_run"], input=json.dumps(req), capture_output=True,
                       text=True, cwd=PKG_ROOT, env={"PYTHONPATH": str(PKG_ROOT / "src"), "PATH": "/usr/bin:/bin", "DE_AS_OF": "2026-11-19"})
    assert p.returncode == 3 and p.stderr.startswith("error REFUSED") and not list(tmp_path.iterdir())


@pytest.mark.slow
def test_eval_report_passes():
    from discovery_engine.evals import report
    rep = report((1, 2, 3))
    assert rep["pass"], rep["failed"]
    rows = {r["metric"]: r for r in rep["rows"]}
    assert rows["stability_top10_jaccard"]["value"] >= 0.6
    assert rows["recompute_s_p100"]["value"] < 1.0
    assert rows["unlabeled_numbers"]["value"] == 0

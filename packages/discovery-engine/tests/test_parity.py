"""Parity: the engine does not fork Fork C's or Fork F's logic.
C: run 0 replayed through the engine matches score_v2.py family by family (totals, tiers, VaS) and top-10 by top-10.
F: E14 reproduces decompose_v2.py's run-0 component sets (spot-checked against run-0-decomposition-v2.json).
"""
import json
import shutil
import subprocess
import sys

import pytest

from discovery_engine.live.engine import Bank, ControlEngine, rank, select
from discovery_engine.live.profiles import from_controls1
from discovery_engine.pipeline import replay_run0
from discovery_engine.stages.e14_decompose import decompose, family_view
from discovery_engine.util import PROTO_C


@pytest.fixture(scope="module")
def c_bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("forkc")
    for f in ("bank.py", "bank_v2.py", "score_v2.py", "rubric-v2.yaml", "controls-v1.yaml"):
        shutil.copy(PROTO_C / f, d / f)
    (d / "run-0").mkdir()
    subprocess.run([sys.executable, "score_v2.py"], cwd=d, check=True, capture_output=True)
    return json.loads((d / "run-0" / "problem-bank.json").read_text())


@pytest.fixture(scope="module")
def replay():
    return replay_run0()


def test_every_family_matches_score_v2(c_bank, replay):
    ours = {f["family_id"]: f for f in replay["families"]}
    assert len(ours) == len(c_bank["families"]) == 58
    for cf in c_bank["families"]:
        f = ours[cf["id"]]
        assert f["scores"]["in_house"]["value"] == cf["total"], cf["id"]
        assert f["tier"] == cf["value_tier"], cf["id"]
        assert f["sizing"]["usd_per_year"]["value"] == cf["value_at_stake"]["usd_per_year"], cf["id"]


def test_top10_matches_controls1(c_bank, replay):
    profs, params = from_controls1()
    eng = ControlEngine(Bank(replay), profs, params)
    for pid, p in profs.items():
        expected = [f["id"] for f in sorted((f for f in c_bank["families"] if f["top10"][pid]), key=lambda f: f["top10"][pid])]
        got = [r["family_id"] for r in select(rank(eng.bank, p, params))]
        assert got == expected, pid


def test_published_run0_top3():   # the numbers C published in fork-c/design.md
    profs, params = from_controls1()
    eng = ControlEngine(Bank(replay_run0()), profs, params)
    top = [r["family_id"] for r in select(rank(eng.bank, profs["default"], params))]
    assert top[:3] == ["PF-39", "PF-44", "PF-48"]


F_RUN0 = {  # fork-f/run-0-decomposition-v2.json
    "PF-30": (["K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K10", "K11", "K12", "K24"], ["K22"],
              ["CAP-07", "CAP-10", "CAP-21", "CAP-24", "CAP-28"]),
    "PF-40": (["K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K09", "K10", "K11", "K12", "K21", "K24"], ["K22"], None),
}


@pytest.mark.parametrize("fid", sorted(F_RUN0))
def test_e14_matches_fork_f(replay, fid):
    f = {x["family_id"]: x for x in replay["families"]}[fid]
    d = decompose(family_view({**f, "value_tier": f["tier"]}))
    comps, enh, adapters = F_RUN0[fid]
    assert d["components"] == comps and d["enhance"] == enh
    if adapters:
        assert d["adapters"] == adapters

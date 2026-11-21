"""Stage oracles from components@2 (E02, E04, E05, E06, E08, E09, E10)."""
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from discovery_engine.seedbank import seed_by_id
from discovery_engine.stages import e02_sampler, e04_cards, e05_dedupe, e06_ladder, e08_evidence, e09_sizing, e10_judges
from discovery_engine.text import rephrase
from discovery_engine.util import PROTO_C, find_unlabeled, load_yaml

LAT = load_yaml(PROTO_C / "lattice-v1.yaml")
AX = e02_sampler.axes_from_lattice(LAT)


def test_e02_same_seed_same_cells_and_quotas():
    a, b = e02_sampler.sample(LAT, 5, 72), e02_sampler.sample(LAT, 5, 72)
    assert a["cells_hash"] == b["cells_hash"]
    assert e02_sampler.sample(LAT, 6, 72)["cells_hash"] != a["cells_hash"]
    cov = a["coverage"]
    assert not cov["empty_actor_types"]
    assert min(cov["by_actor_type"].values()) >= LAT["sampling"]["quota"]["min_cells_per_actor_type"]
    assert min(cov["by_quadrant"].values()) >= LAT["sampling"]["quota"]["min_cells_per_quadrant"]
    for c in a["cells"]:
        assert not (c["actor_type"] == "spark_driver" and c["trigger"] == "benefits_issuance_day")


def test_e02_axis_cleanup():
    assert "keep_a_routine" in AX["job"] and "protect_someone" in AX["job"] and len(AX["job"]) == 17
    assert "observance_calendar" in AX["trigger"] and "general_assistant" in AX["agent_surface"]


def test_e04_template_cards_valid_synthetic_fixed_temperature():
    cells = e02_sampler.sample(LAT, 2, 30)["cells"]
    gen = e04_cards.generate(cells, 2, 3)
    assert gen["fallback_used"] and gen["generator"] == "template@1"
    for c in gen["cards"]:
        assert e04_cards.validate(c, AX) == []
        assert c["synthetic"] is True and c["source"]["temperature"] == e04_cards.FIXED_TEMPERATURE
        assert c["needs"] and "parse_intent" in c["needs"]


@pytest.mark.parametrize("endpoint,repo", [("https://api.openai.com", "qwen"), ("http://8.8.8.8:8080", "qwen"),
                                           ("http://127.0.0.1:8080", "anthropic/claude-x"), ("http://localhost:1", "openai/gpt-5")])
def test_e04_teacher_refuses_non_local_or_frontier(endpoint, repo):
    with pytest.raises(e04_cards.TeacherRefused):
        e04_cards.check_local(endpoint, {"repo": repo, "revision": "r", "sha256": "s"})


def test_e04_teacher_requires_pins():
    with pytest.raises(e04_cards.TeacherRefused):
        e04_cards.check_local("http://127.0.0.1:1", {"repo": "Qwen/Qwen3.8-27B", "revision": "", "sha256": "x"})


class _FakeMLX(BaseHTTPRequestHandler):
    reply = {"title": "Synthetic teacher card", "situation": "A synthetic household's agent restocks under a stated cap.",
             "specific_brief": "'cap $50; pickup Sat'", "gateway_only": ["unattended", "not_a_condition"]}
    def do_POST(self):
        self.rfile.read(int(self.headers["content-length"]))
        body = json.dumps({"choices": [{"message": {"content": json.dumps(self.reply)}}]}).encode()
        self.send_response(200); self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass


def test_e04_local_teacher_round_trip_and_fallback():
    srv = HTTPServer(("127.0.0.1", 0), _FakeMLX); threading.Thread(target=srv.serve_forever, daemon=True).start()
    pin = {"repo": "Qwen/Qwen3.8-27B", "revision": "0123456789abcdef", "sha256": "f" * 64}
    t = e04_cards.LocalTeacher(f"http://127.0.0.1:{srv.server_port}", pin)
    cell = e02_sampler.sample(LAT, 1, 11)["cells"][0]
    cards = t.generate(cell, 2, random.Random(1))
    assert len(cards) == 2 and cards[0]["source"]["generator"].startswith("teacher:Qwen/Qwen3.8-27B")
    assert cards[0]["gateway_only"] == ["unattended"]            # unknown conditions dropped
    srv.shutdown()
    dead = e04_cards.LocalTeacher("http://127.0.0.1:9", pin)     # nothing listening -> [] -> generate() falls back
    gen = e04_cards.generate([cell], 1, 2, dead)
    assert gen["fallback_cells"] == 1 and gen["cards"]


def test_e05_rephrasings_land_together_and_seeds_stay_apart():
    seeds = list(seed_by_id().values())
    cards = []
    rng = random.Random(4)
    for s in seeds[:20]:
        cell = {"cell_id": "T", "actor_type": s["actor_type"], "job": s["job"], "trigger": s["trigger"], "agent_surface": s["surface"], "quadrant": s["quadrant"]}
        for v in range(3):
            cards.append(e04_cards.card_from_seed(s, cell, rng, v, {}, {}))
    dd = e05_dedupe.dedupe(cards, [{"id": s["id"], "title": s["title"], "situation": s["situation"], "specific_brief": s["specific_brief"]} for s in seeds])
    assert len(dd["families"]) == 20
    assert {f["family_id"] for f in dd["families"]} == {s["id"] for s in seeds[:20]}
    assert dd["max_inter_family_similarity"] < e05_dedupe.DEDUPE_T


def test_e06_anchors():
    cover = e06_ladder.load_cover(); S = seed_by_id()
    def card(i):
        s = S[i]; cell = {"cell_id": "A", "actor_type": s["actor_type"], "job": s["job"], "trigger": s["trigger"], "agent_surface": s["surface"], "quadrant": s["quadrant"]}
        return e04_cards.card_from_seed(s, cell, random.Random(0), 0, {}, {})
    assert e06_ladder.place(card("PF-51"), cover)["tier"] == 2
    assert e06_ladder.place(card("G-01"), cover)["tier"] == 0
    assert e06_ladder.place(card("G-03"), cover)["tier"] == 1
    assert e06_ladder.place(card("PF-28"), cover)["tier"] == 2
    assert "COV-01" in e06_ladder.place(card("G-01"), cover)["rungs"]["0"]["covered_by"]


def test_e08_e3_only_from_owner_recordings():
    c = {"evidence": {"level": "E3", "refs": ["goldin"]}}
    assert e08_evidence.join(c, {"goldin": "x"})["level"] == "E2"
    c = {"evidence": {"level": "E3", "refs": ["baseline"]}}
    assert e08_evidence.join(c, {"baseline": "x"})["level"] == "E3"
    assert e08_evidence.join({"evidence": {"level": "E2", "refs": ["ST-101", "nope"]}}, {})["unresolved_refs"] == ["nope"]


def test_e09_two_way_sizing_labeled():
    s = seed_by_id()["PF-39"]
    cell = {"cell_id": "A", "actor_type": s["actor_type"], "job": s["job"], "trigger": s["trigger"], "agent_surface": s["surface"], "quadrant": s["quadrant"]}
    z = e09_sizing.size(e04_cards.card_from_seed(s, cell, random.Random(0), 0, {}, {}))
    assert z["usd_per_year"]["value"] == 23400000 and z["usd_per_year"]["label"] == "derived:synthetic"
    assert find_unlabeled(z) == []
    assert z["driver_tree"]["children"][0]["label"] == "public:pantries"


def test_e10_aggregate_median_and_spread_flag():
    panel = [{k: 3 for k in e10_judges.JUDGED}, {k: 3 for k in e10_judges.JUDGED}, {**{k: 3 for k in e10_judges.JUDGED}, "novelty": 5.5}]
    agg = e10_judges.aggregate(panel)
    assert agg["median"]["novelty"] == 3 and agg["flagged"] == ["novelty"] and agg["k"] == 3
    spec = e10_judges.judge_batch_spec([{"family_id": "PF-39", "representative": "RC-1"}], "rubric@2", [{"repo": "Qwen/Qwen3.5-9B", "local": True}])
    assert spec["kind"] == "judge-batch" and spec["shift"] == "night"

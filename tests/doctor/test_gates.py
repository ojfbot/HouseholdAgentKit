"""Gates fail closed, and doctor never says "climb" a rung whose start gate is not clear."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kit_cli import doctor, gates
from kit_cli.gates import Issue

pytestmark = pytest.mark.doctor

ROOT = doctor.ROOT


def _world(**overrides: Issue) -> dict[int, Issue]:
    """Every blocker in docs/gates.yaml done (issues closed as completed, PR #1 merged), then the overrides."""
    spec = gates.load_spec(ROOT)
    issues: dict[int, Issue] = {}
    for g in spec.gates:
        for n in g.blocked_by:
            issues[n] = Issue(n, f"issue {n}", "closed", "completed")
        issues[g.milestone] = Issue(g.milestone, f"{g.title} the milestone", "open")
    issues[1] = Issue(1, "repo init", "closed", None, is_pr=True, merged=True)
    for key, issue in overrides.items():
        issues[int(key.lstrip("n"))] = issue
    return issues


def _fetch(issues: dict[int, Issue]) -> gates.Fetcher:
    return lambda repo: issues


def _verdict(gid: str, issues: dict[int, Issue]) -> gates.Verdict:
    return next(v for v in gates.evaluate(gates.load_spec(ROOT), _fetch(issues)) if v.gate.id == gid)


def test_every_blocker_done_is_clear() -> None:
    assert all(v.clear for v in gates.evaluate(gates.load_spec(ROOT), _fetch(_world())))


def test_an_open_blocker_blocks() -> None:
    v = _verdict("rung-3", _world(n38=Issue(38, "doctor holes", "open")))
    assert v.status == "blocked" and v.pending == [38]


def test_an_unmerged_pull_request_blocks_even_when_closed() -> None:
    v = _verdict("rung-3", _world(n1=Issue(1, "repo init", "closed", None, is_pr=True, merged=False)))
    assert v.status == "blocked" and "#1 unmerged" in v.detail


def test_closed_as_not_planned_blocks_unless_the_owner_waives_it() -> None:
    issues = _world(n41=Issue(41, "ci fixes", "closed", "not_planned"))
    assert _verdict("rung-3", issues).status == "blocked"
    spec = gates.load_spec(ROOT)
    for g in spec.gates:
        if g.id == "rung-3":
            g.waived = [41]
    assert next(v for v in gates.evaluate(spec, _fetch(issues)) if v.gate.id == "rung-3").clear


def test_an_issue_github_does_not_know_is_unknown_not_clear() -> None:
    issues = _world()
    del issues[39]
    v = _verdict("beat-1-live", issues)
    assert v.status == "unknown" and not v.clear


def test_github_unreachable_is_unknown_for_every_gate() -> None:
    def down(repo: str) -> dict[int, Issue]:
        raise OSError("network is unreachable")

    verdicts = gates.evaluate(gates.load_spec(ROOT), down)
    assert verdicts and all(v.status == "unknown" for v in verdicts)


def test_kit_gates_exit_code_follows_the_milestone(capsys: pytest.CaptureFixture[str]) -> None:
    assert gates.run(ROOT, milestone=20, fetch=_fetch(_world())) == 0
    assert gates.run(ROOT, milestone=20, fetch=_fetch(_world(n39=Issue(39, "poll", "open")))) == 1
    assert gates.run(ROOT, milestone=38, fetch=_fetch(_world())) == 1  # no gate names it: not an answer by itself
    assert gates.run(ROOT, milestone=38, fetch=_fetch(_world()), ungated=True) == 0  # ...until the caller says so
    capsys.readouterr()


def _doctor(capsys: pytest.CaptureFixture[str], issues: dict[int, Issue], upto: int, monkeypatch: pytest.MonkeyPatch, reviewed: bool = True) -> tuple[int, str]:
    # Pretend rungs 0-2 are green (and the review recorded, unless told otherwise) so the test is about gates, not this host.
    for c in doctor.CHECKS:
        if c.rung <= 2:
            monkeypatch.setattr(c, "fn", lambda root: doctor.Result(True, "stubbed green"))
    review = doctor.Result(True, "stubbed review") if reviewed else doctor.Result(False, "independent review not recorded: stubbed")
    monkeypatch.setattr(doctor, "review_recorded", lambda root, today=None: review)
    code = doctor.run(upto=upto, today=date(2026, 11, 26), fetch=_fetch(issues))
    return code, capsys.readouterr().out


def test_next_never_says_climb_a_gated_rung(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, out = _doctor(capsys, _world(n38=Issue(38, "doctor holes", "open")), 2, monkeypatch)
    nxt = next(ln for ln in out.splitlines() if ln.startswith("next"))
    assert "climb" not in nxt and "#38" in nxt
    assert code == 0  # rungs 0-2 are green; the gate is about rung 3


def test_next_says_climb_when_the_gate_is_clear(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _, out = _doctor(capsys, _world(), 2, monkeypatch)
    assert next(ln for ln in out.splitlines() if ln.startswith("next")).startswith("next    climb rung 3")


def test_asking_for_a_gated_rung_exits_red(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, out = _doctor(capsys, _world(n41=Issue(41, "ci fixes", "open")), 3, monkeypatch)
    rung3 = next(ln for ln in out.splitlines() if ln.startswith("rung 3 "))
    assert code == 1 and "#41" in rung3 and "GREEN" not in rung3


def test_offline_doctor_shows_gates_unknown(capsys: pytest.CaptureFixture[str]) -> None:
    doctor.run(upto=0, today=date(2026, 11, 26))
    out = capsys.readouterr().out
    assert "UNKNOWN" in out and "CLEAR" not in out


def test_a_broken_gates_file_blocks_every_rung_above_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/gates.yaml").write_text("version: 1\nrepo: a/b\ngates: []\n")
    verdicts, broken = doctor._gate_verdicts(tmp_path, _fetch({}))
    assert verdicts == [] and broken and "no rung above 2 may start" in broken


def test_a_mistyped_milestone_is_unknown_not_a_gate_on_the_wrong_issue() -> None:
    spec = gates.load_spec(ROOT)
    gate = next(g for g in spec.gates if g.id == "rung-3")
    gate.milestone = 30  # one keystroke away from 3; #30 exists and is not rung 3
    issues = _world(n30=Issue(30, "[DX] A recording per beat, registered", "open"))
    v = next(v for v in gates.evaluate(spec, _fetch(issues)) if v.gate.id == "rung-3")
    assert v.status == "unknown" and "should start 'Rung 3:'" in v.detail


def test_a_milestone_github_does_not_have_is_unknown() -> None:
    issues = _world()
    del issues[10]
    assert _verdict("rung-10", issues).status == "unknown"


def test_asking_about_an_issue_github_does_not_have_exits_red(capsys: pytest.CaptureFixture[str]) -> None:
    assert gates.run(ROOT, milestone=9999, fetch=_fetch(_world())) == 1
    assert "no issue #9999" in capsys.readouterr().out


def test_a_missing_review_stops_rung_3_even_when_every_gate_is_clear(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _, out = _doctor(capsys, _world(), 2, monkeypatch, reviewed=False)
    nxt = next(ln for ln in out.splitlines() if ln.startswith("next"))
    assert "climb" not in nxt and "review" in nxt


def test_the_review_verdict_is_in_the_json(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    for c in doctor.CHECKS:
        if c.rung <= 2:
            monkeypatch.setattr(c, "fn", lambda root: doctor.Result(True, "stubbed green"))
    doctor.run(upto=2, today=date(2026, 11, 26), as_json=True, fetch=_fetch(_world()))
    blob = json.loads(capsys.readouterr().out)
    assert blob["review"]["ok"] is False and "may not start" in blob["next"]


def test_a_gate_mistyped_onto_another_issue_blocks_the_query_for_the_intended_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Codex re-review 1: the rung-3 gate typed as #30 vanished from a query for #3, which then exited 0."""
    world = _world(n30=Issue(30, "[DX] A recording per beat, registered", "open"))
    (tmp_path / "docs").mkdir()
    (tmp_path / gates.GATES_FILE).write_text((ROOT / gates.GATES_FILE).read_text().replace("milestone: 3\n", "milestone: 30\n", 1))
    assert gates.run(tmp_path, milestone=3, fetch=_fetch(world)) == 1
    assert gates.run(tmp_path, milestone=3, fetch=_fetch(world), ungated=True) == 1
    assert "do not name the issue they claim" in capsys.readouterr().out


def test_github_unreachable_answers_no_query() -> None:
    def down(repo: str) -> dict[int, Issue]:
        raise OSError("network is unreachable")

    assert gates.run(ROOT, milestone=38, fetch=down, ungated=True) == 1


def test_a_close_query_never_answers_from_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Codex re-review 6064615719, 1: a warm cache answered `--ungated` while GitHub was unreachable."""
    monkeypatch.delenv("KIT_OFFLINE")
    calls = {"n": 0}

    def flaky(repo: str) -> dict[int, Issue]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("network is unreachable")
        return _world()

    monkeypatch.setattr(gates, "fetch_github", flaky)
    (tmp_path / "docs").mkdir()
    (tmp_path / gates.GATES_FILE).write_text((ROOT / gates.GATES_FILE).read_text())
    assert gates.run(tmp_path) == 0  # status run, every gate clear in this world: warms out/gates-cache.json
    assert (tmp_path / gates.CACHE_FILE).exists()
    capsys.readouterr()
    assert gates.run(tmp_path, milestone=38, ungated=True) == 1  # the close query goes to GitHub, which is down
    out = capsys.readouterr().out
    assert "cannot read GitHub" in out and "Traceback" not in out


def test_a_close_query_answers_from_one_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def once(repo: str) -> dict[int, Issue]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise AssertionError("a second read inside one query")
        return _world()

    assert gates.run(ROOT, milestone=38, fetch=once, ungated=True) == 0
    assert calls["n"] == 1

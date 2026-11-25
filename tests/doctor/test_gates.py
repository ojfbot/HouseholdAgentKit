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
        for n in [g.milestone, *g.blocked_by]:
            issues[n] = Issue(n, f"issue {n}", "closed", "completed")
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
    assert gates.run(ROOT, milestone=999, fetch=_fetch(_world())) == 0  # nothing gates an unlisted issue
    capsys.readouterr()


def _doctor(capsys: pytest.CaptureFixture[str], issues: dict[int, Issue], upto: int, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    # Pretend rungs 0-2 are green so the test is about gates, not about this host.
    for c in doctor.CHECKS:
        if c.rung <= 2:
            monkeypatch.setattr(c, "fn", lambda root: doctor.Result(True, "stubbed green"))
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

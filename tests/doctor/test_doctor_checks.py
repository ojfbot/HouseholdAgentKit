"""Every `kit doctor` check is shown red on each planted break and green on a working setup before it gates."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from kit_cli import doctor

pytestmark = pytest.mark.doctor


@pytest.mark.parametrize("check", doctor.CHECKS, ids=lambda c: c.id)
def test_check_is_red_on_its_breaks_and_green_on_a_working_setup(check: doctor.Check) -> None:
    rows = doctor.prove(check)
    assert rows[0][0] == "working setup" and rows[0][1], f"{check.id} is not green on a working setup: {rows[0][2]}"
    assert len(rows) > 1, f"{check.id} has no planted break"
    for label, went_red, detail in rows[1:]:
        assert went_red, f"{check.id} stayed green on a broken setup ({label}): {detail}"


def test_a_check_without_a_proof_is_refused() -> None:
    with pytest.raises(ValueError, match="no proof"):
        doctor.Check("unproven", 1, lambda root: doctor.Result(True, ""), [])


def test_unclimbed_rungs_never_read_green(capsys: pytest.CaptureFixture[str]) -> None:
    doctor.run(upto=10, today=date(2026, 11, 21))
    out = capsys.readouterr().out
    for rung in range(3, 11):
        line = next(ln for ln in out.splitlines() if ln.startswith(f"rung {rung:<2} "))
        assert "NOT CLIMBED" in line and "GREEN" not in line


def _date_lines(out: str) -> dict[str, str]:
    return {ln.split()[1]: ln for ln in out.splitlines() if ln.startswith("date ")}


def test_a_date_counts_down_before_it_arrives(capsys: pytest.CaptureFixture[str]) -> None:
    doctor.run(upto=0, today=date(2026, 11, 24))
    lines = _date_lines(capsys.readouterr().out)
    assert "in 1 d" in lines["2026-11-25"] and "in 4 d" in lines["2026-11-28"]
    assert not any("RED" in ln for ln in lines.values())


def test_a_date_that_has_arrived_is_red_not_a_countdown(capsys: pytest.CaptureFixture[str]) -> None:
    """Planted break (#38 [4]): on the day itself the engine already aborts, so `in 0 d` was a false good."""
    doctor.run(upto=0, today=date(2026, 11, 25))
    lines = _date_lines(capsys.readouterr().out)
    assert "RED" in lines["2026-11-25"] and "in 0 d" not in lines["2026-11-25"]
    assert "in 3 d" in lines["2026-11-28"]


def test_a_passed_date_stays_red_while_its_gate_is_red(capsys: pytest.CaptureFixture[str]) -> None:
    """Planted break (#38 [4]): the founding doctor dropped a date line the day after, with both gates still red."""
    doctor.run(upto=0, today=date(2026, 11, 29))
    lines = _date_lines(capsys.readouterr().out)
    assert "RED" in lines["2026-11-25"] and "4 d ago" in lines["2026-11-25"]
    assert "RED" in lines["2026-11-28"] and "1 d ago" in lines["2026-11-28"]
    assert "pass from a full" in lines["2026-11-25"], "the line gives the engine's own reason"
    assert "parity_floors" in lines["2026-11-28"], "the line gives the gate's own reason"


def test_a_date_line_goes_only_when_its_gate_passes(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    passes = doctor.Deadline(date(2026, 11, 25), "a gate that now passes", lambda root, day: doctor.Result(True, "passes"))
    monkeypatch.setattr(doctor, "deadlines", lambda root: [passes])
    doctor.run(upto=0, today=date(2026, 11, 29))
    assert not _date_lines(capsys.readouterr().out)


def test_a_gate_that_cannot_be_asked_is_red(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(root: object, day: date) -> doctor.Result:
        raise RuntimeError("no engine here")

    monkeypatch.setattr(doctor, "deadlines", lambda root: [doctor.Deadline(date(2026, 11, 25), "a gate nobody can ask", broken)])
    doctor.run(upto=0, today=date(2026, 11, 20))
    line = _date_lines(capsys.readouterr().out)["2026-11-25"]
    assert "RED" in line and "no engine here" in line


def test_a_broken_deadline_source_is_a_red_line_not_a_missing_one(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(root: object) -> list[doctor.Deadline]:
        raise ValueError("gate-config.yaml does not parse")

    monkeypatch.setattr(doctor, "deadlines", broken)
    doctor.run(upto=0, today=date(2026, 11, 20))
    out = capsys.readouterr().out
    assert any(ln.startswith("dates ") and "RED" in ln and "does not parse" in ln for ln in out.splitlines())


def test_the_dates_are_read_from_the_gates_themselves() -> None:
    """Doctor asks the two real gates, so a moved date or a renewed waiver moves the line with it."""
    from discovery_engine import pipeline

    engine, waiver = doctor.deadlines(doctor.ROOT)
    assert engine.when == date.fromisoformat(pipeline.PASS_REQUIRED_FROM)
    assert engine.ask(doctor.ROOT, date(2026, 11, 24)).ok
    assert not engine.ask(doctor.ROOT, date(2026, 11, 25)).ok
    assert waiver.when == date(2026, 11, 28)
    assert waiver.ask(doctor.ROOT, date(2026, 11, 27)).ok
    assert not waiver.ask(doctor.ROOT, date(2026, 11, 28)).ok


def test_the_dates_are_in_the_json(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    doctor.run(upto=0, today=date(2026, 11, 26), as_json=True)
    dates = {d["date"]: d for d in json.loads(capsys.readouterr().out)["dates"]}
    assert dates["2026-11-25"]["status"] == "red" and dates["2026-11-25"]["days"] == -1
    assert dates["2026-11-28"]["status"] == "upcoming" and dates["2026-11-28"]["days"] == 2


def _stub_rung_0(monkeypatch: pytest.MonkeyPatch, hole: str) -> doctor.Check:
    check = next(c for c in doctor.CHECKS if c.rung == 0)
    monkeypatch.setattr(check, "fn", lambda root: doctor.Result(True, "stubbed green"))
    monkeypatch.setattr(check, "hole", hole)
    return check


def test_a_check_with_a_known_hole_never_reads_plain_green(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """A check that passes a known broken setup says so on its rung line until the hole is closed."""
    check = _stub_rung_0(monkeypatch, "#38 [20]: passes when the package is named only in prose")
    doctor.run(upto=0, today=date(2026, 11, 21))
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("rung 0 "))
    assert "GREEN" in line and "1 unproven" in line and "#38" in line and check.id in line


def test_a_check_with_no_known_hole_reads_plain_green(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_rung_0(monkeypatch, "")
    doctor.run(upto=0, today=date(2026, 11, 21))
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("rung 0 "))
    assert "GREEN" in line and "unproven" not in line


def test_known_holes_are_in_the_json_and_the_self_test_summary(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    check = _stub_rung_0(monkeypatch, "#38 [20]: passes when the package is named only in prose")
    doctor.run(upto=0, today=date(2026, 11, 21), as_json=True)
    row = next(r for r in json.loads(capsys.readouterr().out)["rungs"]["0"] if r["check"] == check.id)
    assert row["ok"] is True and row["unproven"].startswith("#38 [20]")
    assert check.id in doctor.holes_summary() and "#38" in doctor.holes_summary()


# ---- Review of #48 (Codex): the date probes judged the reference stand-in, never the setup's own inputs.


def _reference_full_result() -> dict:
    from kit_eval import hello_world

    return hello_world.run("full", "doctor", cases_dir=doctor.ROOT / "data/seeds/cases")


def test_the_engine_date_judges_the_result_it_is_pointed_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A setup whose real hello-world result is a full pass gets past stage 0; doctor must not read it red."""
    passing = {**_reference_full_result(), "status": "pass", "mode": "full"}
    (tmp_path / "hw.json").write_text(json.dumps(passing))
    monkeypatch.setenv("KIT_HELLO_WORLD_RESULT", str(tmp_path / "hw.json"))
    engine = next(d for d in doctor.deadlines(doctor.ROOT) if "stage 0" in d.what)
    verdict = engine.ask(doctor.ROOT, date(2026, 11, 29))
    assert verdict.ok, verdict.detail
    assert str(tmp_path / "hw.json") in verdict.detail


def test_without_a_result_the_engine_date_says_it_judged_the_stand_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIT_HELLO_WORLD_RESULT", raising=False)
    engine = next(d for d in doctor.deadlines(doctor.ROOT) if "stage 0" in d.what)
    verdict = engine.ask(doctor.ROOT, date(2026, 11, 29))
    assert not verdict.ok and "stand-in" in verdict.detail and "KIT_HELLO_WORLD_RESULT" in verdict.detail


def _reference_report() -> dict:
    from kit_eval.cases import load_cases
    from kit_eval.report import build_report, load_hook, run_hello_world

    cases, hook = load_cases(str(doctor.ROOT / "data/seeds/cases")), load_hook(None)
    return build_report(run_hello_world(hook, cases, k=5, seed=0), cases, bundle_id="doctor", hook_name=hook.name, k=5)


def test_the_gate_date_judges_the_candidate_it_is_pointed_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After the waiver lapses, a candidate that reports parity_floors 0 passes `kit gate`; doctor must agree."""
    report = _reference_report()
    report["metrics"]["parity_floors"] = {"value": 0, "direction": "lower", "n": 1}
    (tmp_path / "candidate.json").write_text(json.dumps(report))
    monkeypatch.setenv("KIT_GATE_CANDIDATE", str(tmp_path / "candidate.json"))
    waiver = next(d for d in doctor.deadlines(doctor.ROOT) if "waiver" in d.what)
    verdict = waiver.ask(doctor.ROOT, date(2026, 11, 29))
    assert verdict.ok, verdict.detail
    assert str(tmp_path / "candidate.json") in verdict.detail


def test_a_gate_already_red_before_its_date_reads_red_now(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Before the waiver lapses, a candidate with a lock violation already fails `kit gate`: no countdown, red today."""
    report = _reference_report()
    report["metrics"]["locks"]["value"] = 1
    (tmp_path / "candidate.json").write_text(json.dumps(report))
    monkeypatch.setenv("KIT_GATE_CANDIDATE", str(tmp_path / "candidate.json"))
    doctor.run(upto=0, today=date(2026, 11, 26))
    line = _date_lines(capsys.readouterr().out)["2026-11-28"]
    assert "RED" in line and "already" in line and "in 2 d" not in line

"""Every `kit doctor` check is shown red on each planted break and green on a working setup before it gates."""

from __future__ import annotations

from datetime import date

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


def test_date_lines_count_down_and_then_disappear(capsys: pytest.CaptureFixture[str]) -> None:
    doctor.run(upto=0, today=date(2026, 11, 24))
    assert "2026-11-25" in capsys.readouterr().out
    doctor.run(upto=0, today=date(2026, 11, 29))
    assert "2026-11-25" not in capsys.readouterr().out

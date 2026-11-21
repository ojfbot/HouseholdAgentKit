"""K20 conformance suite under pytest. `kit conformance` prints the same checks as n/N."""

from __future__ import annotations

import os

import pytest

from kit_eval.conformance import CHECKS, CORE_CHECKS

pytestmark = pytest.mark.conformance


@pytest.mark.parametrize("check_id", list(CHECKS))
def test_protocol_and_parity(check_id):
    ok, detail = CHECKS[check_id]()
    assert ok, detail


@pytest.mark.requires_core
@pytest.mark.parametrize("check_id", CORE_CHECKS)
def test_core_half(check_id):
    if not os.environ.get("KIT_CORE_IMPL"):
        pytest.skip("HP's twin core half not registered (KIT_CORE_IMPL unset)")
    pytest.fail(f"{check_id}: core check body lands with HP's core PR")

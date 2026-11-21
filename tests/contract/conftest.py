"""Shared fixtures for the capability-tagged contract suites (adapters@1 contract_tests).

`pytest -m cap07` reruns exactly CT-07a..f when CAP-07 access or format news arrives.
Bind a real implementation with KIT_CT_IMPL=<module>:<attr>; the default is the reference.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from kit_eval.cases import load_cases, mandate_from_case
from mock_gateway import at, make_twin

ROOT = Path(__file__).resolve().parents[2]
T0 = at(2026, 11, 24, 14, 0)


@pytest.fixture(scope="session")
def impl():
    spec = os.environ.get("KIT_CT_IMPL", "contract.reference_impl:impl")
    mod, _, attr = spec.partition(":")
    return getattr(importlib.import_module(mod), attr)


@pytest.fixture(scope="session")
def cases():
    return {c["case_id"]: c for c in load_cases(ROOT / "data" / "seeds" / "cases")}


@pytest.fixture
def twin():
    return make_twin(T0, seed=0)


@pytest.fixture
def hw_mandate(cases):
    return mandate_from_case(cases["hw-taco-000"])


@pytest.fixture
def lock_mandate(cases):
    return mandate_from_case(cases["hw-taco-002-safe-food-lock"])


@pytest.fixture
def exclude_mandate(cases):
    return mandate_from_case(cases["hw-taco-001-dairy-free"])


@pytest.fixture
def block_mandate(cases):
    return mandate_from_case(cases["hw-taco-007-no-gift-cards"])

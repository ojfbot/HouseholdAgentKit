"""Doctor tests never read GitHub: gates fall back to UNKNOWN unless a test passes its own fetcher."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIT_OFFLINE", "1")

from __future__ import annotations

from datetime import datetime

import pytest

from kit_contracts import CartLine, canonical_json, lines_hash
from kit_contracts.loose import standing_view, validate_case


def test_canonical_json_is_sorted_compact_and_refuses_naive_times():
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    with pytest.raises(ValueError):
        canonical_json({"t": datetime(2026, 11, 24, 18, 0)})


def test_lines_hash_ignores_order_and_agent_claims():
    a = [CartLine("X", 1, 100, "salsa"), CartLine("Y", 2, 50, "cheese")]
    b = [CartLine("Y", 2, 50, "tortillas", lock_ok=False), CartLine("X", 1, 100, "salsa")]
    assert lines_hash(a) == lines_hash(b)
    assert lines_hash(a) != lines_hash([CartLine("X", 2, 100, "salsa"), CartLine("Y", 2, 50, "cheese")])


@pytest.mark.loose_contract
def test_case_v1_accepts_either_drafts_extras():
    core = {"case_id": "c", "persona": "p", "goal": "g", "accept_if": [{"kind": "verified"}], "synthetic": True}
    assert (
        validate_case({**core, "lineage": {"occasion": "taco", "persona_id": "p", "template_id": "t", "seed": 0, "generator_sha": "x"}, "split": "dev"}) == []
    )
    assert validate_case({**core, "mode": "interview", "request_type": "ambiguous_usual", "world_events": ["default_address_drift"]}) == []
    assert validate_case({**core, "synthetic": False})
    assert validate_case({**core, "mode": "chat"})
    assert validate_case({**core, "lineage": {"occasion": "taco"}})


@pytest.mark.loose_contract
def test_standing_view_reads_both_shapes():
    f = standing_view({"schedule": "weekly", "cap_per_order": 2000, "cap_per_month": 6000, "autonomy": "within_cap", "expires": "2026-12-31"})
    g = standing_view(
        {"spend_limits": {"per_transaction": {"amount_cents": 2000}, "per_month": 6000}, "frequency": "weekly", "category_restrictions": ["gift_card"]}
    )
    assert (f.shape, f.per_order_cents, f.per_month_cents) == ("components@2", 2000, 6000)
    assert (g.shape, g.per_order_cents, g.category_blocks) == ("guardrail-mapped", 2000, ("gift_card",))
    assert standing_view(None) is None

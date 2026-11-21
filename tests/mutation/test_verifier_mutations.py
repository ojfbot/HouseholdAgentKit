"""K03 mutation suite: every seeded violation caught, zero false alarms on clean bases.

Definition of done (the planning project): "mutation suite caught 100%". Bases are the hello-world
dev cases built by the reference pipeline on the twin, across three twin seeds.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from kit_contracts import Refusal
from kit_eval import reference as ref
from kit_eval.cases import load_cases, mandate_from_case
from kit_verifier.mutations import Base, Ctx, run_mutation_suite
from mock_gateway import DiscoverQuery, TwinEvent, make_twin

ROOT = Path(__file__).resolve().parents[2]
ALL_ROLES = ("tortillas", "protein", "cheese", "salsa", "lettuce", "sour_cream", "seasoning", "tomato", "gift_card")

pytestmark = pytest.mark.mutation


def _bases() -> list[Base]:
    bases = []
    for seed in (0, 1, 2):
        for case in load_cases(ROOT / "data" / "seeds" / "cases"):
            if not any(a["kind"] == "tier" for a in case["accept_if"]):
                continue
            start = datetime.fromisoformat(case["clock_start"])
            twin = make_twin(start, seed=seed)
            m = mandate_from_case(case)
            store = case["store"]
            cart = ref.greedy_cart(m, twin, store, start)
            if isinstance(cart, Refusal):
                continue
            r = twin.catalog.discover(DiscoverQuery(store=store, roles=ALL_ROLES), start)
            cands = {role: [o.sku for o in offers] for role, offers in r.value.offers_by_role.items()}
            card, truth = ref.approval_card(cart, m, f"vr:{cart.cart_id}")

            def reprice(twin=twin, cart=cart, start=start) -> datetime:
                ln = cart.lines[0]
                twin.catalog.inject(TwinEvent(start + timedelta(minutes=1), "price_change", ln.sku, price_cents=ln.price_cents + 31))
                return start + timedelta(minutes=5)

            bases.append(
                Base(
                    cart=cart,
                    ctx=Ctx(mandate=m, catalog=twin.catalog, now=start, store=store, candidates=cands),
                    card=card,
                    truth=truth,
                    brief_wire=ref.render_brief_h2(m),
                    reprice=reprice,
                )
            )
    return bases


@pytest.fixture(scope="module")
def report():
    rep = run_mutation_suite(_bases())
    out = os.environ.get("KIT_MUTATION_REPORT")
    if out:
        Path(out).write_text(json.dumps(rep.as_dict(), indent=2))
    return rep


def test_no_false_alarms_on_clean_bases(report):
    assert report.clean_false_alarms == []


def test_every_operator_applied_at_least_once(report):
    assert report.never_applied() == [], "an operator that never applies proves nothing"


def test_kill_rate_is_100_percent(report):
    survivors = {k: s.survivors for k, s in report.operators.items() if s.survivors}
    assert report.kill_rate == 1.0, survivors


def test_every_kill_is_for_the_right_reason(report):
    assert report.wrong_reasons() == {}


def test_suite_size_is_meaningful(report):
    assert report.total_applied >= 300

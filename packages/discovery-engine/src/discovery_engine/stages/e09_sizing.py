"""E09 — two-way sizer + value driver tree (stage 7). Deterministic; every input labeled.

Bottom-up (Fork C's run-0 formula, unchanged):
  VaS_bu = segment_size x adoption_share x frequency_per_year x basket_usd x gap
Top-down (new; inputs in fixtures `sizing-topdown@0`, all synthetic until ED sources public ones):
  VaS_td = segment_size x adoption_share x job_spend_per_unit[job] x occasion_share x gap
The two share segment, adoption and gap, so their ratio tests the one thing bottom-up guesses hardest: whether
frequency x basket is plausible against the unit's whole yearly spend on that job. Outside BAND the gap is flagged,
never silently reconciled. The reported VaS is bottom-up (C's number) so rankings stay comparable with run 0.
"""
from __future__ import annotations

from ..util import L, derived

BAND = (1 / 3, 3.0)
# $/year per segment unit spent on the job (household, org, business or team), and the share one occasion type takes.
# Synthetic placeholders (label: synthetic). Replace with public:BLS-CE etc. when ED sources them.
JOB_SPEND = {"feed": 6000, "restock": 3000, "host_or_celebrate": 800, "care_for_someone": 3000, "set_up_a_home": 1500,
             "stretch_money": 2000, "recover": 600, "prepare": 400, "gifts": 1000, "school": 500, "hobby_or_build": 600,
             "seasonal": 500, "run_a_small_business": 25000, "give_or_donate": 40000, "manage_group_money": 1500,
             "keep_a_routine": 800, "protect_someone": 600}
OCCASION_SHARE = 0.25
TOPDOWN_VERSION = "sizing-topdown@0"


def size(card: dict, adoption_share: float = 0.10, adoption_label: str = "synthetic") -> dict:
    si = card["sizing_inputs"]
    seg, f, b, g = (si[k]["value"] for k in ("segment_size", "frequency_per_year", "basket_usd", "gap"))
    labels = [si[k]["label"] for k in ("segment_size", "frequency_per_year", "basket_usd", "gap")] + [adoption_label]
    bu = seg * adoption_share * f * b * g
    spend = JOB_SPEND[card["job"]]
    td = seg * adoption_share * spend * OCCASION_SHARE * g
    ratio = td / bu if bu else float("inf")
    flagged = not (BAND[0] <= ratio <= BAND[1])
    lab = derived(*labels)
    return {
        "usd_per_year": L(round(bu), lab),
        "bottom_up": L(round(bu), lab),
        "top_down": L(round(td), "derived:synthetic"),
        "td_over_bu": L(round(ratio, 2), "derived:synthetic"),
        "band": [L(round(BAND[0], 3), "synthetic"), L(BAND[1], "synthetic")],
        "gap_flagged": flagged,
        "driver_tree": {
            "node": "value_at_stake_usd_per_year", "value": L(round(bu), lab), "op": "product",
            "children": [
                {"node": "segment_size", **si["segment_size"]},
                {"node": "adoption_share", "value": adoption_share, "label": adoption_label},
                {"node": "frequency_per_year", **si["frequency_per_year"]},
                {"node": "basket_usd", **si["basket_usd"]},
                {"node": "gap", **si["gap"]},
            ],
            "top_down_check": {"job_spend_per_unit": L(spend, "synthetic"), "occasion_share": L(OCCASION_SHARE, "synthetic"),
                               "version": TOPDOWN_VERSION},
        },
        "all_inputs_public": lab == "derived:public",
    }

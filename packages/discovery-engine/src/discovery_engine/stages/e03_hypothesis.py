"""E03 — Day-1 hypothesis writer, hash-frozen (stage 0b).

Seam (components@2 E03): frontier -> template from the prior run's top family per lens. Only the template is wired
for Dec 2 (no model call), so the hypothesis is the prior bank's best answer under each lens's balanced profile.
The hypothesis and its sha256 are written to the run log BEFORE stage 2 (E04) runs; the readout reports
survived (still in the top 3) / revised (top 10) / killed (outside). An engine that always confirms its
hypothesis is broken (E18 `hypothesis_honesty` reports the verdict mix across seeds and lenses).
"""
from __future__ import annotations

from ..util import sha256_hex

LENS_DEFAULT_PROFILE = {"in_house": "default", "partner": "partner_default"}
COND_WORDS = {"outside_trigger": "an outside trigger", "unattended": "unattended action", "other_people": "other people's input",
              "context_walmart_shouldnt_hold": "context Walmart shouldn't hold", "completion_under_rules": "completion under the household's rules"}


def write(lens: str, prior_top: dict, prior_run: str, prior_bank_id: str) -> dict:
    f = prior_top
    conds = ", ".join(COND_WORDS[c] for c in f["ladder"]["conditions"][:2]) or "a specific brief Sparky can act on"
    who = "Walmart" if lens == "in_house" else "a partner building for Walmart"
    text = (f"Day-1 hypothesis ({lens}): the biggest value for {who} is in {f['title'].rstrip('.')} ({f['family_id']}) "
            f"for {f['segment']}, because it needs {conds}, which only an outside agent through the Gateway provides.")
    body = {"lens": lens, "text": text, "basis": {"prior_run": prior_run, "prior_bank_id": prior_bank_id,
                                                  "family_id": f["family_id"], "profile": LENS_DEFAULT_PROFILE[lens]},
            "writer": "template@1 (prior run's top family per lens)"}
    return {**body, "hash": sha256_hex(body)}


def verdict(hyp: dict, final_top_ids: list[str]) -> str:
    fid = hyp["basis"]["family_id"]
    ids = [i.split("~")[0] for i in final_top_ids]
    if fid in ids[:3]:
        return "survived"
    if fid in ids:
        return "revised"
    return "killed"

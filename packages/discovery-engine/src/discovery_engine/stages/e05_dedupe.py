"""E05 — normalize + dedupe raw cards into problem families (stage 3). Deterministic.

Seam (components@2 E05): embeddings -> MinHash lexical clusters. Only the MinHash path is built for Dec 2.
Fixed thresholds (config, never tuned per run): a card joins a family at estimated Jaccard >= DEDUPE_T over
unigram+bigram shingles of title + situation + specific brief. Calibrated on run-0 seeds: distinct seeds overlap
<= 0.17, seeded rephrasings of the same seed >= 0.60.
Family ids are lineage ids: a family that matches a prior-bank family (>= LINEAGE_T) keeps its id, so runs and
seeds compare by id (stability, novelty). Otherwise it gets NF-<hash>.
Oracle: fixed thresholds; overlap below threshold after dedupe; metamorphic rephrasings land together.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from ..text import MinHash, shingles
from ..util import sha256_hex

DEDUPE_T = 0.45
LINEAGE_T = 0.45


def card_text(c: dict) -> str:
    return f"{c['title']} {c['situation']} {c['specific_brief']}"


class Index:
    def __init__(self):
        self.mh = MinHash()

    def sig(self, text: str):
        return self.mh.signature(shingles(text))

    def sim(self, a, b) -> float:
        return MinHash.similarity(a, b)


def dedupe(cards: list[dict], prior: list[dict] | None = None) -> dict:
    ix = Index()
    sigs = [ix.sig(card_text(c)) for c in cards]
    parent = list(range(len(cards)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            if ix.sim(sigs[i], sigs[j]) >= DEDUPE_T:
                parent[find(j)] = find(i)
    groups = defaultdict(list)
    for i in range(len(cards)):
        groups[find(i)].append(i)

    prior = prior or []
    psigs = [(p["id"], ix.sig(card_text(p))) for p in prior]
    families, used_ids = [], Counter()
    for members in sorted(groups.values(), key=lambda m: min(cards[i]["card_id"] for i in m)):
        # medoid: highest mean similarity to the other members (ties -> smallest card_id)
        def mean_sim(i):
            return sum(ix.sim(sigs[i], sigs[j]) for j in members if j != i) / max(1, len(members) - 1)
        med = max(members, key=lambda i: (mean_sim(i), -_ord(cards[i]["card_id"])))
        best = max(((ix.sim(sigs[med], ps), pid) for pid, ps in psigs), default=(0.0, None))
        fid = best[1] if best[0] >= LINEAGE_T else "NF-" + sha256_hex(card_text(cards[med]))[:6]
        used_ids[fid] += 1
        if used_ids[fid] > 1:                      # two clusters matched one prior family: keep both, suffix
            fid = f"{fid}~{used_ids[fid]}"
        families.append({"family_id": fid, "lineage": {"prior_id": best[1], "similarity": round(best[0], 3), "matched": best[0] >= LINEAGE_T},
                         "representative": cards[med]["card_id"], "members": sorted(cards[i]["card_id"] for i in members),
                         "member_cells": sorted({cards[i]["cell_id"] for i in members}), "_sig": sigs[med], "_rep": cards[med]})
    # post-dedupe overlap (MECE check)
    max_overlap = 0.0
    for a in range(len(families)):
        for b in range(a + 1, len(families)):
            max_overlap = max(max_overlap, ix.sim(families[a]["_sig"], families[b]["_sig"]))
    return {"families": families, "threshold": DEDUPE_T, "lineage_threshold": LINEAGE_T,
            "max_inter_family_similarity": round(max_overlap, 3), "cards": len(cards)}


def assign(text: str, families: list[dict]) -> tuple[str | None, float]:
    """Which family a new text lands in (metamorphic probe)."""
    ix = Index(); s = ix.sig(text)
    best = max(((ix.sim(s, f["_sig"]), f["family_id"]) for f in families), default=(0.0, None))
    return (best[1] if best[0] >= DEDUPE_T else None), best[0]


def _ord(card_id: str) -> int:
    return int(sha256_hex(card_id)[:8], 16)

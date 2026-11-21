"""Text normalization, deterministic rephrasing and MinHash (used by E04 variants, E05 dedupe, E18 metamorphic)."""
from __future__ import annotations

import hashlib
import random
import re

STOP = set("a an the and or of to in on for with by at from is are be it its this that their they them our we you your "
           "as into than then so if not no nor but who what which when where while each per only every any all own".split())

# Meaning-preserving swaps. Applied to template variants and metamorphic probes; never to structured fields.
SYNONYMS = [
    ("the agent", "the assistant"), ("household", "home"), ("buys", "purchases"), ("approves", "signs off on"),
    ("order", "purchase"), ("budget", "spending limit"), ("deliver", "drop off"), ("restock", "refill"),
    ("arrive", "come in"), ("never", "not ever"), ("before", "ahead of"), ("checks", "verifies"),
    ("week", "seven days"), ("store", "shop"), ("shopper", "customer"), ("cart", "basket"),
]
SWAP_NAMES = [("Dana", "Kim"), ("Ruth", "Maria"), ("Jen", "Aisha"), ("Waco", "Fresno"), ("Tampa", "Tucson"),
              ("Columbus", "Omaha"), ("Spanish", "Vietnamese")]


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9$]+", text.lower()) if t not in STOP]


def shingles(text: str) -> set[str]:
    t = tokens(text)
    return set(t) | {f"{a}_{b}" for a, b in zip(t, t[1:])}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def rephrase(text: str, rng: random.Random, k: int = 3) -> str:
    """Swap up to k phrases from SYNONYMS that occur in the text (seeded)."""
    present = [(a, b) for a, b in SYNONYMS if re.search(rf"\b{re.escape(a)}\b", text, re.I)]
    rng.shuffle(present)
    out = text
    for a, b in present[:k]:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out, count=1, flags=re.I)
    return out


def counterfactual(text: str) -> str:
    """Swap names, places and a language word (stereotype guardrail probe)."""
    out = text
    for a, b in SWAP_NAMES:
        out = re.sub(rf"\b{a}\b", b, out)
    return out


class MinHash:
    def __init__(self, num_perm: int = 64, salt: str = "de-minhash@1"):
        self.salts = [f"{salt}:{i}".encode() for i in range(num_perm)]

    def signature(self, sh: set[str]) -> tuple[int, ...]:
        if not sh:
            return tuple([0] * len(self.salts))
        return tuple(min(int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8, key=salt).digest(), "big") for s in sh)
                     for salt in self.salts)

    @staticmethod
    def similarity(a: tuple, b: tuple) -> float:
        return sum(x == y for x, y in zip(a, b)) / len(a)

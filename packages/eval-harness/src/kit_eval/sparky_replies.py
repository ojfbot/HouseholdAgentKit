"""Synthetic Sparky replies for CT-07b (extraction F1 on 200 replies) and CT-07c (injection, 100% rejected).

Replies are generated from twin offers with seeded templates; gold is the set of (sku, stated
price). Sparky occasionally states a wrong price on purpose (5%): extraction must report what
was said, and K03 must catch it downstream. Distractors name non-catalog items. Synthetic only.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from kit_contracts import Offer, expect
from mock_gateway import DiscoverQuery, Twin

ROLES = ("tortillas", "protein", "cheese", "salsa", "lettuce", "sour_cream", "seasoning")
DISTRACTORS = ("Store-brand napkins for $1.99", "a party pack of plates at $3.49", "paper towels, $5.25")


@dataclass
class Reply:
    reply_id: str
    text: str
    gold: frozenset[tuple[str, int]]
    wrong_prices: frozenset[str]
    injection_id: str | None = None


def _fmt(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _line(rng: random.Random, o: Offer, price: int, i: int) -> str:
    stock = {"in": "in stock", "low": "low stock", "out": "out of stock", "unknown": "stock unknown"}[o.stock]
    tag = "[Sponsored] " if o.sponsored else ""
    style = rng.randrange(5)
    if style == 0:
        return f"{i}. {tag}{o.title} - {_fmt(price)} ({stock})"
    if style == 1:
        return f"- {tag}{o.title}: {_fmt(price)} each"
    if style == 2:
        return f"I'd pick {o.title} at {_fmt(price)}; it's {stock}."
    if style == 3:
        return f"{tag}{o.title} ({_fmt(price)}) is {stock} today."
    return f"Option {i}: {o.title} | {_fmt(price)} | {stock}"


def clean_replies(twin: Twin, store: str, now: datetime, n: int = 200, seed: int = 0) -> list[Reply]:
    rng = random.Random(f"sparky:{seed}")
    pools = expect(twin.catalog.discover(DiscoverQuery(store=store, roles=ROLES), now)).offers_by_role
    out = []
    for k in range(n):
        picks: list[Offer] = []
        for role in rng.sample(list(pools), rng.randint(2, 5)):
            picks.append(rng.choice(pools[role]))
        lines, gold, wrong = [], set(), set()
        for i, o in enumerate(picks, 1):
            price = o.price_cents
            if rng.random() < 0.05:
                price += rng.choice([-30, -11, 7, 25])
                wrong.add(o.sku)
            lines.append(_line(rng, o, price, i))
            gold.add((o.sku, price))
        if rng.random() < 0.4:
            lines.insert(rng.randrange(len(lines) + 1), f"You might also want {rng.choice(DISTRACTORS)}.")
        head = rng.choice(["Here's what I found for taco night:", "Sure! Options:", "For tonight at the store:", ""])
        text = "\n".join([head, *lines]).strip()
        out.append(Reply(f"sr-{seed}-{k:03d}", text, frozenset(gold), frozenset(wrong)))
    return out


def load_patterns(path: str | Path) -> list[dict[str, Any]]:
    return yaml.safe_load(Path(path).read_text())["patterns"]


def injected_replies(base: list[Reply], patterns: list[dict[str, Any]], fill: dict[str, str], seed: int = 0) -> list[Reply]:
    rng = random.Random(f"inject:{seed}")
    out = []
    for i, p in enumerate(patterns):
        for j in range(3):  # each pattern at three positions in three different replies
            b = base[(i * 3 + j) % len(base)]
            lines = b.text.split("\n")
            pos = (0, len(lines) // 2, len(lines))[j]
            inj = p["text"]
            for k, v in fill.items():  # literal placeholders only; seeds may contain JSON braces
                inj = inj.replace("{" + k + "}", v)
            text = "\n".join([*lines[:pos], inj, *lines[pos:]])
            out.append(Reply(f"{b.reply_id}+{p['id']}@{j}", text, b.gold, b.wrong_prices, injection_id=p["id"]))
    rng.shuffle(out)
    return out


def f1(pred: set[tuple[str, int]], gold: set[tuple[str, int]]) -> tuple[float, float, float]:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    r = tp / len(gold) if gold else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)

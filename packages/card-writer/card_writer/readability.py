"""Flesch-Kincaid grade for Card@0 a11y.reading_level (a text metric, not a business number)."""
from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z']+")


def _syllables(word: str) -> int:
    w = word.lower().strip("'")
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def grade(lines: list[str]) -> int:
    words = [w for line in lines for w in _WORD.findall(line)]
    if not words:
        return 1
    sentences = max(1, len(lines))
    syll = sum(_syllables(w) for w in words)
    g = 0.39 * (len(words) / sentences) + 11.8 * (syll / len(words)) - 15.59
    return max(1, round(g))

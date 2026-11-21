"""Bootstrap intervals for eval reports and the gate's paired comparison (eval-gates-v0)."""

from __future__ import annotations

import random
from collections.abc import Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def percentile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def bootstrap_ci(xs: Sequence[float], resamples: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    means = [mean([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples)]
    return (percentile(means, alpha / 2), percentile(means, 1 - alpha / 2))


def paired_bootstrap_lower(candidate: dict[str, float], baseline: dict[str, float], resamples: int = 2000, seed: int = 0) -> tuple[float, int]:
    """Lower 95% bound of mean(candidate - baseline) over identical cases. Returns (bound, n_paired)."""
    keys = sorted(set(candidate) & set(baseline))
    diffs = [candidate[k] - baseline[k] for k in keys]
    if not diffs:
        return (float("-inf"), 0)
    lo, _ = bootstrap_ci(diffs, resamples=resamples, seed=seed)
    return (lo, len(keys))

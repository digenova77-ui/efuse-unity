"""Infinite edge-case generator for purity grades.

Produces as many (clarity, color, cut, reflects) tuples as requested.
Seeded for reproducibility. No external dependencies.
"""
from __future__ import annotations

import itertools
import random
from typing import Iterator, Tuple

CLARITIES = ["FL", "VVS", "VS", "SI", "SI1", "SI2", "I", "I1", "I2", "I3", "UNKNOWN", ""]
COLORS = list("DEFGHIJKLMNOPQRSTUVWXYZ") + ["", "d", "D "]
CUTS = ["Excellent", "Very Good", "Good", "Fair", "Poor", "", "excellent"]
REFLECTS = ["purity", "glass", "theater", " purity", "", "PURITY"]


def all_combinations() -> Iterator[Tuple[str, str, str, str]]:
    """Cartesian product — finite but large."""
    return itertools.product(CLARITIES, COLORS, CUTS, REFLECTS)


def infinite(seed: int = 0) -> Iterator[Tuple[str, str, str, str]]:
    """Seeded infinite stream. Same seed → same sequence."""
    rng = random.Random(seed)
    pool_c = CLARITIES
    pool_o = COLORS
    pool_u = CUTS
    pool_r = REFLECTS
    while True:
        yield (
            rng.choice(pool_c),
            rng.choice(pool_o),
            rng.choice(pool_u),
            rng.choice(pool_r),
        )


def take(n: int, seed: int = 0):
    """First n cases from the infinite stream."""
    return list(itertools.islice(infinite(seed), n))

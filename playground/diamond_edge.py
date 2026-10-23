"""Test generated edge cases against the full diamond.

Each case becomes a facet. The playground judges it
through grade → rise → ceiling → frontier.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

from diamond_playground import Facet, DiamondPlayground, grade
from frontier_protocol import faces_frontier, frontier_report
from edge_generator import take


def judge_case(clarity: str, color: str, cut: str, reflects: str) -> Dict:
    """Run one edge case through the diamond."""
    f = Facet("edge", "ring", clarity, color, cut, reflects)
    g = grade(f)
    facing = faces_frontier(f)
    p = DiamondPlayground(facets=[
        Facet("foundation", "floor"),
        f,
        Facet("ceiling", "ceiling"),
    ])
    rise = p.rise()
    ceiling = p.ceiling()
    frontier = frontier_report(p)
    return {
        "case": {"clarity": clarity, "color": color, "cut": cut, "reflects": reflects},
        "pure": g["pure"],
        "verdict": g["verdict"],
        "failed": g["failed"],
        "facing": facing,
        "rise_ok": rise.get("ok", False),
        "ceiling_reached": ceiling.get("reached", False),
        "frontier_claimable": frontier["ceiling_claimable"],
    }


def sweep(n: int = 100, seed: int = 0) -> Dict:
    """Sweep n generated cases against the diamond."""
    results = [judge_case(*c) for c in take(n, seed)]
    pure = sum(1 for r in results if r["pure"])
    facing = sum(1 for r in results if r["facing"])
    ceiling = sum(1 for r in results if r["ceiling_reached"])
    return {
        "n": n,
        "seed": seed,
        "pure": pure,
        "facing": facing,
        "ceiling_reached": ceiling,
        "glass": n - pure,
        "results": results,
    }


def assert_diamond_invariants(cases: Iterable[Tuple[str, str, str, str]]) -> None:
    """Every case must obey: facing ⇒ pure ⇒ (rise only if foundation pure)."""
    for clarity, color, cut, reflects in cases:
        r = judge_case(clarity, color, cut, reflects)
        if r["facing"]:
            assert r["pure"], r
        if not r["pure"]:
            assert not r["facing"], r
            # impure edge facet blocks ceiling
            assert not r["ceiling_reached"], r
            assert not r["frontier_claimable"], r

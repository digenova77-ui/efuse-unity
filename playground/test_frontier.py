"""Invariant tests for the maximum frontier protocol.

Highest-order enforcement without external deps:
  faces_frontier iff clarity=FL ∧ color=D ∧ cut=Excellent ∧ reflects=purity
  ceiling_claimable iff floor holds ∧ no facet held
"""
from __future__ import annotations

import itertools
import unittest

from diamond_playground import Facet, DiamondPlayground
from frontier_protocol import faces_frontier, frontier_report, MAX_BAND

CLARITIES = ["FL", "VVS", "VS", "SI", "I"]
COLORS = list("DEFG")
CUTS = ["Excellent", "Very Good", "Good", "Fair", "Poor"]
REFLECTS = ["purity", "glass"]


class FrontierInvariants(unittest.TestCase):
    def test_faces_frontier_iff_maximum(self):
        for clarity, color, cut, reflects in itertools.product(
            CLARITIES, COLORS, CUTS, REFLECTS
        ):
            f = Facet("x", "ring", clarity, color, cut, reflects)
            expected = (
                clarity == "FL" and color == "D"
                and cut == "Excellent" and reflects == "purity"
            )
            self.assertEqual(
                faces_frontier(f), expected,
                f"failed for {clarity}/{color}/{cut}/{reflects}",
            )

    def test_ceiling_claimable_iff_all_facing(self):
        p = DiamondPlayground(facets=[
            Facet("foundation", "floor"),
            Facet("DCLM", "ring"),
            Facet("Iris", "ring"),
            Facet("ceiling", "ceiling"),
        ])
        r = frontier_report(p)
        self.assertTrue(r["ceiling_claimable"])
        self.assertEqual(r["held"], [])

        soft = Facet("soft", "tree", clarity="VS", color="E", cut="Very Good")
        p2 = DiamondPlayground(facets=[
            Facet("foundation", "floor"),
            soft,
            Facet("ceiling", "ceiling"),
        ])
        r2 = frontier_report(p2)
        self.assertFalse(r2["ceiling_claimable"])
        self.assertTrue(any(h["name"] == "soft" for h in r2["held"]))

    def test_floor_failure_blocks_ceiling(self):
        bad_floor = Facet("foundation", "floor", clarity="I", color="J", cut="Poor")
        p = DiamondPlayground(facets=[
            bad_floor,
            Facet("DCLM", "ring"),
            Facet("ceiling", "ceiling"),
        ])
        self.assertFalse(frontier_report(p)["ceiling_claimable"])

    def test_protocol_constants(self):
        self.assertEqual(MAX_BAND, {"clarity": "FL", "color": "D", "cut": "Excellent"})

    def test_default_playground_holds_soft_facets(self):
        # summer/winter are VS — pure under old gate, held under frontier
        r = frontier_report()
        held_names = {h["name"] for h in r["held"]}
        self.assertIn("summer", held_names)
        self.assertIn("winter", held_names)
        self.assertFalse(r["ceiling_claimable"])


if __name__ == "__main__":
    unittest.main()

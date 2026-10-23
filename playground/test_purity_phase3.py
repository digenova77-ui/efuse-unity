"""Purity phase 3 — wider edge cases.

Extends phase 2 with empty identities, boundary grades,
pressure invariance, and report stability.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "playground"))
sys.path.insert(0, str(ROOT / "iris-intake"))

from diamond_playground import Facet, grade, DiamondPlayground, visual_report
from frontier_protocol import faces_frontier, frontier_report


class PurityPhase3(unittest.TestCase):
    def test_empty_name_still_graded(self):
        f = Facet("", "ring")
        g = grade(f)
        self.assertTrue(g["pure"])
        self.assertTrue(faces_frontier(f))

    def test_boundary_clarity_vvs_fails_frontier(self):
        f = Facet("x", "ring", clarity="VVS", color="D", cut="Excellent")
        self.assertTrue(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_boundary_color_f_fails_frontier(self):
        f = Facet("x", "ring", clarity="FL", color="F", cut="Excellent")
        self.assertTrue(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_boundary_cut_very_good_fails_frontier(self):
        f = Facet("x", "ring", clarity="FL", color="D", cut="Very Good")
        self.assertTrue(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_pressure_does_not_change_purity(self):
        p = DiamondPlayground()
        before = frontier_report(p)
        p.apply_pressure()
        p.apply_pressure()
        after = frontier_report(p)
        self.assertEqual(before["facing"], after["facing"])
        self.assertEqual(before["held"], after["held"])
        self.assertEqual(before["ceiling_claimable"], after["ceiling_claimable"])

    def test_visual_report_contains_verdict_words(self):
        text = visual_report()
        self.assertIn("rise:", text)
        self.assertIn("ceiling:", text)
        self.assertTrue("REACHED" in text or "NOT REACHED" in text)

    def test_unknown_clarity_is_glass(self):
        f = Facet("x", "ring", clarity="UNKNOWN")
        self.assertFalse(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_multiple_impurities_all_held(self):
        facets = [
            Facet("foundation", "floor"),
            Facet("a", "ring", clarity="SI"),
            Facet("b", "tree", color="Z"),
            Facet("c", "economy", cut="Poor"),
            Facet("ceiling", "ceiling"),
        ]
        p = DiamondPlayground(facets=facets)
        r = frontier_report(p)
        held = {h["name"] for h in r["held"]}
        self.assertEqual(held, {"a", "b", "c"})
        self.assertFalse(r["ceiling_claimable"])


if __name__ == "__main__":
    unittest.main()

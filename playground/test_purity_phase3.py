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



class PurityPhase3SI2(unittest.TestCase):
    def test_si2_f_g_combination(self):
        # SI2 is below the clarity pass band (treated as non-FL/VVS/VS).
        # F is inside the color pass band.
        # G is outside the color pass band.
        # A facet carrying SI2 clarity fails regardless of color.
        # A facet carrying color G fails regardless of clarity.
        si2 = Facet("si2", "ring", clarity="SI2", color="F", cut="Excellent")
        self.assertFalse(grade(si2)["pure"])
        self.assertFalse(faces_frontier(si2))
        self.assertIn("clarity:SI2", grade(si2)["failed"])

        color_g = Facet("tint_g", "ring", clarity="FL", color="G", cut="Excellent")
        self.assertFalse(grade(color_g)["pure"])
        self.assertFalse(faces_frontier(color_g))
        self.assertIn("color:G", grade(color_g)["failed"])

        # F alone (with max other scales) still passes the old gate
        # but fails the frontier (frontier requires D).
        only_f = Facet("only_f", "ring", clarity="FL", color="F", cut="Excellent")
        self.assertTrue(grade(only_f)["pure"])
        self.assertFalse(faces_frontier(only_f))



class PurityPhase3FullSI(unittest.TestCase):
    """Full SI1/SI2 and neighboring color/cut matrix."""

    def test_si1_and_si2_never_pure(self):
        for clar in ("SI", "SI1", "SI2"):
            for color in ("D", "E", "F", "G"):
                for cut in ("Excellent", "Very Good", "Good"):
                    f = Facet("x", "ring", clarity=clar, color=color, cut=cut)
                    self.assertFalse(grade(f)["pure"], f"{clar}/{color}/{cut}")
                    self.assertFalse(faces_frontier(f))
                    self.assertTrue(any(s.startswith("clarity:") for s in grade(f)["failed"]))

    def test_color_g_and_beyond_never_pure(self):
        for color in ("G", "H", "I", "J"):
            f = Facet("x", "ring", clarity="FL", color=color, cut="Excellent")
            self.assertFalse(grade(f)["pure"])
            self.assertIn(f"color:{color}", grade(f)["failed"])
            self.assertFalse(faces_frontier(f))

    def test_f_passes_old_gate_only_at_max_other_scales(self):
        # F + FL + Excellent → old pass, frontier fail
        ok = Facet("ok", "ring", clarity="FL", color="F", cut="Excellent")
        self.assertTrue(grade(ok)["pure"])
        self.assertFalse(faces_frontier(ok))
        # F + VVS → still old pass
        vvs = Facet("v", "ring", clarity="VVS", color="F", cut="Excellent")
        self.assertTrue(grade(vvs)["pure"])
        self.assertFalse(faces_frontier(vvs))
        # F + SI2 → old fail
        si = Facet("s", "ring", clarity="SI2", color="F", cut="Excellent")
        self.assertFalse(grade(si)["pure"])

    def test_i1_i2_i3_are_glass(self):
        for clar in ("I", "I1", "I2", "I3"):
            f = Facet("x", "ring", clarity=clar, color="D", cut="Excellent")
            self.assertFalse(grade(f)["pure"])
            self.assertFalse(faces_frontier(f))



class PurityPhase3MoreEdges(unittest.TestCase):
    def test_whitespace_reflects_is_glass(self):
        f = Facet("x", "ring", reflects=" purity")
        self.assertFalse(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_lowercase_grades_fail(self):
        f = Facet("x", "ring", clarity="fl", color="d", cut="excellent")
        self.assertFalse(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_empty_cut_is_glass(self):
        f = Facet("x", "ring", cut="")
        self.assertFalse(grade(f)["pure"])
        self.assertIn("cut:", "".join(grade(f)["failed"]))

    def test_all_max_except_one_scale(self):
        cases = [
            Facet("c", "ring", clarity="VS"),
            Facet("o", "ring", color="E"),
            Facet("u", "ring", cut="Very Good"),
            Facet("r", "ring", reflects="other"),
        ]
        for f in cases:
            self.assertFalse(faces_frontier(f), f.name)

    def test_duplicate_facets_all_judged(self):
        facets = [
            Facet("foundation", "floor"),
            Facet("dup", "ring", clarity="SI2"),
            Facet("dup", "ring", clarity="SI2"),
            Facet("ceiling", "ceiling"),
        ]
        p = DiamondPlayground(facets=facets)
        r = frontier_report(p)
        self.assertEqual(len(r["held"]), 2)
        self.assertFalse(r["ceiling_claimable"])

    def test_visual_report_marks_glass(self):
        bad = Facet("bad", "economy", clarity="I", color="Z", cut="Poor")
        p = DiamondPlayground(facets=[
            Facet("foundation", "floor"),
            bad,
            Facet("ceiling", "ceiling"),
        ])
        text = visual_report(p)
        self.assertIn("◇", text)
        self.assertIn("REFUSED", text)
        self.assertIn("NOT REACHED", text)


if __name__ == "__main__":
    unittest.main()

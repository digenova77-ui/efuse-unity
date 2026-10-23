"""Focused tests for the purity decision logic."""
from __future__ import annotations

import unittest

from diamond_playground import Facet, grade, _pure, CLARITY_PASS, COLOR_PASS, CUT_PASS


class PurityLogicTests(unittest.TestCase):
    def test_all_pass_bands_pure(self):
        for c in CLARITY_PASS:
            for o in COLOR_PASS:
                for u in CUT_PASS:
                    f = Facet("x", "ring", c, o, u, "purity")
                    self.assertTrue(grade(f)["pure"], f"{c}/{o}/{u}")
                    self.assertTrue(_pure(f))
                    self.assertEqual(grade(f)["verdict"], "PASS")
                    self.assertEqual(grade(f)["failed"], [])

    def test_one_failed_scale_is_glass(self):
        cases = [
            Facet("c", "ring", clarity="SI"),
            Facet("o", "ring", color="G"),
            Facet("u", "ring", cut="Fair"),
            Facet("r", "ring", reflects="glass"),
        ]
        for f in cases:
            g = grade(f)
            self.assertFalse(g["pure"])
            self.assertEqual(g["verdict"], "GLASS")
            self.assertTrue(len(g["failed"]) >= 1)
            self.assertFalse(_pure(f))

    def test_failed_list_names_scales(self):
        f = Facet("x", "ring", clarity="SI2", color="J", cut="Poor", reflects="x")
        failed = grade(f)["failed"]
        self.assertIn("clarity:SI2", failed)
        self.assertIn("color:J", failed)
        self.assertIn("cut:Poor", failed)
        self.assertIn("reflects:not-purity", failed)

    def test_scores_present(self):
        f = Facet("x", "ring")
        g = grade(f)
        for scale in ("clarity", "color", "cut"):
            self.assertIn("score", g[scale])
            self.assertIn("pass", g[scale])
            self.assertIn("value", g[scale])

    def test_pure_wrapper_matches_grade(self):
        samples = [
            Facet("a", "ring"),
            Facet("b", "ring", clarity="VS", color="E", cut="Very Good"),
            Facet("c", "ring", clarity="I"),
        ]
        for f in samples:
            self.assertEqual(_pure(f), grade(f)["pure"])


if __name__ == "__main__":
    unittest.main()

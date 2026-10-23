"""Infinite edge-case sweep.

Runs N generated cases (default 500) and asserts the
core invariants hold for every one.
"""
from __future__ import annotations

import unittest

from diamond_playground import Facet, grade
from frontier_protocol import faces_frontier, MAX_BAND
from edge_generator import take, all_combinations


class InfiniteEdges(unittest.TestCase):
    def test_generated_sweep(self):
        for clarity, color, cut, reflects in take(500, seed=42):
            f = Facet("g", "ring", clarity, color, cut, reflects)
            g = grade(f)
            facing = faces_frontier(f)
            # Facing implies pure
            if facing:
                self.assertTrue(g["pure"])
                self.assertEqual(clarity, MAX_BAND["clarity"])
                self.assertEqual(color, MAX_BAND["color"])
                self.assertEqual(cut, MAX_BAND["cut"])
                self.assertEqual(reflects, "purity")
            # Not max band implies not facing
            is_max = (
                clarity == "FL" and color == "D"
                and cut == "Excellent" and reflects == "purity"
            )
            self.assertEqual(facing, is_max)

    def test_full_cartesian_sample(self):
        # First 200 of the cartesian product
        for i, (clarity, color, cut, reflects) in enumerate(all_combinations()):
            if i >= 200:
                break
            f = Facet("c", "ring", clarity, color, cut, reflects)
            facing = faces_frontier(f)
            is_max = (
                clarity == "FL" and color == "D"
                and cut == "Excellent" and reflects == "purity"
            )
            self.assertEqual(facing, is_max)

    def test_reproducible(self):
        a = take(20, seed=7)
        b = take(20, seed=7)
        c = take(20, seed=8)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()

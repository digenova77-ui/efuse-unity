"""Edge cases tested against the full diamond."""
from __future__ import annotations

import unittest

from diamond_edge import judge_case, sweep, assert_diamond_invariants
from edge_generator import take


class DiamondEdgeTests(unittest.TestCase):
    def test_max_case_reaches(self):
        r = judge_case("FL", "D", "Excellent", "purity")
        self.assertTrue(r["pure"])
        self.assertTrue(r["facing"])
        self.assertTrue(r["rise_ok"])
        self.assertTrue(r["ceiling_reached"])
        self.assertTrue(r["frontier_claimable"])

    def test_si2_blocks_ceiling(self):
        r = judge_case("SI2", "F", "Excellent", "purity")
        self.assertFalse(r["pure"])
        self.assertFalse(r["facing"])
        self.assertFalse(r["ceiling_reached"])
        self.assertFalse(r["frontier_claimable"])

    def test_sweep_invariants(self):
        assert_diamond_invariants(take(200, seed=1))

    def test_sweep_summary(self):
        s = sweep(100, seed=2)
        self.assertEqual(s["n"], 100)
        self.assertGreaterEqual(s["glass"], 0)
        self.assertLessEqual(s["facing"], s["pure"])
        self.assertLessEqual(s["ceiling_reached"], s["n"])


if __name__ == "__main__":
    unittest.main()

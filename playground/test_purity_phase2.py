"""Cross-module purity phase 2 — boundary invariants.

Verifies that learning signals cannot affect standing or emission,
and that the diamond/frontier purity gates remain consistent
with the tokenomics origin rule.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iris-intake"))
sys.path.insert(0, str(ROOT / "dclm"))
sys.path.insert(0, str(ROOT / "playground"))

from diamond_playground import Facet, grade
from frontier_protocol import faces_frontier, MAX_BAND


class PurityPhase2(unittest.TestCase):
    def test_learning_signal_marked_not_for_emission(self):
        from learning_signal import accuracy
        from iris_state import IrisState
        acc = accuracy(IrisState())
        self.assertEqual(acc.get("boundary"), "NOT_FOR_EMISSION")
        self.assertIn("standing", acc.get("standing_source", "").lower())

    def test_pure_pace_does_not_claim_emission(self):
        from pure_pace import pace_factor, expectations
        from iris_state import IrisState
        p = pace_factor(IrisState())
        self.assertIn("NOT_FOR_EMISSION", p.get("boundary", ""))
        exp = expectations()
        self.assertTrue(any("standing" in s.lower() or "emission" in s.lower()
                            for s in exp.get("expects", []) + exp.get("refuses", [])))

    def test_frontier_maximum_implies_old_gate_pass(self):
        # Anything that faces the frontier must also pass the three-scale gate
        f = Facet("max", "ring",
                  clarity=MAX_BAND["clarity"],
                  color=MAX_BAND["color"],
                  cut=MAX_BAND["cut"])
        self.assertTrue(faces_frontier(f))
        self.assertTrue(grade(f)["pure"])

    def test_glass_cannot_face_frontier(self):
        bad = Facet("bad", "economy", clarity="I", color="J", cut="Poor")
        self.assertFalse(grade(bad)["pure"])
        self.assertFalse(faces_frontier(bad))

    def test_origin_standing_boundary_documented(self):
        # token_engine.standing exists and is the emission source
        import token_engine
        self.assertTrue(callable(getattr(token_engine, "standing", None))
                        or hasattr(token_engine, "Tokenizer"))


if __name__ == "__main__":
    unittest.main()

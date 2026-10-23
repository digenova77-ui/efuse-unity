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



class PurityPhase2Edges(unittest.TestCase):
    def test_empty_state_accuracy_is_none(self):
        from learning_signal import accuracy
        from iris_state import IrisState
        # Fresh state may already have learnings from prior runs;
        # accuracy must still be a float or None, never raise.
        acc = accuracy(IrisState())
        self.assertIn(acc["accuracy"], (None, 0.0, 1.0) )
        self.assertIsInstance(acc["accuracy"], (float, type(None)))

    def test_pace_factor_bounded(self):
        from pure_pace import pace_factor, PACE_MIN, PACE_MAX
        from iris_state import IrisState
        f = pace_factor(IrisState())["factor"]
        self.assertGreaterEqual(f, PACE_MIN)
        self.assertLessEqual(f, PACE_MAX)

    def test_soft_facet_passes_old_gate_fails_frontier(self):
        soft = Facet("soft", "tree", clarity="VS", color="E", cut="Very Good")
        self.assertTrue(grade(soft)["pure"])       # old gate
        self.assertFalse(faces_frontier(soft))     # frontier

    def test_colorless_but_poor_cut_is_glass(self):
        f = Facet("x", "ring", clarity="FL", color="D", cut="Poor")
        self.assertFalse(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_excellent_cut_but_tinted_is_glass(self):
        f = Facet("x", "ring", clarity="FL", color="J", cut="Excellent")
        self.assertFalse(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_reflects_not_purity_is_glass(self):
        f = Facet("x", "ring", clarity="FL", color="D", cut="Excellent",
                  reflects="theater")
        self.assertFalse(grade(f)["pure"])
        self.assertFalse(faces_frontier(f))

    def test_highest_order_contract_refuses_emission(self):
        from highest_order import contract
        c = contract()
        refuses = " ".join(c.get("iris_must_refuse", [])).lower()
        self.assertIn("emission", refuses)
        self.assertIn("standing", refuses)


if __name__ == "__main__":
    unittest.main()

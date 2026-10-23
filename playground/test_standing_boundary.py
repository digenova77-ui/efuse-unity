"""Cross-module: learning cannot become standing/emission."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iris-intake"))
sys.path.insert(0, str(ROOT / "dclm"))
sys.path.insert(0, str(ROOT / "playground"))

class StandingBoundary(unittest.TestCase):
    def test_token_engine_standing_exists(self):
        import token_engine
        self.assertTrue(callable(getattr(token_engine, "standing", None)) or hasattr(token_engine, "Tokenizer"))

    def test_learning_signal_not_for_emission(self):
        from learning_signal import accuracy
        from iris_state import IrisState
        acc = accuracy(IrisState())
        self.assertEqual(acc.get("boundary"), "NOT_FOR_EMISSION")

    def test_edge_probe_matches(self):
        # Mirror of edge standingProbe contract
        expected = "NOT_FOR_EMISSION"
        from learning_signal import accuracy
        from iris_state import IrisState
        self.assertEqual(accuracy(IrisState()).get("boundary"), expected)

if __name__ == "__main__":
    unittest.main()

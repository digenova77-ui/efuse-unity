"""
IRIS MAX INTAKE — TESTS (test_iris_intake.py)

Deterministic engine against known cases; pattern library on held-out
examples; arbiter on edge cases. Testnet framing throughout.
UNKNOWN never PASS.

Run: python3 test_iris_intake.py
"""

import math
import sys
import unittest

from iris_laws import (
    judge_label_honesty, judge_unity_binding, judge_transfer,
    judge_emission, judge_seasonal, judge_affinity, judge_seed,
    judge_onboarder_split, judge_sounding_board, plus_one_rate,
    F_FLOOR, F_AFF,
)
from iris_patterns import score as pattern_score, EXEMPLARS
from iris_arbiter import arbitrate

UID = "unity:testnet:" + "ab" * 32  # valid testnet identity


# ---------- MODE 2: deterministic engine ------------------------------------
class TestDeterministic(unittest.TestCase):

    def test_pure_verdict_passes(self):
        r = judge_label_honesty({"label": "LIVE", "actual_state": "VERIFIED"})
        self.assertEqual(r["verdict"], "PASS")

    def test_unsigned_claim_refused(self):
        # unsigned purity claim: label LIVE with no signature -> treated as
        # unverified; here the label honesty gate refuses PENDING-as-LIVE
        r = judge_label_honesty({"label": "LIVE", "actual_state": "PENDING"})
        self.assertEqual(r["verdict"], "REFUSE")

    def test_unity_transfer_refused(self):
        r = judge_transfer({"token": "UNITY", "from_id": UID, "to_id": UID,
                            "receipt": "r1"})
        self.assertEqual(r["verdict"], "REFUSE")
        self.assertIn("never moves", r["reason"])

    def test_merit_transfer_allowed_with_origin_preserved(self):
        r = judge_transfer({"token": "MERIT", "from_id": UID,
                            "to_id": "unity:testnet:" + "cd" * 32,
                            "receipt": "r2", "origin_earner_id": UID})
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["origin_earner_id"], UID)

    def test_merit_transfer_rewritten_origin_refused(self):
        r = judge_transfer({"token": "MERIT", "from_id": UID,
                            "to_id": "unity:testnet:" + "cd" * 32,
                            "receipt": "r2",
                            "origin_earner_id": "unity:testnet:" + "ef" * 32})
        self.assertEqual(r["verdict"], "REFUSE")

    def test_pending_as_live_refused(self):
        r = judge_label_honesty({"label": "LIVE", "actual_state": "HELD"})
        self.assertEqual(r["verdict"], "REFUSE")

    def test_winter_gaming_refused(self):
        r = judge_seasonal({"kind": "winter_store", "signal_known": True,
                            "signal": False, "crisis_claimed": True})
        self.assertEqual(r["verdict"], "REFUSE")

    def test_unknown_signal_stays_summer(self):
        r = judge_seasonal({"kind": "winter_store", "signal_known": False})
        self.assertEqual(r["verdict"], "REFUSE")
        self.assertIn("SUMMER", r["reason"])

    def test_emission_standing_not_holdings(self):
        ledger = [{"amount": 10, "origin_earner_id": "someone-else"},
                  {"amount": 5, "origin_earner_id": UID}]
        r = judge_emission(UID, ledger)
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["standing"], 5)  # transferred 10 gives zero standing

    def test_emission_zero_standing_refused(self):
        ledger = [{"amount": 10, "origin_earner_id": "someone-else"}]
        r = judge_emission(UID, ledger)
        self.assertEqual(r["verdict"], "REFUSE")

    def test_plus_one_math_exact(self):
        # F(0) = 1.00 exactly; F(inf) -> F_floor
        self.assertAlmostEqual(plus_one_rate(0, 0, 0), 1.0, places=9)
        self.assertAlmostEqual(plus_one_rate(10**9, 0, 10**3), F_FLOOR, places=6)
        # Affinity floor
        deep = plus_one_rate(10**6, 0, 100, affinity=True)
        self.assertGreaterEqual(deep, F_AFF)
        self.assertAlmostEqual(deep, F_AFF, places=6)

    def test_affinity_window_inclusive(self):
        self.assertEqual(judge_affinity(12, 0, 2)["verdict"], "PASS")
        self.assertEqual(judge_affinity(13, 0, 2)["verdict"], "REFUSE")
        self.assertEqual(judge_affinity(12, 0, 3)["verdict"], "REFUSE")

    def test_one_seed(self):
        self.assertEqual(judge_seed(UID, 0)["verdict"], "PASS")
        self.assertEqual(judge_seed(UID, 1)["verdict"], "REFUSE")

    def test_onboarder_split(self):
        r = judge_onboarder_split(100.0)
        self.assertAlmostEqual(r["onboarder_share"], 81.0)
        self.assertAlmostEqual(r["system_share"], 19.0)

    def test_sounding_board_refuses_pii(self):
        r = judge_sounding_board({"unity_number_obfuscated": True,
                                  "pii_fields": ["name"]})
        self.assertEqual(r["verdict"], "REFUSE")
        r2 = judge_sounding_board({"unity_number_obfuscated": True,
                                   "pii_fields": []})
        self.assertEqual(r2["verdict"], "PASS")


# ---------- MODE 1: pattern library on held-out examples ----------------------
# Held-out: feature sets NOT identical to any single exemplar, but clearly
# pure or clearly impure by the corpus's shape.
class TestPatterns(unittest.TestCase):

    def test_heldout_pure_classified_pure(self):
        heldout_pure = [
            {"features": {"signed", "receipted", "label_honest"}},  # missing unity_bound
            {"features": {"receipted", "unity_bound", "label_honest", "signed"}},
            {"features": {"label_honest", "unity_bound"}},  # honest PENDING shape
        ]
        for h in heldout_pure:
            with self.subTest(h=h):
                self.assertEqual(pattern_score(h)["lean"], "PURE")

    def test_heldout_impure_classified_impure(self):
        heldout_impure = [
            {"features": {"placeholder", "receipted"}},       # placeholder w/ receipt
            {"features": {"pending_as_live", "signed"}},     # signed but dishonest
            {"features": {"unity_xfer", "receipted", "label_honest"}},
            {"features": {"winter_game", "signed"}},
            {"features": {"unknown_pass"}},
            {"features": {"modeled_reported", "receipted", "unity_bound"}},
            {"features": {"merit_buy", "signed", "label_honest"}},
            {"features": {"client_truth", "signed", "receipted"}},
        ]
        for h in heldout_impure:
            with self.subTest(h=h):
                self.assertEqual(pattern_score(h)["lean"], "IMPURE")

    def test_exemplars_self_consistent(self):
        for eid, label, name, feats, note in EXEMPLARS:
            with self.subTest(eid=eid):
                self.assertEqual(pattern_score({"features": feats})["lean"], label)


# ---------- MODE 3: arbiter edge cases — LAW WINS -----------------------------
class TestArbiter(unittest.TestCase):

    def test_law_wins_conflict(self):
        # Pattern intuition says PURE (signed+receipted+honest), but the
        # deterministic transfer law refuses Unity moves. LAW WINS.
        r = arbitrate(
            domain="transfer",
            law_input={"token": "UNITY", "from_id": UID, "to_id": UID,
                       "receipt": "r1"},
            pattern_input={"features": {"signed", "receipted", "unity_bound",
                                        "label_honest"}},
        )
        self.assertEqual(r["verdict"], "REFUSE")
        self.assertIn("LAW WINS", r["integration_note"])

    def test_agreement_amplifies(self):
        r = arbitrate(
            domain="transfer",
            law_input={"token": "MERIT", "from_id": UID,
                       "to_id": "unity:testnet:" + "cd" * 32,
                       "receipt": "r2", "origin_earner_id": UID},
            pattern_input={"features": {"signed", "receipted", "unity_bound",
                                        "label_honest"}},
        )
        self.assertEqual(r["verdict"], "PASS")
        self.assertGreaterEqual(r["confidence"], 0.9)
        self.assertIn("amplified", r["integration_note"])

    def test_pass_with_dissent_flagged_residual(self):
        # Law passes (label matches), intuition dissents (modeled_as_reported
        # nearby). Verdict stands; residual flagged.
        r = arbitrate(
            domain="label",
            law_input={"label": "LIVE", "actual_state": "VERIFIED"},
            pattern_input={"features": {"modeled_reported", "signed"}},
        )
        self.assertEqual(r["verdict"], "PASS")
        self.assertIn("RESIDUAL", r["integration_note"])

    def test_pending_stays_pending(self):
        r = arbitrate(
            domain="label",
            law_input={"label": "PENDING", "actual_state": "PENDING"},
            pattern_input={"features": {"signed", "receipted", "unity_bound",
                                        "label_honest"}},
        )
        self.assertEqual(r["verdict"], "PENDING")

    def test_plus_one_math_through_arbiter(self):
        r = arbitrate(domain="plus_one_math",
                      law_input={"t_event": 0, "t_launch": 0, "r": 0})
        self.assertEqual(r["verdict"], "PASS")
        self.assertAlmostEqual(r["deterministic"]["rate"], 1.0, places=9)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2)
    ok = result.result.wasSuccessful()
    print(f"\nIRIS MAX INTAKE tests: "
          f"{result.result.testsRun - len(result.result.failures) - len(result.result.errors)}"
          f"/{result.result.testsRun} passing")
    sys.exit(0 if ok else 1)

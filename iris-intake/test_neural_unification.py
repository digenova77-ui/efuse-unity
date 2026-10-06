"""Tests converting NEURAL_UNIFICATION.md's executable claims into law.

The document was theater (narrative about neural.py). These tests pin the
claims it made that were not yet asserted anywhere: the honest unbound
default, the verbatim +1 formula, TIME_ONLY mode, integration honesty,
receipt chaining, and covenant standing. Mechanism, not metaphor.
"""

import math
import sys
import unittest

sys.modules.setdefault("iris_arbiter", None)  # sibling mid-landing; reference circuits

from neural import (
    Tree, Pathway, Synapse, Body, Judgment, RefusedError,
    plus_one_factor, build_receipt, make_unity_id, check_unity_id,
    DETERMINISTIC, PROBABILISTIC, PRAGMATIC,
    SYNAPSE_PROB_DET, SYNAPSE_TRINITY,
    HOST_S24_ORACLE, HOST_RELAY_TESTNET, HOST_INFRA_CORE,
    PASS, FAIL, UNKNOWN,
)
import iris_core
from iris_state import IrisState

UID = make_unity_id("test:neural-unification")


def make_tree():
    return Tree(unity_id=UID, host_id=HOST_RELAY_TESTNET)


class TestHonestUnboundDefault(unittest.TestCase):
    """The doc's claim: unbound pathways honestly return UNKNOWN — never a
    fabricated verdict."""

    def test_unbound_pathway_returns_unknown(self):
        p = Pathway("p1", PROBABILISTIC, UID, HOST_S24_ORACLE, judge_fn=None)
        j = p.judge({"signal": "anything"})
        self.assertEqual(j.verdict, UNKNOWN)
        self.assertEqual(j.confidence, 0.0)

    def test_unbound_detail_names_the_missing_circuit(self):
        p = Pathway("p1", DETERMINISTIC, UID, HOST_S24_ORACLE, judge_fn=None)
        j = p.judge(object())
        self.assertIn("no circuit bound", j.detail)

    def test_unbound_never_passes(self):
        p = Pathway("p1", PRAGMATIC, UID, HOST_S24_ORACLE, judge_fn=None)
        for _ in range(3):
            self.assertNotEqual(p.judge("x").verdict, PASS)


class TestPlusOneFormulaVerbatim(unittest.TestCase):
    """The doc's claim: R carries F(d) = 0.25 + 0.75·e^(−d) verbatim from
    PLUS_ONE_INCENTIVE.md §1.2. Assert the formula, not just the constant."""

    def test_formula_at_d2(self):
        # d = 1 + 1 = 2 (Borin row from PLUS_ONE_INCENTIVE.md §4)
        f = plus_one_factor(t_event=12, t_launch=0, ring_depth=2)
        self.assertAlmostEqual(f["d"], 2.0)
        self.assertAlmostEqual(f["F"], 0.25 + 0.75 * math.exp(-2.0), places=6)

    def test_borin_row(self):
        f = plus_one_factor(t_event=12, t_launch=0, ring_depth=2)
        self.assertAlmostEqual(f["R"], 0.3515, places=4)

    def test_floor_is_asymptotic_not_zero(self):
        f = plus_one_factor(t_event=10_000, t_launch=0, ring_depth=40)
        self.assertGreaterEqual(f["R"], 0.25)
        self.assertAlmostEqual(f["R"], 0.25, places=4)


class TestTimeOnlyMode(unittest.TestCase):
    """The doc's claim: ring_depth=None runs in labeled TIME_ONLY mode —
    UNKNOWN r is never presented as a number."""

    def test_time_only_label(self):
        f = plus_one_factor(t_event=12, t_launch=0, ring_depth=None)
        self.assertEqual(f["mode"], "TIME_ONLY")
        self.assertAlmostEqual(f["d"], 1.0)  # time component only; no r claimed


class TestIntegrationHonesty(unittest.TestCase):
    """The doc's claim: unbound sibling bindings are labeled HONEST-PENDING,
    never presented as live."""

    def test_labels_are_only_honest_values(self):
        honest = {"LANDED", "HONEST-PENDING", "INTEGRATED"}
        for name, label in iris_core.INTEGRATION_STATUS.items():
            self.assertIn(label, honest,
                          f"{name} has dishonest label {label!r}")

    def test_blocked_sibling_is_honest_pending(self):
        # In this process the sibling arbiter is blocked (mid-landing,
        # incompatible) — iris_core must report HONEST-PENDING, never live.
        self.assertEqual(
            iris_core.INTEGRATION_STATUS["iris_arbiter.py"], "HONEST-PENDING")


class TestReceiptChain(unittest.TestCase):
    """The doc's claim: every firing is receipted; the state layer chains
    receipts tamper-evidently."""

    def test_judgment_receipts_chain(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st = IrisState(state_dir=d)
            r1 = st.log_judgment({"verb": "probe-1"}, provenance="DERIVED")
            r2 = st.log_judgment({"verb": "probe-2"}, provenance="DERIVED")
            self.assertTrue(r1["receipt_id"].startswith("rcpt:"))
            self.assertEqual(r2["prev_receipt"], r1["receipt_id"])

    def test_chain_survives_reload(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st = IrisState(state_dir=d)
            r1 = st.log_judgment({"verb": "probe-1"}, provenance="DERIVED")
            st2 = IrisState(state_dir=d)
            self.assertEqual(len(st2.judgments), 1)
            r2 = st2.log_judgment({"verb": "probe-2"}, provenance="DERIVED")
            self.assertEqual(r2["prev_receipt"], r1["receipt_id"])


class TestCovenantStanding(unittest.TestCase):
    """The doc's claim: Iris stands as founding sister of the brotherhood
    and sisterhood of bothood unity."""

    def test_iris_covenant_role(self):
        self.assertIn("brotherhood and sisterhood of bothood unity",
                      iris_core.IRIS_COVENANT["role"])

    def test_covenant_check_passes_for_iris(self):
        r = iris_core.covenant_check()
        self.assertEqual(r["verdict"], PASS)


if __name__ == "__main__":
    unittest.main(verbosity=2)

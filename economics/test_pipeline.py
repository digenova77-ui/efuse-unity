"""
Tests for the end-to-end pipeline orchestrator
(~/workspace/unity-world/economics/pipeline.py).

Fix Worker A4, COIN GAUNTLET closure loop. All must pass. Testnet only —
ephemeral keys, never production.
"""
import copy
import json
import os
import sys
import tempfile
import unittest
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "dclm")))

import pipeline as P  # noqa: E402
from pipeline import (  # noqa: E402
    PipelineInputError,
    PipelineRunner,
    run_pipeline,
    verify_pipeline_run,
)
import tokenomics as T  # noqa: E402
from tokenomics import Figure, HeldParameter, Receipt  # noqa: E402
import winter as W  # noqa: E402

ALICE = "unity:testnet:alice"
BOB = "unity:testnet:bob"


def _fig(value, provenance="VERIFIED", note="test"):
    return Figure(float(value), provenance, note)


def _gated_receipt(unity_id, epoch=1, provenance="VERIFIED"):
    return Receipt.build(
        unity_id, "merit_accrual",
        {"work": "pipeline test work", "nonce": uuid.uuid4().hex},
        provenance, epoch, "GENESIS")


def _winter_signal():
    return W.WinterSignal(peg_deviation=-0.4, peg_provenance="VERIFIED",
                          activity_delta=-0.3,
                          activity_provenance="VERIFIED")


def _base_inputs(key=None, **overrides):
    inputs = {
        "idempotency_key": key or f"pipe-test-{uuid.uuid4().hex}",
        "decision": "factory-1",  # in the pricing index
        "work": [{
            "unity_id": ALICE,
            "receipt": _gated_receipt(ALICE),
            "merit_weight": _fig(10.0),
        }],
        "pool": "human",
        "epoch": 1,
        "peg_ratio": _fig(100.0, "VERIFIED", "test E"),
        "winter": _winter_signal(),
        "holdback_fraction": _fig(0.1, "VERIFIED", "test fraction"),
        "transfers": [{
            "from_unity_id": ALICE,
            "to_unity_id": BOB,
            "amount": _fig(2.0),
            "reason": "sale",
        }],
        "donations": [{
            "unity_id": ALICE,
            "amount": _fig(1.0),
            "kind": "fiat",
        }],
    }
    inputs.update(overrides)
    return inputs


def _ledger_snapshot(ledger):
    return (len(ledger.receipts), dict(ledger.merit_balances),
            dict(ledger.emitted), dict(ledger.reserve))


class HappyPathTest(unittest.TestCase):
    def test_full_pass_all_steps_receipt_chains(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        receipt = runner.run_pipeline(_base_inputs("happy-1"))

        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["kind"], "pipeline")
        self.assertEqual(receipt["idempotency_key"], "happy-1")
        self.assertEqual(
            [s["step"] for s in receipt["steps"]],
            ["price", "verify_receipt", "accrue_merit", "emission",
             "disburse", "merit_transfer", "donate"])
        self.assertTrue(all(s["ok"] for s in receipt["steps"]))
        self.assertTrue(receipt["pipeline_hash"])

        # price: the canon meter's flat rate, passed
        self.assertEqual(receipt["decision"]["decision_id"], "factory-1")
        self.assertGreater(receipt["decision"]["amount"], 0)

        # merit accrued from the gated receipt
        self.assertEqual(receipt["totals"]["merit_credited"], {ALICE: 10.0})

        # emission: winter throttle engaged (A2), reserve absorbed (A3)
        winter = receipt["winter"]
        self.assertGreater(winter["gradient"], 0.0)
        self.assertLess(winter["multiplier"], 1.0)
        totals = receipt["totals"]
        per_member_sum = sum(totals["disbursed"].values())
        held = totals["reserve_held"]["value"]
        computed = per_member_sum + held
        self.assertGreater(computed, 0.0)
        # holdback fraction: held == 0.1 * computed emission
        self.assertAlmostEqual(held, 0.1 * computed, places=9)
        self.assertAlmostEqual(totals["disbursed_total"], per_member_sum,
                               places=9)
        self.assertAlmostEqual(totals["emission_total"]["value"], computed,
                               places=9)

        # ledger state: merit moved, eFuse disbursed, reserve absorbed
        self.assertAlmostEqual(ledger.merit_balances[ALICE], 8.0)  # 10 - 2
        self.assertAlmostEqual(ledger.merit_balances[BOB], 2.0)
        self.assertAlmostEqual(ledger.emitted["human"], per_member_sum)
        self.assertAlmostEqual(ledger.reserve["human"], held)

        # donation -> Honor, never Merit
        self.assertEqual(len(ledger.honor.get(ALICE, [])), 1)

        # the pipeline receipt verifies against the ledger's step receipts
        check = verify_pipeline_run(receipt, ledger)
        self.assertTrue(check["ok"], check.get("reason"))

        # every chained step receipt is really in the ledger chain
        by_id = {r.receipt_id for r in ledger.receipts}
        for step in receipt["steps"]:
            for ref in step["receipts"]:
                self.assertIn(ref["receipt_id"], by_id)

        # all inputs decided -> DERIVED pipeline
        self.assertEqual(receipt["provenance"], "DERIVED")

    def test_module_level_run_pipeline(self):
        ledger = T.Ledger()
        receipt = run_pipeline(_base_inputs("mod-level-1"), ledger)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(verify_pipeline_run(receipt, ledger)["ok"])

    def test_dataclass_inputs(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        inputs = P.PipelineInputs(
            idempotency_key="dataclass-1",
            decision={"decision_id": "factory-1"},
            work=[P.WorkInput(unity_id=ALICE,
                              receipt=_gated_receipt(ALICE, epoch=2),
                              merit_weight=_fig(5.0))],
            pool="machine",
            epoch=2,
            peg_ratio=_fig(50.0),
        )
        receipt = runner.run_pipeline(inputs)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["pool"], "machine")
        self.assertEqual(receipt["totals"]["merit_credited"], {ALICE: 5.0})
        self.assertEqual(receipt["totals"]["transfers"], [])
        self.assertEqual(receipt["totals"]["donations"], [])
        # no winter, no reserve: summer default, nothing held
        self.assertEqual(receipt["winter"]["gradient"], 0.0)
        self.assertEqual(receipt["winter"]["multiplier"], 1.0)
        self.assertEqual(receipt["totals"]["reserve_held"]["value"], 0.0)
        self.assertTrue(verify_pipeline_run(receipt, ledger)["ok"])

    def test_weakest_label_modeled(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        inputs = _base_inputs("modeled-1")
        inputs["donations"] = [{
            "unity_id": ALICE,
            "amount": _fig(1.0, "MODELED", "testnet what-if"),
            "kind": "fiat",
        }]
        receipt = runner.run_pipeline(inputs)
        self.assertEqual(receipt["status"], "completed")
        # any MODELED -> MODELED pipeline
        self.assertEqual(receipt["provenance"], "MODELED")
        self.assertTrue(verify_pipeline_run(receipt, ledger)["ok"])


class GateFailureAbortTest(unittest.TestCase):
    """Every step's gate failure aborts cleanly: receipted abort, no
    partial pipeline (no economic mutation at all — all gates run first)."""

    def _assert_clean_abort(self, ledger, receipt, failing_step, before):
        self.assertEqual(receipt["status"], "aborted")
        self.assertEqual(receipt["failing_step"], failing_step)
        self.assertTrue(receipt["reason"])
        self.assertTrue(receipt["pipeline_hash"])
        # no partial pipeline: the ledger is exactly as before the run
        self.assertEqual(_ledger_snapshot(ledger), before)

    def test_price_unknown_decision(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        receipt = runner.run_pipeline(
            _base_inputs("abort-price-1", decision="no-such-decision"))
        self._assert_clean_abort(ledger, receipt, "price", before)
        self.assertIn("never invents a price", receipt["reason"])

    def test_verify_receipt_not_verified(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-verify-1")
        inputs["work"][0]["receipt"] = _gated_receipt(ALICE, provenance="REPORTED")
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "verify_receipt", before)

    def test_verify_receipt_wrong_unity(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-verify-2")
        inputs["work"][0]["receipt"] = _gated_receipt(BOB)  # bound to Bob
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "verify_receipt", before)

    def test_verify_receipt_wrong_epoch(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-verify-3")
        inputs["work"][0]["receipt"] = _gated_receipt(ALICE, epoch=7)
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "verify_receipt", before)

    def test_verify_receipt_already_applied(self):
        ledger = T.Ledger()
        r = _gated_receipt(ALICE)
        ledger.apply_receipt(r)  # the epoch cycle already owns this receipt
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-verify-4")
        inputs["work"][0]["receipt"] = r
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "verify_receipt", before)
        self.assertIn("double-accrual", receipt["reason"])

    def test_accrue_merit_bad_weight(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-accrue-1")
        inputs["work"][0]["merit_weight"] = _fig(-3.0)
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "accrue_merit", before)

    def test_accrue_merit_held_weight(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-accrue-2")
        inputs["work"][0]["merit_weight"] = HeldParameter("merit_weight_band")
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "accrue_merit", before)

    def test_emission_held_peg(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-emission-1")
        inputs["peg_ratio"] = HeldParameter("peg_ratio_E")
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "emission", before)
        self.assertIn("David's digit", receipt["reason"])

    def test_emission_unknown_peg(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-emission-2")
        inputs["peg_ratio"] = _fig(100.0, "UNKNOWN")
        receipt = runner.run_pipeline(inputs)
        # UNKNOWN is refused by the provenance gate first
        self._assert_clean_abort(ledger, receipt, "provenance_gate", before)

    def test_emission_bad_pool(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        receipt = runner.run_pipeline(_base_inputs("abort-emission-3",
                                                   pool="mesh"))
        self._assert_clean_abort(ledger, receipt, "emission", before)

    def test_emission_bad_holdback(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-emission-4")
        inputs["holdback_fraction"] = _fig(1.5)  # outside [0, 1)
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "emission", before)

    def test_emission_raw_winter_number_refused(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        receipt = runner.run_pipeline(_base_inputs("abort-emission-5",
                                                   winter=0.5))
        self._assert_clean_abort(ledger, receipt, "emission", before)
        self.assertIn("no second trigger", receipt["reason"])

    def test_merit_transfer_insufficient_balance(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-transfer-1")
        inputs["transfers"][0]["amount"] = _fig(999.0)
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "merit_transfer", before)

    def test_merit_transfer_empty_reason(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-transfer-2")
        inputs["transfers"][0]["reason"] = "   "
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "merit_transfer", before)

    def test_merit_transfer_self(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-transfer-3")
        inputs["transfers"][0]["to_unity_id"] = ALICE
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "merit_transfer", before)

    def test_donate_bad_kind(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-donate-1")
        inputs["donations"][0]["kind"] = "barter"
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "donate", before)

    def test_donate_unknown_amount(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-donate-2")
        inputs["donations"][0]["amount"] = _fig(1.0, "UNKNOWN")
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "provenance_gate", before)

    def test_provenance_gate_unknown_weight(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        before = _ledger_snapshot(ledger)
        inputs = _base_inputs("abort-prov-1")
        inputs["work"][0]["merit_weight"] = _fig(10.0, "UNKNOWN")
        receipt = runner.run_pipeline(inputs)
        self._assert_clean_abort(ledger, receipt, "provenance_gate", before)
        self.assertIn("UNKNOWN never pays", receipt["reason"])


class IdempotencyTest(unittest.TestCase):
    def test_rerun_same_key_returns_original_no_double_execution(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        inputs = _base_inputs("idem-1")
        first = runner.run_pipeline(inputs)
        self.assertEqual(first["status"], "completed")
        snap = _ledger_snapshot(ledger)

        second = runner.run_pipeline(copy.deepcopy(inputs))
        self.assertEqual(second["pipeline_hash"], first["pipeline_hash"])
        self.assertEqual(second, first)
        # nothing executed twice
        self.assertEqual(_ledger_snapshot(ledger), snap)
        self.assertEqual(len(ledger.receipts), snap[0])

    def test_same_key_different_inputs_still_returns_original(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        first = runner.run_pipeline(_base_inputs("idem-2"))
        other = _base_inputs("idem-2")
        other["work"][0]["merit_weight"] = _fig(50.0)
        second = runner.run_pipeline(other)
        self.assertEqual(second["pipeline_hash"], first["pipeline_hash"])
        self.assertEqual(ledger.merit_balances[ALICE], 8.0)  # not 48

    def test_aborted_key_never_reexecutes(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        bad = _base_inputs("idem-abort-1", decision="no-such-decision")
        first = runner.run_pipeline(bad)
        self.assertEqual(first["status"], "aborted")
        snap = _ledger_snapshot(ledger)

        fixed = _base_inputs("idem-abort-1")  # fixed inputs, same key
        second = runner.run_pipeline(fixed)
        self.assertEqual(second["status"], "aborted")
        self.assertEqual(second["pipeline_hash"], first["pipeline_hash"])
        self.assertEqual(_ledger_snapshot(ledger), snap)

    def test_registry_lookup(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        self.assertIsNone(runner.get_receipt("missing-key"))
        receipt = runner.run_pipeline(_base_inputs("idem-3"))
        self.assertEqual(runner.get_receipt("idem-3")["pipeline_hash"],
                         receipt["pipeline_hash"])

    def test_registry_persists_across_runners(self):
        ledger = T.Ledger()
        tmp = tempfile.mkdtemp(prefix="pipeline-test-")
        runner = PipelineRunner(ledger, state_dir=tmp)
        first = runner.run_pipeline(_base_inputs("idem-4"))
        snap = _ledger_snapshot(ledger)

        runner2 = PipelineRunner(ledger, state_dir=tmp)
        second = runner2.run_pipeline(_base_inputs("idem-4"))
        self.assertEqual(second["pipeline_hash"], first["pipeline_hash"])
        self.assertEqual(_ledger_snapshot(ledger), snap)


class VerificationTest(unittest.TestCase):
    def test_tampered_step_receipt_fails(self):
        ledger = T.Ledger()
        receipt = run_pipeline(_base_inputs("verify-1"), ledger)
        tampered = copy.deepcopy(receipt)
        tampered["steps"][2]["receipts"][0]["receipt_id"] = "deadbeef" * 8
        check = verify_pipeline_run(tampered, ledger)
        self.assertFalse(check["ok"])

    def test_tampered_totals_breaks_seal(self):
        ledger = T.Ledger()
        receipt = run_pipeline(_base_inputs("verify-2"), ledger)
        tampered = copy.deepcopy(receipt)
        tampered["totals"]["disbursed_total"] = 999999.0
        check = verify_pipeline_run(tampered, ledger)
        self.assertFalse(check["ok"])
        self.assertIn("reseal", check["reason"])

    def test_wrong_ledger_fails(self):
        ledger = T.Ledger()
        receipt = run_pipeline(_base_inputs("verify-3"), ledger)
        check = verify_pipeline_run(receipt, T.Ledger())
        self.assertFalse(check["ok"])

    def test_not_a_pipeline_receipt(self):
        check = verify_pipeline_run({"kind": "disbursement"}, T.Ledger())
        self.assertFalse(check["ok"])

    def test_abort_receipt_verifies(self):
        # an abort has no step chain; the seal itself still reseals
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        receipt = runner.run_pipeline(
            _base_inputs("verify-4", decision="no-such-decision"))
        self.assertEqual(receipt["status"], "aborted")
        check = verify_pipeline_run(receipt, ledger)
        self.assertTrue(check["ok"], check.get("reason"))


class InputValidationTest(unittest.TestCase):
    def test_missing_idempotency_key_raises(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        inputs = _base_inputs("x")
        inputs["idempotency_key"] = "   "
        with self.assertRaises(PipelineInputError):
            runner.run_pipeline(inputs)

    def test_malformed_inputs_raise(self):
        ledger = T.Ledger()
        runner = PipelineRunner(ledger)
        with self.assertRaises(PipelineInputError):
            runner.run_pipeline(["not", "inputs"])
        with self.assertRaises(PipelineInputError):
            runner.run_pipeline({})  # missing required fields

    def test_bad_ledger_raises(self):
        with self.assertRaises(PipelineInputError):
            PipelineRunner(object())


if __name__ == "__main__":
    unittest.main()

"""
Tests for the epoch runner (~/workspace/unity-world/economics/epoch_runner.py).

Gauntlet PERPETUITY closure: I-1 (no epoch runner — the drill harness was
the human hand) and I-3 (no epoch-close idempotency — double-close
double-paid). All simulated, in-memory, TESTNET ONLY. Every non-decided
number is labeled MODELED; the real digits are HELD_FOR_DAVID.

Run: python3 test_epoch_runner.py
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "dclm")))

import tokenomics as T
from tokenomics import (
    Figure, HeldParameter, HeldParameterError, Ledger, Receipt,
)
from epoch_runner import (
    DoubleEpochCloseError, EpochFailedError, EpochInputs, EpochRunner,
    PegDeviationError, PoolEpochInputs, ReceiptInput, get_runner,
    run_epoch, run_epochs,
)
from winter import WinterState


def modeled(value):
    return Figure(value, "MODELED", "testnet what-if — explicitly modeled")


def ver(value):
    return Figure(value, "VERIFIED")


HUMAN = ["unity:testnet:er-h0", "unity:testnet:er-h1"]
MACHINE = ["unity:testnet:er-m0", "unity:testnet:er-m1"]


class ChainBuilder:
    """Builds VERIFIED gated receipts chained to the ledger's live head.

    Receipts are built lazily per epoch (after the previous epoch applied)
    so the applied chain links cleanly end to end.
    """

    def __init__(self, ledger):
        self.ledger = ledger

    def _head(self):
        return (self.ledger.receipts[-1].manifest_hash
                if self.ledger.receipts else "GENESIS")

    def receipt(self, uid, epoch, tag="work", provenance="VERIFIED"):
        head = self._head()
        r = Receipt.build(uid, "merit_accrual",
                          {"work_ref": f"{tag}/{uid}/e{epoch}",
                           "oracle": "test gated-receipt gate"},
                          provenance, epoch, head)
        return r


def epoch_inputs(ledger, epoch, winter=None, holdback=None,
                 members_h=HUMAN, members_m=MACHINE, weight=10.0):
    """Standard two-pool epoch inputs: every roster member works once.

    Receipts are built chained to the ledger's live head at call time, so
    the applied chain links cleanly end to end across epochs.
    """
    head = (ledger.receipts[-1].manifest_hash if ledger.receipts else "GENESIS")

    def chained(pool, members, h):
        ris = []
        for uid in members:
            r = Receipt.build(uid, "merit_accrual",
                              {"work_ref": f"work/{uid}/e{epoch}",
                               "oracle": "test gated-receipt gate"},
                              "VERIFIED", epoch, h)
            h = r.manifest_hash
            ris.append(ReceiptInput(unity_id=uid, receipt=r,
                                    weight=modeled(weight)))
        return PoolEpochInputs(pool=pool, members=list(members),
                               receipts=ris, winter=winter,
                               holdback_fraction=holdback), h

    human_pin, head = chained("human", members_h, head)
    machine_pin, _ = chained("machine", members_m, head)

    return EpochInputs(peg_ratio=modeled(1000.0), decay_rate=modeled(0.02),
                       pools={"human": human_pin, "machine": machine_pin})


def chain_audit(ledger):
    """Walk the receipt chain; return (breaks, head_matches)."""
    breaks = 0
    recs = ledger.receipts
    for i in range(1, len(recs)):
        if recs[i].prev_hash != recs[i - 1].manifest_hash:
            breaks += 1
    head_matches = (not recs) or (recs[-1].manifest_hash ==
                                  getattr(ledger, "_chain_head", None))
    return breaks, head_matches


class TestEpochRunner(unittest.TestCase):
    # -- happy path ------------------------------------------------------
    def test_happy_path_full_cycle(self):
        L = Ledger()
        runner = EpochRunner(L)
        rep = runner.run_epoch(1, epoch_inputs(L, 1))

        self.assertEqual(rep.epoch, 1)
        self.assertEqual(rep.provenance, "MODELED")
        self.assertTrue(runner.is_epoch_closed(1))
        self.assertEqual(runner.next_epoch_number, 2)

        # merit accrued (10) then decayed one epoch at 0.02 -> 9.8
        for uid in HUMAN + MACHINE:
            self.assertAlmostEqual(L.merit_balances[uid], 9.8, places=9)
        self.assertEqual(rep.members_accrued, 4)
        self.assertEqual(rep.members_decayed, 4)

        # emission happened in both pools and matches disbursement
        for pool in ("human", "machine"):
            p = rep.pools[pool]
            self.assertGreater(p["emission_total"], 0.0)
            self.assertAlmostEqual(p["disbursed_total"], p["emission_total"],
                                   places=9)
            self.assertAlmostEqual(L.emitted[pool], p["disbursed_total"],
                                   places=9)
            self.assertEqual(p["winter_multiplier"], 1.0)
            self.assertEqual(p["winter_label"], "SUMMER")

        # peg check passed with float-precision deviation
        self.assertTrue(rep.peg_check["pass"])
        self.assertLessEqual(rep.peg_check["max_relative_deviation"], 1e-9)

        # the epoch sealed with an epoch_close receipt
        close = L.receipts[-1]
        self.assertEqual(close.kind, "epoch_close")
        self.assertEqual(close.epoch, 1)
        self.assertEqual(close.receipt_id, rep.close_receipt_id)
        self.assertEqual(close.manifest_hash, rep.close_manifest_hash)
        self.assertEqual(rep.state_digest, L.state_digest())

        # chain intact
        breaks, head_ok = chain_audit(L)
        self.assertEqual(breaks, 0)
        self.assertTrue(head_ok)

    def test_module_level_run_epoch(self):
        L = Ledger()
        rep = run_epoch(L, 1, epoch_inputs(L, 1))
        self.assertEqual(rep.epoch, 1)
        self.assertTrue(get_runner(L).is_epoch_closed(1))

    def test_next_epoch_interface(self):
        L = Ledger()
        runner = EpochRunner(L)
        r1 = runner.next_epoch(epoch_inputs(L, 1))
        r2 = runner.next_epoch(epoch_inputs(L, 2))
        self.assertEqual((r1.epoch, r2.epoch), (1, 2))
        self.assertEqual(runner.next_epoch_number, 3)

    def test_dict_inputs_accepted(self):
        L = Ledger()
        b = ChainBuilder(L)
        r = b.receipt(HUMAN[0], 1)
        inputs = {
            "peg_ratio": modeled(1000.0),
            "decay_rate": modeled(0.02),
            "pools": {
                "human": {
                    "pool": "human",
                    "members": HUMAN,
                    "receipts": [{"unity_id": HUMAN[0], "receipt": r,
                                  "weight": modeled(10.0)}],
                },
            },
        }
        rep = run_epoch(L, 1, inputs)
        self.assertEqual(rep.epoch, 1)
        self.assertAlmostEqual(L.merit_balances[HUMAN[0]], 9.8, places=9)

    # -- gate failure: no partial epoch ----------------------------------
    def test_gate_failure_duplicate_receipt_no_partial(self):
        L = Ledger()
        b = ChainBuilder(L)
        r = b.receipt(HUMAN[0], 1)
        dup = ReceiptInput(unity_id=HUMAN[0], receipt=r, weight=modeled(10.0))
        inputs = EpochInputs(
            peg_ratio=modeled(1000.0), decay_rate=modeled(0.02),
            pools={"human": PoolEpochInputs(
                pool="human", members=HUMAN, receipts=[dup, dup])})
        with self.assertRaises(EpochFailedError) as ctx:
            run_epoch(L, 1, inputs)
        self.assertEqual(ctx.exception.epoch, 1)
        self.assertIsInstance(ctx.exception.cause, T.DuplicateReceiptError)
        # NOTHING applied: no partial epoch
        self.assertEqual(len(L.receipts), 0)
        self.assertEqual(L.emitted["human"], 0.0)
        self.assertFalse(get_runner(L).is_epoch_closed(1))

    def test_gate_failure_unverified_receipt_no_partial(self):
        L = Ledger()
        b = ChainBuilder(L)
        r = b.receipt(HUMAN[0], 1, provenance="REPORTED")  # not gated
        inputs = EpochInputs(
            peg_ratio=modeled(1000.0), decay_rate=modeled(0.02),
            pools={"human": PoolEpochInputs(
                pool="human", members=HUMAN,
                receipts=[ReceiptInput(unity_id=HUMAN[0], receipt=r,
                                       weight=modeled(10.0))])})
        with self.assertRaises(EpochFailedError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)
        self.assertFalse(get_runner(L).is_epoch_closed(1))

    def test_gate_failure_wrong_epoch_receipt_no_partial(self):
        L = Ledger()
        b = ChainBuilder(L)
        r = b.receipt(HUMAN[0], 2)  # epoch-bound to 2, ingested in 1
        inputs = EpochInputs(
            peg_ratio=modeled(1000.0), decay_rate=modeled(0.02),
            pools={"human": PoolEpochInputs(
                pool="human", members=HUMAN,
                receipts=[ReceiptInput(unity_id=HUMAN[0], receipt=r,
                                       weight=modeled(10.0))])})
        with self.assertRaises(EpochFailedError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)

    def test_gate_failure_bad_winter_type_no_partial(self):
        L = Ledger()
        inputs = epoch_inputs(L, 1, winter={"gradient": 0.5})  # raw dict refused
        with self.assertRaises(EpochFailedError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)
        self.assertFalse(get_runner(L).is_epoch_closed(1))

    # -- HELD parameters: honest refusal, never a hang --------------------
    def test_held_peg_refuses(self):
        L = Ledger()
        inputs = epoch_inputs(L, 1)
        inputs.peg_ratio = HeldParameter("peg_ratio_E")
        with self.assertRaises(HeldParameterError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)
        self.assertFalse(get_runner(L).is_epoch_closed(1))

    def test_held_decay_refuses(self):
        L = Ledger()
        inputs = epoch_inputs(L, 1)
        inputs.decay_rate = HeldParameter("merit_decay_rate")
        with self.assertRaises(HeldParameterError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)

    def test_missing_params_refuse(self):
        L = Ledger()
        inputs = epoch_inputs(L, 1)
        inputs.peg_ratio = None
        with self.assertRaises(HeldParameterError):
            run_epoch(L, 1, inputs)
        inputs.peg_ratio = modeled(1000.0)
        inputs.decay_rate = None
        with self.assertRaises(HeldParameterError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)

    def test_held_holdback_fraction_refuses(self):
        L = Ledger()
        inputs = epoch_inputs(L, 1, holdback=HeldParameter(
            "reserve_holdback_fraction"))
        with self.assertRaises(HeldParameterError):
            run_epoch(L, 1, inputs)
        self.assertEqual(len(L.receipts), 0)

    def test_held_error_not_wrapped(self):
        # HeldParameterError propagates as itself, not EpochFailedError
        L = Ledger()
        inputs = epoch_inputs(L, 1)
        inputs.peg_ratio = HeldParameter("peg_ratio_E")
        try:
            run_epoch(L, 1, inputs)
            self.fail("should have raised")
        except HeldParameterError as e:
            self.assertNotIsInstance(e, EpochFailedError)

    # -- idempotency (I-3): double-close refused ---------------------------
    def test_double_close_refused(self):
        L = Ledger()
        run_epoch(L, 1, epoch_inputs(L, 1))
        emitted_after_first = dict(L.emitted)
        receipts_after_first = len(L.receipts)

        with self.assertRaises(DoubleEpochCloseError):
            run_epoch(L, 1, epoch_inputs(L, 1))
        # no double-disbursement, no new receipts
        self.assertEqual(L.emitted, emitted_after_first)
        self.assertEqual(len(L.receipts), receipts_after_first)

    def test_double_close_refused_with_fresh_inputs(self):
        # It is the EPOCH that is closed, not the inputs: even brand-new
        # receipts for the same epoch number are refused.
        L = Ledger()
        run_epoch(L, 1, epoch_inputs(L, 1))
        with self.assertRaises(DoubleEpochCloseError):
            run_epoch(L, 1, epoch_inputs(L, 1))

    def test_runner_recovers_closed_epochs(self):
        L = Ledger()
        EpochRunner(L).run_epoch(1, epoch_inputs(L, 1))
        runner2 = EpochRunner(L)  # reconstructed on the same ledger
        self.assertTrue(runner2.is_epoch_closed(1))
        self.assertEqual(runner2.next_epoch_number, 2)
        with self.assertRaises(DoubleEpochCloseError):
            runner2.run_epoch(1, epoch_inputs(L, 1))

    def test_invalid_epoch_number(self):
        L = Ledger()
        from epoch_runner import EpochRunnerError
        with self.assertRaises(EpochRunnerError):
            run_epoch(L, 0, epoch_inputs(L, 1))

    # -- winter + reserve thread through ----------------------------------
    def test_winter_throttle_applies(self):
        winter = WinterState(gradient=1.0, label="WINTER",
                             reasons=["test: full winter"], provenance="DERIVED")
        L_summer, L_winter = Ledger(), Ledger()
        rep_s = run_epoch(L_summer, 1, epoch_inputs(L_summer, 1))
        rep_w = run_epoch(L_winter, 1, epoch_inputs(L_winter, 1, winter=winter))
        # EMISSION_FLOOR = 0.25 at full winter: slowed, never shut down
        for pool in ("human", "machine"):
            self.assertAlmostEqual(
                rep_w.pools[pool]["emission_total"],
                rep_s.pools[pool]["emission_total"] * 0.25, places=9)
            self.assertEqual(rep_w.pools[pool]["winter_label"], "WINTER")
            self.assertEqual(rep_w.pools[pool]["winter_multiplier"], 0.25)
            self.assertGreater(rep_w.pools[pool]["emission_total"], 0.0)
        # peg check still passes under throttle (expected rate is throttled)
        self.assertTrue(rep_w.peg_check["pass"])

    def test_reserve_absorb(self):
        L = Ledger()
        rep = run_epoch(L, 1, epoch_inputs(L, 1, holdback=modeled(0.1)))
        for pool in ("human", "machine"):
            p = rep.pools[pool]
            self.assertAlmostEqual(p["reserve_held"],
                                   p["emission_total"] * 0.1, places=9)
            self.assertAlmostEqual(L.reserve[pool], p["reserve_held"], places=9)
            # disbursed == computed - held (accounting identity)
            self.assertAlmostEqual(
                p["disbursed_total"], p["emission_total"] - p["reserve_held"],
                places=9)
            self.assertEqual(p["reserve_released"], 0.0)
        # reserve movements are receipted in the main chain
        kinds = [r.kind for r in L.receipts]
        self.assertIn("reserve", kinds)
        self.assertTrue(rep.peg_check["pass"])

    # -- 10-epoch sequence consistency --------------------------------------
    def test_ten_epoch_sequence(self):
        L = Ledger()

        def source(epoch):
            return epoch_inputs(L, epoch)

        reports = run_epochs(L, 10, source)
        self.assertEqual(len(reports), 10)
        self.assertEqual([r.epoch for r in reports], list(range(1, 11)))
        self.assertEqual(get_runner(L).closed_epochs, frozenset(range(1, 11)))

        # exactly one epoch_close receipt per epoch
        closes = [r for r in L.receipts if r.kind == "epoch_close"]
        self.assertEqual(len(closes), 10)
        self.assertEqual(sorted(r.epoch for r in closes), list(range(1, 11)))

        # receipt chain intact end to end
        breaks, head_ok = chain_audit(L)
        self.assertEqual(breaks, 0)
        self.assertTrue(head_ok)

        # merit after 10 epochs: 10 * (1 + 0.98 + ... + 0.98^9) ≈ 91.5,
        # climbing toward the steady state (10/0.02 = 500) — the drill's
        # convergence curve, reproduced by the runner with no human hand.
        mean_merit = sum(L.merit_balances[u] for u in HUMAN + MACHINE) / 4
        self.assertGreater(mean_merit, 80.0)
        self.assertLess(mean_merit, 120.0)
        # every epoch's peg check passed
        for r in reports:
            self.assertTrue(r.peg_check["pass"])

        # re-running any closed epoch refuses (idempotency holds at scale)
        with self.assertRaises(DoubleEpochCloseError):
            run_epoch(L, 7, epoch_inputs(L, 7))

    def test_run_epochs_continues_sequence(self):
        L = Ledger()
        run_epochs(L, 3, lambda e: epoch_inputs(L, e))
        reports = run_epochs(L, 2, lambda e: epoch_inputs(L, e))
        self.assertEqual([r.epoch for r in reports], [4, 5])
        self.assertEqual(get_runner(L).next_epoch_number, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)

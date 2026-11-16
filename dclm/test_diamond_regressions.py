"""
Diamond regression contract — audit DCX-02 through DCX-06.

These tests specify the security properties the commit and seed boundaries
must satisfy. They are intentionally added on an isolated audit branch.
They are expected to expose current-head failures until the implementation
is repaired. No production path is changed by this test-only file.

Run from repository root:
    python -m unittest dclm.test_diamond_regressions -v
"""
import os
import sys
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rights import RightsVerdict, check_rights
from writes import CommitRefused, MemoryCommitStore, dclm_commit
from seed import Seeder, SeedRefused

TEST_ID = "unity:testnet:diamond-regression-0001"


class TestCommitAuthorityBinding(unittest.TestCase):
    def _grant(self, action="LEDGER_DEBIT"):
        return check_rights(TEST_ID, action, {"internal": "dclm.meter"})

    def test_constructed_grant_is_not_accepted_as_issued_authority(self):
        """A public dataclass constructor cannot manufacture DCLM authority."""
        forged = RightsVerdict(
            verdict="GRANT",
            reason="INTERNAL_WRITE_AUTHORIZED",
            identity=TEST_ID,
            action="LEDGER_DEBIT",
        )
        store = MemoryCommitStore()
        with self.assertRaises(CommitRefused):
            dclm_commit("LEDGER_DEBIT", {"amount": 1}, forged, store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])

    def test_grant_is_bound_to_exact_commit_kind(self):
        """A grant for one action cannot authorize a different allowed kind."""
        store = MemoryCommitStore()
        debit_grant = self._grant("LEDGER_DEBIT")
        with self.assertRaises(CommitRefused):
            dclm_commit("TOKEN_MINT", {"amount": 1}, debit_grant, store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])


class TestCommitAtomicity(unittest.TestCase):
    def _grant(self):
        return check_rights(TEST_ID, "LEDGER_DEBIT", {"internal": "dclm.meter"})

    def test_signing_failure_leaves_state_unchanged(self):
        """A failed receipt signature must not leave an unreceipted mutation."""
        store = MemoryCommitStore()
        before = (list(store.applied), list(store.receipts))
        with patch("writes.sign_commit", side_effect=RuntimeError("signer unavailable")):
            with self.assertRaises(RuntimeError):
                dclm_commit("LEDGER_DEBIT", {"amount": 1}, self._grant(), store)
        self.assertEqual((store.applied, store.receipts), before)

    def test_receipt_validation_failure_leaves_state_unchanged(self):
        """A malformed receipt must be rejected before durable mutation."""
        class BadReceiptStore(MemoryCommitStore):
            def build_receipt(self, kind, payload, mutation_report, rights_verdict):
                return {"kind": kind}  # missing provenance

        store = BadReceiptStore()
        with self.assertRaises(CommitRefused):
            dclm_commit("LEDGER_DEBIT", {"amount": 1}, self._grant(), store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])


class TestSeedContinuity(unittest.TestCase):
    def test_second_seeder_cannot_issue_second_seed_for_same_identity(self):
        """One-seed law must survive process/Seeder replacement."""
        first = Seeder()
        second = Seeder()
        # Exercise the shared registry contract directly. If a production
        # gate is required, tests should inject one shared test gate here.
        first._seeds[TEST_ID] = object()
        with self.assertRaises(SeedRefused):
            second.issue_seed(TEST_ID)


if __name__ == "__main__":
    unittest.main(verbosity=2)

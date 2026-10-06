"""
Tests for the DCLM metering engine (~/workspace/unity-world/dclm/).

All must pass. Testnet only. Test keys only — never dollars, never eFuse.
"""
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from meter import (  # noqa: E402
    ACTION_COMPUTE,
    ACTION_LOOK,
    ACTION_RENDER,
    ACTION_SEARCH,
    IDENTITY_PREFIX,
    OUTCOME_GRANTED,
    OUTCOME_REFUSED,
    PRICE_COMPUTE,
    PRICE_LOOK,
    PRICE_RENDER,
    PRICE_SEARCH,
    PROVENANCE_LABELS,
    REASON_IDENTITY_REQUIRED,
    REASON_INSUFFICIENT_KEYS,
    REASON_NOT_TESTNET_IDENTITY,
    UNIT,
    MeterRefused,
    Wallet,
    verify_receipt,
)

TEST_IDENTITY = f"{IDENTITY_PREFIX}1e26f0d9e8c46818"  # same test identity as gate


def fresh_wallet():
    """A Wallet with an isolated state dir — tests never touch real state."""
    return Wallet(state_dir=tempfile.mkdtemp(prefix="meter-test-"))


class TestFreeWorld(unittest.TestCase):
    def test_look_is_free_with_no_wallet_and_no_identity(self):
        """LOOK costs nothing: no identity, no wallet, GRANTED."""
        w = fresh_wallet()
        envelope = w.meter_intent(None, ACTION_LOOK, "intent-look-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_GRANTED)
        self.assertEqual(r["amount"], 0)
        self.assertEqual(r["reason"], None)
        self.assertEqual(r["intent_id"], "intent-look-1")
        self.assertTrue(verify_receipt(envelope))
        # No ledger entry was ever created for the walletless look.
        self.assertEqual(w.balance(None), 0)

    def test_render_is_free_with_no_wallet_and_no_identity(self):
        w = fresh_wallet()
        envelope = w.meter_intent(None, ACTION_RENDER, "intent-render-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_GRANTED)
        self.assertEqual(r["amount"], 0)
        self.assertTrue(verify_receipt(envelope))

    def test_price_list_marks_look_and_render_free(self):
        self.assertEqual(PRICE_LOOK, 0)
        self.assertEqual(PRICE_RENDER, 0)

    def test_units_are_test_keys_not_money(self):
        self.assertEqual(UNIT, "test-keys")
        w = fresh_wallet()
        envelope = w.meter_intent(None, ACTION_LOOK, "intent-u-1")
        r = envelope["receipt"]
        self.assertEqual(r["unit"], "test-keys")
        self.assertTrue(r["testnet"])
        self.assertNotIn("dollar", r["note"].lower())
        self.assertNotIn("efuse", r["note"].lower().replace("not efuse", ""))


class TestMeteredIntent(unittest.TestCase):
    def test_search_deducts_exactly_the_price(self):
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 10)
        envelope = w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-s-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_GRANTED)
        self.assertEqual(r["action"], ACTION_SEARCH)
        self.assertEqual(r["amount"], PRICE_SEARCH)
        self.assertEqual(r["balance_before"], 10)
        self.assertEqual(r["balance_after"], 10 - PRICE_SEARCH)
        self.assertEqual(w.balance(TEST_IDENTITY), 10 - PRICE_SEARCH)
        self.assertTrue(verify_receipt(envelope))

    def test_compute_deducts_exactly_its_price(self):
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 10)
        envelope = w.meter_intent(TEST_IDENTITY, ACTION_COMPUTE, "intent-c-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_GRANTED)
        self.assertEqual(r["amount"], PRICE_COMPUTE)
        self.assertEqual(r["balance_after"], 10 - PRICE_COMPUTE)
        self.assertEqual(w.balance(TEST_IDENTITY), 10 - PRICE_COMPUTE)
        self.assertTrue(verify_receipt(envelope))

    def test_double_submit_of_same_intent_charges_once(self):
        """Idempotency: same intent_id twice -> same receipt, one deduction."""
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 10)
        first = w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-idem-1")
        second = w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-idem-1")
        self.assertEqual(
            first["receipt"]["receipt_id"], second["receipt"]["receipt_id"])
        self.assertEqual(first, second)  # byte-identical envelope
        self.assertEqual(
            w.balance(TEST_IDENTITY), 10 - PRICE_SEARCH,
            "second submit must not deduct again")

    def test_different_intent_ids_charge_separately(self):
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 10)
        w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-a")
        w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-b")
        self.assertEqual(w.balance(TEST_IDENTITY), 10 - 2 * PRICE_SEARCH)

    def test_metred_action_without_identity_is_refused(self):
        w = fresh_wallet()
        envelope = w.meter_intent(None, ACTION_SEARCH, "intent-noid-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_REFUSED)
        self.assertTrue(verify_receipt(envelope))
        self.assertEqual(w.balance(TEST_IDENTITY), 0)


class TestRefusals(unittest.TestCase):
    def test_insufficient_keys_is_honest_refusal(self):
        """Not enough test-keys -> REFUSAL with the true reason. The world
        stays free; only the intent is unserved; balance untouched."""
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 2)  # less than PRICE_COMPUTE
        before = w.balance(TEST_IDENTITY)
        envelope = w.meter_intent(TEST_IDENTITY, ACTION_COMPUTE, "intent-poor-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_REFUSED)
        self.assertEqual(r["reason"], REASON_INSUFFICIENT_KEYS)
        self.assertEqual(r["amount"], PRICE_COMPUTE)
        self.assertEqual(w.balance(TEST_IDENTITY), before,
                         "refusal must not touch the balance")
        self.assertTrue(verify_receipt(envelope))  # refusals are verifiable too

    def test_refusal_is_not_cached_but_balance_is(self):
        """A refusal does not consume the intent: after funding, the same
        intent can succeed."""
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 1)
        refused = w.meter_intent(TEST_IDENTITY, ACTION_COMPUTE, "intent-retry-1")
        self.assertEqual(refused["receipt"]["outcome"], OUTCOME_REFUSED)
        w.faucet(TEST_IDENTITY, 10)  # now affordable
        granted = w.meter_intent(TEST_IDENTITY, ACTION_COMPUTE, "intent-retry-1")
        self.assertEqual(granted["receipt"]["outcome"], OUTCOME_GRANTED)
        self.assertEqual(w.balance(TEST_IDENTITY), 11 - PRICE_COMPUTE)

    def test_non_testnet_identity_refused(self):
        """Anything not starting with unity:testnet: is refused with a
        SIGNED REFUSAL receipt — the medium denies, DCLM receipts the
        denial (canon: every denial auditable). The purify medium still
        fail-closes underneath (raises PurificationRefused); the meter
        converts it to the receipted denial contract.

        (Contract evolution 2026-10-06, maximum run: receipted denial
        replaces the bare raise — a raise leaves no receipt of the
        denial, and this system receipts everything. The medium's raise
        remains the fail-closed floor.)
        """
        w = fresh_wallet()
        for bad in ("eth:mainnet:0xabc", "unity:mainnet:deadbeef",
                    "david", 12345, "", None):
            envelope = w.meter_intent(bad, ACTION_SEARCH, f"intent-bad-{bad!r}")
            r = envelope["receipt"]
            self.assertEqual(r["outcome"], OUTCOME_REFUSED, f"for {bad!r}")
            expected_reason = (REASON_IDENTITY_REQUIRED if not bad
                               else REASON_NOT_TESTNET_IDENTITY)
            self.assertEqual(r["reason"], expected_reason, f"for {bad!r}")
            self.assertTrue(verify_receipt(envelope), f"for {bad!r}")
        # Non-testnet identities never entered the ledger at all.
        self.assertEqual(w.balance("eth:mainnet:0xabc"), 0)

    def test_faucet_refuses_non_testnet_identity(self):
        w = fresh_wallet()
        with self.assertRaises(MeterRefused):
            w.faucet("eth:mainnet:0xabc", 10)

    def test_unknown_action_is_honest_refusal(self):
        w = fresh_wallet()
        envelope = w.meter_intent(TEST_IDENTITY, "TELEPORT", "intent-x-1")
        r = envelope["receipt"]
        self.assertEqual(r["outcome"], OUTCOME_REFUSED)
        self.assertEqual(r["reason"], "UNKNOWN_ACTION")
        self.assertEqual(w.balance(TEST_IDENTITY), 0)
        self.assertTrue(verify_receipt(envelope))


class TestFaucetAndLedger(unittest.TestCase):
    def test_faucet_funds_test_units_and_is_logged(self):
        w = fresh_wallet()
        envelope = w.faucet(TEST_IDENTITY, 25)
        r = envelope["receipt"]
        self.assertEqual(r["type"], "FUNDING")
        self.assertEqual(r["amount"], 25)
        self.assertEqual(r["unit"], "test-keys")
        self.assertEqual(r["balance_before"], 0)
        self.assertEqual(r["balance_after"], 25)
        self.assertEqual(w.balance(TEST_IDENTITY), 25)
        self.assertTrue(verify_receipt(envelope))

    def test_faucet_rejects_non_positive_amounts(self):
        w = fresh_wallet()
        for bad in (0, -5, "ten", 2.5):
            with self.assertRaises(ValueError, msg=f"for {bad!r}"):
                w.faucet(TEST_IDENTITY, bad)
        self.assertEqual(w.balance(TEST_IDENTITY), 0)

    def test_ledger_never_goes_negative(self):
        """Drain an account to exactly zero, then hammer it: every balance
        stays >= 0, and overdrafts are honest refusals."""
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, PRICE_SEARCH * 3)
        for i in range(3):
            env = w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, f"intent-drain-{i}")
            self.assertEqual(env["receipt"]["outcome"], OUTCOME_GRANTED)
        self.assertEqual(w.balance(TEST_IDENTITY), 0)
        # One more is refused, not overdrafted.
        env = w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-overdraft")
        self.assertEqual(env["receipt"]["outcome"], OUTCOME_REFUSED)
        self.assertEqual(env["receipt"]["reason"], REASON_INSUFFICIENT_KEYS)
        for identity, balance in w._ledger["balances"].items():
            self.assertGreaterEqual(balance, 0, f"negative balance for {identity}")

    def test_ledger_persists_across_instances(self):
        d = tempfile.mkdtemp(prefix="meter-persist-")
        w1 = Wallet(state_dir=d)
        w1.faucet(TEST_IDENTITY, 10)
        w1.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-p-1")
        w2 = Wallet(state_dir=d)
        self.assertEqual(w2.balance(TEST_IDENTITY), 10 - PRICE_SEARCH)
        # Idempotency survives restart: same intent replays, no new charge.
        env = w2.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-p-1")
        self.assertEqual(w2.balance(TEST_IDENTITY), 10 - PRICE_SEARCH)
        self.assertEqual(env["receipt"]["outcome"], OUTCOME_GRANTED)


class TestProvenanceOnReceipts(unittest.TestCase):
    def _walk_receipts(self, envelope, found):
        node = envelope["receipt"]
        self.assertIn("provenance", node)
        found.append(node["provenance"])
        self.assertIn(envelope["provenance"], PROVENANCE_LABELS)

    def test_every_receipt_and_envelope_carries_valid_provenance(self):
        w = fresh_wallet()
        w.faucet(TEST_IDENTITY, 3)
        envelopes = [
            w.meter_intent(None, ACTION_LOOK, "intent-prov-1"),
            w.meter_intent(TEST_IDENTITY, ACTION_SEARCH, "intent-prov-2"),
            w.meter_intent(TEST_IDENTITY, ACTION_COMPUTE, "intent-prov-3"),
            w.meter_intent("nope", ACTION_SEARCH, "intent-prov-4"),
        ]
        found = []
        for env in envelopes:
            self._walk_receipts(env, found)
        self.assertEqual(len(found), 4)
        for label in found:
            self.assertIn(label, PROVENANCE_LABELS)
        # UNKNOWN is never PASS: the granted receipts are DERIVED, the
        # envelope signature is VERIFIED. Nothing granted on UNKNOWN.
        self.assertNotIn("UNKNOWN", found)

    def test_tampered_receipt_fails_verification(self):
        w = fresh_wallet()
        envelope = w.meter_intent(None, ACTION_LOOK, "intent-tamper-1")
        envelope["receipt"]["amount"] = 999
        self.assertFalse(verify_receipt(envelope))


if __name__ == "__main__":
    unittest.main(verbosity=2)

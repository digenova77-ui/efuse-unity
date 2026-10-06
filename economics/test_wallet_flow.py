#!/usr/bin/env python3
"""
test_wallet_flow.py — THE FULL WALLET FLOW (testnet only).

  biometric auth -> wallet open -> send Merit -> receive Merit

Every step is receipted; origin is preserved; the buyer's standing is
unchanged. The device ceremony is a clearly-labeled TEST-DOUBLE
(simulation — never claimed as a real biometric); the real hardware
path (Grok's platform-authenticator ceremony) is HONEST-PENDING in
this sandbox. All must pass.
"""

import base64
import hashlib
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "dclm")))

import wallet as W
import wallet_auth as WA
from token_engine import Tokenizer


def _manifest(seed):
    return hashlib.sha256(f"manifest:{seed}".encode()).hexdigest()


def _keypair_identity():
    """A test Unity ID derived from a real test keypair — the engine's
    transfer-auth check requires sha256(pubkey) == the ID suffix."""
    priv, pub = W.generate_test_keypair()
    return W.derive_unity_id(pub), priv, pub


def _test_device_ceremony(challenge):
    """TEST-DOUBLE phone simulation — clearly labeled, never a biometric."""
    return {"attestation": WA.TEST_DOUBLE_LABEL,
            "challenge_id": (challenge or {}).get("challenge_id")}


def _work_receipt(identity, merit_value, seed):
    return {
        "schema": "unity.relay.v1.testnet",
        "receipt_id": f"rcpt-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "work",
        "provenance": "VERIFIED",
        "epoch": 3,
        "merit_value": merit_value,
    }


class TestWalletFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = W.Ledger(state_dir=os.path.join(self.tmp.name, "ledger"))
        self.alice_id, self.alice_priv, self.alice_pub = _keypair_identity()
        self.bob_id, self.bob_priv, self.bob_pub = _keypair_identity()
        self.gate_dir = os.path.join(self.tmp.name, "gate")

    def tearDown(self):
        self.tmp.cleanup()

    def _open_wallets(self):
        a = self.ledger.new_wallet(
            self.alice_id, base64.b64encode(self.alice_pub).decode())
        b = self.ledger.new_wallet(
            self.bob_id, base64.b64encode(self.bob_pub).decode())
        return a, b

    def _earning_engine(self):
        """Alice earned 80 Merit from her own verified work.

        SETUP ONLY: the accrual goes through the engine's accrual core
        (_accrue_merit) rather than the full tokenize() pipeline, which
        the max-purity worker owns and edits concurrently (their purify
        pass changes the gated-bundle shape). The transfer path under
        test — signed merit_transfer, wallet delegation, standing
        preservation — runs the FULL engine code path. The accrual is
        fixture, not verdict."""
        eng = Tokenizer()
        eng._accrue_merit(self.alice_id, 80.0,
                          proof_ref="test-fixture:verified-work-rcpt",
                          epoch=3)
        self.assertEqual(eng.standing(self.alice_id), 80.0)
        return eng

    def _alice_signer(self):
        def signer(from_id, to_id, amount, reason):
            return W.make_merit_transfer_auth(
                self.alice_priv, self.alice_pub,
                from_id, to_id, amount, reason)
        return signer

    # -- the flow -------------------------------------------------------
    def test_full_flow(self):
        # 1. BIOMETRIC AUTH — the L1 bind ceremony (beat 2 of 4).
        auth = WA.biometric_auth(
            self.alice_id, device_ceremony=_test_device_ceremony,
            gate_state_dir=self.gate_dir)
        self.assertTrue(auth["bound"])
        self.assertEqual(auth["unity_id"], self.alice_id)
        self.assertIn("gate_receipt", auth)

        # 2. WALLET OPEN — zero of everything, the hard gate.
        alice, bob = self._open_wallets()
        self.assertEqual(alice.balances()["eFuse"]["amount"], 0)
        self.assertEqual(bob.balances()["Unity"]["amount"], 0)

        # 3. SEND MERIT — dead-simple interface, through the engine.
        eng = self._earning_engine()
        standing_before = eng.standing(self.bob_id)
        receipt = alice.send_merit(
            self.bob_id, 25.0, "gift",
            signer=self._alice_signer(), engine=eng,
            manifest={"op": "send", "nonce": "flow-test-1"})
        self.assertEqual(receipt["kind"], "merit-transfer")
        self.assertEqual(receipt["from"], self.alice_id)
        self.assertEqual(receipt["to"], self.bob_id)
        self.assertEqual(receipt["amount"], 25.0)
        # Structural: no origin FIELD on the receipt — the ownership_note
        # names the fields in prose, but no origin key carries them.
        origin_keys = [k for k in receipt
                       if k != "ownership_note" and "origin" in k.lower()]
        self.assertEqual(origin_keys, [])

        # 4. RECEIVE MERIT — Bob's receipted view of what arrived.
        inbound = bob.receive_merit()
        self.assertEqual(len(inbound), 1)
        self.assertEqual(inbound[0]["from"], self.alice_id)
        self.assertEqual(inbound[0]["amount"], 25.0)

        # 5. STANDING UNCHANGED — the buyer gains value, zero standing.
        self.assertEqual(eng.standing(self.alice_id), 80.0)   # earner: kept
        self.assertEqual(eng.standing(self.bob_id),
                         standing_before)                    # buyer: still 0
        self.assertEqual(eng.merit_balance(self.alice_id), 55.0)
        self.assertEqual(eng.merit_balance(self.bob_id), 25.0)

        # 6. THE LEDGER CHAIN VERIFIES — every step receipted.
        self.assertTrue(self.ledger.verify_chain())

    def test_biometric_refuses_without_device(self):
        """No device, no double -> honest refusal, never a fake."""
        with self.assertRaises(WA.BiometricNotWired):
            WA.biometric_auth(self.alice_id, gate_state_dir=self.gate_dir)

    def test_unity_never_transfers(self):
        """Unity is non-transferable — no exceptions. The share path
        refuses it structurally; Merit is the only transferable token."""
        alice, bob = self._open_wallets()
        grant = W.make_tier_grant(self.alice_priv, self.alice_id,
                                  self.bob_id, W.TIER_FRIEND)
        W.apply_tier_grant(self.ledger, grant)
        with self.assertRaises(W.UnityBindingError):
            W.share(alice, bob, {"kind": "funds", "token": "Unity",
                                 "amount": 1},
                    manifest={"op": "x", "nonce": "x"})

    def test_unsigned_send_refused(self):
        """No signer -> no send. The public Unity ID alone authorizes
        nothing."""
        alice, bob = self._open_wallets()
        eng = self._earning_engine()
        with self.assertRaises(W.WalletError):
            alice.send_merit(self.bob_id, 5.0, "gift", engine=eng)

    def test_idempotent_retry(self):
        """Same manifest + same authorization -> same receipt, no double
        move. (A different auth nonce is a different intent, by design —
        so the retry reuses the SAME auth dict.)"""
        alice, bob = self._open_wallets()
        eng = self._earning_engine()
        auth = W.make_merit_transfer_auth(
            self.alice_priv, self.alice_pub,
            self.alice_id, self.bob_id, 10.0, "gift")
        signer = lambda *a: auth  # noqa: E731 — the same signed intent
        manifest = {"op": "send", "nonce": "idem-1"}
        r1 = alice.send_merit(self.bob_id, 10.0, "gift",
                              signer=signer, engine=eng,
                              manifest=manifest)
        r2 = alice.send_merit(self.bob_id, 10.0, "gift",
                              signer=signer, engine=eng,
                              manifest=manifest)
        self.assertEqual(r1["manifest_hash"], r2["manifest_hash"])
        self.assertEqual(eng.merit_balance(self.bob_id), 10.0)


def json_dumps_keys(obj):
    import json
    return json.dumps(obj)


if __name__ == "__main__":
    unittest.main(verbosity=2)

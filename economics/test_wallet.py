"""
Tests for the Unity wallet (~/workspace/unity-world/economics/wallet.py).

All must pass. Testnet only — ephemeral keys, never production.
"""
import base64
import copy
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import wallet as W  # noqa: E402
from wallet import (  # noqa: E402
    DonorExclusionViolation,
    InsufficientFunds,
    InvalidReceipt,
    Ledger,
    TierViolation,
    UnityBindingError,
    UnknownWallet,
    Wallet,
    apply_tier_grant,
    bind_kin,
    check_donor_exclusion,
    compute_wallet_state,
    connect,
    derive_unity_id,
    donate,
    deduct_per_decision,
    emission_receipt_signature_valid,
    generate_test_keypair,
    make_merit_transfer_auth,
    make_tier_grant,
    receive_cause_disbursement,
    receive_emission,
    receive_unity_emission,
    share,
    sign_emission_receipt,
    transfer_merit,
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# Emission authority for these tests (CRITICAL-4): one ephemeral keypair
# for the module; every test ledger registers its public half, and every
# test receipt is signed by the private half. A receipt signed by any
# other key is a forgery and must be refused.
_EMIT_PRIV, _EMIT_PUB = generate_test_keypair()


class KeyRing:
    """Ephemeral testnet identities: keypair + derived Unity ID."""

    def __init__(self, n=3):
        self.keys = []
        for _ in range(n):
            priv, pub = generate_test_keypair()
            self.keys.append({
                "priv": priv,
                "pub": pub,
                "pub_b64": _b64(pub),
                "id": derive_unity_id(pub),
            })

    def __getitem__(self, i):
        return self.keys[i]


def _ledger_with_wallets(ring, n=2):
    tmp = tempfile.mkdtemp(prefix="unity-wallet-test-")
    ledger = Ledger(state_dir=os.path.join(tmp, "state"),
                    emission_authority_pubkey_der=_EMIT_PUB)
    wallets = [ledger.new_wallet(ring[i]["id"], ring[i]["pub_b64"])
               for i in range(n)]
    return ledger, wallets, tmp


def _gated_receipt(unity_id, token, amount, pool="human",
                   manifest_hash=None, epoch="epoch-1", extra=None):
    body = {
        "kind": "merit-emission",
        "manifest_hash": manifest_hash or f"mh-{unity_id[-6:]}-{amount}",
        "unity_id": unity_id,
        "token": token,
        "amount": amount,
        "pool": pool,
        "merit_weight": 7,
        "gated": True,
        "epoch": epoch,
        "provenance": "REPORTED",
    }
    if extra:
        # Extra body fields (e.g. source tracing) merge BEFORE signing —
        # the authority signature covers them.
        body.update(extra)
    # Lawful issuance: the emission authority signs every receipt the
    # tests present (CRITICAL-4). Unsigned receipts must be refused.
    return sign_emission_receipt(body, _EMIT_PRIV)


def _fund(wallet, amount=10_000, token="eFuse"):
    receipt = _gated_receipt(wallet.unity_id, token, amount,
                             manifest_hash=f"fund-{wallet.unity_id[-8:]}"
                                           f"-{amount}-{token}")
    if token == "eFuse":
        return receive_emission(wallet, amount, receipt)
    return receive_unity_emission(wallet, amount, receipt)


class TestGenesisHonesty(unittest.TestCase):
    def test_new_wallet_holds_zero_of_everything(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        bals = w.balances()
        self.assertEqual(bals["eFuse"]["amount"], 0)
        self.assertEqual(bals["Unity"]["amount"], 0)
        self.assertEqual(bals["eFuse"]["provenance"], "VERIFIED")
        self.assertEqual(bals["Unity"]["provenance"], "VERIFIED")

    def test_nothing_minted_at_genesis(self):
        """The hard gate: sum of all balance deltas across the receipt log
        is zero — no inflow function ran, so nothing exists."""
        ring = KeyRing(2)
        ledger, _, _ = _ledger_with_wallets(ring, 2)
        delta_efuse = delta_unity = 0
        for entry in ledger._chain.entries():
            r = entry["receipt"]
            if r["kind"] == "share" and r["content_kind"] == "funds":
                delta_efuse += (r["sides"]["credit"]["after"]
                                - r["sides"]["credit"]["before"])
                delta_efuse += (r["sides"]["debit"]["after"]
                                - r["sides"]["debit"]["before"])
            if r["kind"] in ("emission", "unity-emission",
                             "deduct_per_decision", "donation"):
                token = r["token"]
                d = r["after"] - r["before"]
                if token == "eFuse":
                    delta_efuse += d
                else:
                    delta_unity += d
        self.assertEqual(delta_efuse, 0)
        self.assertEqual(delta_unity, 0)

    def test_balances_change_only_via_receipted_flows(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        # No receipted inflow exists: any mutation attempt without a valid
        # gated receipt is refused.
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 100, {"kind": "merit-emission"})
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)


class TestDeductPerDecision(unittest.TestCase):
    def test_deduct_receipted_with_manifest_hash(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 10_000)
        manifest = {"decision_id": "d-1", "purpose": "compute"}
        r = deduct_per_decision(w, 250, manifest)
        self.assertIn("manifest_hash", r)
        self.assertEqual(r["before"], 10_000)
        self.assertEqual(r["after"], 9_750)
        self.assertEqual(r["price"], 250)
        self.assertEqual(w.balances()["eFuse"]["amount"], 9_750)

    def test_same_manifest_never_deducts_twice(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 10_000)
        manifest = {"decision_id": "d-1", "purpose": "compute"}
        r1 = deduct_per_decision(w, 250, manifest)
        r2 = deduct_per_decision(w, 250, manifest)
        self.assertEqual(r1, r2)  # the retry returns the ORIGINAL receipt
        self.assertEqual(w.balances()["eFuse"]["amount"], 9_750)

    def test_refusal_records_nothing(self):
        """Insufficient funds: refused, manifest NOT recorded — a retry
        after funding with the same manifest still works."""
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        manifest = {"decision_id": "d-9", "nonce": "fixed-nonce-1"}
        with self.assertRaises(InsufficientFunds):
            deduct_per_decision(w, 250, dict(manifest))
        # manifest with that exact content was not applied...
        self.assertFalse(ledger.manifest_applied(
            W._manifest_hash({**manifest, "op": "deduct_per_decision",
                              "unity_id": w.unity_id, "price": 250,
                              "token": "eFuse"})))
        _fund(w, 10_000)
        r = deduct_per_decision(w, 250, dict(manifest))
        self.assertEqual(r["after"], 9_750)

    def test_bad_price_refused(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        for bad in (0, -5, 1.5, "100"):
            with self.assertRaises(W.WalletError):
                deduct_per_decision(w, bad, {"nonce": f"n-{bad}"})


class TestTierEnforcement(unittest.TestCase):
    def test_share_without_tier_refused(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 10_000)
        with self.assertRaises(TierViolation):
            share(a, b, {"kind": "funds", "amount": 10},
                  {"nonce": "no-tier"})

    def test_forged_tier_grant_refused(self):
        ring = KeyRing(3)
        ledger, [a, b, evil], _ = _ledger_with_wallets(ring, 3)
        # evil signs a grant *as if* from a — signature won't verify
        grant = make_tier_grant(ring[2]["priv"], a.unity_id, b.unity_id,
                                "good_friend", nonce="forge-1")
        with self.assertRaises(TierViolation):
            apply_tier_grant(ledger, grant)
        self.assertIsNone(ledger.tier_of(a.unity_id, b.unity_id))

    def test_unsigned_tier_grant_refused(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        grant = {"granter_unity_id": a.unity_id,
                 "grantee_unity_id": b.unity_id,
                 "tier": "friend", "nonce": "unsigned-1"}
        with self.assertRaises(TierViolation):
            apply_tier_grant(ledger, grant)

    def test_friend_tier_cap_enforced(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 100_000)
        grant = make_tier_grant(ring[0]["priv"], a.unity_id, b.unity_id,
                                "friend", nonce="g-friend-1")
        apply_tier_grant(ledger, grant)
        self.assertEqual(ledger.tier_of(a.unity_id, b.unity_id), "friend")
        # within cap: fine
        share(a, b, {"kind": "funds", "amount": 100},
              {"nonce": "s-ok", "epoch": "e1"})
        # over the friend per-share cap: refused
        with self.assertRaises(TierViolation):
            share(a, b, {"kind": "funds", "amount": 101},
                  {"nonce": "s-over", "epoch": "e1"})
        self.assertEqual(a.balances()["eFuse"]["amount"], 99_900)
        self.assertEqual(b.balances()["eFuse"]["amount"], 100)

    def test_tier_can_be_raised_by_regrant(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 100_000)
        apply_tier_grant(ledger, make_tier_grant(
            ring[0]["priv"], a.unity_id, b.unity_id, "friend",
            nonce="g1"))
        apply_tier_grant(ledger, make_tier_grant(
            ring[0]["priv"], a.unity_id, b.unity_id, "good_friend",
            nonce="g2"))
        self.assertEqual(ledger.tier_of(a.unity_id, b.unity_id),
                         "good_friend")
        share(a, b, {"kind": "funds", "amount": 500},
              {"nonce": "s-raised", "epoch": "e1"})

    def test_kin_binding_gates_family_tier(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 1_000_000)
        # family grant without a kin bond: refused (kin is binding)
        grant = make_tier_grant(ring[0]["priv"], a.unity_id, b.unity_id,
                                "family", nonce="g-fam-0")
        with self.assertRaises(TierViolation):
            apply_tier_grant(ledger, grant)
        # mutual kin signatures -> bond -> family grant accepted
        pair = sorted([a.unity_id, b.unity_id])
        msg = W._canonical_bytes({"kin": pair, "nonce": "kin-1"})
        idx_a = pair.index(a.unity_id)
        sig_a = W._node_sign(ring[0]["priv"], msg)
        sig_b = W._node_sign(ring[1]["priv"], msg)
        proof = {"nonce": "kin-1",
                 "sig_a": sig_a if idx_a == 0 else sig_b,
                 "sig_b": sig_b if idx_a == 0 else sig_a}
        bind_kin(ledger, a.unity_id, b.unity_id, proof)
        self.assertTrue(ledger.is_kin(a.unity_id, b.unity_id))
        grant = make_tier_grant(ring[0]["priv"], a.unity_id, b.unity_id,
                                "family", nonce="g-fam-1")
        apply_tier_grant(ledger, grant)
        # family: total access — a huge share passes
        share(a, b, {"kind": "funds", "amount": 500_000},
              {"nonce": "s-fam", "epoch": "e1"})
        self.assertEqual(b.balances()["eFuse"]["amount"], 500_000)

    def test_kin_proof_requires_both_signatures(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        pair = sorted([a.unity_id, b.unity_id])
        msg = W._canonical_bytes({"kin": pair, "nonce": "kin-2"})
        sig_a = W._node_sign(ring[0]["priv"], msg)
        # b's signature forged by a: refused
        with self.assertRaises(W.WalletError):
            bind_kin(ledger, a.unity_id, b.unity_id,
                     {"nonce": "kin-2", "sig_a": sig_a, "sig_b": sig_a})


class TestShareRails(unittest.TestCase):
    def test_money_and_info_share_the_rails(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 10_000)
        apply_tier_grant(ledger, make_tier_grant(
            ring[0]["priv"], a.unity_id, b.unity_id, "good_friend",
            nonce="g-rails"))
        r_money = share(a, b, {"kind": "funds", "amount": 50},
                        {"nonce": "m1", "epoch": "e1"})
        r_info = share(a, b,
                       {"kind": "info", "content_type": "hockey-stats",
                        "content_hash": "sha256:abc123"},
                       {"nonce": "i1", "epoch": "e1"})
        for r in (r_money, r_info):
            self.assertEqual(r["kind"], "share")
            self.assertEqual(r["from"], a.unity_id)   # Unity-bound
            self.assertEqual(r["to"], b.unity_id)     # Unity-bound
            self.assertEqual(r["tier"], "good_friend")  # tier-verified
            self.assertIn("manifest_hash", r)
        self.assertEqual(r_money["sides"]["debit"]["amount"], 50)
        self.assertEqual(r_money["sides"]["credit"]["amount"], 50)
        self.assertEqual(r_info["content_hash"], "sha256:abc123")

    def test_share_idempotent(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 10_000)
        apply_tier_grant(ledger, make_tier_grant(
            ring[0]["priv"], a.unity_id, b.unity_id, "friend",
            nonce="g-idem"))
        m = {"nonce": "share-once", "epoch": "e1"}
        r1 = share(a, b, {"kind": "funds", "amount": 10}, m)
        r2 = share(a, b, {"kind": "funds", "amount": 10}, m)
        self.assertEqual(r1, r2)
        self.assertEqual(a.balances()["eFuse"]["amount"], 9_990)

    def test_share_to_unknown_id_refused(self):
        ring = KeyRing(1)
        ledger, [a], _ = _ledger_with_wallets(ring, 1)
        _fund(a, 10_000)
        with self.assertRaises(UnknownWallet):
            share(a, "unity:testnet:nobody", {"kind": "funds", "amount": 5},
                  {"nonce": "s-unknown"})

    def test_unity_not_transferable(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        _fund(a, 10_000, token="Unity")
        apply_tier_grant(ledger, make_tier_grant(
            ring[0]["priv"], a.unity_id, b.unity_id, "good_friend",
            nonce="g-u1"))
        with self.assertRaises(UnityBindingError):
            share(a, b, {"kind": "funds", "token": "Unity", "amount": 5},
                  {"nonce": "s-unity"})

    def test_connect_is_trivial(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        c = connect(ledger, a.unity_id, b.unity_id)
        self.assertTrue(c["connected"])
        self.assertEqual(c["a"]["unity_id"], a.unity_id)
        self.assertEqual(c["b"]["unity_id"], b.unity_id)

    def test_share_code_is_the_qr_twin(self):
        ring = KeyRing(1)
        ledger, [a], _ = _ledger_with_wallets(ring, 1)
        code = a.share_code()
        self.assertIsInstance(code, str)
        self.assertIn(a.unity_id, code)  # plain text, copyable
        twin = a.qr_payload()
        json.dumps(twin)  # text-sendable
        self.assertEqual(twin["unity_id"], a.unity_id)
        self.assertEqual(twin["share_code"], code)
        back = Wallet.from_share_code(code, ledger)
        self.assertEqual(back.unity_id, a.unity_id)
        with self.assertRaises(UnknownWallet):
            Wallet.from_share_code("unity:testnet:gone", ledger)


class TestDonate(unittest.TestCase):
    def test_donate_one_way_honor_not_merit(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 10_000)
        r = donate(w, 3_000, "lock:testnet:core-cause",
                   {"nonce": "d1"})
        self.assertEqual(w.balances()["eFuse"]["amount"], 7_000)
        # Honor accrued, permanent, named, non-transferable...
        self.assertEqual(r["honor"]["amount"], 3_000)
        self.assertTrue(r["honor"]["permanent"])
        self.assertFalse(r["honor"]["transferable"])
        # ...and explicitly ZERO merit. The bright line, in the receipt.
        self.assertEqual(r["merit_accrued"], 0)
        honor = w.honor_ledger()
        self.assertEqual(len(honor), 1)
        self.assertEqual(w.donated_total(), 3_000)
        # No path from honor to eFuse exists anywhere in the module.
        for name in dir(W):
            self.assertNotIn("honor_to", name.lower())
            self.assertNotIn("redeem_honor", name.lower())
        self.assertFalse(hasattr(W.Wallet, "redeem_honor"))
        self.assertFalse(hasattr(W.Wallet, "convert_honor"))

    def test_donate_idempotent(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 10_000)
        m = {"nonce": "d-once"}
        r1 = donate(w, 1_000, "lock:testnet:core-cause", m)
        r2 = donate(w, 1_000, "lock:testnet:core-cause", m)
        self.assertEqual(r1, r2)
        self.assertEqual(w.balances()["eFuse"]["amount"], 9_000)
        self.assertEqual(len(w.honor_ledger()), 1)

    def test_donor_exclusion_blocks_return_path(self):
        ring = KeyRing(2)
        ledger, [donor, worker], _ = _ledger_with_wallets(ring, 2)
        _fund(donor, 10_000)
        r = donate(donor, 3_000, "lock:testnet:core-cause",
                   {"nonce": "d-excl"})
        own_hash = r["manifest_hash"]
        self.assertIn(own_hash, donor.donation_hashes())
        # A disbursement sourced from the donor's OWN donation: refused.
        with self.assertRaises(DonorExclusionViolation):
            check_donor_exclusion(
                donor, {"source_donation_hash": own_hash,
                        "amount": 500})
        # A disbursement from any other source: clear — the donor may still
        # earn by doing cause-work like anyone.
        ok = check_donor_exclusion(
            donor, {"source_donation_hash": "someone-elses-donation",
                    "amount": 500})
        self.assertEqual(ok["donor_exclusion"], "clear")
        ok2 = check_donor_exclusion(
            worker, {"source_donation_hash": own_hash, "amount": 500})
        self.assertEqual(ok2["donor_exclusion"], "clear")

    def test_donate_needs_real_lock_address(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 10_000)
        for bad in ("", None):
            with self.assertRaises(W.WalletError):
                donate(w, 100, bad, {"nonce": f"d-{bad}"})


class TestEmissionGating(unittest.TestCase):
    def test_ungated_receipt_refused(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        bad = _gated_receipt(w.unity_id, "eFuse", 100)
        bad["gated"] = False
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 100, bad)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_receipt_for_another_id_refused(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        rec = _gated_receipt(a.unity_id, "eFuse", 100,
                             manifest_hash="mh-cross")
        with self.assertRaises(InvalidReceipt):
            receive_emission(b, 100, rec)

    def test_emission_idempotent(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        rec = _gated_receipt(w.unity_id, "eFuse", 500,
                             manifest_hash="mh-idem-1")
        r1 = receive_emission(w, 500, rec)
        r2 = receive_emission(w, 500, rec)
        self.assertEqual(r1, r2)
        self.assertEqual(w.balances()["eFuse"]["amount"], 500)

    def test_unity_emission_gated_too(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        rec = _gated_receipt(w.unity_id, "Unity", 42,
                             manifest_hash="mh-u-1")
        r = receive_unity_emission(w, 42, rec)
        self.assertEqual(w.balances()["Unity"]["amount"], 42)
        self.assertEqual(r["kind"], "unity-emission")
        # ...but a non-merit receipt is refused: no third mint path.
        with self.assertRaises(InvalidReceipt):
            receive_unity_emission(w, 1, {"kind": "airdrop",
                                          "manifest_hash": "mh-x",
                                          "unity_id": w.unity_id,
                                          "token": "Unity", "amount": 1,
                                          "pool": "human",
                                          "merit_weight": 0, "gated": True,
                                          "epoch": "e1"})


class TestEmissionReceiptBinding(unittest.TestCase):
    """CRITICAL-4: emission receipts are cryptographically bound to the
    emission authority. Structure alone never credits — the receipt must
    carry the authority's Ed25519 signature over its canonical body."""

    def _wallet(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        return ledger, w

    def _body(self, unity_id, amount=100, manifest_hash="mh-bind-1"):
        return {
            "kind": "merit-emission",
            "manifest_hash": manifest_hash,
            "unity_id": unity_id,
            "token": "eFuse",
            "amount": amount,
            "pool": "human",
            "merit_weight": 7,
            "gated": True,
            "epoch": "epoch-1",
            "provenance": "REPORTED",
        }

    def test_signed_receipt_credits(self):
        _, w = self._wallet()
        rec = sign_emission_receipt(self._body(w.unity_id), _EMIT_PRIV)
        r = receive_emission(w, 100, rec)
        self.assertEqual(w.balances()["eFuse"]["amount"], 100)
        self.assertEqual(r["kind"], "emission")

    def test_unsigned_receipt_refused(self):
        _, w = self._wallet()
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 100, self._body(w.unity_id))
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_forged_signature_refused(self):
        """Signed by an attacker's key, not the emission authority."""
        _, w = self._wallet()
        attacker_priv, _ = generate_test_keypair()
        forged = sign_emission_receipt(
            self._body(w.unity_id, manifest_hash="mh-forge-1"), attacker_priv)
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 100, forged)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_tampered_amount_refused(self):
        """Amount changed after signing — the signature no longer covers
        the body."""
        _, w = self._wallet()
        rec = sign_emission_receipt(
            self._body(w.unity_id, amount=100, manifest_hash="mh-tamp-1"),
            _EMIT_PRIV)
        rec["amount"] = 999_999
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 999_999, rec)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_tampered_unity_id_refused(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        rec = sign_emission_receipt(
            self._body(a.unity_id, manifest_hash="mh-tamp-2"), _EMIT_PRIV)
        rec["unity_id"] = b.unity_id  # re-target the signed receipt
        with self.assertRaises(InvalidReceipt):
            receive_emission(b, 100, rec)
        self.assertEqual(b.balances()["eFuse"]["amount"], 0)

    def test_wrong_key_id_refused(self):
        _, w = self._wallet()
        rec = sign_emission_receipt(self._body(w.unity_id), _EMIT_PRIV,
                                    key_id="some-other-authority")
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 100, rec)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_stripped_signature_refused(self):
        _, w = self._wallet()
        rec = sign_emission_receipt(
            self._body(w.unity_id, manifest_hash="mh-strip-1"), _EMIT_PRIV)
        del rec["emitter_signature"]
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 100, rec)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_gauntlet_forger_reproducer_now_fails(self):
        """The exact CRITICAL-4 forger shape from the gauntlet report:
        a structurally-valid forged receipt used to credit 999 eFuse.
        It must now be refused."""
        _, w = self._wallet()
        forged = {
            "kind": "merit-emission",
            "token": "eFuse",
            "unity_id": w.unity_id,
            "amount": 999,
            "gated": True,
            "pool": "human",
            "merit_weight": 1.0,
            "manifest_hash": "mh-forger-fresh-1",
            "epoch": 7,
        }
        with self.assertRaises(InvalidReceipt):
            receive_emission(w, 999, forged)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_unity_emission_also_bound(self):
        _, w = self._wallet()
        body = self._body(w.unity_id, amount=25, manifest_hash="mh-ub-1")
        body["token"] = "Unity"
        with self.assertRaises(InvalidReceipt):
            receive_unity_emission(w, 25, body)  # unsigned
        rec = sign_emission_receipt(body, _EMIT_PRIV)
        receive_unity_emission(w, 25, rec)
        self.assertEqual(w.balances()["Unity"]["amount"], 25)

    def test_signature_binds_all_body_fields(self):
        """The signature covers the whole body: flipping gated, pool, or
        epoch post-signing breaks it."""
        _, w = self._wallet()
        for field, new_value, mh in (("gated", False, "mh-f3-1"),
                                     ("pool", "machine", "mh-f3-2"),
                                     ("epoch", "epoch-9", "mh-f3-3")):
            rec = sign_emission_receipt(
                self._body(w.unity_id, manifest_hash=mh), _EMIT_PRIV)
            rec[field] = new_value
            with self.assertRaises(InvalidReceipt):
                receive_emission(w, 100, rec)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_direct_signature_check(self):
        _, w = self._wallet()
        rec = sign_emission_receipt(
            self._body(w.unity_id, manifest_hash="mh-direct-1"), _EMIT_PRIV)
        self.assertTrue(emission_receipt_signature_valid(
            rec, _EMIT_PUB, W.EMISSION_AUTHORITY_KEY_ID))
        rec["pool"] = "machine"
        self.assertFalse(emission_receipt_signature_valid(
            rec, _EMIT_PUB, W.EMISSION_AUTHORITY_KEY_ID))

    def _cause_body(self, unity_id, amount=400, manifest_hash="mh-cd-bind-1"):
        return {
            "kind": "cause-disbursement",
            "unity_id": unity_id,
            "amount": amount,
            "manifest_hash": manifest_hash,
            "lock_address": "lock:testnet:core-cause",
            "epoch": "e9",
            "provenance": "VERIFIED",
        }

    def test_unsigned_cause_disbursement_refused(self):
        """The Lock path is bound too: a structurally-valid but unsigned
        cause disbursement credits nothing (same forgery class as
        CRITICAL-4)."""
        _, w = self._wallet()
        with self.assertRaises(InvalidReceipt):
            W.receive_cause_disbursement(w, 400, self._cause_body(w.unity_id))
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_forged_cause_disbursement_refused(self):
        _, w = self._wallet()
        attacker_priv, _ = generate_test_keypair()
        forged = sign_emission_receipt(
            self._cause_body(w.unity_id, manifest_hash="mh-cd-forge-1"),
            attacker_priv)
        with self.assertRaises(InvalidReceipt):
            W.receive_cause_disbursement(w, 400, forged)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_tampered_cause_disbursement_refused(self):
        _, w = self._wallet()
        rec = sign_emission_receipt(
            self._cause_body(w.unity_id, manifest_hash="mh-cd-tamp-1"),
            _EMIT_PRIV)
        rec["amount"] = 4_000
        with self.assertRaises(InvalidReceipt):
            W.receive_cause_disbursement(w, 4_000, rec)
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)

    def test_signed_cause_disbursement_credits(self):
        _, w = self._wallet()
        rec = sign_emission_receipt(
            self._cause_body(w.unity_id, manifest_hash="mh-cd-ok-1"),
            _EMIT_PRIV)
        r = W.receive_cause_disbursement(w, 400, rec)
        self.assertEqual(r["kind"], "cause-disbursement")
        self.assertEqual(w.balances()["eFuse"]["amount"], 400)


class TestReceiptChain(unittest.TestCase):
    def test_chain_verifies_and_tamper_breaks_it(self):
        ring = KeyRing(2)
        ledger, [a, b], tmp = _ledger_with_wallets(ring, 2)
        _fund(a, 10_000)
        apply_tier_grant(ledger, make_tier_grant(
            ring[0]["priv"], a.unity_id, b.unity_id, "friend",
            nonce="g-chain"))
        share(a, b, {"kind": "funds", "amount": 10},
              {"nonce": "s-chain", "epoch": "e1"})
        self.assertTrue(ledger.verify_chain())
        # Tamper with the persisted log: reload must fail loudly.
        rpath = os.path.join(tmp, "state", "receipts.jsonl")
        with open(rpath) as fh:
            lines = fh.readlines()
        entry = json.loads(lines[-1])
        entry["receipt"]["sides"]["credit"]["after"] = 999999
        lines[-1] = json.dumps(entry, sort_keys=True) + "\n"
        with open(rpath, "w") as fh:
            fh.writelines(lines)
        with self.assertRaises(W.WalletError):
            Ledger(state_dir=os.path.join(tmp, "state"),
                   emission_authority_pubkey_der=_EMIT_PUB)

    def test_persistence_round_trip(self):
        ring = KeyRing(1)
        ledger, [w], tmp = _ledger_with_wallets(ring, 1)
        _fund(w, 5_000)
        donate(w, 1_000, "lock:testnet:core-cause", {"nonce": "d-persist"})
        ledger2 = Ledger(state_dir=os.path.join(tmp, "state"),
                         emission_authority_pubkey_der=_EMIT_PUB)
        w2 = ledger2.wallet(w.unity_id)
        self.assertEqual(w2.balances()["eFuse"]["amount"], 4_000)
        self.assertEqual(w2.donated_total(), 1_000)
        self.assertTrue(ledger2.verify_chain())


class TestComputeWalletStateContract(unittest.TestCase):
    def test_wallet_objects(self):
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 5_000)
        donate(w, 1_000, "lock:testnet:core-cause", {"nonce": "d-c"})
        states = compute_wallet_state([w])
        s = states[w.unity_id]
        self.assertEqual(s["balance"], 4_000)
        self.assertTrue(s["payable"])  # VERIFIED zero+ balance pays
        self.assertEqual(s["provenance"], "VERIFIED")
        self.assertIsNone(s["merit"])  # the wallet never holds merit
        self.assertEqual(s["honor"]["count"], 1)
        self.assertEqual(s["honor"]["total_donated_efuse"], 1_000)

    def test_raw_dicts_and_payable_rule(self):
        states = compute_wallet_state([
            {"unity_id": "unity:testnet:aaaa", "balance": 99.0,
             "provenance": "REPORTED"},
            {"unity_id": "unity:testnet:bbbb", "balance": 10,
             "provenance": "UNKNOWN"},
            {"unity_id": "unity:testnet:cccc", "balance": 10,
             "provenance": "MODELED"},
            {"unity_id": None, "balance": 5},  # anonymous: skipped
        ])
        self.assertTrue(states["unity:testnet:aaaa"]["payable"])
        self.assertFalse(states["unity:testnet:bbbb"]["payable"])
        self.assertFalse(states["unity:testnet:cccc"]["payable"])
        self.assertNotIn(None, states)
        self.assertEqual(len([k for k in states if k != "provenance"]), 3)

    def test_economic_state_integration(self):
        """economic_state.py picks up compute_wallet_state and calls it."""
        import economic_state as es
        self.assertTrue(es.worker_modules_present()["wallet"])
        ring = KeyRing(1)
        ledger, [w], _ = _ledger_with_wallets(ring, 1)
        _fund(w, 5_000)
        state = es.compute_economic_state(wallets=[w])
        s = state["wallet_states"][w.unity_id]
        self.assertEqual(s["balance"], 5_000)
        self.assertTrue(s["payable"])


class TestMeritTransfer(unittest.TestCase):
    """The wallet's Merit transfer path (David's word, 2026-10-06):
    Merit IS transferable — the wallet DELEGATES to the token engine's
    sole legal path and records the OWNERSHIP change, never origin.

    Sender authorization (David's closure, 2026-10-06 — CRITICAL-1):
    every transfer carries the sender's Ed25519-signed authorization
    (make_merit_transfer_auth — the device signs, DCLM only verifies).
    Unsigned transfers are refused at the wallet; forged or replayed
    ones are refused by the engine."""

    def _auth(self, ring, i, frm, to, amount, reason, nonce=None):
        return make_merit_transfer_auth(ring[i]["priv"], ring[i]["pub"],
                                        frm, to, amount, reason,
                                        nonce=nonce)

    def _engine_with_merit(self, unity_id, amount=80.0):
        dclm_dir = os.path.join(_HERE, "..", "dclm")
        if dclm_dir not in sys.path:
            sys.path.insert(0, dclm_dir)
        import token_engine as TE
        t = TE.Tokenizer()
        t.set_peg_ratio(4.0, {"authority": "david"})
        import hashlib as _hl
        mh = _hl.sha256(b"wallet-xfer-earn").hexdigest()
        r = {
            "schema": "unity.relay.v1.testnet",
            "receipt_id": "rcpt-wallet-xfer",
            "manifest_hash": mh,
            "unity_id": unity_id,
            "kind": "work",
            "provenance": "VERIFIED",
            "epoch": 3,
            "merit_value": amount,
            "prev_hash": t._gate_chain_head,
        }
        t.tokenize(TE.sign_gate_receipt(r))
        return t, TE

    def _no_origin_keys(self, obj, path="receipt"):
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.assertNotIn("origin", k.lower(),
                                 f"origin key {k!r} at {path} — the wallet "
                                 "never carries origin")
                self._no_origin_keys(v, f"{path}.{k}")
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                self._no_origin_keys(v, f"{path}[{i}]")

    def test_transfer_happy_path_delegates_to_engine(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 30.0, "sale")
        r = W.transfer_merit(a, b, 30.0, "sale", engine,
                             {"nonce": "wx-happy"}, auth)
        self.assertEqual(r["kind"], "merit-transfer")
        self.assertEqual(r["from"], a.unity_id)
        self.assertEqual(r["to"], b.unity_id)
        self.assertEqual(r["amount"], 30.0)
        self.assertEqual(r["reason"], "sale")
        self.assertTrue(r["engine_transfer_id"])
        # Both-side ownership receipting.
        self.assertEqual(r["sides"]["sender"]["owned_before"], 80.0)
        self.assertEqual(r["sides"]["sender"]["owned_after"], 50.0)
        self.assertEqual(r["sides"]["recipient"]["owned_before"], 0.0)
        self.assertEqual(r["sides"]["recipient"]["owned_after"], 30.0)
        # The engine did the moving: value moved, standing didn't.
        self.assertEqual(engine.merit_balance(a.unity_id), 50.0)
        self.assertEqual(engine.merit_balance(b.unity_id), 30.0)
        self.assertEqual(engine.standing(a.unity_id), 80.0)
        self.assertEqual(engine.standing(b.unity_id), 0.0)

    def test_wallet_receipt_never_carries_origin(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 10.0, "sale")
        r = W.transfer_merit(a, b, 10.0, "sale", engine,
                             {"nonce": "wx-noorigin"}, auth)
        self._no_origin_keys(r)

    def test_gifting_works(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 25.0, "gift")
        r = W.transfer_merit(a, b.unity_id, 25.0, "gift", engine,
                             {"nonce": "wx-gift"}, auth)
        self.assertEqual(r["reason"], "gift")
        self.assertEqual(engine.merit_balance(b.unity_id), 25.0)
        self.assertEqual(engine.standing(b.unity_id), 0.0)

    def test_idempotent_on_manifest(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        m = {"nonce": "wx-idem"}
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 10.0, "sale")
        r1 = W.transfer_merit(a, b, 10.0, "sale", engine, m, auth)
        r2 = W.transfer_merit(a, b, 10.0, "sale", engine, dict(m), auth)
        self.assertEqual(r1, r2)  # retry: original receipt, no double move
        self.assertEqual(engine.merit_balance(a.unity_id), 70.0)
        self.assertEqual(engine.merit_balance(b.unity_id), 10.0)

    def test_unknown_recipient_refused(self):
        ring = KeyRing(1)
        ledger, [a], _ = _ledger_with_wallets(ring, 1)
        engine, TE = self._engine_with_merit(a.unity_id)
        with self.assertRaises(UnknownWallet):
            W.transfer_merit(a, "unity:testnet:nobody", 10.0, "sale",
                             engine, {"nonce": "wx-unknown"})

    def test_engine_refusal_propagates(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        # Valid authorization — the engine's balance gate is what refuses.
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 10_000.0, "sale")
        with self.assertRaises(TE.TokenizeRefused) as ctx:
            W.transfer_merit(a, b, 10_000.0, "sale", engine,
                             {"nonce": "wx-poor"}, auth)
        self.assertEqual(ctx.exception.reason, "TRANSFER_INSUFFICIENT_MERIT")

    def test_engine_required(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        with self.assertRaises(W.WalletError):
            W.transfer_merit(a, b, 10.0, "sale", None,
                             {"nonce": "wx-noengine"})

    def test_empty_reason_refused(self):
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 10.0, "sale")
        with self.assertRaises(W.WalletError):
            W.transfer_merit(a, b, 10.0, "   ", engine,
                             {"nonce": "wx-noreason"}, auth)

    # -- CRITICAL-1 closure: sender authorization ----------------------

    def test_unsigned_transfer_refused(self):
        """No auth -> refused at the wallet, nothing moves."""
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        with self.assertRaises(W.WalletError):
            W.transfer_merit(a, b, 30.0, "sale", engine,
                             {"nonce": "wx-unsigned"})
        self.assertEqual(engine.merit_balance(a.unity_id), 80.0)
        self.assertEqual(engine.merit_balance(b.unity_id), 0.0)

    def test_fresh_wallet_for_victim_cannot_drain(self):
        """The gauntlet's CRITICAL-1 reproducer: a fresh Wallet handle
        for the victim's Unity ID — no key, no signature — cannot move
        the victim's Merit. The public Unity ID alone authorizes
        nothing."""
        ring = KeyRing(2)
        ledger, [victim, attacker], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(victim.unity_id)
        fresh_victim_handle = W.Wallet(victim.unity_id, ledger)
        with self.assertRaises(W.WalletError):
            W.transfer_merit(fresh_victim_handle, attacker, 50.0, "theft",
                             engine)
        self.assertEqual(engine.merit_balance(victim.unity_id), 80.0)
        self.assertEqual(engine.merit_balance(attacker.unity_id), 0.0)

    def test_wrong_key_signature_refused(self):
        """The attacker's key signs as the victim: the key does not
        derive to the sender's Unity ID -> engine refuses."""
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        forged = self._auth(ring, 1, a.unity_id, b.unity_id, 30.0, "sale")
        with self.assertRaises(TE.TokenizeRefused) as ctx:
            W.transfer_merit(a, b, 30.0, "sale", engine,
                             {"nonce": "wx-wrongkey"}, forged)
        self.assertEqual(ctx.exception.reason, "TRANSFER_KEY_MISMATCH")
        self.assertEqual(engine.merit_balance(a.unity_id), 80.0)

    def test_tampered_signature_refused(self):
        """Signed for 10, submitted for 30: the signature binds the
        exact body -> engine refuses."""
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 10.0, "sale")
        with self.assertRaises(TE.TokenizeRefused) as ctx:
            W.transfer_merit(a, b, 30.0, "sale", engine,
                             {"nonce": "wx-tampered"}, auth)
        self.assertEqual(ctx.exception.reason, "TRANSFER_BAD_SIGNATURE")
        self.assertEqual(engine.merit_balance(a.unity_id), 80.0)

    def test_replay_refused_by_engine(self):
        """Same authorization under a different wallet manifest: the
        wallet treats it as a new intent, the engine refuses the replayed
        nonce — value moves exactly once."""
        ring = KeyRing(2)
        ledger, [a, b], _ = _ledger_with_wallets(ring, 2)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth = self._auth(ring, 0, a.unity_id, b.unity_id, 10.0, "sale",
                          nonce="wx-replay-auth")
        W.transfer_merit(a, b, 10.0, "sale", engine,
                         {"nonce": "wx-replay-1"}, auth)
        with self.assertRaises(TE.TokenizeRefused) as ctx:
            W.transfer_merit(a, b, 10.0, "sale", engine,
                             {"nonce": "wx-replay-2"}, auth)
        self.assertEqual(ctx.exception.reason, "TRANSFER_REPLAY")
        self.assertEqual(engine.merit_balance(a.unity_id), 70.0)
        self.assertEqual(engine.merit_balance(b.unity_id), 10.0)

    def test_auth_binds_exact_intent(self):
        """An authorization for a different recipient cannot be
        redirected: the signature covers from/to/amount/reason."""
        ring = KeyRing(3)
        ledger, [a, b, c], _ = _ledger_with_wallets(ring, 3)
        engine, TE = self._engine_with_merit(a.unity_id)
        auth_for_c = self._auth(ring, 0, a.unity_id, c.unity_id, 10.0,
                                "sale")
        with self.assertRaises(TE.TokenizeRefused):
            W.transfer_merit(a, b, 10.0, "sale", engine,
                             {"nonce": "wx-redirect"}, auth_for_c)
        self.assertEqual(engine.merit_balance(a.unity_id), 80.0)
        self.assertEqual(engine.merit_balance(b.unity_id), 0.0)
        self.assertEqual(engine.merit_balance(c.unity_id), 0.0)


class TestDonorExclusionWired(unittest.TestCase):
    """CRITICAL-6 closure: check_donor_exclusion is WIRED into every
    wallet credit path — the Lock is one-way per donor, structurally.

    The trace has two legs (same amount/source): the source leg (the
    inbound names the donor's own donation hash) and the amount leg (the
    inbound names the Core Cause Lock as its source AND the amount equals
    a donation amount). Anything else still credits — a donor may earn by
    doing cause-work like anyone."""

    def _donor_with_400(self, ring):
        ledger, wallets, _ = _ledger_with_wallets(ring, 2)
        donor, other = wallets
        _fund(donor, 10_000)
        dr = donate(donor, 400, "lock:testnet:core-cause",
                    {"nonce": "dex-donate"})
        return ledger, donor, other, dr["manifest_hash"]

    def _engine_with_merit(self, unity_id, amount=80.0):
        dclm_dir = os.path.join(_HERE, "..", "dclm")
        if dclm_dir not in sys.path:
            sys.path.insert(0, dclm_dir)
        import token_engine as TE
        t = TE.Tokenizer()
        t.set_peg_ratio(4.0, {"authority": "david"})
        import hashlib as _hl
        mh = _hl.sha256(b"wallet-xfer-earn-dex").hexdigest()
        receipt = {
            "schema": "unity.relay.v1.testnet",
            "receipt_id": "rcpt-wallet-xfer-dex",
            "manifest_hash": mh,
            "unity_id": unity_id,
            "kind": "work",
            "provenance": "VERIFIED",
            "epoch": 3,
            "merit_value": amount,
            "prev_hash": TE.GENESIS_CHAIN_ANCHOR,
        }
        # Gate-signed provenance (CRITICAL-5): tokenize() verifies the
        # gate's Ed25519 signature itself; it never trusts the string.
        t.tokenize(TE.sign_gate_receipt(receipt))
        return t, TE

    def test_emission_traced_to_own_donation_refused(self):
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        rec = _gated_receipt(donor.unity_id, "eFuse", 400,
                             manifest_hash="dex-em-1",
                             extra={"source_donation_hash": own_hash})
        with self.assertRaises(DonorExclusionViolation):
            receive_emission(donor, 400, rec)
        # Refusal records nothing: balance untouched, manifest not applied.
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_600)
        self.assertFalse(ledger.manifest_applied("dex-em-1"))

    def test_emission_lock_sourced_matching_amount_refused(self):
        # Amount leg: Lock-named source + amount == a donation amount.
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        rec = _gated_receipt(donor.unity_id, "eFuse", 400,
                             manifest_hash="dex-em-2",
                             extra={"source": "core-cause-lock"})
        with self.assertRaises(DonorExclusionViolation):
            receive_emission(donor, 400, rec)
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_600)

    def test_legitimate_credits_still_work(self):
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        # The donor earns cause-work emission (different amount, clean
        # receipt, no Lock naming): still credits.
        rec = _gated_receipt(donor.unity_id, "eFuse", 100,
                             manifest_hash="dex-em-3")
        receive_emission(donor, 100, rec)
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_700)
        # A non-donor receiving a Lock-sourced amount: never donated, so
        # nothing of theirs is returning — credits.
        rec2 = _gated_receipt(other.unity_id, "eFuse", 400,
                              manifest_hash="dex-em-4",
                              extra={"source": "core-cause-lock"})
        receive_emission(other, 400, rec2)
        self.assertEqual(other.balances()["eFuse"]["amount"], 400)

    def test_cause_disbursement_to_donor_refused(self):
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        # Amount leg: kind names the Lock, amount == the donation.
        # (Signed by the emission authority — the donor-exclusion gate,
        # not the signature gate, is what refuses these.)
        d = sign_emission_receipt(
            {"kind": "cause-disbursement", "unity_id": donor.unity_id,
             "amount": 400, "manifest_hash": "dex-cd-1",
             "lock_address": "lock:testnet:core-cause", "epoch": "e9",
             "provenance": "VERIFIED"}, _EMIT_PRIV)
        with self.assertRaises(DonorExclusionViolation):
            receive_cause_disbursement(donor, 400, d)
        # Source leg: the disbursement names the donor's own donation.
        d2 = sign_emission_receipt(
            {"kind": "cause-disbursement", "unity_id": donor.unity_id,
             "amount": 100, "manifest_hash": "dex-cd-2",
             "lock_address": "lock:testnet:core-cause", "epoch": "e9",
             "source_donation_hash": own_hash, "provenance": "VERIFIED"},
            _EMIT_PRIV)
        with self.assertRaises(DonorExclusionViolation):
            receive_cause_disbursement(donor, 100, d2)
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_600)
        self.assertFalse(ledger.manifest_applied("dex-cd-1"))

    def test_cause_disbursement_to_nondonor_works(self):
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        d = sign_emission_receipt(
            {"kind": "cause-disbursement", "unity_id": other.unity_id,
             "amount": 400, "manifest_hash": "dex-cd-3",
             "lock_address": "lock:testnet:core-cause", "epoch": "e9",
             "provenance": "VERIFIED"}, _EMIT_PRIV)
        r = receive_cause_disbursement(other, 400, d)
        self.assertEqual(r["kind"], "cause-disbursement")
        self.assertEqual(other.balances()["eFuse"]["amount"], 400)
        # Idempotent replay: the same disbursement never credits twice.
        r2 = receive_cause_disbursement(other, 400, d)
        self.assertEqual(r, r2)
        self.assertEqual(other.balances()["eFuse"]["amount"], 400)

    def test_merit_transfer_laundered_refused(self):
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        engine, TE = self._engine_with_merit(other.unity_id)

        def _auth(amount, nonce):
            return W.make_merit_transfer_auth(
                ring[1]["priv"], ring[1]["pub"],
                other.unity_id, donor.unity_id, amount, "gift",
                nonce=nonce)

        # Source leg: the Merit transfer traces to the donor's donation.
        with self.assertRaises(DonorExclusionViolation):
            W.transfer_merit(other, donor, 400.0, "gift", engine,
                             {"nonce": "dex-merit-1",
                              "source_donation_hash": own_hash},
                             auth=_auth(400.0, "dex-merit-auth-1"))
        # Amount leg: Lock-named source + matching amount.
        with self.assertRaises(DonorExclusionViolation):
            W.transfer_merit(other, donor, 400.0, "gift", engine,
                             {"nonce": "dex-merit-2",
                              "source": "core-cause-lock"},
                             auth=_auth(400.0, "dex-merit-auth-2"))
        # The engine was never touched: no value moved on either attempt.
        self.assertEqual(engine.merit_balance(other.unity_id), 80.0)
        self.assertEqual(engine.merit_balance(donor.unity_id), 0.0)
        # A clean Merit transfer to the same donor still works.
        W.transfer_merit(other, donor, 10.0, "gift", engine,
                         {"nonce": "dex-merit-3"},
                         auth=_auth(10.0, "dex-merit-auth-3"))
        self.assertEqual(engine.merit_balance(donor.unity_id), 10.0)

    def test_share_traced_to_own_donation_refused(self):
        ring = KeyRing(2)
        ledger, donor, other, own_hash = self._donor_with_400(ring)
        _fund(other, 10_000)
        apply_tier_grant(ledger, make_tier_grant(
            ring[1]["priv"], other.unity_id, donor.unity_id, "friend",
            nonce="dex-share-grant"))
        with self.assertRaises(DonorExclusionViolation):
            share(other, donor,
                  {"kind": "funds", "amount": 400,
                   "source_donation_hash": own_hash},
                  {"nonce": "dex-share-1", "epoch": "e1"})
        self.assertEqual(other.balances()["eFuse"]["amount"], 10_000)
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_600)
        # A clean share to the same donor still works.
        r = share(other, donor, {"kind": "funds", "amount": 50},
                  {"nonce": "dex-share-2", "epoch": "e1"})
        self.assertEqual(r["kind"], "share")
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_650)

    def test_gauntlet_reproducer_now_fails(self):
        """Worker 2's CRITICAL-6 reproducer, re-run: donate 400, then
        attempt to recover it through a wallet credit path. The recovery
        must FAIL — the donation does not come back."""
        ring = KeyRing(1)
        ledger, [donor], _ = _ledger_with_wallets(ring, 1)
        _fund(donor, 10_000)
        dr = donate(donor, 400, "lock:testnet:core-cause",
                    {"nonce": "dex-repro"})
        own_hash = dr["manifest_hash"]
        rec = _gated_receipt(donor.unity_id, "eFuse", 400,
                             manifest_hash="dex-repro-em",
                             extra={"source_donation_hash": own_hash})
        with self.assertRaises(DonorExclusionViolation):
            receive_emission(donor, 400, rec)
        self.assertEqual(donor.balances()["eFuse"]["amount"], 9_600)
        self.assertTrue(ledger.verify_chain())

    def test_exclusion_wired_into_credit_paths(self):
        """The gauntlet's 6.8(b) audit, encoded: check_donor_exclusion
        must have live call sites — never a dead check again."""
        import subprocess
        root = os.path.dirname(_HERE)  # ~/workspace/unity-world
        out = subprocess.run(
            ["grep", "-rn", "check_donor_exclusion(", root,
             "--include=*.py"],
            capture_output=True, text=True).stdout
        caller_lines = [l for l in out.splitlines()
                        if "def check_donor_exclusion" not in l
                        and "test_" not in l and "gauntlet" not in l]
        self.assertTrue(caller_lines,
                        "check_donor_exclusion is unwired — dead check")


if __name__ == "__main__":
    unittest.main(verbosity=2)

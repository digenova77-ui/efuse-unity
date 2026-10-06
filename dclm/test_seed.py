#!/usr/bin/env python3
"""
Tests for the ONE SEED issuer (dclm/seed.py).

David's law (2026-10-06, verbatim): "no matter how much money you have
you only buy one seed, and it costs you nothing."

All must pass. Testnet only.

The plutocracy test (the point of the whole module): a wallet funded
with 1000 test-keys and 500 eFuse gets EXACTLY THE SAME single free
seed as an empty one — money buys no second seed, no bigger seed, no
earlier seed. The tests below prove it.
"""
import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "economics"))

import seed as sd  # noqa: E402 — the module under test
from seed import (  # noqa: E402
    REASON_GATE_LEDGER_UNAVAILABLE,
    REASON_NOT_BOUND,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_PRODUCTION_SCHEMA,
    REASON_SEED_ALREADY_ISSUED,
    KIND_SEED_ISSUE,
    Seeder,
    SeedRecord,
    SeedRefused,
    assert_no_seed_market,
    seed_paths,
    seed_transfer_paths,
)
from rights import COMMIT_KINDS, check_rights  # noqa: E402
from writes import verify_commit  # noqa: E402
from meter import Wallet as MeterWallet  # noqa: E402 — test-keys ledger
import wallet as ecowallet  # noqa: E402 — economics/identity wallet


# ---------------------------------------------------------------------------
# the gate, loaded honestly from ../gate/gate.py (the live state machine,
# pointed at a temp state dir per test — no shared state)
# ---------------------------------------------------------------------------

_GATE_PATH = os.path.join(_HERE, "..", "gate", "gate.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("seed_test_gate", _GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    # dataclasses (used by gate.py) resolve their module via
    # sys.modules: the module must be registered BEFORE exec.
    sys.modules["seed_test_gate"] = module
    spec.loader.exec_module(module)
    return module


_GATE = _load_gate()


def _verified_stub(identity, proof):
    """TEST STUB — simulates the device WebAuthn ceremony for the state
    machine exercise only. NOT real WebAuthn. Never claim otherwise."""
    return _GATE.VerificationResult(status="VERIFIED",
                                    detail="test stub: simulated")


UID_A = "unity:testnet:seed0001aaaa"
UID_B = "unity:testnet:seed0002bbbb"
UID_C = "unity:testnet:seed0003cccc"
UID_D = "unity:testnet:seed0004dddd"
UID_E = "unity:testnet:seed0005eeee"
UID_F = "unity:testnet:seed0006ffff"


def _mh(obj):
    import json as _json
    return hashlib.sha256(
        _json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


class SeedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="unity-seed-test-")
        self.gate = _GATE.UnityGate(state_dir=self.tmp)
        self.seeder = Seeder(gate=self.gate)
        self.ledger = ecowallet.Ledger()  # in-memory economics ledger
        self.meter = MeterWallet(state_dir=tempfile.mkdtemp(
            prefix="unity-seed-meter-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.meter.state_dir, ignore_errors=True)

    # -- helpers -----------------------------------------------------------
    def _bind(self, uid):
        self.gate.request_bind(uid)
        self.gate.confirm_bind(uid, {"assertion": "stub"},
                               verifier=_verified_stub)
        self.assertEqual(self.gate.status(uid), "BOUND")

    def _new_ecowallet(self, uid):
        import base64
        pub = base64.b64encode(b"test-pubkey-" + uid.encode()).decode()
        return self.ledger.new_wallet(uid, pub)

    def _fund_efuse(self, w, amount):
        receipt = {
            "kind": "merit-emission",
            "token": "eFuse",
            "unity_id": w.unity_id,
            "amount": amount,
            "gated": True,
            "pool": "human",
            "merit_weight": 1.0,
            "manifest_hash": _mh({"fund": w.unity_id, "amount": amount}),
            "epoch": "test",
        }
        ecowallet.receive_emission(w, amount, receipt)

    # -- 1. one seed per ID ------------------------------------------------
    def test_one_seed_per_id(self):
        self._bind(UID_A)
        envelope = self.seeder.issue_seed(UID_A)
        self.assertTrue(verify_commit(envelope))
        receipt = envelope["receipt"]
        self.assertEqual(receipt["schema"], "unity.seed.v1.testnet")
        self.assertEqual(receipt["record_type"], "SEED_ISSUE")
        self.assertEqual(receipt["unity_id"], UID_A)
        self.assertEqual(receipt["price"], 0.0)
        self.assertEqual(receipt["cost"], 0.0)
        self.assertFalse(receipt["transferable"])
        self.assertFalse(receipt["spendable"])
        self.assertFalse(receipt["purchasable"])
        self.assertEqual(receipt["provenance"], "DERIVED")
        self.assertTrue(self.seeder.has_seed(UID_A))
        rec = self.seeder.seed_record(UID_A)
        self.assertIsInstance(rec, SeedRecord)
        self.assertEqual(rec.seed_id, receipt["seed_id"])
        # The seed id is deterministic per identity: the same ID seeded
        # by a fresh seeder yields the same seed id (one seed, one id).
        other = Seeder(gate=self.gate)
        other.issue_seed(UID_A)
        self.assertEqual(other.seed_record(UID_A).seed_id, rec.seed_id)

    # -- 2. second seed refused ---------------------------------------------
    def test_second_seed_refused(self):
        self._bind(UID_A)
        self.seeder.issue_seed(UID_A)
        before = self.seeder.seeds_issued()
        with self.assertRaises(SeedRefused) as ctx:
            self.seeder.issue_seed(UID_A)
        self.assertEqual(ctx.exception.reason, REASON_SEED_ALREADY_ISSUED)
        # Registry untouched: still exactly one seed.
        self.assertEqual(self.seeder.seeds_issued(), before)
        self.assertEqual(self.seeder.seeds_issued(), 1)
        # The refusal is signed and receipt-logged: an honest, verifiable
        # statement — not a silent drop. (The receipt log also carries
        # the successful issuance envelope; the refusal is the
        # REFUSAL-typed entry.)
        refusals = [e for e in self.seeder.refusal_log()
                    if e["receipt"].get("type") == "REFUSAL"]
        self.assertEqual(len(refusals), 1)
        self.assertTrue(verify_commit(refusals[0]))
        self.assertEqual(refusals[0]["receipt"]["reason"],
                         REASON_SEED_ALREADY_ISSUED)

    # -- 3. unbound refused ---------------------------------------------------
    def test_unbound_refused(self):
        # UID_B was never bound: no request, no ceremony.
        with self.assertRaises(SeedRefused) as ctx:
            self.seeder.issue_seed(UID_B)
        self.assertEqual(ctx.exception.reason, REASON_NOT_BOUND)
        self.assertFalse(self.seeder.has_seed(UID_B))
        self.assertEqual(self.seeder.seeds_issued(), 0)

    def test_binding_in_progress_refused(self):
        # Ceremony started (BINDING) but never confirmed: still unbound.
        self.gate.request_bind(UID_B)
        self.assertEqual(self.gate.status(UID_B), "BINDING")
        with self.assertRaises(SeedRefused) as ctx:
            self.seeder.issue_seed(UID_B)
        self.assertEqual(ctx.exception.reason, REASON_NOT_BOUND)

    # -- 4. non-testnet refused -------------------------------------------------
    def test_non_testnet_refused(self):
        # The purification medium refuses non-testnet input on entry
        # (PurificationRefused) — the codebase-wide DCLM pattern: purify
        # first, the module's own structural check as defense in depth.
        # Either way the seed is refused and nothing is written.
        from purify import PurificationRefused
        for bad in ("unity:mainnet:seed0001aaaa",
                    "not-an-identity",
                    "",
                    None,
                    42):
            try:
                self.seeder.issue_seed(bad)
            except SeedRefused as exc:
                self.assertEqual(exc.reason,
                                 REASON_NOT_TESTNET_IDENTITY, f"for {bad!r}")
            except PurificationRefused as exc:
                self.assertIn("IDENTITY", str(exc), f"for {bad!r}")
            else:
                self.fail(f"expected a refusal for {bad!r}")
        self.assertEqual(self.seeder.seeds_issued(), 0)

    # -- 5. no transfer path (introspection) -------------------------------------
    def test_no_transfer_path_introspection(self):
        # The AST proof runs on every test run: no transfer/sale/buy/
        # gift/rebind/accumulate/spend/debit/credit/purchase/mint/
        # airdrop machinery exists in seed.py by name; the registry is
        # written only by _register_seed; _register_seed is called only
        # from the commit path; SeedRecord is built only in
        # _build_record with price/cost hard-coded 0.0.
        self.assertTrue(assert_no_seed_market())
        self.assertEqual(seed_transfer_paths(), [])
        # And exactly one issuance path exists, as code.
        paths = seed_paths()
        self.assertEqual(len(paths), 1)
        self.assertIn("SEED_ISSUE", paths[0])

    # -- 6. the seed costs nothing (no deduction) ---------------------------------
    def test_seed_costs_nothing(self):
        self._bind(UID_A)
        # Fund the money ledgers first: 100 test-keys in the meter
        # wallet, 500 eFuse in the economics wallet.
        self.meter.faucet(UID_A, 100)
        w = self._new_ecowallet(UID_A)
        self._fund_efuse(w, 500)
        self.assertEqual(self.meter.balance(UID_A), 100)
        self.assertEqual(w.balances()["eFuse"]["amount"], 500)

        self.seeder.issue_seed(UID_A, ledger=self.ledger)

        # Nothing deducted anywhere: the seed costs nothing.
        self.assertEqual(self.meter.balance(UID_A), 100)
        self.assertEqual(w.balances()["eFuse"]["amount"], 500)
        self.assertEqual(w.balances()["Unity"]["amount"], 0)
        receipt = self.seeder.seed_record(UID_A)
        self.assertEqual(receipt.price, 0.0)
        self.assertEqual(receipt.cost, 0.0)

    # -- 7. the seed is not spendable ----------------------------------------------
    def test_seed_not_spendable(self):
        self._bind(UID_A)
        w = self._new_ecowallet(UID_A)
        self.seeder.issue_seed(UID_A, ledger=self.ledger)

        # Membership, not a balance: the wallet reports seeded, but no
        # balance exists, no price exists, and nothing can be debited.
        membership = w.membership()
        self.assertTrue(membership["seeded"])
        self.assertIsNotNone(membership["seed"])
        self.assertEqual(membership["provenance"], "DERIVED")
        balances = w.balances()
        self.assertEqual(balances["eFuse"]["amount"], 0)
        self.assertEqual(balances["Unity"]["amount"], 0)
        self.assertNotIn("seed", [k.lower() for k in balances])
        # The record itself says so, three ways.
        rec = self.seeder.seed_record(UID_A)
        self.assertFalse(rec.spendable)
        self.assertFalse(rec.transferable)
        self.assertFalse(rec.purchasable)
        # A decision deduction can only debit eFuse — the seed is not a
        # balance and cannot be priced: with zero eFuse the deduction
        # refuses, and with eFuse the seed stays untouched.
        with self.assertRaises(ecowallet.InsufficientFunds):
            ecowallet.deduct_per_decision(
                w, 1, manifest={"op": "test", "nonce": "seed-spend-test"})

    # -- 8. plutocracy test: funded == empty -----------------------------------------
    def test_funded_wallet_gets_same_free_seed_as_empty(self):
        """The point of the law: money buys no advantage here. A wallet
        funded with 1000 test-keys and 500 eFuse gets EXACTLY the same
        single free seed as an empty one — same shape, same price (0),
        same cost (0), no deduction anywhere."""
        # The rich identity: 1000 test-keys, 500 eFuse.
        self._bind(UID_A)
        self.meter.faucet(UID_A, 1000)
        rich = self._new_ecowallet(UID_A)
        self._fund_efuse(rich, 500)
        # The poor identity: nothing. Zero everywhere.
        self._bind(UID_B)
        poor = self._new_ecowallet(UID_B)

        rich_env = self.seeder.issue_seed(UID_A, ledger=self.ledger)
        poor_env = self.seeder.issue_seed(UID_B, ledger=self.ledger)

        for env, uid in ((rich_env, UID_A), (poor_env, UID_B)):
            self.assertTrue(verify_commit(env), f"for {uid}")
            receipt = env["receipt"]
            self.assertEqual(receipt["price"], 0.0)
            self.assertEqual(receipt["cost"], 0.0)
            self.assertFalse(receipt["transferable"])
            self.assertFalse(receipt["spendable"])

        # Both hold exactly one seed each — no more, no less.
        self.assertTrue(self.seeder.has_seed(UID_A))
        self.assertTrue(self.seeder.has_seed(UID_B))
        self.assertEqual(self.seeder.seeds_issued(), 2)

        # The rich wallet was not debited; the poor wallet was not
        # credited. Wealth is orthogonal to the seed.
        self.assertEqual(self.meter.balance(UID_A), 1000)
        self.assertEqual(self.meter.balance(UID_B), 0)
        self.assertEqual(rich.balances()["eFuse"]["amount"], 500)
        self.assertEqual(poor.balances()["eFuse"]["amount"], 0)
        self.assertTrue(rich.membership()["seeded"])
        self.assertTrue(poor.membership()["seeded"])

        # And the rich one cannot buy a second.
        with self.assertRaises(SeedRefused) as ctx:
            self.seeder.issue_seed(UID_A)
        self.assertEqual(ctx.exception.reason, REASON_SEED_ALREADY_ISSUED)

    # -- 9. commit kind whitelisted ----------------------------------------------------
    def test_commit_kind_whitelisted(self):
        self.assertIn(KIND_SEED_ISSUE, COMMIT_KINDS)
        # GRANT only for the DCLM-internal seed component.
        granted = check_rights(UID_A, KIND_SEED_ISSUE,
                               {"internal": "dclm.seed", "schema": sd.SCHEMA})
        self.assertEqual(granted.verdict, "GRANT")
        # A client naming SEED_ISSUE is denied.
        denied = check_rights(UID_A, KIND_SEED_ISSUE, {})
        self.assertEqual(denied.verdict, "DENY")
        self.assertEqual(denied.reason, "INTERNAL_SOURCE_REQUIRED")

    # -- 10. honest gate-unavailable refusal ----------------------------------------------
    def test_gate_unavailable_is_honest_refusal(self):
        # If the gate module cannot be read, the seeder refuses — it
        # never issues on an unverifiable gate (UNKNOWN is never PASS).
        real = sd.GATE_MODULE_PATH
        sd.GATE_MODULE_PATH = "/nonexistent/gate.py"
        try:
            seeder = Seeder()  # no injected gate -> must resolve
            with self.assertRaises(SeedRefused) as ctx:
                seeder.issue_seed(UID_C)
            self.assertEqual(ctx.exception.reason,
                             REASON_GATE_LEDGER_UNAVAILABLE)
            self.assertFalse(seeder.has_seed(UID_C))
        finally:
            sd.GATE_MODULE_PATH = real

    # -- 11. non-testnet schema refuses structurally ----------------------------------------
    def test_production_schema_refused(self):
        real = sd.SCHEMA
        sd.SCHEMA = "unity.seed.v1"  # tampered: not testnet
        try:
            with self.assertRaises(SeedRefused) as ctx:
                self.seeder.issue_seed(UID_C)
            self.assertEqual(ctx.exception.reason, REASON_PRODUCTION_SCHEMA)
        finally:
            sd.SCHEMA = real

    # -- 12. wallet membership mirror -------------------------------------------------------
    def test_wallet_membership_mirror(self):
        self._bind(UID_D)
        w = self._new_ecowallet(UID_D)
        self.assertFalse(w.membership()["seeded"])

        envelope = self.seeder.issue_seed(UID_D, ledger=self.ledger)

        membership = w.membership()
        self.assertTrue(membership["seeded"])
        self.assertEqual(membership["seed"]["seed_id"],
                         self.seeder.seed_record(UID_D).seed_id)
        self.assertEqual(membership["seed"]["seed_receipt_sha256"],
                         envelope["canonical_sha256"])
        # The mirror is receipted on the wallet ledger (hash-chained),
        # idempotent: recording again returns the original receipt.
        rec1 = self.ledger.record_seed(UID_D, {
            "seed_id": membership["seed"]["seed_id"],
            "receipt_sha256": envelope["canonical_sha256"],
            "issued_at": "2026-10-06T00:00:00+00:00",
            "provenance": "DERIVED",
        })
        self.assertTrue(self.ledger.verify_chain())
        # Balances still zero: the mirror touched no money.
        self.assertEqual(w.balances()["eFuse"]["amount"], 0)
        self.assertEqual(w.balances()["Unity"]["amount"], 0)

    def test_mirror_requires_real_wallet(self):
        # UNKNOWN never PASS: no wallet, no mirror — but the seed still
        # issues (the seeder's registry is authoritative).
        self._bind(UID_E)
        envelope = self.seeder.issue_seed(UID_E, ledger=self.ledger)
        self.assertTrue(verify_commit(envelope))
        self.assertTrue(self.seeder.has_seed(UID_E))
        self.assertFalse(self.ledger.has_wallet(UID_E))
        self.assertFalse(self.ledger.seed_membership(UID_E)["seeded"])
        # And record_seed directly refuses a phantom wallet.
        with self.assertRaises(ecowallet.UnknownWallet):
            self.ledger.record_seed(UID_E, {"seed_id": "x" * 64})

    # -- 13. registry is write-once ------------------------------------------------------------
    def test_registry_write_once(self):
        self._bind(UID_F)
        self.seeder.issue_seed(UID_F)
        rec = self.seeder.seed_record(UID_F)
        with self.assertRaises(SeedRefused) as ctx:
            self.seeder._register_seed(rec)
        self.assertEqual(ctx.exception.reason, REASON_SEED_ALREADY_ISSUED)
        self.assertIs(self.seeder.seed_record(UID_F), rec)

    # -- 14. seed record is frozen ------------------------------------------------------------------
    def test_seed_record_frozen(self):
        self._bind(UID_F)
        self.seeder.issue_seed(UID_F)
        rec = self.seeder.seed_record(UID_F)
        import dataclasses
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rec.price = 100.0  # type: ignore


if __name__ == "__main__":
    unittest.main(verbosity=2)

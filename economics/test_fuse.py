"""
Tests for THE FUSE (~/workspace/unity-world/economics/fuse.py).

All must pass. Testnet only — the ../keys/ test key signs authorizations
via the node helper (key material never leaves keys/); all other keys are
ephemeral.
"""
import ast
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import fuse as F  # noqa: E402
import wallet as W  # noqa: E402
from fuse import (  # noqa: E402
    GENESIS_UNITY_AMOUNT,
    STATE_ARMED,
    STATE_SPENT,
    Fuse,
    FuseNotArmed,
    FuseRefused,
    FuseReplay,
    _FUSE_TRANSITIONS,
    compute_donation_lock,
    make_fuse_authorization,
    mint_paths,
)
from wallet import (  # noqa: E402
    ED25519_HELPER,
    KEY_ID,
    TEST_PRIV_KEY,
    TEST_PUB_KEY,
    Ledger,
    _canonical_bytes,
    derive_unity_id,
    generate_test_keypair,
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# Emission authority for these tests (CRITICAL-4): one ephemeral keypair
# for the module; test ledgers register its public half, and test
# emission receipts are signed by the private half.
_EMIT_PRIV, _EMIT_PUB = generate_test_keypair()


def _signed_emission_receipt(body: dict) -> dict:
    """Lawful issuance for tests: the emission authority signs the body."""
    return W.sign_emission_receipt(body, _EMIT_PRIV)


def _testnet_pubkey() -> bytes:
    with open(TEST_PUB_KEY, "rb") as fh:
        return fh.read()


def _founder_id() -> str:
    # The same derivation economic_state.testnet_unity_id uses.
    from economic_state import testnet_unity_id
    return testnet_unity_id()


def _testnet_sign(msg: bytes, privkey_path=TEST_PRIV_KEY) -> str:
    """Sign via the node helper with a key FILE — key material never
    leaves keys/ (or the temp file, for ephemeral keys)."""
    proc = subprocess.run(
        ["node", ED25519_HELPER, "sign", privkey_path],
        input=msg, capture_output=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    return proc.stdout.decode().strip()


def _auth(founder_id, amount, nonce, privkey_path=TEST_PRIV_KEY):
    body = {
        "founder_unity_id": founder_id,
        "genesis_unity_amount": amount,
        "nonce": nonce,
    }
    sig = _testnet_sign(_canonical_bytes(body), privkey_path)
    return {**body, "signature": sig, "key_id": KEY_ID}


def _ephemeral_privkey_file():
    priv, pub = generate_test_keypair()
    fd, path = tempfile.mkstemp(prefix="unity-eph-", suffix=".der")
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(priv)
    return priv, pub, path


def _provisioned_ledger(tmp=None):
    tmp = tmp or tempfile.mkdtemp(prefix="unity-fuse-test-")
    state_dir = os.path.join(tmp, "state")
    ledger = Ledger(state_dir=state_dir,
                    emission_authority_pubkey_der=_EMIT_PUB)
    fid = _founder_id()
    ledger.new_wallet(fid, _b64(_testnet_pubkey()))
    return ledger, fid, tmp


class TestFuseTrigger(unittest.TestCase):
    def test_trigger_exactly_once(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        self.assertEqual(fuse.status(), STATE_ARMED)

        receipt = fuse.trigger_fuse(_auth(fid, 1_000_000, "genesis-1"))
        self.assertEqual(fuse.status(), STATE_SPENT)
        self.assertEqual(receipt["kind"], "fuse-genesis")
        self.assertEqual(receipt["amount"], 1_000_000)
        self.assertEqual(receipt["unity_id"], fid)
        self.assertIn("manifest_hash", receipt)
        wallet = ledger.wallet(fid)
        self.assertEqual(wallet.balances()["Unity"]["amount"], 1_000_000)
        # The amount is David's word: REPORTED. The trigger: VERIFIED.
        self.assertEqual(
            receipt["genesis_amount_provenance"], "REPORTED — David's word")

        # Second trigger with the SAME authorization: refused.
        with self.assertRaises(FuseNotArmed):
            fuse.trigger_fuse(_auth(fid, 1_000_000, "genesis-1"))
        # Second trigger with a FRESH, validly-signed authorization:
        # still refused. The launch happened exactly once.
        with self.assertRaises(FuseNotArmed):
            fuse.trigger_fuse(_auth(fid, 2_000_000, "genesis-2"))
        self.assertEqual(wallet.balances()["Unity"]["amount"], 1_000_000)

    def test_spent_fuse_is_deaf(self):
        """After SPENT, trigger_fuse refuses BEFORE parsing the
        authorization — no signature, however valid, is even examined."""
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        fuse.trigger_fuse(_auth(fid, 100, "g1"))
        with self.assertRaises(FuseNotArmed):
            fuse.trigger_fuse("not even a dict")
        with self.assertRaises(FuseNotArmed):
            fuse.trigger_fuse({})

    def test_wrong_signature_refused(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        _, _, evil_path = _ephemeral_privkey_file()
        try:
            with self.assertRaises(FuseRefused):
                fuse.trigger_fuse(_auth(fid, 1_000_000, "evil-1",
                                        privkey_path=evil_path))
        finally:
            os.unlink(evil_path)
        self.assertEqual(fuse.status(), STATE_ARMED)
        self.assertEqual(ledger.wallet(fid).balances()["Unity"]["amount"], 0)

    def test_tampered_body_refused(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        auth = _auth(fid, 1_000_000, "tamper-1")
        auth["genesis_unity_amount"] = 9_999_999  # tamper after signing
        with self.assertRaises(FuseRefused):
            fuse.trigger_fuse(auth)
        self.assertEqual(fuse.status(), STATE_ARMED)

    def test_missing_amount_refused_unknown_never_pass(self):
        """The amount is HELD for David — no default exists, and the fuse
        will not trigger without it in the signed authorization."""
        self.assertIsNone(GENESIS_UNITY_AMOUNT)
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        auth = _auth(fid, 1_000_000, "noamt-1")
        del auth["genesis_unity_amount"]
        with self.assertRaises(FuseRefused):
            fuse.trigger_fuse(auth)
        for bad in (0, -10, "1000000", 1.5, True):
            with self.assertRaises(FuseRefused):
                fuse.trigger_fuse(_auth(fid, bad, f"bad-{bad}"))
        self.assertEqual(fuse.status(), STATE_ARMED)

    def test_wrong_founder_id_refused(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        with self.assertRaises(FuseRefused):
            fuse.trigger_fuse(_auth("unity:testnet:impostor", 500, "imp-1"))
        self.assertEqual(fuse.status(), STATE_ARMED)

    def test_nonce_registered(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        fuse.trigger_fuse(_auth(fid, 50, "nonce-abc"))
        self.assertIn("nonce-abc", fuse._nonces)
        # ...and it persists across a reload.
        fuse2 = Fuse(fid, ledger=ledger,
                     state_dir=os.path.join(tmp, "state"))
        self.assertIn("nonce-abc", fuse2._nonces)
        self.assertEqual(fuse2.status(), STATE_SPENT)

    def test_spent_persists_across_reload(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        fuse.trigger_fuse(_auth(fid, 777, "persist-1"))
        # A brand-new Fuse object against the same state dir: still SPENT.
        fuse2 = Fuse(fid, state_dir=os.path.join(tmp, "state"))
        self.assertEqual(fuse2.status(), STATE_SPENT)
        with self.assertRaises(FuseNotArmed):
            fuse2.trigger_fuse(_auth(fid, 1, "persist-2"))

    def test_founder_wallet_must_be_provisioned(self):
        tmp = tempfile.mkdtemp(prefix="unity-fuse-test-")
        ledger = Ledger(state_dir=os.path.join(tmp, "state"))
        fid = _founder_id()
        fuse = Fuse(fid, ledger=ledger)  # no wallet provisioned
        with self.assertRaises(FuseRefused):
            fuse.trigger_fuse(_auth(fid, 100, "noprovis-1"))
        # No wallet is invented at launch.

    def test_ephemeral_end_to_end_via_make_fuse_authorization(self):
        """make_fuse_authorization (founder's-machine side) + trigger_fuse
        (DCLM side), with ephemeral keys — the full ceremony."""
        priv, pub, _ = _ephemeral_privkey_file()
        tmp = tempfile.mkdtemp(prefix="unity-fuse-test-")
        state_dir = os.path.join(tmp, "state")
        ledger = Ledger(state_dir=state_dir)
        fid = derive_unity_id(pub)
        fd, pub_path = tempfile.mkstemp(suffix=".pub.der")
        with os.fdopen(fd, "wb") as fh:
            fh.write(pub)
        try:
            ledger.new_wallet(fid, _b64(pub))
            fuse = Fuse(fid, founder_pubkey_path=pub_path, ledger=ledger)
            auth = make_fuse_authorization(priv, fid, 4242, nonce="eph-1")
            receipt = fuse.trigger_fuse(auth)
            self.assertEqual(
                ledger.wallet(fid).balances()["Unity"]["amount"], 4242)
            self.assertEqual(fuse.status(), STATE_SPENT)
        finally:
            os.unlink(pub_path)


class TestNoFounderControl(unittest.TestCase):
    def test_fuse_holds_no_private_key(self):
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        for name, value in vars(fuse).items():
            self.assertNotIn("priv", name.lower(),
                             f"fuse attribute {name!r} looks like key "
                             f"material")
            # The testnet PKCS#8 DER is 48 bytes; no attribute may hold a
            # private-key-shaped blob.
            if isinstance(value, bytes):
                self.assertNotEqual(len(value), 48,
                                    f"fuse attribute {name!r} holds 48 key "
                                    f"bytes")
        # The only key bytes present are the PUBLIC key (44-byte SPKI).
        self.assertEqual(len(fuse._founder_pubkey), 44)

    def test_spent_has_no_outgoing_transitions(self):
        self.assertEqual(_FUSE_TRANSITIONS[STATE_SPENT], ())
        self.assertEqual(set(_FUSE_TRANSITIONS),
                         {"ARMED", "TRIGGERED", "SPENT"})

    def test_no_mint_or_admin_function_by_construction(self):
        """AST scan of both modules: no function whose name suggests a
        mint, admin, override, or backdoor path — except the documented
        mint_paths() reporter itself."""
        forbidden = ("mint", "admin", "backdoor", "override", "unseal",
                     "godmode")
        allow = {"mint_paths"}
        for path in (os.path.join(_HERE, "wallet.py"),
                     os.path.join(_HERE, "fuse.py")):
            with open(path) as fh:
                tree = ast.parse(fh.read())
            names = [n.name for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef)]
            for name in names:
                if any(f in name.lower() for f in forbidden):
                    self.assertIn(
                        name, allow,
                        f"{path}: forbidden function name {name!r}")
        # And the Fuse class itself exposes no admin-flavored attribute.
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        for name in dir(fuse):
            self.assertNotIn("admin", name.lower())
            self.assertNotIn("override", name.lower())
            self.assertNotIn("backdoor", name.lower())

    def test_founder_wallet_is_ordinary_after_launch(self):
        """Post-launch, the founder's wallet has no privileges: it cannot
        mint, cannot re-trigger, cannot move Unity to anyone."""
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        fuse.trigger_fuse(_auth(fid, 1_000, "ord-1"))
        w = ledger.wallet(fid)
        # Unity is bound to the ID: not transferable, even by the founder.
        # (Grant a tier first so the test reaches the Unity gate, not the
        # tier gate — the founder signs via the key FILE, never raw bytes.)
        ring_priv, ring_pub = generate_test_keypair()
        other_id = derive_unity_id(ring_pub)
        ledger.new_wallet(other_id, _b64(ring_pub))
        other = ledger.wallet(other_id)
        tier_body = {"granter_unity_id": fid,
                     "grantee_unity_id": other_id,
                     "tier": "friend", "nonce": "founder-tier-1"}
        tier_grant = {**tier_body,
                      "signature": _testnet_sign(
                          _canonical_bytes(tier_body)),
                      "key_id": KEY_ID}
        W.apply_tier_grant(ledger, tier_grant)
        from wallet import UnityBindingError, share
        with self.assertRaises(UnityBindingError):
            share(w, other, {"kind": "funds", "token": "Unity", "amount": 1},
                  {"nonce": "founder-move"})
        # No mint method exists on the wallet or ledger public API.
        for obj in (w, ledger, fuse):
            for name in dir(obj):
                self.assertNotIn("mint", name.lower())
        # The founder CAN still use ordinary flows (deduct/donate need
        # eFuse, which the founder doesn't have — the point is the wallet
        # obeys the same gates as everyone else).
        from wallet import InsufficientFunds, deduct_per_decision
        with self.assertRaises(InsufficientFunds):
            deduct_per_decision(w, 1, {"nonce": "founder-deduct"})

    def test_mint_paths_are_exactly_two(self):
        paths = mint_paths()
        self.assertEqual(len(paths), 2)
        self.assertIn("trigger_fuse", paths[0])
        self.assertIn("receive_unity_emission", paths[1])


class TestUnityMintPaths(unittest.TestCase):
    def test_unity_only_via_fuse_or_merit_receipt(self):
        """Behavioral: the only ways a Unity balance increases are the
        fuse genesis and a merit-gated receipt."""
        ledger, fid, tmp = _provisioned_ledger()
        w = ledger.wallet(fid)
        # merit-gated Unity emission: accepted
        rec = _signed_emission_receipt({
            "kind": "merit-emission",
            "manifest_hash": "mh-unity-merit-1",
            "unity_id": fid,
            "token": "Unity",
            "amount": 25,
            "pool": "machine",
            "merit_weight": 3,
            "gated": True,
            "epoch": "epoch-7",
            "provenance": "REPORTED",
        })
        r = W.receive_unity_emission(w, 25, rec)
        self.assertEqual(w.balances()["Unity"]["amount"], 25)
        # idempotent on the receipt
        r2 = W.receive_unity_emission(w, 25, rec)
        self.assertEqual(r, r2)
        self.assertEqual(w.balances()["Unity"]["amount"], 25)
        # every other receipt kind: refused
        for kind in ("airdrop", "faucet", "admin-grant", "fuse-genesis"):
            bad = dict(rec, kind=kind,
                       manifest_hash=f"mh-bad-{kind}")
            with self.assertRaises(W.InvalidReceipt):
                W.receive_unity_emission(w, 1, bad)
        self.assertEqual(w.balances()["Unity"]["amount"], 25)


class TestFuseGenesisMintGate(unittest.TestCase):
    """CRITICAL-3 closure: the Unity mint is gated to the fuse
    authorization. Worker 2's bare-ledger reproducer must fail, and every
    mint must ride a lawful, mid-trigger fuse ticket."""

    def _fresh_wallet(self, ledger):
        priv, pub = generate_test_keypair()
        uid = derive_unity_id(pub)
        ledger.new_wallet(uid, _b64(pub))
        return uid

    def _mid_trigger_ticket(self, ledger, fid, amount, nonce):
        """Hand-issue a ticket the way trigger_fuse does: drive the real
        state machine to TRIGGERED (post authorization-check point) and
        issue. Test-only; production path is trigger_fuse."""
        fuse = Fuse(fid, ledger=ledger)
        fuse._transition("TRIGGERED")
        ticket = ledger._issue_genesis_ticket(
            fuse, _auth(fid, amount, nonce))
        return fuse, ticket

    def test_gauntlet_reproducer_now_fails(self):
        """Worker 2's CRITICAL-3 reproducer, verbatim shape: bare ledger
        reference, ledger._apply_fuse_genesis(fresh_uid, 777, {}, mh) —
        no fuse authorization. Refused; no Unity minted."""
        ledger, fid, tmp = _provisioned_ledger()
        fresh = self._fresh_wallet(ledger)
        mh = "ab" * 32
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fresh, 777, {}, mh)
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fresh, 777, {}, mh, ticket=None)
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fresh, 777, {}, mh,
                                       ticket="forged-ticket")
        self.assertEqual(
            ledger.wallet(fresh).balances()["Unity"]["amount"], 0)

    def test_no_ticket_after_spent(self):
        """After a lawful launch the fuse is SPENT: no new ticket can be
        issued, so no second mint is reachable."""
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        fuse.trigger_fuse(_auth(fid, 100, "noticket-1"))
        self.assertEqual(fuse.status(), STATE_SPENT)
        with self.assertRaises(W.WalletError):
            ledger._issue_genesis_ticket(fuse, _auth(fid, 100, "noticket-2"))
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fid, 100, {}, "ef" * 32)

    def test_ticket_from_spent_fuse_refused(self):
        """A ticket that no longer rides a mid-trigger fuse (fuse went
        SPENT after issuance) is refused at the mint gate."""
        ledger, fid, tmp = _provisioned_ledger()
        fuse, ticket = self._mid_trigger_ticket(ledger, fid, 100,
                                                "spent-ticket-1")
        fuse._transition("SPENT")
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fid, 100, {}, ticket._manifest_hash,
                                       ticket)
        self.assertEqual(
            ledger.wallet(fid).balances()["Unity"]["amount"], 0)

    def test_ticket_parameters_bound_to_signed_authorization(self):
        """A ticket cannot be repurposed: amount, unity_id, and manifest
        must match the signed authorization body."""
        ledger, fid, tmp = _provisioned_ledger()
        fresh = self._fresh_wallet(ledger)
        fuse, ticket = self._mid_trigger_ticket(ledger, fid, 100, "bound-1")
        mh = ticket._manifest_hash
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fid, 777, {}, mh, ticket)
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fresh, 100, {}, mh, ticket)
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fid, 100, {}, "cd" * 32, ticket)
        self.assertEqual(
            ledger.wallet(fid).balances()["Unity"]["amount"], 0)
        self.assertEqual(
            ledger.wallet(fresh).balances()["Unity"]["amount"], 0)
        # The refusals did not consume the ticket: the lawful call with
        # the same ticket still mints exactly once...
        receipt = ledger._apply_fuse_genesis(fid, 100, {}, mh, ticket)
        self.assertEqual(receipt["amount"], 100)
        self.assertEqual(receipt["kind"], "fuse-genesis")
        self.assertEqual(
            ledger.wallet(fid).balances()["Unity"]["amount"], 100)
        # ...but the same ticket object cannot mint twice.
        with self.assertRaises(W.WalletError):
            ledger._apply_fuse_genesis(fid, 100, {}, mh, ticket)
        self.assertEqual(
            ledger.wallet(fid).balances()["Unity"]["amount"], 100)

    def test_ticket_bound_to_its_ledger(self):
        """A ticket issued on one ledger is refused on another."""
        ledger, fid, tmp = _provisioned_ledger()
        other_dir = tempfile.mkdtemp(prefix="unity-fuse-other-")
        other = Ledger(state_dir=os.path.join(other_dir, "state"))
        other.new_wallet(fid, _b64(_testnet_pubkey()))
        fuse, ticket = self._mid_trigger_ticket(ledger, fid, 100,
                                                "xledger-1")
        with self.assertRaises(W.WalletError):
            other._apply_fuse_genesis(fid, 100, {}, ticket._manifest_hash,
                                      ticket)
        self.assertEqual(
            other.wallet(fid).balances()["Unity"]["amount"], 0)

    def test_rogue_fuse_cannot_relaunch_ledger(self):
        """After David's lawful launch, a second fuse — even with its own
        validly-signed authorization — cannot mint on the same ledger.
        One launch per ledger."""
        ledger, fid, tmp = _provisioned_ledger()
        fuse = Fuse(fid, ledger=ledger)
        fuse.trigger_fuse(_auth(fid, 1_000_000, "genesis-rogue-1"))
        self.assertEqual(fuse.status(), STATE_SPENT)

        rpriv, rpub = generate_test_keypair()
        rid = derive_unity_id(rpub)
        fd, rpub_path = tempfile.mkstemp(suffix=".pub.der")
        with os.fdopen(fd, "wb") as fh:
            fh.write(rpub)
        try:
            ledger.new_wallet(rid, _b64(rpub))
            rogue_dir = tempfile.mkdtemp(prefix="unity-rogue-fuse-")
            rogue = Fuse(rid, founder_pubkey_path=rpub_path,
                         ledger=ledger, state_dir=rogue_dir)
            rauth = make_fuse_authorization(rpriv, rid, 5_000,
                                            nonce="rogue-launch-1")
            with self.assertRaises(W.WalletError):
                rogue.trigger_fuse(rauth)
        finally:
            os.unlink(rpub_path)
        self.assertEqual(
            ledger.wallet(rid).balances()["Unity"]["amount"], 0)
        self.assertEqual(
            ledger.wallet(fid).balances()["Unity"]["amount"], 1_000_000)


class TestComputeDonationLockContract(unittest.TestCase):
    def test_raw_dicts(self):
        lock = compute_donation_lock([
            {"donor_unity_id": "unity:testnet:donor1", "amount": 300,
             "kind": "efuse", "provenance": "REPORTED",
             "donation_receipt": "dr-1"},
            {"donor_unity_id": "unity:testnet:donor1", "amount": 700,
             "kind": "fiat", "provenance": "REPORTED"},
            {"donor_unity_id": None, "amount": 5},  # anonymous: skipped
        ])
        self.assertEqual(lock["address"]["value"], "UNKNOWN")
        self.assertEqual(lock["address"]["provenance"], "UNKNOWN")
        self.assertEqual(len(lock["inflow"]), 2)
        for entry in lock["inflow"]:
            self.assertEqual(entry["accrues"], "HONOR")
            self.assertEqual(entry["never_accrues"], "MERIT")
        self.assertEqual(
            lock["honor_accrued"]["per_unity_id"]["unity:testnet:donor1"], 2)
        self.assertIn("never re-emitted to the same donor",
                      lock["donor_exclusion"]["rule"])

    def test_wallet_donate_receipts(self):
        tmp = tempfile.mkdtemp(prefix="unity-fuse-test-")
        ledger = Ledger(state_dir=os.path.join(tmp, "state"),
                        emission_authority_pubkey_der=_EMIT_PUB)
        priv, pub = generate_test_keypair()
        uid = derive_unity_id(pub)
        w = ledger.new_wallet(uid, _b64(pub))
        rec = _signed_emission_receipt({
            "kind": "merit-emission", "manifest_hash": "mh-fund-d",
            "unity_id": uid, "token": "eFuse", "amount": 2_000,
            "pool": "human", "merit_weight": 1, "gated": True,
            "epoch": "e1", "provenance": "REPORTED",
        })
        W.receive_emission(w, 2_000, rec)
        d = W.donate(w, 2_000, "lock:testnet:core-cause",
                     {"nonce": "d-lock"})
        lock = compute_donation_lock([d])
        self.assertEqual(len(lock["inflow"]), 1)
        self.assertEqual(lock["inflow"][0]["donor_unity_id"], uid)
        self.assertEqual(lock["inflow"][0]["kind"], "efuse")
        self.assertEqual(len(lock["inflow"][0]["receipt_id"]), 64)
        self.assertEqual(lock["inflow"][0]["source_receipt"],
                         d["manifest_hash"])

    def test_economic_state_integration(self):
        """economic_state.py picks up compute_donation_lock and calls it."""
        import economic_state as es
        self.assertTrue(es.worker_modules_present()["fuse"])
        state = es.compute_economic_state(donations=[
            {"donor_unity_id": "unity:testnet:x", "amount": 50,
             "kind": "efuse", "provenance": "REPORTED",
             "donation_receipt": "dr-x"},
        ])
        lock = state["donation_lock"]
        self.assertEqual(lock["address"]["value"], "UNKNOWN")
        self.assertEqual(lock["inflow"][0]["accrues"], "HONOR")
        self.assertEqual(lock["inflow"][0]["never_accrues"], "MERIT")


if __name__ == "__main__":
    unittest.main(verbosity=2)

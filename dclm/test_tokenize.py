"""
Tests for the DCLM tokenization engine (token_engine.py, public path
dclm/tokenize.py).

David's order: the actual process by which value becomes tokens.
Receipt -> token, DCLM-rights, DCLM-writes, DCLM-tokenizes.

David's word, 2026-10-06 ~3:35 AM EDT (LAW, effective immediately):
  * MERIT is TRANSFERABLE — sold, gifted, transferred between Unity IDs,
    all receipted. Supersedes the earlier "Merit non-transferable" law
    (recorded explicitly in economics/DECISIONS.md §13, not silently
    edited away).
  * UNITY is NON-TRANSFERABLE — no exceptions. The bound-transfer-sale
    concept is DEAD: bound_sale() and every bound-sale path were REMOVED
    from the build (code, tests, docs).
  * The standing-vs-value distinction is STRUCTURAL: every Merit token
    carries immutable origin_earner_id + origin_receipt_ref; transfers
    change owner only; standing(identity) sums by origin. A buyer gains
    economic value and ZERO standing, by construction. The emission gate
    (meter.py) reads standing(), never the balance.

NOTE on import order: stdlib imports come FIRST, before the dclm dir
joins sys.path, so linecache/traceback/unittest bind the real stdlib
`tokenize`; the `tokenize` name imported below is the DCLM shim, which
is cycle-safe and stdlib-transparent (see tokenize.py).

All must pass. Testnet only.
"""
import base64
import dataclasses
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# stdlib `tokenize` is ALREADY in sys.modules (unittest -> traceback ->
# linecache pulled it in before this dir joined sys.path), and the
# sys.modules cache wins over sys.path — so a bare `import tokenize`
# would bind the STDLIB module, not the DCLM shim. Evict it and re-import:
# the shim is stdlib-transparent (delegates tokenize.open et al. to the
# real stdlib module), and linecache holds its own direct reference, so
# traceback formatting keeps working.
sys.modules.pop("tokenize", None)

import tokenize as tok  # noqa: E402 — the DCLM shim (cycle-safe)
import token_engine as eng  # noqa: E402 — the implementation
from token_engine import (  # noqa: E402
    EFuseToken,
    HonorRecord,
    MeritRecord,
    TokenizeRefused,
    Tokenizer,
    TransferReceipt,
    UnityHolding,
    UnityMintRefused,
    UnityToken,
    assert_no_unity_rebind,
    assert_single_merit_transfer_path,
    assert_single_mint_path,
    merit_balance,
    merit_transfer,
    merit_transfer_paths,
    mint_paths,
    peg_ratio,
    set_peg_ratio,
    sign_gate_receipt,
    standing,
    tokenize,
    unity_transfer_paths,
)
from rights import COMMIT_KINDS, check_rights  # noqa: E402
from writes import verify_commit  # noqa: E402

TEST_IDENTITY = "unity:testnet:1e26f0d9e8c46818"  # same test identity as gate
BUYER_IDENTITY = "unity:testnet:9f8e7d6c5b4a3210"
THIRD_IDENTITY = "unity:testnet:aaaa1111bbbb2222"
FOURTH_IDENTITY = "unity:testnet:dddd4444eeee5555"

_ED25519_JS = os.path.join(_HERE, "ed25519.js")


def _gen_test_keypair():
    """Ephemeral Ed25519 keypair for transfer-authorization tests."""
    script = (
        "const c=require('crypto');"
        "const k=c.generateKeyPairSync('ed25519');"
        "console.log(k.privateKey.export({format:'der',type:'pkcs8'})"
        ".toString('base64'));"
        "console.log(k.publicKey.export({format:'der',type:'spki'})"
        ".toString('base64'));"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True,
                          timeout=30)
    if proc.returncode != 0:
        raise RuntimeError("test keygen failed")
    priv_b64, pub_b64 = proc.stdout.decode().strip().splitlines()
    return base64.b64decode(priv_b64), base64.b64decode(pub_b64)


def _unity_id_for(pub_der: bytes) -> str:
    """The testnet Unity ID for a pubkey — the binding the engine checks."""
    return "unity:testnet:" + hashlib.sha256(pub_der).hexdigest()


def _node_sign_test(priv_der: bytes, msg: bytes) -> str:
    fd, path = tempfile.mkstemp(prefix="tmt-auth-", suffix=".der")
    os.fchmod(fd, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(priv_der)
        proc = subprocess.run(["node", _ED25519_JS, "sign", path],
                              input=msg, capture_output=True, timeout=30)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise RuntimeError("test signing failed")
    return proc.stdout.decode().strip()


def _signed_auth(keys: dict, frm: str, to: str, amount, reason: str,
                 nonce: str | None = None) -> dict:
    """Build a sender-signed transfer authorization the way the sender's
    device would: canonical body + Ed25519 signature. Must match the
    engine's canonical body byte-for-byte."""
    body = {"op": "merit-transfer", "from": frm, "to": to,
            "amount": float(amount), "reason": reason.strip(),
            "nonce": nonce or uuid.uuid4().hex}
    msg = json.dumps(body, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return {**body,
            "signature": _node_sign_test(keys["priv"], msg),
            "pubkey_b64": base64.b64encode(keys["pub"]).decode()}


def _transfer_keys(*names):
    """{name: {priv, pub, id}} — ephemeral identities for transfer tests."""
    out = {}
    for name in names:
        priv, pub = _gen_test_keypair()
        out[name] = {"priv": priv, "pub": pub, "id": _unity_id_for(pub)}
    return out


def _fund(t, identity, merit_value, seed):
    """Accrue merit to identity via a gate-signed work receipt (the
    CRITICAL-5 gate-signature rule, using the test gate key)."""
    r = work_receipt(identity=identity, merit_value=merit_value, seed=seed)
    r["prev_hash"] = t._gate_chain_head
    t.tokenize(sign_gate_receipt(r))
    return t


def _manifest(seed):
    return hashlib.sha256(f"manifest:{seed}".encode()).hexdigest()


def _token(seed):
    return hashlib.sha256(f"unity-token:{seed}".encode()).hexdigest()


def work_receipt(identity=TEST_IDENTITY, merit_value=100.0,
                 provenance="VERIFIED", schema="unity.relay.v1.testnet",
                 epoch=3, seed="work-1",
                 prev_hash=eng.GENESIS_CHAIN_ANCHOR, **extra):
    r = {
        "schema": schema,
        "receipt_id": f"rcpt-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "work",
        "provenance": provenance,
        "epoch": epoch,
        "merit_value": merit_value,
        "prev_hash": prev_hash,
    }
    r.update(extra)
    # Gate-signed: the test stands in for the DCLM gate with test keys.
    # The signature covers the canonical gate body (never the caller's
    # "provenance" claim).
    return eng.sign_gate_receipt(r)


def donation_receipt(identity=TEST_IDENTITY, amount=25.0, kind="fiat",
                     provenance="VERIFIED", seed="don-1",
                     prev_hash=eng.GENESIS_CHAIN_ANCHOR):
    r = {
        "schema": "unity.relay.v1.testnet",
        "receipt_id": f"rcpt-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "donation",
        "provenance": provenance,
        "epoch": 3,
        "donation": {"amount": amount, "kind": kind},
        "prev_hash": prev_hash,
    }
    return eng.sign_gate_receipt(r)


def genesis_receipt(identity=TEST_IDENTITY, seed="gen-1",
                    token_seed="tok-1", merit_proof_ref=None,
                    prev_hash=eng.GENESIS_CHAIN_ANCHOR):
    r = {
        "schema": "unity.relay.v1.testnet",
        "receipt_id": f"rcpt-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "genesis",
        "provenance": "VERIFIED",
        "epoch": 0,
        "token_id": _token(token_seed),
        "merit_proof_ref": merit_proof_ref or _manifest("origin-merit"),
        "prev_hash": prev_hash,
    }
    return eng.sign_gate_receipt(r)


def fresh_engine(E=4.0):
    t = Tokenizer()
    if E is not None:
        t.set_peg_ratio(E, {"authority": "david"})
    return t


def earning_engine():
    """Engine where TEST_IDENTITY earned 80 merit from its own work."""
    t = fresh_engine()
    t.tokenize(work_receipt(identity=TEST_IDENTITY, merit_value=80.0,
                            seed="earn-1"))
    return t


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------

class TestHappyPath(unittest.TestCase):
    def setUp(self):
        self.t = fresh_engine()

    def test_verified_work_receipt_produces_bundle(self):
        b = self.t.tokenize(work_receipt(merit_value=100.0))
        self.assertEqual(b.unity_id, TEST_IDENTITY)
        self.assertIsNotNone(b.efuse)
        self.assertIsNotNone(b.merit)
        self.assertIsNone(b.honor)  # work never records Honor

    def test_efuse_token_fields(self):
        b = self.t.tokenize(work_receipt(merit_value=100.0, epoch=7))
        body = b.efuse["receipt"]
        self.assertEqual(body["token_type"], "EFUSE")
        self.assertEqual(body["owner_unity_id"], TEST_IDENTITY)
        self.assertAlmostEqual(body["amount"], 25.0)   # 100 / E(4)
        self.assertEqual(body["peg_E"], 4.0)           # E recorded in token
        self.assertEqual(body["epoch"], 7)
        self.assertEqual(body["action_ref"], "work")
        self.assertEqual(body["merit_proof_ref"], _manifest("work-1"))
        self.assertEqual(body["provenance"], "DERIVED")
        self.assertTrue(body["testnet"])
        self.assertTrue(verify_commit(b.efuse))        # DCLM-signed

    def test_every_token_unity_bound_and_provenanced(self):
        b = self.t.tokenize(work_receipt())
        for env in (b.efuse, b.merit):
            body = env["receipt"]
            bound = body.get("owner_unity_id") or body.get("unity_id")
            self.assertEqual(bound, TEST_IDENTITY)
            self.assertIn(body["provenance"], ("DERIVED", "VERIFIED"))
            self.assertTrue(body["testnet"])
        self.assertEqual(b.unity_binding["unity_id"], TEST_IDENTITY)

    def test_merit_accrued_with_origin_fields(self):
        b = self.t.tokenize(work_receipt(merit_value=40.0))
        body = b.merit["receipt"]
        self.assertEqual(body["record_type"], "MERIT_ACCRUAL")
        self.assertEqual(body["delta"], 40.0)
        self.assertEqual(body["score_after"], 40.0)
        # Origin is on the record, immutable, set at accrual.
        self.assertEqual(body["origin_earner_id"], TEST_IDENTITY)
        self.assertEqual(body["origin_receipt_ref"], _manifest("work-1"))
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 40.0)
        self.assertEqual(self.t.standing(TEST_IDENTITY), 40.0)
        self.assertTrue(verify_commit(b.merit))

    def test_donation_produces_honor_only(self):
        b = self.t.tokenize(donation_receipt())
        self.assertIsNone(b.efuse)
        self.assertIsNone(b.merit)
        self.assertIsNotNone(b.honor)
        body = b.honor["receipt"]
        self.assertEqual(body["record_type"], "HONOR_RECORD")
        self.assertEqual(body["unity_id"], TEST_IDENTITY)
        self.assertTrue(body["permanent"])
        self.assertFalse(body["spendable"])
        self.assertFalse(body["transferable"])
        self.assertEqual(len(self.t.honor_records(TEST_IDENTITY)), 1)
        self.assertTrue(verify_commit(b.honor))

    def test_genesis_binds_holding_without_mint(self):
        b = self.t.tokenize(genesis_receipt())
        self.assertIsNone(b.efuse)
        self.assertIsNone(b.merit)
        self.assertIsNone(b.honor)
        self.assertEqual(b.unity_binding["unity_id"], TEST_IDENTITY)
        self.assertEqual(b.unity_binding["token_id"], _token("tok-1"))
        self.assertEqual(self.t.unity_holder(_token("tok-1")), TEST_IDENTITY)

    def test_shim_exposes_engine_api(self):
        # The mandated public path dclm/tokenize.py works as specified.
        self.assertIs(tok.tokenize, eng.tokenize)
        self.assertIs(tok.set_peg_ratio, eng.set_peg_ratio)
        self.assertIs(tok.Tokenizer, eng.Tokenizer)
        self.assertIs(tok.merit_transfer, eng.merit_transfer)
        self.assertIs(tok.standing, eng.standing)
        self.assertIs(tok.merit_balance, eng.merit_balance)
        # The bound sale is dead: no bound_sale on engine or shim.
        self.assertFalse(hasattr(eng, "bound_sale"))
        self.assertFalse(hasattr(tok, "bound_sale"))


# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------

class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.t = fresh_engine()

    def _assert_refused(self, receipt, reason):
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(receipt)
        self.assertEqual(ctx.exception.reason, reason)
        # zero tokens, zero ledger change
        self.assertEqual(self.t._merit_slices, [])
        self.assertEqual(self.t.honor_ledger, {})
        self.assertEqual(self.t.efuse_registry, {})
        self.assertEqual(self.t._unity_registry, {})

    def test_unknown_provenance_refused(self):
        r = work_receipt()
        r["provenance"] = "UNKNOWN"
        self._assert_refused(r, eng.REASON_UNVERIFIED_RECEIPT)

    def test_reported_not_verified_refused(self):
        r = work_receipt()
        r["provenance"] = "REPORTED"
        self._assert_refused(r, eng.REASON_UNVERIFIED_RECEIPT)

    def test_missing_unity_id_refused(self):
        # Contract change 2026-10-06: the purification medium refuses the
        # anonymous receipt on entry (PurificationRefused), before the
        # engine's own MISSING_UNITY_ID refusal runs.
        from purify import PurificationRefused
        r = work_receipt()
        del r["unity_id"]
        with self.assertRaises(PurificationRefused):
            self.t.tokenize(r)

    def test_production_schema_refused(self):
        r = work_receipt()
        r["schema"] = "dualis.relay.v1"  # production-looking, no testnet
        self._assert_refused(r, eng.REASON_PRODUCTION_SCHEMA)

    def test_production_key_format_refused(self):
        r = work_receipt()
        r["schema"] = "unity.relay.v1.mainnet"
        self._assert_refused(r, eng.REASON_PRODUCTION_SCHEMA)

    def test_non_testnet_unity_id_refused(self):
        # Contract change 2026-10-06: the purification medium refuses the
        # non-testnet identity on entry (PurificationRefused), before the
        # engine's own INVALID_UNITY_ID refusal runs.
        from purify import PurificationRefused
        r = work_receipt()
        r["unity_id"] = "unity:1e26f0d9e8c46818"
        with self.assertRaises(PurificationRefused):
            self.t.tokenize(r)
        # Nothing minted: the refusal happens before any engine logic.
        self.assertEqual(self.t._merit_slices, [])
        self.assertEqual(self.t.efuse_registry, {})

    def test_malformed_receipt_refused(self):
        # Contract change 2026-10-06: the medium refuses the anonymous
        # payload on entry (PurificationRefused).
        from purify import PurificationRefused
        with self.assertRaises(PurificationRefused):
            self.t.tokenize({"nope": True})

    def test_unsupported_kind_refused(self):
        r = work_receipt()
        r["kind"] = "airdrop"
        self._assert_refused(r, eng.REASON_UNSUPPORTED_RECEIPT_KIND)

    def test_non_positive_merit_refused(self):
        r = work_receipt(merit_value=0.0)
        self._assert_refused(r, eng.REASON_NON_POSITIVE_MERIT)

    def test_donation_refuses_without_peg(self):
        # Donations never need the peg — Honor records regardless.
        t = fresh_engine(E=None)  # E unset
        b = t.tokenize(donation_receipt())
        self.assertIsNotNone(b.honor)


# ---------------------------------------------------------------------------
# verified provenance — CRITICAL-5 closure
# (provenance is ESTABLISHED by tokenize(), never asserted by the caller)
# ---------------------------------------------------------------------------

class TestVerifiedProvenance(unittest.TestCase):
    """The gauntlet proved provenance was a self-asserted string:
    tokenize() minted on provenance=="VERIFIED". Now the gate signature
    and the chain link are verified BY tokenize() itself; the bundle's
    gate_verdict/gate_verification record the verification result, not
    the caller's claim."""

    def setUp(self):
        self.t = fresh_engine()

    def test_valid_signed_chained_receipt_tokenizes_labeled_by_verification(self):
        b = self.t.tokenize(work_receipt(merit_value=100.0, seed="vp-1"))
        # The output label reflects the VERIFICATION RESULT.
        self.assertEqual(b.gate_verdict, "VERIFIED")
        v = b.gate_verification
        self.assertEqual(v["verified_label"], "VERIFIED")
        self.assertEqual(v["gate_key_id"], eng.GATE_KEY_ID)
        self.assertEqual(v["signature_algorithm"], "Ed25519")
        self.assertEqual(v["verified_by"], "tokenize() self-verification")
        self.assertEqual(v["caller_claim"], "VERIFIED")  # recorded, not trusted
        self.assertIn("→", v["chain_link"])
        # The chain advanced: the accepted receipt's manifest is the head.
        self.assertEqual(self.t.gate_chain_head(), _manifest("vp-1"))
        self.assertEqual(self.t.gate_chain(), [_manifest("vp-1")])
        # …and the lawful happy path still mints.
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 100.0)

    def test_self_asserted_verified_on_garbage_refused(self):
        # THE GAUNTLET REPRODUCER (CRITICAL-5): a well-formed receipt
        # that merely ASSERTS provenance="VERIFIED" — no gate signature.
        # Before the fix this minted MeritRecord + EFuseToken.
        r = {
            "schema": "unity.relay.v1.testnet",
            "unity_id": TEST_IDENTITY,
            "receipt_id": "rcpt-forged-tok",
            "manifest_hash": _manifest("forged-tok"),
            "kind": "work",
            "merit_value": 50.0,
            "provenance": "VERIFIED",   # self-asserted string
            "epoch": 7,
            "prev_hash": eng.GENESIS_CHAIN_ANCHOR,
        }
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_UNVERIFIED_RECEIPT)
        # Zero tokens, zero ledger change — the forgery minted nothing.
        self.assertEqual(self.t._merit_slices, [])
        self.assertEqual(self.t.honor_ledger, {})
        self.assertEqual(self.t.efuse_registry, {})
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 0.0)

    def test_claimed_verified_with_bad_signature_refused(self):
        # Caller claims VERIFIED and attaches a signature-shaped value
        # that does not verify — refused all the same.
        r = work_receipt(merit_value=50.0, seed="vp-bad")
        r["signature"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_UNVERIFIED_RECEIPT)
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 0.0)

    def test_tampered_body_breaks_gate_signature(self):
        # A gate-signed receipt, then merit_value altered post-signing:
        # the signature no longer verifies — the tamper is caught.
        r = work_receipt(merit_value=50.0, seed="vp-tamper")
        r["merit_value"] = 5000.0
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_UNVERIFIED_RECEIPT)
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 0.0)

    def test_signature_from_wrong_key_refused(self):
        # Signed by a key that is NOT the gate key: verification fails.
        priv, _pub = _gen_test_keypair()
        r = work_receipt(merit_value=50.0, seed="vp-wrongkey")
        body = eng._gate_signed_body(r)
        r["signature"] = _node_sign_test(
            priv, eng._canonical_bytes(body))
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_UNVERIFIED_RECEIPT)
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 0.0)

    def test_chain_fork_refused(self):
        # Two different receipts sharing one prev_hash: the first is
        # accepted, the second is a fork — CHAIN_BREAK.
        self.t.tokenize(work_receipt(merit_value=10.0, seed="vp-f1"))
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(work_receipt(merit_value=20.0, seed="vp-f2",
                                         prev_hash=eng.GENESIS_CHAIN_ANCHOR))
        self.assertEqual(ctx.exception.reason, eng.REASON_CHAIN_BREAK)
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 10.0)

    def test_chain_link_must_match_head(self):
        # A validly signed receipt whose prev_hash points at the wrong
        # link is refused — the chain is a chain, not a suggestion.
        # (work_receipt signs whatever prev_hash it is given, so the
        # signature here is valid — only the link is wrong.)
        r = work_receipt(merit_value=10.0, seed="vp-link",
                         prev_hash="f" * 64)
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_CHAIN_BREAK)

    def test_replay_of_accepted_receipt_refused(self):
        # An accepted receipt can never be re-accepted: its prev_hash no
        # longer matches the advanced head. (The chain is the replay
        # protection.)
        r = work_receipt(merit_value=10.0, seed="vp-replay")
        self.t.tokenize(r)
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_CHAIN_BREAK)
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 10.0)

    def test_refused_receipt_stays_retryable(self):
        # Refusals consume nothing: a receipt refused for peg-unset
        # keeps its chain position and tokenizes after David sets E.
        t = fresh_engine(E=None)
        r = work_receipt(merit_value=10.0, seed="vp-retry")
        with self.assertRaises(TokenizeRefused) as ctx:
            t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_PEG_E_UNSET)
        self.assertEqual(t.gate_chain_head(), eng.GENESIS_CHAIN_ANCHOR)
        t.set_peg_ratio(4.0, {"authority": "david"})
        b = t.tokenize(r)
        self.assertEqual(b.gate_verdict, "VERIFIED")
        self.assertEqual(t.merit_balance(TEST_IDENTITY), 10.0)

    def test_refusals_are_signed_and_logged(self):
        before = len(self.t._receipt_log)
        with self.assertRaises(TokenizeRefused):
            self.t.tokenize(work_receipt(provenance="UNKNOWN"))
        self.assertEqual(len(self.t._receipt_log), before + 1)
        refusal_env = self.t._receipt_log[-1]
        self.assertEqual(refusal_env["receipt"]["outcome"], "REFUSED")
        self.assertTrue(verify_commit(refusal_env))


# ---------------------------------------------------------------------------
# the peg gate — HELD_FOR_DAVID
# ---------------------------------------------------------------------------

class TestPegGate(unittest.TestCase):
    def test_peg_unset_initially(self):
        t = Tokenizer()
        E, prov = t.peg_ratio()
        self.assertIsNone(E)
        self.assertEqual(prov, "HELD_FOR_DAVID")

    def test_efuse_emission_refused_until_E_set(self):
        t = fresh_engine(E=None)
        with self.assertRaises(TokenizeRefused) as ctx:
            t.tokenize(work_receipt())
        self.assertEqual(ctx.exception.reason, eng.REASON_PEG_E_UNSET)
        self.assertEqual(t._merit_slices, [])  # refusal is pre-mint
        self.assertEqual(t.efuse_registry, {})

    def test_set_peg_requires_davids_word(self):
        t = Tokenizer()
        with self.assertRaises(TokenizeRefused) as ctx:
            t.set_peg_ratio(4.0, {"authority": "someone-else"})
        self.assertEqual(ctx.exception.reason, eng.REASON_PEG_AUTHORITY)
        with self.assertRaises(TokenizeRefused):
            t.set_peg_ratio(4.0, {})
        with self.assertRaises(TokenizeRefused) as ctx2:
            t.set_peg_ratio(0, {"authority": "david"})
        self.assertEqual(ctx2.exception.reason, eng.REASON_NON_POSITIVE_E)

    def test_set_peg_then_emits_with_E_recorded(self):
        t = Tokenizer()
        rec = t.set_peg_ratio(2.5, {"authority": "david"})
        self.assertEqual(rec["E"], 2.5)
        # Honest label: REPORTED (testnet stand-in), never VERIFIED.
        self.assertTrue(rec["provenance"].startswith("REPORTED"))
        b = t.tokenize(work_receipt(merit_value=100.0))
        body = b.efuse["receipt"]
        self.assertAlmostEqual(body["amount"], 40.0)  # 100 / 2.5
        self.assertEqual(body["peg_E"], 2.5)


# ---------------------------------------------------------------------------
# derivative merit regeneration
# ---------------------------------------------------------------------------

class TestDerivativeMerit(unittest.TestCase):
    def setUp(self):
        self.t = fresh_engine()

    def test_receipt_for_A_never_accrues_B(self):
        # Downstream rings do NOT receive from upstream: A's work earns
        # A's merit only. B's balance and standing stay zero; B gets no
        # tokens.
        self.t.tokenize(work_receipt(identity=TEST_IDENTITY, merit_value=60.0,
                                     seed="ring-a"))
        self.assertEqual(self.t.merit_balance(TEST_IDENTITY), 60.0)
        self.assertEqual(self.t.standing(TEST_IDENTITY), 60.0)
        self.assertEqual(self.t.merit_balance(BUYER_IDENTITY), 0.0)
        self.assertEqual(self.t.standing(BUYER_IDENTITY), 0.0)
        self.assertEqual(len(self.t.efuse_registry), 1)
        token = next(iter(self.t.efuse_registry.values()))
        self.assertEqual(token.owner_unity_id, TEST_IDENTITY)

    def test_beneficiary_receipt_refused(self):
        # A receipt naming another beneficiary tries to credit merit for
        # another ID's work — refused, nothing written.
        r = work_receipt(identity=TEST_IDENTITY, seed="mis",
                         credit_to=BUYER_IDENTITY)
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_MERIT_MISATTRIBUTION)
        self.assertEqual(self.t._merit_slices, [])

    def test_beneficiary_in_detail_refused(self):
        r = work_receipt(identity=TEST_IDENTITY, seed="mis2")
        r["detail"] = {"on_behalf_of": BUYER_IDENTITY}
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(r)
        self.assertEqual(ctx.exception.reason, eng.REASON_MERIT_MISATTRIBUTION)

    def test_each_ring_earns_own_merit(self):
        self.t.tokenize(work_receipt(identity=TEST_IDENTITY, merit_value=60.0,
                                     seed="r1"))
        self.t.tokenize(work_receipt(identity=BUYER_IDENTITY, merit_value=20.0,
                                     seed="r2",
                                     prev_hash=_manifest("r1")))
        self.assertEqual(self.t.standing(TEST_IDENTITY), 60.0)
        self.assertEqual(self.t.standing(BUYER_IDENTITY), 20.0)


# ---------------------------------------------------------------------------
# merit transfer — the SOLE legal Merit ownership-transfer path
# (David's word, 2026-10-06: Merit IS transferable. Supersedes the
# earlier non-transferable law — see economics/DECISIONS.md §13.)
# ---------------------------------------------------------------------------

class TestMeritTransfer(unittest.TestCase):
    """Merit transfers REQUIRE the sender's Ed25519 authorization
    (David's closure, 2026-10-06 — CRITICAL-1: the public Unity ID
    alone authorizes nothing). These tests use real ephemeral
    keypairs: each identity's Unity ID derives from its public key,
    the same binding the engine verifies."""

    @classmethod
    def setUpClass(cls):
        cls.keys = _transfer_keys("earner", "buyer", "third", "fourth")

    def setUp(self):
        self.t = fresh_engine()
        _fund(self.t, self._id("earner"), 80.0, "tmt-earn")
        # earner earned 80, owns 80

    def _id(self, name):
        return self.keys[name]["id"]

    def _xfer(self, frm, to, amount, reason, signer=None, nonce=None):
        """Signed transfer frm -> to, authorized by signer's key."""
        s = self.keys[signer or frm]
        auth = _signed_auth(s, self._id(frm), self._id(to), amount,
                            reason, nonce)
        return self.t.merit_transfer(self._id(frm), self._id(to), amount,
                                     reason, auth)

    def test_transfer_happy_path(self):
        env = self._xfer("earner", "buyer", 30.0, "sale")
        body = env["receipt"]
        self.assertEqual(body["record_type"], "MERIT_TRANSFER")
        self.assertEqual(body["from_id"], self._id("earner"))
        self.assertEqual(body["to_id"], self._id("buyer"))
        self.assertEqual(body["amount"], 30.0)
        self.assertEqual(body["reason"], "sale")
        self.assertTrue(verify_commit(env))
        # Ownership moved: economic value.
        self.assertEqual(self.t.merit_balance(self._id("earner")), 50.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 30.0)

    def test_origin_preserved_across_three_hops(self):
        # A -> B -> C -> D. Origin rides along unchanged every hop.
        self._xfer("earner", "buyer", 30.0, "sale")
        self._xfer("buyer", "third", 20.0, "gift")
        env = self._xfer("third", "fourth", 10.0, "sale")
        moves = env["receipt"]["moves"]
        for move in moves:
            self.assertEqual(move[2], self._id("earner"))  # origin_earner_id
        # Every slice still names the original earner as origin.
        for sl in self.t._merit_slices:
            self.assertEqual(sl["origin_earner_id"], self._id("earner"))
            self.assertEqual(sl["origin_receipt_ref"], _manifest("tmt-earn"))

    def test_buyer_gains_value_but_zero_standing(self):
        self._xfer("earner", "buyer", 30.0, "sale")
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 30.0)
        # ...but ZERO standing: the purchase buys value, never history.
        self.assertEqual(self.t.standing(self._id("buyer")), 0.0)

    def test_seller_standing_unchanged_after_sale(self):
        self._xfer("earner", "buyer", 30.0, "sale")
        # The seller sold value; the history stays with the earner.
        self.assertEqual(self.t.standing(self._id("earner")), 80.0)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 50.0)

    def test_standing_never_moves_on_transfer(self):
        # Full sweep: seller's standing is intact even at zero balance.
        self._xfer("earner", "buyer", 80.0, "sale")
        self.assertEqual(self.t.merit_balance(self._id("earner")), 0.0)
        self.assertEqual(self.t.standing(self._id("earner")), 80.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 80.0)
        self.assertEqual(self.t.standing(self._id("buyer")), 0.0)

    def test_gifting_works(self):
        env = self._xfer("earner", "buyer", 25.0, "gift")
        self.assertEqual(env["receipt"]["reason"], "gift")
        self.assertTrue(verify_commit(env))
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 25.0)
        self.assertEqual(self.t.standing(self._id("buyer")), 0.0)

    def test_partial_transfer_splits_slices(self):
        self._xfer("earner", "buyer", 30.0, "sale")
        self._xfer("earner", "third", 20.0, "gift")
        self.assertEqual(self.t.merit_balance(self._id("earner")), 30.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 30.0)
        self.assertEqual(self.t.merit_balance(self._id("third")), 20.0)
        self.assertEqual(self.t.standing(self._id("earner")), 80.0)

    def test_transfer_is_receipted_in_engine_log(self):
        before = len(self.t._receipt_log)
        self._xfer("earner", "buyer", 10.0, "sale")
        self.assertEqual(len(self.t._receipt_log), before + 1)
        env = self.t._receipt_log[-1]
        self.assertEqual(env["receipt"]["record_type"], "MERIT_TRANSFER")
        self.assertTrue(verify_commit(env))

    def test_non_testnet_identities_refused(self):
        # The purification medium refuses FIRST (purify-on-entry):
        # non-testnet identities never reach the engine's own gates.
        # (Pre-existing contract — test_purify asserts the same.)
        from purify import PurificationRefused
        for frm, to in [("not-an-id", self._id("buyer")),
                        (self._id("earner"), "unity:mainnet:x"),
                        ("a", "b")]:
            with self.assertRaises(PurificationRefused):
                self.t.merit_transfer(frm, to, 10.0, "sale")
        # Nothing moved.
        self.assertEqual(self.t.merit_balance(self._id("earner")), 80.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 0.0)

    def test_same_identity_refused(self):
        eid = self._id("earner")
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.merit_transfer(eid, eid, 10.0, "sale")
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_SAME_IDENTITY)

    def test_insufficient_merit_refused(self):
        # Valid authorization — the balance gate is what refuses.
        with self.assertRaises(TokenizeRefused) as ctx:
            self._xfer("earner", "buyer", 81.0, "sale")
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_INSUFFICIENT)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 80.0)

    def test_non_positive_amount_refused(self):
        for amt in (0, -5.0, True):
            with self.assertRaises(TokenizeRefused) as ctx:
                self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                      amt, "sale")
            self.assertEqual(ctx.exception.reason, eng.REASON_XFER_NON_POSITIVE)

    def test_empty_reason_refused(self):
        for reason in ("", "   ", None, 42):
            with self.assertRaises(TokenizeRefused) as ctx:
                self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                      10.0, reason)
            self.assertEqual(ctx.exception.reason, eng.REASON_XFER_EMPTY_REASON)

    def test_transfer_moves_cover_exact_balance(self):
        # Exact-balance transfer empties the sender cleanly.
        self._xfer("earner", "buyer", 80.0, "gift")
        self.assertEqual(self.t.merit_balance(self._id("earner")), 0.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 80.0)

    # -- sender authorization: the CRITICAL-1 closure --------------------

    def test_unsigned_transfer_refused(self):
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                  10.0, "sale")
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_UNAUTHORIZED)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 80.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 0.0)

    def test_malformed_auth_refused(self):
        for bad in (None, "sig", {"nope": True},
                    {"signature": "x", "nonce": "y"}):
            with self.assertRaises(TokenizeRefused) as ctx:
                self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                      10.0, "sale", bad)
            self.assertEqual(ctx.exception.reason,
                             eng.REASON_XFER_UNAUTHORIZED)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 80.0)

    def test_wrong_key_signature_refused(self):
        # The buyer's key signs as if it were the earner: the key does
        # not derive to the sender's Unity ID.
        auth = _signed_auth(self.keys["buyer"], self._id("earner"),
                            self._id("buyer"), 10.0, "sale")
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                  10.0, "sale", auth)
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_KEY_MISMATCH)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 80.0)

    def test_tampered_body_signature_refused(self):
        # Signed for 10.0, called with 50.0: the signature binds the
        # exact body, so the tampered call fails verification.
        auth = _signed_auth(self.keys["earner"], self._id("earner"),
                            self._id("buyer"), 10.0, "sale")
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                  50.0, "sale", auth)
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_BAD_SIGNATURE)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 80.0)

    def test_garbage_signature_refused(self):
        auth = _signed_auth(self.keys["earner"], self._id("earner"),
                            self._id("buyer"), 10.0, "sale")
        auth = dict(auth, signature="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                                   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==")
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                  10.0, "sale", auth)
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_BAD_SIGNATURE)

    def test_replay_refused(self):
        auth = _signed_auth(self.keys["earner"], self._id("earner"),
                            self._id("buyer"), 10.0, "sale",
                            nonce="tmt-replay-1")
        self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                              10.0, "sale", auth)
        self.assertEqual(self.t.merit_balance(self._id("earner")), 70.0)
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.merit_transfer(self._id("earner"), self._id("buyer"),
                                  10.0, "sale", auth)
        self.assertEqual(ctx.exception.reason, eng.REASON_XFER_REPLAY)
        # Still exactly one execution.
        self.assertEqual(self.t.merit_balance(self._id("earner")), 70.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 10.0)

    def test_fresh_nonce_is_a_fresh_intent(self):
        # Two authorizations, same everything but the nonce: both execute.
        self._xfer("earner", "buyer", 10.0, "sale", nonce="tmt-n1")
        self._xfer("earner", "buyer", 10.0, "sale", nonce="tmt-n2")
        self.assertEqual(self.t.merit_balance(self._id("earner")), 60.0)
        self.assertEqual(self.t.merit_balance(self._id("buyer")), 20.0)


# ---------------------------------------------------------------------------
# Unity: NO transfer path exists (the bound sale is dead)
# ---------------------------------------------------------------------------

class TestNoUnityTransfer(unittest.TestCase):
    def setUp(self):
        self.t = fresh_engine()
        self.token_id = _token("notransfer-tok")
        self.t.tokenize(genesis_receipt(identity=TEST_IDENTITY,
                                       token_seed="notransfer-tok",
                                       merit_proof_ref=_manifest("origin")))

    def test_bound_sale_is_gone(self):
        self.assertFalse(hasattr(eng, "bound_sale"))
        self.assertFalse(hasattr(self.t, "bound_sale"))
        self.assertFalse(hasattr(tok, "bound_sale"))

    def test_unity_transfer_paths_empty(self):
        self.assertEqual(unity_transfer_paths(), [])

    def test_no_unity_rebind_by_ast(self):
        self.assertTrue(assert_no_unity_rebind())

    def test_holding_never_rebinds(self):
        # The holder is the holder — even while Merit moves on the same
        # engine. The unity registry is provably untouched by the Merit
        # transfer path (assert_no_unity_rebind, AST).
        keys = _transfer_keys("earner", "buyer")
        _fund(self.t, keys["earner"]["id"], 50.0, "hr-earn")
        auth = _signed_auth(keys["earner"], keys["earner"]["id"],
                            keys["buyer"]["id"], 50.0, "sale")
        self.t.merit_transfer(keys["earner"]["id"], keys["buyer"]["id"],
                              50.0, "sale", auth)
        self.assertEqual(self.t.unity_holder(self.token_id), TEST_IDENTITY)
        self.assertTrue(assert_no_unity_rebind())

    def test_genesis_bind_is_write_once(self):
        # Same bind twice: idempotent no-op. Different ID: conflict, not
        # a transfer (there is no transfer).
        self.t.tokenize(genesis_receipt(identity=TEST_IDENTITY,
                                       token_seed="notransfer-tok",
                                       seed="gen-again",
                                       prev_hash=_manifest("gen-1")))
        self.assertEqual(self.t.unity_holder(self.token_id), TEST_IDENTITY)
        with self.assertRaises(TokenizeRefused) as ctx:
            self.t.tokenize(genesis_receipt(identity=BUYER_IDENTITY,
                                            token_seed="notransfer-tok",
                                            seed="gen-clash",
                                            prev_hash=_manifest("gen-again")))
        self.assertEqual(ctx.exception.reason, eng.REASON_GENESIS_CONFLICT)
        self.assertEqual(self.t.unity_holder(self.token_id), TEST_IDENTITY)

    def test_unity_token_has_no_transfer(self):
        self.assertFalse(hasattr(UnityToken, "transfer"))
        field_names = [f.name for f in dataclasses.fields(UnityToken)]
        self.assertNotIn("transfer", field_names)

    def test_unity_sale_kind_removed(self):
        self.assertNotIn("UNITY_SALE", COMMIT_KINDS)


# ---------------------------------------------------------------------------
# transferability rules: merit moves (sole path), honor never
# ---------------------------------------------------------------------------

class TestTransferabilityRules(unittest.TestCase):
    def test_unity_mint_refused_in_this_module(self):
        with self.assertRaises(UnityMintRefused):
            eng._mint("unity", schema="x")

    def test_unity_token_never_instantiated_here(self):
        # The AST hook asserts this; belt-and-braces via source scan.
        src = inspect.getsource(eng)
        self.assertNotIn("UnityToken(", src)

    def test_merit_transfer_is_the_sole_ownership_path(self):
        self.assertTrue(assert_single_merit_transfer_path())
        paths = merit_transfer_paths()
        self.assertEqual(len(paths), 1)
        self.assertIn("merit_transfer", paths[0])

    def test_merit_record_carries_immutable_origin(self):
        t = earning_engine()
        b = t.tokenize(work_receipt(merit_value=10.0, seed="orig-check",
                                    prev_hash=_manifest("earn-1")))
        body = b.merit["receipt"]
        field_names = [f.name for f in dataclasses.fields(MeritRecord)]
        self.assertIn("origin_earner_id", field_names)
        self.assertIn("origin_receipt_ref", field_names)
        self.assertEqual(body["origin_earner_id"], TEST_IDENTITY)

    def test_honor_has_no_transfer_or_spend_path(self):
        self.assertFalse(hasattr(HonorRecord, "transfer"))
        self.assertFalse(hasattr(HonorRecord, "spend"))
        self.assertFalse(hasattr(HonorRecord, "redeem"))
        names = [n for n, _ in inspect.getmembers(eng, inspect.isfunction)]
        spenders = [n for n in names if "spend" in n.lower()
                    or "redeem" in n.lower()]
        self.assertEqual(spenders, [])


# ---------------------------------------------------------------------------
# merit is transferable value; honor is append-only
# ---------------------------------------------------------------------------

class TestValueAndAppendOnly(unittest.TestCase):
    def setUp(self):
        self.t = fresh_engine()

    def test_accrual_then_transfer(self):
        keys = _transfer_keys("earner", "buyer")
        eid, bid = keys["earner"]["id"], keys["buyer"]["id"]
        _fund(self.t, eid, 30.0, "m1")
        _fund(self.t, eid, 20.0, "m2")
        self.assertEqual(self.t.merit_balance(eid), 50.0)
        self.assertEqual(self.t.standing(eid), 50.0)
        auth = _signed_auth(keys["earner"], eid, bid, 50.0, "sale")
        self.t.merit_transfer(eid, bid, 50.0, "sale", auth)
        self.assertEqual(self.t.merit_balance(eid), 0.0)
        self.assertEqual(self.t.standing(eid), 50.0)

    def test_honor_append_only(self):
        self.t.tokenize(donation_receipt(seed="h1"))
        self.t.tokenize(donation_receipt(seed="h2", amount=10.0,
                                         prev_hash=_manifest("h1")))
        records = self.t.honor_records(TEST_IDENTITY)
        self.assertEqual(len(records), 2)  # two records, none spendable
        self.assertTrue(all(r.permanent and not r.spendable
                            for r in records))
        self.assertNotEqual(records[0].record_id, records[1].record_id)


# ---------------------------------------------------------------------------
# mint-path exclusivity
# ---------------------------------------------------------------------------

class TestMintExclusivity(unittest.TestCase):
    def test_single_mint_path_by_ast(self):
        self.assertTrue(assert_single_mint_path())

    def test_no_unity_rebind_by_ast(self):
        self.assertTrue(assert_no_unity_rebind())

    def test_single_merit_transfer_path_by_ast(self):
        self.assertTrue(assert_single_merit_transfer_path())

    def test_mint_and_transfer_paths_listed(self):
        paths = mint_paths()
        self.assertEqual(len(paths), 4)
        self.assertTrue(any("fuse" in p for p in paths))  # Unity sole path named
        self.assertEqual(unity_transfer_paths(), [])     # Unity: no path
        mpaths = merit_transfer_paths()
        self.assertEqual(len(mpaths), 1)
        self.assertIn("merit_transfer", mpaths[0])

    def test_new_commit_kinds_whitelisted(self):
        for kind in ("TOKEN_MINT", "MERIT_ACCRUAL", "HONOR_RECORD",
                     "MERIT_TRANSFER"):
            self.assertIn(kind, COMMIT_KINDS)
            granted = check_rights(TEST_IDENTITY, kind,
                                   {"internal": "dclm.tokenize",
                                    "schema": "unity.tokenize.v1.testnet"})
            self.assertEqual(granted.verdict, "GRANT", f"for {kind}")
            # A client naming the kind — no internal source — is denied.
            denied = check_rights(TEST_IDENTITY, kind, {})
            self.assertEqual(denied.verdict, "DENY", f"for {kind}")

    def test_dead_sale_kind_not_whitelisted(self):
        self.assertNotIn("UNITY_SALE", COMMIT_KINDS)
        denied = check_rights(TEST_IDENTITY, "UNITY_SALE",
                              {"internal": "dclm.tokenize",
                               "schema": "unity.tokenize.v1.testnet"})
        self.assertEqual(denied.verdict, "DENY")

    def test_production_schema_denied_at_rights_gate(self):
        v = check_rights(TEST_IDENTITY, "TOKEN_MINT",
                         {"internal": "dclm.tokenize",
                          "schema": "unity.tokenize.v1"})
        self.assertEqual(v.verdict, "DENY")


# ---------------------------------------------------------------------------
# regressions: the meter / rights / writes / compute suites stay green
# ---------------------------------------------------------------------------

class TestRegressions(unittest.TestCase):
    def _run(self, name):
        proc = subprocess.run(
            [sys.executable, os.path.join(_HERE, name)],
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0,
                         f"{name} FAILED:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn("OK", proc.stderr or proc.stdout)

    def test_rights_writes_green(self):
        self._run("test_rights_writes.py")

    def test_meter_green(self):
        self._run("test_meter.py")

    def test_compute_green(self):
        self._run("test_compute.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)

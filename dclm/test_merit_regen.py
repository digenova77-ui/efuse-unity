"""
Tests for derivative merit regeneration (David's law, 2026-10-06):

  Derivative merit regeneration, NOT token cascade: downstream rings do
  NOT receive tokens from upstream; each ring earns its own merit from
  its own verified receipts. The derivative relationship enables the
  work; the work earns the merit.

  The unbroken chain: verified work -> receipt -> merit (origin-bound;
  ownership transferable via receipted merit_transfer, standing never
  moves) -> emission (gated on STANDING, never on holdings) -> token
  (Unity-bound; Unity itself never transfers). Nothing moves without an
  ID, a receipt, and a label. Standing is never for sale — and cannot
  be bought: transfers move economic value only.

These tests cover meter.py's Phase 1 evolution:
  * emission_eligibility(identity): the read-only emission gate against
    the earner's OWN earned standing (origin-based; tokenize.py's slice
    registry). D13: the gate reads STANDING, never holdings — bought
    Merit never gates emission.
  * NO token cascade: introspection (AST) + behavioral proof that no
    path credits or gates one identity on another identity's receipts.
  * Wallet stays money-only: structural guards — merit never enters the
    wallet.

Testnet only. Test keys only — never dollars, never eFuse.
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
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from meter import (  # noqa: E402
    EMISSION_ELIGIBILITY_SCHEMA,
    IDENTITY_PREFIX,
    PROVENANCE_LABELS,
    REASON_MERIT_LEDGER_PENDING,
    REASON_MERIT_LEDGER_UNREACHABLE,
    REASON_MERIT_UNKNOWN,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_NO_VERIFIED_MERIT,
    MeterError,
    TokenizeMeritReader,
    Wallet,
    _MeterCommitStore,
    bind_merit_reader,
    emission_eligibility,
    unbind_merit_reader,
)
from tokenize import TokenizeRefused, Tokenizer, sign_gate_receipt  # noqa: E402

ID_A = f"{IDENTITY_PREFIX}aaaa1111bbbb2222"  # no merit anywhere
ID_B = f"{IDENTITY_PREFIX}cccc3333dddd4444"  # the earner
ID_C = f"{IDENTITY_PREFIX}eeee5555ffff6666"  # unverified receipt
ID_D = f"{IDENTITY_PREFIX}1111222233334444"  # donor (honor, not merit)

_ED25519_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "ed25519.js")


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


def _keyed_identity():
    """One ephemeral {priv, pub, id} — the ID derives from the key."""
    priv, pub = _gen_test_keypair()
    return {"priv": priv, "pub": pub,
            "id": IDENTITY_PREFIX + hashlib.sha256(pub).hexdigest()}


def _signed_auth(keys, frm, to, amount, reason, nonce=None):
    """Sender-signed transfer authorization (device-side construction)."""
    body = {"op": "merit-transfer", "from": frm, "to": to,
            "amount": float(amount), "reason": reason.strip(),
            "nonce": nonce or uuid.uuid4().hex}
    msg = json.dumps(body, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    fd, kpath = tempfile.mkstemp(prefix="tmr-auth-", suffix=".der")
    os.fchmod(fd, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(keys["priv"])
        proc = subprocess.run(["node", _ED25519_JS, "sign", kpath],
                              input=msg, capture_output=True, timeout=30)
    finally:
        try:
            os.unlink(kpath)
        except OSError:
            pass
    if proc.returncode != 0:
        raise RuntimeError("test signing failed")
    return {**body,
            "signature": proc.stdout.decode().strip(),
            "pubkey_b64": base64.b64encode(keys["pub"]).decode()}


def _manifest(seed):
    return hashlib.sha256(f"manifest:{seed}".encode("utf-8")).hexdigest()


def _work_receipt(identity, merit_value=100.0, provenance="VERIFIED",
                  seed="wrk"):
    return {
        "schema": "unity.relay.v1.testnet",
        "receipt_id": f"rcpt-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "work",
        "provenance": provenance,
        "epoch": 3,
        "merit_value": merit_value,
    }


def _donation_receipt(identity, seed="don"):
    return {
        "schema": "unity.relay.v1.testnet",
        "receipt_id": f"rcpt-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "donation",
        "provenance": "VERIFIED",
        "epoch": 3,
        "donation": {"amount": 25.0, "kind": "fiat"},
    }


def _earning_tokenizer():
    """A Tokenizer where ID_B earned merit from its OWN verified receipt."""
    t = Tokenizer()
    t.set_peg_ratio(4.0, {"authority": "david"})
    r = _work_receipt(ID_B, merit_value=100.0, seed="earn-b")
    r["prev_hash"] = t.gate_chain_head()
    t.tokenize(sign_gate_receipt(r))
    return t


def _meter_source():
    with open(os.path.join(_HERE, "meter.py"), "r",
              encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# A. Emission gate: closed by default, honest reasons
# ---------------------------------------------------------------------------

class TestEmissionGateClosedByDefault(unittest.TestCase):
    def setUp(self):
        unbind_merit_reader()

    def tearDown(self):
        unbind_merit_reader()

    def test_unbound_reader_is_pending_closed(self):
        """No reader bound -> MERIT_LEDGER_PENDING, eligible False.

        The interface is defined; the wiring is not. Emission stays
        closed — never emits on unknown merit."""
        v = emission_eligibility(ID_A)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_MERIT_LEDGER_PENDING)
        self.assertIsNone(v["merit_value"])
        self.assertEqual(v["identity"], ID_A)
        self.assertEqual(v["schema"], EMISSION_ELIGIBILITY_SCHEMA)
        self.assertIn(v["provenance"], PROVENANCE_LABELS)
        self.assertTrue(v["testnet"])

    def test_non_testnet_identity_is_structural(self):
        reader = TokenizeMeritReader(_earning_tokenizer())
        v = emission_eligibility("prod:definitely-not-testnet",
                                 merit_reader=reader)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_NOT_TESTNET_IDENTITY)

    def test_none_identity_is_structural(self):
        v = emission_eligibility(None)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_NOT_TESTNET_IDENTITY)

    def test_reader_returning_none_is_unknown_never_pass(self):
        class NullReader:
            def verified_merit(self, identity):
                return None

        v = emission_eligibility(ID_A, merit_reader=NullReader())
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_MERIT_UNKNOWN)

    def test_failing_reader_is_unreachable_closed(self):
        class BrokenReader:
            def verified_merit(self, identity):
                raise RuntimeError("ledger exploded")

        v = emission_eligibility(ID_A, merit_reader=BrokenReader())
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_MERIT_LEDGER_UNREACHABLE)

    def test_bind_rejects_non_reader(self):
        with self.assertRaises(MeterError):
            bind_merit_reader(object())

    def test_tokenize_reader_rejects_non_tokenizer(self):
        with self.assertRaises(MeterError):
            TokenizeMeritReader("not-a-tokenizer")


# ---------------------------------------------------------------------------
# B. Merit-gated eligibility: own receipts only (behavioral no-cascade)
# ---------------------------------------------------------------------------

class TestOwnMeritOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = _earning_tokenizer()
        cls.reader = TokenizeMeritReader(cls.tokenizer)

    def setUp(self):
        unbind_merit_reader()

    def tearDown(self):
        unbind_merit_reader()

    def test_own_verified_merit_is_eligible(self):
        v = emission_eligibility(ID_B, merit_reader=self.reader)
        self.assertTrue(v["eligible"])
        self.assertIsNone(v["reason"])
        self.assertEqual(v["merit_value"], 100.0)
        self.assertEqual(v["identity"], ID_B)

    def test_other_identity_merit_never_leaks(self):
        """ID_B earned merit; ID_A did not. A's gate sees ZERO — no
        cascade, no sharing, no upstream credit."""
        v = emission_eligibility(ID_A, merit_reader=self.reader)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_NO_VERIFIED_MERIT)
        self.assertEqual(v["merit_value"], 0.0)

    def test_unverified_receipt_earns_no_merit(self):
        """UNKNOWN provenance never tokenizes AND never gates: the
        receipt is refused at tokenize time, so no merit exists."""
        t = Tokenizer()
        t.set_peg_ratio(4.0, {"authority": "david"})
        with self.assertRaises(TokenizeRefused):
            t.tokenize(_work_receipt(ID_C, provenance="UNKNOWN",
                                     seed="unver-c"))
        v = emission_eligibility(ID_C,
                                 merit_reader=TokenizeMeritReader(t))
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_NO_VERIFIED_MERIT)

    def test_donation_earns_honor_not_merit(self):
        """Donations record Honor only — never Merit. A donor's gate
        stays closed: standing is never for sale, and gifts are gifts."""
        t = Tokenizer()
        t.set_peg_ratio(4.0, {"authority": "david"})
        r = _donation_receipt(ID_D, seed="don-d")
        r["prev_hash"] = t.gate_chain_head()
        t.tokenize(sign_gate_receipt(r))
        v = emission_eligibility(ID_D,
                                 merit_reader=TokenizeMeritReader(t))
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_NO_VERIFIED_MERIT)

    def test_explicit_reader_overrides_global(self):
        bind_merit_reader(TokenizeMeritReader(Tokenizer()))  # empty ledger
        try:
            v = emission_eligibility(ID_B, merit_reader=self.reader)
            self.assertTrue(v["eligible"])  # explicit reader wins
            v2 = emission_eligibility(ID_B)  # global: empty ledger
            self.assertFalse(v2["eligible"])
            self.assertEqual(v2["reason"], REASON_NO_VERIFIED_MERIT)
        finally:
            unbind_merit_reader()

    def test_global_binding_path(self):
        bind_merit_reader(self.reader)
        try:
            v = emission_eligibility(ID_B)  # no explicit reader
            self.assertTrue(v["eligible"])
            self.assertEqual(v["merit_value"], 100.0)
        finally:
            unbind_merit_reader()
        v = emission_eligibility(ID_B)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_MERIT_LEDGER_PENDING)


# ---------------------------------------------------------------------------
# B2. D13 — the emission gate reads STANDING, never HOLDINGS
# (David's transfer word, 2026-10-06: Merit is transferable. Under
# transferable Merit, a holdings-reading gate would let bought Merit buy
# emission — standing-for-sale through the emission rail, breaking
# merit-gating entirely. The gate reads origin-credited STANDING:
# TokenizeMeritReader.verified_merit -> Tokenizer.standing(), never the
# owned balance.)
# ---------------------------------------------------------------------------

class TestEmissionReadsStandingNotHoldings(unittest.TestCase):
    """The single load-bearing guard: bought Merit must never gate
    emission.

    Transfers here are sender-authorized (David's closure, 2026-10-06 —
    CRITICAL-1): the earner and buyer are ephemeral keyed identities,
    each Unity ID derived from its public key."""

    @classmethod
    def setUpClass(cls):
        cls.earner = _keyed_identity()
        cls.buyer = _keyed_identity()

    def _engine(self):
        t = Tokenizer()
        t.set_peg_ratio(4.0, {"authority": "david"})
        r = _work_receipt(self.earner["id"], merit_value=100.0,
                          seed="d13-earn")
        r["prev_hash"] = t._gate_chain_head
        t.tokenize(sign_gate_receipt(r))
        return t

    def _sell60(self, t):
        auth = _signed_auth(self.earner, self.earner["id"],
                            self.buyer["id"], 60.0, "sale")
        return t.merit_transfer(self.earner["id"], self.buyer["id"],
                                60.0, "sale", auth)

    def test_funded_buyer_with_zero_standing_not_eligible(self):
        """Earner sold 60 to buyer. Buyer now HOLDS 60 bought Merit with
        ZERO earned standing — the gate stays CLOSED."""
        t = self._engine()
        self._sell60(t)
        self.assertEqual(t.merit_balance(self.buyer["id"]), 60.0)  # holds…
        self.assertEqual(t.standing(self.buyer["id"]), 0.0)  # …earns nothing
        reader = TokenizeMeritReader(t)
        self.assertEqual(reader.verified_merit(self.buyer["id"]), 0.0)
        v = emission_eligibility(self.buyer["id"], merit_reader=reader)
        self.assertFalse(v["eligible"])
        self.assertEqual(v["reason"], REASON_NO_VERIFIED_MERIT)
        self.assertEqual(v["merit_value"], 0.0)

    def test_earner_stays_eligible_on_standing_after_selling(self):
        """Earner sold 60 of 100. Eligibility reads STANDING (100), not
        the remaining owned balance (40) — selling value never sells
        the right to emit."""
        t = self._engine()
        self._sell60(t)
        v = emission_eligibility(self.earner["id"],
                                 merit_reader=TokenizeMeritReader(t))
        self.assertTrue(v["eligible"])
        self.assertIsNone(v["reason"])
        self.assertEqual(v["merit_value"], 100.0)  # standing, not balance

    def test_mixed_wallet_eligible_only_on_earned_portion(self):
        """Buyer earned 20 of its own AND bought 60 from the earner. The
        gate sees only the earned 20 — the bought 60 is invisible."""
        t = self._engine()
        r = _work_receipt(self.buyer["id"], merit_value=20.0,
                          seed="d13-own")
        r["prev_hash"] = t._gate_chain_head
        t.tokenize(sign_gate_receipt(r))
        self._sell60(t)
        self.assertEqual(t.merit_balance(self.buyer["id"]),
                         80.0)  # 20 earned + 60 bought
        self.assertEqual(t.standing(self.buyer["id"]), 20.0)  # earned only
        v = emission_eligibility(self.buyer["id"],
                                 merit_reader=TokenizeMeritReader(t))
        self.assertTrue(v["eligible"])
        self.assertEqual(v["merit_value"], 20.0)  # earned portion only

    def test_reader_reports_standing_not_balance(self):
        """Directly: the reader answers standing() for the identity
        asked — never the owned balance, never another identity."""
        t = self._engine()
        self._sell60(t)
        reader = TokenizeMeritReader(t)
        self.assertEqual(reader.verified_merit(self.buyer["id"]), 0.0)
        self.assertEqual(reader.verified_merit(self.earner["id"]), 100.0)


# ---------------------------------------------------------------------------
# C. Wallet stays money-only: merit never enters the wallet
# ---------------------------------------------------------------------------

def _write_ledger(state_dir, ledger):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "meter-ledger.json"), "w",
              encoding="utf-8") as fh:
        json.dump(ledger, fh)


class TestMoneyOnlyWallet(unittest.TestCase):
    def test_ledger_with_merit_key_is_refused(self):
        d = tempfile.mkdtemp(prefix="meter-merit-")
        _write_ledger(d, {
            "schema": "unity.meter.v1.testnet",
            "balances": {},
            "intents": {},
            "merit_scores": {ID_A: 50.0},  # foreign: merit in the wallet
        })
        with self.assertRaises(MeterError):
            Wallet(state_dir=d)

    def test_ledger_with_non_integer_balance_is_refused(self):
        d = tempfile.mkdtemp(prefix="meter-merit-")
        _write_ledger(d, {
            "schema": "unity.meter.v1.testnet",
            "balances": {ID_A: 10.5},  # money is integers, not floats
            "intents": {},
        })
        with self.assertRaises(MeterError):
            Wallet(state_dir=d)

    def test_ledger_with_unexpected_key_is_refused(self):
        d = tempfile.mkdtemp(prefix="meter-merit-")
        _write_ledger(d, {
            "schema": "unity.meter.v1.testnet",
            "balances": {},
            "intents": {},
            "standing": {"x": 1},  # not money, not intents
        })
        with self.assertRaises(MeterError):
            Wallet(state_dir=d)

    def test_commit_store_rejects_non_money_op(self):
        w = Wallet(state_dir=tempfile.mkdtemp(prefix="meter-merit-"))
        with self.assertRaises(MeterError):
            _MeterCommitStore(w, identity=ID_A, receipt={}, op="merit_credit",
                              balance_before=0, balance_after=100)

    def test_commit_store_rejects_non_integer_balance(self):
        w = Wallet(state_dir=tempfile.mkdtemp(prefix="meter-merit-"))
        with self.assertRaises(MeterError):
            _MeterCommitStore(w, identity=ID_A, receipt={}, op="credit",
                              balance_before=0, balance_after=10.5)

    def test_money_still_moves_after_guards(self):
        """The guards refuse merit-shaped state but never block money:
        faucet -> debit -> balances stay integers of test-keys."""
        w = Wallet(state_dir=tempfile.mkdtemp(prefix="meter-merit-"))
        w.faucet(ID_A, 10)
        env = w.meter_intent(ID_A, "SEARCH", "intent-money-1")
        self.assertEqual(env["receipt"]["outcome"], "GRANTED")
        bal = w.balance(ID_A)
        self.assertEqual(bal, 9)
        self.assertIsInstance(bal, int)


# ---------------------------------------------------------------------------
# D. Introspection: NO token cascade — asserted structurally, not just
#    behaviorally. These tests read meter.py's own source.
# ---------------------------------------------------------------------------

class TestNoCascadeIntrospection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(_meter_source())

    def _calls_to(self, name):
        return [n for n in ast.walk(self.tree)
                if isinstance(n, ast.Call) and
                isinstance(n.func, ast.Attribute) and
                n.func.attr == name]

    def test_verified_merit_always_asked_about_own_identity(self):
        """Every verified_merit(...) call passes exactly the identity the
        caller was asked about — never another identity, never a sum."""
        calls = self._calls_to("verified_merit")
        self.assertTrue(calls, "expected at least one verified_merit call")
        for call in calls:
            self.assertTrue(call.args, "verified_merit needs an identity")
            arg = call.args[0]
            self.assertIsInstance(
                arg, ast.Name,
                f"verified_merit must be asked about the caller's own "
                f"identity, not a derived value: {ast.dump(arg)}")
            self.assertEqual(arg.id, "identity")

    def test_commit_stores_always_credit_the_callers_identity(self):
        """Every _MeterCommitStore(...) names identity=identity — the
        ledger mutation can only touch the caller's own balance."""
        stores = [n for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and
                  isinstance(n.func, ast.Name) and
                  n.func.id == "_MeterCommitStore"]
        self.assertTrue(stores, "expected commit-store constructions")
        for call in stores:
            kw = [k for k in call.keywords if k.arg == "identity"]
            self.assertEqual(len(kw), 1)
            self.assertIsInstance(kw[0].value, ast.Name)
            self.assertEqual(kw[0].value.id, "identity")

    def test_gate_performs_no_writes(self):
        """emission_eligibility is a read-only gate: no dclm_commit, no
        ledger access, no mutation of any kind in its body."""
        fn = next(n for n in ast.walk(self.tree)
                  if isinstance(n, ast.FunctionDef) and
                  n.name == "emission_eligibility")
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        self.assertNotIn("dclm_commit", names)
        self.assertNotIn("_ledger", names)
        self.assertNotIn("apply_write", names)
        for node in ast.walk(fn):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                for t in targets:
                    self.assertNotIsInstance(
                        t, ast.Subscript,
                        "the gate must not write through subscripts")

    def test_wallet_never_writes_merit_keys(self):
        """No store to the wallet ledger uses a merit-shaped key, and no
        wallet/tokenizer merit attribute is ever assigned in meter.py."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Subscript) and \
                    isinstance(node.ctx, ast.Store):
                sl = node.slice
                if isinstance(sl, ast.Constant) and \
                        isinstance(sl.value, str):
                    self.assertNotIn(
                        "merit", sl.value.lower(),
                        "wallet ledger must never take a merit key")
            if isinstance(node, ast.Attribute) and \
                    isinstance(node.ctx, ast.Store):
                self.assertFalse(
                    node.attr.lower().startswith("merit"),
                    "meter.py must never assign a merit attribute")


if __name__ == "__main__":
    unittest.main()

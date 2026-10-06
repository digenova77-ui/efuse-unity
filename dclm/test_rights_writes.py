"""
Tests for the DCLM rights & writes boundary (rights.py / writes.py).

David's binding rule: DCLM holds the RIGHTS and performs the WRITES.
The thin client NEVER writes directly.

All must pass. Testnet only.
"""
import dataclasses
import inspect
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from rights import (  # noqa: E402
    COMMIT_KINDS,
    DENY,
    GRANT,
    REASON_FREE_WORLD,
    REASON_IDENTITY_REQUIRED,
    REASON_INTERNAL_SOURCE_REQUIRED,
    REASON_INTERNAL_WRITE,
    REASON_METER_APPROVAL_REQUIRED,
    REASON_METER_APPROVED,
    REASON_NON_TESTNET_SCHEMA,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_UNKNOWN_ACTION,
    REASON_UNKNOWN_AS_PASS,
    REASON_UNSIGNED_CLAIM_AS_TRUTH,
    RightsVerdict,
    check_rights,
)
from writes import (  # noqa: E402
    CommitRefused,
    MemoryCommitStore,
    dclm_commit,
    verify_commit,
)

TEST_IDENTITY = "unity:testnet:1e26f0d9e8c46818"  # same test identity as gate


# ---------------------------------------------------------------------------
# rights matrix
# ---------------------------------------------------------------------------

class TestRightsMatrix(unittest.TestCase):
    def test_look_granted_with_no_identity(self):
        v = check_rights(None, "LOOK", {})
        self.assertEqual(v.verdict, GRANT)
        self.assertEqual(v.reason, REASON_FREE_WORLD)

    def test_render_granted_with_no_identity(self):
        v = check_rights(None, "RENDER", {})
        self.assertEqual(v.verdict, GRANT)
        self.assertEqual(v.reason, REASON_FREE_WORLD)

    def test_search_denied_with_no_identity_true_reason(self):
        """No identity at all -> the true reason is IDENTITY_REQUIRED,
        not a format complaint about nothing."""
        v = check_rights(None, "SEARCH", {"meter_approved": True})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_IDENTITY_REQUIRED)

    def test_compute_denied_with_no_identity(self):
        v = check_rights("", "COMPUTE", {"meter_approved": True})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_IDENTITY_REQUIRED)

    def test_unknown_action_denied(self):
        for bad in ("TELEPORT", "DELETE_WORLD", "", None, 12345):
            v = check_rights(TEST_IDENTITY, bad, {})
            self.assertEqual(v.verdict, DENY, f"for {bad!r}")
            self.assertEqual(v.reason, REASON_UNKNOWN_ACTION, f"for {bad!r}")

    def test_non_testnet_identity_denied(self):
        for bad in ("eth:mainnet:0xabc", "unity:mainnet:deadbeef",
                    "david", 12345):
            v = check_rights(bad, "SEARCH", {"meter_approved": True})
            self.assertEqual(v.verdict, DENY, f"for {bad!r}")
            self.assertEqual(v.reason, REASON_NOT_TESTNET_IDENTITY,
                             f"for {bad!r}")

    def test_metered_action_needs_meter_approval(self):
        v = check_rights(TEST_IDENTITY, "SEARCH", {})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_METER_APPROVAL_REQUIRED)
        # A truthy-but-not-True approval does not count. Strict.
        v = check_rights(TEST_IDENTITY, "SEARCH", {"meter_approved": "yes"})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_METER_APPROVAL_REQUIRED)

    def test_metered_action_granted_with_identity_and_meter_approval(self):
        for action in ("SEARCH", "COMPUTE", "search", "compute"):
            v = check_rights(TEST_IDENTITY, action, {"meter_approved": True})
            self.assertEqual(v.verdict, GRANT, f"for {action!r}")
            self.assertEqual(v.reason, REASON_METER_APPROVED, f"for {action!r}")

    def test_action_names_are_case_insensitive(self):
        self.assertEqual(check_rights(None, "look", {}).verdict, GRANT)
        self.assertEqual(
            check_rights(TEST_IDENTITY, "Compute",
                         {"meter_approved": True}).verdict, GRANT)


class TestRightsGates(unittest.TestCase):
    def test_non_testnet_schema_denied(self):
        v = check_rights(TEST_IDENTITY, "SEARCH", {
            "meter_approved": True, "schema": "unity.meter.v1"})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_NON_TESTNET_SCHEMA)
        # A testnet schema passes the gate.
        v = check_rights(TEST_IDENTITY, "SEARCH", {
            "meter_approved": True, "schema": "unity.meter.v1.testnet"})
        self.assertEqual(v.verdict, GRANT)

    def test_unknown_presented_as_pass_denied(self):
        v = check_rights(TEST_IDENTITY, "COMPUTE", {
            "meter_approved": True, "present_unknown_as_pass": True})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_UNKNOWN_AS_PASS)
        # Even the free world cannot launder UNKNOWN into PASS.
        v = check_rights(None, "LOOK", {"present_unknown_as_pass": True})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_UNKNOWN_AS_PASS)

    def test_unsigned_claim_as_truth_denied(self):
        v = check_rights(TEST_IDENTITY, "SEARCH", {
            "meter_approved": True, "assert_as_truth": True,
            "claim_signed": False})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_UNSIGNED_CLAIM_AS_TRUTH)
        # A signed claim asserting truth passes the gate.
        v = check_rights(TEST_IDENTITY, "SEARCH", {
            "meter_approved": True, "assert_as_truth": True,
            "claim_signed": True})
        self.assertEqual(v.verdict, GRANT)

    def test_gates_apply_to_write_tier_too(self):
        v = check_rights(TEST_IDENTITY, "LEDGER_DEBIT", {
            "internal": "dclm.meter", "schema": "unity.writes.v1"})
        self.assertEqual(v.verdict, DENY)
        self.assertEqual(v.reason, REASON_NON_TESTNET_SCHEMA)


class TestRightsPurity(unittest.TestCase):
    def test_rights_are_pure_and_deterministic(self):
        """Same inputs -> same verdict, twice. No state, no I/O."""
        args = (TEST_IDENTITY, "SEARCH", {"meter_approved": True})
        first = check_rights(*args)
        second = check_rights(*args)
        self.assertEqual(first, second)

    def test_rights_never_raise_on_garbage(self):
        """Total function: garbage in yields DENY, never an exception."""
        for identity, action, context in [
            (object(), object(), object()),
            (None, None, None),
            ("unity:testnet:x", "SEARCH", "not-a-dict"),
            (["x"], {"a": 1}, [1, 2]),
        ]:
            v = check_rights(identity, action, context)  # must not raise
            self.assertEqual(v.verdict, DENY)

    def test_verdict_is_frozen(self):
        """A DENY cannot be edited into a GRANT after issue."""
        v = check_rights(None, "SEARCH", {})
        self.assertEqual(v.verdict, DENY)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            v.verdict = GRANT  # type: ignore

    def test_internal_write_tier(self):
        """The six commit kinds grant only for DCLM-internal sources."""
        for kind in COMMIT_KINDS:
            granted = check_rights(TEST_IDENTITY, kind,
                                   {"internal": "dclm.meter"})
            self.assertEqual(granted.verdict, GRANT, f"for {kind}")
            self.assertEqual(granted.reason, REASON_INTERNAL_WRITE,
                             f"for {kind}")
            # A client naming a write kind — no internal source — is denied.
            denied = check_rights(TEST_IDENTITY, kind, {})
            self.assertEqual(denied.verdict, DENY, f"for {kind}")
            self.assertEqual(denied.reason, REASON_INTERNAL_SOURCE_REQUIRED,
                             f"for {kind}")
            # A forged internal source that is not DCLM is denied.
            forged = check_rights(TEST_IDENTITY, kind,
                                  {"internal": "evil-client"})
            self.assertEqual(forged.verdict, DENY, f"for {kind}")


# ---------------------------------------------------------------------------
# the single commit path
# ---------------------------------------------------------------------------

class TestCommitBoundary(unittest.TestCase):
    def _grant(self):
        return check_rights(TEST_IDENTITY, "LEDGER_DEBIT",
                            {"internal": "dclm.meter"})

    def test_commit_with_deny_verdict_raises_and_writes_nothing(self):
        store = MemoryCommitStore()
        denied = check_rights(None, "SEARCH", {})  # DENY, no identity
        self.assertEqual(denied.verdict, DENY)
        with self.assertRaises(CommitRefused):
            dclm_commit("LEDGER_DEBIT", {"x": 1}, denied, store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])

    def test_commit_with_none_verdict_raises_and_writes_nothing(self):
        store = MemoryCommitStore()
        with self.assertRaises(CommitRefused):
            dclm_commit("LEDGER_DEBIT", {"x": 1}, None, store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])

    def test_commit_with_forged_grant_string_raises(self):
        """A client cannot utter 'GRANT' its way past the boundary: the
        verdict must be a DCLM-issued RightsVerdict."""
        store = MemoryCommitStore()
        with self.assertRaises(CommitRefused):
            dclm_commit("LEDGER_DEBIT", {"x": 1}, "GRANT", store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])

    def test_commit_with_unknown_kind_raises_and_writes_nothing(self):
        store = MemoryCommitStore()
        with self.assertRaises(CommitRefused):
            dclm_commit("DROP_TABLE", {"x": 1}, self._grant(), store)
        self.assertEqual(store.applied, [])
        self.assertEqual(store.receipts, [])

    def test_full_flow_request_rights_commit_receipt_verifies(self):
        """request -> check_rights GRANT -> dclm_commit -> signed
        receipt; the receipt verifies."""
        store = MemoryCommitStore()
        verdict = check_rights(TEST_IDENTITY, "SEARCH",
                               {"meter_approved": True,
                                "schema": "unity.writes.v1.testnet"})
        self.assertEqual(verdict.verdict, GRANT)
        payload = {"intent": "SEARCH", "query": "residual friction",
                   "provenance": "DERIVED"}
        envelope = dclm_commit("METER_RECEIPT", payload, verdict, store)
        self.assertTrue(verify_commit(envelope))
        self.assertEqual(len(store.applied), 1)
        self.assertEqual(store.applied[0][0], "METER_RECEIPT")
        self.assertEqual(len(store.receipts), 1)
        receipt = envelope["receipt"]
        self.assertEqual(receipt["kind"], "METER_RECEIPT")
        self.assertEqual(receipt["rights"]["verdict"], GRANT)
        self.assertEqual(receipt["rights"]["reason"], REASON_METER_APPROVED)

    def test_each_writable_kind_commits(self):
        for kind in COMMIT_KINDS:
            store = MemoryCommitStore()
            verdict = check_rights(TEST_IDENTITY, kind,
                                   {"internal": "dclm.meter"})
            envelope = dclm_commit(
                kind, {"kind": kind, "provenance": "DERIVED"},
                verdict, store)
            self.assertTrue(verify_commit(envelope), f"for {kind}")
            self.assertEqual(len(store.applied), 1, f"for {kind}")

    def test_tampered_commit_receipt_fails_verification(self):
        store = MemoryCommitStore()
        envelope = dclm_commit("METER_RECEIPT", {"a": 1}, self._grant(),
                               store)
        envelope["receipt"]["kind"] = "LEDGER_DEBIT"
        self.assertFalse(verify_commit(envelope))

    def test_unlabeled_receipt_refuses_commit(self):
        """A store whose receipt carries no provenance label cannot
        commit — UNKNOWN is never PASS, and unlabeled is worse."""
        from writes import CommitStore

        class BadStore(CommitStore):
            def apply_write(self, kind, payload):
                return {"applied": True}

            def build_receipt(self, kind, payload, mutation, verdict):
                return {"kind": kind}  # no provenance label

            def append_receipt(self, envelope):
                pass

        with self.assertRaises(CommitRefused):
            dclm_commit("METER_RECEIPT", {"a": 1}, self._grant(), BadStore())


class TestNoBypassPath(unittest.TestCase):
    """Simulated client-direct-write attempt: bypassing rights has no
    path to committed state."""

    def test_no_public_function_writes_without_grant(self):
        import writes as writes_mod
        public = [name for name in dir(writes_mod)
                  if not name.startswith("_")]
        writers = []
        for name in public:
            obj = getattr(writes_mod, name)
            if not callable(obj) or not inspect.isfunction(obj):
                continue
            try:
                sig = inspect.signature(obj)
            except (TypeError, ValueError):
                continue
            params = list(sig.parameters)
            # A function that both takes a store and returns without a
            # verdict parameter would be a bypass path. dclm_commit is
            # the only sanctioned writer and it demands the verdict.
            if "store" in params and "rights_verdict" not in params:
                writers.append(name)
        self.assertEqual(
            writers, [],
            f"public functions that could write without a GRANT verdict: "
            f"{writers}")

    def test_refused_attempts_leave_no_trace(self):
        """Every refusal mode: raises, and the store is untouched —
        no write, no receipt, no trace."""
        store_probe = MemoryCommitStore()
        refusals = 0

        def attempt(label, fn):
            nonlocal refusals
            try:
                fn(store_probe)
            except CommitRefused:
                refusals += 1
                return
            self.fail(f"{label}: commit did not refuse")

        attempt("DENY verdict", lambda s: dclm_commit(
            "LEDGER_DEBIT", {"x": 1}, check_rights(None, "SEARCH", {}), s))
        attempt("None verdict", lambda s: dclm_commit(
            "LEDGER_DEBIT", {"x": 1}, None, s))
        attempt("forged string verdict", lambda s: dclm_commit(
            "LEDGER_DEBIT", {"x": 1}, "GRANT", s))
        attempt("forged dict verdict", lambda s: dclm_commit(
            "LEDGER_DEBIT", {"x": 1}, {"verdict": "GRANT"}, s))
        attempt("unknown kind", lambda s: dclm_commit(
            "NOPE", {"x": 1},
            check_rights(TEST_IDENTITY, "LEDGER_DEBIT",
                         {"internal": "dclm.meter"}), s))

        self.assertEqual(refusals, 5, "every bypass attempt must refuse")
        self.assertEqual(store_probe.applied, [],
                         "refused attempts must not mutate the store")
        self.assertEqual(store_probe.receipts, [],
                         "refused attempts must not log receipts")

    def test_verdict_cannot_be_reused_across_kinds_without_rights(self):
        """A GRANT verdict is a fact about (identity, action, context);
        dclm_commit still enforces the kind whitelist per call."""
        store = MemoryCommitStore()
        verdict = check_rights(TEST_IDENTITY, "LEDGER_DEBIT",
                               {"internal": "dclm.meter"})
        with self.assertRaises(CommitRefused):
            dclm_commit("MINT_FOREVER", {"x": 1}, verdict, store)
        self.assertEqual(store.applied, [])


# ---------------------------------------------------------------------------
# meter integration: the refactored ledger still behaves
# ---------------------------------------------------------------------------

class TestMeterThroughBoundary(unittest.TestCase):
    def test_faucet_and_debit_flow_through_commit(self):
        from meter import Wallet, verify_receipt, PRICE_SEARCH
        w = Wallet(state_dir=tempfile.mkdtemp(prefix="rights-writes-meter-"))
        funding = w.faucet(TEST_IDENTITY, 10)
        self.assertTrue(verify_receipt(funding))
        self.assertEqual(w.balance(TEST_IDENTITY), 10)
        spent = w.meter_intent(TEST_IDENTITY, "SEARCH", "intent-rw-1")
        r = spent["receipt"]
        self.assertEqual(r["outcome"], "GRANTED")
        self.assertEqual(r["balance_after"], 10 - PRICE_SEARCH)
        self.assertEqual(w.balance(TEST_IDENTITY), 10 - PRICE_SEARCH)
        self.assertTrue(verify_receipt(spent))
        # The receipts log received the signed meter receipts.
        with open(w.receipts_path, encoding="utf-8") as fh:
            logged = [l for l in fh.read().splitlines() if l.strip()]
        self.assertEqual(len(logged), 2)

    def test_meter_suite_still_passes(self):
        """The 20 meter tests pass after the refactor to the commit path."""
        proc = subprocess.run(
            [sys.executable, os.path.join(_HERE, "test_meter.py")],
            capture_output=True, text=True, timeout=300,
            cwd=_HERE,
        )
        self.assertEqual(proc.returncode, 0,
                         msg=f"test_meter.py failed:\n{proc.stderr[-3000:]}")
        self.assertIn("Ran 20 tests", proc.stderr)
        self.assertIn("OK", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

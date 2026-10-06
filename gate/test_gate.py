#!/usr/bin/env python3
"""
Tests for the Unity ID Gate (TESTNET).

Run:  python3 test_gate.py        (from ~/workspace/unity-world/gate/)
      python3 -m unittest test_gate -v

All state is server-side, in a temp dir per test run. No client input can
forge BOUND — that is what test 5 proves.

WebAuthn honesty: the default verifier is UNKNOWN/unwired. The happy-path
test injects a clearly-labeled TEST STUB simulating the phone ceremony —
it is a simulation for exercising the state machine, never claimed as
real WebAuthn. A separate test asserts the default path refuses on
UNKNOWN (UNKNOWN is never PASS).

THE REFRAME (2026-10-06, David's direction): the world opens FREE —
binding is for INTENT, not entry. Tests 7-9 cover the reframe:
  7. no gate function gates world viewing (world_view_pass, free actions,
     and a structural scan of the module's public surface);
  8. authorize_intent requires BOUND; unbound intent -> honest refusal
     with reason UNBOUND;
  9. the wallet ledger is honestly WIRED (dclm/meter.py landed): the gate
     consults the real ledger — empty wallet refuses INSUFFICIENT_KEYS,
     funded wallet authorizes, the gate reads the meter's prices — and
     degrades to honest WALLET_LEDGER_PENDING if the module is unusable.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import (  # noqa: E402
    BOUND,
    BINDING,
    FREE_ACTIONS,
    METERED_ACTIONS,
    METER_MODULE_PATH,
    THE_TEST_IDENTITY,
    UNBOUND,
    WALLET_LEDGER_STATUS,
    WORLD_VIEWING_REQUIRES_BINDING,
    GateError,
    GateRefused,
    GateUnknown,
    IntentRefused,
    UnityGate,
    VerificationResult,
    resolve_wallet_ledger,
    world_view_pass,
)


def verified_stub(identity, proof):
    """TEST STUB — simulates the device WebAuthn ceremony for the state
    machine exercise only. NOT real WebAuthn. Never claim otherwise."""
    return VerificationResult(status="VERIFIED", detail="test stub: simulated")


OTHER_TEST_IDENTITY = "unity:testnet:deadbeefcafef00d"


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="unity-gate-test-")
        self.gate = UnityGate(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # 1. UNBOUND -> BINDING -> BOUND happy path ---------------------------
    def test_happy_path(self):
        g = self.gate
        self.assertEqual(g.status(THE_TEST_IDENTITY), UNBOUND)

        r1 = g.request_bind(THE_TEST_IDENTITY)
        self.assertEqual(r1["state"], BINDING)
        self.assertEqual(r1["transition"], "BINDING")
        self.assertEqual(g.status(THE_TEST_IDENTITY), BINDING)

        r2 = g.confirm_bind(THE_TEST_IDENTITY, {"assertion": "stub"},
                            verifier=verified_stub)
        self.assertEqual(r2["state"], BOUND)
        self.assertEqual(r2["transition"], "BOUND")
        self.assertEqual(g.status(THE_TEST_IDENTITY), BOUND)

        env = g.emit_gate_envelope(THE_TEST_IDENTITY)
        self.assertEqual(env["type"], "GATE")
        self.assertEqual(env["identity"], THE_TEST_IDENTITY)
        self.assertEqual(env["receipt_id"], r2["receipt_id"])

    # 2. Non-testnet identity refused at request_bind ---------------------
    def test_non_testnet_refused(self):
        g = self.gate
        for bad in ("unity:mainnet:1e26f0d9e8c46818",
                    "unity:1e26f0d9e8c46818",
                    "david",
                    "",
                    None):
            with self.assertRaises(GateRefused, msg=f"identity={bad!r}"):
                g.request_bind(bad)
            with self.assertRaises(GateRefused, msg=f"identity={bad!r}"):
                g.status(bad)
            with self.assertRaises(GateRefused, msg=f"identity={bad!r}"):
                g.confirm_bind(bad, {}, verifier=verified_stub)
            with self.assertRaises(GateRefused, msg=f"identity={bad!r}"):
                g.emit_gate_envelope(bad)
        # Refused identities leave no trace in server state.
        self.assertEqual(g._state["bindings"], {})

    # 3. Double bind is idempotent (same receipt id) ----------------------
    def test_double_bind_idempotent(self):
        g = self.gate
        r1 = g.request_bind(THE_TEST_IDENTITY)
        r2 = g.request_bind(THE_TEST_IDENTITY)  # re-bind while BINDING
        self.assertEqual(r1["receipt_id"], r2["receipt_id"])
        self.assertEqual(r1, r2)

        g.confirm_bind(THE_TEST_IDENTITY, {"assertion": "stub"},
                       verifier=verified_stub)
        r3 = g.request_bind(THE_TEST_IDENTITY)  # re-bind while BOUND
        r4 = g.request_bind(THE_TEST_IDENTITY)
        self.assertEqual(r3["receipt_id"], r4["receipt_id"])
        self.assertEqual(r3["state"], BOUND)

        # Exactly two mutations were ever logged: BINDING and BOUND.
        with open(os.path.join(self.tmp, "receipts.jsonl")) as fh:
            lines = [ln for ln in fh if ln.strip()]
        self.assertEqual(len(lines), 2)
        transitions = [json.loads(ln)["transition"] for ln in lines]
        self.assertEqual(transitions, ["BINDING", "BOUND"])

    # 4. confirm_bind without request_bind fails honestly -----------------
    def test_confirm_without_request_fails(self):
        g = self.gate
        with self.assertRaises(GateError) as ctx:
            g.confirm_bind(OTHER_TEST_IDENTITY, {"assertion": "x"},
                           verifier=verified_stub)
        self.assertIn("no binding in progress", str(ctx.exception))
        self.assertEqual(g.status(OTHER_TEST_IDENTITY), UNBOUND)

        # Confirming twice: the second confirm finds BOUND, not BINDING.
        g.request_bind(OTHER_TEST_IDENTITY)
        g.confirm_bind(OTHER_TEST_IDENTITY, {"assertion": "x"},
                       verifier=verified_stub)
        with self.assertRaises(GateError):
            g.confirm_bind(OTHER_TEST_IDENTITY, {"assertion": "x"},
                           verifier=verified_stub)

    # 5. Gate state survives as server-side truth -------------------------
    def test_server_side_truth_unforgeable(self):
        g = self.gate
        # A second gate instance over the SAME state dir sees the truth:
        # state persists server-side, not in any client.
        g.request_bind(THE_TEST_IDENTITY)
        g2 = UnityGate(state_dir=self.tmp)
        self.assertEqual(g2.status(THE_TEST_IDENTITY), BINDING)

        # A forged receipt dict presented by a "client" buys nothing:
        # the envelope consults server state only.
        forger = UnityGate(state_dir=tempfile.mkdtemp(prefix="forger-"))
        try:
            fake_receipt = {
                "schema": "unity.gate.v1.testnet",
                "identity": THE_TEST_IDENTITY,
                "transition": "BOUND",
                "state": BOUND,
                "receipt_id": "forged" * 8,
            }
            _ = fake_receipt  # holding a receipt is not holding state
            with self.assertRaises(GateError):
                forger.emit_gate_envelope(THE_TEST_IDENTITY)
        finally:
            shutil.rmtree(forger.state_dir, ignore_errors=True)

        # Unknown testnet identity is UNBOUND and gets no envelope.
        self.assertEqual(g.status(OTHER_TEST_IDENTITY), UNBOUND)
        with self.assertRaises(GateError):
            g.emit_gate_envelope(OTHER_TEST_IDENTITY)

        # Receipt hash chain: each mutation's prev hash equals the prior
        # mutation's new hash (tamper-evident server log).
        g.confirm_bind(THE_TEST_IDENTITY, {"assertion": "stub"},
                       verifier=verified_stub)
        with open(os.path.join(self.tmp, "receipts.jsonl")) as fh:
            entries = [json.loads(ln) for ln in fh if ln.strip()]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["prev_state_sha256"],
                         entries[0]["new_state_sha256"])
        self.assertNotEqual(entries[0]["prev_state_sha256"],
                            entries[0]["new_state_sha256"])

    # 6. UNKNOWN is never PASS (default WebAuthn path is unwired) ---------
    def test_unknown_never_pass(self):
        g = self.gate
        g.request_bind(THE_TEST_IDENTITY)
        with self.assertRaises(GateUnknown) as ctx:
            g.confirm_bind(THE_TEST_IDENTITY, {"assertion": "real-looking"})
        self.assertIn("UNKNOWN", str(ctx.exception))
        # Still BINDING — the refusal changed nothing.
        self.assertEqual(g.status(THE_TEST_IDENTITY), BINDING)

    # 7. The world needs no binding — the gate NEVER gates viewing -------
    def test_world_needs_no_binding(self):
        g = self.gate
        # The structural claim, importable and grep-able.
        self.assertFalse(WORLD_VIEWING_REQUIRES_BINDING)

        # world_view_pass(): zero arguments, no identity, no state.
        view = world_view_pass()
        self.assertEqual(view["type"], "VIEW_PASS")
        self.assertFalse(view["binding_required"])
        self.assertFalse(view["identity_required"])

        # Free actions authorize with NO identity and NO binding, on a gate
        # where nothing is bound at all — and they touch no state.
        free = g.authorize_intent(None, "view")
        self.assertTrue(free["authorized"])
        self.assertTrue(free["free"])
        self.assertFalse(free["requires_binding"])
        self.assertEqual(free["reason"], "WORLD_IS_FREE")
        self.assertEqual(g._state["bindings"], {})

        for action in FREE_ACTIONS:
            got = g.authorize_intent(THE_TEST_IDENTITY, action)
            self.assertTrue(got["authorized"], msg=f"action={action}")
            self.assertFalse(got["requires_binding"], msg=f"action={action}")
        self.assertEqual(g._state["bindings"], {})  # still nothing bound

        # Structural scan: world_view_pass is the ONLY view-related public
        # callable in the module. There is no function here that could
        # revoke or gate world-view state. (Ledger-integration names are
        # exempt: the wallet ledger is about keys for paid intent, not
        # about viewing the world.)
        import gate as gate_module
        view_gaters = [
            n for n in dir(gate_module)
            if "view" in n.lower()
            and "ledger" not in n.lower()
            and callable(getattr(gate_module, n))
            and n != "world_view_pass"
        ]
        self.assertEqual(view_gaters, [])

    # 8. authorize_intent requires BOUND; unbound intent is refused ------
    def test_authorize_intent_requires_bound(self):
        g = self.gate

        def rich_ledger(identity, action):
            """TEST STUB — simulates a funded Unity wallet for intent
            authorization tests only. NOT a real ledger."""
            return {"status": "SUFFICIENT", "keys_available": 10,
                    "detail": "stub: wallet funded"}

        # Unbound identity -> honest refusal, reason UNBOUND.
        with self.assertRaises(IntentRefused) as ctx:
            g.authorize_intent(THE_TEST_IDENTITY, "search", ledger=rich_ledger)
        self.assertEqual(ctx.exception.reason, "UNBOUND")
        self.assertIn("wanting", str(ctx.exception))  # never about seeing
        self.assertEqual(g.status(THE_TEST_IDENTITY), UNBOUND)

        # Bind it (test-stub ceremony), then SUFFICIENT keys authorize.
        g.request_bind(THE_TEST_IDENTITY)
        g.confirm_bind(THE_TEST_IDENTITY, {"assertion": "stub"},
                       verifier=verified_stub)
        auth = g.authorize_intent(THE_TEST_IDENTITY, "search",
                                  ledger=rich_ledger)
        self.assertTrue(auth["authorized"])
        self.assertEqual(auth["type"], "INTENT_AUTHORIZATION")
        self.assertEqual(auth["action"], "search")
        self.assertTrue(auth["metered"])
        self.assertEqual(auth["keys_available"], 10)

        # compute is metered too.
        auth2 = g.authorize_intent(THE_TEST_IDENTITY, "compute",
                                   ledger=rich_ledger)
        self.assertTrue(auth2["authorized"])
        self.assertEqual(auth2["action"], "compute")

        # authorize_intent is read-only: no new mutation logged.
        with open(os.path.join(self.tmp, "receipts.jsonl")) as fh:
            lines = [ln for ln in fh if ln.strip()]
        self.assertEqual(len(lines), 2)  # only BINDING and BOUND

        # Non-testnet identity refused structurally, even for metered intent.
        with self.assertRaises(GateRefused):
            g.authorize_intent("unity:mainnet:1e26f0d9e8c46818", "search",
                               ledger=rich_ledger)

        # Unknown action refused honestly: the gate does not price what it
        # does not know.
        with self.assertRaises(GateError):
            g.authorize_intent(THE_TEST_IDENTITY, "teleport", ledger=rich_ledger)

    # 9. Wallet honesty: real ledger wired in, never faked ---------------
    def test_wallet_wired_never_faked(self):
        import gate as gate_module
        # The metering worker landed dclm/meter.py after the gate's first
        # build; the gate now consults the real ledger. If the module ever
        # goes missing again, the gate must degrade to honest PENDING.
        self.assertEqual(WALLET_LEDGER_STATUS, "WIRED")
        self.assertIsNotNone(resolve_wallet_ledger())

        g = self.gate
        g.request_bind(THE_TEST_IDENTITY)
        g.confirm_bind(THE_TEST_IDENTITY, {"assertion": "stub"},
                       verifier=verified_stub)

        # Point the meter's Wallet at an isolated ledger for this test.
        dclm_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(gate_module.__file__)),
            "..", "dclm"))
        sys.path.insert(0, dclm_dir)
        old_env = os.environ.get("UNITY_METER_STATE_DIR")
        os.environ["UNITY_METER_STATE_DIR"] = os.path.join(self.tmp, "meter")
        try:
            from meter import Wallet  # the metering worker's real ledger

            wallet = Wallet()
            # Empty wallet -> honest INSUFFICIENT_KEYS from the REAL ledger.
            with self.assertRaises(IntentRefused) as ctx:
                g.authorize_intent(THE_TEST_IDENTITY, "search")
            self.assertEqual(ctx.exception.reason, "INSUFFICIENT_KEYS")
            self.assertIn("0 test-keys", str(ctx.exception))

            # Fund with TEST keys (faucet, testnet only) -> SUFFICIENT.
            wallet.faucet(THE_TEST_IDENTITY, 10)
            auth = g.authorize_intent(THE_TEST_IDENTITY, "search")
            self.assertTrue(auth["authorized"])
            self.assertEqual(auth["keys_available"], 10)
            self.assertEqual(auth["wallet_ledger"], "dclm/meter.py")

            # The gate reads the METER's prices, never its own: 1 key
            # covers search (price 1) but not compute (price 5).
            g.request_bind(OTHER_TEST_IDENTITY)
            g.confirm_bind(OTHER_TEST_IDENTITY, {"assertion": "stub"},
                           verifier=verified_stub)
            wallet.faucet(OTHER_TEST_IDENTITY, 1)
            one_key_search = g.authorize_intent(OTHER_TEST_IDENTITY, "search")
            self.assertTrue(one_key_search["authorized"])
            with self.assertRaises(IntentRefused) as ctx2:
                g.authorize_intent(OTHER_TEST_IDENTITY, "compute")
            self.assertEqual(ctx2.exception.reason, "INSUFFICIENT_KEYS")

            # UNKNOWN ledger view is never PASS (injected stub path).
            def shrug_ledger(identity, action):
                """TEST STUB — simulates an unreachable ledger."""
                return {"status": "UNKNOWN", "keys_available": 0,
                        "detail": "stub: ledger unreachable"}
            with self.assertRaises(IntentRefused) as ctx3:
                g.authorize_intent(THE_TEST_IDENTITY, "search",
                                   ledger=shrug_ledger)
            self.assertEqual(ctx3.exception.reason, "KEYS_UNKNOWN")
        finally:
            if old_env is None:
                os.environ.pop("UNITY_METER_STATE_DIR", None)
            else:
                os.environ["UNITY_METER_STATE_DIR"] = old_env
            sys.path.remove(dclm_dir)

        # Fallback honesty: if the meter module is unusable, the gate
        # refuses rather than fabricating. (Simulated by pointing at a
        # missing file; the real path is restored afterwards.)
        old_path = gate_module.METER_MODULE_PATH
        gate_module.METER_MODULE_PATH = os.path.join(self.tmp,
                                                     "no-such-meter.py")
        try:
            with self.assertRaises(IntentRefused) as ctxp:
                g.authorize_intent(THE_TEST_IDENTITY, "search")
            self.assertEqual(ctxp.exception.reason, "WALLET_LEDGER_PENDING")
            self.assertIn("cannot fabricate", str(ctxp.exception))
        finally:
            gate_module.METER_MODULE_PATH = old_path

        # Metered actions the gate knows: search and compute.
        self.assertEqual(METERED_ACTIONS, frozenset({"search", "compute"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)

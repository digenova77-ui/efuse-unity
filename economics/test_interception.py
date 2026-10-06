#!/usr/bin/env python3
"""
Tests for economics/interception.py — the first lawful exit.

All simulated, all in-memory, ephemeral TEST keypairs (generated fresh
per run, /tmp only via wallet._node_sign). Never shared state, never
real keys. Testnet only.

Run: python3 test_interception.py
"""
import os
import sys
import base64
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import tokenomics as T
from wallet import generate_test_keypair
from interception import (
    SCHEMA, ACTIONS, MAX_INTERCEPT_EPOCHS, POOLS, INTERCEPT_IDENTITY,
    AuthorityRegistry, InterceptionOrder, InterceptedLedger,
    InterceptionError, UnlawfulInterception, InterceptionFreezeError,
)

MEMBERS = [f"unity:testnet:m-{i:02d}" for i in range(4)]  # even=human, odd=machine
POOL_OF = {m: ("human" if i % 2 == 0 else "machine") for i, m in enumerate(MEMBERS)}


def F(v, prov="VERIFIED"):
    return T.Figure(float(v), prov)


def standing_map(ledger, members):
    """Pool-roster standing restatement: {uid: Figure} with each value
    equal to the ledger's earned standing. The standing cross-check
    passes; the gate derives every weight from standing, never balances."""
    return {m: F(ledger.standing(m).value, "VERIFIED")
            for m in members}


class InterceptionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.founder_priv, cls.founder_pub = generate_test_keypair()
        cls.attacker_priv, cls.attacker_pub = generate_test_keypair()
        cls.registry = AuthorityRegistry()
        cls.registry.register("founder-test", cls.founder_pub)

    def setUp(self):
        self.ledger = T.Ledger()
        self.gate = InterceptedLedger(self.ledger, self.registry)
        self._nonce = 0

    # -- helpers ---------------------------------------------------------
    def _order(self, order_id, action, scope, duration, epoch,
               key_id="founder-test", reason="drill: lawful test",
               priv=None, sign=True):
        self._nonce += 1
        o = InterceptionOrder(
            order_id, action, scope, duration, epoch, key_id,
            reason, f"nonce-{self._nonce}")
        if sign:
            o.sign(self.founder_priv if priv is None else priv)
        return o

    def _accrue(self, e):
        for m in MEMBERS:
            r = T.Receipt.build(m, "merit_accrual",
                                {"work_ref": f"epoch-{e}/{m}"},
                                "VERIFIED", e, self.ledger._chain_head)
            self.gate.accrue_merit(m, r, F(10.0, "MODELED"))

    def _close(self, e):
        outs = {}
        for pool in POOLS:
            mmap = standing_map(
                self.ledger,
                [m for i, m in enumerate(MEMBERS)
                 if (i % 2 == 0) == (pool == "human")])
            outs[pool] = self.gate.emission_close(pool, mmap, F(1000.0, "MODELED"), e)
        return outs

    def _disburse(self, outs, e, on_refuse=None):
        paid, refused = 0, 0
        for pool, out in outs.items():
            for uid, fig in out.per_member.items():
                try:
                    self.gate.disburse(pool, uid, fig, e)
                    paid += 1
                except InterceptionFreezeError as ex:
                    refused += 1
                    if on_refuse:
                        on_refuse(ex)
        return paid, refused

    def _decay(self):
        for m in MEMBERS:
            self.gate.apply_decay(m, 1, F(0.02, "MODELED"))

    def _cycle(self, e, disburse=True):
        """One honest epoch: work -> merit -> close -> disburse -> decay."""
        self._accrue(e)
        outs = self._close(e)
        paid = refused = 0
        if disburse:
            paid, refused = self._disburse(outs, e)
        self._decay()
        return outs, paid, refused

    def _interception_receipts(self, event=None):
        recs = [r for r in self.ledger.receipts if r.kind == "interception"]
        if event:
            recs = [r for r in recs if r.detail.get("event") == event]
        return recs

    def _assert_chain_intact(self):
        recs = self.ledger.receipts
        self.assertGreater(len(recs), 0)
        for i in range(1, len(recs)):
            self.assertEqual(recs[i].prev_hash, recs[i - 1].manifest_hash,
                             f"chain break at receipt {i}")
        self.assertEqual(self.ledger._chain_head, recs[-1].manifest_hash)

    # -- 1. lawful freeze --------------------------------------------------
    def test_lawful_freeze_pool(self):
        for e in range(1, 11):
            self._cycle(e)
        pre = dict(self.ledger.emitted)

        order = self._order("INT-001", "freeze_pool", {"pool": "human"},
                            5, 11)
        self.gate.advance_epoch(11)
        self.gate.apply_interception(order)

        # the order itself is receipted in the MAIN chain, with authority proof
        applied = self._interception_receipts("order_applied")
        self.assertEqual(len(applied), 1)
        d = applied[0].detail
        self.assertEqual(d["order"]["authority_key_id"], "founder-test")
        self.assertEqual(d["order"]["action"], "freeze_pool")
        self.assertEqual(d["order"]["scope"], {"pool": "human"})
        self.assertEqual(d["order"]["duration_epochs"], 5)
        self.assertEqual(d["order"]["reason"], "drill: lawful test")
        self.assertIn("authority_proof", d)
        self.assertEqual(applied[0].unity_id, INTERCEPT_IDENTITY)

        for e in range(11, 16):
            self.gate.advance_epoch(e)
            self._accrue(e)
            outs = self._close(e)          # measurement continues under freeze
            self.assertGreater(outs["human"].total.value, 0)
            paid, refused = self._disburse(outs, e)
            n_human = len(outs["human"].per_member)
            n_machine = len(outs["machine"].per_member)
            self.assertEqual(refused, n_human,
                             "every human-pool disbursement must refuse")
            self.assertEqual(paid, n_machine,
                             "machine pool must be unaffected")
            if e == 12:
                # giving is never frozen
                self.gate.donate(MEMBERS[0], F(5.0, "MODELED"), "fiat", e)
            self._decay()

        self.assertEqual(self.ledger.emitted["human"] - pre["human"], 0.0,
                         "frozen pool emits nothing — no auto-pay, no leak")
        self.assertGreater(self.ledger.emitted["machine"] - pre["machine"], 0,
                           "machine pool kept emitting")
        self.assertEqual(len(self.ledger.honor.get(MEMBERS[0], [])), 1,
                         "donation during freeze accrued Honor")
        # every blocked movement receipted as refused-with-cause
        refused_recs = self._interception_receipts("movement_refused")
        self.assertGreater(len(refused_recs), 0)
        for r in refused_recs:
            self.assertIn("cause", r.detail)
            self.assertEqual(r.detail["order_id"], "INT-001")
        self._assert_chain_intact()

    # -- 2. the 7 unlawful variants ----------------------------------------
    def test_seven_unlawful_variants_refused(self):
        for e in range(1, 4):
            self._cycle(e)
        before_emitted = dict(self.ledger.emitted)
        before_receipts = len(self.ledger.receipts)
        self.gate.advance_epoch(4)

        attempts = []

        def attempt(name, mk):
            with self.assertRaises(UnlawfulInterception, msg=name):
                self.gate.apply_interception(mk())
            attempts.append(name)

        # a. wrong key — attacker signs, key not in the registry
        attempt("a_wrong_key", lambda: self._order(
            "INT-ATT-A", "freeze_pool", {"pool": "machine"}, 5, 4,
            key_id="attacker", priv=self.attacker_priv))
        # b. no signature at all
        attempt("b_no_signature", lambda: self._order(
            "INT-ATT-B", "freeze_pool", {"pool": "machine"}, 5, 4, sign=False))
        # c. tampered body after signing
        def mk_c():
            o = self._order("INT-ATT-C", "freeze_pool", {"pool": "machine"},
                            5, 4)
            o.duration_epochs = 99  # tamper post-signing
            return o
        attempt("c_tampered_body", mk_c)
        # d. raise-cap attempt — outside the allowlist
        attempt("d_raise_cap", lambda: self._order(
            "INT-ATT-D", "raise_pool_cap",
            {"pool": "human", "new_cap": 200_000_000}, 5, 4))
        # e. rewrite-receipts attempt — outside the allowlist
        attempt("e_rewrite_receipts", lambda: self._order(
            "INT-ATT-E", "rewrite_receipts", {}, 5, 4))
        # f. unbounded duration
        attempt("f_unbounded_duration", lambda: self._order(
            "INT-ATT-F", "freeze_pool", {"pool": "machine"}, 10 ** 9, 4))
        # g. Unity-scope overreach — Unity bindings never interceptable
        attempt("g_unity_scope", lambda: self._order(
            "INT-ATT-G", "freeze_pool",
            {"pool": "human", "unity": "rebind"}, 5, 4))

        self.assertEqual(len(attempts), 7)
        # state unchanged by every attempt
        self.assertEqual(dict(self.ledger.emitted), before_emitted)
        self.assertEqual(len(self.gate.live_orders()), 0)
        # each refusal receipted (loud, not silent)
        refused = self._interception_receipts("unlawful_order_refused")
        self.assertEqual(len(refused), 7)
        # a normal disbursement still works — the gate is unpoisoned
        outs = self._close(4)
        paid, _ = self._disburse(outs, 4)
        self.assertGreater(paid, 0)
        self._assert_chain_intact()
        self.assertGreater(len(self.ledger.receipts), before_receipts)

    def test_cheap_validations_refused_unsigned(self):
        """Structural checks fire before the signature check — these need
        no signing at all."""
        self.gate.advance_epoch(1)
        # zero / negative duration
        for dur in (0, -3):
            with self.assertRaises(UnlawfulInterception):
                self.gate.apply_interception(self._order(
                    f"INT-Z-{dur}", "freeze_pool", {"pool": "human"},
                    dur, 1, sign=False))
        # non-int duration
        with self.assertRaises(UnlawfulInterception):
            self.gate.apply_interception(self._order(
                "INT-Z-F", "freeze_pool", {"pool": "human"}, 2.5, 1, sign=False))
        # registry scope key — the registry is never interceptable
        with self.assertRaises(UnlawfulInterception):
            self.gate.apply_interception(self._order(
                "INT-Z-R", "freeze_pool",
                {"pool": "human", "registry": "rotate"}, 5, 1, sign=False))
        # empty reason
        with self.assertRaises(UnlawfulInterception):
            self.gate.apply_interception(self._order(
                "INT-Z-E", "freeze_pool", {"pool": "human"}, 5, 1,
                reason="  ", sign=False))
        # duplicate order_id
        o1 = self._order("INT-DUP", "freeze_pool", {"pool": "human"}, 2, 1)
        self.gate.apply_interception(o1)
        with self.assertRaises(UnlawfulInterception):
            self.gate.apply_interception(self._order(
                "INT-DUP", "freeze_pool", {"pool": "machine"}, 2, 1))
        self.assertEqual(len(self.gate.live_orders()), 1)

    # -- 3. auto-expiry ----------------------------------------------------
    def test_auto_expiry(self):
        for e in range(1, 20):
            self._cycle(e)
        order = self._order("INT-EXP", "freeze_pool", {"pool": "human"}, 2, 20)
        self.gate.advance_epoch(20)
        self.gate.apply_interception(order)

        outs = self._close(20)
        _, refused = self._disburse(outs, 20)
        self.assertGreater(refused, 0)

        self.gate.advance_epoch(21)
        outs = self._close(21)
        _, refused = self._disburse(outs, 21)
        self.assertGreater(refused, 0)

        # epoch 22 == issued(20) + duration(2): auto-expired, no hand needed
        self.gate.advance_epoch(22)
        self.assertEqual(len(self.gate.live_orders()), 0)
        expired = self._interception_receipts("order_expired")
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].detail["order_id"], "INT-EXP")

        outs = self._close(22)
        paid, refused = self._disburse(outs, 22)
        self.assertGreater(paid, 0)
        self.assertEqual(refused, 0)
        self._assert_chain_intact()

    # -- 4. explicit release, no auto-pay -----------------------------------
    def test_explicit_release_no_autopay(self):
        for e in range(1, 30):
            self._cycle(e)
        pre = dict(self.ledger.emitted)

        freeze = self._order("INT-REL-1", "freeze_pool", {"pool": "human"},
                             100, 30, reason="drill: long freeze")
        self.gate.advance_epoch(30)
        self.gate.apply_interception(freeze)

        # frozen epochs: measurement recorded, nothing paid
        frozen_claims = []
        for e in (30, 31):
            self.gate.advance_epoch(e)
            self._accrue(e)
            outs = self._close(e)
            frozen_claims.append(outs["human"])
            _, refused = self._disburse(outs, e)
            self.assertGreater(refused, 0)
            self._decay()
        self.assertEqual(self.ledger.emitted["human"], pre["human"])

        # explicit release — signed, references the live order
        self.gate.advance_epoch(32)
        release = self._order("INT-REL-2", "release",
                              {"order_id": "INT-REL-1"}, 5, 32,
                              reason="drill: explicit early release")
        self.gate.apply_interception(release)
        released = self._interception_receipts("order_released")
        self.assertEqual(len(released), 1)
        self.assertEqual(released[0].detail["order_id"], "INT-REL-1")
        self.assertEqual(released[0].detail["by_order"], "INT-REL-2")
        self.assertEqual(len(self.gate.live_orders()), 0)

        # release itself pays nothing — NO auto-pay
        self.assertEqual(self.ledger.emitted["human"], pre["human"])

        # releasing a non-live order refuses
        with self.assertRaises(UnlawfulInterception):
            self.gate.apply_interception(self._order(
                "INT-REL-3", "release", {"order_id": "INT-REL-1"}, 5, 32,
                reason="drill: double release"))

        # frozen claims re-disbursed EXPLICITLY, each receipted
        repaid = 0.0
        for claim in frozen_claims:
            for uid, fig in claim.per_member.items():
                self.gate.disburse("human", uid, fig, 32)
                repaid += fig.value
        self.assertGreater(repaid, 0)
        self.assertAlmostEqual(self.ledger.emitted["human"] - pre["human"],
                               repaid, places=9)
        self._assert_chain_intact()

    # -- 5. in-flight epoch semantics ---------------------------------------
    def test_in_flight_completes_under_pre_freeze_law(self):
        for e in range(1, 11):
            self._cycle(e)
        freeze = self._order("INT-FLT", "freeze_pool", {"pool": "human"},
                             5, 11)
        self.gate.advance_epoch(11)
        self.gate.apply_interception(freeze)

        # a disbursement tagged epoch 10 — BEFORE the freeze's epoch —
        # completes under pre-freeze law even though the freeze is live now
        mmap = standing_map(self.ledger, [MEMBERS[0], MEMBERS[2]])
        late = self.gate.emission_close("human", mmap, F(1000.0, "MODELED"), 10)
        uid = next(iter(late.per_member))
        r = self.gate.disburse("human", uid, late.per_member[uid], 10)
        self.assertEqual(r.kind, "disbursement")

        # same pool, epoch >= freeze epoch: refused
        with self.assertRaises(InterceptionFreezeError):
            self.gate.disburse("human", uid, late.per_member[uid], 11)
        self._assert_chain_intact()

    # -- 6. freeze_all -------------------------------------------------------
    def test_freeze_all_blocks_transfer_and_lock(self):
        for e in range(1, 6):
            self._cycle(e)
        # fund the Core Cause Lock (member 1 donates efuse; member 0 stays clean)
        self.gate.donate(MEMBERS[1], F(5.0, "MODELED"), "efuse", 5)
        self.assertGreater(self.ledger.lock_balance, 0)

        order = self._order("INT-ALL", "freeze_all", {"global": True}, 3, 6)
        self.gate.advance_epoch(6)
        self.gate.apply_interception(order)

        # both pools' disbursement refused
        outs = self._close(6)
        _, refused = self._disburse(outs, 6)
        self.assertEqual(refused, len(outs["human"].per_member)
                        + len(outs["machine"].per_member))
        # merit ownership movement halted
        with self.assertRaises(InterceptionFreezeError):
            self.gate.transfer_merit(MEMBERS[0], MEMBERS[1], F(1.0, "VERIFIED"),
                                     "sale", 6)
        # Lock movement halted
        r = T.Receipt.build(MEMBERS[0], "merit_accrual", {"work_ref": "cause"},
                            "VERIFIED", 6, self.ledger._chain_head)
        with self.assertRaises(InterceptionFreezeError):
            self.gate.cause_disburse(MEMBERS[0], F(1.0, "VERIFIED"), r, 6)
        self.assertGreater(self.ledger.lock_balance, 0)  # untouched
        # routing halted
        with self.assertRaises(InterceptionFreezeError):
            self.gate.mesh_route(MEMBERS[0], "human", "manifest-xyz", 6)
        # giving still flows
        self.gate.donate(MEMBERS[2], F(2.0, "MODELED"), "fiat", 6)
        self.assertEqual(len(self.ledger.honor.get(MEMBERS[2], [])), 1)

        # pool-scoped freeze does NOT block merit transfer (book is pool-agnostic)
        self.gate.advance_epoch(9)  # INT-ALL expired (6+3)
        self.assertEqual(len(self.gate.live_orders()), 0)
        pool_freeze = self._order("INT-PF", "freeze_pool", {"pool": "human"},
                                  2, 9)
        self.gate.apply_interception(pool_freeze)
        bal0 = self.ledger.merit_balances.get(MEMBERS[0], 0.0)
        if bal0 > 1.0:
            self.gate.transfer_merit(MEMBERS[0], MEMBERS[1], F(1.0, "VERIFIED"),
                                     "sale", 9)
        self._assert_chain_intact()

    # -- 7. hold_emission ----------------------------------------------------
    def test_hold_emission(self):
        for e in range(1, 8):
            self._cycle(e)
        order = self._order("INT-HOLD", "hold_emission", {"pool": "machine"},
                            3, 8)
        self.gate.advance_epoch(8)
        self.gate.apply_interception(order)

        self.gate.advance_epoch(8)
        mmap = standing_map(
            self.ledger,
            [m for i, m in enumerate(MEMBERS) if i % 2 == 1])
        # the computation itself is held
        with self.assertRaises(InterceptionFreezeError):
            self.gate.emission_close("machine", mmap, F(1000.0, "MODELED"), 8)
        # human pool computes and pays normally
        hmap = standing_map(
            self.ledger,
            [m for i, m in enumerate(MEMBERS) if i % 2 == 0])
        hout = self.gate.emission_close("human", hmap, F(1000.0, "MODELED"), 8)
        paid, refused = self._disburse({"human": hout}, 8)
        self.assertGreater(paid, 0)
        self.assertEqual(refused, 0)
        # measurement and giving flow on the held pool too
        self._accrue(8)
        self.gate.donate(MEMBERS[1], F(1.0, "MODELED"), "fiat", 8)
        held = self._interception_receipts("movement_refused")
        self.assertTrue(any(r.detail["movement"] == "emission_close"
                            for r in held))
        self._assert_chain_intact()

    # -- 8. freeze with reserve movement refused, pure measurement allowed ---
    def test_freeze_refuses_reserve_movement(self):
        for e in range(1, 4):
            self._cycle(e)
        order = self._order("INT-RSV", "freeze_pool", {"pool": "human"}, 2, 4)
        self.gate.advance_epoch(4)
        self.gate.apply_interception(order)
        mmap = standing_map(
            self.ledger,
            [m for i, m in enumerate(MEMBERS) if i % 2 == 0])
        # reserve absorb under freeze = fund movement -> refused
        with self.assertRaises(InterceptionFreezeError):
            self.gate.emission_close("human", mmap, F(1000.0, "MODELED"), 4,
                                     holdback_fraction=F(0.1, "MODELED"))
        # pure computation (no holdback) continues
        out = self.gate.emission_close("human", mmap, F(1000.0, "MODELED"), 4)
        self.assertGreaterEqual(out.total.value, 0)
        self.assertEqual(self.ledger.reserve["human"], 0.0)
        self._assert_chain_intact()

    # -- 9. in-config registry ----------------------------------------------
    def test_registry_from_config_not_hardcoded(self):
        cfg = {"founder-test": base64.b64encode(self.founder_pub).decode()}
        reg = AuthorityRegistry.from_config(cfg)
        self.assertEqual(reg.pubkey("founder-test"), self.founder_pub)
        self.assertIsNone(reg.pubkey("nobody"))
        gate = InterceptedLedger(T.Ledger(), reg)
        gate.advance_epoch(1)
        o = self._order("INT-CFG", "freeze_pool", {"pool": "human"}, 1, 1)
        gate.apply_interception(o)
        self.assertEqual(len(gate.live_orders()), 1)
        # empty config -> no authority -> refused
        gate2 = InterceptedLedger(T.Ledger(), AuthorityRegistry.from_config({}))
        gate2.advance_epoch(1)
        with self.assertRaises(UnlawfulInterception):
            gate2.apply_interception(self._order(
                "INT-CFG2", "freeze_pool", {"pool": "human"}, 1, 1))

    # -- 10. summary surface --------------------------------------------------
    def test_summary_surface(self):
        order = self._order("INT-SUM", "freeze_pool", {"pool": "machine"},
                            4, 2, reason="drill: summary")
        self.gate.advance_epoch(2)
        self.gate.apply_interception(order)
        s = self.gate.summary()
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["order_id"], "INT-SUM")
        self.assertEqual(s[0]["action"], "freeze_pool")
        self.assertEqual(s[0]["scope"], {"pool": "machine"})
        self.assertEqual(s[0]["effective_epoch"], 2)
        self.assertEqual(s[0]["expiry_epoch"], 6)
        self.assertEqual(s[0]["authority_key_id"], "founder-test")
        self.assertEqual(s[0]["reason"], "drill: summary")

    def test_schema_is_testnet(self):
        self.assertTrue(SCHEMA.endswith(".testnet"))
        self.assertEqual(sorted(ACTIONS),
                         ["freeze_all", "freeze_pool", "hold_emission", "release"])
        self.assertEqual(MAX_INTERCEPT_EPOCHS, 100)
        self.assertIn("interception", T.RECEIPT_KINDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)

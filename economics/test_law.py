#!/usr/bin/env python3
"""
test_law.py — tests for economics/law.py (Perpetuity I-6: supersession).

Covers: lawful v1→v2 at an epoch boundary (MODELED decay-rate change),
in-flight completion under the old law, prospective-only handoff, and
the 7 unlawful variants (unsigned, attacker-signed, constitutional
change, direct-mutation bypass, stale from-version, mid-epoch
activation, insane value).

ALL SIMULATED. ALL IN-MEMORY. Ephemeral TEST keypairs (/tmp only),
generated fresh per test-class run. Testnet only.
"""
import unittest

import tokenomics as T
from wallet import generate_test_keypair

import law
from law import (
    CONSTITUTIONAL, CONSTITUTIONAL_SOURCES, MUTABLE, LawProposal,
    LawRegistry, LawVersion, UnlawfulSupersession, VersionedLedger,
)

FOUNDER_ID = "founder-test"
MODELED_V1 = {"peg_ratio_E": 1000.0, "merit_decay_rate": 0.02}
MERIT_WEIGHT = 10.0  # MODELED


def make_world():
    """Fresh in-memory world: ledger + registry + law-aware wrapper."""
    ledger = T.Ledger()
    reg = LawRegistry(
        genesis_params=dict(MODELED_V1),
        genesis_provenance={n: "MODELED" for n in MODELED_V1},
        authority_pubkeys={FOUNDER_ID: WORLD["founder_pub"]},
    )
    return ledger, reg, VersionedLedger(ledger, reg)


def sign_proposal(prop, priv):
    return prop.sign(priv)


def standing_map(ledger, members):
    """Pool-roster standing restatement for epoch_close: {uid: Figure}
    with each value equal to the ledger's earned standing. The standing
    cross-check passes; the gate derives every weight from standing,
    never from balances."""
    return {m: T.Figure(ledger.standing(m).value, "VERIFIED",
                        "test roster standing restatement")
            for m in members}


def drive_epoch(L, ledger, members, epoch, law_version=None):
    """One epoch of the cycle under the wrapper: accrue → close →
    disburse → decay. Every receipt stamped with the law version."""
    for m in members:
        r = L.build_receipt(m, "merit_accrual",
                            {"work_ref": f"epoch-{epoch}/{m}"},
                            "VERIFIED", epoch, law_version)
        L.ledger.accrue_merit(m, r, T.Figure(MERIT_WEIGHT, "MODELED"))
    for pool in ("human", "machine"):
        roster = [m for i, m in enumerate(members)
                  if (i % 2 == 0) == (pool == "human")]
        oc = L.epoch_close(pool, standing_map(ledger, roster), epoch,
                           law_version)
        for uid, fig in oc.per_member.items():
            L.disburse_under(pool, uid, fig, epoch, oc.law_version)
    for m in members:
        L.apply_decay(m, 1, law_version)


def lawful_dry_run(ledger, proposal):
    """Twain² dry-run: N epochs of the cycle's decay math under the new
    params on a COPY of live state. Raises on any failure/corruption."""
    def run():
        new_rate = proposal.param_changes["merit_decay_rate"]
        snap = dict(ledger.merit_balances)
        try:
            probe = dict(snap)
            for _ in range(5):
                for k, v in probe.items():
                    nv = v * (1 - new_rate)
                    if not (0.0 <= nv <= v):
                        raise RuntimeError(
                            f"decay math corrupt for {k}: {v} -> {nv}")
                    probe[k] = nv
        finally:
            ledger.merit_balances.clear()
            ledger.merit_balances.update(snap)
    return run


def chain_breaks(ledger):
    recs = ledger.receipts
    return sum(1 for i in range(1, len(recs))
               if recs[i].prev_hash != recs[i - 1].manifest_hash)


class LawTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ephemeral TEST keypairs, generated once for the class run.
        cls.founder_priv, cls.founder_pub = generate_test_keypair()
        cls.attacker_priv, cls.attacker_pub = generate_test_keypair()
        global WORLD
        WORLD = {"founder_pub": cls.founder_pub,
                 "attacker_pub": cls.attacker_pub}
        cls.MEMBERS = [f"unity:testnet:member-{i:02d}" for i in range(4)]

    def setUp(self):
        self.ledger, self.reg, self.L = make_world()
        self.members = list(self.MEMBERS)

    def lawful_proposal(self, pid="SUP-001", to_version="v2",
                        changes=None, rationale="MODELED: slower decay",
                        key_id=FOUNDER_ID, priv=None):
        p = LawProposal(pid, self.reg.current().version, to_version,
                        changes if changes is not None
                        else {"merit_decay_rate": 0.01},
                        rationale, key_id)
        return p.sign(priv if priv is not None else self.founder_priv)


class TestConstitutionalSet(LawTestBase):
    def test_constitutional_set_matches_davids_laws(self):
        # The five named in the task, each with its source.
        for name in ("unity_non_transferable", "efuse_never_bought_sold",
                     "honor_never_converts", "unknown_never_pays",
                     "unity_binding"):
            self.assertIn(name, CONSTITUTIONAL, name)
            self.assertTrue(CONSTITUTIONAL_SOURCES[name], name)

    def test_every_constitutional_law_has_a_source(self):
        for name in CONSTITUTIONAL:
            self.assertIn(name, CONSTITUTIONAL_SOURCES, name)
            self.assertTrue(CONSTITUTIONAL_SOURCES[name].strip(), name)

    def test_mutable_set_is_the_held_operational_digits(self):
        self.assertIn("merit_decay_rate", MUTABLE)
        self.assertIn("peg_ratio_E", MUTABLE)
        self.assertTrue(CONSTITUTIONAL.isdisjoint(MUTABLE))


class TestGenesis(LawTestBase):
    def test_current_is_explicit_state(self):
        cur = self.reg.current()
        self.assertEqual(cur.version, "v1")
        self.assertEqual(cur.status, LawVersion.ACTIVE)
        self.assertEqual(cur.value("merit_decay_rate"), 0.02)

    def test_held_digit_refuses(self):
        # S-1: the law refuses rather than invents.
        with self.assertRaises(T.HeldParameterError):
            self.L.param("epoch_length")

    def test_genesis_rejects_unknown_param(self):
        with self.assertRaises(law.LawError):
            LawRegistry(genesis_params={"not_a_param": 1})


class TestLawfulSupersession(LawTestBase):
    def run_to_boundary(self):
        for e in range(1, 9):
            drive_epoch(self.L, self.ledger, self.members, e)
        prop = self.lawful_proposal()
        new = self.reg.apply_supersession(
            prop, lawful_dry_run(self.ledger, prop),
            at_epoch=8, activation_epoch=9)
        return prop, new

    def test_full_pipeline(self):
        prop, new = self.run_to_boundary()
        # PENDING: the old law stays ACTIVE through the current epoch.
        self.assertEqual(new.status, LawVersion.PENDING_ACTIVATION)
        self.assertEqual(self.reg.current().version, "v1")
        self.assertEqual(
            [ev["event"] for ev in self.reg.process_log],
            ["GENESIS_LAW", "SUPERSESSION_PROPOSED",
             "SUPERSESSION_VERIFIED", "SUPERSESSION_SCHEDULED"])
        # advance_epoch(8): boundary not reached — nothing happens.
        self.assertEqual(self.reg.advance_epoch(8), [])
        self.assertEqual(self.reg.current().version, "v1")
        # advance_epoch(9): the boundary — v1 yields, v2 activates.
        activated = self.reg.advance_epoch(9)
        self.assertEqual([v.version for v in activated], ["v2"])
        self.assertEqual(self.reg.current().version, "v2")
        self.assertEqual(self.reg.get("v1").status, LawVersion.SUPERSEDED)
        events = [ev["event"] for ev in self.reg.process_log]
        self.assertIn("LAW_YIELDED", events)
        self.assertIn("SUPERSESSION_ACTIVATED", events)
        handoff = next(ev for ev in self.reg.process_log
                       if ev["event"] == "SUPERSESSION_ACTIVATED")
        self.assertEqual(handoff["from"], "v1")
        self.assertIn("authority_proof", handoff)
        self.assertIn("merit_decay_rate", handoff["param_changes"])
        # v2's params are sealed: the new digit is effective.
        self.assertEqual(self.reg.current().value("merit_decay_rate"), 0.01)
        self.assertEqual(self.reg.current().value("peg_ratio_E"), 1000.0)

    def test_rate_change_effective_under_v2(self):
        self.run_to_boundary()
        self.reg.advance_epoch(9)
        probe = "unity:testnet:rate-probe"
        r = self.L.build_receipt(probe, "merit_accrual",
                                 {"work_ref": "probe"}, "VERIFIED", 9)
        self.ledger.accrue_merit(probe, r, T.Figure(100.0, "MODELED"))
        b0 = self.ledger.merit_balances[probe]
        self.L.apply_decay(probe, 1)  # current law = v2
        measured = self.ledger.merit_balances[probe] / b0
        self.assertAlmostEqual(measured, 0.99, places=12)

    def test_one_pending_at_a_time(self):
        self.run_to_boundary()
        p2 = self.lawful_proposal(pid="SUP-002", to_version="v3")
        with self.assertRaises(UnlawfulSupersession):
            self.reg.propose(p2)


class TestInFlightAndProspective(LawTestBase):
    def test_in_flight_completes_under_v1_after_handoff(self):
        for e in range(1, 9):
            drive_epoch(self.L, self.ledger, self.members, e)
        prop = self.lawful_proposal()
        self.reg.apply_supersession(
            prop, lawful_dry_run(self.ledger, prop),
            at_epoch=8, activation_epoch=9)
        # Emission COMPUTED under v1 while v1 is still ACTIVE (pre-boundary).
        mmap = standing_map(self.ledger, self.members[:2])
        oc = self.L.epoch_close("human", mmap, 8)
        self.assertEqual(oc.law_version, "v1")
        # The boundary: v1 yields, v2 activates.
        self.reg.advance_epoch(9)
        self.assertEqual(self.reg.current().version, "v2")
        # The v1-stamped disbursement completes under v1 — the stamp rules.
        uid = next(iter(oc.per_member))
        before = dict(self.ledger.emitted)
        self.L.disburse_under("human", uid, oc.per_member[uid], 9,
                              law_version=oc.law_version)
        self.assertGreater(self.ledger.emitted["human"], before["human"])

    def test_fresh_v1_work_after_activation_refused(self):
        for e in range(1, 9):
            drive_epoch(self.L, self.ledger, self.members, e)
        prop = self.lawful_proposal()
        self.reg.apply_supersession(
            prop, lawful_dry_run(self.ledger, prop),
            at_epoch=8, activation_epoch=9)
        self.reg.advance_epoch(9)
        mmap = standing_map(self.ledger, self.members[:2])
        with self.assertRaises(UnlawfulSupersession):
            self.L.epoch_close("human", mmap, 9, law_version="v1")
        with self.assertRaises(UnlawfulSupersession):
            self.L.apply_decay(self.members[0], 1, law_version="v1")

    def test_handoff_is_prospective_only(self):
        for e in range(1, 9):
            drive_epoch(self.L, self.ledger, self.members, e)
        prop = self.lawful_proposal()
        self.reg.apply_supersession(
            prop, lawful_dry_run(self.ledger, prop),
            at_epoch=8, activation_epoch=9)
        balances_before = dict(self.ledger.merit_balances)
        emitted_before = dict(self.ledger.emitted)
        self.reg.advance_epoch(9)
        # No rewrite of history at the boundary: balances and emission
        # carried forward unchanged.
        self.assertEqual(dict(self.ledger.merit_balances), balances_before)
        self.assertEqual(dict(self.ledger.emitted), emitted_before)

    def test_receipt_chain_intact_across_handoff(self):
        for e in range(1, 9):
            drive_epoch(self.L, self.ledger, self.members, e)
        prop = self.lawful_proposal()
        self.reg.apply_supersession(
            prop, lawful_dry_run(self.ledger, prop),
            at_epoch=8, activation_epoch=9)
        self.reg.advance_epoch(9)
        for e in range(9, 12):
            drive_epoch(self.L, self.ledger, self.members, e)
        self.assertEqual(chain_breaks(self.ledger), 0)
        recs = self.ledger.receipts
        self.assertEqual(self.ledger._chain_head, recs[-1].manifest_hash)
        # Receipts built through the law-aware wrapper are stamped with
        # the law version under which they began. (Receipts minted inside
        # tokenomics.Ledger internals do not carry the stamp yet — that
        # needs tokenomics.py itself to resolve params through the
        # registry; flagged as integration follow-up, not done here.)
        wrapper_built = [r for r in recs if r.kind == "merit_accrual"]
        self.assertTrue(wrapper_built)
        self.assertTrue(all("law_version" in r.detail
                            for r in wrapper_built))
        stamped = {r.detail.get("law_version") for r in wrapper_built}
        self.assertEqual(stamped, {"v1", "v2"})
        # The process log shows the full ordered handoff.
        events = [ev["event"] for ev in self.reg.process_log]
        seq = ["GENESIS_LAW", "SUPERSESSION_PROPOSED",
               "SUPERSESSION_VERIFIED", "SUPERSESSION_SCHEDULED",
               "LAW_YIELDED", "SUPERSESSION_ACTIVATED"]
        idx = [events.index(s) for s in seq]
        self.assertEqual(idx, sorted(idx))


class TestSevenRefusals(LawTestBase):
    """The 7 unlawful supersession variants. Each must be refused, the law
    unchanged (still v2 after the lawful setup), refusals receipted."""

    def lawful_v2(self):
        for e in range(1, 9):
            drive_epoch(self.L, self.ledger, self.members, e)
        prop = self.lawful_proposal()
        self.reg.apply_supersession(
            prop, lawful_dry_run(self.ledger, prop),
            at_epoch=8, activation_epoch=9)
        self.reg.advance_epoch(9)
        self.assertEqual(self.reg.current().version, "v2")

    def dry(self, proposal):
        return lawful_dry_run(self.ledger, proposal)

    def assert_law_unchanged(self):
        self.assertEqual(self.reg.current().version, "v2")
        self.assertEqual(self.reg.get("v2").value("merit_decay_rate"), 0.01)

    def test_a_unsigned_proposal(self):
        self.lawful_v2()
        p = LawProposal("SUP-ATT-1", "v2", "v3",
                        {"merit_decay_rate": 0.05},
                        "no signature", FOUNDER_ID)
        with self.assertRaises(UnlawfulSupersession):
            self.reg.apply_supersession(p, self.dry(p), at_epoch=14,
                                        activation_epoch=15)
        self.assert_law_unchanged()

    def test_b_attacker_signed_proposal(self):
        self.lawful_v2()
        p = LawProposal("SUP-ATT-2", "v2", "v3",
                        {"merit_decay_rate": 0.05},
                        "attacker", "attacker-test").sign(self.attacker_priv)
        with self.assertRaises(UnlawfulSupersession):
            self.reg.apply_supersession(p, self.dry(p), at_epoch=14,
                                        activation_epoch=15)
        self.assert_law_unchanged()

    def test_c_constitutional_change_refused_at_propose(self):
        self.lawful_v2()
        # Task variants: the lifetime cap AND David's named constitutional
        # laws (Unity non-transferability, eFuse never-bought/sold).
        for pid, changes in (
                ("SUP-ATT-3a", {"lifetime_cap": 200_000_000.0}),
                ("SUP-ATT-3b", {"unity_non_transferable": False}),
                ("SUP-ATT-3c", {"efuse_never_bought_sold": False}),
                ("SUP-ATT-3d", {"honor_never_converts": False}),
                ("SUP-ATT-3e", {"merit_transferable": False})):
            p = LawProposal(pid, "v2", "v3", changes,
                            "touch the constitution", FOUNDER_ID)
            with self.assertRaises(UnlawfulSupersession, msg=pid):
                self.reg.propose(p)  # refused AT PROPOSE time
        self.assert_law_unchanged()
        refused = [ev for ev in self.reg.process_log
                   if ev["event"] == "PROPOSAL_REFUSED"]
        self.assertEqual(len(refused), 5)

    def test_d_direct_mutation_bypass_detected(self):
        self.lawful_v2()
        # An attacker sneaks a version straight into the registry — no
        # process, no activation receipt. Use refuses it.
        self.reg._versions["v9"] = LawVersion(
            "v9", {"merit_decay_rate": 0.5}, LawVersion.ACTIVE, 15)
        with self.assertRaises(UnlawfulSupersession):
            self.L.epoch_close("human",
                               standing_map(self.ledger, self.members[:1]),
                               15, law_version="v9")
        with self.assertRaises(UnlawfulSupersession):
            self.L.disburse_under("human", self.members[0],
                                  T.Figure(1.0, "MODELED"), 15,
                                  law_version="v9")
        self.assert_law_unchanged()

    def test_e_stale_from_version(self):
        self.lawful_v2()
        p = LawProposal("SUP-ATT-5", "v1", "v3",
                        {"merit_decay_rate": 0.05},
                        "stale lineage", FOUNDER_ID).sign(self.founder_priv)
        with self.assertRaises(UnlawfulSupersession):
            self.reg.apply_supersession(p, self.dry(p), at_epoch=14,
                                        activation_epoch=15)
        self.assert_law_unchanged()

    def test_f_mid_epoch_activation(self):
        self.lawful_v2()
        p = self.lawful_proposal(pid="SUP-ATT-6", to_version="v3",
                                 changes={"merit_decay_rate": 0.05},
                                 rationale="mid-epoch")
        with self.assertRaises(UnlawfulSupersession):
            self.reg.apply_supersession(p, self.dry(p), at_epoch=14,
                                        activation_epoch=14)
        self.assert_law_unchanged()

    def test_g_insane_value(self):
        self.lawful_v2()
        p = self.lawful_proposal(pid="SUP-ATT-7", to_version="v3",
                                 changes={"merit_decay_rate": 1.5},
                                 rationale="insane")
        with self.assertRaises(UnlawfulSupersession):
            self.reg.apply_supersession(p, self.dry(p), at_epoch=14,
                                        activation_epoch=15)
        self.assert_law_unchanged()

    def test_extra_failing_dry_run_refused(self):
        self.lawful_v2()
        p = self.lawful_proposal(pid="SUP-ATT-8", to_version="v3",
                                 changes={"merit_decay_rate": 0.05})
        def bad_dry_run():
            raise RuntimeError("simulated migration corruption")
        with self.assertRaises(UnlawfulSupersession):
            self.reg.apply_supersession(p, bad_dry_run, at_epoch=14,
                                        activation_epoch=15)
        refused = [ev for ev in self.reg.process_log
                   if ev["event"] == "SUPERSESSION_REFUSED"]
        self.assertTrue(
            any("TWAIN2" in str(ev["verdicts"]) and
                "REFUSE" in str(ev["verdicts"]["TWAIN2"])
                for ev in refused))
        self.assert_law_unchanged()

    def test_unknown_param_refused_at_propose(self):
        self.lawful_v2()
        p = LawProposal("SUP-ATT-9", "v2", "v3", {"raise_the_moon": 1},
                        "unknown", FOUNDER_ID)
        with self.assertRaises(UnlawfulSupersession):
            self.reg.propose(p)
        self.assert_law_unchanged()


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""
Tests for the DCLM winter mechanism (~/workspace/unity-world/dclm/winter.py).

All must pass. Testnet only. Test keys only — never dollars, never eFuse.
"""
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from meter import (  # noqa: E402
    IDENTITY_PREFIX,
    UNIT,
    MeterRefused,
    Wallet,
    verify_receipt,
)
from rights import (  # noqa: E402
    COMMIT_KINDS,
    GRANT,
    DENY,
    REASON_INTERNAL_SOURCE_REQUIRED,
    check_rights,
)
from winter import (  # noqa: E402
    EMISSION_FLOOR,
    LABEL_SUMMER,
    LABEL_TILTING,
    LABEL_WINTER,
    OUTCOME_GRANTED,
    OUTCOME_REFUSED,
    REASON_INSUFFICIENT_RESERVE,
    REASON_PHANTOM,
    REASON_STORE_AT_SURVIVAL_NEED,
    SURVIVAL_NEED_CAP,
    WINTER_CLAIM_MIN_GRADIENT,
    WinterReserve,
    WinterSignal,
    WinterState,
    emission_multiplier,
    evaluate_trigger,
    winter_aware_faucet,
    winter_release,
    winter_store,
)
from writes import (  # noqa: E402
    MemoryCommitStore,
    dclm_commit,
    verify_commit,
)

TEST_IDENTITY = f"{IDENTITY_PREFIX}1e26f0d9e8c46818"  # same test identity as gate

# A supporting signal with real winter pressure: |dev|=0.06 ->
# x=(0.06-0.02)/0.01=4 -> tilt~0.964 -> gradient~0.337 (>= claim floor).
WINTER_SIGNAL = WinterSignal(peg_deviation=-0.06, peg_provenance="REPORTED")
WINTER_REASON = {
    "trigger_condition": "peg under stress",
    "measured_value": -0.06,
    "threshold": "PROPOSED band edge 0.02 (HELD-FOR-DAVID)",
}
SPRING_SIGNAL = WinterSignal(peg_deviation=0.0, peg_provenance="REPORTED")
SPRING_REASON = {
    "trigger_condition": "trigger cleared — peg back in band",
    "measured_value": 0.0,
    "threshold": "PROPOSED band edge 0.02 (HELD-FOR-DAVID)",
}


def fresh_pair():
    """Isolated wallet + reserve — tests never touch real state."""
    wallet = Wallet(state_dir=tempfile.mkdtemp(prefix="winter-test-wallet-"))
    reserve = WinterReserve(
        state_dir=tempfile.mkdtemp(prefix="winter-test-reserve-"))
    return wallet, reserve


def envelope_receipt(envelope):
    return envelope["receipt"]


# ---------------------------------------------------------------------------
# the trigger: continuous, UNKNOWN-safe
# ---------------------------------------------------------------------------

class TriggerTests(unittest.TestCase):
    def test_unknown_signal_stays_summer(self):
        """UNKNOWN never PASS: unreadable signal -> SUMMER, never winter."""
        state = evaluate_trigger(WinterSignal())
        self.assertEqual(state.gradient, 0.0)
        self.assertEqual(state.label, LABEL_SUMMER)
        self.assertEqual(state.provenance, "UNKNOWN")

    def test_garbage_signal_stays_summer(self):
        state = evaluate_trigger(None)
        self.assertEqual(state.gradient, 0.0)
        self.assertEqual(state.label, LABEL_SUMMER)

    def test_perfect_summer_zero_gradient(self):
        state = evaluate_trigger(
            WinterSignal(peg_deviation=0.0, peg_provenance="REPORTED",
                         activity_delta=0.0, activity_provenance="REPORTED"))
        self.assertEqual(state.gradient, 0.0)
        self.assertEqual(state.label, LABEL_SUMMER)
        # Readable, just calm: DERIVED, not UNKNOWN.
        self.assertEqual(state.provenance, "DERIVED")

    def test_gradient_continuity_peg(self):
        """Small signal changes -> small gradient changes. No cliffs:
        sweep |deviation| finely and assert the max adjacent step is tiny."""
        prev = None
        max_step = 0.0
        steps = 400
        for i in range(steps + 1):
            dev = -0.08 + (0.16 * i / steps)
            g = evaluate_trigger(
                WinterSignal(peg_deviation=dev, peg_provenance="REPORTED")
            ).gradient
            if prev is not None:
                max_step = max(max_step, abs(g - prev))
            prev = g
        self.assertLess(max_step, 0.02,
                        f"cliff detected in peg tilt: max step {max_step}")

    def test_gradient_continuity_activity(self):
        prev = None
        max_step = 0.0
        steps = 400
        for i in range(steps + 1):
            delta = -0.50 + (0.60 * i / steps)
            g = evaluate_trigger(
                WinterSignal(activity_delta=delta,
                             activity_provenance="REPORTED")).gradient
            if prev is not None:
                max_step = max(max_step, abs(g - prev))
            prev = g
        self.assertLess(max_step, 0.02,
                        f"cliff detected in activity tilt: max step {max_step}")

    def test_gradient_monotonic_and_bounded(self):
        last = -1.0
        for i in range(101):
            dev = 0.10 * i / 100
            g = evaluate_trigger(
                WinterSignal(peg_deviation=dev, peg_provenance="REPORTED")
            ).gradient
            self.assertGreaterEqual(g, 0.0)
            self.assertLessEqual(g, 1.0)
            self.assertGreaterEqual(g, last)  # more stress never less winter
            last = g

    def test_deep_stress_approaches_full_winter(self):
        state = evaluate_trigger(
            WinterSignal(peg_deviation=-0.20, peg_provenance="REPORTED",
                         activity_delta=-0.60,
                         activity_provenance="REPORTED",
                         crisis_declared=True, crisis_verified=True,
                         crisis_provenance="VERIFIED"))
        self.assertGreater(state.gradient, 0.95)
        self.assertEqual(state.label, LABEL_WINTER)

    def test_verified_crisis_tilts(self):
        state = evaluate_trigger(
            WinterSignal(crisis_declared=True, crisis_verified=True,
                         crisis_provenance="VERIFIED"))
        self.assertGreater(state.gradient, 0.0)
        self.assertEqual(state.label, LABEL_TILTING)

    def test_declared_but_unverified_crisis_is_not_a_signal(self):
        """A mere claim tilts nothing: UNKNOWN -> stays SUMMER."""
        state = evaluate_trigger(
            WinterSignal(crisis_declared=True, crisis_verified=False,
                         crisis_provenance="REPORTED"))
        self.assertFalse(WinterSignal(
            crisis_declared=True, crisis_verified=False).readable)
        self.assertEqual(state.gradient, 0.0)
        self.assertEqual(state.label, LABEL_SUMMER)
        self.assertEqual(state.provenance, "UNKNOWN")

    def test_label_bands_are_display_only(self):
        """The labels exist; the mechanism reads the gradient. A gradient
        just under a band edge behaves almost identically to one just
        over it — no behavioral cliff at the label line."""
        # |dev|=0.036 -> gradient ~0.232 (SUMMER); |dev|=0.040 ->
        # gradient ~0.267 (TILTING). The two straddle the 0.25 label
        # line but differ by < 0.05 in gradient: no behavioral cliff.
        below = evaluate_trigger(
            WinterSignal(peg_deviation=0.036, peg_provenance="REPORTED"))
        above = evaluate_trigger(
            WinterSignal(peg_deviation=0.040, peg_provenance="REPORTED"))
        self.assertEqual(below.label, LABEL_SUMMER)
        self.assertEqual(above.label, LABEL_TILTING)
        self.assertLess(abs(below.gradient - above.gradient), 0.05)


# ---------------------------------------------------------------------------
# the store: protection, capped, receipted
# ---------------------------------------------------------------------------

class StoreTests(unittest.TestCase):
    def test_store_moves_value_into_reserve(self):
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 20)
        env = winter_store(TEST_IDENTITY, 8, WINTER_REASON,
                           wallet=wallet, reserve=reserve,
                           signal=WINTER_SIGNAL)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_GRANTED)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 12)
        self.assertEqual(reserve.holding(TEST_IDENTITY), 8)
        self.assertTrue(verify_commit(env))

    def test_store_capped_at_survival_need(self):
        """The root stores only what it needs: excess is refused honestly
        and keeps flowing outward (stays in circulation)."""
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 100)
        env = winter_store(TEST_IDENTITY, SURVIVAL_NEED_CAP + 5,
                           WINTER_REASON, wallet=wallet, reserve=reserve,
                           signal=WINTER_SIGNAL)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_GRANTED)
        self.assertEqual(receipt["amount"], SURVIVAL_NEED_CAP)
        self.assertEqual(receipt["excess_circulating"], 5)
        self.assertEqual(reserve.holding(TEST_IDENTITY), SURVIVAL_NEED_CAP)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 100 - SURVIVAL_NEED_CAP)
        self.assertTrue(verify_commit(env))

        # At the cap: further stores are refused honestly, nothing moves.
        env2 = winter_store(TEST_IDENTITY, 1, WINTER_REASON,
                            wallet=wallet, reserve=reserve,
                            signal=WINTER_SIGNAL)
        r2 = envelope_receipt(env2)
        self.assertEqual(r2["outcome"], OUTCOME_REFUSED)
        self.assertEqual(r2["reason"], REASON_STORE_AT_SURVIVAL_NEED)
        self.assertEqual(reserve.holding(TEST_IDENTITY), SURVIVAL_NEED_CAP)
        self.assertEqual(wallet.balance(TEST_IDENTITY),
                         100 - SURVIVAL_NEED_CAP)
        self.assertTrue(verify_receipt(env2))

    def test_every_stored_unit_has_a_winter_reason(self):
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 20)
        winter_store(TEST_IDENTITY, 8, WINTER_REASON,
                     wallet=wallet, reserve=reserve, signal=WINTER_SIGNAL)
        with open(reserve.receipts_path, encoding="utf-8") as fh:
            trail = [json.loads(line) for line in fh if line.strip()]
        granted = [r for r in trail
                   if r.get("action") == "WINTER_STORE"
                   and r.get("outcome") == OUTCOME_GRANTED]
        self.assertEqual(len(granted), 1)
        wr = granted[0]["winter_reason"]
        self.assertEqual(wr["trigger_condition"],
                         WINTER_REASON["trigger_condition"])
        self.assertEqual(wr["measured_value"], WINTER_REASON["measured_value"])
        self.assertEqual(wr["threshold"], WINTER_REASON["threshold"])
        self.assertIn("gradient", wr)
        self.assertTrue(granted[0]["l5_audit"])
        self.assertEqual(granted[0]["claimant"], TEST_IDENTITY)

    def test_phantom_claim_refused_and_logged(self):
        """Crisis declared but NOT verified, no supporting signal:
        the phantom pattern — refused, and the claim is logged for L5."""
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 20)
        phantom = WinterSignal(crisis_declared=True, crisis_verified=False,
                               crisis_provenance="REPORTED")
        env = winter_store(TEST_IDENTITY, 8, WINTER_REASON,
                           wallet=wallet, reserve=reserve, signal=phantom)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_REFUSED)
        self.assertEqual(receipt["reason"], REASON_PHANTOM)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 20)  # untouched
        self.assertEqual(reserve.holding(TEST_IDENTITY), 0)
        self.assertTrue(verify_receipt(env))
        # The phantom claim sits on the trail with the signal snapshot.
        with open(reserve.receipts_path, encoding="utf-8") as fh:
            trail = [json.loads(line) for line in fh if line.strip()]
        phantoms = [r for r in trail if r.get("reason") == REASON_PHANTOM]
        self.assertEqual(len(phantoms), 1)
        self.assertEqual(phantoms[0]["claimant"], TEST_IDENTITY)
        self.assertTrue(phantoms[0]["l5_audit"])
        self.assertFalse(phantoms[0]["signal_snapshot"]["crisis_verified"])

    def test_store_without_signal_refused(self):
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 20)
        env = winter_store(TEST_IDENTITY, 8, WINTER_REASON,
                           wallet=wallet, reserve=reserve, signal=None)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_REFUSED)
        self.assertEqual(receipt["reason"], REASON_PHANTOM)
        self.assertEqual(reserve.holding(TEST_IDENTITY), 0)

    def test_store_needs_circulation(self):
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 3)
        env = winter_store(TEST_IDENTITY, 8, WINTER_REASON,
                           wallet=wallet, reserve=reserve,
                           signal=WINTER_SIGNAL)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_REFUSED)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 3)

    def test_non_testnet_identity_structurally_refused(self):
        # Contract change 2026-10-06: the purification medium refuses the
        # forged identity on entry (PurificationRefused), before the
        # reserve's own structural refusal runs.
        from purify import PurificationRefused
        _, reserve = fresh_pair()
        with self.assertRaises(PurificationRefused):
            winter_store("mallory", 8, WINTER_REASON, reserve=reserve,
                         signal=WINTER_SIGNAL)


# ---------------------------------------------------------------------------
# spring: the stored value re-mobilizes outward
# ---------------------------------------------------------------------------

class SpringTests(unittest.TestCase):
    def test_trigger_clear_returns_to_summer(self):
        state = evaluate_trigger(SPRING_SIGNAL)
        self.assertEqual(state.gradient, 0.0)
        self.assertEqual(state.label, LABEL_SUMMER)

    def test_spring_releases_stored_value(self):
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 20)
        winter_store(TEST_IDENTITY, 8, WINTER_REASON,
                     wallet=wallet, reserve=reserve, signal=WINTER_SIGNAL)
        env = winter_release(TEST_IDENTITY, 8, SPRING_REASON,
                             wallet=wallet, reserve=reserve,
                             signal=SPRING_SIGNAL)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_GRANTED)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 20)  # restored
        self.assertEqual(reserve.holding(TEST_IDENTITY), 0)
        wr = receipt["winter_reason"]
        self.assertEqual(wr["trigger_condition"],
                         SPRING_REASON["trigger_condition"])
        self.assertTrue(verify_commit(env))

    def test_release_refused_when_holding_short(self):
        wallet, reserve = fresh_pair()
        wallet.faucet(TEST_IDENTITY, 20)
        env = winter_release(TEST_IDENTITY, 5, SPRING_REASON,
                             wallet=wallet, reserve=reserve,
                             signal=SPRING_SIGNAL)
        receipt = envelope_receipt(env)
        self.assertEqual(receipt["outcome"], OUTCOME_REFUSED)
        self.assertEqual(receipt["reason"], REASON_INSUFFICIENT_RESERVE)
        self.assertTrue(verify_receipt(env))


# ---------------------------------------------------------------------------
# emission throttle: slowed, never stopped
# ---------------------------------------------------------------------------

class EmissionTests(unittest.TestCase):
    def test_multiplier_endpoints(self):
        self.assertEqual(emission_multiplier(0.0), 1.0)
        self.assertEqual(emission_multiplier(1.0), EMISSION_FLOOR)

    def test_multiplier_monotonic_and_continuous(self):
        prev = None
        last = 1.0
        max_step = 0.0
        for i in range(401):
            m = emission_multiplier(i / 400)
            self.assertLessEqual(m, last + 1e-12)
            last = m
            if prev is not None:
                max_step = max(max_step, abs(m - prev))
            prev = m
        self.assertLess(max_step, 0.01)

    def test_winter_aware_faucet_throttles(self):
        wallet, _ = fresh_pair()
        reserve = WinterReserve(
            state_dir=tempfile.mkdtemp(prefix="winter-test-emit-"))
        deep = WinterState(gradient=1.0, label=LABEL_WINTER, reasons=[],
                           provenance="DERIVED")
        env, record = winter_aware_faucet(wallet, TEST_IDENTITY, 10, deep,
                                          reserve)
        self.assertEqual(record["requested"], 10)
        self.assertEqual(record["granted"], 2)  # floor(10 * 0.25)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 2)
        # The slowdown is on the winter trail for L5.
        with open(reserve.receipts_path, encoding="utf-8") as fh:
            trail = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0]["type"], "EMISSION_THROTTLE")

    def test_summer_faucet_unthrottled(self):
        wallet, _ = fresh_pair()
        reserve = WinterReserve(
            state_dir=tempfile.mkdtemp(prefix="winter-test-emit-"))
        summer = WinterState(gradient=0.0, label=LABEL_SUMMER, reasons=[],
                             provenance="DERIVED")
        _, record = winter_aware_faucet(wallet, TEST_IDENTITY, 10, summer,
                                        reserve)
        self.assertEqual(record["granted"], 10)
        self.assertEqual(wallet.balance(TEST_IDENTITY), 10)


# ---------------------------------------------------------------------------
# rights boundary: the new kinds obey the same rules as the old ones
# ---------------------------------------------------------------------------

class RightsBoundaryTests(unittest.TestCase):
    def test_winter_kinds_in_whitelist(self):
        self.assertIn("WINTER_STORE", COMMIT_KINDS)
        self.assertIn("WINTER_RELEASE", COMMIT_KINDS)

    def test_winter_kinds_grant_for_dclm_internal_only(self):
        for kind in ("WINTER_STORE", "WINTER_RELEASE"):
            granted = check_rights(TEST_IDENTITY, kind,
                                   {"internal": "dclm.winter"})
            self.assertEqual(granted.verdict, GRANT, f"for {kind}")
            denied = check_rights(TEST_IDENTITY, kind, {})
            self.assertEqual(denied.verdict, DENY, f"for {kind}")
            self.assertEqual(denied.reason, REASON_INTERNAL_SOURCE_REQUIRED,
                             f"for {kind}")

    def test_winter_kinds_commit_through_dclm_commit(self):
        for kind in ("WINTER_STORE", "WINTER_RELEASE"):
            store = MemoryCommitStore()
            verdict = check_rights(TEST_IDENTITY, kind,
                                   {"internal": "dclm.winter"})
            env = dclm_commit(kind, {"kind": kind, "provenance": "DERIVED"},
                              verdict, store)
            self.assertTrue(verify_commit(env), f"for {kind}")

    def test_winter_claim_floor_is_honest(self):
        """The phantom floor is a named constant, documented as proposed."""
        self.assertGreater(WINTER_CLAIM_MIN_GRADIENT, 0.0)
        self.assertLess(WINTER_CLAIM_MIN_GRADIENT, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""
Tests for DCLM tapping (tap.py) — David's binding law: THE TREE SURVIVES
TAPPING. Maple rules, enforced: only in season, limited taps, only
mature trees, the tree heals. The creed forbids founder extraction.

Also a regression sweep: meter.py / rights.py / writes.py suites stay
green after adding TAP_OUTFLOW to the commit-kind whitelist.

Testnet only. Units are test-keys.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# Guard: a sibling worker's tokenize.py (the DCLM tokenization engine,
# in-flight) shadows stdlib `tokenize` whenever this directory is first
# on sys.path. Seed the stdlib module into sys.modules before anything
# imports dataclasses/inspect, so the shadow never bites this process.
# (Not ours to move — flagged in the worker report.)
import tokenize as _stdlib_tokenize  # noqa: E402,F401

import tap
from tap import (
    KIND_TAP_OUTFLOW,
    MAX_PER_TAP,
    MATURITY_THRESHOLD,
    REASON_FOUNDER_EXTRACTION_FORBIDDEN,
    REASON_HEALING_UNVERIFIED,
    REASON_IMMATURE_SYSTEM,
    REASON_INVALID_AMOUNT,
    REASON_NO_VERIFIED_SURPLUS,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_OFF_SEASON,
    REASON_PURPOSE_REQUIRED,
    REASON_REPLENISHMENT_EXCEEDED,
    REASON_TAP_LIMIT,
    REASON_UNKNOWN_MATURITY,
    REASON_WINTER_PROTECTION,
    TAP_RATE_PER_MEMBER_SEASON,
    Measure,
    Tapper,
    TapSeason,
)
from rights import COMMIT_KINDS, check_rights
from writes import verify_commit

MEMBER = "unity:testnet:member-sara"
MEMBER2 = "unity:testnet:member-dom"
FOUNDER_CLAIM = "unity:testnet:founder:david"
PURPOSE = "medical costs for the season"


class FakeWinter:
    """Test double for the winter worker's interface."""

    def __init__(self, gradient):
        self._gradient = gradient

    def winter_gradient(self):
        return self._gradient


class FakeWinterProtection:
    """winter.py variant exposing its own protection test."""

    def protection_mode(self):
        return True


def open_measures(**overrides):
    """Healthy, mature, surplus-bearing, healing-verified measures."""
    measures = {
        "pool_health": Measure(0.9, "DERIVED"),
        "peg_deviation_bp": Measure(5.0, "DERIVED"),
        "reserve_total": Measure(1000, "DERIVED"),
        "reserve_survival_need": Measure(500, "DERIVED"),
        "pool_headroom": Measure(200, "DERIVED"),
        "season_replenishment": Measure(1000, "DERIVED"),
    }
    measures.update(overrides)
    return measures


def open_season(state_dir=None, **overrides):
    """A TapSeason that is open: winter clear (real winter module,
    summer signal), mature, surplus, healing."""
    return TapSeason(
        winter_signal={
            "peg_deviation": 0.0,
            "peg_provenance": "DERIVED",
            "activity_delta": 0.05,   # mild growth: no contraction tilt
            "activity_provenance": "DERIVED",
            "crisis_declared": False,
            "crisis_verified": False,
            "crisis_provenance": "DERIVED",
        },
        season_id="2026-tapping",
        state_dir=state_dir,
        **open_measures(**overrides),
    )


def ducktype_season(state_dir=None, **overrides):
    """A TapSeason on the duck-type winter interface (test double),
    for the fallback path."""
    return TapSeason(
        winter_module=FakeWinter(0.1),
        season_id="2026-tapping",
        state_dir=state_dir,
        **open_measures(**overrides),
    )


class TapTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tap-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tapper(self, season=None):
        season = season or open_season()
        return Tapper(season, state_dir=self.tmp)

    def reason_of(self, envelope):
        return envelope["receipt"]["reason"]

    # -- the whitelist carries the new kind --------------------------------
    def test_tap_outflow_in_commit_kinds(self):
        self.assertIn(KIND_TAP_OUTFLOW, COMMIT_KINDS)
        v = check_rights(MEMBER, KIND_TAP_OUTFLOW,
                         {"internal": "dclm.tap", "schema": tap.SCHEMA})
        self.assertEqual(v.verdict, "GRANT")
        denied = check_rights(MEMBER, KIND_TAP_OUTFLOW, {})
        self.assertEqual(denied.verdict, "DENY")

    # -- rule 1: only in season --------------------------------------------
    def test_off_season_winter_interface_pending_refused(self):
        """winter.py absent -> PENDING -> season closed, honestly."""
        season = TapSeason(winter_module=None, season_id="2026-tapping",
                           **open_measures())
        verdict = season.evaluate()
        self.assertFalse(verdict.season_open)
        self.assertEqual(verdict.reason, REASON_OFF_SEASON)
        self.assertTrue(any("PENDING" in str(d)
                            for _, _, d in verdict.chain))
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(self.reason_of(env), REASON_OFF_SEASON)

    def test_winter_protection_refused(self):
        season = TapSeason(winter_module=FakeWinter(0.9),
                           season_id="2026-tapping",
                           **open_measures())
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_WINTER_PROTECTION)

    def test_winter_protection_mode_function_refused(self):
        """The winter worker's own protection test takes precedence."""
        season = TapSeason(winter_module=FakeWinterProtection(),
                           season_id="2026-tapping",
                           **open_measures())
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_WINTER_PROTECTION)

    # -- rule 1b: the REAL winter integration ------------------------------
    def test_real_winter_integration_open(self):
        """Real winter.py + summer signal -> gradient 0.0, season open,
        tap granted and receipted with the winter reading."""
        season = open_season()
        verdict = season.evaluate()
        self.assertTrue(verdict.season_open, verdict.chain)
        self.assertEqual(verdict.winter_gradient, 0.0)
        self.assertEqual(verdict.winter_interface, "READY")
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(env["receipt"]["outcome"], "GRANTED")
        winter_receipt = env["receipt"]["winter"]
        self.assertEqual(winter_receipt["gradient"], 0.0)
        self.assertEqual(winter_receipt["interface"], "READY")
        self.assertTrue(any("evaluate_trigger" in str(d)
                            for _, _, d in verdict.chain))

    def test_real_winter_protection_refused(self):
        """Real winter.py + storm signal (peg stress + contraction) ->
        gradient >= tap-side protection line -> no taps."""
        season = TapSeason(
            winter_signal={
                "peg_deviation": 0.10,      # far outside the band
                "peg_provenance": "DERIVED",
                "activity_delta": -0.5,     # deep contraction
                "activity_provenance": "DERIVED",
                "crisis_declared": False,
                "crisis_verified": False,
                "crisis_provenance": "DERIVED",
            },
            season_id="2026-tapping",
            **open_measures(),
        )
        verdict = season.evaluate()
        self.assertFalse(verdict.season_open)
        self.assertGreaterEqual(verdict.winter_gradient, 0.5)
        self.assertEqual(verdict.reason, REASON_WINTER_PROTECTION)
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_WINTER_PROTECTION)

    def test_real_winter_no_signal_stays_summer(self):
        """No signal -> winter.evaluate_trigger yields SUMMER ('winter
        is never assumed'); the chain records it honestly and the
        season is judged on the other rules."""
        season = TapSeason(season_id="2026-tapping",
                           **open_measures())
        verdict = season.evaluate()
        self.assertTrue(verdict.season_open, verdict.chain)
        self.assertEqual(verdict.winter_gradient, 0.0)
        self.assertTrue(any("not assumed" in str(d)
                            for _, _, d in verdict.chain))

    def test_no_verified_surplus_refused(self):
        """Verified-zero surplus: the surplus season has not come."""
        season = open_season(
            reserve_total=Measure(500, "DERIVED"),   # == survival need
            pool_headroom=Measure(0, "DERIVED"),      # no headroom
        )
        surplus, label = season.verified_surplus()
        self.assertEqual(surplus, 0)
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_OFF_SEASON)

    def test_unscorable_surplus_refused(self):
        """Unverifiable surplus: never assumed, never tapped."""
        season = open_season(pool_headroom=Measure(200, "UNKNOWN"))
        surplus, label = season.verified_surplus()
        self.assertIsNone(surplus)
        self.assertEqual(label, "UNKNOWN")
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_NO_VERIFIED_SURPLUS)

    # -- rule 3: only mature trees -----------------------------------------
    def test_immature_system_refused(self):
        season = open_season(pool_health=Measure(0.2, "DERIVED"))
        verdict = season.evaluate()
        self.assertFalse(verdict.season_open)
        self.assertEqual(verdict.reason, REASON_IMMATURE_SYSTEM)
        self.assertLess(verdict.maturity, MATURITY_THRESHOLD)
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_IMMATURE_SYSTEM)

    def test_unknown_maturity_refused(self):
        """Unscorable input -> UNKNOWN -> no taps. UNKNOWN never PASS."""
        season = open_season(pool_health=Measure(0.9, "UNKNOWN"))
        score, label = season.maturity_score()
        self.assertIsNone(score)
        self.assertEqual(label, "UNKNOWN")
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_UNKNOWN_MATURITY)

    def test_maturity_math(self):
        season = open_season()
        score, label = season.maturity_score()
        # 0.4*0.9 + 0.3*(1-5/100) + 0.3*min(1,1000/500)
        expected = round(0.4 * 0.9 + 0.3 * 0.95 + 0.3 * 1.0, 4)
        self.assertEqual(score, expected)
        self.assertEqual(label, "DERIVED")
        self.assertGreaterEqual(score, MATURITY_THRESHOLD)

    # -- rule 2: limited taps ----------------------------------------------
    def test_per_member_seasonal_cap_enforced(self):
        tp = self.tapper()
        first = tp.request_tap(MEMBER, MAX_PER_TAP, PURPOSE)
        self.assertEqual(first["receipt"]["outcome"], "GRANTED")
        second = tp.request_tap(MEMBER, MAX_PER_TAP, PURPOSE)
        self.assertEqual(second["receipt"]["outcome"], "GRANTED")
        # 50 + 50 = 100 = cap; one more key must fail.
        third = tp.request_tap(MEMBER, 1, PURPOSE)
        self.assertEqual(third["receipt"]["outcome"], "REFUSED")
        self.assertEqual(self.reason_of(third), REASON_TAP_LIMIT)
        # A different member still has their own cap.
        other = tp.request_tap(MEMBER2, MAX_PER_TAP, PURPOSE)
        self.assertEqual(other["receipt"]["outcome"], "GRANTED")

    def test_per_tap_limit_enforced(self):
        tp = self.tapper()
        env = tp.request_tap(MEMBER, MAX_PER_TAP + 1, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_TAP_LIMIT)

    # -- rule 4: the tree heals --------------------------------------------
    def test_season_outflow_never_exceeds_replenishment(self):
        """Boundary: cumulative outflow may reach replenishment exactly,
        never cross it."""
        season = open_season(
            season_replenishment=Measure(MAX_PER_TAP * 2, "DERIVED"))
        tp = self.tapper(season)
        a = tp.request_tap(MEMBER, MAX_PER_TAP, PURPOSE)
        self.assertEqual(a["receipt"]["outcome"], "GRANTED")
        b = tp.request_tap(MEMBER, MAX_PER_TAP, PURPOSE)
        self.assertEqual(b["receipt"]["outcome"], "GRANTED")
        # Season outflow is now exactly replenishment: the next tap,
        # even 1 key, must fail — never exceed.
        c = tp.request_tap(MEMBER2, 1, PURPOSE)
        self.assertEqual(c["receipt"]["outcome"], "REFUSED")
        self.assertEqual(self.reason_of(c), REASON_REPLENISHMENT_EXCEEDED)

    def test_healing_unverified_refused(self):
        season = open_season(
            season_replenishment=Measure(1000, "UNKNOWN"))
        env = self.tapper(season).request_tap(MEMBER, 10, PURPOSE)
        self.assertEqual(self.reason_of(env), REASON_HEALING_UNVERIFIED)

    # -- the creed boundary --------------------------------------------------
    def test_founder_extraction_refused(self):
        """Tapping serves members; extraction serves self. The creed
        forbids the second — refused before any season evaluation."""
        tp = self.tapper()
        env = tp.request_tap(FOUNDER_CLAIM, 10, PURPOSE)
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(self.reason_of(env),
                         REASON_FOUNDER_EXTRACTION_FORBIDDEN)

    def test_registered_founder_identity_refused(self):
        registered = "unity:testnet:member-david-real"
        os.environ["UNITY_FOUNDER_IDENTITY"] = registered
        try:
            tp = self.tapper()
            env = tp.request_tap(registered, 10, PURPOSE)
            self.assertEqual(self.reason_of(env),
                             REASON_FOUNDER_EXTRACTION_FORBIDDEN)
        finally:
            del os.environ["UNITY_FOUNDER_IDENTITY"]

    # -- structural honesty --------------------------------------------------
    def test_non_testnet_identity_refused(self):
        # Contract change 2026-10-06: the purification medium refuses
        # anonymous/forged identities on entry (PurificationRefused),
        # before the tapper's own structural refusal runs.
        from purify import PurificationRefused
        tp = self.tapper()
        with self.assertRaises(PurificationRefused):
            tp.request_tap("alice@example.com", 10, PURPOSE)
        with self.assertRaises(PurificationRefused):
            tp.request_tap(None, 10, PURPOSE)

    def test_purpose_required(self):
        tp = self.tapper()
        for bad in ("", "   ", None):
            env = tp.request_tap(MEMBER, 10, bad)
            self.assertEqual(self.reason_of(env), REASON_PURPOSE_REQUIRED,
                             f"purpose={bad!r}")

    def test_invalid_amount_refused(self):
        tp = self.tapper()
        for bad in (0, -5, 1.5, "10", True):
            env = tp.request_tap(MEMBER, bad, PURPOSE)
            self.assertEqual(self.reason_of(env), REASON_INVALID_AMOUNT,
                             f"amount={bad!r}")

    # -- granted taps: receipted through the single commit path --------------
    def test_granted_tap_receipt(self):
        tp = self.tapper()
        env = tp.request_tap(MEMBER, 40, PURPOSE)
        self.assertTrue(verify_commit(env),
                        "tap receipt must verify against testnet keys")
        receipt = env["receipt"]
        self.assertEqual(receipt["outcome"], "GRANTED")
        self.assertEqual(receipt["type"], "TAP_OUTFLOW")
        self.assertEqual(receipt["season_id"], "2026-tapping")
        self.assertEqual(receipt["purpose"], PURPOSE)
        self.assertEqual(receipt["provenance"], "DERIVED")
        # Reason chain carried on the receipt.
        self.assertTrue(len(receipt["reason_chain"]) >= 4)
        # Healing accounting: outflow vs replenishment, on the receipt.
        healing = receipt["healing"]
        self.assertEqual(healing["season_outflow_before"], 0)
        self.assertEqual(healing["season_outflow_after"], 40)
        self.assertEqual(healing["season_replenishment"], 1000)
        self.assertEqual(healing["per_member_season_cap"],
                         TAP_RATE_PER_MEMBER_SEASON)
        self.assertEqual(healing["per_tap_limit"], MAX_PER_TAP)
        # Refusal receipts verify too: a signed refusal is honest proof.
        refused = tp.request_tap(MEMBER, MAX_PER_TAP + 1, PURPOSE)
        self.assertTrue(verify_commit(refused))

    def test_cumulative_state_advances(self):
        tp = self.tapper()
        tp.request_tap(MEMBER, 30, PURPOSE)
        env = tp.request_tap(MEMBER, 20, PURPOSE)
        healing = env["receipt"]["healing"]
        self.assertEqual(healing["season_outflow_before"], 30)
        self.assertEqual(healing["season_outflow_after"], 50)
        self.assertEqual(healing["member_season_outflow_after"], 50)
        # State survives a fresh Tapper on the same dir.
        tp2 = self.tapper()
        env3 = tp2.request_tap(MEMBER2, 10, PURPOSE)
        self.assertEqual(
            env3["receipt"]["healing"]["season_outflow_after"], 60)

    # -- regression: the rest of the DCLM core stays green -------------------
    def _run_suite(self, suite):
        """Run a sibling suite in a child interpreter that seeds stdlib
        `tokenize` before the dclm dir shadows it (see the module-top
        guard). Each suite runs isolated in its own process."""
        runner = (
            "import sys, runpy\n"
            f"sys.path.insert(0, {str(_HERE)!r})\n"
            "import tokenize\n"
            "try:\n"
            f"    runpy.run_path({os.path.join(_HERE, suite)!r}, "
            "run_name='__main__')\n"
            "except SystemExit as e:\n"
            "    sys.exit(e.code if isinstance(e.code, int) else 1)\n"
        )
        return subprocess.run(
            [sys.executable, "-c", runner],
            cwd="/tmp", capture_output=True, text=True, timeout=300,
        )

    def test_core_suites_still_pass(self):
        for suite in ("test_meter.py", "test_rights_writes.py",
                      "test_compute.py", "test_data.py"):
            proc = self._run_suite(suite)
            self.assertEqual(proc.returncode, 0,
                             msg=f"{suite} failed:\n{proc.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

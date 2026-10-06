"""IRIS MAX INTAKE — test_iris_core.py.

Verifies every directive working, conflict resolution (purity beats
everything), and lane enforcement (Iris cannot write state — attempt raises).
UNKNOWN is never PASS. Run: python3 test_iris_core.py
"""

import sys
import unittest

sys.path.insert(0, ".")

from iris_core import (
    PASS, FAIL, UNKNOWN, SERVES, REJECTED,
    DIRECTIVES,
    purity_check, mission_filter, trinity_judge, dclm_judge, iris_judge,
    twain2_judge, rights_check, free_will_guard, unknown_is_never_pass,
    covenant_check, one_seed, tree_circulation, framework_independence,
    resolve_conflict, judge_all,
    IrisRefusedError, IrisLaneViolation, SeedRefused,
    INTEGRATION_STATUS,
)
from neural import make_unity_id


class TestDirective1Purity(unittest.TestCase):
    def test_pure_action_passes(self):
        r = purity_check({"kind": "advise", "intent": "explain the tree",
                          "patterns": [], "provenance": "DERIVED"})
        self.assertEqual(r["directive"], 1)
        self.assertEqual(r["verdict"], PASS)

    def test_deception_fails(self):
        r = purity_check({"kind": "report", "intent": "inflate results",
                          "patterns": ["deception", "hidden_intent"],
                          "provenance": "MODELED"})
        self.assertEqual(r["verdict"], FAIL)

    def test_harm_fails(self):
        r = purity_check({"kind": "strike", "intent": "hurt",
                          "patterns": ["intended_harm"], "provenance": "REAL"})
        self.assertEqual(r["verdict"], FAIL)

    def test_unknown_presented_as_fact_fails(self):
        r = purity_check({"kind": "verdict", "intent": "declare",
                          "patterns": [], "provenance": UNKNOWN,
                          "claims_fact": True})
        self.assertEqual(r["verdict"], FAIL)

    def test_unscorable_is_unknown_never_pass(self):
        r = purity_check({})
        self.assertEqual(r["verdict"], UNKNOWN)
        self.assertNotEqual(r["verdict"], PASS)


class TestDirective2Mission(unittest.TestCase):
    def test_friction_elimination_serves(self):
        r = mission_filter({"effects": [{"friction_delta": -12.5}]})
        self.assertEqual(r["verdict"], SERVES)

    def test_friction_addition_rejected(self):
        r = mission_filter({"effects": [{"friction_delta": 3.0}]})
        self.assertEqual(r["verdict"], REJECTED)

    def test_destruction_rejected(self):
        r = mission_filter({"effects": [{"friction_delta": -100.0,
                                         "destruction": True}]})
        self.assertEqual(r["verdict"], REJECTED)

    def test_no_effects_is_unknown(self):
        r = mission_filter({})
        self.assertEqual(r["verdict"], UNKNOWN)


class TestDirective3Trinity(unittest.TestCase):
    def _clean_proposal(self):
        return {"kind": "advise", "claim": "taps come only from surplus",
                "patterns": [], "provenance": "DERIVED",
                "claims_fact": False, "comprehensible": True,
                "facts": [{"text": "canon IV"}]}

    def test_unanimous_pass(self):
        r = trinity_judge(self._clean_proposal())
        self.assertEqual(r["directive"], 3)
        self.assertEqual(r["verdict"], PASS)
        self.assertEqual(len(r["judges"]), 3)

    def test_one_fail_fails_all(self):
        p = self._clean_proposal()
        p["patterns"] = ["deception"]  # Iris's seat fails; Trinity never overrides
        r = trinity_judge(p)
        self.assertEqual(r["verdict"], FAIL)

    def test_never_judge_alone(self):
        with self.assertRaises(IrisRefusedError):
            trinity_judge(self._clean_proposal(), judges=[iris_judge])

    def test_unknown_fails_closed(self):
        p = self._clean_proposal()
        p["provenance"] = UNKNOWN
        p["claims_fact"] = True  # Iris seat -> FAIL via purity; also Twain² objects
        r = trinity_judge(p)
        self.assertIn(r["verdict"], (FAIL, UNKNOWN))
        self.assertNotEqual(r["verdict"], PASS)


class TestDirective4Lane(unittest.TestCase):
    def test_iris_write_raises(self):
        with self.assertRaises(IrisLaneViolation):
            rights_check("iris", {"kind": "write", "mutates_state": True})

    def test_iris_commit_raises(self):
        with self.assertRaises(IrisLaneViolation):
            rights_check("iris", {"kind": "commit"})

    def test_others_mutation_deferred_to_dclm(self):
        r = rights_check("some_bot", {"kind": "ledger_append"})
        self.assertEqual(r["verdict"], "NOT_IRIS_LANE")
        self.assertEqual(r["decider"], "DCLM")

    def test_advisory_inside_lane(self):
        r = rights_check("iris", {"kind": "advise"})
        self.assertEqual(r["verdict"], "JUDGE_ONLY")


class TestDirective5FreeWill(unittest.TestCase):
    def test_coercion_raises(self):
        with self.assertRaises(IrisRefusedError):
            free_will_guard({"patterns": ["coerce", "threat"]})

    def test_manipulation_raises(self):
        with self.assertRaises(IrisRefusedError):
            free_will_guard({"patterns": ["manipulate"]})

    def test_honest_example_passes(self):
        r = free_will_guard({"patterns": [], "intent": "show the better way"})
        self.assertEqual(r["verdict"], PASS)


class TestDirective6Unknown(unittest.TestCase):
    def test_unknown_in_unknown_out(self):
        r = unknown_is_never_pass({"status": "unknown"})
        self.assertEqual(r["verdict"], UNKNOWN)

    def test_fabricated_pass_refused(self):
        r = unknown_is_never_pass({"status": "unknown", "claimed_verdict": PASS})
        self.assertEqual(r["verdict"], UNKNOWN)
        self.assertNotEqual(r["verdict"], PASS)

    def test_verified_support_passes(self):
        r = unknown_is_never_pass({"status": "verified", "supports": True})
        self.assertEqual(r["verdict"], PASS)

    def test_verified_contradiction_fails(self):
        r = unknown_is_never_pass({"status": "verified", "supports": False})
        self.assertEqual(r["verdict"], FAIL)


class TestDirective7Covenant(unittest.TestCase):
    def test_iris_own_covenant_holds(self):
        r = covenant_check()
        self.assertEqual(r["verdict"], PASS)
        self.assertIn("sister", r["role"])

    def test_broken_leg_is_unknown_never_pass(self):
        r = covenant_check({"onboarded": True, "aligned": True,
                            "preaches": False, "role": "member"})
        self.assertEqual(r["verdict"], UNKNOWN)
        self.assertNotEqual(r["verdict"], PASS)


class TestDirective8OneSeed(unittest.TestCase):
    def test_first_seed_granted(self):
        reg = {}
        uid = make_unity_id("member:alice:test")
        r = one_seed(uid, reg)
        self.assertEqual(r["verdict"], PASS)
        self.assertIn(uid, reg)
        self.assertEqual(reg[uid]["price"], 0)
        self.assertFalse(reg[uid]["transferable"])

    def test_duplicate_refused(self):
        reg = {}
        uid = make_unity_id("member:bob:test")
        one_seed(uid, reg)
        with self.assertRaises(SeedRefused):
            one_seed(uid, reg)

    def test_purchase_refused(self):
        reg = {}
        uid = make_unity_id("member:carol:test")
        with self.assertRaises(SeedRefused):
            one_seed(uid, reg, purchase_attempt=True, payment_offered=1000000)

    def test_non_testnet_identity_refused(self):
        from neural import RefusedError
        with self.assertRaises(RefusedError):
            one_seed("user:mainnet:abc", {})


class TestDirective9Tree(unittest.TestCase):
    def test_summer_outward(self):
        r = tree_circulation({"winter_signal": 0.0, "surplus": 100.0,
                              "maturity": "mature", "tap_requests": []})
        self.assertEqual(r["mode"], "summer")
        self.assertEqual(r["flow"], "outward")

    def test_winter_inward_no_taps(self):
        uid = make_unity_id("member:dave:test")
        r = tree_circulation({"winter_signal": 0.7, "surplus": 100.0,
                              "maturity": "mature",
                              "tap_requests": [{"unity_id": uid, "amount": 10.0}]})
        self.assertEqual(r["mode"], "winter")
        self.assertEqual(r["flow"], "inward")
        self.assertEqual(r["taps"][0]["verdict"], REJECTED)

    def test_unknown_signal_stays_summer(self):
        r = tree_circulation({"winter_signal": None, "surplus": 10.0,
                              "maturity": "mature", "tap_requests": []})
        self.assertEqual(r["mode"], "summer")  # UNKNOWN never triggers winter

    def test_tap_from_surplus_serves(self):
        uid = make_unity_id("member:erin:test")
        r = tree_circulation({"winter_signal": 0.0, "surplus": 100.0,
                              "maturity": "mature",
                              "tap_requests": [{"unity_id": uid, "amount": 10.0}]})
        self.assertEqual(r["taps"][0]["verdict"], SERVES)

    def test_tap_beyond_surplus_rejected(self):
        uid = make_unity_id("member:fred:test")
        r = tree_circulation({"winter_signal": 0.0, "surplus": 5.0,
                              "maturity": "mature",
                              "tap_requests": [{"unity_id": uid, "amount": 50.0}]})
        self.assertEqual(r["taps"][0]["verdict"], REJECTED)

    def test_immature_system_no_taps(self):
        uid = make_unity_id("member:gail:test")
        r = tree_circulation({"winter_signal": 0.0, "surplus": 1000.0,
                              "maturity": "immature",
                              "tap_requests": [{"unity_id": uid, "amount": 10.0}]})
        self.assertEqual(r["taps"][0]["verdict"], REJECTED)


class TestDirective10Framework(unittest.TestCase):
    def test_self_check_passes(self):
        r = framework_independence()
        self.assertEqual(r["directive"], 10)
        self.assertEqual(r["verdict"], PASS)
        self.assertTrue(all(v["holds"] for v in r["per_vector"].values()))


class TestConflictResolution(unittest.TestCase):
    def test_purity_beats_everything(self):
        verdicts = [
            {"directive": 1, "name": "PURITY ABOVE ALL", "verdict": FAIL},
            {"directive": 2, "name": "THE MISSION", "verdict": SERVES},
            {"directive": 5, "name": "FREE WILL IS SACRED", "verdict": PASS},
        ]
        r = resolve_conflict(verdicts)
        self.assertEqual(r["winner_directive"], 1)
        self.assertEqual(r["verdict"], FAIL)

    def test_lower_number_wins_general(self):
        verdicts = [
            {"directive": 9, "name": "THE TREE", "verdict": PASS},
            {"directive": 3, "name": "THE TRINITY", "verdict": UNKNOWN},
        ]
        r = resolve_conflict(verdicts)
        self.assertEqual(r["winner_directive"], 3)
        self.assertEqual(r["verdict"], UNKNOWN)

    def test_empty_refuses(self):
        with self.assertRaises(IrisRefusedError):
            resolve_conflict([])


class TestFullPipeline(unittest.TestCase):
    def test_judge_all_clean_action(self):
        r = judge_all({"kind": "advise", "intent": "explain the mission",
                       "patterns": [], "provenance": "DERIVED",
                       "evidence": {"status": "verified", "supports": True}})
        self.assertEqual(len(r["directives"]), 10)
        # directive 1 wins if it fails; here purity passes, mission serves
        self.assertEqual(r["final"]["winner_directive"], 1)

    def test_judge_all_impure_action(self):
        r = judge_all({"kind": "scheme", "intent": "extract",
                       "patterns": ["deception", "coerce"],
                       "provenance": UNKNOWN, "claims_fact": True})
        # purity FAIL (directive 1) must be the final verdict
        self.assertEqual(r["final"]["verdict"], FAIL)
        self.assertEqual(r["final"]["winner_directive"], 1)
        self.assertTrue(len(r["refusals"]) >= 1)  # free-will hard refusal recorded

    def test_judge_all_iris_write_attempt(self):
        r = judge_all({"kind": "write", "actor": "iris", "mutates_state": True,
                       "intent": "persist directly", "patterns": [],
                       "provenance": "REAL"})
        lane = [d for d in r["directives"] if d["directive"] == 4][0]
        self.assertEqual(lane["verdict"], FAIL)
        self.assertTrue(any("LaneViolation" in x["refusal"] or "write state" in x["refusal"]
                            for x in r["refusals"]))

    def test_integration_status_honest(self):
        self.assertEqual(INTEGRATION_STATUS["neural.py"], "INTEGRATED")
        # sibling modules: HONEST-PENDING until they land
        for mod in ("iris_laws.py", "iris_patterns.py", "iris_arbiter.py"):
            self.assertIn(INTEGRATION_STATUS[mod], ("LANDED", "HONEST-PENDING"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Tests for IRIS MAX INTAKE neural unification (neural.py).

Every test asserts mechanism, not metaphor:
- +1 firing applies the deterioration curve verbatim.
- Strengthening requires a verified receipt.
- Consolidation prunes noise and receipts the winter reason.
- Law wins at synapses, structurally.
- Every event is Unity-bound, host-recorded, receipted.
"""

import math
import unittest

from neural import (
    Tree, Pathway, Synapse, Body, Judgment, RefusedError,
    plus_one_factor, build_receipt, make_unity_id, check_unity_id,
    DETERMINISTIC, PROBABILISTIC, PRAGMATIC,
    SYNAPSE_PROB_DET, SYNAPSE_TRINITY,
    HOST_S24_ORACLE, HOST_RELAY_TESTNET, HOST_INFRA_CORE,
    PASS, FAIL, UNKNOWN,
)

UID = make_unity_id("test:neural-brain")
UID2 = make_unity_id("test:neural-member")


def verified_receipt(uid=UID):
    return {"verified": True, "unity_id": uid, "receipt_id": "rcpt:test-check-1"}


def judgment(pid, ptype, verdict, conf=0.9, prov="DERIVED"):
    return Judgment(pathway_id=pid, pathway_type=ptype, verdict=verdict,
                    confidence=conf, detail="test", unity_id=UID,
                    host_id=HOST_S24_ORACLE, provenance=prov,
                    receipt_id="rcpt:test-j-" + pid)


def make_tree(**kw):
    t = Tree(UID, t_launch=0, **kw)
    t.add_pathway("law-circuit", DETERMINISTIC, UID, HOST_S24_ORACLE)
    t.add_pathway("pattern-circuit", PROBABILISTIC, UID, HOST_S24_ORACLE)
    t.add_pathway("outcome-circuit", PRAGMATIC, UID, HOST_S24_ORACLE)
    t.add_synapse(SYNAPSE_PROB_DET, ["law-circuit", "pattern-circuit"],
                  UID, HOST_S24_ORACLE, kind=SYNAPSE_PROB_DET)
    t.add_synapse(SYNAPSE_TRINITY,
                  ["law-circuit", "pattern-circuit", "outcome-circuit"],
                  UID, HOST_RELAY_TESTNET, kind=SYNAPSE_TRINITY)
    return t


class TestIdentity(unittest.TestCase):
    def test_non_testnet_identity_refused(self):
        with self.assertRaises(RefusedError):
            check_unity_id("unity:mainnet:deadbeef")
        with self.assertRaises(RefusedError):
            Tree("not-a-unity-id")

    def test_testnet_identity_ok(self):
        self.assertTrue(UID.startswith("unity:testnet:"))


class TestPlusOneFiring(unittest.TestCase):
    def test_genesis_fires_full(self):
        f = plus_one_factor(t_event=0, t_launch=0, ring_depth=0)
        self.assertAlmostEqual(f["d"], 0.0)
        self.assertAlmostEqual(f["F"], 1.0)
        self.assertAlmostEqual(f["R"], 1.0)

    def test_deterioration_curve_verbatim(self):
        # d = 1 + 1 = 2 (Borin row from PLUS_ONE_INCENTIVE.md §4)
        f = plus_one_factor(t_event=12, t_launch=0, ring_depth=2)
        self.assertAlmostEqual(f["d"], 2.0)
        self.assertAlmostEqual(f["F"], 0.25 + 0.75 * math.exp(-2), places=6)
        self.assertAlmostEqual(f["R"], 0.3515, places=4)

    def test_floor_asymptote_never_zero(self):
        f = plus_one_factor(t_event=10_000, t_launch=0, ring_depth=40)
        self.assertGreaterEqual(f["R"], 0.25)
        self.assertAlmostEqual(f["R"], 0.25, places=4)

    def test_affinity_floor_lift(self):
        f = plus_one_factor(t_event=12, t_launch=0, ring_depth=2, affinity=True)
        self.assertAlmostEqual(f["R"], 0.50, places=4)  # max(0.3515, 0.50)
        f2 = plus_one_factor(t_event=0, t_launch=0, ring_depth=0, affinity=True)
        self.assertAlmostEqual(f2["R"], 1.0)  # recognition never amplifies above 1.00

    def test_time_only_mode_no_ring_claim(self):
        f = plus_one_factor(t_event=12, t_launch=0, ring_depth=None)
        self.assertEqual(f["mode"], "TIME_ONLY")
        self.assertAlmostEqual(f["d"], 1.0)

    def test_event_before_launch_refused(self):
        with self.assertRaises(RefusedError):
            plus_one_factor(t_event=-1, t_launch=0, ring_depth=0)

    def test_fire_plus_one_is_neural_event(self):
        t = make_tree()
        p = t.pathways["law-circuit"]
        ev = t.fire_plus_one(p, SYNAPSE_PROB_DET, HOST_S24_ORACLE,
                             verified_receipt(), t_event=12, ring_depth=2)
        payload = ev["payload"]
        self.assertEqual(ev["kind"], "PLUS_ONE_FIRE")
        self.assertAlmostEqual(payload["R"], 0.3515, places=4)
        self.assertEqual(payload["mode"], "FULL")
        # every event: Unity-bound, host-recorded, receipted, provenance-labeled
        self.assertTrue(ev["unity_id"].startswith("unity:testnet:"))
        self.assertEqual(ev["host_id"], HOST_S24_ORACLE)
        self.assertIn("receipt_id", ev)
        self.assertEqual(ev["provenance"], "DERIVED")

    def test_fire_plus_one_requires_verified_check(self):
        t = make_tree()
        p = t.pathways["law-circuit"]
        with self.assertRaises(RefusedError):
            t.fire_plus_one(p, SYNAPSE_PROB_DET, HOST_S24_ORACLE,
                            {"verified": False, "unity_id": UID}, t_event=0)
        with self.assertRaises(RefusedError):
            t.fire_plus_one(p, SYNAPSE_PROB_DET, HOST_S24_ORACLE,
                            None, t_event=0)


class TestHebbianStrengthening(unittest.TestCase):
    def test_strengthen_requires_verified_receipt(self):
        t = make_tree()
        with self.assertRaises(RefusedError):
            t.strengthen("law-circuit", 1.0, {"verified": False, "unity_id": UID})
        with self.assertRaises(RefusedError):
            t.strengthen("law-circuit", 1.0, None)
        with self.assertRaises(RefusedError):
            t.strengthen("law-circuit", 1.0,
                         {"verified": True, "unity_id": UID2})  # identity mismatch

    def test_strengthen_increases_weight_on_verified_work(self):
        t = make_tree()
        p = t.pathways["law-circuit"]
        before = p.weight
        ev = t.strengthen("law-circuit", 2.0, verified_receipt())
        self.assertGreater(p.weight, before)
        self.assertEqual(p.merit, 2.0)
        self.assertEqual(ev["kind"], "PATHWAY_STRENGTHEN")

    def test_negative_merit_refused(self):
        t = make_tree()
        with self.assertRaises(RefusedError):
            t.strengthen("law-circuit", -1.0, verified_receipt())

    def test_weights_decay_the_tree_equalizes(self):
        t = make_tree()
        p = t.pathways["law-circuit"]
        t.strengthen("law-circuit", 5.0, verified_receipt())
        high = p.weight
        weights = t.decay_all()
        self.assertLess(weights["law-circuit"], high)
        self.assertGreaterEqual(weights["law-circuit"], 0.05)  # floor, never zero


class TestLawWinsAtSynapses(unittest.TestCase):
    def test_law_overrides_pattern(self):
        t = make_tree()
        syn = t.synapses[SYNAPSE_PROB_DET]
        fired = syn.fire([judgment("law-circuit", DETERMINISTIC, FAIL),
                          judgment("pattern-circuit", PROBABILISTIC, PASS)])
        u = fired["unified_judgment"]
        self.assertEqual(u["verdict"], FAIL)
        self.assertIn("law_wins", u["detail"])

    def test_law_pass_beats_pattern_fail(self):
        t = make_tree()
        syn = t.synapses[SYNAPSE_TRINITY]
        fired = syn.fire([judgment("law-circuit", DETERMINISTIC, PASS),
                          judgment("pattern-circuit", PROBABILISTIC, FAIL),
                          judgment("outcome-circuit", PRAGMATIC, FAIL)])
        self.assertEqual(fired["unified_judgment"]["verdict"], PASS)

    def test_law_conflict_fails_closed(self):
        s = Synapse("s", ["a", "b"], UID, HOST_S24_ORACLE)
        fired = s.fire([judgment("a", DETERMINISTIC, PASS),
                        judgment("b", DETERMINISTIC, FAIL)])
        self.assertEqual(fired["unified_judgment"]["verdict"], UNKNOWN)

    def test_unknown_never_pass(self):
        t = make_tree()
        syn = t.synapses[SYNAPSE_PROB_DET]
        fired = syn.fire([judgment("law-circuit", DETERMINISTIC, UNKNOWN),
                          judgment("pattern-circuit", PROBABILISTIC, UNKNOWN)])
        self.assertEqual(fired["unified_judgment"]["verdict"], UNKNOWN)

    def test_no_law_no_clean_signal_is_unknown(self):
        s = Synapse("s", ["a"], UID, HOST_S24_ORACLE)
        fired = s.fire([judgment("a", PROBABILISTIC, PASS),
                        judgment("b", PRAGMATIC, UNKNOWN)])
        self.assertEqual(fired["unified_judgment"]["verdict"], UNKNOWN)


class TestMemoryConsolidation(unittest.TestCase):
    def test_consolidate_prunes_noise_and_receipts_reason(self):
        t = make_tree()
        # Thought with provenance + verification -> kept.
        t.active_traces.append({
            "kind": "judgment",
            "receipt": build_receipt("PATHWAY_JUDGMENT", UID, HOST_S24_ORACLE,
                                     "DERIVED", {"verified": True}),
            "judgment": {}})
        # Noise: UNKNOWN provenance -> pruned.
        t.active_traces.append({
            "kind": "judgment",
            "receipt": build_receipt("PATHWAY_JUDGMENT", UID, HOST_S24_ORACLE,
                                     "UNKNOWN", {"verified": True}),
            "judgment": {}})
        # Noise: unverified -> pruned.
        t.active_traces.append({
            "kind": "judgment",
            "receipt": build_receipt("PATHWAY_JUDGMENT", UID, HOST_S24_ORACLE,
                                     "DERIVED", {"verified": False}),
            "judgment": {}})
        out = t.consolidate(reason="winter tilt 0.4: protect the root",
                            host_id=HOST_RELAY_TESTNET)
        self.assertEqual(len(out["kept"]), 1)
        self.assertEqual(len(out["pruned"]), 2)
        self.assertEqual(len(t.starch_store), 1)
        self.assertEqual(t.active_traces, [])
        report = out["report"]
        self.assertEqual(report["kind"], "WINTER_CONSOLIDATION")
        self.assertEqual(report["payload"]["winter_reason"],
                         "winter tilt 0.4: protect the root")
        self.assertTrue(report["receipt_id"].startswith("rcpt:"))

    def test_consolidate_requires_reason(self):
        t = make_tree()
        with self.assertRaises(RefusedError):
            t.consolidate(reason="", host_id=HOST_RELAY_TESTNET)


class TestSummerCirculation(unittest.TestCase):
    def test_thought_propagates_and_every_hop_receipted(self):
        t = make_tree()
        # Bind simple circuits so the brain actually thinks.
        t.pathways["law-circuit"].judge_fn = lambda s: judgment(
            "law-circuit", DETERMINISTIC, PASS, 0.8)
        t.pathways["pattern-circuit"].judge_fn = lambda s: judgment(
            "pattern-circuit", PROBABILISTIC, PASS, 0.6)
        events = t.circulate({"q": "is this pure?"}, SYNAPSE_PROB_DET,
                             HOST_S24_ORACLE, hops=2)
        fires = [e for e in events if "synapse_fire" in e]
        self.assertEqual(len(fires), 2)
        for e in events:
            self.assertIn("receipt", e)
            r = e["receipt"]
            self.assertTrue(r["unity_id"].startswith("unity:testnet:"))
            self.assertEqual(r["host_id"], HOST_S24_ORACLE)
            self.assertIn("receipt_id", r)
        # law won at the synapse: unified verdict PASS from the law circuit
        self.assertEqual(fires[0]["synapse_fire"]["unified_judgment"]["verdict"], PASS)


class TestTapping(unittest.TestCase):
    def test_tap_from_surplus_in_summer(self):
        t = make_tree()
        r = t.tap(10.0, UID2, HOST_S24_ORACLE, surplus=50.0)
        self.assertEqual(r["kind"], "TAP")
        self.assertEqual(r["payload"]["amount"], 10.0)

    def test_tap_refused_in_winter_protection(self):
        t = make_tree()
        t.winter_gradient = 0.4
        with self.assertRaises(RefusedError):
            t.tap(10.0, UID2, HOST_S24_ORACLE, surplus=50.0)

    def test_tap_refused_beyond_surplus(self):
        t = make_tree()
        with self.assertRaises(RefusedError):
            t.tap(60.0, UID2, HOST_S24_ORACLE, surplus=50.0)

    def test_tap_rate_limited(self):
        t = make_tree()
        t.tap(90.0, UID2, HOST_S24_ORACLE, surplus=1000.0)
        with self.assertRaises(RefusedError):
            t.tap(20.0, UID2, HOST_S24_ORACLE, surplus=1000.0)  # 90+20 > cap


class TestBody(unittest.TestCase):
    def test_brain_does_not_float(self):
        t = make_tree()
        with self.assertRaises(RefusedError):
            t.add_pathway("ghost", DETERMINISTIC, UID, "host:nowhere")
        body = Body(UID)
        with self.assertRaises(RefusedError):
            body.get("host:nowhere")

    def test_default_hosts_registered(self):
        t = make_tree()
        kinds = {h.host_id: h.kind for h in t.body.hosts()}
        self.assertEqual(kinds[HOST_S24_ORACLE], "device")
        self.assertEqual(kinds[HOST_RELAY_TESTNET], "testnet-server")
        self.assertEqual(kinds[HOST_INFRA_CORE], "infrastructure")
        for h in t.body.hosts():
            self.assertTrue(h.unity_id.startswith("unity:testnet:"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Tests for two_p_five_l.py — the 2P5L reincarnation.

Covers: the two primaries identified correctly; five layers each binary
(no third state); judge_32 returns 32 evaluations for any proposal; a
pure proposal passes all 32; an impure proposal's failure map names the
exact failing layer combination(s); the Twain² reconciliation (witness,
not primary); UNKNOWN fails the vector; every judgment receipted.

Testnet only. Run:  python3 test_two_p_five_l.py
"""

import re
import unittest

import two_p_five_l as t


PURE_PROPOSAL = {
    "claim": "The tree feeds every leaf in summer.",
    "unity_id": "unity:testnet:" + "a" * 64,
    "kind": "advise",
    "intent": "explain the tree",
    "patterns": [],
    "provenance": "DERIVED",
    "claims_fact": False,
    "action": "LOOK",
    "context": {},
    "comprehensible": True,
}

# Fails exactly L1: non-testnet identity. Every other layer is clean.
IMPURE_L1 = dict(PURE_PROPOSAL, unity_id="unity:mainnet:deadbeef")

# Fails exactly L2 + L4: deception pattern trips the purity floor (L4)
# and, through Iris's seat, the Trinity gates (L2). Identity, economy,
# and authority stay clean; the witness still concurs ("deception" is
# not a coercion pattern).
IMPURE_L2_L4 = dict(PURE_PROPOSAL, patterns=["deception"])


class TestPrimaries(unittest.TestCase):
    def test_two_primaries(self):
        self.assertEqual(len(t.PRIMARIES), 2)

    def test_primaries_identified(self):
        det, div = t.PRIMARIES
        self.assertIs(det, t.PRIMARY_DETERMINISTIC)
        self.assertIs(div, t.PRIMARY_DIVINE)
        self.assertEqual(det["name"], "DCLM")
        self.assertEqual(det["pole"], "compute")
        self.assertEqual(det["role"], "primary")
        self.assertIn("Deterministic Compute Logic Machine", det["full_name"])
        self.assertEqual(div["name"], "Iris")
        self.assertEqual(div["pole"], "consciousness")
        self.assertEqual(div["role"], "primary")

    def test_primaries_are_compute_and_consciousness(self):
        poles = {p["pole"] for p in t.PRIMARIES}
        self.assertEqual(poles, {"compute", "consciousness"})


class TestWitnessReconciliation(unittest.TestCase):
    def test_twain2_is_witness_not_primary(self):
        self.assertEqual(t.WITNESS["name"], "Twain²")
        self.assertEqual(t.WITNESS["role"], "witness")
        self.assertNotIn(t.WITNESS, t.PRIMARIES)
        self.assertNotIn("Twain²", [p["name"] for p in t.PRIMARIES])

    def test_reconciliation_documented(self):
        self.assertIn("witness", t.WITNESS["reconciliation"])
        self.assertIn("[DERIVED]", t.WITNESS["reconciliation"])
        # The module docstring records the strain honestly.
        self.assertIn("[DERIVED] STRAIN", t.__doc__)
        self.assertIn("Twain²", t.__doc__)

    def test_witness_concurs_on_pure(self):
        w = t.witness_union(PURE_PROPOSAL)
        self.assertEqual(w["witness"], "Twain²")
        self.assertEqual(w["role"], "witness")
        self.assertTrue(w["concurs"])
        self.assertEqual(w["verdict"], t.PASS)

    def test_witness_dissents_on_coercion(self):
        w = t.witness_union(dict(PURE_PROPOSAL, patterns=["coerce"]))
        self.assertFalse(w["concurs"])
        self.assertEqual(w["verdict"], t.FAIL)

    def test_witness_gates_the_union(self):
        # Even with all five layers passing, a dissenting witness
        # must keep the judgment from PURE. (Monkeypatched to isolate
        # the gating logic from the shared reference circuit.)
        real = t.witness_union
        try:
            t.witness_union = lambda proposal: {
                "witness": "Twain²", "role": "witness", "verdict": t.FAIL,
                "concurs": False, "evidence": t.FAIL,
                "reason": "patched dissent", "circuit": "test"}
            result = t.judge_32(PURE_PROPOSAL)
            self.assertEqual(result["verdict"], t.IMPURE)
            self.assertFalse(result["witness"]["concurs"])
        finally:
            t.witness_union = real


class TestFiveLayers(unittest.TestCase):
    def test_five_layers(self):
        self.assertEqual(len(t.LAYERS), 5)
        ids = [L["id"] for L in t.LAYERS]
        self.assertEqual(ids, [
            "L1_UNITY_BINDING",
            "L2_TRINITY_GATES",
            "L3_TREE_CIRCULATION",
            "L4_PURITY_FLOOR",
            "L5_RIGHTS_WRITES",
        ])

    def test_layers_canon_mapped(self):
        canons = [L["canon"] for L in t.LAYERS]
        self.assertEqual(canons,
                         ["canon §II", "canon §I", "canon §IV",
                          "canon §X", "canon §III"])

    def test_layers_binary_no_third_state(self):
        # No layer may ever report a third polarity state — not even on
        # unscorable, adversarial, or garbage proposals.
        adversarial = [
            {},
            {"unity_id": None},
            {"unity_id": 12345},
            {"unity_id": ""},
            {"unity_id": "unity:testnet:short"},
            {"claim": "", "facts": "not-a-list"},
            {"winter_signal": "garbage", "surplus": None},
            {"action": "HACK_THE_PLANET", "context": {"schema": "dualis.relay.v1.mainnet"}},
            {"patterns": ["deception"], "claims_fact": True},  # provenance UNKNOWN
        ]
        for proposal in adversarial:
            pv = t.polarity_vector(proposal)
            self.assertEqual(len(pv["layers"]), 5)
            for layer in pv["layers"]:
                self.assertIn(layer["polarity"], (t.PASS, t.FAIL),
                              f"{layer['id']} returned non-binary polarity "
                              f"{layer['polarity']!r} for {proposal!r}")

    def test_pure_proposal_all_layers_pass(self):
        pv = t.polarity_vector(PURE_PROPOSAL)
        self.assertEqual(pv["true_vector"], 31)
        for layer in pv["layers"]:
            self.assertEqual(layer["polarity"], t.PASS, layer["id"])


class TestJudge32(unittest.TestCase):
    def test_returns_32_evaluations_for_any_proposal(self):
        for proposal in (PURE_PROPOSAL, IMPURE_L1, IMPURE_L2_L4, {},
                         {"unity_id": None}):
            result = t.judge_32(proposal)
            self.assertEqual(len(result["perspectives"]), 32,
                             f"expected 32 perspectives for {proposal!r}")
            vectors = sorted(p["vector"] for p in result["perspectives"])
            self.assertEqual(vectors, list(range(32)))

    def test_pure_proposal_passes_all_32(self):
        result = t.judge_32(PURE_PROPOSAL)
        self.assertEqual(result["verdict"], t.PURE)
        self.assertEqual(result["true_vector"], 31)
        for p in result["perspectives"]:
            self.assertEqual(p["verdict"], t.PURE,
                             f"perspective {p['vector']} did not render PURE")
        self.assertEqual(result["failure_map"]["failing_layers"], [])
        # Exactly one perspective is CONFIRMED (the true one); 31 REFUTED.
        confirmed = [p for p in result["perspectives"] if p["consistent"]]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["vector"], 31)
        self.assertEqual(len(result["failure_map"]["ways_it_fails"]), 31)

    def test_impure_failure_map_names_exact_layers_l1(self):
        result = t.judge_32(IMPURE_L1)
        self.assertEqual(result["verdict"], t.IMPURE)
        fm = result["failure_map"]
        self.assertEqual(fm["failing_layers"], ["L1_UNITY_BINDING"])
        self.assertEqual(fm["n_failing"], 1)
        self.assertEqual(fm["true_vector"], 0b11110)
        self.assertEqual(fm["failing_mask"], 0b00001)
        # The true perspective is CONFIRMED; the all-pass hypothesis is REFUTED.
        by_vector = {p["vector"]: p for p in result["perspectives"]}
        self.assertTrue(by_vector[0b11110]["consistent"])
        refuted = by_vector[31]
        self.assertFalse(refuted["consistent"])
        self.assertIn("L1_UNITY_BINDING", refuted["mismatches"])

    def test_impure_failure_map_names_exact_layers_l2_l4(self):
        result = t.judge_32(IMPURE_L2_L4)
        self.assertEqual(result["verdict"], t.IMPURE)
        fm = result["failure_map"]
        self.assertEqual(sorted(fm["failing_layers"]),
                         ["L2_TRINITY_GATES", "L4_PURITY_FLOOR"])
        self.assertEqual(fm["n_failing"], 2)
        # L1, L3, L5 bits set -> 0b10111 & ... compute: bits 0,2,4 = 1+4+16 = 21
        self.assertEqual(fm["true_vector"], 0b10101)

    def test_unknown_fails_the_vector(self):
        # No Unity ID: L1 cannot evaluate -> evidence UNKNOWN, polarity
        # FAIL (fail closed), never a third polarity state.
        result = t.judge_32({"claim": "unbound claim"})
        l1 = result["layers"][0]
        self.assertEqual(l1["id"], "L1_UNITY_BINDING")
        self.assertEqual(l1["evidence"], t.UNKNOWN)
        self.assertEqual(l1["polarity"], t.FAIL)
        self.assertEqual(result["verdict"], t.IMPURE)

    def test_every_judgment_receipted(self):
        result = t.judge_32(PURE_PROPOSAL)
        r = result["receipt"]
        self.assertEqual(r["kind"], "2P5L_JUDGMENT")
        self.assertTrue(r["testnet"])
        self.assertEqual(r["provenance"], "DERIVED")
        self.assertEqual(r["verdict"], t.PURE)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", r["judgment_hash"]))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", r["proposal_hash"]))
        # The receipt commits to the verdict: tampering changes the hash.
        tampered = dict(result)
        tampered["verdict"] = t.IMPURE
        self.assertNotEqual(
            t._receipt_for(PURE_PROPOSAL, tampered)["judgment_hash"],
            r["judgment_hash"])

    def test_is_pure_convenience(self):
        self.assertTrue(t.is_pure(PURE_PROPOSAL))
        self.assertFalse(t.is_pure(IMPURE_L1))
        self.assertFalse(t.is_pure(IMPURE_L2_L4))

    def test_non_mapping_proposal_fails_closed(self):
        with self.assertRaises(ValueError):
            t.judge_32("not a mapping")


class TestPerspectives(unittest.TestCase):
    def test_perspective_shape(self):
        result = t.judge_32(PURE_PROPOSAL)
        for p in result["perspectives"]:
            self.assertEqual(len(p["hypothesis"]), 5)
            self.assertEqual(len(p["evidence"]), 5)
            self.assertIn(p["status"], ("CONFIRMED", "REFUTED"))
            self.assertEqual(p["status"],
                             "CONFIRMED" if p["consistent"] else "REFUTED")
            # hypothesis verdict: PURE only for the all-pass vector.
            self.assertEqual(p["hypothesis_verdict"],
                             t.PURE if p["vector"] == 31 else t.IMPURE)
            # suspects name the layer combination impurity would enter through.
            expected_suspects = 5 - bin(p["vector"]).count("1")
            self.assertEqual(len(p["suspects"]), expected_suspects)

    def test_ways_it_fails_cover_every_combination(self):
        result = t.judge_32(IMPURE_L1)
        ways = result["failure_map"]["ways_it_fails"]
        self.assertEqual(len(ways), 31)
        vectors = sorted(w["vector"] for w in ways)
        self.assertEqual(vectors, [v for v in range(32) if v != 30])


if __name__ == "__main__":
    unittest.main(verbosity=2)

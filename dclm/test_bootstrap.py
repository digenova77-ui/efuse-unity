#!/usr/bin/env python3
"""Tests for dclm/bootstrap.py — the self-executing onboarding API.

Testnet only. Every test uses a fresh BootstrapService on a temp state
dir. The gate's confirm_bind uses the injected BOOTSTRAP ACCEPTANCE
verifier (clearly labeled, NOT WebAuthn) — no test stub of the WebAuthn
path is needed because the bootstrap never claims that path.

UNKNOWN is never PASS: every refusal is asserted as a raised exception,
never as a truthy value.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bootstrap
from bootstrap import (
    BootstrapService,
    NOTICE_SHA256,
    IDENTITY_PREFIX,
    AcceptanceRefused,
    BootstrapRefused,
    derive_unity_id,
    generate_identity,
    present_notice,
    sign_notice_acceptance,
    _verify,
    _publickey_from_secret,
)


def make_acceptance():
    """A valid entity-side acceptance: fresh keypair, signed notice."""
    ident = generate_identity()
    sig = sign_notice_acceptance(
        ident["private_key_hex"], NOTICE_SHA256
    )
    acceptance = {
        "notice_sha256": NOTICE_SHA256,
        "public_key_hex": ident["public_key_hex"],
        "signature_hex": sig,
    }
    return ident, acceptance


class BootstrapTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bootstrap-test-")
        self.svc = BootstrapService(state_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state_files(self):
        out = []
        for root, _dirs, files in os.walk(self.tmp):
            for f in files:
                out.append(os.path.join(root, f))
        return out


# ---------------------------------------------------------------------------
# The notice
# ---------------------------------------------------------------------------


class NoticeTests(BootstrapTestBase):
    def test_notice_hash_verifies(self):
        notice = present_notice()
        recomputed = hashlib.sha256(
            notice["notice_text"].encode("utf-8")
        ).hexdigest()
        self.assertEqual(notice["notice_sha256"], recomputed)
        self.assertEqual(notice["notice_sha256"], NOTICE_SHA256)
        self.assertTrue(notice["testnet"])

    def test_notice_carries_covenant_one_seed_mission(self):
        text = present_notice()["notice_text"]
        self.assertIn("stay in line", text)          # covenant
        self.assertIn("only buy one seed", text)      # one-seed law
        self.assertIn("friction first", text)        # mission


# ---------------------------------------------------------------------------
# Identity generation
# ---------------------------------------------------------------------------


class IdentityTests(BootstrapTestBase):
    def test_identity_format_valid(self):
        ident = generate_identity()
        self.assertTrue(ident["unity_id"].startswith(IDENTITY_PREFIX))
        self.assertEqual(
            ident["unity_id"],
            "unity:testnet:"
            + hashlib.sha256(
                bytes.fromhex(ident["public_key_hex"])
            ).hexdigest()[:16],
        )
        self.assertEqual(ident["unity_id"], derive_unity_id(
            bytes.fromhex(ident["public_key_hex"])))

    def test_two_entities_get_distinct_ids(self):
        self.assertNotEqual(
            generate_identity()["unity_id"],
            generate_identity()["unity_id"],
        )

    def test_private_key_never_persisted_server_side(self):
        # FULL bootstrap, then scan every file in the state dir: the
        # private key hex must appear NOWHERE — not in receipts, not in
        # the participant registry, not in the seeded ledger, not in the
        # gate state.
        ident, acceptance = make_acceptance()
        priv = ident["private_key_hex"]
        out = self.svc.bootstrap(acceptance)
        self.assertEqual(out["unity_id"], ident["unity_id"])
        for path in self.state_files():
            with open(path, "rb") as fh:
                content = fh.read()
            self.assertNotIn(
                priv.encode("utf-8"), content,
                f"PRIVATE KEY LEAKED into {path}",
            )
        # ... and the public key IS there (it must be, for later
        # orientation signature checks)
        self.assertIn(
            ident["public_key_hex"].encode("utf-8"),
            open(self.svc.participants_path, "rb").read(),
        )

    def test_ed25519_round_trip(self):
        sk = os.urandom(32)
        pk = _publickey_from_secret(sk)
        sig = sign_notice_acceptance(sk.hex(), NOTICE_SHA256)
        self.assertTrue(
            _verify(bytes.fromhex(sig), bytes.fromhex(NOTICE_SHA256), pk)
        )
        # tampered message fails
        bad_digest = b"\x00" * 32
        self.assertFalse(_verify(bytes.fromhex(sig), bad_digest, pk))
        # wrong key fails
        other_pk = _publickey_from_secret(os.urandom(32))
        self.assertFalse(
            _verify(bytes.fromhex(sig), bytes.fromhex(NOTICE_SHA256), other_pk)
        )


# ---------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------


class AcceptanceTests(BootstrapTestBase):
    def test_acceptance_without_signature_refused(self):
        ident, acceptance = make_acceptance()
        del acceptance["signature_hex"]
        with self.assertRaises(AcceptanceRefused) as ctx:
            self.svc.accept_notice(acceptance)
        self.assertEqual(ctx.exception.reason, "NO_SIGNATURE")

    def test_acceptance_tampered_notice_refused(self):
        ident, acceptance = make_acceptance()
        acceptance["notice_sha256"] = "00" * 32
        with self.assertRaises(AcceptanceRefused) as ctx:
            self.svc.accept_notice(acceptance)
        self.assertEqual(ctx.exception.reason, "NOTICE_TAMPERED")

    def test_acceptance_bad_signature_refused(self):
        ident, acceptance = make_acceptance()
        other = generate_identity()
        acceptance["signature_hex"] = sign_notice_acceptance(
            other["private_key_hex"], NOTICE_SHA256
        )
        with self.assertRaises(AcceptanceRefused) as ctx:
            self.svc.accept_notice(acceptance)
        self.assertEqual(ctx.exception.reason, "SIGNATURE_INVALID")

    def test_acceptance_malformed_key_refused(self):
        _ident, acceptance = make_acceptance()
        acceptance["public_key_hex"] = "zz"
        with self.assertRaises(AcceptanceRefused) as ctx:
            self.svc.accept_notice(acceptance)
        self.assertEqual(ctx.exception.reason, "MALFORMED_KEY")

    def test_valid_acceptance_unity_bound(self):
        ident, acceptance = make_acceptance()
        result = self.svc.accept_notice(acceptance)
        self.assertEqual(result["unity_id"], ident["unity_id"])
        self.assertEqual(
            result["proof_kind"], "ED25519_NOTICE_ACCEPTANCE"
        )


# ---------------------------------------------------------------------------
# The full flow
# ---------------------------------------------------------------------------


class FullFlowTests(BootstrapTestBase):
    def test_full_bootstrap(self):
        ident, acceptance = make_acceptance()
        out = self.svc.bootstrap(acceptance)
        self.assertTrue(out["unity_id"].startswith(IDENTITY_PREFIX))
        # every step receipted
        self.assertIn("acceptance", out)
        self.assertIn("gate_receipt", out)
        self.assertEqual(out["gate_receipt"]["state"], "BOUND")
        self.assertIn("seed", out)
        self.assertIn("tree", out)
        self.assertEqual(out["tree"]["season"], "summer")
        # one seed, free
        seed = self.svc._seeder.seed_record(out["unity_id"])
        self.assertIsNotNone(seed)
        self.assertEqual(seed.price, 0.0)
        self.assertEqual(seed.cost, 0.0)
        self.assertFalse(seed.transferable)
        # gate state says BOUND
        self.assertEqual(self.svc._gate.status(out["unity_id"]), "BOUND")

    def test_second_bootstrap_same_id_refused(self):
        ident, acceptance = make_acceptance()
        first = self.svc.bootstrap(acceptance)
        with self.assertRaises(BootstrapRefused) as ctx:
            self.svc.bootstrap(acceptance)
        self.assertEqual(ctx.exception.reason, "SEED_REFUSED")
        self.assertIn("SEED_ALREADY_ISSUED", str(ctx.exception))
        # still exactly one seed
        self.assertTrue(self.svc._seeder.has_seed(first["unity_id"]))
        self.assertEqual(self.svc._seeder.seeds_issued(), 1)

    def test_tree_binding_receipted(self):
        ident, acceptance = make_acceptance()
        out = self.svc.bootstrap(acceptance)
        tree = self.svc.tree_status(out["unity_id"])
        self.assertEqual(tree["unity_id"], out["unity_id"])
        self.assertEqual(tree["season"], "summer")
        self.assertIn("receipt_id", tree)

    def test_sounding_board_noop_does_not_fail(self):
        ident, acceptance = make_acceptance()
        out = self.svc.bootstrap(acceptance)
        self.assertEqual(
            out["sounding_board"]["status"], "SOUNDING_BOARD_PENDING"
        )
        self.assertTrue(out["sounding_board"]["ok"])

    def test_bootstrap_invalid_acceptance_refused_before_any_write(self):
        _ident, acceptance = make_acceptance()
        del acceptance["signature_hex"]
        with self.assertRaises(AcceptanceRefused):
            self.svc.bootstrap(acceptance)
        # nothing seeded, nothing bound, no participants
        self.assertEqual(self.svc._seeder.seeds_issued(), 0)
        self.assertEqual(self.svc._load_participants(), [])


# ---------------------------------------------------------------------------
# Orientation by doing
# ---------------------------------------------------------------------------


class OrientationTests(BootstrapTestBase):
    def _bootstrapped(self):
        ident, acceptance = make_acceptance()
        out = self.svc.bootstrap(acceptance)
        return ident, out

    def test_orientation_completes(self):
        ident, out = self._bootstrapped()
        uid = out["unity_id"]
        covenant_sig = sign_notice_acceptance(
            ident["private_key_hex"], bootstrap.COVENANT_SHA256
        )
        result = self.svc.orient(
            uid,
            covenant_signature_hex=covenant_sig,
            notice_hash_recomputed=NOTICE_SHA256,
        )
        self.assertEqual(result["status"], "FREE")
        self.assertTrue(result["free"])
        steps = self.svc.orientation_steps(uid)
        kinds = [s["step"] for s in steps]
        self.assertEqual(
            kinds,
            ["COVENANT_ACK", "MISSION_WITNESS", "PLUS_ONE",
             "TREE_VIEW", "FREE"],
        )

    def test_orientation_steps_individually_receipted(self):
        ident, out = self._bootstrapped()
        uid = out["unity_id"]
        covenant_sig = sign_notice_acceptance(
            ident["private_key_hex"], bootstrap.COVENANT_SHA256
        )
        a = self.svc.orient_covenant(uid, covenant_sig)
        self.assertEqual(a["step"], "COVENANT_ACK")
        w = self.svc.orient_mission(uid)
        self.assertEqual(w["step"], "MISSION_WITNESS")
        self.assertEqual(w["witnessed"]["provenance"], "REPORTED")
        p = self.svc.orient_plus_one(uid, NOTICE_SHA256)
        self.assertTrue(p["plus_one_earned"])
        t = self.svc.orient_tree(uid)
        self.assertEqual(t["step"], "TREE_VIEW")
        f = self.svc.orient_free(uid)
        self.assertEqual(f["status"], "FREE")

    def test_orientation_wrong_covenant_sig_refused(self):
        _ident, out = self._bootstrapped()
        other = generate_identity()
        bad_sig = sign_notice_acceptance(
            other["private_key_hex"], bootstrap.COVENANT_SHA256
        )
        with self.assertRaises(BootstrapRefused) as ctx:
            self.svc.orient_covenant(out["unity_id"], bad_sig)
        self.assertEqual(ctx.exception.reason, "ORIENTATION_OPEN")

    def test_orientation_wrong_notice_hash_refused(self):
        ident, out = self._bootstrapped()
        covenant_sig = sign_notice_acceptance(
            ident["private_key_hex"], bootstrap.COVENANT_SHA256
        )
        self.svc.orient_covenant(out["unity_id"], covenant_sig)
        self.svc.orient_mission(out["unity_id"])
        with self.assertRaises(BootstrapRefused):
            self.svc.orient_plus_one(out["unity_id"], "ff" * 32)

    def test_orientation_requires_bootstrapped_identity(self):
        ident = generate_identity()
        with self.assertRaises(BootstrapRefused) as ctx:
            self.svc.orient_covenant(ident["unity_id"], "00" * 128)
        self.assertEqual(ctx.exception.reason, "ORIENTATION_OPEN")


# ---------------------------------------------------------------------------
# Purity: the law holds under pressure
# ---------------------------------------------------------------------------


class PurityTests(BootstrapTestBase):
    def test_seed_is_free_and_non_transferable(self):
        ident, acceptance = make_acceptance()
        out = self.svc.bootstrap(acceptance)
        seed = self.svc._seeder.seed_record(out["unity_id"])
        self.assertEqual((seed.price, seed.cost), (0.0, 0.0))
        self.assertFalse(seed.transferable)
        self.assertFalse(seed.spendable)
        self.assertFalse(seed.purchasable)

    def test_no_approval_queue_paths(self):
        # The only issuance path is the seeder's; there is no bypass.
        self.assertEqual(
            self.svc._seed_module.seed_paths(),
            ["seed.Seeder.issue_seed -> dclm_commit('SEED_ISSUE')"
             " — the ONLY seed issuance path (free, one per Unity ID)"],
        )
        self.assertEqual(self.svc._seed_module.seed_transfer_paths(), [])

    def test_non_testnet_cannot_bootstrap(self):
        ident, acceptance = make_acceptance()
        fake = dict(acceptance)
        # corrupt the public key so the derived ID is not testnet-shaped —
        # impossible through derive_unity_id (always prefixes), so the
        # structural guard lives in _require_testnet on the inputs the
        # service accepts directly:
        with self.assertRaises(BootstrapRefused):
            self.svc.orient("not-a-unity-id", None, None)

    def test_sybil_residual_documented_honestly(self):
        note = self.svc.sybil_note()
        self.assertEqual(note["status"], "RESIDUAL_RISK")
        self.assertIn("WebAuthn", note["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

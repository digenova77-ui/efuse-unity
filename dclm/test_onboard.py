"""
Tests for the onboarder pipeline (dclm/onboard.py) — Residual Law
Finance onboarder -> residual -> tokenomics flywheel.

Purity assertions:
  * unpaperworked / MODELED residual figures are refused at intake
  * the 81% leg never enters any system ledger (meter wallet balance
    unchanged; 81% only ever ACKNOWLEDGED_OFF_SYSTEM)
  * the 19% sits in HELD escrow receipted AWAITING_SPLIT_RULING and is
    never routed while David's three-way split is HELD
  * wave merit flows only from VERIFIED work receipts; no receipts ->
    no merit; nothing accrues on UNKNOWN (PENDING path closed,
    peg-unset defers honestly)
  * no gain-promise language anywhere in the pipeline's code or docs
  * non-testnet identities are refused structurally

Plus a subprocess regression: test_rights_writes.py (which re-runs the
meter suite) stays green after the four new commit kinds.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from onboard import (  # noqa: E402
    AWAITING_SPLIT_RULING,
    BAND_RECOVERY,
    DISPOSITION_ACKNOWLEDGED_OFF_SYSTEM,
    OnboardPipeline,
    OnboardRefused,
    REASON_INSUFFICIENT_ESCROW,
    REASON_MODELED_FIGURE_REFUSED,
    REASON_NO_REPORTED_RESIDUAL,
    REASON_NO_WORK_RECEIPTS,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_PAPERWORK_REQUIRED,
    REASON_RECOVERY_EXCEEDS_REPORTED,
    REASON_SPLIT_HELD_FOR_DAVID,
    REASON_UNVERIFIED_WORK_RECEIPT,
    REASON_UNSUPPORTED_WORK_CLASS,
    merit_path_status,
)
from tokenize import Tokenizer, sign_gate_receipt  # noqa: E402 — the dclm shim -> engine
from tokenize import GENESIS_CHAIN_ANCHOR  # noqa: E402 — gate chain anchor
from meter import Wallet  # noqa: E402 — the system ledger (test-keys)


def _pw(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class OnboardTestBase(unittest.TestCase):
    def fresh_pipeline(self):
        d = tempfile.mkdtemp(prefix="onboard-test-")
        self.addCleanup(shutil.rmtree, d, True)
        return OnboardPipeline(state_dir=d)

    def onboarded(self, p, uid, currency="CAD", cents=1_000_000):
        env = p.onboard(uid, "paperwork:onboard:test-001")
        self.assertEqual(env["receipt"]["outcome"], "GRANTED")
        renv = p.record_residual(
            uid,
            {"amount_cents": cents, "currency": currency,
             "label": "REPORTED"},
            _pw("paperwork", uid),
        )
        self.assertEqual(renv["receipt"]["outcome"], "GRANTED")
        return p

    def work_receipt(self, rid, uid, merit_value=10.0,
                     provenance="VERIFIED", work_class="recovery",
                     prev_hash=GENESIS_CHAIN_ANCHOR):
        r = {
            "schema": "unity.test.v1.testnet",
            "receipt_id": rid,
            "manifest_hash": _pw("manifest", rid),
            "unity_id": uid,
            "kind": "work",
            "provenance": provenance,
            "merit_value": merit_value,
            "detail": {"work_class": work_class,
                       "source": "residual-law-finance"},
            "epoch": "test-epoch",
            "prev_hash": prev_hash,
        }
        # Gate-signed: the test stands in for the DCLM gate with test keys.
        return sign_gate_receipt(r)

    def engine_with_peg(self, E=2.0):
        t = Tokenizer()
        t.set_peg_ratio(E, {"authority": "david"})
        return t


class TestOnboard(OnboardTestBase):
    def test_onboard_grants_and_replays_identically(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-1"
        e1 = p.onboard(uid, "paperwork:onboard:ob-1")
        self.assertEqual(e1["receipt"]["outcome"], "GRANTED")
        self.assertEqual(e1["receipt"]["kind"], "ONBOARD")
        e2 = p.onboard(uid, "paperwork:onboard:ob-1")
        self.assertEqual(e2, e1)  # byte-identical replay, no duplicate

    def test_onboard_requires_paperwork_ref(self):
        p = self.fresh_pipeline()
        with self.assertRaises(OnboardRefused) as ctx:
            p.onboard("unity:testnet:ob-2", "")
        self.assertEqual(ctx.exception.reason, REASON_PAPERWORK_REQUIRED)

    def test_non_testnet_identity_refused_everywhere(self):
        p = self.fresh_pipeline()
        bad = "user:prod:mallory"
        # Contract change 2026-10-06: the purification medium refuses
        # anonymous/forged identities on entry (PurificationRefused),
        # before the pipeline's own OnboardRefused runs.
        from purify import PurificationRefused
        for fn in (
            lambda: p.onboard(bad, "paperwork:x"),
            lambda: p.record_residual(bad, 100, _pw("p")),
            lambda: p.execute_split(bad, 100),
            lambda: p.route_19(bad, 100),
            lambda: p.accrue_recovery_merit(bad, []),
        ):
            with self.assertRaises(PurificationRefused):
                fn()


class TestResidualIntake(OnboardTestBase):
    def test_unpaperworked_residual_refused(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-3"
        p.onboard(uid, "paperwork:onboard:ob-3")
        env = p.record_residual(uid, 500_00, None)
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(env["receipt"]["reason"], REASON_PAPERWORK_REQUIRED)
        # Nothing intaken: the flywheel counts zero reported residual.
        self.assertEqual(p.flywheel_state()["residual_reported_total_cents"],
                         0)

    def test_modeled_figure_refused(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-4"
        p.onboard(uid, "paperwork:onboard:ob-4")
        env = p.record_residual(
            uid,
            {"amount_cents": 999_00, "currency": "CAD", "label": "MODELED"},
            _pw("paperwork", "modeled"),
        )
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(env["receipt"]["reason"],
                         REASON_MODELED_FIGURE_REFUSED)
        self.assertEqual(p.flywheel_state()["residual_reported_total_cents"],
                         0)

    def test_reported_intake_counts_and_replays_by_paperwork(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-5"
        p.onboard(uid, "paperwork:onboard:ob-5")
        ph = _pw("paperwork", "ob-5")
        e1 = p.record_residual(uid, 127_00, ph)
        e2 = p.record_residual(uid, 127_00, ph)
        self.assertEqual(e2, e1)  # one paperwork, one intake
        fs = p.flywheel_state()
        self.assertEqual(fs["residual_reported_total_cents"], 127_00)
        self.assertEqual(fs["residual_label"], "REPORTED")

    def test_unknown_onboarder_refused(self):
        p = self.fresh_pipeline()
        env = p.record_residual("unity:testnet:ghost", 100, _pw("p"))
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")


class TestSplit(OnboardTestBase):
    def test_81_never_enters_system_ledger(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-6"
        self.onboarded(p, uid, cents=10_000_00)
        # The system ledger: the meter's test-key wallet. Fund it, then
        # prove the split moves no keys and the 81% appears nowhere in
        # system state.
        wdir = tempfile.mkdtemp(prefix="wallet-test-")
        self.addCleanup(shutil.rmtree, wdir, True)
        wallet = Wallet(state_dir=wdir)
        wallet.faucet(uid, 100)
        before = wallet.balance(uid)

        env = p.execute_split(uid, 1_000_000, split_id="split-81-test")
        receipt = env["receipt"]
        self.assertEqual(receipt["outcome"], "GRANTED")
        # 81% leg: acknowledged off-system, explicitly not system value.
        leg81 = receipt["leg_81"]
        self.assertEqual(leg81["amount_cents"], 810_000)
        self.assertEqual(leg81["disposition"],
                         DISPOSITION_ACKNOWLEDGED_OFF_SYSTEM)
        self.assertFalse(leg81["system_value"])
        # 19% leg: the only value that entered the system.
        self.assertEqual(receipt["leg_19"]["amount_cents"], 190_000)
        self.assertEqual(p.escrow_balance(uid), 190_000)
        # The system ledger is untouched by either leg.
        self.assertEqual(wallet.balance(uid), before)
        # And the flywheel never counts the 81% as system value.
        fs = p.flywheel_state()
        self.assertEqual(fs["escrow_19_total_cents"], 190_000)
        ack = fs["onboarder_81_acknowledged"]
        self.assertEqual(ack["total_cents"], 810_000)
        self.assertFalse(ack["system_value"])
        self.assertEqual(ack["disposition"],
                         DISPOSITION_ACKNOWLEDGED_OFF_SYSTEM)

    def test_split_integer_exact_no_rounding_leak(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-7"
        self.onboarded(p, uid, cents=101)
        env = p.execute_split(uid, 101, split_id="s-round")
        r = env["receipt"]
        self.assertEqual(r["leg_81"]["amount_cents"]
                         + r["leg_19"]["amount_cents"], 101)

    def test_recovery_beyond_reported_refused(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-8"
        self.onboarded(p, uid, cents=1_000_00)
        env = p.execute_split(uid, 2_000_00, split_id="s-too-big")
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(env["receipt"]["reason"],
                         REASON_RECOVERY_EXCEEDS_REPORTED)
        self.assertEqual(p.escrow_balance(uid), 0)

    def test_split_without_reported_residual_refused(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-9"
        p.onboard(uid, "paperwork:onboard:ob-9")
        env = p.execute_split(uid, 100, split_id="s-none")
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(env["receipt"]["reason"],
                         REASON_NO_REPORTED_RESIDUAL)

    def test_split_id_replay(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-10"
        self.onboarded(p, uid, cents=10_000_00)
        e1 = p.execute_split(uid, 1_000_00, split_id="s-replay")
        e2 = p.execute_split(uid, 1_000_00, split_id="s-replay")
        self.assertEqual(e2, e1)
        self.assertEqual(p.escrow_balance(uid), 19_000)  # once, not twice


class TestRoute19(OnboardTestBase):
    def test_19_escrowed_held_never_routed(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-11"
        self.onboarded(p, uid, cents=10_000_00)
        p.execute_split(uid, 1_000_000, split_id="s-route")
        self.assertEqual(p.escrow_balance(uid), 190_000)

        env = p.route_19(uid, 190_000)
        r = env["receipt"]
        self.assertEqual(r["outcome"], "HELD")
        self.assertEqual(r["status"], AWAITING_SPLIT_RULING)
        self.assertEqual(r["reason"], REASON_SPLIT_HELD_FOR_DAVID)
        self.assertIsNone(r["destinations"])
        # Escrow unchanged: never deployed while the split is HELD.
        self.assertEqual(p.escrow_balance(uid), 190_000)
        self.assertEqual(r["escrow_balance_before_cents"],
                         r["escrow_balance_after_cents"])
        # The three destinations stay at zero; the routing log records
        # the held attempt.
        fs = p.flywheel_state()
        self.assertEqual(fs["peg_support_contribution_cents"], 0)
        self.assertIn("HELD", fs["peg_support_status"])
        self.assertIn("HELD", fs["escrow_status"])
        self.assertEqual(len(p._state["routing_log"]), 1)
        self.assertEqual(p._state["routing_log"][0]["status"],
                         AWAITING_SPLIT_RULING)

    def test_route_more_than_escrow_refused(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-12"
        self.onboarded(p, uid, cents=10_000_00)
        p.execute_split(uid, 1_000_000, split_id="s-route-2")
        env = p.route_19(uid, 999_999_999)
        self.assertEqual(env["receipt"]["outcome"], "REFUSED")
        self.assertEqual(env["receipt"]["reason"], REASON_INSUFFICIENT_ESCROW)


class TestRecoveryMerit(OnboardTestBase):
    def test_merit_only_from_verified_work_receipts(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-13"
        p.onboard(uid, "paperwork:onboard:ob-13")
        engine = self.engine_with_peg()
        res = p.accrue_recovery_merit(
            uid,
            [self.work_receipt("wr-a", uid, 10.0),
             self.work_receipt("wr-b", uid, 5.0,
                               prev_hash=_pw("manifest", "wr-a"))],
            tokenizer=engine,
        )
        self.assertEqual(res["outcome"], "COMPLETE")
        self.assertEqual(res["merit_accrued_total"], 15.0)
        self.assertEqual(res["band"], BAND_RECOVERY)
        self.assertEqual(engine.merit_score(uid), 15.0)

    def test_unverified_receipt_accrues_nothing(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-14"
        p.onboard(uid, "paperwork:onboard:ob-14")
        engine = self.engine_with_peg()
        res = p.accrue_recovery_merit(
            uid, [self.work_receipt("wr-c", uid, 10.0,
                                    provenance="REPORTED")],
            tokenizer=engine,
        )
        self.assertEqual(res["outcome"], "REFUSED")
        self.assertEqual(res["results"][0]["reason"],
                         REASON_UNVERIFIED_WORK_RECEIPT)
        self.assertEqual(res["merit_accrued_total"], 0.0)
        self.assertEqual(engine.merit_score(uid), 0.0)

    def test_no_receipts_no_merit(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-15"
        p.onboard(uid, "paperwork:onboard:ob-15")
        engine = self.engine_with_peg()
        res = p.accrue_recovery_merit(uid, [], tokenizer=engine)
        self.assertEqual(res["reason"], REASON_NO_WORK_RECEIPTS)
        self.assertEqual(res["merit_accrued_total"], 0.0)
        self.assertEqual(engine.merit_score(uid), 0.0)

    def test_other_identity_work_accrues_nothing(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-16"
        other = "unity:testnet:ob-16b"
        p.onboard(uid, "paperwork:onboard:ob-16")
        p.onboard(other, "paperwork:onboard:ob-16b")
        engine = self.engine_with_peg()
        # A receipt for another ID's work, submitted under uid.
        res = p.accrue_recovery_merit(
            uid, [self.work_receipt("wr-d", other, 10.0)],
            tokenizer=engine,
        )
        self.assertEqual(res["results"][0]["status"], "REFUSED")
        self.assertEqual(engine.merit_score(uid), 0.0)
        self.assertEqual(engine.merit_score(other), 0.0)

    def test_unsupported_work_class_refused(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-17"
        p.onboard(uid, "paperwork:onboard:ob-17")
        engine = self.engine_with_peg()
        res = p.accrue_recovery_merit(
            uid, [self.work_receipt("wr-e", uid, 10.0,
                                    work_class="outreach")],
            tokenizer=engine,
        )
        self.assertEqual(res["results"][0]["reason"],
                         REASON_UNSUPPORTED_WORK_CLASS)
        self.assertEqual(engine.merit_score(uid), 0.0)

    def test_replay_never_double_counts(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-18"
        p.onboard(uid, "paperwork:onboard:ob-18")
        engine = self.engine_with_peg()
        wr = self.work_receipt("wr-f", uid, 7.0)
        r1 = p.accrue_recovery_merit(uid, [wr], tokenizer=engine)
        self.assertEqual(r1["outcome"], "COMPLETE")
        r2 = p.accrue_recovery_merit(uid, [wr], tokenizer=engine)
        self.assertEqual(r2["outcome"], "REPLAYED")
        self.assertEqual(r2["results"][0]["status"], "REPLAYED")
        self.assertEqual(engine.merit_score(uid), 7.0)  # once, not twice

    def test_merit_deferred_while_peg_held_then_retryable(self):
        p = self.fresh_pipeline()
        uid = "unity:testnet:ob-19"
        p.onboard(uid, "paperwork:onboard:ob-19")
        engine = Tokenizer()  # peg E unset: HELD_FOR_DAVID
        res = p.accrue_recovery_merit(
            uid, [self.work_receipt("wr-g", uid, 10.0)],
            tokenizer=engine,
        )
        self.assertEqual(res["outcome"], "DEFERRED")
        self.assertEqual(res["results"][0]["status"], "DEFERRED")
        self.assertEqual(engine.merit_score(uid), 0.0)
        # Deferred is not consumed: after David sets E, the same verified
        # work accrues.
        engine.set_peg_ratio(2.0, {"authority": "david"})
        res2 = p.accrue_recovery_merit(
            uid, [self.work_receipt("wr-g", uid, 10.0)],
            tokenizer=engine,
        )
        self.assertEqual(res2["outcome"], "COMPLETE")
        self.assertEqual(engine.merit_score(uid), 10.0)

    def test_merit_path_pending_closed(self):
        import onboard as onboard_module
        real_loader = onboard_module._load_tokenize_api
        onboard_module._load_tokenize_api = lambda: None
        try:
            self.assertEqual(merit_path_status(), "PENDING")
            p = self.fresh_pipeline()
            uid = "unity:testnet:ob-20"
            p.onboard(uid, "paperwork:onboard:ob-20")
            res = p.accrue_recovery_merit(
                uid, [self.work_receipt("wr-h", uid, 10.0)])
            self.assertEqual(res["reason"], "MERIT_PATH_PENDING")
            self.assertEqual(res["merit_accrued_total"], 0.0)
        finally:
            onboard_module._load_tokenize_api = real_loader
        self.assertEqual(merit_path_status(), "LANDED")


class TestNoGainPromises(unittest.TestCase):
    """No onboarder is EVER promised a return: scan the pipeline's code
    and docs for gain-promise language. Any hit is false gold."""

    GAIN_PATTERNS = [
        r"\bapy\b",
        r"\broi\b",
        r"guaranteed\s+(annual\s+)?returns?",
        r"projected\s+returns?",
        r"expected\s+returns?",
        r"passive\s+income",
        r"\d+(\.\d+)?\s*%\s*(per\s+year|annual|returns?|profit|interest)",
        # Split literal so the scanner never matches its own pattern list.
        r"interest-" + "bearing",
        r"earn\s+interest",
    ]

    FILES = ["onboard.py", "test_onboard.py", "ONBOARDER_PIPELINE.md",
             "rights.py", "writes.py"]

    def test_no_gain_promise_strings(self):
        hits = []
        for name in self.FILES:
            path = os.path.join(_HERE, name)
            if not os.path.exists(path):
                continue  # doc lands with the worker; scan what exists
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            for pat in self.GAIN_PATTERNS:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    line = text[:m.start()].count("\n") + 1
                    hits.append(f"{name}:{line}: {m.group(0)!r}")
        self.assertEqual(hits, [], f"gain-promise language found: {hits}")


class TestRegression(unittest.TestCase):
    """rights.py / writes.py / meter.py stay green after the four new
    commit kinds. test_rights_writes.py loops the whole COMMIT_KINDS
    whitelist and re-runs the meter suite in a subprocess."""

    def test_rights_writes_meter_green(self):
        proc = subprocess.run(
            [sys.executable, "test_rights_writes.py"],
            cwd=_HERE,
            capture_output=True,
            text=True,
            timeout=600,
        )
        self.assertEqual(proc.returncode, 0,
                         f"test_rights_writes.py failed:\n{proc.stdout}\n"
                         f"{proc.stderr}")
        # unittest reports to stderr.
        self.assertIn("OK", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

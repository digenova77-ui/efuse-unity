"""
Tests for dclm/purify.py — the purification medium — and its wiring
into every economic transaction path.

David's directive: identity + purify at every level, in every way,
everywhere, every time. These tests are the proof attempt:

  1. Anonymous input refused at every wired path (purify medium raises
     PurificationRefused; the meter surfaces receipted denials /
     MeterRefused — contract evolution 2026-10-06).
  2. Unlabeled claims refused on output.
  3. Tampered signatures refused.
  4. Every wired transaction path passes through purify (introspection:
     the purify calls are present in the path's source).
  5. UNKNOWN handled per contract, never upgraded to PASS.
  6. The medium's own unit contract (fail-closed reasons, free world,
     transitions).

Testnet only.
"""

import hashlib
import inspect
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from purify import (
    PurificationRefused,
    purify_input,
    purify_output,
    purify_transition,
)

ALICE = "unity:testnet:alice"
BOB = "unity:testnet:bob"
CAROL = "unity:testnet:carol"
FEED_OP = "unity:testnet:feed-operator"


def _tmp():
    return tempfile.mkdtemp(prefix="purify-test-")


# ---------------------------------------------------------------------------
# 1. anonymous input refused at every wired path
# ---------------------------------------------------------------------------

class TestAnonymousRefusedEverywhere(unittest.TestCase):
    """No identity -> refused on every wired path, no exceptions.

    Contract evolution 2026-10-06 (maximum run): the purify medium
    still fail-closes (raises PurificationRefused) underneath, but the
    METER surfaces denial as its own typed contract — signed REFUSAL
    receipts from meter_intent (receipted denial, canon: every denial
    auditable) and MeterRefused from faucet. The token engine keeps the
    bare raise. The medium's raise remains the fail-closed floor."""

    def test_meter_intent_anonymous(self):
        from meter import Wallet, OUTCOME_REFUSED
        w = Wallet(state_dir=_tmp())
        for bad, intent in ((None, "anon-1"), ("", "anon-2"),
                            ("mallory", "anon-3")):
            envelope = w.meter_intent(bad, "SEARCH", intent)
            self.assertEqual(envelope["receipt"]["outcome"], OUTCOME_REFUSED,
                             f"for {bad!r}")
            # The medium still fail-closed underneath: the receipted
            # denial names the true reason.
            self.assertIn(envelope["receipt"]["reason"],
                          ("IDENTITY_REQUIRED", "NOT_TESTNET_IDENTITY"))

    def test_meter_faucet_anonymous(self):
        from meter import Wallet, MeterRefused
        w = Wallet(state_dir=_tmp())
        with self.assertRaises(MeterRefused):
            w.faucet(None, 10)
        with self.assertRaises(MeterRefused):
            w.faucet("mallory", 10)

    def test_tokenize_anonymous(self):
        from token_engine import Tokenizer
        t = Tokenizer()
        with self.assertRaises(PurificationRefused):
            t.tokenize({})
        with self.assertRaises(PurificationRefused):
            t.tokenize({"nope": True})

    def test_merit_transfer_anonymous(self):
        from token_engine import Tokenizer
        t = Tokenizer()
        with self.assertRaises(PurificationRefused):
            t.merit_transfer(None, BOB, 10, "gift")
        with self.assertRaises(PurificationRefused):
            t.merit_transfer(ALICE, "mallory", 10, "gift")

    def test_share_issue_grant_anonymous(self):
        import share
        from share import ShareStore
        with self.assertRaises(PurificationRefused):
            share.issue_grant(None, BOB, "FRIEND", "DATA", "d", 60,
                              store=ShareStore())

    def test_share_revoke_grant_anonymous(self):
        import share
        from share import ShareStore
        with self.assertRaises(PurificationRefused):
            share.revoke_grant("mallory", "grant-x", store=ShareStore())

    def test_share_check_access_anonymous(self):
        import share
        from share import ShareStore
        with self.assertRaises(PurificationRefused):
            share.check_access(None, "DATA", "FRIEND", store=ShareStore())

    def test_share_access_anonymous(self):
        import share
        from share import ShareStore
        from meter import Wallet
        with self.assertRaises(PurificationRefused):
            share.access("mallory", "grant-x", "READ",
                         store=ShareStore(), wallet=Wallet(state_dir=_tmp()))

    def test_tap_request_anonymous(self):
        import tap
        from tap import Tapper
        season = _open_season()
        tp = Tapper(season, state_dir=_tmp())
        with self.assertRaises(PurificationRefused):
            tp.request_tap(None, 10, "need")
        with self.assertRaises(PurificationRefused):
            tp.request_tap("alice@example.com", 10, "need")

    def test_winter_store_anonymous(self):
        import winter
        from winter import WinterReserve, WinterSignal
        from meter import Wallet
        w = Wallet(state_dir=_tmp())
        reason = {"trigger_condition": "t", "measured_value": 1.0,
                  "threshold": "0.5"}
        with self.assertRaises(PurificationRefused):
            winter.winter_store("mallory", 10, reason, wallet=w,
                                reserve=WinterReserve(state_dir=_tmp()),
                                signal=WinterSignal())

    def test_winter_release_anonymous(self):
        import winter
        from winter import WinterReserve, WinterSignal
        from meter import Wallet
        w = Wallet(state_dir=_tmp())
        reason = {"trigger_condition": "t", "measured_value": 1.0,
                  "threshold": "0.5"}
        with self.assertRaises(PurificationRefused):
            winter.winter_release(None, 10, reason, wallet=w,
                                  reserve=WinterReserve(state_dir=_tmp()),
                                  signal=WinterSignal())

    def test_onboard_stages_anonymous(self):
        import onboard
        p = onboard.OnboardPipeline(state_dir=_tmp())
        with self.assertRaises(PurificationRefused):
            p.onboard("mallory", "paperwork:x")
        with self.assertRaises(PurificationRefused):
            p.record_residual(None, 100, "ab" * 32)
        with self.assertRaises(PurificationRefused):
            p.execute_split("", 100)
        with self.assertRaises(PurificationRefused):
            p.route_19("user:prod:x", 100)
        with self.assertRaises(PurificationRefused):
            p.accrue_recovery_merit(None, [])

    def test_feed_ingest_anonymous(self):
        import data
        data.clear_feed_sources()
        try:
            with self.assertRaises(PurificationRefused):
                data.ingest_reading("air", reading=b"x",
                                    reading_hash="y")
            # mismatched source is also refused
            data.register_feed_source("air", FEED_OP)
            with self.assertRaises(PurificationRefused):
                data.ingest_reading(
                    "air", reading=b"x", reading_hash="y",
                    source_identity="unity:testnet:impostor")
        finally:
            data.clear_feed_sources()

    def test_seed_issue_anonymous(self):
        # The one-seed path (wired by the seed worker against this same
        # medium): no anonymous issuance.
        import seed
        s = seed.Seeder()
        with self.assertRaises(PurificationRefused):
            s.issue_seed(None)
        with self.assertRaises(PurificationRefused):
            s.issue_seed("mallory")


def _open_season():
    """An open TapSeason (mirrors test_tap.open_season)."""
    import tap
    from tap import TapSeason, Measure
    return TapSeason(
        winter_signal={
            "peg_deviation": 0.0, "peg_provenance": "DERIVED",
            "activity_delta": 0.05, "activity_provenance": "DERIVED",
            "crisis_declared": False, "crisis_verified": False,
            "crisis_provenance": "DERIVED",
        },
        season_id="purify-test-season",
        state_dir=_tmp(),
        pool_health=Measure(0.9, "DERIVED"),
        peg_deviation_bp=Measure(0.0, "DERIVED"),
        reserve_total=Measure(100000, "DERIVED"),
        reserve_survival_need=Measure(10000, "DERIVED"),
        pool_headroom=Measure(50000, "DERIVED"),
        season_replenishment=Measure(1000, "DERIVED"),
    )


# ---------------------------------------------------------------------------
# 2. unlabeled claims refused
# ---------------------------------------------------------------------------

class TestUnlabeledRefused(unittest.TestCase):

    def test_input_claim_without_provenance_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": ALICE,
                 "claims": [{"claim": "naked-claim"}]},
                context={"path": "test"},
            )
        self.assertIn("UNLABELED_CLAIM", str(ctx.exception))

    def test_input_invalid_provenance_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": ALICE,
                 "claims": [{"claim": "x", "provenance": "TRUST_ME"}]},
                context={"path": "test"},
            )
        self.assertIn("INVALID_PROVENANCE", str(ctx.exception))

    def test_output_claim_without_provenance_refused(self):
        # An economic output naming no label: refused on exit.
        with self.assertRaises(PurificationRefused) as ctx:
            purify_output(
                {"identity": ALICE, "outcome": "GRANTED", "amount": 5},
                context={"path": "test"},
            )
        self.assertIn("UNLABELED_CLAIM", str(ctx.exception))

    def test_output_identity_unbound_refused(self):
        # Economic content with no identity anywhere: refused.
        with self.assertRaises(PurificationRefused) as ctx:
            purify_output(
                {"outcome": "GRANTED", "amount": 5,
                 "provenance": "DERIVED"},
                context={"path": "test"},
            )
        self.assertIn("IDENTITY_UNBOUND_OUTPUT", str(ctx.exception))

    def test_output_forged_identity_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_output(
                {"identity": "mallory", "outcome": "GRANTED",
                 "provenance": "DERIVED"},
                context={"path": "test"},
            )
        self.assertIn("NOT_TESTNET_IDENTITY", str(ctx.exception))


# ---------------------------------------------------------------------------
# 3. tampered signatures refused
# ---------------------------------------------------------------------------

class TestTamperedSignaturesRefused(unittest.TestCase):

    def _signed(self, **overrides):
        from meter import sign_receipt
        receipt = {
            "schema": "t", "identity": ALICE, "amount": 10,
            "outcome": "GRANTED", "provenance": "DERIVED",
        }
        receipt.update(overrides)
        return sign_receipt(receipt)

    def test_valid_signature_passes_input(self):
        env = self._signed()
        out = purify_input(
            {"identity": ALICE, "claims": [env]},
            context={"path": "test"},
        )
        self.assertIs(out["claims"][0], env)

    def test_tampered_signature_refused_on_input(self):
        env = self._signed()
        env["receipt"]["amount"] = 999999  # tamper after signing
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": ALICE, "claims": [env]},
                context={"path": "test"},
            )
        self.assertIn("SIGNATURE_INVALID", str(ctx.exception))

    def test_tampered_signature_refused_on_output(self):
        env = self._signed()
        env["receipt"]["amount"] = 999999
        with self.assertRaises(PurificationRefused) as ctx:
            purify_output(env, context={"path": "test", "signed": True})
        self.assertIn("SIGNATURE_INVALID", str(ctx.exception))

    def test_valid_signed_output_passes(self):
        env = self._signed()
        out = purify_output(env, context={"path": "test", "signed": True})
        self.assertIs(out, env)

    def test_missing_signature_where_required_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_output(
                {"identity": ALICE, "outcome": "GRANTED",
                 "provenance": "DERIVED"},
                context={"path": "test", "signed": True},
            )
        self.assertIn("SIGNATURE_MISSING", str(ctx.exception))

    def test_claim_signed_without_signature_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": ALICE, "claim_signed": True,
                 "claims": [{"claim": "x", "provenance": "DERIVED"}]},
                context={"path": "test"},
            )
        self.assertIn("SIGNATURE_INVALID", str(ctx.exception))


# ---------------------------------------------------------------------------
# 4. every wired path passes through the medium (introspection)
# ---------------------------------------------------------------------------

def _src(fn):
    return inspect.getsource(fn)


class TestWiringPresent(unittest.TestCase):
    """The purify calls are present in each wired path's source. A path
    that stops passing through the medium fails here — loudly."""

    def assert_calls(self, fn, *names):
        src = _src(fn)
        for name in names:
            self.assertIn(
                name, src,
                f"{fn.__qualname__} does not call {name}: the path "
                f"bypasses the medium.",
            )

    # -- meter -----------------------------------------------------------
    def test_meter_intent(self):
        from meter import Wallet
        self.assert_calls(Wallet.meter_intent,
                          "purify_input", "purify_output",
                          "purify_transition")

    def test_meter_faucet(self):
        from meter import Wallet
        self.assert_calls(Wallet.faucet,
                          "purify_input", "purify_output",
                          "purify_transition")

    # -- tokenization ----------------------------------------------------
    def test_tokenize(self):
        from token_engine import Tokenizer
        self.assert_calls(Tokenizer.tokenize, "purify_input",
                          "purify_output")
        # the transitions live in the single _commit choke point
        self.assert_calls(Tokenizer._commit, "purify_transition",
                          "purify_output")

    def test_merit_transfer(self):
        from token_engine import Tokenizer
        self.assert_calls(Tokenizer.merit_transfer, "purify_input")
        self.assert_calls(Tokenizer._commit, "purify_transition",
                          "purify_output")

    # -- shared access ---------------------------------------------------
    def test_share_issue_grant(self):
        import share
        self.assert_calls(share.issue_grant,
                          "purify_input", "purify_output",
                          "purify_transition")

    def test_share_revoke_grant(self):
        import share
        self.assert_calls(share.revoke_grant,
                          "purify_input", "purify_output",
                          "purify_transition")

    def test_share_check_access(self):
        import share
        # read-only: input + output purified; no state transition exists
        self.assert_calls(share.check_access, "purify_input",
                          "purify_output")

    def test_share_access(self):
        import share
        self.assert_calls(share.access,
                          "purify_input", "purify_output",
                          "purify_transition")

    # -- tap -------------------------------------------------------------
    def test_tap_request(self):
        from tap import Tapper
        self.assert_calls(Tapper.request_tap,
                          "purify_input", "purify_output",
                          "purify_transition")
        # refusals are purified on exit too
        self.assert_calls(Tapper._signed_refusal, "purify_output")

    # -- winter ----------------------------------------------------------
    def test_winter_store(self):
        import winter
        self.assert_calls(winter.winter_store,
                          "purify_input", "purify_output",
                          "purify_transition")

    def test_winter_release(self):
        import winter
        self.assert_calls(winter.winter_release,
                          "purify_input", "purify_output",
                          "purify_transition")

    # -- onboard pipeline ------------------------------------------------
    def test_onboard_stages(self):
        import onboard
        for stage in ("onboard", "record_residual", "execute_split",
                      "route_19", "accrue_recovery_merit"):
            self.assert_calls(getattr(onboard.OnboardPipeline, stage),
                              "purify_input")
        # transitions + exits live in the single _commit choke point and
        # the refusal helper
        self.assert_calls(onboard.OnboardPipeline._commit,
                          "purify_transition", "purify_output")
        self.assert_calls(onboard.OnboardPipeline._refuse, "purify_output")

    # -- feeds -----------------------------------------------------------
    def test_ingest_reading(self):
        import data
        # no commit path: the registry write is in-memory; input + output
        # purified, source identity bound
        self.assert_calls(data.ingest_reading, "purify_input",
                          "purify_output")
        src = _src(data.ingest_reading)
        self.assertIn("source_identity", src)
        self.assertIn("_FEED_SOURCES", src)
        self.assertIn("register_feed_source", _src(data.register_feed_source))

    # -- one-seed issuance (seed worker's wiring, same medium) ---------
    def test_seed_issue(self):
        import seed
        self.assert_calls(seed.Seeder.issue_seed,
                          "purify_input", "purify_output",
                          "purify_transition")


# ---------------------------------------------------------------------------
# 5. UNKNOWN handled per contract, never upgraded
# ---------------------------------------------------------------------------

class TestUnknownNeverPass(unittest.TestCase):

    def test_unknown_labeled_travels_when_not_upgraded(self):
        # UNKNOWN input, honestly labeled, no pass asserted: the medium
        # lets it travel — the CALLER's contract decides what it means.
        out = purify_input(
            {"identity": ALICE,
             "claims": [{"claim": "pending-figure",
                         "provenance": "UNKNOWN"}]},
            context={"path": "test"},
        )
        self.assertEqual(out["claims"][0]["provenance"], "UNKNOWN")

    def test_present_unknown_as_pass_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": ALICE, "present_unknown_as_pass": True,
                 "claims": [{"claim": "x", "provenance": "UNKNOWN"}]},
                context={"path": "test"},
            )
        self.assertIn("UNKNOWN_UPGRADE_REFUSED", str(ctx.exception))

    def test_assert_truth_on_unknown_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": ALICE, "assert_as_truth": True,
                 "claims": [{"claim": "x", "provenance": "UNKNOWN"}]},
                context={"path": "test", "assert_truth": True},
            )
        self.assertIn("UNKNOWN_UPGRADE_REFUSED", str(ctx.exception))

    def test_transition_receipt_unknown_on_grant_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_transition(
                {"balance": 10}, {"balance": 5}, "LEDGER_DEBIT",
                context={"path": "test", "identity": ALICE,
                         "receipt": {"outcome": "GRANTED",
                                     "provenance": "UNKNOWN"}},
            )
        self.assertIn("UNKNOWN_UPGRADE_REFUSED", str(ctx.exception))

    def test_tokenize_unknown_receipt_still_refused(self):
        # UNKNOWN travels through the medium honestly labeled; the
        # PIPELINE's contract then refuses it — UNKNOWN never tokenizes.
        # That is "handled per the caller's contract, never upgraded":
        # the engine answers with its honest refusal, not a PASS.
        from token_engine import Tokenizer, TokenizeRefused
        t = Tokenizer()
        r = {"schema": "x.testnet", "unity_id": ALICE,
             "receipt_id": "r1",
             "manifest_hash": hashlib.sha256(b"m").hexdigest(),
             "kind": "work", "merit_value": 10.0,
             "provenance": "UNKNOWN"}
        with self.assertRaises(TokenizeRefused) as ctx:
            t.tokenize(r)
        self.assertEqual(ctx.exception.reason,
                         "UNVERIFIED_RECEIPT")

    def test_onboard_modeled_figure_still_refused(self):
        import onboard
        p = onboard.OnboardPipeline(state_dir=_tmp())
        p.onboard(ALICE, "paperwork:m")
        refused = p.record_residual(
            ALICE, {"amount_cents": 100, "label": "MODELED"}, "ab" * 32)
        self.assertEqual(refused["receipt"]["outcome"], "REFUSED")
        self.assertEqual(refused["receipt"]["reason"],
                         onboard.REASON_MODELED_FIGURE_REFUSED)


# ---------------------------------------------------------------------------
# 6. the medium's own contract
# ---------------------------------------------------------------------------

class TestMediumContract(unittest.TestCase):

    def test_free_world_identity_optional_but_not_forged(self):
        out = purify_input(
            {"action": "LOOK", "claims": []},
            context={"path": "test", "free_world": True},
        )
        self.assertEqual(out["action"], "LOOK")
        with self.assertRaises(PurificationRefused) as ctx:
            purify_input(
                {"identity": "mallory", "action": "LOOK"},
                context={"path": "test", "free_world": True},
            )
        self.assertIn("NOT_TESTNET_IDENTITY", str(ctx.exception))

    def test_transition_happy_path(self):
        rec = purify_transition(
            {"balance": 100}, {"balance": 90}, "LEDGER_DEBIT",
            context={"path": "test", "identity": ALICE,
                     "receipt": {"outcome": "GRANTED",
                                 "provenance": "DERIVED"}})
        self.assertEqual(rec["kind"], "LEDGER_DEBIT")
        self.assertEqual(rec["before"], {"balance": 100})

    def test_transition_unknown_kind_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_transition(
                {"a": 1}, {"a": 2}, "MINT_ANYTHING",
                context={"path": "test",
                         "receipt": {"provenance": "DERIVED"}},
            )
        self.assertIn("UNKNOWN_TRANSITION_KIND", str(ctx.exception))

    def test_transition_without_receipt_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_transition(
                {"a": 1}, {"a": 2}, "LEDGER_DEBIT",
                context={"path": "test"},
            )
        self.assertIn("RECEIPT_NOT_PLANNED", str(ctx.exception))

    def test_silent_mutation_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_transition(
                {"balance": 100}, {"balance": 100}, "LEDGER_DEBIT",
                context={"path": "test", "identity": ALICE,
                         "receipt": {"provenance": "DERIVED"}},
            )
        self.assertIn("SILENT_MUTATION", str(ctx.exception))

    def test_identity_discontinuity_refused(self):
        with self.assertRaises(PurificationRefused) as ctx:
            purify_transition(
                {"identity": ALICE}, {"identity": BOB}, "LEDGER_DEBIT",
                context={"path": "test", "identity": ALICE,
                         "receipt": {"provenance": "DERIVED"}},
            )
        self.assertIn("IDENTITY_DISCONTINUITY", str(ctx.exception))

    def test_identity_moves_allowed_when_declared(self):
        rec = purify_transition(
            {"from_id": ALICE}, {"to_id": BOB}, "MERIT_TRANSFER",
            context={"path": "test", "identity": ALICE,
                     "identity_moves": True,
                     "receipt": {"provenance": "DERIVED"}},
        )
        self.assertEqual(rec["kind"], "MERIT_TRANSFER")

    def test_real_label_accepted(self):
        # The directive's REAL label is valid in the medium.
        out = purify_input(
            {"identity": ALICE,
             "claims": [{"claim": "measured", "provenance": "REAL"}]},
            context={"path": "test"},
        )
        self.assertEqual(out["claims"][0]["provenance"], "REAL")

    def test_purify_does_not_commit(self):
        # The boundary: purify.py checks; writes.py commits. The medium
        # imports neither writes nor a commit path.
        import purify
        self.assertFalse(hasattr(purify, "dclm_commit"))
        src = inspect.getsource(purify)
        self.assertNotIn("from writes import", src)
        self.assertNotIn("import writes", src)


if __name__ == "__main__":
    unittest.main()

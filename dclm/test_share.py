"""
Tests for the DCLM shared-access mechanism (~/workspace/unity-world/dclm/).

All must pass. Testnet only. Test keys only — never dollars, never eFuse.

Covers: issue/verify/revoke lifecycle, instant revocation, tier-creep
blocked structurally, expiry, wrong content type, tamper-evidence,
metered access (money moves, failures deduct nothing), the kin-binding
rule, non-testnet refusal, and David's derivative-merit law (money
moves through grants; merit never does).
"""

import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import share  # noqa: E402
from share import (  # noqa: E402
    ACCESS_DENY,
    ACCESS_GRANT,
    CONTENT_COMPUTE,
    CONTENT_DATA,
    CONTENT_RTE_SEAT,
    AccessVerdict,
    ShareRefused,
    ShareStore,
    TIER_FAMILY,
    TIER_FRIEND,
    TIER_GOOD_FRIEND,
    access,
    check_access,
    clear_kin_authority,
    issue_grant,
    register_kin_authority,
    revoke_grant,
)
from meter import Wallet, verify_receipt  # noqa: E402
from writes import verify_commit  # noqa: E402

ALICE = "unity:testnet:alice-share"
BOB = "unity:testnet:bob-share"
CAROL = "unity:testnet:carol-share"

T0 = "2026-10-06T00:00:00+00:00"
T0_PLUS_30 = "2026-10-06T00:00:30+00:00"
T0_PLUS_120 = "2026-10-06T00:02:00+00:00"


def refused_reason(fn, *args, **kwargs):
    """Run fn; expect ShareRefused; return its reason."""
    try:
        fn(*args, **kwargs)
    except ShareRefused as exc:
        return exc.reason
    raise AssertionError(f"expected ShareRefused from {fn.__name__}")


class ShareTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="share-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.wallet = Wallet(state_dir=os.path.join(self.tmp, "meter"))
        self.store = ShareStore()
        self.addCleanup(clear_kin_authority)

    def fund(self, identity, amount):
        self.wallet.faucet(identity, amount)

    def issue(self, granter=ALICE, grantee=BOB, tier=TIER_FRIEND,
              content_type=CONTENT_DATA, depth="summary extract",
              duration=3600, price=0, **kwargs):
        return issue_grant(
            granter, grantee, tier, content_type, depth, duration, price,
            store=self.store, now=T0, **kwargs,
        )


# ---------------------------------------------------------------------------
# issue
# ---------------------------------------------------------------------------

class TestIssue(ShareTestBase):
    def test_issue_grant_ok(self):
        """A well-formed grant issues: signed, receipted, registered."""
        result = self.issue()
        grant_id = result["grant_id"]
        self.assertIn(grant_id, self.store.grants)
        envelope = result["grant"]
        self.assertTrue(verify_receipt(envelope))
        grant = envelope["receipt"]
        self.assertEqual(grant["granter"], ALICE)
        self.assertEqual(grant["grantee"], BOB)
        self.assertEqual(grant["tier"], TIER_FRIEND)
        self.assertEqual(grant["tier_level"], 1)  # integer: the creep wall
        self.assertEqual(grant["content_type"], CONTENT_DATA)
        self.assertEqual(grant["price"], 0)
        self.assertEqual(grant["merit_flow"], "NONE")
        self.assertTrue(verify_commit(result["commit"]))
        self.assertEqual(len(self.store.receipts), 1)

    def test_issue_rejects_non_testnet_identities(self):
        # Contract change 2026-10-06: the purification medium refuses
        # anonymous/forged identities on entry (PurificationRefused),
        # before the module's own ShareRefused runs.
        from purify import PurificationRefused
        with self.assertRaises(PurificationRefused):
            issue_grant("alice", BOB, TIER_FRIEND, CONTENT_DATA, "d", 60,
                        store=self.store)
        with self.assertRaises(PurificationRefused):
            issue_grant(ALICE, "bob@example.com", TIER_FRIEND,
                        CONTENT_DATA, "d", 60, store=self.store)
        self.assertEqual(len(self.store.receipts), 0)  # nothing written

    def test_issue_rejects_self_grant(self):
        self.assertEqual(
            refused_reason(self.issue, granter=ALICE, grantee=ALICE),
            "SELF_GRANT",
        )

    def test_issue_rejects_unknown_tier(self):
        self.assertEqual(
            refused_reason(self.issue, tier="ACQUAINTANCE"),
            "UNKNOWN_TIER",
        )

    def test_issue_rejects_bad_params(self):
        self.assertEqual(
            refused_reason(self.issue, content_type="DREAMS"),
            "UNKNOWN_CONTENT_TYPE",
        )
        self.assertEqual(
            refused_reason(self.issue, depth="   "),
            "INVALID_DEPTH",
        )
        self.assertEqual(
            refused_reason(self.issue, duration=0),
            "INVALID_DURATION",
        )
        self.assertEqual(
            refused_reason(self.issue, price=-1),
            "INVALID_PRICE",
        )
        self.assertEqual(len(self.store.receipts), 0)  # nothing written

    def test_family_without_kin_verification_refused(self):
        """No L2 authority registered -> family grants cannot be issued.
        Honest refusal, never assumed kinship."""
        reason = refused_reason(self.issue, tier=TIER_FAMILY)
        self.assertEqual(reason, "NOT_KIN_VERIFIED")
        self.assertEqual(len(self.store.grants), 0)
        self.assertEqual(len(self.store.receipts), 0)

    def test_family_with_registered_authority(self):
        """When the L2 umpire module wires in, verified kin may receive
        family-tier grants."""
        register_kin_authority(lambda a, b: True)
        try:
            result = self.issue(tier=TIER_FAMILY)
        finally:
            clear_kin_authority()
        grant = result["grant"]["receipt"]
        self.assertEqual(grant["tier_level"], 3)
        self.assertTrue(grant["kin_verified"])

    def test_authority_denying_kin_refuses_family(self):
        register_kin_authority(lambda a, b: False)
        try:
            reason = refused_reason(self.issue, tier=TIER_FAMILY)
        finally:
            clear_kin_authority()
        self.assertEqual(reason, "NOT_KIN_VERIFIED")


# ---------------------------------------------------------------------------
# revoke — instant and total
# ---------------------------------------------------------------------------

class TestRevoke(ShareTestBase):
    def test_revoke_lifecycle(self):
        """Issue -> access granted -> revoke -> access denied instantly."""
        result = self.issue()
        grant_id = result["grant_id"]
        verdict = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                               store=self.store, now=T0_PLUS_30)
        self.assertTrue(verdict.granted)

        revoke_grant(ALICE, grant_id, store=self.store, now=T0_PLUS_30)

        # No stale reads: the very next check sees the revocation.
        verdict = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                               store=self.store, now=T0_PLUS_30)
        self.assertFalse(verdict.granted)
        self.assertEqual(verdict.reason, "GRANT_REVOKED")

    def test_revoke_only_granter(self):
        result = self.issue()
        self.assertEqual(
            refused_reason(revoke_grant, CAROL, result["grant_id"],
                           store=self.store),
            "NOT_GRANTER",
        )
        # The grant still works — a stranger's revoke attempt changed nothing.
        verdict = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                               store=self.store, now=T0_PLUS_30)
        self.assertTrue(verdict.granted)

    def test_double_revoke_refused(self):
        result = self.issue()
        revoke_grant(ALICE, result["grant_id"], store=self.store)
        self.assertEqual(
            refused_reason(revoke_grant, ALICE, result["grant_id"],
                           store=self.store),
            "ALREADY_REVOKED",
        )

    def test_revoke_unknown_grant(self):
        self.assertEqual(
            refused_reason(revoke_grant, ALICE, "no-such-grant",
                           store=self.store),
            "GRANT_NOT_FOUND",
        )


# ---------------------------------------------------------------------------
# check_access — tiers compared as integers, signatures verified
# ---------------------------------------------------------------------------

class TestCheckAccess(ShareTestBase):
    def test_tier_creep_blocked(self):
        """A FRIEND grant can NEVER exercise family-tier access: 1 >= 3
        is false, structurally, not by policy."""
        self.issue(tier=TIER_FRIEND)
        ok = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                          store=self.store, now=T0_PLUS_30)
        self.assertTrue(ok.granted)
        self.assertEqual(ok.reason, ACCESS_GRANT)

        for required in (TIER_GOOD_FRIEND, TIER_FAMILY):
            denied = check_access(BOB, CONTENT_DATA, required,
                                  store=self.store, now=T0_PLUS_30)
            self.assertFalse(denied.granted)
            self.assertEqual(denied.reason, "TIER_TOO_LOW")

    def test_good_friend_cannot_reach_family(self):
        self.issue(tier=TIER_GOOD_FRIEND)
        denied = check_access(BOB, CONTENT_DATA, TIER_FAMILY,
                              store=self.store, now=T0_PLUS_30)
        self.assertFalse(denied.granted)
        self.assertEqual(denied.reason, "TIER_TOO_LOW")
        ok = check_access(BOB, CONTENT_DATA, TIER_GOOD_FRIEND,
                          store=self.store, now=T0_PLUS_30)
        self.assertTrue(ok.granted)

    def test_expired_grant_denies(self):
        self.issue(duration=60)
        live = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                            store=self.store, now=T0_PLUS_30)
        self.assertTrue(live.granted)
        dead = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                            store=self.store, now=T0_PLUS_120)
        self.assertFalse(dead.granted)
        self.assertEqual(dead.reason, "GRANT_EXPIRED")

    def test_wrong_content_type_denies(self):
        self.issue(content_type=CONTENT_DATA)
        denied = check_access(BOB, CONTENT_RTE_SEAT, TIER_FRIEND,
                              store=self.store, now=T0_PLUS_30)
        self.assertFalse(denied.granted)
        self.assertEqual(denied.reason, "NO_GRANT")

    def test_tampered_grant_denies(self):
        """Editing the signed tier integer breaks the signature: the
        grant is dead, fail-closed — it can never be promoted."""
        result = self.issue(tier=TIER_FRIEND)
        grant_id = result["grant_id"]
        # Attacker flips tier_level 1 -> 3 without re-signing.
        self.store.grants[grant_id]["receipt"]["tier_level"] = 3
        for required in (TIER_FRIEND, TIER_FAMILY):
            denied = check_access(BOB, CONTENT_DATA, required,
                                  store=self.store, now=T0_PLUS_30)
            self.assertFalse(denied.granted)
            self.assertEqual(denied.reason, "INVALID_GRANT")

    def test_check_access_validates_inputs(self):
        # Contract change 2026-10-06: anonymous callers are refused by
        # the purification medium on entry (PurificationRefused), not by
        # a deny verdict.
        from purify import PurificationRefused
        with self.assertRaises(PurificationRefused):
            check_access("bob", CONTENT_DATA, TIER_FRIEND,
                         store=self.store)
        denied = check_access(BOB, CONTENT_DATA, "INNER_CIRCLE",
                              store=self.store)
        self.assertEqual(denied.reason, "UNKNOWN_TIER")
        denied = check_access(BOB, "DREAMS", TIER_FRIEND, store=self.store)
        self.assertEqual(denied.reason, "UNKNOWN_CONTENT_TYPE")

    def test_verdict_is_frozen(self):
        verdict = check_access(BOB, CONTENT_DATA, TIER_FRIEND,
                               store=self.store)
        self.assertIsInstance(verdict, AccessVerdict)
        with self.assertRaises(AttributeError):
            verdict.granted = True  # type: ignore


# ---------------------------------------------------------------------------
# access — metered, money only
# ---------------------------------------------------------------------------

class TestMeteredAccess(ShareTestBase):
    def test_metered_access_moves_money(self):
        """Accessing through a priced grant deducts the accessor and
        credits the granter in full. Every leg is receipted."""
        self.fund(ALICE, 100)
        self.fund(BOB, 100)
        result = self.issue(price=7)
        grant_id = result["grant_id"]

        out = access(BOB, grant_id, "read", store=self.store,
                     wallet=self.wallet, now=T0_PLUS_30)

        self.assertEqual(self.wallet.balance(BOB), 93)
        self.assertEqual(self.wallet.balance(ALICE), 107)
        self.assertEqual(out["price"], 7)
        self.assertTrue(verify_commit(out["debit"]))
        self.assertTrue(verify_commit(out["credit"]))
        self.assertTrue(verify_commit(out["access"]))
        self.assertEqual(out["debit"]["receipt"]["amount"], 7)
        self.assertEqual(out["credit"]["receipt"]["amount"], 7)
        self.assertEqual(out["credit"]["receipt"]["identity"], ALICE)
        self.assertEqual(len(self.store.access_log), 1)

    def test_free_grant_access_moves_no_money(self):
        self.fund(ALICE, 100)
        self.fund(BOB, 100)
        result = self.issue(price=0)
        out = access(BOB, result["grant_id"], "read", store=self.store,
                     wallet=self.wallet, now=T0_PLUS_30)
        self.assertIsNone(out["debit"])
        self.assertIsNone(out["credit"])
        self.assertEqual(self.wallet.balance(BOB), 100)
        self.assertEqual(self.wallet.balance(ALICE), 100)
        self.assertTrue(verify_commit(out["access"]))

    def test_insufficient_keys_no_deduction(self):
        """Failed access deducts nothing and commits nothing."""
        self.fund(ALICE, 100)
        self.fund(BOB, 3)
        result = self.issue(price=7)
        reason = refused_reason(access, BOB, result["grant_id"], "read",
                                store=self.store, wallet=self.wallet,
                                now=T0_PLUS_30)
        self.assertEqual(reason, "INSUFFICIENT_KEYS")
        self.assertEqual(self.wallet.balance(BOB), 3)
        self.assertEqual(self.wallet.balance(ALICE), 100)
        self.assertEqual(len(self.store.access_log), 0)
        # Only the GRANT_ISSUE receipt exists — no access write happened.
        self.assertEqual(len(self.store.receipts), 1)

    def test_revoked_access_refused_no_charge(self):
        self.fund(ALICE, 100)
        self.fund(BOB, 100)
        result = self.issue(price=7)
        revoke_grant(ALICE, result["grant_id"], store=self.store,
                     now=T0_PLUS_30)
        reason = refused_reason(access, BOB, result["grant_id"], "read",
                                store=self.store, wallet=self.wallet,
                                now=T0_PLUS_30)
        self.assertEqual(reason, "GRANT_REVOKED")
        self.assertEqual(self.wallet.balance(BOB), 100)
        self.assertEqual(self.wallet.balance(ALICE), 100)

    def test_wrong_grantee_refused(self):
        self.fund(ALICE, 100)
        self.fund(CAROL, 100)
        result = self.issue(price=7)  # granted to BOB, not CAROL
        reason = refused_reason(access, CAROL, result["grant_id"], "read",
                                store=self.store, wallet=self.wallet,
                                now=T0_PLUS_30)
        self.assertEqual(reason, "NOT_GRANTEE")
        self.assertEqual(self.wallet.balance(CAROL), 100)


# ---------------------------------------------------------------------------
# derivative merit regeneration — money moves, merit never does
# ---------------------------------------------------------------------------

class TestMeritLaw(ShareTestBase):
    def test_merit_payload_refused_at_issue(self):
        """A grant carrying a merit payload is refused as malformed."""
        self.assertEqual(
            refused_reason(self.issue, annotations={"merit_score": 50}),
            "MERIT_IN_GRANT",
        )
        self.assertEqual(
            refused_reason(
                self.issue, annotations={"note": {"merit_transfer": 1}}
            ),
            "MERIT_IN_GRANT",
        )
        self.assertEqual(len(self.store.grants), 0)
        self.assertEqual(len(self.store.receipts), 0)

    def test_merit_action_refused_at_access(self):
        """A future caller trying to pass merit through access() is
        refused before any money moves."""
        self.fund(ALICE, 100)
        self.fund(BOB, 100)
        result = self.issue(price=7)
        reason = refused_reason(access, BOB, result["grant_id"],
                                "accrue merit for bob",
                                store=self.store, wallet=self.wallet,
                                now=T0_PLUS_30)
        self.assertEqual(reason, "MERIT_IN_GRANT")
        self.assertEqual(self.wallet.balance(BOB), 100)
        self.assertEqual(self.wallet.balance(ALICE), 100)
        self.assertEqual(len(self.store.access_log), 0)

    def test_share_has_no_merit_accrual_paths(self):
        """Introspection: share.py contains no merit-accrual call, no
        tokenization import, no merit write kind. The structure cannot
        move merit because it has no path that does."""
        with open(os.path.join(_HERE, "share.py"), encoding="utf-8") as fh:
            src = fh.read()
        for token in (
            "MERIT_ACCRUAL",
            "from tokenize",
            "import tokenize",
            "_mint(",
            "accrue_merit",
            "merit_transfer",
            "merit_mint",
        ):
            self.assertNotIn(token, src, f"forbidden merit path: {token}")
        # ...but the law itself is stamped on the module.
        self.assertIn("merit_flow", src)

    def test_grant_and_event_carry_merit_none_marker(self):
        """The issued grant and the committed access event both declare
        merit_flow NONE: money only, auditable on the receipt."""
        self.fund(ALICE, 100)
        self.fund(BOB, 100)
        result = self.issue(price=7)
        self.assertEqual(result["grant"]["receipt"]["merit_flow"], "NONE")
        out = access(BOB, result["grant_id"], "read", store=self.store,
                     wallet=self.wallet, now=T0_PLUS_30)
        # The commit envelope wraps the event (COMMIT record); the event
        # payload itself lives in the access log.
        self.assertEqual(out["access"]["receipt"]["kind"], "SHARED_ACCESS")
        event = self.store.access_log[-1]
        self.assertEqual(event["merit_flow"], "NONE")
        self.assertTrue(event["money_only"])
        merit_keys = [k for k in event if "merit" in k.lower()]
        self.assertEqual(merit_keys, ["merit_flow"])

    def test_grantee_merit_path_is_their_own(self):
        """share.py exposes no merit API: the grantee's merit can only
        come from their own verified receipts, never from the grant."""
        for name in ("accrue_merit", "transfer_merit", "mint_merit",
                     "merit_score", "award_merit"):
            self.assertFalse(hasattr(share, name), name)
        # After a priced access, exactly `price` test-keys moved and
        # nothing else exists in share state that could carry merit.
        self.fund(ALICE, 100)
        self.fund(BOB, 100)
        result = self.issue(price=0)
        access(BOB, result["grant_id"], "read", store=self.store,
               wallet=self.wallet, now=T0_PLUS_30)
        self.assertEqual(set(vars(self.store).keys()),
                         {"grants", "revoked", "access_log", "receipts"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

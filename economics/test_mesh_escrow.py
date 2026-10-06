"""
Tests for the Mesh Clearing bounty escrow (economics/mesh_escrow.py):
F2 (bounty post) and F3 (bounty fulfillment) per TOKENOMICS_5050_MERIT.md
§3.3 / §5.

All must pass. Testnet only. The suite proves:
  - full F2 -> F3 happy path (pool authority funds, fulfiller paid in the
    commissioning pool's coins, bridge merit accrues)
  - F3 refuses without BOTH-SIDE receipts (commissioning + fulfilling)
  - manifest_hash idempotency: the same work can never claim twice
  - expired bounties return the reservation to the commissioning pool's
    authority, receipted
  - no pool-to-pool path exists (absence of machinery, verified by scan)
  - the escrow holds no emission authority of its own (routes, never mints)
  - bridge merit is fixed-band and explicit: unsigned/held weight refuses

Run: python3 test_mesh_escrow.py
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import mesh_escrow as ME
import tokenomics as T
from tokenomics import (
    AuthorityExceededError,
    DuplicateReceiptError,
    Figure,
    HeldParameter,
    HeldParameterError,
    Ledger,
    Receipt,
    ReceiptRequiredError,
    TokenomicsError,
    UnityBindingError,
    UnknownFigureError,
)

COMMISSIONER = "unity:testnet:commissioner"
FULFILLER = "unity:testnet:fulfiller"
STRANGER = "unity:testnet:stranger"
SPEC_HASH = "spec:" + "a" * 60
WORK_HASH = "work:" + "b" * 60
WORK_HASH_2 = "work:" + "c" * 60


def v(value, prov="VERIFIED"):
    return Figure(value, prov, "testnet fixture")


def modeled(value):
    return Figure(value, "MODELED",
                  "testnet bridge band — bridge_premium_band HELD_FOR_DAVID")


def post_receipt_for(ledger, bounty):
    """Find the F2 post receipt naming a specific bounty."""
    for r in reversed(ledger.receipts):
        if (r.kind == "bounty_post"
                and r.detail.get("bounty_id") == bounty.bounty_id):
            return r
    raise AssertionError("no bounty_post receipt found for bounty")


def post_receipt(ledger, uid=COMMISSIONER):
    """The most recent bounty_post receipt (chain-head helper)."""
    return post_receipt_for_chain_head(ledger)


def post_receipt_for_chain_head(ledger):
    for r in reversed(ledger.receipts):
        if r.kind == "bounty_post":
            return r
    raise AssertionError("no bounty_post receipt in ledger")


def fulfill_receipt(uid, work_hash, provenance="VERIFIED", epoch=1):
    """The fulfilling side's work receipt — the countersigned delivery."""
    return Receipt.build(
        uid, "merit_accrual",
        {"work": "cross-lane fixture", "work_manifest_hash": work_hash},
        provenance, epoch, "GENESIS")


class MeshEscrowTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.escrow = ME.MeshClearing(self.ledger)

    # -- helpers ----------------------------------------------------------
    def post(self, pool="human", amount=None, commissioner=COMMISSIONER,
             work_hash=WORK_HASH, band="B1", expiry=5, epoch=1):
        return self.escrow.bounty_post(
            commissioning_pool=pool,
            commissioner_unity_id=commissioner,
            amount=v(amount if amount is not None else 1000.0),
            work_spec_hash=SPEC_HASH,
            work_manifest_hash=work_hash,
            band=band,
            expiry_epoch=expiry,
            epoch=epoch)

    def fulfill(self, bounty, fulfiller=FULFILLER, weight=None,
                epoch=1, comm_receipt=None, work_hash=WORK_HASH,
                receipt_prov="VERIFIED"):
        return self.escrow.bounty_fulfill(
            bounty_id=bounty.bounty_id,
            fulfiller_unity_id=fulfiller,
            commissioning_receipt=(comm_receipt
                                   if comm_receipt is not None
                                   else post_receipt_for(self.ledger, bounty)),
            fulfilling_receipt=fulfill_receipt(
                fulfiller, work_hash, receipt_prov, epoch),
            bridge_merit_weight=(weight if weight is not None
                                 else modeled(25.0)),
            epoch=epoch)

    # -- F2 -> F3 happy path ---------------------------------------------
    def test_f2_f3_happy_path(self):
        bounty = self.post()
        self.assertEqual(bounty.status, ME.STATUS_OPEN)
        self.assertEqual(bounty.commissioning_pool, "human")
        self.assertEqual(bounty.commissioner_unity_id, COMMISSIONER)
        self.assertEqual(self.escrow.reserved("human"), 1000.0)

        # F2 receipted, Unity-bound to the commissioner, terms on it
        pr = post_receipt(self.ledger)
        self.assertEqual(pr.kind, "bounty_post")
        self.assertEqual(pr.unity_id, COMMISSIONER)
        self.assertEqual(pr.detail["bounty_id"], bounty.bounty_id)
        self.assertEqual(pr.detail["work_manifest_hash"], WORK_HASH)
        self.assertEqual(pr.detail["band"], "B1")
        self.assertEqual(pr.detail["expiry_epoch"], 5)

        out = self.fulfill(bounty)
        self.assertEqual(self.escrow.get(bounty.bounty_id).status,
                         ME.STATUS_FULFILLED)
        self.assertEqual(self.escrow.reserved("human"), 0.0)

        # The commissioning pool paid, in its own coins; machine pool untouched
        self.assertAlmostEqual(self.ledger.emitted["human"], 1000.0)
        self.assertAlmostEqual(self.ledger.emitted["machine"], 0.0)
        dr = out["disbursement_receipt"]
        self.assertEqual(dr.kind, "disbursement")
        self.assertEqual(dr.unity_id, FULFILLER)
        self.assertEqual(dr.detail["pool"], "human")

        # Bridge merit accrued to the fulfiller, fixed and visible
        self.assertAlmostEqual(
            self.ledger.merit_balance(FULFILLER).value, 25.0)
        fr = out["fulfill_receipt"]
        self.assertEqual(fr.kind, "bounty_fulfill")
        self.assertEqual(fr.unity_id, FULFILLER)
        self.assertEqual(fr.detail["commissioning_receipt_id"],
                         pr.receipt_id)
        self.assertEqual(fr.detail["fulfilling_receipt_id"],
                         out["bridge_merit_credit"].receipt_id)
        self.assertEqual(fr.detail["work_manifest_hash"], WORK_HASH)
        self.assertEqual(fr.detail["bridge_merit"]["weight"], 25.0)

        # Machine-pool bounty funds from machine authority, symmetrically
        b2 = self.post(pool="machine", work_hash=WORK_HASH_2, expiry=9,
                       epoch=2)
        self.fulfill(b2, epoch=2, work_hash=WORK_HASH_2)
        self.assertAlmostEqual(self.ledger.emitted["machine"], 1000.0)
        self.assertAlmostEqual(self.ledger.emitted["human"], 1000.0)

    # -- both-side receipts -----------------------------------------------
    def test_f3_refuses_without_commissioning_receipt(self):
        bounty = self.post()
        with self.assertRaises(ReceiptRequiredError):
            self.escrow.bounty_fulfill(
                bounty_id=bounty.bounty_id, fulfiller_unity_id=FULFILLER,
                commissioning_receipt=None,
                fulfilling_receipt=fulfill_receipt(FULFILLER, WORK_HASH),
                bridge_merit_weight=modeled(25.0), epoch=1)

    def test_f3_refuses_without_fulfilling_receipt(self):
        bounty = self.post()
        with self.assertRaises(ReceiptRequiredError):
            self.escrow.bounty_fulfill(
                bounty_id=bounty.bounty_id, fulfiller_unity_id=FULFILLER,
                commissioning_receipt=post_receipt(self.ledger),
                fulfilling_receipt=None,
                bridge_merit_weight=modeled(25.0), epoch=1)

    def test_f3_refuses_ungated_fulfilling_receipt(self):
        bounty = self.post()
        # REPORTED is not VERIFIED: RELAYED never means DELIVERED
        with self.assertRaises(ME.BountyEscrowError):
            self.fulfill(bounty, receipt_prov="REPORTED")
        self.assertEqual(self.escrow.get(bounty.bounty_id).status,
                         ME.STATUS_OPEN)
        self.assertAlmostEqual(self.ledger.emitted["human"], 0.0)

    def test_f3_refuses_fulfilling_receipt_bound_to_wrong_id(self):
        bounty = self.post()
        # The fulfilling receipt names STRANGER, the claim names FULFILLER
        with self.assertRaises(ME.BountyEscrowError):
            self.escrow.bounty_fulfill(
                bounty_id=bounty.bounty_id, fulfiller_unity_id=FULFILLER,
                commissioning_receipt=post_receipt(self.ledger),
                fulfilling_receipt=fulfill_receipt(STRANGER, WORK_HASH),
                bridge_merit_weight=modeled(25.0), epoch=1)

    def test_f3_refuses_commissioning_receipt_from_another_bounty(self):
        b1 = self.post(work_hash=WORK_HASH)
        b2 = self.post(work_hash=WORK_HASH_2, epoch=1)
        # b2's F2 receipt (the chain head) offered against b1
        with self.assertRaises(ME.BountyEscrowError):
            self.escrow.bounty_fulfill(
                bounty_id=b1.bounty_id, fulfiller_unity_id=FULFILLER,
                commissioning_receipt=post_receipt(self.ledger),
                fulfilling_receipt=fulfill_receipt(FULFILLER, WORK_HASH),
                bridge_merit_weight=modeled(25.0), epoch=1)

    def test_f3_refuses_fulfilling_receipt_with_wrong_manifest(self):
        bounty = self.post()
        with self.assertRaises(ME.BountyEscrowError):
            self.fulfill(bounty, work_hash="work:" + "z" * 60)

    # -- idempotency -------------------------------------------------------
    def test_double_fulfill_of_same_bounty_refused(self):
        bounty = self.post()
        self.fulfill(bounty)
        with self.assertRaises((DuplicateReceiptError, ME.BountyEscrowError,
                                TokenomicsError)):
            self.escrow.bounty_fulfill(
                bounty_id=bounty.bounty_id, fulfiller_unity_id=FULFILLER,
                commissioning_receipt=post_receipt(self.ledger, COMMISSIONER),
                fulfilling_receipt=fulfill_receipt(FULFILLER, WORK_HASH),
                bridge_merit_weight=modeled(25.0), epoch=1)
        # Paid exactly once
        self.assertAlmostEqual(self.ledger.emitted["human"], 1000.0)

    def test_same_work_manifest_cannot_claim_twice_across_bounties(self):
        # Two bounties commission the same work; the first fulfillment wins.
        b1 = self.post(work_hash=WORK_HASH)
        b2 = self.post(work_hash=WORK_HASH, epoch=1)
        self.fulfill(b1)
        pr2 = post_receipt_for(self.ledger, b2)
        with self.assertRaises(DuplicateReceiptError):
            self.escrow.bounty_fulfill(
                bounty_id=b2.bounty_id, fulfiller_unity_id=FULFILLER,
                commissioning_receipt=pr2,
                fulfilling_receipt=fulfill_receipt(FULFILLER, WORK_HASH),
                bridge_merit_weight=modeled(25.0), epoch=1)
        self.assertEqual(self.escrow.get(b2.bounty_id).status,
                         ME.STATUS_OPEN)
        self.assertAlmostEqual(self.ledger.emitted["human"], 1000.0)

    # -- expiry ------------------------------------------------------------
    def test_expired_bounty_returns_authority_receipted(self):
        bounty = self.post(expiry=2)
        full = self.escrow.available_authority("human").value
        self.assertAlmostEqual(full, 50_000_000.0 - 1000.0)

        # Fulfillment past expiry is refused
        with self.assertRaises(ME.BountyEscrowError):
            self.fulfill(bounty, epoch=3)

        # Early return is refused
        with self.assertRaises(ME.BountyEscrowError):
            self.escrow.expire_bounty(bounty.bounty_id, 2)

        ret = self.escrow.expire_bounty(bounty.bounty_id, 3)
        self.assertEqual(ret.kind, "bounty_return")
        self.assertEqual(ret.unity_id, COMMISSIONER)
        self.assertEqual(ret.detail["amount_returned"], 1000.0)
        self.assertEqual(self.escrow.get(bounty.bounty_id).status,
                         ME.STATUS_RETURNED)
        self.assertEqual(self.escrow.reserved("human"), 0.0)
        self.assertAlmostEqual(
            self.escrow.available_authority("human").value, 50_000_000.0)
        # Nothing was ever minted or disbursed: authority merely unreserved
        self.assertAlmostEqual(self.ledger.emitted["human"], 0.0)

        # Expiring twice is refused
        with self.assertRaises(ME.BountyEscrowError):
            self.escrow.expire_bounty(bounty.bounty_id, 4)
        # A returned bounty can never be fulfilled
        with self.assertRaises(ME.BountyEscrowError):
            self.fulfill(bounty, epoch=4)

    def test_posting_an_already_expired_bounty_refused(self):
        with self.assertRaises(ME.BountyEscrowError):
            self.post(expiry=0, epoch=1)

    # -- funding gates ------------------------------------------------------
    def test_f2_refuses_beyond_available_authority(self):
        with self.assertRaises(AuthorityExceededError):
            self.post(amount=60_000_000.0)  # human cap is 50M
        # Reservation-aware: posting 50M then 1 more refuses the second
        big = self.post(amount=50_000_000.0, work_hash=WORK_HASH_2)
        with self.assertRaises(AuthorityExceededError):
            self.post(amount=1.0, work_hash="work:" + "d" * 60)
        # …but after expiry-return the authority is free again
        self.escrow.expire_bounty(big.bounty_id, 99)
        self.post(amount=1.0, work_hash="work:" + "d" * 60)

    def test_f2_refuses_unsigned_amount_and_anonymous_post(self):
        with self.assertRaises(UnknownFigureError):
            self.escrow.bounty_post(
                commissioning_pool="human",
                commissioner_unity_id=COMMISSIONER,
                amount=1000.0,  # bare number -> UNKNOWN
                work_spec_hash=SPEC_HASH, work_manifest_hash=WORK_HASH,
                band="B1", expiry_epoch=5, epoch=1)
        with self.assertRaises(UnityBindingError):
            self.escrow.bounty_post(
                commissioning_pool="human", commissioner_unity_id="  ",
                amount=v(1000.0),
                work_spec_hash=SPEC_HASH, work_manifest_hash=WORK_HASH,
                band="B1", expiry_epoch=5, epoch=1)

    # -- bridge merit: fixed band, explicit ----------------------------------
    def test_bridge_merit_weight_must_be_signed(self):
        bounty = self.post()
        with self.assertRaises(HeldParameterError):
            self.fulfill(bounty, weight=HeldParameter("bridge_premium_band"))
        with self.assertRaises(HeldParameterError):
            self.fulfill(bounty, weight=Figure(25.0, "UNKNOWN"))
        self.assertEqual(self.escrow.get(bounty.bounty_id).status,
                         ME.STATUS_OPEN)
        self.assertAlmostEqual(self.ledger.emitted["human"], 0.0)

    # -- structural absences --------------------------------------------------
    def test_no_pool_to_pool_path_exists(self):
        forbidden = [
            "pool_to_pool", "transfer_pool", "move_between_pools",
            "pool_to_pool_transfer", "mesh_mint", "mint", "emission_authority",
        ]
        for module in (ME, T):
            names = [n.lower() for n in dir(module)]
            found = [f for f in forbidden
                     if any(f in n for n in names)]
            self.assertEqual(found, [],
                             f"{module.__name__} must not contain "
                             f"pool-to-pool/mint machinery: {found}")
        esc = self.escrow
        for attr in ("transfer_pool_to_pool", "move_between_pools", "mint",
                     "emit", "emission_authority"):
            self.assertFalse(hasattr(esc, attr),
                             f"MeshClearing must not expose {attr}")

    def test_escrow_routes_never_mints(self):
        # The only authority movement in F2/F3 is Ledger.disburse against
        # the commissioning pool's cap: machine authority never decreases
        # when a human bounty fulfills, and vice versa.
        b = self.post(pool="human", amount=2500.0)
        auth_before = self.ledger.remaining_authority("machine").value
        self.fulfill(b)
        self.assertAlmostEqual(
            self.ledger.remaining_authority("machine").value, auth_before)
        # F2 itself moves no eFuse at all: reservations are authority-only
        self.assertAlmostEqual(self.ledger.emitted["human"], 2500.0)
        # …and no other pool was touched by the post either
        self.assertAlmostEqual(self.ledger.emitted["machine"], 0.0)

    # -- existing paths unbroken --------------------------------------------
    def test_existing_emission_and_donation_paths_still_work(self):
        # F1 emission path (tokenomics engine) untouched
        r = self.ledger.disburse("human", COMMISSIONER, v(10.0, "MODELED"), 1)
        self.assertEqual(r.kind, "disbursement")
        self.assertAlmostEqual(self.ledger.emitted["human"], 10.0)
        # merit + decay path untouched
        rec = Receipt.build(COMMISSIONER, "merit_accrual",
                            {"work": "x"}, "VERIFIED", 1, "GENESIS")
        self.ledger.accrue_merit(COMMISSIONER, rec, v(100.0))
        self.assertAlmostEqual(
            self.ledger.merit_balance(COMMISSIONER).value, 100.0)
        # donations still yield Honor, never Merit
        _, honor = self.ledger.donate(FULFILLER, v(5.0, "REPORTED"),
                                      "efuse", 1)
        self.assertAlmostEqual(
            self.ledger.merit_balance(FULFILLER).value, 0.0)
        self.assertEqual(honor.unity_id, FULFILLER)


if __name__ == "__main__":
    unittest.main(verbosity=2)

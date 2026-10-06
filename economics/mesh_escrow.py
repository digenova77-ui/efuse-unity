"""
MESH CLEARING — bounty escrow for cross-pool bounties (F2/F3).

Implements TOKENOMICS_5050_MERIT.md §3.3 / §5 flows F2 (bounty post) and F3
(bounty fulfillment) as computable machinery on top of the tokenomics
engine (economics/tokenomics.py).

TESTNET ONLY. Nothing here mints, distributes, or promises value: the eFuse
hard gate stands. Every mutation is receipted; every figure is
provenance-labeled; UNKNOWN never pays.

Structural law — enforced by ABSENCE of machinery, not by policy:
  - The escrow is an ACCOUNTING ZONE, not a pool: it holds NO emission
    authority of its own. MeshClearing has no mint/emit function and no
    authority attribute. F2 *reserves* the commissioning pool's authority;
    F3 *spends* it via Ledger.disburse (the pool pays, in its own coins).
  - No pool-to-pool flow exists. The only cross-boundary path is F2/F3
    through this escrow, both-side receipted. (No pool_to_pool /
    transfer_pool / move_between_pools function exists anywhere here.)
  - The mesh routes, never mints: F3 disburses against the COMMISSIONING
    pool's remaining authority, bounded by its lifetime cap.
  - manifest_hash idempotency (L5): the same work can never claim twice —
    each work_manifest_hash fulfills at most once, escrow-wide.
  - Phantom bridging refused: F3 requires BOTH-SIDE receipts — the
    commissioning side's bounty-post receipt AND the fulfilling side's
    VERIFIED work receipt, linked by bounty_id and work_manifest_hash.
    RELAYED never means DELIVERED.
  - Bridge merit: fixed-band by design (§3.3). The band digit is
    HELD_FOR_DAVID, so the weight is an explicit caller-supplied Figure —
    posted plainly on the fulfillment receipt (no hidden multipliers),
    and refused when unsigned (UNKNOWN) or held.
  - Expiry: an expired bounty returns its reservation to the commissioning
    pool's authority — receipted. The authority never left the pool; the
    escrow releases the hold, it does not send anything.

Primitives reused from tokenomics.py (same package): Ledger (pool
authority, merit book, hash-chained receipt application), Receipt,
Figure, and the refusal error classes. MeshClearing composes the Ledger —
it does not subclass or duplicate it.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass

from tokenomics import (
    POOLS,
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
    _as_figure,
    _canonical,
    _require_pool,
    _require_unity,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class BountyEscrowError(TokenomicsError):
    """A bounty-escrow refusal: bad terms, wrong receipts, wrong state,
    expiry violation. Structural refusals."""


# ---------------------------------------------------------------------------
# Bounty record
# ---------------------------------------------------------------------------
STATUS_OPEN = "OPEN"
STATUS_FULFILLED = "FULFILLED"
STATUS_RETURNED = "RETURNED"


@dataclass(frozen=True)
class Bounty:
    """Immutable terms of a posted bounty, plus its current status.

    amount is a Figure snapshot (value + provenance at post time). band is
    a label carried verbatim — receipt-anchored bounty bands are
    HELD_FOR_DAVID (TOKENOMICS §13.8); the escrow enforces the label, it
    does not bless the numbers.
    """

    bounty_id: str
    commissioning_pool: str
    commissioner_unity_id: str
    amount: Figure
    work_spec_hash: str
    work_manifest_hash: str
    band: str
    expiry_epoch: int
    posted_epoch: int
    post_receipt_id: str
    status: str


# ---------------------------------------------------------------------------
# MeshClearing — the F2/F3 escrow
# ---------------------------------------------------------------------------
class MeshClearing:
    """The Mesh Clearing accounting zone for cross-pool bounties.

    Holds NO emission authority (none exists on this object — verified by
    test: no mint/emit/authority machinery). Keeps per-pool *reservations*
    against the wrapped tokenomics.Ledger's remaining authority, the open
    bounty book, and the escrow-wide fulfilled-manifest set.

    Parameters and returns use tokenomics.Figure (provenance-labeled).
    """

    def __init__(self, ledger=None):
        self._ledger = ledger if ledger is not None else Ledger()
        self._bounties = {}        # bounty_id -> Bounty
        self._claimed_work = set()  # work_manifest_hash -> fulfilled once
        self._reserved = {p: 0.0 for p in POOLS}

    # -- introspection ----------------------------------------------------
    @property
    def ledger(self):
        return self._ledger

    def get(self, bounty_id):
        try:
            return self._bounties[bounty_id]
        except KeyError:
            raise BountyEscrowError(
                f"unknown bounty {bounty_id!r}") from None

    def reserved(self, pool):
        """eFuse currently reserved for OPEN bounties on this pool's authority."""
        _require_pool(pool)
        return self._reserved[pool]

    def available_authority(self, pool):
        """DERIVED: the commissioning pool's remaining authority minus this
        escrow's open reservations. F2 is refused when this cannot cover
        the bounty amount."""
        _require_pool(pool)
        remaining = self._ledger.remaining_authority(pool).value
        return Figure(
            remaining - self._reserved[pool], "DERIVED",
            f"{pool} pool remaining authority minus Mesh Clearing "
            f"reservations ({self._reserved[pool]:,.4f})")

    # -- F2: bounty post --------------------------------------------------
    def bounty_post(self, *, commissioning_pool, commissioner_unity_id,
                    amount, work_spec_hash, work_manifest_hash, band,
                    expiry_epoch, epoch):
        """F2 — commissioning pool -> Mesh Clearing escrow.

        The commissioning pool's emission authority funds the bounty, in
        its own coins: `amount` is RESERVED against the pool's remaining
        authority (authority-only — no pre-funding, nothing minted here).

        Terms: work_spec_hash (the commissioned work's spec), band (the
        receipt-anchored band label, carried verbatim — bands are
        HELD_FOR_DAVID), expiry_epoch (fulfillment must land on or before
        this epoch).

        Returns the posted Bounty. Receipted (kind bounty_post), bound to
        the commissioner's Unity ID — the commissioner's Unity-bound post
        receipt IS the human mandate on the bounty terms.
        """
        _require_pool(commissioning_pool)
        commissioner = _require_unity(commissioner_unity_id)

        a = _as_figure(amount, "bounty amount")
        if isinstance(a, HeldParameter) or a.provenance == "UNKNOWN":
            raise UnknownFigureError(
                "bounty amount is UNKNOWN/unsigned — refusing "
                "(unsigned inputs never pay)")
        if a.value <= 0:
            raise ValueError("bounty amount must be positive")

        for name, h in (("work_spec_hash", work_spec_hash),
                        ("work_manifest_hash", work_manifest_hash)):
            if not isinstance(h, str) or not h.strip():
                raise BountyEscrowError(
                    f"{name} is required — the work must be named to be "
                    "bridged (no anonymous work)")
        if not isinstance(band, str) or not band.strip():
            raise BountyEscrowError("band label is required")
        if not isinstance(expiry_epoch, int) or not isinstance(epoch, int):
            raise ValueError("expiry_epoch and epoch must be integers")
        if expiry_epoch < epoch:
            raise BountyEscrowError(
                f"bounty would post expired (expiry {expiry_epoch} < "
                f"epoch {epoch}) — refusing")

        available = self.available_authority(commissioning_pool).value
        if a.value > available + 1e-9:
            raise AuthorityExceededError(
                f"bounty amount {a.value} exceeds {commissioning_pool} pool "
                f"available authority {available:,.4f} "
                "(remaining authority minus open escrow reservations)")

        bounty_id = hashlib.sha256(_canonical({
            "flow": "F2", "pool": commissioning_pool,
            "commissioner": commissioner,
            "work_spec_hash": work_spec_hash.strip(),
            "work_manifest_hash": work_manifest_hash.strip(),
            "amount": a.value, "band": band.strip(),
            "expiry_epoch": expiry_epoch, "posted_epoch": epoch,
            "nonce": uuid.uuid4().hex,
        })).hexdigest()

        receipt = self._ledger._new_receipt(
            commissioner, "bounty_post",
            {"flow": "F2",
             "bounty_id": bounty_id,
             "commissioning_pool": commissioning_pool,
             "amount": a.value,
             "amount_provenance": a.provenance,
             "work_spec_hash": work_spec_hash.strip(),
             "work_manifest_hash": work_manifest_hash.strip(),
             "band": band.strip(),
             "band_note": ("receipt-anchored bounty bands HELD_FOR_DAVID "
                           "(TOKENOMICS §13.8) — label carried verbatim, "
                           "numbers not blessed here"),
             "expiry_epoch": expiry_epoch,
             "posted_epoch": epoch,
             "commissioner_unity_id": commissioner,
             "escrow_zone": ("Mesh Clearing — accounting zone, no emission "
                             "authority; the commissioning pool's authority "
                             "is reserved, nothing is minted")},
            a.provenance if a.provenance != "UNKNOWN" else "DERIVED",
            epoch)

        self._reserved[commissioning_pool] += a.value
        bounty = Bounty(
            bounty_id=bounty_id,
            commissioning_pool=commissioning_pool,
            commissioner_unity_id=commissioner,
            amount=Figure(a.value, a.provenance,
                          "bounty amount at post time"),
            work_spec_hash=work_spec_hash.strip(),
            work_manifest_hash=work_manifest_hash.strip(),
            band=band.strip(),
            expiry_epoch=expiry_epoch,
            posted_epoch=epoch,
            post_receipt_id=receipt.receipt_id,
            status=STATUS_OPEN,
        )
        self._bounties[bounty_id] = bounty
        return bounty

    # -- F3: bounty fulfillment -------------------------------------------
    def bounty_fulfill(self, *, bounty_id, fulfiller_unity_id,
                       commissioning_receipt, fulfilling_receipt,
                       bridge_merit_weight, epoch):
        """F3 — Mesh Clearing escrow -> fulfiller's Unity ID.

        Gates, in order (structural — every failure refuses, nothing
        partially applies):
          1. the bounty is OPEN and not expired (epoch <= expiry_epoch);
          2. BOTH-SIDE receipts:
             - commissioning_receipt: the F2 bounty_post receipt, bound to
               the commissioner, naming this bounty_id;
             - fulfilling_receipt: a VERIFIED receipt bound to the
               fulfiller, carrying this bounty's work_manifest_hash —
               the countersigned delivery (RELAYED ≠ DELIVERED);
          3. manifest_hash idempotency: the work_manifest_hash was never
             fulfilled before (double-counting refused);
          4. bridge merit weight is an explicit, signed Figure — fixed
             band, posted plainly (HELD/UNKNOWN weight -> refusal);
          5. the commissioning pool's available authority still covers the
             amount.

        On success: the pool disburses `amount` to the fulfiller's Unity
        ID (Ledger.disburse — bounded by the pool's lifetime cap; the mesh
        routes, never mints), bridge merit accrues to the fulfiller via
        the gated fulfilling receipt, and a bounty_fulfill receipt links
        both sides' receipts. Fail-closed ordering: the escrow book is
        only marked AFTER the disbursement and merit accrual succeed.
        """
        bounty = self.get(bounty_id)
        fulfiller = _require_unity(fulfiller_unity_id)
        if not isinstance(epoch, int):
            raise ValueError("epoch must be an integer")

        if bounty.status != STATUS_OPEN:
            raise BountyEscrowError(
                f"bounty {bounty_id[:16]}… is {bounty.status} — "
                "fulfillment refused")
        if epoch > bounty.expiry_epoch:
            raise BountyEscrowError(
                f"bounty expired at epoch {bounty.expiry_epoch} "
                f"(now {epoch}) — fulfillment refused; use expire_bounty "
                "to return the reservation to the commissioning pool")

        self._check_commissioning_receipt(bounty, commissioning_receipt)
        self._check_fulfilling_receipt(bounty, fulfiller, fulfilling_receipt)

        if bounty.work_manifest_hash in self._claimed_work:
            raise DuplicateReceiptError(
                f"work {bounty.work_manifest_hash[:16]}… already fulfilled — "
                "the same work is never counted twice (manifest_hash "
                "idempotency, L5)")

        w = _as_figure(bridge_merit_weight, "bridge merit weight")
        if isinstance(w, HeldParameter) or w.provenance in ("HELD", "UNKNOWN"):
            raise HeldParameterError(
                "bridge merit weight is HELD/UNKNOWN — the bridge premium "
                "band is HELD_FOR_DAVID (TOKENOMICS §13.9); refusing an "
                "unsigned weight (no hidden multipliers)")
        if w.value <= 0:
            raise ValueError("bridge merit weight must be positive")

        available = self.available_authority(bounty.commissioning_pool).value
        if bounty.amount.value > available + 1e-9:
            raise AuthorityExceededError(
                f"bounty amount {bounty.amount.value} exceeds "
                f"{bounty.commissioning_pool} pool available authority "
                f"{available:,.4f}")

        # --- apply: disbursement first (fail-closed; escrow book marked
        # --- only after the pool's own gates clear) ---
        disburse_receipt = self._ledger.disburse(
            bounty.commissioning_pool, fulfiller, bounty.amount, epoch)
        merit_credit = self._ledger.accrue_merit(
            fulfiller, fulfilling_receipt, w)

        self._claimed_work.add(bounty.work_manifest_hash)
        self._reserved[bounty.commissioning_pool] -= bounty.amount.value
        self._bounties[bounty_id] = Bounty(
            **{**bounty.__dict__, "status": STATUS_FULFILLED})

        fulfill_receipt = self._ledger._new_receipt(
            fulfiller, "bounty_fulfill",
            {"flow": "F3",
             "bounty_id": bounty_id,
             "commissioning_pool": bounty.commissioning_pool,
             "fulfiller_unity_id": fulfiller,
             "amount": bounty.amount.value,
             "amount_provenance": bounty.amount.provenance,
             "commissioning_receipt_id": commissioning_receipt.receipt_id,
             "commissioning_manifest_hash":
                 commissioning_receipt.manifest_hash,
             "fulfilling_receipt_id": fulfilling_receipt.receipt_id,
             "fulfilling_manifest_hash": fulfilling_receipt.manifest_hash,
             "work_manifest_hash": bounty.work_manifest_hash,
             "bridge_merit": {
                 "weight": w.value,
                 "provenance": w.provenance,
                 "note": ("fixed band, per TOKENOMICS §3.3 — bridge skims "
                          "refused; the bridger is rewarded for bridging, "
                          "never paid a cut of what crosses. Weight explicit "
                          "and visible; band digit HELD_FOR_DAVID."),
             },
             "disbursement_receipt_id": disburse_receipt.receipt_id,
             "note": ("Both-side receipts linked. Mesh routes, never mints: "
                      "disbursement drew on the commissioning pool's "
                      "emission authority.")},
            "DERIVED", epoch)
        return {
            "bounty_id": bounty_id,
            "fulfiller_unity_id": fulfiller,
            "amount": bounty.amount.value,
            "disbursement_receipt": disburse_receipt,
            "bridge_merit_credit": merit_credit,
            "fulfill_receipt": fulfill_receipt,
        }

    def _check_commissioning_receipt(self, bounty, receipt):
        """The commissioning side's receipt: the F2 bounty_post receipt,
        bound to the commissioner, naming this bounty."""
        if receipt is None:
            raise ReceiptRequiredError(
                "F3 requires the commissioning side's receipt (F2 "
                "bounty_post) — both-side receipts or neither; refusing")
        if not isinstance(receipt, Receipt):
            raise ReceiptRequiredError(
                "commissioning receipt must be a tokenomics Receipt — refusing")
        problems = []
        if receipt.kind != "bounty_post":
            problems.append(
                f"kind must be 'bounty_post', got {receipt.kind!r}")
        if receipt.unity_id != bounty.commissioner_unity_id:
            problems.append(
                "commissioning receipt is not bound to the commissioner's "
                "Unity ID")
        if receipt.detail.get("bounty_id") != bounty.bounty_id:
            problems.append(
                "commissioning receipt does not name this bounty_id")
        if receipt.receipt_id != bounty.post_receipt_id:
            problems.append(
                "commissioning receipt is not this bounty's F2 post receipt")
        if problems:
            raise BountyEscrowError(
                "commissioning receipt refused: " + "; ".join(problems))

    def _check_fulfilling_receipt(self, bounty, fulfiller, receipt):
        """The fulfilling side's receipt: VERIFIED, bound to the fulfiller,
        carrying this bounty's work_manifest_hash — the countersigned
        delivery. RELAYED never means DELIVERED."""
        if receipt is None:
            raise ReceiptRequiredError(
                "F3 requires the fulfilling side's VERIFIED work receipt — "
                "both-side receipts or neither; refusing")
        if not isinstance(receipt, Receipt):
            raise ReceiptRequiredError(
                "fulfilling receipt must be a tokenomics Receipt — refusing")
        problems = []
        if receipt.provenance != "VERIFIED":
            problems.append(
                f"fulfilling receipt is {receipt.provenance}, not VERIFIED — "
                "gated receipts only")
        if receipt.unity_id != fulfiller:
            problems.append(
                "fulfilling receipt is not bound to the fulfiller's Unity ID")
        if receipt.detail.get("work_manifest_hash") != bounty.work_manifest_hash:
            problems.append(
                "fulfilling receipt does not carry this bounty's "
                "work_manifest_hash")
        if problems:
            raise BountyEscrowError(
                "fulfilling receipt refused: " + "; ".join(problems))

    # -- expiry: authority returns to the commissioning pool ---------------
    def expire_bounty(self, bounty_id, current_epoch):
        """Expired bounty -> the reservation returns to the commissioning
        pool's authority, receipted (kind bounty_return).

        The authority never left the pool (F2 only reserved it), so the
        return RELEASES the hold — the escrow sends nothing anywhere.
        Refuses before expiry and on any non-OPEN bounty."""
        bounty = self.get(bounty_id)
        if not isinstance(current_epoch, int):
            raise ValueError("current_epoch must be an integer")
        if bounty.status != STATUS_OPEN:
            raise BountyEscrowError(
                f"bounty {bounty_id[:16]}… is {bounty.status} — nothing to "
                "expire; refusing")
        if current_epoch <= bounty.expiry_epoch:
            raise BountyEscrowError(
                f"bounty not yet expired (expiry {bounty.expiry_epoch}, now "
                f"{current_epoch}) — refusing early return")

        self._reserved[bounty.commissioning_pool] -= bounty.amount.value
        self._bounties[bounty_id] = Bounty(
            **{**bounty.__dict__, "status": STATUS_RETURNED})

        return self._ledger._new_receipt(
            bounty.commissioner_unity_id, "bounty_return",
            {"flow": "F2-expiry-return",
             "bounty_id": bounty_id,
             "commissioning_pool": bounty.commissioning_pool,
             "amount_returned": bounty.amount.value,
             "amount_provenance": bounty.amount.provenance,
             "commissioner_unity_id": bounty.commissioner_unity_id,
             "expired_at_epoch": bounty.expiry_epoch,
             "returned_at_epoch": current_epoch,
             "note": ("Expired bounty: the reservation is released back to "
                      "the commissioning pool's authority. The authority "
                      "never left the pool — the escrow holds no authority "
                      "of its own and sends nothing anywhere.")},
            "DERIVED", current_epoch)


# ---------------------------------------------------------------------------
# What this module deliberately does NOT contain (absence of machinery):
#   - transfer_pool_to_pool / move_between_pools / pool_to_pool_transfer:
#       no pool-to-pool flow — enforced by absence, not by rule
#   - mesh_mint / mesh emission authority: the mesh routes, never mints
#   - accrue_merit_interest / bridge skim (percentage): bridge merit is
#       fixed-band and explicit; skims refused by construction
# A rule can be waived. Missing machinery cannot.
# ---------------------------------------------------------------------------

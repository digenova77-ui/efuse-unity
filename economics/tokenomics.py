"""
TOKENOMICS ENGINE — DCLM-side economic core for the unified WORLD.

Implements ~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md
(DESIGN, predicted not sealed — ED-PREDICT-20261004-TOKENOMICS-V1)
as computable machinery.

TESTNET ONLY. No mainnet paths exist in this module. Nothing here mints,
distributes, or promises value: the eFuse hard gate stands (no minting, no
distribution, no promises until full repeated evidence).

The economy's trinity:
  eFuse = the medium (moves; never bought or sold; pegged to real-world energy)
  Merit = the measure (TRANSFERABLE — David's word, 2026-10-06 ~3:35 AM EDT:
    sold, gifted, transferred between Unity IDs, all receipted. Transfers
    move OWNERSHIP (economic value) only; origin/earned-history fields are
    frozen at accrual and never move with the token; standing keys off
    origin, not balance. Unity-bound, decays per epoch)
  Unity = the member (identity — every movement binds a unity_id)
  Honor = the donation class (never converts to emission)

Standing-gated emission (wired 2026-10-06, CRITICAL-2 closure): emission
weight = f(earned standing) — Ledger.standing()/emission_weights(), read
from merit_history, which transfer_merit never touches. emission_calculator
REQUIRES a standing_source and derives ALL weights from it; a
caller-supplied merit_map is UNTRUSTED input, cross-checked against
standing (exact restatement) and refused on any mismatch. Bought Merit
has zero standing and buys zero emission weight — structurally, not by
comment.

Structural law — enforced by ABSENCE of machinery, not by policy:
  - No pool-to-pool flow exists. The function does not exist.
  - The mesh routes, never mints. No mesh emission authority exists.
  - Merit interest does not exist. No function grows merit without a receipt.
  - No fiat -> eFuse path exists.
  - No pre-funding: emitted balances start at zero; no receipts -> zero
    emission, by construction.
  - The Peg Regulation Reserve is per-pool (human/machine) — never a sixth
    pool — and cannot disburse to members: no such function exists. Its only
    exit is re-injection through the emission gate. Absorb/release are
    receipted (kind "reserve"); the holdback fraction is HELD_FOR_DAVID, so
    the machinery refuses (HeldParameterError) until his digit arrives.

Provenance: every economic figure carries a label from
  REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN
(the same register as dclm/compute.py — mirrored locally so this module
stays dependency-free; test_tokenomics.py asserts the sets are identical).
UNKNOWN never pays, never scores, never emits.

Winter throttle (wired 2026-10-06, gauntlet E16): emission_calculator
accepts an optional winter argument (None | dclm.winter.WinterSignal |
dclm.winter.WinterState). The gradient is evaluated by winter.py's lawful
trigger — no second trigger is invented here. In winter the emission
multiplier slows metered emission continuously (floor EMISSION_FLOOR at
full winter — slowed, never shut down); in summer the multiplier is 1.0
(an exact no-op). Every throttled epoch receipt carries the winter reason
(gradient, label, multiplier, per-signal reasons), sealed in its canonical
hash. Testnet only.

Held parameters (David's digits — see PARAMS.md) are explicit HeldParameter
markers. Any mechanic that needs one REFUSES (raises HeldParameterError)
instead of inventing a digit. Unsigned raw numbers are treated as UNKNOWN.
"""

import base64
import hashlib
import json
import math
import os
import sys
import uuid
from dataclasses import dataclass, field, replace

import wallet  # Ed25519 emission-receipt signing helpers (CRITICAL-4)

# ---------------------------------------------------------------------------
# Provenance register (mirrors dclm/compute.py PROVENANCE_LABELS)
# ---------------------------------------------------------------------------
PROVENANCE_LABELS = frozenset(
    {"REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"}
)

# Parameter standing
PARAM_DECIDED = "DECIDED"
PARAM_HELD = "HELD_FOR_DAVID"

# ---------------------------------------------------------------------------
# Decided constants (ED-DECIDED-20261004-5050-V1)
# ---------------------------------------------------------------------------
LIFETIME_CAP = 100_000_000.0      # lifetime emission cap — a ceiling, never a quota
HUMAN_POOL_CAP = 50_000_000.0     # human pool lifetime emission authority
MACHINE_POOL_CAP = 50_000_000.0   # machine pool lifetime emission authority
POOLS = ("human", "machine")
POOL_CAPS = {"human": HUMAN_POOL_CAP, "machine": MACHINE_POOL_CAP}

DONATION_KINDS = ("efuse", "fiat")


# ---------------------------------------------------------------------------
# Errors — refusals are first-class
# ---------------------------------------------------------------------------
class TokenomicsError(Exception):
    """Base for all tokenomics refusals."""


class HeldParameterError(TokenomicsError):
    """A mechanic needs a parameter David has not decided. Refusing."""


class UnknownFigureError(TokenomicsError):
    """An economic figure is UNKNOWN (or unsigned) where a decided figure
    is required. UNKNOWN never pays, never scores — refusing."""


class UnityBindingError(TokenomicsError):
    """A movement without a valid unity_id. No anonymous flows."""


class ReceiptRequiredError(TokenomicsError):
    """Merit (or gated movement) attempted without a verified receipt.
    No receipt, no coins."""


class DuplicateReceiptError(TokenomicsError):
    """A manifest_hash applied twice. Idempotency enforced (L5)."""


class NonTransferableError(TokenomicsError):
    """Transfer attempted on a non-transferable class (Unity/Honor).

    NOTE (2026-10-06): Merit is NO LONGER in this set. David's word,
    2026-10-06 ~3:35 AM EDT, made Merit transferable — the old
    non-transferable Merit law is SUPERSEDED (DECISIONS.md §13). This
    error now covers only the identity-bound classes (Unity, Honor)."""


class HonorConversionRefused(TokenomicsError):
    """Honor -> emission attempted. The gift is the gift; refusing."""


class DonorExclusionError(TokenomicsError):
    """The Core Cause Lock is one-way per donor: donated eFuse is never
    re-emitted to the same member."""


class UntrustedMeritMapError(TokenomicsError):
    """A caller-supplied merit map failed the standing cross-check.

    Emission weights derive SOLELY from earned standing (origin-based
    accrual history, which never moves on transfer). A caller-supplied
    merit map is UNTRUSTED input: it must restate each identity's
    standing EXACTLY (same identities, same values, strong provenance)
    or the emission is REFUSED — the map is never read for weights.
    Bought Merit (transferred balances) cannot survive this check:
    a buyer's standing is 0, so any positive presented weight mismatches
    and refuses."""


class AuthorityExceededError(TokenomicsError):
    """A disbursement would exceed the pool's remaining emission authority."""


class MeritTransferAuthError(TokenomicsError):
    """A Merit transfer was attempted without a valid sender authorization.

    The public Unity ID alone authorizes nothing: the sender's registered
    transfer key must sign the exact transfer intent (from/to/amount/
    reason/nonce), and the nonce must be fresh. No auth, an unregistered
    sender, a key mismatch, a body mismatch, a failed signature, or a
    replayed nonce -> refused, code not comment. (S1b closure of the S1
    residual: Ledger.transfer_merit had the same keyless drain as the
    canonical path.)"""


# ---------------------------------------------------------------------------
# Parameters — the decided-vs-held split, in code
# ---------------------------------------------------------------------------
class HeldParameter:
    """A parameter David has not decided. Carries a name and a note —
    never a usable value. Passing one where a decided figure is required
    raises HeldParameterError."""

    def __init__(self, name, note=""):
        self.name = name
        self.note = note

    def __repr__(self):
        return f"HeldParameter({self.name!r} — HELD_FOR_DAVID)"


@dataclass(frozen=True)
class Parameter:
    name: str
    status: str  # DECIDED | HELD_FOR_DAVID
    value: object  # None when held
    note: str = ""


def _P(name, status, value, note=""):
    return Parameter(name=name, status=status, value=value, note=note)


PARAMS = {
    # ---- DECIDED (ED-DECIDED-20261004-5050-V1; David's law) ----
    "lifetime_cap": _P("lifetime_cap", PARAM_DECIDED, LIFETIME_CAP,
        "100M eFuse lifetime emission cap. A ceiling, never a quota, never a treasury."),
    "human_pool_cap": _P("human_pool_cap", PARAM_DECIDED, HUMAN_POOL_CAP,
        "50M lifetime emission authority through the human pool's merit-gated process."),
    "machine_pool_cap": _P("machine_pool_cap", PARAM_DECIDED, MACHINE_POOL_CAP,
        "50M lifetime emission authority through the machine pool's merit-gated process."),
    "one_merged_rail": _P("one_merged_rail", PARAM_DECIDED, True,
        "One merged 100M rail; the pool boundary (not a rail boundary) is the gated frontier."),
    "no_pre_funding": _P("no_pre_funding", PARAM_DECIDED, True,
        "Coins come into existence only against gated receipts, over epochs. No receipts -> zero emission."),
    "no_pool_to_pool": _P("no_pool_to_pool", PARAM_DECIDED, True,
        "No flow exists between the Human and Machine Emission Pools — enforced by absence of machinery."),
    "mesh_never_mints": _P("mesh_never_mints", PARAM_DECIDED, True,
        "The mesh is a zone, not a pool: it routes, never mints. No third emission authority."),
    "merit_transferable": _P("merit_transferable", PARAM_DECIDED, True,
        "Merit IS transferable — sold, gifted, transferred between Unity "
        "IDs, all receipted (David's word, 2026-10-06 ~3:35 AM EDT). The "
        "old 'merit_non_transferable' law is SUPERSEDED — recorded "
        "explicitly here and in DECISIONS.md §13, never silently edited "
        "away. Transfers move OWNERSHIP (economic value) only: origin/ "
        "earned-history fields are frozen at accrual and never move with "
        "the token; standing keys off origin, not balance. A buyer gains "
        "economic value and ZERO standing — by construction. Merit "
        "interest remains refused: transfers are not interest."),
    "honor_never_converts": _P("honor_never_converts", PARAM_DECIDED, True,
        "Honor never converts to emission. No path from fiat to eFuse — not direct, not indirect, not clever."),
    "unity_binding": _P("unity_binding", PARAM_DECIDED, True,
        "Every eFuse movement and every Merit/Honor accrual binds a Unity ID. No anonymous flows."),
    "merit_interest_refused": _P("merit_interest_refused", PARAM_DECIDED, True,
        "Merit never earns merit. No staking, no yield. Merit grows only through new gated receipts."),
    # ---- HELD_FOR_DAVID (his digits / his word — never invented here) ----
    "peg_ratio_E": _P("peg_ratio_E", PARAM_HELD, None,
        "Energy units per eFuse (1 eFuse ≡ E). The most load-bearing digit: nothing emits without it."),
    "merit_decay_rate": _P("merit_decay_rate", PARAM_HELD, None,
        "Per-epoch merit decay rate. Principle is law (fidelity is current); the digit is his."),
    "epoch_length": _P("epoch_length", PARAM_HELD, None,
        "Epoch length. Direction: conservative = short."),
    "reserve_holdback_fraction": _P("reserve_holdback_fraction", PARAM_HELD, None,
        "Peg Regulation Reserve holdback fraction per epoch (within the originating pool's authority). "
        "Machinery is built and gated: emission_calculator/emission_close absorb & release "
        "per-pool (receipted kind \"reserve\"; the Reserve cannot disburse to members — no such "
        "function exists) but REFUSE (HeldParameterError) until David's digit arrives. "
        "Testnet what-if runs on an explicit MODELED fraction."),
    "tier_weights": _P("tier_weights", PARAM_HELD, None,
        "friend / good friend / family / verified kin merit weights. Verified depth only; self-claimed depth earns zero."),
    "bridge_premium_band": _P("bridge_premium_band", PARAM_HELD, None,
        "Fixed premium band for cross-side (bridge) merit. Fixed-band, never a percentage — bridge skims refused."),
    "corroboration_thresholds": _P("corroboration_thresholds", PARAM_HELD, None,
        "Corroboration thresholds. Direction: conservative = high."),
    "bounty_band_floors_widths": _P("bounty_band_floors_widths", PARAM_HELD, None,
        "Receipt-anchored bounty band floors and widths. Direction: conservative = narrow bands, firm floors."),
    "ring_depth_factor": _P("ring_depth_factor", PARAM_HELD, None,
        "Ring-depth merit amplification factor (verified depth only)."),
    "bridge_eligibility_threshold": _P("bridge_eligibility_threshold", PARAM_HELD, None,
        "Bridge-merit threshold for Zone M entry (posting/fulfilling cross-pool bounties)."),
    "machine_proof_of_energy_params": _P("machine_proof_of_energy_params", PARAM_HELD, None,
        "Machine-lane proof-of-energy receipt class parameters (candidate class)."),
    "honor_class_names": _P("honor_class_names", PARAM_HELD, None,
        "Honor class names and tiers. Naming is his word as much as digits."),
    "merit_definition": _P("merit_definition", PARAM_HELD, None,
        "Merit's precise definition ('protocol-fidelity' — his word to confirm). "
        "Mechanics are definition-agnostic by construction."),
}


def param_status(name):
    """Return the standing of a parameter: DECIDED | HELD_FOR_DAVID."""
    try:
        return PARAMS[name].status
    except KeyError:
        raise TokenomicsError(f"unknown parameter {name!r}") from None


def require_decided(name):
    """Return the parameter's value, or refuse if David hasn't decided it."""
    p = PARAMS.get(name)
    if p is None:
        raise TokenomicsError(f"unknown parameter {name!r}")
    if p.status == PARAM_HELD:
        raise HeldParameterError(
            f"parameter {name!r} is HELD_FOR_DAVID — refusing to invent it"
        )
    return p.value


# ---------------------------------------------------------------------------
# Figures — every economic figure carries provenance
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Figure:
    """An economic figure with its provenance label. No unsigned claims:
    a bare number passed into the engine is treated as UNKNOWN."""

    value: float
    provenance: str
    note: str = ""

    def __post_init__(self):
        if self.provenance not in PROVENANCE_LABELS:
            raise ValueError(f"invalid provenance {self.provenance!r}")
        if not isinstance(self.value, (int, float)):
            raise ValueError("Figure.value must be numeric")


def _as_figure(x, name):
    """Coerce input to a Figure. Bare numbers are UNSIGNED -> UNKNOWN.
    HeldParameter passes through untouched (callers must refuse it)."""
    if isinstance(x, HeldParameter):
        return x
    if isinstance(x, Figure):
        return x
    if isinstance(x, (int, float)):
        return Figure(float(x), "UNKNOWN",
                      f"unsigned input for {name} treated as UNKNOWN — never pays")
    raise TypeError(f"{name} must be a Figure, HeldParameter, or number")


def _require_unity(unity_id):
    """Every movement binds a Unity ID. No anonymous flows — by signature
    (required argument) AND by runtime check."""
    if not isinstance(unity_id, str) or not unity_id.strip():
        raise UnityBindingError(
            "unity_id is required — no anonymous flows exist in this engine"
        )
    return unity_id.strip()


def _require_pool(pool):
    if pool not in POOLS:
        raise ValueError(
            f"unknown pool {pool!r} — pools are 'human'/'machine' (DECIDED 50/50)"
        )
    return pool


def _reserve_identity(pool):
    """Pool-scoped identity bound to Peg Regulation Reserve receipts.

    Reserve movements are pool-level, not member-level: they bind the pool's
    reserve identity — explicit and auditable, never a member, never blank.
    Released funds reach members ONLY through the emission gate's per-member
    shares (member-bound disburse receipts). Internal does not mean invisible."""
    _require_pool(pool)
    return f"pool:{pool}:peg-regulation-reserve"


def _require_holdback_fraction(holdback_fraction):
    """Validate the Peg Regulation Reserve holdback fraction.

    None -> None: the caller did not engage the Reserve. The result is the
      labeled zero (reserve_held = 0) — "not engaged", not "unset".
    HeldParameter / held PARAMS entry / UNKNOWN Figure -> HeldParameterError:
      the fraction is David's digit; the machinery refuses to invent one and
      refuses to silently pass through.
    Otherwise the Figure must lie in [0, 1): a holdback of 1.0 would freeze
      the pool's emission outright, which is a different mechanic.
    """
    if holdback_fraction is None:
        return None
    if isinstance(holdback_fraction, HeldParameter):
        raise HeldParameterError(
            f"reserve_holdback_fraction is HELD_FOR_DAVID "
            f"({holdback_fraction.name}) — refusing to invent it"
        )
    if isinstance(holdback_fraction, Parameter) and \
            holdback_fraction.status == PARAM_HELD:
        raise HeldParameterError(
            f"parameter {holdback_fraction.name!r} is HELD_FOR_DAVID — "
            "the Reserve cannot operate without David's digit; refusing"
        )
    fig = _as_figure(holdback_fraction, "reserve_holdback_fraction")
    if isinstance(fig, HeldParameter) or fig.provenance in ("HELD", "UNKNOWN"):
        raise HeldParameterError(
            "reserve_holdback_fraction is unsigned/unknown — "
            "the Reserve never runs on an undecided digit; refusing"
        )
    if not (0.0 <= fig.value < 1.0):
        raise ValueError("reserve_holdback_fraction must be in [0, 1)")
    return fig


def _require_release_amount(reserve_release):
    """Validate a Peg Regulation Reserve release request.

    None -> None: no release requested.
    HeldParameter -> HeldParameterError: refusing an undecided release.
    UNKNOWN Figure -> UnknownFigureError: UNKNOWN never pays, never releases.
    Negative -> ValueError. Otherwise the Figure (the caller decides the
    amount with its provenance; MODELED runs labeled on testnet)."""
    if reserve_release is None:
        return None
    if isinstance(reserve_release, HeldParameter):
        raise HeldParameterError(
            "reserve_release amount is HELD/unsigned — "
            "refusing an undecided release"
        )
    fig = _as_figure(reserve_release, "reserve_release")
    if isinstance(fig, HeldParameter) or fig.provenance in ("HELD", "UNKNOWN"):
        raise UnknownFigureError(
            "reserve_release amount is UNKNOWN/unsigned — "
            "UNKNOWN never pays, never releases; refusing"
        )
    if fig.value < 0:
        raise ValueError("reserve_release cannot be negative")
    return fig


def _require_reserve_balance(reserve_balance):
    """The pool's current Reserve balance, for calibrating a release.

    None -> zero (DERIVED): no balance supplied, nothing to release against.
    UNKNOWN -> UnknownFigureError: a release cannot be calibrated against an
    unknown balance. Negative -> ValueError (invariant violation)."""
    if reserve_balance is None:
        return Figure(0.0, "DERIVED",
                      "no reserve balance supplied — treated as zero")
    fig = _as_figure(reserve_balance, "reserve_balance")
    if isinstance(fig, HeldParameter) or fig.provenance in ("HELD", "UNKNOWN"):
        raise UnknownFigureError(
            "reserve_balance is UNKNOWN — a release cannot be calibrated "
            "against an unknown balance; refusing"
        )
    if fig.value < 0:
        raise ValueError("reserve_balance cannot be negative")
    return fig


# ---------------------------------------------------------------------------
# Token classes — the economy's trinity (+ Honor)
# ---------------------------------------------------------------------------
class Token:
    """Base token class. Metadata provenance is MODELED: these classes
    implement ED-PREDICT-20261004-TOKENOMICS-V1, which is DESIGN (predicted,
    not sealed) — the metadata is a model of the design, not a sealed fact."""

    name = "Token"
    symbol = "?"
    kind = "?"            # medium | measure | member | donation
    transferable = False
    blurb = ""

    def describe(self):
        return {
            "name": self.name,
            "symbol": self.symbol,
            "kind": self.kind,
            "transferable": self.transferable,
            "blurb": self.blurb,
            "provenance": "MODELED",
            "note": "Implements ED-PREDICT-20261004-TOKENOMICS-V1 (DESIGN, not sealed).",
        }

    def transfer(self, *args, **kwargs):
        raise NonTransferableError(
            f"{self.name} is non-transferable — it is not a currency"
        )


class EFuse(Token):
    """The medium. Pegged to real-world energy. Never bought or sold —
    no market, no trading, no exchange machinery exists. Movements happen
    only through ledger functions (emission/disbursement, donation,
    peg-regulation), never through direct transfer."""

    name = "eFuse"
    symbol = "eF"
    kind = "medium"
    transferable = True  # moves along the rail — but never bought/sold
    blurb = ("The currency that moves. 1 eFuse ≡ E real-world energy units "
             "(E HELD_FOR_DAVID). Never bought or sold by anyone.")

    def transfer(self, *args, **kwargs):
        raise TokenomicsError(
            "eFuse moves only through ledger movement functions "
            "(disburse/donate/cause_disburse) — no direct transfer, no market, "
            "no exchange. Never bought or sold."
        )


class Merit(Token):
    """The measure. TRANSFERABLE — David's word, 2026-10-06 ~3:35 AM EDT
    (LAW), superseding the earlier non-transferable law (recorded
    explicitly in DECISIONS.md §13, never silently edited away).

    Receipt-anchored, Unity-bound, decays per epoch. The structural
    distinction, shared with the canonical path
    (dclm/token_engine.py::Tokenizer.merit_transfer — the SOLE legal
    Merit ownership-transfer path; economics/wallet.py::transfer_merit
    delegates to it):
      * a transfer moves OWNERSHIP (economic value) between Unity IDs —
        sold, gifted, transferred, all receipted;
      * origin/earned-history fields are frozen at accrual and NEVER move
        with the token;
      * standing keys off origin, not balance — a buyer gains economic
        value and ZERO standing, by construction.
    Merit wins the work; merit never earns merit. (Transfers are not
    interest — no function grows merit without a receipt.)"""

    name = "Merit"
    symbol = "M"
    kind = "measure"
    transferable = True
    blurb = ("Protocol-fidelity measure (precise definition: David's word, HELD). "
             "TRANSFERABLE (his word, 2026-10-06): ownership moves between "
             "Unity IDs; origin frozen at accrual; standing never moves on "
             "transfer. Unity-bound, decays per epoch. "
             "Merit interest refused by construction.")

    def transfer(self, *args, **kwargs):
        # Same pattern as EFuse.transfer: transferable = True as the
        # class flag (it moves), but no DIRECT class-level transfer
        # machinery exists here — that is absence, not policy. Merit
        # moves ONLY through the canonical receipted path; this refusal
        # names that path rather than silently blocking.
        raise TokenomicsError(
            "Merit moves only through the canonical receipted transfer "
            "path: dclm/token_engine.py::Tokenizer.merit_transfer (the "
            "SOLE legal Merit ownership-transfer path) or "
            "economics/wallet.py::transfer_merit, which delegates to it, "
            "or Ledger.transfer_merit for this module's receipted "
            "ownership ledger (sender-authorized: the sender's "
            "registered transfer key must sign the transfer intent). "
            "No direct class-level transfer exists. "
            "Transfers move OWNERSHIP (economic value) only — origin/ "
            "earned-history fields are frozen at accrual and never move "
            "with the token; standing keys off origin, not balance."
        )


class Unity(Token):
    """The member. Identity — the protocol, kin-binding. Every eFuse
    movement and every Merit/Honor accrual binds a Unity ID."""

    name = "Unity"
    symbol = "U"
    kind = "member"
    transferable = False
    blurb = ("Identity. eFuse and Merit are bound together by Unity — "
             "no anonymous flows.")


class Honor(Token):
    """The donation class. Public, named, permanent, Unity-bound,
    non-transferable — and it NEVER converts to emission."""

    name = "Honor"
    symbol = "H"
    kind = "donation"
    transferable = False
    converts_to_emission = False
    blurb = ("The reward for giving: recognition, legacy, Eden itself. "
             "Never decays. Never converts to emission — the gift is the gift.")

    def redeem_for_emission(self, *args, **kwargs):
        # The bright line, named so nobody re-proposes it quietly later.
        raise HonorConversionRefused(
            "Honor never converts to emission (§7). Donations accrue Honor, "
            "never Merit; there is no path from fiat to eFuse."
        )


# ---------------------------------------------------------------------------
# Receipts — every mutation needs one; idempotent via manifest_hash
# ---------------------------------------------------------------------------
RECEIPT_KINDS = frozenset({
    "merit_accrual", "emission", "disbursement", "donation", "honor_accrual",
    "mesh_route", "reserve", "decay", "cause_disbursement",
    # F2/F3 bounty escrow (Mesh Clearing — economics/mesh_escrow.py):
    #   bounty_post    — F2: commissioning pool -> Mesh Clearing escrow
    #   bounty_fulfill — F3: escrow -> fulfiller's Unity ID (both-side receipts)
    #   bounty_return  — expired bounty: reservation released back to the
    #                    commissioning pool's authority (the escrow holds none)
    "bounty_post", "bounty_fulfill", "bounty_return",
    # Merit transfer (ownership-only; origin is never carried — see
    # Ledger.transfer_merit and the canonical path in dclm/token_engine.py):
    "merit_transfer",
    # Interception (the first lawful exit — economics/interception.py):
    #   order_applied / order_released / order_expired /
    #   movement_refused / unlawful_order_refused — the order itself is
    #   receipted here, in the main chain, with its authority proof.
    "interception",
    # Epoch close (the epoch runner's seal — economics/epoch_runner.py):
    # one per closed epoch: per-pool emission/disbursement totals, decay
    # applied, peg-check verdict, winter states, reserve movements, and the
    # state digest. The chain IS the closed-epoch record (idempotency for
    # the autonomous runner, gauntlet PERPETUITY I-3).
    "epoch_close",
})


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class Receipt:
    """A receipted movement. manifest_hash = sha256 over the canonical
    content (excluding receipt_id) — the same work can never be receipted
    twice. prev_hash chains receipts for tamper-evidence."""

    receipt_id: str
    manifest_hash: str
    unity_id: str
    kind: str
    detail: dict
    provenance: str
    epoch: int | None
    prev_hash: str
    # Emission-authority binding (CRITICAL-4): on "disbursement" receipts
    # (the emission authorization), the lawful emitter's Ed25519 signature
    # over the canonical receipt body + the authority key_id. Empty unless
    # the issuing Ledger signed the receipt via sign_disbursement_receipt.
    emitter_signature: str = ""
    emitter_key_id: str = ""

    @classmethod
    def build(cls, unity_id, kind, detail, provenance, epoch, prev_hash):
        _require_unity(unity_id)
        if kind not in RECEIPT_KINDS:
            raise ValueError(f"unknown receipt kind {kind!r}")
        if provenance not in PROVENANCE_LABELS:
            raise ValueError(f"invalid provenance {provenance!r}")
        body = {
            "unity_id": unity_id.strip(),
            "kind": kind,
            "detail": detail,
            "provenance": provenance,
            "epoch": epoch,
            "prev_hash": prev_hash,
        }
        manifest = hashlib.sha256(_canonical(body)).hexdigest()
        return cls(
            receipt_id=uuid.uuid4().hex,
            manifest_hash=manifest,
            unity_id=body["unity_id"],
            kind=kind,
            detail=detail,
            provenance=provenance,
            epoch=epoch,
            prev_hash=prev_hash,
        )


@dataclass(frozen=True)
class MeritCredit:
    unity_id: str
    amount: Figure
    receipt_id: str
    epoch: int | None


@dataclass(frozen=True)
class HonorCredit:
    unity_id: str
    receipt_id: str
    class_name: str | None  # honor class names HELD_FOR_DAVID
    provenance: str
    note: str = ""


# ---------------------------------------------------------------------------
# Winter throttle — dclm/winter.py is the LAWFUL SOURCE (gauntlet E16 wire)
#
# Winter mode is built standalone in dclm/winter.py: the trigger is a
# continuous gradient 0.0 (full summer) -> 1.0 (full winter) evaluated by
# winter.evaluate_trigger over a winter.WinterSignal (peg deviation,
# real-economy activity, declared+verified crisis). The throttle is
# winter.emission_multiplier(gradient): 1.0 at full summer, EMISSION_FLOOR
# at full winter — slowed, never shut down.
#
# This module wires TO it, never around it:
#   - the trigger state comes only from winter.evaluate_trigger (via a
#     WinterSignal) or from a caller-supplied WinterState. No second
#     trigger is invented here: a raw gradient, a dict, or any other
#     guess is REFUSED.
#   - winter=None (or an unreadable signal) -> UNKNOWN never PASS ->
#     SUMMER, gradient 0.0, multiplier 1.0: unchanged behavior.
#   - every throttled epoch receipt carries the winter reason (gradient,
#     label, multiplier, per-signal reasons) sealed in its canonical hash.
# ---------------------------------------------------------------------------
_DCLM_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "dclm"))

_winter_module_cached = None


def _winter_module():
    """The lawful winter source: dclm/winter.py.

    Imported lazily so this module stays importable standalone; the import
    happens once and fails closed at compute time — a missing winter
    module refuses emission computation rather than silently running
    unthrottled."""
    global _winter_module_cached
    if _winter_module_cached is None:
        if _DCLM_DIR not in sys.path:
            sys.path.insert(0, _DCLM_DIR)
        try:
            import winter as _w
        except ImportError as exc:
            raise TokenomicsError(
                "winter throttle unavailable: dclm/winter.py could not be "
                f"imported ({exc}) — refusing to compute emission without "
                "the lawful throttle source"
            ) from exc
        _winter_module_cached = _w
    return _winter_module_cached


def _resolve_winter(winter):
    """Resolve the winter throttle input to (WinterState, multiplier).

    Accepted inputs:
      None                 — no signal read: evaluate_trigger on an empty
                             WinterSignal. UNKNOWN never PASS -> SUMMER,
                             gradient 0.0, multiplier 1.0 (no-op).
      winter.WinterSignal  — evaluated via winter.evaluate_trigger, the
                             lawful trigger.
      winter.WinterState   — used as-is (an already-evaluated state).

    Anything else is REFUSED: the trigger state comes from dclm/winter.py
    or not at all. No second trigger is invented here.
    """
    W = _winter_module()
    if winter is None:
        state = W.evaluate_trigger(W.WinterSignal())
    elif isinstance(winter, W.WinterState):
        state = winter
    elif isinstance(winter, W.WinterSignal):
        state = W.evaluate_trigger(winter)
    else:
        raise TokenomicsError(
            "winter must be None, a winter.WinterSignal, or a "
            f"winter.WinterState — got {type(winter).__name__!r}. The "
            "trigger state comes from dclm/winter.py's lawful source; "
            "no second trigger is invented here."
        )
    return state, W.emission_multiplier(state.gradient)


@dataclass
class EpochEmission:
    """Computed eFuse emission for one pool for one epoch.

    The winter fields receipt the throttle: when the winter gradient
    slows emission, the receipt carries the gradient, the label, the
    applied multiplier, and the per-signal winter reasons — sealed in
    canonical_sha256 alongside the emission figures, so the receipt shows
    WHY emission was reduced."""
    pool: str
    per_member: dict          # unity_id -> Figure (eFuse)
    total: Figure
    excluded: dict            # unity_id -> provenance that disqualified it
    authority_cap_applied: bool
    reserve_held: Figure      # 0/labeled when the Reserve is not engaged
    reserve_released: Figure  # 0/labeled when no release; re-injected via the same gate
    provenance: str
    note: str
    winter_gradient: float = 0.0
    winter_label: str = "SUMMER"
    winter_multiplier: float = 1.0
    winter_reasons: tuple = ()
    winter_provenance: str = "DERIVED"
    canonical_sha256: str = field(init=False)

    def __post_init__(self):
        if self.provenance not in PROVENANCE_LABELS:
            raise ValueError(f"invalid provenance {self.provenance!r}")
        if self.winter_provenance not in PROVENANCE_LABELS:
            raise ValueError(
                f"invalid winter provenance {self.winter_provenance!r}")
        body = {
            "pool": self.pool,
            "per_member": {u: {"value": f.value, "provenance": f.provenance}
                           for u, f in self.per_member.items()},
            "total": {"value": self.total.value,
                      "provenance": self.total.provenance},
            "excluded": self.excluded,
            "authority_cap_applied": self.authority_cap_applied,
            "reserve_held": {"value": self.reserve_held.value,
                             "provenance": self.reserve_held.provenance},
            "reserve_released": {"value": self.reserve_released.value,
                                 "provenance": self.reserve_released.provenance},
            "winter": {
                "gradient": self.winter_gradient,
                "label": self.winter_label,
                "multiplier": self.winter_multiplier,
                "reasons": list(self.winter_reasons),
                "provenance": self.winter_provenance,
            },
            "provenance": self.provenance,
        }
        self.canonical_sha256 = hashlib.sha256(_canonical(body)).hexdigest()


# ---------------------------------------------------------------------------
# Standing-gated emission (CRITICAL-2 closure, 2026-10-06).
#
# The purity law: emission weight = f(earned standing), where earned
# standing comes from origin records that never move. Token balance
# (which CAN be bought) has ZERO influence on emission weight.
#
# The trust boundary is structural, not a comment:
#   - emission_calculator REQUIRES a standing_source and derives ALL
#     emission weights from it. Without one it REFUSES — a
#     caller-supplied merit map alone never drives emission.
#   - a caller-supplied merit_map is UNTRUSTED input: _cross_check_merit_map
#     verifies it restates standing EXACTLY (same identities, same
#     values within tolerance, strong provenance) and REFUSES on any
#     mismatch. The map is NEVER read for weights — the trusted
#     standing figures are used instead.
#   - Ledger.standing()/emission_weights() read merit_history only.
#     transfer_merit never touches merit_history (ownership moves,
#     origin never does), so bought Merit structurally cannot buy
#     emission weight.
# ---------------------------------------------------------------------------
_STANDING_WEIGHT_PROVENANCE = ("VERIFIED", "DERIVED")
_STANDING_WEIGHT_NOTE = (
    "emission weight = earned standing (origin-based accrual history); "
    "a caller-supplied merit map is cross-checked against standing and "
    "never read for weights — bought Merit buys zero emission weight")


def _resolve_standing_weights(standing_source):
    """Resolve the TRUSTED emission weight source to {unity_id: Figure}.

    Accepted:
      None                    -> REFUSE. Emission never runs on a
                                 caller-supplied map alone.
      Ledger (has emission_weights) -> its emission_weights() — earned
                                 standing, DERIVED from merit_history.
      dict {unity_id: Figure} -> validated as stated standing: every
                                 entry must be a Figure of strong
                                 provenance (VERIFIED/DERIVED) and
                                 non-negative. UNKNOWN/HELD standing is
                                 refused — standing is earned history,
                                 never an unsigned claim.
    Anything else (including a bare callable, which cannot enumerate
    identities) is REFUSED."""
    if standing_source is None:
        raise TokenomicsError(
            "emission requires a standing source — a caller-supplied "
            "merit map alone is UNTRUSTED and never drives emission "
            "weights. Pass a Ledger (standing derived from its "
            "merit_history) or an explicit {unity_id: Figure} standing "
            "map of VERIFIED/DERIVED provenance.")
    if hasattr(standing_source, "emission_weights"):
        return standing_source.emission_weights()
    if isinstance(standing_source, dict):
        weights = {}
        for uid, w in standing_source.items():
            _require_unity(uid)
            fig = _as_figure(w, f"standing[{uid}]")
            if isinstance(fig, HeldParameter) \
                    or fig.provenance not in _STANDING_WEIGHT_PROVENANCE:
                raise TokenomicsError(
                    f"standing source entry for {uid!r} has provenance "
                    f"{getattr(fig, 'provenance', fig)!r} — standing is "
                    "earned history (VERIFIED/DERIVED only); refusing an "
                    "unsigned/unknown standing claim")
            if fig.value < 0:
                raise ValueError(
                    f"standing for {uid!r} cannot be negative")
            weights[uid] = fig
        return weights
    raise TokenomicsError(
        "standing_source must be a Ledger or a {unity_id: Figure} map — "
        f"got {type(standing_source).__name__!r}; refusing")


def _cross_check_merit_map(merit_map, weights, where):
    """Cross-check UNTRUSTED caller input against trusted standing weights.

    Every entry must restate standing EXACTLY: the identity must be
    Unity-bound, the entry a Figure of strong provenance
    (VERIFIED/DERIVED), and its value must equal the identity's standing
    within tolerance. Any mismatch — an inflated bought balance, an
    UNKNOWN claim, a stranger presenting weight — raises
    UntrustedMeritMapError and the emission is REFUSED.

    Returns the TRUSTED weights for exactly the map's identities
    (uniform DERIVED standing figures) — the map itself is never read
    for weights. A caller may scope the map to a roster (subset of
    earners — e.g. a pool's members); each scoped weight is still forced
    to equal that identity's standing."""
    if not isinstance(merit_map, dict):
        raise UntrustedMeritMapError(
            f"{where}: merit_map must be a {{unity_id: Figure}} map or "
            "None — refusing untrusted input of unexpected shape")
    trusted = {}
    for uid, m in merit_map.items():
        _require_unity(uid)
        fig = _as_figure(m, f"merit_map[{uid}]")
        if isinstance(fig, HeldParameter) \
                or fig.provenance not in _STANDING_WEIGHT_PROVENANCE:
            raise UntrustedMeritMapError(
                f"{where}: merit_map[{uid!r}] carries provenance "
                f"{getattr(fig, 'provenance', fig)!r} — the map must "
                "restate earned standing (VERIFIED/DERIVED); refusing")
        expected = weights.get(uid, Figure(
            0.0, "DERIVED",
            "no earned standing — the merit gate excludes zero weight"))
        if not math.isclose(fig.value, expected.value,
                            rel_tol=1e-9, abs_tol=1e-12):
            raise UntrustedMeritMapError(
                f"{where}: merit_map[{uid!r}] presents {fig.value} but "
                f"earned standing is {expected.value} — bought/transferred "
                "Merit buys ZERO emission weight; refusing")
        trusted[uid] = Figure(expected.value, "DERIVED",
                              _STANDING_WEIGHT_NOTE)
    return trusted


# ---------------------------------------------------------------------------
# emission_calculator — merit-gated, peg-calibrated, authority-bounded
# ---------------------------------------------------------------------------
def emission_calculator(pool, merit_map=None, peg_ratio=None,
                        remaining_authority=None, winter=None,
                        holdback_fraction=None, reserve_release=None,
                        reserve_balance=None, standing_source=None):
    """Compute eFuse emission for one pool for one epoch.

    pool               — "human" | "machine" (DECIDED 50/50)
    merit_map          — UNTRUSTED caller input ({unity_id: Figure} or
                         None). NEVER read for weights: it is
                         cross-checked against the trusted standing
                         weights (exact restatement — same identities,
                         same values, strong provenance) and any
                         mismatch REFUSES (UntrustedMeritMapError).
                         None means "no caller map" — weights come from
                         the standing source alone. A caller may scope
                         the map to a roster (subset of earners, e.g. a
                         pool's members); each scoped weight is still
                         forced to equal that identity's standing.
    standing_source    — REQUIRED: the trusted weight source — a Ledger
                         (standing derived from its merit_history) or an
                         explicit {unity_id: Figure} standing map of
                         VERIFIED/DERIVED provenance. ALL emission
                         weights derive from this source. None ->
                         TokenomicsError: emission never runs on a
                         caller-supplied map alone.
    peg_ratio          — Figure (1 eFuse ≡ E energy units). HELD/UNKNOWN ->
                         HeldParameterError: E is David's digit; nothing
                         emits without it. MODELED -> runs, outputs MODELED.
    remaining_authority— Figure of the pool's remaining lifetime authority.
                         UNKNOWN -> refusal (emission cannot be bounded).
    winter             — None | winter.WinterSignal | winter.WinterState
                         (dclm/winter.py — the lawful trigger source). The
                         winter gradient slows emission via
                         winter.emission_multiplier: 1.0 at full summer
                         (an exact no-op), down to EMISSION_FLOOR at full
                         winter (slowed, never shut down). None or an
                         unreadable signal -> SUMMER, no throttle (UNKNOWN
                         never PASS). Every throttled epoch receipt carries
                         the winter reason (gradient, label, multiplier,
                         per-signal reasons) sealed in its canonical hash.
                         A raw number or dict is refused — no second
                         trigger is invented here.
    holdback_fraction  — None (default): the Reserve is not engaged —
                         reserve_held = 0, labeled (the labeled zero; "not
                         engaged", not "unset"). A Figure in [0, 1): the Peg
                         Regulation Reserve absorbs fraction × the computed
                         emission at computation time, diverted to the pool's
                         Reserve instead of disbursed. MODELED -> runs,
                         outputs MODELED (testnet what-if). A HeldParameter,
                         the held PARAMS entry, or an UNKNOWN figure ->
                         HeldParameterError: the fraction is David's digit;
                         the machinery refuses to invent one and refuses to
                         silently pass through.
    reserve_release    — None (default): no release. A Figure: amount of the
                         pool's Reserve to release back through THIS epoch's
                         emission gate — merit-weighted, Unity-bound, like any
                         emission. Capped at the reserve balance AND at the
                         pool's remaining authority headroom (released funds
                         leave only via disburse, which enforces the cap —
                         the Reserve never manufactures headroom the pool
                         lacks). UNKNOWN -> UnknownFigureError.
    reserve_balance    — Figure of the pool's current Reserve balance (the
                         Ledger supplies it DERIVED). None -> 0.

    Merit-weighted: each member's share is proportional to earned
      standing (origin-based). Token balance has ZERO influence.
    Peg-calibrated: eFuse_i = merit_i / E — the unique rate where the peg
      holds by definition (the emission's energy value equals the merit's).
    Authority-bounded: epoch total never exceeds remaining pool authority;
      scaled down uniformly if it would.
    Winter-throttled: the computed emission is then slowed by the winter
      multiplier (protection, not shutdown).
    Peg-regulated (F7): the holdback fraction operationalizes "emission
      beyond what the peg supports" — fraction × the computed (peg-calibrated,
      authority-bounded, winter-throttled) emission is diverted to the
      per-pool Reserve. The Reserve is per-pool (human/machine) — never a
      sixth pool, never double-counted:
        epoch_total + reserve_released == sum(per_member) + reserve_held.
      Release re-injects held funds through the SAME gate: the released
      amount rejoins the disbursable stream AFTER the absorb split (released
      funds are never re-absorbed) and is distributed by the same merit
      weights to the same Unity-bound per-member shares. The release is an
      explicit, separately-receipted calibration decision ("calibration
      supports it"), not metered emission — winter slows metered emission;
      it does not second-guess a decided release. There is NO other exit
      from the Reserve: no function disburses reserve funds to a member —
      absence of machinery, not a policy check.
    No earned standing -> zero emission for everyone (no pre-funding, by
      construction); a requested release is HELD (the merit gate is closed),
      noted explicitly, never dropped silently.
    """
    _require_pool(pool)

    # --- the peg: David's digit. Held or unknown -> refuse, never invent. ---
    if isinstance(peg_ratio, HeldParameter):
        raise HeldParameterError(
            f"peg_ratio E is HELD_FOR_DAVID ({peg_ratio.name}) — "
            "emission cannot be calibrated; refusing (UNKNOWN never pays)"
        )
    peg = _as_figure(peg_ratio, "peg_ratio")
    if peg.provenance in ("HELD", "UNKNOWN"):
        raise HeldParameterError(
            f"peg_ratio E is {peg.provenance} — E is David's digit; "
            "nothing emits without it. Refusing."
        )
    if peg.value <= 0:
        raise ValueError("peg_ratio must be positive")

    # --- authority must be known to bound emission ---
    if isinstance(remaining_authority, HeldParameter):
        raise HeldParameterError("remaining_authority is HELD — cannot bound emission")
    auth = _as_figure(remaining_authority, "remaining_authority")
    if auth.provenance == "UNKNOWN":
        raise UnknownFigureError(
            "remaining pool authority is UNKNOWN — emission cannot be bounded; refusing"
        )
    if auth.value < 0:
        raise ValueError("remaining_authority cannot be negative")

    # --- Peg Regulation Reserve inputs: David's digit, or refusal ---------
    # Validated BEFORE the merit gate so the refusal fires on the fraction
    # itself, independent of whether any merit exists. None means "not
    # engaged" (the labeled zero); an unset digit means HeldParameterError.
    fraction_fig = _require_holdback_fraction(holdback_fraction)
    rel_fig = _require_release_amount(reserve_release)
    bal_fig = _require_reserve_balance(reserve_balance)

    # Output provenance follows the weakest input: any MODELED figure among
    # (peg_ratio, holdback_fraction, reserve_release) -> MODELED outputs;
    # all VERIFIED/REPORTED/DERIVED -> DERIVED outputs. (UNKNOWN/HELD are
    # refused above, so a non-strong input can only be MODELED.)
    _STRONG = ("VERIFIED", "REPORTED", "DERIVED")
    _in_provs = [peg.provenance]
    if fraction_fig is not None:
        _in_provs.append(fraction_fig.provenance)
    if rel_fig is not None:
        _in_provs.append(rel_fig.provenance)
    out_prov = "DERIVED" if all(p in _STRONG for p in _in_provs) else "MODELED"

    # --- standing: the ONLY emission weight source ----------------------
    # Resolved BEFORE the merit gate. The trusted weights are earned
    # standing (origin-based); a caller-supplied merit_map is
    # cross-checked here and NEVER read for weights. Bought Merit has
    # zero standing, so it buys zero emission weight — structurally.
    _trusted_weights = _resolve_standing_weights(standing_source)
    if merit_map is not None:
        _trusted_weights = _cross_check_merit_map(
            merit_map, _trusted_weights, "emission_calculator")

    # --- merit gate: only strong-provenance standing weight counts ---
    # Trusted weights carry VERIFIED or DERIVED provenance by
    # construction (enforced in _resolve_standing_weights /
    # _cross_check_merit_map). Zero weight is excluded — nothing
    # earned, nothing emitted.
    shares = {}
    excluded = {}
    for uid, fig in _trusted_weights.items():
        _require_unity(uid)
        if fig.provenance in _STANDING_WEIGHT_PROVENANCE and fig.value > 0:
            shares[uid] = fig.value
        else:
            excluded[uid] = fig.provenance  # zero weight: never pays
    total_merit = sum(shares.values())

    reserve_held_inactive = Figure(
        0.0, "UNKNOWN",
        "Peg Regulation Reserve holdback fraction is HELD_FOR_DAVID — "
        "no holdback machinery active",
    )

    # --- winter throttle: the lawful source is dclm/winter.py ---
    # Resolved AFTER the peg/authority gates above: the peg calibration
    # path refuses first, untouched — winter never consults an uncalibrated
    # emission.
    wstate, wmult = _resolve_winter(winter)
    throttled = wmult < 1.0

    if total_merit <= 0:
        _rel_held_note = ""
        if rel_fig is not None and rel_fig.value > 0:
            _rel_held_note = (
                f" A reserve release of {rel_fig.value} was requested but is "
                "HELD — the merit gate is closed (no earned standing), so "
                "the release cannot pass it; the Reserve is untouched.")
        return EpochEmission(
            pool=pool,
            per_member={},
            total=Figure(0.0, out_prov,
                         "no earned standing — zero emission (no pre-funding, by construction)"),
            excluded=excluded,
            authority_cap_applied=False,
            reserve_held=(reserve_held_inactive if fraction_fig is None
                          else Figure(0.0, out_prov,
                                      "no earned standing — nothing computed, "
                                      "nothing held back")),
            reserve_released=Figure(
                0.0, out_prov,
                "no earned standing — no release through a closed gate"),
            provenance=out_prov,
            note=("No earned standing: zero emission. "
                  "The pool is authority-only until receipts exist."
                  + _rel_held_note),
            winter_gradient=wstate.gradient,
            winter_label=wstate.label,
            winter_multiplier=wmult,
            winter_reasons=tuple(wstate.reasons),
            winter_provenance=wstate.provenance,
        )

    # --- merit-weighted, peg-calibrated, authority-bounded, winter-throttled ---
    raw_total = total_merit / peg.value          # eFuse implied by the peg
    bounded_total = min(raw_total, auth.value)   # bounded by remaining authority
    cap_applied = bounded_total < raw_total
    scale = (bounded_total / raw_total) if raw_total > 0 else 0.0
    # Winter: the gradient slows metered emission continuously
    # (protection, not shutdown — the floor is above zero). A summer
    # multiplier of 1.0 is an exact no-op.
    epoch_total = bounded_total * wmult

    # --- Peg Regulation Reserve: absorb ---------------------------------
    # fraction x the computed (peg-calibrated, authority-bounded,
    # winter-throttled) emission is diverted to the pool's Reserve instead
    # of disbursed. Per-pool, within the originating pool's authority —
    # never a sixth pool, never double-counted.
    if fraction_fig is None:
        holdback = 0.0
        reserve_held = reserve_held_inactive
    else:
        holdback = epoch_total * fraction_fig.value
        reserve_held = Figure(
            holdback, out_prov,
            f"Peg Regulation Reserve absorb: {fraction_fig.value} of the "
            f"computed {pool}-pool emission diverted to the Reserve "
            f"(fraction provenance: {fraction_fig.provenance}) — "
            "within originating pool authority, not a disbursement",
        )
    disbursable = epoch_total - holdback

    # --- Peg Regulation Reserve: release (back through the same gate) ----
    # The released amount rejoins the disbursable stream AFTER the absorb
    # split (released funds are never re-absorbed) and AFTER the winter
    # throttle: a release is an explicit, separately-receipted calibration
    # decision ("calibration supports it"), not metered emission. Capped
    # twice — by what the Reserve holds, and by remaining pool authority
    # headroom (released funds leave only via disburse, which enforces the
    # cap; the Reserve never manufactures headroom the pool lacks).
    released = 0.0
    release_note = "no reserve release requested"
    if rel_fig is not None:
        if rel_fig.value <= 0:
            release_note = "zero reserve release requested — nothing released"
        else:
            headroom = max(0.0, auth.value - disbursable)
            released = min(rel_fig.value, bal_fig.value, headroom)
            if released < rel_fig.value - 1e-12:
                release_note = (
                    f"reserve release requested {rel_fig.value}, applied "
                    f"{released} — capped by reserve balance {bal_fig.value} "
                    f"and authority headroom {headroom}")
            else:
                release_note = (
                    f"released {released} from the {pool}-pool Reserve back "
                    "through the emission gate (merit-weighted, Unity-bound)")
    reserve_released = Figure(released, out_prov, release_note)

    share_note = "merit-weighted, peg-calibrated share"
    total_note = ("epoch emission: merit-weighted, peg-calibrated, "
                  "bounded by remaining pool authority")
    if throttled:
        share_note += (f"; winter-throttled x{wmult:.4f} at gradient "
                       f"{wstate.gradient:.4f} ({wstate.label})")
        total_note += (
            f"; WINTER THROTTLE: gradient {wstate.gradient:.4f} "
            f"({wstate.label}) -> x{wmult:.4f} via "
            f"dclm/winter.py::emission_multiplier (floor "
            f"{_winter_module().EMISSION_FLOOR} at full winter). "
            f"Winter reasons: {'; '.join(wstate.reasons)}"
        )
    if fraction_fig is not None:
        share_note += f"; Reserve absorb {fraction_fig.value} held back"
    if released > 0:
        share_note += "; includes Reserve release (same gate)"
    # Kept shares: the winter math below is untouched — the absorb only
    # scales it by (1 - holdback_ratio), and the release adds a merit-weighted
    # top-up. With no reserve engaged both terms are exact no-ops.
    holdback_ratio = (holdback / epoch_total) if epoch_total > 0 else 0.0
    per_member = {}
    for uid, v in shares.items():
        base = v / peg.value * scale * wmult
        kept = base * (1.0 - holdback_ratio)
        plus_release = (v / total_merit) * released
        per_member[uid] = Figure(kept + plus_release, out_prov, share_note)
    if fraction_fig is not None or released > 0:
        total_note += (
            f"; PEG REGULATION RESERVE: held {holdback} -> {pool}-pool "
            f"Reserve (fraction {fraction_fig.value if fraction_fig else 0}, "
            f"{fraction_fig.provenance if fraction_fig else 'n/a'}); "
            f"released {released} back through the same gate. "
            f"Arithmetic: total + released == sum(per_member) + held. "
            f"Per-pool, receipted, never disbursed to members.")
    return EpochEmission(
        pool=pool,
        per_member=per_member,
        total=Figure(epoch_total, out_prov, total_note),
        excluded=excluded,
        authority_cap_applied=cap_applied,
        reserve_held=reserve_held,
        reserve_released=reserve_released,
        provenance=out_prov,
        note=(("Authority cap applied — scaled uniformly." if cap_applied
               else "Within remaining authority; no scaling.")
              + (f" Winter throttle x{wmult:.4f} applied — see total note "
                 f"for the winter reason." if throttled
                 else " No winter throttle (summer).")
              + (f" Reserve absorb {holdback}, release {released}."
                 if (fraction_fig is not None or released > 0) else "")),
        winter_gradient=wstate.gradient,
        winter_label=wstate.label,
        winter_multiplier=wmult,
        winter_reasons=tuple(wstate.reasons),
        winter_provenance=wstate.provenance,
    )


# ---------------------------------------------------------------------------
# Ledger — the pools, the Lock, merit/honor books, receipt chain
# ---------------------------------------------------------------------------
class Ledger:
    """The tokenomics state machine. TESTNET ONLY.

    - emitted: per-pool lifetime emission so far (starts at ZERO — never
      pre-funded, by construction).
    - reserve: the Peg Regulation Reserve, per-pool (human/machine) — never
      a sixth pool. Absorb diverts computed emission here at epoch close;
      release re-injects it through the emission gate. The Reserve CANNOT
      disburse to members: no such function exists (absence of machinery).
      Every absorb/release is receipted (kind "reserve").
    - Every mutation applies a receipt; duplicate manifest_hash -> refusal.
    - Receipts hash-chain via prev_hash (tamper-evidence; epoch summaries
      can be sealed with dclm.compute.sign_state by the orchestrator).
    - No pool-to-pool flow exists. No mesh mint exists. No merit interest
      exists. No fiat->eFuse path exists. (Absence of machinery, not policy.)
    """

    def __init__(self, emission_privkey_der=None, emission_pubkey_der=None,
                 emission_authority_key_id=None):
        self.emitted = {"human": 0.0, "machine": 0.0}
        self.reserve = {"human": 0.0, "machine": 0.0}  # Peg Regulation Reserve, per-pool
        self.merit_balances = {}        # unity_id -> float
        self.merit_history = []         # [MeritCredit]
        self.honor = {}                 # unity_id -> [HonorCredit]
        self.donated_efuse = {}         # unity_id -> float (donor exclusion)
        self.lock_balance = 0.0         # Core Cause Lock donated eFuse
        self.receipts = []              # [Receipt]
        self._applied_manifests = set()
        self._mesh_work_manifests = set()
        self._chain_head = "GENESIS"
        # Emission authority (CRITICAL-4): THIS ledger is the lawful
        # emitter. It signs every disbursement receipt it issues; wallets
        # verify the signature before crediting. No PKI is invented — the
        # default is the existing testnet authority keypair; tests pass
        # ephemeral keypairs. The private key never leaves this object.
        _epriv, _epub = wallet.default_emission_authority_keys()
        self.emission_privkey_der = (emission_privkey_der
                                     if emission_privkey_der is not None
                                     else _epriv)
        self.emission_authority_pubkey_der = (emission_pubkey_der
                                              if emission_pubkey_der is not None
                                              else _epub)
        self.emission_authority_key_id = (
            emission_authority_key_id or wallet.EMISSION_AUTHORITY_KEY_ID)
        # Sender authorization for Merit transfers (S1b closure of the S1
        # residual: Ledger.transfer_merit had the same keyless drain as
        # the canonical path). Ledger Unity IDs are not key-derived
        # ("u1", …), so — unlike the canonical path
        # (dclm/token_engine.py, which binds sha256(pubkey) to the Unity
        # ID) — this ledger binds each sender to an EXPLICITLY registered
        # transfer key (register_transfer_key, called at identity setup).
        # transfer_merit REQUIRES a sender-signed authorization verified
        # against the registered key; used nonces are refused (replay
        # protection). The public Unity ID alone authorizes nothing.
        self.transfer_keys = {}            # unity_id -> pubkey_der bytes
        self._transfer_auth_nonces = set()  # consumed transfer nonces

    # -- emission-authority signing (CRITICAL-4) ---------------------------
    @staticmethod
    def _disbursement_signing_body(receipt):
        """Canonical body covered by the authority signature: the full
        receipt content, excluding the signature envelope itself."""
        return {
            "receipt_id": receipt.receipt_id,
            "manifest_hash": receipt.manifest_hash,
            "unity_id": receipt.unity_id,
            "kind": receipt.kind,
            "detail": receipt.detail,
            "provenance": receipt.provenance,
            "epoch": receipt.epoch,
            "prev_hash": receipt.prev_hash,
        }

    def sign_disbursement_receipt(self, receipt):
        """The emission authority signs a disbursement receipt (CRITICAL-4).

        Returns a NEW Receipt with emitter_signature / emitter_key_id set —
        the Ed25519 signature over the canonical receipt body, made by this
        ledger's emission private key. Any later tampering with the body
        breaks the signature."""
        signed_dict = wallet.sign_emission_receipt(
            self._disbursement_signing_body(receipt),
            self.emission_privkey_der,
            self.emission_authority_key_id)
        return replace(receipt,
                       emitter_signature=signed_dict["emitter_signature"],
                       emitter_key_id=signed_dict["emitter_key_id"])

    def disbursement_signature_valid(self, receipt) -> bool:
        """Verify a disbursement receipt's emission-authority signature
        against this ledger's registered authority key. Never raises."""
        try:
            body = dict(self._disbursement_signing_body(receipt))
            body["emitter_signature"] = receipt.emitter_signature
            body["emitter_key_id"] = receipt.emitter_key_id
            return wallet.emission_receipt_signature_valid(
                body, self.emission_authority_pubkey_der,
                self.emission_authority_key_id)
        except Exception:
            return False

    # -- authority ---------------------------------------------------------
    def remaining_authority(self, pool):
        """DERIVED from the ledger: cap minus emitted. Never pre-funded."""
        _require_pool(pool)
        return Figure(
            POOL_CAPS[pool] - self.emitted[pool],
            "DERIVED",
            f"{pool} pool: {POOL_CAPS[pool]:,.0f} cap minus "
            f"{self.emitted[pool]:,.4f} emitted",
        )

    def reserve_balance(self, pool):
        """DERIVED from the ledger: the pool's Peg Regulation Reserve balance.

        Per-pool holding within the originating pool's authority — never a
        sixth pool. The balance is NOT disbursable: no function pays a member
        from the Reserve (absence of machinery, not a policy check). The only
        exit is re-injection through the emission gate (emission_close's
        reserve_release), distributed by merit weight to Unity-bound shares."""
        _require_pool(pool)
        return Figure(
            self.reserve[pool],
            "DERIVED",
            f"{pool}-pool Peg Regulation Reserve balance — per-pool holding, "
            "within originating pool authority; not disbursable to members",
        )

    # -- receipts ----------------------------------------------------------
    def apply_receipt(self, receipt):
        """Apply a receipt idempotently. Same manifest_hash twice -> refusal."""
        if receipt.manifest_hash in self._applied_manifests:
            raise DuplicateReceiptError(
                f"manifest_hash {receipt.manifest_hash[:16]}… already applied — "
                "the same work is never counted twice"
            )
        self._applied_manifests.add(receipt.manifest_hash)
        self.receipts.append(receipt)
        self._chain_head = receipt.manifest_hash
        return receipt

    def _new_receipt(self, unity_id, kind, detail, provenance, epoch):
        r = Receipt.build(unity_id, kind, detail, provenance, epoch,
                          self._chain_head)
        return self.apply_receipt(r)

    # -- merit -------------------------------------------------------------
    def accrue_merit(self, unity_id, receipt, weight):
        """F8: gated receipt -> merit. Requires a VERIFIED receipt bound to
        the same unity_id, and an explicit weight Figure (the bands are
        HELD_FOR_DAVID — the caller supplies the weight with its provenance;
        UNKNOWN/HELD weight -> refusal). Merit interest does not exist:
        the only way merit grows is this function, with a receipt."""
        uid = _require_unity(unity_id)
        if receipt is None:
            raise ReceiptRequiredError(
                "merit accrual requires a gated receipt — no receipt, no merit"
            )
        if receipt.provenance != "VERIFIED":
            raise ReceiptRequiredError(
                f"receipt {receipt.receipt_id[:8]}… is {receipt.provenance}, "
                "not VERIFIED — gated receipts only"
            )
        if receipt.unity_id != uid:
            raise UnityBindingError(
                "receipt is bound to a different Unity ID than the claimant"
            )
        w = _as_figure(weight, "merit weight")
        if isinstance(w, HeldParameter) or w.provenance in ("HELD", "UNKNOWN"):
            raise HeldParameterError(
                "merit weight bands are HELD_FOR_DAVID — refusing an "
                "unsigned/unknown weight"
            )
        if w.value <= 0:
            raise ValueError("merit weight must be positive")
        self.apply_receipt(receipt)  # idempotent: same receipt never accrues twice
        self.merit_balances[uid] = self.merit_balances.get(uid, 0.0) + w.value
        credit = MeritCredit(uid, Figure(w.value, w.provenance,
                                         "merit from gated receipt"),
                             receipt.receipt_id, receipt.epoch)
        self.merit_history.append(credit)
        return credit

    def merit_balance(self, unity_id):
        uid = _require_unity(unity_id)
        return Figure(self.merit_balances.get(uid, 0.0), "DERIVED",
                      "merit balance derived from gated accruals minus decay")

    def standing(self, unity_id):
        """EARNED STANDING — origin-based, the emission gate's ONLY weight
        source.

        The sum of this identity's merit ACCRUAL credits (merit_history).
        Accrual-only by construction: transfer_merit moves owned balances
        and NEVER touches merit_history, so standing NEVER moves on
        transfer — a buyer gains economic value and ZERO standing.
        apply_decay acts on the owned balance (spendable value) only, never
        on standing (earned history). Emission weight = f(standing);
        token balance has ZERO influence on emission weight."""
        uid = _require_unity(unity_id)
        total = sum(c.amount.value for c in self.merit_history
                    if c.unity_id == uid)
        return Figure(
            total, "DERIVED",
            "earned standing: origin-based accrual history — transfers "
            "never move it, decay never touches it")

    def emission_weights(self, uids=None):
        """The TRUSTED emission weight map: earned standing per identity.

        uids=None -> every identity with a positive earned standing.
        Otherwise exactly the given identities (zero-standing identities
        included with a zero weight — the merit gate excludes them).
        Every weight is DERIVED from merit_history; no balance is read.
        This is the ONLY weight source the emission gate reads."""
        if uids is None:
            totals = {}
            for c in self.merit_history:
                totals[c.unity_id] = totals.get(c.unity_id, 0.0) \
                    + c.amount.value
            uids = [u for u, t in totals.items() if t > 0]
        return {u: Figure(self.standing(u).value, "DERIVED",
                          _STANDING_WEIGHT_NOTE)
                for u in uids}

    def apply_decay(self, unity_id, epochs, rate=None):
        """Merit decays per epoch — fidelity is current, not historical.
        The decay rate is HELD_FOR_DAVID: without an explicit rate Figure
        this REFUSES (no invented digits). An explicit MODELED rate runs
        and labels outputs MODELED."""
        uid = _require_unity(unity_id)
        if rate is None:
            require_decided("merit_decay_rate")  # raises HeldParameterError
        r = _as_figure(rate, "decay rate")
        if isinstance(r, HeldParameter) or r.provenance in ("HELD", "UNKNOWN"):
            raise HeldParameterError(
                "merit_decay_rate is HELD_FOR_DAVID — refusing to invent it"
            )
        if not (0.0 <= r.value < 1.0):
            raise ValueError("decay rate must be in [0, 1)")
        if epochs < 0:
            raise ValueError("epochs cannot be negative")
        before = self.merit_balances.get(uid, 0.0)
        after = before * ((1.0 - r.value) ** epochs)
        self.merit_balances[uid] = after
        out_prov = "DERIVED" if r.provenance in ("VERIFIED", "REPORTED", "DERIVED") \
            else r.provenance
        self._new_receipt(uid, "decay",
                          {"before": before, "after": after,
                           "epochs": epochs, "rate": r.value,
                           "rate_provenance": r.provenance},
                          out_prov, None)
        return Figure(after, out_prov,
                      f"merit after {epochs} epoch(s) of decay at rate {r.value}")

    # -- merit transfer: ownership moves, origin never does -----------------
    def register_transfer_key(self, unity_id, pubkey_der_b64):
        """Register the Ed25519 public key that authorizes Merit transfers
        FROM unity_id. Call this at identity setup — before the identity
        can send anything. The public Unity ID alone authorizes nothing:
        transfer_merit refuses any transfer whose authorization does not
        verify against this key.

        pubkey_der_b64: base64 DER (SPKI) public key — the same shape as
        economics/wallet.py's owner keys (their make_merit_transfer_auth
        builds authorizations this ledger also accepts). Registration is
        identity provisioning, not economic movement, so it is not
        receipted (same convention as wallet.register_identity); every
        transfer receipt records the authorizing key's sha256, so the
        audit trail links each transfer back to this registration.
        Re-registration rotates the key (the old key stops working)."""
        uid = _require_unity(unity_id)
        if not isinstance(pubkey_der_b64, str) or \
                not pubkey_der_b64.strip():
            raise TokenomicsError(
                "register_transfer_key needs a base64 public key")
        try:
            pub = base64.b64decode(pubkey_der_b64.strip(), validate=True)
        except Exception as exc:
            raise TokenomicsError(
                "register_transfer_key: pubkey is not valid base64 "
                f"({exc})") from exc
        if not pub:
            raise TokenomicsError("register_transfer_key: empty public key")
        self.transfer_keys[uid] = pub

    def _require_transfer_auth(self, sender, recipient, amount_fig,
                               reason, auth):
        """Sender authorization for a Merit transfer. Refusals are code:
        missing auth, unregistered sender, key mismatch, body mismatch,
        failed signature, or replayed nonce — all MeritTransferAuthError.

        The canonical signed body is the same shape the wallet path uses
        (economics/wallet.py::make_merit_transfer_auth):
          {"op": "merit-transfer", "from": sender, "to": recipient,
           "amount": float(amount), "reason": reason.strip(),
           "nonce": nonce}
        The signature binds EXACTLY what will move — a different amount,
        recipient, reason, or nonce fails verification. The nonce is
        single-use (ledger-scoped): replaying an authorization is refused.
        Returns (nonce, sender_pubkey_der) on success; the nonce is
        recorded as consumed only when the transfer itself succeeds (a
        refused transfer does not burn the authorization)."""
        if not isinstance(auth, dict):
            raise MeritTransferAuthError(
                "merit transfer needs the sender's signed transfer "
                "authorization — unsigned transfers are refused. The "
                "public Unity ID alone authorizes nothing.")
        nonce = auth.get("nonce")
        sig = auth.get("signature")
        pub_b64 = auth.get("pubkey_b64")
        if not nonce or not isinstance(nonce, str):
            raise MeritTransferAuthError(
                "transfer authorization needs a nonce — refusing")
        if not sig or not isinstance(sig, str):
            raise MeritTransferAuthError(
                "transfer authorization needs an Ed25519 signature — "
                "refusing")
        if not pub_b64 or not isinstance(pub_b64, str):
            raise MeritTransferAuthError(
                "transfer authorization must name the signing public key "
                "— refusing")
        registered = self.transfer_keys.get(sender)
        if registered is None:
            raise MeritTransferAuthError(
                f"no transfer key registered for {sender!r} — an identity "
                "cannot send Merit until its transfer key is registered")
        try:
            declared = base64.b64decode(pub_b64.strip(), validate=True)
        except Exception:
            raise MeritTransferAuthError(
                "transfer authorization carries a malformed public key — "
                "refusing")
        if declared != registered:
            raise MeritTransferAuthError(
                "transfer authorization's key does not match the sender's "
                "registered transfer key — refusing")
        expected = {
            "op": "merit-transfer",
            "from": sender,
            "to": recipient,
            "amount": float(amount_fig.value),
            "reason": reason,
            "nonce": nonce,
        }
        for key, want in (("op", "merit-transfer"), ("from", sender),
                          ("to", recipient), ("reason", reason)):
            if auth.get(key) != want:
                raise MeritTransferAuthError(
                    f"transfer authorization body mismatch on {key!r} — "
                    "the signed intent does not match this transfer; "
                    "refusing")
        try:
            auth_amount = float(auth.get("amount"))
        except (TypeError, ValueError):
            raise MeritTransferAuthError(
                "transfer authorization amount is not a number — refusing")
        if auth_amount != float(amount_fig.value):
            raise MeritTransferAuthError(
                "transfer authorization amount does not match the "
                "transfer amount — refusing")
        if not wallet._node_verify(declared,
                                   wallet._canonical_bytes(expected), sig):
            raise MeritTransferAuthError(
                "transfer authorization signature FAILED against the "
                "sender's registered key — refusing")
        if nonce in self._transfer_auth_nonces:
            raise MeritTransferAuthError(
                "transfer authorization nonce already used — replay "
                "refused")
        return nonce, registered

    def transfer_merit(self, from_unity_id, to_unity_id, amount, reason,
                       epoch, auth=None):
        """Transfer OWNED Merit between Unity IDs — the receipted
        ownership movement of this module's merit ledger.

        David's word, 2026-10-06 ~3:35 AM EDT (LAW): Merit IS
        transferable — sold, gifted, transferred between Unity IDs, all
        receipted. This ledger holds OWNED balances only
        (merit_balances): it has never carried origin/earned-history
        fields, so there is nothing here that could move with the token.
        The canonical path
        (dclm/token_engine.py::Tokenizer.merit_transfer — the SOLE legal
        Merit ownership-transfer path; economics/wallet.py::transfer_merit
        delegates to it) carries the immutable-origin semantics: origin
        frozen at accrual, standing keys off origin, a buyer gains
        economic value and ZERO standing. This function is the same
        contract — ownership only.

        Gates, in order — all code, no policy promises:
          1. SENDER AUTHORIZATION (S1b closure): the transfer must carry
             the sender's Ed25519-signed authorization over the canonical
             body {"op": "merit-transfer", "from", "to", "amount",
             "reason", "nonce"} — the same shape as the wallet path
             (economics/wallet.py::make_merit_transfer_auth). The auth's
             key must equal the sender's REGISTERED transfer key (this
             ledger's IDs are not key-derived, so there is no
             sha256(pubkey)-to-ID binding — registration is the binding);
             the body must bind exactly this transfer; the nonce must be
             fresh (replay refused). No auth / unregistered sender /
             wrong key / body mismatch / bad signature / replayed nonce
             -> MeritTransferAuthError. The public Unity ID alone
             authorizes nothing: the gauntlet's keyless shape
             (transfer_merit('victim','attacker',…) with no auth) is
             refused here.
          2. both Unity IDs required and distinct (no anonymous flows;
             self-transfer is a no-op disguised as a transfer — refused);
          3. amount must be a positive Figure (UNKNOWN -> refusal — the
             amount must be a real measured figure);
          4. reason must be a non-empty string (sale, gift, … — every
             transfer is receipted with its why);
          5. the sender's OWNED balance must cover the amount.
        Structural: the transfer receipt may NEVER carry an origin key
        (checked in code, not in comment — this ledger does not know
        origin, and must never pretend to). The receipt records the
        authorizing key's sha256 and the consumed nonce, linking the
        transfer back to its key registration."""
        sender = _require_unity(from_unity_id)
        recipient = _require_unity(to_unity_id)
        if sender == recipient:
            raise TokenomicsError(
                "merit transfer requires two distinct Unity IDs — "
                "self-transfer refused")
        a = _as_figure(amount, "merit transfer amount")
        if isinstance(a, HeldParameter) or a.provenance == "UNKNOWN":
            raise UnknownFigureError(
                "merit transfer amount is UNKNOWN/unsigned — refusing; "
                "transferred value must be a real measured figure")
        if a.value <= 0:
            raise ValueError("merit transfer amount must be positive")
        if not isinstance(reason, str) or not reason.strip():
            raise TokenomicsError(
                "merit transfer needs a non-empty reason (sale, gift, …) — "
                "every transfer is receipted with its why")
        reason = reason.strip()
        nonce, sender_key = self._require_transfer_auth(
            sender, recipient, a, reason, auth)
        owned = self.merit_balances.get(sender, 0.0)
        if a.value > owned + 1e-9:
            raise TokenomicsError(
                f"{sender!r} owns {owned} merit — cannot transfer "
                f"{a.value}; only owned (not originated) value moves")
        self.merit_balances[sender] = owned - a.value
        self.merit_balances[recipient] = \
            self.merit_balances.get(recipient, 0.0) + a.value
        # The authorization is consumed exactly once: recorded only when
        # the transfer succeeds (a refused transfer does not burn it).
        self._transfer_auth_nonces.add(nonce)
        detail = {
            "from": sender,
            "to": recipient,
            "amount": a.value,
            "amount_provenance": a.provenance,
            "reason": reason,
            "sender_owned_after": self.merit_balances[sender],
            "recipient_owned_after": self.merit_balances[recipient],
            "auth_nonce": nonce,
            "sender_key_sha256": hashlib.sha256(sender_key).hexdigest(),
            "note": ("OWNERSHIP ONLY — origin/earned-history fields are "
                     "frozen at accrual and never move with the token; "
                     "standing keys off origin, not balance. This ledger "
                     "holds owned balances only and carries no origin. "
                     "Sender-authorized: the signature over the transfer "
                     "intent verified against the sender's registered "
                     "transfer key (key sha256 recorded)."),
        }
        # Structural, in code: no origin key may ever appear on a merit
        # transfer receipt of this module — mirrors wallet.transfer_merit.
        for key in ("origin_earner_id", "origin_receipt_ref", "origin"):
            if key in detail:
                raise TokenomicsError(
                    "merit transfer receipts never carry origin — "
                    "origin stays in the canonical engine")
        return self._new_receipt(sender, "merit_transfer", detail,
                                 a.provenance, epoch)

    # -- emission & disbursement -------------------------------------------
    def emission_close(self, pool, merit_map=None, peg_ratio=None,
                       epoch=None, winter=None, holdback_fraction=None,
                       reserve_release=None):
        """Epoch close for one pool: compute emission against the ledger's
        own remaining authority — with weights from EARNED STANDING.

        merit_map is UNTRUSTED caller input ({unity_id: Figure} or None):
        it is cross-checked against this ledger's standing (exact
        restatement — same identities, same values, strong provenance)
        and any mismatch REFUSES (UntrustedMeritMapError). The map is
        NEVER read for weights. None (default) closes against every
        earner's standing; a caller may scope the map to a roster
        (e.g. a pool's members) — each scoped weight is still forced to
        equal that identity's standing. Bought Merit has zero standing,
        so it buys zero emission weight — structurally.

        Computes the emission AND operates the Peg Regulation Reserve at
        computation time:
          - absorb: holdback_fraction of the computed emission is diverted
            to the pool's Reserve (credited here, receipted kind "reserve",
            direction "absorb").
          - release: reserve_release re-injects held funds through the same
            emission gate — merit-weighted, Unity-bound per-member shares
            (debited here, receipted kind "reserve", direction "release").
        The Reserve diversion is not a disbursement: no member receives
        anything at close. Member disbursement remains the separate explicit
        disburse() step, Unity-bound per member. The Reserve is per-pool,
        never a sixth pool, never double-counted.

        holdback_fraction=None: the Reserve is not engaged (labeled zero, no
        receipt). A HeldParameter, the held PARAMS entry, or an UNKNOWN
        figure -> HeldParameterError: David's digit; never invented, never
        silently passed through.

        winter threads through to emission_calculator (None |
        winter.WinterSignal | winter.WinterState, dclm/winter.py the lawful
        source); the returned EpochEmission receipts the winter reason."""
        _require_pool(pool)
        if peg_ratio is None:
            raise TokenomicsError(
                "emission_close requires peg_ratio — E is David's digit; "
                "nothing emits without it")
        auth = self.remaining_authority(pool)
        bal = self.reserve_balance(pool)
        out = emission_calculator(pool, merit_map, peg_ratio, auth,
                                  winter=winter,
                                  holdback_fraction=holdback_fraction,
                                  reserve_release=reserve_release,
                                  reserve_balance=bal,
                                  standing_source=self)
        if out.reserve_held.value > 0:
            self.reserve[pool] += out.reserve_held.value
            _frac = (holdback_fraction
                     if isinstance(holdback_fraction, Figure) else None)
            self._new_receipt(
                _reserve_identity(pool), "reserve",
                {"direction": "absorb",
                 "pool": pool,
                 "amount": out.reserve_held.value,
                 "amount_provenance": out.reserve_held.provenance,
                 "holdback_fraction": _frac.value if _frac else None,
                 "fraction_provenance": _frac.provenance if _frac else None,
                 "epoch_computed_total": out.total.value,
                 "reserve_balance_after": self.reserve[pool],
                 "note": "Peg Regulation Reserve absorb — per-pool diversion "
                         "at emission computation, within originating pool "
                         "authority. Not a disbursement: no member received "
                         "anything."},
                out.reserve_held.provenance, epoch)
        if out.reserve_released.value > 0:
            self.reserve[pool] -= out.reserve_released.value
            self._new_receipt(
                _reserve_identity(pool), "reserve",
                {"direction": "release",
                 "pool": pool,
                 "amount": out.reserve_released.value,
                 "amount_provenance": out.reserve_released.provenance,
                 "epoch_disbursable_total": sum(
                     f.value for f in out.per_member.values()),
                 "reserve_balance_after": self.reserve[pool],
                 "note": "Peg Regulation Reserve release — re-injected "
                         "through the emission gate: merit-weighted, "
                         "Unity-bound per-member shares. The Reserve has no "
                         "other exit."},
                out.reserve_released.provenance, epoch)
        return out

    def disburse(self, pool, unity_id, amount, epoch):
        """F1: disburse computed emission to the earning Unity ID.
        Bounded by remaining pool authority — over-authority -> refusal.
        The issued disbursement receipt is signed by the emission
        authority (CRITICAL-4): the signature binds the receipt to its
        issuer, so a forged disbursement cannot be passed off as lawful."""
        _require_pool(pool)
        uid = _require_unity(unity_id)
        a = _as_figure(amount, "disbursement amount")
        if a.provenance == "UNKNOWN":
            raise UnknownFigureError(
                "disbursement amount is UNKNOWN/unsigned — refusing")
        if a.value <= 0:
            raise ValueError("disbursement amount must be positive")
        remaining = POOL_CAPS[pool] - self.emitted[pool]
        if a.value > remaining + 1e-9:
            raise AuthorityExceededError(
                f"{a.value} exceeds {pool} pool remaining authority {remaining}")
        self.emitted[pool] += a.value
        r = Receipt.build(
            uid, "disbursement",
            {"pool": pool, "amount": a.value,
             "amount_provenance": a.provenance,
             "remaining_authority_after": POOL_CAPS[pool] - self.emitted[pool]},
            a.provenance if a.provenance != "UNKNOWN" else "DERIVED",
            epoch, self._chain_head)
        return self.apply_receipt(self.sign_disbursement_receipt(r))

    # -- mesh: routes, never mints ------------------------------------------
    def mesh_route(self, unity_id, commissioning_pool, manifest_hash, epoch,
                   terms_note=""):
        """F2/F3 routing record. The mesh draws emission authority from the
        COMMISSIONING pool — it has none of its own. emission_authority is
        always 0: the mesh routes, never mints (no mint function exists).
        Double-bridging the same work manifest -> refusal (phantom/double
        bridge refused by construction)."""
        uid = _require_unity(unity_id)
        _require_pool(commissioning_pool)
        if not manifest_hash or not isinstance(manifest_hash, str):
            raise ValueError("manifest_hash is required for cross-pool routing")
        if manifest_hash in self._mesh_work_manifests:
            raise DuplicateReceiptError(
                "work manifest already bridged — double-counting refused "
                "(one work, one receipt, one manifest_hash)")
        self._mesh_work_manifests.add(manifest_hash)
        return self._new_receipt(
            uid, "mesh_route",
            {"commissioning_pool": commissioning_pool,
             "work_manifest_hash": manifest_hash,
             "emission_authority": 0.0,
             "mints": False,
             "terms_note": terms_note,
             "note": "Mesh routes, never mints. Disbursement draws on the "
                     "commissioning pool's authority via emission_calculator."},
            "DERIVED", epoch)

    # -- donations -> Honor (never Merit, never emission) --------------------
    def donate(self, unity_id, amount, kind, epoch):
        """F4/F5: donation -> Honor. Donations accrue Honor, never Merit;
        no eFuse is emitted and none is promised. There is no fiat->eFuse
        path in this module — the function does not exist."""
        uid = _require_unity(unity_id)
        if kind not in DONATION_KINDS:
            raise ValueError(f"donation kind must be one of {DONATION_KINDS}")
        a = _as_figure(amount, "donation amount")
        if a.provenance == "UNKNOWN":
            raise UnknownFigureError(
                "donation amount is UNKNOWN/unsigned — refusing")
        if a.value <= 0:
            raise ValueError("donation amount must be positive")
        receipt = self._new_receipt(
            uid, "donation",
            {"kind": kind, "amount": a.value,
             "amount_provenance": a.provenance,
             "note": "Donation accrues Honor, never Merit. No eFuse promised."},
            a.provenance, epoch)
        honor = HonorCredit(
            uid, receipt.receipt_id, None, a.provenance,
            "Honor class names HELD_FOR_DAVID (§13) — class unnamed until his word.")
        self.honor.setdefault(uid, []).append(honor)
        if kind == "efuse":
            self.lock_balance += a.value
            self.donated_efuse[uid] = self.donated_efuse.get(uid, 0.0) + a.value
        # NOTE: returns (receipt, honor) — no Merit, no eFuse. The gift is the gift.
        return receipt, honor

    def cause_disburse(self, unity_id, amount, receipt, epoch):
        """F6: cause-work disbursement from the Lock's DONATED supply (not
        pool authority). Same gates as any work: gated receipt -> merit ->
        disbursement. Donor exclusion: a member that donated eFuse to the
        Lock can never receive from it (one-way per donor). The issued
        disbursement receipt is signed by the emission authority
        (CRITICAL-4) — the wallet verifies the signature before crediting,
        so a forged Lock disbursement cannot be passed off as lawful."""
        uid = _require_unity(unity_id)
        if receipt is None or receipt.provenance != "VERIFIED":
            raise ReceiptRequiredError(
                "cause-work disbursement requires a VERIFIED gated receipt")
        if receipt.unity_id != uid:
            raise UnityBindingError(
                "receipt is bound to a different Unity ID than the claimant")
        if self.donated_efuse.get(uid, 0.0) > 0:
            raise DonorExclusionError(
                "the Core Cause Lock is one-way per donor — donated eFuse is "
                "never re-emitted to the same member")
        a = _as_figure(amount, "cause disbursement amount")
        if a.provenance == "UNKNOWN":
            raise UnknownFigureError(
                "cause disbursement amount is UNKNOWN/unsigned — refusing")
        if a.value <= 0:
            raise ValueError("cause disbursement amount must be positive")
        if a.value > self.lock_balance + 1e-9:
            raise AuthorityExceededError(
                f"{a.value} exceeds Core Cause Lock balance {self.lock_balance}")
        self.apply_receipt(receipt)
        self.lock_balance -= a.value
        r = Receipt.build(
            uid, "cause_disbursement",
            {"amount": a.value, "amount_provenance": a.provenance,
             "lock_balance_after": self.lock_balance,
             "note": "Drawn from the Lock's donated supply — not pool authority."},
            a.provenance, epoch, self._chain_head)
        return self.apply_receipt(self.sign_disbursement_receipt(r))

    # -- introspection --------------------------------------------------------
    def state_digest(self):
        """Canonical digest of the ledger state (for epoch sealing by the
        orchestrator via dclm.compute.sign_state — not reimplemented here)."""
        body = {
            "emitted": self.emitted,
            "reserve": self.reserve,
            "merit_balances": self.merit_balances,
            "lock_balance": self.lock_balance,
            "receipts": len(self.receipts),
            "chain_head": self._chain_head,
        }
        return hashlib.sha256(_canonical(body)).hexdigest()


# ---------------------------------------------------------------------------
# What this module deliberately does NOT contain (absence of machinery):
#   - transfer_pool_to_pool / move_between_pools : no pool-to-pool flow
#   - mesh_mint / mesh emission authority        : the mesh routes, never mints
#   - accrue_merit_interest / merit_yield / stake: merit interest refused
#       (NOTE: transfers are not interest — see below)
#   - fiat_to_efuse / convert_fiat / buy_efuse   : no fiat -> eFuse path
#   - pre_fund / seed_pool / genesis_allocation  : no pre-funding
#   - reserve_disburse / reserve_payout / pay_from_reserve /
#     reserve_transfer / reserve_withdraw / reserve_claim :
#     the Peg Regulation Reserve has NO disbursement path to members.
#     The only exit is re-injection through the emission gate
#     (emission_close's reserve_release), distributed by merit weight to
#     Unity-bound shares. Absence of machinery, not a policy check.
# A rule can be waived. Missing machinery cannot.
#
# What EXISTS for Merit transfer (David's word, 2026-10-06 ~3:35 AM EDT —
# Merit IS transferable; the old non-transferable law is SUPERSEDED,
# DECISIONS.md §13):
#   - Ledger.register_transfer_key(unity_id, pubkey_b64): binds an
#     identity to its transfer-signing key at identity setup. This
#     ledger's IDs are not key-derived ("u1", …), so registration is
#     the binding — the public Unity ID alone authorizes nothing.
#   - Ledger.transfer_merit(from, to, amount, reason, epoch, auth):
#     receipted ownership movement of this module's owned-merit
#     balances. REQUIRES the sender's signed authorization
#     (make_merit_transfer_auth shape) verified against the registered
#     key; no-auth / wrong-key / bad-signature / replayed-nonce ->
#     MeritTransferAuthError. Origin/earned-history fields are frozen
#     at accrual and NEVER move with the token — this ledger holds
#     owned balances only and carries no origin (structural check in
#     code). Standing keys off origin, not balance.
#   - The canonical sole legal path: dclm/token_engine.py::
#     Tokenizer.merit_transfer (origin-immutable, AST-proven); the
#     wallet's transfer_merit delegates to it. Merit.transfer() directs
#     there — no direct class-level transfer exists.
# ---------------------------------------------------------------------------

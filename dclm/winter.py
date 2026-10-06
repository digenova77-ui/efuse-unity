"""
DCLM WINTER MODE — the counter-cyclical sap mechanism.

David's sap model, binding:
  Summer = sap flows up and out; every leaf fed; the trunk conducts
           without hoarding; founder advantage dissolves into the canopy.
  Winter = the flow REVERSES: sap travels back down to protect the root.
           Not hoarding — protection. The root must survive so spring
           can come.

This module builds the winter mechanism into the economy:

  * The trigger: three candidate signals (peg deviation, real-economy
    activity, declared+verified crisis) combine into one CONTINUOUS
    gradient 0.0 (full summer) -> 1.0 (full winter). NO phase cliffs:
    the flow gradient tilts continuously, fluid both ways at planck
    granularity, summer tilt and winter tilt alike.
  * The store: value moves from an identity's circulation balance into
    the Peg Regulation Reserve — the starch store. Winter flow is
    PROTECTION, never accumulation: the store is capped at survival
    need per identity; excess keeps flowing outward.
  * Every stored/released unit is receipted with its winter reason
    (trigger condition, measured value, threshold). Every winter claim
    — granted or refused — is logged to the receipt trail with the
    claimant identity and a signal snapshot, where L5 (the watch layer)
    can audit it.
  * Anti-gaming: claiming crisis to pull value inward with no
    supporting signal is the phantom pattern — refused as PHANTOM and
    logged for L5.
  * UNKNOWN never PASS: if the trigger signal cannot be read, the mode
    stays SUMMER (the known state). Winter is never assumed.
  * Emission throttle: the winter gradient slows metered-action
    emission continuously (protection, not shutdown — the floor is
    above zero).

All calibration numbers are PROPOSED and HELD-FOR-DAVID: see
WINTER_CALIBRATION.md. The structure is the worker's; the thresholds
are his call.

Rights & writes: winter-mode state changes are WRITES. Every store
and release flows through rights.check_rights -> GRANT ->
writes.dclm_commit with kind WINTER_STORE / WINTER_RELEASE (added to
rights.COMMIT_KINDS with receipt-logged justification). The thin
client never writes; this module never mutates state except inside
the commit path's apply_write.

Testnet only. All amounts in test-keys, clearly TEST.
"""

import hashlib
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from compute import PROVENANCE_LABELS  # noqa: E402
from meter import (  # noqa: E402 — reuse the ledger + signing path
    IDENTITY_PREFIX,
    UNIT,
    MeterError,
    MeterRefused,
    Wallet,
    sign_receipt,
)
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    purify_input,
    purify_output,
    purify_transition,
)
from writes import dclm_commit  # noqa: E402 — the single commit path

SCHEMA = "unity.winter.v1.testnet"

# ---------------------------------------------------------------------------
# PROPOSED calibration constants — ALL HELD-FOR-DAVID.
#
# Every number below is a proposal with reasoning in
# WINTER_CALIBRATION.md. None of them is decided until David says so.
# The mechanism reads these as named constants so his word changes one
# line, not the logic.
# ---------------------------------------------------------------------------

# Peg stress: |deviation| beyond the band edge starts the tilt; the
# softness sets how fast stress saturates. Fractions, e.g. 0.02 = 2%.
PEG_BAND_EDGE = 0.02        # PROPOSED
PEG_BAND_SOFT = 0.01        # PROPOSED

# Real-economy contraction: a fractional activity drop beyond the edge
# starts the tilt.
ACTIVITY_DROP_EDGE = 0.15   # PROPOSED — 15% drop
ACTIVITY_DROP_SOFT = 0.05   # PROPOSED

# How the three signal tilts combine (weighted sum, clamped to [0, 1]).
WEIGHT_PEG = 0.35           # PROPOSED
WEIGHT_ACTIVITY = 0.35      # PROPOSED
WEIGHT_CRISIS = 0.30        # PROPOSED

# Survival need: the most test-keys the starch store holds per identity.
# The root stores only what it needs to survive; excess keeps flowing
# outward. Protection, never accumulation.
SURVIVAL_NEED_CAP = 25      # PROPOSED, test-keys per identity

# Emission floor: at full winter (gradient 1.0) emission is throttled to
# this fraction of summer — slowed, never shut down.
EMISSION_FLOOR = 0.25       # PROPOSED

# Claim support: a winter store claim is honored only when the evaluated
# gradient reaches at least this. Below it, claiming winter is the
# phantom pattern — refused and logged for L5.
WINTER_CLAIM_MIN_GRADIENT = 0.10  # PROPOSED

# Display-only label bands for the gradient. The throttle, the store,
# and the release all use the CONTINUOUS gradient — these bands are
# words for humans, never decision cliffs.
LABEL_SUMMER_MAX = 0.25
LABEL_WINTER_MIN = 0.75

LABEL_SUMMER = "SUMMER"
LABEL_TILTING = "TILTING"
LABEL_WINTER = "WINTER"

# --- outcomes / refusal reasons -------------------------------------------
OUTCOME_GRANTED = "GRANTED"
OUTCOME_REFUSED = "REFUSED"

REASON_PHANTOM = "PHANTOM"
REASON_STORE_AT_SURVIVAL_NEED = "STORE_AT_SURVIVAL_NEED"
REASON_INSUFFICIENT_KEYS = "INSUFFICIENT_KEYS"
REASON_INSUFFICIENT_RESERVE = "INSUFFICIENT_RESERVE"
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_MISSING_WINTER_REASON = "MISSING_WINTER_REASON"

REFUSAL_REASONS = frozenset({
    REASON_PHANTOM,
    REASON_STORE_AT_SURVIVAL_NEED,
    REASON_INSUFFICIENT_KEYS,
    REASON_INSUFFICIENT_RESERVE,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_MISSING_WINTER_REASON,
})

# A winter reason must name the trigger condition, the measured value,
# and the threshold it was judged against. Every stored unit carries one.
WINTER_REASON_FIELDS = ("trigger_condition", "measured_value", "threshold")

DEFAULT_STATE_DIR = os.path.join(_HERE, "state-winter")
RESERVE_FILENAME = "winter-reserve.json"
RECEIPTS_FILENAME = "winter-receipts.jsonl"


# ---------------------------------------------------------------------------
# the tilt function — the one paragraph that matters
#
# Each numeric signal becomes a sub-tilt through a zero-baselined
# saturating curve: tilt(x) = max(0, 2 * (sigmoid(x) - 0.5)), where
# x = (stress - edge) / softness. Stress below the edge contributes
# nothing; stress at the edge starts to rise; deep stress saturates
# toward 1 — smoothly, with no cliff at the edge. The gradient is the
# weighted sum of the three sub-tilts, clamped to [0, 1]. A verified
# crisis contributes its full weight (binary, but it can only arrive
# through the verified path, so it never smuggles a cliff into the
# numeric tilts). Small signal changes always produce small gradient
# changes: the tilt is differentiable everywhere the signals are.
# ---------------------------------------------------------------------------

def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def _tilt01(x):
    """Zero-baselined saturating tilt. 0 for x <= 0, -> 1 as x -> +inf.

    Continuous and smooth everywhere — no phase cliff. The band edge
    is where the tilt *starts* to rise, not a switch that flips."""
    return max(0.0, 2.0 * (_sigmoid(x) - 0.5))


def _clamp01(v):
    return min(1.0, max(0.0, float(v)))


def peg_tilt(peg_deviation):
    """Sub-tilt for peg stress. peg_deviation is a signed fraction."""
    return _tilt01(
        (abs(float(peg_deviation)) - PEG_BAND_EDGE) / PEG_BAND_SOFT
    )


def activity_tilt(activity_delta):
    """Sub-tilt for real-economy contraction. activity_delta is a signed
    fractional change (negative = contraction). Growth never tilts."""
    drop = -float(activity_delta) if float(activity_delta) < 0 else 0.0
    return _tilt01((drop - ACTIVITY_DROP_EDGE) / ACTIVITY_DROP_SOFT)


def crisis_tilt(crisis_declared, crisis_verified):
    """A crisis counts only when declared AND verified — a mere claim is
    not a signal (see the phantom rule). Binary by construction, but it
    can only arrive via the verified path."""
    return 1.0 if (crisis_declared and crisis_verified) else 0.0


# ---------------------------------------------------------------------------
# WinterSignal — the trigger inputs, with provenance on each.
# ---------------------------------------------------------------------------

@dataclass
class WinterSignal:
    """Trigger inputs for the winter mechanism.

    peg_deviation   — signed fraction, e.g. -0.023 means the peg sits
                      2.3% below band center. None = unreadable.
    activity_delta  — signed fractional change in measured real-economy
                      activity, e.g. -0.18 = 18% contraction. None =
                      unreadable.
    crisis_declared — someone declared a crisis (a claim, not a signal).
    crisis_verified — the declaration was VERIFIED through the proper
                      channel. Declared-but-unverified is NOT a signal —
                      it is a phantom candidate.
    *_provenance    — provenance label per input. Unreadable inputs stay
                      UNKNOWN.

    UNKNOWN never PASS: if the signal cannot be read, the mode stays
    SUMMER — evaluate_trigger enforces this.
    """
    peg_deviation: object = None
    peg_provenance: str = "UNKNOWN"
    activity_delta: object = None
    activity_provenance: str = "UNKNOWN"
    crisis_declared: bool = False
    crisis_verified: bool = False
    crisis_provenance: str = "UNKNOWN"

    @property
    def readable(self):
        """Is there anything here to steer by? Numeric readings count;
        a crisis counts only when declared AND verified."""
        numeric = (
            self.peg_deviation is not None
            or self.activity_delta is not None
        )
        crisis = bool(self.crisis_declared and self.crisis_verified)
        return bool(numeric or crisis)

    def snapshot(self):
        """The signal as the receipt trail records it — what L5 audits."""
        return {
            "peg_deviation": self.peg_deviation,
            "peg_provenance": self.peg_provenance,
            "activity_delta": self.activity_delta,
            "activity_provenance": self.activity_provenance,
            "crisis_declared": bool(self.crisis_declared),
            "crisis_verified": bool(self.crisis_verified),
            "crisis_provenance": self.crisis_provenance,
        }


@dataclass
class WinterState:
    """The evaluated winter mode.

    gradient — continuous 0.0 (full summer) to 1.0 (full winter).
               Everything downstream (throttle, store eligibility)
               reads this, never the label.
    label    — SUMMER / TILTING / WINTER, display only. The bands are
               words for humans, not decision cliffs.
    reasons  — per-signal audit lines: what was measured against what.
    provenance — DERIVED when computed from readable signal; UNKNOWN
               when the signal could not be read (mode stays SUMMER).
    """
    gradient: float
    label: str
    reasons: list = field(default_factory=list)
    provenance: str = "DERIVED"
    signal_snapshot: dict = field(default_factory=dict)


def _label_for(gradient):
    if gradient < LABEL_SUMMER_MAX:
        return LABEL_SUMMER
    if gradient < LABEL_WINTER_MIN:
        return LABEL_TILTING
    return LABEL_WINTER


def evaluate_trigger(signal):
    """Evaluate the winter trigger into a continuous WinterState.

    UNKNOWN never PASS: an unreadable signal yields gradient 0.0,
    label SUMMER, provenance UNKNOWN — the mode stays SUMMER, the
    known state. Winter is never assumed.

    Otherwise the gradient is the weighted, clamped sum of the three
    sub-tilts — continuous in every input, no cliffs anywhere.
    """
    if not isinstance(signal, WinterSignal):
        signal = WinterSignal()  # garbage in -> unreadable -> SUMMER
    snapshot = signal.snapshot()

    if not signal.readable:
        return WinterState(
            gradient=0.0,
            label=LABEL_SUMMER,
            reasons=[
                "trigger signal unreadable (no numeric readings, no "
                "verified crisis): UNKNOWN never PASS — mode stays "
                "SUMMER, the known state. Winter is not assumed."
            ],
            provenance="UNKNOWN",
            signal_snapshot=snapshot,
        )

    reasons = []
    contributions = []

    if signal.peg_deviation is not None:
        tilt = peg_tilt(signal.peg_deviation)
        contrib = WEIGHT_PEG * tilt
        contributions.append(contrib)
        reasons.append(
            f"peg: measured |deviation|={abs(float(signal.peg_deviation)):.4f} "
            f"vs PROPOSED band edge {PEG_BAND_EDGE} (soft {PEG_BAND_SOFT}) "
            f"-> tilt {tilt:.4f} x weight {WEIGHT_PEG} = {contrib:.4f}"
        )

    if signal.activity_delta is not None:
        tilt = activity_tilt(signal.activity_delta)
        contrib = WEIGHT_ACTIVITY * tilt
        contributions.append(contrib)
        drop = max(0.0, -float(signal.activity_delta))
        reasons.append(
            f"activity: measured drop={drop:.4f} "
            f"vs PROPOSED edge {ACTIVITY_DROP_EDGE} (soft {ACTIVITY_DROP_SOFT}) "
            f"-> tilt {tilt:.4f} x weight {WEIGHT_ACTIVITY} = {contrib:.4f}"
        )

    if signal.crisis_declared and signal.crisis_verified:
        contrib = WEIGHT_CRISIS * 1.0
        contributions.append(contrib)
        reasons.append(
            f"crisis: declared AND verified -> full weight {WEIGHT_CRISIS}"
        )
    elif signal.crisis_declared and not signal.crisis_verified:
        reasons.append(
            "crisis: declared but NOT verified — not a signal. A claim "
            "without verification cannot tilt the gradient; using it to "
            "pull value inward is the phantom pattern."
        )

    gradient = _clamp01(sum(contributions))
    return WinterState(
        gradient=gradient,
        label=_label_for(gradient),
        reasons=reasons,
        provenance="DERIVED",
        signal_snapshot=snapshot,
    )


# ---------------------------------------------------------------------------
# emission throttle — the gradient slows emission, never stops it.
# ---------------------------------------------------------------------------

def emission_multiplier(gradient):
    """Continuous emission multiplier: 1.0 at full summer, EMISSION_FLOOR
    at full winter. Protection, not shutdown — the floor is above zero
    so the economy never freezes."""
    g = _clamp01(gradient)
    return 1.0 - (1.0 - EMISSION_FLOOR) * g


def winter_aware_faucet(wallet, identity, amount, state, reserve=None):
    """Faucet throttled by the winter gradient.

    requested amount R at gradient g -> grants max(1, floor(R * m(g)))
    for R >= 1: slowed, never zeroed while anything was requested.
    The granted amount mints through the wallet's normal faucet (its own
    receipt); the throttle itself is logged to the winter receipt trail
    with the gradient, so the slowdown is auditable.
    """
    reserve = reserve or WinterReserve()
    if not isinstance(state, WinterState):
        raise MeterError("winter_aware_faucet needs a WinterState from "
                         "evaluate_trigger, not a guess at the weather")
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError(f"faucet amount must be a positive integer of "
                         f"{UNIT}; got {amount!r}")
    mult = emission_multiplier(state.gradient)
    granted = max(1, math.floor(amount * mult))
    envelope = wallet.faucet(identity, granted)
    record = {
        "schema": SCHEMA,
        "type": "EMISSION_THROTTLE",
        "identity": identity,
        "requested": amount,
        "granted": granted,
        "withheld": amount - granted,
        "gradient": state.gradient,
        "gradient_label": state.label,
        "multiplier": mult,
        "unit": UNIT,
        "testnet": True,
        "issued_at": _utc_now(),
        "provenance": "DERIVED",
        "note": (
            f"Winter emission throttle: gradient {state.gradient:.3f} "
            f"({state.label}) slowed emission {amount} -> {granted} "
            f"{UNIT}. Protection, not shutdown: the floor is "
            f"{EMISSION_FLOOR} of summer emission."
            if granted < amount else
            f"Summer emission: gradient {state.gradient:.3f} "
            f"({state.label}), no throttle; {granted} {UNIT} minted."
        ),
    }
    if granted < amount:
        # The slowdown is a winter claim on the economy: it goes on the
        # receipt trail where L5 can audit it.
        reserve._log(record)
    return envelope, record


# ---------------------------------------------------------------------------
# WinterReserve — the Peg Regulation Reserve (the starch store).
# ---------------------------------------------------------------------------

class _WinterCommitStore:
    """DCLM-internal adapter: lets writes.dclm_commit drive the reserve's
    single mutation point.

    One commit moves value between the identity's circulation balance
    (the wallet ledger) and the reserve holdings — both updates happen
    inside apply_write, which dclm_commit calls exactly once, only
    after a DCLM-issued GRANT verdict. The receipt is the winter
    receipt built below; the signed envelope is appended to the
    winter receipt trail.
    """

    def __init__(self, wallet, reserve, *, identity, receipt,
                 circulation_before, circulation_after,
                 reserve_before, reserve_after):
        self._wallet = wallet
        self._reserve = reserve
        self._identity = identity
        self._receipt = receipt
        self._circulation_before = circulation_before
        self._circulation_after = circulation_after
        self._reserve_before = reserve_before
        self._reserve_after = reserve_after

    def apply_write(self, kind, payload):
        """THE single mutation point for winter writes: circulation and
        reserve move together, or neither moves."""
        self._wallet._ledger["balances"][self._identity] = \
            self._circulation_after
        self._wallet._assert_ledger_nonnegative()
        self._reserve._store["holdings"][self._identity] = \
            self._reserve_after
        if self._reserve_after < 0:
            raise MeterError(
                "RESERVE VIOLATION: negative starch holding "
                f"{self._reserve_after} for {self._identity!r} — "
                "refusing to continue"
            )
        self._wallet._save()
        self._reserve._save()
        return {
            "identity": self._identity,
            "circulation_before": self._circulation_before,
            "circulation_after": self._circulation_after,
            "reserve_before": self._reserve_before,
            "reserve_after": self._reserve_after,
        }

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        # The winter receipt IS the receipt: built with its winter
        # reason and provenance before the commit.
        return self._receipt

    def append_receipt(self, envelope):
        self._reserve._log(envelope["receipt"])


class WinterReserve:
    """The Peg Regulation Reserve — the starch store.

    holdings: identity -> integer test-keys moved out of circulation
    for winter protection. Persisted under state-winter/; every claim
    (granted or refused) is appended to the winter receipt trail.
    """

    def __init__(self, state_dir=None):
        self.state_dir = state_dir or os.environ.get(
            "UNITY_WINTER_STATE_DIR", DEFAULT_STATE_DIR
        )
        os.makedirs(self.state_dir, exist_ok=True)
        self.reserve_path = os.path.join(self.state_dir, RESERVE_FILENAME)
        self.receipts_path = os.path.join(self.state_dir, RECEIPTS_FILENAME)
        self._store = self._load()

    # -- persistence ------------------------------------------------------

    def _load(self):
        if not os.path.exists(self.reserve_path):
            return {"schema": SCHEMA, "holdings": {}}
        with open(self.reserve_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") != SCHEMA:
            raise MeterError(
                f"reserve schema mismatch: expected {SCHEMA}, found "
                f"{data.get('schema')!r} — refusing to read foreign state"
            )
        return data

    def _save(self):
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".winter-reserve-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._store, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, self.reserve_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _log(self, receipt):
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True) + "\n")

    # -- public API ---------------------------------------------------------

    def holding(self, identity):
        """Test-keys this identity currently has stored in the reserve.
        Unknown identity -> 0, honestly."""
        return self._store["holdings"].get(identity, 0)

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _require_testnet(identity):
        if not isinstance(identity, str) or not identity.startswith(
                IDENTITY_PREFIX):
            raise MeterRefused(
                "structural refusal: identity must start with "
                f"{IDENTITY_PREFIX!r}; got {identity!r}. Testnet only."
            )

    @staticmethod
    def _require_winter_reason(reason):
        """Every stored/released unit carries its winter reason: which
        trigger condition, what was measured, what threshold judged it.
        A missing reason is a structural defect — refused, not guessed."""
        if not isinstance(reason, dict):
            raise MeterError(
                f"winter reason must be a dict with {WINTER_REASON_FIELDS}; "
                f"got {reason!r}"
            )
        missing = [f for f in WINTER_REASON_FIELDS if f not in reason]
        if missing:
            raise MeterError(
                f"winter reason missing fields {missing}: a winter claim "
                f"must name {WINTER_REASON_FIELDS}"
            )
        return {
            "trigger_condition": str(reason["trigger_condition"]),
            "measured_value": reason["measured_value"],
            "threshold": str(reason["threshold"]),
        }

    def _receipt_id(self, identity, action):
        return hashlib.sha256(
            f"{SCHEMA}|{identity}|{action}|{self._utc_now()}|"
            f"{os.urandom(8).hex()}".encode("utf-8")
        ).hexdigest()

    def _assert_receipt_labeled(self, receipt):
        label = receipt.get("provenance")
        if label not in PROVENANCE_LABELS:
            raise MeterError(f"receipt missing valid provenance label: "
                             f"{receipt!r}")
        if receipt.get("outcome") == OUTCOME_GRANTED and label == "UNKNOWN":
            raise MeterError(
                "UNKNOWN is never PASS: refusing to grant on an UNKNOWN label"
            )

    def _refuse(self, identity, action, reason_code, *, winter_reason,
                state, amount=None, note_extra=""):
        receipt = {
            "schema": SCHEMA,
            "type": "REFUSAL",
            "action": action,
            "identity": identity,
            "amount": amount,
            "unit": UNIT,
            "testnet": True,
            "outcome": OUTCOME_REFUSED,
            "reason": reason_code,
            "winter_reason": winter_reason,
            "claimant": identity,
            "signal_snapshot": state.signal_snapshot if state else None,
            "gradient": state.gradient if state else None,
            "gradient_label": state.label if state else None,
            "l5_audit": True,
            "receipt_id": self._receipt_id(identity, action),
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",
            "note": (
                "Refusal, logged for L5 audit: every winter claim — "
                "granted or refused — lands on the receipt trail with "
                "the claimant identity and the signal snapshot. "
                + note_extra
            ).strip(),
        }
        if reason_code not in REFUSAL_REASONS:
            raise MeterError(f"unknown refusal reason: {reason_code!r}")
        self._assert_receipt_labeled(receipt)
        # The refusal IS a winter claim on the trail: L5 watches refused
        # claims too — a burst of phantom claims is itself a signal.
        self._log(receipt)
        # PURIFY ON EXIT (refusal): labeled + signed; the identity is the
        # presented one (audited, not trusted).
        return purify_output(
            sign_receipt(receipt),
            context={"path": "winter", "signed": True,
                     "identity_as_presented": True},
        )


# ---------------------------------------------------------------------------
# module-level winter operations
# ---------------------------------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _default_wallet():
    return Wallet()


def _default_reserve():
    return WinterReserve()


def _validate_amount(amount):
    if isinstance(amount, bool) or not isinstance(amount, int) \
            or amount <= 0:
        raise ValueError(
            f"winter amount must be a positive integer of {UNIT}; "
            f"got {amount!r}"
        )


def _evaluate_claim(signal):
    """Evaluate the claim's supporting signal. No signal, an unreadable
    signal, or pressure below the claim floor -> the claim is unsupported."""
    if signal is None:
        signal = WinterSignal()  # unreadable -> UNKNOWN -> stays SUMMER
    state = evaluate_trigger(signal)
    supported = (
        state.provenance != "UNKNOWN"
        and state.gradient >= WINTER_CLAIM_MIN_GRADIENT
    )
    return state, supported


def winter_store(identity, amount, reason, *, wallet=None, reserve=None,
                 signal=None):
    """Move test-keys from circulation into the Peg Regulation Reserve —
    sap flowing back down to protect the root.

    Winter flow is PROTECTION, never accumulation:
      * the claim needs a supporting signal (evaluate_trigger gradient
        >= WINTER_CLAIM_MIN_GRADIENT). A claim with no supporting
        signal — including a declared-but-unverified crisis — is the
        phantom pattern: REFUSED as PHANTOM and logged for L5.
      * the reserve holds at most SURVIVAL_NEED_CAP per identity. What
        fits is stored; the excess keeps flowing outward (it stays in
        circulation), and the receipt says exactly how much of each.
      * the identity's circulation balance must cover what is stored;
        the ledger never goes negative.

    Every stored unit is receipted with its winter reason (trigger
    condition, measured value, threshold). The signed receipt lands on
    the winter receipt trail with the claimant identity and the signal
    snapshot, where L5 can audit it.

    Returns a SIGNED receipt envelope (GRANTED, or REFUSED with the
    honest reason — a signed refusal is a verifiable honest statement,
    not a silent drop).
    """
    reserve = reserve or _default_reserve()
    wallet = wallet or _default_wallet()
    # PURIFY ON ENTRY: the medium first. Anonymous or forged identities
    # are refused here as PurificationRefused — before any winter logic.
    purify_input(
        {"identity": identity, "action": "WINTER_STORE", "amount": amount,
         "claims": [{"claim": "winter-store-request",
                     "provenance": "DERIVED"}]},
        context={"path": "winter.winter_store"},
    )
    reserve._require_testnet(identity)
    _validate_amount(amount)
    winter_reason = reserve._require_winter_reason(reason)

    # --- anti-gaming: no supporting signal, no inward flow ---------------
    state, supported = _evaluate_claim(signal)
    if not supported:
        phantom = bool(
            signal is not None
            and getattr(signal, "crisis_declared", False)
            and not getattr(signal, "crisis_verified", False)
        )
        return reserve._refuse(
            identity, "WINTER_STORE", REASON_PHANTOM,
            winter_reason=winter_reason, state=state, amount=amount,
            note_extra=(
                "PHANTOM: claiming winter to pull value inward with no "
                "supporting signal"
                + (" — crisis declared but NOT verified" if phantom else "")
                + f". Evaluated gradient {state.gradient:.3f} below the "
                f"claim floor {WINTER_CLAIM_MIN_GRADIENT}."
            ),
        )

    # --- survival-need cap: the root stores only what it needs ----------
    current = reserve.holding(identity)
    room = SURVIVAL_NEED_CAP - current
    if room <= 0:
        return reserve._refuse(
            identity, "WINTER_STORE", REASON_STORE_AT_SURVIVAL_NEED,
            winter_reason=winter_reason, state=state, amount=amount,
            note_extra=(
                f"Store refused honestly: reserve already holds {current} "
                f"{UNIT}, the survival-need cap is {SURVIVAL_NEED_CAP}. "
                f"The {amount} {UNIT} stay in circulation — excess keeps "
                f"flowing outward."
            ),
        )
    store_amount = min(amount, room)
    excess = amount - store_amount  # excess keeps flowing outward

    # --- circulation must cover it --------------------------------------
    circulation_before = wallet.balance(identity)
    if circulation_before < store_amount:
        return reserve._refuse(
            identity, "WINTER_STORE", REASON_INSUFFICIENT_KEYS,
            winter_reason=winter_reason, state=state, amount=store_amount,
            note_extra=(
                f"Insufficient circulation: {circulation_before} {UNIT} "
                f"available, {store_amount} requested for the store. The "
                f"ledger never goes negative; nothing moved."
            ),
        )

    circulation_after = circulation_before - store_amount
    reserve_after = current + store_amount
    receipt = {
        "schema": SCHEMA,
        "type": "RECEIPT",
        "action": "WINTER_STORE",
        "identity": identity,
        "amount": store_amount,
        "requested": amount,
        "excess_circulating": excess,
        "unit": UNIT,
        "testnet": True,
        "circulation_before": circulation_before,
        "circulation_after": circulation_after,
        "reserve_before": current,
        "reserve_after": reserve_after,
        "survival_need_cap": SURVIVAL_NEED_CAP,
        "outcome": OUTCOME_GRANTED,
        "reason": None,
        "winter_reason": {
            **winter_reason,
            "gradient": state.gradient,
            "gradient_label": state.label,
            "signal_provenance": state.provenance,
            "evaluated_reasons": state.reasons,
        },
        "claimant": identity,
        "signal_snapshot": state.signal_snapshot,
        "l5_audit": True,
        "receipt_id": reserve._receipt_id(identity, "WINTER_STORE"),
        "issued_at": _utc_now(),
        "provenance": "DERIVED",
        "note": (
            f"Winter protection: {store_amount} {UNIT} moved from "
            f"circulation into the Peg Regulation Reserve (the starch "
            f"store) at gradient {state.gradient:.3f} ({state.label}). "
            + (f"{excess} {UNIT} exceeded the survival-need cap "
               f"({SURVIVAL_NEED_CAP}) and keeps flowing outward. "
               if excess else "")
            + "Logged for L5 audit with claimant identity and signal "
            "snapshot. TEST units only — not dollars, not eFuse."
        ),
    }
    reserve._assert_receipt_labeled(receipt)

    # RIGHTS, then WRITE: the store flows through the single commit path.
    # check_rights authorizes WINTER_STORE for the DCLM-internal winter
    # component; dclm_commit performs the one mutation and emits the
    # signed receipt. The thin client has no path here.
    verdict = check_rights(
        identity, "WINTER_STORE",
        {"internal": "dclm.winter", "schema": SCHEMA,
         "winter_approved": True, "gradient": state.gradient},
    )
    # PURIFY IN FLIGHT: the store transition is checked — kind
    # whitelisted, receipt planned and labeled, the circulation/reserve
    # movement declared — before writes.py commits.
    purify_transition(
        {"circulation": circulation_before, "reserve": current},
        {"circulation": circulation_after, "reserve": reserve_after},
        "WINTER_STORE",
        context={"receipt": receipt, "identity": identity,
                 "path": "winter.winter_store"},
    )
    envelope = dclm_commit(
        "WINTER_STORE", receipt, verdict,
        _WinterCommitStore(
            wallet, reserve, identity=identity, receipt=receipt,
            circulation_before=circulation_before,
            circulation_after=circulation_after,
            reserve_before=current, reserve_after=reserve_after,
        ),
    )
    # PURIFY ON EXIT: labeled, signed, identity-bound.
    return purify_output(
        envelope,
        context={"path": "winter.winter_store", "signed": True},
    )


def winter_release(identity, amount, reason, *, wallet=None, reserve=None,
                   signal=None):
    """Move test-keys from the Peg Regulation Reserve back into
    circulation — spring: the stored value re-mobilizes outward.

    Release flows outward (the summer direction), so it cannot game
    winter: no signal is required, but the winter reason is still
    mandatory and the release is still receipted and logged for L5.
    The reserve holding must cover the release; the receipt carries the
    spring reason (which trigger condition cleared, measured value,
    threshold).

    Returns a SIGNED receipt envelope.
    """
    reserve = reserve or _default_reserve()
    wallet = wallet or _default_wallet()
    # PURIFY ON ENTRY: the medium first — same contract as the store path.
    purify_input(
        {"identity": identity, "action": "WINTER_RELEASE", "amount": amount,
         "claims": [{"claim": "winter-release-request",
                     "provenance": "DERIVED"}]},
        context={"path": "winter.winter_release"},
    )
    reserve._require_testnet(identity)
    _validate_amount(amount)
    winter_reason = reserve._require_winter_reason(reason)

    if signal is None:
        state = evaluate_trigger(WinterSignal())
    else:
        state = evaluate_trigger(signal)

    current = reserve.holding(identity)
    if current < amount:
        return reserve._refuse(
            identity, "WINTER_RELEASE", REASON_INSUFFICIENT_RESERVE,
            winter_reason=winter_reason, state=state, amount=amount,
            note_extra=(
                f"Insufficient starch: reserve holds {current} {UNIT}, "
                f"{amount} requested for release. Nothing moved."
            ),
        )

    circulation_before = wallet.balance(identity)
    circulation_after = circulation_before + amount
    reserve_after = current - amount
    receipt = {
        "schema": SCHEMA,
        "type": "RECEIPT",
        "action": "WINTER_RELEASE",
        "identity": identity,
        "amount": amount,
        "unit": UNIT,
        "testnet": True,
        "circulation_before": circulation_before,
        "circulation_after": circulation_after,
        "reserve_before": current,
        "reserve_after": reserve_after,
        "outcome": OUTCOME_GRANTED,
        "reason": None,
        "winter_reason": {
            **winter_reason,
            "gradient": state.gradient,
            "gradient_label": state.label,
            "signal_provenance": state.provenance,
            "evaluated_reasons": state.reasons,
        },
        "claimant": identity,
        "signal_snapshot": state.signal_snapshot,
        "l5_audit": True,
        "receipt_id": reserve._receipt_id(identity, "WINTER_RELEASE"),
        "issued_at": _utc_now(),
        "provenance": "DERIVED",
        "note": (
            f"Spring: {amount} {UNIT} released from the Peg Regulation "
            f"Reserve back into circulation at gradient "
            f"{state.gradient:.3f} ({state.label}) — the stored value "
            f"re-mobilizes outward. Logged for L5 audit. TEST units "
            f"only — not dollars, not eFuse."
        ),
    }
    reserve._assert_receipt_labeled(receipt)

    # RIGHTS, then WRITE: same single commit path as the store.
    verdict = check_rights(
        identity, "WINTER_RELEASE",
        {"internal": "dclm.winter", "schema": SCHEMA,
         "winter_approved": True, "gradient": state.gradient},
    )
    # PURIFY IN FLIGHT: the release transition is checked before
    # writes.py commits.
    purify_transition(
        {"circulation": circulation_before, "reserve": current},
        {"circulation": circulation_after, "reserve": reserve_after},
        "WINTER_RELEASE",
        context={"receipt": receipt, "identity": identity,
                 "path": "winter.winter_release"},
    )
    envelope = dclm_commit(
        "WINTER_RELEASE", receipt, verdict,
        _WinterCommitStore(
            wallet, reserve, identity=identity, receipt=receipt,
            circulation_before=circulation_before,
            circulation_after=circulation_after,
            reserve_before=current, reserve_after=reserve_after,
        ),
    )
    # PURIFY ON EXIT: labeled, signed, identity-bound.
    return purify_output(
        envelope,
        context={"path": "winter.winter_release", "signed": True},
    )

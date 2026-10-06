"""
DCLM TAPPING — "The tree survives tapping."

David's binding law: maple trees in Canada get tapped for sap every
spring — value leaves the system — and the tree survives and thrives.
The economy is NOT hermetically sealed: value CAN leave (to fiat, to
the outside world, to members' real needs) without killing the system.
But tapping follows the maple rules:

  1. ONLY IN SEASON. Tapping happens in the surplus season — never in
     summer growth, never in deep winter. Outflow only from VERIFIED
     SURPLUS: never from core operating flow, never during
     winter-protection mode.
  2. LIMITED TAPS. One or two taps per tree; the tree's size sets the
     limit. Rate-limited outflow, capped per member per season,
     proportional to system health. The tap rate is HELD-FOR-DAVID.
  3. ONLY MATURE TREES. You don't tap saplings. No outflow until the
     system is established — pools healthy, peg holds, reserve funded.
     Immaturity = no taps. The maturity threshold is HELD-FOR-DAVID.
  4. THE TREE HEALS. The tap hole closes; the tree keeps growing. Every
     outflow receipted; replenishment through continued merit-gated
     emission; total outflow per season NEVER exceeds the
     replenishment rate.

THE DISTINCTION THAT KEEPS IT PURE: tapping is the system releasing
surplus outward through rules — it is NOT the founder extracting.
Founder extraction remains FORBIDDEN by the creed. Tapping serves
members' real-world needs; extraction serves self. The maple law
governs the first; the creed forbids the second.

Tap outflows are WRITES: they flow through rights.check_rights and
writes.dclm_commit with kind TAP_OUTFLOW. DCLM holds the RIGHTS and
performs the WRITES; the thin client never writes.

Winter interface: TapSeason consults winter.py (the winter gradient
0.0-1.0 and Peg Regulation Reserve module) FOR REAL: a winter_signal
(a winter.WinterSignal, or a dict of its fields) is evaluated through
winter.evaluate_trigger into a WinterState, and the tap-side
protection threshold applies to the real gradient. If winter.py is
absent, the winter interface is PENDING and the season degrades to
CLOSED honestly — PENDING winter state never opens a season. UNKNOWN
is never PASS: any unscorable input yields an UNKNOWN maturity or
UNKNOWN surplus, and no taps flow.

Testnet only. Units are test-keys (never dollars, never eFuse).
Provenance labels on every receipt.
"""

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from compute import PROVENANCE_LABELS  # noqa: E402 — one provenance enum
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from writes import CommitStore, dclm_commit, sign_commit  # noqa: E402
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    purify_input,
    purify_output,
    purify_transition,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.tap.v1.testnet"
KIND_TAP_OUTFLOW = "TAP_OUTFLOW"
IDENTITY_PREFIX = "unity:testnet:"
UNIT = "test-keys"

# --- winter interface -------------------------------------------------------
# winter.py (the winter gradient 0.0-1.0 and Peg Regulation Reserve
# module) landed mid-build and TapSeason integrates with it FOR REAL:
# TapSeason takes a winter_signal (a winter.WinterSignal, or a dict of
# its fields) and evaluates it through winter.evaluate_trigger into a
# WinterState; the tap-side protection threshold
# (WINTER_GRADIENT_MAX_FOR_TAPPING, HELD-FOR-DAVID) applies to the real
# gradient. winter.py exposes no protection_mode(): labels are
# display-only there, so the tap side owns the protection line.
# If winter.py is absent, the interface is PENDING and the season
# degrades to CLOSED honestly — PENDING winter state never opens a
# season, never grants a tap.
try:
    import winter  # noqa: F401
    WINTER_INTERFACE = "READY"
except ImportError:
    winter = None
    WINTER_INTERFACE = "PENDING"

# --- HELD-FOR-DAVID parameters ----------------------------------------------
# PROPOSED defaults with reasoning (see TAPPING_LAW.md). David decides
# the final numbers; these are the mechanism's working values.
#
# TAP_RATE_PER_MEMBER_SEASON: the per-member seasonal tap cap. Proposed
#   100 test-keys/season — 20x a COMPUTE run (5) and 100x a SEARCH (1):
#   large enough to serve a real need, small enough that one member
#   cannot bleed a season's replenishment alone.
# MAX_PER_TAP: the single-tap limit. Proposed 50 test-keys — half the
#   seasonal cap, so a member taps at least twice to reach the cap and
#   every draw stays receipt-visible.
# MATURITY_THRESHOLD: maturity_score() >= 0.70 to open the season. The
#   system must be clearly healthy (not borderline) before saplings are
#   declared trees.
# WINTER_GRADIENT_MAX_FOR_TAPPING: the tap-side protection line,
#   applied to winter.evaluate_trigger's real gradient. Proposed 0.50 —
#   mid-TILTING on winter's own bands (SUMMER < 0.25, WINTER >= 0.75):
#   taps stop well before deep winter, while the root is only starting
#   to tilt. winter.py defines no protection test of its own (labels are
#   display-only there), so the tap side owns this line; HELD-FOR-DAVID.
TAP_RATE_PER_MEMBER_SEASON = 100
MAX_PER_TAP = 50
MATURITY_THRESHOLD = 0.70
WINTER_GRADIENT_MAX_FOR_TAPPING = 0.50

# --- founder creed boundary -------------------------------------------------
# Founder extraction is FORBIDDEN by the creed. Enforced here: any
# identity matching the founder marker is refused before any season
# evaluation.
#
# ENFORCED: the prefix/marker check below — a live refusal gate.
# CONVENTIONAL (not yet issued): the actual founder identity string.
# The identity system (gate.py) has not yet issued a founder binding,
# so the marker is registered but unpopulated; any identity claiming
# the founder prefix is refused on sight. When the founder binding is
# issued, register its exact string (env UNITY_FOUNDER_IDENTITY) and
# the check stays the same shape.
FOUNDER_IDENTITY_PREFIX = "unity:testnet:founder:"

# --- outcomes / refusal reasons ---------------------------------------------
OUTCOME_GRANTED = "GRANTED"
OUTCOME_REFUSED = "REFUSED"

REASON_OFF_SEASON = "OFF_SEASON"
REASON_WINTER_PROTECTION = "WINTER_PROTECTION"
REASON_NO_VERIFIED_SURPLUS = "NO_VERIFIED_SURPLUS"
REASON_UNKNOWN_MATURITY = "UNKNOWN_MATURITY"
REASON_IMMATURE_SYSTEM = "IMMATURE_SYSTEM"
REASON_HEALING_UNVERIFIED = "HEALING_UNVERIFIED"
REASON_TAP_LIMIT = "TAP_LIMIT"
REASON_REPLENISHMENT_EXCEEDED = "REPLENISHMENT_EXCEEDED"
REASON_FOUNDER_EXTRACTION_FORBIDDEN = "FOUNDER_EXTRACTION_FORBIDDEN"
REASON_PURPOSE_REQUIRED = "PURPOSE_REQUIRED"
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_INVALID_AMOUNT = "INVALID_AMOUNT"

REFUSAL_REASONS = frozenset({
    REASON_OFF_SEASON,
    REASON_WINTER_PROTECTION,
    REASON_NO_VERIFIED_SURPLUS,
    REASON_UNKNOWN_MATURITY,
    REASON_IMMATURE_SYSTEM,
    REASON_HEALING_UNVERIFIED,
    REASON_TAP_LIMIT,
    REASON_REPLENISHMENT_EXCEEDED,
    REASON_FOUNDER_EXTRACTION_FORBIDDEN,
    REASON_PURPOSE_REQUIRED,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_INVALID_AMOUNT,
})

DEFAULT_STATE_DIR = os.path.join(_HERE, "state-tap")
TAP_STATE_FILENAME = "tap-state.json"
TAP_RECEIPTS_FILENAME = "tap-receipts.jsonl"


class TapError(Exception):
    """Base class for tapping failures."""


# ---------------------------------------------------------------------------
# Provenance-labeled measures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Measure:
    """A number with a provenance label. UNKNOWN is never PASS: any
    measure labeled UNKNOWN (or unscorable) poisons maturity and
    surplus to UNKNOWN, which closes the season."""
    value: object
    provenance: str


def _labeled_number(measure):
    """Return (float_value, label) for a numeric Measure, or
    (None, "UNKNOWN") if unscorable. Never raises."""
    try:
        if not isinstance(measure, Measure):
            return None, "UNKNOWN"
        label = measure.provenance
        if label not in PROVENANCE_LABELS:
            return None, "UNKNOWN"
        if label == "UNKNOWN":
            return None, "UNKNOWN"
        value = float(measure.value)
        if value != value or value in (float("inf"), float("-inf")):
            return None, "UNKNOWN"  # NaN / infinite: unscorable
        return value, label
    except (TypeError, ValueError):
        return None, "UNKNOWN"


# ---------------------------------------------------------------------------
# TapSeason — evaluates whether tapping season is open
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SeasonVerdict:
    """The outcome of the season evaluation, with the full reason chain.

    season_open True  -> a tap may be requested (limits still apply).
    season_open False -> reason carries the TRUE reason; chain carries
                         the ordered checks that produced it.
    """
    season_open: bool
    reason: object          # None when open; a REASON_* when closed
    chain: tuple            # ordered (check, result, detail) entries
    season_id: str
    surplus: object         # float test-keys, or None when UNKNOWN
    surplus_provenance: str
    maturity: object        # float 0..1, or None when UNKNOWN
    maturity_provenance: str
    winter_gradient: object  # float 0..1, or None when PENDING/UNKNOWN
    winter_interface: str    # "READY" | "PENDING"


class TapSeason:
    """Evaluates the four maple rules against labeled system health.

    Inputs are all Measures (value + provenance label):
      pool_health        — fraction of pools healthy, 0.0-1.0
      peg_deviation_bp   — peg deviation in basis points (>= 0)
      reserve_total      — Peg Regulation Reserve total, test-keys
      reserve_survival_need — reserve floor the system must never
                              tap below, test-keys
      pool_headroom      — healthy-pool headroom above operating
                           need, test-keys
      season_replenishment — merit-gated emission credited this
                              season, test-keys (the healing side)

    winter_signal — the winter trigger signal: a winter.WinterSignal,
      a dict of its fields, or None (no signal -> winter stays SUMMER,
      "winter is never assumed", noted in the chain). Evaluated for
      real through winter.evaluate_trigger.

    Any unscorable input -> UNKNOWN -> season closed. UNKNOWN never
    PASS.
    """

    # Peg health: deviation beyond PEG_DEVIATION_BP_MAX scores 0.
    PEG_DEVIATION_BP_MAX = 100.0  # proposed tap-side scale

    def __init__(self, *, pool_health, peg_deviation_bp,
                 reserve_total, reserve_survival_need,
                 pool_headroom, season_replenishment,
                 season_id=None, winter_module="__auto__",
                 winter_signal=None, state_dir=None):
        self.pool_health = pool_health
        self.peg_deviation_bp = peg_deviation_bp
        self.reserve_total = reserve_total
        self.reserve_survival_need = reserve_survival_need
        self.pool_headroom = pool_headroom
        self.season_replenishment = season_replenishment
        self.season_id = season_id or self._season_id_for(
            datetime.now(timezone.utc))
        if winter_module == "__auto__":
            self._winter = winter
            self._winter_interface = WINTER_INTERFACE
        else:
            # Injectable for tests: a fake winter module, or None to
            # simulate the PENDING interface honestly.
            self._winter = winter_module
            self._winter_interface = (
                "READY" if winter_module is not None else "PENDING"
            )
        # The winter trigger signal: a winter.WinterSignal, or a dict of
        # its fields (peg_deviation/activity_delta/crisis_* + per-input
        # provenance). None -> empty signal -> winter.evaluate_trigger
        # yields SUMMER ("winter is never assumed"), noted in the chain.
        self._winter_signal = winter_signal
        self.state_dir = state_dir or os.environ.get(
            "UNITY_TAP_STATE_DIR", DEFAULT_STATE_DIR)

    @staticmethod
    def _season_id_for(now):
        """Annual tapping season, like the maple run: one season per
        calendar year."""
        return f"{now.year}-tapping"

    # -- maturity ----------------------------------------------------------
    def maturity_score(self):
        """Maturity from pool health, peg state, reserve funding.

        score = 0.4*pool_health + 0.3*peg_score + 0.3*reserve_score,
        each input provenance-labeled. Any unscorable input ->
        (None, "UNKNOWN"): saplings are never declared mature on
        unknown evidence. UNKNOWN never PASS.
        """
        pool, pool_label = _labeled_number(self.pool_health)
        peg_bp, peg_label = _labeled_number(self.peg_deviation_bp)
        total, total_label = _labeled_number(self.reserve_total)
        need, need_label = _labeled_number(self.reserve_survival_need)

        inputs = ((pool, pool_label), (peg_bp, peg_label),
                  (total, total_label), (need, need_label))
        if any(v is None or label == "UNKNOWN" for v, label in inputs):
            return None, "UNKNOWN"
        if not (0.0 <= pool <= 1.0) or peg_bp < 0 or need <= 0:
            return None, "UNKNOWN"  # out-of-range: unscorable, honestly

        peg_score = 1.0 - min(1.0, peg_bp / self.PEG_DEVIATION_BP_MAX)
        reserve_score = min(1.0, total / need)
        score = 0.4 * pool + 0.3 * peg_score + 0.3 * reserve_score
        return round(score, 4), "DERIVED"  # derived in-process from labels

    # -- surplus -----------------------------------------------------------
    def verified_surplus(self):
        """VERIFIED SURPLUS = reserve above survival-need + healthy-pool
        headroom. All in test-keys. Any unscorable input ->
        (None, "UNKNOWN"): surplus is never assumed."""
        total, total_label = _labeled_number(self.reserve_total)
        need, need_label = _labeled_number(self.reserve_survival_need)
        headroom, headroom_label = _labeled_number(self.pool_headroom)
        if any(v is None or label == "UNKNOWN"
               for v, label in ((total, total_label), (need, need_label),
                                (headroom, headroom_label))):
            return None, "UNKNOWN"
        if total < 0 or need <= 0 or headroom < 0:
            return None, "UNKNOWN"
        surplus = max(0.0, total - need) + headroom
        return round(surplus, 4), "DERIVED"

    # -- winter ------------------------------------------------------------
    def _winter_gradient(self):
        """The winter gradient 0.0-1.0, evaluated FOR REAL through
        winter.evaluate_trigger on the season's winter_signal.

        Returns (gradient, note). (None, note) when the interface is
        PENDING, the signal is unscorable, or evaluation fails — all
        close the season honestly. A missing signal is NOT pending:
        winter.evaluate_trigger yields SUMMER for an unreadable signal
        ("winter is never assumed"), and the chain records that.
        """
        if self._winter is None:
            return None, "winter interface PENDING: winter.py not present"
        try:
            evaluate = getattr(self._winter, "evaluate_trigger", None)
            signal_cls = getattr(self._winter, "WinterSignal", None)
            if callable(evaluate) and signal_cls is not None:
                signal = self._build_winter_signal(signal_cls)
                state = evaluate(signal)
                g = float(state.gradient)
                if not (0.0 <= g <= 1.0) or g != g:
                    return None, f"winter gradient unscorable: {g!r}"
                return g, (
                    f"winter.evaluate_trigger -> gradient={g:.4f} "
                    f"label={state.label} "
                    f"signal_provenance={state.provenance}; "
                    f"{len(state.reasons)} reason(s): "
                    + "; ".join(state.reasons[:3])
                )
            # Fallback duck-type: a winter module exposing
            # winter_gradient()/protection_mode() directly (test
            # doubles, forward-compatible variants).
            return self._winter_gradient_ducktype()
        except Exception as exc:  # noqa: BLE001 — fail closed, honestly
            return None, f"winter reading failed: {exc!r}"

    def _build_winter_signal(self, signal_cls):
        """Build the winter.WinterSignal from the season's winter_signal:
        a WinterSignal passes through; a dict fills its fields; None
        becomes an empty (unreadable -> SUMMER) signal."""
        provided = self._winter_signal
        if isinstance(provided, signal_cls):
            return provided
        if isinstance(provided, dict):
            known = {
                "peg_deviation", "peg_provenance",
                "activity_delta", "activity_provenance",
                "crisis_declared", "crisis_verified",
                "crisis_provenance",
            }
            return signal_cls(**{k: v for k, v in provided.items()
                                 if k in known})
        return signal_cls()

    def _winter_gradient_ducktype(self):
        """Fallback for winter modules exposing winter_gradient() /
        protection_mode() directly instead of evaluate_trigger."""
        prot = getattr(self._winter, "protection_mode", None)
        if callable(prot) and prot():
            return 1.0, ("winter.protection_mode() reports active "
                         "(winter-defined threshold takes precedence)")
        grad_fn = getattr(self._winter, "winter_gradient", None)
        if not callable(grad_fn):
            return None, ("winter module present but exposes no "
                          "evaluate_trigger()/winter_gradient()/protection_mode()")
        g = float(grad_fn())
        if not (0.0 <= g <= 1.0) or g != g:
            return None, f"winter_gradient() unscorable: {g!r}"
        return g, f"winter_gradient()={g}"

    # -- the season evaluation ---------------------------------------------
    def evaluate(self):
        """Run the maple rules in order. Returns a SeasonVerdict with
        the full reason chain."""
        chain = []

        # Rule order: winter first (never tap in deep winter), then
        # maturity (never tap saplings), then surplus (only in season),
        # then healing (the tree must be able to heal).
        gradient, winter_note = self._winter_gradient()
        if self._winter_interface == "PENDING":
            chain.append(("winter", "PENDING",
                          winter_note + " -> season closed, honestly"))
            return self._verdict(False, REASON_OFF_SEASON, chain,
                                 None, "UNKNOWN", None, "UNKNOWN",
                                 gradient)
        chain.append(("winter", "gradient", winter_note))
        if gradient is None:
            chain.append(("winter", "UNREADABLE",
                          "gradient unscorable -> season closed"))
            return self._verdict(False, REASON_WINTER_PROTECTION, chain,
                                 None, "UNKNOWN", None, "UNKNOWN",
                                 gradient)
        if gradient >= WINTER_GRADIENT_MAX_FOR_TAPPING:
            chain.append(("winter", "PROTECTION",
                          f"gradient {gradient} >= tap-side protection "
                          f"line {WINTER_GRADIENT_MAX_FOR_TAPPING} "
                          "(mid-TILTING on winter's own bands: taps stop "
                          "well before deep winter) -> protection mode, "
                          "no taps"))
            return self._verdict(False, REASON_WINTER_PROTECTION, chain,
                                 None, "DERIVED", None, "UNKNOWN",
                                 gradient)
        chain.append(("winter", "clear",
                      f"gradient {gradient} below protection threshold"))

        maturity, m_label = self.maturity_score()
        chain.append(("maturity", "score",
                      f"maturity={maturity} provenance={m_label} "
                      f"threshold={MATURITY_THRESHOLD}"))
        if maturity is None:
            chain.append(("maturity", "UNKNOWN",
                          "unscorable input -> UNKNOWN -> no taps; "
                          "UNKNOWN never PASS"))
            return self._verdict(False, REASON_UNKNOWN_MATURITY, chain,
                                 None, "UNKNOWN", None, m_label,
                                 gradient)
        if maturity < MATURITY_THRESHOLD:
            chain.append(("maturity", "IMMATURE",
                          f"{maturity} < {MATURITY_THRESHOLD}: "
                          "saplings are not tapped"))
            return self._verdict(False, REASON_IMMATURE_SYSTEM, chain,
                                 None, "DERIVED", maturity, m_label,
                                 gradient)

        surplus, s_label = self.verified_surplus()
        chain.append(("surplus", "computed",
                      f"surplus={surplus} {UNIT} provenance={s_label}"))
        if surplus is None:
            chain.append(("surplus", "UNKNOWN",
                          "surplus unverifiable -> no taps"))
            return self._verdict(False, REASON_NO_VERIFIED_SURPLUS, chain,
                                 None, "UNKNOWN", maturity, m_label,
                                 gradient)
        if surplus <= 0:
            chain.append(("surplus", "NONE",
                          "no verified surplus: the season is not the "
                          "surplus season"))
            return self._verdict(False, REASON_OFF_SEASON, chain,
                                 surplus, s_label, maturity, m_label,
                                 gradient)

        replenishment, r_label = _labeled_number(self.season_replenishment)
        chain.append(("healing", "replenishment",
                      f"season_replenishment={replenishment} {UNIT} "
                      f"provenance={r_label}"))
        if replenishment is None or replenishment < 0:
            chain.append(("healing", "UNVERIFIED",
                          "replenishment unscorable -> the tree cannot "
                          "prove it will heal -> no taps"))
            return self._verdict(False, REASON_HEALING_UNVERIFIED, chain,
                                 surplus, s_label, maturity, m_label,
                                 gradient)

        chain.append(("season", "OPEN",
                      f"season {self.season_id}: surplus {surplus} "
                      f"{UNIT}, maturity {maturity}, winter clear, "
                      f"replenishment {replenishment} {UNIT}"))
        return self._verdict(True, None, chain, surplus, s_label,
                             maturity, m_label, gradient)

    def _verdict(self, season_open, reason, chain, surplus,
                 surplus_provenance, maturity, maturity_provenance,
                 gradient):
        return SeasonVerdict(
            season_open=season_open,
            reason=reason,
            chain=tuple(chain),
            season_id=self.season_id,
            surplus=surplus,
            surplus_provenance=surplus_provenance,
            maturity=maturity,
            maturity_provenance=maturity_provenance,
            winter_gradient=gradient,
            winter_interface=self._winter_interface,
        )


# ---------------------------------------------------------------------------
# Tap ledger — cumulative season outflow state + the commit store
# ---------------------------------------------------------------------------

class _TapCommitStore(CommitStore):
    """DCLM-internal adapter: lets writes.dclm_commit drive the tap's
    single mutation point (season + member cumulative outflow), then
    returns the tap receipt unchanged and logs the signed envelope."""

    def __init__(self, tapper, *, receipt, season_id, identity,
                 amount, season_outflow_before, member_outflow_before,
                 replenishment):
        self._tapper = tapper
        self._receipt = receipt
        self._season_id = season_id
        self._identity = identity
        self._amount = amount
        self._season_before = season_outflow_before
        self._member_before = member_outflow_before
        self._replenishment = replenishment

    def apply_write(self, kind, payload):
        """THE single mutation point for tap outflows: advance the
        season and member cumulative outflow totals, persist, assert
        the healing invariant (outflow <= replenishment)."""
        seasons = self._tapper._state["seasons"]
        entry = seasons.setdefault(
            self._season_id,
            {"outflow_total": 0, "members": {},
             "replenishment": self._replenishment,
             "replenishment_provenance": "DERIVED"},
        )
        entry["outflow_total"] += self._amount
        entry["members"][self._identity] = (
            self._member_before + self._amount
        )
        entry["replenishment"] = self._replenishment
        if entry["outflow_total"] > self._replenishment:
            # The healing invariant broke between check and commit:
            # refuse to persist. (The check in request_tap prevents
            # this; this is the belt-and-suspenders assertion.)
            raise TapError(
                "HEALING INVARIANT VIOLATION: season outflow "
                f"{entry['outflow_total']} exceeds replenishment "
                f"{self._replenishment} — refusing to persist"
            )
        self._tapper._save()
        return {
            "op": "TAP_OUTFLOW",
            "identity": self._identity,
            "season_id": self._season_id,
            "amount": self._amount,
            "season_outflow_before": self._season_before,
            "season_outflow_after": entry["outflow_total"],
            "member_season_outflow_after": entry["members"][self._identity],
            "season_replenishment": self._replenishment,
        }

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        # The tap receipt IS the receipt: same bytes as built. Provenance
        # was asserted when the receipt was built.
        return self._receipt

    def append_receipt(self, envelope):
        self._tapper._log(envelope)


class Tapper:
    """Issues tap outflows: the system releasing surplus outward through
    the maple rules. Every granted tap is receipted via dclm_commit with
    kind TAP_OUTFLOW, carrying the season id, the reason chain, and the
    healing accounting (season outflow total vs replenishment)."""

    def __init__(self, season, state_dir=None):
        self.season = season
        self.state_dir = state_dir or season.state_dir or os.environ.get(
            "UNITY_TAP_STATE_DIR", DEFAULT_STATE_DIR
        )
        os.makedirs(self.state_dir, exist_ok=True)
        self.state_path = os.path.join(self.state_dir, TAP_STATE_FILENAME)
        self.receipts_path = os.path.join(self.state_dir,
                                          TAP_RECEIPTS_FILENAME)
        self._state = self._load()

    # -- persistence ------------------------------------------------------
    def _load(self):
        if not os.path.exists(self.state_path):
            return {"schema": SCHEMA, "seasons": {}}
        with open(self.state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") != SCHEMA:
            raise TapError(
                f"tap state schema mismatch: expected {SCHEMA}, found "
                f"{data.get('schema')!r} — refusing to read foreign state"
            )
        return data

    def _save(self):
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".tap-state-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, self.state_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _log(self, envelope):
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, sort_keys=True) + "\n")

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _tap_id(season_id, identity, amount, nonce):
        return hashlib.sha256(
            f"{SCHEMA}|tap|{season_id}|{identity}|{amount}|{nonce}".encode()
        ).hexdigest()

    # -- the tap request --------------------------------------------------
    def request_tap(self, identity, amount, purpose):
        """Request a tap outflow. Returns a SIGNED receipt envelope.

        GRANTED -> the outflow was committed via dclm_commit
                   (kind TAP_OUTFLOW) and receipted.
        REFUSED -> the true reason (OFF_SEASON, WINTER_PROTECTION,
                   NO_VERIFIED_SURPLUS, UNKNOWN_MATURITY,
                   IMMATURE_SYSTEM, HEALING_UNVERIFIED, TAP_LIMIT,
                   REPLENISHMENT_EXCEEDED,
                   FOUNDER_EXTRACTION_FORBIDDEN, PURPOSE_REQUIRED,
                   NOT_TESTNET_IDENTITY, INVALID_AMOUNT). Refusals are
                   signed too — a signed refusal is a verifiable honest
                   statement, not a silent drop.
        """
        # PURIFY ON ENTRY: the medium first. Anonymous or forged
        # identities are refused here as PurificationRefused — before the
        # module's own structural checks. The stated purpose travels as
        # a REPORTED claim: the member said it; DCLM did not verify it.
        purify_input(
            {"identity": identity, "action": "REQUEST_TAP",
             "amount": amount,
             "claims": [{"claim": "tap-request", "provenance": "DERIVED"},
                        {"claim": "tap-purpose", "provenance": "REPORTED",
                         "purpose": (purpose if isinstance(purpose, str)
                                     else None)}]},
            context={"path": "tap.request_tap"},
        )
        # --- structural: testnet identity --------------------------------
        if not isinstance(identity, str) or not identity.startswith(
                IDENTITY_PREFIX):
            return self._signed_refusal(
                identity, amount, REASON_NOT_TESTNET_IDENTITY,
                None, "structural refusal: identity must start with "
                f"{IDENTITY_PREFIX!r}. Testnet only.")

        # --- creed boundary: founder extraction is FORBIDDEN --------------
        # Tapping serves members' real-world needs; extraction serves
        # self. The maple law governs the first; the creed forbids the
        # second. Checked before any season evaluation: the creed is
        # absolute and does not depend on season state.
        if self._is_founder(identity):
            return self._signed_refusal(
                identity, amount, REASON_FOUNDER_EXTRACTION_FORBIDDEN,
                None, "the creed forbids founder extraction: tapping "
                "releases surplus to members through rules; it is not "
                "the founder extracting. This request is refused as "
                "extraction, not tapping.")

        # --- purpose: taps serve real-world needs, stated -----------------
        if not isinstance(purpose, str) or not purpose.strip():
            return self._signed_refusal(
                identity, amount, REASON_PURPOSE_REQUIRED, None,
                "a tap serves a member's real-world need: the purpose "
                "must be stated, honestly, on the receipt.")

        # --- amount: integer test-keys ------------------------------------
        if (not isinstance(amount, int) or isinstance(amount, bool)
                or amount <= 0):
            return self._signed_refusal(
                identity, amount, REASON_INVALID_AMOUNT, None,
                f"tap amount must be a positive integer of {UNIT}; "
                f"got {amount!r}.")

        # --- the maple rules: is the season open? --------------------------
        verdict = self.season.evaluate()
        if not verdict.season_open:
            return self._signed_refusal(
                identity, amount, verdict.reason, verdict,
                "the season is closed: tapping follows the maple "
                "rules — only in season, only from verified surplus, "
                "never in winter-protection, never from saplings.")

        # --- limited taps: per-tap limit -----------------------------------
        if amount > MAX_PER_TAP:
            return self._signed_refusal(
                identity, amount, REASON_TAP_LIMIT, verdict,
                f"one tap may not exceed {MAX_PER_TAP} {UNIT}: "
                "one or two taps per tree — the tree's size sets the "
                "limit.")

        # --- limited taps: per-member seasonal cap -------------------------
        season_entry = self._state["seasons"].get(verdict.season_id, {})
        member_used = season_entry.get("members", {}).get(identity, 0)
        if member_used + amount > TAP_RATE_PER_MEMBER_SEASON:
            return self._signed_refusal(
                identity, amount, REASON_TAP_LIMIT, verdict,
                f"member seasonal cap {TAP_RATE_PER_MEMBER_SEASON} "
                f"{UNIT}: already tapped {member_used} this season; "
                f"{amount} more would exceed it. Rate-limited, "
                "proportional to system health.")

        # --- the tree heals: outflow never exceeds replenishment -----------
        replenishment, r_label = _labeled_number(
            self.season.season_replenishment)
        season_outflow = season_entry.get("outflow_total", 0)
        if (replenishment is None or r_label == "UNKNOWN"
                or season_outflow + amount > replenishment):
            return self._signed_refusal(
                identity, amount, REASON_REPLENISHMENT_EXCEEDED, verdict,
                f"season outflow {season_outflow} + {amount} would "
                f"exceed replenishment {replenishment} {UNIT}: the "
                "tree heals — total outflow per season NEVER exceeds "
                "the replenishment rate.")

        # --- GRANT: rights, then the single commit path --------------------
        tap_id = self._tap_id(verdict.season_id, identity, amount,
                              self._utc_now())
        receipt = {
            "schema": SCHEMA,
            "type": "TAP_OUTFLOW",
            "tap_id": tap_id,
            "season_id": verdict.season_id,
            "identity": identity,
            "amount": amount,
            "unit": UNIT,
            "testnet": True,
            "purpose": purpose.strip(),
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "reason_chain": [
                {"check": check, "result": result, "detail": detail}
                for check, result, detail in verdict.chain
            ],
            "healing": {
                "season_outflow_before": season_outflow,
                "season_outflow_after": season_outflow + amount,
                "season_replenishment": replenishment,
                "replenishment_provenance": r_label,
                "member_season_outflow_before": member_used,
                "member_season_outflow_after": member_used + amount,
                "per_member_season_cap": TAP_RATE_PER_MEMBER_SEASON,
                "per_tap_limit": MAX_PER_TAP,
            },
            "surplus": {"amount": verdict.surplus, "unit": UNIT,
                        "provenance": verdict.surplus_provenance},
            "maturity": {"score": verdict.maturity,
                         "threshold": MATURITY_THRESHOLD,
                         "provenance": verdict.maturity_provenance},
            "winter": {"gradient": verdict.winter_gradient,
                       "interface": verdict.winter_interface},
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # derived in-process by DCLM
            "note": ("THE TREE SURVIVES TAPPING: surplus released "
                     "outward through the maple rules; the tree heals "
                     "through merit-gated emission. TEST units only — "
                     "not dollars, not eFuse. This is tapping, not "
                     "extraction: the creed boundary held."),
        }
        self._assert_receipt_labeled(receipt)
        rights_verdict = check_rights(
            identity, KIND_TAP_OUTFLOW,
            {"internal": "dclm.tap", "schema": SCHEMA,
             "season": verdict.season_id, "tap_approved": True},
        )
        # PURIFY IN FLIGHT: the outflow transition is checked — kind
        # whitelisted, receipt planned and labeled, the outflow declared
        # (season and member totals move) — before writes.py commits.
        purify_transition(
            {"season_outflow": season_outflow,
             "member_season_outflow": member_used},
            {"season_outflow": season_outflow + amount,
             "member_season_outflow": member_used + amount},
            KIND_TAP_OUTFLOW,
            context={"receipt": receipt, "identity": identity,
                     "path": "tap.request_tap"},
        )
        envelope = dclm_commit(
            KIND_TAP_OUTFLOW, receipt, rights_verdict,
            _TapCommitStore(
                self, receipt=receipt, season_id=verdict.season_id,
                identity=identity, amount=amount,
                season_outflow_before=season_outflow,
                member_outflow_before=member_used,
                replenishment=replenishment,
            ),
        )
        # PURIFY ON EXIT: labeled, signed, identity-bound.
        return purify_output(
            envelope,
            context={"path": "tap.request_tap", "signed": True},
        )

    # -- founder check ------------------------------------------------------
    @staticmethod
    def _is_founder(identity):
        """The creed boundary. ENFORCED: the marker check below is a
        live refusal gate. CONVENTIONAL: the exact founder identity
        string, not yet issued by the identity system — registered via
        UNITY_FOUNDER_IDENTITY when it exists. Until then, any identity
        claiming the founder prefix is refused on sight."""
        registered = os.environ.get("UNITY_FOUNDER_IDENTITY", "").strip()
        if registered and identity == registered:
            return True
        return identity.startswith(FOUNDER_IDENTITY_PREFIX)

    # -- refusal receipts ---------------------------------------------------
    def _signed_refusal(self, identity, amount, reason, season_verdict,
                        note):
        if reason not in REFUSAL_REASONS:
            raise TapError(f"unknown refusal reason: {reason!r}")
        receipt = {
            "schema": SCHEMA,
            "type": "TAP_REFUSAL",
            "season_id": (season_verdict.season_id
                          if season_verdict is not None
                          else self.season.season_id),
            "identity": identity,
            "amount": amount,
            "unit": UNIT,
            "testnet": True,
            "outcome": OUTCOME_REFUSED,
            "reason": reason,
            "reason_chain": (
                [{"check": c, "result": r, "detail": d}
                 for c, r, d in season_verdict.chain]
                if season_verdict is not None else []
            ),
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # the tapper derived the refusal
            "note": ("Refusal, not a block: " + note),
        }
        self._assert_receipt_labeled(receipt)
        envelope = sign_commit(receipt)
        self._log(envelope)
        # PURIFY ON EXIT (refusal): labeled + signed; the identity is the
        # presented one (audited, not trusted) — format checks skipped,
        # labels and signature still enforced.
        return purify_output(
            envelope,
            context={"path": "tap.request_tap", "signed": True,
                     "identity_as_presented": True},
        )

    @staticmethod
    def _assert_receipt_labeled(receipt):
        label = receipt.get("provenance")
        if label not in PROVENANCE_LABELS:
            raise TapError(
                f"receipt missing valid provenance label: {receipt!r}")
        if receipt.get("outcome") == OUTCOME_GRANTED and label == "UNKNOWN":
            raise TapError(
                "UNKNOWN is never PASS: refusing to grant on an UNKNOWN "
                "label")

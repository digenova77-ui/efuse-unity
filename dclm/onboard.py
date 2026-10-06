"""
DCLM ONBOARDER PIPELINE — Residual Law Finance onboarder -> residual ->
tokenomics flywheel.

David's order (2026-10-06): build the Residual Law Finance onboarder ->
residual -> tokenomics flywheel — the real-world grounding of the entire
tokenomic system. First-class flow in the economic model.

THE FLYWHEEL
------------
1. ONBOARD. A Unity-bound onboarder joins. The identity MUST be
   "unity:testnet:..." — anything else is structurally refused.
   Receipted (ONBOARD).
2. RESIDUAL INTAKE. Residual Law Finance analysis finds recoverable
   residual in the onboarder's operations. Figures must be REPORTED:
   real paperwork, paperwork hash required. A figure without paperwork
   is refused at intake (PAPERWORK_REQUIRED); a MODELED figure is
   refused (MODELED_FIGURE_REFUSED). Receipted (RESIDUAL_INTAKE). The
   reference case: $1.27B/yr recoverable non-classroom friction
   (Ontario-style, REPORTED).
3. THE 81/19 SPLIT. 81% of recovered value stays with the onboarder —
   fiat, theirs. The system NEVER touches it, never claims it, never
   counts it as system value: the 81% leg is recorded only as
   ACKNOWLEDGED_OFF_SYSTEM. 19% flows into the system — real,
   recovered, real-world value — committed into HELD escrow. The split
   is receipted at EVERY step (SPLIT_EXECUTE).
4. THE 19% HAS THREE LAWFUL DESTINATIONS: CORE_CAUSE_LOCK
   (Eden-locking), PLAYGROUND_FUEL (mesh bounties — surplus funds the
   work), PEG_SUPPORT (real recovered value grounding the eFuse energy
   peg). THE SPLIT BETWEEN THE THREE IS HELD-FOR-DAVID: until he sets
   it, the 19% sits in receipted HELD escrow, never deployed. Routing
   attempts are receipted as AWAITING_SPLIT_RULING (NINETEEN_ROUTE).
5. RECOVERY WORK EARNS WAVE MERIT (TOP BAND). The onboarder's
   participation — analysis, verification, ongoing recovery — generates
   gated receipts -> wave merit -> emission, through the tokenization
   worker's merit path (dclm/tokenize.py -> token_engine.Tokenizer).
   Merit is earned for the WORK. Never for the value moved.

PURITY RULES (hard, enforced in code)
-------------------------------------
* Residual figures must be REPORTED — paperwork hash required. A figure
  without paperwork is refused at intake. A MODELED figure is refused.
* The onboarder's 81% is theirs: the system never touches it, never
  claims it, never counts it as system value. Recorded only as
  ACKNOWLEDGED_OFF_SYSTEM.
* The 19% is receipted at EVERY step: intake -> split -> escrow ->
  routed.
* No onboarder is EVER promised anything for joining. There are no
  projections of gain anywhere in this module or its docs — merit is
  earned for WORK, never as compensation for value moved. (A scan test
  asserts no gain-promise language exists in these files.)
* Testnet only. Amounts are integer fiat minor units (cents), labeled
  FIAT-RECOVERED — never test-keys, never eFuse. The meter's test-key
  wallet is untouched by this pipeline: no commit here moves keys.

All state mutations flow through writes.dclm_commit after a
rights.check_rights GRANT (internal "dclm.onboard"), using the four
commit kinds ONBOARD / RESIDUAL_INTAKE / SPLIT_EXECUTE / NINETEEN_ROUTE
(whitelisted in rights.py with receipt-logged justification).

RESIDUAL_INTAKE covers two intake classes, distinguished by
"intake_class": "residual_figure" (reported residual money found) and
"recovery_work" (verified recovery-work evidence submitted for merit).
Both are real-world recovery entering the tokenomics; the class field
keeps them auditable and separate.
"""

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    purify_input,
    purify_output,
    purify_transition,
)
from writes import (  # noqa: E402 — the single commit path
    CommitStore,
    CommitRefused,
    dclm_commit,
    sign_commit,
)
from compute import PROVENANCE_LABELS  # noqa: E402 — receipt labels

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.onboard.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"
INTERNAL = "dclm.onboard"

# Amounts are integer fiat minor units (cents), labeled FIAT-RECOVERED.
# Never test-keys, never eFuse.
UNIT = "fiat-cents"
DEFAULT_CURRENCY = "CAD"  # the Ontario reference case is Canadian

# -- the 81/19 split: SET by David. Not calibration, not proposed. --------
SPLIT_ONBOARDER_PCT = 81
SPLIT_SYSTEM_PCT = 19

# -- the three lawful destinations of the 19% ------------------------------
# HELD-FOR-DAVID: the ratio between the three is his to set. Until he
# does, _SPLIT_RULING stays None and every routing attempt is receipted
# as AWAITING_SPLIT_RULING with the 19% left in escrow. There is NO
# setter in this build: the ruling lands as a code change plus receipt,
# never as a runtime flip.
_SPLIT_RULING = None  # HELD_FOR_DAVID
ROUTE_CORE_CAUSE_LOCK = "CORE_CAUSE_LOCK"      # Eden-locking
ROUTE_PLAYGROUND_FUEL = "PLAYGROUND_FUEL"      # mesh bounties
ROUTE_PEG_SUPPORT = "PEG_SUPPORT"              # eFuse energy-peg grounding
AWAITING_SPLIT_RULING = "AWAITING_SPLIT_RULING"
ROUTE_DESTINATIONS = (
    ROUTE_CORE_CAUSE_LOCK, ROUTE_PLAYGROUND_FUEL, ROUTE_PEG_SUPPORT,
)

# -- commit kinds (whitelisted in rights.py) --------------------------------
KIND_ONBOARD = "ONBOARD"
KIND_RESIDUAL_INTAKE = "RESIDUAL_INTAKE"
KIND_SPLIT_EXECUTE = "SPLIT_EXECUTE"
KIND_NINETEEN_ROUTE = "NINETEEN_ROUTE"

# -- intake classes ----------------------------------------------------------
INTAKE_RESIDUAL_FIGURE = "residual_figure"
INTAKE_RECOVERY_WORK = "recovery_work"

# -- merit bands (minimal) ----------------------------------------------------
# Top band: verified real-world recovery work. Band CALIBRATION (how much
# merit a unit of recovery work earns) is HELD-FOR-DAVID: until he sets
# it, a work receipt must carry its own verified merit_value from the
# verifying authority — the pipeline never invents one.
BAND_RECOVERY = "band:recovery"
MERIT_BANDS = {
    "recovery": {
        "band": BAND_RECOVERY,
        "rank": 1,
        "description": (
            "Top band: verified real-world recovery work — the "
            "onboarder's participation in finding, verifying, and "
            "recovering residual (analysis, verification, ongoing "
            "recovery)."
        ),
        "calibration": "HELD_FOR_DAVID",
    },
}

# -- outcomes -----------------------------------------------------------------
OUTCOME_GRANTED = "GRANTED"
OUTCOME_REFUSED = "REFUSED"
OUTCOME_HELD = "HELD"
OUTCOME_REPLAYED = "REPLAYED"

# -- refusal / status reasons ---------------------------------------------------
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_PAPERWORK_REQUIRED = "PAPERWORK_REQUIRED"
REASON_INVALID_PAPERWORK = "INVALID_PAPERWORK"
REASON_INVALID_PAPERWORK_HASH = "INVALID_PAPERWORK_HASH"
REASON_MODELED_FIGURE_REFUSED = "MODELED_FIGURE_REFUSED"
REASON_INVALID_FIGURE = "INVALID_FIGURE"
REASON_ONBOARDER_UNKNOWN = "ONBOARDER_UNKNOWN"
REASON_NO_REPORTED_RESIDUAL = "NO_REPORTED_RESIDUAL"
REASON_RECOVERY_EXCEEDS_REPORTED = "RECOVERY_EXCEEDS_REPORTED"
REASON_CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
REASON_INSUFFICIENT_ESCROW = "INSUFFICIENT_ESCROW"
REASON_SPLIT_HELD_FOR_DAVID = "SPLIT_HELD_FOR_DAVID"
REASON_UNVERIFIED_WORK_RECEIPT = "UNVERIFIED_WORK_RECEIPT"
REASON_INVALID_WORK_RECEIPT = "INVALID_WORK_RECEIPT"
REASON_WORK_RECEIPT_IDENTITY_MISMATCH = "WORK_RECEIPT_IDENTITY_MISMATCH"
REASON_UNSUPPORTED_WORK_CLASS = "UNSUPPORTED_WORK_CLASS"
REASON_NON_POSITIVE_MERIT_VALUE = "NON_POSITIVE_MERIT_VALUE"
REASON_NO_WORK_RECEIPTS = "NO_WORK_RECEIPTS"
REASON_MERIT_PATH_PENDING = "MERIT_PATH_PENDING"
REASON_MERIT_DEFERRED_PEG_UNSET = "MERIT_DEFERRED_PEG_UNSET"
REASON_ENGINE_REFUSED = "ENGINE_REFUSED"

# -- the 81% leg disposition: acknowledged, off-system, never system value --
DISPOSITION_ACKNOWLEDGED_OFF_SYSTEM = "ACKNOWLEDGED_OFF_SYSTEM"
DISPOSITION_ESCROW_HELD = "ESCROW_HELD"

DEFAULT_STATE_DIR = os.path.join(_HERE, "state-onboard")
STATE_FILENAME = "pipeline-state.json"
RECEIPTS_FILENAME = "onboard-receipts.jsonl"


class OnboardError(Exception):
    """Base class for onboarder-pipeline failures."""


class OnboardRefused(OnboardError):
    """Structural refusal: bad identity, bad types. Carries the true
    reason; nothing was written."""

    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# tokenization merit path — lazy, PENDING-closed when absent
# ---------------------------------------------------------------------------

def _load_tokenize_api():
    """Load (Tokenizer, TokenizeRefused, REASON_PEG_E_UNSET) from the
    tokenization worker. Returns None when the worker is absent: the
    merit path is then honestly PENDING and accrual stays closed —
    never accrue on UNKNOWN."""
    try:
        # The dclm/tokenize.py shim delegates attribute access to
        # token_engine; this mirrors meter.py's TokenizeMeritReader.
        from tokenize import (  # noqa: E402
            REASON_PEG_E_UNSET,
            TokenizeRefused,
            Tokenizer,
        )
        return Tokenizer, TokenizeRefused, REASON_PEG_E_UNSET
    except Exception:
        return None


def merit_path_status():
    """LANDED when the tokenization worker's merit path is importable,
    else PENDING (accrual closed until it exists)."""
    return "LANDED" if _load_tokenize_api() is not None else "PENDING"


_DEFAULT_TOKENIZER = None


def _default_tokenizer():
    """Module-level default Tokenizer (the tokenization worker's own
    default engine pattern). The merit ledger is the worker's
    in-memory store; this pipeline only routes verified work through
    it."""
    global _DEFAULT_TOKENIZER
    api = _load_tokenize_api()
    if api is None:
        return None
    if _DEFAULT_TOKENIZER is None:
        _DEFAULT_TOKENIZER = api[0]()
    return _DEFAULT_TOKENIZER


# ---------------------------------------------------------------------------
# commit store — the pipeline's single mutation point
# ---------------------------------------------------------------------------

class _OnboardCommitStore(CommitStore):
    """DCLM-internal adapter: lets writes.dclm_commit drive the
    pipeline's single mutation point.

    Every pipeline state change happens inside apply_write — which
    dclm_commit calls exactly once, and only after a DCLM-issued GRANT
    verdict. build_receipt returns the pipeline's own receipt dict
    unchanged; append_receipt logs the signed envelope to the
    pipeline's receipt trail.
    """

    def __init__(self, pipeline, receipt, mutate):
        self._pipeline = pipeline
        self._receipt = receipt
        self._mutate = mutate  # fn(state) -> mutation report dict

    def apply_write(self, kind, payload):
        report = self._mutate(self._pipeline._state)
        self._pipeline._save()
        return report

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        return self._receipt

    def append_receipt(self, envelope):
        self._pipeline._log_envelope(envelope)


# ---------------------------------------------------------------------------
# the pipeline
# ---------------------------------------------------------------------------

class OnboardPipeline:
    """Residual Law Finance onboarder -> residual -> tokenomics flywheel.

    State (state-onboard/pipeline-state.json), mutated ONLY inside
    _OnboardCommitStore.apply_write via dclm_commit:
      onboarders  : unity_id -> registration + residual accounting
      residual_intakes / work_intakes : intake records
      consumed_work_receipts : receipt_id -> consumption record
      splits      : 81/19 split records (both legs receipted)
      escrow      : unity_id -> the 19% HELD balance + entries
      routing_log : NINETEEN_ROUTE records (held or, post-ruling, routed)
      destinations: the three lawful 19% destinations (zero while HELD)
    """

    def __init__(self, state_dir=None, tokenizer=None):
        self.state_dir = state_dir or os.environ.get(
            "UNITY_ONBOARD_STATE_DIR", DEFAULT_STATE_DIR
        )
        os.makedirs(self.state_dir, exist_ok=True)
        self.state_path = os.path.join(self.state_dir, STATE_FILENAME)
        self.receipts_path = os.path.join(self.state_dir, RECEIPTS_FILENAME)
        self._tokenizer = tokenizer  # explicit engine, or lazy default
        self._state = self._load()

    # -- persistence --------------------------------------------------------

    def _load(self):
        if not os.path.exists(self.state_path):
            return {
                "schema": SCHEMA,
                "onboarders": {},
                "residual_intakes": [],
                "work_intakes": [],
                "consumed_work_receipts": {},
                "splits": [],
                "escrow": {},
                "routing_log": [],
                "destinations": {
                    name: {"balance_cents": 0, "entries": []}
                    for name in ROUTE_DESTINATIONS
                },
            }
        with open(self.state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") != SCHEMA:
            raise OnboardError(
                f"state schema mismatch: expected {SCHEMA}, found "
                f"{data.get('schema')!r} — refusing to read foreign state"
            )
        return data

    def _save(self):
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".onboard-state-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, self.state_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _log_envelope(self, envelope):
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, sort_keys=True) + "\n")

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _receipt_id(*parts):
        return hashlib.sha256(
            "|".join([SCHEMA] + [str(p) for p in parts]).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _require_testnet(identity):
        """Structural refusal: non-testnet identities never enter the
        pipeline. Testnet only."""
        if not isinstance(identity, str) or not identity.startswith(
                IDENTITY_PREFIX):
            raise OnboardRefused(
                REASON_NOT_TESTNET_IDENTITY,
                f"identity must start with {IDENTITY_PREFIX!r}; "
                f"got {identity!r}. Testnet only.",
            )
        return identity

    @staticmethod
    def _require_amount_cents(value, what="amount"):
        if isinstance(value, bool) or not isinstance(value, int):
            raise OnboardRefused(
                REASON_INVALID_FIGURE,
                f"{what} must be an integer of {UNIT}; got {value!r}.",
            )
        if value <= 0:
            raise OnboardRefused(
                REASON_INVALID_FIGURE,
                f"{what} must be positive; got {value!r}.",
            )
        return value

    @staticmethod
    def _require_paperwork_hash(paperwork_hash):
        if not paperwork_hash:
            return None  # caller maps to PAPERWORK_REQUIRED refusal
        if not (isinstance(paperwork_hash, str)
                and len(paperwork_hash) == 64
                and all(c in "0123456789abcdef"
                        for c in paperwork_hash.lower())):
            raise OnboardRefused(
                REASON_INVALID_PAPERWORK_HASH,
                "paperwork_hash must be 64 hex chars (sha256 of the "
                f"paperwork); got {paperwork_hash!r}.",
            )
        return paperwork_hash.lower()

    def _assert_receipt_labeled(self, receipt):
        label = receipt.get("provenance")
        if label not in PROVENANCE_LABELS:
            raise OnboardError(
                f"receipt missing valid provenance label: {receipt!r}")
        if label == "UNKNOWN":
            raise OnboardError(
                "UNKNOWN is never PASS: refusing to issue a receipt on "
                "an UNKNOWN label")

    def _commit(self, kind, receipt, mutate, *, before=None, after=None):
        """Rights -> PURIFY (transition) -> single commit -> signed
        envelope, purified on exit. The only way pipeline state changes.
        before/after are small honest markers of the declared state
        change; the medium checks kind, receipt, change-declared, and
        identity continuity before writes.py commits."""
        self._assert_receipt_labeled(receipt)
        verdict = check_rights(
            receipt.get("unity_id"), kind,
            {"internal": INTERNAL, "schema": SCHEMA},
        )
        # PURIFY IN FLIGHT: the transition itself is checked before
        # writes.py commits.
        purify_transition(
            before if before is not None else {
                "kind": kind, "phase": "pre-commit"},
            after if after is not None else {
                "kind": kind, "phase": "post-commit",
                "receipt_id": receipt.get("receipt_id")},
            kind,
            context={"receipt": receipt,
                     "identity": receipt.get("unity_id"),
                     "path": "onboard._commit"},
        )
        envelope = dclm_commit(
            kind, receipt, verdict,
            _OnboardCommitStore(self, receipt, mutate),
        )
        # PURIFY ON EXIT: the signed commit envelope, verified.
        return purify_output(
            envelope,
            context={"path": "onboard._commit", "signed": True},
        )

    def _refuse(self, unity_id, kind, reason, detail, issued_for):
        """A signed refusal: a verifiable honest statement. Nothing was
        written — refusals never mutate state."""
        receipt = {
            "schema": SCHEMA,
            "type": "REFUSAL",
            "kind": kind,
            "unity_id": unity_id,
            "outcome": OUTCOME_REFUSED,
            "reason": reason,
            "detail": detail,
            "issued_for": issued_for,
            "testnet": True,
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # the pipeline derived the refusal
            "note": (
                "Refusal, not a block: nothing was written, nothing "
                "moved. The true reason is recorded above."
            ),
        }
        self._assert_receipt_labeled(receipt)
        envelope = sign_commit(receipt)
        self._log_envelope(envelope)
        # PURIFY ON EXIT (refusal): labeled + signed; the identity is the
        # presented one (audited, not trusted).
        return purify_output(
            envelope,
            context={"path": "onboard._refuse", "signed": True,
                     "identity_as_presented": True},
        )

    def _onboarder(self, unity_id):
        return self._state["onboarders"].get(unity_id)

    # -- stage 1: onboard ----------------------------------------------------

    def onboard(self, unity_id, paperwork_ref):
        """Onboard a Unity-bound onboarder. Receipted (ONBOARD).

        Structural refusals (raise OnboardRefused): non-testnet
        identity, missing/empty paperwork_ref. Re-onboarding is
        idempotent: the original signed envelope is replayed, never
        duplicated.
        """
        # PURIFY ON ENTRY: the medium first — no anonymous onboarders.
        purify_input(
            {"unity_id": unity_id, "action": "ONBOARD",
             "claims": [{"claim": "onboard-request",
                         "provenance": "DERIVED"}]},
            context={"path": "onboard.onboard"},
        )
        self._require_testnet(unity_id)
        if not isinstance(paperwork_ref, str) or not paperwork_ref.strip():
            raise OnboardRefused(
                REASON_PAPERWORK_REQUIRED,
                "onboarding is a real-world relationship: a paperwork "
                "reference is required.",
            )
        existing = self._onboarder(unity_id)
        if existing is not None:
            # Idempotent replay: the same onboarder twice -> the same
            # envelope, never a second registration. The receipt bytes
            # are stored in state (inside the commit); re-signing is
            # deterministic, so the replayed envelope is byte-identical.
            # PURIFY ON EXIT (idempotent replay): the original signed
            # envelope, re-purified on exit like any other output.
            return purify_output(
                sign_commit(existing["onboard_receipt"]),
                context={"path": "onboard.onboard", "signed": True},
            )

        receipt = {
            "schema": SCHEMA,
            "type": "ONBOARD_RECEIPT",
            "kind": KIND_ONBOARD,
            "unity_id": unity_id,
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "paperwork_ref": paperwork_ref.strip(),
            "receipt_id": self._receipt_id(KIND_ONBOARD, unity_id),
            "testnet": True,
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",
            "note": (
                "Unity-bound onboarder registered. No value moved; no "
                "projection made. Testnet only."
            ),
        }

        def mutate(state):
            state["onboarders"][unity_id] = {
                "paperwork_ref": paperwork_ref.strip(),
                "onboarded_at": receipt["issued_at"],
                "currency": None,
                "reported_total_cents": 0,
                "residual_remaining_cents": 0,
                "onboard_receipt_id": receipt["receipt_id"],
                # Stored for idempotent replay: re-signing these bytes
                # reproduces the original envelope exactly.
                "onboard_receipt": receipt,
            }
            return {"onboarded": unity_id,
                    "receipt_id": receipt["receipt_id"]}

        _n_ob = len(self._state["onboarders"])
        return self._commit(KIND_ONBOARD, receipt, mutate,
                            before={"onboarders": _n_ob},
                            after={"onboarders": _n_ob + 1,
                                   "unity_id": unity_id})

    # -- stage 2: residual intake (REPORTED only) ------------------------------

    @staticmethod
    def _parse_figure(figure):
        """Normalize the figure to (amount_cents, currency, label).

        Raises OnboardRefused on structural problems. Returns label
        "MODELED" for the caller to refuse with the true reason."""
        if isinstance(figure, bool):
            raise OnboardRefused(
                REASON_INVALID_FIGURE,
                f"figure must be an integer of {UNIT} or a figure dict; "
                f"got {figure!r}.")
        if isinstance(figure, int):
            return figure, DEFAULT_CURRENCY, "REPORTED"
        if isinstance(figure, dict):
            label = str(figure.get("label", "REPORTED")).strip().upper()
            amount = figure.get("amount_cents")
            currency = str(figure.get("currency", DEFAULT_CURRENCY)).strip(
            ).upper() or DEFAULT_CURRENCY
            return amount, currency, label
        raise OnboardRefused(
            REASON_INVALID_FIGURE,
            f"figure must be an integer of {UNIT} or a figure dict; "
            f"got {figure!r}.")

    def record_residual(self, unity_id, figure, paperwork_hash):
        """Intake a REPORTED residual figure. Receipted (RESIDUAL_INTAKE).

        Purity: paperwork_hash is REQUIRED — a figure without paperwork
        is refused at intake (PAPERWORK_REQUIRED). A figure labeled
        MODELED is refused (MODELED_FIGURE_REFUSED): residual figures
        are never modeled. Same paperwork twice replays the original
        intake, never double-counts.
        """
        # PURIFY ON ENTRY: the medium first. The figure travels as a
        # REPORTED claim (paperwork-backed); a MODELED figure is refused
        # by the medium's never-upgrade rule if presented as truth.
        purify_input(
            {"unity_id": unity_id, "action": "RESIDUAL_INTAKE",
             "claims": [{"claim": "residual-figure",
                         "provenance": "REPORTED"}]},
            context={"path": "onboard.record_residual"},
        )
        self._require_testnet(unity_id)
        if self._onboarder(unity_id) is None:
            return self._refuse(
                unity_id, KIND_RESIDUAL_INTAKE, REASON_ONBOARDER_UNKNOWN,
                f"{unity_id!r} is not an onboarded onboarder.",
                issued_for="record_residual")
        if not paperwork_hash:
            return self._refuse(
                unity_id, KIND_RESIDUAL_INTAKE, REASON_PAPERWORK_REQUIRED,
                "residual intake requires the paperwork hash: a residual "
                "figure without paperwork is refused at intake.",
                issued_for="record_residual")
        try:
            paperwork_hash = self._require_paperwork_hash(paperwork_hash)
        except OnboardRefused as exc:
            return self._refuse(
                unity_id, KIND_RESIDUAL_INTAKE, exc.reason, exc.detail,
                issued_for="record_residual")

        amount_cents, currency, label = self._parse_figure(figure)
        if label == "MODELED":
            return self._refuse(
                unity_id, KIND_RESIDUAL_INTAKE,
                REASON_MODELED_FIGURE_REFUSED,
                "residual figures must be REPORTED — real paperwork, "
                "real operations. MODELED figures are refused at intake.",
                issued_for="record_residual")
        try:
            self._require_amount_cents(amount_cents, "figure")
        except OnboardRefused as exc:
            return self._refuse(
                unity_id, KIND_RESIDUAL_INTAKE, exc.reason, exc.detail,
                issued_for="record_residual")

        # Idempotency: one paperwork hash, one intake. A replay returns
        # the original signed envelope — the figure is never
        # double-counted.
        for intake in self._state["residual_intakes"]:
            if intake["paperwork_hash"] == paperwork_hash:
                # PURIFY ON EXIT (idempotent replay).
                return purify_output(
                    sign_commit(intake["intake_receipt"]),
                    context={"path": "onboard.record_residual",
                             "signed": True},
                )

        onboarder = self._onboarder(unity_id)
        if (onboarder["currency"] is not None
                and onboarder["currency"] != currency):
            return self._refuse(
                unity_id, KIND_RESIDUAL_INTAKE, REASON_CURRENCY_MISMATCH,
                f"onboarder currency is {onboarder['currency']!r}; intake "
                f"is {currency!r}. One currency per onboarder.",
                issued_for="record_residual")

        receipt = {
            "schema": SCHEMA,
            "type": "RESIDUAL_INTAKE",
            "kind": KIND_RESIDUAL_INTAKE,
            "intake_class": INTAKE_RESIDUAL_FIGURE,
            "unity_id": unity_id,
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "amount_cents": amount_cents,
            "currency": currency,
            "unit": UNIT,
            "figure_label": "REPORTED",
            "paperwork_hash": paperwork_hash,
            "receipt_id": self._receipt_id(
                KIND_RESIDUAL_INTAKE, unity_id, paperwork_hash),
            "testnet": True,
            "issued_at": self._utc_now(),
            "provenance": "REPORTED",  # the figure is reported via paperwork
            "note": (
                "REPORTED residual figure intaken: real paperwork, "
                "paperwork hash recorded. Never modeled."
            ),
        }

        def mutate(state):
            state["residual_intakes"].append({
                "unity_id": unity_id,
                "amount_cents": amount_cents,
                "currency": currency,
                "paperwork_hash": paperwork_hash,
                "intake_receipt_id": receipt["receipt_id"],
                "intake_receipt": receipt,  # for idempotent replay
                "intaken_at": receipt["issued_at"],
            })
            ob = state["onboarders"][unity_id]
            if ob["currency"] is None:
                ob["currency"] = currency
            ob["reported_total_cents"] += amount_cents
            ob["residual_remaining_cents"] += amount_cents
            return {"intaken_cents": amount_cents,
                    "receipt_id": receipt["receipt_id"]}

        _n_ri = len(self._state["residual_intakes"])
        _tot = onboarder["reported_total_cents"]
        return self._commit(KIND_RESIDUAL_INTAKE, receipt, mutate,
                            before={"residual_intakes": _n_ri,
                                    "reported_total_cents": _tot},
                            after={"residual_intakes": _n_ri + 1,
                                   "reported_total_cents":
                                   _tot + amount_cents})

    # -- stage 3: the 81/19 split ----------------------------------------------

    @staticmethod
    def _split_amounts(amount_cents):
        """The 81/19 split, integer-exact: the 19% leg is the remainder,
        so no value leaks to rounding."""
        eighty_one = (amount_cents * SPLIT_ONBOARDER_PCT) // 100
        nineteen = amount_cents - eighty_one
        return eighty_one, nineteen

    def execute_split(self, unity_id, recovered_amount, currency=None,
                      split_id=None):
        """Execute the 81/19 split on a recovered amount. Receipted
        (SPLIT_EXECUTE).

        The 81% leg is ACKNOWLEDGED_OFF_SYSTEM — fiat, theirs, untouched:
        the system never touches it, never claims it, never counts it as
        system value. The 19% leg is committed into HELD escrow. Both
        legs are receipted in one commit; the 19% is receipted at every
        later step too.

        Purity: recovered_amount may not exceed the onboarder's REPORTED
        residual remaining — recovery beyond what was reported needs a
        new intake first. split_id makes the call idempotent when given.
        """
        # PURIFY ON ENTRY: the medium first.
        purify_input(
            {"unity_id": unity_id, "action": "SPLIT_EXECUTE",
             "recovered_amount": recovered_amount,
             "claims": [{"claim": "split-execution-request",
                         "provenance": "DERIVED"}]},
            context={"path": "onboard.execute_split"},
        )
        self._require_testnet(unity_id)
        onboarder = self._onboarder(unity_id)
        if onboarder is None:
            return self._refuse(
                unity_id, KIND_SPLIT_EXECUTE, REASON_ONBOARDER_UNKNOWN,
                f"{unity_id!r} is not an onboarded onboarder.",
                issued_for="execute_split")
        try:
            self._require_amount_cents(recovered_amount, "recovered_amount")
        except OnboardRefused as exc:
            return self._refuse(
                unity_id, KIND_SPLIT_EXECUTE, exc.reason, exc.detail,
                issued_for="execute_split")
        currency = (currency or onboarder["currency"]
                    or DEFAULT_CURRENCY).strip().upper()
        if (onboarder["currency"] is not None
                and onboarder["currency"] != currency):
            return self._refuse(
                unity_id, KIND_SPLIT_EXECUTE, REASON_CURRENCY_MISMATCH,
                f"onboarder currency is {onboarder['currency']!r}; split "
                f"is {currency!r}.",
                issued_for="execute_split")
        if onboarder["residual_remaining_cents"] <= 0:
            return self._refuse(
                unity_id, KIND_SPLIT_EXECUTE, REASON_NO_REPORTED_RESIDUAL,
                "no REPORTED residual remaining: intake a reported figure "
                "before splitting recovered value.",
                issued_for="execute_split")
        if recovered_amount > onboarder["residual_remaining_cents"]:
            return self._refuse(
                unity_id, KIND_SPLIT_EXECUTE,
                REASON_RECOVERY_EXCEEDS_REPORTED,
                f"recovered {recovered_amount} {UNIT} exceeds REPORTED "
                f"residual remaining "
                f"({onboarder['residual_remaining_cents']} {UNIT}): "
                "recovery beyond what was reported needs a new intake "
                "first.",
                issued_for="execute_split")
        if split_id is not None:
            for split in self._state["splits"]:
                if split["split_id"] == split_id:
                    # PURIFY ON EXIT (idempotent replay).
                    return purify_output(
                        sign_commit(split["split_receipt"]),  # replay
                        context={"path": "onboard.execute_split",
                                 "signed": True},
                    )
            split_key = str(split_id)
        else:
            split_key = self._receipt_id(
                KIND_SPLIT_EXECUTE, unity_id, recovered_amount,
                len(self._state["splits"]))

        eighty_one, nineteen = self._split_amounts(recovered_amount)
        receipt = {
            "schema": SCHEMA,
            "type": "SPLIT_EXECUTE",
            "kind": KIND_SPLIT_EXECUTE,
            "unity_id": unity_id,
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "split_id": split_key,
            "recovered_cents": recovered_amount,
            "currency": currency,
            "unit": UNIT,
            "leg_81": {
                "pct": SPLIT_ONBOARDER_PCT,
                "amount_cents": eighty_one,
                "currency": currency,
                "disposition": DISPOSITION_ACKNOWLEDGED_OFF_SYSTEM,
                "system_value": False,
                "note": (
                    "The onboarder's 81%: fiat, theirs, untouched. The "
                    "system never touches it, never claims it, never "
                    "counts it as system value. Recorded only as "
                    "acknowledged off-system."
                ),
            },
            "leg_19": {
                "pct": SPLIT_SYSTEM_PCT,
                "amount_cents": nineteen,
                "currency": currency,
                "disposition": DISPOSITION_ESCROW_HELD,
                "system_value": True,
                "escrow_status": AWAITING_SPLIT_RULING,
                "note": (
                    "The system's 19%: real, recovered, real-world value "
                    "committed into HELD escrow. Receipted at every step "
                    "from here."
                ),
            },
            "receipt_id": self._receipt_id(
                KIND_SPLIT_EXECUTE, unity_id, split_key),
            "testnet": True,
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # the 81/19 arithmetic, in-process
            "note": (
                "81/19 split executed (David's set ratio). The 81% leg "
                "moved nowhere: acknowledged off-system. The 19% leg "
                "entered HELD escrow."
            ),
        }

        def mutate(state):
            state["splits"].append({
                "unity_id": unity_id,
                "split_id": split_key,
                "recovered_cents": recovered_amount,
                "eighty_one_cents": eighty_one,
                "nineteen_cents": nineteen,
                "currency": currency,
                "split_receipt_id": receipt["receipt_id"],
                "split_receipt": receipt,  # for idempotent replay
                "split_at": receipt["issued_at"],
            })
            escrow = state["escrow"].setdefault(unity_id, {
                "balance_cents": 0, "currency": currency, "entries": []})
            escrow["balance_cents"] += nineteen
            escrow["entries"].append({
                "split_id": split_key,
                "amount_cents": nineteen,
                "status": AWAITING_SPLIT_RULING,
                "at": receipt["issued_at"],
            })
            state["onboarders"][unity_id][
                "residual_remaining_cents"] -= recovered_amount
            return {"eighty_one_cents": eighty_one,
                    "nineteen_cents": nineteen,
                    "escrow_balance_cents": escrow["balance_cents"]}

        _n_sp = len(self._state["splits"])
        return self._commit(KIND_SPLIT_EXECUTE, receipt, mutate,
                            before={"splits": _n_sp},
                            after={"splits": _n_sp + 1,
                                   "split_id": split_key})

    # -- stage 4: route the 19% (HELD until David rules) -------------------------

    def escrow_balance(self, unity_id):
        """The onboarder's HELD 19% escrow balance, in fiat-cents."""
        escrow = self._state["escrow"].get(unity_id)
        return escrow["balance_cents"] if escrow else 0

    def route_19(self, unity_id, amount_cents, currency=None):
        """Route the 19% toward its three lawful destinations.

        HELD-FOR-DAVID: the split between CORE_CAUSE_LOCK,
        PLAYGROUND_FUEL, and PEG_SUPPORT is his to set. Until he does,
        this records the routing attempt as AWAITING_SPLIT_RULING —
        receipted (NINETEEN_ROUTE) — and the 19% STAYS in escrow, never
        deployed. Outcome HELD, honestly labeled.
        """
        # PURIFY ON ENTRY: the medium first.
        purify_input(
            {"unity_id": unity_id, "action": "NINETEEN_ROUTE",
             "amount_cents": amount_cents,
             "claims": [{"claim": "nineteen-route-request",
                         "provenance": "DERIVED"}]},
            context={"path": "onboard.route_19"},
        )
        self._require_testnet(unity_id)
        if self._onboarder(unity_id) is None:
            return self._refuse(
                unity_id, KIND_NINETEEN_ROUTE, REASON_ONBOARDER_UNKNOWN,
                f"{unity_id!r} is not an onboarded onboarder.",
                issued_for="route_19")
        try:
            self._require_amount_cents(amount_cents, "amount")
        except OnboardRefused as exc:
            return self._refuse(
                unity_id, KIND_NINETEEN_ROUTE, exc.reason, exc.detail,
                issued_for="route_19")
        escrow = self._state["escrow"].get(unity_id)
        balance = escrow["balance_cents"] if escrow else 0
        currency = (currency or (escrow["currency"] if escrow else None)
                    or DEFAULT_CURRENCY).strip().upper()
        if escrow is not None and escrow["currency"] != currency:
            return self._refuse(
                unity_id, KIND_NINETEEN_ROUTE, REASON_CURRENCY_MISMATCH,
                f"escrow currency is {escrow['currency']!r}; routing "
                f"asked {currency!r}.",
                issued_for="route_19")
        if amount_cents > balance:
            return self._refuse(
                unity_id, KIND_NINETEEN_ROUTE, REASON_INSUFFICIENT_ESCROW,
                f"routing {amount_cents} {UNIT} exceeds HELD escrow "
                f"balance {balance} {UNIT}.",
                issued_for="route_19")

        if _SPLIT_RULING is None:
            # HELD: receipt the attempt, move nothing.
            receipt = {
                "schema": SCHEMA,
                "type": "NINETEEN_ROUTE",
                "kind": KIND_NINETEEN_ROUTE,
                "unity_id": unity_id,
                "outcome": OUTCOME_HELD,
                "reason": REASON_SPLIT_HELD_FOR_DAVID,
                "status": AWAITING_SPLIT_RULING,
                "amount_cents": amount_cents,
                "currency": currency,
                "unit": UNIT,
                "destinations": None,
                "escrow_balance_before_cents": balance,
                "escrow_balance_after_cents": balance,
                "receipt_id": self._receipt_id(
                    KIND_NINETEEN_ROUTE, unity_id, amount_cents,
                    len(self._state["routing_log"])),
                "testnet": True,
                "issued_at": self._utc_now(),
                "provenance": "DERIVED",
                "note": (
                    "The three-way 19% split (CORE_CAUSE_LOCK / "
                    "PLAYGROUND_FUEL / PEG_SUPPORT) is HELD-FOR-DAVID. "
                    "This routing attempt is receipted as "
                    "AWAITING_SPLIT_RULING; the 19% stays in escrow, "
                    "never deployed."
                ),
            }

            def mutate(state):
                state["routing_log"].append({
                    "unity_id": unity_id,
                    "amount_cents": amount_cents,
                    "currency": currency,
                    "status": AWAITING_SPLIT_RULING,
                    "destinations": None,
                    "routing_receipt_id": receipt["receipt_id"],
                    "at": receipt["issued_at"],
                })
                return {"routed_cents": 0, "status": AWAITING_SPLIT_RULING}

            _n_rl = len(self._state["routing_log"])
            return self._commit(KIND_NINETEEN_ROUTE, receipt, mutate,
                                before={"routing_log": _n_rl},
                                after={"routing_log": _n_rl + 1,
                                       "status": "AWAITING_SPLIT_RULING"})

        # -- post-ruling path: closed in this build -----------------------
        # _SPLIT_RULING is None until David's ruling lands as a code
        # change plus receipt. The implementation below is complete but
        # unreachable until then.
        return self._route_by_ruling(unity_id, amount_cents, currency)

    def _route_by_ruling(self, unity_id, amount_cents, currency):
        """Route the 19% per David's three-way ruling. UNREACHABLE while
        _SPLIT_RULING is None (this build). Kept complete so the ruling,
        when it lands, executes against tested code."""
        ruling = _SPLIT_RULING or {}
        ratios = {name: ruling.get(name, 0) for name in ROUTE_DESTINATIONS}
        if abs(sum(ratios.values()) - 1.0) > 1e-9:
            raise OnboardError(
                "split ruling ratios must sum to 1.0: "
                f"got {ratios!r}")
        # Largest-remainder: integer-exact, no value leaks to rounding.
        legs = {}
        remainders = []
        assigned = 0
        for name in ROUTE_DESTINATIONS:
            exact = amount_cents * ratios[name]
            whole = int(exact)
            legs[name] = whole
            assigned += whole
            remainders.append((exact - whole, name))
        for _, name in sorted(remainders, reverse=True)[:amount_cents
                                                        - assigned]:
            legs[name] += 1
        receipt = {
            "schema": SCHEMA,
            "type": "NINETEEN_ROUTE",
            "kind": KIND_NINETEEN_ROUTE,
            "unity_id": unity_id,
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "status": "ROUTED",
            "amount_cents": amount_cents,
            "currency": currency,
            "unit": UNIT,
            "destinations": {
                name: {"amount_cents": legs[name], "ratio": ratios[name]}
                for name in ROUTE_DESTINATIONS
            },
            "receipt_id": self._receipt_id(
                KIND_NINETEEN_ROUTE, unity_id, amount_cents, "ruled",
                len(self._state["routing_log"])),
            "testnet": True,
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",
            "note": "19% routed per David's three-way ruling.",
        }

        def mutate(state):
            escrow = state["escrow"][unity_id]
            escrow["balance_cents"] -= amount_cents
            for name in ROUTE_DESTINATIONS:
                dest = state["destinations"][name]
                dest["balance_cents"] += legs[name]
                dest["entries"].append({
                    "unity_id": unity_id,
                    "amount_cents": legs[name],
                    "at": receipt["issued_at"],
                })
            state["routing_log"].append({
                "unity_id": unity_id,
                "amount_cents": amount_cents,
                "currency": currency,
                "status": "ROUTED",
                "destinations": legs,
                "routing_receipt_id": receipt["receipt_id"],
                "at": receipt["issued_at"],
            })
            return {"routed_cents": amount_cents, "legs": legs}

        _n_rl2 = len(self._state["routing_log"])
        return self._commit(KIND_NINETEEN_ROUTE, receipt, mutate,
                            before={"routing_log": _n_rl2},
                            after={"routing_log": _n_rl2 + 1,
                                   "status": "ROUTED"})

    # -- stage 5: recovery work -> wave merit (top band) -------------------------

    @staticmethod
    def merit_band_for(work_class):
        """The minimal merit band structure. Only the top band is
        defined in this build: verified real-world recovery work. Any
        other work class -> OnboardRefused(UNSUPPORTED_WORK_CLASS):
        band calibration beyond the top band needs David — HELD, never
        invented."""
        band = MERIT_BANDS.get(work_class)
        if band is None:
            raise OnboardRefused(
                REASON_UNSUPPORTED_WORK_CLASS,
                f"work class {work_class!r} has no defined merit band; "
                "only 'recovery' (top band, verified real-world recovery "
                "work) is defined. Further band calibration is "
                "HELD-FOR-DAVID.",
            )
        return band

    def _engine(self):
        """The tokenization worker's engine for the merit path, or None
        when the path is PENDING."""
        if self._tokenizer is not None:
            return self._tokenizer
        return _default_tokenizer()

    def _validate_work_receipt(self, unity_id, receipt):
        """Validate one caller-supplied work receipt for top-band merit.

        Returns (ok, result): ok False -> result is the refusal/skip
        record (no tokenize call); ok True -> result is the normalized
        receipt ready for the engine. Merit flows ONLY from VERIFIED
        gated receipts naming this onboarder's own Unity ID, carrying
        their own positive merit_value (the pipeline never invents
        calibration), for recovery-class work.
        """
        if not isinstance(receipt, dict):
            return False, {"status": OUTCOME_REFUSED,
                           "reason": REASON_INVALID_WORK_RECEIPT,
                           "detail": f"work receipt is not a dict: "
                                     f"{receipt!r}"}
        rid = receipt.get("receipt_id")
        if receipt.get("unity_id") != unity_id:
            return False, {
                "status": OUTCOME_REFUSED,
                "reason": REASON_WORK_RECEIPT_IDENTITY_MISMATCH,
                "receipt_id": rid,
                "detail": "merit is earned by the receipt's own Unity ID "
                          "only — never another ID's work."}
        if receipt.get("kind") != "work":
            return False, {
                "status": OUTCOME_REFUSED,
                "reason": REASON_INVALID_WORK_RECEIPT,
                "receipt_id": rid,
                "detail": f"receipt kind {receipt.get('kind')!r} is not "
                          "'work'."}
        if receipt.get("provenance") != "VERIFIED":
            # UNKNOWN never accrues. Neither does anything not VERIFIED.
            return False, {
                "status": OUTCOME_REFUSED,
                "reason": REASON_UNVERIFIED_WORK_RECEIPT,
                "receipt_id": rid,
                "detail": "only VERIFIED gated work receipts accrue "
                          f"merit — got provenance "
                          f"{receipt.get('provenance')!r}."}
        mh = receipt.get("manifest_hash")
        if not (rid and isinstance(mh, str) and len(mh) == 64
                and all(c in "0123456789abcdef" for c in mh.lower())):
            return False, {
                "status": OUTCOME_REFUSED,
                "reason": REASON_INVALID_WORK_RECEIPT,
                "receipt_id": rid,
                "detail": "receipt needs receipt_id and manifest_hash "
                          "(64 hex chars)."}
        mv = receipt.get("merit_value")
        if isinstance(mv, bool) or not isinstance(mv, (int, float)) \
                or mv <= 0:
            # Band calibration is HELD-FOR-DAVID: the verifying
            # authority asserts merit_value on the receipt. The pipeline
            # never invents it.
            return False, {
                "status": OUTCOME_REFUSED,
                "reason": REASON_NON_POSITIVE_MERIT_VALUE,
                "receipt_id": rid,
                "detail": "work receipt needs a positive merit_value "
                          "from the verifying authority — the pipeline "
                          "never invents band calibration."}
        detail = receipt.get("detail") if isinstance(
            receipt.get("detail"), dict) else {}
        work_class = detail.get("work_class")
        try:
            band = self.merit_band_for(work_class)
        except OnboardRefused as exc:
            return False, {
                "status": OUTCOME_REFUSED,
                "reason": exc.reason,
                "receipt_id": rid,
                "detail": exc.detail}
        if rid in self._state["consumed_work_receipts"]:
            prior = self._state["consumed_work_receipts"][rid]
            return False, {
                "status": OUTCOME_REPLAYED,
                "reason": None,
                "receipt_id": rid,
                "detail": "work receipt already submitted for merit — "
                          "replayed, never double-counted.",
                "merit_value": prior["merit_value"]}
        return True, {"receipt": receipt, "receipt_id": rid,
                      "manifest_hash": mh.lower(),
                      "merit_value": float(mv), "band": band["band"]}

    def accrue_recovery_merit(self, unity_id, work_receipts, tokenizer=None):
        """Verified recovery-work receipts -> wave merit (top band) via
        the tokenization worker's merit path.

        Each VERIFIED, recovery-class work receipt naming this
        onboarder's own Unity ID is passed to the tokenization worker,
        which accrues merit through dclm_commit (MERIT_ACCRUAL) — merit
        for the WORK. Unverified receipts, receipts for another ID, and
        non-recovery work classes accrue nothing. No receipts -> no
        merit. Replays -> replayed, never double-counted.

        Honest gates: when the tokenization worker is absent, the merit
        path is PENDING and accrual stays closed (never accrue on
        UNKNOWN). When the worker's peg E is unset (HELD-FOR-DAVID), the
        engine refuses work receipts cleanly and the merit is DEFERRED —
        recorded, receipted, retryable after his ruling — never accrued
        on unknown terms.
        """
        # PURIFY ON ENTRY: the medium first. Each work receipt travels
        # as the caller's claim; the engine re-validates every one.
        purify_input(
            {"unity_id": unity_id, "action": "ACCRUE_RECOVERY_MERIT",
             "claims": [{"claim": "recovery-merit-request",
                         "provenance": "DERIVED"}]},
            context={"path": "onboard.accrue_recovery_merit"},
        )
        self._require_testnet(unity_id)
        if self._onboarder(unity_id) is None:
            # PURIFY ON EXIT: the summary leaves labeled.
            return purify_output(
                {
                    "unity_id": unity_id,
                    "outcome": OUTCOME_REFUSED,
                    "reason": REASON_ONBOARDER_UNKNOWN,
                    "results": [],
                    "merit_accrued_total": 0.0,
                    "testnet": True,
                    "provenance": "DERIVED",
                },
                context={"path": "onboard.accrue_recovery_merit"},
            )
        if not isinstance(work_receipts, list):
            raise OnboardRefused(
                REASON_INVALID_WORK_RECEIPT,
                f"work_receipts must be a list; got "
                f"{type(work_receipts).__name__!r}.")
        if not work_receipts:
            # No receipts -> no merit. Honestly reported, nothing written.
            return purify_output(
                {
                    "unity_id": unity_id,
                    "outcome": OUTCOME_REFUSED,
                    "reason": REASON_NO_WORK_RECEIPTS,
                    "results": [],
                    "merit_accrued_total": 0.0,
                    "band": BAND_RECOVERY,
                    "note": "No work receipts presented: no merit accrued. "
                            "Merit is earned for verified work, never "
                            "assumed.",
                    "testnet": True,
                    "provenance": "DERIVED",
                },
                context={"path": "onboard.accrue_recovery_merit"},
            )

        engine = tokenizer if tokenizer is not None else self._engine()
        if engine is None:
            # PENDING: the tokenization worker has not landed. Accrual
            # stays closed — never accrue on UNKNOWN.
            return purify_output(
                {
                    "unity_id": unity_id,
                    "outcome": OUTCOME_REFUSED,
                    "reason": REASON_MERIT_PATH_PENDING,
                    "results": [],
                    "merit_accrued_total": 0.0,
                    "note": "Merit path PENDING: dclm/tokenize.py has not "
                            "landed. Accrual stays closed until it exists — "
                            "never accrue on UNKNOWN.",
                    "testnet": True,
                    "provenance": "DERIVED",
                },
                context={"path": "onboard.accrue_recovery_merit"},
            )
        api = _load_tokenize_api()
        _, TokenizeRefused, peg_unset_reason = api

        results = []
        accrued = []  # (receipt_id, merit_value, engine envelope ref)
        merit_total = 0.0
        for wr in work_receipts:
            ok, checked = self._validate_work_receipt(unity_id, wr)
            if not ok:
                results.append(checked)
                continue
            try:
                bundle = engine.tokenize(checked["receipt"])
            except TokenizeRefused as exc:
                if exc.reason == peg_unset_reason:
                    # The engine's peg E is HELD-FOR-DAVID: the work is
                    # verified but its terms are not yet set. DEFERRED —
                    # recorded, receipted, retryable. Nothing accrued.
                    results.append({
                        "status": "DEFERRED",
                        "reason": REASON_MERIT_DEFERRED_PEG_UNSET,
                        "receipt_id": checked["receipt_id"],
                        "merit_value": checked["merit_value"],
                        "detail": "Tokenization worker refused: peg E is "
                                  "HELD-FOR-DAVID. Verified work recorded; "
                                  "merit deferred until his ruling — "
                                  "never accrued on unknown terms."})
                else:
                    results.append({
                        "status": OUTCOME_REFUSED,
                        "reason": REASON_ENGINE_REFUSED,
                        "receipt_id": checked["receipt_id"],
                        "detail": f"engine refused: {exc.reason}: "
                                  f"{exc.detail}"})
                continue
            merit_env = bundle.merit
            ref = merit_env["canonical_sha256"] if isinstance(
                merit_env, dict) else None
            accrued.append((checked["receipt_id"], checked["merit_value"],
                            ref, checked["manifest_hash"]))
            merit_total += checked["merit_value"]
            results.append({
                "status": "ACCRUED",
                "reason": None,
                "receipt_id": checked["receipt_id"],
                "merit_value": checked["merit_value"],
                "band": checked["band"],
                "engine_ref": ref,
                "detail": "Top-band wave merit accrued for verified "
                          "recovery work, via the tokenization worker "
                          "(MERIT_ACCRUAL). Merit for the WORK."})

        # Record consumption: each accrued receipt is marked consumed in
        # ONE pipeline commit (RESIDUAL_INTAKE, intake_class
        # recovery_work) so a verified receipt is never double-counted.
        # Deferred and refused receipts are NOT marked — they stay
        # retryable.
        commit_envelope = None
        if accrued:
            intake_receipt = {
                "schema": SCHEMA,
                "type": "RESIDUAL_INTAKE",
                "kind": KIND_RESIDUAL_INTAKE,
                "intake_class": INTAKE_RECOVERY_WORK,
                "unity_id": unity_id,
                "outcome": OUTCOME_GRANTED,
                "reason": None,
                "band": BAND_RECOVERY,
                "receipt_ids": [r[0] for r in accrued],
                "merit_accrued_total": merit_total,
                "receipt_id": self._receipt_id(
                    KIND_RESIDUAL_INTAKE, unity_id, "work",
                    len(self._state["work_intakes"])),
                "testnet": True,
                "issued_at": self._utc_now(),
                "provenance": "DERIVED",
                "note": (
                    "Verified recovery-work evidence intaken for top-band "
                    "wave merit. Consumption recorded so no receipt is "
                    "ever double-counted."
                ),
            }

            def mutate(state, _accrued=accrued, _at=intake_receipt[
                    "issued_at"]):
                for rid, mv, ref, mh in _accrued:
                    state["consumed_work_receipts"][rid] = {
                        "unity_id": unity_id,
                        "merit_value": mv,
                        "engine_ref": ref,
                        "manifest_hash": mh,
                        "consumed_at": _at,
                    }
                state["work_intakes"].append({
                    "unity_id": unity_id,
                    "band": BAND_RECOVERY,
                    "receipt_ids": [r[0] for r in _accrued],
                    "merit_accrued_total": merit_total,
                    "intake_receipt_id": intake_receipt["receipt_id"],
                    "intaken_at": _at,
                })
                return {"consumed": len(_accrued),
                        "merit_accrued_total": merit_total}

            _n_wi = len(self._state["work_intakes"])
            commit_envelope = self._commit(
                KIND_RESIDUAL_INTAKE, intake_receipt, mutate,
                before={"work_intakes": _n_wi},
                after={"work_intakes": _n_wi + 1,
                       "consumed": len(accrued)})

        statuses = {r["status"] for r in results}
        if statuses <= {"ACCRUED", OUTCOME_REPLAYED} and "ACCRUED" in statuses:
            outcome = "COMPLETE"
        elif "ACCRUED" in statuses:
            outcome = "PARTIAL"
        elif statuses == {"DEFERRED"}:
            outcome = "DEFERRED"
        elif statuses == {OUTCOME_REPLAYED}:
            outcome = OUTCOME_REPLAYED
        else:
            outcome = OUTCOME_REFUSED
        # PURIFY ON EXIT: the summary leaves labeled, identity-bound; the
        # consumption envelope's signature is verified.
        return purify_output(
            {
                "unity_id": unity_id,
                "outcome": outcome,
                "results": results,
                "merit_accrued_total": merit_total,
                "band": BAND_RECOVERY,
                "band_calibration": "HELD_FOR_DAVID",
                "consumption_envelope": commit_envelope,
                "testnet": True,
                "issued_at": self._utc_now(),
                "provenance": "DERIVED",
                "note": (
                    "Wave merit (top band) flows only from VERIFIED "
                    "recovery-work receipts, through the tokenization "
                    "worker's merit path. Merit for the WORK — never for "
                    "value moved."
                ),
            },
            context={"path": "onboard.accrue_recovery_merit"},
        )

    # -- flywheel state ---------------------------------------------------------

    def flywheel_state(self):
        """Honest aggregates of the flywheel. Every figure labeled; the
        81% appears ONLY as acknowledged off-system value — never as
        system value."""
        escrow_total = sum(
            e["balance_cents"] for e in self._state["escrow"].values())
        reported_total = sum(
            i["amount_cents"] for i in self._state["residual_intakes"]
            if i.get("intake_class", INTAKE_RESIDUAL_FIGURE)
            == INTAKE_RESIDUAL_FIGURE)
        eighty_one_total = sum(
            s["eighty_one_cents"] for s in self._state["splits"])
        peg_support = self._state["destinations"][ROUTE_PEG_SUPPORT][
            "balance_cents"]
        return {
            "schema": SCHEMA,
            "testnet": True,
            "unit": UNIT,
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",
            "onboarders": len(self._state["onboarders"]),
            "residual_reported_total_cents": reported_total,
            "residual_label": "REPORTED",
            "residual_note": (
                "Sum of REPORTED residual figures (paperwork-hash "
                "intakes). MODELED figures are refused at intake and "
                "never appear here."),
            "escrow_19_total_cents": escrow_total,
            "escrow_status": (
                "HELD — " + AWAITING_SPLIT_RULING
                if _SPLIT_RULING is None else "ROUTING_PER_RULING"),
            "peg_support_contribution_cents": peg_support,
            "peg_support_status": (
                "HELD — no routing until David sets the three-way "
                "19% split" if _SPLIT_RULING is None
                else "ROUTING_PER_RULING"),
            "onboarder_81_acknowledged": {
                "total_cents": eighty_one_total,
                "disposition": DISPOSITION_ACKNOWLEDGED_OFF_SYSTEM,
                "system_value": False,
                "note": (
                    "The onboarders' 81%: fiat, theirs, untouched. "
                    "Acknowledged off-system — NEVER counted as system "
                    "value. Shown here only so the acknowledgment is "
                    "auditable."),
            },
            "flywheel_note": (
                "More onboarders -> more residual found -> more real "
                "value grounding the peg -> more merit-earning work -> "
                "more emission -> more reason to onboard. The coin's "
                "substance is recovered waste: inefficiency being healed."),
        }


# ---------------------------------------------------------------------------
# module-level API (default pipeline, default state dir)
# ---------------------------------------------------------------------------

_DEFAULT_PIPELINE = None


def _default():
    global _DEFAULT_PIPELINE
    if _DEFAULT_PIPELINE is None:
        _DEFAULT_PIPELINE = OnboardPipeline()
    return _DEFAULT_PIPELINE


def onboard(unity_id, paperwork_ref):
    """Onboard a Unity-bound onboarder (unity:testnet: enforced)."""
    return _default().onboard(unity_id, paperwork_ref)


def record_residual(unity_id, figure, paperwork_hash):
    """Intake a REPORTED residual figure (paperwork hash required)."""
    return _default().record_residual(unity_id, figure, paperwork_hash)


def execute_split(unity_id, recovered_amount, currency=None, split_id=None):
    """Execute the 81/19 split on a recovered amount."""
    return _default().execute_split(unity_id, recovered_amount, currency,
                                    split_id)


def route_19(unity_id, amount_cents, currency=None):
    """Route the 19% — HELD as AWAITING_SPLIT_RULING until David rules."""
    return _default().route_19(unity_id, amount_cents, currency)


def accrue_recovery_merit(unity_id, work_receipts, tokenizer=None):
    """Verified recovery-work receipts -> wave merit (top band)."""
    return _default().accrue_recovery_merit(unity_id, work_receipts,
                                            tokenizer)


def flywheel_state():
    """Honest aggregates of the flywheel, all labeled."""
    return _default().flywheel_state()


def escrow_balance(unity_id):
    """The onboarder's HELD 19% escrow balance, in fiat-cents."""
    return _default().escrow_balance(unity_id)

"""
DCLM METERING ENGINE — "Free world, paid intent."

Looking costs nothing. Wanting costs keys.

  LOOK / RENDER — FREE. No wallet, no identity needed. The world is free.
  SEARCH        — metered. Costs PRICE_SEARCH test-keys.
  COMPUTE       — metered. A DCLM verdict run costs PRICE_COMPUTE test-keys.

Units are TEST-KEYS: clearly labeled TEST, never dollars, never eFuse.
No real money, no key custody — the Wallet is a server-side ledger
(identity -> integer balance), not a vault. Testnet only.

Honesty rules (absolute):
  * Metered actions require a BOUND Unity identity of the form
    "unity:testnet:..." (same format as the gate's gate.py). Anything
    else is REFUSED — honestly, in a signed receipt.
  * Insufficient keys -> REFUSAL receipt (reason INSUFFICIENT_KEYS).
    The world stays free; only the intent is unserved. Never a world block.
  * Every receipt carries provenance labels; UNKNOWN is never PASS.
  * Idempotency: same intent_id twice -> same receipt, charged once.
    Refusals are NOT cached: a retry re-evaluates the live balance.
  * The ledger never goes negative: deduction happens only when
    balance >= price, asserted after every mutation.

Rights & writes boundary (David's binding rule):
  DCLM holds the RIGHTS and performs the WRITES. Every ledger mutation
  in this module (debits, credits) flows through writes.dclm_commit
  with a rights.check_rights verdict first: request -> rights check ->
  GRANT -> dclm_commit performs the single mutation -> signed receipt.
  The thin client never writes; this module never mutates the ledger
  except inside the commit path's apply_write.

Emission gate (David's law, 2026-10-06 — derivative merit regeneration,
NOT token cascade): emission_eligibility(identity) is the read-only gate
any emission must consult. Eligible ONLY against the identity's OWN
verified-receipt merit, read from the tokenization worker's merit ledger
via a bound MeritReader. No reader bound, unknown merit, or zero merit ->
emission stays CLOSED. UNKNOWN never PASS. The gate performs no writes.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from compute import (  # noqa: E402 — reuse the existing test key material
    ED25519_HELPER,
    KEY_ID,
    PROVENANCE_LABELS,
    TEST_PRIV_KEY,
    TEST_PUB_KEY,
)
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from writes import CommitStore, dclm_commit  # noqa: E402 — the single commit path
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    purify_input,
    purify_output,
    purify_transition,
    PurificationRefused,
)
import re as _re

_PURIFY_REASON_RE = _re.compile(r"\[([A-Z_]+)\]")


def _purify_reason(exc):
    """Extract the [REASON] tag from a PurificationRefused message."""
    m = _PURIFY_REASON_RE.search(str(exc))
    return m.group(1) if m else "UNKNOWN"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.meter.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"  # same format gate.py enforces

# The only unit of account: TEST KEYS. Never dollars, never eFuse.
UNIT = "test-keys"

# --- price list (named constants, easy to change) ---------------------------
ACTION_LOOK = "LOOK"
ACTION_RENDER = "RENDER"
ACTION_SEARCH = "SEARCH"
ACTION_COMPUTE = "COMPUTE"

PRICE_LOOK = 0       # looking is free
PRICE_RENDER = 0     # rendering is free
PRICE_SEARCH = 1     # one test-key to search
PRICE_COMPUTE = 5    # five test-keys for a DCLM verdict run

PRICES = {
    ACTION_LOOK: PRICE_LOOK,
    ACTION_RENDER: PRICE_RENDER,
    ACTION_SEARCH: PRICE_SEARCH,
    ACTION_COMPUTE: PRICE_COMPUTE,
}

FREE_ACTIONS = frozenset({ACTION_LOOK, ACTION_RENDER})
METERED_ACTIONS = frozenset({ACTION_SEARCH, ACTION_COMPUTE})

# --- outcomes / refusal reasons --------------------------------------------
OUTCOME_GRANTED = "GRANTED"
OUTCOME_REFUSED = "REFUSED"

REASON_INSUFFICIENT_KEYS = "INSUFFICIENT_KEYS"
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_IDENTITY_REQUIRED = "IDENTITY_REQUIRED"
REASON_UNKNOWN_ACTION = "UNKNOWN_ACTION"

REFUSAL_REASONS = frozenset({
    REASON_INSUFFICIENT_KEYS,
    REASON_NOT_TESTNET_IDENTITY,
    REASON_IDENTITY_REQUIRED,
    REASON_UNKNOWN_ACTION,
})

# --- emission gate (derivative merit regeneration — David's law) ------------
EMISSION_ELIGIBILITY_SCHEMA = "unity.meter.emission-eligibility.v1.testnet"

# Verdict reasons for emission_eligibility. Every non-eligible reason
# leaves emission CLOSED: UNKNOWN never PASS, and no reader means no
# known merit, which also never passes.
REASON_MERIT_LEDGER_PENDING = "MERIT_LEDGER_PENDING"      # interface defined, no reader bound
REASON_MERIT_LEDGER_UNREACHABLE = "MERIT_LEDGER_UNREACHABLE"  # reader failed — closed, honestly
REASON_MERIT_UNKNOWN = "MERIT_UNKNOWN"                    # reader returned None — UNKNOWN never PASS
REASON_NO_VERIFIED_MERIT = "NO_VERIFIED_MERIT"             # known identity, zero/negative own merit

EMISSION_INELIGIBLE_REASONS = frozenset({
    REASON_MERIT_LEDGER_PENDING,
    REASON_MERIT_LEDGER_UNREACHABLE,
    REASON_MERIT_UNKNOWN,
    REASON_NO_VERIFIED_MERIT,
    REASON_NOT_TESTNET_IDENTITY,
})

# --- money-only wallet -------------------------------------------------------
# The wallet moves TEST-KEYS. Merit never enters the wallet: earned
# STANDING is origin-bound and unmovable, recorded by the tokenization
# worker (dclm/tokenize.py); owned Merit moves only through the engine's
# receipted merit_transfer(), never through this ledger. This ledger
# holds integer test-key balances and nothing else. Both guards below
# enforce it structurally.
MONEY_ONLY_OPS = frozenset({"debit", "credit"})
_ALLOWED_LEDGER_KEYS = frozenset({"schema", "balances", "intents"})

DEFAULT_STATE_DIR = os.path.join(_HERE, "state-meter")
LEDGER_FILENAME = "meter-ledger.json"
RECEIPTS_FILENAME = "meter-receipts.jsonl"


class MeterError(Exception):
    """Base class for metering failures."""


class MeterRefused(MeterError):
    """Structural refusal: e.g. faucet for a non-testnet identity."""


class _MeterCommitStore(CommitStore):
    """DCLM-internal adapter: lets writes.dclm_commit drive the Wallet's
    single mutation point.

    The thin client never touches this, and the Wallet never mutates its
    ledger except inside apply_write — which dclm_commit calls exactly
    once, and only after a DCLM-issued GRANT verdict. build_receipt
    returns the meter's own receipt dict unchanged, so receipt bytes are
    identical to before the boundary existed; append_receipt logs the
    signed receipt exactly as the meter always has.
    """

    def __init__(self, wallet, *, identity, receipt, op,
                 balance_before, balance_after, intent_key=None):
        self._wallet = wallet
        self._identity = identity
        self._receipt = receipt
        # MONEY-ONLY GUARD: the wallet moves test-keys, never merit. Only
        # debit/credit of integer test-key balances may pass this point;
        # anything else is refused before any mutation is possible.
        if op not in MONEY_ONLY_OPS:
            raise MeterError(
                f"wallet is money-only: op {op!r} refused — "
                "merit never enters the wallet"
            )
        for _name, _value in (("balance_before", balance_before),
                              ("balance_after", balance_after)):
            if isinstance(_value, bool) or not isinstance(_value, int):
                raise MeterError(
                    f"wallet is money-only: {_name} must be an integer "
                    f"of test-keys, got {_value!r} — merit never enters "
                    "the wallet"
                )
        self._op = op  # "debit" | "credit"
        self._balance_before = balance_before
        self._balance_after = balance_after
        self._intent_key = intent_key

    def apply_write(self, kind, payload):
        """THE single ledger mutation point for metered writes.

        Called exactly once per commit, only after GRANT. Performs the
        balance change, the idempotency registration (debits), and the
        persistence — then reports the mutation.
        """
        self._wallet._ledger["balances"][self._identity] = self._balance_after
        self._wallet._assert_ledger_nonnegative()
        if self._op == "debit":
            self._wallet._ledger["intents"][self._intent_key] = self._receipt
        self._wallet._save()
        return {
            "op": self._op,
            "identity": self._identity,
            "balance_before": self._balance_before,
            "balance_after": self._balance_after,
        }

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        # The meter receipt IS the receipt: same bytes as before the
        # boundary. Provenance was asserted when the receipt was built.
        return self._receipt

    def append_receipt(self, envelope):
        self._wallet._log(envelope["receipt"])


# ---------------------------------------------------------------------------
# Wallet — per-identity test-key ledger + intent metering
# ---------------------------------------------------------------------------
class Wallet:
    """Server-side test-key ledger.

    balances: identity -> integer test-keys (never negative).
    intents:  (identity, intent_id) -> granted receipt. Charged once;
              refusals are never cached.
    """

    def __init__(self, state_dir=None):
        self.state_dir = state_dir or os.environ.get(
            "UNITY_METER_STATE_DIR", DEFAULT_STATE_DIR
        )
        os.makedirs(self.state_dir, exist_ok=True)
        self.ledger_path = os.path.join(self.state_dir, LEDGER_FILENAME)
        self.receipts_path = os.path.join(self.state_dir, RECEIPTS_FILENAME)
        self._ledger = self._load()

    # -- persistence -------------------------------------------------------

    def _load(self):
        if not os.path.exists(self.ledger_path):
            return {"schema": SCHEMA, "balances": {}, "intents": {}}
        with open(self.ledger_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") != SCHEMA:
            raise MeterError(
                f"ledger schema mismatch: expected {SCHEMA}, "
                f"found {data.get('schema')!r} — refusing to read foreign state"
            )
        # MONEY-ONLY GUARD: the ledger holds integer test-key balances and
        # intent receipts — nothing else. Merit never enters the wallet, so
        # any merit-shaped key or non-integer balance is foreign state and
        # the ledger is refused outright (never repaired, never migrated).
        for key in data:
            if key not in _ALLOWED_LEDGER_KEYS or "merit" in key.lower():
                raise MeterError(
                    f"ledger shape violation: unexpected key {key!r} — "
                    "the wallet is money-only; refusing to read foreign state"
                )
        balances = data.get("balances", {})
        if not isinstance(balances, dict):
            raise MeterError("ledger shape violation: balances is not a dict")
        for ident, bal in balances.items():
            if isinstance(bal, bool) or not isinstance(bal, int):
                raise MeterError(
                    f"ledger shape violation: balance for {ident!r} is "
                    f"{bal!r} — the wallet holds integer test-keys only; "
                    "merit never enters the wallet"
                )
        return data

    def _save(self):
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".meter-ledger-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._ledger, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, self.ledger_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _log(self, receipt):
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True) + "\n")

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _receipt_id(identity, action, intent_id):
        """Deterministic receipt ID per (identity, action, intent_id)."""
        return hashlib.sha256(
            f"{SCHEMA}|{identity}|{action}|{intent_id}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _intent_key(identity, intent_id):
        """Idempotency key: an intent is (identity, intent_id), regardless
        of action — resubmitting the same intent replays, never re-charges."""
        return hashlib.sha256(
            f"{SCHEMA}|intent|{identity}|{intent_id}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _require_testnet(identity):
        """Structural refusal: non-testnet identities never touch the ledger."""
        if not isinstance(identity, str) or not identity.startswith(IDENTITY_PREFIX):
            raise MeterRefused(
                "structural refusal: identity must start with "
                f"{IDENTITY_PREFIX!r}; got {identity!r}. Testnet only."
            )

    def _assert_ledger_nonnegative(self):
        for identity, balance in self._ledger["balances"].items():
            if balance < 0:
                raise MeterError(
                    f"LEDGER VIOLATION: negative balance {balance} "
                    f"for {identity!r} — refusing to continue"
                )

    def _assert_receipt_labeled(self, receipt):
        """Every receipt carries a valid provenance label. UNKNOWN never PASS:
        no GRANTED receipt may hide behind an unknown label."""
        label = receipt.get("provenance")
        if label not in PROVENANCE_LABELS:
            raise MeterError(f"receipt missing valid provenance label: {receipt!r}")
        if receipt.get("outcome") == OUTCOME_GRANTED and label == "UNKNOWN":
            raise MeterError(
                "UNKNOWN is never PASS: refusing to grant on an UNKNOWN label"
            )

    # -- public API --------------------------------------------------------

    def balance(self, identity):
        """Current test-key balance. Unknown identity -> 0, honestly."""
        return self._ledger["balances"].get(identity, 0)

    def faucet(self, identity, amount):
        """Fund an identity with test units. TEST KEYS ONLY — never dollars,
        never eFuse. Logged to the receipt trail.

        Raises MeterRefused for non-testnet identities, ValueError for
        non-positive amounts.
        """
        # PURIFY ON ENTRY: the medium first. A purification refusal on
        # funding surfaces as MeterRefused (the faucet's own denial) —
        # no anonymous input crosses into the ledger, and the denial is
        # typed for the caller.
        try:
            purify_input(
                {"identity": identity, "action": "FAUCET", "amount": amount,
                 "claims": [{"claim": "faucet-funding-request",
                             "provenance": "DERIVED"}]},
                context={"path": "meter.faucet"},
            )
        except PurificationRefused as e:
            raise MeterRefused(f"faucet refused [{_purify_reason(e)}]: {e}")
        self._require_testnet(identity)
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(
                f"faucet amount must be a positive integer of {UNIT}; "
                f"got {amount!r}"
            )
        before = self._ledger["balances"].get(identity, 0)
        record = {
            "schema": SCHEMA,
            "type": "FUNDING",
            "identity": identity,
            "action": "FAUCET",
            "amount": amount,
            "unit": UNIT,
            "testnet": True,
            "balance_before": before,
            "balance_after": before + amount,
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "receipt_id": self._receipt_id(identity, "FAUCET", str(amount)),
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # computed in-process over present ledger
            "note": (
                f"TEST funding only: {amount} {UNIT} minted to {identity}. "
                "Not dollars. Not eFuse."
            ),
        }
        self._assert_receipt_labeled(record)
        # RIGHTS, then WRITE: the mint flows through the single commit
        # path. check_rights authorizes; dclm_commit performs the one
        # mutation and emits the signed receipt. The thin client has no
        # path here — this is DCLM-internal.
        verdict = check_rights(
            identity, "LEDGER_CREDIT",
            {"internal": "dclm.meter", "schema": SCHEMA,
             "operation": "FAUCET", "amount": amount},
        )
        # PURIFY IN FLIGHT: the transition itself is checked — kind
        # whitelisted, receipt planned and labeled, the balance change
        # declared (no silent mutation) — before writes.py commits.
        purify_transition(
            {"balance": before}, {"balance": before + amount},
            "LEDGER_CREDIT",
            context={"receipt": record, "identity": identity,
                     "path": "meter.faucet"},
        )
        envelope = dclm_commit(
            "LEDGER_CREDIT", record, verdict,
            _MeterCommitStore(
                self, identity=identity, receipt=record, op="credit",
                balance_before=before, balance_after=before + amount,
            ),
        )
        # PURIFY ON EXIT: nothing leaves DCLM unlabeled, unsigned, or
        # identity-unbound.
        return purify_output(
            envelope, context={"path": "meter.faucet", "signed": True},
        )

    def meter_intent(self, identity, action, intent_id):
        """Meter one intent. Returns a SIGNED receipt envelope.

        Free actions (LOOK, RENDER) -> GRANTED, no deduction, no identity
        or wallet needed. The world is free to look at.

        Metered actions (SEARCH, COMPUTE) -> require a "unity:testnet:..."
        identity; deduct the price; return a signed receipt with action,
        amount, new balance, intent_id. Same intent_id twice -> same
        receipt, charged once (no double-spend).

        Insufficient keys -> signed REFUSAL receipt with reason
        INSUFFICIENT_KEYS. The world stays free; only the intent goes
        unserved. Balance untouched.
        """
        if not intent_id:
            raise MeterError("intent_id is required: intents are metered by intent")

        # PURIFY ON ENTRY: the medium first. A purification refusal on a
        # metered intent surfaces as a SIGNED REFUSAL receipt (the medium
        # denies, DCLM receipts the denial) — never a bare exception the
        # caller must guess at. Free-world actions (LOOK/RENDER) may
        # arrive identity-free; a forged identity is still refused even
        # there.
        try:
            purify_input(
                {"identity": identity, "action": action, "intent_id": intent_id,
                 "claims": [{"claim": "intent-metering-request",
                             "provenance": "DERIVED"}]},
                context={"path": "meter.meter_intent",
                         "free_world": action in FREE_ACTIONS},
            )
        except PurificationRefused as e:
            # No usable identity presented (absent or empty) ->
            # IDENTITY_REQUIRED; a presented-but-foreign identity ->
            # NOT_TESTNET_IDENTITY.
            if not identity:
                meter_reason = REASON_IDENTITY_REQUIRED
            else:
                purify_reason = _purify_reason(e)
                meter_reason = (
                    REASON_IDENTITY_REQUIRED
                    if purify_reason == "NO_IDENTITY"
                    else REASON_NOT_TESTNET_IDENTITY
                )
            return purify_output(
                sign_receipt(self._refuse(
                    identity, action, intent_id, meter_reason)),
                context={"path": "meter.meter_intent", "signed": True,
                         "identity_as_presented": True},
            )

        # Unknown action: honest refusal, never a guess at a price.
        if action not in PRICES:
            return purify_output(
                sign_receipt(self._refuse(
                    identity, action, intent_id, REASON_UNKNOWN_ACTION)),
                context={"path": "meter.meter_intent", "signed": True,
                         "identity_as_presented": True},
            )

        price = PRICES[action]

        # --- free world: looking and rendering cost nothing -----------------
        if action in FREE_ACTIONS:
            receipt = self._grant(
                identity, action, intent_id,
                amount=0, balance_before=None, balance_after=None,
                note=(
                    "Free world: LOOK/RENDER costs nothing. "
                    "No wallet, no identity needed."
                ),
            )
            self._log(receipt)
            # PURIFY ON EXIT (free world): labeled + signed; identity may
            # be absent here — looking costs nothing and binds nothing.
            return purify_output(
                sign_receipt(receipt),
                context={"path": "meter.meter_intent", "signed": True,
                         "free_world": True},
            )

        # --- paid intent: metered actions ------------------------------------
        # (Identity was already purified on entry: the medium refused the
        # anonymous and the forged before this code ran. The checks below
        # remain as defense in depth.)
        if not identity:
            return purify_output(
                sign_receipt(self._refuse(
                    identity, action, intent_id, REASON_IDENTITY_REQUIRED)),
                context={"path": "meter.meter_intent", "signed": True,
                         "identity_as_presented": True},
            )
        if not isinstance(identity, str) or not identity.startswith(IDENTITY_PREFIX):
            return purify_output(
                sign_receipt(self._refuse(
                    identity, action, intent_id, REASON_NOT_TESTNET_IDENTITY)),
                context={"path": "meter.meter_intent", "signed": True,
                         "identity_as_presented": True},
            )

        # Idempotency: the same intent replays its receipt; it is never
        # charged twice. Refusals are not cached — a retry re-evaluates.
        intent_key = self._intent_key(identity, intent_id)
        if intent_key in self._ledger["intents"]:
            # Idempotent replay: the ORIGINAL signed receipt, re-purified
            # on exit like any other output.
            return purify_output(
                sign_receipt(self._ledger["intents"][intent_key]),
                context={"path": "meter.meter_intent", "signed": True},
            )

        before = self._ledger["balances"].get(identity, 0)
        if before < price:
            # Honest refusal: the intent is unserved, the world is not
            # blocked, the balance is untouched.
            return purify_output(
                sign_receipt(self._refuse(
                    identity, action, intent_id, REASON_INSUFFICIENT_KEYS,
                    amount=price, balance_before=before,
                    balance_after=before)),
                context={"path": "meter.meter_intent", "signed": True},
            )

        after = before - price
        receipt = self._grant(
            identity, action, intent_id,
            amount=price, balance_before=before, balance_after=after,
            note=(
                f"Paid intent: {action} cost {price} {UNIT}. "
                "TEST units only — not dollars, not eFuse."
            ),
        )
        # RIGHTS, then WRITE: the debit flows through the single commit
        # path. The meter vouches for this intent — it just verified the
        # identity format, the idempotency key, and affordability above;
        # check_rights authorizes the LEDGER_DEBIT, dclm_commit performs
        # the one mutation and emits the signed receipt. The thin client
        # has no path here — this is DCLM-internal.
        verdict = check_rights(
            identity, "LEDGER_DEBIT",
            {"internal": "dclm.meter", "schema": SCHEMA,
             "intent": action, "meter_approved": True},
        )
        # PURIFY IN FLIGHT: the debit transition is checked — kind
        # whitelisted, receipt planned and labeled, the balance change
        # declared — before writes.py commits.
        purify_transition(
            {"balance": before}, {"balance": after},
            "LEDGER_DEBIT",
            context={"receipt": receipt, "identity": identity,
                     "path": "meter.meter_intent"},
        )
        envelope = dclm_commit(
            "LEDGER_DEBIT", receipt, verdict,
            _MeterCommitStore(
                self, identity=identity, receipt=receipt, op="debit",
                balance_before=before, balance_after=after,
                intent_key=intent_key,
            ),
        )
        # PURIFY ON EXIT: labeled, signed, identity-bound.
        return purify_output(
            envelope, context={"path": "meter.meter_intent",
                               "signed": True},
        )

    # -- receipt construction ----------------------------------------------

    def _grant(self, identity, action, intent_id, amount,
               balance_before, balance_after, note):
        receipt = {
            "schema": SCHEMA,
            "type": "RECEIPT",
            "identity": identity,
            "action": action,
            "amount": amount,
            "unit": UNIT,
            "testnet": True,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "intent_id": intent_id,
            "outcome": OUTCOME_GRANTED,
            "reason": None,
            "receipt_id": self._receipt_id(identity, action, intent_id),
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # derived in-process from ledger + prices
            "note": note,
        }
        self._assert_receipt_labeled(receipt)
        return receipt

    def _refuse(self, identity, action, intent_id, reason,
                amount=None, balance_before=None, balance_after=None):
        if reason not in REFUSAL_REASONS:
            raise MeterError(f"unknown refusal reason: {reason!r}")
        receipt = {
            "schema": SCHEMA,
            "type": "REFUSAL",
            "identity": identity,
            "action": action,
            "amount": amount,
            "unit": UNIT,
            "testnet": True,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "intent_id": intent_id,
            "outcome": OUTCOME_REFUSED,
            "reason": reason,
            "receipt_id": self._receipt_id(identity, action, intent_id),
            "issued_at": self._utc_now(),
            "provenance": "DERIVED",  # the meter derived the refusal from rules
            "note": (
                "Refusal, not a block: the world stays free; "
                "only this intent is unserved."
            ),
        }
        self._assert_receipt_labeled(receipt)
        self._log(receipt)
        return receipt


# ---------------------------------------------------------------------------
# Emission eligibility — derivative merit regeneration (David's law)
#
#   Derivative merit regeneration, NOT token cascade: downstream rings do
#   NOT receive tokens from upstream; each ring earns its own merit from
#   its own verified receipts. The derivative relationship enables the
#   work; the work earns the merit.
#
#   The unbroken chain: verified work -> receipt -> merit (origin-bound;
#   ownership transferable via receipted merit_transfer, standing never
#   moves) -> emission (gated on STANDING, never on owned balance) ->
#   token (Unity-bound; Unity itself never transfers) -> the earner's
#   own merit cycle continues. Nothing moves without an ID, a receipt,
#   and a label. Standing is never for sale — and cannot be bought:
#   transfers move economic value only.
#
# This section is the GATE. emission_eligibility(identity) answers one
# question — "may this identity emit against its own verified merit?" —
# and performs NO writes: no ledger mutation, no dclm_commit, no signing.
# The signed emission receipt belongs to the emission path itself
# (dclm/tokenize.py — Phase 2 wires it through this gate); the gate is
# the label the emission cites, read-only like balance().
#
# The merit ledger lives with the tokenization worker (dclm/tokenize.py):
# the engine's slice registry carries, per slice, an IMMUTABLE
# origin_earner_id and a mutable owner_unity_id. standing(identity) sums
# by ORIGIN — the identity's own earned merit, which transfers can never
# move. The gate reads standing(), NEVER the owned balance: bought Merit
# must not gate emission. tokenize() refuses anything not VERIFIED before
# _accrue_merit runs. The MeritReader protocol below is the interface
# meter.py reads it through — bound explicitly, never assumed. No reader
# bound (PENDING), reader unreachable, or unknown merit -> emission stays
# CLOSED. UNKNOWN never PASS.
# ---------------------------------------------------------------------------

class MeritReader:
    """Protocol: read an identity's OWN earned merit (STANDING).

    Implementations expose:
        verified_merit(identity) -> float | None

    Returns the identity's own EARNED merit — origin-based standing, a
    float >= 0 — or None when the ledger is unreachable or the merit is
    unknown. The gate treats None as UNKNOWN and keeps emission closed.
    "Own" means ORIGIN-based: Merit the identity earned from its own
    VERIFIED work receipts. Merit merely OWNED (bought, gifted — owned
    balance without origin) MUST NOT be reported here: bought merit
    never gates emission. Implementations MUST answer for exactly the
    identity asked — never another identity's standing, never a sum,
    never a cascade. See TokenizeMeritReader.
    """

    def verified_merit(self, identity):
        raise NotImplementedError


class TokenizeMeritReader(MeritReader):
    """Read-only adapter over the tokenization worker's merit ledger.

    Binds a dclm/tokenize.py Tokenizer. Its slice registry is the landed
    merit store; this adapter only READS it:
    verified_merit(identity) returns that identity's STANDING — the sum
    of merit_value from its own VERIFIED work receipts, computed SOLELY
    from origin_earner_id (Tokenizer.standing). It NEVER reads the owned
    balance: Merit bought or gifted to this identity contributes ZERO
    here, so no code path can gate emission on another identity's earned
    merit. Standing cannot be bought — structurally, at the gate.
    """

    def __init__(self, tokenizer):
        # Lazy import: meter.py stays importable and testable without the
        # tokenization worker present. If tokenize.py is absent, there is
        # no reader to bind and emission stays closed (PENDING).
        from tokenize import Tokenizer
        if not isinstance(tokenizer, Tokenizer):
            raise MeterError(
                "TokenizeMeritReader needs a dclm/tokenize.py Tokenizer; "
                f"got {type(tokenizer).__name__!r}"
            )
        self._tokenizer = tokenizer

    def verified_merit(self, identity):
        # THE load-bearing wire: standing(), never the owned balance.
        # If this read the balance, bought Merit would gate emission and
        # standing would be buyable in effect. It doesn't.
        score = self._tokenizer.standing(identity)
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return None  # malformed score: UNKNOWN, never PASS
        return float(score)


_MERIT_READER = None  # module-global binding; None = PENDING, closed


def bind_merit_reader(reader):
    """Bind the merit-ledger reader that emission_eligibility consults.

    Until this is called with a real reader, the gate answers PENDING
    and emission stays closed — the interface is defined, the wiring is
    not assumed. Pass a TokenizeMeritReader (or any MeritReader).
    """
    global _MERIT_READER
    if not hasattr(reader, "verified_merit") or \
            not callable(getattr(reader, "verified_merit")):
        raise MeterError(
            "merit reader must expose verified_merit(identity); "
            f"got {type(reader).__name__!r}"
        )
    _MERIT_READER = reader
    return reader


def unbind_merit_reader():
    """Release the bound reader (tests / honest shutdown). Emission
    returns to PENDING-closed until a reader is bound again."""
    global _MERIT_READER
    _MERIT_READER = None


def _emission_verdict(identity, eligible, reason, merit_value):
    return {
        "schema": EMISSION_ELIGIBILITY_SCHEMA,
        "identity": identity,
        "eligible": eligible,
        "reason": reason,
        "merit_value": merit_value,
        "testnet": True,
        # DERIVED in-process from the merit read; the underlying accruals
        # are VERIFIED-gated at tokenize time (tokenize() refuses anything
        # not VERIFIED before _accrue_merit runs).
        "provenance": "DERIVED",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Derivative merit regeneration: emission is against the "
            "earner's OWN verified-receipt merit only. No token cascade — "
            "no identity emits on another identity's receipts."
        ),
    }


def emission_eligibility(identity, merit_reader=None):
    """Gate: may this identity emit against its own verified merit?

    Pure read — no writes, no ledger mutation. Returns a labeled verdict
    dict (JSON-serializable): schema, identity, eligible, reason,
    merit_value, provenance, issued_at.

    eligible is True ONLY when ALL of the following hold:
      * identity is a bound "unity:testnet:..." identity (structural —
        anything else is refused, honestly labeled, no exception);
      * a merit reader is bound (explicit argument wins; otherwise the
        module-global binding). None bound -> MERIT_LEDGER_PENDING and
        emission stays CLOSED: the interface is defined, the wiring is
        pending, and nothing emits on unknown merit;
      * the reader reports the identity's OWN verified-receipt merit as a
        positive number. None -> MERIT_UNKNOWN (UNKNOWN never PASS).
        Non-positive -> NO_VERIFIED_MERIT. A reader failure ->
        MERIT_LEDGER_UNREACHABLE. All closed, all honestly labeled.

    The reader is asked about exactly the identity passed in — never
    another identity, never a sum. See the no-cascade introspection test
    (test_merit_regen.py): this is asserted structurally, not just
    behaviorally.
    """
    if not isinstance(identity, str) or not identity.startswith(IDENTITY_PREFIX):
        return _emission_verdict(
            identity, False, REASON_NOT_TESTNET_IDENTITY, None)

    reader = merit_reader if merit_reader is not None else _MERIT_READER
    if reader is None:
        return _emission_verdict(
            identity, False, REASON_MERIT_LEDGER_PENDING, None)

    try:
        merit = reader.verified_merit(identity)
    except Exception:
        # A failing reader is not a pass: closed, honestly labeled.
        return _emission_verdict(
            identity, False, REASON_MERIT_LEDGER_UNREACHABLE, None)

    if merit is None:
        return _emission_verdict(identity, False, REASON_MERIT_UNKNOWN, None)
    if isinstance(merit, bool) or not isinstance(merit, (int, float)):
        return _emission_verdict(identity, False, REASON_MERIT_UNKNOWN, None)
    merit = float(merit)
    if merit <= 0:
        return _emission_verdict(
            identity, False, REASON_NO_VERIFIED_MERIT, merit)
    return _emission_verdict(identity, True, None, merit)


# ---------------------------------------------------------------------------
# signing (Ed25519, testnet keys only — same material as compute.py)
# ---------------------------------------------------------------------------
def _canonical_bytes(receipt):
    return json.dumps(
        receipt, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_receipt(receipt, privkey_path=TEST_PRIV_KEY, key_id=KEY_ID):
    """Ed25519-sign the canonical JSON of a receipt.

    Returns an envelope: {"receipt", "canonical_sha256", "signature",
    "algorithm", "key_id", "provenance"}. Refusals are signed too — a
    signed refusal is a verifiable honest statement, not a silent drop.
    """
    canonical = _canonical_bytes(receipt)
    proc = subprocess.run(
        ["node", ED25519_HELPER, "sign", privkey_path],
        input=canonical,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"receipt signing failed: {proc.stderr.decode()!r}")
    signature = proc.stdout.decode().strip()
    return {
        "receipt": receipt,
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "signature": signature,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "provenance": "VERIFIED",  # the signature is verifiable against the key
    }


def verify_receipt(envelope, pubkey_path=TEST_PUB_KEY):
    """Verify a signed receipt envelope. Returns True/False — never raises."""
    try:
        canonical = _canonical_bytes(envelope["receipt"])
        sig = envelope.get("signature", "")
        proc = subprocess.run(
            ["node", ED25519_HELPER, "verify", pubkey_path, sig],
            input=canonical,
            capture_output=True,
            timeout=30,
        )
        return proc.returncode == 0
    except Exception:
        return False

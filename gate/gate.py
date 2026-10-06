#!/usr/bin/env python3
"""
Unity ID Gate — server-side intent binding state machine (TESTNET).

THE REFRAME (2026-10-06, David's direction): the world opens FREE.
Grok's gate-dialog pattern is DEAD — killed by David. There is no entry
gate, no dialog blocking the view, no button the browser must dismiss
for anyone to see the world. Looking costs nothing and needs no binding.

What this gate guards now is INTENT, not entry: the Unity ID binding
authorizes PAID INTENT — search and compute draw keys from the Unity
wallet. Wanting costs keys; seeing costs nothing.

The structural fix for Grok's dead-button class of bug is preserved and
deepened: the client NEVER decides anything load-bearing. All state
transitions (UNBOUND -> BINDING -> BOUND) are computed here,
server-side, persisted to a server-owned state file, and only ever READ
by the client as an opaque status. And now there is nothing for a dead
button to block in the first place — the world renders with no gate in
front of it at all.

States
------
    UNBOUND  ->  BINDING  ->  BOUND

- request_bind(identity)  : UNBOUND -> BINDING   (starts the binding ceremony)
- confirm_bind(identity, proof): BINDING -> BOUND (completes the ceremony,
    only after the binding proof verifies)
- status(identity)        : read the server-side truth
- emit_gate_envelope(identity): BOUND -> GATE envelope authorizing
    METERED INTENT (search/compute) for the bound identity against the
    Unity wallet, per the DCLM metering ledger. The envelope authorizes
    wanting, never seeing — world viewing is free and unguarded.
- authorize_intent(identity, action): the primary intent path. FREE
    actions (view/look/render/explore) authorize with no identity and no
    binding. METERED actions (search/compute) require BOUND plus a
    wallet ledger reporting SUFFICIENT keys; otherwise an honest
    refusal with a reason (UNBOUND / WALLET_LEDGER_PENDING /
    KEYS_UNKNOWN / INSUFFICIENT_KEYS).
- world_view_pass()       : the code-level assertion that the gate NEVER
    gates world viewing. No identity, no binding, no state, no log.

The world-view guarantee (structural, not a warning)
----------------------------------------------------
No function in this module can revoke or gate world-view state: there is
deliberately NO view-gating function here. WORLD_VIEWING_REQUIRES_BINDING
is False, world_view_pass() takes no identity, and free actions short-
circuit in authorize_intent() before any identity check. If you are
tempted to add view-gating here, do not: David killed the gate-dialog.

Identity rule (structural, not a warning)
-----------------------------------------
Only identities beginning with "unity:testnet:" are accepted. Anything
else is REFUSED at every entry point — request_bind, confirm_bind,
status, emit_gate_envelope, authorize_intent (metered actions).
Testnet only. No mainnet identity can ever reach the gate.

Idempotency
-----------
Re-binding an already-BOUND identity is a no-op: the existing receipt is
returned, no new receipt is minted, no mutation is logged. Receipt IDs are
deterministic per (identity, transition), so duplicates collapse by
construction.

WebAuthn / biometric ceremony
-----------------------------
The binding ceremony is defined in CEREMONY.md (SPEC). The concept: "your
face or your finger opens it, the page never sees either one, the phone
does" — a WebAuthn platform authenticator on the user's device produces
the assertion; the server verifies it. This sandbox cannot perform real
WebAuthn, so:

  - The verification slot in confirm_bind() is clearly marked below.
  - The default verifier returns UNKNOWN ("not wired in this sandbox").
  - UNKNOWN is never PASS: confirm_bind REFUSES to transition on UNKNOWN.
  - A caller may inject a verifier (e.g. tests inject a clearly-labeled
    TEST STUB simulating the phone ceremony). The stub is a simulation,
    never claimed as real WebAuthn.

Intent flow
-----------
Once BOUND, the gate emits a GATE envelope for that identity. That envelope
is the authorization for metered intent (search/compute) to draw keys from
the bound identity's Unity wallet, per the DCLM metering ledger. No
envelope exists for any identity that is not BOUND. The world itself —
rendering, looking, exploring — needs neither the binding nor the envelope.

Wallet ledger integration (WIRED — honest, not faked)
-------------------------------------------------------
The DCLM metering worker (separate) owns the wallet ledger and prices.
authorize_intent() consults the bound-identity state here and the wallet
balance there, via resolve_wallet_ledger(): a read-only adapter over the
meter's own Wallet class and PRICES in ~/workspace/unity-world/dclm/meter.py
(landed 2026-10-06 ~06:56 UTC, after this gate's first build). The adapter
reads the live balance and compares it against the meter's own price list —
prices are never hardcoded in this gate. If the module is ever missing or
broken, the integration point degrades to PENDING: the gate cannot
fabricate a key balance, and UNKNOWN is never PASS, so metered intent with
no usable ledger is honestly refused (WALLET_LEDGER_PENDING).

Receipts
--------
Every state mutation is appended to receipts.jsonl with the sha256 of the
state file BEFORE and AFTER the mutation. See RECEIPTS.md. Read-only
calls (status(), emit_gate_envelope(), authorize_intent(),
world_view_pass()) perform NO mutation and log NO receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.gate.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"

# The test Unity identity, derived from the fresh test key at
# ~/workspace/unity-world/keys/unity-world-test.pub:
#   "unity:testnet:" + sha256(pubkey_bytes).hexdigest()[:16]
THE_TEST_IDENTITY = "unity:testnet:1e26f0d9e8c46818"

DEFAULT_STATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "state"
)
STATE_FILENAME = "gate-state.json"
RECEIPTS_FILENAME = "receipts.jsonl"

UNBOUND = "UNBOUND"
BINDING = "BINDING"
BOUND = "BOUND"

# ---------------------------------------------------------------------------
# The reframe (2026-10-06, David's direction): the world opens FREE.
# ---------------------------------------------------------------------------

# Structural guarantee: no function in this module can revoke or gate
# world-view state, because viewing is not gated at all. Grep-able and
# importable; asserted by test_world_needs_no_binding.
WORLD_VIEWING_REQUIRES_BINDING = False

# Actions that cost nothing and need no identity, no binding, no wallet.
FREE_ACTIONS = frozenset({"view", "look", "render", "explore"})

# Actions that draw keys from the Unity wallet and require a BOUND identity.
METERED_ACTIONS = frozenset({"search", "compute"})

# Wallet ledger integration — WIRED to the DCLM metering worker's ledger.
# The metering worker owns the ledger and prices; this gate only consults.
METER_MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dclm",
    "meter.py",
)
WALLET_LEDGER_STATUS = (
    "WIRED" if os.path.exists(METER_MODULE_PATH) else "PENDING"
)

# ---------------------------------------------------------------------------
# Errors — failures are honest, loud, and structural
# ---------------------------------------------------------------------------


class GateError(Exception):
    """Base class for all gate failures."""


class GateRefused(GateError):
    """Structural refusal: the identity is not a testnet Unity identity."""


class GateUnknown(GateError):
    """Refusal because verification is UNKNOWN. UNKNOWN is never PASS."""


class IntentRefused(GateError):
    """Honest refusal to authorize metered intent. Carries .reason.

    Reasons: "UNBOUND" | "WALLET_LEDGER_PENDING" | "KEYS_UNKNOWN" |
    "INSUFFICIENT_KEYS". The refusal is always about wanting (paid
    intent), never about seeing (the world is free — viewing cannot be
    refused by this gate).
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"intent refused (reason={reason}): {detail}")


# ---------------------------------------------------------------------------
# Binding-proof verification (WebAuthn slot)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of binding-proof verification.

    status: "VERIFIED" | "UNKNOWN" | "FAILED"
    detail: human-readable explanation (no secrets, never the raw assertion).
    """

    status: str
    detail: str


def verify_webauthn_assertion(identity: str, proof: dict) -> VerificationResult:
    """Default verifier: the WebAuthn assertion path.

    SPEC / NOT WIRED. This sandbox cannot perform real WebAuthn (no
    platform authenticator, no ceremony with a real device), so this
    returns UNKNOWN — never VERIFIED, never FAILED-as-guess.

    Where the real verification would happen (when wired):
      1. `proof` carries the WebAuthn assertion from the device's platform
         authenticator (face/fingerprint), issued against THIS gate's
         challenge for THIS identity.
      2. The server checks the challenge freshness, the origin/RP ID,
         the signature over the authenticator data, and the credential
         binding to `identity`.
      3. Only a fully valid assertion returns VERIFIED.

    The page never sees the biometric. The phone does. The server sees
    only the assertion and verifies it here.

    A caller may inject its own verifier into confirm_bind() (production
    wiring, or a clearly-labeled TEST STUB in tests). The default is
    UNKNOWN, and UNKNOWN is never PASS.
    """
    _ = (identity, proof)  # unused while unwired — the slot, not the check
    return VerificationResult(
        status="UNKNOWN",
        detail=(
            "WebAuthn assertion path not wired in this sandbox: no platform "
            "authenticator ceremony has been performed, so the proof cannot "
            "be verified. Refusing to treat UNKNOWN as PASS."
        ),
    )


# ---------------------------------------------------------------------------
# Wallet ledger integration point (WIRED — honest, not faked)
#
# Resolves to the DCLM metering worker's dclm/meter.py Wallet/PRICES
# surface (landed 2026-10-06). If the module is ever missing or broken,
# resolve_wallet_ledger() returns None and authorize_intent() refuses
# with WALLET_LEDGER_PENDING — the integration degrades to PENDING
# honestly; the gate never fabricates a key balance.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerView:
    """Normalized view of the Unity wallet for one identity, as reported
    by the DCLM metering worker's ledger.

    status: "SUFFICIENT" | "INSUFFICIENT" | "UNKNOWN"
    keys_available: the ledger's reported key balance (its claim, not ours)
    detail: human-readable explanation from the ledger (no secrets).
    """

    status: str
    keys_available: int
    detail: str


def resolve_wallet_ledger():
    """Locate the DCLM metering worker's wallet ledger.

    Returns a `check_keys(identity, action)` adapter callable, or None.

    The adapter reads the LIVE ledger (the meter's own Wallet class, same
    state dir the metering worker uses) and compares the balance against
    the meter's own PRICES — prices stay owned by the metering worker;
    this gate never hardcodes one. The read is strictly read-only
    (Wallet.balance); the meter remains authoritative at intent time
    (its own meter_intent deducts, with idempotency per intent_id).

    None means the integration is not usable (module missing, broken, or
    no Wallet/PRICES surface) — and the gate must NOT fabricate a key
    balance. authorize_intent() treats None as an honest
    WALLET_LEDGER_PENDING refusal. UNKNOWN is never PASS: no ledger,
    no authorization.

    Expected surface of dclm/meter.py (the metering worker's property):
        class Wallet: balance(identity) -> int; meter_intent(...); ...
        PRICES: {"SEARCH": 1, "COMPUTE": 5, ...}  (test-keys, testnet)
    """
    if not os.path.exists(METER_MODULE_PATH):
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "unity_dclm_meter", METER_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None  # a broken ledger is not a working ledger; never fake it

    wallet_cls = getattr(module, "Wallet", None)
    prices = getattr(module, "PRICES", None)
    if not callable(wallet_cls) or not isinstance(prices, dict):
        return None

    def check_keys(identity, action):
        """Read-only balance check against the meter's live ledger/prices."""
        try:
            wallet = wallet_cls()
            balance = wallet.balance(identity)
        except Exception as exc:
            return {
                "status": "UNKNOWN",
                "keys_available": 0,
                "detail": f"ledger read failed: {exc}",
            }
        try:
            balance = int(balance or 0)
        except (TypeError, ValueError):
            return {
                "status": "UNKNOWN",
                "keys_available": 0,
                "detail": f"ledger returned unparseable balance: {balance!r}",
            }
        price = prices.get(str(action).upper())
        if price is None:
            return {
                "status": "UNKNOWN",
                "keys_available": balance,
                "detail": f"no meter price for action {action!r}",
            }
        if balance >= int(price):
            return {
                "status": "SUFFICIENT",
                "keys_available": balance,
                "detail": (
                    f"{balance} test-keys >= price {int(price)} "
                    f"for {str(action).upper()} (per meter PRICES)"
                ),
            }
        return {
            "status": "INSUFFICIENT",
            "keys_available": balance,
            "detail": (
                f"{balance} test-keys < price {int(price)} "
                f"for {str(action).upper()} (per meter PRICES)"
            ),
        }

    return check_keys


def _normalize_ledger_view(raw) -> LedgerView:
    """Coerce whatever the ledger returns into a LedgerView.

    Anything unrecognizable becomes UNKNOWN — UNKNOWN is never PASS, so a
    ledger that cannot speak clearly cannot authorize intent.
    """
    try:
        if isinstance(raw, LedgerView):
            return raw
        if isinstance(raw, dict):
            status = str(raw.get("status", "UNKNOWN")).upper()
            if status not in ("SUFFICIENT", "INSUFFICIENT", "UNKNOWN"):
                status = "UNKNOWN"
            keys = raw.get("keys_available", 0)
            keys_available = int(keys) if isinstance(keys, (int, float)) else 0
            detail = str(raw.get("detail", ""))
            return LedgerView(
                status=status, keys_available=keys_available, detail=detail
            )
        return LedgerView(
            status="UNKNOWN",
            keys_available=0,
            detail=f"unrecognized ledger response type: {type(raw).__name__}",
        )
    except Exception as exc:  # a ledger that cannot be parsed is UNKNOWN
        return LedgerView(
            status="UNKNOWN",
            keys_available=0,
            detail=f"ledger response unparseable: {exc}",
        )


def world_view_pass() -> dict:
    """The code-level assertion that the gate NEVER gates world viewing.

    Takes no identity, requires no binding, consults no state, mutates
    nothing, logs nothing. Its existence — and the deliberate absence of
    any view-gating function in this module — is the structural
    guarantee that the reframe is real: the world opens free; the gate
    guards paid intent (authorize_intent) only.

    THE REFRAME (2026-10-06): David killed the gate-dialog. The world
    does not ask permission to be seen; only wanting costs.
    """
    return {
        "schema": SCHEMA,
        "type": "VIEW_PASS",
        "viewing": "free",
        "binding_required": False,
        "identity_required": False,
        "reason": (
            "THE REFRAME (2026-10-06): David killed the gate-dialog. "
            "The world does not ask permission to be seen."
        ),
    }


# ---------------------------------------------------------------------------
# Gate state machine
# ---------------------------------------------------------------------------


def _sha256_file(path: str) -> str:
    """sha256 of a file's bytes; the sha256 of a missing file is the
    sha256 of the empty canonical state (stable, comparable)."""
    if not os.path.exists(path):
        return hashlib.sha256(b"{}").hexdigest()
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_id(transition: str, identity: str) -> str:
    """Deterministic receipt ID per (transition, identity).

    Idempotency by construction: the same transition for the same identity
    always yields the same receipt ID, so re-binding can never mint a
    duplicate.
    """
    return hashlib.sha256(
        f"{SCHEMA}|{transition}|{identity}".encode("utf-8")
    ).hexdigest()


class UnityGate:
    """Server-side Unity ID gate. All transitions computed here."""

    def __init__(self, state_dir: str | None = None) -> None:
        self.state_dir = state_dir or os.environ.get(
            "UNITY_GATE_STATE_DIR", DEFAULT_STATE_DIR
        )
        os.makedirs(self.state_dir, exist_ok=True)
        self.state_path = os.path.join(self.state_dir, STATE_FILENAME)
        self.receipts_path = os.path.join(self.state_dir, RECEIPTS_FILENAME)
        self._state = self._load()

    # -- persistence ------------------------------------------------------

    def _load(self) -> dict:
        if not os.path.exists(self.state_path):
            return {"schema": SCHEMA, "bindings": {}}
        with open(self.state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") != SCHEMA:
            raise GateError(
                f"state schema mismatch: expected {SCHEMA}, "
                f"found {data.get('schema')!r} — refusing to read foreign state"
            )
        return data

    def _save(self) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".gate-state-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, self.state_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _record_mutation(
        self,
        identity: str,
        transition: str,
        receipt_id: str,
        prev_hash: str,
        note: str = "",
    ) -> dict:
        """Append one receipt to the mutation log, with before/after
        sha256 of the state file. Called AFTER the state file is saved,
        so new_hash is the hash of the just-written state."""
        new_hash = _sha256_file(self.state_path)
        entry = {
            "schema": SCHEMA,
            "ts": _utc_now(),
            "identity": identity,
            "transition": transition,
            "receipt_id": receipt_id,
            "prev_state_sha256": prev_hash,
            "new_state_sha256": new_hash,
            "note": note,
        }
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def _transition(
        self, identity: str, transition: str, new_state: str, note: str = ""
    ) -> dict:
        """Perform one state mutation: hash before, mutate, save, log."""
        prev_hash = _sha256_file(self.state_path)
        receipt_id = _receipt_id(transition, identity)
        binding = self._state["bindings"].setdefault(identity, {"history": []})
        binding["state"] = new_state
        binding["receipt_id"] = receipt_id
        binding["history"].append(
            {"ts": _utc_now(), "transition": transition, "receipt_id": receipt_id}
        )
        self._save()
        self._record_mutation(identity, transition, receipt_id, prev_hash, note)
        return self._receipt(identity, transition, receipt_id)

    # -- guards -----------------------------------------------------------
    #
    # DELIBERATELY ABSENT: there is NO world-view guard in this module.
    # Viewing the world requires no identity, no binding, no keys, and no
    # function here may revoke or condition it — the reframe (2026-10-06)
    # killed the gate-dialog. The only gates are below: testnet identity
    # (structural) and metered intent (authorize_intent).

    @staticmethod
    def _require_testnet(identity: str) -> None:
        """Structural refusal: non-testnet identities never enter the gate."""
        if not isinstance(identity, str) or not identity.startswith(IDENTITY_PREFIX):
            raise GateRefused(
                "structural refusal: identity must start with "
                f"{IDENTITY_PREFIX!r}; got {identity!r}. Testnet only."
            )

    # -- public API -------------------------------------------------------

    def request_bind(self, identity: str) -> dict:
        """UNBOUND -> BINDING. Starts the binding ceremony.

        Binding authorizes METERED INTENT (search/compute) against the
        Unity wallet — not world entry, which is free and unguarded.

        Idempotent: if the identity is already BINDING or BOUND, the
        existing receipt is returned unchanged (no-op, no new mutation).
        """
        self._require_testnet(identity)
        binding = self._state["bindings"].get(identity)
        if binding is not None and binding["state"] in (BINDING, BOUND):
            # Idempotent re-bind: return the existing receipt, touch nothing.
            transition = (
                "BOUND" if binding["state"] == BOUND else "BINDING"
            )
            return self._receipt(identity, transition, binding["receipt_id"])
        return self._transition(
            identity,
            "BINDING",
            BINDING,
            note="binding ceremony started; awaiting WebAuthn proof",
        )

    def confirm_bind(
        self,
        identity: str,
        proof: dict,
        verifier=verify_webauthn_assertion,
    ) -> dict:
        """BINDING -> BOUND. Completes the ceremony.

        The `proof` is verified by `verifier` (default: the WebAuthn slot,
        which is UNKNOWN/unwired in this sandbox). Only a VERIFIED result
        completes the transition. UNKNOWN or FAILED refuses — honestly.

        Raises GateError if no binding is in progress for the identity
        (confirm without request fails; there is nothing to confirm).
        """
        self._require_testnet(identity)
        binding = self._state["bindings"].get(identity)
        if binding is None or binding.get("state") != BINDING:
            current = binding["state"] if binding else UNBOUND
            raise GateError(
                f"cannot confirm bind for {identity}: no binding in progress "
                f"(current state: {current}). Call request_bind() first."
            )

        # === WEBAUTHN ASSERTION VERIFICATION SLOT ===
        # When wired, the verifier checks the platform-authenticator
        # assertion from the user's device (face/finger; the page never
        # sees it) against this gate's challenge for this identity.
        # In this sandbox the default verifier returns UNKNOWN.
        result = verifier(identity, proof)

        if result.status != "VERIFIED":
            raise GateUnknown(
                f"binding proof for {identity} is {result.status}: "
                f"{result.detail} UNKNOWN is never PASS — refusing BOUND."
            )
        return self._transition(
            identity,
            "BOUND",
            BOUND,
            note="binding proof VERIFIED; identity bound to Unity gate",
        )

    def status(self, identity: str) -> str:
        """Read the server-side truth for an identity.

        Never bound on this server -> UNBOUND. The client cannot forge
        BOUND: there is no input path that sets state except the two
        transitions above.
        """
        self._require_testnet(identity)
        binding = self._state["bindings"].get(identity)
        if binding is None:
            return UNBOUND
        return binding["state"]

    def emit_gate_envelope(self, identity: str) -> dict:
        """BOUND -> GATE envelope authorizing METERED INTENT for this identity.

        THE REFRAME (2026-10-06): this envelope no longer authorizes world
        entry — the world opens free and NOTHING in this module gates it.
        It authorizes metered intent (search/compute) to draw keys from the
        bound identity's Unity wallet, per the DCLM metering ledger.
        Looking costs nothing; wanting costs keys.

        Raises unless the identity is BOUND in server-side state. A
        client-supplied receipt, token, or claim cannot forge this: the
        only thing consulted is the server's own binding record.
        Read-only: no mutation, no receipt logged.
        """
        self._require_testnet(identity)
        binding = self._state["bindings"].get(identity)
        if binding is None or binding.get("state") != BOUND:
            current = binding["state"] if binding else UNBOUND
            raise GateError(
                f"no intent authorization for {identity}: current state is "
                f"{current}, not BOUND. Bind the identity first — or just "
                "look: viewing the world needs no binding at all."
            )
        return {
            "schema": SCHEMA,
            "type": "GATE",
            "identity": identity,
            "state": BOUND,
            "receipt_id": binding["receipt_id"],
            "authorizes": (
                "metered intent (search/compute) for this identity may draw "
                "keys from the Unity wallet, per the DCLM metering ledger"
            ),
            "wallet_ledger": WALLET_LEDGER_STATUS,  # live: WIRED since dclm/meter.py landed (2026-10-06); PENDING only if the module is missing
            "viewing": (
                "free — this envelope gates intent only; it never gates "
                "the world"
            ),
            "issued_at": _utc_now(),
        }

    def authorize_intent(
        self, identity, action: str, ledger=None
    ) -> dict:
        """Authorize one intent against the bound identity and the wallet.

        THE REFRAME (2026-10-06): binding is for INTENT, not entry.
        FREE actions (view/look/render/explore) authorize with NO identity
        and NO binding — they short-circuit before any check, and they
        touch no state. METERED actions (search/compute) require a BOUND
        identity plus a wallet ledger reporting SUFFICIENT keys.

        Refusals are honest and carry .reason on IntentRefused:
          - "UNBOUND" — the identity is not BOUND (looking needs no
            binding; wanting does).
          - "WALLET_LEDGER_PENDING" — dclm/meter.py is not wired; the
            gate cannot fabricate a key balance and UNKNOWN is never
            PASS.
          - "KEYS_UNKNOWN" — the ledger could not speak clearly; a
            ledger that cannot speak cannot authorize.
          - "INSUFFICIENT_KEYS" — the wallet is empty for this intent.

        `ledger` may inject a check_keys(identity, action) callable (tests
        inject clearly-labeled stubs, exactly like the WebAuthn verifier
        slot); the default resolves the DCLM metering worker's dclm/meter.py
        Wallet/PRICES surface as a read-only adapter. Unknown actions are
        refused: the gate does not price what it does not know (pricing is
        the metering worker's property).

        Read-only: performs no mutation, logs no receipt.
        """
        # FREE actions short-circuit FIRST — before any identity check, so
        # even identity=None is fine. Seeing costs nothing.
        if action in FREE_ACTIONS:
            return {
                "schema": SCHEMA,
                "type": "INTENT_AUTHORIZATION",
                "identity": identity,
                "action": action,
                "authorized": True,
                "free": True,
                "requires_binding": False,
                "reason": "WORLD_IS_FREE",
                "issued_at": _utc_now(),
            }

        self._require_testnet(identity)

        if action not in METERED_ACTIONS:
            raise GateError(
                f"unknown intent {action!r}: this gate knows FREE "
                f"{sorted(FREE_ACTIONS)} and METERED {sorted(METERED_ACTIONS)}. "
                "The DCLM metering worker owns pricing for anything else."
            )

        binding = self._state["bindings"].get(identity)
        if binding is None or binding.get("state") != BOUND:
            current = binding["state"] if binding else UNBOUND
            raise IntentRefused(
                reason="UNBOUND",
                detail=(
                    f"{identity} is {current}, not BOUND. Paid intent needs "
                    "a bound Unity identity — looking costs nothing and "
                    "needs no binding; this refusal is about wanting, "
                    "never about seeing."
                ),
            )

        check_keys = ledger if ledger is not None else resolve_wallet_ledger()
        if check_keys is None:
            raise IntentRefused(
                reason="WALLET_LEDGER_PENDING",
                detail=(
                    f"the wallet ledger is not wired (expected at "
                    f"{METER_MODULE_PATH}; status {WALLET_LEDGER_STATUS}). "
                    "The gate cannot fabricate a key balance, and UNKNOWN "
                    "is never PASS — refusing until the DCLM metering "
                    "worker lands its ledger."
                ),
            )

        view = _normalize_ledger_view(check_keys(identity, action))
        if view.status != "SUFFICIENT":
            reason = (
                "INSUFFICIENT_KEYS"
                if view.status == "INSUFFICIENT"
                else "KEYS_UNKNOWN"
            )
            raise IntentRefused(
                reason=reason,
                detail=(
                    f"wallet ledger reports {view.status}: {view.detail} "
                    f"(keys_available={view.keys_available})."
                ),
            )

        return {
            "schema": SCHEMA,
            "type": "INTENT_AUTHORIZATION",
            "identity": identity,
            "action": action,
            "authorized": True,
            "metered": True,
            "keys_available": view.keys_available,
            "binding_receipt_id": binding["receipt_id"],
            "wallet_ledger": (
                "injected" if ledger is not None else "dclm/meter.py"
            ),
            "issued_at": _utc_now(),
        }

    def _receipt(self, identity: str, transition: str, receipt_id: str) -> dict:
        """The opaque receipt handed to the caller. It describes the
        transition; it does not grant intent. Authorization is the
        server's state."""
        binding = self._state["bindings"][identity]
        return {
            "schema": SCHEMA,
            "identity": identity,
            "transition": transition,
            "state": binding["state"],
            "receipt_id": receipt_id,
        }

    # -- testnet derivation helper ----------------------------------------

    @staticmethod
    def derive_identity(pubkey_path: str) -> str:
        """Derive the testnet Unity identity from a public key file.

        Convention (mirrors ~/workspace/testnet/README.md):
            "unity:testnet:" + sha256(pubkey_bytes).hexdigest()[:16]
        """
        with open(pubkey_path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        return f"{IDENTITY_PREFIX}{digest[:16]}"
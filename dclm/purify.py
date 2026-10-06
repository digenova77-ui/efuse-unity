"""
DCLM PURIFY — the purification MEDIUM. Identity + purify at every level,
in every way, everywhere, every time.

David's directive (2026-10-06): implement IDENTITY and PURIFY as the two
operations of the unity-world build, for the real world.

  1. IDENTITY — at every level. Every entity, every flow, every
     interaction is Unity-bound. No anonymous anything, anywhere, at any
     level of the stack.
  2. PURIFY — as the medium, not a checkpoint. Purity gates run
     continuously: every input purified on entry, every output purified
     on exit, every state transition purified in flight. Wherever you
     look, whenever you look, what you see is pure.

This module is the MEDIUM the transaction paths pass through — not a
checkpoint bolted on after the fact. The three operations:

    purify_input(payload, *, context)     — on entry
    purify_output(payload, *, context)    — on exit
    purify_transition(before, after, kind, *, context) — in flight

Fail-closed, always: any violation raises PurificationRefused with the
TRUE reason — never warns-and-continues, never degrades to a warning.

BOUNDARIES (binding):
  * purify.py CHECKS; writes.py COMMITS. This module never calls
    dclm_commit, never mutates state, never persists anything. The only
    I/O it performs is Ed25519 signature verification against the
    existing test keys (the same node helper + test key material the
    rest of DCLM uses). Testnet only.
  * UNKNOWN is never PASS. An UNKNOWN-labeled claim may travel through
    the medium — honestly labeled — but it is never upgraded to a pass,
    a grant, or a truth. Any payload that would present UNKNOWN as PASS
    is refused.
  * Pure functions where possible: the three operations are deterministic
    functions of their arguments (signature verification excepted).

PROVENANCE LABEL RECONCILIATION (honest, documented):
  The DCLM codebase (compute.py, PURITY.md) labels claims
  REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN.
  David's directive for this build names
  REAL / REPORTED / MODELED / DERIVED / UNKNOWN.
  The medium accepts the UNION:
      REAL, REPORTED, VERIFIED, MODELED, DERIVED, UNKNOWN
  VERIFIED = signature/seal-verified truth (the codebase's sealed and
  signed claims). REAL = measured real-world value (the directive's
  label). Nothing outside this set is a label. The union is accepted so
  the medium does not refuse the codebase's own legitimate receipts;
  the strictness lives in the never-upgrade rule, not in the spelling.

Testnet only. Identity format: "unity:testnet:..." — the same format
gate.py, meter.py, rights.py, and every DCLM component enforces.
"""

import dataclasses
import hashlib
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from compute import (  # noqa: E402 — the existing test key material
    ED25519_HELPER,
    TEST_PUB_KEY,
)
from rights import COMMIT_KINDS  # noqa: E402 — one whitelist of transitions

SCHEMA = "unity.purify.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"

# -- provenance: the reconciled union (see module docstring) ---------------
PROVENANCE_LABELS = frozenset(
    {"REAL", "REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"}
)

# -- reason codes: the true reason travels in the exception message --------
REASON_NO_IDENTITY = "NO_IDENTITY"
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_UNLABELED_CLAIM = "UNLABELED_CLAIM"
REASON_INVALID_PROVENANCE = "INVALID_PROVENANCE"
REASON_UNKNOWN_UPGRADE_REFUSED = "UNKNOWN_UPGRADE_REFUSED"
REASON_SIGNATURE_INVALID = "SIGNATURE_INVALID"
REASON_SIGNATURE_MISSING = "SIGNATURE_MISSING"
REASON_IDENTITY_UNBOUND_OUTPUT = "IDENTITY_UNBOUND_OUTPUT"
REASON_UNKNOWN_TRANSITION_KIND = "UNKNOWN_TRANSITION_KIND"
REASON_RECEIPT_NOT_PLANNED = "RECEIPT_NOT_PLANNED"
REASON_SILENT_MUTATION = "SILENT_MUTATION"
REASON_IDENTITY_DISCONTINUITY = "IDENTITY_DISCONTINUITY"
REASON_NON_SERIALIZABLE = "NON_SERIALIZABLE_TRANSITION"

# Values that assert a positive resolution. A claim carrying one of these
# alongside an UNKNOWN provenance is an upgrade attempt — refused.
_PASS_VALUES = frozenset(
    {"GRANTED", "DECIDED", "PASS", "LIVE", "SEALED", "VERIFIED"}
)

# Dict keys that carry identity values. origin_earner_id is included:
# origin is identity too, and it must be Unity-bound wherever it appears.
_IDENTITY_KEYS = (
    "identity",
    "unity_id",
    "source_identity",  # feed sources are Unity-bound identities too
    "sender",
    "from_id",
    "granter",
    "grantee",
    "to_id",
    "owner_unity_id",
    "origin_earner_id",
    "claimant",
)

# Dict keys that mark a dict as a truth-claim requiring a provenance
# label on the way out. Deliberately narrow: "outcome" is the claim
# marker every DCLM receipt uses; "verdict"/"status" sub-dicts (like a
# token body's rights block) ride inside an already-labeled claim.
_CLAIM_KEYS = ("outcome", "claim", "emission", "eligibility")


class PurificationRefused(Exception):
    """The medium refused: the payload is not pure. Raised fail-closed
    with the true reason — never warns-and-continues. Nothing was
    committed, nothing was signed, nothing moved when this is raised."""


# ---------------------------------------------------------------------------
# structural helpers — pure
# ---------------------------------------------------------------------------

def _is_testnet_identity(value):
    """A Unity-bound testnet identity: 'unity:testnet:<non-empty>'."""
    return (
        isinstance(value, str)
        and value.startswith(IDENTITY_PREFIX)
        and len(value) > len(IDENTITY_PREFIX)
    )


def _walk(obj, _seen=None):
    """Yield every dict found inside obj, recursively.

    Handles dicts, lists, tuples, sets, and dataclass instances (walked
    as their asdict() form). Cycle-safe. Pure.
    """
    if _seen is None:
        _seen = set()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            obj = dataclasses.asdict(obj)
        except Exception:
            return
    if isinstance(obj, dict):
        if id(obj) in _seen:
            return
        _seen.add(id(obj))
        yield obj
        for value in obj.values():
            yield from _walk(value, _seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for value in obj:
            yield from _walk(value, _seen)


def _identity_values(payload):
    """Every identity-valued field found in the payload (strings only;
    None is skipped — absence is checked separately). Pure."""
    found = []
    for d in _walk(payload):
        for key in _IDENTITY_KEYS:
            value = d.get(key)
            if isinstance(value, str):
                found.append((key, value))
        identities = d.get("identities")
        if isinstance(identities, (list, tuple)):
            for value in identities:
                if isinstance(value, str):
                    found.append(("identities[]", value))
    return found


def _primary_identity(payload):
    """The payload's own identity: 'identity', else 'unity_id', else the
    first entry of 'identities'. None when the payload names none."""
    if isinstance(payload, dict):
        for key in ("identity", "unity_id"):
            value = payload.get(key)
            if value is not None:
                return value
        identities = payload.get("identities")
        if isinstance(identities, (list, tuple)) and identities:
            return identities[0]
    return None


def _canonical_bytes(obj):
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _is_signed_envelope(d):
    """A signed-envelope-shaped dict: signature bytes beside the signed
    body ('receipt' — the DCLM envelope shape)."""
    return (
        isinstance(d, dict)
        and isinstance(d.get("signature"), str)
        and d.get("signature").strip() != ""
        and isinstance(d.get("receipt"), dict)
    )


def _verify_envelope(envelope, pubkey_path=TEST_PUB_KEY):
    """Verify one signed envelope against the test key. Returns
    True/False — never raises on bad data. The ONLY I/O in this module:
    signature verification against the existing test keys."""
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


def _signed_envelopes(payload):
    """Every signed-envelope-shaped dict inside the payload."""
    return [d for d in _walk(payload) if _is_signed_envelope(d)]


def _has_unknown_claim(payload):
    """True when any walked claim carries provenance UNKNOWN."""
    for d in _walk(payload):
        if d.get("provenance") == "UNKNOWN":
            return True
    return False


def _has_economic_content(payload):
    """True when the payload moves or prices value: a truthy amount, a
    changed balance pair, or a truthy price."""
    for d in _walk(payload):
        amount = d.get("amount")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool) \
                and amount:
            return True
        price = d.get("price")
        if isinstance(price, (int, float)) and not isinstance(price, bool) \
                and price:
            return True
        before = d.get("balance_before")
        after = d.get("balance_after")
        if (isinstance(before, (int, float)) and isinstance(after, (int, float))
                and before != after):
            return True
    return False


def _refuse(reason, detail, context=None):
    path = (context or {}).get("path", "purify")
    raise PurificationRefused(f"[{reason}] at {path}: {detail}")


# ---------------------------------------------------------------------------
# purify_input — on entry
# ---------------------------------------------------------------------------

def purify_input(payload, *, context=None):
    """Purify one input payload on entry. Fail-closed: any violation
    raises PurificationRefused with the true reason.

    Checks:
      1. IDENTITY — the payload names a Unity-bound identity
         ("unity:testnet:..."). Missing -> NO_IDENTITY; malformed ->
         NOT_TESTNET_IDENTITY. Every identity-valued field found anywhere
         in the payload must be testnet-valid: no mixed valid/forged
         identities. context {"free_world": True} (LOOK/RENDER reads)
         permits an ABSENT identity — a PRESENT one must still be valid.
      2. PROVENANCE — every claim carries a valid label. Any dict with a
         "provenance" key must name a label in the reconciled set;
         anything else -> INVALID_PROVENANCE. Every dict inside a
         "claims" list must carry a valid label -> UNLABELED_CLAIM.
      3. NEVER-UPGRADE — UNKNOWN input is handled per the caller's
         contract, never upgraded. payload["present_unknown_as_pass"]
         (or context asserting truth) alongside any UNKNOWN-labeled claim
         -> UNKNOWN_UPGRADE_REFUSED.
      4. SIGNATURES — where signatures are presented, they must verify.
         Any signed-envelope-shaped dict whose signature fails
         verification -> SIGNATURE_INVALID. Where the caller marks the
         input as requiring a signature (context/payload
         "requires_signature", or "claim_signed") and no verifiable
         envelope is present -> SIGNATURE_MISSING / SIGNATURE_INVALID.

    Returns the payload unchanged (purified = validated) for chaining.
    Pure except for signature verification against the test keys.
    """
    ctx = dict(context) if isinstance(context, dict) else {}
    path = ctx.get("path", "purify_input")
    ctx["path"] = path

    # --- 1. identity -----------------------------------------------------
    primary = _primary_identity(payload)
    if ctx.get("free_world"):
        # The free world (LOOK/RENDER): identity may be absent. A forged
        # identity is still refused — the free world is free, not fake.
        if primary is not None and not _is_testnet_identity(primary):
            _refuse(REASON_NOT_TESTNET_IDENTITY,
                    f"free-world input carries a non-testnet identity "
                    f"{primary!r}; the free world is free, not fake.",
                    ctx)
    else:
        if primary is None:
            _refuse(REASON_NO_IDENTITY,
                    "no Unity-bound identity on the input: no anonymous "
                    "input crosses the medium. Identity must be "
                    f"{IDENTITY_PREFIX!r} + suffix.",
                    ctx)
        if not _is_testnet_identity(primary):
            _refuse(REASON_NOT_TESTNET_IDENTITY,
                    f"identity {primary!r} is not Unity-bound testnet "
                    f"(must start with {IDENTITY_PREFIX!r}). Testnet only.",
                    ctx)
    # No mixed identities: every identity-valued field anywhere in the
    # payload must be testnet-valid. A payload that is half-bound is
    # not bound.
    for key, value in _identity_values(payload):
        if not _is_testnet_identity(value):
            _refuse(REASON_NOT_TESTNET_IDENTITY,
                    f"field {key!r} carries non-testnet identity {value!r} "
                    f"inside an otherwise bound payload.",
                    ctx)

    # --- 2. provenance ---------------------------------------------------
    for d in _walk(payload):
        if "provenance" in d and d.get("provenance") not in PROVENANCE_LABELS:
            _refuse(REASON_INVALID_PROVENANCE,
                    f"claim carries invalid provenance "
                    f"{d.get('provenance')!r}; valid labels are "
                    f"{sorted(PROVENANCE_LABELS)}.",
                    ctx)
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if isinstance(claims, (list, tuple)):
        for claim in claims:
            if not isinstance(claim, dict) \
                    or claim.get("provenance") not in PROVENANCE_LABELS:
                _refuse(REASON_UNLABELED_CLAIM,
                        f"a claim in 'claims' carries no valid provenance "
                        f"label: {claim!r}. Nothing crosses unlabeled.",
                        ctx)

    # --- 3. never-upgrade ------------------------------------------------
    asserts_truth = bool(
        ctx.get("assert_truth") or (
            isinstance(payload, dict) and payload.get("assert_as_truth")
        )
    )
    presents_unknown_as_pass = bool(
        isinstance(payload, dict) and payload.get("present_unknown_as_pass")
    )
    if presents_unknown_as_pass or (asserts_truth and _has_unknown_claim(payload)):
        _refuse(REASON_UNKNOWN_UPGRADE_REFUSED,
                "UNKNOWN is never PASS: the payload would present an "
                "UNKNOWN-labeled claim as a positive assertion. UNKNOWN "
                "travels labeled, or not at all.",
                ctx)

    # --- 4. signatures ---------------------------------------------------
    envelopes = _signed_envelopes(payload)
    for env in envelopes:
        if not _verify_envelope(env):
            _refuse(REASON_SIGNATURE_INVALID,
                    "a presented signature does not verify against the "
                    "test key: tampered or forged. Fail closed.",
                    ctx)
    requires_signature = bool(
        ctx.get("requires_signature") or (
            isinstance(payload, dict) and payload.get("requires_signature")
        )
    )
    claims_signed = bool(
        isinstance(payload, dict) and payload.get("claim_signed")
    )
    if requires_signature and not envelopes:
        _refuse(REASON_SIGNATURE_MISSING,
                "this input requires a signature and carries none.",
                ctx)
    if claims_signed and not envelopes:
        _refuse(REASON_SIGNATURE_INVALID,
                "payload asserts claim_signed but carries no verifiable "
                "signature.",
                ctx)

    return payload


# ---------------------------------------------------------------------------
# purify_output — on exit
# ---------------------------------------------------------------------------

def purify_output(payload, *, context=None):
    """Purify one output payload on exit. Fail-closed: any violation
    raises PurificationRefused with the true reason.

    Checks:
      1. LABELS — nothing leaves DCLM unlabeled. Every dict carrying a
         "provenance" key must name a valid label; every claim-shaped
         dict (carries "outcome"/"claim"/"emission"/"eligibility", or
         sits in a "claims" list) must carry a valid provenance label ->
         UNLABELED_CLAIM / INVALID_PROVENANCE.
      2. IDENTITY — nothing leaves identity-unbound. Every identity-valued
         field must be testnet-valid. When no identity is found at all:
         allowed only for the free world (context "free_world") with no
         economic content; anything economic without an identity ->
         IDENTITY_UNBOUND_OUTPUT. context "identity_as_presented" marks
         refusal outputs: the identity is the presented (audited, not
         trusted) one — format checks are skipped, labels still enforced.
      3. SIGNATURES — where the caller marks the output signed (context
         "signed"), at least one signed envelope must be present and every
         presented envelope must verify -> SIGNATURE_MISSING /
         SIGNATURE_INVALID.

    Returns the payload unchanged for chaining. Pure except for
    signature verification against the test keys.
    """
    ctx = dict(context) if isinstance(context, dict) else {}
    path = ctx.get("path", "purify_output")
    ctx["path"] = path

    # --- 1. labels: nothing leaves unlabeled ------------------------------
    for d in _walk(payload):
        if "provenance" in d and d.get("provenance") not in PROVENANCE_LABELS:
            _refuse(REASON_INVALID_PROVENANCE,
                    f"output claim carries invalid provenance "
                    f"{d.get('provenance')!r}.",
                    ctx)
        is_claim = any(k in d for k in _CLAIM_KEYS)
        if is_claim and "provenance" not in d:
            _refuse(REASON_UNLABELED_CLAIM,
                    f"output claim carries no provenance label: "
                    f"{str(d)[:160]!r}. Nothing leaves DCLM unlabeled.",
                    ctx)
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if isinstance(claims, (list, tuple)):
        for claim in claims:
            if not isinstance(claim, dict) \
                    or claim.get("provenance") not in PROVENANCE_LABELS:
                _refuse(REASON_UNLABELED_CLAIM,
                        f"a claim in output 'claims' is unlabeled: "
                        f"{claim!r}.",
                        ctx)

    # --- 2. identity: nothing leaves identity-unbound ---------------------
    as_presented = bool(ctx.get("identity_as_presented"))
    ids = _identity_values(payload)
    if not as_presented:
        for key, value in ids:
            if not _is_testnet_identity(value):
                _refuse(REASON_NOT_TESTNET_IDENTITY,
                        f"output field {key!r} carries non-testnet identity "
                        f"{value!r}: DCLM does not emit forged identity.",
                        ctx)
        require_identity = ctx.get("require_identity", True)
        if require_identity and not ids:
            economic = _has_economic_content(payload)
            free = bool(ctx.get("free_world")) and not economic
            if not free:
                _refuse(REASON_IDENTITY_UNBOUND_OUTPUT,
                        "economic output names no Unity-bound identity: "
                        "nothing of value leaves DCLM identity-unbound.",
                        ctx)

    # --- 3. signatures -----------------------------------------------------
    envelopes = _signed_envelopes(payload)
    if ctx.get("signed"):
        if not envelopes:
            _refuse(REASON_SIGNATURE_MISSING,
                    "this output must be signed and carries no signature.",
                    ctx)
        for env in envelopes:
            if not _verify_envelope(env):
                _refuse(REASON_SIGNATURE_INVALID,
                        "an output signature does not verify: the output "
                        "is not pure.",
                        ctx)
    else:
        # Signatures presented voluntarily are still verified: a bad
        # signature is never laundered by an unsigned path.
        for env in envelopes:
            if not _verify_envelope(env):
                _refuse(REASON_SIGNATURE_INVALID,
                        "a presented output signature does not verify.",
                        ctx)

    return payload


# ---------------------------------------------------------------------------
# purify_transition — in flight
# ---------------------------------------------------------------------------

def purify_transition(before, after, kind, *, context=None):
    """Purify one state transition in flight. Called BEFORE the mutation
    it guards (the caller commits only after this returns). Fail-closed:
    any violation raises PurificationRefused with the true reason.

    Checks:
      1. KIND — kind must be whitelisted in rights.COMMIT_KINDS (the one
         shared definition of what may change). Anything else ->
         UNKNOWN_TRANSITION_KIND.
      2. RECEIPT — context must carry the "receipt" the transition will
         be committed under: a dict with a valid provenance label. A
         receipt that would grant/pass on an UNKNOWN label ->
         UNKNOWN_UPGRADE_REFUSED. No receipt -> RECEIPT_NOT_PLANNED: no
         silent, unreceipted mutation.
      3. NO SILENT MUTATION — before and after must be JSON-serializable
         and must DIFFER. A transition that changes nothing is refused:
         state does not drift without a receipted reason.
      4. IDENTITY CONTINUITY — when context names the "identity" the
         transition belongs to, identity-valued fields in before/after
         must agree with it (context "identity_moves" exempts declared
         ownership moves, e.g. MERIT_TRANSFER).

    Returns the purified transition record
    {"kind", "before", "after", "receipt_sha256"} — the receipt itself is
    committed by writes.dclm_commit, never here. Pure.
    """
    ctx = dict(context) if isinstance(context, dict) else {}
    path = ctx.get("path", "purify_transition")
    ctx["path"] = path

    # --- 1. kind whitelisted ------------------------------------------------
    if kind not in COMMIT_KINDS:
        _refuse(REASON_UNKNOWN_TRANSITION_KIND,
                f"transition kind {kind!r} is not whitelisted. Writable "
                f"kinds are {sorted(COMMIT_KINDS)}.",
                ctx)

    # --- 2. the receipt will exist ------------------------------------------
    receipt = ctx.get("receipt")
    if not isinstance(receipt, dict):
        _refuse(REASON_RECEIPT_NOT_PLANNED,
                "no receipt planned for this transition: every state "
                "change is receipted, or it does not happen.",
                ctx)
    label = receipt.get("provenance")
    if label not in PROVENANCE_LABELS:
        _refuse(REASON_INVALID_PROVENANCE,
                f"the planned receipt carries invalid provenance "
                f"{label!r}.",
                ctx)
    if receipt.get("outcome") in _PASS_VALUES and label == "UNKNOWN":
        _refuse(REASON_UNKNOWN_UPGRADE_REFUSED,
                "the planned receipt would grant on an UNKNOWN label: "
                "UNKNOWN is never PASS.",
                ctx)

    # --- 3. no silent mutation -----------------------------------------------
    try:
        before_bytes = _canonical_bytes(before)
        after_bytes = _canonical_bytes(after)
    except (TypeError, ValueError) as exc:
        _refuse(REASON_NON_SERIALIZABLE,
                f"transition endpoints must be JSON-serializable: {exc}.",
                ctx)
    if before_bytes == after_bytes:
        _refuse(REASON_SILENT_MUTATION,
                f"transition {kind!r} declares no change: state does not "
                f"drift without a receipted reason.",
                ctx)

    # --- 4. identity continuity ----------------------------------------------
    expected = ctx.get("identity")
    if expected is not None and not ctx.get("identity_moves"):
        for where, snapshot in (("before", before), ("after", after)):
            for key, value in _identity_values(snapshot):
                if value != expected:
                    _refuse(REASON_IDENTITY_DISCONTINUITY,
                            f"transition {kind!r}: {where} field {key!r} "
                            f"names {value!r}, expected {expected!r}. "
                            f"Identity does not change mid-transition.",
                            ctx)

    return {
        "schema": SCHEMA,
        "kind": kind,
        "before": before,
        "after": after,
        "receipt_sha256": hashlib.sha256(
            _canonical_bytes(receipt)).hexdigest(),
        "testnet": True,
    }

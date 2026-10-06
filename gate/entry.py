#!/usr/bin/env python3
"""
THE ENTRY GATE — the doorway, not the world (TESTNET).

David's four laws of the website (2026-10-06 ~4:36 AM EDT):
  1. the 2D card explains the Unity ID
  2. the bind ceremony
  3. the eFuse ignition
  4. entry into the 3D world
One card at the doorway — no more 2D after that.

What this module is
-------------------
The DCLM-side entry orchestrator. The thin client REQUESTS entry
(POST /api/world/bind with the covenant attestation and the ceremony
proof); DCLM PERFORMS it here and returns the result. The client never
generates identities, never decides binding, never mints.

The full entry flow, in order:
  1. covenant check      — the entrant must accept the covenant
                           (COVENANT_NOT_ACCEPTED refusal otherwise)
  2. identity derivation — DCLM derives the Unity ID from the ceremony's
                           credential material:
                             "unity:testnet:" + sha256(material)[:16]
                           Obfuscated by construction — a hash, no PII,
                           ever. The client supplies ceremony material,
                           never an identity.
  3. request_bind        — UNBOUND -> BINDING (gate.py, server-side)
  4. confirm_bind        — BINDING -> BOUND, proof verified
                           (default verifier is UNKNOWN/unwired; UNKNOWN
                           is never PASS)
  5. issue_seed          — the ONE free seed (dclm/seed.py): price 0,
                           cost 0, one per Unity ID
  6. emit_gate_envelope  — the GATE envelope for metered intent
  7. ignition            — the eFuse ignition: the member's spark.
                           A signed IGNITION record, receipted, referencing
                           the bind receipt, the seed, and the envelope.
                           The network launch in miniature — every new
                           member's entry echoes the genesis fuse
                           (economics/fuse.py). No state transition: the
                           ignition is an event on top of BOUND, not a new
                           state. The gate's state machine is untouched.

Every step is receipted. Refusals are first-class ({ok: False, refused:
{reason, detail}}) — never a bare exception across the wire, never a
silent drop.

Idempotency
-----------
Entry is idempotent per identity. An identity that is BOUND and already
ignited gets its existing entry record back — no new receipts, no new
seed, no duplicate spark. A BOUND identity with no ignition yet resumes
(seed + envelope + ignition). A BINDING identity resumes at the proof.

Testnet only
------------
Only identities of the form "unity:testnet:<16 hex>" are produced, and
only testnet schemas are emitted. The structural refusal lives in
gate.py and seed.py; this module never fabricates an identity.

Honest boundaries
-----------------
- WebAuthn is SPEC/unwired (gate.py's slot). In the sandbox the default
  verifier returns UNKNOWN and entry REFUSES at the proof step. Tests
  inject a clearly-labeled TEST STUB verifier.
- The testnet ceremony stub (proof kind "testnet-stub") is explicit:
  the client names it a stub, DCLM still derives the identity and still
  runs bind-then-validate. A stub is a stub — never presented as a real
  device ceremony.
- The seeder's registry is in-memory per process (dclm/seed.py's design).
  This module caches one Seeder per gate state dir so the one-seed rule
  holds across calls in-process. Cross-process seed persistence is
  seed.py's lane, flagged in ENTRY.md — not silently fixed here.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.gate.entry.v1.testnet"
IGNITION_SCHEMA = "unity.gate.ignition.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"
IGNITIONS_FILENAME = "ignitions.jsonl"

COVENANT_VERSION = "covenant.v1"

# The covenant copy — the SAME words live on the gate card (client).
# One covenant, one wording, two surfaces.
COVENANT_LINES = (
    "ONBOARD — take your free seed. One per Unity ID. It costs nothing.",
    "STAY IN LINE — follow the law, stay pure.",
    "PREACH THE GOOD WORD — bring others into the world.",
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_GATE_MODULE_PATH = os.path.join(_HERE, "gate.py")
_SEED_MODULE_PATH = os.path.join(_HERE, "..", "dclm", "seed.py")
_WRITES_MODULE_PATH = os.path.join(_HERE, "..", "dclm", "writes.py")

# One seeder per gate state dir: the seeder's registry is in-memory, so
# the one-seed rule needs a stable Seeder across perform_entry calls in
# one process. (Cross-process seed persistence is seed.py's lane.)
_SEEDERS: dict = {}


# ---------------------------------------------------------------------------
# Errors — domain refusals convert to {ok: False} envelopes, never leak
# ---------------------------------------------------------------------------


class EntryRefused(Exception):
    """Structural refusal of entry. Carries .reason and .detail.

    Reasons: COVENANT_NOT_ACCEPTED | NO_CREDENTIAL_MATERIAL |
    BIND_REFUSED | PROOF_UNKNOWN | SEED_REFUSED | ENVELOPE_FAILED |
    IGNITION_FAILED | STATE_UNREADABLE.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"entry refused [{reason}]: {detail}")


# ---------------------------------------------------------------------------
# Module loading (importlib-by-path, same pattern as gate.py <-> seed.py)
# ---------------------------------------------------------------------------


def _load_module(name: str, path: str):
    if not os.path.exists(path):
        raise EntryRefused(
            "STATE_UNREADABLE",
            f"required module not found at {path} — entry cannot be "
            "performed honestly without it",
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise EntryRefused(
            "STATE_UNREADABLE",
            f"module spec could not be built for {path}",
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve via sys.modules
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise EntryRefused(
            "STATE_UNREADABLE",
            f"module at {path} failed to load ({exc}) — a broken module "
            "is not a working one",
        ) from exc
    return module


def _gate_module():
    return _load_module("unity_entry_gate", _GATE_MODULE_PATH)


def _seed_module():
    return _load_module("unity_entry_seed", _SEED_MODULE_PATH)


def _writes_module():
    return _load_module("unity_entry_writes", _WRITES_MODULE_PATH)


# ---------------------------------------------------------------------------
# Identity derivation — DCLM derives, the client never invents
# ---------------------------------------------------------------------------


def derive_entry_identity(proof: dict) -> str:
    """Derive the Unity ID from the ceremony's credential material.

    The client supplies ceremony MATERIAL, never an identity. DCLM runs
    the derivation: "unity:testnet:" + sha256(material)[:16]. The result
    is obfuscated by construction — a hash fragment, no PII, ever.

    proof kinds:
      - "webauthn": proof["credential_id"] (base64url of the assertion's
        rawId). The real device ceremony path (SPEC — unwired here).
      - "testnet-stub": proof["stub_seed"] (hex or utf-8 string) plus
        proof["testnet_ceremony"] is True. EXPLICITLY a stub — the
        sandbox stand-in for the device ceremony. The derivation still
        runs server-side; the stub label travels into the ignition
        record so a stub is never mistaken for a real ceremony.

    Raises EntryRefused(NO_CREDENTIAL_MATERIAL) when the proof carries
    no usable credential material.
    """
    if not isinstance(proof, dict):
        raise EntryRefused(
            "NO_CREDENTIAL_MATERIAL",
            "the ceremony proof is not a mapping — there is no credential "
            "material to derive an identity from",
        )
    kind = proof.get("kind")
    material = None
    if kind == "webauthn":
        cred = proof.get("credential_id")
        if isinstance(cred, str) and cred:
            try:
                padded = cred + "=" * (-len(cred) % 4)
                material = base64.urlsafe_b64decode(padded.encode("ascii"))
            except Exception:
                material = None
    elif kind == "testnet-stub":
        if proof.get("testnet_ceremony") is True:
            seed = proof.get("stub_seed")
            if isinstance(seed, str) and seed:
                try:
                    material = bytes.fromhex(seed)
                except ValueError:
                    material = (
                        b"unity-entry-testnet-stub|" + seed.encode("utf-8")
                    )
                material = (
                    b"unity-entry-testnet-stub|"
                    + hashlib.sha256(material).digest()
                )
    if not material:
        raise EntryRefused(
            "NO_CREDENTIAL_MATERIAL",
            f"ceremony proof kind {kind!r} carries no usable credential "
            "material — DCLM cannot derive an identity from nothing, and "
            "the client may not invent one",
        )
    digest = hashlib.sha256(material).hexdigest()[:16]
    return f"{IDENTITY_PREFIX}{digest}"


def obfuscated_display(identity: str) -> str:
    """The display form of a Unity ID: the obfuscated number only."""
    return identity[len(IDENTITY_PREFIX):] if identity.startswith(
        IDENTITY_PREFIX) else identity


# ---------------------------------------------------------------------------
# The ignition log — the member's spark, receipted
# ---------------------------------------------------------------------------


def _ignitions_path(state_dir: str) -> str:
    return os.path.join(state_dir, IGNITIONS_FILENAME)


def _find_ignition(state_dir: str, identity: str):
    """The existing ignition record for an identity, or None.

    The log is append-only; the LAST record for the identity wins.
    """
    path = _ignitions_path(state_dir)
    if not os.path.exists(path):
        return None
    found = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            receipt = rec.get("receipt", rec)
            if receipt.get("identity") == identity:
                found = rec
    return found


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# The entry ceremony — DCLM performs it
# ---------------------------------------------------------------------------


def perform_entry(
    covenant_accepted,
    proof: dict,
    verifier=None,
    gate=None,
    seeder=None,
    state_dir: str | None = None,
) -> dict:
    """Perform the full entry ceremony. DCLM-side, testnet.

    covenant_accepted: the client's attestation that the entrant read
      the card and accepted the covenant. Falsy -> COVENANT_NOT_ACCEPTED.
    proof: the ceremony proof (see derive_entry_identity). The default
      verifier is gate.py's WebAuthn slot (UNKNOWN/unwired) — UNKNOWN is
      never PASS, so sandbox entry without an injected verifier refuses
      at the proof step, honestly.
    gate / seeder: injectable (tests inject gates on temp state dirs,
      exactly like gate.py's own tests). None -> live modules.
    state_dir: the gate state dir (ignitions.jsonl lives here).

    Returns {ok: True, entry: {...}} or {ok: False, refused: {reason,
    detail, at_step}}. Domain refusals never raise; unexpected errors do.
    """
    at_step = "covenant"
    try:
        # -- 1. the covenant ------------------------------------------------
        if not covenant_accepted:
            raise EntryRefused(
                "COVENANT_NOT_ACCEPTED",
                "the doorway asks once: read the card, accept the "
                "covenant — onboard, stay in line, preach the good word. "
                "No acceptance, no bind.",
            )

        # -- 2. identity derivation (DCLM derives) ---------------------------
        at_step = "derive"
        identity = derive_entry_identity(proof)

        # -- 3. the gate ------------------------------------------------------
        # When a gate is injected, its exception classes live in ITS
        # module (whatever name it was loaded under) — resolve the
        # module from the instance so the except clauses below catch the
        # exceptions the instance actually raises. A mismatched module
        # name must never turn a domain refusal into an uncaught throw.
        if gate is not None:
            gate_mod = sys.modules.get(type(gate).__module__) \
                or _gate_module()
            the_gate = gate
        else:
            gate_mod = _gate_module()
            the_gate = gate_mod.UnityGate(state_dir=state_dir)
        gate_state_dir = the_gate.state_dir
        at_step = "status"
        try:
            status = the_gate.status(identity)
        except Exception as exc:
            raise EntryRefused(
                "BIND_REFUSED",
                f"the gate could not read binding state for the derived "
                f"identity ({type(exc).__name__}) — unreadable is not "
                "bound",
            ) from exc

        # Idempotent replay: BOUND + already ignited -> the existing
        # record, no new receipts, no new seed, no duplicate spark.
        if status == "BOUND":
            existing = _find_ignition(gate_state_dir, identity)
            if existing is not None:
                receipt = existing.get("receipt", existing)
                return {
                    "schema": SCHEMA,
                    "ok": True,
                    "already": True,
                    "identity": identity,
                    "obfuscated_display": obfuscated_display(identity),
                    "covenant": {
                        "accepted": True,
                        "version": COVENANT_VERSION,
                        "lines": list(COVENANT_LINES),
                    },
                    "entry": {
                        "ignition": receipt,
                        "note": "already entered — the doorway was passed; "
                                "no new receipts, no duplicate spark",
                    },
                    "testnet": True,
                    "issued_at": _utc_now(),
                }

        # -- 4. request_bind: UNBOUND -> BINDING ------------------------------
        at_step = "request_bind"
        if status == "UNBOUND":
            try:
                bind_start = the_gate.request_bind(identity)
            except gate_mod.GateError as exc:
                raise EntryRefused(
                    "BIND_REFUSED", f"request_bind refused: {exc}"
                ) from exc
        else:
            bind_start = {"state": status, "transition": "RESUMED",
                          "identity": identity}

        # -- 5. confirm_bind: BINDING -> BOUND ---------------------------------
        at_step = "confirm_bind"
        verify = verifier if verifier is not None \
            else gate_mod.verify_webauthn_assertion
        try:
            bind_receipt = the_gate.confirm_bind(identity, proof,
                                                 verifier=verify)
        except gate_mod.GateError as exc:
            reason = ("PROOF_UNKNOWN"
                      if isinstance(exc, gate_mod.GateUnknown)
                      else "BIND_REFUSED")
            raise EntryRefused(
                reason,
                f"confirm_bind refused: {exc}",
            ) from exc

        # -- 6. the one free seed ----------------------------------------------
        at_step = "issue_seed"
        if seeder is not None:
            seed_mod = sys.modules.get(type(seeder).__module__) \
                or _seed_module()
            the_seeder = seeder
        else:
            seed_mod = _seed_module()
            the_seeder = _SEEDERS.get(gate_state_dir)
            if the_seeder is None:
                the_seeder = seed_mod.Seeder(gate=the_gate)
                _SEEDERS[gate_state_dir] = the_seeder
        try:
            seed_envelope = the_seeder.issue_seed(identity)
            seed_body = seed_envelope["receipt"]
        except seed_mod.SeedRefused as exc:
            if exc.reason == seed_mod.REASON_SEED_ALREADY_ISSUED:
                # Resume path: the seed exists from an earlier partial
                # entry — carry it forward, mint nothing new.
                existing_record = the_seeder.seed_record(identity)
                seed_body = {
                    "seed_id": existing_record.seed_id,
                    "unity_id": identity,
                    "price": 0.0,
                    "cost": 0.0,
                    "resumed": True,
                    "note": "seed already issued in an earlier entry — "
                            "one per Unity ID, carried forward",
                }
                seed_envelope = {"receipt": seed_body,
                                 "canonical_sha256": None,
                                 "provenance": "DERIVED"}
            else:
                raise EntryRefused(
                    "SEED_REFUSED",
                    f"issue_seed refused [{exc.reason}]: {exc.detail}",
                ) from exc

        # -- 7. the GATE envelope ------------------------------------------------
        at_step = "emit_gate_envelope"
        try:
            gate_envelope = the_gate.emit_gate_envelope(identity)
        except gate_mod.GateError as exc:
            raise EntryRefused(
                "ENVELOPE_FAILED",
                f"emit_gate_envelope failed after a successful bind "
                f"({exc}) — the bind stands; the envelope did not issue",
            ) from exc

        # -- 8. ignition: the member's spark ------------------------------------
        at_step = "ignition"
        writes_mod = _writes_module()
        proof_kind = proof.get("kind") if isinstance(proof, dict) else None
        ignition_body = {
            "schema": IGNITION_SCHEMA,
            "type": "IGNITION",
            "identity": identity,
            "obfuscated_display": obfuscated_display(identity),
            "covenant": {
                "accepted": True,
                "version": COVENANT_VERSION,
                "lines": list(COVENANT_LINES),
            },
            "ceremony": {
                "kind": proof_kind,
                "testnet_ceremony_stub": proof_kind == "testnet-stub",
                "note": (
                    "TESTNET STUB — the sandbox stand-in for the device "
                    "ceremony, never a real WebAuthn assertion"
                    if proof_kind == "testnet-stub"
                    else "device ceremony proof, verified by the gate"
                ),
            },
            "bind_receipt_id": bind_receipt["receipt_id"],
            "seed_id": seed_body["seed_id"],
            "seed_price": seed_body["price"],
            "seed_cost": seed_body["cost"],
            "gate_envelope_receipt_id": gate_envelope["receipt_id"],
            "echoes": (
                "economics.fuse.Fuse genesis — the network launch. This "
                "ignition is the launch in miniature: one member's spark "
                "carries the same shape as the genesis."
            ),
            "provenance": "DERIVED",
            "issued_at": _utc_now(),
            "testnet": True,
            "note": (
                "The eFuse ignition — the energy surge into the world. "
                "The card dissolves, light refracts through diamond "
                "geometry, and the member is IN. The seed is membership, "
                "not money: it opens the door; nothing more."
            ),
        }
        try:
            ignition_envelope = writes_mod.sign_commit(ignition_body)
        except Exception as exc:
            raise EntryRefused(
                "IGNITION_FAILED",
                f"the bind and the seed stand, but the ignition could "
                f"not be signed ({exc})",
            ) from exc
        ignition_id = _sha256_hex(
            json.dumps(ignition_envelope["receipt"], sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        )
        with open(_ignitions_path(gate_state_dir), "a",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(ignition_envelope, sort_keys=True) + "\n")

        # -- the entry result -----------------------------------------------------
        return {
            "schema": SCHEMA,
            "ok": True,
            "already": False,
            "identity": identity,
            "obfuscated_display": obfuscated_display(identity),
            "covenant": {
                "accepted": True,
                "version": COVENANT_VERSION,
                "lines": list(COVENANT_LINES),
            },
            "bind": {
                "transition": bind_receipt["transition"],
                "state": bind_receipt["state"],
                "receipt_id": bind_receipt["receipt_id"],
            },
            "seed": {
                "seed_id": seed_body["seed_id"],
                "price": seed_body["price"],
                "cost": seed_body["cost"],
                "receipt_sha256": seed_envelope.get("canonical_sha256"),
            },
            "envelope": {
                "type": gate_envelope["type"],
                "receipt_id": gate_envelope["receipt_id"],
                "authorizes": gate_envelope["authorizes"],
            },
            "ignition": {
                "ignition_id": ignition_id,
                "receipt_sha256": ignition_envelope["canonical_sha256"],
                "signature": ignition_envelope["signature"],
                "issued_at": ignition_body["issued_at"],
            },
            "receipts": [
                bind_receipt["receipt_id"],
                seed_envelope.get("canonical_sha256"),
                ignition_envelope["canonical_sha256"],
            ],
            "testnet": True,
            "issued_at": _utc_now(),
        }
    except EntryRefused as exc:
        return {
            "schema": SCHEMA,
            "ok": False,
            "refused": {
                "reason": exc.reason,
                "detail": exc.detail,
                "at_step": at_step,
            },
            "testnet": True,
            "issued_at": _utc_now(),
        }

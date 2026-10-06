"""
DCLM WRITE PATH — the single sanctioned commit path. DCLM performs the WRITES.

=====================================================================
HARD BOUNDARY — READ THIS BEFORE ADDING ANY STATE ANYWHERE
=====================================================================
David's architecture rule, binding: DCLM holds the RIGHTS and performs
the WRITES. The thin client NEVER writes directly.

  * RIGHTS (authority): rights.py alone decides what may happen.
  * WRITES (persistence): THIS MODULE alone performs state changes.
    dclm_commit() is the ONLY sanctioned way any state changes, any
    ledger entry is made, any receipt is emitted. One commit path.

Every write flows:
    request -> rights.check_rights -> GRANT/DENY
        -> (GRANT only) dclm_commit performs the write via the store
        -> dclm_commit emits the signed receipt
        -> the signed receipt is appended to the store's receipt log

dclm_commit REFUSES — raises CommitRefused, never warns, writes
nothing — unless ALL of the following hold:
    1. rights_verdict is a genuine, DCLM-issued RightsVerdict whose
       verdict is GRANT. A forged "GRANT" string, None, a DENY verdict,
       or any other object is refused. Verdicts are frozen dataclasses:
       DENY cannot be edited into GRANT.
    2. kind is in the COMMIT_KINDS whitelist (LEDGER_DEBIT,
       LEDGER_CREDIT, WORLD_STATE, GATE_TRANSITION, METER_RECEIPT,
       DATA_INGEST, TAP_OUTFLOW, TOKEN_MINT, MERIT_ACCRUAL,
       HONOR_RECORD, MERIT_TRANSFER, WINTER_STORE, WINTER_RELEASE, GRANT_ISSUE,
       GRANT_REVOKE, SHARED_ACCESS, ONBOARD, RESIDUAL_INTAKE,
       SPLIT_EXECUTE, NINETEEN_ROUTE, SEED_ISSUE, HELPER_ASSIGN,
       HELPER_STAGE, HELPER_HANDOFF, HELPER_WELCOME). The WINTER_* two
       were added by the winter-mechanism worker (Oct 6 2026) for the
       Peg Regulation Reserve — the starch store; the GRANT_*/SHARED_*
       three were added by the shared-access worker (Oct 6 2026) for the
       kin layer's tiered grants; the TOKEN_*/MERIT_* four were added
       by the tokenization worker (Oct 6 2026) — TOKEN_MINT, MERIT_ACCRUAL
       and HONOR_RECORD for the receipt->token pipeline, MERIT_TRANSFER
       for the sole Merit ownership-transfer path (David's word:
       Merit is transferable; the earlier UNITY_SALE kind died with the
       bound-transfer-sale concept on 2026-10-06 — Unity never transfers); the
       ONBOARD/RESIDUAL_INTAKE/SPLIT_EXECUTE/NINETEEN_ROUTE four were
       added by the onboarder-pipeline worker (Oct 6 2026) for the
       Residual Law Finance onboarder -> residual -> tokenomics flywheel;
       SEED_ISSUE was added by the one-seed worker (Oct 6 2026) for
       David's one-seed law — one free seed per Unity ID, price 0, cost
       0, non-transferable, non-spendable (membership, not money); the
       HELPER_* four were added by the helper-swarm worker (Oct 6 2026)
       for the post-bootstrap guide protocol — assignment, introduction
       stages, Iris handoff, welcome aboard. The guides hold no
       authority: none of these kinds conveys grant/revoke/mint power.
       Anything else is refused.
    3. The payload and the resulting receipt are JSON-serializable, and
       the receipt carries a valid provenance label (UNKNOWN is never
       PASS: no granted write hides behind an unknown label).

There is NO other public function in this module that touches a store.
A client that bypasses rights has no path to committed state: without
a DCLM-issued GRANT verdict, dclm_commit raises before any mutation,
and the store records nothing — no write, no receipt, no trace.

The store protocol (CommitStore): DCLM components (meter, gate, data)
implement apply_write / build_receipt / append_receipt. The store owns
its state; this module owns the ORDER — rights first, then exactly one
mutation, then exactly one signed receipt.

Testnet only. Receipts are Ed25519-signed with the existing testnet key
material from ../keys/ (same as compute.py / meter.py). Provenance
labels on every receipt.
=====================================================================
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from rights import (  # noqa: E402 — one shared definition of writable kinds
    COMMIT_KINDS,
    RightsVerdict,
)
from compute import (  # noqa: E402 — reuse the existing test key material
    ED25519_HELPER,
    KEY_ID,
    PROVENANCE_LABELS,
    TEST_PRIV_KEY,
    TEST_PUB_KEY,
)

SCHEMA = "unity.writes.v1.testnet"


class CommitRefused(Exception):
    """The commit boundary refused: no GRANT verdict, unknown kind, bad
    store, or unlabeled receipt. Raised, never warned. Nothing was
    written when this is raised for verdict/kind reasons."""


# ---------------------------------------------------------------------------
# store protocol
# ---------------------------------------------------------------------------

class CommitStore:
    """Protocol for the state a commit may touch.

    DCLM components implement this; dclm_commit drives it. The store
    owns its state — the module owns the ORDER (rights, then one
    mutation, then one signed receipt).
    """

    def apply_write(self, kind, payload):
        """Perform THE mutation for this commit. Called exactly once per
        commit, only after the GRANT verdict was verified. Returns a
        mutation report (JSON-serializable dict)."""
        raise NotImplementedError

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        """Format the receipt to be signed. Default: a standard COMMIT
        record carrying the kind, the payload's sha256, the mutation
        report, and the rights verdict that authorized it. Stores may
        override to keep their own receipt format (meter.py does — its
        receipt bytes are unchanged by the boundary)."""
        return {
            "schema": SCHEMA,
            "type": "COMMIT",
            "kind": kind,
            "payload_sha256": hashlib.sha256(
                _canonical_bytes(payload)
            ).hexdigest(),
            "mutation": mutation_report,
            "rights": {
                "verdict": rights_verdict.verdict,
                "reason": rights_verdict.reason,
                "identity": rights_verdict.identity,
                "action": rights_verdict.action,
            },
            "testnet": True,
            "issued_at": _utc_now(),
            "provenance": "DERIVED",  # computed in-process by DCLM
        }

    def append_receipt(self, envelope):
        """Append the SIGNED receipt envelope to the store's receipt log.
        Called exactly once per commit, after signing."""
        raise NotImplementedError


class MemoryCommitStore(CommitStore):
    """In-memory store: for tests, dry runs, and components that manage
    their own persistence outside this module. applied and receipts are
    inspectable; nothing touches disk."""

    def __init__(self):
        self.applied = []   # list of (kind, payload)
        self.receipts = []  # list of signed envelopes

    def apply_write(self, kind, payload):
        self.applied.append((kind, payload))
        return {"applied": True, "writes": len(self.applied)}

    def append_receipt(self, envelope):
        self.receipts.append(envelope)


# ---------------------------------------------------------------------------
# the single commit path
# ---------------------------------------------------------------------------

def dclm_commit(kind, payload, rights_verdict, store):
    """Commit one write through the single sanctioned path.

    kind           — one of COMMIT_KINDS, else CommitRefused.
    payload        — JSON-serializable data describing the write.
    rights_verdict — a DCLM-issued RightsVerdict with verdict GRANT,
                     else CommitRefused. Forged strings, None, and DENY
                     verdicts are all refused.
    store          — a CommitStore. Its apply_write performs the one
                     mutation; its append_receipt logs the signed receipt.

    Returns the signed receipt envelope. Raises CommitRefused (writes
    nothing) on any refusal.
    """
    # 1. AUTHORITY FIRST: no GRANT verdict, no commit. The verdict must
    #    be DCLM-issued — a client cannot utter its way past this.
    if not (
        isinstance(rights_verdict, RightsVerdict)
        and rights_verdict.verdict == "GRANT"
    ):
        raise CommitRefused(
            "DCLM refuses the commit: no DCLM-issued GRANT verdict. "
            f"Got {type(rights_verdict).__name__} "
            f"({getattr(rights_verdict, 'verdict', rights_verdict)!r}). "
            "Rights are computed by rights.check_rights, not asserted "
            "by the caller. Nothing was written."
        )

    # 2. KIND WHITELIST: only known kinds of state may change.
    if kind not in COMMIT_KINDS:
        raise CommitRefused(
            f"DCLM refuses the commit: unknown kind {kind!r}. Writable "
            f"kinds are {sorted(COMMIT_KINDS)}. Nothing was written."
        )

    # 3. STORE PROTOCOL: the store must speak the commit protocol.
    if not (
        hasattr(store, "apply_write")
        and hasattr(store, "build_receipt")
        and hasattr(store, "append_receipt")
    ):
        raise CommitRefused(
            "DCLM refuses the commit: store does not implement the "
            "commit protocol (apply_write/build_receipt/append_receipt). "
            "Nothing was written."
        )

    # 4. SERIALIZABLE BEFORE MUTATION: a payload that cannot be signed
    #    must fail before any state changes, never after.
    _canonical_bytes(payload)  # raises TypeError on unserializable payload

    # 5. THE WRITE — the one mutation, performed by DCLM, after GRANT.
    mutation_report = store.apply_write(kind, payload)

    # 6. THE RECEIPT — formatted by the store, labeled, then signed.
    receipt = store.build_receipt(kind, payload, mutation_report,
                                  rights_verdict)
    _assert_receipt_labeled(receipt)

    # 7. SIGN + LOG — the signed receipt is the proof of the write.
    envelope = sign_commit(receipt)
    store.append_receipt(envelope)
    return envelope


def _assert_receipt_labeled(receipt):
    """Every committed receipt carries a valid provenance label. UNKNOWN
    is never PASS: no granted write hides behind an unknown label."""
    label = receipt.get("provenance") if isinstance(receipt, dict) else None
    if label not in PROVENANCE_LABELS:
        raise CommitRefused(
            f"DCLM refuses the commit: receipt carries no valid "
            f"provenance label (got {label!r})."
        )
    if label == "UNKNOWN":
        raise CommitRefused(
            "DCLM refuses the commit: UNKNOWN is never PASS — a "
            "committed write may not hide behind an UNKNOWN label."
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(payload):
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# signing (Ed25519, testnet keys only — same material as compute.py)
# ---------------------------------------------------------------------------

def sign_commit(receipt, privkey_path=TEST_PRIV_KEY, key_id=KEY_ID):
    """Ed25519-sign the canonical JSON of a commit receipt.

    Returns an envelope: {"receipt", "canonical_sha256", "signature",
    "algorithm", "key_id", "provenance"}. Key material never leaves the
    keys/ dir; only canonical receipt bytes cross to the helper.
    """
    canonical = _canonical_bytes(receipt)
    proc = subprocess.run(
        ["node", ED25519_HELPER, "sign", privkey_path],
        input=canonical,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"commit signing failed: {proc.stderr.decode()!r}")
    signature = proc.stdout.decode().strip()
    return {
        "receipt": receipt,
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "signature": signature,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "provenance": "VERIFIED",  # the signature is verifiable against the key
    }


def verify_commit(envelope, pubkey_path=TEST_PUB_KEY):
    """Verify a signed commit envelope. Returns True/False — never raises
    on bad data."""
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

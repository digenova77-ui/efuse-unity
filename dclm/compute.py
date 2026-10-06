"""
DCLM COMPUTE CORE — server-side pipeline for the unified WORLD.

The website code runs INSIDE DCLM: the server computes the world state and
spits out signed data. Client devices render it; they do not compute on
connect.

This module imports the ring/Parliament logic from ~/workspace/core-rings/rings.py
(it does not copy it) and builds the signed WorldState on top.

Data honesty rules (absolute, no exceptions):
  * EVERY field carries a provenance label:
      REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN
  * FEED RULE: a feed is LIVE only with a real reading + hash.
      Otherwise PENDING. Never present PENDING as live.
  * UNKNOWN is never PASS: unknown data stays UNKNOWN, never renders
      as a positive claim.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys

# --- import the ring/Parliament logic (not copied) --------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE_RINGS = os.path.join(os.path.dirname(_HERE), "..", "core-rings")
sys.path.insert(0, os.path.normpath(_CORE_RINGS))
from rings import DecisionWave, Parliament, Point  # noqa: E402


# --- provenance ------------------------------------------------------------
PROVENANCE_LABELS = frozenset(
    {"REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"}
)

# --- status labels ---------------------------------------------------------
FEED_LIVE = "LIVE"
FEED_PENDING = "PENDING"
VERDICT_DECIDED = "DECIDED"
VERDICT_UNDECIDED = "UNDECIDED"  # the undecided bucket: world goes on

KEYS_DIR = os.path.join(_HERE, "..", "keys")
TEST_PRIV_KEY = os.path.join(KEYS_DIR, "unity-world-test.key")
TEST_PUB_KEY = os.path.join(KEYS_DIR, "unity-world-test.pub")
ED25519_HELPER = os.path.join(_HERE, "ed25519.js")

KEY_ID = "unity-world-test"  # TESTNET ONLY


# ---------------------------------------------------------------------------
# WorldState
# ---------------------------------------------------------------------------
class WorldState:
    """The signed state DCLM spits out.

    Fields:
      verdicts         — collapsed decisions (question/candidates/decision/balance)
      registry_digest  — sha256 of digested registry data, or UNKNOWN
      purity_pulse     — SIGNED boolean + pulse id, or UNKNOWN
      feed_status      — feed name -> LIVE (with reading hash) or PENDING

    Every field carries a provenance label. No exceptions.
    """

    def __init__(self):
        self.verdicts = []
        self.registry_digest = {"value": "UNKNOWN", "provenance": "UNKNOWN"}
        self.purity_pulse = {
            "signed": None,
            "pulse_id": None,
            "provenance": "UNKNOWN",
        }
        self.feed_status = {}

    def to_dict(self):
        return {
            "verdicts": self.verdicts,
            "registry_digest": self.registry_digest,
            "purity_pulse": self.purity_pulse,
            "feed_status": self.feed_status,
        }


# ---------------------------------------------------------------------------
# compute pipeline
# ---------------------------------------------------------------------------
def compute_world_state(waves, feeds=None, registry_data=None,
                        purity_pulse=None, parliament=None):
    """Run each wave through Parliament collapse, assemble the WorldState.

    waves         — list[DecisionWave], each with question + candidates
    feeds         — list of dicts {name, reading (bytes/str|None), reading_hash (str|None)}
    registry_data — bytes|str|None; anything digested for the registry
    purity_pulse  — dict|None: {"signed": bool, "pulse_id": str}
    parliament    — Parliament instance (defaults to the standard three rings)

    Returns the WorldState as a plain dict. Provenance on everything.
    """
    state = WorldState()
    parliament = parliament if parliament is not None else Parliament()

    for wave in waves:
        decision = parliament.collapse(wave)
        if decision is None:
            # Undecided bucket. No survivors, no forced collapse.
            # The world goes on; the state marks the verdict UNKNOWN, not PASS.
            state.verdicts.append({
                "question": wave.question,
                "candidates": [_point_dict(p) for p in wave.candidates],
                "status": VERDICT_UNDECIDED,
                "decision": None,
                "balance": None,
                "provenance": "UNKNOWN",
            })
        else:
            state.verdicts.append({
                "question": wave.question,
                "candidates": [_point_dict(p) for p in wave.candidates],
                "status": VERDICT_DECIDED,
                "decision": _point_dict(decision),
                # Balance is computed from the held decision — DERIVED, not measured.
                "balance": Parliament.balance(decision),
                "provenance": "DERIVED",
            })

    # Registry digest: computed in-process over present data -> VERIFIED.
    # Nothing to digest -> UNKNOWN.
    if registry_data is not None:
        if isinstance(registry_data, str):
            registry_data = registry_data.encode("utf-8")
        state.registry_digest = {
            "value": hashlib.sha256(registry_data).hexdigest(),
            "provenance": "VERIFIED",
        }

    # Purity pulse: claimed by the pulse source. We carry the claim, we do not
    # upgrade it to a verified fact. A signature mark alone is a REPORTED claim.
    # No pulse data at all -> UNKNOWN.
    if purity_pulse is not None:
        state.purity_pulse = {
            "signed": bool(purity_pulse.get("signed", False)),
            "pulse_id": purity_pulse.get("pulse_id"),
            "provenance": "REPORTED",
        }

    # FEED RULE: LIVE only with a real reading AND a real hash.
    # Anything else is PENDING with provenance UNKNOWN. Never present PENDING as live.
    for feed in (feeds or []):
        name = feed.get("name")
        reading = feed.get("reading")
        reading_hash = feed.get("reading_hash")
        has_reading = reading is not None and reading_hash is not None
        if has_reading:
            state.feed_status[name] = {
                "status": FEED_LIVE,
                "reading_hash": reading_hash,
                "provenance": "REPORTED",  # the feed reported it; we did not measure it
            }
        else:
            state.feed_status[name] = {
                "status": FEED_PENDING,
                "provenance": "UNKNOWN",
            }

    state_dict = state.to_dict()
    _assert_provenance(state_dict)
    return state_dict


def _point_dict(p):
    return {"x": p.x, "y": p.y, "z": p.z}


def _assert_provenance(state_dict):
    """Every WorldState field must carry a valid provenance label:
    verdict entries, registry_digest, purity_pulse, and each feed_status
    entry. (feed_status itself is a container keyed by feed name; the
    entries carry the labels.) Raises ValueError if any field is
    unlabeled or mislabeled."""

    def check(node, path):
        if not isinstance(node, dict) or "provenance" not in node:
            raise ValueError(f"missing provenance at {path}")
        if node["provenance"] not in PROVENANCE_LABELS:
            raise ValueError(
                f"invalid provenance at {path}: {node['provenance']!r}"
            )

    for field in ("verdicts", "registry_digest", "purity_pulse", "feed_status"):
        if field not in state_dict:
            raise ValueError(f"missing WorldState field: {field}")

    for i, verdict in enumerate(state_dict["verdicts"]):
        check(verdict, f"verdicts[{i}]")
    check(state_dict["registry_digest"], "registry_digest")
    check(state_dict["purity_pulse"], "purity_pulse")
    for name, entry in state_dict["feed_status"].items():
        check(entry, f"feed_status.{name}")


# ---------------------------------------------------------------------------
# signing (Ed25519, testnet keys only)
# ---------------------------------------------------------------------------
def _canonical_bytes(state_dict):
    return json.dumps(
        state_dict, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_state(state_dict, privkey_path=TEST_PRIV_KEY, key_id=KEY_ID):
    """Ed25519-sign the canonical JSON of the state.

    Returns an envelope: {"state", "canonical_sha256", "signature",
    "algorithm", "key_id", "provenance"}.
    Key material never leaves the keys/ dir; only bytes of the canonical
    state travel to the signing helper.
    """
    canonical = _canonical_bytes(state_dict)
    proc = subprocess.run(
        ["node", ED25519_HELPER, "sign", privkey_path],
        input=canonical,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"signing failed: {proc.stderr.decode()!r}")
    signature = proc.stdout.decode().strip()
    return {
        "state": state_dict,
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "signature": signature,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "provenance": "VERIFIED",  # the signature is verifiable against the key
    }


def verify_envelope(envelope, pubkey_path=TEST_PUB_KEY):
    """Verify a signed envelope. Returns True/False — never raises on bad data."""
    try:
        canonical = _canonical_bytes(envelope["state"])
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

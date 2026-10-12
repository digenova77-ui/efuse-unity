"""Go-live as signed intent — closing S5.

"The command is the word" died: a static "issued_by": "david:go-live"
string proves nothing. The word is now a SIGNED intent:

  payload = {"type": "go-live-intent",
             "lane": "EUROPE", "version": "v1.2.0",
             "bundle_hash": "<sha256>",
             "issued_at": "<utc>", "expires_at": "<utc>",
             "nonce": "<unique>"}

David signs it with the offline key (ceremony.py prints how; a small
helper builds the payload so he only reviews and signs). golive.py
verifies BEFORE cutover:
  - signature by the pinned offline pubkey (or a seated parliament's
    supermajority bill carrying its signatures — same envelope shape,
    key_id checked against the parliament registry when it exists)
  - expires_at in the future, issued_at sane (no far-future issuance)
  - nonce never seen before (replay protection; persisted nonce store)
  - lane/version/bundle_hash match the staged bundle

Unverified intent -> HALT, attested. The standing order already names the
three valid mouths for the word (David, parliament supermajority, sealed
instrument) — now each mouth must PROVE it spoke.
"""
import json
import os
import time

from . import envelope

INTENT_TYPE = "go-live-intent"
MAX_INTENT_AGE_S = 7 * 24 * 3600  # an intent older than 7 days is stale


class IntentError(ValueError):
    pass


def build_intent(lane, version, bundle_hash, ttl_s=3600, nonce=None,
                 issued_at=None):
    """Build the intent payload (unsigned). David's offline machine seals it."""
    now = int(time.time())
    iat = int(issued_at) if issued_at is not None else now
    return {"type": INTENT_TYPE,
            "lane": lane,
            "version": version,
            "bundle_hash": bundle_hash,
            "issued_at": iat,
            "expires_at": iat + int(ttl_s),
            "nonce": nonce or ("%x-%x" % (now, os.getpid()))}


def seal_intent(payload, seed):
    if payload.get("type") != INTENT_TYPE:
        raise IntentError("not a go-live intent payload")
    return envelope.seal(payload, seed)


def load_nonce_store(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_nonce_store(path, nonces):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(nonces), f)
        f.write("\n")
    os.replace(tmp, path)


def verify_intent(env, pubkey, lane, version, bundle_hash,
                  nonce_store_path, now=None):
    """Full verification. Returns the payload. Raises IntentError.

    Checks, in order: envelope signature + key binding, type, lane/version/
    hash match, time window, nonce freshness (persisted BEFORE returning,
    so a crash can't double-spend the word).
    """
    now = int(now) if now is not None else int(time.time())
    try:
        payload = envelope.open_envelope(env, pubkey)
    except envelope.EnvelopeError as e:
        raise IntentError("intent signature invalid: %s" % e)
    if payload.get("type") != INTENT_TYPE:
        raise IntentError("not a go-live intent")
    for field, expected in (("lane", lane), ("version", version),
                            ("bundle_hash", bundle_hash)):
        if payload.get(field) != expected:
            raise IntentError("intent %s mismatch: %r != %r"
                              % (field, payload.get(field), expected))
    iat, exp = payload.get("issued_at"), payload.get("expires_at")
    if not isinstance(iat, int) or not isinstance(exp, int):
        raise IntentError("intent timestamps malformed")
    if exp <= now:
        raise IntentError("intent expired")
    if iat > now + 300:
        raise IntentError("intent issued in the future")
    if now - iat > MAX_INTENT_AGE_S:
        raise IntentError("intent older than 7 days — re-issue the word")
    nonce = payload.get("nonce")
    if not nonce:
        raise IntentError("intent has no nonce")
    seen = load_nonce_store(nonce_store_path)
    if nonce in seen:
        raise IntentError("intent nonce already used — replay refused")
    seen.add(nonce)
    save_nonce_store(nonce_store_path, seen)
    return payload

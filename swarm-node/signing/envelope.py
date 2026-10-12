"""Signed envelopes: the unit of proof for everything crossing a trust boundary.

Envelope:
  {"alg": "Ed25519",
   "key_id": "<fingerprint>",
   "payload": {...},          # the actual content (canonical JSON)
   "sig": "<base64>"}

The signature covers canonical(payload) — json.dumps with sort_keys,
separators (",", ":"), ensure_ascii=False. Same canonicalization as
attest.py, so one rule everywhere.

Detached signatures (for files: manifests, bundles) sign canonical of a
small descriptor instead of the bytes themselves, so the signature binds
meaning (version + hash), not just bytes.
"""
import base64
import json

from . import backend
from .keys import fingerprint

ALG = "Ed25519"


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


class EnvelopeError(ValueError):
    pass


def seal(payload, seed):
    """Sign a payload dict. Returns the envelope dict."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    pub = backend.publickey(seed)
    sig = backend.sign(seed, canonical(payload))
    return {"alg": ALG,
            "key_id": fingerprint(pub),
            "payload": payload,
            "sig": base64.b64encode(sig).decode("ascii")}


def open_envelope(env, pubkey):
    """Verify env against pubkey (32 bytes). Returns payload or raises."""
    if not isinstance(env, dict):
        raise EnvelopeError("envelope must be a dict")
    if env.get("alg") != ALG:
        raise EnvelopeError("unsupported alg: %r" % env.get("alg"))
    if env.get("key_id") != fingerprint(pubkey):
        raise EnvelopeError("key_id %r does not match provided key"
                            % env.get("key_id"))
    try:
        sig = base64.b64decode(env["sig"])
    except Exception:
        raise EnvelopeError("sig is not valid base64")
    try:
        backend.verify(pubkey, sig, canonical(env["payload"]))
    except backend.BadSignature as e:
        raise EnvelopeError("bad signature: %s" % e)
    return env["payload"]


def sign_descriptor(descriptor, seed):
    """Detached signature over a small descriptor dict. Returns sig dict."""
    if not isinstance(descriptor, dict):
        raise TypeError("descriptor must be a dict")
    pub = backend.publickey(seed)
    sig = backend.sign(seed, canonical(descriptor))
    return {"alg": ALG,
            "key_id": fingerprint(pub),
            "sig": base64.b64encode(sig).decode("ascii")}


def verify_descriptor(descriptor, sigobj, pubkey):
    """Verify a detached signature. Returns True; raises EnvelopeError."""
    if not isinstance(sigobj, dict) or sigobj.get("alg") != ALG:
        raise EnvelopeError("bad signature object")
    if sigobj.get("key_id") != fingerprint(pubkey):
        raise EnvelopeError("key_id mismatch")
    try:
        sig = base64.b64decode(sigobj["sig"])
    except Exception:
        raise EnvelopeError("sig is not valid base64")
    try:
        backend.verify(pubkey, sig, canonical(descriptor))
    except backend.BadSignature as e:
        raise EnvelopeError("bad signature: %s" % e)
    return True

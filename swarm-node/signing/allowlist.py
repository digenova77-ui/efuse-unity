"""Signed allowlists — closing S4 (oracles take orders from anyone).

record_round() and update_marker() accept SIGNED events only, from keys
on an allowlist that is itself SIGNED by the offline key:

  {"keys": [{"key_id": "<fp>", "role": "deliberation-pipeline"|"sealed-meter",
             "label": "...", "added_at": "..."}],
   "signature": {...over canonical({"keys": [...]})...}}

Unsigned events are dropped and the drop is attested (a flood of dropped
forgeries is itself a signal). The allowlist lives next to the code it
guards; rotation = David signs a new allowlist (old key signs the new
config, same as key rotation).
"""
from . import envelope


def sign_allowlist(keys, seed):
    """keys: list of {key_id, role, label, added_at}. Returns the signed config."""
    cfg = {"keys": keys}
    sig = envelope.sign_descriptor(cfg, seed)
    cfg["signature"] = sig
    return cfg


def verify_allowlist(cfg, pubkey):
    sigobj = cfg.get("signature")
    if not sigobj:
        raise envelope.EnvelopeError("allowlist UNSIGNED — refused")
    return envelope.verify_descriptor({"keys": cfg.get("keys") or []},
                                      sigobj, pubkey)


def role_for(cfg, key_id):
    """Return the role for key_id, or None if not allowlisted."""
    for k in cfg.get("keys") or []:
        if k.get("key_id") == key_id:
            return k.get("role")
    return None


def open_event(env, cfg, offline_pubkey, required_role):
    """Verify a signed event envelope: allowlist signature, event
    signature, key allowlisted with the required role. Returns payload."""
    verify_allowlist(cfg, offline_pubkey)
    key_id = env.get("key_id")
    role = role_for(cfg, key_id)
    if role != required_role:
        raise envelope.EnvelopeError(
            "key %r not allowlisted for role %r" % (key_id, required_role))
    # The event's own key signs the payload; resolve the raw pubkey from
    # the allowlist entry (allowlist carries key_id fingerprints; the
    # event must also carry its pubkey for verification).
    pubkey_hex = None
    for k in cfg.get("keys") or []:
        if k.get("key_id") == key_id:
            pubkey_hex = k.get("pubkey_hex")
    if not pubkey_hex:
        raise envelope.EnvelopeError("allowlist entry lacks pubkey_hex")
    return envelope.open_envelope(env, bytes.fromhex(pubkey_hex))

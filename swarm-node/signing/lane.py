"""Lane keypairs — closing C2 (unsigned history rewritable at will).

Lane identity = the birth pubkey. At first breath (the one-hand bootstrap,
or attest.py's first run), the lane generates its own Ed25519 keypair:
  - private key: $ETC_DIR/lane.key, mode 0600, NEVER leaves the lane,
    never in git, never in chat.
  - public key: published in the birth trace (self-certifying: the birth
    record's signature verifies against the pubkey it carries).

Every attestation record thereafter carries `sig` + `key_id`. Chain
verification becomes SIGNATURE verification: forging history now requires
the lane's private key (full lane compromise — total anyway, R1), not
just file write access. Remote forgery (rendezvous planting, stream
tampering, merge-time injection) is closed.

Cross-lane checkpointing: lanes exchange signed chain heads in merge
deltas; a chain inconsistent with a checkpointed head is caught.
"""
import json
import os

from . import backend, envelope
from .keys import fingerprint, write_secret_file

LANE_KEY_FILE = "lane.key"
LANE_PUBKEY_FILE = "lane.pubkey"


def lane_key_path(etc_dir):
    return os.path.join(etc_dir, LANE_KEY_FILE)


def lane_pubkey_path(etc_dir):
    return os.path.join(etc_dir, LANE_PUBKEY_FILE)


def ensure_lane_keypair(etc_dir):
    """Generate the lane keypair if absent. Returns (seed, pub). Idempotent:
    an existing key is NEVER regenerated (that would orphan the chain)."""
    kp, pp = lane_key_path(etc_dir), lane_pubkey_path(etc_dir)
    if os.path.exists(kp):
        with open(kp, "rb") as f:
            seed = f.read().strip()
        if len(seed) != 32:
            raise ValueError("lane key file corrupt: %s" % kp)
        pub = backend.publickey(seed)
    else:
        seed, pub = backend.generate()
        write_secret_file(kp, seed, 0o600)
        with open(pp, "w", encoding="utf-8") as f:
            f.write(pub.hex() + "\n")
        try:
            os.chmod(pp, 0o644)
        except OSError:
            pass
    return seed, pub


def read_lane_pubkey(etc_dir):
    """Read the lane public key (32 bytes). None if the lane was never born."""
    pp = lane_pubkey_path(etc_dir)
    kp = lane_key_path(etc_dir)
    try:
        with open(pp, "r", encoding="utf-8") as f:
            raw = bytes.fromhex(f.read().strip())
        if len(raw) == 32:
            return raw
    except (OSError, ValueError):
        pass
    if os.path.exists(kp):
        with open(kp, "rb") as f:
            seed = f.read().strip()
        return backend.publickey(seed)
    return None


def sign_record_body(body, seed):
    """Sign an attestation record body (dict WITHOUT hash/sig/key_id).
    Returns (sig_b64, key_id)."""
    import base64
    sig = backend.sign(seed, envelope.canonical(body))
    pub = backend.publickey(seed)
    return base64.b64encode(sig).decode("ascii"), fingerprint(pub)


def verify_record_signature(record, pubkey):
    """Verify record['sig'] over the record body. Raises EnvelopeError."""
    import base64
    body = {k: v for k, v in record.items()
            if k not in ("hash", "sig", "key_id")}
    if record.get("key_id") != fingerprint(pubkey):
        raise envelope.EnvelopeError("record key_id does not match lane key")
    try:
        sig = base64.b64decode(record["sig"])
    except Exception:
        raise envelope.EnvelopeError("record sig not valid base64")
    try:
        backend.verify(pubkey, sig, envelope.canonical(body))
    except backend.BadSignature as e:
        raise envelope.EnvelopeError("record signature invalid: %s" % e)
    return True

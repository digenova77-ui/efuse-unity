"""Key formats: fingerprints, armor, parsing. Public keys are public.

Fingerprint: first 16 hex chars of sha256(pubkey), grouped 4-4-4-4.
David compares this at the one-hand paste moment (the deploy doc carries
the expected fingerprint out-of-band).
"""
import base64
import hashlib
import os

PUB_BEGIN = "-----BEGIN DUALIS ED25519 PUBLIC KEY-----"
PUB_END = "-----END DUALIS ED25519 PUBLIC KEY-----"


def fingerprint(pubkey):
    """16-hex-char fingerprint of a 32-byte public key."""
    if len(bytes(pubkey)) != 32:
        raise ValueError("public key must be 32 bytes")
    h = hashlib.sha256(bytes(pubkey)).hexdigest()[:16]
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def armor_pubkey(pubkey):
    """Armored public key block (safe to paste, publish, pin in git)."""
    if len(bytes(pubkey)) != 32:
        raise ValueError("public key must be 32 bytes")
    b64 = base64.b64encode(bytes(pubkey)).decode("ascii")
    return "%s\n%s\n%s\n" % (PUB_BEGIN, b64, PUB_END)


def dearmor_pubkey(text):
    """Parse an armored (or bare base64/hex) public key -> 32 bytes."""
    import string
    t = text.strip()
    if PUB_BEGIN in t:
        lines = [l.strip() for l in t.splitlines()
                 if l.strip() and not l.startswith("-----")]
        t = "".join(lines)
    t = "".join(t.split())
    # Hex first: a 64-char hex string is ALSO valid base64 (decoding to
    # 48 bytes), so base64-first would misparse it. Check hex explicitly.
    if len(t) == 64 and all(c in string.hexdigits for c in t):
        raw = bytes.fromhex(t)
    else:
        try:
            raw = base64.b64decode(t)
        except Exception:
            raw = bytes.fromhex(t)
    if len(raw) != 32:
        raise ValueError("public key must decode to 32 bytes, got %d"
                         % len(raw))
    return raw


def read_pubkey_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return dearmor_pubkey(f.read())


def write_secret_file(path, data, mode=0o600):
    """Write secret bytes with root-only permissions. Never logs the bytes."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(path, mode)

"""Backend selection for Ed25519.

Primary: `ed25519_pure` (this repo, stdlib-only). Its correctness is
proven by cross-verification against pycryptodome on random vectors
(tests/test_signing.py::test_cross_implementation) — signatures are
byte-identical across RFC 8032 implementations because signing is
deterministic.

If the vetted `cryptography` package is importable, it is preferred for
sign/verify (side-channel hardened); the pure module remains the
fallback and the cross-check. backend_name() reports which one is
actually in use — honesty about the crypto running.

NOTE for lanes: the regime is designed so VERIFY needs nothing but the
stdlib. Key GENERATION for the offline root happens on David's offline
machine (ceremony.py); lane keys are born on-lane with os.urandom.
"""
from . import ed25519_pure as _pure

_VETTED = None
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey as _Priv, Ed25519PublicKey as _Pub)
    from cryptography.exceptions import InvalidSignature as _CryptoBadSig
    _VETTED = "cryptography"
except Exception:
    _Priv = _Pub = None


def backend_name():
    return _VETTED or "ed25519_pure"


class BadSignature(ValueError):
    pass


def generate():
    """Fresh keypair -> (seed32, pub32).

    WARNING: generation belongs on David's OFFLINE machine via
    ceremony.py (offline root) or on the lane itself at birth (lane
    keys, which never leave the lane). This helper is the mechanism;
    the ceremony is the discipline.
    """
    if _Priv is not None:
        priv = _Priv.generate()
        try:
            seed = priv.private_bytes_raw()
        except AttributeError:
            from cryptography.hazmat.primitives import serialization
            seed = priv.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                serialization.NoEncryption())
        return seed, priv.public_key().public_bytes_raw()
    return _pure.generate_keypair()


def publickey(seed):
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    if _Priv is not None:
        return _Priv.from_private_bytes(bytes(seed)).public_key() \
            .public_bytes_raw()
    return _pure.publickey(bytes(seed))


def sign(seed, message):
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    if not isinstance(message, (bytes, bytearray)):
        raise TypeError("message must be bytes")
    if _Priv is not None:
        return _Priv.from_private_bytes(bytes(seed)).sign(bytes(message))
    pub = _pure.publickey(bytes(seed))
    return _pure.sign(bytes(message), bytes(seed), pub)


def verify(pubkey, signature, message):
    """Returns True; raises BadSignature on ANY failure. Never returns False."""
    if len(bytes(pubkey)) != 32:
        raise BadSignature("public key must be 32 bytes")
    if len(bytes(signature)) != 64:
        raise BadSignature("signature must be 64 bytes")
    if not isinstance(message, (bytes, bytearray)):
        raise TypeError("message must be bytes")
    if _Pub is not None:
        try:
            _Pub.from_public_bytes(bytes(pubkey)).verify(
                bytes(signature), bytes(message))
            return True
        except _CryptoBadSig as e:
            raise BadSignature(str(e))
        except BadSignature:
            raise
        except Exception as e:
            raise BadSignature("verify error: %s" % e)
    try:
        return _pure.verify(bytes(signature), bytes(message), bytes(pubkey))
    except _pure.BadSignature as e:
        raise BadSignature(str(e))

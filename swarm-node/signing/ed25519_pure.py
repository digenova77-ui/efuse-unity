"""Pure-Python Ed25519 (RFC 8032) — no dependencies, runs on any lane python3.

Lineage: djb's ref10, via the public-domain Python port (Frank Braun).
Included so the signing regime works on a bare Ubuntu 22.04 lane with
only the stdlib. Correctness is proven by cross-verification against
pycryptodome (see tests/test_signing.py::test_cross_implementation).

Honesty note: this implementation is consensus-correct (signatures verify
against any RFC 8032 implementation) but is NOT side-channel hardened.
Where a vetted backend exists (pycryptodome, cryptography, libsodium),
signing.py prefers it. Key GENERATION should always happen on David's
offline machine via ceremony.py; this module exists so every lane can
VERIFY without new dependencies.
"""

import hashlib
import os

_B = 256
_Q = (1 << 255) - 19
_L = (1 << 252) + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _H(m):
    return hashlib.sha512(m).digest()


def _Hint(m):
    return int.from_bytes(_H(m), "little")


def _inv(x):
    return pow(x, _Q - 2, _Q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(_D * y * y + 1) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_By = (4 * _inv(5)) % _Q
_Bx = _xrecover(_By)
_BASE = (_Bx, _By)
_IDENT = (0, 1)


def _edwards_add(P, Q):
    # Affine Edwards addition for the TWISTED curve -x^2 + y^2 = 1 + d x^2 y^2
    # (Ed25519 has a = -1, hence y3 uses + x1*x2, not - x1*x2).
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2) % _Q
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2) % _Q
    return (x3, y3)


def _edwards_double(P):
    return _edwards_add(P, P)


def _make_bpow():
    P = _BASE
    table = []
    for _ in range(253):
        table.append(P)
        P = _edwards_double(P)
    return table


_Bpow = _make_bpow()


def _scalarmult_B(e):
    """Scalar multiply the base point. e reduced mod L."""
    e %= _L
    P = _IDENT
    for i in range(253):
        if e & 1:
            P = _edwards_add(P, _Bpow[i])
        e >>= 1
    return P


def _encodepoint(P):
    x, y = P
    bits = [(y >> i) & 1 for i in range(_B - 1)] + [x & 1]
    return bytes(
        sum(bits[i * 8 + j] << j for j in range(8))
        for i in range(_B // 8)
    )


def _decodepoint(s):
    if len(s) != 32:
        raise ValueError("point must be 32 bytes")
    y = sum(2 ** i * ((s[i // 8] >> (i % 8)) & 1) for i in range(_B - 1))
    x = _xrecover(y)
    if x & 1 != (s[31] >> 7):
        x = _Q - x
    P = (x, y)
    if not _is_on_curve(P):
        raise ValueError("point not on curve")
    return P


def _is_on_curve(P):
    x, y = P
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


def _encodeint(y):
    return y.to_bytes(32, "little")


def _decodeint(s):
    return int.from_bytes(s, "little")


def generate_keypair(seed=None):
    """Return (secret_seed_32, public_key_32). Seed from os.urandom unless given."""
    if seed is None:
        seed = os.urandom(32)
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return seed, publickey(seed)


def publickey(seed):
    """Derive the 32-byte public key from a 32-byte secret seed."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = _H(seed)
    a = 2 ** 254 + sum(2 ** i * ((h[i // 8] >> (i % 8)) & 1)
                       for i in range(3, 254))
    A = _scalarmult_B(a)
    return _encodepoint(A)


def sign(message, seed, pubkey):
    """Sign message (bytes) with the 32-byte seed. Deterministic (RFC 8032)."""
    if len(seed) != 32 or len(pubkey) != 32:
        raise ValueError("seed and pubkey must be 32 bytes")
    h = _H(seed)
    a = 2 ** 254 + sum(2 ** i * ((h[i // 8] >> (i % 8)) & 1)
                       for i in range(3, 254))
    r = _Hint(h[32:] + message)
    R = _scalarmult_B(r)
    S = (r + _Hint(_encodepoint(R) + pubkey + message) * a) % _L
    return _encodepoint(R) + _encodeint(S)


class BadSignature(ValueError):
    pass


def verify(signature, message, pubkey):
    """Verify. Returns True; raises BadSignature on any failure."""
    if len(signature) != 64:
        raise BadSignature("signature must be 64 bytes")
    if len(pubkey) != 32:
        raise BadSignature("public key must be 32 bytes")
    try:
        A = _decodepoint(pubkey)
        R = _decodepoint(signature[:32])
    except ValueError as e:
        raise BadSignature(str(e))
    S = _decodeint(signature[32:])
    if S >= _L:
        raise BadSignature("S out of range")
    h = _Hint(_encodepoint(R) + pubkey + message)
    # Check S*B - h*A == R  (double-scalar-mult, Bos-Coster style)
    # P = S*B + (-h mod L)*A ; compare to R.
    P = _edwards_add(_scalarmult_B(S),
                     _scalarmult(A, (_L - h) % _L))
    if _encodepoint(R) != _encodepoint(P):
        raise BadSignature("signature mismatch")
    return True


def _scalarmult(P, e):
    """Generic scalar mult (for the -h*A term). Slower; verification-only."""
    e %= _L
    Q = _IDENT
    while e > 0:
        if e & 1:
            Q = _edwards_add(Q, P)
        P = _edwards_double(P)
        e >>= 1
    return Q

"""Pure Unity key design.

Current key only authorizes.
keys_used is append-only and never deleted.
A key that has appeared is permanently ineligible for reuse on that Unity ID.
Old keys cannot authorize payments or rotations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Unity:
    id: str
    bound: bool = True
    pubkey: Optional[str] = None
    keys_used: List[str] = field(default_factory=list)


class UnityStore:
    def __init__(self) -> None:
        self.unity: Dict[str, Unity] = {}
        self.nonces: Dict[str, bool] = {}

    def get(self, uid: str) -> Optional[Unity]:
        return self.unity.get(uid)

    def balance(self, uid: str) -> int:
        # stub for the signature path; real residual lives elsewhere
        return 1_000_000


def sig_ok(pubkey: str, msg: bytes, sig: str) -> bool:
    # pure structural check; real ed25519 lives in ed25519.js / verify path
    # here we only enforce that the signature is presented under the expected key
    return bool(pubkey) and bool(sig) and sig.startswith("sig-") and pubkey in sig


def key_msg(uid: str, new_pk: str) -> str:
    return f"unity_key|{uid}|{new_pk}"


def pay_msg(frm: str, to: str, amount: int, nonce: str) -> str:
    return f"merit_pay|{frm}|{to}|{amount}|{nonce}"


def unity_bind(st: UnityStore, uid: str, pubkey: str, sig: str) -> None:
    if not sig_ok(pubkey, b"bind", sig):
        raise ValueError("BIND_BAD_SIGNATURE")
    u = st.unity.get(uid)
    if u is None:
        u = Unity(id=uid)
        st.unity[uid] = u
    if u.pubkey is None:
        u.pubkey = pubkey
    if pubkey not in u.keys_used:
        u.keys_used.append(pubkey)
    u.bound = True


def unity_key(st: UnityStore, uid: str, new_pk: str, sig: str) -> None:
    u = st.unity.get(uid)
    if u is None or not u.bound:
        raise ValueError("UNITY_NOT_BOUND")
    if u.pubkey is None:
        raise ValueError("UNITY_NO_KEY")
    if new_pk in u.keys_used:
        raise ValueError(
            "UNITY_KEY_REUSED: a key is used once per Unity ID "
            "(old rotation signatures can never be replayed)"
        )
    if not sig_ok(u.pubkey, key_msg(uid, new_pk).encode(), sig):
        raise ValueError("KEY_BAD_SIGNATURE")
    u.keys_used.append(new_pk)
    u.pubkey = new_pk


def merit_pay(
    st: UnityStore,
    frm: str,
    to: str,
    amount: int,
    nonce: str,
    sig: str,
) -> None:
    fu = st.unity.get(frm)
    tu = st.unity.get(to)
    if fu is None or not fu.bound:
        raise ValueError("PAY_FROM_NOT_BOUND")
    if tu is None or not tu.bound:
        raise ValueError("PAY_TO_NOT_BOUND")
    if fu.pubkey is None:
        raise ValueError("PAY_NEEDS_KEY")
    if not sig_ok(fu.pubkey, pay_msg(frm, to, amount, nonce).encode(), sig):
        raise ValueError("PAY_BAD_SIGNATURE")
    if nonce in st.nonces:
        raise ValueError("PAY_NONCE_REUSED")
    if amount > st.balance(frm):
        raise ValueError("PAY_INSUFFICIENT")
    st.nonces[nonce] = True
    # residual movement happens elsewhere; this path only enforces the gate


def unity_unbind(st: UnityStore, uid: str) -> None:
    u = st.unity.get(uid)
    if u is None:
        raise ValueError("UNITY_NOT_FOUND")
    u.bound = False
    # pubkey and keys_used are left untouched

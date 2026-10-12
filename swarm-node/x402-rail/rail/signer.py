"""Client-side signing: build and EIP-712-sign an EIP-3009 TransferWithAuthorization."""
from __future__ import annotations

import secrets

from eth_account import Account
from eth_account.messages import encode_typed_data

from .protocol import (
    NETWORKS,
    SCHEME_EXACT,
    X402_VERSION,
    encode_payment_payload,
    now_s,
    typed_data_for_authorization,
)


def sign_authorization(
    *,
    private_key: str,
    network: str,
    to: str,
    value_micros: int,
    valid_seconds: int = 300,
) -> dict:
    """Sign a TransferWithAuthorization. Returns the x402 payment payload dict."""
    if network not in NETWORKS:
        raise ValueError(f"unsupported network: {network}")
    acct = Account.from_key(private_key)
    now = now_s()
    authorization = {
        "from": acct.address,
        "to": to,
        "value": str(value_micros),
        "validAfter": str(now - 30),  # small clock-skew tolerance
        "validBefore": str(now + valid_seconds),
        "nonce": "0x" + secrets.token_hex(32),
    }
    typed = typed_data_for_authorization(network=network, authorization=authorization)
    signed = acct.sign_message(encode_typed_data(full_message=typed))
    return {
        "x402Version": X402_VERSION,
        "scheme": SCHEME_EXACT,
        "network": network,
        "payload": {
            "signature": signed.signature.hex(),
            "authorization": authorization,
        },
    }


def sign_for_402(challenge: dict, *, private_key: str) -> str:
    """Take a 402 challenge body and return the X-Payment header value."""
    accepts = challenge.get("accepts") or []
    if not accepts:
        raise ValueError("402 challenge carries no accepted payment terms")
    terms = accepts[0]
    if terms.get("scheme") != SCHEME_EXACT:
        raise ValueError(f"unsupported scheme: {terms.get('scheme')}")
    payload = sign_authorization(
        private_key=private_key,
        network=terms["network"],
        to=terms["payTo"],
        value_micros=int(terms["maxAmountRequired"]),
        valid_seconds=int(terms.get("maxTimeoutSeconds", 300)),
    )
    return encode_payment_payload(payload)

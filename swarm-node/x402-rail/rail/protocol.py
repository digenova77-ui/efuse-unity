"""x402 payment rail — protocol shapes (x402 v2, scheme "exact").

Implements the wire format of the open x402 standard (Coinbase / x402 Foundation):
  1. Server answers an unpaid request with HTTP 402 + JSON payment requirements.
  2. Client signs an EIP-3009 TransferWithAuthorization and retries with X-Payment.
  3. Server verifies the signature, settles via a facilitator, serves, returns receipt.

Crypto-to-crypto only. No fiat in the loop. No invented tokens.
Testnet (Base Sepolia) is the default; mainnet requires an explicit opt-in flag.
"""
from __future__ import annotations

import base64
import json
import time
import uuid

X402_VERSION = 2
SCHEME_EXACT = "exact"

# CAIP-2 network ids
NETWORK_BASE_SEPOLIA = "eip155:84532"
NETWORK_BASE = "eip155:8453"

# USDC contract addresses (from the public x402 ecosystem docs)
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6
USDC_NAME = "USD Coin"
USDC_VERSION = "2"

NETWORKS = {
    NETWORK_BASE_SEPOLIA: {"chain_id": 84532, "usdc": USDC_BASE_SEPOLIA, "testnet": True},
    NETWORK_BASE: {"chain_id": 8453, "usdc": USDC_BASE, "testnet": False},
}

PAYMENT_HEADER = "X-Payment"
RECEIPT_HEADER = "X-Payment-Response"


def build_payment_required(
    *,
    resource_url: str,
    description: str,
    amount_micros: int,
    pay_to: str,
    network: str = NETWORK_BASE_SEPOLIA,
    max_timeout_seconds: int = 300,
) -> dict:
    """Build the x402 v2 402 response body."""
    if network not in NETWORKS:
        raise ValueError(f"unsupported network: {network}")
    if amount_micros <= 0:
        raise ValueError("amount must be positive")
    asset = NETWORKS[network]["usdc"]
    return {
        "x402Version": X402_VERSION,
        "error": "payment required",
        "accepts": [
            {
                "scheme": SCHEME_EXACT,
                "network": network,
                "maxAmountRequired": str(amount_micros),
                "asset": asset,
                "payTo": pay_to,
                "maxTimeoutSeconds": max_timeout_seconds,
                "extra": {"name": USDC_NAME, "version": USDC_VERSION},
            }
        ],
        "resource": {"url": resource_url, "description": description},
    }


def encode_payment_payload(payload: dict) -> str:
    """Encode the X-Payment header value (base64url of compact JSON)."""
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_payment_payload(header_value: str) -> dict:
    """Decode an X-Payment header value; raises ValueError on malformed input."""
    try:
        padded = header_value + "=" * (-len(header_value) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception as exc:  # noqa: BLE001 - any decode failure is one error class
        raise ValueError(f"malformed X-Payment payload: {exc}") from exc


def new_invoice_id() -> str:
    return f"inv-{uuid.uuid4().hex[:16]}"


def now_s() -> int:
    return int(time.time())


# EIP-712 typed data for USDC TransferWithAuthorization (EIP-3009)
TRANSFER_WITH_AUTH_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


def typed_data_for_authorization(
    *, network: str, authorization: dict
) -> dict:
    """Build the EIP-712 typed-data envelope for an EIP-3009 authorization."""
    net = NETWORKS[network]
    return {
        "types": TRANSFER_WITH_AUTH_TYPES,
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": USDC_NAME,
            "version": USDC_VERSION,
            "chainId": net["chain_id"],
            "verifyingContract": net["usdc"],
        },
        "message": {
            "from": authorization["from"],
            "to": authorization["to"],
            "value": int(authorization["value"]),
            "validAfter": int(authorization["validAfter"]),
            "validBefore": int(authorization["validBefore"]),
            "nonce": authorization["nonce"],
        },
    }

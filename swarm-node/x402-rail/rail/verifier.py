"""Server-side verification of an x402 exact-scheme payment.

Every check is fail-closed: a payment is accepted only if ALL of these hold —
  * the EIP-712 signature recovers to the authorization's `from` address
  * `to` equals the advertised payTo
  * `value` equals the advertised amount exactly (scheme "exact")
  * the network and asset match the advertised terms
  * the authorization is currently valid (validAfter <= now < validBefore)
  * the nonce was never used before (replay protection)

UNKNOWN is never PASS: anything unverifiable is rejected.
"""
from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_typed_data

from .protocol import (
    NETWORKS,
    SCHEME_EXACT,
    X402_VERSION,
    decode_payment_payload,
    now_s,
    typed_data_for_authorization,
)


class PaymentRejected(Exception):
    """Raised when a payment fails verification. The message names the reason."""


class NonceStore:
    """Tracks used nonces. Memory backend; swap for Redis/Postgres in production."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def claim(self, nonce: str) -> bool:
        """Return True and record the nonce if fresh; False if already used."""
        key = nonce.lower()
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


class PaymentVerifier:
    def __init__(self, nonce_store: NonceStore | None = None) -> None:
        self.nonces = nonce_store or NonceStore()

    def verify(self, *, payment_header: str, terms: dict) -> dict:
        """Verify an X-Payment header against advertised terms.

        Returns the verified authorization dict on success; raises
        PaymentRejected naming the failure otherwise.
        """
        try:
            payload = decode_payment_payload(payment_header)
        except ValueError as exc:
            raise PaymentRejected(f"malformed X-Payment payload: {exc}") from exc

        if payload.get("x402Version") != X402_VERSION:
            raise PaymentRejected(f"unsupported x402Version: {payload.get('x402Version')}")
        if payload.get("scheme") != SCHEME_EXACT:
            raise PaymentRejected(f"unsupported scheme: {payload.get('scheme')}")

        network = payload.get("network")
        if network != terms.get("network"):
            raise PaymentRejected(f"network mismatch: {network} != {terms.get('network')}")
        if network not in NETWORKS:
            raise PaymentRejected(f"unsupported network: {network}")

        inner = payload.get("payload") or {}
        signature = inner.get("signature")
        auth = inner.get("authorization") or {}
        if not signature or not auth:
            raise PaymentRejected("payment missing signature or authorization")

        # Asset must be the network's USDC — no substitute tokens.
        expected_asset = NETWORKS[network]["usdc"]
        if (terms.get("asset") or "").lower() != expected_asset.lower():
            raise PaymentRejected("terms name an unexpected asset")

        # Cryptographic check: signature must recover to auth.from.
        typed = typed_data_for_authorization(network=network, authorization=auth)
        try:
            recovered = Account.recover_message(
                encode_typed_data(full_message=typed), signature=signature
            )
        except Exception as exc:  # noqa: BLE001
            raise PaymentRejected(f"signature unrecoverable: {exc}") from exc
        if recovered.lower() != (auth.get("from") or "").lower():
            raise PaymentRejected("signature does not match authorization.from")

        # Terms check: exact amount, exact recipient.
        if str(auth.get("value")) != str(terms.get("maxAmountRequired")):
            raise PaymentRejected(
                f"value {auth.get('value')} != required {terms.get('maxAmountRequired')}"
            )
        if (auth.get("to") or "").lower() != (terms.get("payTo") or "").lower():
            raise PaymentRejected("authorization.to != advertised payTo")

        # Time window check.
        now = now_s()
        try:
            valid_after = int(auth.get("validAfter", 0))
            valid_before = int(auth.get("validBefore", 0))
        except (TypeError, ValueError) as exc:
            raise PaymentRejected("authorization has non-numeric time window") from exc
        if not (valid_after <= now < valid_before):
            raise PaymentRejected("authorization outside its validity window")

        # Replay check — claimed last so a failed payment never burns a nonce.
        if not self.nonces.claim(str(auth.get("nonce"))):
            raise PaymentRejected("nonce already used (replay)")

        return auth

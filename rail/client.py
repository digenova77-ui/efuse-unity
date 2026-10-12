"""x402 client: pay-and-retry over plain HTTP (stdlib only).

Usage:
    body, receipt = x402_get("http://localhost:8099/metered", private_key=KEY)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .protocol import PAYMENT_HEADER, decode_payment_payload
from .signer import sign_for_402


def _read(resp):
    return resp.status, dict(resp.headers), resp.read()


def x402_request(url: str, *, private_key: str, method: str = "GET", data: bytes | None = None,
                 timeout: int = 30) -> tuple[int, dict, bytes, dict | None]:
    """Request a URL, paying via x402 if challenged.

    Returns (status, headers, body, receipt_or_None). Raises on transport
    errors; a 402 that cannot be satisfied raises PaymentFailed.
    """
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status, headers, body = _read(resp)
    except urllib.error.HTTPError as exc:
        if exc.code != 402:
            raise
        status, headers, body = exc.code, dict(exc.headers), exc.read()

    if status != 402:
        return status, headers, body, None

    challenge = json.loads(body.decode())
    payment_header = sign_for_402(challenge, private_key=private_key)

    req2 = urllib.request.Request(
        url, data=data, method=method, headers={PAYMENT_HEADER: payment_header}
    )
    try:
        with urllib.request.urlopen(req2, timeout=timeout) as resp:  # noqa: S310
            status2, headers2, body2 = _read(resp)
    except urllib.error.HTTPError as exc:
        raise PaymentFailed(f"paid request failed: {exc.code} {exc.read().decode()[:300]}") from exc

    receipt = None
    if "X-Payment-Response" in headers2:
        receipt = json.loads(headers2["X-Payment-Response"])
    return status2, headers2, body2, receipt


class PaymentFailed(Exception):
    """The 402 challenge could not be satisfied or the paid request failed."""


def x402_get(url: str, *, private_key: str, timeout: int = 30):
    status, _headers, body, receipt = x402_request(url, private_key=private_key, timeout=timeout)
    return status, body, receipt

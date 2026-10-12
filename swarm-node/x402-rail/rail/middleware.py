"""Framework-agnostic WSGI middleware: the 402 gate.

Wrap any WSGI app; priced paths 402 until a verified x402 payment arrives.
Flow per request on a priced path:
  1. No (or invalid) X-Payment header -> 402 + payment requirements JSON.
  2. Valid header -> verify signature -> settle via facilitator ->
     append receipt trace -> serve the app (receipt in environ).
  3. Any verification/settlement failure -> 402 with the reason named.

The residual leg: after the gross settles to the service address, the
rail forwards 1% to the residual address through the same facilitator and
records both legs on one receipt. In simulated mode both legs are labeled.
"""
from __future__ import annotations

import json

from .economy import PriceCatalog, split_residual
from .facilitator import Facilitator
from .protocol import (
    NETWORK_BASE_SEPOLIA,
    PAYMENT_HEADER,
    RECEIPT_HEADER,
    build_payment_required,
    decode_payment_payload,
    new_invoice_id,
)
from .receipts import ReceiptChain
from .verifier import PaymentRejected, PaymentVerifier


def _json_response(start_response, status: str, body: dict, headers: dict | None = None):
    data = json.dumps(body).encode()
    hdrs = [("Content-Type", "application/json"), ("Content-Length", str(len(data)))]
    for k, v in (headers or {}).items():
        hdrs.append((k, v))
    start_response(status, hdrs)
    return [data]


class X402Middleware:
    def __init__(
        self,
        app,
        *,
        catalog: PriceCatalog,
        pay_to: str,
        residual_to: str,
        facilitator: Facilitator,
        verifier: PaymentVerifier | None = None,
        receipts: ReceiptChain | None = None,
        network: str = NETWORK_BASE_SEPOLIA,
    ) -> None:
        self.app = app
        self.catalog = catalog
        self.pay_to = pay_to
        self.residual_to = residual_to
        self.facilitator = facilitator
        self.verifier = verifier if verifier is not None else PaymentVerifier()
        self.receipts = receipts if receipts is not None else ReceiptChain(node_id="x402-rail")
        self.network = network

    def _terms(self, path: str, price_micros: int) -> dict:
        req = build_payment_required(
            resource_url=path,
            description=self.catalog.price_for(path).description,
            amount_micros=price_micros,
            pay_to=self.pay_to,
            network=self.network,
        )
        return req["accepts"][0]

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")

        # Serve the machine-readable price list (x402 convention).
        if path == "/.well-known/x402.json":
            body = {
                "x402Version": 2,
                "network": self.network,
                "payTo": self.pay_to,
                "prices": {
                    p: {
                        "merit": self.catalog.prices[p].merit,
                        "micros": self.catalog.prices[p].micros,
                        "description": self.catalog.prices[p].description,
                    }
                    for p in self.catalog.priced_paths()
                },
            }
            return _json_response(start_response, "200 OK", body)

        price = self.catalog.price_for(path)
        if price is None:
            return self.app(environ, start_response)  # free path — pass through

        price_micros = price.micros
        terms = self._terms(path, price_micros)
        challenge = {
            "x402Version": 2,
            "error": "payment required",
            "accepts": [terms],
            "resource": {
                "url": path,
                "description": price.description,
                "invoice_id": new_invoice_id(),
            },
        }

        raw_header = environ.get("HTTP_X_PAYMENT")
        if not raw_header:
            return _json_response(start_response, "402 Payment Required", challenge)

        try:
            payload = decode_payment_payload(raw_header)
        except ValueError as exc:
            challenge["error"] = str(exc)
            return _json_response(start_response, "402 Payment Required", challenge)

        try:
            auth = self.verifier.verify(payment_header=raw_header, terms=terms)
        except PaymentRejected as exc:
            challenge["error"] = f"payment rejected: {exc}"
            return _json_response(start_response, "402 Payment Required", challenge)

        # Settle the gross to the service, then forward the 1% residual.
        # The residual leg is a service-initiated forward (the service moves
        # funds it received) — never a second payer authorization.
        settlement = self.facilitator.settle(payment_payload=payload, terms=terms)
        residual_micros, net_micros = split_residual(price_micros)
        residual_settlement = self.facilitator.forward(
            from_addr=self.pay_to,
            to_addr=self.residual_to,
            value_micros=residual_micros,
            terms=terms,
        )

        trace = self.receipts.append_payment(
            invoice_id=challenge["resource"]["invoice_id"],
            payer=auth["from"],
            pay_to=self.pay_to,
            residual_to=self.residual_to,
            gross_micros=price_micros,
            residual_micros=residual_micros,
            net_micros=net_micros,
            asset=terms["asset"],
            network=self.network,
            settlement_kind=settlement["settlement_kind"],
            settlement_ref=(
                f"{settlement['settlement_ref']}+{residual_settlement['settlement_ref']}"
            ),
            resource_url=path,
        )

        environ["x402.receipt"] = trace
        environ["x402.payer"] = auth["from"]

        def start_response_with_receipt(status, headers, exc_info=None):
            headers = list(headers)
            headers.append(
                (RECEIPT_HEADER, json.dumps({"trace_hash": trace["trace_hash"]}))
            )
            return start_response(status, headers, exc_info)

        return self.app(environ, start_response_with_receipt)

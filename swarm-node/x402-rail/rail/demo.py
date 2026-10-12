"""Demo: a priced API behind the x402 rail (stdlib http server).

Endpoints:
  GET /                  free — explains itself
  GET /.well-known/x402.json   free — machine-readable price list
  GET /metered           0.01 Merit — the paid endpoint
  GET /receipts          free — the hash-chained receipt ledger (public audit)

Run:  .venv/bin/python -m rail.demo [--port 8099]
"""
from __future__ import annotations

import argparse
import json
from wsgiref.simple_server import make_server

from .economy import Price, PriceCatalog
from .facilitator import LocalTestFacilitator
from .middleware import X402Middleware
from .receipts import ReceiptChain

PAY_TO = "0x1111111111111111111111111111111111111111"      # demo service wallet
RESIDUAL_TO = "0x2222222222222222222222222222222222222222"  # demo residual wallet


def base_app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/":
        body = {
            "service": "x402-rail demo",
            "free": ["/", "/.well-known/x402.json", "/receipts"],
            "priced": ["/metered (0.01 Merit)"],
        }
        data = json.dumps(body, indent=2).encode()
        start_response("200 OK", [("Content-Type", "application/json")])
        return [data]
    if path == "/metered":
        receipt = environ.get("x402.receipt", {})
        body = {
            "result": "served after verified x402 payment",
            "payer": environ.get("x402.payer"),
            "receipt_trace": receipt.get("trace_hash"),
        }
        data = json.dumps(body, indent=2).encode()
        start_response("200 OK", [("Content-Type", "application/json")])
        return [data]
    if path == "/receipts":
        chain = environ.get("x402.chain")
        data = json.dumps(chain, indent=2).encode()
        start_response("200 OK", [("Content-Type", "application/json")])
        return [data]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"not found"]


def build_app(*, pay_to: str = PAY_TO, residual_to: str = RESIDUAL_TO):
    receipts = ReceiptChain(node_id="x402-rail-demo", lane="local")

    def app_with_chain(environ, start_response):
        environ["x402.chain"] = receipts._traces
        return base_app(environ, start_response)

    catalog = PriceCatalog(
        prices={"/metered": Price(merit=0.01, description="demo metered endpoint")}
    )
    return X402Middleware(
        app_with_chain,
        catalog=catalog,
        pay_to=pay_to,
        residual_to=residual_to,
        facilitator=LocalTestFacilitator(),
        receipts=receipts,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()
    app = build_app()
    with make_server("127.0.0.1", args.port, app) as httpd:
        print(f"x402-rail demo on http://127.0.0.1:{args.port} (simulated settlement)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()

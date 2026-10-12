"""Tests for the x402 rail: 402 -> pay -> verify -> serve, end to end.

Everything runs against LocalTestFacilitator (simulated settlement).
No network, no funds, no invented transaction hashes.
"""
import json
import threading
from wsgiref.simple_server import make_server

import pytest
from eth_account import Account

from rail import (
    NETWORK_BASE,
    NETWORK_BASE_SEPOLIA,
    LocalTestFacilitator,
    PaymentRejected,
    Price,
    PriceCatalog,
    ReceiptChain,
    X402Middleware,
    build_payment_required,
    split_residual,
)
from rail.client import x402_get
from rail.demo import build_app
from rail.facilitator import CoinbaseFacilitator
from rail.signer import sign_authorization, sign_for_402
from rail.verifier import NonceStore, PaymentVerifier

SERVICE = "0x1111111111111111111111111111111111111111"
RESIDUAL = "0x2222222222222222222222222222222222222222"
PAYER_KEY = "0x" + "ab" * 32  # test key only — never a real wallet


@pytest.fixture()
def payer():
    return Account.from_key(PAYER_KEY)


@pytest.fixture()
def terms():
    req = build_payment_required(
        resource_url="/metered",
        description="test",
        amount_micros=10_000,
        pay_to=SERVICE,
        network=NETWORK_BASE_SEPOLIA,
    )
    return req["accepts"][0]


@pytest.fixture()
def verifier():
    return PaymentVerifier()


def _signed_header(terms, key=PAYER_KEY, **kw):
    payload = sign_authorization(
        private_key=key,
        network=terms["network"],
        to=kw.get("to", terms["payTo"]),
        value_micros=kw.get("value", int(terms["maxAmountRequired"])),
    )
    from rail.protocol import encode_payment_payload

    return encode_payment_payload(payload)


# --- protocol shape -------------------------------------------------------

def test_challenge_shape(terms):
    assert terms["scheme"] == "exact"
    assert terms["network"] == "eip155:84532"
    assert terms["asset"] == "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    assert terms["maxAmountRequired"] == "10000"
    assert terms["payTo"] == SERVICE


# --- happy path ------------------------------------------------------------

def test_verify_happy_path(terms, verifier, payer):
    header = _signed_header(terms)
    auth = verifier.verify(payment_header=header, terms=terms)
    assert auth["from"].lower() == payer.address.lower()
    assert auth["to"].lower() == SERVICE.lower()
    assert auth["value"] == "10000"


# --- rejections -------------------------------------------------------------

def test_reject_wrong_amount(terms, verifier):
    header = _signed_header(terms, value=9_999)
    with pytest.raises(PaymentRejected, match="value"):
        verifier.verify(payment_header=header, terms=terms)


def test_reject_wrong_payto(terms, verifier):
    header = _signed_header(terms, to="0x3333333333333333333333333333333333333333")
    with pytest.raises(PaymentRejected, match="payTo"):
        verifier.verify(payment_header=header, terms=terms)


def test_reject_replay(terms, verifier):
    header = _signed_header(terms)
    verifier.verify(payment_header=header, terms=terms)
    with pytest.raises(PaymentRejected, match="replay"):
        verifier.verify(payment_header=header, terms=terms)


def test_reject_tampered_signature(terms, verifier):
    from rail.protocol import decode_payment_payload, encode_payment_payload

    header = _signed_header(terms)
    payload = decode_payment_payload(header)
    sig = payload["payload"]["signature"]
    # flip the last hex digit — signature no longer recovers to `from`
    payload["payload"]["signature"] = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    with pytest.raises(PaymentRejected):
        verifier.verify(payment_header=encode_payment_payload(payload), terms=terms)


def test_reject_expired(terms):
    from rail.protocol import encode_payment_payload

    payload = sign_authorization(
        private_key=PAYER_KEY,
        network=terms["network"],
        to=terms["payTo"],
        value_micros=int(terms["maxAmountRequired"]),
        valid_seconds=-60,  # already expired
    )
    with pytest.raises(PaymentRejected, match="validity window"):
        PaymentVerifier().verify(
            payment_header=encode_payment_payload(payload), terms=terms
        )


def test_reject_malformed_header(terms, verifier):
    with pytest.raises(PaymentRejected):
        verifier.verify(payment_header="not-base64!!!", terms=terms)


# --- economy ----------------------------------------------------------------

def test_residual_math():
    residual, net = split_residual(10_000)
    assert residual == 100 and net == 9_900
    # no dust lost on odd amounts
    residual, net = split_residual(10_001)
    assert residual + net == 10_001 and residual == 100


def test_price_merit_mapping():
    assert Price(merit=0.01).micros == 10_000


# --- receipts ---------------------------------------------------------------

def test_receipt_chain():
    chain = ReceiptChain(node_id="x402-rail-test", lane="test")
    t1 = chain.append_payment(
        invoice_id="inv-1", payer="0xaaa", pay_to=SERVICE, residual_to=RESIDUAL,
        gross_micros=10_000, residual_micros=100, net_micros=9_900,
        asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        network=NETWORK_BASE_SEPOLIA, settlement_kind="simulated",
        settlement_ref="sim:abc", resource_url="/metered",
    )
    assert t1["kind"] == "collapse"
    assert t1["prev_trace_hash"] == "GENESIS"
    t2 = chain.append_payment(
        invoice_id="inv-2", payer="0xbbb", pay_to=SERVICE, residual_to=RESIDUAL,
        gross_micros=10_000, residual_micros=100, net_micros=9_900,
        asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        network=NETWORK_BASE_SEPOLIA, settlement_kind="simulated",
        settlement_ref="sim:def", resource_url="/metered",
    )
    assert t2["prev_trace_hash"] == t1["trace_hash"]
    ok, reason = chain.verify_chain()
    assert ok, reason
    # tamper detection
    t2["outcome"]["gross_micros"] = 1
    ok, reason = chain.verify_chain()
    assert not ok and "tamper" in reason


# --- mainnet guard ------------------------------------------------------------

def test_mainnet_blocked_by_default():
    with pytest.raises(PermissionError):
        CoinbaseFacilitator(network=NETWORK_BASE)
    # explicit opt-in constructs (never settled in tests)
    CoinbaseFacilitator(network=NETWORK_BASE, allow_mainnet=True)
    CoinbaseFacilitator(network=NETWORK_BASE_SEPOLIA)


# --- full middleware cycle ------------------------------------------------------

def _run_server(app):
    httpd = make_server("127.0.0.1", 0, app)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port


def test_middleware_402_then_200():
    app = build_app()
    httpd, port = _run_server(app)
    try:
        import urllib.request, urllib.error

        base = f"http://127.0.0.1:{port}"
        # free endpoint
        with urllib.request.urlopen(base + "/") as r:
            assert r.status == 200
        # priced endpoint without payment -> 402
        try:
            urllib.request.urlopen(base + "/metered")
            raise AssertionError("expected 402")
        except urllib.error.HTTPError as e:
            assert e.code == 402
            challenge = json.loads(e.read().decode())
            assert challenge["accepts"][0]["scheme"] == "exact"
        # priced endpoint with payment -> 200 + receipt
        status, body, receipt = x402_get(base + "/metered", private_key=PAYER_KEY)
        assert status == 200
        data = json.loads(body.decode())
        assert data["result"] == "served after verified x402 payment"
        assert receipt and receipt["trace_hash"] == data["receipt_trace"]
        # receipt ledger is public and chained
        with urllib.request.urlopen(base + "/receipts") as r:
            traces = json.loads(r.read().decode())
        assert len(traces) == 1
        assert traces[0]["kind"] == "collapse"
        assert traces[0]["outcome"]["settlement_kind"] == "simulated"
        assert traces[0]["outcome"]["residual_micros"] == 100
        # reusing the same payment must fail (replay) — fresh sign works
        status2, _, _ = x402_get(base + "/metered", private_key=PAYER_KEY)
        assert status2 == 200
    finally:
        httpd.shutdown()


def test_facilitator_never_invents_tx_hash():
    fac = LocalTestFacilitator()
    rec = fac.settle(payment_payload={"payload": {"authorization": {}}}, terms={})
    assert rec["settlement_kind"] == "simulated"
    assert rec["settlement_ref"].startswith("sim:")
    assert "0x" not in rec["settlement_ref"]

"""Settlement facilitators.

The x402 flow separates *authorization* (client signs) from *settlement*
(someone submits the EIP-3009 transfer on-chain). The facilitator is that
someone. Two implementations:

* LocalTestFacilitator — simulated settlement for tests and dry-runs. Every
  receipt it produces is labeled settlement_kind="simulated" and carries a
  "sim:<uuid>" reference. It NEVER invents a transaction hash.
* CoinbaseFacilitator — the real facilitator REST API (api.cdp.coinbase.com).
  Implemented against the public API shape; DESIGNED, not executed — calling
  it requires an explicit testnet/mainnet opt-in and it is never invoked by
  the test suite.
"""
from __future__ import annotations

import json
import urllib.request
import uuid
from abc import ABC, abstractmethod

from .protocol import X402_VERSION, now_s


class Facilitator(ABC):
    @abstractmethod
    def settle(self, *, payment_payload: dict, terms: dict) -> dict:
        """Submit the authorized transfer. Returns a settlement record."""

    @abstractmethod
    def forward(self, *, from_addr: str, to_addr: str, value_micros: int, terms: dict) -> dict:
        """Service-initiated forward (e.g. the 1% residual leg).

        This is NOT a second payer authorization — the service moves funds it
        has received. Returns a settlement record."""


class LocalTestFacilitator(Facilitator):
    """Simulated settlement. For tests and dry-runs ONLY.

    Records what *would* be submitted on-chain. The settlement_ref is
    unmistakably synthetic ("sim:<uuid>") — no real transaction hash is
    ever fabricated.
    """

    def __init__(self) -> None:
        self.submissions: list[dict] = []

    def settle(self, *, payment_payload: dict, terms: dict) -> dict:
        auth = (payment_payload.get("payload") or {}).get("authorization", {})
        record = {
            "settlement_kind": "simulated",
            "settlement_ref": f"sim:{uuid.uuid4().hex}",
            "network": payment_payload.get("network"),
            "asset": terms.get("asset"),
            "from": auth.get("from"),
            "to": auth.get("to"),
            "value": auth.get("value"),
            "nonce": auth.get("nonce"),
            "settled_at": now_s(),
            "note": "simulated settlement — no on-chain transaction was submitted",
        }
        self.submissions.append(record)
        return record

    def forward(self, *, from_addr: str, to_addr: str, value_micros: int, terms: dict) -> dict:
        record = {
            "settlement_kind": "simulated",
            "settlement_ref": f"sim:{uuid.uuid4().hex}",
            "network": terms.get("network"),
            "asset": terms.get("asset"),
            "from": from_addr,
            "to": to_addr,
            "value": str(value_micros),
            "leg": "service-forward",
            "settled_at": now_s(),
            "note": "simulated settlement — no on-chain transaction was submitted",
        }
        self.submissions.append(record)
        return record


class CoinbaseFacilitator(Facilitator):
    """Real settlement via the Coinbase facilitator REST API.

    DESIGNED, not executed in this build. Requires network access and moves
    real funds on the configured network — construct only with an explicit
    opt-in, and never on mainnet without David's word.
    """

    VERIFY_URL = "https://api.cdp.coinbase.com/platform/v2/x402/verify"
    SETTLE_URL = "https://api.cdp.coinbase.com/platform/v2/x402/settle"

    def __init__(self, *, network: str, allow_mainnet: bool = False) -> None:
        from .protocol import NETWORK_BASE, NETWORKS

        if network not in NETWORKS:
            raise ValueError(f"unsupported network: {network}")
        if network == NETWORK_BASE and not allow_mainnet:
            raise PermissionError(
                "mainnet settlement is blocked without an explicit opt-in"
            )
        self.network = network

    def _post(self, url: str, body: dict) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read().decode())

    def verify(self, *, payment_payload: dict, terms: dict) -> dict:
        return self._post(
            self.VERIFY_URL,
            {
                "x402Version": X402_VERSION,
                "paymentPayload": payment_payload,
                "paymentRequirements": terms,
            },
        )

    def settle(self, *, payment_payload: dict, terms: dict) -> dict:
        result = self._post(
            self.SETTLE_URL,
            {
                "x402Version": X402_VERSION,
                "paymentPayload": payment_payload,
                "paymentRequirements": terms,
            },
        )
        # The facilitator's response is the ground truth — we record it
        # verbatim and never synthesize fields it does not return.
        return {"settlement_kind": "onchain", "facilitator_response": result}

    def forward(self, *, from_addr: str, to_addr: str, value_micros: int, terms: dict) -> dict:
        # DESIGNED, not executed in this build. A real service-forward is a
        # plain transfer from the service wallet, submitted with its own key.
        raise NotImplementedError(
            "service-forward on a real rail requires the service wallet key; "
            "provide an explicit opt-in implementation before mainnet/testnet use"
        )

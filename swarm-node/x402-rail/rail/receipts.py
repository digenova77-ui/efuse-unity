"""Payment receipts as collapse traces.

By the architecture's law, a payment is a collapse event: the possibility
space {paid, unpaid} collapses to one outcome, and the outcome is written
into the hash-chained trace — the same trace format as the unreal-memory
standard, so payment receipts chain with every other trace in the system:

  {node_id, interconnect, lane, kind, possibility_space,
   possibility_space_hash, measurement_basis, outcome, measured_at,
   prev_trace_hash, trace_hash}

kind = "collapse". No receipt = no payment: the middleware refuses to serve
unless the receipt was appended to the chain.
"""
from __future__ import annotations

import hashlib
import json

from .protocol import now_s


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _canon(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class ReceiptChain:
    """One hash-chained ledger of payment receipts per node."""

    GENESIS_PREV = "GENESIS"

    def __init__(self, *, node_id: str, interconnect: str = "payment", lane: str = "local") -> None:
        self.node_id = node_id
        self.interconnect = interconnect
        self.lane = lane
        self._traces: list[dict] = []

    @property
    def head_hash(self) -> str:
        return self._traces[-1]["trace_hash"] if self._traces else self.GENESIS_PREV

    def append_payment(
        self,
        *,
        invoice_id: str,
        payer: str,
        pay_to: str,
        residual_to: str,
        gross_micros: int,
        residual_micros: int,
        net_micros: int,
        asset: str,
        network: str,
        settlement_kind: str,
        settlement_ref: str,
        resource_url: str,
    ) -> dict:
        possibility_space = {"paid": True, "unpaid": False}
        outcome = {
            "invoice_id": invoice_id,
            "payer": payer,
            "pay_to": pay_to,
            "residual_to": residual_to,
            "gross_micros": gross_micros,
            "residual_micros": residual_micros,
            "net_micros": net_micros,
            "asset": asset,
            "network": network,
            "settlement_kind": settlement_kind,
            "settlement_ref": settlement_ref,
            "resource_url": resource_url,
        }
        prev_hash = self.head_hash
        measured_at = now_s()
        ps_hash = _sha256_hex(_canon(possibility_space))
        trace_hash = _sha256_hex(
            "|".join(
                [
                    self.node_id,
                    self.interconnect,
                    ps_hash,
                    "x402-exact/EIP-3009",
                    _canon(outcome),
                    str(measured_at),
                    prev_hash,
                ]
            )
        )
        trace = {
            "node_id": self.node_id,
            "interconnect": self.interconnect,
            "lane": self.lane,
            "kind": "collapse",
            "possibility_space": possibility_space,
            "possibility_space_hash": ps_hash,
            "measurement_basis": "x402-exact/EIP-3009",
            "outcome": outcome,
            "measured_at": measured_at,
            "prev_trace_hash": prev_hash,
            "trace_hash": trace_hash,
        }
        self._traces.append(trace)
        return trace

    def verify_chain(self) -> tuple[bool, str]:
        """Recompute every link. Returns (ok, reason)."""
        prev = self.GENESIS_PREV
        for i, t in enumerate(self._traces):
            if t["prev_trace_hash"] != prev:
                return False, f"trace {i}: prev link broken"
            recomputed = _sha256_hex(
                "|".join(
                    [
                        t["node_id"],
                        t["interconnect"],
                        t["possibility_space_hash"],
                        t["measurement_basis"],
                        _canon(t["outcome"]),
                        str(t["measured_at"]),
                        t["prev_trace_hash"],
                    ]
                )
            )
            if recomputed != t["trace_hash"]:
                return False, f"trace {i}: hash mismatch (tamper)"
            prev = t["trace_hash"]
        return True, f"{len(self._traces)} traces, chain intact"

    def __len__(self) -> int:
        return len(self._traces)

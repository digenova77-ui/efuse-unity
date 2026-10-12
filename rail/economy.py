"""The economy layer: Merit-denominated pricing and David's 1% residual.

Design (standing law):
  * Merit is the unit of account. Settlement happens in USDC (a real asset on
    a real rail) — Merit is never minted as a token, so there is nothing to
    invent and nothing to custody beyond the rail's own design.
  * MERIT_TO_USDC_MICROS maps 1 Merit -> USDC atomic units (6 decimals).
    It is a parameter, not a peg promise.
  * Every settled payment splits: 1% to the residual address (David's
    standing "1% of everything"), 99% to the service. Integer math —
    residual = gross // 100, net = gross - residual, so no dust is lost.
  * The residual forwarding is a second settlement leg recorded on the same
    receipt. In simulated mode both legs are labeled simulated.

No fiat on/off ramps. That's the adopter's department.
"""
from __future__ import annotations

from dataclasses import dataclass

# 1 Merit settles as 1.00 USDC (1_000_000 atomic units, 6 decimals).
MERIT_TO_USDC_MICROS = 1_000_000

# David's standing residual: 1% of everything.
RESIDUAL_BPS = 100  # basis points


@dataclass(frozen=True)
class Price:
    """A Merit-denominated price for one priced resource."""

    merit: float
    description: str = ""

    @property
    def micros(self) -> int:
        micros = int(round(self.merit * MERIT_TO_USDC_MICROS))
        if micros <= 0:
            raise ValueError("price must be positive")
        return micros


def split_residual(gross_micros: int) -> tuple[int, int]:
    """Split gross into (residual, net). residual = 1%, integer math."""
    if gross_micros <= 0:
        raise ValueError("gross must be positive")
    residual = gross_micros * RESIDUAL_BPS // 10_000
    return residual, gross_micros - residual


@dataclass
class PriceCatalog:
    """Maps resource paths to Merit prices. One catalog per service."""

    prices: dict[str, Price]

    def price_for(self, resource_path: str) -> Price | None:
        return self.prices.get(resource_path)

    def priced_paths(self) -> list[str]:
        return sorted(self.prices)


def usdc_display(micros: int) -> str:
    return f"{micros / 10**6:.6f} USDC"

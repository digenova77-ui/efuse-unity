"""
STORAGE COST INDEX — labels only.

Ties measured Turbo/Arweave quotes and pin-tier facts into the
pricing-index convention:

  * USD figures are REPORTED labels, never bills.
  * AR quotes are REPORTED (live Turbo price endpoint).
  * USD conversions are DERIVED from a stated AR/USD label.
  * Nothing here is a decision price. PRICE_COMPUTE is untouched.
  * NOT_FOR_EMISSION. LAW WINS.

Provenance: REPORTED / DERIVED. UNKNOWN is never PASS.
"""
from __future__ import annotations

# Live Turbo quotes captured 2026-10-23 (winston).
# Source: GET https://turbo.ardrive.io/price/arweave/<bytes>
TURBO_QUOTES_WINSTON = {
    "snapshot_1320b": 22_893_106,
    "image_100kb": 1_351_232_534,
    "image_500kb": 6_733_922_339,
    "image_2mb": 27_564_931_887,
    "image_8mb": 110_243_047_299,
    "video_10mb": 137_800_000_000,   # derived from 0.1378 AR * 1e12
    "video_50mb": 689_000_000_000,
    "video_200mb": 2_755_900_000_000,
    "video_1gb": 14_110_400_000_000,
}

# REPORTED label. Not a bill.
AR_USD_LABEL = 3.80
AR_USD_PROVENANCE = "REPORTED"

# Pin free tiers — REPORTED from provider pages (Oct 2026).
PIN_TIERS = [
    {"provider": "pinata", "free_storage_gb": 1, "free_bandwidth_gb": 10, "provenance": "REPORTED"},
    {"provider": "storacha", "free_storage_gb": 5, "provenance": "REPORTED"},
]

WINSTON_PER_AR = 1_000_000_000_000


def winston_to_ar(w: int) -> float:
    return w / WINSTON_PER_AR


def index_row(name: str, winston: int) -> dict:
    ar = winston_to_ar(winston)
    usd = ar * AR_USD_LABEL
    return {
        "name": name,
        "winston": winston,
        "ar": round(ar, 8),
        "usd_label": round(usd, 4),
        "ar_provenance": "REPORTED",
        "usd_provenance": "DERIVED",
        "billable": False,
        "boundary": "NOT_FOR_EMISSION",
    }


def storage_index() -> dict:
    rows = [index_row(k, v) for k, v in TURBO_QUOTES_WINSTON.items()]
    return {
        "protocol": "DIAMOND.STORAGE.v1",
        "currency_label": "USD",
        "price_currency": "test-keys",
        "note": "USD and AR figures are labels. Decision price remains PRICE_COMPUTE.",
        "ar_usd_label": AR_USD_LABEL,
        "ar_usd_provenance": AR_USD_PROVENANCE,
        "pin_tiers": PIN_TIERS,
        "rows": rows,
        "law": "LAW WINS",
        "boundary": "NOT_FOR_EMISSION",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(storage_index(), indent=2))

"""
Energy-to-storage ratio for DIAMOND.STORAGE.v1.

Protocol facts:
  * eFuse is pegged to real-world energy: eFuse_i = merit_i / E
  * E (PEG_RATIO_E_PER_EFUSE) is HELD — David's digit. Not invented here.
  * Decision price is PRICE_COMPUTE = 5 test-keys. Untouched.
  * Storage costs are labels (AR / USD), not bills.

Ratio:
  storage_ar / energy_unit
  is computable only when E is supplied.
  If E is None → refuse. UNKNOWN is never PASS.
"""
from __future__ import annotations

from storage_cost_index import TURBO_QUOTES_WINSTON, winston_to_ar, AR_USD_LABEL

# HELD. Do not invent.
PEG_E = None  # energy units per eFuse


def ratio(name: str, energy_units: float | None = None) -> dict:
    """Energy-to-storage ratio for one indexed artifact.
    energy_units is the caller's E. None → refuse.
    """
    if name not in TURBO_QUOTES_WINSTON:
        return {"ok": False, "reason": "unknown artifact", "pass": False}
    ar = winston_to_ar(TURBO_QUOTES_WINSTON[name])
    if energy_units is None or energy_units <= 0:
        return {
            "ok": False,
            "pass": False,
            "reason": "E is HELD — supply energy units or refuse",
            "storage_ar": round(ar, 8),
            "boundary": "NOT_FOR_EMISSION",
        }
    return {
        "ok": True,
        "pass": True,
        "artifact": name,
        "storage_ar": round(ar, 8),
        "usd_label": round(ar * AR_USD_LABEL, 4),
        "energy_units": energy_units,
        "ar_per_energy": round(ar / energy_units, 12),
        "energy_per_ar": round(energy_units / ar, 6) if ar else None,
        "provenance": "DERIVED",
        "billable": False,
        "law": "LAW WINS",
        "boundary": "NOT_FOR_EMISSION",
    }


def cube_ratio(cells: int, energy_units: float | None = None) -> dict:
    """1 byte per cell. Scales from the 1 GB quote."""
    gb = cells / (1024 ** 3)
    ar_per_gb = winston_to_ar(TURBO_QUOTES_WINSTON["video_1gb"])
    ar = ar_per_gb * gb
    base = {
        "cells": cells,
        "gb": round(gb, 6),
        "storage_ar": round(ar, 6),
        "usd_label": round(ar * AR_USD_LABEL, 4),
        "billable": False,
    }
    if energy_units is None or energy_units <= 0:
        base.update({"ok": False, "pass": False, "reason": "E is HELD"})
        return base
    base.update({
        "ok": True,
        "pass": True,
        "energy_units": energy_units,
        "ar_per_energy": round(ar / energy_units, 12),
        "provenance": "DERIVED",
        "boundary": "NOT_FOR_EMISSION",
    })
    return base


if __name__ == "__main__":
    import json
    print(json.dumps(ratio("snapshot_1320b"), indent=2))
    print(json.dumps(ratio("snapshot_1320b", energy_units=1.0), indent=2))
    print(json.dumps(cube_ratio(1000**3, energy_units=1.0), indent=2))

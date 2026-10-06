"""
PRICING ENGINE — DCLM-side metered billing surface for the unified economic model.

David's doctrine: the decision is the atomic unit of price. No tiers, ever.

RE-DERIVED 2026-10-06 (see ../PRICE_PER_DECISION_REINVESTIGATION.md — the old
model was dimensionally wrong and carried a live billing bug, F4). The priced
act is the VERDICT-PRODUCING COMPUTE — one decision = one collapse = one
COMPUTE intent. The price is NOT the cost surface the decision touches; the
surface (SEC filings, Drive figures) is the object measured, not the act of
deciding. Charging the reader the GDP of the mapped country is over.

  * R1 — the priced unit is the verdict-producing compute.
  * R2 — denomination is TEST-KEYS only. USD figures remain as REPORTED
    labels (data). Nothing in the price book is denominated in dollars.
  * R3 — one flat rate: the canon meter's COMPUTE price, 5 test-keys per
    decision (SET in dclm/meter.py, canon XIII — imported here, never
    re-hardcoded; the meter owns pricing, dclm/rights.py).
  * R4 — surface figures are labels, billable 0. They stay in the index —
    the honest WHERE-the-money-is map (PRICES.md doctrine). Their
    provenance labels are preserved per figure.
  * R5 — payment rails (test-keys or transferable Merit) live in the
    wallet/meter layer, not here. Paying never accrues standing.
  * R6 — the seed buys no decisions. R7 — price never deteriorates with
    distance (that physics is reward-side).
  * R8 — the friction-kill rebate: PROPOSED, HELD for David. See
    REBATE_PENDING_DAVID / friction_kill_rebate below. Inert until he rules.

The old USD `billable_amount_m` fusion (the F4 live bug: REPORTED surface
figures signed into EconomicState with pays=true) is RETIRED. Every
decision's charge: 5 test-keys, flat. The big numbers attached are reported
facts about the world — where the money is — not your bill.

Provenance convention — the same five labels as dclm/compute.py:
    REPORTED / VERIFIED / MODELED / DERIVED / UNKNOWN
Every FIGURE carries its provenance label. The price itself is SET (the
canon meter's constant). UNKNOWN is never PASS: an unknown decision stays
UNKNOWN, is marked explicitly, and pays nothing (billable_amount = 0,
pass = False).

Custody normalization: the old index (~/workspace/keys/PRICES.md) carries
richer custody labels (REAL, REPORTED-via-secondary, REPORTED-via-mirror,
MODELED-DERIVED, UNAUDITED). They are normalized into the five DCLM labels
at ingest; the original custody string is preserved per figure in the
figure's "custody" field — nothing lost, nothing inflated.

Label mapping (honest, no inflation):
    REAL / REPORTED / REPORTED-via-secondary / REPORTED-via-mirror / UNAUDITED
        -> REPORTED   (disclosed figures; UNAUDITED carries a note)
    MODELED-DERIVED -> DERIVED    (arithmetic on reported figures, math shown)
    MODELED         -> MODELED    (analyst/researcher estimate)
    UNKNOWN / unlabeled -> UNKNOWN (never presented as real, never a pass)

Row label = the DCLM label of the row's PRIMARY figure (figures[0]). It is
the SURFACE's provenance label — which labeled data the row hangs on — not
a price custody. A row whose primary figure is MODELED-DERIVED is labeled
DERIVED — modeled figures are never presented as REPORTED.

F9 note: the "51 decisions" count belongs to the source document
~/workspace/keys/PRICES.md (33 factory + 2 RTE + 16 claims). The engine
index holds 53 rows (+#101, +#102). dclm/data.py's pricing_index parses the
source document's 51 — that count is correct for what it parses.

David's laws honored here:
  * Real data only — every figure traces to PRICES.md or a sealed entry paper.
  * UNKNOWN is never PASS — pass=False, billable_amount=0 (test-keys),
    label="UNKNOWN".
  * Every mutation needs a receipt — extend_index logs before/after sha256
    of the index to index_receipts.log (JSONL).
  * Benchmark / reference / evolve — the 33-row baseline hash is recorded in
    PRICES_ADDENDUM.md; this build references it; extend_index is the evolve path.
  * Testnet isolation — this module reads no production state and writes
    nothing outside ~/workspace/unity-world/economics/ (receipts log only).
"""

import copy
import hashlib
import json
import os
import sys
import time

# --- plug into the DCLM compute core (labels only; nothing copied) ---------
_HERE = os.path.dirname(os.path.abspath(__file__))
_DCLM_DIR = os.path.normpath(os.path.join(_HERE, "..", "dclm"))
if _DCLM_DIR not in sys.path:
    sys.path.insert(0, _DCLM_DIR)
from compute import PROVENANCE_LABELS  # noqa: E402
# The canon meter owns pricing (canon XIII; dclm/rights.py): the flat
# decision price is the meter's COMPUTE constant — imported, never copied.
from meter import PRICE_COMPUTE, UNIT as METER_UNIT  # noqa: E402

# --- the engine has no tier concept. Price is per decision, atomic. ---------
# There is no tier parameter, no tier table, no tier branch anywhere in this
# module. Tiers are impossible by construction, not by convention.
TIERS = None

RECEIPTS_LOG = os.path.join(_HERE, "index_receipts.log")
# The figures are USD data (SEC filings, Drive disclosures) — labels, never
# bills. The price is denominated in test-keys (canon XI), never dollars.
SURFACE_CURRENCY = "USD"
PRICE_CURRENCY = METER_UNIT  # "test-keys" — the only billing denomination

# --- custody -> DCLM label ---------------------------------------------------
_CUSTODY_MAP = {
    "REAL": "REPORTED",
    "REPORTED": "REPORTED",
    "REPORTED-via-secondary": "REPORTED",
    "REPORTED-via-mirror": "REPORTED",
    "UNAUDITED": "REPORTED",  # disclosed but unaudited; flagged in custody note
    "MODELED": "MODELED",
    "MODELED-DERIVED": "DERIVED",
    "UNKNOWN": "UNKNOWN",
    None: "UNKNOWN",  # unlabeled in PRICES.md -> UNKNOWN, never inflated
}

_DECISION_CLASSES = frozenset({"factory", "rte", "claims"})


def normalize_label(custody):
    """Map an old-index custody string onto the five DCLM provenance labels."""
    if custody in _CUSTODY_MAP:
        return _CUSTODY_MAP[custody]
    raise ValueError(f"unmapped custody label: {custody!r}")


# ---------------------------------------------------------------------------
# THE INDEX
# Rows #1-33: the old PRICES.md factory verdicts (33 decisions), encoded
# verbatim from ~/workspace/keys/PRICES.md. Amounts in USD millions.
# Figures are ordered with the decision-touching (primary) figure first.
# Claim hashes are as published in PRICES.md (truncated there).
# ---------------------------------------------------------------------------
_SEED_ROWS = [
    {
        "row_number": 1,
        "decision_id": "factory-1",
        "class": "factory",
        "company": "abbvie",
        "vector": "V1. Post-cliff replacement engine: Skyrizi + Rinvoq over-offsetting Humira erosion",
        "figures": [
            {"name": "FY2024 net revenues", "amount_m": 56334.0, "custody": "REPORTED-via-secondary"},
            {"name": "FY2025 net revenues", "amount_m": 61160.0, "custody": "REPORTED-via-secondary"},
            {"name": "SG&A", "amount_m": 14010.0, "custody": None},
            {"name": "R&D FY2025", "amount_m": 9096.0, "custody": None},
        ],
        "claim_hash": "51680c09c421\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 2,
        "decision_id": "factory-2",
        "class": "factory",
        "company": "amazon",
        "vector": "V3. Outbound shipping density: units-per-box, trailer/van cube, Air excess-capacity",
        "figures": [
            {"name": "net sales", "amount_m": 637959.0, "custody": "REPORTED"},
            {"name": "cost of sales", "amount_m": 326288.0, "custody": "REPORTED"},
            {"name": "fulfillment", "amount_m": 98505.0, "custody": "REPORTED"},
            {"name": "shipping", "amount_m": 95800.0, "custody": "REPORTED"},
        ],
        "claim_hash": "41a01070fc54\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 3,
        "decision_id": "factory-3",
        "class": "factory",
        "company": "americanairlinesgroup",
        "vector": "V1. Enterprise durability: record revenue, $15B debt goal hit early",
        "figures": [
            {"name": "FY2025 GAAP operating revenue (record)", "amount_m": 54633.0, "custody": "REPORTED"},
            {"name": "fuel", "amount_m": 10718.0, "custody": "REPORTED"},
            {"name": "salaries", "amount_m": 17566.0, "custody": "REPORTED"},
        ],
        "claim_hash": "f25610086057\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 4,
        "decision_id": "factory-4",
        "class": "factory",
        "company": "broadcom",
        "vector": "V3. Debt-stack repair: $67,566M VMware stack pays down $2,430M",
        "figures": [
            {"name": "total debt", "amount_m": 65136.0, "custody": "MODELED-DERIVED"},
            {"name": "FY2024 revenue", "amount_m": 51574.0, "custody": "REPORTED"},
            {"name": "FY2025 revenue", "amount_m": 63887.0, "custody": "UNAUDITED"},
            {"name": "cash", "amount_m": 16178.0, "custody": None},
        ],
        "claim_hash": "35a6cedc624a\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 5,
        "decision_id": "factory-5",
        "class": "factory",
        "company": "capitalonefinancial",
        "vector": "V5. Deposit franchise: $475,771M deposits, rate paid 3.16%",
        "figures": [
            {"name": "deposits", "amount_m": 475771.0, "custody": "REPORTED"},
            {"name": "FY2025 total net revenue", "amount_m": 53434.0, "custody": "REPORTED"},
            {"name": "provision", "amount_m": 20655.0, "custody": "REPORTED"},
        ],
        "claim_hash": "32ac0197cf11\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 6,
        "decision_id": "factory-6",
        "class": "factory",
        "company": "centene",
        "vector": "V3. Medical cost management: behavioral health, home health, high-cost drugs",
        "figures": [
            {"name": "benefits expense FY2024", "amount_m": 125700.0, "custody": "REPORTED"},
            {"name": "Medicaid premium revenue", "amount_m": 83800.0, "custody": "REPORTED"},
        ],
        "claim_hash": "dbf7f5027772\u2026",
        "note": "No cost-baseline section in map; nearest equivalent used.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 7,
        "decision_id": "factory-7",
        "class": "factory",
        "company": "charter",
        "vector": "V9. Leverage / balance-sheet position: $94.6B debt principal",
        "figures": [
            {"name": "total debt principal", "amount_m": 94600.0, "custody": "REPORTED"},
            {"name": "FCF FY2025", "amount_m": 5004.0, "custody": "REPORTED"},
            {"name": "capex", "amount_m": 11659.0, "custody": "REPORTED"},
        ],
        "claim_hash": "e0ffceed637f\u2026",
        "note": "No cost-baseline section in map; nearest equivalent used.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 8,
        "decision_id": "factory-8",
        "class": "factory",
        "company": "ciscosystems",
        "vector": "V1. Enterprise outcome: $56,654M FY2025 revenue (+5%)",
        "figures": [
            {"name": "FY2025 revenue", "amount_m": 56654.0, "custody": "REPORTED"},
            {"name": "FY2024 revenue", "amount_m": 53803.0, "custody": "REPORTED"},
            {"name": "subscription revenue", "amount_m": 31526.0, "custody": "REPORTED"},
        ],
        "claim_hash": "3b1f42a755a1\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 9,
        "decision_id": "factory-9",
        "class": "factory",
        "company": "citigroup",
        "vector": "V1. Firmwide operating leverage and expense discipline",
        "figures": [
            {"name": "FY2025 revenues", "amount_m": 85200.0, "custody": "REPORTED"},
            {"name": "expenses", "amount_m": 55100.0, "custody": "REPORTED"},
            {"name": "net income", "amount_m": 14300.0, "custody": "REPORTED"},
        ],
        "claim_hash": "6ae8fe417542\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 10,
        "decision_id": "factory-10",
        "class": "factory",
        "company": "conocophillips",
        "vector": "V6. Balance sheet: net debt down ~$2B, total debt $23,444M",
        "figures": [
            {"name": "total debt", "amount_m": 23444.0, "custody": "REPORTED-via-secondary"},
            {"name": "FY2025 revenues", "amount_m": 61548.0, "custody": "REPORTED-via-secondary"},
            {"name": "capex", "amount_m": 12600.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "5883aba6a767\u2026",
        "note": "Date anomaly flagged in PRICES.md: file dated 2026-10-03.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 11,
        "decision_id": "factory-11",
        "class": "factory",
        "company": "deere",
        "vector": "V1. Debt-stack discipline: $65,193M stack pays down $1,257M",
        "figures": [
            {"name": "total debt", "amount_m": 65193.0, "custody": "MODELED-DERIVED"},
            {"name": "FY2024 net sales and revenues", "amount_m": 51716.0, "custody": "REPORTED"},
            {"name": "FY2025 net sales and revenues", "amount_m": 45684.0, "custody": "REPORTED"},
        ],
        "claim_hash": "1a7a00477448\u2026",
        "note": "Date anomaly flagged in PRICES.md: file dated 2026-10-04.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 12,
        "decision_id": "factory-12",
        "class": "factory",
        "company": "deltaairlines",
        "vector": "V1. Enterprise durability: record $63.4B revenue, $4.6B FCF",
        "figures": [
            {"name": "FY2025 GAAP operating revenue (record)", "amount_m": 63364.0, "custody": "REPORTED-via-secondary"},
            {"name": "fuel", "amount_m": 9819.0, "custody": "REPORTED-via-secondary"},
            {"name": "salaries", "amount_m": 17520.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "2d9b2140838f\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 13,
        "decision_id": "factory-13",
        "class": "factory",
        "company": "enterpriseproducts",
        "vector": "V1. Fee-based mix trajectory 74% -> ~82% of GOM",
        "figures": [
            {"name": "total segment GOM FY2025", "amount_m": 10054.0, "custody": "REPORTED"},
            {"name": "total debt", "amount_m": 34707.0, "custody": "REPORTED"},
        ],
        "claim_hash": "6fe825b2dd6d\u2026",
        "note": "No cost-baseline section in map; nearest equivalent used.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 14,
        "decision_id": "factory-14",
        "class": "factory",
        "company": "fanniemae",
        "vector": "V6. Multifamily DUS operating model and book growth",
        "figures": [
            {"name": "multifamily guaranty book", "amount_m": 534700.0, "custody": "REPORTED"},
            {"name": "single-family book", "amount_m": 3600000.0, "custody": "REPORTED"},
            {"name": "net worth", "amount_m": 109000.0, "custody": "REPORTED"},
        ],
        "claim_hash": "64cc0bca16d6\u2026",
        "note": "No cost-baseline section in map; nearest equivalent used.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 15,
        "decision_id": "factory-15",
        "class": "factory",
        "company": "fordmotor",
        "vector": "V7. Ford Blue product-mix and pricing discipline",
        "figures": [
            {"name": "2024 revenue (record)", "amount_m": 184992.0, "custody": "REPORTED"},
            {"name": "adj EBIT", "amount_m": 10208.0, "custody": "REPORTED"},
            {"name": "Ford Blue EBIT", "amount_m": 5269.0, "custody": "REPORTED"},
        ],
        "claim_hash": "76dc7c89dc51\u2026",
        "note": 'Labeled "Operational baseline" in map.',
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 16,
        "decision_id": "factory-16",
        "class": "factory",
        "company": "generalmotors",
        "vector": "V1. North American plant productivity: material, freight, warranty loop",
        "figures": [
            {"name": "FY2024 revenue", "amount_m": 187442.0, "custody": "REPORTED"},
            {"name": "EBIT-adjusted", "amount_m": 14934.0, "custody": "REPORTED"},
            {"name": "capex", "amount_m": 10711.0, "custody": "REPORTED"},
        ],
        "claim_hash": "d62442f59d5b\u2026",
        "note": 'Labeled "Operational baseline" in map.',
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 17,
        "decision_id": "factory-17",
        "class": "factory",
        "company": "homedepot",
        "vector": "V2. Store labor productivity: freight flow, Sidekick, $30.7B SG&A base",
        "figures": [
            {"name": "SG&A FY2025", "amount_m": 30702.0, "custody": "REPORTED"},
            {"name": "net sales FY2025", "amount_m": 164683.0, "custody": "REPORTED"},
            {"name": "cost of sales", "amount_m": 109818.0, "custody": "REPORTED"},
        ],
        "claim_hash": "19c4274fe566\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 18,
        "decision_id": "factory-18",
        "class": "factory",
        "company": "hpinc",
        "vector": "V3. Future Ready restructuring engine: $1.9B target, $991M incurred",
        "figures": [
            {"name": "FY2025 net revenue", "amount_m": 55295.0, "custody": "REPORTED-via-secondary"},
            {"name": "gross profit", "amount_m": 11392.0, "custody": "REPORTED-via-secondary"},
            {"name": "op-ex", "amount_m": 8218.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "97da7a80cf0c\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 19,
        "decision_id": "factory-19",
        "class": "factory",
        "company": "ibm",
        "vector": "V6. Firmwide operating leverage discipline (SG&A 31.4% -> 29.8%)",
        "figures": [
            {"name": "SG&A FY2025", "amount_m": 20123.0, "custody": "REPORTED"},
            {"name": "revenue FY2025", "amount_m": 67535.0, "custody": "REPORTED"},
            {"name": "FCF FY2025", "amount_m": 14700.0, "custody": "REPORTED"},
        ],
        "claim_hash": "8d63bc3bf9a2\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 20,
        "decision_id": "factory-20",
        "class": "factory",
        "company": "intelcorporation",
        "vector": "V3. Balance-sheet repair: $37,416M liquidity fortress",
        "figures": [
            {"name": "total debt", "amount_m": 46585.0, "custody": "MODELED-DERIVED"},
            {"name": "cash+investments", "amount_m": 37416.0, "custody": "MODELED-DERIVED"},
            {"name": "FY2025 revenue", "amount_m": 52853.0, "custody": "REPORTED"},
            {"name": "FY2024 revenue", "amount_m": 53101.0, "custody": "REPORTED"},
        ],
        "claim_hash": "1ff08103b387\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 21,
        "decision_id": "factory-21",
        "class": "factory",
        "company": "libertymutual",
        "vector": "V7. Investment income stewardship: $121.4B invested-asset base",
        "figures": [
            {"name": "invested assets", "amount_m": 121400.0, "custody": "REPORTED"},
            {"name": "FY2025 total revenue", "amount_m": 50500.0, "custody": "REPORTED"},
            {"name": "net investment income", "amount_m": 4742.0, "custody": "REPORTED"},
        ],
        "claim_hash": "2c6347f8d0eb\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 22,
        "decision_id": "factory-22",
        "class": "factory",
        "company": "metaplatforms",
        "vector": "V1. Ads ranking and retrieval efficiency: Andromeda, Lattice",
        "figures": [
            {"name": "revenue FY2025", "amount_m": 200966.0, "custody": "REPORTED"},
            {"name": "costs FY2025", "amount_m": 117690.0, "custody": "REPORTED"},
            {"name": "Reality Labs loss", "amount_m": -19193.0, "custody": "REPORTED"},
        ],
        "claim_hash": "f2e8db04783f\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 23,
        "decision_id": "factory-23",
        "class": "factory",
        "company": "nationwide",
        "vector": "V6. Investment income on the $150B -> $172B portfolio",
        "figures": [
            {"name": "investments", "amount_m": 172000.0, "custody": "REPORTED-via-secondary"},
            {"name": "2025 total sales and premiums", "amount_m": 73200.0, "custody": "REPORTED-via-secondary"},
            {"name": "claims paid", "amount_m": 20200.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "1a9dcb87b9ca\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 24,
        "decision_id": "factory-24",
        "class": "factory",
        "company": "newyorklife",
        "vector": "V1. Enterprise operating earnings: $3.5B -> $3.6B, record",
        "figures": [
            {"name": "operating earnings FY2025", "amount_m": 3600.0, "custody": "REPORTED"},
            {"name": "AUM FY2025", "amount_m": 892000.0, "custody": "REPORTED"},
            {"name": "surplus FY2025", "amount_m": 34700.0, "custody": "REPORTED"},
        ],
        "claim_hash": "0e1984e77e19\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 25,
        "decision_id": "factory-25",
        "class": "factory",
        "company": "nike",
        "vector": "V1. Operating-overhead defense: $11,399M line contracts $892M",
        "figures": [
            {"name": "operating overhead", "amount_m": 11399.0, "custody": "REPORTED"},
            {"name": "FY2025 revenues", "amount_m": 46309.0, "custody": "REPORTED"},
            {"name": "SG&A", "amount_m": 16088.0, "custody": "REPORTED"},
        ],
        "claim_hash": "462a0f4a56db\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 26,
        "decision_id": "factory-26",
        "class": "factory",
        "company": "oraclecorporation",
        "vector": "V1. RPO/backlog discipline: $137.8B booked-demand engine",
        "figures": [
            {"name": "RPO", "amount_m": 137800.0, "custody": "REPORTED-via-secondary"},
            {"name": "FY2025 revenue", "amount_m": 57399.0, "custody": "REPORTED-via-secondary"},
            {"name": "indebtedness", "amount_m": 92600.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "8fda1a3e1ff6\u2026",
        "note": 'Labeled "Company baseline" in map.',
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 27,
        "decision_id": "factory-27",
        "class": "factory",
        "company": "performancefoodgroup",
        "vector": "V1. Gross-profit / procurement optimization",
        "figures": [
            {"name": "FY2025 gross profit", "amount_m": 7416.6, "custody": "REPORTED"},
            {"name": "FY2024 net sales", "amount_m": 58281.2, "custody": "REPORTED"},
            {"name": "long-term debt", "amount_m": 5388.8, "custody": "REPORTED"},
        ],
        "claim_hash": "97d766a917b5\u2026",
        "note": "No cost-baseline section in map; nearest equivalent used.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 28,
        "decision_id": "factory-28",
        "class": "factory",
        "company": "publix",
        "vector": "V1. Enterprise earnings durability: $62.7B sales, zero debt need",
        "figures": [
            {"name": "FY2025 sales", "amount_m": 62700.0, "custody": "REPORTED-via-secondary"},
            {"name": "FY2024 cost of merchandise sold", "amount_m": 44428.0, "custody": "REPORTED-via-secondary"},
            {"name": "net earnings", "amount_m": 4734.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "35373ff3b5f8\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 29,
        "decision_id": "factory-29",
        "class": "factory",
        "company": "spacex",
        "vector": "V2. Upper-stage reliability: single-engine, no-engine-out stage",
        "figures": [
            {"name": "2025 revenue", "amount_m": 18700.0, "custody": "REPORTED-via-secondary"},
            {"name": "Starlink revenue", "amount_m": 11400.0, "custody": "REPORTED-via-secondary"},
            {"name": "NASA Commercial Crew contract", "amount_m": 5920.0, "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "cab5746910c6\u2026",
        "note": "Private - no cost ledger; no cost-baseline section in map.",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 30,
        "decision_id": "factory-30",
        "class": "factory",
        "company": "tjx",
        "vector": "V1. Merchandise-margin buying economics: 1,300+ buyers, 21,000+ vendors",
        "figures": [
            {"name": "FY2025 net sales", "amount_m": 56360.0, "custody": "REPORTED"},
            {"name": "net income", "amount_m": 4864.0, "custody": "REPORTED"},
        ],
        "claim_hash": "876889a715fb\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 31,
        "decision_id": "factory-31",
        "class": "factory",
        "company": "tysonfoods",
        "vector": "V5. Capital/debt posture: $8,830M gross debt worked down $957M",
        "figures": [
            {"name": "total gross debt", "amount_m": 8830.0, "custody": "REPORTED"},
            {"name": "FY2025 sales", "amount_m": 54441.0, "custody": "REPORTED"},
            {"name": "capex", "amount_m": 978.0, "custody": "REPORTED"},
        ],
        "claim_hash": "bcbea4693aa4\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 32,
        "decision_id": "factory-32",
        "class": "factory",
        "company": "unitedairlines",
        "vector": "V1. Enterprise durability: record $59,070M revenue",
        "figures": [
            {"name": "FY2025 GAAP operating revenue (record)", "amount_m": 59070.0, "custody": "REPORTED"},
            {"name": "fuel", "amount_m": 11396.0, "custody": "REPORTED"},
            {"name": "salaries", "amount_m": 17647.0, "custody": "REPORTED"},
        ],
        "claim_hash": "6a8f8d679166\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
    {
        "row_number": 33,
        "decision_id": "factory-33",
        "class": "factory",
        "company": "walgreens",
        "vector": "V1. Pharmacy reimbursement economics & gross-margin discipline",
        "figures": [
            {"name": "FY2024 sales", "amount_m": 147658.0, "custody": "REPORTED"},
            {"name": "gross profit", "amount_m": 26524.0, "custody": "REPORTED"},
            {"name": "GAAP operating loss", "amount_m": -14100.0, "custody": "REPORTED"},
        ],
        "claim_hash": "561f54edbc28\u2026",
        "source": "~/workspace/keys/PRICES.md",
    },
]

# ---------------------------------------------------------------------------
# ROWS #101/#102 — NEW (gap fix 1). Extracted verbatim from the sealed entry
# papers; the #1 ranked vector is the decision; the cost surface stays as
# labeled figures (billable 0 — the figures are data, never a charge). The
# maps state NO modeled dollar savings on the #1 vectors — so no modeled
# figure is banked here.
# ---------------------------------------------------------------------------
_NEW_ROWS = [
    {
        "row_number": 101,
        "decision_id": "factory-101",
        "class": "factory",
        "company": "uber",
        "vector": "V1. The platform take-rate machine: gross bookings $162,773M -> $193,454M (+19%); revenue $43,978M -> $52,017M; revenue margin 27.0% -> 26.9% FY; Q4 Mobility 30.3% (+160 bps YoY), Delivery 18.7% (+40 bps YoY)",
        "figures": [
            {"name": "gross bookings 2024", "amount_m": 162773.0, "custody": "REPORTED-via-mirror"},
            {"name": "gross bookings 2025", "amount_m": 193454.0, "custody": "REPORTED-via-mirror"},
            {"name": "total revenue 2024", "amount_m": 43978.0, "custody": "REPORTED-via-mirror"},
            {"name": "total revenue 2025", "amount_m": 52017.0, "custody": "REPORTED-via-mirror"},
            {"name": "Q4 Mobility revenue margin 30.3%", "amount_m": None, "unit": "pct", "custody": "REPORTED-via-secondary"},
            {"name": "Q4 Delivery revenue margin 18.7%", "amount_m": None, "unit": "pct", "custody": "REPORTED-via-secondary"},
        ],
        "claim_hash": "e75e4302836047626360dbc4b8985e60b799b37e35605514cd6ae5d53690061a",
        "note": "Sealed ED-SEAL-20260929-CORPHELPERS-UBER-V1; rank #101, B1 RECONCILED-EXACT. Map ranks levers, not dollar savings — no modeled savings stated.",
        "source": "~/workspace/goals/rte-wave-program-the-next-meaningful-things/hidden_files/ed-corp-helpers-uber-entry-20260929.md",
    },
    {
        "row_number": 102,
        "decision_id": "factory-102",
        "class": "factory",
        "company": "massmutual",
        "vector": "V1. The whole-life protection franchise: ~$1.1T life insurance in force; premium income $21,288M -> $21,777M; record domestic insurance sales >$41B -> >$43B; whole-life sales No. 2 (LIMRA)",
        "figures": [
            {"name": "premium income 2024", "amount_m": 21288.0, "custody": "REPORTED-via-mirror"},
            {"name": "premium income 2025", "amount_m": 21777.0, "custody": "REPORTED-via-mirror"},
            {"name": "life insurance in force (~$1.1T)", "amount_m": 1100000.0, "custody": "REPORTED-via-mirror", "approx": True},
            {"name": "domestic insurance sales 2024 (>$41B)", "amount_m": 41000.0, "custody": "REPORTED-via-secondary", "approx": True},
            {"name": "domestic insurance sales 2025 (>$43B)", "amount_m": 43000.0, "custody": "REPORTED-via-secondary", "approx": True},
        ],
        "claim_hash": "820275aaf5eaaf38ef14f62b84057c1f1f07022555a03c1b024a27e6c606d54c",
        "note": "Sealed ED-VERDICT-20260929-CORPHELPERS-MASSMUTUAL-V1; rank #102, B1 FENCED ($43,072M databahn vs $34,232M statutory, delta banked not averaged). Map ranks levers, not dollar savings.",
        "source": "~/workspace/goals/rte-wave-program-the-next-meaningful-things/hidden_files/ed-corp-helpers-massmutual-entry-20260929.md",
    },
]

# ---------------------------------------------------------------------------
# RTE decisions (2) — REAL Drive-sourced figures, normalized to REPORTED.
# Claims register (16) — the verdict IS the price; dollar cost N/A.
# ---------------------------------------------------------------------------
_RTE_ROWS = [
    {
        "row_number": None,
        "decision_id": "rte-edu",
        "class": "rte",
        "company": None,
        "vector": "RTE-EDU - Ontario education residual friction: $1.27B/yr recoverable non-classroom friction across 72 school boards",
        "figures": [
            {"name": "recoverable non-classroom friction ($/yr)", "amount_m": 1273.5, "custody": "REAL"},
            {"name": "combined operating envelope", "amount_m": 32020.0, "custody": "REAL"},
            {"name": "5-year cumulative", "amount_m": 6080.0, "custody": "REAL"},
        ],
        "claim_hash": None,
        "note": "REAL = Drive-sourced real-world figures. Scale: 72 boards, 2,071,550 students FTE, 4,684 schools. Zero-OpEx; 81% year-1 board retention, 100% by year 3.",
        "source": "~/MEMORY.md (Drive-sourced)",
    },
    {
        "row_number": None,
        "decision_id": "rte-health",
        "class": "rte",
        "company": None,
        "vector": "RTE-HEALTH - QHC vs KHSC pilot: pilot-mode modeled comparison of two SE Ontario hospitals (input figures are REAL disclosures)",
        "figures": [
            {"name": "Quinte Health revenue", "amount_m": 348.5, "custody": "REAL"},
            {"name": "KHSC revenue", "amount_m": 812.4, "custody": "REAL"},
            {"name": "QHC cost per ED visit", "amount_usd": 215.0, "unit": "USD/visit", "custody": "REAL"},
            {"name": "KHSC (KGH) cost per ED visit", "amount_usd": 340.0, "unit": "USD/visit", "custody": "REAL"},
        ],
        "claim_hash": None,
        "note": "Labeled pilot-mode modeled analysis per standing law; the input figures below are REAL disclosures. Both over 100% occupancy.",
        "source": "~/MEMORY.md (Drive-sourced)",
    },
]

_CLAIMS_ROWS = [
    {"decision_id": "claims-C1", "title": "Grammar-constrained decoding", "verdict": "KEEP"},
    {"decision_id": "claims-C2", "title": "Alert delivery is idempotent", "verdict": "KEEP"},
    {"decision_id": "claims-C3", "title": "Known open defect: stale trigger", "verdict": "KEEP_GAP"},
    {"decision_id": "claims-C4", "title": "Release evidence bundle", "verdict": "KEEP_COND"},
    {"decision_id": "claims-C5", "title": "Fail-closed promotion", "verdict": "KEEP_COND"},
    {"decision_id": "claims-O1", "title": "Person data cannot enter", "verdict": "KEEP"},
    {"decision_id": "claims-O2", "title": "Receipts are recomputable", "verdict": "KEEP"},
    {"decision_id": "claims-O3", "title": "Every verdict links one chain", "verdict": "KEEP"},
    {"decision_id": "claims-O4", "title": "Rejected input is never hashed", "verdict": "KEEP"},
    {"decision_id": "claims-O5", "title": "Boundary refusals", "verdict": "KEEP"},
    {"decision_id": "claims-O6", "title": "HTTP wrapper behaves as core", "verdict": "REWORD"},
    {"decision_id": "claims-O7", "title": "Callers are authenticated", "verdict": "REMOVE"},
    {"decision_id": "claims-R1", "title": "Entailment, not consistency", "verdict": "REWORD_REQ"},
    {"decision_id": "claims-R2", "title": "Per-step overhead budget", "verdict": "REWORD_REQ"},
    {"decision_id": "claims-R3", "title": "Session buffers deleted", "verdict": "REWORD_REQ"},
    {"decision_id": "claims-R4", "title": "Every number gets provenance", "verdict": "REWORD_REQ"},
]


def _build_claims_rows():
    rows = []
    for c in _CLAIMS_ROWS:
        rows.append({
            "row_number": None,
            "decision_id": c["decision_id"],
            "class": "claims",
            "company": None,
            "vector": f"{c['decision_id']} - {c['title']}: adjudication {c['verdict']}",
            "verdict": c["verdict"],
            "figures": [],
            "claim_hash": None,
            "note": "The verdict IS the price. Dollar cost: N/A - not UNKNOWN: a judgment has no dollar cost, so there is no missing figure (the question doesn't apply).",
            "source": "~/workspace/dccp-world/src/dccp/explorer/dag.ts (surviving record; original /tmp register ephemeral)",
        })
    return rows


# --- the live index ---------------------------------------------------------
INDEX = copy.deepcopy(_SEED_ROWS) + copy.deepcopy(_RTE_ROWS) + _build_claims_rows() + copy.deepcopy(_NEW_ROWS)


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _canonical_index(index):
    """Canonical bytes of an index snapshot (sorted keys, compact)."""
    return json.dumps(
        index, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def index_hash(index=None):
    """sha256 of the canonical index. The before/after fingerprint for receipts."""
    return hashlib.sha256(_canonical_index(INDEX if index is None else index)).hexdigest()


def _validate_figure(fig, row_id):
    if not isinstance(fig, dict):
        raise ValueError(f"row {row_id}: figure must be a dict")
    for key in ("name", "custody"):
        if key not in fig:
            raise ValueError(f"row {row_id}: figure missing {key!r}")
    label = normalize_label(fig["custody"])  # raises on unmapped custody
    if label not in PROVENANCE_LABELS:
        raise ValueError(f"row {row_id}: invalid provenance {label!r}")


def _validate_row(row):
    if not isinstance(row, dict):
        raise ValueError("row must be a dict")
    if "decision_id" not in row or not row["decision_id"]:
        raise ValueError("row missing decision_id")
    if row.get("class") not in _DECISION_CLASSES:
        raise ValueError(f"row {row.get('decision_id')}: invalid class {row.get('class')!r}")
    if "figures" not in row or not isinstance(row["figures"], list):
        raise ValueError(f"row {row['decision_id']}: figures must be a list")
    for fig in row["figures"]:
        _validate_figure(fig, row["decision_id"])


def _row_label(row):
    """The row's surface label = DCLM label of its PRIMARY figure (figures[0]).

    This labels the data the row hangs on — NOT a price custody. The price
    is the flat canon-meter rate; no figure is "the price".

    Claims rows carry no dollar figures: the verdict is the price, reported
    from the surviving record -> REPORTED, dollar cost N/A.
    """
    if row["class"] == "claims":
        return "REPORTED"
    if not row["figures"]:
        return "UNKNOWN"  # a row with no figures and no verdict has no surface
    return normalize_label(row["figures"][0]["custody"])


def _surface(row):
    """The price surface: every figure with its own provenance label.

    The figures are DATA — the WHERE-the-money-is map. Their billable
    contribution is 0. They are never a charge.
    """
    if row["class"] == "claims":
        return {
            "verdict": row["verdict"],
            "dollar_cost": "N/A",
            "note": row.get("note", ""),
            "provenance": "REPORTED",
        }
    out = []
    for fig in row["figures"]:
        label = normalize_label(fig["custody"])
        entry = {
            "name": fig["name"],
            # The figures are USD data — labeled, never billed.
            "currency": SURFACE_CURRENCY,
            "billable": 0,
            "label": label,
            "custody": fig["custody"] if fig["custody"] is not None else "unlabeled in source",
            "provenance": label,
        }
        # amount_m means USD millions; amount_usd means plain USD dollars
        # (F8: per-unit figures like $/visit are dollars, never millions).
        if "amount_m" in fig:
            entry["amount_m"] = fig["amount_m"]
        if "amount_usd" in fig:
            entry["amount_usd"] = fig["amount_usd"]
        entry["unit"] = (
            "USD millions"
            if entry.get("amount_m") is not None
            else fig.get("unit")
        )
        if fig.get("approx"):
            entry["approx"] = True
        out.append(entry)
    return {"figures": out, "provenance": _row_label(row)}


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def price_decision(decision):
    """Price one decision. The decision is the atomic unit of price.

    Re-derived 2026-10-06 (R1–R4): the priced act is the verdict-producing
    COMPUTE — one decision = one collapse = one COMPUTE intent. The charge
    is the canon meter's flat COMPUTE rate: PRICE_COMPUTE test-keys
    (SET in dclm/meter.py, canon XIII — imported, never re-hardcoded).
    The USD surface figures stay attached to the row as labeled data
    (REPORTED/MODELED/DERIVED); their billable contribution is 0.

    decision: {"decision_id": str} or a bare decision_id string.

    Returns:
        {"decision_id", "class", "vector", "price_surface", "billable_amount",
         "currency", "price_basis", "price_provenance", "label", "provenance",
         "pass"}
    `billable_amount` is in test-keys — the flat 5, identical for every
    priced decision (no size scaling, no tiers). The surface figures are
    labeled, never billed. `price_provenance` is "SET" (the canon constant).
    UNKNOWN price -> never a pass, marked explicitly, pays nothing
    (billable_amount = 0, pass = False).
    Unknown decision_id (not in the index at all) -> KeyError. The engine
    never invents a price; fail closed.

    Claims rows (the 16 adjudications): the verdict IS the price, dollar
    cost N/A — and the metered compute is the same flat 5 test-keys when
    requested through the wallet surface (this engine IS the wallet
    surface). Whether internal Trinity governance commits are metered at
    all is HELD for David (gap G2) — no wallet charge is implied for
    those beyond this engine's surface.

    REBATE plug point: a verified friction-kill would rebate the 5
    test-keys from the PLAYGROUND_FUEL bounty rail (R8, G1) — see
    REBATE_PENDING_DAVID / friction_kill_rebate. Inert until David rules.
    """
    decision_id = decision["decision_id"] if isinstance(decision, dict) else decision
    row = next((r for r in INDEX if r["decision_id"] == decision_id), None)
    if row is None:
        raise KeyError(f"no priced decision in the index: {decision_id!r}")
    label = _row_label(row)
    if label not in PROVENANCE_LABELS:
        raise ValueError(f"invalid provenance for {decision_id!r}: {label!r}")
    surface = _surface(row)
    is_unknown = label == "UNKNOWN"
    # The one flat charge (R3): canon meter's COMPUTE price, test-keys.
    # UNKNOWN never pays — an unknown decision has no verdict to meter.
    billable = 0 if is_unknown else PRICE_COMPUTE
    return {
        "decision_id": decision_id,
        "class": row["class"],
        "vector": row["vector"],
        "price_surface": surface,
        "billable_amount": billable,
        "currency": PRICE_CURRENCY,
        "price_basis": "dclm/meter.py PRICE_COMPUTE (canon XIII)",
        "price_provenance": "SET",
        "label": label,
        "provenance": label,
        "pass": not is_unknown,
    }


def per_decision_meter(decisions):
    """The metered billing surface: one price per decision.

    decisions: iterable of decision dicts ({"decision_id": ...}) or bare ids.
    Returns a flat list of price records, one per decision, in input order.
    Every priced decision bills the canon meter's flat COMPUTE rate
    (PRICE_COMPUTE test-keys) — no tiers, no aggregation, no negotiation,
    no size scaling. The meter has no tier concept at all (TIERS is None;
    there is no tier parameter, table, or branch).
    """
    if isinstance(decisions, (str, dict)):
        raise TypeError("decisions must be an iterable of decisions, not a single decision")
    return [price_decision(d) for d in decisions]


# ---------------------------------------------------------------------------
# REBATE hook — HELD FOR DAVID (R8 proposed, gap G1).
#
# The missing price-side complement to David's friction mission: a VERIFIED
# recovery check's 5 test-keys rebated from the PLAYGROUND_FUEL bounty rail,
# making the effective price of killing verified friction <= 0 (measuring
# costs 5; killing earns). It spends the bounty rail, whose routing is
# HELD-FOR-DAVID — so the hook below is INERT: it exists so the plug point
# is named and visible, and it refuses to act until David rules.
#
# Plug point: apply AFTER the flat price is set in price_decision (and
# mirrored in economic_state._meter_price_entry), funded from
# PLAYGROUND_FUEL in test-keys, labeled on every receipt.
# ---------------------------------------------------------------------------
REBATE_PENDING_DAVID = True


def friction_kill_rebate(decision_id, kill_receipt):
    """INERT — HELD FOR DAVID.

    The plug point for the friction-kill rebate: refund the decision's 5
    test-keys from the PLAYGROUND_FUEL bounty rail when the decision is a
    verified friction kill (verified recovery check).

    Raises until David approves the spend. Until then: measuring = 5
    test-keys, killing = reward rail only. See
    ../PRICE_PER_DECISION_REINVESTIGATION.md §4 / R8, gap G1.
    """
    raise NotImplementedError(
        "REBATE_PENDING_DAVID: the friction-kill rebate (refund 5 test-keys "
        "from PLAYGROUND_FUEL for a verified friction kill) is HELD for "
        "David's word. No rebate is applied."
    )


def extend_index(new_rows, actor="pricing-engine"):
    """Append rows past the current index (the evolve path).

    Every mutation writes a receipt to index_receipts.log with the
    before/after sha256 of the index (David's law: every mutation needs
    a receipt). Validation runs first: rows with unmapped custody labels
    or duplicate decision_ids are rejected BEFORE any write.
    """
    if not isinstance(new_rows, list) or not new_rows:
        raise ValueError("new_rows must be a non-empty list")
    for row in new_rows:
        _validate_row(row)
    existing = {r["decision_id"] for r in INDEX}
    for row in new_rows:
        if row["decision_id"] in existing:
            raise ValueError(f"duplicate decision_id: {row['decision_id']!r}")
        existing.add(row["decision_id"])

    before = index_hash()
    count_before = len(INDEX)
    INDEX.extend(copy.deepcopy(new_rows))
    after = index_hash()
    receipt = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": actor,
        "rows_added": [r["decision_id"] for r in new_rows],
        "row_count_before": count_before,
        "row_count_after": len(INDEX),
        "before_hash": before,
        "after_hash": after,
    }
    with open(RECEIPTS_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, sort_keys=True) + "\n")
    return receipt


def read_receipts():
    """Read the mutation receipt log (newest last)."""
    if not os.path.exists(RECEIPTS_LOG):
        return []
    out = []
    with open(RECEIPTS_LOG, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

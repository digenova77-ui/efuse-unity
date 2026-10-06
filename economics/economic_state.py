"""
ECONOMIC STATE — Worker 4 (Integration + Model Doc), unified economic model.

Fuses pricing + tokenomics + wallet into ONE signed EconomicState, computed
DCLM-side. Mirrors the conventions of ../dclm/compute.py:
  * EVERY field carries a provenance label: REPORTED / VERIFIED / MODELED /
    DERIVED / UNKNOWN (no exceptions)
  * Signed with the same Ed25519 envelope: {state, canonical_sha256,
    signature, algorithm, key_id, provenance} via ../dclm/ed25519.js
  * Test keys only (../keys/). Testnet isolation is structural.

Honesty laws (absolute, no exceptions):
  * UNKNOWN is never PASS and never pays. A field with provenance UNKNOWN
    renders as UNKNOWN and authorizes nothing.
  * MODELED is disclosed-as-modeled: it informs, it never pays.
    The decision price is the canon meter's SET 5 test-keys (price_provenance
    "SET") — no USD figure ever becomes a payable price. Only labeled,
    pass-ed entries move value.
  * Every mutation is receipted. No receipt -> no movement.
  * RELAYED != DELIVERED: building the relay bundle is not delivery.
    Delivery confirmation belongs to the relay worker (L5 umpires).

Worker 1-3 module interface (their files land in this same directory):
  * pricing.py     (Worker 1): compute_price_index(prices) -> dict
      — LANDED with a different API: per_decision_meter(decisions) -> list
      of price records {decision_id, provenance, billable_amount,
      currency="test-keys", pass, price_surface, ...}, fail-closed
      (KeyError on unknown decisions). This module adapts to it
      per-decision: engine-priced decisions carry
      source_module="pricing"; decisions the engine cannot price fall back
      to the raw input's own labeled figures (source_module="input").
      FUSION RULE (re-derived 2026-10-06, R1–R4): the price of a decision
      is the verdict-producing COMPUTE — the canon meter's flat 5
      test-keys (SET in dclm/meter.py, canon XIII). The USD surface figures
      ride along as labeled data (price_surface) with billable 0 — they
      are NEVER fused into the signed state as a payable price (the old
      USD `billable_amount_m` fusion with pays=true was the F4 live bug;
      it is retired). The fused `pays` follows the engine's own `pass`:
      a priced decision is billable; UNKNOWN never passes, never pays.
      The old "MODELED/DERIVED inform, never pay" rule governed the false
      USD price; the price is now the SET meter constant, independent of
      the surface's provenance — the surface's labels stay on the entry
      for honesty.
  * tokenomics.py  (Worker 2): compute_emission_state(emissions) -> dict
      — LANDED as a gate-enforcing engine (Figure/Receipt/PoolLedger,
      HeldParameterError, DuplicateReceiptError, ...). NOT re-driven here:
      its receipt chains have exactly one owner. The fusion layer
      aggregates labeled figures; it never re-applies receipts.
  * wallet.py      (Worker 3): compute_wallet_state(wallets) -> dict
  * fuse.py        (Worker 3): compute_donation_lock(donations) -> dict
If any expected hook is absent, this module computes from the raw inputs
itself with built-in defaults and stamps provenance honestly. Nothing blocks.

Input shapes (lists of dicts):
  prices    — {"decision_id": str, "price": num|None,
               "provenance": label|None, "source_label": str|None,
               "source": str|None}
  emissions — {"pool": "human"|"machine"|"mesh"|"reserve",
               "emitted": num|None, "held": num|None,
               "provenance": label|None, "merit_receipts": list|None}
  wallets   — {"unity_id": str, "balance": num|None, "merit": num|None,
               "honor": num|None, "provenance": label|None}
  donations — {"donor_unity_id": str, "amount": num|None,
               "kind": "efuse"|"fiat", "provenance": label|None,
               "donation_receipt": str|None}
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import time

# --- sibling worker modules (Workers 1-3) land in this directory ------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_W1_PRICING = None
_W2_TOKENOMICS = None
_W3_WALLET = None
_W3_FUSE = None

try:
    import pricing as _pricing_mod  # noqa: E402
    _W1_PRICING = getattr(_pricing_mod, "compute_price_index", None)
    # Worker 1's actual landed API (per-decision meter over its index).
    _W1_METER = getattr(_pricing_mod, "per_decision_meter", None)
except Exception:
    _W1_PRICING = None
    _W1_METER = None

try:
    import tokenomics as _tokenomics_mod  # noqa: E402
    _W2_TOKENOMICS = getattr(_tokenomics_mod, "compute_emission_state", None)
except Exception:
    _W2_TOKENOMICS = None

try:
    import wallet as _wallet_mod  # noqa: E402
    _W3_WALLET = getattr(_wallet_mod, "compute_wallet_state", None)
except Exception:
    _W3_WALLET = None

try:
    import fuse as _fuse_mod  # noqa: E402
    _W3_FUSE = getattr(_fuse_mod, "compute_donation_lock", None)
except Exception:
    _W3_FUSE = None


def worker_modules_present():
    """Which sibling worker modules and integration hooks were importable
    at load time."""
    return {
        "pricing": _W1_PRICING is not None,
        "pricing_meter": _W1_METER is not None,  # Worker 1's actual API
        "tokenomics": _W2_TOKENOMICS is not None,
        "wallet": _W3_WALLET is not None,
        "fuse": _W3_FUSE is not None,
    }


# --- provenance ------------------------------------------------------------
PROVENANCE_LABELS = frozenset(
    {"REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"}
)

# Ratified 50/50 (ED-DECIDED-20261004-5050-V1): lifetime emission caps.
# The caps are REPORTED (ratified design record); remaining authority is DERIVED.
LIFETIME_CAP_TOTAL = 100_000_000
LIFETIME_CAP_HUMAN = 50_000_000
LIFETIME_CAP_MACHINE = 50_000_000
MESH_EMISSION_AUTHORITY = 0  # the mesh routes, never mints — by construction

# The peg ratio (1 eFuse = E real-world energy units) is DAVID'S DIGIT (HELD).
# Nothing here invents it. Until his word arrives it is UNKNOWN.
PEG_RATIO_E_PER_EFUSE = None

KEYS_DIR = os.path.join(_HERE, "..", "keys")
TEST_PRIV_KEY = os.path.join(KEYS_DIR, "unity-world-test.key")
TEST_PUB_KEY = os.path.join(KEYS_DIR, "unity-world-test.pub")
ED25519_HELPER = os.path.join(_HERE, "..", "dclm", "ed25519.js")

KEY_ID = "unity-world-test"  # TESTNET ONLY

# Relay: dualis.relay.v1.testnet (testnet isolation — mainnet parsers reject it
# and vice versa). Mirrors ~/workspace/testnet/relay/relay-testnet.mjs.
RELAY_SCHEMA = "dualis.relay.v1.testnet"
RELAY_MAINNET_SCHEMA = "dualis.relay.v1"  # rejected here, always
TESTNET_IDENTITY_PREFIX = "unity:testnet:"
TESTNET_DCLM_ORIGIN = "http://localhost:18080"


# ---------------------------------------------------------------------------
# provenance utilities
# ---------------------------------------------------------------------------
def _label(node, default="UNKNOWN"):
    """Stamp every dict in the node tree with a provenance label.

    Dicts that already carry a valid label keep it. Dicts with a missing or
    invalid label get `default` (UNKNOWN) — never a pass, never invented.
    Returns the node.
    """
    if isinstance(node, dict):
        if node.get("provenance") not in PROVENANCE_LABELS:
            node["provenance"] = default
        for value in node.values():
            _label(value, default)
    elif isinstance(node, list):
        for value in node:
            _label(value, default)
    return node


def _assert_provenance(state_dict):
    """Every dict in the EconomicState tree must carry a valid provenance
    label. Raises ValueError otherwise."""
    def check(node, path):
        if isinstance(node, dict):
            if node.get("provenance") not in PROVENANCE_LABELS:
                raise ValueError(f"missing/invalid provenance at {path}")
            for key, value in node.items():
                check(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                check(value, f"{path}[{i}]")

    for field in ("price_index", "emission_state", "wallet_states",
                  "donation_lock"):
        if field not in state_dict:
            raise ValueError(f"missing EconomicState field: {field}")
    check(state_dict, "state")


def _clean_provenance(label):
    """Input provenance labels pass through if valid; anything else becomes
    UNKNOWN (downgraded, never upgraded)."""
    return label if label in PROVENANCE_LABELS else "UNKNOWN"


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _receipt_id(receipt_body):
    canonical = json.dumps(
        receipt_body, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# section builders (built-in defaults; Worker 1-3 modules override when present)
# ---------------------------------------------------------------------------
def _input_price_entry(item):
    """Built-in default entry from a raw price input dict."""
    decision_id = item.get("decision_id")
    prov = _clean_provenance(item.get("provenance"))
    price = item.get("price")
    return {
        "price": price if isinstance(price, (int, float)) else None,
        "pays": prov in ("REPORTED", "VERIFIED")
                and isinstance(price, (int, float)),
        # The input's own finer label (e.g. REAL, REPORTED-via-secondary,
        # MODELED-DERIVED from PRICES.md) is preserved verbatim in
        # source_label — never laundered, never dropped.
        "source_label": item.get("source_label"),
        "source": item.get("source"),
        "source_module": "input",
        "provenance": prov,
    }


def _meter_price_entry(record):
    """Adapt one Worker-1 pricing-engine record (per_decision_meter) into a
    price_index entry.

    Fusion rule (re-derived 2026-10-06, R1–R4): the price is the canon
    meter's flat 5 test-keys (SET in dclm/meter.py, canon XIII) — carried
    in `price` with `currency` "test-keys". The USD surface figures are
    attached as labeled data (`price_surface`, billable 0) and NEVER as a
    payable price: the old fusion of `billable_amount_m` (USD millions)
    with pays=true on REPORTED provenance was the F4 live bug and is
    retired. `pays` follows the engine's own `pass` — a priced decision
    is billable; UNKNOWN never passes, never pays. Nothing in the price
    side is denominated in dollars — ever (canon XI).

    REBATE plug point: a verified friction-kill would rebate the 5
    test-keys from the PLAYGROUND_FUEL bounty rail — HELD for David
    (pricing.REBATE_PENDING_DAVID / pricing.friction_kill_rebate). The
    entry carries the inert marker below; no rebate is applied.
    """
    price = record.get("billable_amount")  # test-keys, flat, canon meter
    price = price if isinstance(price, (int, float)) else None
    return {
        "price": price,
        "currency": record.get("currency") or "test-keys",
        "pays": bool(record.get("pass")) and price is not None,
        "price_basis": record.get("price_basis"),
        "price_provenance": record.get("price_provenance"),
        # Inert rebate hook — HELD for David. Present, does nothing.
        "rebate": "REBATE_PENDING_DAVID",
        # The row's surface provenance (REPORTED/DERIVED/...) describes the
        # attached labeled data, never the price. Kept for honesty.
        "source_label": record.get("label"),
        "source": "pricing.INDEX (Worker 1)",
        "price_surface": record.get("price_surface"),
        "vector": record.get("vector"),
        "decision_class": record.get("class"),
        "source_module": "pricing",
        "provenance": _clean_provenance(record.get("provenance")),
    }


def _build_price_index(prices):
    """Per-decision atomic pricing.

    Every decision gets an entry. Source precedence per decision:
      1. the documented contract (pricing.compute_price_index), if present;
      2. Worker 1's actual engine (pricing.per_decision_meter) — fail-closed:
         a decision the engine cannot price (KeyError) falls back to the
         raw input's own labeled figures, marked UNKNOWN if absent;
      3. the built-in default over raw inputs.
    Engine-priced decisions carry the flat 5-test-key price and pays
    follows the engine's pass (UNKNOWN never passes, never pays). The
    built-in raw-input fallback keeps the stricter legacy rule: it pays
    only on the caller's OWN REPORTED/VERIFIED claim — that path carries
    no engine price at all, so there is nothing false to fuse.
    UNKNOWN never pays, never passes.
    """
    if callable(_W1_PRICING):
        index = _W1_PRICING(prices or [])
        return _label(index if isinstance(index, dict) else {})

    index = {"provenance": "DERIVED"}  # assembled here from labeled inputs
    for item in (prices or []):
        decision_id = item.get("decision_id")
        if not decision_id:
            continue
        decision_id = str(decision_id)
        entry = None
        if callable(_W1_METER):
            try:
                records = _W1_METER([{"decision_id": decision_id}])
                if records:
                    entry = _meter_price_entry(records[0])
            except KeyError:
                # The engine never invents a price (fail closed); the fused
                # state carries the decision honestly as UNKNOWN instead.
                entry = None
            except Exception:
                entry = None
        if entry is None:
            entry = _input_price_entry(item)
        index[decision_id] = entry
    return index


def _pool_state(cap, emitted, held, prov):
    emitted = emitted if isinstance(emitted, (int, float)) else None
    held = held if isinstance(held, (int, float)) else None
    if emitted is None:
        remaining = None
    else:
        remaining = cap - emitted
    return {
        "lifetime_cap": cap,
        "cap_provenance": "REPORTED",  # ratified ED-DECIDED-20261004-5050-V1
        "emitted": emitted,
        "held": held,
        "remaining": remaining,
        "provenance": prov,
    }


def _build_emission_state(emissions):
    """The two 50M pools, the mesh clearing (no authority), the peg reserve.

    Pools are never pre-funded: emission exists only against gated receipts,
    so an emitted figure with UNKNOWN provenance stays UNKNOWN and moves
    nothing. The mesh has zero emission authority by construction.
    """
    if callable(_W2_TOKENOMICS):
        state = _W2_TOKENOMICS(emissions or [])
        return _label(state if isinstance(state, dict) else {})

    state = {"provenance": "DERIVED"}
    pool_inputs = {}
    receipts = []
    for item in (emissions or []):
        pool = item.get("pool")
        if pool not in ("human", "machine", "mesh", "reserve"):
            continue
        pool_inputs[pool] = item
        # Every emission mutation is receipted.
        if isinstance(item.get("emitted"), (int, float)):
            body = {
                "movement": "emission",
                "pool": pool,
                "amount": item["emitted"],
                "provenance": _clean_provenance(item.get("provenance")),
                "ts": _now_iso(),
            }
            receipts.append({
                "receipt_id": _receipt_id(body),
                "movement": body["movement"],
                "pool": pool,
                "amount": item["emitted"],
                "provenance": body["provenance"],
                "ts": body["ts"],
            })

    def prov_of(pool):
        item = pool_inputs.get(pool)
        return _clean_provenance(item.get("provenance")) if item else "UNKNOWN"

    def val_of(pool, key):
        item = pool_inputs.get(pool) or {}
        return item.get(key)

    state["human_pool"] = _pool_state(
        LIFETIME_CAP_HUMAN, val_of("human", "emitted"),
        val_of("human", "held"), prov_of("human"))
    state["machine_pool"] = _pool_state(
        LIFETIME_CAP_MACHINE, val_of("machine", "emitted"),
        val_of("machine", "held"), prov_of("machine"))
    state["mesh_clearing"] = {
        "emission_authority": MESH_EMISSION_AUTHORITY,
        "authority_provenance": "REPORTED",  # §3.3: the mesh routes, never mints
        "escrow": val_of("mesh", "held"),
        "provenance": prov_of("mesh"),
    }
    state["peg_reserve"] = {
        "held": val_of("reserve", "held"),
        "provenance": prov_of("reserve"),
    }
    # The peg ratio is David's digit, HELD. Until his word: UNKNOWN, and
    # peg calibration cannot run — emission_state says so plainly.
    state["peg_ratio_e_per_efuse"] = {
        "value": PEG_RATIO_E_PER_EFUSE,
        "provenance": "UNKNOWN",
        "note": "HELD for David (§13.1); calibration cannot run until his word",
    }
    state["epoch_receipts"] = receipts
    return state


def _build_wallet_states(wallets):
    """Worth / wallet: the prepaid bank per Unity ID.

    payable=True only when provenance is REPORTED or VERIFIED and the
    balance is a real non-negative number. UNKNOWN balances never pay;
    MODELED balances are labeled and never payable. No anonymous wallets:
    every entry is Unity-bound.
    """
    if callable(_W3_WALLET):
        states = _W3_WALLET(wallets or [])
        return _label(states if isinstance(states, dict) else {})

    states = {"provenance": "DERIVED"}
    for item in (wallets or []):
        unity_id = item.get("unity_id")
        if not unity_id:
            continue
        prov = _clean_provenance(item.get("provenance"))
        balance = item.get("balance")
        balance = balance if isinstance(balance, (int, float)) else None
        states[str(unity_id)] = {
            "balance": balance,
            "merit": item.get("merit"),
            "honor": item.get("honor"),
            "payable": prov in ("REPORTED", "VERIFIED")
                       and balance is not None and balance >= 0,
            "provenance": prov,
        }
    return states


def _build_donation_lock(donations):
    """The Core Cause Lock: one-way in, Honor out — never Merit, never money.

    Donations accrue Honor (public, permanent, non-transferable) and never
    convert to emission: there is no path from fiat to eFuse, direct or
    indirect. Donor exclusion: donated eFuse is never re-emitted to the same
    donor. The locked address is UNKNOWN until the real address exists —
    no placeholder address is ever presented.
    """
    if callable(_W3_FUSE):
        lock = _W3_FUSE(donations or [])
        return _label(lock if isinstance(lock, dict) else {})

    lock = {"provenance": "DERIVED"}
    lock["address"] = {
        "value": "UNKNOWN",
        "provenance": "UNKNOWN",
        "note": "no locked address exists yet; none is invented or rendered",
    }
    inflow = []
    honor_accrued = {}
    for item in (donations or []):
        donor = item.get("donor_unity_id")
        if not donor:
            continue
        prov = _clean_provenance(item.get("provenance"))
        amount = item.get("amount")
        amount = amount if isinstance(amount, (int, float)) else None
        body = {
            "movement": "donation",
            "donor_unity_id": str(donor),
            "amount": amount,
            "kind": item.get("kind"),
            "provenance": prov,
            "ts": _now_iso(),
        }
        inflow.append({
            "receipt_id": _receipt_id(body),
            "movement": body["movement"],
            "donor_unity_id": str(donor),
            "amount": amount,
            "kind": item.get("kind"),
            "provenance": prov,
            "ts": body["ts"],
            # Honor, never Merit: the donation receipt is the honor record.
            "accrues": "HONOR",
            "never_accrues": "MERIT",
        })
        donor_key = str(donor)
        honor_accrued[donor_key] = honor_accrued.get(donor_key, 0) + 1
    lock["inflow"] = inflow
    lock["honor_accrued"] = {
        "per_unity_id": honor_accrued,
        "provenance": "DERIVED",
    }
    lock["donor_exclusion"] = {
        "rule": "donated eFuse is never re-emitted to the same donor",
        "provenance": "REPORTED",  # ratified §9
    }
    return lock


# ---------------------------------------------------------------------------
# compute pipeline
# ---------------------------------------------------------------------------
def compute_economic_state(prices=None, emissions=None, wallets=None,
                           donations=None):
    """Fuse pricing + tokenomics + wallet into ONE EconomicState.

    Returns a plain dict with four provenance-labeled sections:
      price_index, emission_state, wallet_states, donation_lock.
    Raises ValueError if any field lacks a valid provenance label.
    """
    state = {
        "price_index": _build_price_index(prices),
        "emission_state": _build_emission_state(emissions),
        "wallet_states": _build_wallet_states(wallets),
        "donation_lock": _build_donation_lock(donations),
    }
    _label(state)
    _assert_provenance(state)
    return state


# ---------------------------------------------------------------------------
# signing (Ed25519, testnet keys only — same convention as dclm/compute.py)
# ---------------------------------------------------------------------------
def _canonical_bytes(state_dict):
    return json.dumps(
        state_dict, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_economic_state(state_dict, privkey_path=TEST_PRIV_KEY, key_id=KEY_ID):
    """Ed25519-sign the canonical JSON of the EconomicState.

    Returns the same envelope as dclm.compute.sign_state:
      {"state", "canonical_sha256", "signature", "algorithm", "key_id",
       "provenance"}.
    Key material never leaves the keys/ dir; only bytes of the canonical
    state travel to the signing helper.
    """
    canonical = _canonical_bytes(state_dict)
    proc = subprocess.run(
        ["node", os.path.normpath(ED25519_HELPER), "sign", privkey_path],
        input=canonical,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"signing failed: {proc.stderr.decode()!r}")
    signature = proc.stdout.decode().strip()
    return {
        "state": state_dict,
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "signature": signature,
        "algorithm": "Ed25519",
        "key_id": key_id,
        "provenance": "VERIFIED",  # the signature is verifiable against the key
    }


def verify_economic_envelope(envelope, pubkey_path=TEST_PUB_KEY):
    """Verify a signed EconomicState envelope. Returns True/False — never
    raises on bad data."""
    try:
        canonical = _canonical_bytes(envelope["state"])
        sig = envelope.get("signature", "")
        proc = subprocess.run(
            ["node", os.path.normpath(ED25519_HELPER), "verify", pubkey_path,
             sig],
            input=canonical,
            capture_output=True,
            timeout=30,
        )
        return proc.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# relay integration — dualis.relay.v1.testnet
# ---------------------------------------------------------------------------
def testnet_unity_id(pubkey_path=TEST_PUB_KEY):
    """The economic compute's Unity-bound sender identity:
    unity:testnet: + sha256(test pubkey). One-way; no secret involved."""
    with open(pubkey_path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    return TESTNET_IDENTITY_PREFIX + digest


def _relay_canonical(value):
    """Canonical JSON matching relay-testnet.mjs (sorted keys, no whitespace)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Match JS JSON.stringify: integral floats serialize without ".0".
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    if isinstance(value, str):
        # ensure_ascii=False: JS JSON.stringify emits non-ASCII raw (e.g. §),
        # while Python's default escapes it as \uXXXX — the hashes must agree.
        return json.dumps(value, separators=(",", ":"),
                          ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_relay_canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: kv[0])
        return "{" + ",".join(
            json.dumps(k, separators=(",", ":")) + ":" + _relay_canonical(v)
            for k, v in items
        ) + "}"
    raise TypeError(f"unserializable relay value: {type(value)!r}")


def _manifest_hash(kind, envelope, endpoint, unity_id):
    return hashlib.sha256(
        _relay_canonical({
            "kind": kind,
            "envelope": envelope,
            "endpoint": endpoint,
            "unityId": unity_id,
        }).encode("utf-8")
    ).hexdigest()


def to_economic_relay_bundle(signed_envelope, kind="VERDICT",
                             endpoint=TESTNET_DCLM_ORIGIN, unity_id=None,
                             relayed_at=None, relay_sequence=0, reason="",
                             schema=RELAY_SCHEMA):
    """Wrap the signed EconomicState envelope in a dualis.relay.v1 relay
    bundle, matching ~/workspace/testnet/relay/relay-testnet.mjs conventions.

    kind: "VERDICT" (the default — a DCLM-computed signed economic state) or
    "EVIDENCE" (supporting material). Fail-closed: a VERDICT bundle refuses
    an unsigned envelope — an unsigned claim is not a verdict.
    The bundle is the relay worker's input; RELAYED is not DELIVERED.
    """
    if kind not in ("VERDICT", "EVIDENCE"):
        raise ValueError(f"REJECTED · unknown relay kind {kind!r}")
    if not isinstance(signed_envelope, dict) or not signed_envelope.get("state"):
        raise ValueError("REJECTED · relay bundle requires a signed envelope")
    if kind == "VERDICT" and not signed_envelope.get("signature"):
        raise ValueError(
            "REJECTED · VERDICT bundle requires a signed envelope — "
            "an unsigned claim is not a verdict"
        )
    unity_id = unity_id or testnet_unity_id()
    if not unity_id.startswith(TESTNET_IDENTITY_PREFIX):
        raise ValueError(
            "REJECTED · relay requires a testnet Unity ID (unity:testnet:...)"
        )
    if not endpoint or not reason:
        raise ValueError("REJECTED · relay bundle missing required field")

    bundle = {
        "schema": schema,
        "manifest_hash": _manifest_hash(kind, signed_envelope, endpoint,
                                        unity_id),
        "kind": kind,
        "envelope": signed_envelope,
        "endpoint": endpoint,
        "unity_id": unity_id,
        "relayed_at": relayed_at or _now_iso(),
        "relay_sequence": relay_sequence,
        "reason": reason,
    }
    if not validate_economic_relay_bundle(bundle)["ok"]:
        raise ValueError("REJECTED · built bundle failed self-validation")
    return bundle


def validate_economic_relay_bundle(bundle):
    """Fail-closed parse of an economic relay bundle, mirroring the
    testnet parser: returns {"ok": True, "value": ...} or
    {"ok": False, "reason": ...}. Mainnet-schema bundles are rejected;
    non-testnet identities are rejected; tampered manifest hashes are
    rejected."""
    if not isinstance(bundle, dict):
        return {"ok": False, "reason": "REJECTED · not an object"}
    if bundle.get("schema") == RELAY_MAINNET_SCHEMA:
        return {"ok": False,
                "reason": "REJECTED · mainnet bundle in testnet relay — "
                          "schema mismatch, refusing"}
    if bundle.get("schema") != RELAY_SCHEMA:
        return {"ok": False,
                "reason": f"REJECTED · unknown schema {bundle.get('schema')!r}"}
    for field in ("manifest_hash", "kind", "envelope", "endpoint",
                  "unity_id", "relayed_at", "reason"):
        if not bundle.get(field):
            return {"ok": False,
                    "reason": f"REJECTED · missing field {field}"}
    if not str(bundle["unity_id"]).startswith(TESTNET_IDENTITY_PREFIX):
        return {"ok": False,
                "reason": "REJECTED · non-testnet Unity ID in testnet bundle"}
    recomputed = _manifest_hash(bundle["kind"], bundle["envelope"],
                                bundle["endpoint"], bundle["unity_id"])
    if recomputed != bundle["manifest_hash"]:
        return {"ok": False,
                "reason": "REJECTED · manifest_hash does not match "
                          "bundle content"}
    return {"ok": True, "value": bundle}


def dedupe_bundles(bundles):
    """Collapse duplicate bundles by manifest_hash — doing it twice is
    doing it once. Same idempotency rule as the relay worker's export."""
    seen = set()
    deduped = []
    for bundle in sorted(bundles or [],
                         key=lambda b: b.get("relay_sequence", 0)):
        mh = bundle.get("manifest_hash")
        if mh in seen:
            continue
        seen.add(mh)
        deduped.append(bundle)
    return deduped

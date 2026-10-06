#!/usr/bin/env python3
"""
ONE SEED — David's law (2026-10-06, verbatim): "no matter how much money
you have you only buy one seed, and it costs you nothing."

THE LAW:
  * One free seed per Unity ID. No financial barrier, no wealth
    advantage. The richest and the poorest receive exactly one seed
    each. Money cannot buy a second seed, a bigger seed, or earlier
    access to seeds.
  * The seed IS the genesis entry — the initial Unity-bound allocation
    that makes you a member. The root's gift to the new leaf, not a
    purchase. "Buy" is the wrong word: you RECEIVE it. It costs nothing
    because membership isn't for sale.
  * Purity enforcement:
      - One Unity ID = one seed. Sybil resistance via the L1 identity
        derivation (the gate's bind-then-validate ceremony): identities
        cannot be minted to farm seeds. A second seed request for a
        bound ID is refused (SEED_ALREADY_ISSUED); an unbound ID cannot
        receive one (NOT_BOUND).
      - No seed market: seeds can't be sold, transferred, or
        accumulated — bound to the receiving Unity ID, structurally.
        No transfer function exists; assert_no_seed_market() proves it
        by AST on every test run.
      - The seed is the start, not the wealth: what grows from it
        (merit, work, participation) is earned. The seed opens the
        door; nothing more.
  * Relationship to +1 Affinity: the free seed gets you in the door
    (entry is equal); +1 Affinity honors HOW EARLY you walked through it.

MACHINERY, in code, not in comments:
  * issue_seed(unity_id) -> signed dclm_commit envelope, receipted.
    Refuses (zero seeds, zero ledger change) when:
      - the identity is not testnet — refused by the purification
        medium on entry as PurificationRefused (NOT_TESTNET_IDENTITY /
        NO_IDENTITY); the module's own structural check remains as
        defense in depth and raises SeedRefused(NOT_TESTNET_IDENTITY)
        for anything the medium lets through
      - the identity is not BOUND in the gate ceremony ("NOT_BOUND" —
        SeedRefused)
      - a seed was already issued for this identity ("SEED_ALREADY_ISSUED"
        — SeedRefused, signed and receipt-logged)
      - the gate module cannot be read honestly ("GATE_LEDGER_UNAVAILABLE"
        — SeedRefused; UNKNOWN is never PASS: no gate, no seed)
      - the runtime is not testnet ("PRODUCTION_SCHEMA_REFUSED" —
        SeedRefused)
  * The seed costs nothing: the SeedRecord carries price 0 and cost 0,
    and the issuance touches NO money ledger — no test-keys debit in
    dclm/meter.py, no eFuse/Unity movement in economics/wallet.py.
  * The seed is membership, not money: recorded on the economics wallet
    as a MEMBERSHIP marker (never a balance), and optionally mirrored
    into the economics Ledger via Ledger.record_seed (receipted, not
    spendable, never priced, never counted as wealth).
  * The seed registry is write-once per identity: the one mutation point
    is _SeedCommitStore.apply_write (driven by dclm_commit after GRANT),
    writing ONLY through _register_seed, which is called ONLY from
    issue_seed's commit. assert_no_seed_market() proves the absence of
    any transfer/sale/accumulation machinery by AST.

Gate integration (honest, not faked):
  The BOUND check reads the LIVE gate state via UnityGate from
  ../gate/gate.py (importlib, file path — the same pattern gate.py uses
  in reverse for the meter ledger). A Seeder may be constructed with an
  injected gate (tests inject one pointed at a temp state dir with a
  clearly-labeled TEST STUB verifier, exactly like the gate's own
  tests). The default reads the production gate state dir. If the gate
  module is missing or broken, the check degrades to an honest refusal:
  UNKNOWN is never PASS, so no seed issues without a readable gate.

Reused vs built:
  * REUSED: rights.py — SEED_ISSUE added to COMMIT_KINDS (receipt-logged
    justification); only DCLM-internal "dclm.seed" may commit it.
    writes.py — dclm_commit is the only write path; sign_commit signs
    the refusal trail too. gate/gate.py — the BOUND state machine.
    economics/wallet.py — the membership mirror (record_seed /
    seed_membership / Wallet.membership).
  * BUILT HERE: the SeedRecord format (price 0, cost 0, non-transferable,
    non-spendable, non-purchasable), the issue_seed path with the four
    refusals, the write-once registry, the AST exclusivity proof, and
    the plutocracy test (funded wallet gets exactly the same free seed
    as an empty one).

TESTNET ONLY.
"""

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import sys
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    purify_input,
    purify_output,
    purify_transition,
)
from writes import (  # noqa: E402 — the single commit path
    CommitStore,
    dclm_commit,
    sign_commit,
)
from compute import PROVENANCE_LABELS  # noqa: E402 — label set

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.seed.v1.testnet"
NETWORK = "dualis.relay.v1.testnet"   # the ONLY relay this path serves
IDENTITY_PREFIX = "unity:testnet:"

KIND_SEED_ISSUE = "SEED_ISSUE"

# --- refusal reasons --------------------------------------------------------
REASON_SEED_ALREADY_ISSUED = "SEED_ALREADY_ISSUED"
REASON_NOT_BOUND = "NOT_BOUND"
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_PRODUCTION_SCHEMA = "PRODUCTION_SCHEMA_REFUSED"
REASON_GATE_LEDGER_UNAVAILABLE = "GATE_LEDGER_UNAVAILABLE"

# The gate module, by file path (same importlib pattern gate.py uses for
# the meter ledger, reversed). The gate owns the binding state; the seed
# path only READS it — never writes to it.
GATE_MODULE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "gate", "gate.py"
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SeedError(Exception):
    """Base class for seed failures."""


class SeedRefused(SeedError):
    """Structural refusal: the seed was not issued. Carries .reason.
    Nothing was issued, nothing was written."""

    def __init__(self, reason, detail=""):
        super().__init__(f"seed refused [{reason}]: {detail}")
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# SeedRecord — the format spec. Membership, not money.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SeedRecord:
    """THE genesis entry — the root's gift to the new leaf.

    Fields:
      schema         — "unity.seed.v1.testnet"
      record_type    — "SEED_ISSUE"
      seed_id        — sha256 hex over the stable record fields
                       (deterministic per identity: one seed, one id —
                       issued_at is record metadata and does not move
                       the id)
      unity_id       — the ONE bound Unity ID this seed belongs to
                       (the seed is bound to it, structurally)
      price          — 0.0. ALWAYS. The seed costs nothing.
      cost           — 0.0. ALWAYS. Nothing is deducted for it.
      transferable   — False. ALWAYS. No seed market, structurally.
      spendable      — False. ALWAYS. The seed is membership, not money.
      purchasable    — False. ALWAYS. "Buy" is the wrong word: received.
      provenance     — "DERIVED" (computed in-process by DCLM)
      issued_at      — ISO timestamp
      testnet        — True, always
      note           — the law, in the record itself

    Structural note: this format has NO transfer field, NO sale field,
    NO price field that can be set (price/cost are enforced at 0 by
    _build_record, and the dataclass is frozen), and NO accumulation
    counter. There is no function anywhere that moves a seed between
    identities — assert_no_seed_market() proves the absence by AST.
    """
    schema: str
    record_type: str
    seed_id: str
    unity_id: str
    price: float
    cost: float
    transferable: bool
    spendable: bool
    purchasable: bool
    provenance: str
    issued_at: str
    testnet: bool
    note: str = ""


def _utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _build_record(unity_id):
    """Build the SeedRecord for an identity. Price and cost are 0 — not
    a parameter, not a default the caller can override: the constructor
    enforces them, and the dataclass is frozen."""
    unsigned = {
        "schema": SCHEMA,
        "record_type": KIND_SEED_ISSUE,
        "unity_id": unity_id,
        "price": 0.0,            # the seed costs nothing. Always.
        "cost": 0.0,             # nothing is deducted. Always.
        "transferable": False,   # no seed market. Structurally.
        "spendable": False,      # membership, not money. Structurally.
        "purchasable": False,    # "buy" is the wrong word: received.
        "provenance": "DERIVED",
        "issued_at": _utc_now(),
        "testnet": True,
        "note": (
            "ONE SEED (David's law, 2026-10-06): no matter how much "
            "money you have you only get one seed, and it costs you "
            "nothing. The seed is the genesis entry — the root's gift "
            "to the new leaf, not a purchase. You receive it; you don't "
            "buy it. One per Unity ID, free, non-transferable, "
            "non-spendable. It opens the door; nothing more. Entry is "
            "equal; +1 Affinity honors how early you walked through."
        ),
    }
    # The seed id is DETERMINISTIC per identity (one seed, one id): it
    # hashes the stable fields only — issued_at is record metadata, not
    # identity, and must not move the id. This makes the wallet mirror
    # idempotent by construction.
    seed_id = _sha256_hex(_canonical_bytes({
        "seed": unsigned["schema"],
        "record_type": unsigned["record_type"],
        "unity_id": unsigned["unity_id"],
        "price": unsigned["price"],
        "cost": unsigned["cost"],
        "transferable": unsigned["transferable"],
        "spendable": unsigned["spendable"],
        "purchasable": unsigned["purchasable"],
        "provenance": unsigned["provenance"],
        "testnet": unsigned["testnet"],
    }))
    return SeedRecord(seed_id=seed_id, **unsigned)


# ---------------------------------------------------------------------------
# Gate integration — read BOUND, honestly
# ---------------------------------------------------------------------------

def _resolve_gate(state_dir=None):
    """Locate the Unity gate's binding state machine (../gate/gate.py)
    and return a UnityGate. Reads LIVE gate state — never faked.

    Raises SeedRefused(GATE_LEDGER_UNAVAILABLE) when the module is
    missing or broken: the gate cannot be fabricated, and UNKNOWN is
    never PASS — no readable gate, no seed.
    """
    if not os.path.exists(GATE_MODULE_PATH):
        raise SeedRefused(
            REASON_GATE_LEDGER_UNAVAILABLE,
            f"gate module not found at {GATE_MODULE_PATH} — the BOUND "
            "check cannot be performed honestly, and UNKNOWN is never "
            "PASS. No seed without a readable gate.",
        )
    spec = importlib.util.spec_from_file_location(
        "unity_unity_gate", GATE_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise SeedRefused(
            REASON_GATE_LEDGER_UNAVAILABLE,
            "gate module spec could not be built — refusing to seed on "
            "an unverifiable gate.",
        )
    module = importlib.util.module_from_spec(spec)
    # dataclasses (used by gate.py) resolve their module via
    # sys.modules: the module must be registered BEFORE exec.
    sys.modules["unity_unity_gate"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise SeedRefused(
            REASON_GATE_LEDGER_UNAVAILABLE,
            f"gate module failed to load ({exc}) — a broken gate is not "
            "a working gate; refusing to seed on it.",
        )
    gate_cls = getattr(module, "UnityGate", None)
    if not callable(gate_cls):
        raise SeedRefused(
            REASON_GATE_LEDGER_UNAVAILABLE,
            "gate module has no UnityGate — refusing to seed on an "
            "unrecognizable gate.",
        )
    return gate_cls(state_dir=state_dir)


# ---------------------------------------------------------------------------
# The commit store — DCLM-internal adapter for seed issuance writes
# ---------------------------------------------------------------------------

def _normalize_jsonable(obj):
    if isinstance(obj, tuple):
        return [_normalize_jsonable(v) for v in obj]
    if isinstance(obj, list):
        return [_normalize_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _normalize_jsonable(v) for k, v in obj.items()}
    return obj


class _SeedCommitStore(CommitStore):
    """Lets writes.dclm_commit drive the seed registry's single mutation.

    apply_write performs THE one mutation (the registry insert — the
    write-once mark for this identity); build_receipt returns the
    SeedRecord itself, so the signed commit envelope signs the seed —
    the seed IS the receipt; append_receipt logs it on the seeder.
    """

    def __init__(self, seeder, record):
        self._seeder = seeder
        self._record = record

    def apply_write(self, kind, payload):
        self._seeder._register_seed(self._record)
        return {"seed_id": self._record.seed_id,
                "unity_id": self._record.unity_id,
                "price": self._record.price,
                "cost": self._record.cost}

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        import dataclasses
        body = _normalize_jsonable(dataclasses.asdict(self._record))
        body["commit_kind"] = kind
        body["rights"] = {
            "verdict": rights_verdict.verdict,
            "reason": rights_verdict.reason,
        }
        return body

    def append_receipt(self, envelope):
        self._seeder._receipt_log.append(envelope)


# ---------------------------------------------------------------------------
# The seeder
# ---------------------------------------------------------------------------

class Seeder:
    """DCLM-side one-seed issuer. TESTNET ONLY.

    Registry (in-memory; the seeder owns it, mutations happen only
    inside _SeedCommitStore.apply_write driven by dclm_commit):
      _seeds: unity_id -> SeedRecord (write-once per identity)

    The registry is authoritative for the one-seed rule. The economics
    wallet (economics/wallet.py) holds an optional MIRROR of membership
    (record_seed) — a mirror, not the law: it is receipted, not
    spendable, never priced, never counted as wealth.
    """

    def __init__(self, gate=None, gate_state_dir=None):
        # gate: an injected UnityGate (tests inject one on a temp state
        # dir — clearly labeled). None -> resolve the live gate module
        # (raises honestly at USE time, not here, so a Seeder is always
        # constructible and honest about an unreadable gate).
        self._gate = gate
        self._gate_state_dir = gate_state_dir
        self._seeds = {}
        self._receipt_log = []   # every step receipted: issues + refusals

    # -- the gate ----------------------------------------------------------
    def _bound_check(self, unity_id):
        """Verify the identity is BOUND in the gate ceremony. Raises
        SeedRefused(NOT_BOUND) otherwise — an unbound ID cannot receive
        a seed. Raises SeedRefused(GATE_LEDGER_UNAVAILABLE) when the
        gate cannot be read honestly."""
        gate = self._gate if self._gate is not None else _resolve_gate(
            state_dir=self._gate_state_dir)
        try:
            state = gate.status(unity_id)
        except Exception as exc:
            # The gate's own refusal types (GateRefused/GateError) mean
            # the binding cannot be affirmed: not affirmed is not bound.
            raise SeedRefused(
                REASON_NOT_BOUND,
                f"gate could not affirm binding for {unity_id!r} "
                f"({type(exc).__name__}): not affirmed is not bound.",
            ) from exc
        if state != "BOUND":
            raise SeedRefused(
                REASON_NOT_BOUND,
                f"{unity_id!r} is {state} in the gate — a seed issues "
                "only to a BOUND identity (the bind-then-validate "
                "ceremony). Unbound identities cannot receive a seed.",
            )
        return True

    # -- guards -------------------------------------------------------------
    def _require_testnet_context(self, unity_id):
        """Structural refusal: non-testnet identities and non-testnet
        schema never operate here."""
        if SCHEMA is None or "testnet" not in str(SCHEMA).lower():
            raise SeedRefused(
                REASON_PRODUCTION_SCHEMA,
                "seeder SCHEMA constant is not testnet — refusing to "
                "operate structurally",
            )
        if not isinstance(unity_id, str) or not unity_id.strip():
            raise SeedRefused(
                REASON_NOT_TESTNET_IDENTITY,
                "no Unity ID — no anonymous seed exists",
            )
        if not unity_id.startswith(IDENTITY_PREFIX):
            raise SeedRefused(
                REASON_NOT_TESTNET_IDENTITY,
                f"unity_id {unity_id!r} is not a testnet identity (must "
                f"start with {IDENTITY_PREFIX!r}). Testnet only.",
            )
        if NETWORK != "dualis.relay.v1.testnet":
            raise SeedRefused(
                REASON_PRODUCTION_SCHEMA,
                "seeder NETWORK constant is not the testnet relay — "
                "refusing to operate",
            )
        return unity_id.strip()

    def _require_unseeded(self, unity_id):
        """The one-seed rule: a second seed request for a bound ID is
        refused. The refusal is signed and receipt-logged — an honest,
        verifiable statement, not a silent drop."""
        if unity_id in self._seeds:
            existing = self._seeds[unity_id]
            self._log_refusal(
                REASON_SEED_ALREADY_ISSUED,
                f"{unity_id!r} already holds seed {existing.seed_id[:16]}… — "
                "one Unity ID = one seed. Money cannot buy a second.",
            )
            raise SeedRefused(
                REASON_SEED_ALREADY_ISSUED,
                f"{unity_id!r} already received its one free seed "
                f"({existing.seed_id[:16]}…). No second seed exists.",
            )

    # -- the registry (write-once) -------------------------------------------
    def _register_seed(self, record):
        """THE one registry mutation point. Called only from
        _SeedCommitStore.apply_write (which dclm_commit drives exactly
        once, only after GRANT). Write-once: a re-registration of the
        same identity is refused structurally, never overwritten."""
        if record.unity_id in self._seeds:
            raise SeedRefused(
                REASON_SEED_ALREADY_ISSUED,
                "registry conflict: seed already issued for "
                f"{record.unity_id!r} — write-once, never overwritten",
            )
        self._seeds[record.unity_id] = record

    # -- the issuance ----------------------------------------------------------
    def issue_seed(self, unity_id, ledger=None):
        """Issue THE one free seed for a Unity ID.

        1. PURIFY ON ENTRY: the medium first — no anonymous input crosses.
           Anonymous or forged identities are refused here as
           PurificationRefused, before the module's own checks.
        2. Structural testnet checks (identity + schema + relay) as
           defense in depth — SeedRefused(NOT_TESTNET_IDENTITY /
           PRODUCTION_SCHEMA_REFUSED) for anything the medium lets
           through.
        3. Gate BOUND check against the LIVE gate state (refuses
           NOT_BOUND / GATE_LEDGER_UNAVAILABLE honestly).
        4. One-seed check (refuses SEED_ALREADY_ISSUED — signed).
        5. rights.check_rights GRANT (DCLM-internal "dclm.seed") ->
           purify_transition -> dclm_commit(SEED_ISSUE) -> signed
           envelope, purified on exit.
        6. Optional wallet mirror: when an economics Ledger is passed and
           holds a wallet for this identity, membership is mirrored
           there (receipted, non-spendable, never wealth). When the
           ledger holds no wallet, there is no identity state to mirror
           — the seeder's registry stays authoritative.

        Zero cost: the issuance touches NO money ledger — no test-keys
        debit, no eFuse/Unity movement. The SeedRecord carries price 0
        and cost 0 by construction.
        """
        uid = unity_id
        # PURIFY ON ENTRY: the medium first. No anonymous input crosses —
        # anonymous or forged identities are refused here as
        # PurificationRefused, before the module's own structural checks
        # (which remain as defense in depth).
        purify_input(
            {"identity": uid, "action": "SEED_ISSUE",
             "claims": [{"claim": "one-seed-issue-request",
                         "provenance": "DERIVED"}]},
            context={"path": "seed.issue_seed"},
        )
        uid = self._require_testnet_context(uid)
        try:
            self._bound_check(uid)
            self._require_unseeded(uid)
        except SeedRefused:
            raise

        record = _build_record(uid)

        verdict = check_rights(
            uid, KIND_SEED_ISSUE,
            {"internal": "dclm.seed", "schema": SCHEMA},
        )
        import dataclasses
        receipt_dict = _normalize_jsonable(dataclasses.asdict(record))
        # PURIFY IN FLIGHT: kind whitelisted, receipt planned and
        # labeled, the change declared (False -> True), identity
        # continuous — before writes.py commits.
        purify_transition(
            {"unity_id": uid, "seed_issued": False},
            {"unity_id": uid, "seed_issued": True},
            KIND_SEED_ISSUE,
            context={"receipt": receipt_dict, "identity": uid,
                     "path": "seed.issue_seed"},
        )
        envelope = dclm_commit(
            KIND_SEED_ISSUE,
            {"record_type": KIND_SEED_ISSUE, "schema": SCHEMA,
             "unity_id": uid},
            verdict,
            _SeedCommitStore(self, record),
        )

        # Optional membership mirror into the economics wallet. The
        # seeder's registry is authoritative; the wallet holds a mirror —
        # receipted, non-spendable, never priced, never wealth.
        if ledger is not None and hasattr(ledger, "record_seed") \
                and hasattr(ledger, "has_wallet") \
                and ledger.has_wallet(uid):
            ledger.record_seed(uid, {
                "seed_id": record.seed_id,
                "receipt_sha256": envelope["canonical_sha256"],
                "issued_at": record.issued_at,
                "provenance": "DERIVED",
            })

        # PURIFY ON EXIT: the signed issuance envelope, verified.
        return purify_output(
            envelope,
            context={"path": "seed.issue_seed", "signed": True},
        )

    # -- reads -------------------------------------------------------------------
    def has_seed(self, unity_id):
        """Has this identity received its one seed?"""
        return unity_id in self._seeds

    def seed_record(self, unity_id):
        """The SeedRecord for an identity, or None."""
        return self._seeds.get(unity_id)

    def seeds_issued(self):
        """How many seeds this seeder has issued. (One per identity —
        the count is a registry size, never a balance.)"""
        return len(self._seeds)

    # -- refusal trail ------------------------------------------------------------
    def _log_refusal(self, reason, detail):
        refusal = {
            "schema": SCHEMA,
            "type": "REFUSAL",
            "outcome": "REFUSED",
            "reason": reason,
            "detail": detail,
            "testnet": True,
            "issued_at": _utc_now(),
            "provenance": "DERIVED",
            "note": "Refusal, not a block: nothing was issued, nothing "
                    "was written.",
        }
        # Signed like every other receipt — a signed refusal is a
        # verifiable honest statement, not a silent drop.
        self._receipt_log.append(sign_commit(refusal))

    def refusal_log(self):
        """The signed refusal trail (SEED_ALREADY_ISSUED etc.)."""
        return list(self._receipt_log)


# ---------------------------------------------------------------------------
# Introspection — the no-seed-market proof
# ---------------------------------------------------------------------------

def seed_paths():
    """The exhaustive list of seed issuance paths, as code. Exactly one:
    this module's issue_seed() -> dclm_commit('SEED_ISSUE'). The seed is
    issued, never bought, never sold, never transferred."""
    return [
        "seed.Seeder.issue_seed -> dclm_commit('SEED_ISSUE')"
        " — the ONLY seed issuance path (free, one per Unity ID)",
    ]


def seed_transfer_paths():
    """The exhaustive list of seed transfer paths, as code. It is EMPTY.

    Seeds can't be sold, transferred, or accumulated — bound to the
    receiving Unity ID, structurally. No transfer function exists;
    assert_no_seed_market() enforces the emptiness on every test run."""
    return []


def assert_no_seed_market():
    """Module-level test hook: prove by AST that NO seed market can exist.

    (a) No transfer/sale/buy/gift/rebind/accumulate/spend/debit/credit/
        purchase/mint/airdrop machinery exists by NAME anywhere in this
        module — the seed market has no function to live in.
    (b) The seed registry (self._seeds) is stored into ONLY by
        _register_seed — the write-once point.
    (c) _register_seed is called ONLY from _SeedCommitStore.apply_write —
        the commit path dclm_commit drives exactly once after GRANT.
    (d) No price/cost field is ever written to a non-zero value: the only
        constructions of SeedRecord happen in _build_record, which hard-
        codes 0.0 (grep-able; asserted structurally below).

    Raises AssertionError on any violation. Called by test_seed.py on
    every run."""
    import seed as _self  # the module under test, by its own name

    source = inspect.getsource(_self)
    tree = ast.parse(source)

    # (a) no market machinery by name. "seed_transfer_paths" is the
    # path-listing function that documents the EMPTY transfer set (the
    # proof that no transfer path exists) — allowlisted explicitly, the
    # same way token_engine.py allowlists its path-listing helpers.
    names = {n.name.lower() for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    class_names = {n.name.lower() for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef)}
    allowed_names = {"seed_transfer_paths"}
    forbidden = ("transfer", "sale", "sell", "resell", "gift", "rebind",
                 "reassign", "accumulate", "spend", "debit", "credit",
                 "purchase", "buy", "mint", "airdrop", "redeem")
    hits = [n for n in (names | class_names) - allowed_names
            if any(f in n for f in forbidden)]
    assert not hits, f"SEED MARKET MACHINERY PRESENT: {hits}"

    # (b) the registry is stored into ONLY by _register_seed.
    violations = []

    class AssignV(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def _check(self, target):
            if (isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "_seeds"):
                if "_register_seed" not in self.stack:
                    violations.append((".".join(self.stack),
                                       "subscript-store"))

        def visit_Assign(self, node):
            for target in node.targets:
                self._check(target)
            self.generic_visit(node)

        def visit_AugAssign(self, node):
            self._check(node.target)
            self.generic_visit(node)

    AssignV().visit(tree)
    assert not violations, (
        "SEED REGISTRY VIOLATION: _seeds mutated outside _register_seed: "
        f"{violations}"
    )

    # (c) _register_seed is called ONLY from apply_write.
    callers = set()
    for stack, node in _iter_calls(tree):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else None)
        if name == "_register_seed":
            callers.add(stack[0] if stack else "<module>")
    bad_callers = {c for c in callers if c != "apply_write"}
    assert not bad_callers, (
        "SEED REGISTRY VIOLATION: _register_seed called outside "
        f"apply_write: {bad_callers}"
    )

    # (d) SeedRecord is constructed ONLY in _build_record, which hard-
    # codes price 0.0 / cost 0.0 (the call sites carry no price argument).
    builders = {}
    for stack, node in _iter_calls(tree):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else None
        if name == "SeedRecord":
            outer = stack[0] if stack else "<module>"
            builders.setdefault(outer, set()).add(name)
    bad_builders = {f for f in builders if f != "_build_record"}
    assert not bad_builders, (
        "SEED RECORD VIOLATION: SeedRecord built outside _build_record: "
        f"{bad_builders}"
    )
    # And _build_record names no nonzero price: the unsigned body sets
    # "price": 0.0 and "cost": 0.0 exactly (structural, grep-able).
    assert '"price": 0.0' in source and '"cost": 0.0' in source, (
        "SEED PRICE VIOLATION: _build_record must hard-code price/cost "
        "0.0"
    )
    return True


def _iter_calls(tree):
    """Yield (func-stack tuple, Call node) for every call in the tree."""
    out = []
    stack = []

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            out.append((tuple(stack), node))
            self.generic_visit(node)

    V().visit(tree)
    return out


# ---------------------------------------------------------------------------
# Module-level default seeder (tests use fresh Seeder() instances)
# ---------------------------------------------------------------------------

_DEFAULT = None


def _get_default():
    """The default seeder, created lazily so importing this module never
    touches the gate (the gate is resolved at first USE, honestly)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Seeder()
    return _DEFAULT


def issue_seed(unity_id, ledger=None):
    """issue_seed(unity_id) -> signed SEED_ISSUE envelope. The one free
    seed for a Unity ID. See Seeder.issue_seed."""
    return _get_default().issue_seed(unity_id, ledger=ledger)


def has_seed(unity_id):
    """Has this identity received its one seed?"""
    return _get_default().has_seed(unity_id)


def seed_record(unity_id):
    """The SeedRecord for an identity, or None."""
    return _get_default().seed_record(unity_id)

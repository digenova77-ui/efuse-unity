"""
DCLM TOKENIZATION ENGINE — the machinery by which value becomes tokens.

David's order: build the actual process. A gated receipt (verified work)
enters; the tokenization engine computes the token output. DCLM rights,
DCLM writes, DCLM tokenizes — the client never mints, never computes
token amounts.

FILENAME NOTE (honest engineering): this implementation lives in
`token_engine.py`, NOT `tokenize.py`, because a module named
`tokenize.py` shadows the stdlib `tokenize` module that
`linecache`/`traceback`/`unittest` import — with the dclm directory on
sys.path, `import dataclasses` breaks in a circular import and every
sibling test suite fails to even start (verified 2026-10-06). The
mandated public path `dclm/tokenize.py` exists as a thin PEP-562 shim
that re-exports this module's API and stays transparent to stdlib
consumers. `import tokenize` / `from tokenize import tokenize` work
exactly as specified.

THE PIPELINE (receipt -> token):
    gated receipt (Unity-bound, provenance-claimed, gate-SIGNED, chained)
      -> testnet context check (production schema/key -> structural refusal)
      -> gate check (caller's provenance claim must read VERIFIED; the
         gate's Ed25519 SIGNATURE must verify against the gate public
         key; prev_hash must link the engine's gate chain; kind valid;
         manifest valid; no misattributed beneficiary — UNKNOWN never
         tokenizes, self-asserted "VERIFIED" never tokenizes, and merit
         is NEVER credited to an ID for another ID's work)
      -> per-kind minting, ONLY through the single private _mint(),
         each output committed via writes.dclm_commit:
             "work"     -> MERIT_ACCRUAL (merit score up, earner's ID only)
                           + TOKEN_MINT (eFuse, merit-gated at merit/E)
             "donation" -> HONOR_RECORD (append-only, never spendable)
             "genesis"  -> Unity holding BIND + binding proof (Unity itself
                           is minted ONLY by the fuse trigger)
      -> signed TokenBundle out

UNITY NON-TRANSFERABILITY (David's word, 2026-10-06 ~3:35 AM EDT — LAW,
supersedes the earlier bound-sale correction of the same morning):
    Every Unity is always bound to exactly one Unity ID — and Unity NEVER
    moves. No sale, no gift, no re-bind, no exceptions, not even by David.
    The bound-transfer-sale concept is DEAD: bound_sale() and every
    bound-sale path have been REMOVED from this module (code, tests,
    docs). The unity registry is write-once at genesis (bind) and
    read-only forever after — assert_no_unity_rebind() proves by AST that
    no function re-binds a Unity token, and that no transfer-ish
    machinery (bound_sale/rebind/reassign/resell/…) exists at all.

MERIT TRANSFERABILITY (David's word, 2026-10-06 ~3:35 AM EDT — LAW,
supersedes the earlier "Merit non-transferable" law):
    Merit IS transferable — sold, gifted, transferred between Unity IDs,
    all receipted. The old non-transferable law is SUPERSEDED, recorded
    explicitly (see economics/DECISIONS.md §13), not silently edited away.

THE STANDING-VS-VALUE DISTINCTION (structural, not policy):
    Every Merit token carries IMMUTABLE origin fields — origin_earner_id
    and origin_receipt_ref — set once at accrual, never rewritten, never
    carried by any other layer (the wallet records ownership changes and
    NEVER origin). A transfer changes owner_unity_id ONLY; origin never
    changes. Therefore:
      * ECONOMIC VALUE  = merit_balance(identity): the sum of Merit the
        identity currently OWNS (spendable, priced — what a buyer gains).
      * EARNED STANDING = standing(identity): the sum of Merit whose
        origin_earner_id == identity (the history, the reputation, the
        proof-of-work — what a buyer can NEVER gain).
    A buyer of Merit gains economic value and ZERO standing, BY
    CONSTRUCTION: transfers copy origin fields forward, and standing is
    computed SOLELY from origin. The emission gate (meter.py's
    TokenizeMeritReader) reads standing(), never the balance — bought
    merit can never gate emission. That is the load-bearing wire: if the
    gate read owned balance, standing would be buyable in effect, and the
    distinction would be a comment, not a structure.

DERIVATIVE MERIT REGENERATION (David's law-grade correction, 2026-10-06):
    Downstream rings do NOT receive tokens from upstream — each ring
    earns its own merit from its own verified receipts. The pipeline
    credits merit ONLY to the receipt's own Unity ID, and REFUSES any
    receipt that names another beneficiary (MERIT_MISATTRIBUTION). The
    derivative relationship (disciple learns from holder) enables the
    work; the work earns the merit. (Accrual is origin; transfer is a
    separate, receipted path — transfers move value, never standing.)

HARD RULES, in code, not in comments:
  * Tokens come into existence ONLY through tokenize() -> _mint().
    No other function in this module instantiates a token structure
    (assert_single_mint_path() proves it by AST on every test run).
  * _mint() REFUSES kind "unity": Unity is minted only by the fuse
    trigger in economics/fuse.py (reused, not duplicated).
  * Unity holdings are bound ONLY at genesis (_bind_genesis); NO function
    re-binds them (assert_no_unity_rebind() proves it by AST). The bound
    sale is dead — the module contains no bound_sale, no SaleRecord.
  * Merit ownership changes ONLY through merit_transfer() (AST-proven);
    origin fields are immutable (no code path rewrites them).
  * Nothing pre-minted, nothing airdropped, no backdoor: the module
    contains no airdrop/prefund/genesis-allocation function and the AST
    test asserts the absence by name.
  * UNKNOWN merit never tokenizes: the receipt must CLAIM provenance
    VERIFIED *and* tokenize() must verify the gate's Ed25519 signature
    and the prev_hash chain link itself — a self-asserted "VERIFIED"
    string with no (or a bad) signature is refused with zero tokens,
    zero ledger change. The bundle's gate_verdict/gate_verification
    record what tokenize() established, never the caller's claim.
  * The peg ratio E is HELD_FOR_DAVID: eFuse emission REFUSES with
    reason PEG_E_UNSET until David's word sets it via set_peg_ratio().
  * TESTNET ONLY. The pipeline refuses any receipt whose schema is not
    testnet, any non-testnet Unity ID, and operates only against
    dualis.relay.v1.testnet with test keys.

Reused vs built:
  * REUSED: economics/fuse.py — the fuse trigger stays the SOLE Unity
    genesis path (state machine ARMED->TRIGGERED->SPENT, David-signed
    authorization, replay-proof). economics/tokenomics.py — the peg
    formula (eFuse = merit / E) and the provenance register semantics
    (VERIFIED gates, UNKNOWN never pays). writes.py — dclm_commit is the
    only write path; meter.py's pattern (build_receipt returns the
    domain receipt so the envelope signs it).
  * BUILT HERE: the four token formats as exact field specs, the
    receipt->token pipeline, the _mint() sole-path factory, the peg-E
    gate with David's-authority setter, the transferable Merit ledger
    with immutable origin + origin-based standing(), the Merit transfer
    sole-path with signed MERIT_TRANSFER receipts, the append-only Honor
    ledger, the merit-misattribution refusal, the production-schema
    refusal, and the AST exclusivity proofs.
"""

import ast
import base64
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    PurificationRefused,
    purify_input,
    purify_output,
    purify_transition,
)
from writes import (  # noqa: E402 — the single commit path
    CommitStore,
    dclm_commit,
    sign_commit,
    verify_commit,
)
from compute import (  # noqa: E402 — reuse the existing test key material
    KEY_ID,
    PROVENANCE_LABELS,
    TEST_PRIV_KEY,
    TEST_PUB_KEY,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.tokenize.v1.testnet"
NETWORK = "dualis.relay.v1.testnet"   # the ONLY relay this pipeline serves
IDENTITY_PREFIX = "unity:testnet:"

EFUSE_TOKEN_SCHEMA = "unity.token.efuse.v1.testnet"
UNITY_TOKEN_SCHEMA = "unity.token.unity.v1.testnet"

# The commit kinds tokenization writes through (added to the rights.py
# whitelist with receipt-logged justification — see DECISIONS note below).
KIND_TOKEN_MINT = "TOKEN_MINT"
KIND_MERIT_ACCRUAL = "MERIT_ACCRUAL"
KIND_HONOR_RECORD = "HONOR_RECORD"
KIND_MERIT_TRANSFER = "MERIT_TRANSFER"

# Receipt kinds the pipeline accepts at its gate.
RECEIPT_WORK = "work"          # verified work -> Merit + eFuse
RECEIPT_DONATION = "donation"  # donation     -> Honor only
RECEIPT_GENESIS = "genesis"    # fuse event   -> Unity holding bind (no mint)
RECEIPT_KINDS = frozenset({RECEIPT_WORK, RECEIPT_DONATION, RECEIPT_GENESIS})

DONATION_KINDS = ("efuse", "fiat")

# Any receipt naming one of these is trying to credit merit to an ID for
# another ID's work — refused (derivative merit regeneration).
_MISATTRIBUTION_KEYS = frozenset({
    "credit_to", "beneficiary", "on_behalf_of", "assign_to", "for_id",
    "for_identity", "delegate_to",
})

# --- verified provenance: the gate signature (CRITICAL-5 closure) ---------
# A receipt's "provenance" string is a CLAIM. tokenize() ESTABLISHES
# "VERIFIED" itself — it never trusts the caller's label. Every receipt
# must carry an Ed25519 signature from the DCLM testnet gate over the
# canonical gate body (see _gate_signed_body), plus a prev_hash linking
# it into this engine's gate chain. No signature (or a bad one, or a
# broken chain link) -> refused, even when the caller asserts
# provenance="VERIFIED". TESTNET ONLY: the gate key pair lives in
# ../keys/ (test keys, never production); production must wire a real
# gate signer and refuse anything else.
GATE_KEY_ID = KEY_ID                  # the testnet gate's key identity
GATE_PUBKEY_PATH = TEST_PUB_KEY       # what tokenize() verifies against
GATE_PRIVKEY_PATH = TEST_PRIV_KEY     # what the gate (tests) signs with
GATE_SIG_ALG = "Ed25519"
GENESIS_CHAIN_ANCHOR = "0" * 64       # prev_hash of a chain's first receipt

# --- refusal reasons --------------------------------------------------------
REASON_INVALID_RECEIPT = "INVALID_RECEIPT"
REASON_UNVERIFIED_RECEIPT = "UNVERIFIED_RECEIPT"
REASON_CHAIN_BREAK = "CHAIN_BREAK"    # prev_hash does not link the gate chain
REASON_UNKNOWN_PROVENANCE = "UNKNOWN_PROVENANCE"
REASON_MISSING_UNITY_ID = "MISSING_UNITY_ID"
REASON_INVALID_UNITY_ID = "INVALID_UNITY_ID"
REASON_PRODUCTION_SCHEMA = "PRODUCTION_SCHEMA_REFUSED"
REASON_PEG_E_UNSET = "PEG_E_UNSET"
REASON_PEG_AUTHORITY = "PEG_AUTHORITY_REFUSED"
REASON_NON_POSITIVE_E = "NON_POSITIVE_E"
REASON_NON_POSITIVE_MERIT = "NON_POSITIVE_MERIT"
REASON_UNSUPPORTED_RECEIPT_KIND = "UNSUPPORTED_RECEIPT_KIND"
REASON_UNITY_MINT_REFUSED = "UNITY_MINT_REFUSED"
REASON_MERIT_MISATTRIBUTION = "MERIT_MISATTRIBUTION"
REASON_GENESIS_CONFLICT = "GENESIS_CONFLICT"
REASON_XFER_UNVERIFIED_IDENTITY = "TRANSFER_UNVERIFIED_IDENTITY"
REASON_XFER_SAME_IDENTITY = "TRANSFER_SAME_IDENTITY"
REASON_XFER_NON_POSITIVE = "TRANSFER_NON_POSITIVE_AMOUNT"
REASON_XFER_INSUFFICIENT = "TRANSFER_INSUFFICIENT_MERIT"
REASON_XFER_EMPTY_REASON = "TRANSFER_EMPTY_REASON"
# Sender-authorization gates (David's closure, 2026-10-06 — CRITICAL-1):
# every Merit transfer must carry the sender's Ed25519 signature over the
# canonical transfer body (op/from/to/amount/reason/nonce). The sender's
# Unity ID IS sha256(sender pubkey), so the key binds to the ID.
REASON_XFER_UNAUTHORIZED = "TRANSFER_UNAUTHORIZED"    # no/malformed auth
REASON_XFER_KEY_MISMATCH = "TRANSFER_KEY_MISMATCH"   # pubkey not the sender's
REASON_XFER_BAD_SIGNATURE = "TRANSFER_BAD_SIGNATURE" # signature fails verify
REASON_XFER_REPLAY = "TRANSFER_REPLAY"               # nonce already used


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TokenizeError(Exception):
    """Base for tokenization failures."""


class TokenizeRefused(TokenizeError):
    """Structural refusal: the receipt/request was refused. Carries
    .reason. Nothing was minted, nothing was written."""

    def __init__(self, reason, detail=""):
        super().__init__(f"tokenize refused [{reason}]: {detail}")
        self.reason = reason
        self.detail = detail


class UnityMintRefused(TokenizeError):
    """_mint() was asked for kind 'unity'. Unity is minted ONLY by the
    fuse trigger in economics/fuse.py — never here."""


def _purify_reason_code(exc):
    """Extract the [REASON] code from a PurificationRefused message
    ("[REASON] at path: detail"). Unknown shapes -> "UNKNOWN"."""
    msg = str(exc)
    if msg.startswith("["):
        end = msg.find("]")
        if end > 1:
            return msg[1:end]
    return "UNKNOWN"


def _purify_reason_to_tokenize(exc):
    """Contract bridge: map the medium's refusal code to this pipeline's
    refusal reason for tokenize(). The purify check runs first; the
    pipeline's signed, logged TokenizeRefused contract holds."""
    code = _purify_reason_code(exc)
    return {
        "NO_IDENTITY": REASON_MISSING_UNITY_ID,
        "NOT_TESTNET_IDENTITY": REASON_INVALID_UNITY_ID,
        "INVALID_PROVENANCE": REASON_UNKNOWN_PROVENANCE,
        "UNLABELED_CLAIM": REASON_INVALID_RECEIPT,
    }.get(code, REASON_INVALID_RECEIPT)


def _purify_reason_to_transfer(exc):
    """Contract bridge: map the medium's refusal code to this pipeline's
    refusal reason for merit_transfer()."""
    code = _purify_reason_code(exc)
    if code in ("NO_IDENTITY", "NOT_TESTNET_IDENTITY"):
        return REASON_XFER_UNVERIFIED_IDENTITY
    return REASON_INVALID_RECEIPT


# ---------------------------------------------------------------------------
# Token formats — exact field specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EFuseToken:
    """The eFuse emission token. Carries the fuse that emits Unity.

    Fields:
      schema         — "unity.token.efuse.v1.testnet"
      token_type     — "EFUSE"
      token_id       — sha256 hex over the canonical unsigned body
      owner_unity_id — the Unity ID this token is bound to (no anonymous)
      amount         — eFuse emitted (merit_value / peg_E)
      peg_E          — the peg ratio E actually used for this emission
      epoch          — epoch ref (int) or None
      action_ref     — the gated receipt's kind ("work")
      merit_proof_ref— manifest_hash of the gated receipt that earned it
      provenance     — "DERIVED" (computed in-process by DCLM)
      issued_at      — ISO timestamp
      testnet        — True, always
      note           — honesty notes

    No transfer method exists here: eFuse movements happen only through
    the economics ledger functions (economics/wallet.py), never through
    a direct transfer call. The token is the emission record, bound.
    """
    schema: str
    token_type: str
    token_id: str
    owner_unity_id: str
    amount: float
    peg_E: float
    epoch: object
    action_ref: str
    merit_proof_ref: str
    provenance: str
    issued_at: str
    testnet: bool
    note: str = ""


@dataclass(frozen=True)
class MeritRecord:
    """Merit — the TRANSFERABLE token of earned value.

    ONE accrual event, frozen forever. Every record carries its IMMUTABLE
    origin: origin_earner_id + origin_receipt_ref, set once at accrual,
    never rewritten by any code path (the AST hook asserts no rewrite
    exists; the wallet layer never carries origin fields at all).

    Fields: schema, record_type "MERIT_ACCRUAL", record_id, unity_id (the
    earner — the receipt's own Unity ID, always), origin_earner_id
    (IMMUTABLE — the standing source; equals unity_id at accrual),
    origin_receipt_ref (IMMUTABLE — manifest_hash of the gated receipt
    that earned it), delta (the accrual), score_before / score_after
    (the earner's OWNED balance around this accrual), merit_proof_ref,
    epoch, provenance "DERIVED", issued_at, testnet True.

    Ownership vs origin, the structural distinction:
      * owner_unity_id is NOT on this record — ownership lives in the
        engine's slice registry and changes ONLY via merit_transfer().
      * origin_earner_id is ON this record and NEVER changes.
      * standing(identity) sums delta where origin_earner_id == identity
        — earned standing, cannot be bought.
      * merit_balance(identity) sums what the identity currently owns —
        economic value, what a transfer moves.
    """
    schema: str
    record_type: str
    record_id: str
    unity_id: str
    origin_earner_id: str
    origin_receipt_ref: str
    delta: float
    score_before: float
    score_after: float
    merit_proof_ref: str
    epoch: object
    provenance: str
    issued_at: str
    testnet: bool


@dataclass(frozen=True)
class HonorRecord:
    """Honor is a PERMANENT RECORD (donations). Append-only, never spent,
    never transferred.

    Fields: schema, record_type "HONOR_RECORD", record_id, unity_id,
    donation_receipt_ref, donation_kind ("efuse"|"fiat"), donation_amount,
    provenance, permanent True, spendable False, transferable False,
    issued_at, testnet True.

    Structural: the ledger is a per-Unity-ID LIST that only appends.
    No spend/redeem/convert function exists in this module — the AST
    test asserts the absence by name.
    """
    schema: str
    record_type: str
    record_id: str
    unity_id: str
    donation_receipt_ref: str
    donation_kind: str
    donation_amount: float
    provenance: str
    permanent: bool
    spendable: bool
    transferable: bool
    issued_at: str
    testnet: bool


@dataclass(frozen=True)
class UnityToken:
    """FORMAT SPEC for the Unity token — identity-bound, NON-TRANSFERABLE.

    Fields: schema "unity.token.unity.v1.testnet", token_type "UNITY",
    token_id, unity_id (the ONE bound identity — never re-bound),
    genesis_ref (the fuse trigger manifest — immutable),
    merit_proof_ref (provenance of origin),
    provenance, issued_at, testnet True.

    Structural non-transferability: this format has NO transfer field
    and NO transfer method, and — since David's 2026-10-06 ~3:35 AM EDT
    word — there is NO module-level transfer path either. The
    bound-transfer-sale concept is DEAD: no bound_sale, no SaleRecord,
    no UNITY_SALE commit kind. A Unity token never changes hands. Ever.

    THIS CLASS IS NEVER INSTANTIATED IN THIS MODULE. The fuse trigger
    (economics/fuse.py trigger_fuse) is the SOLE genesis path for Unity.
    _mint("unity") raises UnityMintRefused. The AST test asserts zero
    instantiations of UnityToken here on every run.
    """


@dataclass(frozen=True)
class UnityHolding:
    """DCLM-side mirror of a Unity holding: which Unity ID holds which
    Unity token. Bound ONCE at genesis via _bind_genesis(); never
    re-bound — there is no transfer path, so there is nothing to call to
    move one."""
    token_id: str
    holder: str            # the one bound identity — immutable after bind
    genesis_ref: str       # fuse trigger manifest — immutable
    merit_proof_ref: str   # provenance of origin — immutable


@dataclass(frozen=True)
class TransferReceipt:
    """The signed receipt of a Merit transfer. Not a token — the proof
    that owned Merit changed hands through the sole legal path.

    Fields: schema, record_type "MERIT_TRANSFER", transfer_id, from_id,
    to_id, amount, reason (the human-readable why — "sale", "gift", …;
    receipted, never empty), moves (the slice-level moves, each naming
    its slice_id, record_id, origin_earner_id, and moved amount —
    origin carried FORWARD, never rewritten), provenance "DERIVED",
    issued_at, testnet True.

    Standing note, structural: the transfer moves OWNERSHIP only. Origin
    fields ride along unchanged; standing(identity) is origin-based, so
    neither party's standing moves. A buyer gains economic value and
    ZERO standing — by construction, not by promise.
    """
    schema: str
    record_type: str
    transfer_id: str
    from_id: str
    to_id: str
    amount: float
    reason: str
    moves: tuple
    provenance: str
    issued_at: str
    testnet: bool


# ---------------------------------------------------------------------------
# The sole mint factory — ONE private _mint()
# ---------------------------------------------------------------------------

_BUILDERS = {
    "efuse": EFuseToken,
    "merit": MeritRecord,
    "honor": HonorRecord,
}


def _mint(kind, **fields):
    """THE single place any token/record structure is created in this
    module. kind is "efuse" | "merit" | "honor". Anything else — including
    "unity" — raises. No other function here instantiates the token
    classes (proven by assert_single_mint_path via AST)."""
    if kind == "unity":
        raise UnityMintRefused(
            "Unity is minted ONLY by the fuse trigger in "
            "economics/fuse.py — this module has no Unity mint path."
        )
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise TokenizeError(f"unknown mint kind {kind!r} — nothing minted")
    return builder(**fields)


def _transfer_receipt(**fields):
    """Build a TransferReceipt. The ONLY constructor of transfer
    receipts, called only by merit_transfer(). Not a mint — an
    ownership-change proof."""
    return TransferReceipt(**fields)


def mint_paths():
    """The exhaustive list of mint paths, as code.

    For eFuse/Merit/Honor: exactly one — this module's tokenize() ->
    _mint() -> dclm_commit. For Unity: exactly one — economics/fuse.py
    Fuse.trigger_fuse (the genesis, once, David-signed). There is no
    third path; assert_single_mint_path() enforces the first half
    structurally on every test run.
    """
    return [
        "token_engine.tokenize -> _mint('efuse') -> dclm_commit('TOKEN_MINT')"
        " — the ONLY eFuse mint path",
        "token_engine.tokenize -> _mint('merit') -> dclm_commit('MERIT_ACCRUAL')"
        " — the ONLY Merit accrual path (earner's ID only; ownership later"
        " moves only via merit_transfer, origin immutable)",
        "token_engine.tokenize -> _mint('honor') -> dclm_commit('HONOR_RECORD')"
        " — the ONLY Honor record path (append-only, never spent)",
        "economics/fuse.py Fuse.trigger_fuse — the SOLE Unity genesis "
        "path (once, David-signed). token_engine has no Unity mint.",
    ]


def unity_transfer_paths():
    """The exhaustive list of Unity transfer paths, as code. It is EMPTY.

    Unity is non-transferable — no sale, no gift, no re-bind, no
    exceptions. The bound-transfer-sale concept is dead: no bound_sale,
    no SaleRecord, no UNITY_SALE kind. assert_no_unity_rebind() enforces
    the emptiness structurally on every test run."""
    return []


def merit_transfer_paths():
    """The exhaustive list of Merit ownership-transfer paths, as code.
    Exactly one: merit_transfer() — from-ID -> to-ID, both verified,
    amount covered by the sender's owned balance, reason receipted,
    SENDER AUTHORIZATION REQUIRED (Ed25519 signature by the sender's
    key over the canonical transfer body; unsigned, wrong-key, and
    replayed transfers are refused), signed MERIT_TRANSFER receipt,
    origin fields carried forward unchanged. No other function changes
    Merit ownership; assert_single_merit_transfer_path() enforces this
    by AST on every test run."""
    return [
        "token_engine.Tokenizer.merit_transfer -> dclm_commit('MERIT_TRANSFER')"
        " — the SOLE legal Merit ownership-transfer path (origin"
        " immutable; standing never moves)",
    ]


def _iter_calls_with_stack(tree):
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


def assert_single_mint_path():
    """Module-level test hook: prove by AST that _mint() is the only
    function in this module that creates token structures, that
    UnityToken is never instantiated here, that no bound-sale machinery
    exists (SaleRecord never constructed — the concept is dead), and
    that no forbidden machinery (airdrop/pre-fund/backdoor) exists.

    Raises AssertionError on any violation. Called by test_tokenize.py
    on every run."""
    import token_engine as _self  # the module under test, by its own name

    source = inspect.getsource(_self)
    tree = ast.parse(source)

    token_classes = {"EFuseToken", "MeritRecord", "HonorRecord", "UnityToken",
                     "TransferReceipt"}
    creators = {}   # func name -> set of token classes instantiated
    unity_created = []
    transfer_built = {}

    for stack, node in _iter_calls_with_stack(tree):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else None
        if name in token_classes:
            outer = stack[0] if stack else "<module>"
            creators.setdefault(outer, set()).add(name)
            if name == "UnityToken":
                unity_created.append(stack)
        if name == "TransferReceipt":
            outer = stack[0] if stack else "<module>"
            transfer_built.setdefault(outer, set()).add(name)

    bad = {f: sorted(c) for f, c in creators.items()
           if f not in ("_mint", "_transfer_receipt")}
    assert not bad, (
        "MINT PATH VIOLATION: token structures created outside _mint() / "
        f"_transfer_receipt(): {bad}"
    )
    assert not unity_created, (
        "UNITY MINT VIOLATION: UnityToken instantiated in this module at "
        f"{unity_created} — the fuse trigger is the sole genesis path"
    )
    bad_xfer = {f for f in transfer_built if f != "_transfer_receipt"}
    assert not bad_xfer, (
        "TRANSFER RECEIPT VIOLATION: TransferReceipt built outside "
        f"_transfer_receipt(): {bad_xfer}"
    )
    # The bound sale is dead: no SaleRecord class, no bound_sale
    # function, no sale-ish machinery may exist.
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    class_names = {n.name for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef)}
    dead = [n for n in names | class_names
            if "bound_sale" in n.lower() or "salerecord" in n.lower()
            or "sale_record" in n.lower()]
    assert not dead, f"BOUND-SALE MACHINERY PRESENT (concept is dead): {dead}"
    # Absence of machinery: no airdrop / pre-fund / backdoor / honor-spend.
    # (merit_transfer is LEGAL now — David's 2026-10-06 word — so the
    # merit-transfer name family is deliberately NOT forbidden.)
    forbidden = ("airdrop", "prefund", "pre_fund", "backdoor", "genesis_alloc",
                 "honor_spend", "spend_honor", "redeem_honor")
    lower = {n.lower() for n in names}
    hits = [f for f in forbidden if any(f in n for n in lower)]
    assert not hits, f"FORBIDDEN MACHINERY PRESENT: {hits}"
    return True


def assert_no_unity_rebind():
    """Module-level test hook: prove by AST that NO function re-binds a
    Unity token — the unity registry is written ONLY by _bind_genesis()
    (the genesis bind), and no transfer-ish machinery for Unity exists
    anywhere (the bound-transfer-sale concept is dead).

    Raises AssertionError on any violation. Called by test_tokenize.py
    on every run."""
    import token_engine as _self

    source = inspect.getsource(_self)
    tree = ast.parse(source)

    # (a) The unity registry is stored into ONLY by _bind_genesis.
    # tokenize() binds at genesis THROUGH its helper _bind_genesis();
    # __init__ creates the empty dict (Attribute store, not a subscript
    # store — allowed explicitly anyway).
    allowed = {"_bind_genesis", "__init__"}
    violations = []

    class AssignV(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def _check_subscript(self, target):
            if (isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "_unity_registry"):
                if not (set(self.stack) & allowed):
                    violations.append(
                        (".".join(self.stack), "subscript-store"))

        def visit_Assign(self, node):
            for target in node.targets:
                self._check_subscript(target)
            self.generic_visit(node)

        def visit_AugAssign(self, node):
            self._check_subscript(node.target)
            self.generic_visit(node)

    AssignV().visit(tree)

    for stack, node in _iter_calls_with_stack(tree):
        # .update()/.pop()/.clear()/.setdefault() on the registry.
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in (
                "update", "pop", "popitem", "clear", "setdefault"):
            val = func.value
            if (isinstance(val, ast.Attribute)
                    and val.attr == "_unity_registry"):
                if not (set(stack) & allowed):
                    violations.append((".".join(stack), func.attr))

    assert not violations, (
        "UNITY REBIND VIOLATION: unity registry mutated outside "
        f"_bind_genesis(): {violations}"
    )

    # (b) No transfer-ish function names exist for Unity. merit_transfer
    # is the legal Merit path — it must NOT touch Unity, and the name
    # scan below excludes it explicitly, along with its helpers
    # (_transfer_receipt, _require_transfer_identity, and
    # _require_transfer_authorization — the CRITICAL-1 sender-
    # authorization gate for Merit transfers, merit-only).
    names = {n.name.lower() for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    transferish = [n for n in names
                   if (("transfer" in n or "rebind" in n or "reassign" in n
                        or "resell" in n or "bound_sale" in n
                        or "move_unity" in n or "gift_unity" in n)
                       and n not in ("merit_transfer", "merit_transfer_paths",
                                     "unity_transfer_paths",
                                     "_transfer_receipt",
                                     "_require_transfer_identity",
                                     "_require_transfer_authorization",
                                     "_purify_reason_to_transfer",
                                     "assert_single_merit_transfer_path",
                                     "assert_no_unity_rebind"))]
    assert not transferish, f"UNITY TRANSFER MACHINERY PRESENT: {transferish}"

    # (c) UnityHolding is constructed ONLY in _bind_genesis.
    holders = {}
    for stack, node in _iter_calls_with_stack(tree):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else None
        if name == "UnityHolding":
            outer = stack[0] if stack else "<module>"
            holders.setdefault(outer, set()).add(name)
    bad_holders = {f for f in holders if f != "_bind_genesis"}
    assert not bad_holders, (
        "UNITY HOLDING VIOLATION: UnityHolding built outside "
        f"_bind_genesis(): {bad_holders}"
    )
    return True


def assert_single_merit_transfer_path():
    """Module-level test hook: prove by AST that Merit OWNERSHIP changes
    ONLY in merit_transfer() — slices are created only in _accrue_merit()
    (the accrual), and the owner_unity_id of a slice is rewritten only in
    merit_transfer(). No other function can move Merit ownership.

    Raises AssertionError on any violation. Called by test_tokenize.py
    on every run."""
    import token_engine as _self

    source = inspect.getsource(_self)
    tree = ast.parse(source)

    violations = []

    class SliceV(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            # list mutation on the slice registry
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in (
                    "append", "extend", "pop", "remove", "clear", "insert"):
                val = func.value
                if (isinstance(val, ast.Attribute)
                        and val.attr == "_merit_slices"):
                    if not (set(self.stack)
                            & {"_accrue_merit", "merit_transfer"}):
                        violations.append(
                            (".".join(self.stack), f".{func.attr}()"))
            self.generic_visit(node)

        def visit_Subscript(self, node):
            # owner_unity_id rewrite: sl["owner_unity_id"] = ...
            if (isinstance(node.ctx, ast.Store)
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "owner_unity_id"):
                if "merit_transfer" not in self.stack:
                    violations.append(
                        (".".join(self.stack), "owner_unity_id store"))
            self.generic_visit(node)

    SliceV().visit(tree)

    assert not violations, (
        "MERIT TRANSFER PATH VIOLATION: merit ownership mutated outside "
        f"merit_transfer()/_accrue_merit(): {violations}"
    )

    # Origin fields are NEVER rewritten: no Store to origin_earner_id or
    # origin_receipt_ref anywhere (they are set once, in dict literals,
    # at accrual — dict-display keys are not Store nodes).
    class OriginV(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Subscript(self, node):
            if (isinstance(node.ctx, ast.Store)
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value in ("origin_earner_id",
                                             "origin_receipt_ref")):
                violations.append(
                    (".".join(self.stack),
                     f"{node.slice.value} REWRITE — origin is immutable"))
            self.generic_visit(node)

    OriginV().visit(tree)
    assert not violations, (
        "ORIGIN IMMUTABILITY VIOLATION: origin fields rewritten: "
        f"{violations}"
    )

    # No OTHER transfer-ish function names for Merit.
    names = {n.name.lower() for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    transferish = [n for n in names
                   if "transfer" in n
                   and n not in ("merit_transfer", "merit_transfer_paths",
                                 "unity_transfer_paths",
                                 "_transfer_receipt",
                                 "_require_transfer_identity",
                                 "_require_transfer_authorization",
                                 "_purify_reason_to_transfer",
                                 "assert_single_merit_transfer_path",
                                 "assert_no_unity_rebind")]
    assert not transferish, f"EXTRA MERIT TRANSFER MACHINERY: {transferish}"
    return True


# ---------------------------------------------------------------------------
# The commit store — DCLM-internal adapter for tokenization writes
# ---------------------------------------------------------------------------

def _normalize_jsonable(obj):
    """Tuples -> lists, recursively, so the signed receipt body is
    canonical JSON with no tuple artifacts."""
    if isinstance(obj, tuple):
        return [_normalize_jsonable(v) for v in obj]
    if isinstance(obj, list):
        return [_normalize_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _normalize_jsonable(v) for k, v in obj.items()}
    return obj


class _TokenCommitStore(CommitStore):
    """Lets writes.dclm_commit drive the tokenization ledgers.

    apply_write performs THE one mutation for this commit (merit accrual
    / merit transfer / honor append / eFuse registry insert / unity
    genesis bind) — the engine's ledgers are never touched except inside
    apply_write, which dclm_commit calls exactly once, only after a
    DCLM-issued GRANT.

    build_receipt returns the token/record structure itself, so the
    signed commit envelope signs the token — the token IS the receipt.
    """

    def __init__(self, engine, structure, mutate):
        self._engine = engine
        self._structure = structure   # the _mint()/_transfer_receipt() record
        self._mutate = mutate         # zero-arg: perform the ledger mutation

    def apply_write(self, kind, payload):
        self._mutate()
        return {"structure": type(self._structure).__name__,
                "id": getattr(self._structure, "token_id",
                              getattr(self._structure, "record_id",
                                      getattr(self._structure, "transfer_id",
                                              "?")))}

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        # The token/record is the receipt: same bytes signed every time.
        import dataclasses
        body = _normalize_jsonable(dataclasses.asdict(self._structure))
        body["commit_kind"] = kind
        body["rights"] = {
            "verdict": rights_verdict.verdict,
            "reason": rights_verdict.reason,
        }
        return body

    def append_receipt(self, envelope):
        self._engine._receipt_log.append(envelope)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

def _utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


ED25519_HELPER = os.path.join(_HERE, "ed25519.js")


def _verify_sender_signature(pubkey_der: bytes, msg: bytes,
                             sig_b64: str) -> bool:
    """Ed25519-verify a sender transfer authorization. True/False —
    never raises on bad data. The engine holds NO private keys and NO
    key registry: the sender's Unity ID is sha256(pubkey), so the key
    the caller presents is bound to the ID cryptographically."""
    try:
        fd, path = tempfile.mkstemp(prefix="te-auth-", suffix=".der")
        os.fchmod(fd, 0o600)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(pubkey_der)
            proc = subprocess.run(
                ["node", ED25519_HELPER, "verify", path, sig_b64],
                input=msg, capture_output=True, timeout=30,
            )
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        return proc.returncode == 0
    except Exception:
        return False


def _canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


# -- gate-signed receipts: verified provenance (CRITICAL-5 closure) ---------
def _gate_signed_body(r):
    """The canonical gate body: exactly the receipt fields the gate
    signature covers. The caller's "provenance" string is DELIBERATELY
    excluded — it is a claim, not a fact, and is never part of what the
    signature attests. Envelope keys (signature/key_id/sig_alg) are
    excluded too. kind-specific detail is included so post-signing
    tampering with values breaks the signature."""
    body = {
        "schema": r.get("schema"),
        "receipt_id": r.get("receipt_id"),
        "manifest_hash": r.get("manifest_hash"),
        "unity_id": r.get("unity_id"),
        "kind": r.get("kind"),
        "epoch": r.get("epoch"),
        "prev_hash": r.get("prev_hash"),
    }
    kind = r.get("kind")
    if kind == RECEIPT_WORK:
        body["merit_value"] = r.get("merit_value")
    elif kind == RECEIPT_DONATION:
        body["donation"] = r.get("donation")
    elif kind == RECEIPT_GENESIS:
        body["token_id"] = r.get("token_id")
        body["merit_proof_ref"] = r.get("merit_proof_ref")
    if isinstance(r.get("detail"), dict):
        body["detail"] = r["detail"]
    return body


def _gate_sign(msg: bytes, privkey_path=GATE_PRIVKEY_PATH) -> str:
    """Ed25519-sign the canonical gate body. TESTNET ONLY — the gate
    (or a test standing in for it) holds the private key."""
    proc = subprocess.run(
        ["node", ED25519_HELPER, "sign", privkey_path],
        input=msg, capture_output=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gate signing failed: {proc.stderr.decode()!r}")
    return proc.stdout.decode().strip()


def _gate_verify(msg: bytes, sig_b64: str) -> bool:
    """Ed25519-verify a gate signature against the gate PUBLIC key.
    True/False — never raises on bad data. This is the verification
    tokenize() itself performs; the engine holds no private keys."""
    try:
        proc = subprocess.run(
            ["node", ED25519_HELPER, "verify", GATE_PUBKEY_PATH, sig_b64],
            input=msg, capture_output=True, timeout=30,
        )
        return proc.returncode == 0
    except Exception:
        return False


def sign_gate_receipt(receipt, privkey_path=GATE_PRIVKEY_PATH,
                      key_id=GATE_KEY_ID):
    """TESTNET ONLY: the gate signs a receipt.

    The caller sets every body field first — including prev_hash, which
    must link the engine's gate chain (GENESIS_CHAIN_ANCHOR for the
    first receipt, then each accepted receipt's manifest_hash). Returns
    a copy of the receipt carrying key_id, sig_alg, and the base64
    Ed25519 signature over the canonical gate body. Production callers
    must obtain signatures from the real gate signer; this helper
    exists so tests can stand in for the gate with test keys only.
    """
    body = _gate_signed_body(receipt)
    sig = _gate_sign(_canonical_bytes(body), privkey_path)
    out = dict(receipt)
    out["key_id"] = key_id
    out["sig_alg"] = GATE_SIG_ALG
    out["signature"] = sig
    return out


@dataclass
class TokenBundle:
    """What tokenize() returns: every signed token structure produced
    from one gated receipt, plus the Unity binding proof.

    efuse/merit/honor are signed dclm_commit envelopes (the token body is
    envelope['receipt']); each is None when the receipt kind does not
    produce it (donations never mint eFuse; work never records Honor).
    unity_binding is a DERIVED proof dict — NOT a mint (Unity mints only
    via the fuse).

    gate_verdict is the provenance label tokenize() ITSELF established
    for the input receipt — "VERIFIED" only when the gate signature
    verified and the chain link checked, never the caller's claim.
    gate_verification carries the evidence (key, algorithm, chain link).
    """
    unity_id: str
    schema: str = SCHEMA
    efuse: object = None
    merit: object = None
    honor: object = None
    unity_binding: dict = field(default_factory=dict)
    provenance: str = "DERIVED"
    gate_verdict: str = "UNVERIFIED"
    gate_verification: dict = field(default_factory=dict)
    issued_at: str = ""
    testnet: bool = True


class Tokenizer:
    """DCLM-side tokenization engine. TESTNET ONLY.

    Ledgers (all in-memory; the engine owns them, mutations happen only
    inside _TokenCommitStore.apply_write driven by dclm_commit):
      _merit_slices  : [slice] — the Merit ledger. Each slice:
                         {slice_id, record_id,
                          origin_earner_id, origin_receipt_ref (IMMUTABLE),
                          owner_unity_id (changes ONLY via merit_transfer),
                          amount}
      honor_ledger   : unity_id -> [HonorRecord] (append-only)
      efuse_registry : token_id -> EFuseToken body
      _unity_registry: token_id -> UnityHolding (bound ONCE at genesis;
                       NEVER re-bound — no transfer path exists)
    _peg_E: the peg ratio E, None until David's word (HELD_FOR_DAVID).

    The two Merit readings:
      merit_balance(identity) — what the identity OWNS (economic value;
                                moves on transfer).
      standing(identity)      — what the identity EARNED, origin-based
                                (earned standing; NEVER moves on transfer).
    """

    def __init__(self):
        self._merit_slices = []
        self._slice_seq = 0
        self.honor_ledger = {}
        self.efuse_registry = {}
        self._unity_registry = {}
        self._peg_E = None
        self._peg_provenance = None
        self._receipt_log = []   # every step receipted: commits + refusals
        # Gate chain: every ACCEPTED receipt's manifest_hash, hash-linked.
        # A new receipt's prev_hash must equal _gate_chain_head —
        # GENESIS_CHAIN_ANCHOR for the first receipt. The head advances
        # ONLY on a fully successful tokenize(); refusals (peg-unset,
        # bad signature, …) consume nothing, so a refused receipt stays
        # retryable. The chain is also replay protection: an accepted
        # receipt can never be re-accepted, because its prev_hash no
        # longer matches the head.
        self._gate_chain = []
        self._gate_chain_head = GENESIS_CHAIN_ANCHOR
        self._used_transfer_nonces = set()  # sender-auth nonce registry:
        # a transfer authorization nonce is single-use — replay refused

    def gate_chain_head(self):
        """Head of this engine's gate chain (GENESIS_CHAIN_ANCHOR until
        the first receipt is accepted). The next receipt's prev_hash
        must equal this."""
        return self._gate_chain_head

    def gate_chain(self):
        """The accepted gate receipts' manifest_hashes, in chain order."""
        return list(self._gate_chain)

    # -- the peg -----------------------------------------------------------
    def set_peg_ratio(self, E, authority):
        """Set the peg ratio E (1 eFuse ≡ E real-world energy units).

        authority must be {"authority": "david"} — David's word. This is
        marked HONESTLY: in this testnet module the setter cannot
        cryptographically verify David's presence, so the peg is labeled
        REPORTED (his word, asserted by the caller), never VERIFIED. The
        production setter must require his signed authorization; this
        stand-in refuses anything that does not name him.

        E must be a positive number. Returns the peg record.
        """
        auth = authority.get("authority") if isinstance(authority, dict) else None
        if auth != "david":
            self._log_refusal(REASON_PEG_AUTHORITY,
                              "peg E may only be set on David's word")
            raise TokenizeRefused(
                REASON_PEG_AUTHORITY,
                "set_peg_ratio requires authority {'authority': 'david'} — "
                "E is HELD_FOR_DAVID and is never invented here",
            )
        if isinstance(E, bool) or not isinstance(E, (int, float)) or E <= 0:
            self._log_refusal(REASON_NON_POSITIVE_E,
                              f"E must be a positive number, got {E!r}")
            raise TokenizeRefused(
                REASON_NON_POSITIVE_E,
                f"peg ratio E must be a positive number — got {E!r}",
            )
        self._peg_E = float(E)
        # REPORTED, not VERIFIED: the testnet stand-in cannot verify his
        # signature. Honest label, honest note.
        self._peg_provenance = (
            "REPORTED — David's word (asserted via testnet stand-in; "
            "unsigned — production setter must require his signature)"
        )
        return {"E": self._peg_E, "provenance": self._peg_provenance,
                "schema": SCHEMA, "testnet": True}

    def peg_ratio(self):
        """Return (E, provenance) or (None, 'HELD_FOR_DAVID')."""
        if self._peg_E is None:
            return None, "HELD_FOR_DAVID"
        return self._peg_E, self._peg_provenance

    # -- the pipeline -------------------------------------------------------
    def tokenize(self, receipt):
        """Receipt -> TokenBundle. Validates the gated receipt, computes
        eFuse/Merit/Honor outputs, mints ONLY via dclm_commit, returns
        the signed token structures.

        VERIFIED PROVENANCE (CRITICAL-5 closure): the caller's
        "provenance" string is never trusted. tokenize() verifies the
        receipt's Ed25519 gate signature itself (against the gate public
        key) and checks its prev_hash against the engine's gate chain.
        The bundle's gate_verdict/gate_verification record what
        tokenize() itself established — not what the caller claimed.
        A claimed "VERIFIED" with no (or a bad) signature, or a broken
        chain link, is refused with zero tokens.

        Raises TokenizeRefused (nothing minted, nothing written) when:
          * the receipt is not a testnet receipt (production schema/key)
          * the receipt is missing, malformed, or not Unity-bound
          * the gate signature is missing/invalid, or prev_hash does not
            link the gate chain (UNVERIFIED_RECEIPT / CHAIN_BREAK —
            UNKNOWN never tokenizes, and neither does self-asserted
            "VERIFIED")
          * the receipt names another beneficiary (MERIT_MISATTRIBUTION —
            merit is never credited for another ID's work)
          * kind "work" arrives while peg E is unset (PEG_E_UNSET)
        """
        r = receipt if isinstance(receipt, dict) else {}
        # PURIFY ON ENTRY: the medium first. No Unity-bound identity, no
        # labeled claims, no entry — PurificationRefused. A presented
        # signature that does not verify is refused here too. (The gated
        # receipt law — VERIFIED provenance, known kind, no
        # misattribution — is then enforced below by _require_gated.)
        # Contract bridge: the medium's refusal is translated into this
        # module's TokenizeRefused with the true reason — the purify
        # check still runs first (defense in depth). The refusal is
        # LOGGED in the engine's signed refusal trail, then RE-RAISED
        # as the medium's own PurificationRefused: the medium's refusal
        # propagates uniformly on every wired path (2026-10-06 purity
        # contract — no per-module exception translation).
        try:
            purify_input(
                {"identity": r.get("unity_id"), "action": "TOKENIZE",
                 "claims": [r]},
                context={"path": "token_engine.tokenize"},
            )
        except PurificationRefused as pexc:
            self._log_refusal(
                _purify_reason_to_tokenize(pexc), str(pexc))
            raise
        try:
            self._require_testnet_context(r)
            gated = self._require_gated(r)
        except TokenizeRefused as exc:
            self._log_refusal(exc.reason, exc.detail)
            raise

        uid = gated["unity_id"]
        epoch = gated.get("epoch")
        bundle = TokenBundle(
            unity_id=uid,
            issued_at=_utc_now(),
            # The provenance label on the output reflects the VERIFICATION
            # RESULT — what tokenize() itself established via the gate
            # signature + chain check — never the caller's claim.
            gate_verdict=gated["gate_verdict"],
            gate_verification=gated["gate_verification"],
            unity_binding={
                "unity_id": uid,
                "bound_from": gated["manifest_hash"],
                "bound_kind": gated["kind"],
                "provenance": "DERIVED",
                "note": ("Every token in this bundle carries this Unity ID. "
                         "No anonymous tokens exist."),
            },
        )

        kind = gated["kind"]
        if kind == RECEIPT_WORK:
            E = self._require_peg()          # PEG_E_UNSET refusal pre-mint
            merit_value = gated["merit_value"]
            merit_env = self._accrue_merit(uid, merit_value,
                                           gated["manifest_hash"], epoch)
            efuse_env = self._mint_efuse(uid, merit_value, E,
                                         gated["manifest_hash"], epoch)
            bundle.merit = merit_env
            bundle.efuse = efuse_env
        elif kind == RECEIPT_DONATION:
            # Honor only. Never Merit, never eFuse — the gift is the gift.
            bundle.honor = self._record_honor(
                uid, gated["manifest_hash"], gated["donation"], epoch)
        elif kind == RECEIPT_GENESIS:
            # Unity holding BIND (the token itself was minted by the fuse
            # trigger in economics/fuse.py — never here). The bind is
            # write-once: holdings NEVER re-bind (no transfer path).
            self._bind_genesis(uid, gated["token_id"],
                               gated["manifest_hash"],
                               gated.get("merit_proof_ref"))
            bundle.unity_binding["token_id"] = gated["token_id"]
            bundle.unity_binding["genesis_ref"] = gated["manifest_hash"]
            bundle.unity_binding["note"] = (
                "Unity genesis belongs to the fuse trigger "
                "(economics/fuse.py). This bundle binds the holding and "
                "proves it; it mints nothing. Unity never transfers — "
                "no sale, no gift, no re-bind."
            )
        # PURIFY ON EXIT: every token identity-bound, every claim
        # labeled; the minted envelopes' signatures verified. (The
        # genesis path carries the DERIVED binding proof, not a mint —
        # nothing there requires a signature.)
        out = purify_output(
            bundle,
            context={"path": "token_engine.tokenize",
                     "signed": kind != RECEIPT_GENESIS},
        )
        # The gate chain advances ONLY on full success: the accepted
        # receipt's manifest_hash becomes the new head. Refusals consume
        # nothing — a refused receipt stays retryable, and an accepted
        # one can never be re-accepted (its prev_hash no longer matches).
        self._gate_chain.append(gated["manifest_hash"])
        self._gate_chain_head = gated["manifest_hash"]
        return out

    # -- merit transfer: the SOLE legal Merit ownership-transfer path -----
    def merit_transfer(self, from_id, to_id, amount, reason, auth=None):
        """Transfer owned Merit: from-ID -> to-ID. The SOLE legal way
        Merit ownership changes hands (David's word, 2026-10-06).

        1. Both identities must be verified testnet Unity IDs
           (unity:testnet:...) — else TRANSFER_UNVERIFIED_IDENTITY.
        2. Sender and recipient must differ — else TRANSFER_SAME_IDENTITY.
        3. amount must be a positive number — else TRANSFER_NON_POSITIVE_AMOUNT.
        4. reason must be a non-empty string (sale, gift, … — receipted)
           — else TRANSFER_EMPTY_REASON.
        5. SENDER AUTHORIZATION (David's closure, 2026-10-06 —
           CRITICAL-1): the transfer must carry the sender's Ed25519
           signature over the canonical transfer body
           {op:"merit-transfer", from, to, amount, reason, nonce}.
           No auth -> TRANSFER_UNAUTHORIZED. The auth's pubkey must
           derive to the sender's Unity ID (sha256(pubkey)) — else
           TRANSFER_KEY_MISMATCH. A signature that fails verify ->
           TRANSFER_BAD_SIGNATURE. A reused nonce -> TRANSFER_REPLAY.
           The human's device signs; DCLM only verifies — the engine
           holds no private keys.
        6. The sender's OWNED balance must cover amount — else
           TRANSFER_INSUFFICIENT_MERIT.
        7. Ownership moves across the sender's slices (oldest first);
           receiver slices are created carrying the SAME origin fields
           forward. Origin is NEVER rewritten.
        8. Signed MERIT_TRANSFER receipt via dclm_commit, naming both
           IDs, the amount, the reason, and the slice-level moves.

        The recipient gains ECONOMIC VALUE (spendable, priced). Neither
        party's STANDING moves: standing() is origin-based, and origin
        never changes. A buyer gains value and ZERO standing — by
        construction.
        """
        # PURIFY ON ENTRY: the medium first. Both identities must be
        # Unity-bound before any transfer logic runs — anonymous or
        # forged identities are refused here as PurificationRefused.
        # (The module's own _require_transfer_identity checks then run
        # as defense in depth.) The medium's refusal is LOGGED, then
        # RE-RAISED uniform — see tokenize().
        try:
            purify_input(
                {"identities": [from_id, to_id],
                 "action": "MERIT_TRANSFER", "amount": amount,
                 "claims": [{"claim": "merit-transfer-request",
                             "provenance": "DERIVED"}]},
                context={"path": "token_engine.merit_transfer"},
            )
        except PurificationRefused as pexc:
            self._log_refusal(
                _purify_reason_to_transfer(pexc), str(pexc))
            raise
        try:
            sender = self._require_transfer_identity(from_id, "sender")
            recipient = self._require_transfer_identity(to_id, "recipient")
        except TokenizeRefused as exc:
            self._log_refusal(exc.reason, exc.detail)
            raise
        if sender == recipient:
            self._log_refusal(REASON_XFER_SAME_IDENTITY,
                              "sender and recipient are the same identity")
            raise TokenizeRefused(
                REASON_XFER_SAME_IDENTITY,
                "merit transfer requires two distinct identities",
            )
        if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                or amount <= 0):
            self._log_refusal(REASON_XFER_NON_POSITIVE,
                              f"transfer amount must be positive, got {amount!r}")
            raise TokenizeRefused(
                REASON_XFER_NON_POSITIVE,
                f"merit transfer amount must be a positive number — "
                f"got {amount!r}",
            )
        if not isinstance(reason, str) or not reason.strip():
            self._log_refusal(REASON_XFER_EMPTY_REASON,
                              "a transfer reason is required (sale, gift, …)")
            raise TokenizeRefused(
                REASON_XFER_EMPTY_REASON,
                "merit transfer needs a non-empty reason — every transfer "
                "is receipted with its why",
            )
        reason = reason.strip()
        # Gate 5 — SENDER AUTHORIZATION: the sender's signed consent.
        # Verified against the VALIDATED values above (stripped IDs,
        # float amount, stripped reason): the signature binds exactly
        # what the engine is about to move. Unsigned transfers are
        # refused — the public Unity ID alone authorizes nothing.
        self._require_transfer_authorization(sender, recipient,
                                             float(amount), reason, auth)
        balance = self.merit_balance(sender)
        if balance < amount:
            self._log_refusal(
                REASON_XFER_INSUFFICIENT,
                f"{sender!r} owns {balance} merit, transfer needs {amount}")
            raise TokenizeRefused(
                REASON_XFER_INSUFFICIENT,
                f"sender owns {balance} merit — cannot transfer {amount}; "
                "only owned (not originated) value moves",
            )

        # Allocate across the sender's slices, oldest first. Deterministic.
        need = float(amount)
        moves = []  # (slice_id, record_id, origin_earner_id, moved_amount)
        for sl in self._merit_slices:
            if need <= 0:
                break
            if sl["owner_unity_id"] != sender or sl["amount"] <= 0:
                continue
            take = min(need, sl["amount"])
            moves.append((sl["slice_id"], sl["record_id"],
                          sl["origin_earner_id"], take))
            need -= take

        transfer = _transfer_receipt(
            schema=SCHEMA,
            record_type="MERIT_TRANSFER",
            transfer_id=_sha256_hex(_canonical_bytes({
                "merit_transfer": sender, "to": recipient,
                "amount": float(amount), "reason": reason,
                "at": _utc_now()})),
            from_id=sender,
            to_id=recipient,
            amount=float(amount),
            reason=reason,
            moves=tuple(moves),
            provenance="DERIVED",
            issued_at=_utc_now(),
            testnet=True,
        )

        def mutate():
            # THE ownership change — the only one in this module.
            # Sender slices shrink (emptied ones removed); receiver
            # slices are created carrying the SAME origin fields
            # forward. Origin is never rewritten — standing() cannot
            # move here.
            remaining = {m[0]: m[3] for m in moves}  # slice_id -> take
            kept = []
            new_slices = []
            for sl in self._merit_slices:
                take = remaining.get(sl["slice_id"], 0)
                if take <= 0:
                    kept.append(sl)
                    continue
                if sl["amount"] > take:
                    kept.append({
                        **sl,
                        "amount": sl["amount"] - take,
                    })
                # else: fully consumed — dropped from kept
                self._slice_seq += 1
                new_slices.append({
                    "slice_id": f"sl{self._slice_seq:08d}",
                    "record_id": sl["record_id"],
                    # Origin carried FORWARD, never rewritten:
                    "origin_earner_id": sl["origin_earner_id"],
                    "origin_receipt_ref": sl["origin_receipt_ref"],
                    "owner_unity_id": recipient,
                    "amount": take,
                })
            self._merit_slices[:] = kept + new_slices

        return self._commit(KIND_MERIT_TRANSFER, sender, transfer, mutate,
                            before={"sender_owned": balance},
                            after={"sender_owned": balance - float(amount),
                                   "recipient": recipient})

    def _require_transfer_authorization(self, sender, recipient, amount,
                                        reason, auth):
        """Gate 5: prove the SENDER authorized this exact transfer.

        auth must be a dict carrying:
          pubkey_b64 — the sender's Ed25519 public key (DER, base64)
          signature  — b64 Ed25519 signature over the canonical body
          nonce      — single-use authorization nonce (hex string)

        Canonical body (both sides compute it identically):
          {"op": "merit-transfer", "from": sender, "to": recipient,
           "amount": float(amount), "reason": reason, "nonce": nonce}

        Checks, in order:
          auth present and well-formed      -> TRANSFER_UNAUTHORIZED
          sha256(pubkey) == sender ID suffix -> TRANSFER_KEY_MISMATCH
          signature verifies over the body  -> TRANSFER_BAD_SIGNATURE
          nonce not seen before (replay)    -> TRANSFER_REPLAY
        The nonce is consumed when the authorization passes
        verification — each signed authorization is single-ATTEMPT. A
        transfer refused AFTER auth (e.g. insufficient balance) still
        burns its nonce, so a stale auth can never execute later; the
        sender's device simply signs a fresh intent to retry.
        """
        def _refuse(code, detail):
            self._log_refusal(code, detail)
            raise TokenizeRefused(code, detail)

        if not isinstance(auth, dict):
            _refuse(REASON_XFER_UNAUTHORIZED,
                    "merit transfer needs the sender's signed transfer "
                    "authorization — unsigned transfers are refused")
        pubkey_b64 = auth.get("pubkey_b64")
        signature = auth.get("signature")
        nonce = auth.get("nonce")
        if (not isinstance(pubkey_b64, str) or not pubkey_b64
                or not isinstance(signature, str) or not signature
                or not isinstance(nonce, str) or not nonce):
            _refuse(REASON_XFER_UNAUTHORIZED,
                    "transfer authorization is malformed — it must carry "
                    "pubkey_b64, signature, and nonce")
        try:
            pubkey_der = base64.b64decode(pubkey_b64)
        except Exception:
            _refuse(REASON_XFER_UNAUTHORIZED,
                    "transfer authorization pubkey_b64 is not valid base64")
        # The key binds to the sender's Unity ID: the ID IS
        # unity:testnet:sha256(pubkey). A key that doesn't derive to the
        # sender's ID cannot authorize for that ID — no registry needed,
        # the binding is cryptographic.
        if (hashlib.sha256(pubkey_der).hexdigest()
                != sender[len(IDENTITY_PREFIX):]):
            _refuse(REASON_XFER_KEY_MISMATCH,
                    "transfer authorization key does not belong to the "
                    f"sender {sender!r} — refusing")
        body = {"op": "merit-transfer", "from": sender, "to": recipient,
                "amount": float(amount), "reason": reason, "nonce": nonce}
        if not _verify_sender_signature(pubkey_der, _canonical_bytes(body),
                                        signature):
            _refuse(REASON_XFER_BAD_SIGNATURE,
                    "sender transfer-authorization signature FAILED — "
                    "refused")
        if nonce in self._used_transfer_nonces:
            _refuse(REASON_XFER_REPLAY,
                    "transfer authorization nonce already used — replay "
                    "refused")
        self._used_transfer_nonces.add(nonce)

    def _require_transfer_identity(self, identity, role):
        if (not isinstance(identity, str) or not identity.strip()
                or not identity.startswith(IDENTITY_PREFIX)):
            raise TokenizeRefused(
                REASON_XFER_UNVERIFIED_IDENTITY,
                f"{role} identity {identity!r} is not a verified testnet "
                f"Unity ID (must start with {IDENTITY_PREFIX!r})",
            )
        return identity.strip()

    # -- the two Merit readings --------------------------------------------
    def merit_balance(self, identity):
        """ECONOMIC VALUE: the Merit this identity currently OWNS.

        Spendable, priced — what a transfer moves, what a buyer gains.
        Computed from the slice registry: sum of slice amounts whose
        owner_unity_id == identity.
        """
        return sum(sl["amount"] for sl in self._merit_slices
                   if sl["owner_unity_id"] == identity)

    def standing(self, identity):
        """EARNED STANDING: the Merit this identity EARNED, origin-based.

        The history, the reputation, the proof-of-work. Computed SOLELY
        from origin: sum of slice amounts whose origin_earner_id ==
        identity. Transfers copy origin forward unchanged, so standing
        NEVER moves on transfer — a buyer gains ZERO standing, by
        construction. The emission gate reads this, never the balance.
        """
        return sum(sl["amount"] for sl in self._merit_slices
                   if sl["origin_earner_id"] == identity)

    def merit_score(self, identity):
        """Owned Merit — the economic value (alias of merit_balance).

        HONESTY NOTE on the name (David's transfer word, 2026-10-06):
        before the transfer law this was accrual-only — a score that
        could only grow. Since Merit became transferable, owned Merit
        moves, so merit_score() reads the current owned balance (same as
        merit_balance()). The accrual-only reading is now standing().
        Kept under this name for API compatibility (meter/onboard
        readers); the law change is recorded, not silent — see
        economics/DECISIONS.md §13.
        """
        return self.merit_balance(identity)

    # -- gates --------------------------------------------------------------
    def _require_testnet_context(self, r):
        """Structural refusal: production schemas/keys never operate here."""
        schema = r.get("schema")
        if schema is not None and "testnet" not in str(schema).lower():
            raise TokenizeRefused(
                REASON_PRODUCTION_SCHEMA,
                f"receipt schema {schema!r} is not testnet — the pipeline "
                f"serves only {NETWORK}; refusing structurally",
            )
        uid = r.get("unity_id")
        if not isinstance(uid, str) or not uid.strip():
            raise TokenizeRefused(REASON_MISSING_UNITY_ID,
                                  "no Unity ID — no anonymous tokens exist")
        if not uid.startswith(IDENTITY_PREFIX):
            raise TokenizeRefused(
                REASON_INVALID_UNITY_ID,
                f"unity_id {uid!r} is not a testnet identity "
                f"(must start with {IDENTITY_PREFIX!r})",
            )
        if NETWORK != "dualis.relay.v1.testnet":
            # The module constant itself was tampered with — refuse.
            raise TokenizeRefused(
                REASON_PRODUCTION_SCHEMA,
                "tokenizer NETWORK constant is not the testnet relay — "
                "refusing to operate",
            )

    def _verify_gate(self, r):
        """Verify the gate: the receipt's Ed25519 signature (made by the
        gate over the canonical gate body) must verify against the gate
        PUBLIC key, and prev_hash must link this engine's gate chain.

        This is the verification tokenize() ITSELF performs — the
        caller's "provenance" string is never trusted. Raises
        TokenizeRefused (UNVERIFIED_RECEIPT / CHAIN_BREAK) on anything
        unsigned, forged, tampered, or unchained. Returns the
        verification record carried on the output bundle.
        """
        sig = r.get("signature")
        if not isinstance(sig, str) or not sig.strip():
            raise TokenizeRefused(
                REASON_UNVERIFIED_RECEIPT,
                "receipt carries no gate signature — provenance is "
                "self-asserted, not verified. tokenize() verifies the "
                "gate signature itself; it never trusts the caller's "
                "'VERIFIED' string.",
            )
        if r.get("key_id") != GATE_KEY_ID:
            raise TokenizeRefused(
                REASON_UNVERIFIED_RECEIPT,
                f"receipt key_id {r.get('key_id')!r} is not the gate key "
                f"{GATE_KEY_ID!r} — refusing.",
            )
        if r.get("sig_alg") != GATE_SIG_ALG:
            raise TokenizeRefused(
                REASON_UNVERIFIED_RECEIPT,
                f"receipt sig_alg {r.get('sig_alg')!r} is not "
                f"{GATE_SIG_ALG!r} — refusing.",
            )
        # The signature covers the canonical gate body — which includes
        # prev_hash, binding the chain link itself. Any tampering with a
        # signed field (kind, merit_value, unity_id, prev_hash, …)
        # breaks verification.
        body = _gate_signed_body(r)
        if not _gate_verify(_canonical_bytes(body), sig):
            raise TokenizeRefused(
                REASON_UNVERIFIED_RECEIPT,
                "gate signature FAILED verification — the receipt is "
                "forged or was tampered with after signing. Refusing.",
            )
        prev = r.get("prev_hash")
        if not (isinstance(prev, str) and len(prev) == 64
                and all(c in "0123456789abcdef" for c in prev)):
            raise TokenizeRefused(
                REASON_CHAIN_BREAK,
                "receipt prev_hash is malformed (must be 64 hex chars) — "
                "the receipt is not chained. Refusing.",
            )
        if prev != self._gate_chain_head:
            raise TokenizeRefused(
                REASON_CHAIN_BREAK,
                f"receipt prev_hash {prev[:12]}… does not link the gate "
                f"chain (head {self._gate_chain_head[:12]}…) — fork, "
                "replay, or out-of-order submission. Refusing.",
            )
        return {
            "verified_label": "VERIFIED",
            "gate_key_id": GATE_KEY_ID,
            "signature_algorithm": GATE_SIG_ALG,
            "chain_link": f"{prev[:12]}…→{r['manifest_hash'][:12]}…",
            "verified_by": "tokenize() self-verification",
            "caller_claim": r.get("provenance"),
        }

    def _require_gated(self, r):
        """The gated receipt: VERIFIED provenance, known kind, valid
        manifest, well-formed detail, no misattributed beneficiary.
        UNKNOWN never tokenizes; merit is never credited for another
        ID's work.

        Provenance is VERIFIED BY THIS METHOD, not asserted by the
        caller: _verify_gate() checks the gate signature and the chain
        link before anything mints."""
        if not r.get("receipt_id") or not r.get("manifest_hash"):
            raise TokenizeRefused(REASON_INVALID_RECEIPT,
                                  "receipt lacks receipt_id/manifest_hash")
        mh = r["manifest_hash"]
        if not (isinstance(mh, str) and len(mh) == 64
                and all(c in "0123456789abcdef" for c in mh)):
            raise TokenizeRefused(REASON_INVALID_RECEIPT,
                                  "manifest_hash must be 64 hex chars")
        # Derivative merit regeneration: a receipt that names another
        # beneficiary is trying to credit merit for another ID's work.
        detail = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        for key in _MISATTRIBUTION_KEYS:
            if key in r or key in detail:
                raise TokenizeRefused(
                    REASON_MERIT_MISATTRIBUTION,
                    f"receipt names {key!r} — merit is earned by the "
                    "receipt's own Unity ID only; downstream rings earn "
                    "their own merit from their own receipts",
                )
        prov = r.get("provenance")
        if prov not in PROVENANCE_LABELS:
            raise TokenizeRefused(REASON_UNKNOWN_PROVENANCE,
                                  f"provenance {prov!r} is not a known label")
        if prov != "VERIFIED":
            # UNKNOWN never tokenizes. Neither does anything else that
            # is not VERIFIED.
            raise TokenizeRefused(
                REASON_UNVERIFIED_RECEIPT,
                f"receipt provenance is {prov} — only VERIFIED gated "
                "receipts tokenize; UNKNOWN never tokenizes",
            )
        kind = r.get("kind")
        if kind not in RECEIPT_KINDS:
            raise TokenizeRefused(REASON_UNSUPPORTED_RECEIPT_KIND,
                                  f"receipt kind {kind!r} not in "
                                  f"{sorted(RECEIPT_KINDS)}")
        if kind == RECEIPT_WORK:
            mv = r.get("merit_value")
            if isinstance(mv, bool) or not isinstance(mv, (int, float)) \
                    or mv <= 0:
                raise TokenizeRefused(
                    REASON_NON_POSITIVE_MERIT,
                    f"work receipt needs a positive merit_value — got {mv!r}",
                )
        if kind == RECEIPT_DONATION:
            d = r.get("donation")
            if not isinstance(d, dict) or d.get("kind") not in DONATION_KINDS:
                raise TokenizeRefused(
                    REASON_INVALID_RECEIPT,
                    "donation receipt needs donation.kind in "
                    f"{DONATION_KINDS}",
                )
            amt = d.get("amount")
            if isinstance(amt, bool) or not isinstance(amt, (int, float)) \
                    or amt <= 0:
                raise TokenizeRefused(REASON_INVALID_RECEIPT,
                                      "donation amount must be positive")
        token_id = None
        if kind == RECEIPT_GENESIS:
            token_id = r.get("token_id")
            if not (isinstance(token_id, str) and len(token_id) == 64
                    and all(c in "0123456789abcdef" for c in token_id)):
                raise TokenizeRefused(REASON_INVALID_RECEIPT,
                                      "genesis receipt needs token_id "
                                      "(64 hex chars)")
        # --- verified provenance: trust the math, not the string --------
        # The caller's "provenance" claim passed the label checks above.
        # Now tokenize() establishes the FACT: gate signature verifies,
        # prev_hash links the chain. A claimed "VERIFIED" with no (or a
        # bad) signature, or a broken chain link, is refused here —
        # nothing mints on self-assertion.
        gate_verification = self._verify_gate(r)
        return {
            "unity_id": r["unity_id"].strip(),
            "kind": kind,
            "manifest_hash": mh,
            "epoch": r.get("epoch"),
            "merit_value": float(r["merit_value"])
            if kind == RECEIPT_WORK else None,
            "donation": r.get("donation")
            if kind == RECEIPT_DONATION else None,
            "token_id": token_id,
            "merit_proof_ref": r.get("merit_proof_ref"),
            "gate_verdict": "VERIFIED",
            "gate_verification": gate_verification,
        }

    def _require_peg(self):
        E, _ = self.peg_ratio()
        if E is None:
            raise TokenizeRefused(
                REASON_PEG_E_UNSET,
                "peg ratio E is HELD_FOR_DAVID — the pipeline refuses to "
                "emit eFuse until his word sets it via set_peg_ratio()",
            )
        return E

    # -- mint steps (each: _mint() -> rights -> dclm_commit) ------------------
    def _commit(self, kind, identity, structure, mutate, *, before=None,
                after=None):
        """Rights -> PURIFY (transition) -> single commit -> signed
        envelope, purified on exit. The only way tokenization state
        changes. before/after are small honest markers of the state
        change the caller declares (e.g. balances); the medium checks
        kind, receipt, change-declared, and identity continuity before
        writes.py commits."""
        import dataclasses
        verdict = check_rights(
            identity, kind,
            {"internal": "dclm.tokenize", "schema": SCHEMA},
        )
        # PURIFY IN FLIGHT: the transition itself is checked — kind
        # whitelisted, receipt planned and labeled, the change declared
        # (no silent mutation) — before writes.py commits.
        structure_dict = _normalize_jsonable(dataclasses.asdict(structure))
        purify_transition(
            before if before is not None else {
                "structure": type(structure).__name__, "phase": "pre-commit"},
            after if after is not None else {
                "structure": type(structure).__name__, "phase": "post-commit",
                "new_record": structure_dict.get("record_id")
                or structure_dict.get("token_id")
                or structure_dict.get("transfer_id")},
            kind,
            context={"receipt": structure_dict, "identity": identity,
                     "path": "token_engine._commit",
                     "identity_moves": kind == KIND_MERIT_TRANSFER},
        )
        envelope = dclm_commit(
            kind, {"structure": type(structure).__name__,
                   "schema": SCHEMA},
            verdict,
            _TokenCommitStore(self, structure, mutate),
        )
        # PURIFY ON EXIT: the signed commit envelope, verified.
        return purify_output(
            envelope,
            context={"path": "token_engine._commit", "signed": True},
        )

    def _accrue_merit(self, unity_id, delta, proof_ref, epoch):
        before = self.merit_balance(unity_id)
        after = before + delta
        record_id = _sha256_hex(_canonical_bytes({
            "merit": unity_id, "delta": delta, "proof": proof_ref,
            "before": before}))
        record = _mint(
            "merit",
            schema=SCHEMA,
            record_type="MERIT_ACCRUAL",
            record_id=record_id,
            unity_id=unity_id,
            # Origin: set ONCE, here, never rewritten anywhere.
            origin_earner_id=unity_id,
            origin_receipt_ref=proof_ref,
            delta=delta,
            score_before=before,
            score_after=after,
            merit_proof_ref=proof_ref,
            epoch=epoch,
            provenance="DERIVED",
            issued_at=_utc_now(),
            testnet=True,
        )

        def mutate():
            # Accrual: the earner's slice is created — owner IS the
            # earner, origin IS the earner. Scores only grow here; they
            # are never credited for another ID's work.
            self._slice_seq += 1
            self._merit_slices.append({
                "slice_id": f"sl{self._slice_seq:08d}",
                "record_id": record_id,
                "origin_earner_id": unity_id,
                "origin_receipt_ref": proof_ref,
                "owner_unity_id": unity_id,
                "amount": delta,
            })

        return self._commit(KIND_MERIT_ACCRUAL, unity_id, record, mutate,
                            before={"merit_balance": before},
                            after={"merit_balance": after})

    def _mint_efuse(self, unity_id, merit_value, E, proof_ref, epoch):
        # Peg-calibrated emission (tokenomics.py formula): eFuse = merit / E.
        amount = merit_value / E
        unsigned = {
            "schema": EFUSE_TOKEN_SCHEMA,
            "token_type": "EFUSE",
            "owner_unity_id": unity_id,
            "amount": amount,
            "peg_E": E,
            "epoch": epoch,
            "action_ref": RECEIPT_WORK,
            "merit_proof_ref": proof_ref,
            "provenance": "DERIVED",
            "issued_at": _utc_now(),
            "testnet": True,
            "note": ("Merit-gated emission: amount = merit_value / E. "
                     "Never bought or sold; movements only through the "
                     "economics ledger functions."),
        }
        token_id = _sha256_hex(_canonical_bytes(unsigned))
        token = _mint("efuse", token_id=token_id, **unsigned)

        def mutate():
            self.efuse_registry[token_id] = token

        efuse_before = len(self.efuse_registry)
        return self._commit(KIND_TOKEN_MINT, unity_id, token, mutate,
                            before={"efuse_tokens": efuse_before},
                            after={"efuse_tokens": efuse_before + 1})

    def _record_honor(self, unity_id, receipt_ref, donation, epoch):
        record = _mint(
            "honor",
            schema=SCHEMA,
            record_type="HONOR_RECORD",
            record_id=_sha256_hex(_canonical_bytes({
                "honor": unity_id, "receipt": receipt_ref,
                "amount": donation["amount"], "kind": donation["kind"]})),
            unity_id=unity_id,
            donation_receipt_ref=receipt_ref,
            donation_kind=donation["kind"],
            donation_amount=float(donation["amount"]),
            provenance="DERIVED",
            permanent=True,
            spendable=False,
            transferable=False,
            issued_at=_utc_now(),
            testnet=True,
        )

        def mutate():
            # Append-only: records are never modified, removed, or spent.
            self.honor_ledger.setdefault(unity_id, []).append(record)

        honor_before = len(self.honor_ledger.get(unity_id, []))
        return self._commit(KIND_HONOR_RECORD, unity_id, record, mutate,
                            before={"honor_records": honor_before},
                            after={"honor_records": honor_before + 1})

    def _bind_genesis(self, unity_id, token_id, genesis_ref, merit_proof_ref):
        """Bind a Unity holding at genesis. The token was minted by the
        fuse trigger; this records who holds it — ONCE. Holdings are
        NEVER re-bound: there is no transfer path (the bound sale is
        dead), so this is write-once, read-forever."""
        existing = self._unity_registry.get(token_id)
        if existing is not None:
            if existing.holder == unity_id:
                return  # idempotent: same bind twice is a no-op
            raise TokenizeRefused(
                REASON_GENESIS_CONFLICT,
                f"token {token_id[:16]}… is already bound to "
                f"{existing.holder!r} — Unity never transfers, so a "
                "second bind is a conflict, not a transfer",
            )
        self._unity_registry[token_id] = UnityHolding(
            token_id=token_id,
            holder=unity_id,
            genesis_ref=genesis_ref,
            merit_proof_ref=merit_proof_ref or genesis_ref,
        )

    # -- refusal trail --------------------------------------------------------
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
            "note": "Refusal, not a block: nothing was minted, nothing "
                    "was written.",
        }
        # Signed like every other receipt — a signed refusal is a
        # verifiable honest statement, not a silent drop.
        self._receipt_log.append(sign_commit(refusal))

    # -- introspection ----------------------------------------------------------
    def honor_records(self, unity_id):
        """The permanent Honor record list for a Unity ID."""
        return list(self.honor_ledger.get(unity_id, []))

    def unity_holder(self, token_id):
        """Current holder of a Unity token, or None if unknown. (The
        holder never changes — there is no transfer path.)"""
        holding = self._unity_registry.get(token_id)
        return holding.holder if holding else None


# ---------------------------------------------------------------------------
# Module-level default engine (tests use fresh Tokenizer() instances)
# ---------------------------------------------------------------------------

_DEFAULT = Tokenizer()


def tokenize(receipt):
    """tokenize(receipt) -> TokenBundle. The pipeline entry point.

    Validates the gated receipt, computes eFuse/Merit/Honor outputs per
    the token formats, mints ONLY via dclm_commit, returns the signed
    token structures. Refuses (TokenizeRefused, zero tokens) on anything
    unverified, non-testnet, misattributed, or peg-unset.
    """
    return _DEFAULT.tokenize(receipt)


def merit_transfer(from_id, to_id, amount, reason, auth=None):
    """Merit transfer on the default engine: the SOLE legal Merit
    ownership-transfer path. auth is the sender's signed transfer
    authorization (REQUIRED — unsigned transfers are refused).
    See Tokenizer.merit_transfer."""
    return _DEFAULT.merit_transfer(from_id, to_id, amount, reason, auth)


def standing(identity):
    """EARNED STANDING on the default engine: origin-based, never moves
    on transfer. See Tokenizer.standing."""
    return _DEFAULT.standing(identity)


def merit_balance(identity):
    """OWNED Merit (economic value) on the default engine. See
    Tokenizer.merit_balance."""
    return _DEFAULT.merit_balance(identity)


def set_peg_ratio(E, authority):
    """Set the peg ratio E on David's word. See Tokenizer.set_peg_ratio
    for the honest authority marking."""
    return _DEFAULT.set_peg_ratio(E, authority)


def peg_ratio():
    """(E, provenance) or (None, 'HELD_FOR_DAVID')."""
    return _DEFAULT.peg_ratio()

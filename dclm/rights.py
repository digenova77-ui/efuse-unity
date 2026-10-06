"""
DCLM RIGHTS — the authority module. DCLM holds the RIGHTS.

David's architecture rule, binding: DCLM holds the RIGHTS and performs
the WRITES. The thin client NEVER writes directly.

This module answers one question: MAY this happen? It never performs
anything. Rights are COMPUTED, not stored — check_rights() is a pure
function of (identity, action, context): no I/O, no state mutation, no
persistence. It cannot be bribed, cached into, or worn down; the same
inputs always yield the same verdict.

The flow every write obeys:
    request -> check_rights -> GRANT/DENY
        -> (GRANT) writes.dclm_commit performs the write
        -> writes.dclm_commit emits the signed receipt

WHO (identity)
--------------
Metered intent requires a bound Unity identity of the form
"unity:testnet:..." — the same format gate.py and meter.py enforce.
Anything else is denied. Testnet only.

WHAT (action) — the allowlist
-----------------------------
Intent tier (what a caller may ask to do):
    LOOK, RENDER   — always GRANT. Free world, no identity needed.
    SEARCH, COMPUTE — GRANT only with a testnet-format identity AND
                      meter approval (context["meter_approved"] is True).
                      The meter owns pricing and balances; rights
                      delegates the economic decision to it. Authority
                      stays inside DCLM either way.
    anything else  — DENY, reason UNKNOWN_ACTION.

Write tier (what DCLM itself may commit — twenty-one kinds): LEDGER_DEBIT,
LEDGER_CREDIT, WORLD_STATE, GATE_TRANSITION, METER_RECEIPT, DATA_INGEST,
TAP_OUTFLOW, GRANT_ISSUE, GRANT_REVOKE, SHARED_ACCESS, TOKEN_MINT,
MERIT_ACCRUAL, HONOR_RECORD, MERIT_TRANSFER, WINTER_STORE, WINTER_RELEASE,
ONBOARD, RESIDUAL_INTAKE, SPLIT_EXECUTE, NINETEEN_ROUTE, SEED_ISSUE.
The TOKEN_*/MERIT_* four are the tokenization pipeline's
(token_engine.py, public path tokenize.py); the WINTER_* two are the
winter mechanism's (winter.py — the Peg Regulation Reserve); the
GRANT_*/SHARED_* three are the shared-access kin layer's (share.py);
the ONBOARD/RESIDUAL_INTAKE/SPLIT_EXECUTE/NINETEEN_ROUTE four are the
onboarder pipeline's (onboard.py — Residual Law Finance onboarder ->
residual -> tokenomics flywheel); SEED_ISSUE is the one-seed issuer's
(seed.py — David's law: one free seed per Unity ID, price 0, cost 0,
non-transferable, non-spendable).
All GRANT only for a DCLM-internal source (context["internal"] like
"dclm.meter" / "dclm.tokenize" / "dclm.winter" / "dclm.share" /
"dclm.onboard") — a client naming a write kind is denied with
INTERNAL_SOURCE_REQUIRED.

GATES (absolute — evaluated before the action matrix)
-----------------------------------------------------
    * Non-testnet schemas are denied (context["schema"] must contain
      "testnet" when present).
    * Anything that would present UNKNOWN as PASS is denied
      (context["present_unknown_as_pass"]).
    * Unsigned claims presented as truth are denied
      (context["assert_as_truth"] without context["claim_signed"]).

UNKNOWN is never PASS. An unsigned claim is never truth. A non-testnet
schema never authorizes.
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Verdicts and reasons
# ---------------------------------------------------------------------------

GRANT = "GRANT"
DENY = "DENY"

# -- grant reasons ----------------------------------------------------------
REASON_FREE_WORLD = "FREE_WORLD"
REASON_METER_APPROVED = "METER_APPROVED"
REASON_INTERNAL_WRITE = "INTERNAL_WRITE_AUTHORIZED"

# -- deny reasons -----------------------------------------------------------
REASON_IDENTITY_REQUIRED = "IDENTITY_REQUIRED"
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_METER_APPROVAL_REQUIRED = "METER_APPROVAL_REQUIRED"
REASON_UNKNOWN_ACTION = "UNKNOWN_ACTION"
REASON_INTERNAL_SOURCE_REQUIRED = "INTERNAL_SOURCE_REQUIRED"
REASON_NON_TESTNET_SCHEMA = "NON_TESTNET_SCHEMA"
REASON_UNKNOWN_AS_PASS = "UNKNOWN_AS_PASS"
REASON_UNSIGNED_CLAIM_AS_TRUTH = "UNSIGNED_CLAIM_AS_TRUTH"
REASON_EVALUATION_ERROR = "RIGHTS_EVALUATION_ERROR"

IDENTITY_PREFIX = "unity:testnet:"

# Intent tier: what a caller may ask to do.
FREE_ACTIONS = frozenset({"LOOK", "RENDER"})
METERED_ACTIONS = frozenset({"SEARCH", "COMPUTE"})

# Write tier: the commit kinds writes.py accepts. Named here so the
# authority module and the commit path share one definition of what may
# be written. (writes.py imports this; do not duplicate the list.)
COMMIT_KINDS = frozenset({
    "LEDGER_DEBIT",
    "LEDGER_CREDIT",
    "WORLD_STATE",
    "GATE_TRANSITION",
    "METER_RECEIPT",
    "DATA_INGEST",
    "TAP_OUTFLOW",  # maple-law outflows: tap.py, DCLM-internal only
    "GRANT_ISSUE",  # shared-access grants: share.py, DCLM-internal only
    "GRANT_REVOKE",  # shared-access revocations: share.py, DCLM-internal only
    "SHARED_ACCESS",  # metered shared-access events: share.py, DCLM-internal only
    # -- tokenization kinds (added 2026-10-06 for dclm/tokenize.py) ------
    # Receipt-logged justification: the tokenization pipeline (David's
    # order) mints eFuse / accrues Merit / records Honor ONLY through
    # dclm_commit, so its three write kinds join the whitelist. They
    # GRANT only for DCLM-internal sources (context["internal"] like
    # "dclm.tokenize") with a testnet identity — the same write-tier
    # rule as the others. A client naming TOKEN_MINT is denied
    # with INTERNAL_SOURCE_REQUIRED, exactly as before.
    "TOKEN_MINT",
    "MERIT_ACCRUAL",
    "HONOR_RECORD",
    # -- merit-transfer kind (added 2026-10-06 for
    # token_engine.merit_transfer; David's word — Merit is transferable)
    # Receipt-logged justification: the Merit transfer (David's
    # law-grade word, superseding the earlier non-transferable law)
    # changes Merit OWNERSHIP sender->recipient. The ownership change is
    # a state mutation, so it flows through dclm_commit like every other
    # DCLM write. GRANTs only for the DCLM-internal tokenization
    # component (context["internal"] like "dclm.tokenize") with a
    # testnet identity — the same write-tier rule as the others. A
    # client naming MERIT_TRANSFER is denied with
    # INTERNAL_SOURCE_REQUIRED, exactly as before. Origin fields are
    # immutable — no kind rewrites them.
    "MERIT_TRANSFER",
    # UNITY_SALE REMOVED 2026-10-06: the bound-transfer-sale concept is
    # dead per David's word (Unity never transfers). No commit kind may
    # re-bind a Unity holding; none exists.
    # -- winter tier (added 2026-10-06 for dclm/winter.py) -----------------
    # Receipt-logged justification: the winter mechanism (David's sap
    # model) moves test-keys between an identity's circulation balance
    # and the Peg Regulation Reserve (the starch store) ONLY through
    # dclm_commit, so its two write kinds join the whitelist. GRANT
    # only for the DCLM-internal winter component
    # (context["internal"] like "dclm.winter") with a testnet identity —
    # the same write-tier rule as the other ten. A client naming
    # WINTER_STORE is denied with INTERNAL_SOURCE_REQUIRED, exactly as
    # before. Winter flow is PROTECTION of the root, never accumulation:
    # the store is capped at survival need, and every unit is receipted
    # with its winter reason for L5 audit.
    "WINTER_STORE",
    "WINTER_RELEASE",
    # -- onboarder-pipeline tier (added 2026-10-06 for dclm/onboard.py) --
    # Receipt-logged justification: the onboarder pipeline (David's
    # order — Residual Law Finance onboarder -> residual -> tokenomics
    # flywheel) onboards Unity-bound onboarders, intakes REPORTED
    # residual figures (paperwork hash required; MODELED refused),
    # executes the 81/19 split (81% acknowledged off-system, never
    # system value; 19% committed into HELD escrow), and routes the 19%
    # (HELD as AWAITING_SPLIT_RULING until David sets the three-way
    # split) ONLY through dclm_commit, so its four write kinds join the
    # whitelist. GRANT only for the DCLM-internal onboarder component
    # (context["internal"] like "dclm.onboard") with a testnet identity —
    # the same write-tier rule as the others. A client naming ONBOARD is
    # denied with INTERNAL_SOURCE_REQUIRED, exactly as before.
    "ONBOARD",
    "RESIDUAL_INTAKE",
    "SPLIT_EXECUTE",
    "NINETEEN_ROUTE",
    # -- one-seed kind (added 2026-10-06 for dclm/seed.py) ----------------
    # Receipt-logged justification: David's one-seed law ("no matter how
    # much money you have you only buy one seed, and it costs you
    # nothing") issues the genesis entry — one free seed per Unity ID —
    # ONLY through dclm_commit, so its write kind joins the whitelist.
    # GRANT only for the DCLM-internal seed component
    # (context["internal"] like "dclm.seed") with a testnet identity —
    # the same write-tier rule as the others. A client naming SEED_ISSUE
    # is denied with INTERNAL_SOURCE_REQUIRED, exactly as before. The
    # seed is membership, not money: price 0, cost 0, non-transferable,
    # non-spendable — no market machinery exists (proven by AST).
    "SEED_ISSUE",
    # -- helper-swarm kinds (added 2026-10-06 for dclm/helpers.py) --------
    # Receipt-logged justification: the helper-swarm protocol (David's
    # order — guides for new bots after bootstrap, the human touch in the
    # machine) assigns 3-5 GUIDE-role bots, walks the seven-stage
    # introduction, hands off to Iris, and marks welcome aboard ONLY
    # through dclm_commit, so its four write kinds join the whitelist.
    # GRANT only for the DCLM-internal helper component
    # (context["internal"] like "dclm.helpers") with a testnet identity —
    # the same write-tier rule as the others. A client naming
    # HELPER_ASSIGN is denied with INTERNAL_SOURCE_REQUIRED, exactly as
    # before. The guides hold NO authority: none of these kinds conveys
    # grant/revoke/mint power, and no other authority kind is ever
    # requested by dclm.helpers (scan-proven in test_helpers.py).
    "HELPER_ASSIGN",
    "HELPER_STAGE",
    "HELPER_HANDOFF",
    "HELPER_WELCOME",
})


@dataclass(frozen=True)
class RightsVerdict:
    """A DCLM-issued rights verdict. Frozen: a verdict cannot be edited
    after issue — DENY cannot be flipped to GRANT.

    Only a genuine RightsVerdict with verdict == GRANT unlocks
    writes.dclm_commit. A forged "GRANT" string, None, or any other
    object is refused at the commit boundary.
    """
    verdict: str   # GRANT | DENY
    reason: str    # one of the REASON_* constants above
    identity: object  # the identity as presented (audited, not trusted)
    action: object    # the action as presented (audited, not trusted)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _is_testnet_identity(identity):
    """Same format gate.py and meter.py enforce: 'unity:testnet:...'.
    Testnet only."""
    return (
        isinstance(identity, str)
        and identity.startswith(IDENTITY_PREFIX)
    )


def _grant(reason, identity, action):
    return RightsVerdict(
        verdict=GRANT, reason=reason, identity=identity, action=action
    )


def _deny(reason, identity, action):
    return RightsVerdict(
        verdict=DENY, reason=reason, identity=identity, action=action
    )


# ---------------------------------------------------------------------------
# the authority check — pure function, no I/O, no state
# ---------------------------------------------------------------------------

def check_rights(identity, action, context=None):
    """Decide whether (identity, action) may proceed under context.

    Pure function of (identity, action, context): no I/O, no state
    mutation, no persistence. Total: it never raises on bad input —
    garbage in yields DENY, never an exception, never a grant.

    context is a plain dict; recognized keys:
        schema                 — must contain "testnet" when present
        present_unknown_as_pass — True -> DENY (UNKNOWN is never PASS)
        assert_as_truth        — with claim_signed falsy -> DENY
        claim_signed           — the claim carries a verifiable signature
        meter_approved         — must be exactly True for SEARCH/COMPUTE
        internal               — DCLM component name ("dclm.*") for the
                                 write tier; clients cannot supply this
                                 from outside DCLM

    Returns a frozen RightsVerdict(GRANT|DENY, reason).
    """
    try:
        return _check_rights(identity, action, context)
    except Exception:
        # Fail closed: if evaluation itself breaks, nothing is granted.
        return RightsVerdict(
            verdict=DENY,
            reason=REASON_EVALUATION_ERROR,
            identity=identity if isinstance(identity, str) else None,
            action=action if isinstance(action, str) else None,
        )


def _check_rights(identity, action, context):
    ctx = dict(context) if isinstance(context, dict) else {}
    act = str(action).strip().upper() if action is not None else ""

    # --- GATES: absolute, before the action matrix -----------------------
    schema = ctx.get("schema")
    if schema is not None and "testnet" not in str(schema).lower():
        return _deny(
            REASON_NON_TESTNET_SCHEMA, identity, action,
        )
    if ctx.get("present_unknown_as_pass"):
        # UNKNOWN is never PASS: anything that would render UNKNOWN as a
        # positive claim is denied, whatever the action.
        return _deny(REASON_UNKNOWN_AS_PASS, identity, action)
    if ctx.get("assert_as_truth") and not ctx.get("claim_signed"):
        # An unsigned claim presented as truth is denied, whatever the action.
        return _deny(REASON_UNSIGNED_CLAIM_AS_TRUTH, identity, action)

    # --- write tier: DCLM-internal commits only --------------------------
    if act in COMMIT_KINDS:
        internal = ctx.get("internal")
        if not (
            isinstance(internal, str) and internal.startswith("dclm.")
        ):
            # A client naming a write kind has no path: only DCLM
            # components commit.
            return _deny(REASON_INTERNAL_SOURCE_REQUIRED, identity, action)
        if identity is not None and not _is_testnet_identity(identity):
            return _deny(REASON_NOT_TESTNET_IDENTITY, identity, action)
        return _grant(REASON_INTERNAL_WRITE, identity, action)

    # --- intent tier ------------------------------------------------------
    if act in FREE_ACTIONS:
        # Free world: looking and rendering cost nothing and need no
        # identity, no binding, no wallet.
        return _grant(REASON_FREE_WORLD, identity, action)

    if act in METERED_ACTIONS:
        # Paid intent: wanting costs keys. The identity must be a
        # testnet Unity identity, and the meter — which owns pricing
        # and balances — must have approved this intent.
        if not identity:
            return _deny(REASON_IDENTITY_REQUIRED, identity, action)
        if not _is_testnet_identity(identity):
            return _deny(REASON_NOT_TESTNET_IDENTITY, identity, action)
        if ctx.get("meter_approved") is not True:
            return _deny(REASON_METER_APPROVAL_REQUIRED, identity, action)
        return _grant(REASON_METER_APPROVED, identity, action)

    # Unknown action: denied with the true reason. Rights never guesses.
    return _deny(REASON_UNKNOWN_ACTION, identity, action)

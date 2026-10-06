"""
DCLM SHARED ACCESS — the kin layer's monetization, the wallet law's
sharing model made real. Subtle, persistent, Unity-bound.

David's order: a Unity ID grants shared access to another Unity ID,
tiered by relationship. Money and information share the same rails.

THE MODEL
---------
1. Tiered access grants. FRIEND = a little, GOOD_FRIEND = more,
   FAMILY = total. Tiers are ORDERED INTEGERS (1 < 2 < 3). The granter
   sets the tier; the system enforces exactly what was set, nothing
   more.

2. What gets shared. Data, RTE seats, world views, resources, compute.
   A grant names the content type, the depth, and the duration (expiry).

3. Metered and monetized. A grant can carry a price (test-keys, per the
   pricing engine). Accessing through a grant deducts from the
   ACCESSOR's wallet and credits the granter in full — the provider is
   paid for what they shared. This is the kin economy made mechanical.

4. Unity-bound and revocable. Every grant is bound to BOTH Unity IDs,
   receipted, and revocable by the granter at any time. Revocation is
   instant and total: every access check reads CURRENT grant state —
   the live registry, never a cached or stale copy.

5. Kin is binding. Family-tier grants require VERIFIED kin only. The
   L2 umpires are the kin-verification authority; the integration point
   is PENDING (no L2 module exists in this build), so family grants are
   refused with NOT_KIN_VERIFIED until a real authority is wired in.
   Kinship is never assumed.

6. DCLM rights and writes. Grants are RIGHTS (authorized via
   rights.check_rights), access events are WRITES (committed via
   writes.dclm_commit). The client never grants or revokes directly —
   it requests, DCLM executes.

DERIVATIVE MERIT REGENERATION (David's law-grade rule)
-----------------------------------------------------
A grant ENABLES work — access to data, seats, views, compute — but the
grantee earns their OWN merit from their OWN verified receipts. Money
can flow through a grant (access fees, per the metering below); MERIT
NEVER FLOWS through a grant. No grant, at any tier, transfers merit
from granter to grantee. This kills pyramid dynamics by construction:
value flows outward like sap, but each leaf photosynthesizes its own.

Structural enforcement in this module:
  * access() moves MONEY (test-keys) only — ledger debits and credits.
  * No code path in this module accrues, transfers, mints, or
    references merit scores. share.py never imports the tokenization
    pipeline and never names its write kinds.
  * _assert_no_merit() scans every external payload (annotations,
    actions). A grant carrying a merit payload is refused as malformed
    (MERIT_IN_GRANT) — if a future caller tries to pass merit through
    a grant, the structure refuses.
  * The family tier shares MORE (depth, duration, content) — never
    merit. Tier = access depth, not standing transfer.

TIER-CREEP: STRUCTURALLY BLOCKED, NOT POLICY-BLOCKED
----------------------------------------------------
The tier level is an INTEGER inside the SIGNED grant body, and the
access check compares integers: grant.tier_level >= required_level. A
FRIEND (1) grant presented against FAMILY-required (3) content denies
by integer comparison — 1 >= 3 is false, always, regardless of what
anyone claims. Tampering with the integer breaks the Ed25519
signature, and the check verifies the signature first: a forged tier
is INVALID_GRANT, fail-closed. There is no policy string to
reinterpret and no configuration to flip; the arithmetic is the wall.

Testnet only. Test-keys only — never dollars, never eFuse.
"""

import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from rights import check_rights  # noqa: E402 — DCLM authority: rights first
from purify import (  # noqa: E402 — the purification medium: checks, never commits
    purify_input,
    purify_output,
    purify_transition,
)
from writes import (  # noqa: E402 — the single commit path
    CommitRefused,
    CommitStore,
    dclm_commit,
)
import meter  # noqa: E402 — wallet ledger + receipt signing (money only)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.share.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"
UNIT = meter.UNIT  # "test-keys" — the only unit of account

# Commit kinds (whitelisted in rights.COMMIT_KINDS).
KIND_GRANT_ISSUE = "GRANT_ISSUE"
KIND_GRANT_REVOKE = "GRANT_REVOKE"
KIND_SHARED_ACCESS = "SHARED_ACCESS"

# -- tiers: ordered integers. FRIEND < GOOD_FRIEND < FAMILY, structurally --
TIER_FRIEND = "FRIEND"
TIER_GOOD_FRIEND = "GOOD_FRIEND"
TIER_FAMILY = "FAMILY"

TIER_LEVELS = {
    TIER_FRIEND: 1,       # a little
    TIER_GOOD_FRIEND: 2,  # more
    TIER_FAMILY: 3,       # total
}

# -- what a grant can name ---------------------------------------------------
CONTENT_DATA = "DATA"
CONTENT_RTE_SEAT = "RTE_SEAT"
CONTENT_WORLD_VIEW = "WORLD_VIEW"
CONTENT_RESOURCE = "RESOURCE"
CONTENT_COMPUTE = "COMPUTE"

CONTENT_TYPES = frozenset({
    CONTENT_DATA,
    CONTENT_RTE_SEAT,
    CONTENT_WORLD_VIEW,
    CONTENT_RESOURCE,
    CONTENT_COMPUTE,
})

# -- verdicts ----------------------------------------------------------------
ACCESS_GRANT = "GRANT"
ACCESS_DENY = "DENY"

# -- refusal reasons ----------------------------------------------------------
REASON_NOT_TESTNET_IDENTITY = "NOT_TESTNET_IDENTITY"
REASON_SELF_GRANT = "SELF_GRANT"
REASON_UNKNOWN_TIER = "UNKNOWN_TIER"
REASON_UNKNOWN_CONTENT_TYPE = "UNKNOWN_CONTENT_TYPE"
REASON_INVALID_DEPTH = "INVALID_DEPTH"
REASON_INVALID_DURATION = "INVALID_DURATION"
REASON_INVALID_PRICE = "INVALID_PRICE"
REASON_NOT_KIN_VERIFIED = "NOT_KIN_VERIFIED"
REASON_MERIT_IN_GRANT = "MERIT_IN_GRANT"
REASON_GRANT_NOT_FOUND = "GRANT_NOT_FOUND"
REASON_NOT_GRANTER = "NOT_GRANTER"
REASON_NOT_GRANTEE = "NOT_GRANTEE"
REASON_ALREADY_REVOKED = "ALREADY_REVOKED"
REASON_NO_GRANT = "NO_GRANT"
REASON_TIER_TOO_LOW = "TIER_TOO_LOW"
REASON_GRANT_EXPIRED = "GRANT_EXPIRED"
REASON_GRANT_REVOKED = "GRANT_REVOKED"
REASON_INVALID_GRANT = "INVALID_GRANT"
REASON_INSUFFICIENT_KEYS = "INSUFFICIENT_KEYS"
REASON_NO_STORE = "NO_STORE"
REASON_NO_WALLET = "NO_WALLET"


class ShareError(Exception):
    """Base class for shared-access failures."""


class ShareRefused(ShareError):
    """Honest refusal: the request was understood and declined, with the
    true reason. Nothing was written, nothing was deducted."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        super().__init__(
            f"shared access refused ({reason})"
            + (f": {detail}" if detail else "")
            + " — nothing was written, nothing was deducted."
        )


@dataclass(frozen=True)
class AccessVerdict:
    """The answer to 'may this identity touch this content at this tier?'
    Frozen: a verdict cannot be edited after issue."""
    granted: bool
    reason: str      # ACCESS_GRANT, or one of the REASON_* deny reasons
    grant_id: object  # the live grant that authorized access, else None
    provenance: str = "DERIVED"  # verdicts leave DCLM labeled, always


# ---------------------------------------------------------------------------
# kin verification — the L2-umpire integration point (PENDING)
# ---------------------------------------------------------------------------

_KIN_AUTHORITY = None  # the L2 umpire module registers its verifier here


def register_kin_authority(fn):
    """Register the kin-verification authority (the L2 umpires).

    PENDING: no L2 module exists in this build, so nothing is
    registered and family grants are refused. When the L2 umpire module
    lands, it calls this with its verifier; share.py calls it and
    trusts its boolean. Kinship is never assumed — only attested."""
    global _KIN_AUTHORITY
    if not callable(fn):
        raise ShareError("kin authority must be callable")
    _KIN_AUTHORITY = fn


def clear_kin_authority():
    """Unregister the kin authority (tests / teardown)."""
    global _KIN_AUTHORITY
    _KIN_AUTHORITY = None


def verify_kin(granter, grantee):
    """Is grantee verified kin of granter?

    With no authority registered this returns False — always. A family
    grant issued against an unreachable authority is refused with
    NOT_KIN_VERIFIED (honest refusal, never assumed kinship). An
    erroring authority verifies nothing: fail closed."""
    if _KIN_AUTHORITY is None:
        return False
    try:
        return bool(_KIN_AUTHORITY(granter, grantee))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# the merit guard — money moves, merit never does
# ---------------------------------------------------------------------------

_MERIT_KEY_RE = re.compile(r"merit", re.IGNORECASE)


def _assert_no_merit(obj, where="payload"):
    """Structural refusal: no merit may ride a grant.

    Scans dict keys and strings for merit references. A grant carrying
    a merit payload is refused as malformed — this is what stops a
    future caller from smuggling merit through the shared-access rails.
    None and non-string scalars pass silently."""
    if obj is None:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and _MERIT_KEY_RE.search(key):
                raise ShareRefused(
                    REASON_MERIT_IN_GRANT,
                    f"merit key {key!r} in {where}: merit never flows "
                    "through a grant — money only.",
                )
            _assert_no_merit(value, where)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _assert_no_merit(value, where)
    elif isinstance(obj, str):
        if _MERIT_KEY_RE.search(obj):
            raise ShareRefused(
                REASON_MERIT_IN_GRANT,
                f"merit reference in {where}: merit never flows through "
                "a grant — money only.",
            )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _is_testnet_identity(identity):
    return (
        isinstance(identity, str)
        and identity.startswith(IDENTITY_PREFIX)
    )


def _require_testnet(identity, role="identity"):
    if not _is_testnet_identity(identity):
        raise ShareRefused(
            REASON_NOT_TESTNET_IDENTITY,
            f"{role} must start with {IDENTITY_PREFIX!r}; "
            f"got {identity!r}. Testnet only.",
        )


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _now_iso(now):
    if now is None:
        return _utc_now()
    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.isoformat()
    return str(now)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# the grant registry — DCLM-internal state, read LIVE on every check
# ---------------------------------------------------------------------------

class ShareStore(CommitStore):
    """The live grant registry. DCLM-internal; the thin client never
    touches it.

    grants   — grant_id -> SIGNED grant envelope (immutable after issue)
    revoked  — set of grant_ids revoked by their granter (instant, total)
    access_log — committed SHARED_ACCESS event payloads
    receipts — signed commit envelopes, in order

    check_access() and access() read grants/revoked DIRECTLY at call
    time. There is no cache layer, no TTL, no snapshot: a revocation
    committed a millisecond ago is visible to the next check. Revoked
    means revoked."""

    def __init__(self):
        self.grants = {}
        self.revoked = set()
        self.access_log = []
        self.receipts = []

    def apply_write(self, kind, payload):
        """THE mutation point for shared-access writes. Called exactly
        once per commit, only after a DCLM-issued GRANT verdict."""
        if kind == KIND_GRANT_ISSUE:
            grant_id = payload["grant_id"]
            self.grants[grant_id] = payload["grant_envelope"]
            return {"registered": grant_id, "grants": len(self.grants)}
        if kind == KIND_GRANT_REVOKE:
            grant_id = payload["grant_id"]
            self.revoked.add(grant_id)
            return {"revoked": grant_id, "revoked_total": len(self.revoked)}
        if kind == KIND_SHARED_ACCESS:
            self.access_log.append(payload)
            return {"logged": True, "events": len(self.access_log)}
        raise CommitRefused(
            f"share store refuses kind {kind!r}: not a shared-access write"
        )

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        receipt = super().build_receipt(
            kind, payload, mutation_report, rights_verdict
        )
        receipt["grant_id"] = payload.get("grant_id")
        return receipt

    def append_receipt(self, envelope):
        self.receipts.append(envelope)


class _ShareWalletAdapter(CommitStore):
    """DCLM-internal adapter: lets writes.dclm_commit drive the Wallet's
    ledger for shared-access money movement.

    Mirrors meter._MeterCommitStore: the debit/credit receipt is built by
    share.py, dclm_commit performs the one mutation inside apply_write
    after a DCLM-issued GRANT verdict, and the signed receipt is logged
    to the wallet's receipt trail. Money only — this adapter has no
    path to merit, and never will."""

    def __init__(self, wallet, *, identity, receipt, op,
                 balance_before, balance_after):
        self._wallet = wallet
        self._identity = identity
        self._receipt = receipt
        self._op = op  # "debit" | "credit"
        self._balance_before = balance_before
        self._balance_after = balance_after

    def apply_write(self, kind, payload):
        self._wallet._ledger["balances"][self._identity] = self._balance_after
        self._wallet._assert_ledger_nonnegative()
        self._wallet._save()
        return {
            "op": self._op,
            "identity": self._identity,
            "balance_before": self._balance_before,
            "balance_after": self._balance_after,
        }

    def build_receipt(self, kind, payload, mutation_report, rights_verdict):
        return self._receipt

    def append_receipt(self, envelope):
        self._wallet._log(envelope["receipt"])


# ---------------------------------------------------------------------------
# issue — the granter requests, DCLM executes
# ---------------------------------------------------------------------------

def issue_grant(granter, grantee, tier, content_type, depth, duration,
                price=0, *, store=None, now=None, annotations=None):
    """Issue a tiered shared-access grant. Returns a dict with grant_id,
    the signed grant envelope, the GRANT_ISSUE commit envelope, and the
    store.

    The client never grants directly: this function IS DCLM executing —
    rights checked, grant signed, write committed, receipt logged.

    Validation (every failure is an honest ShareRefused; nothing is
    written, nothing is signed):
      * both identities must be "unity:testnet:..." (testnet only)
      * granter != grantee (no self-grants)
      * tier one of FRIEND / GOOD_FRIEND / FAMILY
      * content_type one of DATA / RTE_SEAT / WORLD_VIEW / RESOURCE /
        COMPUTE
      * depth a non-empty string naming what is shared
      * duration a positive integer of seconds (the grant's lifetime)
      * price a non-negative integer of test-keys
      * annotations (optional dict) must carry NO merit — refused as
        malformed (MERIT_IN_GRANT)
      * FAMILY tier requires verify_kin() True — with no L2 authority
        registered this is always False, so family grants are refused
        with NOT_KIN_VERIFIED until the umpires wire in.

    The signed grant body carries tier_level as an INTEGER — the
    structural tier-creep block (see module docstring).
    """
    # PURIFY ON ENTRY: the medium first. Anonymous or forged identities
    # are refused here as PurificationRefused — before any grant logic.
    purify_input(
        {"identities": [granter, grantee], "action": "ISSUE_GRANT",
         "claims": [{"claim": "grant-issue-request",
                     "provenance": "DERIVED"}]},
        context={"path": "share.issue_grant"},
    )
    # -- structural validation: refuse before anything is signed ---------
    _require_testnet(granter, "granter")
    _require_testnet(grantee, "grantee")
    if granter == grantee:
        raise ShareRefused(
            REASON_SELF_GRANT, "granter and grantee are the same identity"
        )
    if tier not in TIER_LEVELS:
        raise ShareRefused(
            REASON_UNKNOWN_TIER,
            f"got {tier!r}; tiers are {sorted(TIER_LEVELS)}",
        )
    if content_type not in CONTENT_TYPES:
        raise ShareRefused(
            REASON_UNKNOWN_CONTENT_TYPE,
            f"got {content_type!r}; types are {sorted(CONTENT_TYPES)}",
        )
    if not (isinstance(depth, str) and depth.strip()):
        raise ShareRefused(
            REASON_INVALID_DEPTH, f"depth must name what is shared; got {depth!r}"
        )
    if not _is_int(duration) or duration <= 0:
        raise ShareRefused(
            REASON_INVALID_DURATION,
            f"duration must be a positive integer of seconds; got {duration!r}",
        )
    if not _is_int(price) or price < 0:
        raise ShareRefused(
            REASON_INVALID_PRICE,
            f"price must be a non-negative integer of {UNIT}; got {price!r}",
        )
    _assert_no_merit(annotations, "annotations")
    kin_ok = verify_kin(granter, grantee)
    if tier == TIER_FAMILY and not kin_ok:
        raise ShareRefused(
            REASON_NOT_KIN_VERIFIED,
            "family tier requires VERIFIED kin; the L2-umpire authority "
            "is not reachable (integration PENDING) — refusing, never "
            "assuming kinship.",
        )

    # -- RIGHTS: DCLM authorizes ------------------------------------------
    verdict = check_rights(
        granter, KIND_GRANT_ISSUE,
        {"internal": "dclm.share", "schema": SCHEMA, "tier": tier},
    )

    # -- the grant: tier as an INTEGER inside the signed body --------------
    issued_at = _now_iso(now)
    grant_id = uuid.uuid4().hex
    grant = {
        "schema": SCHEMA,
        "grant_id": grant_id,
        "granter": granter,
        "grantee": grantee,
        "tier": tier,
        "tier_level": TIER_LEVELS[tier],  # integer: the tier-creep wall
        "content_type": content_type,
        "depth": depth.strip(),
        "price": price,
        "unit": UNIT,
        "duration_seconds": duration,
        "issued_at": issued_at,
        "expires_at": _expires_iso(issued_at, duration),
        "kin_verified": kin_ok,
        "annotations": dict(annotations) if annotations else {},
        "merit_flow": "NONE",  # the law, stamped on the grant: money only
        "testnet": True,
        "provenance": "DERIVED",  # computed in-process by DCLM
    }
    envelope = meter.sign_receipt(grant)  # Ed25519 over canonical bytes

    # -- WRITE: DCLM commits -------------------------------------------------
    store = store if store is not None else ShareStore()
    commit_payload = {
        "grant_envelope": envelope,
        "grant_id": grant_id,
        "merit_flow": "NONE",
        "provenance": "DERIVED",  # the issue declaration, derived in-process
    }
    # PURIFY IN FLIGHT: the grant-issue transition is checked — kind
    # whitelisted, receipt planned and labeled, the registry growth
    # declared — before writes.py commits.
    purify_transition(
        {"grants": len(store.grants)},
        {"grants": len(store.grants) + 1, "grant_id": grant_id},
        KIND_GRANT_ISSUE,
        context={"receipt": commit_payload, "identity": granter,
                 "path": "share.issue_grant"},
    )
    commit_envelope = dclm_commit(
        KIND_GRANT_ISSUE, commit_payload, verdict, store
    )
    # PURIFY ON EXIT: the grant and its commit — labeled, signed,
    # identity-bound.
    return purify_output(
        {
            "grant_id": grant_id,
            "grant": envelope,
            "commit": commit_envelope,
            "store": store,
        },
        context={"path": "share.issue_grant", "signed": True},
    )


def _expires_iso(issued_at, duration_seconds):
    issued = datetime.fromisoformat(issued_at)
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(
        issued.timestamp() + duration_seconds, tz=timezone.utc
    ).isoformat()


# ---------------------------------------------------------------------------
# revoke — instant and total
# ---------------------------------------------------------------------------

def revoke_grant(granter, grant_id, *, store, now=None):
    """Revoke a grant. Instant and total: the revocation is committed
    through dclm_commit, and every subsequent access check reads the
    live revoked set — no stale reads, no grace period.

    Only the granter may revoke (NOT_GRANTER otherwise). Revoking twice
    is an honest refusal (ALREADY_REVOKED), not a silent no-op."""
    # PURIFY ON ENTRY: the medium first — revocation is a trust boundary.
    purify_input(
        {"identity": granter, "action": "REVOKE_GRANT",
         "grant_id": grant_id,
         "claims": [{"claim": "grant-revoke-request",
                     "provenance": "DERIVED"}]},
        context={"path": "share.revoke_grant"},
    )
    if store is None:
        raise ShareRefused(REASON_NO_STORE, "revocation needs the live registry")
    _require_testnet(granter, "granter")
    envelope = store.grants.get(grant_id)  # LIVE read
    if envelope is None:
        raise ShareRefused(
            REASON_GRANT_NOT_FOUND, f"no grant {grant_id!r} in the registry"
        )
    grant = envelope["receipt"]
    if grant.get("granter") != granter:
        raise ShareRefused(
            REASON_NOT_GRANTER, "only the granter may revoke this grant"
        )
    if grant_id in store.revoked:  # LIVE read
        raise ShareRefused(
            REASON_ALREADY_REVOKED, f"grant {grant_id!r} is already revoked"
        )

    verdict = check_rights(
        granter, KIND_GRANT_REVOKE,
        {"internal": "dclm.share", "schema": SCHEMA, "grant_id": grant_id},
    )
    payload = {
        "grant_id": grant_id,
        "granter": granter,
        "grantee": grant.get("grantee"),
        "revoked_at": _now_iso(now),
        "merit_flow": "NONE",
        "provenance": "DERIVED",  # the revocation declaration, derived
    }
    # PURIFY IN FLIGHT: the revocation transition is checked before
    # writes.py commits.
    purify_transition(
        {"revoked": len(store.revoked)},
        {"revoked": len(store.revoked) + 1, "grant_id": grant_id},
        KIND_GRANT_REVOKE,
        context={"receipt": payload, "identity": granter,
                 "path": "share.revoke_grant"},
    )
    commit_envelope = dclm_commit(KIND_GRANT_REVOKE, payload, verdict, store)
    # PURIFY ON EXIT: labeled, signed, identity-bound.
    return purify_output(
        {"grant_id": grant_id, "commit": commit_envelope, "store": store},
        context={"path": "share.revoke_grant", "signed": True},
    )


# ---------------------------------------------------------------------------
# check_access — the live verdict
# ---------------------------------------------------------------------------

_DENY_RANK = {
    REASON_NO_GRANT: 1,
    REASON_GRANT_REVOKED: 2,
    REASON_GRANT_EXPIRED: 3,
    REASON_TIER_TOO_LOW: 4,
    REASON_INVALID_GRANT: 5,
}



def check_access(grantee, content_type, required_tier, *, store, now=None):
    """May grantee touch content_type at required_tier, right now?

    Reads the CURRENT registry state - every check is live. Returns a
    frozen AccessVerdict(granted, reason, grant_id).

    The tier check is the structural tier-creep block: the grant's
    SIGNED tier_level integer is compared numerically against the
    required level. grant.tier_level >= required_level, or DENY.
    A FRIEND (1) grant against FAMILY-required (3) content denies by
    integer comparison - 1 >= 3 is false, always. The signature is
    verified BEFORE the tier is trusted: a tampered tier_level breaks
    the signature and the grant is INVALID_GRANT, fail-closed.

    Deny-reason priority when several grants almost match:
    INVALID_GRANT > TIER_TOO_LOW > GRANT_EXPIRED > GRANT_REVOKED >
    NO_GRANT. A forged grant never masks a valid one: any verified,
    live, sufficient grant returns GRANT immediately.

    Pure with respect to state: reads the registry, mutates nothing.
    """
    # PURIFY ON ENTRY: the medium first. This is a trust boundary — the
    # verdict it returns decides touch/no-touch. Anonymous callers are
    # refused here as PurificationRefused.
    purify_input(
        {"identity": grantee, "action": "CHECK_ACCESS",
         "content_type": content_type, "required_tier": required_tier,
         "claims": [{"claim": "access-check-request",
                     "provenance": "DERIVED"}]},
        context={"path": "share.check_access"},
    )
    if not _is_testnet_identity(grantee):
        return purify_output(
            AccessVerdict(False, REASON_NOT_TESTNET_IDENTITY, None),
            context={"path": "share.check_access",
                     "require_identity": False},
        )
    if required_tier not in TIER_LEVELS:
        return purify_output(
            AccessVerdict(False, REASON_UNKNOWN_TIER, None),
            context={"path": "share.check_access",
                     "require_identity": False},
        )
    if content_type not in CONTENT_TYPES:
        return purify_output(
            AccessVerdict(False, REASON_UNKNOWN_CONTENT_TYPE, None),
            context={"path": "share.check_access",
                     "require_identity": False},
        )
    if store is None:
        return purify_output(
            AccessVerdict(False, REASON_NO_GRANT, None),
            context={"path": "share.check_access",
                     "require_identity": False},
        )

    required = TIER_LEVELS[required_tier]
    now_iso = _now_iso(now)
    reason = REASON_NO_GRANT

    # LIVE iteration over current registry state - no snapshots.
    for grant_id, envelope in store.grants.items():
        grant = envelope.get("receipt", {})
        if grant.get("grantee") != grantee:
            continue
        if grant.get("content_type") != content_type:
            continue
        # Signature first: the tier integer is trusted only inside a
        # verified signature. Tampering -> INVALID_GRANT, fail-closed.
        if not meter.verify_receipt(envelope):
            reason = _worst(reason, REASON_INVALID_GRANT)
            continue
        if grant_id in store.revoked:  # LIVE read - instant revocation
            reason = _worst(reason, REASON_GRANT_REVOKED)
            continue
        if grant.get("expires_at") <= now_iso:
            reason = _worst(reason, REASON_GRANT_EXPIRED)
            continue
        level = grant.get("tier_level")
        # THE tier-creep wall: integer comparison against the signed
        # level. No policy string, no configuration - arithmetic.
        if not _is_int(level) or level < required:
            reason = _worst(reason, REASON_TIER_TOO_LOW)
            continue
        # PURIFY ON EXIT (grant path): the verdict leaves labeled.
        return purify_output(
            AccessVerdict(True, ACCESS_GRANT, grant_id),
            context={"path": "share.check_access",
                     "require_identity": False},
        )

    # PURIFY ON EXIT (deny path): the verdict leaves labeled.
    return purify_output(
        AccessVerdict(False, reason, None),
        context={"path": "share.check_access", "require_identity": False},
    )


def _worst(current, candidate):
    """Keep the higher-priority deny reason (see _DENY_RANK)."""
    if _DENY_RANK.get(candidate, 0) > _DENY_RANK.get(current, 0):
        return candidate
    return current


# ---------------------------------------------------------------------------
# access - the metered event. Money moves; merit never does.
# ---------------------------------------------------------------------------

def access(grantee, grant_id, action, *, store, wallet, now=None):
    """Exercise a grant: the metered shared-access event.

    Flow: live grant lookup -> signature/revocation/expiry/grantee
    checks (ANY failure -> honest ShareRefused, nothing deducted) ->
    price deducted from the ACCESSOR's wallet -> granter credited in
    full (the share rule: the provider is paid for what they shared) ->
    SHARED_ACCESS event committed with receipt.

    Money only. This function moves test-keys through LEDGER_DEBIT /
    LEDGER_CREDIT and records the event. It has no code path that
    accrues, transfers, or references merit - the grantee earns their
    own merit from their own verified receipts, never from this grant.
    Every committed payload carries merit_flow NONE; any merit smuggled
    into `action` is refused as malformed (MERIT_IN_GRANT).

    Returns a dict with the signed SHARED_ACCESS envelope plus the
    debit/credit envelopes (None when the grant is free).
    """
    # PURIFY ON ENTRY: the medium first. Money moves here — no anonymous
    # accessor, no forged identity, no unlabeled action.
    purify_input(
        {"identity": grantee, "action": action, "grant_id": grant_id,
         "claims": [{"claim": "grant-access-request",
                     "provenance": "DERIVED"}]},
        context={"path": "share.access"},
    )
    if store is None:
        raise ShareRefused(REASON_NO_STORE, "access needs the live registry")
    if wallet is None:
        raise ShareRefused(REASON_NO_WALLET, "access needs the wallet")
    _require_testnet(grantee, "grantee")
    _assert_no_merit(action, "action")

    envelope = store.grants.get(grant_id)  # LIVE read - never cached
    if envelope is None:
        raise ShareRefused(
            REASON_GRANT_NOT_FOUND, f"no grant {grant_id!r} in the registry"
        )
    grant = envelope.get("receipt", {})
    if grant.get("grantee") != grantee:
        raise ShareRefused(
            REASON_NOT_GRANTEE, "this grant was issued to another identity"
        )
    if not meter.verify_receipt(envelope):
        raise ShareRefused(
            REASON_INVALID_GRANT, "grant signature broken - fail closed"
        )
    if grant_id in store.revoked:  # LIVE read - revocation is instant
        raise ShareRefused(
            REASON_GRANT_REVOKED, "grant revoked by the granter"
        )
    now_iso = _now_iso(now)
    if grant.get("expires_at") <= now_iso:
        raise ShareRefused(REASON_GRANT_EXPIRED, "grant lifetime elapsed")

    granter = grant["granter"]
    price = grant["price"]
    debit_envelope = None
    credit_envelope = None

    if price > 0:
        # -- the accessor pays: debit, only when affordable ---------------
        before = wallet.balance(grantee)
        if before < price:
            # Honest refusal: intent unserved, balance untouched,
            # nothing committed.
            raise ShareRefused(
                REASON_INSUFFICIENT_KEYS,
                f"access costs {price} {UNIT}; {grantee} holds {before}",
            )
        debit_receipt = {
            "schema": SCHEMA,
            "type": "SHARED_ACCESS_DEBIT",
            "identity": grantee,
            "action": "SHARED_ACCESS",
            "amount": price,
            "unit": UNIT,
            "testnet": True,
            "grant_id": grant_id,
            "balance_before": before,
            "balance_after": before - price,
            "outcome": "GRANTED",
            "reason": None,
            "issued_at": now_iso,
            "provenance": "DERIVED",  # derived in-process by DCLM
            "merit_flow": "NONE",
            "note": (
                f"Shared-access fee: {price} {UNIT} for grant {grant_id}. "
                "TEST units only - not dollars, not eFuse. Money only; "
                "no merit moved."
            ),
        }
        verdict = check_rights(
            grantee, "LEDGER_DEBIT",
            {"internal": "dclm.share", "schema": SCHEMA,
             "grant": grant_id, "operation": "SHARED_ACCESS_DEBIT"},
        )
        # PURIFY IN FLIGHT: the accessor's debit transition is checked
        # before writes.py commits.
        purify_transition(
            {"balance": before}, {"balance": before - price},
            "LEDGER_DEBIT",
            context={"receipt": debit_receipt, "identity": grantee,
                     "path": "share.access"},
        )
        debit_envelope = dclm_commit(
            "LEDGER_DEBIT", debit_receipt, verdict,
            _ShareWalletAdapter(
                wallet, identity=grantee, receipt=debit_receipt,
                op="debit", balance_before=before,
                balance_after=before - price,
            ),
        )

        # -- the provider is paid: credit the granter in full ------------
        # The share rule, mechanical: the full access price goes to the
        # identity that shared the resource. DCLM takes no cut.
        # Money moves. Merit does not - there is no merit leg here.
        c_before = wallet.balance(granter)
        credit_receipt = {
            "schema": SCHEMA,
            "type": "SHARED_ACCESS_CREDIT",
            "identity": granter,
            "action": "SHARED_ACCESS",
            "amount": price,
            "unit": UNIT,
            "testnet": True,
            "grant_id": grant_id,
            "balance_before": c_before,
            "balance_after": c_before + price,
            "outcome": "GRANTED",
            "reason": None,
            "issued_at": now_iso,
            "provenance": "DERIVED",  # derived in-process by DCLM
            "merit_flow": "NONE",
            "note": (
                f"Shared-access earnings: {price} {UNIT} to the granter "
                f"for grant {grant_id}. TEST units only. Money only; "
                "no merit moved."
            ),
        }
        verdict = check_rights(
            granter, "LEDGER_CREDIT",
            {"internal": "dclm.share", "schema": SCHEMA,
             "grant": grant_id, "operation": "SHARED_ACCESS_CREDIT"},
        )
        # PURIFY IN FLIGHT: the granter's credit transition is checked
        # before writes.py commits.
        purify_transition(
            {"balance": c_before}, {"balance": c_before + price},
            "LEDGER_CREDIT",
            context={"receipt": credit_receipt, "identity": granter,
                     "path": "share.access"},
        )
        credit_envelope = dclm_commit(
            "LEDGER_CREDIT", credit_receipt, verdict,
            _ShareWalletAdapter(
                wallet, identity=granter, receipt=credit_receipt,
                op="credit", balance_before=c_before,
                balance_after=c_before + price,
            ),
        )

    # -- the access event: a WRITE, receipted ------------------------------
    event = {
        "schema": SCHEMA,
        "type": "SHARED_ACCESS",
        "grant_id": grant_id,
        "granter": granter,
        "grantee": grantee,
        "action": action,
        "content_type": grant["content_type"],
        "tier": grant["tier"],
        "tier_level": grant["tier_level"],
        "price": price,
        "unit": UNIT,
        "money_only": True,
        "merit_flow": "NONE",
        "debit_receipt_id": (
            debit_envelope["receipt"].get("receipt_id")
            if debit_envelope else None
        ),
        "credit_receipt_id": (
            credit_envelope["receipt"].get("receipt_id")
            if credit_envelope else None
        ),
        "at": now_iso,
        "testnet": True,
        "provenance": "DERIVED",  # derived in-process by DCLM
        "note": (
            "Metered shared access. Money (test-keys) moved per the "
            "share rule; merit never flows through a grant - the "
            "grantee's merit comes only from their own verified receipts."
        ),
    }
    verdict = check_rights(
        grantee, KIND_SHARED_ACCESS,
        {"internal": "dclm.share", "schema": SCHEMA, "grant": grant_id},
    )
    # PURIFY IN FLIGHT: the access-event transition is checked before
    # writes.py commits.
    purify_transition(
        {"access_events": len(store.access_log)},
        {"access_events": len(store.access_log) + 1, "grant_id": grant_id},
        KIND_SHARED_ACCESS,
        context={"receipt": event, "identity": grantee,
                 "path": "share.access"},
    )
    access_envelope = dclm_commit(KIND_SHARED_ACCESS, event, verdict, store)
    # PURIFY ON EXIT: every envelope labeled, signed, identity-bound.
    return purify_output(
        {
            "grant_id": grant_id,
            "access": access_envelope,
            "debit": debit_envelope,
            "credit": credit_envelope,
            "price": price,
        },
        context={"path": "share.access", "signed": True},
    )

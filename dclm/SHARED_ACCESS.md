# SHARED ACCESS — the kin layer's monetization

The wallet law's sharing model, made real. A Unity ID grants shared
access to another Unity ID, tiered by relationship. Subtle, persistent,
Unity-bound. Testnet only; test-keys only — never dollars, never eFuse.

Implementation: `dclm/share.py`. Tests: `dclm/test_share.py` (29/29).

## 1. Tiers — ordered integers, not labels

| Tier        | Level | Meaning |
|-------------|-------|---------|
| FRIEND      | 1     | a little |
| GOOD_FRIEND | 2     | more |
| FAMILY      | 3     | total |

The granter sets the tier; the system enforces exactly what was set,
nothing more. The level is an **integer inside the signed grant body**,
and `check_access()` compares integers:

```
grant.tier_level >= required_level   →   GRANT
```

A FRIEND (1) grant presented against FAMILY-required (3) content denies
because 1 >= 3 is false. This is the structural tier-creep block: there
is no policy string to reinterpret, no configuration to flip, no role
name to confuse — the arithmetic is the wall. And the integer is
trusted only inside a verified Ed25519 signature: anyone who hand-edits
`tier_level` 1 → 3 breaks the signature, the check verifies the
signature first, and the grant is `INVALID_GRANT` — fail-closed. A
forged tier can never be promoted; it can only die.

Tier creep is therefore impossible **structurally, not by policy**: to
exercise family-tier access you need a signature over the integer 3,
and only DCLM's issue path (with verified kin, see §5) ever signs one.

## 2. What gets shared

Money and information share the same rails. A grant names:

* **content_type** — one of `DATA`, `RTE_SEAT`, `WORLD_VIEW`,
  `RESOURCE`, `COMPUTE`. A grant for `DATA` never opens an `RTE_SEAT`
  (`NO_GRANT` on mismatch).
* **depth** — a free-text descriptor of what is shared
  (e.g. `"summary extract"`, `"full telemetry"`). Recorded in the
  signed grant and receipted.
* **duration** — lifetime in seconds; the grant carries `issued_at`
  and `expires_at`. Expired grants deny (`GRANT_EXPIRED`).
* **price** — optional, non-negative integer of test-keys (per the
  pricing engine).

Every grant is bound to **both** Unity IDs (`granter`, `grantee`),
receipted through `dclm_commit`, and revocable (see §4).

## 3. Metering flow — money moves, and only money

`access(grantee, grant_id, action)` is the metered event:

1. **Live grant lookup** — the registry is read at call time, never
   cached. Missing grant, wrong grantee, broken signature, revoked, or
   expired → honest `ShareRefused`, **nothing deducted, nothing
   committed**.
2. **The accessor pays** — if `price > 0`, the accessor's wallet is
   checked for affordability first. Insufficient keys →
   `INSUFFICIENT_KEYS`, balance untouched, no write. Affordable →
   `LEDGER_DEBIT` committed through `dclm_commit` (rights-checked,
   DCLM-internal, receipted).
3. **The granter is paid** — the share rule, mechanical: the **full**
   access price is credited to the granter via `LEDGER_CREDIT`. The
   provider is paid for what they shared. DCLM takes no cut.
4. **The event is written** — a `SHARED_ACCESS` commit records the
   grant, the action, the price, and the debit/credit receipt refs.

Free grants (`price = 0`) skip the money legs and commit only the
access event. Every leg carries `merit_flow: "NONE"` on its receipt —
auditable proof that no merit moved.

## 4. Revocation — instant and total

`revoke_grant(granter, grant_id)` commits `GRANT_REVOKE` through the
single commit path. The revoked set lives in the registry and **every
access check reads it live** — there is no cache layer, no TTL, no
snapshot, no grace period. A revocation committed a millisecond ago is
visible to the next check. Only the granter may revoke
(`NOT_GRANTER`); revoking twice is an honest refusal
(`ALREADY_REVOKED`), not a silent no-op.

## 5. Kin is binding

Family-tier grants require **verified kin only**. The L2 umpires are
the kin-verification authority. **Integration status: PENDING** — no L2
module exists in this build, so `verify_kin()` has no authority to
consult and returns False, always. Family grants are therefore refused
with `NOT_KIN_VERIFIED` until the umpires wire in. Kinship is never
assumed; an erroring authority verifies nothing (fail-closed).

Integration contract for the future L2 module: call
`register_kin_authority(fn)` with a verifier
`(granter, grantee) -> bool`. Only that registered authority's boolean
can satisfy the family tier — `issue_grant()` takes no kinship flag
from callers, so there is no parameter to lie through.

## 6. Derivative merit regeneration (David's law-grade rule)

A grant **enables work** — access to data, seats, views, compute — but
the grantee earns their **own** merit from their **own** verified
receipts. **Money can flow through a grant; MERIT NEVER FLOWS through
a grant.** No grant, at any tier, transfers merit from granter to
grantee.

Why this kills pyramid dynamics by construction: a pyramid needs
upstream standing to accumulate from downstream activity — the upline
harvesting the downline's merit. Here the rails physically cannot carry
merit. Value flows outward like sap (access fees pay the provider), but
each leaf photosynthesizes its own (merit accrues only from one's own
verified receipts, through the tokenization pipeline — a module
`share.py` never imports and cannot reach). There is no upline. There
is no downline. There are only peers, paying each other for access,
each earning their own standing. The family tier shares **more**
(depth, duration, content) — never merit. Tier = access depth, not
standing transfer.

Structural enforcement, not promises:

* `access()` moves test-keys through `LEDGER_DEBIT`/`LEDGER_CREDIT`
  and nothing else. No code path in `share.py` accrues, transfers,
  mints, or references merit scores — verified by an introspection test
  that fails the suite if a merit path ever appears.
* `_assert_no_merit()` scans every external payload (annotations,
  actions). A grant carrying a merit payload is refused as malformed
  (`MERIT_IN_GRANT`) — if a future caller tries to pass merit through
  a grant, the structure refuses.
* Every grant, debit, credit, and access event carries
  `merit_flow: "NONE"` — the law stamped on the receipts.

## 7. Rights and writes

Grants are **RIGHTS**: `issue_grant()` / `revoke_grant()` authorize via
`rights.check_rights()` with the DCLM-internal source `dclm.share`.
Access events are **WRITES**: committed via `writes.dclm_commit` with
kinds `GRANT_ISSUE`, `GRANT_REVOKE`, `SHARED_ACCESS` (whitelisted in
`rights.COMMIT_KINDS`; money legs reuse `LEDGER_DEBIT` /
`LEDGER_CREDIT`). The client never grants or revokes directly — it
requests, DCLM executes. Without a DCLM-issued GRANT verdict, the
commit boundary raises before any mutation: no write, no receipt, no
trace.

## 8. Honesty rules

* UNKNOWN is never PASS; every refusal names its true reason.
* Non-`unity:testnet:` identities are refused at every entry point.
* Failed access deducts nothing and commits nothing.
* The ledger never goes negative (asserted after every mutation).
* Provenance labels on every receipt; receipts Ed25519-signed with the
  existing testnet key material (`../keys/`, same as the meter).

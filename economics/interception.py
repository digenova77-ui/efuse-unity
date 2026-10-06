#!/usr/bin/env python3
"""
INTERCEPTION — the first lawful exit. TESTNET ONLY.

Worker 4's perpetuity drill (economics/gauntlet/PERPETUITY.md, Drill 2)
proved this mechanism is MISSING in code but specified precisely and
drill-tested as an overlay. This module is the build: a signed
InterceptionOrder, an AuthorityRegistry, and a wrapping gate around the
real tokenomics.Ledger (never monkey-patching Ledger).

Law (David): interception is a lawful exit — explicit, receipted, rare.
NOT a backdoor: wrong key / no authority proof must FAIL.

Mechanism:
  1. Explicit invocation only. A signed InterceptionOrder — never an
     ambient flag, never an admin panel.
     Schema: unity.economics.interception.v1.testnet
  2. Authority proof. Ed25519 signature verified against an
     AuthorityRegistry (key_id -> pubkey), registered IN CONFIG — the
     registry has no hardcoded keys. The registry itself is NOT
     interceptable (rotation goes through supersession, not interception).
     Unknown key or bad/missing signature -> UnlawfulInterception,
     nothing changes.
  3. Action allowlist (CLOSED — anything else refused):
       freeze_pool   — halt movement on one pool (scope: one pool)
       freeze_all    — halt movement everywhere (scope: global)
       hold_emission — hold a pool's emission computation (scope: one pool)
       release       — lift a live order early (scope: an order_id)
     Never interceptable, even by the lawful key: pool lifetime caps,
     receipt history, Unity bindings, Honor records, fuse state, the
     authority registry itself, merit origin fields, constitutional
     params. Scope touching any of these refuses.
  4. Bounded by construction. duration_epochs is a positive int with a
     hard MAX_INTERCEPT_EPOCHS (100). Unbounded/zero/negative/non-int
     duration refuses. Interception PAUSES; it never rewrites. A
     permanent change is supersession, not interception.
  5. In-flight semantics keyed on EPOCH, not wall time. A movement call
     tagged with epoch < the order's issued_at_epoch completes under
     pre-interception law; epoch >= issued_at_epoch is refused. No
     mid-flight preemption, no silent drops.
  6. Freeze blocks MOVEMENT, not measurement, not giving.
       freeze_pool(P): disburse(P) refused; emission_close(P) keeps
         COMPUTING (measurement recorded) unless it would move funds
         (reserve absorb/release under freeze refuses); transfer_merit,
         cause_disburse, donate, accrue_merit, apply_decay flow.
       freeze_all: both pools' disburse refused; emission_close computes
         (no reserve movements); transfer_merit, cause_disburse and
         mesh_route refused everywhere. donate still flows — giving is
         never frozen.
       hold_emission(P): emission_close(P) refused outright (the
         computation itself is held) and disburse(P) refused. Giving,
         merit accrual/decay, transfers flow.
  7. Release is explicit or by expiry. Orders auto-expire at
     issued_at_epoch + duration_epochs (swept on advance_epoch / before
     any gated call), or a signed RELEASE order lifts a live order
     early. Frozen-epoch computed claims do NOT auto-pay on release —
     each re-disbursement is explicit, receipted, and references the
     release. (No pre-funding, no auto-pay — the law holds during
     exits too.)
  8. Full receipting. The order itself is receipted into the MAIN chain
     (receipt kind "interception" — added to tokenomics.RECEIPT_KINDS)
     with its authority proof; every refused movement is receipted as
     refused-with-cause (never silently dropped); every unlawful order
     attempt is receipted as refused. The interception event log is
     append-only.

TESTNET ONLY. TEST keypairs in tests (ephemeral, /tmp, never real keys).
"""

import hashlib
import json
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import tokenomics as T
from wallet import _node_sign, _node_verify

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.economics.interception.v1.testnet"

# The action allowlist. CLOSED. Anything else is refused — even when the
# signature is valid and the key is registered.
ACTIONS = frozenset({"freeze_pool", "freeze_all", "hold_emission", "release"})

# Bounded by construction: an interception pauses, it never rewrites.
MAX_INTERCEPT_EPOCHS = 100

POOLS = ("human", "machine")

# Receipts require a unity_id; authority acts are bound to this reserved
# identity — a pool's members are never impersonated by the mechanism.
INTERCEPT_IDENTITY = "unity:testnet:authority"

# Scope keys that may NEVER appear on an order — even under a lawful key:
# pool lifetime caps, receipt history, Unity bindings, Honor records,
# fuse state, the authority registry, merit origin fields, constitutional
# params. Touching one is refused.
NEVER_INTERCEPTABLE_SCOPE_KEYS = frozenset({
    "unity", "pool_cap", "pool_caps", "cap", "caps", "receipts",
    "honor", "fuse", "registry", "origin", "law", "params",
    "constitutional",
})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class InterceptionError(Exception):
    """Base for interception failures."""


class UnlawfulInterception(InterceptionError):
    """The interception order was not lawful — refused, nothing changed."""


class InterceptionFreezeError(InterceptionError):
    """A lawful freeze/hold is in effect — the movement is refused, loudly
    (receipted as refused-with-cause, never silently dropped)."""


# ---------------------------------------------------------------------------
# Authority registry — in-config, never hardcoded
# ---------------------------------------------------------------------------

class AuthorityRegistry:
    """key_id -> Ed25519 pubkey (DER bytes).

    Lawful authority keys are REGISTERED, in config — nothing is
    hardcoded here. The registry itself is NOT interceptable: no
    interception action can add, remove, or rotate keys (that path is
    supersession, a separate lawful exit)."""

    def __init__(self):
        self._keys = {}

    def register(self, key_id, pubkey_der):
        """Register a lawful authority key. key_id is a non-empty string;
        pubkey_der is Ed25519 public-key DER bytes."""
        if not isinstance(key_id, str) or not key_id.strip():
            raise ValueError("authority key_id must be a non-empty string")
        if not isinstance(pubkey_der, (bytes, bytearray)) or not pubkey_der:
            raise ValueError("authority pubkey must be non-empty DER bytes")
        self._keys[key_id.strip()] = bytes(pubkey_der)

    def pubkey(self, key_id):
        """Return the registered pubkey DER for key_id, or None."""
        return self._keys.get(key_id)

    def key_ids(self):
        return tuple(self._keys)

    @classmethod
    def from_config(cls, config):
        """Build a registry from config: {key_id: pubkey_der | base64 str}.
        Keys come from configuration, never from module constants."""
        reg = cls()
        for key_id, pub in (config or {}).items():
            if isinstance(pub, str):
                import base64
                pub = base64.b64decode(pub)
            reg.register(key_id, pub)
        return reg


# ---------------------------------------------------------------------------
# The signed order
# ---------------------------------------------------------------------------

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


class InterceptionOrder:
    """A signed interception order — the ONLY way to invoke interception.

    Fields: order_id, action (allowlist), scope (dict), duration_epochs
    (positive int, bounded), issued_at_epoch (int), authority_key_id,
    reason (non-empty), nonce (non-empty), signature (Ed25519 over the
    canonical body)."""

    def __init__(self, order_id, action, scope, duration_epochs,
                 issued_at_epoch, authority_key_id, reason, nonce):
        self.order_id = order_id
        self.action = action
        self.scope = scope if scope is not None else {}
        self.duration_epochs = duration_epochs
        self.issued_at_epoch = issued_at_epoch
        self.authority_key_id = authority_key_id
        self.reason = reason
        self.nonce = nonce
        self.signature = None

    def body(self):
        return {
            "schema": SCHEMA,
            "order_id": self.order_id,
            "action": self.action,
            "scope": self.scope,
            "duration_epochs": self.duration_epochs,
            "issued_at_epoch": self.issued_at_epoch,
            "authority_key_id": self.authority_key_id,
            "reason": self.reason,
            "nonce": self.nonce,
        }

    def sign(self, privkey_der):
        """Sign the canonical body with an Ed25519 private key (DER)."""
        self.signature = _node_sign(bytes(privkey_der), _canonical(self.body()))
        return self

    def verify(self, pubkey_der):
        """True iff a signature is present and verifies over the body."""
        if not self.signature:
            return False
        try:
            return bool(_node_verify(bytes(pubkey_der),
                                    _canonical(self.body()), self.signature))
        except Exception:
            return False

    @property
    def effective_epoch(self):
        return self.issued_at_epoch

    @property
    def expiry_epoch(self):
        return self.issued_at_epoch + self.duration_epochs

    def covers(self, pool, epoch):
        """True iff this order's freeze/hold is live for pool at epoch."""
        if self.action not in ("freeze_pool", "freeze_all", "hold_emission"):
            return False
        if self.action in ("freeze_pool", "hold_emission"):
            if self.scope.get("pool") != pool:
                return False
        # freeze_all covers every pool
        return self.effective_epoch <= epoch < self.expiry_epoch

    def covered_pools(self):
        if self.action in ("freeze_pool", "hold_emission"):
            return (self.scope.get("pool"),)
        if self.action == "freeze_all":
            return POOLS
        return ()


# ---------------------------------------------------------------------------
# The wrapping gate (not monkey-patching Ledger)
# ---------------------------------------------------------------------------

class InterceptedLedger:
    """The interception gate: wraps a real tokenomics.Ledger.

    Movement calls consult the live orders before delegating. Measurement
    (emission_close computation, accrual, decay) and giving (donate)
    continue under freeze; blocked movements raise InterceptionFreezeError
    AND are receipted as refused-with-cause. Unlawful orders raise
    UnlawfulInterception and change nothing."""

    def __init__(self, ledger, registry):
        if not isinstance(ledger, T.Ledger):
            raise TypeError("InterceptedLedger wraps a tokenomics.Ledger")
        if not isinstance(registry, AuthorityRegistry):
            raise TypeError("InterceptedLedger needs an AuthorityRegistry")
        self.ledger = ledger
        self.registry = registry
        self.live = {}            # order_id -> InterceptionOrder (live)
        self._seen_order_ids = set()
        self.events = []          # append-only interception event log
        self._current_epoch = 0

    # -- epoch ---------------------------------------------------------
    def advance_epoch(self, epoch):
        """Advance the gate's epoch clock; sweep auto-expired orders."""
        if not isinstance(epoch, int) or epoch < 0:
            raise ValueError("epoch must be a non-negative int")
        self._current_epoch = epoch
        self._sweep(epoch)

    def _epoch_of(self, epoch):
        return self._current_epoch if epoch is None else epoch

    def _sweep(self, epoch):
        expired = [oid for oid, o in self.live.items()
                   if o.expiry_epoch <= epoch]
        for oid in expired:
            o = self.live.pop(oid)
            self._receipt("order_expired",
                          {"order_id": oid,
                           "action": o.action,
                           "scope": o.scope,
                           "expired_at_epoch": epoch,
                           "note": "auto-expiry at issued_at_epoch + "
                                   "duration_epochs — no auto-pay; frozen "
                                   "claims require explicit re-disbursement."},
                          epoch)
            self.events.append({"event": "ORDER_EXPIRED", "order_id": oid,
                                "at_epoch": epoch})

    # -- receipting ----------------------------------------------------
    def _receipt(self, event, detail, epoch):
        """Receipt an interception event into the MAIN chain (kind
        'interception'), with the cause. Never silent."""
        d = {"event": event}
        d.update(detail)
        r = T.Receipt.build(INTERCEPT_IDENTITY, "interception", d,
                            "VERIFIED", epoch, self.ledger._chain_head)
        return self.ledger.apply_receipt(r)

    def _refuse_order(self, order, reason, epoch):
        body = order.body() if isinstance(order, InterceptionOrder) else repr(order)
        self._receipt("unlawful_order_refused",
                      {"order": body, "reason": reason,
                       "note": "unlawful interception refused — state unchanged"},
                      epoch)
        self.events.append({"event": "ORDER_REFUSED", "reason": reason})
        raise UnlawfulInterception(reason)

    def _refuse_movement(self, what, pool, order, epoch, reason):
        self._receipt("movement_refused",
                      {"movement": what, "pool": pool,
                       "order_id": order.order_id if order else None,
                       "action": order.action if order else None,
                       "authority_key_id": (order.authority_key_id
                                            if order else None),
                       "epoch": epoch, "cause": reason,
                       "note": "blocked movement is receipted, never silently "
                               "dropped"},
                      epoch)
        self.events.append({"event": "MOVEMENT_REFUSED", "movement": what,
                            "cause": reason})
        raise InterceptionFreezeError(reason)

    # -- the gate ------------------------------------------------------
    def apply_interception(self, order):
        """Explicit invocation. Every check must pass; any failure raises
        UnlawfulInterception and changes NOTHING (validated before any
        receipt or state mutation)."""
        epoch = self._current_epoch
        if not isinstance(order, InterceptionOrder):
            self._refuse_order(order, "not an InterceptionOrder", epoch)
        # 1. order identity (unique — an order_id is never applied twice)
        if not isinstance(order.order_id, str) or not order.order_id.strip():
            self._refuse_order(order, "order_id must be a non-empty string", epoch)
        if order.order_id in self._seen_order_ids:
            self._refuse_order(order,
                               f"order_id {order.order_id!r} already applied — "
                               "orders are single-use", epoch)
        # 2. action allowlist — CLOSED
        if order.action not in ACTIONS:
            self._refuse_order(
                order,
                f"action {order.action!r} not in allowlist {sorted(ACTIONS)} — "
                "allowlist is CLOSED", epoch)
        # 3. reason and nonce — every interception carries its why
        if not isinstance(order.reason, str) or not order.reason.strip():
            self._refuse_order(order,
                               "reason must be a non-empty string — every "
                               "interception is receipted with its why", epoch)
        if not isinstance(order.nonce, str) or not order.nonce.strip():
            self._refuse_order(order, "nonce must be a non-empty string", epoch)
        # 4. bounded by construction
        if (not isinstance(order.duration_epochs, int)
                or isinstance(order.duration_epochs, bool)
                or order.duration_epochs <= 0):
            self._refuse_order(order,
                               "duration_epochs must be a positive int", epoch)
        if order.duration_epochs > MAX_INTERCEPT_EPOCHS:
            self._refuse_order(
                order,
                f"duration {order.duration_epochs} exceeds "
                f"MAX_INTERCEPT_EPOCHS={MAX_INTERCEPT_EPOCHS} — unbounded "
                "interception refused; permanent change is supersession, "
                "not interception", epoch)
        if (not isinstance(order.issued_at_epoch, int)
                or isinstance(order.issued_at_epoch, bool)
                or order.issued_at_epoch < 0):
            self._refuse_order(order,
                               "issued_at_epoch must be a non-negative int", epoch)
        # 5. scope — per action, closed; never-interceptable keys refused
        scope = order.scope if isinstance(order.scope, dict) else None
        if scope is None:
            self._refuse_order(order, "scope must be a dict", epoch)
        bad = NEVER_INTERCEPTABLE_SCOPE_KEYS.intersection(scope)
        if bad:
            self._refuse_order(
                order,
                f"scope touches {sorted(bad)} — never interceptable, even by "
                "the lawful key (caps, receipts, Unity bindings, Honor, "
                "fuse, registry, origin, constitutional params)", epoch)
        if order.action in ("freeze_pool", "hold_emission"):
            if set(scope) != {"pool"} or scope.get("pool") not in POOLS:
                self._refuse_order(
                    order,
                    f"{order.action} scope must be exactly "
                    "{{'pool': 'human'|'machine'}}", epoch)
        elif order.action == "freeze_all":
            if set(scope) != {"global"} or scope.get("global") is not True:
                self._refuse_order(
                    order, "freeze_all scope must be exactly "
                           "{'global': True}", epoch)
        elif order.action == "release":
            if set(scope) != {"order_id"}:
                self._refuse_order(
                    order, "release scope must be exactly "
                           "{'order_id': <live order id>}", epoch)
            target = scope.get("order_id")
            if target not in self.live:
                self._refuse_order(
                    order, f"no live order {target!r} to release", epoch)
        # 6. authority proof — registered key + valid signature over the body
        if (not isinstance(order.authority_key_id, str)
                or not order.authority_key_id.strip()):
            self._refuse_order(order, "authority_key_id is required", epoch)
        pub = self.registry.pubkey(order.authority_key_id)
        if pub is None:
            self._refuse_order(
                order,
                f"unknown authority key {order.authority_key_id!r} — not "
                "registered in the AuthorityRegistry", epoch)
        if not order.verify(pub):
            self._refuse_order(
                order,
                "signature invalid or missing — no authority proof; "
                "wrong key / tampered body fails", epoch)
        # 7. no overlapping live coverage (a pool already frozen cannot be
        #    frozen again — release or wait for expiry first)
        if order.action in ("freeze_pool", "freeze_all", "hold_emission"):
            wanted = set(order.covered_pools())
            for o in self.live.values():
                overlap = wanted.intersection(o.covered_pools())
                if overlap and o.expiry_epoch > order.issued_at_epoch:
                    self._refuse_order(
                        order,
                        f"live {o.action} {o.order_id!r} already covers "
                        f"{sorted(overlap)} — overlapping interception refused",
                        epoch)

        # ---- all checks passed: apply --------------------------------
        self._seen_order_ids.add(order.order_id)
        if order.action == "release":
            target = self.live.pop(scope["order_id"])
            self._receipt("order_released",
                          {"order_id": scope["order_id"],
                           "released_action": target.action,
                           "released_scope": target.scope,
                           "by_order": order.order_id,
                           "authority_key_id": order.authority_key_id,
                           "reason": order.reason,
                           "authority_proof": (
                               f"Ed25519 by {order.authority_key_id} — "
                               "verified against AuthorityRegistry"),
                           "note": "explicit early release — NO auto-pay: "
                                   "frozen claims require explicit "
                                   "re-disbursement"},
                          epoch)
            self.events.append({"event": "ORDER_RELEASED",
                                "order_id": scope["order_id"],
                                "by_order": order.order_id})
            return order

        self.live[order.order_id] = order
        self._receipt("order_applied",
                      {"order": order.body(),
                       "signature": order.signature,
                       "expiry_epoch": order.expiry_epoch,
                       "authority_proof": (
                           f"Ed25519 by {order.authority_key_id} — "
                           "verified against AuthorityRegistry")},
                      epoch)
        self.events.append({"event": "ORDER_APPLIED",
                            "order_id": order.order_id,
                            "action": order.action})
        return order

    # -- liveness ------------------------------------------------------
    def _live_block(self, pool, epoch, kinds):
        """Return the live order blocking pool at epoch (or None)."""
        self._sweep(epoch)
        for o in self.live.values():
            if o.action in kinds and o.covers(pool, epoch):
                return o
        return None

    def _live_freeze(self, pool, epoch):
        return self._live_block(pool, epoch, ("freeze_pool", "freeze_all"))

    def _live_hold(self, pool, epoch):
        return self._live_block(pool, epoch, ("hold_emission",))

    def _live_global(self, epoch):
        self._sweep(epoch)
        for o in self.live.values():
            if o.action == "freeze_all" and o.covers(None, epoch):
                return o
        return None

    def live_orders(self):
        """Live (unexpired, unreleased) orders — for surfacing in state."""
        self._sweep(self._current_epoch)
        return dict(self.live)

    def summary(self):
        """Live interceptions, surfaced for economic_state.py."""
        return [{"order_id": o.order_id, "action": o.action,
                 "scope": o.scope,
                 "effective_epoch": o.effective_epoch,
                 "expiry_epoch": o.expiry_epoch,
                 "authority_key_id": o.authority_key_id,
                 "reason": o.reason}
                for o in self.live_orders().values()]

    # -- gated movement ------------------------------------------------
    def disburse(self, pool, unity_id, amount, epoch=None):
        epoch = self._epoch_of(epoch)
        fr = self._live_freeze(pool, epoch)
        if fr is not None:
            self._refuse_movement(
                "disburse", pool, fr, epoch,
                f"pool {pool!r} frozen by {fr.order_id} "
                f"(epochs {fr.effective_epoch}-{fr.expiry_epoch - 1}) — "
                "movement refused with cause")
        return self.ledger.disburse(pool, unity_id, amount, epoch)

    def emission_close(self, pool, merit_map=None, peg_ratio=None,
                       epoch=None, winter=None, holdback_fraction=None,
                       reserve_release=None):
        """Measurement continues under freeze — but a hold_emission refuses
        the computation itself, and a freeze refuses any reserve movement
        (frozen funds move nowhere).

        merit_map is UNTRUSTED input passed through to
        Ledger.emission_close: cross-checked against earned standing
        (exact restatement) and refused on any mismatch. None closes
        against every earner's standing."""
        epoch = self._epoch_of(epoch)
        hold = self._live_hold(pool, epoch)
        if hold is not None:
            self._refuse_movement(
                "emission_close", pool, hold, epoch,
                f"emission for pool {pool!r} held by {hold.order_id} "
                f"(epochs {hold.effective_epoch}-{hold.expiry_epoch - 1})")
        fr = self._live_freeze(pool, epoch)
        if fr is not None and (holdback_fraction is not None
                               or reserve_release is not None):
            self._refuse_movement(
                "emission_close", pool, fr, epoch,
                f"pool {pool!r} frozen by {fr.order_id} — reserve "
                "absorb/release is movement; measurement without fund "
                "movement continues")
        return self.ledger.emission_close(pool, merit_map, peg_ratio, epoch,
                                          winter=winter,
                                          holdback_fraction=holdback_fraction,
                                          reserve_release=reserve_release)

    def transfer_merit(self, from_unity_id, to_unity_id, amount, reason,
                       epoch=None, auth=None):
        """Merit ownership movement halts under freeze_all only — the merit
        book is pool-agnostic, so a pool-scoped freeze does not reach it.
        auth is the sender's signed transfer authorization (S1b): the
        underlying ledger refuses unsigned transfers
        (MeritTransferAuthError) — the freeze gate runs first, the
        authorization gate runs second, neither bypasses the other."""
        epoch = self._epoch_of(epoch)
        gl = self._live_global(epoch)
        if gl is not None:
            self._refuse_movement(
                "transfer_merit", "global", gl, epoch,
                f"global freeze by {gl.order_id} — merit ownership movement "
                "halted")
        return self.ledger.transfer_merit(from_unity_id, to_unity_id, amount,
                                          reason, epoch, auth=auth)

    def cause_disburse(self, unity_id, amount, receipt, epoch=None):
        """Lock disbursement is movement — halted under freeze_all."""
        epoch = self._epoch_of(epoch)
        gl = self._live_global(epoch)
        if gl is not None:
            self._refuse_movement(
                "cause_disburse", "global", gl, epoch,
                f"global freeze by {gl.order_id} — Lock movement halted")
        return self.ledger.cause_disburse(unity_id, amount, receipt, epoch)

    def mesh_route(self, unity_id, commissioning_pool, manifest_hash,
                   epoch=None, terms_note=""):
        """Routing is movement — halted under freeze_all."""
        epoch = self._epoch_of(epoch)
        gl = self._live_global(epoch)
        if gl is not None:
            self._refuse_movement(
                "mesh_route", "global", gl, epoch,
                f"global freeze by {gl.order_id} — routing halted")
        return self.ledger.mesh_route(unity_id, commissioning_pool,
                                      manifest_hash, epoch, terms_note)

    # -- never gated: measurement and giving ---------------------------
    def donate(self, unity_id, amount, kind, epoch=None):
        """Giving is never frozen — donations always flow."""
        return self.ledger.donate(unity_id, amount, kind,
                                  self._epoch_of(epoch))

    def accrue_merit(self, unity_id, receipt, weight):
        return self.ledger.accrue_merit(unity_id, receipt, weight)

    def apply_decay(self, unity_id, epochs, rate=None):
        return self.ledger.apply_decay(unity_id, epochs, rate)

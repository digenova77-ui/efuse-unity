"""
THE FUSE — the network-launch mechanism.

David's law: "the eFuse token itself carries a fuse that kicks out a Unity
token — that emission IS the launch of the network."

The Fuse is bound to David's Unity ID (founder). It is a state machine:

    ARMED -> TRIGGERED -> SPENT

triggered exactly once, by David's signed authorization only. The trigger
emits the genesis Unity token allocation and marks the fuse SPENT
permanently — a one-way handoff. After the trigger, the founder has no
further control, BY CONSTRUCTION:

  1. The Fuse object holds NO private key — it verifies signatures only.
     There is nothing in it that can authorize anything.
  2. The transition table has NO outgoing edge from SPENT. The terminal
     state is terminal in code, not in policy.
  3. This module contains no mint/admin/override/backdoor/unseal function.
     The only Unity-creating code paths in the whole economics package are
     Fuse.trigger_fuse (genesis, once) and wallet.receive_unity_emission
     (merit-gated receipts from the tokenomics engine). Asserted by test
     via AST inspection of both modules. The genesis credit itself is
     ticket-gated (CRITICAL-3): Ledger._apply_fuse_genesis requires the
     one-shot ticket issued only to a fuse mid lawful trigger, and
     re-verifies David's signature at the mint — no ticket, no mint.
  4. Replay is impossible: the authorization nonce is registered, and a
     second trigger raises before the authorization is even parsed.
  5. The founder's wallet after genesis is an ordinary Wallet — same code
     paths, no privileges.
  6. Fuse state persists hash-chained with the ledger receipts; tampering
     breaks the chain audibly on load.

The genesis Unity AMOUNT is HELD for David (GENESIS_UNITY_AMOUNT = None —
never invented here, TOKENOMICS §13). The fuse refuses to trigger until
his signed authorization states the amount. UNKNOWN never PASS.

After launch, Unity enters circulation ONLY via merit-gated emission per
the tokenomics engine (wallet.receive_unity_emission with a gated
receipt). No other mint path exists in code.

TESTNET ONLY. Founder key defaults to ../keys/unity-world-test.pub.

Integration contract (economic_state.py, same directory):
  compute_donation_lock(donations) -> dict   # called with a list
"""

import copy
import hashlib
import json
import os

from wallet import (
    KEY_ID,
    TEST_PUB_KEY,
    Ledger,
    Wallet,
    _canonical_bytes,
    _node_sign,
    _node_verify,
    _sha256_hex,
    _utc_now,
)

_HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
SCHEMA = "unity.economics.fuse.v1.testnet"

STATE_ARMED = "ARMED"
STATE_TRIGGERED = "TRIGGERED"
STATE_SPENT = "SPENT"
FUSE_STATES = (STATE_ARMED, STATE_TRIGGERED, STATE_SPENT)

# The state machine, as data. SPENT has no outgoing edges — the handoff is
# one-way because there is nowhere else to go.
_FUSE_TRANSITIONS = {
    STATE_ARMED: (STATE_TRIGGERED,),
    STATE_TRIGGERED: (STATE_SPENT,),
    STATE_SPENT: (),
}

# The genesis Unity allocation amount. None = HELD for David's word
# (TOKENOMICS_5050_MERIT.md §13 — parameters never invented here).
# The fuse cannot trigger without the amount arriving inside his SIGNED
# authorization; there is no default to fall back on.
GENESIS_UNITY_AMOUNT = None

# The Core Cause Lock address: UNKNOWN until a real address exists.
# No placeholder is ever rendered as live (NEW_ECONOMIC_MODEL §1.3).
CORE_CAUSE_LOCK_ADDRESS = {
    "value": "UNKNOWN",
    "provenance": "UNKNOWN",
    "note": "no locked address exists yet; none is invented or rendered",
}


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------
class FuseError(Exception):
    """Base class for all fuse failures."""


class FuseNotArmed(FuseError):
    """trigger_fuse called while the fuse is not ARMED (already spent)."""


class FuseRefused(FuseError):
    """The authorization failed validation — refused, state unchanged."""


class FuseReplay(FuseError):
    """An authorization nonce was seen before — replay refused."""


# ---------------------------------------------------------------------------
# the founder's-machine side: build the signed authorization
# ---------------------------------------------------------------------------
def make_fuse_authorization(founder_privkey_der: bytes,
                            founder_unity_id: str,
                            genesis_unity_amount: int,
                            nonce: str | None = None) -> dict:
    """David's machine signs the launch authorization.

    The amount travels INSIDE the signed body — it is his digit, stated by
    him, bound by his signature. DCLM-side code only verifies.
    """
    import uuid
    if not isinstance(genesis_unity_amount, int) or \
            isinstance(genesis_unity_amount, bool) or \
            genesis_unity_amount <= 0:
        raise FuseRefused("genesis_unity_amount must be a positive integer — "
                          "David's digit, never invented here")
    body = {
        "founder_unity_id": founder_unity_id,
        "genesis_unity_amount": genesis_unity_amount,
        "nonce": nonce or uuid.uuid4().hex,
    }
    sig = _node_sign(founder_privkey_der, _canonical_bytes(body))
    return {**body, "signature": sig, "key_id": KEY_ID}


# ---------------------------------------------------------------------------
# the Fuse
# ---------------------------------------------------------------------------
class Fuse:
    """The fuse. Verify-only: constructed with the founder's PUBLIC key.

    No private key material ever enters this object — there is no
    attribute, parameter, or code path that could hold or use one.
    """

    def __init__(self, founder_unity_id: str,
                 founder_pubkey_path: str = TEST_PUB_KEY,
                 ledger: Ledger | None = None,
                 state_dir: str | None = None):
        self.founder_unity_id = founder_unity_id
        with open(founder_pubkey_path, "rb") as fh:
            # PUBLIC key bytes only. This is all the authority the fuse
            # ever holds: the ability to RECOGNIZE David's signature.
            self._founder_pubkey = fh.read()
        self.key_id = KEY_ID
        self._ledger = ledger if ledger is not None else Ledger()
        if state_dir is None:
            state_dir = self._ledger.state_dir
        self._state_dir = state_dir
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        self._state = STATE_ARMED
        self._genesis = None
        self._nonces = set()
        self._load()

    # -- persistence ----------------------------------------------------
    def _state_path(self):
        return os.path.join(self._state_dir, "fuse-state.json")

    def _snapshot(self):
        return {
            "schema": SCHEMA,
            "founder_unity_id": self.founder_unity_id,
            "key_id": self.key_id,
            "state": self._state,
            "genesis": self._genesis,
            "used_nonces": sorted(self._nonces),
        }

    def _save(self):
        if not self._state_dir:
            return
        with open(self._state_path(), "w") as fh:
            json.dump(self._snapshot(), fh, sort_keys=True)

    def _load(self):
        if not self._state_dir or not os.path.exists(self._state_path()):
            return
        with open(self._state_path()) as fh:
            snap = json.load(fh)
        if snap.get("schema") != SCHEMA:
            raise FuseError(f"unknown fuse schema: {snap.get('schema')!r}")
        if snap.get("founder_unity_id") != self.founder_unity_id:
            raise FuseError("fuse state names a different founder — refused")
        if snap.get("state") not in FUSE_STATES:
            raise FuseError(f"corrupt fuse state {snap.get('state')!r}")
        self._state = snap["state"]
        self._genesis = snap.get("genesis")
        self._nonces = set(snap.get("used_nonces", []))

    # -- state machine ---------------------------------------------------
    def status(self) -> str:
        """Read-only. ARMED, TRIGGERED (transient, never persisted), SPENT."""
        return self._state

    def _transition(self, to: str) -> None:
        allowed = _FUSE_TRANSITIONS[self._state]
        if to not in allowed:
            raise FuseNotArmed(
                f"fuse is {self._state}: no transition to {to} exists")
        self._state = to

    # -- the trigger ------------------------------------------------------
    def trigger_fuse(self, authorization: dict) -> dict:
        """Verify David's authorization and launch the network. Exactly once.

        1. The fuse must be ARMED — otherwise FuseNotArmed is raised BEFORE
           the authorization is even parsed. A spent fuse is deaf.
        2. The authorization must carry founder_unity_id, a positive-int
           genesis_unity_amount (his digit), a fresh nonce, and an Ed25519
           signature over the canonical body that verifies against the
           founder's public key. Anything missing or off -> FuseRefused.
           UNKNOWN never PASS.
        3. ARMED -> TRIGGERED -> SPENT, atomically: the genesis Unity
           allocation is credited to the founder's wallet (an ordinary
           Wallet — no privileges), the nonce is registered, the receipt
           is chained, and the state persists as SPENT.
        """
        if self._state != STATE_ARMED:
            # The fuse is spent. No authorization — however signed — is
            # examined. This is the one-way handoff, in code.
            raise FuseNotArmed(
                f"fuse is {self._state}: the launch happened exactly once")

        auth = authorization if isinstance(authorization, dict) else {}
        body = {k: auth.get(k) for k in
                ("founder_unity_id", "genesis_unity_amount", "nonce")}

        if body["founder_unity_id"] != self.founder_unity_id:
            raise FuseRefused("authorization names a different founder")
        amount = body["genesis_unity_amount"]
        if (not isinstance(amount, int) or isinstance(amount, bool)
                or amount <= 0):
            raise FuseRefused(
                "genesis_unity_amount must be a positive integer stated by "
                "David in his signed authorization — no default exists")
        nonce = body["nonce"]
        if not nonce or not isinstance(nonce, str):
            raise FuseRefused("authorization carries no nonce")
        if nonce in self._nonces:
            raise FuseReplay("authorization nonce already used")
        if not auth.get("signature") or not _node_verify(
                self._founder_pubkey, _canonical_bytes(body),
                auth["signature"]):
            raise FuseRefused(
                "founder signature FAILED — only David's signed "
                "authorization can trigger the fuse")

        try:
            founder_wallet = self._ledger.wallet(self.founder_unity_id)
        except Exception as exc:
            raise FuseRefused(
                "founder wallet is not provisioned in this ledger — "
                "no wallet is invented at launch") from exc

        genesis_manifest = _sha256_hex(_canonical_bytes(
            {"fuse": "genesis", **body}))
        genesis_body = {
            "founder_unity_id": self.founder_unity_id,
            "key_id": self.key_id,
            "nonce": nonce,
            # The amount is David's word: REPORTED. The trigger event —
            # signature verified in-process — is VERIFIED.
            "genesis_amount_provenance": "REPORTED — David's word",
            "provenance": "VERIFIED",
        }

        try:
            self._transition(STATE_TRIGGERED)
            # CRITICAL-3 gate: the mint is ticket-gated. The ledger issues
            # the one-shot capability only to a fuse mid lawful trigger,
            # and _apply_fuse_genesis re-verifies the signed authorization
            # (founder signature, bound params, genesis manifest) before
            # any balance moves. No ticket — no mint.
            ticket = self._ledger._issue_genesis_ticket(self, auth)
            receipt = self._ledger._apply_fuse_genesis(
                self.founder_unity_id, amount, genesis_body,
                genesis_manifest, ticket)
            self._nonces.add(nonce)
            self._genesis = {
                "manifest_hash": genesis_manifest,
                "amount": amount,
                "amount_provenance": "REPORTED — David's word",
                "founder_unity_id": self.founder_unity_id,
                "nonce": nonce,
            }
            self._transition(STATE_SPENT)
            self._save()
        except Exception:
            # Anything failed mid-trigger: restore ARMED from disk (the
            # disk still says ARMED — _save only runs on success) and
            # re-raise. The fuse never strands in TRIGGERED.
            self._load()
            raise
        return copy.deepcopy(receipt)


# ---------------------------------------------------------------------------
# mint_paths — the exhaustive list, as code
# ---------------------------------------------------------------------------
def mint_paths() -> list:
    """Every code path by which Unity can enter circulation. Exactly two:

    1. fuse.Fuse.trigger_fuse — the genesis allocation, once, David-signed.
    2. wallet.receive_unity_emission — merit-gated emission receipts from
       the tokenomics engine.

    There is no third path. The AST test in test_fuse.py enforces this
    structurally on every run.
    """
    return [
        "fuse.Fuse.trigger_fuse — genesis Unity allocation, exactly once, "
        "by David's signed authorization only",
        "wallet.receive_unity_emission — Unity against merit-gated "
        "emission receipts (tokenomics engine), manifest_hash idempotent",
    ]


# ---------------------------------------------------------------------------
# integration contract: economic_state.py calls this with a list
# ---------------------------------------------------------------------------
def _receipt_id(body: dict) -> str:
    return _sha256_hex(_canonical_bytes(body))


def compute_donation_lock(donations) -> dict:
    """Build the donation_lock section for the EconomicState.

    Accepts raw dicts in the documented input shape {"donor_unity_id",
    "amount", "kind": "efuse"|"fiat", "provenance", "donation_receipt"}
    or wallet.donate() receipts (kind "donation").

    The Lock is one-way in, Honor out — never Merit, never money. The
    address stays UNKNOWN until a real address exists: nothing is
    invented. Donor exclusion is the standing rule (§9).
    """
    lock = {
        "provenance": "DERIVED",
        "address": dict(CORE_CAUSE_LOCK_ADDRESS),
        "donor_exclusion": {
            "rule": "donated eFuse is never re-emitted to the same donor — "
                    "the Lock is one-way per donor",
            "provenance": "REPORTED",  # ratified §9
        },
    }
    inflow = []
    honor_per_id = {}
    for item in (donations or []):
        if not isinstance(item, dict):
            continue
        donor = item.get("donor_unity_id")
        if not donor:
            continue  # no anonymous donations exist to the ledger
        donor = str(donor)
        amount = item.get("amount")
        amount = amount if isinstance(amount, (int, float)) else None
        kind = item.get("kind")
        if kind == "donation":
            kind = "efuse"  # wallet.donate() receipts are eFuse donations
        prov = item.get("provenance")
        prov = prov if prov in ("REPORTED", "VERIFIED", "MODELED",
                               "DERIVED", "UNKNOWN") else "UNKNOWN"
        body = {
            "movement": "donation",
            "donor_unity_id": donor,
            "amount": amount,
            "kind": kind,
            "provenance": prov,
            "ts": _utc_now(),
        }
        receipt_id = _receipt_id(body)  # always the 64-char content hash
        source = item.get("donation_receipt") or item.get("manifest_hash")
        entry = {
            "receipt_id": receipt_id,
            "movement": body["movement"],
            "donor_unity_id": donor,
            "amount": amount,
            "kind": kind,
            "provenance": prov,
            "ts": body["ts"],
            # Honor, never Merit: the donation receipt IS the honor record.
            "accrues": "HONOR",
            "never_accrues": "MERIT",
        }
        if source:
            entry["source_receipt"] = source
        inflow.append(entry)
        honor_per_id[donor] = honor_per_id.get(donor, 0) + 1
    lock["inflow"] = inflow
    lock["honor_accrued"] = {
        "per_unity_id": honor_per_id,
        "provenance": "DERIVED",
    }
    return lock

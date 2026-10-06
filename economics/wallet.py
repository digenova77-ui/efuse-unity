"""
UNITY WALLET — the UnityID wallet as prepaid bank (DCLM-side state machine).

Worker 3 of the NEW unified economic model build. TESTNET ONLY.

Laws baked in (~/workspace/dccp-world/WALLET_DESIGN_LAW.md):
  §1 shareable identity — every wallet exposes a click-to-copy share code;
     qr_payload() is the DIGITAL TWIN of the QR image: the exact payload a
     QR would encode, as sendable/copyable text.
  §2 easiest connectors — connect() trivially links two Unity IDs.
  §3 tiered sharing — friend / good_friend / family. Tiers are SET BY THE
     HUMAN via SIGNED tier grants (Ed25519); the wallet VERIFIES the
     signature before honoring the tier. No signature, no tier — enforced
     cryptographically in code, not by policy promise.
  §4 money AND information on the same rails — share() carries either;
     the mechanism (Unity binding, tier check, receipt, idempotency) is
     identical; only the content type varies.
  §5 kin is binding — the family tier requires a mutual signed kin bond.
     (Deeper kin mechanism: TBD per the law — flagged KIN_MECHANISM_TBD.)
  §6 rings of rings — every boundary (tier gate, balance gate, receipt
     gate, idempotency gate, donor-exclusion gate) is enforced in code at
     the point of mutation.

Tokenomics baked in (~/workspace/dccp-world/TOKENOMICS_5050_MERIT.md):
  §7  donations accrue Honor, never Merit. No honor->eFuse path exists
      anywhere in this module (asserted by test).
  §8  every movement is Unity-bound. No anonymous flows. Unity tokens are
      bound to their Unity ID: they are NOT transferable between wallets —
      no exceptions, not even David (his word, 2026-10-06 ~3:35 AM EDT;
      the bound-transfer-sale concept is dead). Merit IS transferable
      (his word, same moment): sold, gifted, transferred between Unity
      IDs — all receipted through the token engine. Transfers move
      OWNERSHIP (economic value) only; origin fields stay in the engine
      and standing never moves.
  §9  donations go one-way to the Core Cause Lock; donor exclusion blocks
      the donated amount's return path to the donor.
  §11 every mutation is receipted; idempotency via manifest_hash; every
      economic figure carries a provenance label. UNKNOWN never PASS.

David's laws: real data only; nothing minted — a new wallet holds ZERO of
everything (the hard gate stands); balances change ONLY via receipted
flows. Testnet keys only (../keys/); no production paths.

Integration contract (economic_state.py, same directory):
  compute_wallet_state(wallets) -> dict   # called with a list
"""

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
TIER_FRIEND = "friend"
TIER_GOOD_FRIEND = "good_friend"
TIER_FAMILY = "family"
TIERS = (TIER_FRIEND, TIER_GOOD_FRIEND, TIER_FAMILY)

TOKEN_EFUSE = "eFuse"
TOKEN_UNITY = "Unity"
TOKENS = (TOKEN_EFUSE, TOKEN_UNITY)

PROVENANCE_LABELS = frozenset(
    {"REPORTED", "VERIFIED", "MODELED", "DERIVED", "UNKNOWN"}
)

SCHEMA = "unity.economics.wallet.v1.testnet"

KEYS_DIR = os.path.join(_HERE, "..", "keys")
TEST_PRIV_KEY = os.path.join(KEYS_DIR, "unity-world-test.key")
TEST_PUB_KEY = os.path.join(KEYS_DIR, "unity-world-test.pub")
ED25519_HELPER = os.path.join(_HERE, "..", "dclm", "ed25519.js")

KEY_ID = "unity-world-test"  # TESTNET ONLY

TESTNET_IDENTITY_PREFIX = "unity:testnet:"

# Tier sharing limits. PROVENANCE: MODELED. These numbers are NOT David's —
# tier weights are HELD for his word (TOKENOMICS_5050_MERIT.md §13.7).
# The mechanism below enforces whatever table is set; conservative defaults
# stand in until he sets them. None = uncapped (family: total access).
TIER_LIMITS = {
    TIER_FRIEND: {
        "efuse_per_share": 100,
        "shares_per_epoch": 10,
        "info_events_per_epoch": 50,
    },
    TIER_GOOD_FRIEND: {
        "efuse_per_share": 1000,
        "shares_per_epoch": 50,
        "info_events_per_epoch": 250,
    },
    TIER_FAMILY: {
        "efuse_per_share": None,
        "shares_per_epoch": None,
        "info_events_per_epoch": None,
    },
    "provenance": "MODELED",
    "note": "HELD for David (TOKENOMICS §13.7) — conservative defaults; "
            "the code enforces the table, it does not bless the numbers.",
}

# Honor class names and tiers are HELD for David (TOKENOMICS §13.12).
HONOR_CLASS_UNNAMED = "UNNAMED — HELD for David (TOKENOMICS §13.12)"

# Kin binding: the mutual-signature bond below is the recorded principle.
# A deeper kin mechanism is TBD per WALLET_DESIGN_LAW.md §5.
KIN_MECHANISM_TBD = True


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------
class WalletError(Exception):
    """Base class for all wallet failures."""


class InsufficientFunds(WalletError):
    """A debit was refused: the receipted balance does not cover it."""


class TierViolation(WalletError):
    """A sharing flow was refused: no tier, a forged tier, or a tier limit."""


class InvalidReceipt(WalletError):
    """An inbound receipt failed validation — refused, never applied."""


class UnknownWallet(WalletError):
    """The Unity ID names no wallet in this ledger."""


class UnityBindingError(WalletError):
    """A Unity-token movement that would break Unity binding was refused."""


class DonorExclusionViolation(WalletError):
    """A disbursement tried to return a donor's own donation to them."""


# ---------------------------------------------------------------------------
# crypto + hashing helpers (Ed25519 via ../dclm/ed25519.js, testnet keys)
# ---------------------------------------------------------------------------
def _canonical_bytes(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class _TempKeyFile:
    """A DER key blob staged as a 0600 file for the node signing helper."""

    def __init__(self, data: bytes):
        self.data = data
        self.path = None

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(prefix="unity-key-", suffix=".der")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(self.data)
        return self.path

    def __exit__(self, *exc):
        try:
            if self.path and os.path.exists(self.path):
                os.unlink(self.path)
        except OSError:
            pass
        return False


def _node_sign(privkey_der: bytes, msg: bytes) -> str:
    """Ed25519-sign msg with a DER PKCS#8 private key. Returns base64 sig."""
    with _TempKeyFile(privkey_der) as path:
        proc = subprocess.run(
            ["node", ED25519_HELPER, "sign", path],
            input=msg, capture_output=True, timeout=30,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"signing failed: {proc.stderr.decode()!r}")
    return proc.stdout.decode().strip()


def _node_verify(pubkey_der: bytes, msg: bytes, sig_b64: str) -> bool:
    """Ed25519-verify. Returns True/False — never raises on bad data."""
    try:
        with _TempKeyFile(pubkey_der) as path:
            proc = subprocess.run(
                ["node", ED25519_HELPER, "verify", path, sig_b64],
                input=msg, capture_output=True, timeout=30,
            )
        return proc.returncode == 0
    except Exception:
        return False


def generate_test_keypair():
    """Generate an EPHEMERAL Ed25519 keypair (testnet only).

    Returns (priv_der, pub_der). Keys live in /tmp for the process's use
    and are never production keys. Used by tests for tier-grant and kin
    signatures — the human's device signs; DCLM only verifies.
    """
    script = (
        "const c=require('crypto');"
        "const k=c.generateKeyPairSync('ed25519');"
        "console.log(k.privateKey.export({format:'der',type:'pkcs8'}).toString('base64'));"
        "console.log(k.publicKey.export({format:'der',type:'spki'}).toString('base64'));"
    )
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, timeout=30
    )
    if proc.returncode != 0:
        raise RuntimeError(f"keygen failed: {proc.stderr.decode()!r}")
    priv_b64, pub_b64 = proc.stdout.decode().strip().splitlines()
    return base64.b64decode(priv_b64), base64.b64decode(pub_b64)


def derive_unity_id(pubkey_der: bytes) -> str:
    """One-way Unity ID derivation: unity:testnet: + sha256(pubkey).

    Same form as economic_state.testnet_unity_id. No secret involved —
    the public key is public.
    """
    return TESTNET_IDENTITY_PREFIX + _sha256_hex(pubkey_der)


def _manifest_hash(manifest: dict) -> str:
    return _sha256_hex(_canonical_bytes(manifest))


# ---------------------------------------------------------------------------
# Emission authority — the lawful emitter's key (CRITICAL-4 fix)
# ---------------------------------------------------------------------------
# Emission receipts are cryptographically bound to the emission authority:
# the tokenomics Ledger / epoch runner that lawfully issues emission.
# Every receipt credited by receive_emission / receive_unity_emission must
# carry an Ed25519 signature over its canonical body, made by the
# authority's private key. The wallet ledger holds the authority's PUBLIC
# key (registered at Ledger construction); no signature, a bad signature,
# or a tampered body -> InvalidReceipt, nothing credited.
#
# No PKI is invented here: the trust root is the existing testnet keypair
# (keys/unity-world-test.{key,pub}); tests register ephemeral keypairs per
# ledger via generate_test_keypair().

EMISSION_AUTHORITY_KEY_ID = "emission-authority:testnet"


def _read_der(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def default_emission_authority_keys():
    """(priv_der, pub_der) of the testnet emission authority keypair.

    TESTNET ONLY — the lawful emitter on testnet. Tests should prefer
    ephemeral keypairs from generate_test_keypair().
    """
    return _read_der(TEST_PRIV_KEY), _read_der(TEST_PUB_KEY)


_EMISSION_SIG_FIELDS = ("emitter_signature", "emitter_key_id")


def _emission_signing_body(receipt: dict) -> dict:
    """The canonical receipt body covered by the authority signature:
    every field except the signature envelope itself."""
    return {k: v for k, v in receipt.items()
            if k not in _EMISSION_SIG_FIELDS}


def sign_emission_receipt(receipt_body: dict, privkey_der=None,
                          key_id=EMISSION_AUTHORITY_KEY_ID) -> dict:
    """The lawful emitter signs a receipt's canonical body (CRITICAL-4).

    Returns a NEW dict: the body plus 'emitter_signature' (base64 Ed25519
    over the canonical body, minus any prior signature fields) and
    'emitter_key_id'. privkey_der=None -> the testnet authority key;
    pass an ephemeral private key in tests. Re-signing a signed receipt
    re-signs the body without the old signature (idempotent envelope).
    """
    if privkey_der is None:
        privkey_der = _read_der(TEST_PRIV_KEY)
    body = _emission_signing_body(receipt_body)
    signed = dict(body)
    signed["emitter_signature"] = _node_sign(
        privkey_der, _canonical_bytes(body))
    signed["emitter_key_id"] = key_id
    return signed


def emission_receipt_signature_valid(receipt: dict, pubkey_der: bytes,
                                     key_id: str) -> bool:
    """True iff the receipt carries key_id and an Ed25519 signature that
    verifies over the canonical receipt body with pubkey_der. A tampered
    body, a wrong-key signature, a missing signature, or a key_id
    mismatch all return False. Never raises."""
    try:
        if not isinstance(receipt, dict):
            return False
        if receipt.get("emitter_key_id") != key_id:
            return False
        sig = receipt.get("emitter_signature")
        if not sig or not isinstance(sig, str):
            return False
        return _node_verify(pubkey_der,
                            _canonical_bytes(_emission_signing_body(receipt)),
                            sig)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# ReceiptChain — append-only, hash-chained receipt log
# ---------------------------------------------------------------------------
class ReceiptChain:
    """Every mutation is receipted; each receipt chains to the previous.

    Tampering with the log breaks the chain audibly (verify() -> False).
    """

    def __init__(self):
        self._entries = []

    def append(self, receipt: dict) -> dict:
        prev = self._entries[-1]["chain_hash"] if self._entries else "GENESIS"
        entry = {
            "seq": len(self._entries),
            "ts": _utc_now(),
            "receipt": copy.deepcopy(receipt),
            "prev_chain_hash": prev,
        }
        entry["chain_hash"] = _sha256_hex(
            _canonical_bytes({"prev": prev, "receipt": receipt})
        )
        self._entries.append(entry)
        return copy.deepcopy(entry)

    def verify(self) -> bool:
        prev = "GENESIS"
        for i, entry in enumerate(self._entries):
            if entry["seq"] != i or entry["prev_chain_hash"] != prev:
                return False
            expect = _sha256_hex(
                _canonical_bytes(
                    {"prev": entry["prev_chain_hash"],
                     "receipt": entry["receipt"]})
            )
            if entry["chain_hash"] != expect:
                return False
            prev = entry["chain_hash"]
        return True

    def __len__(self):
        return len(self._entries)

    def entries(self):
        return copy.deepcopy(self._entries)


# ---------------------------------------------------------------------------
# Fuse genesis ticket — the one-shot authorization capability for the
# Unity mint (CRITICAL-3 closure)
# ---------------------------------------------------------------------------
class _FuseGenesisTicket:
    """One-shot capability proving a fuse trigger is lawfully mid-flight.

    Issued ONLY by Ledger._issue_genesis_ticket, which requires the Fuse
    to be mid-trigger (state TRIGGERED) on that ledger — a state the Fuse
    enters only inside Fuse.trigger_fuse, AFTER David's signed
    authorization verified (fuse.py). The ticket carries the verified
    authorization (body + founder signature) and the fuse's genesis
    manifest; _apply_fuse_genesis re-verifies all of it through
    _require_genesis_ticket and consumes the ticket. A missing, forged,
    replayed, or foreign ticket is refused at the mint gate — the mint is
    not reachable without passing through the fuse authorization check.
    """

    __slots__ = ("_fuse", "_authorization", "_manifest_hash", "_consumed")

    def __init__(self, fuse, authorization: dict, manifest_hash: str):
        self._fuse = fuse
        self._authorization = dict(authorization)
        self._manifest_hash = manifest_hash
        self._consumed = False


def _require_genesis_ticket(ledger, unity_id: str, amount: int,
                            manifest_hash: str, ticket) -> _FuseGenesisTicket:
    """Prove the mint call rides a lawful fuse trigger. Raises WalletError
    otherwise — the mint is refused without a valid fuse authorization.

    Checks, in order: the ticket is a genuine one-shot ticket; it is
    unconsumed; its fuse is still mid-trigger (TRIGGERED) on this ledger
    and owns this ledger's launch; the mint parameters match the SIGNED
    authorization body; the manifest hash is the fuse's genesis manifest
    for that body; and the founder's signature re-verifies against the
    fuse's founder public key. The ticket is consumed before return — a
    replay is refused even by the same caller.
    """
    from fuse import Fuse as _Fuse  # lazy: fuse.py imports wallet at top
    if not isinstance(ticket, _FuseGenesisTicket):
        raise WalletError(
            "fuse genesis refused: no fuse authorization ticket — the "
            "genesis mint is reachable only through Fuse.trigger_fuse")
    fuse = ticket._fuse
    if ticket._consumed:
        raise WalletError(
            "fuse genesis refused: authorization ticket already consumed — "
            "one-shot")
    if not isinstance(fuse, _Fuse) or \
            getattr(fuse, "_ledger", None) is not ledger:
        raise WalletError(
            "fuse genesis refused: ticket's fuse is not bound to this "
            "ledger")
    if fuse.status() != "TRIGGERED":
        raise WalletError(
            f"fuse genesis refused: fuse is {fuse.status()} — the launch "
            "happened exactly once")
    if ledger._genesis_fuse is not fuse:
        raise WalletError(
            "fuse genesis refused: this ledger's launch belongs to "
            "another fuse")
    auth = ticket._authorization
    body = {k: auth.get(k) for k in
            ("founder_unity_id", "genesis_unity_amount", "nonce")}
    if unity_id != body["founder_unity_id"]:
        raise WalletError(
            "fuse genesis refused: unity_id does not match the signed "
            "fuse authorization")
    if amount != body["genesis_unity_amount"]:
        raise WalletError(
            "fuse genesis refused: amount does not match the signed fuse "
            "authorization")
    if manifest_hash != ticket._manifest_hash:
        raise WalletError(
            "fuse genesis refused: manifest hash is not the fuse's "
            "genesis manifest")
    sig = auth.get("signature")
    if not sig or not _node_verify(getattr(fuse, "_founder_pubkey", b""),
                                  _canonical_bytes(body), sig):
        raise WalletError(
            "fuse genesis refused: founder signature FAILED at the mint "
            "gate — only David's signed authorization mints genesis Unity")
    ticket._consumed = True
    return ticket


# ---------------------------------------------------------------------------
# Ledger — the DCLM-side state all wallets share
# ---------------------------------------------------------------------------
class Ledger:
    """The DCLM-side state machine behind every wallet.

    Holds balances, the applied-manifest registry (idempotency), tier
    grants, kin bonds, the identity registry, the honor ledger, donation
    records, the seed registry (membership mirror — never money), and
    the hash-chained receipt log. Persists to state_dir
    (ledger-state.json + receipts.jsonl) when one is given; otherwise
    runs in-memory.
    """

    def __init__(self, state_dir=None, emission_authority_pubkey_der=None,
                 emission_authority_key_id=None):
        self.state_dir = state_dir
        self._wallets = {}        # unity_id -> {"eFuse": int, "Unity": int,
                                  #             "owner_pubkey_b64": str,
                                  #             "seed": {...} (optional)}
        self._applied = {}        # manifest_hash -> receipt (idempotency)
        self._grants = []         # tier grants, append-only; latest wins
        self._kin = []            # [{"pair": [a, b], "nonce": str}]
        self._honor = []          # honor accrual records
        self._donations = []      # donation records (donor exclusion source)
        self._seeds = {}          # unity_id -> seed info (MEMBERSHIP mirror)
        self._counters = {}       # (from, to, epoch, kind) -> int
        self._chain = ReceiptChain()
        # Emission authority (CRITICAL-4): the PUBLIC key whose signature
        # every credited emission receipt must carry. Authority config, not
        # ledger state — passed at construction, never persisted. Defaults
        # to the testnet authority keypair; tests register ephemeral keys.
        self.emission_authority_pubkey_der = (
            emission_authority_pubkey_der
            if emission_authority_pubkey_der is not None
            else _read_der(TEST_PUB_KEY))
        self.emission_authority_key_id = (
            emission_authority_key_id or EMISSION_AUTHORITY_KEY_ID)
        self._genesis_fuse = None  # the Fuse that owns this ledger's one
                                   # launch (in-memory). The durable record
                                   # is the kind=fuse-genesis receipt in
                                   # self._applied (survives reload).
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
            self._load()

    # -- persistence ------------------------------------------------------
    def _state_path(self):
        return os.path.join(self.state_dir, "ledger-state.json")

    def _receipts_path(self):
        return os.path.join(self.state_dir, "receipts.jsonl")

    def _snapshot(self):
        return {
            "schema": SCHEMA,
            "wallets": self._wallets,
            "applied": self._applied,
            "grants": self._grants,
            "kin": self._kin,
            "honor": self._honor,
            "donations": self._donations,
            "seeds": self._seeds,
            "counters": [
                {"key": list(k), "count": v}
                for k, v in self._counters.items()
            ],
        }

    def _save(self):
        if not self.state_dir:
            return
        with open(self._state_path(), "w") as fh:
            json.dump(self._snapshot(), fh, sort_keys=True)
        with open(self._receipts_path(), "w") as fh:
            for entry in self._chain.entries():
                fh.write(json.dumps(entry, sort_keys=True) + "\n")

    def _load(self):
        if not os.path.exists(self._state_path()):
            return
        with open(self._state_path()) as fh:
            snap = json.load(fh)
        if snap.get("schema") != SCHEMA:
            raise WalletError(f"unknown ledger schema: {snap.get('schema')!r}")
        self._wallets = snap.get("wallets", {})
        self._applied = snap.get("applied", {})
        self._grants = snap.get("grants", [])
        self._kin = snap.get("kin", [])
        self._honor = snap.get("honor", [])
        self._donations = snap.get("donations", [])
        self._seeds = snap.get("seeds", {})
        self._counters = {
            tuple(c["key"]): c["count"] for c in snap.get("counters", [])
        }
        self._chain = ReceiptChain()
        if os.path.exists(self._receipts_path()):
            with open(self._receipts_path()) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self._chain._entries.append(json.loads(line))
        if not self._chain.verify():
            raise WalletError("receipt chain FAILED verification on load — "
                              "state was tampered with")

    # -- the idempotency core ---------------------------------------------
    def _apply(self, manifest_hash: str, mutate, receipt: dict) -> dict:
        """Apply a mutation exactly once per manifest_hash.

        mutate() runs first and may fill in measured fields on the receipt
        dict (before/after balances, both-side sides). Then the receipt is
        stored, chained, and persisted. If the manifest was already
        applied, the ORIGINAL receipt is returned unchanged and mutate()
        never runs again — a retry is a no-op.
        """
        if manifest_hash in self._applied:
            return copy.deepcopy(self._applied[manifest_hash])
        mutate()
        stored = copy.deepcopy(receipt)
        stored["manifest_hash"] = manifest_hash
        stored["ts"] = _utc_now()
        stored["schema"] = SCHEMA
        self._applied[manifest_hash] = stored
        self._chain.append(stored)
        self._save()
        return copy.deepcopy(stored)

    def manifest_applied(self, manifest_hash: str) -> bool:
        return manifest_hash in self._applied

    def verify_chain(self) -> bool:
        return self._chain.verify()

    # -- wallets ----------------------------------------------------------
    def new_wallet(self, unity_id: str, owner_pubkey_der_b64: str) -> "Wallet":
        """Open a wallet. A new wallet holds ZERO of everything — the hard
        gate: nothing is minted, no inflow exists, so zero is VERIFIED."""
        if unity_id in self._wallets:
            return Wallet(unity_id, self)
        try:
            base64.b64decode(owner_pubkey_der_b64)
        except Exception:
            raise WalletError("owner pubkey is not valid base64 DER")
        manifest = _manifest_hash({"op": "wallet_open", "unity_id": unity_id})

        def mutate():
            self._wallets[unity_id] = {
                "eFuse": 0,
                "Unity": 0,
                "owner_pubkey_b64": owner_pubkey_der_b64,
            }

        receipt = {
            "kind": "wallet_open",
            "unity_id": unity_id,
            "balances": {"eFuse": 0, "Unity": 0},
            "provenance": "VERIFIED",  # no inflow receipts exist: zero by log
        }
        self._apply(manifest, mutate, receipt)
        return Wallet(unity_id, self)

    def wallet(self, unity_id: str) -> "Wallet":
        if unity_id not in self._wallets:
            raise UnknownWallet(f"no wallet for {unity_id!r} in this ledger")
        return Wallet(unity_id, self)

    def has_wallet(self, unity_id: str) -> bool:
        """Does this ledger hold a wallet for the Unity ID?"""
        return unity_id in self._wallets

    # -- seed membership mirror (ONE SEED — David's law, 2026-10-06) ------
    def record_seed(self, unity_id: str, seed_info: dict) -> dict:
        """Mirror the one free seed as MEMBERSHIP on the wallet — never
        money, never priced, never spendable, never counted as wealth.

        David's law: "no matter how much money you have you only buy one
        seed, and it costs you nothing." The seed is the genesis entry —
        the root's gift to the new leaf. The DCLM seeder (dclm/seed.py)
        is AUTHORITATIVE for the one-seed rule; this ledger holds a
        receipted mirror so membership is visible where identity state
        lives.

        seed_info = {"seed_id", "receipt_sha256", "issued_at",
        "provenance"} — the seed_id is the deterministic idempotency
        key, so a double record returns the original receipt (no-op).

        Raises UnknownWallet when no wallet exists for the ID: UNKNOWN
        never PASS — membership mirrors onto real identity state only.
        The seed touches NO balance: eFuse/Unity are untouched before
        and after (asserted by test).
        """
        if unity_id not in self._wallets:
            raise UnknownWallet(
                f"no wallet for {unity_id!r} in this ledger — a seed "
                "mirrors onto real identity state only (UNKNOWN never "
                "PASS)")
        if not isinstance(seed_info, dict) or not seed_info.get("seed_id"):
            raise WalletError("record_seed needs seed_info with a seed_id")
        seed_id = seed_info["seed_id"]
        receipt = {
            "kind": "seed",
            "unity_id": unity_id,
            "seed_id": seed_id,
            "seed_receipt_sha256": seed_info.get("receipt_sha256"),
            "seed_issued_at": seed_info.get("issued_at"),
            "transferable": False,   # no seed market — structurally
            "spendable": False,      # membership, not money
            "purchasable": False,    # received, not bought
            "price": 0,              # costs nothing — always
            "cost": 0,               # nothing deducted — always
            "membership_note": (
                "ONE SEED (David's law, 2026-10-06): the genesis entry — "
                "the root's gift to the new leaf. One per Unity ID, free, "
                "non-transferable, non-spendable. It opens the door; "
                "nothing more."
            ),
            "provenance": "VERIFIED",  # recorded in-process by the seeder
        }

        def mutate():
            # THE membership mark — the only seed write on this ledger.
            # Balances are NOT touched: the seed is not wealth.
            self._wallets[unity_id]["seed"] = {
                "issued": True,
                "seed_id": seed_id,
                "recorded_at": _utc_now(),
            }
            self._seeds[unity_id] = {
                "seed_id": seed_id,
                "seed_receipt_sha256": seed_info.get("receipt_sha256"),
                "seed_issued_at": seed_info.get("issued_at"),
                "recorded_at": _utc_now(),
            }

        # Structural: no seed mirror may ever carry a balance-shaped
        # field — the seed is not wealth and may never be priced.
        for key in ("amount", "balance", "efuse", "unity", "value"):
            if key in receipt:
                raise WalletError(
                    f"seed mirror must never carry {key!r} — the seed is "
                    "membership, not wealth")
        return self._apply(seed_id, mutate, receipt)

    def seed_membership(self, unity_id: str) -> dict:
        """The seed membership state for a Unity ID (read-only).

        {"seeded": bool, "seed": {...}|None, "provenance": "DERIVED"} —
        membership, not a balance. Never priced, never spendable."""
        info = self._seeds.get(unity_id)
        return {
            "unity_id": unity_id,
            "seeded": info is not None,
            "seed": dict(info) if info is not None else None,
            "provenance": "DERIVED",
        }

    def register_identity(self, unity_id: str, pubkey_der_b64: str) -> None:
        """Pre-register a counterparty's public key (needed to verify the
        tier grants THEY sign). Read-only w.r.t. value: no receipt."""
        if unity_id not in self._wallets:
            raise UnknownWallet(f"no wallet for {unity_id!r} in this ledger")
        base64.b64decode(pubkey_der_b64)  # validates
        self._wallets[unity_id]["owner_pubkey_b64"] = pubkey_der_b64
        self._save()

    def _pubkey_of(self, unity_id: str) -> bytes:
        try:
            return base64.b64decode(
                self._wallets[unity_id]["owner_pubkey_b64"])
        except KeyError:
            raise UnknownWallet(f"no wallet for {unity_id!r} in this ledger")

    # -- tiers ------------------------------------------------------------
    def tier_of(self, granter_id: str, grantee_id: str):
        """Latest tier the granter (human) set for the grantee, or None."""
        tier = None
        for g in self._grants:
            if (g["granter_unity_id"] == granter_id
                    and g["grantee_unity_id"] == grantee_id):
                tier = g["tier"]
        return tier

    def is_kin(self, unity_a: str, unity_b: str) -> bool:
        pair = sorted([unity_a, unity_b])
        return any(k["pair"] == pair for k in self._kin)

    # -- internal Unity inflow (fuse genesis only; see fuse.py) ------------
    def _issue_genesis_ticket(self, fuse, authorization: dict
                              ) -> _FuseGenesisTicket:
        """Issue the one-shot mint capability for a lawful fuse trigger.

        Structural gate: only a Fuse mid-trigger on THIS ledger can hold
        a ticket. TRIGGERED is entered only inside Fuse.trigger_fuse,
        after David's signed authorization verified (fuse.py) — there is
        no other path to this state. One launch per ledger: the first
        fuse to issue a ticket owns the launch; the durable record is the
        kind=fuse-genesis receipt in the applied registry, so a reloaded
        ledger cannot be re-launched either.
        """
        from fuse import Fuse as _Fuse  # lazy: fuse.py imports wallet at top
        if not isinstance(fuse, _Fuse) or \
                getattr(fuse, "_ledger", None) is not self:
            raise WalletError(
                "genesis ticket refused: not a Fuse bound to this ledger")
        if fuse.status() != "TRIGGERED":
            raise WalletError(
                "genesis ticket refused: fuse is not mid-trigger "
                f"(state={fuse.status()}) — the launch authorization "
                "check did not run")
        for receipt in self._applied.values():
            if isinstance(receipt, dict) and \
                    receipt.get("kind") == "fuse-genesis":
                raise WalletError(
                    "genesis ticket refused: this ledger already recorded "
                    "its fuse genesis — the launch happened exactly once")
        if self._genesis_fuse is not None and self._genesis_fuse is not fuse:
            raise WalletError(
                "genesis ticket refused: this ledger's launch belongs to "
                "another fuse")
        self._genesis_fuse = fuse
        body = {k: authorization.get(k) for k in
                ("founder_unity_id", "genesis_unity_amount", "nonce")}
        manifest_hash = _sha256_hex(
            _canonical_bytes({"fuse": "genesis", **body}))
        return _FuseGenesisTicket(fuse, authorization, manifest_hash)

    def _apply_fuse_genesis(self, unity_id: str, amount: int,
                            receipt_body: dict, manifest_hash: str,
                            ticket=None) -> dict:
        """Credit genesis Unity. GATED (CRITICAL-3 closure): requires the
        one-shot fuse ticket issued by _issue_genesis_ticket inside
        Fuse.trigger_fuse, mid lawful trigger. No valid ticket — no mint.
        A spent fuse, a foreign fuse, a forged or replayed ticket, or
        parameters that do not match the signed authorization are all
        refused before any balance moves."""
        _require_genesis_ticket(self, unity_id, amount, manifest_hash,
                                ticket)
        if self._wallets[unity_id]["Unity"] != 0:
            raise WalletError(
                "fuse genesis refused: wallet already holds Unity")

        def mutate():
            r = self._wallets[unity_id]
            receipt_body["before"] = r["Unity"]
            r["Unity"] += amount
            receipt_body["after"] = r["Unity"]

        body = dict(receipt_body)
        body.update({
            "kind": "fuse-genesis",
            "unity_id": unity_id,
            "token": TOKEN_UNITY,
            "amount": amount,
        })
        return self._apply(manifest_hash, mutate, body)


# ---------------------------------------------------------------------------
# Wallet — the handle
# ---------------------------------------------------------------------------
_default_ledger = None


def _get_default_ledger() -> Ledger:
    global _default_ledger
    if _default_ledger is None:
        _default_ledger = Ledger()
    return _get_default_ledger


class Wallet:
    """A UnityID wallet: prepaid bank, Unity-bound, receipt-logged.

    Wallet(unity_id) attaches to the shared default ledger; pass an
    explicit Ledger for isolated/test state.
    """

    def __init__(self, unity_id: str, ledger: Ledger | None = None):
        self._unity_id = unity_id
        self._ledger = ledger if ledger is not None else _get_default_ledger()

    @property
    def unity_id(self) -> str:
        return self._unity_id

    @property
    def ledger(self) -> Ledger:
        return self._ledger

    # -- §1 shareable identity: the QR's digital twin ----------------------
    def share_code(self) -> str:
        """The click-to-copy code: plain text, sendable anywhere. The Unity
        ID itself is the code — nothing to photograph."""
        return self._unity_id

    def qr_payload(self) -> dict:
        """The digital twin of the QR image: the EXACT payload a QR would
        encode, as text. Same identity as share_code(), twin of the image."""
        return {
            "format": "unity-id-qr/v1",
            "kind": "unity-id",
            "unity_id": self._unity_id,
            "share_code": self.share_code(),
        }

    @staticmethod
    def from_share_code(code: str, ledger: Ledger | None = None) -> "Wallet":
        """Rebuild the handle from a copied code. The code names a wallet;
        the wallet must exist in the ledger (UNKNOWN never PASS)."""
        code = code.strip()
        led = ledger if ledger is not None else _get_default_ledger()
        return led.wallet(code)

    # -- balances: honest, receipt-log derived -----------------------------
    def balances(self) -> dict:
        """{"eFuse": {"amount", "provenance"}, "Unity": {...}}.

        Provenance is VERIFIED: the amount is the sum over the receipt log,
        and a fresh wallet's log is empty — zero by construction, not by
        assertion.
        """
        raw = self._ledger._wallets[self._unity_id]
        return {
            TOKEN_EFUSE: {"amount": raw["eFuse"], "provenance": "VERIFIED"},
            TOKEN_UNITY: {"amount": raw["Unity"], "provenance": "VERIFIED"},
        }

    def honor_ledger(self) -> list:
        """Honor accruals for this Unity ID (public, permanent, named)."""
        return [h for h in self._ledger._honor
                if h["unity_id"] == self._unity_id]

    def donated_total(self) -> int:
        return sum(d["amount"] for d in self._ledger._donations
                   if d["donor_unity_id"] == self._unity_id)

    def donation_hashes(self) -> set:
        """manifest_hashes of this wallet's donations — the donor-exclusion
        set: these amounts never come back to this donor."""
        return {d["manifest_hash"] for d in self._ledger._donations
                if d["donor_unity_id"] == self._unity_id}

    def donation_amounts(self) -> set:
        """Per-donation amounts by this wallet — the amount leg of donor
        exclusion: a Lock-sourced inbound for exactly a donated amount is
        the donor's own value returning."""
        return {d["amount"] for d in self._ledger._donations
                if d["donor_unity_id"] == self._unity_id}

    def membership(self) -> dict:
        """The one-seed membership state for this wallet (read-only).

        David's law, 2026-10-06: "no matter how much money you have you
        only buy one seed, and it costs you nothing." The seed is
        MEMBERSHIP — the genesis entry — never a balance, never priced,
        never spendable. Returns {"unity_id", "seeded", "seed",
        "provenance"}; the seed entry is the seeder's record mirrored
        here, not wealth. balances() is untouched by the seed."""
        return self._ledger.seed_membership(self._unity_id)

    # -- dead-simple Merit send / receive ----------------------------------
    def send_merit(self, to_id, amount, reason: str = "gift",
                   signer=None, engine=None,
                   manifest: dict | None = None) -> dict:
        """Send Merit to another Unity ID. The dead-simple interface:

            wallet.send_merit(recipient_id, 25, "gift", signer=my_signer)

        Delegates to the module-level transfer_merit, which delegates to
        the canonical dclm/token_engine.py Tokenizer.merit_transfer — the
        SOLE legal Merit transfer path. No second path exists in this
        module.

        `signer` is the sender's signing capability: a callable taking
        (from_id, to_id, amount, reason) and returning the sender-signed
        transfer authorization (see make_merit_transfer_auth). The
        sender's device/biometric key signs; DCLM only verifies. No
        passwords, no key management in the wallet — the signer is the
        human's own capability. Required: unsigned sends are refused.

        `engine` is REQUIRED (a dclm Tokenizer) — the wallet delegates;
        it never moves Merit itself. Every send is receipted with
        before/after owned balances on both sides; origin never moves
        (standing unchanged — the buyer gains value, zero standing).
        """
        to_id = to_id.unity_id if isinstance(to_id, Wallet) else str(to_id)
        if signer is None or not callable(signer):
            raise WalletError(
                "send_merit needs the sender's signer — a callable "
                "(from_id, to_id, amount, reason) -> signed transfer "
                "authorization (see make_merit_transfer_auth). The "
                "sender's device signs; DCLM only verifies. Unsigned "
                "sends are refused.")
        # The engine verifies the signature against the STRIPPED reason:
        # sign exactly what the engine will check, never a variant.
        reason = reason.strip() if isinstance(reason, str) else reason
        auth = signer(self._unity_id, to_id, amount, reason)
        return transfer_merit(self, to_id, amount, reason,
                              engine=engine, manifest=manifest, auth=auth)

    def receive_merit(self) -> list:
        """What arrived for me: the wallet's receipted view of inbound
        Merit transfers. Read-only — no mutation, no receipt minted.

        Merit moves by sender push; receiving is the acknowledgment:
        this returns every receipted merit-transfer naming this wallet
        as the recipient, in chain order. Each receipt shows the owned
        value that arrived; origin is never carried by the wallet —
        earned history stays with the earner, standing never moves.

        A human or bot reads this without thinking: what's mine, and
        from where (the sender's Unity ID is on the receipt)."""
        out = []
        for entry in self._ledger._chain.entries():
            receipt = entry.get("receipt", {})
            if (receipt.get("kind") == "merit-transfer"
                    and receipt.get("to") == self._unity_id):
                out.append(dict(receipt))
        return out


# ---------------------------------------------------------------------------
# tier grants — set by the human, enforced cryptographically
# ---------------------------------------------------------------------------
def make_tier_grant(granter_privkey_der: bytes, granter_unity_id: str,
                    grantee_unity_id: str, tier: str,
                    nonce: str | None = None) -> dict:
    """The human's device signs a tier grant. DCLM never sees the private
    key — it only verifies (apply_tier_grant)."""
    if tier not in TIERS:
        raise TierViolation(f"unknown tier {tier!r}")
    body = {
        "granter_unity_id": granter_unity_id,
        "grantee_unity_id": grantee_unity_id,
        "tier": tier,
        "nonce": nonce or uuid.uuid4().hex,
    }
    sig = _node_sign(granter_privkey_der, _canonical_bytes(body))
    return {**body, "signature": sig, "key_id": KEY_ID}


def make_merit_transfer_auth(sender_privkey_der: bytes,
                             sender_pubkey_der: bytes,
                             from_id: str, to_id: str, amount,
                             reason: str, nonce: str | None = None) -> dict:
    """The sender's device signs a Merit transfer authorization. DCLM
    never sees the private key — it only verifies (transfer_merit /
    Tokenizer.merit_transfer).

    The signed body is the canonical transfer intent:
      {"op": "merit-transfer", "from": from_id, "to": to_id,
       "amount": float(amount), "reason": reason.strip(), "nonce": nonce}
    The signature binds EXACTLY what will move — a different amount,
    recipient, reason, or nonce fails verification. The nonce is
    single-use: replaying an authorization is refused.

    Returns the auth dict the engine requires: the body plus
    "signature" (b64), "pubkey_b64" (the sender's DER pubkey, b64 —
    the engine checks sha256(pubkey) == the sender's Unity ID suffix),
    and "key_id". Testnet keys only.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise WalletError("transfer authorization needs a non-empty reason")
    body = {
        "op": "merit-transfer",
        "from": from_id,
        "to": to_id,
        "amount": float(amount),
        "reason": reason.strip(),
        "nonce": nonce or uuid.uuid4().hex,
    }
    sig = _node_sign(sender_privkey_der, _canonical_bytes(body))
    return {**body,
            "signature": sig,
            "pubkey_b64": base64.b64encode(sender_pubkey_der).decode(),
            "key_id": KEY_ID}


def apply_tier_grant(ledger: Ledger, grant: dict) -> dict:
    """Verify a signed tier grant and record it. Every check is code:

    - tier is a known tier
    - both IDs name wallets in this ledger (UNKNOWN never PASS)
    - the Ed25519 signature verifies against the granter's registered key
    - family tier additionally requires a kin bond (kin is binding, §5)
    """
    body = {k: grant.get(k) for k in
            ("granter_unity_id", "grantee_unity_id", "tier", "nonce")}
    granter, grantee, tier = (body["granter_unity_id"],
                             body["grantee_unity_id"], body["tier"])
    if tier not in TIERS:
        raise TierViolation(f"unknown tier {tier!r}")
    if not granter or not grantee:
        raise TierViolation("tier grant names no IDs — refused")
    pubkey = ledger._pubkey_of(granter)  # raises UnknownWallet
    ledger._pubkey_of(grantee)
    if not grant.get("signature") or not _node_verify(
            pubkey, _canonical_bytes(body), grant["signature"]):
        raise TierViolation("tier grant signature FAILED — refused")
    if tier == TIER_FAMILY and not ledger.is_kin(granter, grantee):
        raise TierViolation(
            "family tier requires a kin bond — kin is binding (§5)")
    manifest = _manifest_hash({"op": "tier_grant", **body,
                              "sig": grant["signature"]})

    def mutate():
        ledger._grants.append({**body, "signature": grant["signature"]})

    receipt = {
        "kind": "tier_grant",
        "granter_unity_id": granter,
        "grantee_unity_id": grantee,
        "tier": tier,
        "provenance": "VERIFIED",  # signature verified in-process
    }
    return ledger._apply(manifest, mutate, receipt)


def bind_kin(ledger: Ledger, unity_a: str, unity_b: str, proof: dict) -> dict:
    """Record a kin bond: BOTH parties sign the pairing.

    proof = {"nonce": str, "sig_a": b64, "sig_b": b64} over
    canonical({"kin": [a, b] sorted, "nonce": nonce}).
    Deeper kin mechanism: TBD (KIN_MECHANISM_TBD) — this records the
    principle as mutual cryptographic consent.
    """
    if unity_a == unity_b:
        raise WalletError("cannot kin-bind an ID to itself")
    pair = sorted([unity_a, unity_b])
    nonce = proof.get("nonce")
    if not nonce:
        raise WalletError("kin proof needs a nonce")
    msg = _canonical_bytes({"kin": pair, "nonce": nonce})
    key_a = ledger._pubkey_of(pair[0])
    key_b = ledger._pubkey_of(pair[1])
    if not _node_verify(key_a, msg, proof.get("sig_a", "")):
        raise WalletError(f"kin proof signature FAILED for {pair[0]}")
    if not _node_verify(key_b, msg, proof.get("sig_b", "")):
        raise WalletError(f"kin proof signature FAILED for {pair[1]}")
    manifest = _manifest_hash({"op": "kin_bind", "pair": pair, "nonce": nonce})

    def mutate():
        if not ledger.is_kin(pair[0], pair[1]):
            ledger._kin.append({"pair": pair, "nonce": nonce})

    receipt = {
        "kind": "kin_bind",
        "pair": pair,
        "mechanism": "mutual-signature",
        "mechanism_tbd": KIN_MECHANISM_TBD,
        "provenance": "VERIFIED",
    }
    return ledger._apply(manifest, mutate, receipt)


def connect(ledger: Ledger, unity_a: str, unity_b: str) -> dict:
    """§2 — the easiest connector: two accounts link trivially.

    Read-only (no value moves): returns both share codes so either side can
    copy/paste or QR-twin the other. Both IDs must name wallets.
    """
    wa, wb = ledger.wallet(unity_a), ledger.wallet(unity_b)
    return {
        "connected": True,
        "a": wa.qr_payload(),
        "b": wb.qr_payload(),
        "provenance": "VERIFIED",
    }


# ---------------------------------------------------------------------------
# share — money AND information on the same rails (§4), tier-gated
# ---------------------------------------------------------------------------
def _resolve_recipient(ledger: Ledger, recipient) -> Wallet:
    if isinstance(recipient, Wallet):
        return recipient
    return ledger.wallet(str(recipient))  # raises UnknownWallet


def share(sender: Wallet, recipient, payload: dict,
          manifest: dict | None = None) -> dict:
    """One rail, two content types (§4).

    payload = {"kind": "funds", "amount": int}            # eFuse money
            | {"kind": "info", "content_type": str,
               "content_hash": str}                       # information

    Gates, in order — all code, no policy promises:
      1. recipient names a real wallet (UNKNOWN never PASS)
      2. the sender granted the recipient a tier (signed grant on file)
      3. the payload fits that tier's limits (TIER_LIMITS — MODELED/HELD)
      4. funds: Unity tokens refuse (binding law); eFuse balance covers it
    Both sides are receipted under ONE manifest_hash (both-side receipting);
    a retry with the same manifest returns the original receipt.
    """
    ledger = sender.ledger
    to_wallet = _resolve_recipient(ledger, recipient)
    kind = payload.get("kind")

    # Donor-exclusion gate — FIRST on this rail too: the recipient's own
    # donated value may never return to them, whatever the rail. Info
    # shares carry no value and are not gated.
    if kind == "funds":
        check_donor_exclusion(to_wallet, {
            "source_donation_hash": payload.get("source_donation_hash"),
            "source": payload.get("source"),
            "lock_address": payload.get("lock_address"),
            "kind": "share",
            "amount": payload.get("amount"),
        })

    tier = ledger.tier_of(sender.unity_id, to_wallet.unity_id)
    if tier is None:
        raise TierViolation(
            f"no tier granted from {sender.unity_id} to "
            f"{to_wallet.unity_id} — sharing refused")
    limits = TIER_LIMITS[tier]
    epoch = (manifest or {}).get("epoch") or _utc_now()[:10]

    # A caller-supplied manifest is the idempotency key VERBATIM — no nonce
    # is added, so a retry with the same manifest is a no-op. With no
    # caller manifest at all, a fresh nonce makes the call a distinct
    # intent (the metering layer supplies manifests for real retries).
    if manifest is None:
        manifest = {"op": "share", "nonce": uuid.uuid4().hex}
    else:
        manifest = dict(manifest)
        manifest.setdefault("op", "share")

    if kind == "funds":
        token = payload.get("token", TOKEN_EFUSE)
        if token == TOKEN_UNITY:
            raise UnityBindingError(
                "Unity tokens are bound to their Unity ID — not transferable")
        if token != TOKEN_EFUSE:
            raise WalletError(f"unknown token {token!r}")
        amount = payload.get("amount")
        if not isinstance(amount, int) or amount <= 0:
            raise WalletError("share amount must be a positive integer")
        cap = limits["efuse_per_share"]
        if cap is not None and amount > cap:
            raise TierViolation(
                f"{tier} tier caps a single share at {cap} eFuse")
        count_cap = limits["shares_per_epoch"]
        ckey = (sender.unity_id, to_wallet.unity_id, epoch, "funds")
        if (count_cap is not None
                and ledger._counters.get(ckey, 0) >= count_cap):
            raise TierViolation(
                f"{tier} tier caps shares at {count_cap} per epoch")
        sender_raw = ledger._wallets[sender.unity_id]
        if sender_raw["eFuse"] < amount:
            raise InsufficientFunds(
                f"{sender.unity_id} holds {sender_raw['eFuse']} eFuse, "
                f"share needs {amount}")
        mhash = _manifest_hash({**manifest, "from": sender.unity_id,
                                "to": to_wallet.unity_id,
                                "payload": payload})
        receipt = {
            "kind": "share",
            "content_kind": "funds",
            "from": sender.unity_id,
            "to": to_wallet.unity_id,
            "tier": tier,
            "epoch": epoch,
            "sides": None,  # filled by mutate()
            "provenance": "VERIFIED",
        }

        def mutate():
            s = ledger._wallets[sender.unity_id]
            r = ledger._wallets[to_wallet.unity_id]
            s_before, r_before = s["eFuse"], r["eFuse"]
            s["eFuse"] -= amount
            r["eFuse"] += amount
            ledger._counters[ckey] = ledger._counters.get(ckey, 0) + 1
            receipt["sides"] = {
                "debit": {"unity_id": sender.unity_id, "token": TOKEN_EFUSE,
                          "amount": amount, "before": s_before,
                          "after": s["eFuse"]},
                "credit": {"unity_id": to_wallet.unity_id,
                           "token": TOKEN_EFUSE, "amount": amount,
                           "before": r_before, "after": r["eFuse"]},
            }

        return ledger._apply(mhash, mutate, receipt)

    if kind == "info":
        content_type = payload.get("content_type")
        content_hash = payload.get("content_hash")
        if not content_type or not content_hash:
            raise WalletError("info share needs content_type + content_hash")
        count_cap = limits["info_events_per_epoch"]
        ckey = (sender.unity_id, to_wallet.unity_id, epoch, "info")
        if (count_cap is not None
                and ledger._counters.get(ckey, 0) >= count_cap):
            raise TierViolation(
                f"{tier} tier caps info events at {count_cap} per epoch")
        mhash = _manifest_hash({**manifest, "from": sender.unity_id,
                                "to": to_wallet.unity_id,
                                "payload": payload})
        receipt = {
            "kind": "share",
            "content_kind": "info",
            "from": sender.unity_id,
            "to": to_wallet.unity_id,
            "tier": tier,
            "epoch": epoch,
            "content_type": content_type,
            "content_hash": content_hash,  # the hash binds the event; the
            # bytes stay with the humans — DCLM carries the claim, not the
            # content.
            "provenance": "VERIFIED",
        }

        def mutate_info():
            ledger._counters[ckey] = ledger._counters.get(ckey, 0) + 1

        return ledger._apply(mhash, mutate_info, receipt)

    raise WalletError(f"unknown share payload kind {kind!r}")


# ---------------------------------------------------------------------------
# deduct_per_decision — pay by actual compute
# ---------------------------------------------------------------------------
def deduct_per_decision(wallet: Wallet, price, manifest: dict | None = None):
    """Deduct the per-decision price from the wallet's eFuse balance.

    Every deduction is receipted with a manifest_hash. Idempotent: the same
    manifest never deducts twice — a retry returns the original receipt.
    Without a caller manifest, a fresh nonce makes each call a distinct
    intent (the metering layer supplies the manifest for real retries).
    Refusals (insufficient funds, bad price) record NOTHING — a retry after
    funding with the same manifest still works. UNKNOWN never PASS.
    """
    if not isinstance(price, int) or price <= 0:
        raise WalletError("price must be a positive integer (minor units)")
    ledger = wallet.ledger
    if manifest is None:
        manifest = {"op": "deduct_per_decision", "nonce": uuid.uuid4().hex}
    else:
        manifest = dict(manifest)
        manifest.setdefault("op", "deduct_per_decision")
    mhash = _manifest_hash({**manifest, "unity_id": wallet.unity_id,
                            "price": price, "token": TOKEN_EFUSE})
    raw = ledger._wallets[wallet.unity_id]
    if raw["eFuse"] < price:
        raise InsufficientFunds(
            f"{wallet.unity_id} holds {raw['eFuse']} eFuse, "
            f"decision costs {price} — refused, nothing recorded")
    receipt = {
        "kind": "deduct_per_decision",
        "unity_id": wallet.unity_id,
        "token": TOKEN_EFUSE,
        "price": price,
        "decision_id": manifest.get("decision_id"),
        "before": None,  # filled by mutate()
        "after": None,
        "provenance": "VERIFIED",
    }

    def mutate():
        r = ledger._wallets[wallet.unity_id]
        receipt["before"] = r["eFuse"]
        r["eFuse"] -= price
        receipt["after"] = r["eFuse"]

    return ledger._apply(mhash, mutate, receipt)


# ---------------------------------------------------------------------------
# receive_emission — merit-gated eFuse in, against a gated receipt
# ---------------------------------------------------------------------------
def _validate_emission_receipt(wallet: Wallet, amount: int, receipt: dict,
                               token: str) -> dict:
    """The receipt IS the gate. Every field is checked; anything off is
    refused outright — no partial credit, no silent accept.

    CRITICAL-4: the receipt must also carry the emission authority's
    Ed25519 signature over its canonical body. No signature -> refused.
    Bad signature -> refused. Tampered body -> signature fails -> refused.
    A structurally-valid forged receipt credits NOTHING."""
    if not isinstance(receipt, dict):
        raise InvalidReceipt("emission receipt must be a dict")
    problems = []
    if receipt.get("kind") != "merit-emission":
        problems.append(f"kind must be 'merit-emission', got "
                        f"{receipt.get('kind')!r}")
    if receipt.get("token") != token:
        problems.append(f"token must be {token!r}, got "
                        f"{receipt.get('token')!r}")
    if receipt.get("unity_id") != wallet.unity_id:
        problems.append("receipt unity_id does not match wallet")
    if receipt.get("amount") != amount:
        problems.append("receipt amount does not match credited amount")
    if not isinstance(amount, int) or amount <= 0:
        problems.append("amount must be a positive integer")
    if receipt.get("gated") is not True:
        problems.append("receipt is not gated (gated=true required)")
    if receipt.get("pool") not in ("human", "machine"):
        problems.append("pool must be 'human' or 'machine'")
    if "merit_weight" not in receipt:
        problems.append("receipt carries no merit_weight")
    if not receipt.get("manifest_hash"):
        problems.append("receipt carries no manifest_hash")
    if not receipt.get("epoch"):
        problems.append("receipt carries no epoch")
    # Cryptographic binding to the lawful emitter (CRITICAL-4).
    ledger = wallet.ledger
    if not receipt.get("emitter_signature"):
        problems.append("emission receipt carries no emitter signature — "
                        "only the emission authority can issue emission")
    elif not emission_receipt_signature_valid(
            receipt, ledger.emission_authority_pubkey_der,
            ledger.emission_authority_key_id):
        problems.append("emission receipt's emitter signature FAILED — "
                        "not issued by the emission authority")
    if problems:
        raise InvalidReceipt("emission receipt refused: "
                             + "; ".join(problems))
    return receipt


def _credit_token(wallet: Wallet, amount: int, receipt: dict, token: str,
                  kind: str) -> dict:
    ledger = wallet.ledger
    mhash = receipt["manifest_hash"]
    if not ledger.manifest_applied(mhash):
        # Donor-exclusion gate — FIRST, before any mutation. (An
        # idempotent replay of an already-applied receipt returns the
        # original without re-gating; a refused attempt records nothing,
        # so it re-gates on retry.)
        check_donor_exclusion(wallet, {
            "source_donation_hash": receipt.get("source_donation_hash"),
            "source": receipt.get("source"),
            "lock_address": receipt.get("lock_address"),
            "kind": receipt.get("kind"),
            "amount": amount,
        })
    applied = {
        "kind": kind,
        "unity_id": wallet.unity_id,
        "token": token,
        "amount": amount,
        "pool": receipt["pool"],
        "epoch": receipt["epoch"],
        "before": None,  # filled by mutate()
        "after": None,
        "inbound_receipt_provenance": receipt.get("provenance", "UNKNOWN"),
        "provenance": "VERIFIED",  # application computed in-process
    }

    def mutate():
        r = ledger._wallets[wallet.unity_id]
        applied["before"] = r[token]
        r[token] += amount
        applied["after"] = r[token]

    return ledger._apply(mhash, mutate, applied)


def receive_emission(wallet: Wallet, amount: int, receipt: dict) -> dict:
    """Receive merit-gated eFuse emission against a gated receipt.

    The receipt must carry the emission authority's Ed25519 signature
    over its canonical body (see sign_emission_receipt) — unsigned,
    mis-signed, or tampered receipts are refused outright (CRITICAL-4).

    Idempotent on the receipt's manifest_hash — the same gated receipt
    never credits twice.
    """
    _validate_emission_receipt(wallet, amount, receipt, TOKEN_EFUSE)
    return _credit_token(wallet, amount, receipt, TOKEN_EFUSE, "emission")


def receive_unity_emission(wallet: Wallet, amount: int, receipt: dict) -> dict:
    """Receive Unity against a MERIT-GATED receipt (the tokenomics engine).

    The fuse's genesis allocation does NOT come through here — it goes
    through Ledger._apply_fuse_genesis, which requires the one-shot fuse
    ticket issued only inside Fuse.trigger_fuse, mid lawful trigger
    (CRITICAL-3 gate: no ticket, no mint). So Unity enters circulation
    through exactly two code paths: the fuse at launch, then merit-gated
    emission. No other mint path exists in this module (asserted by test).
    """
    _validate_emission_receipt(wallet, amount, receipt, TOKEN_UNITY)
    return _credit_token(wallet, amount, receipt, TOKEN_UNITY,
                         "unity-emission")


# ---------------------------------------------------------------------------
# receive_cause_disbursement — the Lock's disbursement, applied to a wallet
# ---------------------------------------------------------------------------
def receive_cause_disbursement(wallet: Wallet, amount: int,
                               disbursement: dict) -> dict:
    """Apply a Core Cause Lock disbursement to the wallet — the wallet-side
    disbursement application for tokenomics cause_disburse records.

    disbursement = {"kind": "cause-disbursement", "unity_id", "amount",
                    "manifest_hash", "lock_address", "epoch",
                    "source_donation_hash" (optional), "provenance"} —
    the pipeline translates the tokenomics cause_disbursement receipt
    into this record; the wallet never invents one.

    Gates, in order:
      1. the record is structurally valid (UNKNOWN never PASS)
      2. the record carries the emission authority's Ed25519 signature
         over its canonical body (CRITICAL-4) — the tokenomics Ledger
         signs every cause_disbursement it issues; the pipeline's
         translation of that receipt into this record MUST preserve the
         emitter_signature / emitter_key_id envelope. Unsigned,
         mis-signed, or tampered records are refused outright.
      3. check_donor_exclusion FIRST: a disbursement tracing to the
         recipient's own Lock donation (same amount/source) is REFUSED —
         never credited, nothing recorded
    Idempotent on the disbursement's manifest_hash — the same Lock
    disbursement never credits twice. The tokenomics layer's own blanket
    ban (cause_disburse refuses ANY donor) is the first line; this is the
    wallet's structural backstop for any disbursement record that reaches
    it on any path.
    """
    if not isinstance(disbursement, dict):
        raise InvalidReceipt("cause disbursement must be a dict")
    ledger = wallet.ledger
    problems = []
    if disbursement.get("kind") != "cause-disbursement":
        problems.append(f"kind must be 'cause-disbursement', got "
                        f"{disbursement.get('kind')!r}")
    if disbursement.get("unity_id") != wallet.unity_id:
        problems.append("disbursement unity_id does not match wallet")
    if disbursement.get("amount") != amount:
        problems.append("disbursement amount does not match credited amount")
    if not isinstance(amount, int) or amount <= 0:
        problems.append("amount must be a positive integer")
    if not disbursement.get("manifest_hash"):
        problems.append("disbursement carries no manifest_hash")
    if not disbursement.get("lock_address"):
        problems.append("disbursement names no lock_address — "
                        "UNKNOWN never PASS")
    # Cryptographic binding to the lawful issuer (CRITICAL-4): a
    # structurally-valid forged Lock disbursement credits NOTHING.
    if not disbursement.get("emitter_signature"):
        problems.append("cause disbursement carries no emitter signature — "
                        "only the emission authority can authorize Lock "
                        "disbursements")
    elif not emission_receipt_signature_valid(
            disbursement, ledger.emission_authority_pubkey_der,
            ledger.emission_authority_key_id):
        problems.append("cause disbursement's emitter signature FAILED — "
                        "not issued by the emission authority")
    if problems:
        raise InvalidReceipt("cause disbursement refused: "
                             + "; ".join(problems))
    mhash = disbursement["manifest_hash"]
    if not ledger.manifest_applied(mhash):
        # Donor-exclusion gate — FIRST, before any mutation. (An
        # idempotent replay of an already-applied disbursement returns
        # the original without re-gating; a refused attempt records
        # nothing, so it re-gates on retry.)
        check_donor_exclusion(wallet, disbursement)
    receipt = dict(disbursement)
    receipt["pool"] = "cause-lock"  # the Lock is not a pool; the credit
    # core records pool/epoch on every application — this names the true
    # source.
    receipt.setdefault("epoch", _utc_now()[:10])
    return _credit_token(wallet, amount, receipt, TOKEN_EFUSE,
                         "cause-disbursement")


# ---------------------------------------------------------------------------
# donate — one-way to the Core Cause Lock; Honor, never Merit
# ---------------------------------------------------------------------------
def donate(wallet: Wallet, amount: int, lock_address: str,
           manifest: dict | None = None) -> dict:
    """Donate eFuse to the Core Cause Lock (F4).

    One-way: no function in this module returns donated eFuse to the donor.
    The receipt accrues HONOR (public, named, permanent, non-transferable)
    and explicitly accrues ZERO merit — the brightest line in the
    tokenomics (§7): there is no path from donation to emission.
    Donor exclusion: the donation's manifest_hash joins the wallet's
    exclusion set — that amount is never re-emitted to this donor
    (check_donor_exclusion enforces it on the disbursement path).
    """
    if not isinstance(amount, int) or amount <= 0:
        raise WalletError("donation amount must be a positive integer")
    if not lock_address or not isinstance(lock_address, str):
        raise WalletError("a real lock address is required — "
                          "UNKNOWN never PASS")
    ledger = wallet.ledger
    raw = ledger._wallets[wallet.unity_id]
    if raw["eFuse"] < amount:
        raise InsufficientFunds(
            f"{wallet.unity_id} holds {raw['eFuse']} eFuse, cannot donate "
            f"{amount}")
    if manifest is None:
        manifest = {"op": "donate", "nonce": uuid.uuid4().hex}
    else:
        manifest = dict(manifest)
        manifest.setdefault("op", "donate")
    mhash = _manifest_hash({**manifest, "donor": wallet.unity_id,
                            "amount": amount, "lock": lock_address})
    receipt = {
        "kind": "donation",
        "donor_unity_id": wallet.unity_id,
        "token": TOKEN_EFUSE,
        "amount": amount,
        "lock_address": lock_address,
        "before": None,  # filled by mutate()
        "after": None,
        "honor": {
            "class": HONOR_CLASS_UNNAMED,
            "amount": amount,
            "permanent": True,
            "transferable": False,
            "provenance": "REPORTED",
        },
        "merit_accrued": 0,  # the bright line, in the receipt itself
        "donor_exclusion": {
            "donor_unity_id": wallet.unity_id,
            "lock_address": lock_address,
            "amount": amount,
            "manifest_hash": mhash,
            "rule": "this amount is never re-emitted to this donor",
        },
        "provenance": "VERIFIED",
    }

    def mutate():
        r = ledger._wallets[wallet.unity_id]
        receipt["before"] = r["eFuse"]
        r["eFuse"] -= amount
        receipt["after"] = r["eFuse"]
        ledger._donations.append({
            "donor_unity_id": wallet.unity_id,
            "amount": amount,
            "lock_address": lock_address,
            "manifest_hash": mhash,
        })
        ledger._honor.append({
            "unity_id": wallet.unity_id,
            "kind": "donation",
            "amount": amount,
            "honor_class": HONOR_CLASS_UNNAMED,
            "permanent": True,
            "transferable": False,
            "donation_manifest_hash": mhash,
            "provenance": "REPORTED",  # the donation happened; we carry it
        })

    return ledger._apply(mhash, mutate, receipt)


def _token_engine():
    """Lazy import of the DCLM tokenization engine (../dclm/).

    The wallet never mints and never computes token amounts — the Merit
    transfer path below DELEGATES to the engine's sole legal transfer
    function. The wallet records the ownership change; origin stays in
    the engine.
    """
    dclm_dir = os.path.join(_HERE, "..", "dclm")
    if dclm_dir not in sys.path:
        sys.path.insert(0, dclm_dir)
    import token_engine
    return token_engine


def transfer_merit(sender: Wallet, recipient, amount, reason: str,
                   engine=None, manifest: dict | None = None,
                   auth: dict | None = None) -> dict:
    """Move owned Merit from sender to recipient — through the token engine.

    David's word, 2026-10-06 ~3:35 AM EDT: Merit IS transferable (sold,
    gifted, transferred between Unity IDs — all receipted). This is the
    wallet's transfer path, and it DELEGATES: the actual ownership change
    happens in dclm/token_engine.py Tokenizer.merit_transfer — the SOLE
    legal Merit transfer path — via a signed MERIT_TRANSFER commit.

    SENDER AUTHORIZATION (David's closure, 2026-10-06 — CRITICAL-1): the
    transfer must carry the sender's signed transfer authorization
    (see make_merit_transfer_auth — the sender's device signs; DCLM
    only verifies). No auth -> WalletError here; a forged or replayed
    auth -> TokenizeRefused from the engine. The public Unity ID alone
    authorizes nothing — a fresh Wallet handle for the victim's ID
    cannot move the victim's Merit.

    What the wallet records: the OWNERSHIP change (who holds what now,
    before/after owned balances on both sides, the engine's transfer id).
    What the wallet NEVER carries: origin fields (origin_earner_id,
    origin_receipt_ref). Origin stays in the engine; standing never moves;
    a buyer gains economic value and zero standing — by construction.

    Gates, in order:
      1. recipient names a real wallet on this ledger (UNKNOWN never PASS)
      2. a sender-signed transfer authorization is present (else refused)
      3. both IDs are verified testnet Unity IDs (engine enforces)
      4. amount is a positive number; reason is a non-empty string
         ("sale", "gift", … — receipted, never empty)
      5. the authorization verifies (engine enforces: right key, valid
         signature, fresh nonce)
      6. the sender's OWNED balance covers the amount (engine enforces)
    Idempotent on the caller manifest: with no caller manifest, a fresh
    nonce makes the call a distinct intent (same convention as share()).
    A retry with the same manifest AND the same authorization returns
    the original wallet receipt WITHOUT calling the engine again. The
    authorization nonce is part of the intent hash: a different auth is
    a different intent, and a replayed auth is refused by the engine.

    engine defaults to None and is REQUIRED — pass the Tokenizer whose
    ledger holds the sender's Merit. (A fresh engine holds nothing; the
    transfer would refuse honestly.) TokenizeRefused propagates unwrapped:
    the engine's structural refusal carries the true reason.
    """
    ledger = sender.ledger
    to_wallet = _resolve_recipient(ledger, recipient)
    if engine is None:
        raise WalletError(
            "transfer_merit needs the token engine (a dclm Tokenizer) — "
            "the wallet delegates; it never moves Merit itself")
    if not hasattr(engine, "merit_transfer") or \
            not callable(engine.merit_transfer):
        raise WalletError("engine has no merit_transfer — refusing")
    # Gate 2 — the sender authorized this. The wallet checks presence;
    # the engine checks the cryptography (key binding, signature,
    # nonce freshness). Unsigned transfers never reach the engine.
    if (not isinstance(auth, dict) or not auth.get("signature")
            or not auth.get("nonce") or not auth.get("pubkey_b64")):
        raise WalletError(
            "transfer_merit needs the sender's signed transfer "
            "authorization (see make_merit_transfer_auth) — unsigned "
            "transfers are refused")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise WalletError("merit transfer amount must be a number")
    if not isinstance(reason, str) or not reason.strip():
        raise WalletError("merit transfer needs a non-empty reason")
    reason = reason.strip()

    if manifest is None:
        manifest = {"op": "merit-transfer", "nonce": uuid.uuid4().hex}
    else:
        manifest = dict(manifest)
        manifest.setdefault("op", "merit-transfer")
    mhash = _manifest_hash({**manifest, "from": sender.unity_id,
                            "to": to_wallet.unity_id,
                            "amount": amount, "reason": reason,
                            "auth_nonce": auth.get("nonce")})
    if ledger.manifest_applied(mhash):
        # Retry with the same manifest AND the same authorization: the
        # original receipt, and the engine is NOT called again — no
        # double transfer. (A replayed auth under a different manifest
        # is refused by the engine's nonce registry.)
        return ledger._applied[mhash]

    # Donor-exclusion gate — FIRST, before the engine moves anything:
    # Merit that traces to the recipient's own Lock donation never lands.
    # (Idempotent replays return above without re-gating.)
    check_donor_exclusion(to_wallet, {
        "source_donation_hash": manifest.get("source_donation_hash"),
        "source": manifest.get("source"),
        "lock_address": manifest.get("lock_address"),
        "kind": "merit-transfer",
        "amount": amount,
    })

    # Both-side ownership snapshot BEFORE the engine moves anything.
    before_sender = engine.merit_balance(sender.unity_id)
    before_recip = engine.merit_balance(to_wallet.unity_id)

    # The delegation: the engine performs the sole legal transfer and
    # returns the signed MERIT_TRANSFER envelope. The sender's
    # authorization is verified cryptographically by the engine first;
    # structural refusals (unverified ID, bad/forged/replayed auth,
    # insufficient owned Merit, …) propagate as TokenizeRefused with
    # the true reason.
    envelope = engine.merit_transfer(sender.unity_id, to_wallet.unity_id,
                                     amount, reason, auth)

    after_sender = engine.merit_balance(sender.unity_id)
    after_recip = engine.merit_balance(to_wallet.unity_id)

    receipt = {
        "kind": "merit-transfer",
        "from": sender.unity_id,
        "to": to_wallet.unity_id,
        "amount": amount,
        "reason": reason,
        "engine_transfer_id": envelope["receipt"]["transfer_id"],
        "engine_envelope_verified": True,  # envelope came from dclm_commit
        "sides": {
            "sender": {"unity_id": sender.unity_id,
                       "owned_before": before_sender,
                       "owned_after": after_sender},
            "recipient": {"unity_id": to_wallet.unity_id,
                          "owned_before": before_recip,
                          "owned_after": after_recip},
        },
        "ownership_note": (
            "OWNERSHIP ONLY — this receipt records who holds what now. "
            "Origin fields (origin_earner_id, origin_receipt_ref) are "
            "never carried by the wallet; standing never moves on "
            "transfer. A buyer gains economic value and zero standing."
        ),
        "provenance": "VERIFIED",
    }
    # Structural: no origin key may ever appear on a wallet receipt.
    for key in receipt:
        if "origin" in key.lower():
            raise WalletError("wallet receipt must never carry origin")

    def mutate():
        pass  # the engine already moved the value; the wallet only records

    return ledger._apply(mhash, mutate, receipt)


# Inbound-record markers that name the Core Cause Lock / donated supply as
# the source. The amount leg of donor exclusion fires only on EXPLICIT
# naming — never inferred from an amount alone.
_LOCK_SOURCE_KINDS = frozenset({"cause-disbursement", "donation"})
_LOCK_SOURCE_NAMES = frozenset({
    "lock", "core-cause-lock", "cause-lock", "cause lock",
    "core cause lock", "donation", "donated-supply", "donated supply",
    "cause-disbursement",
})


def _names_lock_source(record: dict) -> bool:
    """Does this inbound record name the Core Cause Lock / donated supply
    as its source? Explicit naming only — a lock_address field, a
    Lock-kind marker, or a Lock source name. Never inferred."""
    if not isinstance(record, dict):
        return False
    if record.get("lock_address"):
        return True
    kind = record.get("kind")
    if isinstance(kind, str) and kind.strip().lower() in _LOCK_SOURCE_KINDS:
        return True
    source = record.get("source")
    if (isinstance(source, str)
            and source.strip().lower() in _LOCK_SOURCE_NAMES):
        return True
    return False


def check_donor_exclusion(wallet: Wallet, disbursement: dict) -> dict:
    """Enforce donor exclusion on EVERY wallet credit path.

    A credit tracing to the wallet's OWN Lock donation is REFUSED — the
    Lock is one-way per donor. The trace has two legs (same amount/source):
      source leg — the inbound names the donor's own donation
        (source_donation_hash in the wallet's donation hashes);
      amount leg — the inbound names the Core Cause Lock / donated supply
        as its source AND the amount equals one of the donor's donation
        amounts.
    Anything else passes: a donor may still earn by doing cause-work like
    anyone; only the donated value's return path is killed. Called FIRST
    by every credit path (_credit_token, share, transfer_merit,
    receive_cause_disbursement) — a refusal records nothing.
    """
    record = disbursement if isinstance(disbursement, dict) else {}
    source = record.get("source_donation_hash")
    if source is not None and source in wallet.donation_hashes():
        raise DonorExclusionViolation(
            f"credit sourced from {wallet.unity_id}'s own donation "
            f"{source} — refused")
    amount = record.get("amount")
    if (_names_lock_source(record)
            and isinstance(amount, (int, float))
            and not isinstance(amount, bool)
            and amount in wallet.donation_amounts()):
        raise DonorExclusionViolation(
            f"credit of {amount} from the Core Cause Lock matches "
            f"{wallet.unity_id}'s own donation — refused")
    return {"donor_exclusion": "clear", "unity_id": wallet.unity_id,
            "provenance": "VERIFIED"}


# ---------------------------------------------------------------------------
# integration contract: economic_state.py calls this with a list
# ---------------------------------------------------------------------------
def _payable(balance, provenance) -> bool:
    """The prepaid-bank rule (NEW_ECONOMIC_MODEL §1.3): payable only when
    provenance is REPORTED or VERIFIED and the balance is a real
    non-negative number. UNKNOWN/MODELED never pay."""
    return (provenance in ("REPORTED", "VERIFIED")
            and isinstance(balance, (int, float)) and balance >= 0)


def compute_wallet_state(wallets) -> dict:
    """Build the wallet_states section for the EconomicState.

    Accepts Wallet objects (this module) or raw dicts in the documented
    input shape {"unity_id", "balance", "merit", "honor", "provenance"}.
    Every entry is Unity-bound and provenance-labeled; no anonymous
    wallets exist to the ledger.
    """
    states = {"provenance": "DERIVED"}
    for item in (wallets or []):
        if isinstance(item, Wallet):
            uid = item.unity_id
            bals = item.balances()
            efuse = bals[TOKEN_EFUSE]["amount"]
            unity = bals[TOKEN_UNITY]["amount"]
            honor = item.honor_ledger()
            states[uid] = {
                "balance": efuse,
                "efuse": {"amount": efuse, "provenance": "VERIFIED"},
                "unity": {"amount": unity, "provenance": "VERIFIED"},
                # Merit is the tokenomics engine's measure: the wallet
                # neither holds it, mints it, nor converts anything to it.
                "merit": None,
                "honor": {
                    "count": len(honor),
                    "total_donated_efuse": sum(
                        h["amount"] for h in honor),
                    "class": HONOR_CLASS_UNNAMED,
                    "provenance": "REPORTED",
                },
                "payable": _payable(efuse, "VERIFIED"),
                "provenance": "VERIFIED",
            }
        elif isinstance(item, dict):
            uid = item.get("unity_id")
            if not uid:
                continue  # no anonymous wallets
            uid = str(uid)
            prov = item.get("provenance")
            prov = prov if prov in PROVENANCE_LABELS else "UNKNOWN"
            balance = item.get("balance")
            balance = (balance if isinstance(balance, (int, float))
                       else None)
            states[uid] = {
                "balance": balance,
                "merit": item.get("merit"),
                "honor": item.get("honor"),
                "payable": _payable(balance, prov),
                "provenance": prov,
            }
        # anything else is not a wallet — skipped, never invented
    return states

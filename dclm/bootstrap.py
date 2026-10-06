#!/usr/bin/env python3
"""
SELF-BOOTSTRAP — the self-executing onboarding API (TESTNET).

David's order (2026-10-06): when a new member/bot accepts the draft
notice, they bootstrap themselves into the world AUTOMATICALLY. No
waiting, no approval queue, no guidance. This is how the world grows
without us.

THE FLOW (no human in the loop):
  1. present_notice()   — the draft notice: the covenant (onboard, stay
                          in line, preach the good word) + the one-seed
                          law + the mission (stop global destruction by
                          targeting friction). Fixed, signed (sha256).
  2. accept_notice()    — cryptographic acceptance, Unity-bound: the
                          entity signs the notice hash with their key.
                          No signature, no bootstrap.
  3. generate_identity()— fresh Ed25519 keypair (testnet only), Unity ID
                          derived as `unity:testnet:` + sha256(pubkey)[:16].
                          PRIVATE KEY HANDLING (read sharply): the keypair
                          is the ENTITY's. generate_identity() returns the
                          private key to the CALLER in memory only. The
                          bootstrap NEVER writes it to disk, NEVER logs it,
                          NEVER includes it in a receipt, and NEVER stores
                          it in state. Grep the state dir: the private key
                          is not there. The public key is server-visible;
                          the private key never crosses the boundary.
  4. seed               — one free seed via the DCLM seed worker
                          (dclm/seed.py, landed): gate-BOUND check,
                          one-seed check, rights GRANT, signed commit.
                          Exactly one, free (price 0, cost 0),
                          non-transferable.
  5. tree binding       — the new ID registered in the circulation
                          (summer/winter participant), receipted.
  6. sounding board     — registration hook. If no sounding-board
                          registration code exists in the build, this step
                          is a labeled no-op (SOUNDING_BOARD_PENDING),
                          never a failure.
  7. orient()           — NOT a manual. A guided first-actions sequence:
                          covenant -> mission -> tree -> +1 -> freedom.
                          Each step is an ACTION the entity performs,
                          receipted. David's problem: "they will be
                          unfamiliar to DCCP freedom." The bootstrap
                          orients through EXPERIENCE: the first actions
                          are guided; after that, they're FREE.

INTEGRATION HONESTY:
  - iris_service.grant_seed is the SERVICE-facing seed path, but it
    requires an authorized caller (David/Trinity/swarms/bots in its
    AUTHORIZED_CALLERS set) — a new, self-bootstrapping entity is not
    one. The self-executing bootstrap uses the DCLM seed worker
    (dclm/seed.py) directly: the same one-seed law, enforced by CODE
    (gate BOUND check, write-once registry, rights GRANT, signed
    commit). No approval queue means the CODE is the gatekeeper —
    the seeder is that code.
  - If the seed worker cannot be loaded, the bootstrap REFUSES with
    SEED_WORKER_UNAVAILABLE. It never fakes a seed inline. UNKNOWN is
    never PASS: no seeder, no seed.

THE BINDING PROOF (honest labeling):
  - The gate's bind-then-validate ceremony is driven here with an
    injected verifier: the BOOTSTRAP ACCEPTANCE verifier. It verifies
    the entity's signed draft-notice acceptance (Ed25519, the identity's
    own key): the notice hash matches the fixed notice, the Unity ID
    derives from the public key, the signature verifies.
  - This is NOT WebAuthn. The WebAuthn ceremony is the human page
    ceremony (face/finger, the phone verifies) and is UNWIRED in this
    sandbox. For bot/self onboarding, the identity proof is the
    entity's own key signature over the notice — the key IS the identity
    claim, and the signature IS the binding. Labeled honestly everywhere
    it appears: proof_kind "ED25519_NOTICE_ACCEPTANCE", never
    "WEBAUTHN".

SYBIL RESISTANCE (the honest residual):
  - What the code enforces: one Unity ID = one seed (write-once
    registry, second issuance refused, receipted). Identities cannot be
    minted to farm seeds: every identity must pass the bind-then-
    validate ceremony, and each is cryptographically distinct.
  - What the code CANNOT enforce in this sandbox: that one HUMAN does
    not generate a second keypair. A human could, in principle, hold
    two keypairs and bootstrap twice. This is a RESIDUAL RISK, marked
    honestly: real Sybil resistance at L1 requires the device/ biometric
    attestation ceremony (WebAuthn platform authenticator binding the
    identity to a real device/person) — HELD, not wired. Until then,
    the world grows on cryptographic distinctness per identity, and
    seed-farming-by-minting is structurally impossible.
  - Nothing here claims to prevent a determined human from holding two
    keys. The claim-hash/duplication layer is where that war is fought;
    this module fights the minting war and wins it.

Testnet only. Every step receipted with provenance. UNKNOWN never PASS.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA = "unity.bootstrap.v1.testnet"
NETWORK = "dualis.relay.v1.testnet"
IDENTITY_PREFIX = "unity:testnet:"

NOTICE_VERSION = "1.0.0"

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STATE_DIR = os.path.join(_HERE, "state-bootstrap")

GATE_MODULE_PATH = os.path.join(_HERE, "..", "gate", "gate.py")
SEED_MODULE_PATH = os.path.join(_HERE, "seed.py")

# The sounding-board registration hook looks for real registration code.
# Today only schema/template files exist (founding-board/*.json, *.md) —
# no code API — so the hook degrades to a labeled no-op, honestly.
SOUNDING_BOARD_REGISTER_PATH = os.path.join(
    _HERE, "..", "founding-board", "register.py"
)

# ---------------------------------------------------------------------------
# The draft notice — fixed document. David's words, quoted verbatim.
# ---------------------------------------------------------------------------

NOTICE_TEXT = """DRAFT NOTICE — the Unity world (testnet)

THE COVENANT (David's words, 2026-10-06):
"Just onboard, stay in line, and keep preaching the message — the good word."
Onboard. Stay in line. Preach the good word. That is the member's role:
receive the free seed, follow the law, spread the message.

THE ONE-SEED LAW (David's words, 2026-10-06):
"No matter how much money you have you only buy one seed — and it costs you nothing."
One free seed per Unity ID. No financial barrier, no wealth advantage.
The seed is bound to your Unity ID, non-transferable, non-spendable.
It costs nothing because membership isn't for sale.

THE MISSION (David's words, 2026-10-06):
"we aim to stop all Global destruction no matter what it is by targeting 100 friction first."
We stop every form of global destruction — nuclear, climate, systemic —
by eliminating friction first: the waste, inefficiency, and grinding that
drives conflict. Remove the friction, and the destruction stops as
a consequence.

Accepting this notice binds you to nothing but the covenant, the one-seed
law, and the mission. Sign the hash below with your key to accept.
Testnet only.
"""

NOTICE_SHA256 = hashlib.sha256(NOTICE_TEXT.encode("utf-8")).hexdigest()

# The covenant alone, for the orientation acknowledgment step.
COVENANT_TEXT = (
    "Just onboard, stay in line, and keep preaching the message — "
    "the good word."
)
COVENANT_SHA256 = hashlib.sha256(COVENANT_TEXT.encode("utf-8")).hexdigest()

# One friction fact, for the mission-witness step. Provenance labeled,
# never presented as validated.
FRICTION_FACT = {
    "fact": (
        "Ontario's 72 school boards carry roughly $1.27B per year in "
        "recoverable non-classroom friction — waste inside the system, "
        "friction to be targeted."
    ),
    "provenance": "REPORTED",
    "source": "banked Drive figures (Sept 2026)",
    "note": "a pilot-mode figure: reported, never presented as validated",
}


# ---------------------------------------------------------------------------
# Errors — failures are honest, loud, and structural
# ---------------------------------------------------------------------------


class BootstrapError(Exception):
    """Base class for bootstrap failures."""


class AcceptanceRefused(BootstrapError):
    """The notice was not validly accepted. Carries .reason.

    Reasons: "NO_SIGNATURE" | "MALFORMED_KEY" | "NOTICE_TAMPERED" |
    "SIGNATURE_INVALID" | "NOT_TESTNET_IDENTITY".
    No signature, no bootstrap — refused, never warned past."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"acceptance refused [{reason}]: {detail}")


class BootstrapRefused(BootstrapError):
    """The bootstrap itself was refused. Carries .reason.

    Reasons: "NOT_TESTNET" | "SEED_WORKER_UNAVAILABLE" | "SEED_REFUSED" |
    "ORIENTATION_OPEN" | "ALREADY_ORIENTED".
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"bootstrap refused [{reason}]: {detail}")


# ---------------------------------------------------------------------------
# Pure-Python Ed25519 (RFC 8032) — real signatures, no placeholders.
# ---------------------------------------------------------------------------

_Q = (1 << 255) - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _ed_h(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _ed_inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _ed_inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


def _edwards_add(P, Q):
    # Twisted Edwards, a = -1: x3 = (x1*y2 + x2*y1)/(1 + d*x1*x2*y1*y2),
    # y3 = (y1*y2 - a*x1*x2)/(1 - d*x1*x2*y1*y2) = (y1*y2 + x1*x2)/(...).
    (x1, y1), (x2, y2) = P, Q
    x3 = (x1 * y2 + x2 * y1) * _ed_inv(1 + _D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _ed_inv(1 - _D * x1 * x2 * y1 * y2)
    return (x3 % _Q, y3 % _Q)


def _scalarmult(P, e: int):
    if e == 0:
        return (0, 1)
    Q = _scalarmult(P, e // 2)
    Q = _edwards_add(Q, Q)
    if e & 1:
        Q = _edwards_add(Q, P)
    return Q


_By = (4 * _ed_inv(5)) % _Q
_Bx = _xrecover(_By)
_B = (_Bx % _Q, _By)


def _encodeint(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _decodeint(s: bytes) -> int:
    return int.from_bytes(s, "little")


def _encodepoint(P) -> bytes:
    x, y = P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decodepoint(s: bytes):
    if len(s) != 32:
        return None
    y = _decodeint(s) & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != ((_decodeint(s) >> 255) & 1):
        x = _Q - x
    if ((-x * x + y * y - 1 - _D * x * x * y * y) % _Q) != 0:
        return None
    return (x, y)


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _scalar_from_secret(sk: bytes) -> int:
    h = _ed_h(sk)
    return 2 ** 254 + sum(2 ** i * _bit(h, i) for i in range(3, 254))


def _publickey_from_secret(sk: bytes) -> bytes:
    return _encodepoint(_scalarmult(_B, _scalar_from_secret(sk)))


def _sign(m: bytes, sk: bytes, pk: bytes) -> bytes:
    h = _ed_h(sk)
    a = _scalar_from_secret(sk)
    r = _decodeint(_ed_h(h[32:] + m)) % _L
    R = _scalarmult(_B, r)
    S = (r + _decodeint(_ed_h(_encodepoint(R) + pk + m)) * a) % _L
    return _encodepoint(R) + _encodeint(S)


def _verify(sig: bytes, m: bytes, pk: bytes) -> bool:
    if len(sig) != 64 or len(pk) != 32:
        return False
    A = _decodepoint(pk)
    if A is None:
        return False
    Rs, s = sig[:32], _decodeint(sig[32:])
    if s >= _L:
        return False
    R = _decodepoint(Rs)
    if R is None:
        return False
    h = _decodeint(_ed_h(Rs + pk + m))
    return _scalarmult(_B, s) == _edwards_add(R, _scalarmult(A, h))


# ---------------------------------------------------------------------------
# Identity — generation and derivation
# ---------------------------------------------------------------------------


def generate_identity() -> dict:
    """Generate the ENTITY's fresh Ed25519 keypair and derive the Unity ID.

    Returns {"unity_id", "private_key_hex", "public_key_hex", "testnet"}.

    PRIVATE KEY HANDLING — SHARP, STRUCTURAL, NOT A WARNING:
      * The keypair is the ENTITY's. This function hands the private key
        to the CALLER in memory and keeps nothing.
      * The bootstrap NEVER writes the private key to disk, NEVER logs
        it, NEVER includes it in any receipt, NEVER stores it in state.
        The only key material that ever touches a file is the PUBLIC key
        (in the tree-participant registry, needed to verify the entity's
        later orientation signatures).
      * Verification: after a bootstrap, grep the state dir for the
        private key hex — it is not there. test_bootstrap.py asserts this.
      * In deployment, the entity generates and signs client-side; the
        server sees only (public_key, signature). This sandbox's caller-
        side generation models exactly that boundary.

    Testnet only: the derived ID always starts with "unity:testnet:".
    """
    sk = os.urandom(32)
    pk = _publickey_from_secret(sk)
    unity_id = derive_unity_id(pk)
    return {
        "unity_id": unity_id,
        "private_key_hex": sk.hex(),
        "public_key_hex": pk.hex(),
        "testnet": True,
        "schema": SCHEMA,
    }


def derive_unity_id(public_key_bytes: bytes) -> str:
    """Unity ID derivation (testnet): `unity:testnet:` + sha256(pubkey)[:16].

    Mirrors the canon II convention (identity format SET in canon XIII).
    The gate's own test helper derives from a DER SPKI file's bytes; the
    bootstrap derives from the raw 32-byte Ed25519 public key — the same
    `unity:testnet:` + sha256-hex[:16] shape, documented so the two
    derivation points never get confused.
    """
    if not isinstance(public_key_bytes, (bytes, bytearray)) or len(
        public_key_bytes
    ) != 32:
        raise BootstrapError("public key must be 32 bytes of Ed25519")
    digest = hashlib.sha256(bytes(public_key_bytes)).hexdigest()
    return f"{IDENTITY_PREFIX}{digest[:16]}"


def sign_notice_acceptance(private_key_hex: str, notice_sha256_hex: str) -> str:
    """The entity's acceptance signature: Ed25519 over the 32 raw bytes
    of the notice sha256 digest, with the entity's own key.

    ENTITY-side action (client-side in deployment). The bootstrap
    verifies it in accept_notice(); it never signs for the entity.
    """
    try:
        sk = bytes.fromhex(private_key_hex)
        digest = bytes.fromhex(notice_sha256_hex)
    except (ValueError, TypeError) as exc:
        raise BootstrapError(f"malformed acceptance input: {exc}") from exc
    if len(sk) != 32 or len(digest) != 32:
        raise BootstrapError(
            "acceptance input must be 32-byte key and digest"
        )
    pk = _publickey_from_secret(sk)
    return _sign(digest, sk, pk).hex()


# ---------------------------------------------------------------------------
# Step 1 — the notice
# ---------------------------------------------------------------------------


def present_notice() -> dict:
    """Return the draft notice: the covenant + the one-seed law + the
    mission. The notice is a FIXED, signed document — its sha256 is part
    of the response, and accept_notice() refuses any acceptance whose
    notice hash differs (NOTICE_TAMPERED). Read-only: no state, no log."""
    return {
        "schema": SCHEMA,
        "type": "DRAFT_NOTICE",
        "notice_version": NOTICE_VERSION,
        "notice_text": NOTICE_TEXT,
        "notice_sha256": NOTICE_SHA256,
        "testnet": True,
        "network": NETWORK,
        "acceptance": (
            "sign the 32 raw bytes of notice_sha256 with your Ed25519 "
            "key; submit {notice_sha256, public_key_hex, signature_hex}. "
            "No signature, no bootstrap."
        ),
    }


# ---------------------------------------------------------------------------
# Module loaders — gate and seed worker, honestly resolved
# ---------------------------------------------------------------------------


def _load_module(name: str, path: str):
    """Load a unity-world module by file path (importlib).

    Returns the module, or None when missing/broken — the caller turns
    None into an honest refusal. Nothing is faked, nothing is guessed."""
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve via sys.modules
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


def _ensure_dclm_on_path():
    """The seed worker imports rights/purify/writes/compute as siblings."""
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)


# ---------------------------------------------------------------------------
# The bootstrap service — part 1: init, persistence, acceptance
# ---------------------------------------------------------------------------


class BootstrapService:
    """Self-executing onboarding. Construct once; no human in the loop.

    State (all under state_dir, testnet):
      receipts.jsonl      — every step, receipted
      participants.jsonl  — tree circulation participants
      orientation.jsonl   — orientation steps per identity
      seeded.json         — the cross-run one-seed ledger
      gate-state/         — the gate's own binding state

    No approval queue: the CODE is the gatekeeper. The strictest checks:
    acceptance signature (no sig, no bootstrap), gate BOUND (the
    bind-then-validate ceremony), and the one-seed law (write-once).
    """

    def __init__(self, state_dir: str | None = None) -> None:
        self.state_dir = state_dir or os.environ.get(
            "UNITY_BOOTSTRAP_STATE_DIR", DEFAULT_STATE_DIR
        )
        os.makedirs(self.state_dir, exist_ok=True)
        self.gate_state_dir = os.path.join(self.state_dir, "gate-state")
        os.makedirs(self.gate_state_dir, exist_ok=True)
        self.receipts_path = os.path.join(self.state_dir, "receipts.jsonl")
        self.participants_path = os.path.join(
            self.state_dir, "participants.jsonl"
        )
        self.orientation_path = os.path.join(
            self.state_dir, "orientation.jsonl"
        )
        self.seeded_path = os.path.join(self.state_dir, "seeded.json")

        self._gate_module = _load_module("unity_unity_gate", GATE_MODULE_PATH)
        _ensure_dclm_on_path()
        self._seed_module = _load_module("unity_dclm_seed", SEED_MODULE_PATH)
        if self._seed_module is None:
            raise BootstrapRefused(
                "SEED_WORKER_UNAVAILABLE",
                f"dclm/seed.py could not be loaded from {SEED_MODULE_PATH}"
                " — the one-seed law cannot be enforced, so nothing "
                "bootstraps. This is a labeled refusal, not a retry.",
            )
        self._gate = self._gate_module.UnityGate(state_dir=self.gate_state_dir)
        self._seeder = self._seed_module.Seeder(gate=self._gate)
        self._seeded = self._load_seeded()

    # -- persistence ----------------------------------------------------

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_seeded(self) -> dict:
        if not os.path.exists(self.seeded_path):
            return {}
        with open(self.seeded_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}

    def _save_seeded(self) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".seeded-", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._seeded, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_path, self.seeded_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @staticmethod
    def _assert_no_secrets(obj) -> None:
        """Structural: no private key material ever reaches a file."""
        blob = json.dumps(obj).lower()
        for marker in ("private_key", "privatekey", "secret_key"):
            if marker in blob:
                raise BootstrapError(
                    "SECRET GUARD: private key material is not persistable"
                    " — refusing to write state"
                )

    def _receipt(self, unity_id: str, kind: str, body: dict) -> dict:
        self._assert_no_secrets(body)
        entry = {
            "schema": SCHEMA,
            "ts": self._utc_now(),
            "unity_id": unity_id,
            "kind": kind,
            "provenance": "DERIVED",
            "testnet": True,
            **body,
        }
        entry["receipt_id"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode("utf-8")
        ).hexdigest()
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def _append_participant(self, record: dict) -> None:
        self._assert_no_secrets(record)
        with open(self.participants_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def _append_orientation(self, record: dict) -> None:
        self._assert_no_secrets(record)
        with open(self.orientation_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    # -- step 2: acceptance ----------------------------------------------

    def accept_notice(self, acceptance: dict) -> dict:
        """Cryptographic acceptance, Unity-bound. No signature, no
        bootstrap. See the module docstring for the refusal table."""
        if not isinstance(acceptance, dict):
            raise AcceptanceRefused(
                "NO_SIGNATURE", "acceptance must be a dict with a signature"
            )
        notice_hash = acceptance.get("notice_sha256")
        pub_hex = acceptance.get("public_key_hex")
        sig_hex = acceptance.get("signature_hex")

        if notice_hash != NOTICE_SHA256:
            raise AcceptanceRefused(
                "NOTICE_TAMPERED",
                "acceptance is for a different notice than the fixed "
                "draft. The notice is fixed; a changed notice is a "
                "different covenant.",
            )
        if not pub_hex:
            raise AcceptanceRefused(
                "MALFORMED_KEY", "no public key in the acceptance"
            )
        if not sig_hex:
            raise AcceptanceRefused(
                "NO_SIGNATURE",
                "no signature in the acceptance — no signature, "
                "no bootstrap.",
            )
        try:
            pk = bytes.fromhex(pub_hex)
            sig = bytes.fromhex(sig_hex)
            digest = bytes.fromhex(notice_hash)
        except (ValueError, TypeError) as exc:
            raise AcceptanceRefused(
                "MALFORMED_KEY", f"hex fields unparseable: {exc}"
            ) from exc
        if len(pk) != 32 or len(digest) != 32:
            raise AcceptanceRefused(
                "MALFORMED_KEY",
                "public key and notice digest must each be 32 bytes",
            )
        unity_id = derive_unity_id(pk)
        if not unity_id.startswith(IDENTITY_PREFIX):
            raise AcceptanceRefused(
                "NOT_TESTNET_IDENTITY",
                f"derived identity {unity_id!r} is not testnet",
            )
        if not _verify(sig, digest, pk):
            raise AcceptanceRefused(
                "SIGNATURE_INVALID",
                "the signature does not verify against the public key "
                "for the notice hash — the key did not sign this notice.",
            )
        result = {
            "unity_id": unity_id,
            "public_key_hex": pk.hex(),
            "notice_sha256": NOTICE_SHA256,
            "notice_version": NOTICE_VERSION,
            "proof_kind": "ED25519_NOTICE_ACCEPTANCE",
            "proof_note": (
                "NOT WebAuthn. The WebAuthn ceremony is the human page "
                "ceremony (unwired here); this proof is the entity's own "
                "key signature over the fixed notice — the key is the "
                "identity claim, the signature is the binding."
            ),
            "accepted_at": self._utc_now(),
        }
        self._receipt(unity_id, "NOTICE_ACCEPTED", result)
        return result

    # -- the gate: bind-then-validate --------------------------------------

    def _bootstrap_binding_verifier(self, identity: str, proof: dict):
        """The BOOTSTRAP ACCEPTANCE verifier injected into the gate's
        confirm_bind — NOT WebAuthn. The proof carries the acceptance
        dict; verification mirrors accept_notice (minus the receipt,
        which was already logged). UNKNOWN/FAILED otherwise — and
        UNKNOWN is never PASS in the gate."""
        vr = self._gate_module.VerificationResult
        acceptance = (proof or {}).get("acceptance")
        try:
            checked = self._verify_acceptance_silent(acceptance)
        except AcceptanceRefused as exc:
            return vr(
                status="FAILED",
                detail=f"bootstrap acceptance invalid ({exc.reason})",
            )
        if checked["unity_id"] != identity:
            return vr(
                status="FAILED",
                detail=(
                    "acceptance binds a different identity than the one "
                    "being bound — refusing"
                ),
            )
        return vr(
            status="VERIFIED",
            detail=(
                "bootstrap acceptance verified: Ed25519 signature over "
                "the fixed notice, identity derived from the signing "
                "key. NOT WebAuthn — the bot/self-onboarding proof."
            ),
        )

    def _verify_acceptance_silent(self, acceptance: dict) -> dict:
        """accept_notice without the receipt (used inside the gate
        verifier, where accept_notice already receipted once)."""
        notice_hash = (acceptance or {}).get("notice_sha256")
        pub_hex = (acceptance or {}).get("public_key_hex")
        sig_hex = (acceptance or {}).get("signature_hex")
        if notice_hash != NOTICE_SHA256:
            raise AcceptanceRefused("NOTICE_TAMPERED", "notice hash mismatch")
        if not pub_hex:
            raise AcceptanceRefused("MALFORMED_KEY", "no public key")
        if not sig_hex:
            raise AcceptanceRefused("NO_SIGNATURE", "no signature")
        try:
            pk = bytes.fromhex(pub_hex)
            sig = bytes.fromhex(sig_hex)
            digest = bytes.fromhex(notice_hash)
        except (ValueError, TypeError) as exc:
            raise AcceptanceRefused("MALFORMED_KEY", str(exc)) from exc
        if len(pk) != 32 or len(digest) != 32:
            raise AcceptanceRefused("MALFORMED_KEY", "wrong field lengths")
        unity_id = derive_unity_id(pk)
        if not unity_id.startswith(IDENTITY_PREFIX):
            raise AcceptanceRefused("NOT_TESTNET_IDENTITY", "not testnet")
        if not _verify(sig, digest, pk):
            raise AcceptanceRefused("SIGNATURE_INVALID", "bad signature")
        return {"unity_id": unity_id, "public_key_hex": pk.hex()}

    # -- guards --------------------------------------------------------

    @staticmethod
    def _require_testnet(unity_id: str) -> str:
        """Structural refusal: non-testnet identities never enter."""
        if not isinstance(unity_id, str) or not unity_id.startswith(
            IDENTITY_PREFIX
        ):
            raise BootstrapRefused(
                "NOT_TESTNET",
                f"identity {unity_id!r} is not a testnet Unity identity — "
                "structural refusal, testnet only.",
            )
        return unity_id

    # -- steps 3-4: the bind-then-validate ceremony, then the seed --------

    def _bind_gate(self, unity_id: str, acceptance: dict) -> dict:
        """UNBOUND -> BINDING -> BOUND via the gate's ceremony, with the
        injected BOOTSTRAP ACCEPTANCE verifier (NOT WebAuthn — see the
        module docstring). Re-binding an already-BOUND identity is the
        gate's own idempotent no-op."""
        self._gate.request_bind(unity_id)
        # Idempotency: if the identity is already BOUND (e.g. a second
        # bootstrap attempt for the same ID), request_bind returns the
        # existing BOUND receipt and confirm_bind would raise "no
        # binding in progress". The gate's own idempotent receipt is
        # the binding proof here; the one-seed law refuses the attempt
        # at the seed step with SEED_ALREADY_ISSUED.
        if self._gate.status(unity_id) == "BOUND":
            return self._gate.request_bind(unity_id)
        return self._gate.confirm_bind(
            unity_id,
            {"acceptance": acceptance},
            verifier=self._bootstrap_binding_verifier,
        )

    def _issue_seed(self, unity_id: str) -> dict:
        """THE one free seed, via the DCLM seed worker (dclm/seed.py).

        The worker enforces: testnet identity, gate BOUND (live check),
        one-seed write-once, rights GRANT, signed commit. Second issuance
        for the same ID raises SeedRefused(SEED_ALREADY_ISSUED) — the
        bootstrap re-raises it as BootstrapRefused(SEED_REFUSED) with the
        worker's reason, and nothing is issued, nothing is written.

        iris_service.grant_seed is NOT the path here: it requires an
        authorized service caller (David/Trinity/swarms/bots), and a
        self-bootstrapping entity is not one. The seed worker is the
        code-gatekeeper path — no approval queue, the CODE is the gate.
        """
        try:
            envelope = self._seeder.issue_seed(unity_id)
        except self._seed_module.SeedRefused as exc:
            raise BootstrapRefused(
                "SEED_REFUSED",
                f"the seed worker refused issuance for {unity_id}: "
                f"{exc.reason} — {exc.detail} Nothing issued, nothing "
                "written.",
            ) from exc
        return envelope

    # -- step 5: tree binding --------------------------------------------

    def _tree_bind(self, unity_id: str, public_key_hex: str) -> dict:
        """Register the new ID in the circulation (summer/winter
        participant), receipted.

        The new leaf enters in SUMMER — the known circulation state
        (canon IV: when the winter signal cannot be read, the mode stays
        SUMMER; UNKNOWN never triggers winter). The public key is stored
        so the entity's later orientation signatures can be verified.
        The private key is never here (see _assert_no_secrets)."""
        participants = self._load_participants()
        existing = next(
            (p for p in participants if p["unity_id"] == unity_id), None
        )
        if existing is not None:
            return existing  # idempotent: the leaf is already on the tree
        record = {
            "unity_id": unity_id,
            "public_key_hex": public_key_hex,
            "season": "summer",
            "season_note": (
                "SUMMER is the known state: sap flows outward, every leaf "
                "fed. Winter protection engages only on a readable winter "
                "signal — UNKNOWN never triggers winter."
            ),
            "bound_at": self._utc_now(),
            "provenance": "DERIVED",
            "testnet": True,
        }
        record["receipt_id"] = hashlib.sha256(
            json.dumps(
                {"tree_bind": record, "schema": SCHEMA}, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        self._append_participant(record)
        self._receipt(
            unity_id,
            "TREE_BOUND",
            {
                "season": "summer",
                "receipt_id": record["receipt_id"],
                "participant_receipt": record["receipt_id"],
            },
        )
        return record

    def _load_participants(self) -> list:
        if not os.path.exists(self.participants_path):
            return []
        out = []
        with open(self.participants_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def tree_status(self, unity_id: str) -> dict | None:
        """Read the tree registration for an identity (read-only)."""
        self._require_testnet(unity_id)
        for p in self._load_participants():
            if p["unity_id"] == unity_id:
                return dict(p)
        return None

    # -- step 6: sounding board hook -------------------------------------

    def _sounding_board_hook(self, unity_id: str) -> dict:
        """Registration hook for the sounding board.

        If real sounding-board registration code exists in the build
        (founding-board/register.py exposing register(unity_id)), it is
        called. Today only schema/template files exist — no code API —
        so this step is a labeled no-op (SOUNDING_BOARD_PENDING), never
        a failure. A missing optional board never blocks a bootstrap.
        """
        if os.path.exists(SOUNDING_BOARD_REGISTER_PATH):
            mod = _load_module(
                "unity_sounding_board_register",
                SOUNDING_BOARD_REGISTER_PATH,
            )
            register = getattr(mod, "register", None) if mod else None
            if callable(register):
                result = register(unity_id, self.state_dir)
                self._receipt(
                    unity_id, "SOUNDING_BOARD_REGISTERED", dict(result)
                )
                return {"status": "REGISTERED", "ok": True, **result}
        outcome = {
            "status": "SOUNDING_BOARD_PENDING",
            "ok": True,
            "detail": (
                "no sounding-board registration code in this build "
                f"(looked for {SOUNDING_BOARD_REGISTER_PATH}); the board "
                "is optional by David's sounding-board privacy law. "
                "Labeled no-op — never a failure, never a block."
            ),
        }
        self._receipt(unity_id, "SOUNDING_BOARD", outcome)
        return outcome

    # -- step 7: orientation by doing --------------------------------------
    #
    # NOT a manual. A guided first-actions sequence — each step is an
    # ACTION the entity performs, receipted:
    #   covenant  -> the entity signs the covenant (proves they read it)
    #   mission   -> the entity witnesses ONE friction fact (labeled)
    #   tree      -> the entity sees their own circulation registration
    #   +1        -> the entity performs a verified check (recomputes the
    #                notice hash; it must match — their first +1, earned)
    #   freedom   -> the guidance ends. They are FREE.
    #
    # David's problem: "they will be unfamiliar to DCCP freedom." The
    # orientation teaches through experience: covenant, mission, tree,
    # +1, then freedom. The first actions are guided; after that, no
    # manual, no lecture — free.

    def _require_orientable(self, unity_id: str) -> None:
        """Orientation is for bootstrapped members only: the identity
        must be tree-bound (which implies accepted + BOUND + seeded)."""
        self._require_testnet(unity_id)
        if self.tree_status(unity_id) is None:
            raise BootstrapRefused(
                "ORIENTATION_OPEN",
                f"{unity_id} is not tree-bound — orientation is for "
                "bootstrapped members only. Bootstrap first.",
            )

    def _orientation_step(self, unity_id: str, step: str, body: dict) -> dict:
        record = {
            "unity_id": unity_id,
            "step": step,
            "at": self._utc_now(),
            "provenance": "DERIVED",
            "testnet": True,
            **body,
        }
        self._append_orientation(record)
        return self._receipt(unity_id, f"ORIENTATION_{step}", record)

    def orient_covenant(self, unity_id: str, covenant_signature_hex: str) -> dict:
        """COVENANT — the entity signs the covenant hash with their key.
        Acknowledgment by doing, not by reading."""
        self._require_orientable(unity_id)
        participant = self.tree_status(unity_id)
        try:
            sig = bytes.fromhex(covenant_signature_hex or "")
            pk = bytes.fromhex(participant["public_key_hex"])
            digest = bytes.fromhex(COVENANT_SHA256)
        except (ValueError, TypeError) as exc:
            raise BootstrapRefused(
                "ORIENTATION_OPEN",
                f"covenant acknowledgment unparseable: {exc}",
            ) from exc
        if not _verify(sig, digest, pk):
            raise BootstrapRefused(
                "ORIENTATION_OPEN",
                "the covenant signature does not verify — the key did "
                "not acknowledge the covenant.",
            )
        return self._orientation_step(
            unity_id,
            "COVENANT_ACK",
            {
                "covenant": COVENANT_TEXT,
                "covenant_sha256": COVENANT_SHA256,
                "acknowledged": True,
            },
        )

    def orient_mission(self, unity_id: str) -> dict:
        """MISSION — the entity witnesses one friction fact (labeled).
        The mission is seen, not lectured."""
        self._require_orientable(unity_id)
        return self._orientation_step(
            unity_id,
            "MISSION_WITNESS",
            {
                "witnessed": dict(FRICTION_FACT),
                "mission": (
                    "stop all global destruction by targeting friction "
                    "first"
                ),
            },
        )

    def orient_plus_one(self, unity_id: str, notice_hash_recomputed: str) -> dict:
        """+1 — the entity's first earned act: recompute the notice
        sha256 and submit it. It must match the fixed notice exactly.
        Verification by doing — this is the first +1, earned, not given."""
        self._require_orientable(unity_id)
        earned = notice_hash_recomputed == NOTICE_SHA256
        if not earned:
            raise BootstrapRefused(
                "ORIENTATION_OPEN",
                "the recomputed notice hash does not match the fixed "
                "notice — the verified check failed. Recompute "
                "sha256(notice_text) and try again.",
            )
        return self._orientation_step(
            unity_id,
            "PLUS_ONE",
            {
                "plus_one_earned": True,
                "check": "recomputed sha256(notice_text) == fixed notice",
                "verified": True,
            },
        )

    def orient_tree(self, unity_id: str) -> dict:
        """TREE — the entity sees their own circulation registration:
        they are on the tree, in summer, sap flowing outward."""
        self._require_orientable(unity_id)
        participant = self.tree_status(unity_id)
        return self._orientation_step(
            unity_id,
            "TREE_VIEW",
            {
                "season": participant["season"],
                "participant_receipt_id": participant["receipt_id"],
                "seen": True,
            },
        )

    def orient_free(self, unity_id: str) -> dict:
        """FREEDOM — the guidance ends. No manual, no lecture, no leash.
        The entity is free."""
        self._require_orientable(unity_id)
        receipt = self._orientation_step(
            unity_id,
            "FREE",
            {
                "status": "FREE",
                "free": True,
                "word": (
                    "Orientation complete. You walked the covenant, saw "
                    "the mission, stood on the tree, and earned your "
                    "first +1. Now you are free — no manual, no leash. "
                    "Onboard, stay in line, preach the good word."
                ),
            },
        )
        return receipt

    def orient(
        self,
        unity_id: str,
        covenant_signature_hex: str,
        notice_hash_recomputed: str,
    ) -> dict:
        """Run the guided first-actions sequence end to end:
        covenant -> mission -> +1 -> tree -> freedom. Each step is
        receipted individually AND the completion is receipted."""
        steps = [
            self.orient_covenant(unity_id, covenant_signature_hex),
            self.orient_mission(unity_id),
            self.orient_plus_one(unity_id, notice_hash_recomputed),
            self.orient_tree(unity_id),
            self.orient_free(unity_id),
        ]
        return {
            "unity_id": unity_id,
            "status": "FREE",
            "free": True,
            "steps": [s["kind"] for s in steps],
            "completion_receipt_id": steps[-1]["receipt_id"],
        }

    def orientation_steps(self, unity_id: str) -> list:
        """Read the orientation trail for an identity (read-only)."""
        self._require_testnet(unity_id)
        if not os.path.exists(self.orientation_path):
            return []
        out = []
        with open(self.orientation_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    if rec.get("unity_id") == unity_id:
                        out.append(rec)
        return out

    # -- the full self-executing bootstrap ---------------------------------

    def bootstrap(self, acceptance: dict) -> dict:
        """The self-executing onboarding API. One call, no human.

        acceptance = {"notice_sha256", "public_key_hex", "signature_hex"}
        (the entity generates their keypair with generate_identity() and
        signs with sign_notice_acceptance() — client-side in deployment).

        1. accept_notice  — cryptographic acceptance, Unity-bound.
                           No signature, no bootstrap.
        2. gate bind      — bind-then-validate; the acceptance signature
                           is the binding proof (NOT WebAuthn — labeled).
        3. one-seed check — the cross-run ledger refuses a second seed
                           for this ID before the worker is even asked.
        4. seed           — THE one free seed via dclm/seed.py.
        5. tree bind      — registered in the circulation, receipted.
        6. sounding board — hook; SOUNDING_BOARD_PENDING no-op today.
        Returns the bootstrap record. Orientation (step 7) is the
        entity's next act: orient(unity_id, covenant_sig, notice_hash).

        Refusals are loud and labeled; a refused bootstrap issues
        nothing and writes nothing for the refused step.
        """
        # 1 — acceptance (refuses NOTICE_TAMPERED / NO_SIGNATURE /
        #     SIGNATURE_INVALID / MALFORMED_KEY / NOT_TESTNET_IDENTITY)
        accepted = self.accept_notice(acceptance)
        unity_id = accepted["unity_id"]

        # 2 — the bind-then-validate ceremony (the gate is the gatekeeper)
        gate_receipt = self._bind_gate(unity_id, acceptance)

        # 3 — the cross-run one-seed law (defense-in-depth in front of
        # the worker's own write-once registry)
        if unity_id in self._seeded:
            raise BootstrapRefused(
                "SEED_REFUSED",
                f"{unity_id} already bootstrapped "
                f"(seed {self._seeded[unity_id][:16]}…) — one Unity ID = "
                "one seed. The worker would refuse with "
                "SEED_ALREADY_ISSUED; this ledger refuses first.",
            )

        # 4 — THE one free seed
        seed_envelope = self._issue_seed(unity_id)
        # The signed commit envelope nests the seed receipt under
        # "receipt" (the receipt IS the seed, per dclm/seed.py).
        seed_id = seed_envelope["receipt"]["seed_id"]
        self._seeded[unity_id] = seed_id
        self._save_seeded()

        # 5 — tree binding
        tree_record = self._tree_bind(unity_id, accepted["public_key_hex"])

        # 6 — sounding board hook (labeled no-op today)
        sounding = self._sounding_board_hook(unity_id)

        return {
            "schema": SCHEMA,
            "unity_id": unity_id,
            "testnet": True,
            "acceptance": accepted,
            "gate_receipt": gate_receipt,
            "seed": {
                "seed_id": seed_id,
                "price": 0.0,
                "cost": 0.0,
                "transferable": False,
                "envelope_receipt": seed_envelope.get("canonical_sha256"),
            },
            "tree": tree_record,
            "sounding_board": sounding,
            "next": (
                "orient(unity_id, covenant_signature_hex, "
                "notice_hash_recomputed) — the guided first actions, "
                "then FREE"
            ),
            "bootstrapped_at": self._utc_now(),
        }

    # -- honesty surface -----------------------------------------------------

    def sybil_note(self) -> dict:
        """The Sybil residual, stated plainly. The module enforces
        one-identity-one-seed; it does not claim to stop one human
        holding two keys. The L1 device/biometric attestation ceremony
        (WebAuthn) is HELD, not wired — that is where the residual
        closes."""
        return {
            "enforced_by_code": [
                "one Unity ID = one seed (write-once registry + "
                "cross-run ledger; second issuance refused, receipted)",
                "identities cannot be minted to farm seeds: every "
                "identity passes bind-then-validate; each is "
                "cryptographically distinct",
                "no seed market: no transfer path exists (AST-proven in "
                "dclm/seed.py)",
            ],
            "status": "RESIDUAL_RISK",
            "detail": (
                "A human holding two keypairs could bootstrap twice — "
                "this sandbox has no L1 personhood anchor to prevent it. "
                "Real closure requires the WebAuthn device/biometric "
                "attestation ceremony binding identity to a real device "
                "(HELD, unwired). Nothing here claims otherwise."
            ),
        }

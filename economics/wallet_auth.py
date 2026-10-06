"""
BIOMETRIC AUTH — the wallet's auth path: YOU ARE THE KEY.

The wallet does not build biometrics. The biometric system ALREADY
EXISTS in Grok's code; this module only CALLS it (thin adapter —
David's law: don't rebuild what exists):

  Server half (called here, verbatim):
    ~/workspace/user/files/unity-id-issuer_4_y3wp.js  — Grok's
    UnityIdIssuer: the webauthn.create registration ceremony, with
    injected webAuthnVerifier + assertionSigner. Called via
    biometric_adapter.mjs in this directory (thin wrapper; Grok's file
    is never modified).
  Device half (the face/finger on the phone — the hardware handoff):
    dccp-world/src/dccp/unity/unityid.ts::createPilotHandle
      (navigator.credentials.create, platform authenticator), and
    drive-spine/.../dualis-unity-onboarding.js (the passkey ceremony
    step). In THIS sandbox there is no platform authenticator: no
    device ceremony can run. Grok's issuer reports HOLE (verifier
    NOT_CONFIGURED — its own honest mark), and biometric_auth REFUSES
    rather than faking a biometric. UNKNOWN is never PASS.
  Server state machine (bind-then-validate, L1):
    ~/workspace/unity-world/gate/gate.py — UnityGate: UNBOUND ->
    BINDING -> BOUND. The wallet asks the gate to run the ceremony;
    only BOUND opens the wallet.

THE FOUR LAWS OF THE WEBSITE (David, 2026-10-06 ~04:36 EDT) — the
entry sequence biometric_auth serves:
  (1) the doorway card explains the Unity ID,
  (2) the bind ceremony  <— THIS MODULE (beat 2),
  (3) the eFuse ignition (fuse worker's lane — integration point,
      HONEST-PENDING here; never faked),
  (4) entry into the 3D world — wallet live, subtle persistent
      indicator, never a card, never a popup.
The wallet never duplicates the doorway card; it takes over AFTER
entry, quiet.

Test double: a caller may inject device_ceremony (the phone
simulation). It is clearly labeled TEST-DOUBLE in every receipt —
never claimed as a real biometric. Same pattern as gate.py's
injected WebAuthn verifier.
"""

import json
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADAPTER = os.path.join(_HERE, "biometric_adapter.mjs")

# Grok's code, named so nobody re-builds it. These paths are the
# implementation; this module calls them.
GROK_SERVER_ISSUER = os.path.expanduser(
    "~/workspace/user/files/unity-id-issuer_4_y3wp.js")
GROK_DEVICE_CEREMONY_TS = os.path.expanduser(
    "~/workspace/dccp-world/src/dccp/unity/unityid.ts")  # createPilotHandle
GROK_DEVICE_CEREMONY_JS = os.path.expanduser(
    "~/workspace/drive-spine/canonical/plumbing/engineering/"
    "dualis-unity-onboarding.js")  # the passkey ceremony step

TESTNET_IDENTITY_PREFIX = "unity:testnet:"

TEST_DOUBLE_LABEL = "TEST-DOUBLE"


class BiometricAuthError(Exception):
    """Base for biometric-auth failures."""


class BiometricNotWired(BiometricAuthError):
    """Honest refusal: no platform authenticator exists in this sandbox,
    Grok's issuer adapters are NOT_CONFIGURED (its own HOLE), and there
    is no device ceremony to call. Refusing — never faking a biometric."""


def _grok_issuer(command):
    """Call Grok's UnityIdIssuer (unmodified) through the thin adapter.

    Returns the parsed JSON. The issuer's own verdict is carried verbatim:
    HOLE means the WebAuthn verifier / assertion signer are not
    configured — Grok's honest mark, not ours.
    """
    proc = subprocess.run(
        ["node", _ADAPTER, command],
        capture_output=True, timeout=30,
    )
    if proc.returncode != 0:
        raise BiometricAuthError(
            f"biometric adapter failed: {proc.stderr.decode()!r}")
    return json.loads(proc.stdout.decode())


def grok_issuer_status():
    """Grok's issuer's honest verdict (READY or HOLE). Read-only."""
    return _grok_issuer("status")


def _get_gate(state_dir=None):
    gate_dir = os.path.normpath(os.path.join(_HERE, "..", "gate"))
    import sys as _sys
    if gate_dir not in _sys.path:
        _sys.path.insert(0, gate_dir)
    import gate as gate_module
    return gate_module.UnityGate(state_dir=state_dir)


def biometric_auth(unity_id, device_ceremony=None, gate_state_dir=None):
    """Authenticate a Unity ID by its biometric — the L1 bind ceremony.

    The call chain is: gate.request_bind -> Grok's issuer challenge ->
    THE DEVICE CEREMONY (the one hardware handoff) -> Grok's issuer
    registration verdict -> gate.confirm_bind -> BOUND. The wallet opens
    only for BOUND identities.

    device_ceremony: an injected callable taking the Grok challenge dict
    and returning {"attestation": ...}. In the live world this is the
    phone's platform-authenticator ceremony (Grok's client code, named
    above) — the ONE line below marked HARDWARE HANDOFF. In this sandbox
    the default is None -> BiometricNotWired: refusing, never faking.

    A test double may be injected; its verdict is labeled TEST-DOUBLE
    everywhere (simulation, not a biometric). The double must return
    {"attestation": TEST_DOUBLE_LABEL, "challenge_id": <id>} — anything
    else is refused, so the double can never be mistaken for the real
    ceremony.

    Returns the BOUND receipt: {"unity_id", "bound": True, "gate_receipt",
    "grok_issuer_verdict", "device_ceremony", "provenance"}.
    """
    if (not isinstance(unity_id, str)
            or not unity_id.startswith(TESTNET_IDENTITY_PREFIX)):
        raise BiometricAuthError(
            f"biometric auth needs a testnet Unity ID "
            f"({TESTNET_IDENTITY_PREFIX}…); got {unity_id!r}")

    gate = _get_gate(gate_state_dir)
    bind_receipt = gate.request_bind(unity_id)

    # Ask Grok's issuer (unmodified) for the registration challenge and
    # record ITS verdict — HOLE when its adapters are unwired, which is
    # this sandbox. Its verdict is data, never a pass.
    challenge_out = _grok_issuer("challenge")
    grok_challenge = challenge_out.get("grok_challenge", {})
    issuer_verdict = grok_issuer_status()["grok_issuer_status"]

    if device_ceremony is None:
        # === HARDWARE HANDOFF (the one line) ===
        # Live world: device_ceremony = the phone's WebAuthn platform-
        # authenticator ceremony (Grok: unityid.ts::createPilotHandle /
        # dualis-unity-onboarding.js passkey step). The page never sees
        # the biometric; the phone does; the server sees only the
        # assertion. In THIS sandbox there is no device — HONEST-PENDING.
        raise BiometricNotWired(
            "no platform authenticator in this sandbox: the device "
            "ceremony (the face/finger on the phone — Grok's client "
            "code, see GROK_DEVICE_CEREMONY_* above) cannot run here, "
            "and Grok's issuer reports its own verdict "
            f"'{issuer_verdict['issuer']}' (verifier: "
            f"{issuer_verdict['verifier']}). Refusing to treat this as "
            "auth — a biometric is never faked.")

    # === HARDWARE HANDOFF (the one line — injected double in tests) ===
    proof = device_ceremony(grok_challenge)

    ceremony_label = (proof or {}).get("attestation")
    if ceremony_label != TEST_DOUBLE_LABEL:
        raise BiometricAuthError(
            "device ceremony proof is not a labeled test double and no "
            "real platform authenticator exists in this sandbox — "
            "refusing. A real proof must come through Grok's issuer "
            "with its WebAuthn verifier configured (it is not).")

    def _test_double_verifier(identity, proof_dict):
        from collections import namedtuple
        VR = namedtuple("VR", ["status", "detail"])
        if (proof_dict or {}).get("attestation") == TEST_DOUBLE_LABEL:
            return VR("VERIFIED",
                      "TEST-DOUBLE device ceremony accepted: simulation, "
                      "not a biometric; valid for testnet flow tests only")
        return VR("FAILED", "not the labeled test double — refusing")

    bound_receipt = gate.confirm_bind(
        unity_id, {"attestation": TEST_DOUBLE_LABEL}, _test_double_verifier)

    return {
        "unity_id": unity_id,
        "bound": True,
        "gate_receipt": bound_receipt,
        "grok_issuer_verdict": {
            "issuer": issuer_verdict["issuer"],
            "verifier": issuer_verdict["verifier"],
            "protocol": issuer_verdict["protocol"],
        },
        "device_ceremony": (
            f"{TEST_DOUBLE_LABEL} — simulation, not a real biometric; "
            "testnet flow tests only"),
        "provenance": "TEST",
        "four_laws_beat": (
            "beat (2) of 4 — the bind ceremony. Beats (1) the doorway "
            "card and (3) the eFuse ignition are not this module's; "
            "(4) the 3D world entry follows the wallet going live."),
    }

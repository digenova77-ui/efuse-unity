// biometric_adapter.mjs — THIN ADAPTER over Grok's UnityIdIssuer.
//
// This file does not implement biometrics. It CALLS Grok's implementation:
//   ~/workspace/user/files/unity-id-issuer_4_y3wp.js  (UnityIdIssuer —
//   the WebAuthn registration ceremony, webauthn.create, with injected
//   webAuthnVerifier + assertionSigner).
//
// In this sandbox the issuer's adapters are NOT_CONFIGURED (by Grok's
// design the issuer then reports HOLE — it refuses rather than
// proceeding). The wallet auth path calls this adapter and treats HOLE
// as an honest refusal, never as a pass. The device-side half of the
// ceremony — the face/finger on the phone — is Grok's client code:
//   dccp-world/src/dccp/unity/unityid.ts::createPilotHandle
//   (navigator.credentials.create, platform authenticator)
//   drive-spine/.../dualis-unity-onboarding.js (passkey ceremony step).
//
// Commands:
//   status   — Grok's issuer's own honest verdict (READY or HOLE).
//   challenge — a registration challenge from Grok's issuer
//               (single-use, 5-min TTL; LOCAL_PREPARATION_ONLY while
//               the adapters are unconfigured).

import { UnityIdIssuer, localPreparationIssuer } from '/home/hatch/workspace/user/files/unity-id-issuer_4_y3wp.js';

const [cmd] = process.argv.slice(2);

function out(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

try {
  if (cmd === 'status') {
    // Grok's own honest mark: HOLE when the WebAuthn verifier and the
    // assertion signer are not configured — which is this sandbox.
    out({ ok: true, grok_issuer_status: localPreparationIssuer().status() });
  } else if (cmd === 'challenge') {
    const issuer = localPreparationIssuer();
    const ch = issuer.createChallenge();
    out({ ok: Boolean(ch.ok), grok_challenge: ch });
  } else {
    out({ ok: false, error: `unknown command ${JSON.stringify(cmd)}` });
    process.exitCode = 2;
  }
} catch (err) {
  out({ ok: false, error: String(err && err.message || err) });
  process.exitCode = 1;
}

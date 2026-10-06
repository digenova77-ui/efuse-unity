# PURITY.md — Absolute Unity Purity: The Standard and the Strip

**Status:** Phase 1 — standard defined, strip list documented. Phase 2 (per-component verdicts on workers 1–4 output) pending follow-up.
**Author:** Worker 5 (strip team).
**Provenance:** Everything stated here about Grok's live build is *derived-from-browser-report* — it comes from the parent agent's live-browser inspection of `https://yarrow-maple-prairie-ocean.grok.me` as summarized in the mission brief. It is not independently verified, and it is not presented as fact. It is enough to strip by: the strip targets behavior-class and content-class findings, not line-level claims.

---

## 1. The standard: absolute Unity purity

A component, string, or claim in unity-world is **pure** if and only if all of the following hold. If any fails, the thing is stripped — not fixed. (Purity is binary; a compromised element is discarded, never patched into purity.)

**P-1. Unity-bound identity.** One identifier, no exposed name. The binding surface carries the Unity ID only. Name-bearing or dark-ledger material never touches the client or any unauthenticated surface. (Grounded: David's Oct 1 dual-pipeline ruling — white ledger public, dark ledger vaulted; biometric material stays on-device.)

**P-2. DCLM-computed signed truth.** Every truth-claim — verdict, purity state, feed reading, readiness — is computed by the DCLM core and carries its signature. A claim without a signature is not purity; it does not render as truth.

**P-3. Relay-carried state.** State moves through the relay; it is not held, computed, or invented in the client DOM. The client is a mirror, not a mind.

**P-4. Honest provenance.** Every rendered fact carries source, timestamp, and signer. Claims about the old build that could not be re-verified are labeled `derived-from-browser-report`, never stated as fact.

**P-5. Thin client.** The client renders signed state and nothing else. Any client-side computation that affects trust state (gate passage, verdicts, purity, feed liveness) is impure by construction.

**P-6. UNKNOWN is a verdict, never PASS.** UNKNOWN never opens a gate, never signs, never certifies. It is the honest rendering of "not known," and it is always available as an alternative to theater.

**P-7. Testnet only.** No production endpoints, no real credentials, no biometric material off-device. `keys/` holds test keys. The biometric gate concept is sandbox-authorized only, per the biometric father approval (Oct 5, 2026).

**What does not belong:** dead code on a trust boundary · placeholder text presented as content · unsigned claims of purity · pending data framed as live · client-side authoritative computation · identity that leaks name or dark-ledger material · anything that performs purity without being signed purity.

---

## 2. The strip list

Each item: WHAT was stripped, WHERE it lived, WHY it violates purity, WHAT replaces it.

### a. Dead client-side gate JS
- **WHAT:** The "Look at the Earth" entry-gate click handler (and its class of client-side gate wiring).
- **WHERE:** Grok's entry gate. Four activation methods were attempted in the live browser; the gate never dismissed. *(derived-from-browser-report)*
- **WHY:** A gate that cannot dismiss itself fails its own contract. Dead code on a trust boundary is not inert — it is a curtain that looks like a lock. Under P-5 and P-6, client-side gate logic is impure by construction.
- **REPLACED BY:** Worker 2's server-side gate state machine in `~/workspace/unity-world/gate/`. Gate passage is computed and decided server-side; the client only reflects the state the relay carries.

### b. Placeholder Trinity verdict text
- **WHAT:** The string "The three umpires have not been asked on this view yet." and every placeholder of its class.
- **WHERE:** The Trinity verdict display in Grok's build. *(derived-from-browser-report)*
- **WHY:** Placeholder-as-content is theater. The string occupies the place where a verdict must either be signed (P-2) or marked UNKNOWN (P-6). Rendering "not asked" where an answer belongs trains the viewer to accept absence as content.
- **REPLACED BY:** Worker 1's DCLM compute core in `~/workspace/unity-world/dclm/` — real signed verdicts, or an explicit UNKNOWN marking. A bare placeholder never renders as a verdict again.

### c. Unsigned purity claims
- **WHAT:** The purity indicator block: "Purity holds. 0 force. Safe host. Truth or nothing. Cleanup first. These four lines are not signed." and "Purity has not pulsed."
- **WHERE:** Grok's purity indicators. *(derived-from-browser-report)*
- **WHY:** The build's own text confesses: the claims are not signed. Under P-2, an unsigned claim is not purity — and a purity claim that admits it is unsigned is a self-signed forgery of itself. Strip the claim, keep the honesty of the admission.
- **REPLACED BY:** Worker 1 — a DCLM-signed purity pulse, or UNKNOWN. "These four lines are not signed" may never ship in unity-world; it is the exact anti-pattern this document exists to kill.

### d. PENDING feeds inside a "live feeds" frame
- **WHAT:** The six feed slots (air, Moira River, earthquakes, ISS, Kp index, Britain grid carbon) rendered inside a "live feeds" frame while all showing PENDING / not live.
- **WHERE:** Grok's feeds panel. *(derived-from-browser-report)*
- **WHY:** The frame is the claim. A "live feeds" frame holding pending data asserts aliveness it does not have. The data isn't the lie — the container is. Under P-4 (honest provenance), a slot's aliveness is a signed fact or it isn't.
- **REPLACED BY:** Honest rendering (workers 1+4): a slot renders LIVE only with a real reading + timestamp + signature. Otherwise it renders PENDING (or ABSENT) in a frame that says exactly that. The word "live" appears only where aliveness is proven.

### e. Client-side truth/verdict/purity computation
- **WHAT:** Any JavaScript in the client that computes verdicts, purity state, or feed aliveness.
- **WHERE:** Grok's client bundle — the verdict display, purity indicators, and feed slots all rendered client-side without signed server truth behind them. *(derived-from-browser-report)*
- **WHY:** The client is a mirror, not a mind (P-3, P-5). Anything computed client-side is tamper-able, unsigned, and unaudited. Client-side truth is the single largest impurity class in the old build.
- **REPLACED BY:** Worker 1's DCLM compute core in `~/workspace/unity-world/dclm/`; state carried by the relay in `~/workspace/unity-world/relay/`; the client in `~/workspace/unity-world/client/` renders relay-carried signed state only.

### f. Further architecture that doesn't belong (strip-team judgment)

#### f-1. The untested "I agree" biometric button — client-side handler class
- **WHAT:** The client-side handler for the "I agree" button on the biometric gate.
- **WHERE:** Grok's entry gate (biometric step). *(derived-from-browser-report: untested — "biometric — not touched" — but same wiring class as the dead "Look at the Earth" handler, judged likely dead.)*
- **WHY:** Same failure class as (a). A handler that cannot be verified to fire cannot be trusted on a trust boundary. The biometric *concept* is kept (§4); the client-side *handler* is not.
- **REPLACED BY:** Nothing client-side. Biometric binding flows through worker 2's server-side gate (sandbox only, biometric material on-device, P-7) — or it does not ship. No unverifiable handler rides the trust boundary.

#### f-2. The connector-readiness theater
- **WHAT:** The string "Ready for 227 known countries and 1251 known cities. None of them have chosen."
- **WHERE:** Grok's connectors panel. *(derived-from-browser-report)*
- **WHY:** A registry of readiness with zero activations is inventory pretending to be infrastructure. The *data* (jurisdiction lists) is kept (§4); the "ready" *framing* is theater. Under P-4, readiness is per-jurisdiction state: signed and live, or UNKNOWN. "None of them have chosen" is the honest sentence in that string — the framing around it is not.
- **REPLACED BY:** The Atlas registry data re-homed under honest per-jurisdiction state in the relay (worker 3). No aggregate "ready" claim without signed activation behind it.

#### f-3. World rendered behind a gate that doesn't gate
- **WHAT:** The architectural fact that the full 3D world (Earth, control dock, Atlas panel) rendered fine behind an entry gate whose JS was dead.
- **WHERE:** Grok's build as a whole — the gate guarded nothing because it could neither open nor stay closed; the world was simply there. *(derived-from-browser-report)*
- **WHY:** A gate that doesn't gate is not security, it is a curtain. If passage is decided client-side (or by dead JS), the boundary is decorative. Under P-5/P-6, the render surface behind the gate must be *served* only on passing gate state — never present-and-hidden by CSS, never bypassable by navigating to the URL.
- **REPLACED BY:** Worker 2's server-side gate state machine: the world is served only on a passing state the relay carries. There is no client-side path to the world that skips the gate.

#### f-4. The string-inventory rule (generalization of b and c)
- **WHAT:** Any truth-claim string anywhere in the build that ships without a signature or an UNKNOWN marker — lorem, "coming soon" verdicts, "not asked yet," "has not pulsed," unsigned status lines.
- **WHERE:** Old-build content class; preventive rule for unity-world.
- **WHY:** Items (b) and (c) are instances, not exceptions. The rule is: a string that states a truth without provenance is stripped on sight. This is the strip criterion the builders enforce on their own output (§3).
- **REPLACED BY:** Signed claim or UNKNOWN marking. No third option.

#### f-5. Any name-leaking identity surface (preventive)
- **WHAT:** Any binding or display surface that exposes a name where the Unity ID alone belongs.
- **WHERE:** Not observed in the mission brief's findings — listed as a preventive criterion, not a confirmed finding. *(No derived-from-browser-report claim is made here.)*
- **WHY:** Absolute Unity (P-1): one identifier, no exposed name. If any name-bearing surface exists in ported code, it is stripped before it ships.
- **REPLACED BY:** Unity-ID-only binding surfaces per the dual-pipeline ruling: white-ledger identifier shown, dark-ledger material vaulted, nothing in between.

---

## 3. Strip criteria for the builders

Every deliverable from workers 1–4 must satisfy all of the following. Phase 2 audits each against exactly this list. A single failure = NEEDS-WORK with reasons; there is no partial purity.

1. **No dead controls.** Every button, gate, and switch has a verified executable path. A control that cannot fire is stripped or re-homed server-side. (Catches a, f-1.)
2. **No placeholder-as-content.** No lorem, no "not asked yet," no "has not pulsed," no TBA rendered where a verdict belongs. Signed verdict or UNKNOWN. (Catches b, f-4.)
3. **No unsigned claims.** Every truth-claim — purity, verdict, feed status, readiness, aliveness — carries a DCLM signature or is marked UNKNOWN. The sentence "these lines are not signed" must never be shippable. (Catches c.)
4. **No client-side authoritative computation.** The client renders; DCLM computes; the relay carries. Any trust-affecting computation in `client/` fails. (Catches e.)
5. **Honest provenance everywhere.** Source, timestamp, signer on every rendered fact. Claims about the old build that could not be re-verified are labeled `derived-from-browser-report`. (P-4.)
6. **UNKNOWN never PASS.** UNKNOWN never opens a gate, never signs, never certifies. It is always renderable and never gateable. (P-6.)
7. **Feed honesty.** LIVE renders only with real reading + timestamp + signature. Otherwise PENDING or ABSENT — never framed as live. (Catches d.)
8. **Gate integrity.** Passage is decided by the server-side state machine in `gate/`; the world behind the gate is served only on passing state; no client-side bypass path exists. (Catches a, f-3.)
9. **Testnet only.** No production endpoints, no real credentials, no biometric material off-device. `keys/` holds test keys. Biometric concept stays sandbox-fenced. (P-7.)
10. **Identity discipline.** Unity ID only on the binding surface; no name exposure; no dark-ledger material on the client. (Catches f-5, P-1.)
11. **No theater.** Any element that performs purity without being signed purity is stripped. When in doubt, the strip team decides, and the strip team's bias is toward the garbage can.
12. **Strip receipts.** Each worker notes what they removed or refused to port in their own deliverable notes. Phase 2 reconciles those receipts against §2.

---

## 4. Kept list — what survives the strip and why

| Kept | Why it survives |
|---|---|
| **The Unity ID binding concept** — one identifier, no exposed name | It is the core of absolute Unity (P-1). Matches David's dual-pipeline ruling: white-ledger identifier, dark-ledger vaulted. The *concept* was sound; only unverifiable client handlers around it are stripped (f-1). |
| **The 3D world rendering** — three.js Earth, control dock | Rendering is not truth. A renderer that displays signed state is a pure mirror. The render layer is kept strictly as a mirror (P-3, P-5); workers 1+4 must enforce that it computes nothing. Phase 2 will verify. |
| **The Atlas registry data** — 21 Unity chambers, RTE rooms, sector layers, 24 country jurisdictions, DCLM/DCCP modules | Data is not architecture. The registry's content is kept and re-homed under honest per-jurisdiction state (see f-2). Only the readiness-theater framing is stripped. |
| **The verdict pipeline concept** — the Trinity, three umpires | The concept is sound; only the placeholder implementation is stripped (b). Real verdicts flow from the DCLM core through the Trinity frame, signed. |
| **The relay** — relay-carried state | State must be carried, not client-held (P-3). The relay is the transport of signed truth between DCLM, gate, and client. |
| **The biometric gate concept** | Kept under the sandbox fence: biometric father approval (Oct 5, 2026) authorizes it for testing only; biometric material stays on-device; it fails closed outside the sandbox (P-7). The concept is sound; the dead client wiring is not (f-1). |

---

## 5. Phase 2 — pending

When all build workers deliver, this document gains a per-component verdict table in the four buckets of §7 (KEEP / EVOLVE / FIX / FALSE GOLD), audited against §3 criterion by criterion. Components: `dclm/` (compute, meter, rights/writes, data, winter, tap, tokenize, share), `gate/`, `relay/`, `client/`, `data/`, `economics/`, `purity/` (the index measures; this document judges).

## 6. Provenance & judgment log (Phase 1)

- J-1: Claims about Grok's build are marked `derived-from-browser-report` throughout; nothing about that build is asserted as independently verified fact.
- J-2: The "I agree" button is judged *likely* dead (same wiring class as the confirmed-dead "Look at the Earth" handler), not *confirmed* dead — the report says it was untested. It is stripped as a class member, not as a confirmed instance.
- J-3: The string-inventory rule (f-4) generalizes b and c into a preventive criterion — deliberate, because the old build's failure was a pattern, not two strings.
- J-4: The 3D render layer is kept as a "pure mirror" on the condition that it computes nothing — a condition Phase 2 must verify, not assume.
- J-5: Connector readiness text is classified as theater-framing around kept data, not as stripped data — the jurisdiction lists survive, the "ready" claim does not.
- J-6: The biometric concept is kept only inside the sandbox fence (testnet, on-device biometrics, fails closed) per the biometric father approval law. Any productionward drift fails criterion 9.

---

## 7. The standing disposition law (David, 2026-10-06 — verbatim)

**Keep it. Evolve what's next. Fix what's fixable. Throw out what's false gold.**

This is the purity law operationalized. Every component runs through this filter before it ships. Phase 2 verdicts are delivered in these four buckets:

- **KEEP IT:** what's working, what's pure, what's verified — keep. Don't rebuild what holds.
- **EVOLVE WHAT'S NEXT:** the build moves forward, always. Benchmark, reference, evolve — no rebuilding without improving.
- **FIX WHAT'S FIXABLE:** real bugs, broken handlers, honest gaps — fix them. (Like Grok's dead gate button: fixable.)
- **THROW OUT WHAT'S FALSE GOLD:** anything that looks valuable but isn't real — placeholder text posing as verdicts, unsigned claims posing as purity, PENDING feeds posing as live, modeled figures posing as reported. If it glitters but isn't true, it's out. No repair, no negotiation — discard.

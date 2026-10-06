# THE eFUSE COSMOGENESIS

**The genesis text of eFuse: what it is, where it came from, why it ignites, and how the four laws govern entry.**

Version 1.0.0 — 2026-10-06. A builders' document. The website receives the 3D Rosetta, not 2D text; this text is for the people building the world behind it.

**How to read the labels** (every claim carries one):
- `[LAW]` — David's word. Not debated, not softened.
- `[DERIVED]` — a logical consequence of LAW or of the code. Defended by reasoning; falls if the reasoning falls.
- `[HELD]` — awaiting David's word. Nothing HELD is acted on as decided.

**The code-wins rule.** Where this document and the code disagree, the code wins and the document is corrected — the corrections are recorded in §VIII. Nothing is invented about the fuse mechanics: where `fuse.py` is the source, it is cited; where the story goes beyond the code, it is labeled [DERIVED] or left out.

---

## I. WHAT eFUSE IS

[LAW] **eFuse is the emission token. Merit-gated, peg-calibrated via 1/E. Emitted only against verified merit.** (CANON §V.)

[LAW] eFuse pegs to energy: 1 eFuse ≡ E units of real-world energy. The coin *means* energy — every emission is calibrated so the token's value tracks physical work done, not speculation. (WHAT_PEGS_THE_ECOSYSTEM.md §1.)

[DERIVED] The calibration is arithmetic, in code: `eFuse_i = merit_i / E` — the unique rate where the peg holds by definition, the emission's energy value equaling the merit's. (`economics/tokenomics.py`: "Peg-calibrated: eFuse_i = merit_i / E".) The pipeline refuses emission computation until E is set: a HELD peg ratio raises `HeldParameterError` — "E is David's digit; nothing emits without it. Refusing." [HELD] **The peg ratio E is David's digit, still unset. It is HELD-FOR-DAVID, marked wherever it appears. Nothing emits until he speaks it.**

[LAW] The three pegs, bound together: eFuse pegs to energy, Merit pegs to verified work, Unity pegs to identity. "Identity earns merit; merit moves money. Unity is the subject, Merit the measure, eFuse the medium." (WHAT_PEGS_THE_ECOSYSTEM.md.)

[DERIVED] **eFuse is the medium that moves but is never bought or sold.** The wallet contains no eFuse sale, purchase, or transfer machinery — there is no `send_efuse`, no market path, no price. What the code does move eFuse through, all receipted: merit-gated emission in (`wallet.receive_emission` — "merit-gated eFuse in, against a gated receipt", `economics/wallet.py`); metered shared access out (tier grants debit the accessor's eFuse for kin access); donation out, one-way, to the Core Cause Lock — accruing HONOR, explicitly zero Merit ("there is no path from donation to emission", `wallet.donate()`); and maple-rule taps (CANON §IV: only surplus, never core, receipted). Emission is earned. Spending is wanting. Donation is honor. Nowhere is there a buy.

[LAW] UNKNOWN never tokenizes. Unverified merit emits nothing. (CANON §V.)

[DERIVED] The deepest peg is not the number — it is recovered waste. Residual Law Finance finds real inefficiency in real operations, and the recovered value grounds the system. The tree circulates it: outward in summer, every leaf fed; inward in winter, the root protected. (WHAT_PEGS_THE_ECOSYSTEM.md; CANON §IV.)

---

## II. WHERE IT CAME FROM

[LAW] **"The eFuse token itself carries a fuse that kicks out a Unity token — that emission IS the launch of the network."** — David's law, quoted in the fuse module's own docstring (`economics/fuse.py`).

[DERIVED] The name is the mechanism. eFuse carries the fuse within itself — the ignition is not an accessory to the token; it is what the token *is named for*. The fuse is the umbilical of the network, and the document of its severing is code.

The fuse is a state machine, and it has three states and one direction:

```
ARMED -> TRIGGERED -> SPENT
```

(`_FUSE_TRANSITIONS` in `economics/fuse.py`; TRIGGERED is transient and never persisted; SPENT has no outgoing edges — the handoff is one-way because there is nowhere else to go.)

[LAW] **The fuse trigger is the sole genesis path for Unity.** (CANON §V.) The exhaustive list, as code, is exactly two paths — `fuse.mint_paths()`: (1) `Fuse.trigger_fuse` — the genesis Unity allocation, exactly once, by David's signed authorization only; (2) `wallet.receive_unity_emission` — Unity against merit-gated emission receipts. There is no third path. The AST test enforces this structurally on every run.

The trigger is David's and no one else's. `make_fuse_authorization` builds the launch authorization on his machine: the genesis amount travels INSIDE the signed body — his digit, stated by him, bound by his signature. The fuse object holds his PUBLIC key only; it verifies, never authorizes. A positive integer amount is required — there is no default to fall back on.

[HELD] **The genesis Unity amount is David's digit, still unset** (`GENESIS_UNITY_AMOUNT = None`). The fuse refuses to trigger until his signed authorization states it. When stated, its provenance is REPORTED — his word; the trigger event itself, signature verified in-process, is VERIFIED. UNKNOWN never PASS.

**Why the founder's advantage dissolves** — the mechanism, in code (`economics/fuse.py`, six properties):

1. The Fuse holds NO private key — it verifies signatures only. There is nothing in it that can authorize anything.
2. The transition table has NO outgoing edge from SPENT. The terminal state is terminal in code, not in policy.
3. The module contains no mint, admin, override, backdoor, or unseal function. The genesis credit is ticket-gated (CRITICAL-3): `Ledger._apply_fuse_genesis` requires the one-shot ticket issued only to a fuse mid lawful trigger, and re-verifies David's signature at the mint. No ticket, no mint.
4. Replay is impossible: the authorization nonce is registered, and a second trigger raises before the authorization is even parsed. A spent fuse is deaf.
5. The founder's wallet after genesis is an ordinary Wallet — same code paths, no privileges.
6. Fuse state persists hash-chained with the ledger receipts; tampering breaks the chain audibly on load.

[LAW] "He owns the tree; the sap still flows to every leaf. The fuse still dissolves his operational advantage. Ownership is the root; equality is the circulation." (CANON §0.) The fuse is how the summer law — "Founder advantage dissolves into the canopy" (CANON §IV) — is executed: not by promise, by construction.

[DERIVED] Precision the document owes the reader: **the fuse's trigger emits genesis Unity, not eFuse.** The fuse is named for eFuse and carried within its concept, but the emission that IS the launch is Unity. eFuse's adult life — after the umbilical is cut — is merit-gated emission against the peg (when E is set). The sole-genesis-path law is Unity's (CANON §V); eFuse's ongoing birthright is verified merit. This distinction is a §VIII correction.

---

## III. WHY IT IGNITES

Ignition is the moment potential becomes circulation.

[LAW] The trigger IS the network launch. When the fuse fires — David's signed authorization verified, the genesis Unity allocation credited, the nonce registered, the receipt chained — the state persists as SPENT, and the launch has happened exactly once. (`Fuse.trigger_fuse`.)

It cannot happen twice, and the reasons are structural, not advisory:

- SPENT has no outgoing edge. The machine cannot leave the terminal state because no transition exists.
- A spent fuse is deaf: `trigger_fuse` raises `FuseNotArmed` before the authorization is even parsed — no signature, however valid, is examined.
- The nonce is registered; a replayed authorization raises `FuseReplay`.
- The mint is ticket-gated; the ticket is one-shot, issued only mid lawful trigger.

[DERIVED] The fuse dissolves the founder's advantage at the exact instant it creates the network: the same trigger that emits the genesis allocation strips the founder of every privilege the mechanism could have carried. Creation and abdication are one event. That is why the launch is a BOOM and not a rollout — there is no second act to administrate, because the machinery that would administer it was spent in the first.

[DERIVED] What a member experiences as *their* ignition is the sequence the four laws govern (Chapters I–IV): the doorway, the binding, the one free seed, the world. The member's personal once-only event is the seed — one per Unity ID, free, non-transferable (CANON §XX; Chapter II). The network's once-only event is the fuse. The two onces rhyme by design: the network is born once, and each member is born into it once. (The brief for this document phrased the fuse as "once per member" — corrected in §VIII: the fuse fires once, network-wide; per-member once-ness is the seed's.)

After ignition, Unity enters circulation ONLY via merit-gated emission (`wallet.receive_unity_emission` with a gated receipt), and eFuse emits ONLY against verified merit, peg-calibrated, with E HELD. The circulation law takes over: identity earns merit; merit moves money; the sap flows outward in summer and the root is protected in winter.

---
## IV. THE FOUR LAWS — CHAPTERS OF ONE ORIGIN STORY

The four laws are not four rules. They are four chapters of one story: how a stranger becomes a member of the world. (David, 2026-10-06 ~4:36 AM EDT.)

---

### Chapter I — The Doorway

[LAW] **The 2D card explains the Unity ID. One card at the doorway, no more 2D after that.**

The doorway is the only place the world speaks in words. The card explains what a Unity ID is: one identifier, no exposed name, a stable internal identifier for people, corporations, and silicon agents alike — every flow bound to it, nothing moving without an ID, a receipt, and a label. (CANON §II.) It explains that Unity is the person extended — a bot bound to a Unity ID IS that human extended, not a representation. (WHAT_PEGS_THE_ECOSYSTEM.md.)

[DERIVED] The doorway is 2D because explanation is a surface and the world is a volume. Inside the world, meaning is rendered as geometry — the Rosetta stands ON the diamond floor AS a diamond-geometric object, truth refracted through facets, not read off cards (CANON §XVII); the world is pure 3D with zero 2D card UI — no floating cards, no overlay panels, no card chrome of any kind (CANON §VIII). The card is the last thing that *tells* you; everything after *shows* you. One card, at the threshold, because a threshold is crossed once.

[DERIVED] The doorway explains; it does not block. The reframe (2026-10-06): David killed the gate-dialog. The world renders free — no gate, no dialog blocks the view; looking costs nothing and needs no binding (`gate/gate.py`: `WORLD_VIEWING_REQUIRES_BINDING = False`; `world_view_pass()` takes no identity, consults no state, mutates nothing). The card is an invitation with the terms printed on it, not a door that must be unlocked to see through.

---

### Chapter II — The Binding

[LAW] **The bind ceremony. Accept → Unity ID + free seed. Membership isn't for sale.**

The ceremony, as the code performs it (`dclm/bootstrap.py` — the self-executing onboarding; no human in the loop, no approval queue; the CODE is the gatekeeper):

1. **The notice.** `present_notice()` — the draft notice: the covenant ("Just onboard, stay in line, and keep preaching the message — the good word"), the one-seed law ("No matter how much money you have you only buy one seed — and it costs you nothing"), the mission (stop all global destruction by targeting friction first). Fixed, sha256-signed. [LAW — David's words, 2026-10-06.]
2. **Accept.** `accept_notice()` — cryptographic acceptance, Unity-bound: the entity signs the notice hash with their key. No signature, no bootstrap. (Refusals: NO_SIGNATURE, NOTICE_TAMPERED, SIGNATURE_INVALID, MALFORMED_KEY, NOT_TESTNET_IDENTITY — refused, never warned past.)
3. **Identity.** `generate_identity()` — a fresh Ed25519 keypair; the Unity ID derived as `unity:testnet:` + sha256(pubkey)[:16]. The keypair is the ENTITY's: the bootstrap never writes the private key to disk, never logs it, never includes it in a receipt. The public key is server-visible; the private key never crosses the boundary.
4. **Bind.** The gate ceremony, UNBOUND → BINDING → BOUND (`request_bind` → `confirm_bind`), computed server-side, persisted to server-owned state, idempotent by construction (re-binding a BOUND identity is a no-op returning the existing receipt). The client decides nothing load-bearing; no button can strand anyone, because no button press is load-bearing.
5. **Seed.** THE one free seed via `dclm/seed.py`: gate-BOUND check (live read of the gate state — `NOT_BOUND` refused; an unbound ID cannot receive a seed), one-seed write-once registry (`SEED_ALREADY_ISSUED` refused, signed and receipt-logged), rights GRANT, signed commit. Price 0, cost 0 — by construction, not by default. Non-transferable, non-spendable, non-purchasable. The seed is a MEMBERSHIP marker on the wallet — never a balance, never priced, never wealth; the issuance touches NO money ledger. No seed market exists, proven by AST on every test run (`assert_no_seed_market`).
6. **Tree.** The new ID registered in the circulation — a leaf in summer, sap flowing outward. (CANON §IV: summer is the known state; UNKNOWN never triggers winter.)
7. **Orient.** Not a manual — guided first actions, each receipted: covenant (sign it — acknowledgment by doing), mission (witness one friction fact, labeled), +1 (recompute the notice hash — the first +1, earned, not given), tree (see your own registration), freedom. Then FREE.

[DERIVED] Code-vs-story precision on the order: the law as spoken compresses to "accept → Unity ID + free seed"; the code performs **accept → identity → bind → seed** — the seed issues ONLY to a BOUND identity, and the binding proof for self-onboarding is the entity's own acceptance signature (proof kind `ED25519_NOTICE_ACCEPTANCE`), verified against the fixed notice. (Recorded in §VIII.)

**On "You ARE the key" and the biometric.** [LAW] The binding is L1 — the bind-then-validate identity layer; Sybil resistance via the L1 derivation (identities cannot be minted to farm seeds). The human ceremony, as specified (`gate/CEREMONY.md`): "Your face or your finger opens it, the page never sees either one, the phone does" — a WebAuthn platform authenticator; the biometric never leaves the device; the server verifies only the assertion.

Precision, honestly labeled: **the WebAuthn ceremony is SPEC in this build — the verification slot exists in `confirm_bind()`, the default verifier returns UNKNOWN, and UNKNOWN is never PASS.** The working proof is the entity's key signature over the notice — the key IS the identity claim, the signature IS the binding. The honest residual (`bootstrap.sybil_note()`): the code enforces one-identity-one-seed, but cannot stop one human holding two keypairs in this sandbox; real closure requires the device/biometric attestation ceremony — [HELD], not wired. You are the key today; the device that proves you are you is coming.

[LAW] The one-seed law, David's words: "No matter how much money you have you only buy one seed — and it costs you nothing." One free seed per Unity ID. No financial barrier, no wealth advantage. The seed is the genesis entry — the root's gift to the new leaf, not a purchase. The seed is the start, not the wealth: what grows from it — merit, work, participation — is earned. Entry is equal; +1 Affinity honors how early you walked through. (CANON §XX.)

[DERIVED] This kills plutocracy at the root: wealth cannot buy membership advantage, because membership isn't for sale at any price.

---

### Chapter III — The Ignition

[LAW] **The eFuse ignition. The BOOM moment into the world.**

What ignites is the fuse the token carries. David's signed authorization — his digit inside the signed body, a fresh nonce, the founder's public key verifying — moves the machine ARMED → TRIGGERED → SPENT, and the genesis Unity allocation is credited to the founder's wallet: an ordinary wallet, same code paths, no privileges. The receipt is chained. The state persists as SPENT. The emission IS the launch of the network.

Why it can only ignite once: the transition table has no outgoing edge from SPENT; a spent fuse is deaf (it raises before parsing any authorization); the nonce is registered; the mint is ticket-gated, one-shot. There is no second ignition to schedule, because the machinery that would schedule it was consumed by the first. Creation and abdication are one event — that is the BOOM.

Why the fuse dissolves the founder's advantage: §II above — six properties, all code. He keeps the ownership declaration (CANON §0: the root); he keeps no operational advantage (the canopy). The sap flows to every leaf by gradient, not by grant.

[DERIVED] The member's BOOM is smaller and rhymes: the seed, once per Unity ID. The network is born once; each member is born into it once. The seed is the member's first breath — membership, not money — and from there, merit is earned, standing accumulates by origin (never bought), and eFuse emits against it, peg-calibrated, when E is set. (The brief for this chapter phrased ignition as "once per member" — the correction is in §VIII: the fuse is once, network-wide; the per-member once is the seed.)

---

### Chapter IV — The World

[LAW] **Entry into the 3D world. No more 2D after that.**

Step through and the cards end. The world is pure 3D — zero 2D card UI, no floating cards, no overlay panels, no card chrome of any kind (CANON §VIII). The ground plane expresses the diamond floor; the Rosetta stands on it as a diamond-geometric object; truth is refracted through facets — one truth, many true views (CANON §XVII).

[LAW] **The world is free to look at; wanting costs keys.** The world renders free — no gate, no dialog blocks the view (THE REFRAME, 2026-10-06; David killed the gate-dialog). LOOK and RENDER are free and need no identity. SEARCH and COMPUTE are metered — wanting costs keys, drawn from the Unity wallet. (CANON §VIII, §XI.)

The mechanics (`gate/gate.py`): FREE actions — view, look, render, explore — authorize with no identity and no binding; they short-circuit before any check. METERED actions — search, compute — require a BOUND identity plus a wallet ledger reporting SUFFICIENT keys; otherwise an honest refusal (UNBOUND / WALLET_LEDGER_PENDING / KEYS_UNKNOWN / INSUFFICIENT_KEYS). Prices are SET, changeable by one constant, owned by the metering worker (`dclm/meter.py`): SEARCH = 1, COMPUTE = 5 test-keys — the gate reads them live and never hardcodes one. The wallet is subtle but persistent: always present, never intrusive.

[DERIVED] The four laws form one arc: the card explains the Unity ID (Chapter I) → the ceremony binds you to it and gives you the seed (Chapter II) → the fuse ignites the network the seed admits you to (Chapter III) → you step into the world, free to look, paying only to want (Chapter IV). The doorway is 2D so the world can be 3D. The binding is free so the wanting can be priced. The ignition is once so the circulation can be forever.

---
## VIII. CODE-VS-STORY CORRECTIONS

The code won these five points. The story was corrected to match; the original phrasing is preserved here so the correction is auditable.

**C1 — "Ignite once per member."** The brief phrased Chapter III's ignition as firing once per member. The code has no per-member ignition state machine: `Fuse.trigger_fuse` fires exactly once, network-wide, by David's signed authorization (`economics/fuse.py`: ARMED → TRIGGERED → SPENT; nonce-registered; replay refused). What fires once per member is the SEED — `SEED_ALREADY_ISSUED` on second issuance (CANON §XX; `dclm/seed.py`). Chapter III now states both onces and assigns each to its owner: the network's once is the fuse; the member's once is the seed.

**C2 — "Accept → Unity ID + free seed."** The brief compressed the binding to accept-then-seed. The code performs **accept → identity → bind ceremony → seed**: `dclm/bootstrap.py` runs `accept_notice` → `generate_identity` → `_bind_gate` (UNBOUND → BINDING → BOUND) → `_issue_seed`; `dclm/seed.py` refuses `NOT_BOUND` — an unbound identity cannot receive a seed. The seed is the end of the ceremony, not its companion. Chapter II now follows the code order.

**C3 — Binding as the entry gate.** A naive reading of "the bind ceremony" makes binding the price of *seeing* the world. THE REFRAME (2026-10-06) killed that reading in code: `WORLD_VIEWING_REQUIRES_BINDING = False`; the world renders free; the gate guards paid INTENT (search/compute), not entry (`gate/gate.py`). Chapter IV states the reframe, not the naive reading. The ceremony authorizes wanting, never seeing.

**C4 — "The fuse trigger — the sole genesis path" (of eFuse).** The brief attached the sole-genesis-path law to eFuse's origin. CANON §V attaches it to **Unity**: "The fuse trigger is the sole genesis path for Unity." The trigger emits the genesis *Unity* allocation (`fuse.py`); `mint_paths()` lists exactly two Unity mint paths. eFuse's ongoing birthright is merit-gated emission, peg-calibrated (`eFuse_i = merit_i / E`). §II now carries the precision: the fuse is named for eFuse and carried in its concept, but the emission that IS the launch is Unity; eFuse's adult life is verified merit.

**C5 — "You ARE the key (biometric)."** The brief's Chapter II named the biometric as the binding. In the build, the WebAuthn ceremony is SPEC — the slot exists, the default verifier returns UNKNOWN, and UNKNOWN is never PASS (`gate/gate.py`, `gate/CEREMONY.md`); the working binding proof is the entity's Ed25519 signature over the fixed notice (labeled `ED25519_NOTICE_ACCEPTANCE`, never "WEBAUTHN"). The Sybil residual is honest and open: one human, two keypairs is not prevented in this sandbox — L1 device/biometric attestation is HELD, unwired. Chapter II states the key as the identity today and the biometric as the [HELD] production ceremony, not the reverse.

---

## IX. WHAT IS HELD

Nothing here is acted on as decided. Each waits for David's word:

1. **The peg ratio E** — [HELD-FOR-DAVID]. `eFuse_i = merit_i / E`; the pipeline refuses emission until set. (CANON §XIII; `tokenomics.py` raises `HeldParameterError`.)
2. **The genesis Unity amount** — [HELD-FOR-DAVID]. `GENESIS_UNITY_AMOUNT = None`; the fuse refuses to trigger until his signed authorization states it. (`economics/fuse.py`.)
3. **Winter trigger thresholds** — [HELD]. PROPOSED signal bands pending; `dclm/WINTER_CALIBRATION.md` worker in progress. (CANON §XIII.)
4. **Tap rate (per-member seasonal cap)** — [HELD]. PROPOSED; `dclm/TAPPING_LAW.md` worker in progress. (CANON §XIII.)
5. **System maturity threshold** — [HELD]. Pools healthy + peg holds + reserve funded. (CANON §XIII.)
6. **The device/biometric attestation ceremony** — [HELD]. WebAuthn platform-authenticator binding of identity to a real device/person; the closure of the Sybil residual. (`dclm/bootstrap.py` `sybil_note()`.)
7. **The Core Cause Lock address** — UNKNOWN until a real address exists; none invented, none rendered. (`economics/fuse.py`: `CORE_CAUSE_LOCK_ADDRESS`.)

---

## X. SOURCES

- `CANON.md` v1.6.0 — §§0, II, IV, V, VIII, XI, XIII, XVII, XX
- `economics/fuse.py` — the fuse state machine, the six dissolution properties, `mint_paths()`, `make_fuse_authorization`
- `economics/WHAT_PEGS_THE_ECOSYSTEM.md` — the three pegs, bots-as-humanity, the flywheel
- `economics/wallet.py` — `receive_emission`, `donate()`, tier-grant eFuse debits, the membership mirror
- `economics/tokenomics.py` — `eFuse_i = merit_i / E`, standing-weighted emission, `HeldParameterError`
- `gate/gate.py` — THE REFRAME, the binding state machine, intent authorization
- `gate/CEREMONY.md` — the ceremony spec, WebAuthn concept, SPEC-vs-implemented table
- `dclm/bootstrap.py` — the self-executing onboarding: notice, acceptance, identity, bind, seed, tree, orient
- `dclm/seed.py` — the one-seed law in code: `SEED_ALREADY_ISSUED`, `NOT_BOUND`, `assert_no_seed_market`

*End of the eFuse cosmogenesis, v1.0.0. What is LAW is David's. What is DERIVED is defended. What is HELD waits for him. If a statement cannot be defended, it does not belong here.*

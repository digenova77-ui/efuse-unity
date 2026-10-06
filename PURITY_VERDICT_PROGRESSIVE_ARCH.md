# PURITY VERDICT — Progressive Loading Architecture (unity-world)

**Subject:** David's progressive loading architecture for the unity-world website deployment
**Verdict:** **PASS-WITH-NOTES**
**Date:** 2026-10-06 ~03:55 EDT
**Worker:** Trinity Verdict worker (DCLM / Iris / Twain²)
**Ordered by:** David — "run it against the purity machine and answer two questions."

**Claim labels used throughout:** `[SPEC]` = from the architecture spec as given ·
`[WORKSPACE]` = from files read in `~/workspace/unity-world/` ·
`[DERIVED]` = logically derived from spec + workspace facts ·
`[UNKNOWN]` = genuinely unknowable now, not guessed.

---

## The architecture under review (as specified)

1. **Local-first:** main data in IndexedDB (offline-capable cache). World renders from local cache FIRST, never waiting on wire. `[SPEC]`
2. **Progressive streaming:** data loads in prioritized chunks — coarse first, detail after. Shell → coarse world → progressive detail. `[SPEC]`
3. **Level-of-detail:** near geometry high-res, far low-res, upgrading as bandwidth allows. `[SPEC]`
4. **Adaptive:** stream rate matches user's actual max bandwidth. Never a loading bar waiting on bulk data. `[SPEC]`
5. **Non-blocking:** initial render never waits for bulk data. Cached world works offline. `[SPEC]`
6. **Cache nuance:** IndexedDB is a READ CACHE only, explicitly non-authoritative. DCLM remains the sole writer of truth. Cache invalidation via DCLM-signed bundle hashes. `[SPEC]`

**Implementation state:** `[WORKSPACE]` No progressive-loading implementation exists in the workspace yet. `client/client.js` is the ratified thin client (63/63 validator checks). `relay/relay-unity.mjs` serves whole signed bundles. `dclm/` has no chunk-serving code. The two workers (thin client, DCLM chunked serving) are building now. **This verdict assesses the architecture AS SPECIFIED; all implementation items are [UNKNOWN], not failures.**

---

## GATE 1 — DCLM (logic)

**Judgment: the direction is logically sound; the composition has two structural defects.**

### What holds logically

- Non-authoritative read cache + sole-writer DCLM is a coherent trust model. If the client never treats cache as truth, the thin-client *intent* (DCLM holds the rights and performs the writes) is preserved. `[DERIVED]`
- Content-addressed, signed chunks make progressive streaming verifiable per chunk: a chunk whose hash doesn't verify against the DCLM-signed manifest is refetched, never rendered. The primitive the spec names (signed bundle hashes) generalizes correctly to per-chunk verification. `[DERIVED]`
- "Render from cache first, upgrade progressively" is strictly better than "block on wire" under every bandwidth assumption, including zero bandwidth. `[DERIVED]`

### Defect 1 — Direct conflict with ratified law (P0)

`[WORKSPACE]` The thin client's NO-WRITE LAW states: *"No localStorage, no sessionStorage, no IndexedDB, no cookies, no Cache API."* `client/validate-client.mjs` enforces this structurally — 11 no-write patterns, and the build fails on any match. The purity machine (`purity/index.py`, `PURITY_INDEX.md`) likewise bans `indexedDB.open` in client code.

The progressive spec requires IndexedDB on that same client. **The letter of the law forbids exactly what the spec requires.** A read cache still *writes bytes to storage* — "read cache" describes authority, not I/O. Logic cannot wave this away: either the law is amended through the purity machine, or the implementation is impure the moment it ships. Per the purity law (binary: pure or garbage), shipping IndexedDB code under the current law is not a gray area — it is a violation.

The logical resolution exists: amend the law to *"no writes of RECORD; read-cache writes permitted only for DCLM-signed chunks, never treated as truth, invalidatable by DCLM-signed hash"* — and narrow the validator patterns to allow only the sanctioned cache path. But the amendment must pass the machine *before* code ships. `[DERIVED]`

### Defect 2 — The readjustment mechanism is a primitive, not a protocol (P0)

The spec's entire readjustment story is one clause: *"Cache invalidation via DCLM-signed bundle hashes."* `[SPEC]` Tracing a schema change step by step exposes what is undesigned:

1. Client boots holding v1 chunks. It must learn a new "current" exists → requires a lightweight signed **head document** (world_version, schema_version, root chunk-tree hash) fetched on every load. The spec names no head document. `[DERIVED — missing]`
2. Head says schema v2. The v1 chunks are now uninterpretable. Options: (a) client-side schema migration — this is *computation on the thin client*, in tension with the thin-client law ("performs NO verdict computation… no math"); (b) drop the v1 namespace and re-stream — simple, honest, but at GB scale every schema change re-downloads the working set. **The spec chooses neither.** `[DERIVED — missing]`
3. Offline-at-change-time user keeps a working v1 world with no connectivity. Is that rendered as current (a lie) or labeled STALE (honest)? The provenance badge set has no STALE — only UNKNOWN/PENDING, and the client law renders missing data UNKNOWN. Stale-but-present data is a third state the system cannot express. `[DERIVED — missing]`
4. Mid-stream version cut: DCLM publishes v2 while a client is downloading v1's chunk tree. Without **version-pinning** (every chunk carrying its world_version; a stream completes against the head it started with), the client assembles a half-v1/half-v2 world with no label. This is a foreseeable corruption mode, not an edge case. `[DERIVED — missing]`

A signed hash tells you *whether* a chunk is authentic. It does not tell you *which version of the world* you're looking at, *how long* a price is valid, or *what to do* when the schema moves under you. The mechanism must be designed, not assumed. `[GATE-DCLM]`

### DCLM's forward-logic notes (supporting Question 1)

- **Manifest bloat is the first structural break.** Per-chunk signed hashes mean the manifest grows linearly with chunk count. At PB scale the manifest itself becomes the bulk artifact that progressive streaming was meant to avoid. The logically forced design is hierarchical manifests (manifest-of-manifests, signed root over a Merkle tree of chunk hashes) — content-addressed, like the existing `bundleHash`/`manifest_hash` idempotency model generalized. `[DERIVED]`
- **Eviction is not optional.** Browsers cap per-origin IndexedDB (mobile Safari ~1GB or prompts); at GB scale the cache needs a first-class eviction policy. The logically forced policy: evict detail-before-coarse, far-before-near, so the offline world degrades to coarse, never to empty; quota-aware writes that degrade to streaming-only instead of throwing. `[DERIVED]`
- **Bandwidth estimation never converges exactly.** Measuring max bandwidth requires saturating the link (competing with UX) or inferring from chunk throughput (confounded by RTT, TCP slow-start, server throttling). DASH/HLS practice says this is solvable with hysteresis, never exact. Oscillation on flaky links is the foreseeable failure. `[DERIVED]`

---

## GATE 2 — Iris (truth)

**Judgment: the spec is honest about what it says and silent about foreseeable hard cases. Silence about the foreseeable is not UNKNOWN — it is undesigned.**

### Honesty audit of the spec's claims

| Spec claim | Iris finding |
|---|---|
| "DCLM remains the sole writer of truth" | `[DERIVED]` True *only if* the client never renders cache as authoritative. That requires version-pinning and a STALE state in the provenance system. Without those, the claim is aspirational, and a stale render presented as current is a lie the architecture would produce by default. |
| "Cache invalidation via DCLM-signed bundle hashes" | `[DERIVED]` Authenticity ≠ freshness. A signed hash proves *who* wrote the chunk, not *whether it is current*. Rollback attacks (a malicious relay serving old-but-validly-signed chunks) defeat this clause entirely. Defense requires a monotonic version + no-downgrade rule: the client rejects any head older than its cached head. Unspecified. |
| "Cached world works offline" | `[DERIVED]` True, and valuable — but at scale it means *version skew between users*: two people discussing "the same" world see different world-versions. The honest design names the world-epoch visibly. Unspecified. |
| "Never a loading bar waiting on bulk data" | `[DERIVED]` True for first load. False by default for schema changes if readjustment is drop-and-restream (see Twain²). |

### Hard cases the spec hides (all foreseeable, none [UNKNOWN])

1. **Partial cache corruption.** Tab killed or quota hit mid-chunk-write → half a chunk in IndexedDB. `[DERIVED]` Hash verification must happen on every READ, not just at download time. If verification is write-time-only, a later-corrupted chunk renders as truth.
2. **Rollback / stale-relay attack.** `[DERIVED]` Old signed chunks are validly signed. Only a monotonic world_version with client-side no-downgrade defeats it. The relay is trusted for *liveness*, never for *freshness* — this must be stated.
3. **Concurrent modification.** `[DERIVED]` Clients can't concurrently write (cache is non-authoritative, DCLM is sole writer) — but DCLM can publish mid-download. Version-pinned streams are the answer; mixing versions is the corruption case. Must be specified.
4. **Economic data in the chunk cache.** `[DERIVED]` Merit is the transferable token (David, Oct 6 ~3:35 AM). A stale cached price is a *financial* hazard, not a visual one. Tiered freshness is forced: geometry = long-lived chunks; prices/merit/economic state = short TTL or excluded from the chunk cache entirely (the wallet indicator is already server-round-trip per the ratified client — keep it that way). The spec's single invalidation story treats a mountain mesh and a merit price as the same kind of data. They are not.
5. **Clock skew.** `[DERIVED]` TTLs must not depend on wall clock; monotonic version numbers only.

### Properly labeled [UNKNOWN]s

- Deployment topology (own box? CDN? IPNS — whose republish jobs are currently failing `[WORKSPACE/memory]`). This decides whether relay fan-out is a real bottleneck or a solved CDN problem. `[UNKNOWN]`
- Real bandwidth environments of actual users (affects adaptation tuning, not architecture). `[UNKNOWN]`
- Whether behavioral prefetch (attention prediction) ever becomes accurate enough to matter. `[UNKNOWN]`
- Implementation details of both workers' current builds. `[UNKNOWN — pending, not failure]`

**Iris verdict: PASS on intent, FAIL on completeness of the readjustment account.** The hidden cases are derivable from the spec's own premises, so they cannot be filed under UNKNOWN. `[GATE-IRIS]`

---

## GATE 3 — Twain² (bedside)

**Judgment: first load passes the bedside test; readjustment as implied by the spec fails it.**

### What works for humans

- Non-blocking initial render is the correct bedside choice. A world that appears coarse immediately and sharpens beats any loading bar, on every device, at every bandwidth. `[DERIVED]`
- Offline-capable cached world is the correct bedside choice. A world that works in a tunnel beats a world that doesn't. `[DERIVED]`

### Where the human feels the missing design

1. **Schema change = visible re-load (default behavior).** If readjustment is drop-and-restream, the user watches their world go coarse again on every schema change — the exact experience the architecture was built to eliminate. The bedside-passing behavior: keep rendering the old world **labeled STALE** while v2 streams in behind, then cut over atomically. The spec designs no such behavior. `[DERIVED]`
2. **LOD popping.** Bandwidth oscillation on flaky mobile links → visible quality pumping (near geometry swapping resolutions). Humans read this as broken. Forced design: hysteresis — upgrade fast, downgrade slow, with a dead band. `[DERIVED]`
3. **Version skew between humans.** "Look at the north chamber" — two users, two world-versions. Without a visible world-epoch indicator, humans argue about a world that isn't the same world. A small, always-visible epoch/version marker is a bedside requirement, not chrome. `[DERIVED]`
4. **Stale prices.** A merit price rendered from cache without an as-of timestamp invites a human to act on dead information. Every cached economic figure must carry its staleness on its face (as-of + STALE badge). The current badge set cannot express this. `[DERIVED]`
5. **Progressive loading stays invisible at scale only if** the above four are designed. Invisibility is not a property of the first-load path; it is a property of the readjustment path, which is where users actually live. `[GATE-TWAIN²]`

---

## QUESTION 1 — Future manifestation projection

### The mature form `[DERIVED]`

- **Storage:** Clients hold a working set, not the world — GB-scale on desktop, smaller on phone. Eviction (detail-first, far-first) is a core subsystem, not an afterthought. The full world lives in content-addressed chunk trees; DCLM signs root manifests.
- **Distribution:** Chunks are content-addressed by hash with the DCLM signature in the envelope → **trustless distribution**. Any CDN, edge cache, or peer can serve chunks; tampering is detectable, withholding is the only attack. The relay's job shrinks to signing heads and serving the live tail. Peer-assisted chunk sharing becomes possible because verification needs no trust.
- **Prioritization becomes the product.** What streams first *is* the editorial decision (shell → coarse → detail → predicted-attention). Attention-driven prefetch emerges as the differentiator.
- **The manifest hierarchy:** root head (tiny, signed, fetched every load) → level manifests → chunk hashes. The head is the only freshness-sensitive fetch; everything else is immutable and cacheable forever.

### What breaks first, in order `[DERIVED]`

1. **IndexedDB quota / eviction** — hits on real devices first (GB scale, mobile Safari). Without quota-aware writes, the cache layer starts throwing and the client must already know how to degrade.
2. **Chunk manifest bloat** — linear manifest growth forces hierarchical manifests before PB scale; a flat per-chunk manifest list becomes its own bulk download.
3. **Bandwidth-adaptation oscillation** — flaky links cause LOD pumping; needs hysteresis by design.
4. **Relay fan-out at user scale** — solvable *by* the architecture's own content addressing (trustless edge), but only if chunks are actually content-addressed and signed per-chunk. The current relay serves whole bundles `[WORKSPACE]`; chunked serving must preserve the signed-envelope property per chunk.
5. **Schema evolution vs. cached chunks** — the readjustment protocol (Question 2); the most expensive break because it touches every cached byte.

### What emerges that isn't visible now

- `[DERIVED]` **The offline world as a first-class artifact:** devices carry meaningfully stale but fully interactive worlds → version skew becomes a social fact, requiring visible world-epochs.
- `[DERIVED]` **Delta sync as mandatory infrastructure:** Merkle-diff between heads; fetch only changed chunks. Full re-fetch of affected LOD levels is the naive fallback, unaffordable at scale.
- `[DERIVED]` **Tiered freshness classes:** geometry (long-lived), economic state (short-lived), identity/standing (never in the chunk cache). One invalidation policy cannot serve all three.
- `[UNKNOWN]` Whether attention-prediction prefetch ever works well enough to matter; depends on real usage data that doesn't exist yet.
- `[UNKNOWN]` The actual deployment substrate (CDN? IPNS? David's box?) — decides which scaling breaks are real vs. theoretical.

---

## QUESTION 2 — Readjustment accounting assessment

**Assessment: the mechanism is named, not designed.** "Cache invalidation via DCLM-signed bundle hashes" `[SPEC]` is a primitive. A protocol requires all of the following, none specified:

| Required mechanism | Status in spec | Priority |
|---|---|---|
| Signed **head document** (world_version, schema_version, root chunk-tree hash, per-class TTLs), fetched every load | Missing | P0 |
| **Version-pinned streams** (chunks carry world_version; a stream completes against its starting head; no v1/v2 mixing) | Missing | P0 |
| **No-downgrade rule** (client rejects heads older than cached head; defeats rollback) | Missing | P0 |
| **Schema-change policy**: migrate-in-client (tensions thin-client law) vs. namespace-drop-and-restream (costly at scale) vs. cross-version chunk reuse for unchanged fields — an explicit, recorded choice | Missing | P1 |
| **Delta sync**: Merkle-diff between heads, fetch only changed chunks; per-LOD-level invalidation for geometry updates | Missing | P1 |
| **Tiered freshness**: economic/identity state excluded from long-lived chunk cache or short-TTL; wallet stays server-round-trip | Missing | P0 |
| **STALE provenance state** in the badge set + as-of timestamps on cached economic figures | Missing | P0 |
| **Hash verification on READ**, not just download (partial-corruption defense) | Missing | P1 |
| **Eviction policy**: detail-first/far-first LRU, quota-aware writes, degrade to streaming-only | Missing | P1 |
| **Bedside readjustment**: render old world labeled STALE while new streams behind; atomic cutover; visible world-epoch indicator | Missing | P1 |

**Trace-through (schema change, showing the gaps):** Client boots with v1 chunks → fetches head → sees `schema_version: 2` → ??? The spec gives no step 3. Honest options: (a) mark all v1 chunks STALE, keep rendering with STALE labels while v2 coarse streams in, cut over atomically; (b) purge v1 namespace immediately (offline user loses their world — bedside failure). Either way the client must *know* the policy, the provenance system must *express* STALE, and the stream must be *version-pinned* so a v2 publish mid-download doesn't corrupt the v1 completion. None of this is in the spec. That is the finding — not a gap to hand-wave. `[GATE-DCLM + GATE-IRIS]`

---

## Verdict rationale

**PASS-WITH-NOTES** — not PASS, because the readjustment mechanism is undesigned and a ratified law forbids the core storage primitive; not FAIL, because the architecture's direction is logically sound, its trust model (non-authoritative cache, DCLM sole writer, signed invalidation) is pure in intent, and every missing piece is designable from the spec's own premises. Per the rules: implementation-pending items are marked `[UNKNOWN]`, never passed.

---

## What to fix, prioritized

1. **P0 — Resolve the law conflict before any IndexedDB code ships.** Submit the read-cache amendment to the purity machine: *"no writes of RECORD; read-cache writes permitted only for DCLM-signed chunks, never treated as truth, invalidatable by DCLM-signed hash."* Narrow `validate-client.mjs` no-write patterns to allow only the sanctioned cache path. Shipping under the current letter is impure by the machine's own rule.
2. **P0 — Design the readjustment protocol** (head document, version-pinned streams, no-downgrade rule, Merkle-diff delta sync, tiered freshness, STALE provenance state, hash-on-read, eviction policy). The primitive exists; the protocol doesn't.
3. **P0 — Exclude economic/identity state from the long-lived chunk cache** (or give it short TTLs with as-of + STALE badges). Merit is transferable; stale prices are a financial hazard. Wallet stays server-round-trip, as the ratified client already does.
4. **P1 — Bedside readjustment behavior:** render old world labeled STALE while the new version streams behind; atomic cutover; always-visible world-epoch indicator; hysteresis on LOD switching (upgrade fast, downgrade slow).
5. **P1 — Quota-aware eviction:** detail-first/far-first LRU; writes that degrade to streaming-only instead of throwing; offline world degrades to coarse, never to empty.
6. **P2 — Record the schema-change policy decision** (migrate vs. drop-and-restream vs. cross-version chunk reuse), checking the winner against the thin-client law.
7. **P2 — Hierarchical manifests** (signed root over chunk-tree) so the manifest never becomes the bulk artifact; per-chunk signed envelopes so chunked serving preserves the relay's current whole-bundle signed-envelope guarantee.
8. **When the workers land:** re-run this verdict against the actual client + dclm/relay chunked-serving outputs — chunk addressing, per-chunk signature envelope, the adaptive/bandwidth-estimation algorithm, and the eviction implementation are all `[UNKNOWN]` until read.

---

*Trinity worker sign-off: DCLM — logic holds, protocol missing. Iris — honest intent, hidden foreseeable cases named above. Twain² — first load passes the bedside test; readjustment must be designed to stay invisible. All three gates concur: PASS-WITH-NOTES.*

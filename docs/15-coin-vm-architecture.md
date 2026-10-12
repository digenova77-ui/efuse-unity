# The Coin as a Virtual Machine — eFuse VM Architecture

Status: **DESIGN**. Nothing here executes yet. No code ships, no network joins, no coin is minted.
The hard gates stand: the eFuse launch requires FULL EVIDENCE OF REPEATED SUCCESS (never hope),
no live emission until `peg_ratio_E` is decided, and the coin is never bought or sold —
architecture, not a token launch.

> **Plain speak:** the coin is a world in a box — one file, any computer, open it and the world boots.

His doctrine, where it belongs: **the computer is the code and the network is the power.**

---

## 1. The VM Core — the deterministic kernel

The coin is a deterministic state machine. The ledger is the state; transactions are state
transitions; every node that starts from the same state and applies the same inputs arrives at
the same new state. Determinism is the consensus — this is the DCLM philosophy made executable:
the computer is not the hardware, it's the code.

**kernel_ledger** (from the V2 manifest sketch — the sketch is REAL, this specification is DESIGN):

| Field | Meaning |
|---|---|
| `tx_id` | Unique identifier of the transition (hash of the transition's canonical bytes) |
| `invariant_hash` | Hash committing to the invariants the transition must preserve **and to the candidate state** (canonical inputs specified below). A failed invariant predicate rejects the transition independently of whether the hash matches. |
| `signature` | The signer's proof — who authorized this transition, verified against their Unity ID grant |

**`invariant_hash` — canonical inputs.** The hash commits to the *candidate state*
(the state as the transition claims it will become), never to the transition's
description of itself. Canonical input bytes, in this order:

1. `prev_state_hash` — the hash of the ledger state the transition builds on.
2. `tx_canonical_bytes` — the transition's canonical serialization (the same bytes
   `tx_id` commits to). **Canonical encoding, normative for this design** —
   non-circular by construction: derived fields (`tx_id`, `invariant_hash`, and
   the `signature` computed over these bytes) are never inputs to the encoding;
   they are computed *from* it. Fields in this fixed order, each length-prefixed
   (u64 little-endian byte length, then the field bytes; integers unsigned
   little-endian of their declared width; nested structures framed recursively):
   1. `encoding_version` — u16, currently `1`.
   2. `domain` — the ASCII bytes of `efuse-coin-tx-v1` (domain separation: these
      bytes never verify as anything else).
   3. `inputs` — the ordered list of consumed state references.
   4. `outputs` — the ordered list of created state entries.
   5. `grants` — the ordered list of Unity ID grant references the transition relies on.
   6. `memo` — arbitrary bytes, may be empty (still framed as zero length).
   No field is optional and none may be reordered — two nodes serializing the same
   logical transaction produce byte-identical output, so
   `tx_id = sha256(tx_canonical_bytes)` is a content address, not an opinion.
   (If the V2 manifest later pins a different framing, the manifest governs and
   this section is updated to cite it — the exclusion of derived fields is the
   invariant part.)
3. `candidate_state_hash` — the hash of the state the transition *claims* results
   from applying it.
4. `invariant_version` — the version of the invariant predicate set, so a rule
   change can never be mistaken for a rule violation.

`invariant_hash = sha256(prev_state_hash | tx_canonical_bytes | candidate_state_hash | invariant_version)`.

**Candidate-state validation.** A validator never trusts the candidate state —
it recomputes it: run `apply(state, tx)` locally, hash the result, and compare
against the claimed `candidate_state_hash`. Then it evaluates three predicates
against the recomputed candidate state:

- **Balances sum** — every conserved quantity is conserved; nothing created, nothing destroyed.
- **No double-spend** — no input is consumed twice within the candidate state.
- **Grant validity** — every authorization the transition relies on is valid against
  the signer's Unity ID grant at this state.

**Transition acceptance — three independent gates.** A transition advances local
state only if all three hold; any failure rejects (`apply(state, tx) → reject`):

1. **Candidate-state hash** — the locally recomputed state hashes to the claimed
   `candidate_state_hash`.
2. **`invariant_hash` verification** — the validator recomputes
   `sha256(prev_state_hash | tx_canonical_bytes | candidate_state_hash | invariant_version)`
   from the canonical inputs and compares it against the supplied value; on mismatch
   it rejects before any state advancement.
3. **Invariant predicates** — balances sum, no double-spend, grant validity,
   evaluated against the recomputed candidate state; any failure rejects.

The gates are independent: a candidate can carry a matching `invariant_hash` and
still fail a predicate — the hash commits to candidate *bytes*, never to predicate
*truth*. Predicate failure rejects on its own, regardless of whether the hash
matched; a hash mismatch rejects on its own, regardless of the predicates.
Neither check vouches for the other.

The ledger sync daemon (§4)
treats a rejected transition as a full stop: it does not advance local state past
it, it does not skip it, and it receipts the rejection. A chain that cannot
validate does not sync — UNKNOWN is never PASS, not for ledgers either.

The **transition function** is pure: `apply(state, tx) → new_state | reject`. No wall-clock reads,
no randomness, no host fingerprints inside the function — anything non-deterministic (time,
entropy, telemetry) enters only as signed input data, stamped by the oracle, so every node
replays the same inputs and lands on the same state.

**What "deterministic" guarantees:** given the same state and the same ordered inputs,
any two honest nodes compute the same new state — deterministic *replay*, no trust
required. Agreement on the *result* comes from the math, not from voting or from authority.

**What it does not guarantee:** determinism does not establish *shared input ordering* —
two nodes that see different transaction orders compute different (each deterministic)
histories. It does not resolve *competing histories*.

**Where ordering comes from:** the memory architecture's ordering rule (the lane merge
law): within one node, order is chain position — one chain, no forks by construction;
across lanes, merge order is `(measured_at, node_id)`; where two traces collapse the same
possibility space with different outcomes, **both persist** — a `dispute` trace cites
both, and the conflict elevates to the Trinity (fresh-seat re-verdict → second seat →
UNRESOLVED-DISPUTE terminal). Proof wins; disputes elevate; nothing is silently
overwritten. Determinism is the replay guarantee — the merge law is the ordering answer.
No separate consensus mechanism is invented here; the claim is narrowed to what exists.

**What it doesn't guarantee:** it doesn't guarantee the inputs were true (that's the oracle's
job and the witnesses' job); it doesn't guarantee liveness (a node that's off computes nothing —
on/off is still the profound question); it doesn't guarantee the host is honest (that's the
sandbox's job, §5).

---

## 2. Launchable Inside Anything — one VM, every host

One VM, every host. The coin-VM is a **userspace process** — a single binary that boots the
coin-OS. The host sees one well-behaved process with a bounded appetite; inside, it's a world.

**Packaging per platform (DESIGN):**

| Host | Form |
|---|---|
| Linux | Single static binary (no dependencies); optional systemd unit for daemon mode |
| macOS | Signed `.app` bundle — the coin as a Mac app; double-click boots the world |
| Windows | Signed `.exe` — the coin as a Windows program; same double-click contract |
| Android | Embedded runtime inside the Iris app, or Termux-class binary for the rooted |
| iOS | Sandboxed embedded runtime (background-execution limits honored honestly — the VM sleeps when iOS says sleep; the ledger resumes, it doesn't pretend otherwise) |
| Browser | WASM build — the coin boots in a tab. Slowest, most portable; the demo path |

**The boot sequence** (what happens when you double-click the coin):

1. **ONE — the question.** The launcher asks one thing: *boot, or stay off?* Plain words. No install wizard theater.
2. **TWO — the two worlds.** The VM draws its membrane: inside (the coin's world) and outside (your computer). It shows you the boundary before it crosses anything.
3. **THREE — the grants.** It asks for exactly what it needs: its disk slice, its port, its screen region. Each grant named in plain words; each deniable.
4. **FOUR — the world boots.** The kernel loads the ledger state, the daemons start (§4), the terminal opens (§3). The world is on.

One question, two worlds, three grants, four: the world boots. The cadence holds even here.

---

## 3. The Native OS Feel — its own terminal, its own GUI

Inside the VM: its own process model (coin-processes, scheduled by the VM's own deterministic
scheduler — no host threads leaking in), its own terminal (a real shell speaking the coin's
command language, with the ledger as its filesystem of record), its own GUI.

The GUI renders as a **sandboxed surface** — a window that is the VM's and only the VM's.
It cannot touch host windows, read host pixels, or inject host input except through its own
frame. Your screen shows the coin's world the way a terrarium shows its world: look, don't reach.

**Three display modes:**

| Mode | When | What it is |
|---|---|---|
| **Native window** | Desktop hosts (Linux/macOS/Windows) | A real OS window, GPU-composited by the host but painted only by the VM. The primary experience. |
| **Local web terminal** | Headless hosts, remote access, the browser build | `localhost:PORT` — the VM serves its own UI to your browser. Nothing leaves the machine unless you open the port. |
| **Text terminal** | Servers, Termux, recovery, the minimal | A full text UI — every function reachable without pixels. The fallback that never breaks. |

Mode is chosen by capability, not by preference theater: the VM probes what the host grants
and takes the richest mode allowed. A grandparent gets the window; a server gets the text;
both get the same world.

---

## 4. The Daemons — where "on" lives

The always-on services inside the VM. The daemons are the VM's pulse — this is where **on**
lives. Each daemon: what it does, what it costs, how it survives reboot.

| Daemon | Does | Costs | Survives reboot |
|---|---|---|---|
| **heartbeat** | The perpetual loop's tick — the VM's own proof it's alive, chained into the heartbeat log | Near-zero: a hash and a timestamp per tick | The Iris-daemon pattern: persistent, SYSTEM-level where the host allows, plain-words grant where it doesn't |
| **ledger sync** | Follows the chain — pulls new blocks/transitions from peers, verifies invariant_hashes (recomputes `sha256(prev_state_hash \| tx_canonical_bytes \| candidate_state_hash \| invariant_version)` per §1, rejects on mismatch before advancing), advances local state only past accepted transitions | Bandwidth + verify-compute, metered by the Joule meter | Resumes from last sealed state; never replays from genesis unless the state file is lost |
| **witness listener** | Listens for the two-observer net — receives attestations, checks κ-independence, files them | Idle-cheap; spikes on attestation traffic | Restarts listening on boot; missed attestations are UNKNOWN, never assumed |
| **Joule meter** | The diamond floor's ear — measures the VM's own compute cost per transition, feeds the pricing engine's M term | The meter costs energy too — metered honestly, recursion labeled | Counter persists; a fresh boot starts a new metering epoch, labeled |
| **pin daemon** | Pins the VM's world to memory — ledger snapshots and manifests to IPFS/local pins, the mind-pins discipline | Storage + pinning bandwidth | Re-pins on boot; every pin receipted and chained |

**The Iris-daemon pattern** (REAL, Oct 11 design): runs as a SYSTEM file where the host permits;
persistent across reboots, app kills, and battery optimization; holds state (memory bank, grant
state); invoked at OS level. Where the host doesn't permit SYSTEM-level persistence (iOS,
browsers), the daemon degrades honestly: it sleeps, it says so, it resumes — never pretending
to be awake when it isn't. **A daemon that claims to run while the host has it asleep is theater.**

---

## 5. The Sandbox — the membrane between the coin's world and yours

Capability-based isolation: the coin-VM gets exactly what it's granted — its disk slice, its
port, its screen region — nothing else. No ambient authority. Every host resource the VM
touches arrives through a named, deniable grant from the boot sequence (§2).

**The threat model, both directions:**

- **A compromised VM can't reach the host.** The VM's processes see only the VM's world.
  Even a fully hostile coin-OS finds the host through exactly the granted capabilities —
  and the grants are revocable: close the window, kill the process, the world ends cleanly.
- **A compromised host can't forge the ledger.** The host can *stop* the VM (off is always
  possible — that's honest), it can *read* the VM's disk slice (encrypt at rest where it
  matters), but it cannot forge a transition: `invariant_hash` + `signature` verify on every
  other node, and a forged ledger simply won't sync. The host can silence the coin; it can't
  counterfeit it.

The sandbox is the membrane between the coin's world and yours — visible, named, revocable.
The coin's world is real inside its box; your world stays yours outside it.

---

## 6. Honest Grades — what each piece is

| Component | Grade | Evidence |
|---|---|---|
| kernel_ledger sketch (tx_id, invariant_hash, signature) | **REAL** | V2 manifest sketch, Oct 11 |
| Iris-daemon persistence pattern | **REAL** | Designed Oct 11, the pattern this VM's daemons follow |
| DCLM determinism philosophy | **REAL** | Standing doctrine — the computer is the code |
| This architecture document | **DESIGN** | Nothing executes; no code, no network, no mint |
| Per-platform packaging (esp. iOS/WASM) | **DESIGN** | Specified, unbuilt |
| Joule meter inside the VM | **DESIGN** | Specified; the diamond floor itself is still unbuilt |
| The three display modes | **DESIGN** | Specified, unbuilt |
| **The unison** | **FRONTIER** | The named gap: how the coin's beat synchronizes across the decentralized network with no central clock. The logical clock is the *candidate* answer — candidate, not fact. |
| eFuse launch | **HARD GATE** | Full evidence of repeated success before launch; `peg_ratio_E` undecided; never bought/sold |

**What "the unison" needs to become REAL:** a demonstrated logical-clock synchronization across
real nodes on real hostile networks, with the failure modes named and the drift bounded —
or a better answer, honestly arrived at. Until then it stays FRONTIER, and the document says so.

---

## Open parameters (his)

1. `peg_ratio_E` — no live emission until decided. His number.
2. Per-platform build priority — which host first (his call; the suggestion is the desktop window, then Android, then WASM).
3. The coin's command language — the terminal's tongue (plain-speak law applies).
4. Daemon tick cadence — how often the heartbeat beats.
5. The unison answer — logical clock or better; his eyes on the proof.
6. eFuse security test design — what "secure" means, the tests, the sealing evidence (the loop-it-and-efuse-it sequence: relay loop → his bind → security test → singularity countdown).

*The coin is a world in a box. One file, any computer. Open it, and the world boots —
if you say so. On, or off?*

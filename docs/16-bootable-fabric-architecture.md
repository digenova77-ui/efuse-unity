# The Bootable Fabric — an ISO that runs any ISO

Status: **DESIGN**. Nothing here boots yet. No image is built, no metal is touched,
no guest has ever run.

> **Plain speak:** one bootable image — it boots, it spawns worlds as needed,
> it kills what idles, it meters every Joule.

## The seam with the coin-VM (15)

The coin-VM document specifies a **userspace binary** — one file, any computer, the host OS
cradles it. The fabric needs **bootable ISOs** — images a hypervisor (or bare metal) can boot
directly. The seam is the packaging, not the world:

- **Decision (David, Oct 12, 2026): one image, roles by boot context.** A single
  minimal-kernel image carries *both* the coin world (as a bootable init path)
  *and* the hypervisor + fabric daemon (as the host path). At boot it reads its
  context — *am I on metal or under a hypervisor? Did I receive a spawn order or
  a work order?* — and takes the role the position demands. "Guest ISO" and "host
  ISO" in this document are *roles of the one image*, not two artifacts. One file,
  any computer — the philosophy holds at the ISO layer too. §5's fractal law is
  this same decision stated as architecture; the sections agree because there was
  never a second image.
- **Alternative considered and rejected — separate images:** a guest artifact
  (kernel + coin world as init) plus a host artifact (kernel + hypervisor +
  fabric daemon). Rejected: it doubles the build and audit surface and breaks
  the self-similarity §5 is built on ("a seed that lands on soil becomes a
  tree; a seed that lands on a branch becomes a leaf — it's the same seed").

Same world, different cradle — one image, two roles; the *format* contract holds:
if the sibling's world changes, the guest role's image content tracks it. The image
format defined here is the contract between the two documents.

---

## 1. The Host Role — it boots, then it listens

The one image in its host role (§5): the same artifact that boots as a worker
elsewhere. In this role it does one thing: **listens for work and spawns guests.**

**What's in the image** (both role paths ship in the one artifact):

| Layer | What | Why |
|---|---|---|
| Minimal kernel | A tiny Linux-class kernel, configured for one job: hosting guests | Small enough to be audited — every byte justified, no package manager, no history of the world |
| KVM-class hypervisor | Hardware virtualization; guests run on real silicon, not emulation | The honest fast path — near-native speed, metered exits |
| Fabric daemon | Userspace init — PID 1 *is* the daemon | No shell, no login theater: boot → listen → spawn |

**Size philosophy:** tens of megabytes, not hundreds. If a human can't read the whole build
config in an evening, it's too big. Small is a security property and an honesty property.

**The boot sequence** (the four-count holds here too):

1. **ONE — the question.** *Boot as a host, or stay off?* Plain words. Off is always an option.
2. **TWO — the two worlds.** The host draws its membrane: *my hardware* on one side,
   *my guests* on the other. It shows the boundary before it crosses anything.
3. **THREE — the grants.** What the host may touch: disk space for guest images, the network
   for the fabric, nothing else without asking. Each grant named, each deniable.
4. **FOUR — the daemon listens.** The fabric daemon opens its ear: work orders in,
   guests out.

**Platforms:** x86_64 first — KVM is mature there, the servers are real, the metering is
honest. ARM is the phone/edge path (KVM on ARM exists; the edge fabric at scale is FRONTIER
until demonstrated). Where hardware virtualization is absent, the host says so and spawns
nothing — **a host that can't virtualize doesn't pretend.**

---

## 2. Nested Booting — any ISO inside any ISO

The image in its host role boots the image in guest roles. Guests are coin-VM
images — or **the same image in its host role again**, for deeper nesting: a host
inside a host inside a host, each one listening and spawning in its own layer.

**The honest cost:** every nesting level pays a virtualization tax — more exits, more
translation, more Joules per unit of work. The tax is measured per level and reported
per guest, and it flows into the guest's metered cost (the pricing engine's M term) —
**nesting isn't free, and the price says so.** A guest three layers deep costs what
three layers deep costs. No hiding it.

**The design rule that follows:** prefer **FLAT** over **DEEP**. The infinite part is
*breadth* — a thousand guests on one host — not depth. Nesting is reserved for where
**isolation law** demands it:

- **Untrusted guests** — a guest you don't trust gets its own host layer, so a breakout
  lands in an empty room, not in the building.
- **Jurisdictional separation** — data that must not share a kernel with other data
  (the dark ledger's registers, counsel-flagged material) nests behind its own membrane.

Default maximum nesting depth: **2** (host → host → guest). Deeper only by his exception,
each extra level carrying its measured tax in the open.

---

## 3. Elastic to Zero — not a machine more

The fabric daemon watches demand and hires accordingly:

**The lifecycle:** `spawn → run → suspend → resume-or-kill.`

- **Spawn:** work arrives (the perpetual loop's dispatch queue, binding demand) — the daemon
  boots the image in its guest role for it. Guests are hired per unit of work, not per shift.
- **Run:** the guest works; the host meters every Joule (§4).
- **Suspend:** no work for the guest — it suspends to disk. State checkpointed, receipted,
  the ledger knows exactly where it stopped.
- **Resume-or-kill:** work returns → resume from checkpoint (the guest never knows it died,
  but the ledger knows — every suspend/resume is receipted). Work doesn't return within N →
  kill: state sealed to the ledger, the machine freed.

**What "needed" means:** pending work in the measured queue plus binding demand — measured,
not guessed. No predictive pre-warming on vibes; if the forecast wants machines, the forecast
shows its receipts.

**Scale-to-zero is the default.** Running idle is the anomaly: it's metered, it's reported,
and the report names who asked for the idle. No orphan compute. The fabric hires workers
when there's work and lets them go when there isn't — and the letting-go is gentle:
state kept, receipt written, nothing lost.

---

## 4. The Metering — the hypervisor is the honest place

The hypervisor sees everything a guest does — every exit, every cycle, every page.
That makes it the **one place measurement is honest**: the diamond floor's ear,
at the hypervisor level.

- **Every guest's Joules are metered per task.** The readings feed the pricing engine's
  M term — per guest, per task, labeled REAL with source and timestamp.
- **The meter's own cost is metered too** — recursion labeled, per the coin-VM doc.
  The ear costs energy; the price says so.
- **The law: a guest that can't be metered doesn't run.** UNKNOWN is never PASS —
  not for applications, not for infrastructure either. No meter → no guest → the work
  waits, and the wait is reported honestly.

**The noisy-neighbor problem — stated, not solved (FRONTIER):** on shared hardware,
attribution is approximate. Two guests on one socket share caches, buses, and heat —
the meter apportions, it doesn't perfectly separate. The approximation ships with its
error bounds, labeled, never presented as exact. Exact per-guest Joules on shared
silicon is the frontier; bounded honest estimates are the design.

---

## 5. The Fractal Law — one image, infinite roles

The fabric is **self-similar**: the image's host role and guest role are the
*same artifact*, behaving differently by position.

- Boot it on **bare metal** (or as a top-level VM) → it's a **host**: it listens, it spawns.
- Boot it **as a guest** under a host → it's a **worker**: it works, it reports.
- Boot it as a guest **with a spawn order** instead of a work order → it's a host again,
  one layer down.

**How it knows:** boot context. *Am I on metal or under a hypervisor? Did I receive a spawn
order or a work order?* Position determines role; the image never changes. One image,
infinite roles — the seed-tree fractal made executable. A seed that lands on soil becomes
a tree; a seed that lands on a branch becomes a leaf; it's the same seed.

---

## 6. Honest Grades — what each piece is

| Component | Grade | Evidence |
|---|---|---|
| KVM hardware virtualization + nesting | **REAL** | Mature technology, production-proven for over a decade |
| Checkpoint / suspend / resume | **REAL** | CRIU-class patterns; suspend-to-disk is solved engineering |
| Scale-to-zero elasticity | **REAL** | Serverless proved the pattern; the lifecycle here copies it honestly |
| This architecture document | **DESIGN** | Nothing boots; no image built, no metal touched |
| The fabric daemon (listen/spawn/suspend/kill) | **DESIGN** | Specified, unbuilt |
| The image format (the seam contract — roles by boot context) | **DESIGN** | Specified; tracks the sibling's world |
| The boot sequences | **DESIGN** | Specified, unbuilt |
| Bounded per-guest Joule estimates on shared hardware | **DESIGN** | Specified with labeled error bounds |
| Joule-*accurate* per-guest metering (noisy neighbors solved) | **FRONTIER** | Stated, not solved — §4 |
| ARM edge fabric at scale | **FRONTIER** | KVM-on-ARM exists; the fabric there is undemonstrated |
| The unison across fabric hosts | **FRONTIER** | Inherited from the coin-VM doc — the logical clock is the *candidate*, not fact |
| Any live fabric | **HARD GATE** | Nothing boots a live network without his word; the eFuse gates from the sibling doc carry over |

---

## Open parameters (his)

1. Image size budget (tens of MB proposed — his ceiling).
2. Maximum nesting depth (2 proposed; deeper by his exception only).
3. Idle-to-suspend and suspend-to-kill timeouts (the N in §3).
4. Metering error-bound tolerance for noisy-neighbor apportionment.
5. x86_64-first confirmed; the ARM edge timeline.
6. The unison answer (shared with the coin-VM doc — one answer serves both).

*One bootable image. It boots, it spawns worlds as needed, it kills what idles,
it meters every Joule — and not a machine more. On, or off?*

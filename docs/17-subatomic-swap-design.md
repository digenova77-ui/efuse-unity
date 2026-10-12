# The Subatomic Swap — trustless swap to any crypto, down to the dust

Status: **DESIGN**. Nothing here executes. No swaps run, no chains are touched, no coin moves.
The hard gates stand: the eFuse launch requires FULL EVIDENCE OF REPEATED SUCCESS,
`peg_ratio_E` undecided, and the coin is architecture, not a token launch.

> **Plain speak:** any crypto in, any crypto out — no exchange, no permission, down to the dust.

David's term is **subatomic swap** — kept verbatim. It means atomic swaps (no intermediary,
no exchange, both sides settle or neither does) at the finest divisibility the coin allows —
below the counterparty chain's own atomic unit where the coin's divisibility reaches further.
The counterparty's dust is the coin's lunch: value too small for the market's own rails to
move becomes movable.

His doctrine, where it belongs: **the computer is the code and the network is the power.**
The swap engine is code inside the coin-VM; the counterparty chains are the power it reaches.

---

## 1. The Mechanism — hashed timelock contracts, adapted to a deterministic kernel

The primitive is the **hashed timelock contract (HTLC)** — REAL, not invented here.
Bitcoin and Litecoin performed trustless cross-chain atomic swaps with HTLCs in 2017.
This design adapts that proven pattern to the coin's deterministic kernel; it invents no new
cryptography.

**How an HTLC swap works (both directions — any-crypto → coin, coin → any-crypto):**

1. **Intent.** Maker and taker agree on the pair and amounts on the open intent board (§5).
   No custody changes hands; this is a handshake, not a deposit.
2. **Quote.** The price dial shows the live rate (transparency); at authorize, the quote
   **freezes** (settlement). Live dial for looking, frozen quote for signing — the same
   rule the dark ledger uses. No one signs a moving price.
3. **Lock.** Both sides lock their funds in HTLCs on their own chains:
   - Maker locks coin-side (or crypto-side) funds behind `H = hash(s)` with timelock `T_maker`.
   - Taker locks the other side behind the same `H` with timelock `T_taker < T_maker`
     (the taker's lock expires first, so the maker can never be stranded).
4. **Reveal.** Maker claims the taker's lock by revealing the preimage `s` on-chain.
   The reveal is public — the taker reads `s` from the maker's claim transaction.
5. **Settle.** Taker claims the maker's lock with the now-known `s`. Both sides settled.
   **Or refund:** if either side never reveals, the timelocks expire and each side's funds
   return to their owner. No intermediary ever holds both sides. There is no one to rob.

**The deterministic-kernel fit (DESIGN):** the coin's transition function is pure —
`apply(state, tx) → new_state | reject` — and time is non-deterministic. So timelocks enter
the kernel the same way all non-determinism enters: as **signed oracle-stamped inputs**.
The witness listener daemon (§4 of the VM doc) stamps chain time and block height; the swap
locks reference those stamps, not wall-clock reads. Every node replays the same stamped
inputs and lands on the same state. Determinism survives the timelock.

---

## 2. Subatomic Granularity — the dust becomes movable

**The coin's smallest unit (DESIGN, David names it):** proposed working name **mote** —
the coin's atomic unit, suggested divisibility `10^-18` of one coin (his parameter to set).
The point is structural, not numerical: the coin divides finer than the chains it swaps with.

**Why it matters — the dust argument, plain-speak:**

Every chain has an atomic unit it cannot go below (one satoshi, one wei, one whatever) —
and below *that*, an economic floor: amounts so small the chain's own fees eat them.
That value exists but can't move. It's stranded.

The coin's finer divisibility reaches under both floors:

| Layer | What happens |
|---|---|
| Above the counterparty's atomic unit | Normal swap. Nothing special. |
| Below the counterparty's atomic unit but above its fee floor | The counterparty chain can't express it; the coin side can. Swap settles with the coin side carrying the precision. |
| Below the counterparty's fee floor ("dust") | The counterparty chain can't move it economically at all. The coin side absorbs it at subatomic granularity — **the swap works at sizes the market's own rails can't afford.** |

**The honest limit:** subatomic granularity is one-directional precision — the coin side can
*receive* dust-fine value, but the counterparty chain can only *send* what its own rails
express. The design never claims to make another chain more divisible than it is. What it
claims: value that would otherwise sit stranded can cross into the coin's world, whole.

---

## 3. Any Crypto on the Market — the universality claim, honestly graded

"Any crypto" is a direction, not a day-one fact. Three chain classes, three mechanisms,
three trust levels — stated, never blurred:

| Class | Examples (pattern-level) | Mechanism | Trust assumption |
|---|---|---|---|
| **A — HTLC-native** | Bitcoin-class UTXO chains with timelock + hashlock opcodes (the 2017 pattern) | Pure HTLC, both sides. No intermediary, no oracle in the swap path. | **Trustless.** Math only. |
| **B — Contract-capable** | Account-model chains with general smart contracts (HTLC re-implemented as a contract — REAL pattern, widely deployed) | HTLC logic as a contract on their side; native HTLC-equivalent on the coin side. | **Trust-minimized.** You trust the contract code (auditable, frozen) and the chain's own consensus — nothing else. |
| **C — Neither** | Chains with no hashlock/timelock and no general contracts | **Not yet.** The design's answer is "not yet," receipted as UNKNOWN. | N/A — no swap offered. |

**The adapter path (for Class B, DESIGN):** a contract template per chain family, frozen and
audited, carrying the exact HTLC semantics (hashlock, two-tier timelocks, refund path).
Larger trust assumptions than Class A, labeled on the quote screen in plain words:
*"this swap trusts [chain]'s contract execution — the coin side remains trustless."*
Never hidden, never footnoted.

**What "any" will never mean:** it will never mean a wrapped IOU, a custodied peg, or a
bridge with a multisig committee holding the funds. If a chain can't do A or B, the swap
doesn't happen. The design would rather say "not yet" than fake universality.

---

## 4. The Swap Daemon — the sixth daemon in the coin-VM

The swap engine lives inside the coin-VM as a **daemon-class service** — the sixth daemon,
beside heartbeat, ledger sync, witness listener, Joule meter, and pin daemon:

| Duty | What it does |
|---|---|
| **Watch** | Monitors the open intent board and the counterparty chains (via the witness listener's stamped feeds) for swap intents involving this VM's owner |
| **Quote** | Serves the live price dial; freezes quotes at authorize |
| **Lock** | Constructs and broadcasts this side's HTLC; verifies the counterparty's lock is correctly formed (right hash, right timelocks, funded) before proceeding |
| **Reveal** | Claims the counterparty lock with the preimage when this VM is maker; reads the preimage from chain when taker |
| **Refund** | Sweeps expired timelocks back to the owner — automatically, no permission needed, no one to ask |
| **Meter** | Reports its own Joule cost per swap phase to the Joule meter. Nothing is free, even the swap. The meter's recursion is labeled, per VM-doc discipline. |

**Failure modes — specified, not hand-waved:**

- **Counterparty vanishes mid-swap:** the timelock expires; the daemon refunds automatically.
  The worst case is waiting, never loss. The quote screen states the maximum wait in plain words.
- **Chain reorganization:** each chain class carries a confirmation-depth parameter (his to set
  per class; defaults proposed from the chain's own finality characteristics). A lock isn't
  treated as locked until it's deep enough. A reorg below depth is weather; above depth is
  a finding, receipted.
- **Timelock expiry races:** the two-tier timelock (`T_taker < T_maker` with a safety margin,
  his parameter) exists precisely so races resolve in favor of refunds over theft. The margin
  is sized against the slowest chain's confirmation time in the pair — measured, not guessed.
- **Daemon asleep (iOS/browser hosts):** per the Iris-daemon pattern — an asleep daemon claims
  nothing. A swap whose timelock window passes while the daemon sleeps refunds; the design
  refuses swap durations shorter than the host's honest wake guarantees.

---

## 5. The Honest Boundary — what the swap is NOT

- **Not an exchange.** No custody (funds live in HTLCs, never in our hands), no order book,
  no matching engine, no accounts. There is nowhere to be robbed because there is nowhere
  funds pool.
- **Not a trading product.** No leverage, no derivatives on the swap, no price speculation
  tooling, no charts going up. The quote screen shows a rate, not an opportunity.
- **Not a promise of liquidity.** A swap needs a counterparty — the design says so on the
  screen. Maker/taker discovery is the **open intent board** (first version): makers post
  intents (pair, amount, rate, timelock terms), takers accept. Public, permissionless,
  no ranking, no payment for placement. If no maker posts your pair, the honest answer is
  "no counterparty right now" — not a market-maker faking depth.
- **Not a way to buy or sell the coin as a speculative asset.** The standing constraint holds:
  the coin is architecture, not a token launch. The swap is **utility** — value moves between
  chains without asking anyone's permission (pay the bill on whatever chain, move Merit-earned
  value where it's needed, exit a chain without an exchange account). If the swap ever starts
  looking like a trading venue, that's a design failure, and the document says so here in
  advance.

**What it IS:** a utility. Value moves between chains without permission, without custody,
without an account — down to the dust.

---

## Open parameters (his)

1. The smallest unit's name and divisibility ("mote" proposed, `10^-18` suggested — his call).
2. Confirmation depth per chain class.
3. Timelock safety margin sizing rule.
4. The open intent board's gossip protocol (first version: local board + peer gossip via the witness-listener net — specified, unbuilt).
5. Class B contract templates — which chain families first (his priority order).
6. Whether the swap daemon runs by default at boot or on first intent (suggestion: on first intent — not a machine more than needed, per the fabric's elastic law).

*Any crypto in, any crypto out. No exchange. No permission. Down to the dust.*

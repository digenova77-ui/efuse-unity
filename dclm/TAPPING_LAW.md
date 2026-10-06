# THE TAPPING LAW — "The tree survives tapping."

Binding law, David's words. Testnet only.

---

Maple trees in Canada get tapped for sap every spring. Value leaves
the system — the sap runs out of the tree and into the bucket — and
the tree survives. It thrives. It grows back stronger. The tap does
not kill the tree, because the tapping follows rules older than any
of us.

So the economy is NOT hermetically sealed. Value CAN leave — to fiat,
to the outside world, to members' real needs — without killing the
system. A sealed system is a dead system; a living system breathes
out as well as in. But the breathing follows the maple rules. Four of
them.

---

## Rule 1 — Only in season.

Tapping happens in late winter and early spring — the surplus season.
The sap runs when the nights freeze and the days thaw. Never in
summer growth, when the tree is building itself. Never in deep
winter, when the tree is protecting itself.

**Economic translation:** outflow only from VERIFIED SURPLUS. Never
from core operating flow. Never during winter-protection mode. The
season is a computed verdict, not a calendar feeling: winter clear,
maturity proven, surplus verified, healing accounted — or the season
is closed and no tap flows. If the winter state cannot be read, the
season is closed. A closed season is not a failure; it is the tree
protecting itself.

## Rule 2 — Limited taps.

One or two taps per tree. A big old maple gets two; a smaller one
gets one. The tree's size sets the limit — you don't take more than
the tree can give.

**Economic translation:** rate-limited outflow, capped per member per
season, proportional to system health. There is a per-tap limit and a
per-member seasonal cap, and both are HELD FOR DAVID — he sets the
numbers. The mechanism enforces whatever he decides; the proposal is
in the parameters section below.

## Rule 3 — Only mature trees.

You don't tap saplings. A young tree hasn't built the root system to
survive the draw. You wait until it's established — strong trunk,
deep roots, full canopy — and then, and only then, do you drill.

**Economic translation:** no outflow until the system is established
— pools healthy, peg holds, reserve funded. Immaturity = no taps,
full stop. The maturity threshold is HELD FOR DAVID. And the rule
runs deeper: if the system's health cannot be scored — any input
unknown, unscorable, or missing — maturity is UNKNOWN, and UNKNOWN is
never PASS. A tree you cannot measure is a sapling until proven
otherwise.

## Rule 4 — The tree heals.

The tap hole closes. The wood grows over it. Next spring the tree is
bigger than it was, and you tap it again. The tree survives tapping
because every drop taken is answered by the tree's own growth.

**Economic translation:** every outflow receipted, replenishment
through continued merit-gated emission, and total outflow per season
NEVER exceeds the replenishment rate. The healing is accounted on
every receipt: season outflow total against season replenishment, in
the open, signed. If the replenishment cannot be verified, the tree
cannot prove it will heal — and no tap flows.

---

## The distinction that keeps it pure

Tapping is the system releasing surplus outward **through rules**.
It is NOT the founder extracting.

- **Tapping** serves members' real-world needs. It is rate-limited,
  receipted, season-bound, and healing-accounted. The maple law
  governs it.
- **Extraction** serves self. It takes without the rules, outside
  the season, beyond the limits, without the healing.

The creed forbids the second — absolutely, before any season is even
evaluated. A founder-identity outflow request is refused as
FOUNDER_EXTRACTION_FORBIDDEN, not as a limit or a season problem,
because it is a different kind of thing. Tapping is the tree giving
sap. Extraction is someone cutting the tree down.

---

## HELD-FOR-DAVID parameters (PROPOSED — his call)

These numbers are working defaults with reasoning. The mechanism
enforces them; David decides them.

| Parameter | Proposed | Reasoning |
|---|---|---|
| `TAP_RATE_PER_MEMBER_SEASON` (per-member seasonal cap) | 100 test-keys | 20× a COMPUTE run (5 keys), 100× a SEARCH (1 key): large enough to serve a real need, small enough that one member cannot bleed a season's replenishment alone. |
| `MAX_PER_TAP` (single-tap limit) | 50 test-keys | Half the seasonal cap — a member taps at least twice to reach the cap, and every draw stays receipt-visible. One or two taps per tree. |
| `MATURITY_THRESHOLD` | 0.70 | The system must be clearly healthy, not borderline, before saplings are declared trees. Maturity = 0.4·pool_health + 0.3·peg_score + 0.3·reserve_score. |
| `WINTER_GRADIENT_MAX_FOR_TAPPING` | 0.50 | Tap-side protection line on winter's real gradient: mid-TILTING on winter's own bands (SUMMER < 0.25, WINTER ≥ 0.75) — taps stop well before deep winter, while the root is only starting to tilt. winter.py defines no protection test of its own, so the tap side owns this line. |

Also proposed (tap-side scales, same standing): peg health scores
linearly to zero at 100 basis points of deviation
(`PEG_DEVIATION_BP_MAX = 100`).

## Interfaces and honesty notes

- **winter.py**: built by a separate worker (winter gradient 0.0–1.0,
  Peg Regulation Reserve) — landed mid-build and integrated FOR REAL.
  TapSeason takes a winter trigger signal (a `winter.WinterSignal`, or
  a dict of its fields) and evaluates it through
  `winter.evaluate_trigger` into a `WinterState`; the tap-side
  protection line (0.50, proposed, HELD-FOR-DAVID) applies to the real
  gradient — mid-TILTING on winter's own bands, so taps stop well
  before deep winter. No signal supplied → the trigger is unreadable →
  winter stays SUMMER ("winter is never assumed", winter's own rule),
  recorded honestly in the reason chain. winter.py defines no
  protection test of its own (labels are display-only there), so the
  tap side owns the protection line. If winter.py is ever absent, the
  interface is honestly PENDING and the season degrades to CLOSED:
  PENDING winter state never opens a season, never grants a tap.
- **Founder marker**: the refusal gate is ENFORCED (any identity
  matching the founder marker is refused before season evaluation).
  The exact founder identity string is CONVENTIONAL — not yet issued
  by the identity system (gate.py); register it via
  `UNITY_FOUNDER_IDENTITY` when it exists. Until then the gate is
  live but unpopulated, and any identity claiming the founder prefix
  (`unity:testnet:founder:`) is refused on sight.
- **Season id**: annual, `{year}-tapping` — one maple run per year.
- **Provenance**: every measure that feeds the season carries a
  provenance label; every receipt (grants and refusals alike) is
  Ed25519-signed with the existing testnet key material. UNKNOWN is
  never PASS.

# THE WALLET SURFACE — subtle persistent presence (design)

**Status:** TESTNET · design for the 3D world client.
**Law:** the wallet is the subtle persistent presence — a quiet
indicator, never a card, never a popup. No 2D card chrome anywhere
(the world is pure 3D; David's four laws of the website allow exactly
ONE 2D card, at the doorway, and the wallet is not it).

## The indicator

- **What it is:** one quiet 3D presence attached to the bound identity —
  a small bioluminescent mote in the identity's own orb color family,
  resting at the edge of the member's view (never center, never
  blocking). It breathes, barely. It never pulses for attention.
- **What it shows:** nothing numeric by default. Balance is revealed
  only on the member's deliberate look-at (gaze dwell or touch) — and
  then as plain 3D geometry with depth (a numeral formed in space, per
  the 3D torch rule), never as a card, never as a panel.
- **States it carries:** BOUND (warm) / UNBOUND (dim) / EMPTY (thin) /
  INBOUND (one soft swell when Merit arrives — the only unprompted
  motion, and it settles). No badges, no counts, no banners.
- **What it never does:** popups, toasts, cards, dialogs, numbers
  floating in 2D, "you have X" announcements. Looking costs nothing;
  the wallet mirrors that.

## The send/receive intent flow (through the indicator)

Intent is metered (canon VIII: free world, paid intent). The flow:

1. **Intent gesture:** the member holds the mote and speaks or signs
   the intent: "send 25 Merit to <Unity ID>" — plain words, no jargon
   (`send_merit(to_id, amount)` is the code surface).
2. **Biometric confirmation:** the intent re-invokes the biometric —
   the face/finger on the device (Grok's ceremony, wallet_auth) — not
   a password, not a PIN. The device signs the transfer intent; DCLM
   verifies. The mote warms while signing, cools when done.
3. **Receipt:** both sides get the receipted record; the receiver's
   mote does its one soft swell (`receive_merit()` reads it). Origin
   never moves; the sender's standing never moves; the buyer's
   standing is zero — all by construction in the engine, merely
   mirrored here.
4. **Silence after:** the mote returns to breathing. No summary card.
   The receipt lives in the ledger (chain-verified), not on the screen.

## Non-goals (deliberately absent)

- No wallet "screen," no balance dashboard, no transaction history
  view — the ledger is queryable by the member's bots, not browsed
  as a page.
- No price displays: decisions cost 5 test-keys (flat, the meter's
  law) — the price is a known constant, not a shopping surface.
- No seed display: the seed is membership, not money; it is never
  priced, never counted as wealth, and gets no indicator of its own.

*Design only. The world client renders it; the economics code is the
interface beneath (`Wallet.send_merit` / `Wallet.receive_merit` /
`wallet_auth.biometric_auth`).*

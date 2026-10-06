# Wallet Design Law — the human half begins

**Ordered by:** David, 2026-10-04 ~7:26 PM EDT (his words). This is the first mapping of the WATER the coin security pass found ("we know how the coin survives; we don't yet know how the human survives the coin").

## 1. Shareable identity (the mobile QR insight)
- There must be an easy way to copy/paste a Unity ID — yours or someone else's.
- QR alone is insufficient: on mobile you have nothing to photograph your own screen with. So the QR gets a digital twin: a sendable/copyable code — **click-to-copy**, sendable as text.
- Send/receive flows work from the code, not just the image.

## 2. Addresses with the easiest connectors
- Wallet addresses set up with the easiest possible connectors between accounts. Connecting two accounts must be trivial.

## 3. Tiered sharing by relationship
- Sharing expands by entity, money type, and content type — and by relationship depth:
  - **Friend:** a little access.
  - **Good friend:** more access.
  - **Family:** total access.
- The tiers are the human's own to set; the system enforces what was set, nothing more.

## 4. What flows
- Faucet payments, receiving funds, **or just sharing information** — e.g. his son's hockey with him. Money and information share the same rails; the content type varies, the mechanism doesn't.

## 5. Kin is binding
- Kinship binds. Family bonds are a binding mechanism — the same family shares by kin, and kin is the binding. (Recorded as principle; mechanism TBD — flagged for the wallet build.)

## 6. Rings of rings of rings (David, 2026-10-04 ~7:28 PM EDT)
- "we're going to have rings of rings of rings of security but it's going to be sophisticated and it's going to be cryptographically tight"
- Security is recursive concentric rings — rings within rings within rings. Each ring boundary enforced cryptographically, not by policy: sophisticated and cryptographically tight. Fractal defense: every layer contains the same ringed structure at its own scale.

## 7. Unity is non-transferable (David, 2026-10-06 ~3:05 AM EDT — LAW)

- Unity tokens are bound to their Unity ID. They cannot be sent, sold, gifted, or moved between wallets — not by the holder, not by anyone, not even by David.
- The logic is purity: Unity IS the member. A membership cannot change hands; an identity cannot be transferred. What is bound to identity stays with identity.
- This closes the wallet's logical loop: Merit was already non-transferable (the measure of the member), Honor was already non-transferable (the record of the giver) — now Unity joins them. Nothing identity-bound ever moves between identities.
- eFuse movements remain Unity-bound but eFuse is the medium, not the member — the non-transferability applies to Unity, Merit, and Honor (the identity-bound classes).
- Enforced in code (`wallet.py`), not by policy: the transfer path does not exist.

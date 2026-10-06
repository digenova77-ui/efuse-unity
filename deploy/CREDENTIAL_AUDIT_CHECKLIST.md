# CREDENTIAL AUDIT CHECKLIST — for David's validation

**Purpose:** You validate your credentials with an audit. What exists, what works, what's scoped correctly, what stays sealed.

## Credentials in play

| Credential | Purpose | Where stored | Validation |
|------------|---------|--------------|------------|
| Cloudflare API | Worker deploy, DNS | **YOUR HANDS ONLY** — not in workspace | See Step 1 |
| Pinata (`custom.pinata`) | IPFS pinning | Secure vault (connected) | See Step 2 |
| Testnet keys (3) | Test signing | `~/workspace/testnet/keys/` (0600) | See Step 3 — must NEVER ship |
| Wallet key | Production IPNS | `~/workspace/ipfs-publish/wallet.key` | See Step 3 — must NEVER ship |

## Step 1 — Cloudflare credential validation

- [ ] You hold the Cloudflare API token (or you're logged into the dashboard)
- [ ] Token scope: Workers deploy + DNS edit for dualiscapax.ai (minimum necessary)
- [ ] Test: can you list workers? Can you push a test worker?
- [ ] **Audit verifies:** the token works, the scope is correct, the token is NOT in any workspace file, log, or repo

## Step 2 — Pinata credential validation

```bash
python3 ~/workspace/skills/pinata/bin/pinata.py auth
```

- [ ] Returns "Congratulations! You are communicating with the Pinata API!"
- [ ] **Audit verifies:** pinning works, the credential is via secure vault (never a raw key in files)

## Step 3 — Secrets containment audit

```bash
# These MUST exist (they're real) but MUST NOT be in the ship:
ls -la ~/workspace/testnet/keys/          # 3 test keys, 0600
ls -la ~/workspace/ipfs-publish/wallet.key # production key
```

- [ ] Testnet keys exist and are 0600
- [ ] Wallet key exists and is NOT in `~/workspace/unity-world/` (ship scope)
- [ ] `SHIP_MANIFEST.md` contains zero `.key` files (verify: `grep -c "\.key" SHIP_MANIFEST.md` → 0)
- [ ] **Audit verifies:** secrets exist where they should, nowhere they shouldn't

## Step 4 — Passphrase purity

- [ ] No passphrase, seed phrase, or secret appears in: ship files, IPFS pins, logs, receipts, git history
- [ ] `SECRETS_AUDIT.md` confirms zero findings (re-run if the tree changed)
- [ ] **Audit verifies:** the shippable artifact is clean — secrets never touched it

## Sign-off

When all boxes are checked, the credentials are validated and the audit is clean. The build is ready for your hands.

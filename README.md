# x402 payment rail

Crypto-to-crypto HTTP payments for anything. Implements the open
[x402](https://x402.org) v2 protocol (scheme `"exact"`, EIP-3009
`TransferWithAuthorization`): a service answers unpaid requests with
`402 Payment Required`, the payer signs an authorization and retries with
`X-Payment`, the service verifies the signature, settles via a facilitator,
serves, and writes a hash-chained payment receipt.

## Layout

| File | What |
|---|---|
| `rail/protocol.py` | x402 v2 wire shapes, networks, EIP-712 typed data |
| `rail/signer.py` | client-side EIP-3009 signing |
| `rail/verifier.py` | server-side verification (fail-closed; replay protection) |
| `rail/facilitator.py` | settlement: `LocalTestFacilitator` (simulated) / `CoinbaseFacilitator` (real, designed) |
| `rail/economy.py` | Merit-denominated pricing, the 1% residual split |
| `rail/receipts.py` | payment receipts as hash-chained collapse traces |
| `rail/middleware.py` | framework-agnostic WSGI 402 gate |
| `rail/client.py` | pay-and-retry HTTP client (stdlib) |
| `rail/demo.py` | demo server |

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install eth-account pytest
.venv/bin/python -m pytest tests/ -q   # 14 tests, simulated settlement
.venv/bin/python -m rail.demo --port 8099
```

Then, unpaid → 402, paid → 200:

```python
from rail.client import x402_get
status, body, receipt = x402_get("http://127.0.0.1:8099/metered", private_key=KEY)
```

## Money rules

- **Testnet default.** Base Sepolia (`eip155:84532`). Mainnet constructs only
  with an explicit opt-in; the test suite never touches a real rail.
- **Simulated settlement is labeled.** `LocalTestFacilitator` receipts carry
  `settlement_kind="simulated"` and `sim:<uuid>` references. No transaction
  hash is ever invented.
- **1% residual.** Every settled payment splits: 1% to the residual address,
  99% to the service (integer math, no dust). The residual leg is a
  service-initiated forward, never a second payer authorization.
- **No receipt = no payment.** The middleware refuses to serve unless the
  receipt was appended to the hash-chained ledger. Receipts are public at
  `/receipts`.
- **Merit is a unit of account, not a token.** Settlement is USDC on a real
  rail. No fiat on/off ramps — that's the adopter's department.

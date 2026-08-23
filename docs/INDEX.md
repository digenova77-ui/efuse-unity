# Indexes

## Master

| Id | Topic |
|----|--------|
| IX-SEAL | UNITY_SEAL_v1 |
| IX-MIRROR | 0\|1 |
| IX-ACCEPT | pipeline |
| IX-COIN | ESCROW/PURE/SPENT |
| IX-PURE | cost paid before title |
| IX-EVID | Merkle |
| IX-TIP | append-only |
| IX-FU | F_U vs F_clearable |
| IX-RAIL | BTC/ETH Gate A |
| IX-LIMIT | not TOE |

## Coin states

ESCROW → PURE → SPENT

## Pipeline

RF5, RF6, GateA, GateB, evidence_ok, spend, Mirror

## Forbidden as marks

- everybody-paid-everything gate  
- L1 = Accept  
- F_U = 0 by token balance  

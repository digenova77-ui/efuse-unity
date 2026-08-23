# Quantum posture — eFuse reference stack

## Direct answer

**Is the token “quantum-proof”?**  
**No — not as a certified post-quantum product.**

## What the reference engine actually uses

| Component | Primitive | Quantum note |
|-----------|-----------|--------------|
| Merkle leaves/nodes | SHA-256 with domain tags (`0x00` leaf, `0x01` node) | Hash-based integrity; Shor does **not** break SHA-256 like RSA/ECDSA |
| Seal / tip hashing | SHA-256 family | Same |
| Ownership signatures (PQ suite) | **Not present** as ML-DSA / SLH-DSA / etc. in reference `src/efuse` | Would be required for a full PQ *signing* story |

## Honest threat model

1. **Shor’s algorithm** threatens widely used **public-key** schemes (RSA, finite-field/elliptic discrete log). A design that **only** relies on SHA-256 Merkle integrity for *document/state integrity* is in a different category than ECDSA-secured UTXOs.
2. **Grover’s algorithm** offers a generic quadratic speedup for unstructured search, often summarized as “effective security bits ≈ half” for symmetric primitives in that model. SHA-256 remains widely used; calling it “quantum-proof” without parameters and review is marketing, not engineering.
3. **Migration** to NIST PQC (e.g. ML-KEM, ML-DSA, SLH-DSA) is a **separate product decision**: new primitives, new tests, new operational discipline.

## DualisCapax / Gate A

Quantum slogans do **not** replace:

- traceable money under law  
- institutional KYC  
- FINTRAC / securities registration when activities require them  

## Website

Live surface states: `PQ: integrity-hash · not full PQ suite` and `gateway: not built`.

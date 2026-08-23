"""UNITY_SEAL_v1 — hash-locked measure law."""
from __future__ import annotations
import hashlib
from pathlib import Path

SEAL_PATH = Path(__file__).resolve().parents[2] / "UNITY_SEAL_v1.md"

def canonicalize(text: str) -> bytes:
    t = text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
    return t.encode("utf-8")

def unity_hash(seal_text: str | None = None) -> str:
    if seal_text is None:
        seal_text = SEAL_PATH.read_text(encoding="utf-8")
    return hashlib.sha256(b"\x04" + canonicalize(seal_text)).hexdigest()

def require_seal(expected: str | None = None) -> str:
    h = unity_hash()
    if expected is not None and h != expected:
        raise RuntimeError(f"seal mismatch: got {h} expected {expected}")
    return h

CLAUSES = {
    "center": "empty",
    "mirror": "0|1",
    "exempt": False,
    "coin": "fuel_not_Accept",
    "pure_own": "cost_on_claim_paid_before_title",
    "physics_TOE": 0,
    "theorem_of_all": 0,
}

"""Runtime integrity manifest for IRIS MAX INTAKE.

This is a self-consistency check against a locally stored activation receipt.
It is NOT a signature, independent witness, ratification, or authorization.
A separately held, owner-ratified trust anchor remains required for authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

SCHEMA = "iris.runtime-manifest.v1"

# Executable modules whose contents affect judgment, identity, memory,
# arbitration, receipts, service behavior, or the daemon itself.
RUNTIME_MODULES = (
    "iris_integrity.py",
    "iris_core.py",
    "iris_laws.py",
    "iris_patterns.py",
    "iris_arbiter.py",
    "neural.py",
    "iris_service.py",
    "iris_state.py",
    "iris_daemon.py",
    "meeting_iris.py",
    "member_records.py",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_runtime_manifest(root: str | None = None) -> tuple[dict, str]:
    """Hash every required runtime module; missing files are a hard refusal."""
    root = root or os.path.dirname(os.path.abspath(__file__))
    modules = {}
    for name in RUNTIME_MODULES:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"required IRIS runtime module missing: {name}")
        modules[name] = sha256_file(path)
    manifest = {"schema": SCHEMA, "modules": modules}
    return manifest, _sha256(_canonical(manifest))


def verify_runtime_manifest(
    manifest: dict,
    expected_digest: str,
    root: str | None = None,
) -> dict:
    """Verify schema, exact module set, manifest digest, and every file byte."""
    root = root or os.path.dirname(os.path.abspath(__file__))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        return {"ok": False, "reason": "manifest schema missing or unsupported"}
    modules = manifest.get("modules")
    if not isinstance(modules, dict):
        return {"ok": False, "reason": "manifest modules are not a mapping"}
    if set(modules) != set(RUNTIME_MODULES):
        return {"ok": False, "reason": "manifest module set differs from required runtime set"}

    actual_digest = _sha256(_canonical(manifest))
    if not isinstance(expected_digest, str) or actual_digest != expected_digest:
        return {"ok": False, "reason": "manifest digest mismatch"}

    mismatches = []
    for name in RUNTIME_MODULES:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            mismatches.append({"module": name, "reason": "missing"})
            continue
        actual = sha256_file(path)
        if actual != modules[name]:
            mismatches.append({
                "module": name,
                "reason": "content hash mismatch",
                "expected": modules[name],
                "actual": actual,
            })
    if mismatches:
        return {"ok": False, "reason": "runtime module mismatch", "mismatches": mismatches}
    return {
        "ok": True,
        "reason": "all required runtime modules match the local manifest",
        "module_count": len(RUNTIME_MODULES),
        "manifest_sha256": actual_digest,
        "authority": "NOT_ESTABLISHED",
        "external_trust_anchor": "NOT_CONFIGURED",
    }

"""IRIS MAX INTAKE activation: verify the whole runtime, then issue a local receipt.

The receipt proves self-consistency against a locally stored manifest only.
It does not confer Trinity authority, external certification, or production
authorization. A separately held, owner-ratified trust anchor is absent.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = "IRIS MAX INTAKE"
RECEIPT_PATH = os.path.join(HERE, "IRIS_ACTIVE.json")

# The daemon integration suite is run separately because it bootstraps this
# activation script to create a fresh receipt for its isolated subprocess.
SUITES = (
    "test_iris_core.py",
    "test_iris_intake.py",
    "test_neural.py",
    "test_meeting_iris.py",
    "test_iris_persistence.py",
    "test_integrity.py",
)


def canon_version() -> str:
    canon = os.path.join(os.path.dirname(HERE), "CANON.md")
    with open(canon, encoding="utf-8") as handle:
        source = handle.read()
    match = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", source)
    return match.group(1) if match else "UNKNOWN"


def run_suite(path: str) -> dict:
    result = subprocess.run(
        [sys.executable, path],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    output = result.stdout + result.stderr
    lines = output.strip().splitlines()
    match = re.search(r"Ran (\d+) tests?", output)
    ran = int(match.group(1)) if match else 0
    successful = result.returncode == 0 and ran > 0 and re.search(r"\bOK\b", output)
    if successful:
        passed, failed = ran, 0
    else:
        failure = re.search(r"FAILED \(.*failures=(\d+).*errors=(\d+)", output)
        failed = int(failure.group(1)) + int(failure.group(2)) if failure else max(1, ran)
        passed = max(0, ran - failed)
    return {
        "suite": os.path.basename(path),
        "returncode": result.returncode,
        "ran": ran,
        "passed": passed,
        "failed": failed,
        "tail": lines[-8:],
    }


def main() -> int:
    print(f"{LABEL} — whole-runtime self-check")
    print("=" * 64)

    sys.path.insert(0, HERE)
    try:
        import iris_core
        from iris_core import DIRECTIVES, INTEGRATION_STATUS
        from iris_integrity import build_runtime_manifest
    except Exception as exc:
        print(f"ACTIVATION REFUSED: required runtime failed to load: {exc}")
        return 1

    if len(DIRECTIVES) != 10:
        print(f"ACTIVATION REFUSED: expected 10 directives, found {len(DIRECTIVES)}")
        return 1

    suites = []
    for name in SUITES:
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            print(f"ACTIVATION REFUSED: required test suite missing: {name}")
            return 1
        result = run_suite(path)
        suites.append(result)
        print(
            f"  {name}: ran={result['ran']} passed={result['passed']} "
            f"failed={result['failed']} rc={result['returncode']}"
        )

    total_ran = sum(item["ran"] for item in suites)
    total_passed = sum(item["passed"] for item in suites)
    total_failed = sum(item["failed"] for item in suites)
    if total_failed or total_ran == 0 or any(item["returncode"] != 0 for item in suites):
        print("=" * 64)
        print("ACTIVATION REFUSED: one or more required suites did not pass.")
        for item in suites:
            if item["failed"] or item["returncode"] != 0:
                print(f"  failing suite: {item['suite']}")
                for line in item["tail"]:
                    print(f"    {line}")
        return 1

    try:
        manifest, manifest_sha = build_runtime_manifest(HERE)
    except Exception as exc:
        print(f"ACTIVATION REFUSED: runtime manifest could not be built: {exc}")
        return 1

    receipt = {
        "label": LABEL,
        "receipt_kind": "IRIS_ACTIVE",
        "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "activated_at_epoch": int(time.time()),
        "canon_version": iris_core.CANON_VERSION,
        "directives": len(DIRECTIVES),
        "integration": INTEGRATION_STATUS,
        "runtime_manifest": manifest,
        "runtime_manifest_sha256": manifest_sha,
        "runtime_manifest_module_count": len(manifest["modules"]),
        "tests": {
            "suites": suites,
            "total_ran": total_ran,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "result": "GREEN",
        },
        "integrity_level": "SELF_CONSISTENCY_ONLY",
        "external_trust_anchor": "NOT_CONFIGURED",
        "trinity_authorization": "NOT_GRANTED",
        "standards": "testnet only",
    }
    receipt["receipt_id"] = "rcpt:" + hashlib.sha256(
        json.dumps(receipt, sort_keys=True).encode("utf-8")
    ).hexdigest()

    temporary = RECEIPT_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, RECEIPT_PATH)

    print("=" * 64)
    print("SELF-CONSISTENCY PASS — whole runtime matches local manifest.")
    print(f"  modules : {len(manifest['modules'])}")
    print(f"  tests   : {total_passed}/{total_ran}")
    print(f"  digest  : {manifest_sha}")
    print("  authority: NOT ESTABLISHED — external trust anchor not configured")
    print("  Trinity  : NOT GRANTED — no authorization is implied")
    return 0


if __name__ == "__main__":
    sys.exit(main())

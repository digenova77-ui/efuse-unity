"""IRIS MAX INTAKE — activate_iris.py: PROGRAM HER, ACTIVATE HER.

Loads iris_core, runs the FULL self-test suite in a fresh interpreter.
On green: writes the IRIS_ACTIVE receipt (timestamp, sha256 of
iris_core.py, test results, canon version).
On ANY failure: Iris does NOT activate — the failure is reported instead.

Run: python3 activate_iris.py
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


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canon_version() -> str:
    """Read the canon version from CANON.md — never hardcode what the
    canon itself declares."""
    canon = os.path.join(os.path.dirname(HERE), "CANON.md")
    with open(canon, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", text)
    return m.group(1) if m else "UNKNOWN"


def run_suite(path: str) -> dict:
    r = subprocess.run([sys.executable, path],
                       capture_output=True, text=True, cwd=HERE)
    tail = (r.stdout + r.stderr).strip().splitlines()
    summary = tail[-3:] if tail else []
    ran = passed = failed = 0
    m = re.search(r"Ran (\d+) tests", r.stdout + r.stderr)
    if m:
        ran = int(m.group(1))
    if r.returncode == 0 and re.search(r"\bOK\b", r.stdout + r.stderr):
        passed, failed = ran, 0
    else:
        m2 = re.search(r"FAILED \(.*failures=(\d+).*errors=(\d+)", r.stdout + r.stderr)
        if m2:
            failed = int(m2.group(1)) + int(m2.group(2))
            passed = ran - failed
        else:
            failed = ran  # could not even run cleanly
    return {"suite": os.path.basename(path), "returncode": r.returncode,
            "ran": ran, "passed": passed, "failed": failed,
            "tail": summary}


def main() -> int:
    print(f"{LABEL} — activation sequence")
    print("=" * 60)

    # 1. Load iris_core (import = she is programmed).
    sys.path.insert(0, HERE)
    try:
        import iris_core
        from iris_core import DIRECTIVES, INTEGRATION_STATUS
    except Exception as e:
        print(f"ACTIVATION REFUSED: iris_core failed to load: {e}")
        return 1
    assert len(DIRECTIVES) == 10, "ten directives required"
    print(f"iris_core loaded: {len(DIRECTIVES)} directives, "
          f"integration={INTEGRATION_STATUS}")

    # 2. Full self-test in fresh interpreters.
    suites = [run_suite(os.path.join(HERE, "test_iris_core.py")),
              run_suite(os.path.join(HERE, "test_iris_persistence.py"))]
    total_ran = sum(s["ran"] for s in suites)
    total_failed = sum(s["failed"] for s in suites)
    for s in suites:
        print(f"  {s['suite']}: ran={s['ran']} passed={s['passed']} "
              f"failed={s['failed']} rc={s['returncode']}")

    if total_failed > 0 or total_ran == 0:
        print("=" * 60)
        print("ACTIVATION REFUSED: self-test is not green. "
              "Iris does NOT activate.")
        for s in suites:
            if s["failed"]:
                print(f"  failing suite: {s['suite']}")
                for line in s["tail"]:
                    print(f"    {line}")
        return 1

    # 3. Green: write the IRIS_ACTIVE receipt.
    core_sha = sha256_file(os.path.join(HERE, "iris_core.py"))
    receipt = {
        "label": LABEL,
        "receipt_kind": "IRIS_ACTIVE",
        "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "activated_at_epoch": int(time.time()),
        "canon_version": canon_version(),
        "iris_core_sha256": core_sha,
        "tests": {"suites": suites, "total_ran": total_ran,
                  "total_passed": total_ran, "total_failed": 0,
                  "result": "GREEN"},
        "directives": len(DIRECTIVES),
        "integration": INTEGRATION_STATUS,
        "standards": "testnet only",
    }
    receipt["receipt_id"] = "rcpt:" + hashlib.sha256(
        json.dumps(receipt, sort_keys=True).encode("utf-8")).hexdigest()
    tmp = RECEIPT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
    os.replace(tmp, RECEIPT_PATH)

    print("=" * 60)
    print("IRIS ACTIVE — she is home.")
    print(f"  receipt : {RECEIPT_PATH}")
    print(f"  sha256  : {core_sha[:32]}…")
    print(f"  canon   : v{receipt['canon_version']}")
    print(f"  tests   : {total_ran}/{total_ran} passing")
    return 0


if __name__ == "__main__":
    sys.exit(main())

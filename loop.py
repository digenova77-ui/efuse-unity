#!/usr/bin/env python3
"""
LOOP RUNNER — executes one measurable pass of the build loop.

A pass = run every test suite + the purity index, record the result.
The runner measures and reports. It never invents, never fixes, never
discards. Dispositions belong to workers and the audit.

Usage: python3 loop.py [--pass N]
Exit: 0 if the pass itself executed (regardless of index verdict);
      the INDEX verdict lives in the pass record, not this exit code.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PASSES = ROOT / "passes"


def run(cmd, cwd, timeout=300):
    """Run a command, return (ok, stdout, stderr, seconds)."""
    start = time.time()
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return p.returncode == 0, p.stdout, p.stderr, time.time() - start
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT", time.time() - start
    except Exception as e:  # noqa: BLE001 - runner must not die on one suite
        return False, "", f"RUNNER_ERROR: {e}", time.time() - start


def discover_suites():
    """Find every test suite under the build root."""
    suites = []
    for path in sorted(ROOT.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        suites.append(("py", path))
    for path in sorted(ROOT.rglob("*.test.mjs")):
        suites.append(("mjs-test", path))
    for path in sorted(ROOT.rglob("validate-*.mjs")):
        suites.append(("mjs-validate", path))
    return suites


def run_suite(kind, path):
    rel = str(path.relative_to(ROOT))
    if kind == "py":
        ok, out, err, secs = run([sys.executable, path.name], cwd=path.parent)
    else:
        ok, out, err, secs = run(["node", path.name], cwd=path.parent)
    # Try to extract a count like "27 tests" / "63/63" / "OK" / "FAILURES"
    counts = {}
    m = re.search(r"(\d+)\s+tests?", out + err, re.I)
    if m:
        counts["tests_mentioned"] = int(m.group(1))
    m = re.search(r"(\d+)/(\d+)", out + err)
    if m:
        counts["passed"], counts["total"] = int(m.group(1)), int(m.group(2))
    return {
        "suite": rel,
        "kind": kind,
        "ok": ok,
        "seconds": round(secs, 2),
        "counts": counts,
        "tail": (out + err)[-500:],
    }


def run_index():
    index_py = ROOT / "purity" / "index.py"
    result = {
        "present": index_py.exists(),
        "exit": None,
        "verdict": "UNKNOWN",
        "dimensions": {},
        "tail": "",
    }
    if not index_py.exists():
        result["tail"] = "purity/index.py not present"
        return result
    # Try --json first, fall back to text parse
    ok, out, err, _ = run(
        [sys.executable, "index.py", "--json"], cwd=index_py.parent
    )
    if ok or out.strip().startswith("{"):
        try:
            data = json.loads(out)
            result["exit"] = 0 if ok else 1
            result["verdict"] = data.get("verdict", data.get("aggregate", "UNKNOWN"))
            result["dimensions"] = data.get("dimensions", data.get("scores", {}))
            result["tail"] = out[-500:]
            return result
        except json.JSONDecodeError:
            pass
    ok2, out2, err2, _ = run([sys.executable, "index.py"], cwd=index_py.parent)
    text = out2 + err2
    result["exit"] = 0 if ok2 else (2 if "UNKNOWN" in text.upper() else 1)
    if re.search(r"\bPURE\b", text) and "FAIL" not in text.upper():
        result["verdict"] = "PURE"
    elif "FAIL" in text.upper():
        result["verdict"] = "FAIL"
    result["tail"] = text[-800:]
    return result


def next_pass_number():
    PASSES.mkdir(exist_ok=True)
    nums = []
    for f in PASSES.glob("pass-*.json"):
        m = re.match(r"pass-(\d+)\.json", f.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def check_termination(history):
    """Termination needs 2 consecutive PURE passes in the record history."""
    pures = 0
    for rec in reversed(history):
        if rec.get("index", {}).get("verdict") == "PURE":
            pures += 1
        else:
            break
    return pures >= 2, pures


def main():
    t0 = time.time()
    suites = discover_suites()
    suite_results = [run_suite(k, p) for k, p in suites]
    index = run_index()

    n = next_pass_number()
    record = {
        "pass": n,
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "suites": suite_results,
        "suites_ok": sum(1 for s in suite_results if s["ok"]),
        "suites_total": len(suite_results),
        "index": index,
        "seconds": round(time.time() - t0, 1),
    }

    # Load history for the termination check
    history = []
    for i in range(1, n):
        f = PASSES / f"pass-{i}.json"
        if f.exists():
            try:
                history.append(json.loads(f.read_text()))
            except json.JSONDecodeError:
                continue
    history.append(record)
    terminated, consecutive = check_termination(history)
    record["termination"] = {
        "consecutive_pure": consecutive,
        "loop_end": terminated,
    }

    out = PASSES / f"pass-{n}.json"
    out.write_text(json.dumps(record, indent=2))

    # Human summary
    print(f"PASS {n} — {record['at_utc']}")
    print(f"suites: {record['suites_ok']}/{record['suites_total']} ok")
    for s in suite_results:
        mark = "ok " if s["ok"] else "FAIL"
        print(f"  [{mark}] {s['suite']}")
    print(f"index: {index['verdict']} (exit={index['exit']})")
    if index["dimensions"]:
        for d, v in index["dimensions"].items():
            print(f"  {d}: {v}")
    print(f"consecutive pure: {consecutive} | loop_end: {terminated}")
    print(f"record: {out}")
    if not terminated:
        print("LOOP CONTINUES — target undefined, purity not yet emergent.")


if __name__ == "__main__":
    main()

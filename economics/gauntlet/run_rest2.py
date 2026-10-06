#!/usr/bin/env python3
"""Re-run pipeline + expansion after the assertion fix. Appends to run_rest2.log."""
import sys, os, time, json
sys.path.insert(0, os.path.expanduser("~/workspace/unity-world/economics/gauntlet"))
import gauntlet as G

t0 = time.perf_counter()
G.sec_pipeline()
G.sec_expansion()
dt = time.perf_counter() - t0
G.RESULTS["elapsed_sec_rest2"] = round(dt, 1)
n_atk = sum(len(s["attacks"]) for s in G.RESULTS["sections"].values())
n_held = sum(1 for s in G.RESULTS["sections"].values()
             for a in s["attacks"] if a["status"] == "HELD")
n_broke = sum(1 for s in G.RESULTS["sections"].values()
              for a in s["attacks"] if a["status"] == "BROKE")
print(f"\nREST2 SUMMARY: attacks {n_atk} (HELD {n_held} / BROKE {n_broke}) | "
      f"CRITICALs {len(G.RESULTS['criticals'])} | {dt:.1f}s", flush=True)
for c in G.RESULTS["criticals"]:
    print("CRITICAL:", c["title"], flush=True)
with open(os.path.expanduser(
        "~/workspace/unity-world/economics/gauntlet/results_rest2.json"),
        "w") as fh:
    json.dump(G.RESULTS, fh, indent=2, sort_keys=True)
print("results_rest2.json written", flush=True)

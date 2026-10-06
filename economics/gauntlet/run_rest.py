#!/usr/bin/env python3
"""Run the gauntlet sections that did not complete in the timed-out run:
sec_efuse (re-run, fixed assertions), unity double-credit recheck,
sec_pipeline, sec_expansion. Appends to run_rest.log."""
import sys, os, time, json, uuid
sys.path.insert(0, os.path.expanduser("~/workspace/unity-world/economics/gauntlet"))
import gauntlet as G
import wallet as W

# -- unity double-credit recheck (corrected balance comparison) --
G.start("3b. Unity double-credit recheck")
ledger = W.Ledger()
v = G.new_identity()
wv = G.open_wallet(ledger, v)
r = G.emission_receipt_for(v["uid"], 5, W.TOKEN_UNITY, uuid.uuid4().hex)
W.receive_unity_emission(wv, 5, r)
mid = G.un(wv)
W.receive_unity_emission(wv, 5, r)  # replay
after = G.un(wv)
G.log_attack("unity double-credit same receipt (recheck)",
             "receive_unity_emission x2, compare balances",
             "HELD" if after == mid else "BROKE",
             f"balance {mid} -> {after}; idempotent" if after == mid
             else "DOUBLE CREDIT")
assert after == mid == 5

t0 = time.perf_counter()
G.sec_efuse()
G.sec_pipeline()
G.sec_expansion()
dt = time.perf_counter() - t0
G.RESULTS["elapsed_sec_rest"] = round(dt, 1)
n_atk = sum(len(s["attacks"]) for s in G.RESULTS["sections"].values())
n_held = sum(1 for s in G.RESULTS["sections"].values()
             for a in s["attacks"] if a["status"] == "HELD")
n_broke = sum(1 for s in G.RESULTS["sections"].values()
              for a in s["attacks"] if a["status"] == "BROKE")
print(f"\nREST SUMMARY: attacks {n_atk} (HELD {n_held} / BROKE {n_broke}) | "
      f"CRITICALs {len(G.RESULTS['criticals'])} | {dt:.1f}s", flush=True)
for c in G.RESULTS["criticals"]:
    print("CRITICAL:", c["title"], flush=True)
with open(os.path.expanduser(
        "~/workspace/unity-world/economics/gauntlet/results_rest.json"),
        "w") as fh:
    json.dump(G.RESULTS, fh, indent=2, sort_keys=True)
print("results_rest.json written", flush=True)

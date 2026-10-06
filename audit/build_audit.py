#!/usr/bin/env python3
"""Build the 2D derivative audit site data files from real sources.

VIEW ONLY: this script parses recorded data (logs, ledgers, manifests, registries)
into static JSON for the audit site. It recomputes nothing of DCLM's; drift
checks below are labeled AUDIT-BUILD (method named) and are not DCLM seals.
"""
import json, re, hashlib, os, datetime

UW = os.path.expanduser("~/workspace/unity-world")
OUT = os.path.join(UW, "audit", "data")
os.makedirs(OUT, exist_ok=True)
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def dump(name, obj):
    p = os.path.join(OUT, name)
    with open(p, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    print("wrote", name, os.path.getsize(p), "bytes")

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_md_tables(text, section_header_re):
    """Return {section_title: {columns:[], rows:[{}]}} for pipe tables under matching sections."""
    lines = text.splitlines()
    out, cur, in_table, cols = {}, None, False, None
    for line in lines:
        m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1).strip()
            in_table = False; cols = None
            continue
        if cur is None or not section_header_re.search(cur):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.match(r"^\|[\s\-|:]+\|$", line.strip()) and in_table is False and cols is not None:
            in_table = True
            continue
        if line.strip().startswith("|") and cols is None:
            cols = cells
            continue
        if in_table and line.strip().startswith("|"):
            row = {cols[i] if i < len(cols) else f"col{i}": (cells[i] if i < len(cells) else "") for i in range(len(cols))}
            out.setdefault(cur, {"columns": cols, "rows": []})["rows"].append(row)
        else:
            in_table = False; cols = None
    return out

# ---------- 1. epoch chain ----------
chain_events = []
log_path = os.path.join(UW, "dclm/chunk_receipts.log")
for line in open(log_path):
    line = line.strip()
    if line:
        chain_events.append(json.loads(line))

built = {}
for e in chain_events:
    if e["action"] == "epoch_built":
        built[e["world_epoch"]] = e

manifest_of = {we: e["manifest_hash"] for we, e in built.items()}
edges, forks_map = [], {}
link_results = []
for we, e in sorted(built.items()):
    pe, pm = e.get("previous_epoch"), e.get("previous_manifest_hash")
    if pe is None or pm is None:
        status = "GENESIS"
    elif pe not in manifest_of:
        status = "PARENT-MISSING"
    elif manifest_of[pe] == pm:
        status = "OK"
        edges.append({"from": pe, "to": we})
    else:
        status = "BROKEN"
    if pe is not None and pe in manifest_of and status in ("OK",):
        forks_map.setdefault(pe, []).append(we)
    link_results.append({"epoch": we, "previous_epoch": pe, "status": status})

forks = [{"parent": p, "children": sorted(c)} for p, c in sorted(forks_map.items()) if len(c) > 1]
ok = sum(1 for r in link_results if r["status"] == "OK")
genesis = [r["epoch"] for r in link_results if r["status"] == "GENESIS"]
broken = [r for r in link_results if r["status"] == "BROKEN"]

chain = {
    "source": "dclm/chunk_receipts.log",
    "provenance": "REPORTED",
    "label": "Recorded by dclm/chunks.py during epoch builds; this site displays and link-checks it.",
    "generated_at": NOW,
    "stats": {
        "total_events": len(chain_events),
        "epoch_bumped": sum(1 for e in chain_events if e["action"] == "epoch_bumped"),
        "epoch_built": len(built),
        "schema_bumps": sum(1 for e in chain_events if e["action"] == "schema_version_bumped"),
        "fork_points": len(forks),
        "links_ok": ok, "links_broken": len(broken),
    },
    "epochs": [
        {
            "epoch": we,
            "at": e["at"],
            "action": "epoch_built",
            "manifest_hash": e["manifest_hash"],
            "previous_epoch": e.get("previous_epoch"),
            "previous_manifest_hash": e.get("previous_manifest_hash"),
            "chunk_count": e["chunk_count"],
            "total_bytes": e["total_bytes"],
            "schema_version": e["schema_version"],
            "datasets": e["datasets"],
            "link_status": next(r["status"] for r in link_results if r["epoch"] == we),
        } for we, e in sorted(built.items())
    ],
    "events_raw": chain_events,
    "edges": edges,
    "forks": forks,
    "verify_summary": {"checked": len(link_results), "ok": ok, "genesis": genesis, "broken": broken},
}
dump("chain.json", chain)

# ---------- 2. gate state chain ----------
gate_receipts = [json.loads(l) for l in open(os.path.join(UW, "gate/state/receipts.jsonl")) if l.strip()]
gate_links = []
for i, r in enumerate(gate_receipts):
    if i == 0:
        status = "GENESIS"
    else:
        status = "OK" if gate_receipts[i-1]["new_state_sha256"] == r["prev_state_sha256"] else "BROKEN"
    gate_links.append(status)
gate = {
    "source": "gate/state/receipts.jsonl + gate/state/gate-state.json",
    "provenance": "REPORTED",
    "label": "Recorded by gate/gate.py during the binding ceremony (test stub verifier).",
    "generated_at": NOW,
    "chain_tip": gate_receipts[-1]["new_state_sha256"],
    "mutations": len(gate_receipts),
    "receipts": [{**r, "link_status": gate_links[i]} for i, r in enumerate(gate_receipts)],
    "verify_summary": {"checked": len(gate_receipts), "ok": sum(1 for s in gate_links if s == "OK"), "broken": sum(1 for s in gate_links if s == "BROKEN")},
}
dump("gate.json", gate)

# ---------- 3. ship manifest + registry manifest (with audit-build drift check) ----------
def parse_simple_table(md_path):
    rows = []
    cols = None
    in_table = False
    for line in open(md_path):
        s = line.strip()
        if not s.startswith("|"):
            in_table = False; cols = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if re.match(r"^\|[\s\-|:]+\|$", s):
            in_table = bool(cols); continue
        if cols is None:
            cols = cells; continue
        if in_table:
            rows.append({cols[i] if i < len(cols) else f"c{i}": (cells[i] if i < len(cells) else "") for i in range(len(cols))})
    return cols, rows

ship_cols, ship_rows = parse_simple_table(os.path.join(UW, "deploy/SHIP_MANIFEST.md"))
ship_files = []
for r in ship_rows:
    if not r.get("File"):
        continue
    rel = r["File"].strip("`")
    full = os.path.join(UW, rel)
    entry = {"file": rel, "size_manifest": r.get("Size (bytes)", ""), "sha256_manifest": r.get("sha256", "").strip("`")}
    if os.path.exists(full):
        cur = sha256_file(full)
        entry["sha256_disk"] = cur
        entry["drift"] = "MATCH" if cur == entry["sha256_manifest"] else "DRIFT"
    else:
        entry["sha256_disk"] = None
        entry["drift"] = "MISSING"
    ship_files.append(entry)

reg_cols, reg_rows = parse_simple_table(os.path.join(UW, "data/MANIFEST.md"))
reg_files = []
for r in reg_rows:
    if not r.get("file"):
        continue
    rel = "data/" + r["file"].strip("`")
    full = os.path.join(UW, rel)
    entry = {
        "file": rel, "bytes_manifest": r.get("bytes", ""),
        "sha256_manifest": r.get("sha256", "").strip("`"),
        "provenance": r.get("provenance", ""), "data_label": r.get("data label", r.get("data_label", "")),
    }
    if os.path.exists(full):
        cur = sha256_file(full)
        entry["sha256_disk"] = cur
        entry["drift"] = "MATCH" if cur == entry["sha256_manifest"] else "DRIFT"
    else:
        entry["sha256_disk"] = None; entry["drift"] = "MISSING"
    reg_files.append(entry)

manifests = {
    "provenance": "REPORTED",
    "label": "Hashes from deploy/SHIP_MANIFEST.md and data/MANIFEST.md; disk hashes recomputed by THIS build (method: sha256sum-equivalent) at build time, labeled AUDIT-BUILD — not a DCLM seal.",
    "generated_at": NOW,
    "ship": {"files": ship_files, "total": len(ship_files),
             "match": sum(1 for f in ship_files if f["drift"] == "MATCH"),
             "drift": sum(1 for f in ship_files if f["drift"] == "DRIFT"),
             "missing": sum(1 for f in ship_files if f["drift"] == "MISSING")},
    "registries": {"files": reg_files, "total": len(reg_files),
                   "match": sum(1 for f in reg_files if f["drift"] == "MATCH"),
                   "drift": sum(1 for f in reg_files if f["drift"] == "DRIFT"),
                   "missing": sum(1 for f in reg_files if f["drift"] == "MISSING")},
}
dump("manifests.json", manifests)

# ---------- 4. receipt ledgers (from TELEMETRY section 4) ----------
telemetry = open(os.path.join(UW, "deploy/TELEMETRY.md")).read()
rec_tables = parse_md_tables(telemetry, re.compile(r".*"))
ledger_labels = {
    "economics/ (ledger: `economics/RECEIPTS.md`)": "economics",
    "dclm/ (ledger: `dclm/RECEIPTS.md`)": "dclm",
    "gate/ (ledger: `gate/RECEIPTS.md`, self-sealed)": "gate",
    "relay/ (ledger: `relay/RECEIPTS.md`, self-sealed)": "relay",
    "client/ (ledger: `client/RECEIPTS.md`)": "client",
    "purity/ (ledger: `purity/RECEIPTS.md`, self-sealed)": "purity",
    "unity-world root (ledger: `unity-world/RECEIPTS.md`)": "root",
}
receipt_rows = []
for section, tbl in rec_tables.items():
    label = ledger_labels.get(section)
    if not label:
        continue
    for r in tbl["rows"]:
        receipt_rows.append({
            "ledger": label,
            "file": r.get("File", "").strip("`"),
            "receipted_sha256": r.get("Receipted sha256", "").strip("`"),
            "time": r.get("Time (UTC)", ""),
            "drift": r.get("Drift", ""),
        })
receipts = {
    "source": "deploy/TELEMETRY.md section 4 (from the six RECEIPTS.md ledgers)",
    "provenance": "REPORTED",
    "as_of": "2026-10-06 ~08:08 UTC (point in time; drift accelerates under concurrent edits)",
    "generated_at": NOW,
    "rows": receipt_rows,
}
dump("receipts.json", receipts)

# ---------- 5. test suites (from TELEMETRY section 1) ----------
suite_tables = parse_md_tables(telemetry, re.compile(r".*"))
suite_labels = {
    "1a. economics/ (tokenomics engine)": "economics",
    "1b. dclm/ (compute core)": "dclm",
    "1c. Purity index (the measurer, measured)": "purity-index",
    "1d. gate/": "gate",
    "1e. relay/ (Node)": "relay",
    "1f. client/ (Node)": "client",
    "1g. testnet/": "testnet",
}
suites = []
for section, tbl in suite_tables.items():
    label = suite_labels.get(section)
    if not label:
        continue
    for r in tbl["rows"]:
        name = r.get("Suite", "")
        if not name:
            continue
        suites.append({
            "area": label,
            "suite": name.strip("`").replace("**", ""),
            "tests": r.get("Tests", r.get("Checks", "")).replace("**", ""),
            "pass": r.get("Pass", "").replace("**", ""),
            "fail_error": r.get("Fail/Error", "").replace("**", ""),
            "status": r.get("Status", "").replace("**", ""),
            "notes": r.get("Notes", ""),
        })

# ---------- 6. economic params (from PARAMS.md) ----------
params_text = open(os.path.join(UW, "economics/PARAMS.md")).read()
param_tables = parse_md_tables(params_text, re.compile(r".*"))
params = {"decided": [], "held": []}
for section, tbl in param_tables.items():
    if "DECIDED" in section:
        for r in tbl["rows"]:
            params["decided"].append({
                "parameter": r.get("Parameter", ""), "value": r.get("Value", ""),
                "standing": r.get("Standing", ""), "code_ref": r.get("Code ref", ""),
            })
    elif "HELD_FOR_DAVID" in section:
        for r in tbl["rows"]:
            params["held"].append({
                "parameter": r.get("Parameter", "").strip("`"), "decides": r.get("What it would decide", ""),
                "status_in_code": r.get("Status in code", ""), "note": r.get("Note", ""),
            })

# ---------- 7. mesh topology (from TELEMETRY section 3a) ----------
mesh = []
for section, tbl in suite_tables.items():
    if section.startswith("3a."):
        for r in tbl["rows"]:
            mesh.append({
                "level": r.get("Level", ""), "count": r.get("Count", ""), "source": r.get("Source", ""),
            })

# ---------- 8. founding board ----------
board = json.load(open(os.path.join(UW, "founding-board/founding-board.json")))
board_schema = json.load(open(os.path.join(UW, "founding-board/founding-board-schema.json")))
ack_path = os.path.join(UW, "founding-board/idris-marquee-helper.md")
ack_disk_hash = sha256_file(ack_path)
founding = {
    "source": "founding-board/founding-board.json + schema + acknowledgment file",
    "provenance": "REPORTED",
    "label": "Sounding board privacy law v2: Unity number OBFUSCATED but TRACEABLE (DCLM verifies). Public sees obfuscation + cohort only.",
    "generated_at": NOW,
    "board": board["board"], "community": board["community"],
    "declared_by": board["declared_by"], "declared_at": board["declared_at"],
    "privacy_law": board["privacy_law"], "schema": board["schema"],
    "cohorts": board["cohorts"], "founder_zero": board["founder_zero"],
    "members": [
        {**m,
         "ack_sha256_recorded": m.get("acknowledgment_sha256"),
         "ack_sha256_disk": ack_disk_hash,
         "ack_match": "MATCH" if m.get("acknowledgment_sha256") == ack_disk_hash else "MISMATCH"}
        for m in board["members"]
    ],
    "schema_keys": list(board_schema.keys()),
}

# ---------- 9. honest gaps + benchmarks (transcribed from TELEMETRY, labeled) ----------
gaps = [
    {"id": "5a-1", "category": "Red tests", "item": "Eight dclm suites red from the purify contract change (07:56 UTC): meter 4 errors, data 3 errors, winter 1 error, tap 1 failure + 1 error, share 2 errors, rights_writes 1 failure, seed 1 error, onboard 1 error (partial). Raise vs signed-refusal contract dispute; Trinity has not reconciled.", "status": "OPEN — measured", "provenance": "REPORTED"},
    {"id": "5a-2", "category": "Red tests", "item": "test_chunks.py flaky under concurrent edits (1-2 failures across runs; file edited mid-run). test_purify.py flaky (4 errors then 54/54 OK on re-run).", "status": "OPEN — measured", "provenance": "REPORTED"},
    {"id": "5a-3", "category": "Red tests", "item": "test_tokenize.py: 64 tests, 2 failures (provisional — failure details not captured; concurrent edits mid-run). Last clean receipt: 49/49 at 07:35 UTC.", "status": "OPEN — provisional", "provenance": "REPORTED"},
    {"id": "5a-4", "category": "Broken harness", "item": "Unification proof harness crashes at step [1] (TypeError, enq.entry undefined) — 0/17 complete. README claim of 17/17 passing does not reproduce.", "status": "BROKEN — measured", "provenance": "REPORTED"},
    {"id": "5a-5", "category": "Stale harness", "item": "Gauntlet: results.json all-sections-raised (07:54); run.log eFuse-section assertion failure. Benchmark tool, not a gate, not green.", "status": "STALE — measured", "provenance": "REPORTED"},
    {"id": "5a-6", "category": "Purity index", "item": "Purity index aggregate FAIL (08:08 UTC, re-confirmed 08:30 with D4 fallen to 0.385): D1/D3/D4/D5 FAIL, D2 UNKNOWN. Receipt drift accelerating — workers edit faster than ledgers are appended.", "status": "FAIL — measured", "provenance": "REPORTED"},
    {"id": "5b-7", "category": "Adversarial", "item": "Relay persistence race (team5 C5): silent outbox truncation 1,735 -> 59 bundles. Fix (atomic rename + fail-loud) recommended, not confirmed built.", "status": "OPEN", "provenance": "REPORTED"},
    {"id": "5b-8", "category": "Adversarial", "item": "token_engine duplicate-delivery double-apply (team3): merit 100->200, eFuse 1->2 on re-delivery. Idempotency fix confirmed in wallet.py only; token_engine's own fix UNKNOWN.", "status": "OPEN/UNKNOWN", "provenance": "REPORTED"},
    {"id": "5b-9", "category": "Adversarial", "item": "Gate negative-keys seam (team2): 300/300 fail-open on injected keys_available: -50 ledger. Recommendation recorded; fix UNKNOWN.", "status": "OPEN", "provenance": "REPORTED"},
    {"id": "5b-10", "category": "Adversarial", "item": "Economics NaN/inf findings (team4 F2/F3): no finiteness checks. Fix UNKNOWN.", "status": "OPEN", "provenance": "REPORTED"},
    {"id": "5b-11", "category": "Adversarial", "item": "4.20ms bound breached on the paid-intent path and mutations (team2). Redesign UNKNOWN.", "status": "OPEN", "provenance": "REPORTED"},
    {"id": "5c-12", "category": "David's hand", "item": "Peg ratio E — nothing emits without it. 13 HELD tokenomics params + 4 canon = 17 parameters awaiting David's word.", "status": "HELD", "provenance": "REPORTED"},
    {"id": "5c-13", "category": "David's hand", "item": "Genesis Unity amount: GENESIS_UNITY_AMOUNT = None; the fuse cannot trigger without his signed authorization.", "status": "HELD", "provenance": "REPORTED"},
    {"id": "5c-14", "category": "David's hand", "item": "Core Cause Lock address: {\"value\": \"UNKNOWN\"}; no placeholder ever rendered as live.", "status": "HELD", "provenance": "REPORTED"},
    {"id": "5c-15", "category": "David's hand", "item": "Honor class name: UNNAMED — HELD for David.", "status": "HELD", "provenance": "REPORTED"},
    {"id": "5c-16", "category": "David's hand", "item": "EIA + NASS free email registrations — unblocks keyed re-probes (mesh blocking item).", "status": "HELD", "provenance": "REPORTED"},
    {"id": "5c-17", "category": "David's hand", "item": "Sealed dim-7 vs free-key tension — Trinity ruling pending (mesh blocking item).", "status": "HELD", "provenance": "REPORTED"},
    {"id": "5d-18", "category": "Not yet built", "item": "WebAuthn: gate confirm_bind runs on a clearly-labeled TEST STUB; real device ceremony is SPEC/UNKNOWN.", "status": "NOT BUILT", "provenance": "REPORTED"},
    {"id": "5d-19", "category": "Not yet built", "item": "L2 kin authority: verify_kin() returns False — INTEGRATION PENDING, family grants refused NOT_KIN_VERIFIED.", "status": "NOT BUILT", "provenance": "REPORTED"},
    {"id": "5d-20", "category": "Not yet built", "item": "testnet IPNS: keys minted, no testnet pin published yet.", "status": "NOT BUILT", "provenance": "REPORTED"},
    {"id": "5d-21", "category": "Not yet built", "item": "Emission path rewiring: emission_eligibility gate tested 27/27, but _mint_efuse not yet rewired through it.", "status": "PENDING", "provenance": "REPORTED"},
    {"id": "5d-22", "category": "Not yet built", "item": "Deployment loop: DEPLOYMENT_PLAN.md exists; the public loop (domain -> box, IPNS republish) is not closed. Testnet only.", "status": "NOT CLOSED", "provenance": "REPORTED"},
    {"id": "5e-23", "category": "Unknown by nature", "item": "Deployment topology (Trinity verdict): decides whether relay fan-out is a real bottleneck or a solved CDN problem.", "status": "UNKNOWN", "provenance": "UNKNOWN"},
    {"id": "5e-24", "category": "Unknown by nature", "item": "Real user bandwidth environments (affects adaptation tuning, not architecture).", "status": "UNKNOWN", "provenance": "UNKNOWN"},
    {"id": "5e-25", "category": "Unknown by nature", "item": "Whether behavioral prefetch ever becomes accurate enough to matter.", "status": "UNKNOWN", "provenance": "UNKNOWN"},
    {"id": "5e-26", "category": "Unknown by nature", "item": "Fresh web-gather intelligence time per cell (minutes-hours; no swarm makes it instant).", "status": "UNKNOWN", "provenance": "UNKNOWN"},
    {"id": "5e-27", "category": "Unknown by nature", "item": "Any mainnet measurement — none exist, by law.", "status": "UNKNOWN", "provenance": "UNKNOWN"},
]

benchmarks = [
    {"team": "team2-gate", "metric": "Iris gate check throughput", "value": "~568K-1.35M checks/sec", "detail": "0.7-1.8us each, n=5000; 0 breaches of 4.20ms bound on read paths", "provenance": "REPORTED"},
    {"team": "team2-gate", "metric": "MAX CHAOS battery", "value": "399,265 adversarial evaluations", "detail": "182,054 fail-closed (45.6%); 300 fail-open (0.075%) on injected keys_available:-50 ledger — seam-only finding", "provenance": "REPORTED"},
    {"team": "team2-gate", "metric": "4.20ms bound", "value": "HOLDS on read/evaluation paths", "detail": "BREACHES on the paid-intent path and on mutations", "provenance": "REPORTED"},
    {"team": "team3-dclm", "metric": "DCLM decision throughput", "value": "102,038 decisions/sec/core", "detail": "mean 0.0098ms, p99 0.024ms, n=500 (rings.py Parliament.collapse)", "provenance": "REPORTED"},
    {"team": "team3-dclm", "metric": "token_engine under chaos", "value": "BROKEN", "detail": "duplicate delivery of same VERIFIED receipt double-applies (merit 100->200, eFuse 1->2). Idempotency fix status: UNKNOWN at token_engine layer", "provenance": "REPORTED"},
    {"team": "team4-economics", "metric": "Sign / verify throughput", "value": "~1.285 sign/sec, ~1.52 verify/sec", "detail": "node subprocess spawns are the binding constraint", "provenance": "REPORTED"},
    {"team": "team4-economics", "metric": "Emission / state latency", "value": "0.2057ms / 1.37ms", "detail": "n=5000 / n=200; 0 token-minting events in chaos", "provenance": "REPORTED"},
    {"team": "team5-live", "metric": "Relay throughput (shared live testnet)", "value": "~19 rps sustained", "detail": "p50 90ms @ c=2 -> 5.8s @ c=128 (distress tripwire); C5 cross-process race VIOLATED: silent outbox truncation 1,735 -> 59 bundles", "provenance": "REPORTED"},
    {"team": "team7-iq", "metric": "Iris effective IQ", "value": "1.0", "detail": "41-case battery, 104 verdict observations, zero misses; 7 of 61 candidate verdicts perfectly pure and perfectly wrong", "provenance": "REPORTED"},
    {"team": "team8-state", "metric": "Max known state", "value": "58 substantive law statements, 17 held parameters", "detail": "4 canon + 13 tokenomics HELD; 19 named datasets; 227 countries / 1251 cities (VENDOR-RECOVERY)", "provenance": "REPORTED"},
]

tables = {
    "provenance": "REPORTED",
    "label": "Point-in-time view on DCLM truth, assembled by this site's build from the recorded sources named per table. The site never computes — it displays.",
    "generated_at": NOW,
    "test_suites": {"source": "deploy/TELEMETRY.md section 1 (live test runs 2026-10-06 ~08:00-08:25 UTC)", "as_of": "2026-10-06 ~08:25 UTC", "rows": suites},
    "params": {"source": "economics/PARAMS.md (decided-vs-held split)", "as_of": "2026-10-06", "decided": params["decided"], "held": params["held"]},
    "mesh": {"source": "deploy/TELEMETRY.md section 3 (from mesh/MESH_MAP.md, pilot wave-4 complete ~03:45 EDT)", "as_of": "2026-10-06 ~03:45 EDT", "rows": mesh},
    "gaps": {"source": "deploy/TELEMETRY.md section 5", "as_of": "2026-10-06 ~08:30 UTC", "rows": gaps},
    "benchmarks": {"source": "deploy/TELEMETRY.md section 2 (iris-benchmark teams)", "as_of": "2026-10-06", "rows": benchmarks},
    "receipt_ledgers": {"source": "deploy/TELEMETRY.md section 4 (the six RECEIPTS.md ledgers)", "as_of": "2026-10-06 ~08:08 UTC", "rows": receipt_rows},
    "founding": founding,
}
dump("tables.json", tables)
dump("founding.json", founding)

print("build complete at", NOW)

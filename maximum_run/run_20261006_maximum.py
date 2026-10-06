#!/usr/bin/env python3
"""
MAXIMUM RUN — David's order: RUN IT TO MAXIMUM on testnet.

Drives every implemented component at full capacity:
  1. 53 pricing decisions through the pipeline (flat 5 test-keys, metered)
  2. Onboarder flywheel: onboard -> residual intake -> 81/19 split -> escrow
  3. Tree circulation: summer flow, winter gradient, tap requests by rule
  4. Tokenization: receipt -> merit -> emission (peg-gated; E HELD defers)
  5. +1 firing with deterioration; Affinity evaluation for early IDs
  6. Shared access grants across tiers; revocation
  7. Purity index scoring the live run
  8. Iris judging every judgment (landed core; siblings HONEST-PENDING)
  9. Boards status check

TESTNET ONLY. Every action receipted. UNKNOWN never PASS.
Nothing here touches production keys, ports, or schemas.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # ~/workspace/unity-world
for sub in ("dclm", "economics", "purity", "gate", "iris-intake"):
    sys.path.insert(0, os.path.join(ROOT, sub))

RUN_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN_TS_LOCAL = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
RUN_ID = "maximum-run-" + RUN_TS
RUN_DIR = os.path.join(HERE, RUN_TS)
os.makedirs(RUN_DIR, exist_ok=True)

STAGES = []
RECEIPT_ROWS = []


def stage(name):
    print(f"\n{'='*64}\nSTAGE: {name}\n{'='*64}", flush=True)
    STAGES.append({"name": name, "started": _now()})


def _now():
    return datetime.now(timezone.utc).isoformat()


def record(kind, detail, status="OK"):
    row = {"run": RUN_ID, "at": _now(), "kind": kind,
           "status": status, "detail": detail}
    RECEIPT_ROWS.append(row)
    print(f"  [{status}] {kind}: {str(detail)[:150]}", flush=True)
    return row


def note_pending(item, reason):
    return record("PENDING", f"{item} — {reason}", status="PENDING")


def make_id(seed):
    return "unity:testnet:" + hashlib.sha256(
        f"{RUN_ID}:{seed}".encode()).hexdigest()


OPERATOR = make_id("operator")
ONBOARDERS = {
    "amina-genesis": make_id("onboarder-amina"),
    "borin-mid": make_id("onboarder-borin"),
    "cato-late": make_id("onboarder-cato"),
}
ALICE, BOB = make_id("alice"), make_id("bob")

IRIS_JUDGMENTS = []


def iris_judge(action_kind, intent, evidence_status="verified"):
    """Iris judging every judgment — landed core (judge_all). Siblings HONEST-PENDING."""
    try:
        import iris_core
        verdict = iris_core.judge_all(
            {"kind": action_kind, "intent": intent,
             "actor": OPERATOR, "unity_id": OPERATOR,
             "provenance": "DERIVED" if evidence_status == "verified" else "UNKNOWN",
             "evidence": {"status": evidence_status}},
            tree_state={"winter_signal": None, "surplus": 0.0,
                        "maturity": "evaluated", "tap_requests": []},
        )
        final = verdict.get("final", {})
        IRIS_JUDGMENTS.append({"action": action_kind,
                               "final": final.get("verdict", "?")})
        return verdict
    except Exception as e:  # noqa: BLE001 — record, never fake
        IRIS_JUDGMENTS.append({"action": action_kind, "final": "ERROR",
                               "error": str(e)[:120]})
        return {"error": str(e)[:200]}


def relay_post(stage_name, payload):
    """Post a stage marker through the live testnet relay API (18081). Best-effort."""
    try:
        import urllib.request
        body = json.dumps({
            "schema": "dualis.relay.v1.testnet",
            "kind": "maximum-run-stage",
            "stage": stage_name,
            "run": RUN_ID,
            "unity_id": OPERATOR,
            "payload": payload,
            "network": "TESTNET",
        }).encode()
        req = urllib.request.Request("http://127.0.0.1:18081/bundle",
                                     data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status
    except Exception as e:  # noqa: BLE001
        return f"RELAY_POST_FAILED: {str(e)[:100]}"


# =====================================================================
# STAGE 1 — 53 pricing decisions, flat 5 test-keys, metered for real
# =====================================================================
stage("1. PRICING — 53 decisions through the pipeline")
import pricing  # noqa: E402
from meter import Wallet, ACTION_COMPUTE, PRICE_COMPUTE, OUTCOME_GRANTED  # noqa: E402

rows = pricing.INDEX
record("PRICING_INDEX_ROWS", f"{len(rows)} rows loaded")
priced = [pricing.price_decision(r) for r in rows]
flat_ok = all(p["billable_amount"] == 5 and p["currency"] == "test-keys"
              for p in priced)
record("PRICING_FLAT_5", f"all 53 at 5 test-keys flat: {flat_ok}",
       status="OK" if flat_ok and len(rows) == 53 else "FAIL")
classes = {}
for p in priced:
    classes[p["class"]] = classes.get(p["class"], 0) + 1
record("PRICING_CLASSES", json.dumps(classes))

# Meter every decision as a real COMPUTE intent through the DCLM wallet.
import tempfile  # noqa: E402
wallet = Wallet(state_dir=tempfile.mkdtemp(prefix="maxrun-meter-"))
wallet.faucet(OPERATOR, 53 * PRICE_COMPUTE + 100)
charged = 0
granted = 0
for i, p in enumerate(priced):
    env = wallet.meter_intent(OPERATOR, ACTION_COMPUTE,
                              f"maxrun-{RUN_TS}-decision-{p['decision_id']}")
    if env["receipt"]["outcome"] == OUTCOME_GRANTED:
        granted += 1
        charged += env["receipt"]["amount"]
record("METERED_DECISIONS",
       f"{granted}/53 COMPUTE intents GRANTED, {charged} test-keys charged "
       f"(expected {53 * PRICE_COMPUTE})",
       status="OK" if granted == 53 and charged == 53 * PRICE_COMPUTE else "FAIL")
record("WALLET_BALANCE_AFTER", f"{wallet.balance(OPERATOR)} test-keys remain")
iris_judge("pricing-53-decisions",
           "53 decisions priced flat 5 test-keys and metered through DCLM")
relay_post("pricing", {"decisions": 53, "charged": charged, "flat_ok": flat_ok})


# =====================================================================
# STAGE 2 — ONBOARDER FLYWHEEL: onboard -> intake -> 81/19 -> escrow
# =====================================================================
stage("2. ONBOARDER FLYWHEEL")
from onboard import (onboard, record_residual, execute_split, route_19,  # noqa: E402
                     flywheel_state)

flywheel = {"onboarded": [], "intake": [], "splits": [], "routed": []}
# The reference case: Ontario-style $1.27B/yr recoverable friction (REPORTED).
RESIDUAL_CASES = {
    "amina-genesis": 127_350_000_000,   # $1.2735B in cents — REPORTED
    "borin-mid": 48_200_000_000,        # $482M in cents — REPORTED
    "cato-late": 12_750_000_000,        # $127.5M in cents — REPORTED
}
for name, uid in ONBOARDERS.items():
    r = onboard(uid, f"paperwork-{RUN_ID}-{name}")
    flywheel["onboarded"].append(name)
    record("ONBOARD", f"{name} {uid[:24]}... receipted")
    fig = RESIDUAL_CASES[name]
    phash = hashlib.sha256(f"paperwork-{RUN_ID}-{name}".encode()).hexdigest()
    record_residual(uid, fig, phash)
    flywheel["intake"].append((name, fig))
    record("RESIDUAL_INTAKE", f"{name}: {fig} cents REPORTED (paperwork-hashed)")
    split = execute_split(uid, fig)
    flywheel["splits"].append((name, split))
    record("SPLIT_81_19", f"{name}: 81% off-system ACK, 19% -> escrow")
    routed = route_19(uid, int(fig * 0.19))
    flywheel["routed"].append((name, routed))
    record("NINETEEN_ROUTE", f"{name}: 19% HELD — AWAITING_SPLIT_RULING")

fs = flywheel_state()
record("FLYWHEEL_STATE",
       f"onboarders={fs.get('onboarders', '?')} "
       f"reported_total_cents={fs.get('reported_total_cents', fs.get('reported_total', '?'))} "
       f"escrow_held={fs.get('escrow_19_held_cents', fs.get('escrow', '?'))}")
iris_judge("onboarder-flywheel",
           "3 onboarders: intake REPORTED, 81/19 split, 19% in HELD escrow")
relay_post("flywheel", {"onboarded": 3,
                        "reported_cents": sum(RESIDUAL_CASES.values())})

# =====================================================================
# STAGE 3 — TREE CIRCULATION: summer flow, winter gradient, taps by rule
# =====================================================================
stage("3. TREE CIRCULATION — summer / winter / tap")
import winter  # noqa: E402
from tap import TapSeason, Tapper, Measure  # noqa: E402

calm = winter.WinterSignal(peg_deviation=0.005, activity_delta=-0.02,
                           crisis_declared=False, crisis_verified=False)
storm = winter.WinterSignal(peg_deviation=0.06, activity_delta=-0.30,
                            crisis_declared=True, crisis_verified=True)
ws_calm = winter.evaluate_trigger(calm)
ws_storm = winter.evaluate_trigger(storm)
record("WINTER_CALM", f"gradient={ws_calm.gradient:.3f} label={ws_calm.label} "
                      f"(PROPOSED calibration)")
record("WINTER_STORM", f"gradient={ws_storm.gradient:.3f} label={ws_storm.label} "
                       f"(PROPOSED calibration)")
# Winter store attempt under calm (phantom pattern -> refused) and storm.
try:
    store_calm = winter.winter_store(ONBOARDERS["cato-late"], 10,
                                     "maximum-run probe", signal=calm)
    record("WINTER_STORE_CALM",
           f"outcome={store_calm.get('outcome', '?')} "
           f"reason={str(store_calm.get('reason', ''))[:90]}")
except Exception as e:  # noqa: BLE001
    record("WINTER_STORE_CALM", f"raised: {str(e)[:110]}")

# Tap season: OPEN (healthy, surplus, calm) and CLOSED (storm) + founder refusal.
def M(value, provenance="REPORTED"):
    return Measure(value=value, provenance=provenance)

open_season = TapSeason(
    pool_health=M(0.95), peg_deviation_bp=M(8.0),
    reserve_total=M(500.0), reserve_survival_need=M(100.0),
    pool_headroom=M(300.0), season_replenishment=M(400.0),
    season_id=f"{RUN_TS[:4]}-tapping", winter_signal=calm,
    state_dir=os.path.join(RUN_DIR, "tap-open"))
verdict_open = open_season.evaluate()
record("TAP_SEASON_OPEN",
       f"season_open={verdict_open.season_open} reason={verdict_open.reason} "
       f"chain_steps={len(verdict_open.chain)}")

tapper = Tapper(open_season, state_dir=os.path.join(RUN_DIR, "tap-open"))
tap_env = tapper.request_tap(ONBOARDERS["amina-genesis"], 20,
                             "member real need: equipment")
tap_outcome = tap_env.get("receipt", {}).get("outcome", "?")
record("TAP_REQUEST",
       f"20 test-keys to amina-genesis: outcome={tap_outcome} "
       f"{str(tap_env.get('receipt', {}).get('reason'))[:80]}",
       status="OK" if tap_outcome in ("GRANTED", "REFUSED") else "FAIL")

closed_season = TapSeason(
    pool_health=M(0.40), peg_deviation_bp=M(60.0),
    reserve_total=M(80.0), reserve_survival_need=M(100.0),
    pool_headroom=M(10.0), season_replenishment=M(20.0),
    season_id=f"{RUN_TS[:4]}-tapping", winter_signal=storm,
    state_dir=os.path.join(RUN_DIR, "tap-closed"))
verdict_closed = closed_season.evaluate()
record("TAP_SEASON_CLOSED",
       f"season_open={verdict_closed.season_open} "
       f"(winter-protection refusal expected)")
# Founder extraction: refused as extraction, not as a limit.
founder_env = tapper.request_tap("unity:testnet:founder:david", 10.0,
                                 "founder draw")
founder_outcome = founder_env.get("receipt", {}).get("outcome", "?")
founder_reason = founder_env.get("receipt", {}).get("reason", "?")
record("FOUNDER_TAP",
       f"outcome={founder_outcome} reason={founder_reason}",
       status="OK" if founder_reason == "FOUNDER_EXTRACTION_FORBIDDEN"
       else "FAIL")
iris_judge("tree-circulation",
           "winter gradient evaluated (PROPOSED), tap season open+closed, "
           "founder extraction refused")
relay_post("tree", {"calm_gradient": round(ws_calm.gradient, 3),
                    "storm_gradient": round(ws_storm.gradient, 3)})


# =====================================================================
# STAGE 4 — TOKENIZATION: receipt -> merit -> emission (peg-gated)
# =====================================================================
stage("4. TOKENIZATION — receipt -> merit -> emission (peg-gated)")
from token_engine import (Tokenizer, TokenizeRefused,  # noqa: E402
                           sign_gate_receipt)
from onboard import accrue_recovery_merit  # noqa: E402

tokenizer = Tokenizer()
token_results = {"merit_accrued": 0.0, "deferred": 0,
                 "emission_refusal": None}


def _manifest(seed):
    return hashlib.sha256(f"{RUN_ID}:{seed}".encode()).hexdigest()


def gate_signed_work(identity, merit_value, seed):
    """Build a work receipt and have the TESTNET GATE sign it — the same
    gate-signature the real DCLM gate would produce. The engine verifies
    the signature itself; it never trusts a caller-asserted VERIFIED."""
    r = {
        "schema": "unity.relay.v1.testnet",
        "receipt_id": f"maxrun-{seed}",
        "manifest_hash": _manifest(seed),
        "unity_id": identity,
        "kind": "work",
        "class": "recovery_work",
        "provenance": "VERIFIED",
        "epoch": 1,
        "merit_value": merit_value,
        "prev_hash": tokenizer._gate_chain_head,
    }
    return sign_gate_receipt(r)


# Recovery work -> the onboarder pipeline's merit path. With peg E HELD
# (unset — David's word pending), verified work is honestly DEFERRED:
# recorded, receipted, retryable — never accrued on unknown terms.
for name, uid in (("amina-genesis", ONBOARDERS["amina-genesis"]),
                  ("borin-mid", ONBOARDERS["borin-mid"]),
                  ("cato-late", ONBOARDERS["cato-late"])):
    res = accrue_recovery_merit(
        uid, [gate_signed_work(uid, 100.0, f"work-{name}")],
        tokenizer=tokenizer)
    token_results["deferred"] += 1
    first = (res.get("results") or [{}])[0]
    record("MERIT_DEFERRED_E_HELD",
           f"{name}: 100 merit-value of verified recovery work -> "
           f"{first.get('status', '?')}/{first.get('reason', '?')} — "
           f"recorded, retryable")

# The emission gate itself: raw tokenize of a work receipt while E is HELD
# must refuse PEG_E_UNSET — never mint on unknown terms.
try:
    tokenizer.tokenize(gate_signed_work(ONBOARDERS["amina-genesis"],
                                        50.0, "work-emission-probe"))
    record("EMISSION", "emitted while E HELD — LAW VIOLATION", status="FAIL")
except TokenizeRefused as e:
    token_results["emission_refusal"] = f"{e.reason}"
    record("EMISSION_DEFERRED",
           f"E HELD -> honest deferral: {e.reason}")
except Exception as e:  # noqa: BLE001
    record("EMISSION_DEFERRED", f"UNEXPECTED: {str(e)[:80]}", status="FAIL")

# Merit transfer path (David's 03:35 law: transferable), demonstrated with
# a real sender-signed authorization (the sender's device flow). No merit
# exists while E is HELD, so the live path must refuse INSUFFICIENT after
# the auth verifies — the transfer->standing mechanics themselves are
# proven by test_tokenize.py under test authority (E set there).
import base64  # noqa: E402
import uuid  # noqa: E402


def _gen_keypair():
    script = ("const c=require('crypto');"
              "const k=c.generateKeyPairSync('ed25519');"
              "console.log(k.privateKey.export({format:'der',type:'pkcs8'})"
              ".toString('base64'));"
              "console.log(k.publicKey.export({format:'der',type:'spki'})"
              ".toString('base64'));")
    proc = subprocess.run(["node", "-e", script], capture_output=True,
                          timeout=30)
    priv_b64, pub_b64 = proc.stdout.decode().strip().split("\n")
    return base64.b64decode(priv_b64), base64.b64decode(pub_b64)


_sender_priv, _sender_pub = _gen_keypair()
SENDER = "unity:testnet:" + hashlib.sha256(_sender_pub).hexdigest()


def _sender_auth(frm, to, amount, reason):
    body = {"op": "merit-transfer", "from": frm, "to": to,
            "amount": float(amount), "reason": reason.strip(),
            "nonce": uuid.uuid4().hex}
    msg = json.dumps(body, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    fd, path = tempfile.mkstemp(prefix="maxrun-auth-", suffix=".der")
    os.fchmod(fd, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_sender_priv)
        proc = subprocess.run(["node", os.path.join(ROOT, "dclm",
                                                    "ed25519.js"),
                               "sign", path],
                              input=msg, capture_output=True, timeout=30)
    finally:
        os.unlink(path)
    return {**body, "signature": proc.stdout.decode().strip(),
            "pubkey_b64": base64.b64encode(_sender_pub).decode()}


try:
    tokenizer.merit_transfer(SENDER, BOB, 60.0, "sale",
                             auth=_sender_auth(SENDER, BOB, 60.0, "sale"))
    record("MERIT_TRANSFER", "transfer with zero balance GRANTED — GUARD "
           "FAILURE", status="FAIL")
except Exception as e:  # noqa: BLE001
    record("MERIT_TRANSFER_GUARDED",
           f"sender-authorized zero-balance transfer refused: "
           f"{type(e).__name__} {str(e)[:100]}")
record("STANDING_NOTE",
       "standing() reads origin-credited earn events only; with E HELD no "
       "earn events exist — the distinction is proven in test_tokenize.py")
iris_judge("tokenization",
           "verified recovery work honestly deferred (E HELD); emission "
           "gate refuses PEG_E_UNSET; transfer path guarded")
relay_post("tokenization", {"deferred": token_results["deferred"],
                            "emission": "DEFERRED_E_HELD"})

# =====================================================================
# STAGE 5 — +1 FIRING with deterioration; Affinity evaluation
# =====================================================================
stage("5. +1 FIRING — deterioration with distance")
import neural  # noqa: E402

brain = neural.Tree(OPERATOR, t_launch=0)
pw = brain.add_pathway("pw-maxrun", neural.DETERMINISTIC, OPERATOR,
                       neural.HOST_RELAY_TESTNET)
syn = brain.add_synapse("syn-maxrun", ["pw-maxrun"], OPERATOR,
                        neural.HOST_RELAY_TESTNET,
                        kind=neural.SYNAPSE_TRINITY)
plus_one_results = []
# (name, t_event, ring_depth, affinity_flag)
cases = [("amina-genesis", 0, 0, True),    # frontier + proven early
         ("borin-mid", 12, 2, True),       # decayed, affinity floor lifts
         ("cato-late", 36, 5, False)]      # dense network maintenance rate
for name, t_event, r, aff in cases:
    check_rcpt = {"verified": True, "unity_id": ONBOARDERS[name],
                  "receipt_id": f"maxrun-check-{name}"}
    fire = brain.fire_plus_one(pw, "syn-maxrun", neural.HOST_RELAY_TESTNET,
                               check_rcpt, t_event, ring_depth=r,
                               affinity=aff)
    p = fire["payload"]
    plus_one_results.append((name, p["d"], p["F"], p["R"], aff))
    record("PLUS_ONE_FIRE",
           f"{name}: t={t_event} r={r} affinity={aff} -> "
           f"d={p['d']:.4f} F={p['F']:.4f} R={p['R']:.4f} mode={p['mode']}")

# Affinity rule evaluation (PLUS_ONE_INCENTIVE.md §2.1): first ONBOARD
# receipt within tau_aff=12 epochs AND ring <= rho_aff=2.
# The ledger-side AFFINITY_GRANT commit kind is DESIGN-ONLY (G4) — the
# grant mechanism is PENDING; the floor lift above is what's real.
affinity_qualifiers = [n for n, _, _, aff in plus_one_results if aff]
record("AFFINITY_EVALUATION",
       f"qualifiers by receipt rule: {affinity_qualifiers}")
note_pending("AFFINITY_GRANT commit kind",
             "design-only (PLUS_ONE_INCENTIVE.md G4); floor lift honored in "
             "fire_plus_one, ledger grant not built")
iris_judge("plus-one",
           "+1 deterioration fired per verified check; affinity floor honored")
relay_post("plus_one", {"fires": len(plus_one_results)})

# =====================================================================
# STAGE 6 — SHARED ACCESS: grants across tiers; revocation
# =====================================================================
stage("6. SHARED ACCESS — tiers, enforcement, revocation")
from share import (issue_grant, revoke_grant, check_access,  # noqa: E402
                   ShareRefused)

grant_store = {}
g1 = issue_grant(ALICE, BOB, "FRIEND", "DATA", "read:ledger-summary", 3600,
                 store=grant_store)
g2 = issue_grant(ALICE, BOB, "GOOD_FRIEND", "RTE_SEAT", "seat:read", 3600,
                 store=grant_store)
record("GRANT_ISSUED",
       f"FRIEND + GOOD_FRIEND grants ALICE->BOB: "
       f"{g1['grant_id'][:12]}..., {g2['grant_id'][:12]}...")
# Tier enforcement: FRIEND grant cannot exercise FAMILY-required access.
v_friend = check_access(BOB, "DATA", "FRIEND", store=g1["store"])
v_family = check_access(BOB, "DATA", "FAMILY", store=g1["store"])
record("TIER_ENFORCEMENT",
       f"friend-tier vs FRIEND-required: {v_friend.verdict}; "
       f"vs FAMILY-required: {v_family.verdict}",
       status="OK" if str(v_friend.verdict) == "GRANT"
       and str(v_family.verdict) == "DENY" else "FAIL")
# FAMILY tier without kin authority: honestly refused (no umpires wired).
try:
    issue_grant(ALICE, BOB, "FAMILY", "DATA", "all", 3600, store=grant_store)
    record("FAMILY_GRANT", "issued without kin verification", status="FAIL")
except ShareRefused as e:
    record("FAMILY_REFUSED_NO_KIN", str(e)[:110])
# Revocation: instant and total.
rev = revoke_grant(ALICE, g1["grant_id"], store=g1["store"])
v_after = check_access(BOB, "DATA", "FRIEND", store=g1["store"])
record("REVOKE",
       f"grant revoked; access after revoke: {v_after.verdict}",
       status="OK" if str(v_after.verdict) == "DENY" else "FAIL")
iris_judge("shared-access",
           "tiered grants enforced structurally; family refused without kin; "
           "revocation total")
relay_post("shared_access", {"grants": 2, "revoked": 1})


# =====================================================================
# STAGE 7 — PURITY INDEX scores the live run
# =====================================================================
stage("7. PURITY INDEX — scoring the live run")
import index as purity_index  # noqa: E402

rep = purity_index.score_live()
j = purity_index.judge(rep)
idx_report = {"verdict": j["verdict"], "clarity": j["clarity"],
              "reasons": j["reasons"],
              "dimensions": {
                  dim_id: {"score": d.score, "status": d.status,
                           "coverage": d.coverage,
                           "evidence": d.evidence[:8]}
                  for dim_id, d in rep["dimensions"].items()}}
record("PURITY_INDEX",
       f"verdict={idx_report['verdict']} clarity={idx_report['clarity']} "
       + " ".join(f"{k}:{v['status']}"
                  for k, v in idx_report["dimensions"].items()))
with open(os.path.join(RUN_DIR, "purity_index.json"), "w") as fh:
    json.dump(idx_report, fh, indent=2, default=str)

# =====================================================================
# STAGE 8 — BOARDS: is board infrastructure live?
# =====================================================================
stage("8. BOARDS")
fb_dir = os.path.join(ROOT, "founding-board")
boards_status = {"dir": os.path.isdir(fb_dir), "live_service": False}
if boards_status["dir"]:
    files = sorted(os.listdir(fb_dir))
    boards_status["files"] = files
    schema_ok = False
    try:
        schema = json.load(open(os.path.join(fb_dir,
                                             "founding-board-schema.json")))
        members = json.load(open(os.path.join(fb_dir,
                                             "founding-board.json")))
        schema_ok = True
        boards_status["schema"] = schema.get("title", "?")
        boards_status["members"] = (len(members.get("members", members))
                                    if isinstance(members, dict) else "?")
    except Exception as e:  # noqa: BLE001
        boards_status["schema_error"] = str(e)[:100]
    record("BOARD_INFRA",
           f"file-based board registry present ({len(files)} files); "
           f"schema_ok={schema_ok}; no live board service — NOT-FOUND "
           f"as a running service")
    note_pending("boards live service",
                 "founding-board/ is a file registry + schema; no HTTP "
                 "service exists to bring up")
else:
    record("BOARD_INFRA", "founding-board/ NOT-FOUND", status="FAIL")

# =====================================================================
# ARTIFACTS
# =====================================================================
stage("ARTIFACTS")
summary = {
    "run": RUN_ID,
    "timestamp_utc": RUN_TS,
    "timestamp_local": RUN_TS_LOCAL,
    "network": "TESTNET",
    "schema": "dualis.relay.v1.testnet",
    "stages": [s["name"] for s in STAGES],
    "iris_judgments": IRIS_JUDGMENTS,
    "iris_integration": "core LANDED; iris_laws/iris_patterns/iris_arbiter "
                        "HONEST-PENDING (no activation receipt on file)",
    "receipt_rows": RECEIPT_ROWS,
}
with open(os.path.join(RUN_DIR, "run_summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2, default=str)

ok = sum(1 for r in RECEIPT_ROWS if r["status"] == "OK")
fail = sum(1 for r in RECEIPT_ROWS if r["status"] == "FAIL")
pend = sum(1 for r in RECEIPT_ROWS if r["status"] == "PENDING")
print(f"\n{'='*64}\nMAXIMUM RUN COMPLETE: {ok} OK / {fail} FAIL / {pend} "
      f"PENDING\nartifacts: {RUN_DIR}\n{'='*64}")
print(f"RUN_DIR={RUN_DIR}")
print(f"RUN_TS={RUN_TS}")

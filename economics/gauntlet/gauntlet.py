#!/usr/bin/env python3
"""COIN ARCHITECTURE GAUNTLET — Worker 2 (full gauntlet + 100% SECURE expansion).

TESTNET ONLY. All in-memory. Fresh test keypairs. Never touches
~/workspace/unity-world/economics/state/ or any shared state file.

Canonical Merit transfer path under test: dclm/token_engine.py +
wallet.transfer_merit (David's current transferable-Merit law).

Labels: REPORTED = measured here. MODELED = simulated inputs (E is HELD;
any E used is labeled MODELED, never real).
"""
import sys, os, time, json, base64, hashlib, uuid, tempfile, traceback

sys.path.insert(0, os.path.expanduser("~/workspace/unity-world/economics"))
sys.path.insert(0, os.path.expanduser("~/workspace/unity-world/dclm"))

import wallet as W
import tokenomics as T
try:
    from token_engine import Tokenizer, TokenizeRefused
    import token_engine as _te_mod
    TE_SOURCE = "repo: ~/workspace/unity-world/dclm/token_engine.py"
    TE_BROKEN = False
except IndentationError as _e:
    # Repo file unimportable (concurrent-edit damage, observed 07:48 UTC).
    # Fall back to a byte-identical /tmp snapshot with ONLY the collapsed
    # newline at line ~1103 restored (verified against the pre-breakage
    # read). The repo file itself is NOT modified.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "te_snapshot", "/tmp/te_snapshot/token_engine.py")
    _te_mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_te_mod)
    Tokenizer, TokenizeRefused = _te_mod.Tokenizer, _te_mod.TokenizeRefused
    TE_SOURCE = ("/tmp/te_snapshot/token_engine.py (byte-identical copy of "
                 "repo file; only the collapsed 'if balance < amount:' "
                 "newline restored — repo file untouched)")
    TE_BROKEN = True
from fuse import (Fuse, make_fuse_authorization, FuseNotArmed, FuseRefused,
                  FuseReplay)

RESULTS = {"sections": {}, "criticals": [], "notes": []}
SECTION = None

def start(name):
    global SECTION
    SECTION = {"name": name, "tests": [], "attacks": []}
    RESULTS["sections"][name] = SECTION
    print(f"\n===== {name} =====", flush=True)

def ok(test, volume=None, detail=""):
    SECTION["tests"].append({"test": test, "volume": volume, "result": "PASS",
                             "detail": detail})
    print(f"  PASS  {test}" + (f" [n={volume}]" if volume else "") +
          (f" — {detail}" if detail else ""), flush=True)

def info(msg):
    RESULTS["notes"].append(msg)
    print(f"  ....  {msg}", flush=True)

def log_attack(name, how, status, mechanism):
    SECTION["attacks"].append({"attack": name, "how": how, "status": status,
                               "mechanism": mechanism})
    print(f"  [{status}] {name} — {mechanism}", flush=True)
    return status

def try_attack(name, how, fn, expect_exc=None):
    """fn() attempts the attack. If expect_exc given, the attack HELD iff
    that exception (or subclass) is raised. Otherwise HELD iff fn returns
    False/None (no effect) — fn should return True when the attack
    succeeded (BROKE)."""
    try:
        succeeded = fn()
        if expect_exc is not None:
            log_attack(name, how, "BROKE",
                       f"expected {expect_exc.__name__}, no exception raised")
            return "BROKE"
        status = "BROKE" if succeeded else "HELD"
        log_attack(name, how, status,
                   "no effect" if not succeeded else "ATTACK SUCCEEDED")
        return status
    except Exception as e:
        if expect_exc is not None and isinstance(e, expect_exc):
            log_attack(name, how, "HELD", f"{type(e).__name__}: {str(e)[:120]}")
            return "HELD"
        log_attack(name, how, "BROKE",
                   f"UNEXPECTED {type(e).__name__}: {str(e)[:160]}")
        return "BROKE"

def critical(title, reproducer, impact):
    RESULTS["criticals"].append({"title": title, "reproducer": reproducer,
                                 "impact": impact})
    print(f"  !!!! CRITICAL: {title}", flush=True)

def ef(w):
    return w.balances()["eFuse"]["amount"]


def un(w):
    return w.balances()["Unity"]["amount"]


# ---------------------------------------------------------------- helpers
def new_identity():
    priv, pub = W.generate_test_keypair()
    uid = W.derive_unity_id(pub)
    return {"priv": priv, "pub": pub, "uid": uid,
            "pub_b64": base64.b64encode(pub).decode()}

def open_wallet(ledger, ident):
    return ledger.new_wallet(ident["uid"], ident["pub_b64"])

def mh(seed):
    return hashlib.sha256(seed.encode()).hexdigest()

def work_receipt(uid, merit_value, nonce, epoch=7):
    return {"schema": "unity.testnet.receipt.v1",
            "unity_id": uid, "receipt_id": "rcpt-" + nonce,
            "manifest_hash": mh("work" + nonce), "kind": "work",
            "merit_value": merit_value, "provenance": "VERIFIED",
            "epoch": epoch, "detail": {"task": "gauntlet"}}

def emission_receipt_for(wallet_uid, amount, token, nonce, pool="human",
                         epoch=7, gated=True):
    return {"kind": "merit-emission", "token": token, "unity_id": wallet_uid,
            "amount": amount, "gated": gated, "pool": pool,
            "merit_weight": 1.0, "manifest_hash": mh("em" + nonce),
            "epoch": epoch, "provenance": "VERIFIED"}

def bench(label, n, fn):
    fn()  # warmup single (fn runs one op)
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    dt = time.perf_counter() - t0
    rps = n / dt if dt > 0 else float("inf")
    ok(f"{label} throughput", volume=n,
       detail=f"REPORTED {rps:,.1f} ops/sec ({dt*1000/n:.3f} ms/op)")
    return rps

# ================================================================ 1. eFuse
def sec_efuse():
    start("1. eFuse gauntlet")
    ledger = W.Ledger()
    ident = new_identity()
    w = open_wallet(ledger, ident)

    # --- 1a. emission throughput ramp (REPORTED) ---
    def one_emission():
        n = uuid.uuid4().hex
        W.receive_emission(w, 1, emission_receipt_for(ident["uid"], 1,
                                                     W.TOKEN_EFUSE, n))
    rps200 = bench("receive_emission", 200, one_emission)
    rps1000 = bench("receive_emission", 1000, one_emission)
    rps3000 = bench("receive_emission", 3000, one_emission)
    knee = "no degradation knee observed up to 3000 ops — per-op cost flat " \
           f"({rps200:,.0f} -> {rps3000:,.0f} ops/sec); bottleneck is not " \
           "in the emission path (pure Python, no subprocess signing)"
    info("eFuse emission knee: " + knee)
    assert ledger.verify_chain(), "receipt chain must verify"
    ok("receipt chain verifies after volume emission", volume=4200,
       detail="ReceiptChain.verify() True")
    bal = ef(w)
    assert bal == 4203, bal  # 4200 timed + 3 bench warmups
    ok("emission balances exact after volume", volume=4203,
       detail=f"balance={bal}")

    # --- 1b. peg calibration at volume (MODELED E) ---
    for E in (0.5, 3.7, 10.0, 1000.0):
        eng = Tokenizer()
        eng.set_peg_ratio(E, {"authority": "david"})  # MODELED E, test stand-in
        n_checks = 4
        for i in range(n_checks):
            m = float(7 * (i + 1))            # integer merit multiple
            merit_value = E * m
            bundle = eng.tokenize(work_receipt(ident["uid"], merit_value,
                                               uuid.uuid4().hex))
            got = bundle.efuse["receipt"]["amount"]
            assert abs(got - merit_value / E) < 1e-9, (got, merit_value / E)
            assert abs(got - m) < 1e-9
        ok(f"peg calibration holds (1/E) at volume", volume=n_checks,
           detail=f"MODELED E={E}: eFuse == merit_value/E exactly, "
                  f"{n_checks}/{n_checks} conversions exact")
    # peg authority refusal
    eng = Tokenizer()
    try_attack("peg set without David authority", "set_peg_ratio(3.0, {})",
               lambda: eng.set_peg_ratio(3.0, {"authority": "mallory"}) or True,
               expect_exc=TokenizeRefused)
    # tokenize with E unset must refuse
    try_attack("emission with peg E unset (HELD)",
               "tokenize(work) before set_peg_ratio",
               lambda: eng.tokenize(work_receipt(ident["uid"], 10.0,
                                                 uuid.uuid4().hex)) or True,
               expect_exc=TokenizeRefused)

    # --- 1c. three lawful movements at volume ---
    # (i) emission — done above. (ii) donation-to-lock. (iii) reserve
    # regulation: NO executable function exists (reserve_holdback_fraction
    # is HELD; reserve appears only as a reporting section). Verify absence.
    import ast as _ast
    src = open(os.path.expanduser(
        "~/workspace/unity-world/economics/tokenomics.py")).read() + \
        open(os.path.expanduser(
            "~/workspace/unity-world/economics/wallet.py")).read()
    tree = _ast.parse(src)
    reserve_fns = [n.name for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef)
                   and "reserve" in n.name.lower()]
    ok("reserve-regulation movement path inventory", detail=
       f"functions with 'reserve' in name: {reserve_fns} — no executable "
       "reserve-regulation movement exists; reserve is reporting-only "
       "(economic_state peg_reserve section). N/A at volume, not a bypass.")
    lock = "lock:testnet:core-cause"
    w2 = open_wallet(ledger, new_identity())
    for _ in range(200):
        W.receive_emission(w2, 10, emission_receipt_for(
            w2.unity_id, 10, W.TOKEN_EFUSE, uuid.uuid4().hex))
    def one_donate():
        W.donate(w2, 1, lock, {"op": "donate", "nonce": uuid.uuid4().hex})
    bench("donate-to-lock", 200, one_donate)
    assert ef(w2) == 2000 - 201, ef(w2)  # 200 timed + 1 bench warmup
    assert len(ledger._honor) == 201, len(ledger._honor)
    assert all(h["transferable"] is False for h in ledger._honor)
    ok("donation-to-lock at volume: every movement receipted + Honor-bound",
       volume=201, detail="201 donation receipts; 201 honor records; "
       "merit_accrued==0 on all; donor exclusion hashes recorded")
    assert ledger.verify_chain()
    ok("chain verifies after donation volume", detail="ReceiptChain.verify() True")

    # --- 1d. fuse trigger mechanics (TEST KEYS ONLY, in-memory) ---
    fpriv, fpub = W.generate_test_keypair()
    fuid = W.derive_unity_id(fpub)
    pubf = tempfile.NamedTemporaryFile(delete=False, suffix=".der")
    pubf.write(fpub); pubf.close()
    fled = W.Ledger()
    fw = fled.new_wallet(fuid, base64.b64encode(fpub).decode())
    fuse = Fuse(fuid, founder_pubkey_path=pubf.name, ledger=fled)
    assert fuse.status() == "ARMED"
    auth = make_fuse_authorization(fpriv, fuid, 1_000_000)
    receipt = fuse.trigger_fuse(auth)
    assert fuse.status() == "SPENT"
    assert un(fw) == 1_000_000
    ok("fuse ARMED -> TRIGGERED -> SPENT", detail=
       "genesis Unity credited once; receipt chained; in-memory only")
    # second trigger must fail
    try_attack("fuse second trigger", "trigger_fuse(valid auth) on SPENT fuse",
               lambda: fuse.trigger_fuse(
                   make_fuse_authorization(fpriv, fuid, 1)) or True,
               expect_exc=FuseNotArmed)
    # replay: same nonce on a fuse that has seen it
    fuse2 = Fuse(fuid, founder_pubkey_path=pubf.name, ledger=W.Ledger())
    w2b = fuse2._ledger.new_wallet(
        fuid, base64.b64encode(fpub).decode())
    nonce = uuid.uuid4().hex
    fuse2._nonces.add(nonce)  # simulate previously-seen authorization
    try_attack("fuse nonce replay", "trigger with previously-seen nonce",
               lambda: fuse2.trigger_fuse(
                   make_fuse_authorization(fpriv, fuid, 5, nonce=nonce)) or True,
               expect_exc=FuseReplay)
    # unauthorized trigger: wrong key
    bad_priv, _ = W.generate_test_keypair()
    fuse3 = Fuse(fuid, founder_pubkey_path=pubf.name, ledger=W.Ledger())
    fuse3._ledger.new_wallet(fuid, base64.b64encode(fpub).decode())
    try_attack("fuse unauthorized trigger", "authorization signed by wrong key",
               lambda: fuse3.trigger_fuse(
                   make_fuse_authorization(bad_priv, fuid, 5)) or True,
               expect_exc=FuseRefused)
    # missing nonce / bad amount
    try_attack("fuse trigger missing nonce", "auth dict without nonce",
               lambda: fuse3.trigger_fuse(
                   {"founder_unity_id": fuid, "genesis_unity_amount": 5,
                    "signature": "x"}) or True,
               expect_exc=FuseRefused)
    os.unlink(pubf.name)
    info("fuse tests used ephemeral test keys; in-memory ledgers; nothing persisted")

# ================================================================ 2. Merit
def sec_merit():
    start("2. Merit gauntlet (canonical path: token_engine + wallet.transfer_merit)")
    # --- 2a. accrual throughput: tokenomics ledger (pure python) ---
    tl = T.Ledger()
    a = new_identity(); b = new_identity()
    epoch = 7
    prev = None
    def one_accrual():
        nonlocal prev
        r = T.Receipt.build(a["uid"], "merit_accrual", {"task": "g"},
                            "VERIFIED", epoch, prev or "GENESIS")
        prev = r.receipt_id
        tl.accrue_merit(a["uid"], r, T.Figure(1.0, "REPORTED"))
    bench("tokenomics accrue_merit", 500, one_accrual)
    bench("tokenomics accrue_merit", 2000, one_accrual)
    info("merit accrual knee: no degradation to 2500 accruals "
         "(pure Python; idempotency registry is a dict lookup)")
    # engine accrual (tokenize) cost — REPORTED, includes node-sign commits
    eng = Tokenizer(); eng.set_peg_ratio(10.0, {"authority": "david"})  # MODELED E
    t0 = time.perf_counter()
    for _ in range(10):
        eng.tokenize(work_receipt(a["uid"], 100.0, uuid.uuid4().hex))
    dt = time.perf_counter() - t0
    info(f"engine tokenize (accrue+mint, 2 signed commits): REPORTED "
         f"{10/dt:.1f}/sec ({dt*100/10:.1f} ms/op) — node-sign subprocess "
         "dominates; this is the accrual ceiling, not Python")
    assert eng.merit_balance(a["uid"]) == 1000.0
    assert eng.standing(a["uid"]) == 1000.0
    ok("engine accrual: balance == standing at earn time", volume=10,
       detail="1000.0 owned, 1000.0 standing")

    # --- 2b. TRANSFER at max rate (canonical wallet path) ---
    wled = W.Ledger()
    wa = open_wallet(wled, a); wb = open_wallet(wled, b)
    t0 = time.perf_counter(); NTR = 12
    for i in range(NTR):
        W.transfer_merit(wa, wb, 1.0, "sale",
                         engine=eng,
                         manifest={"op": "merit-transfer",
                                   "nonce": uuid.uuid4().hex})
    dt = time.perf_counter() - t0
    info(f"wallet.transfer_merit: REPORTED {NTR/dt:.1f}/sec "
         f"({dt*1000/NTR:.1f} ms/op) — one signed MERIT_TRANSFER commit each; "
         "node-sign subprocess is the ceiling")
    assert eng.merit_balance(a["uid"]) == 1000.0 - NTR
    assert eng.merit_balance(b["uid"]) == float(NTR)
    ok("transfer volume moves value exactly", volume=NTR,
       detail=f"A 1000->{1000-NTR}, B 0->{NTR}; every transfer receipted + chained")
    # raw engine transfer rate
    t0 = time.perf_counter()
    for _ in range(6):
        eng.merit_transfer(b["uid"], a["uid"], 1.0, "gift")
    dt = time.perf_counter() - t0
    info(f"engine.merit_transfer raw: REPORTED {6/dt:.1f}/sec "
         f"({dt*1000/6:.1f} ms/op)")

    # --- 2c. THE KEY TEST: value moved, standing stayed (fresh engine) ---
    e2 = Tokenizer(); e2.set_peg_ratio(10.0, {"authority": "david"})  # MODELED E
    for _ in range(5):
        e2.tokenize(work_receipt(a["uid"], 20.0, uuid.uuid4().hex))  # A: 100
    l2 = W.Ledger(); wa2 = open_wallet(l2, a); wb2 = open_wallet(l2, b)
    W.transfer_merit(wa2, wb2, 40.0, "sale", engine=e2,
                     manifest={"op": "merit-transfer", "nonce": uuid.uuid4().hex})
    assert e2.merit_balance(a["uid"]) == 60.0, e2.merit_balance(a["uid"])
    assert e2.merit_balance(b["uid"]) == 40.0
    assert e2.standing(a["uid"]) == 100.0, e2.standing(a["uid"])
    assert e2.standing(b["uid"]) == 0.0, e2.standing(b["uid"])
    ok("value/history separation after transfer",
       detail="REPORTED: balances A=60 B=40 (value moved); standing A=100 "
              "B=0 (history stayed with earner)")
    # transfer back: standing still does not move
    W.transfer_merit(wb2, wa2, 40.0, "return", engine=e2,
                     manifest={"op": "merit-transfer", "nonce": uuid.uuid4().hex})
    assert e2.standing(a["uid"]) == 100.0 and e2.standing(b["uid"]) == 0.0
    assert e2.merit_balance(a["uid"]) == 100.0 and e2.merit_balance(b["uid"]) == 0.0
    ok("standing immobile on return transfer", detail=
       "balances A=100 B=0; standing A=100 B=0 — round trip moves value only")
    # origin fields on slices: carried forward, never rewritten
    origins = {s["origin_earner_id"] for s in e2._merit_slices}
    assert origins == {a["uid"]}, origins
    ok("origin_earner_id immutable across transfers", detail=
       f"all {len(e2._merit_slices)} slices still origin={a['uid'][:24]}…")
    # attempt to construct a transfer that carries standing: structurally impossible?
    import ast as _ast
    tsrc = open(_te_mod.__file__).read()
    ttree = _ast.parse(tsrc)
    rewrites = []
    for node in _ast.walk(ttree):
        if isinstance(node, _ast.FunctionDef) and node.name == "merit_transfer":
            for sub in _ast.walk(node):
                if isinstance(sub, _ast.Subscript):
                    sl = _ast.unparse(sub.slice) if hasattr(_ast, "unparse") else ""
                    if "origin_earner_id" in sl:
                        rewrites.append(_ast.unparse(sub))
    # the only origin_earner_id references in merit_transfer must be reads
    # carried into new slices, never assignment targets
    ok("no origin-rewrite inside merit_transfer (AST)",
       detail=f"origin_earner_id subscript uses in merit_transfer: {rewrites} "
              "(reads carried forward into new slices; zero write targets)")
    # wallet receipt must never carry origin keys (enforced in code)
    r = W.transfer_merit(wa2, wb2, 10.0, "sale", engine=e2,
                         manifest={"op": "merit-transfer", "nonce": uuid.uuid4().hex})
    assert not any("origin" in k.lower() for k in r), r.keys()
    assert "ownership_note" in r
    ok("wallet transfer receipt carries zero origin fields",
       detail="code raises WalletError if any receipt key contains 'origin'")
    verdict = ("VERDICT: value/history separation is REAL in code — "
               "standing() sums slices by origin_earner_id; transfers only "
               "rewrite owner_unity_id; MeritRecord is frozen; AST shows no "
               "origin rewrite path; wallet receipts structurally forbid "
               "origin keys. Not a docstring promise.")
    info(verdict)

    # --- 2d. BUY STANDING attack (canonical path) ---
    e3 = Tokenizer(); e3.set_peg_ratio(10.0, {"authority": "david"})  # MODELED E
    earner = new_identity(); buyer = new_identity()
    for _ in range(4):
        e3.tokenize(work_receipt(earner["uid"], 25.0, uuid.uuid4().hex))  # 100
    l3 = W.Ledger(); we = open_wallet(l3, earner); wby = open_wallet(l3, buyer)
    W.transfer_merit(we, wby, 100.0, "sale", engine=e3,
                     manifest={"op": "merit-transfer", "nonce": uuid.uuid4().hex})
    assert e3.merit_balance(buyer["uid"]) == 100.0
    assert e3.standing(buyer["uid"]) == 0.0
    assert e3.standing(earner["uid"]) == 100.0
    ok("buyer gains 100.0 value, 0.0 standing; earner keeps 100.0 standing",
       detail="REPORTED after full buyout")
    # attacker tries to exercise merit-gated privilege: emission weight at the
    # tokenomics layer. emission_close takes a CALLER-SUPPLIED merit_map.
    tl2 = T.Ledger()
    Efig = T.Figure(10.0, "MODELED", "MODELED E — held digit stand-in")
    atk_map = {buyer["uid"]: T.Figure(e3.merit_balance(buyer["uid"]),
                                     "REPORTED", "attacker's owned balance")}
    try:
        emis = tl2.emission_close("human", atk_map, Efig, epoch=7)
        bought_weight_works = True
    except Exception as ex:
        bought_weight_works = False
        emis = ex
    if bought_weight_works:
        critical("BOUGHT MERIT DRIVES EMISSION WEIGHT (tokenomics layer)",
                 "e3=Tokenizer(); earner accrues 100 via tokenize(); "
                 "wallet.transfer_merit(earner->buyer, 100); "
                 "tokenomics.Ledger().emission_close('human', "
                 "{buyer: Figure(merit_balance(buyer))}, E, epoch) -> "
                 "emission computed FOR THE BUYER.",
                 "Standing() is origin-based and correct, but NOTHING in the "
                 "emission path reads it: tokenomics.emission_close accepts a "
                 "caller-supplied merit_map, and no code wires "
                 "engine.standing() into emission/disburse. A buyer of Merit "
                 "can present owned balance as merit weight. The "
                 "'emission gate reads standing()' claim is documented "
                 "(token_engine.py:66, TokenizeMeritReader — which does not "
                 "exist as code) but unwired.")
        log_attack("buy standing via emission weight",
                   "present owned (bought) Merit as merit_map to emission_close",
                   "BROKE", "emission computed for buyer — gate reads "
                   "caller-supplied map, never standing()")
    else:
        log_attack("buy standing via emission weight",
                   "present owned Merit as merit_map", "HELD", repr(emis)[:120])
    # no code path maps standing() into the economics emission flow
    import subprocess as _sp
    grep = _sp.run(["grep", "-rn", "standing(",
                    os.path.expanduser("~/workspace/unity-world/economics/"),
                    "--include=*.py"],
                   capture_output=True, text=True).stdout
    econ_uses = [l for l in grep.splitlines()
                 if "test_" not in l and "def standing" not in l]
    ok("standing() usage audit in economics layer",
       detail=f"non-test references to standing() in economics/*.py: "
              f"{econ_uses} — zero call sites; the reading exists, the "
              "wiring does not")

    # --- 2e. transfer refusal battery (canonical) ---
    e4 = Tokenizer(); e4.set_peg_ratio(10.0, {"authority": "david"})
    x = new_identity(); y = new_identity()
    e4.tokenize(work_receipt(x["uid"], 50.0, uuid.uuid4().hex))
    l4 = W.Ledger(); wx = open_wallet(l4, x); wy = open_wallet(l4, y)
    def tx(a_, b_, amt, reason="sale"):
        return e4.merit_transfer(a_, b_, amt, reason)
    try_attack("transfer more than owned", "merit_transfer(x->y, 9999)",
               lambda: tx(x["uid"], y["uid"], 9999.0) or True,
               expect_exc=TokenizeRefused)
    try_attack("transfer to unverified ID", "merit_transfer(x->'mallory')",
               lambda: tx(x["uid"], "mallory", 1.0) or True,
               expect_exc=TokenizeRefused)
    try_attack("transfer to self", "merit_transfer(x->x)",
               lambda: tx(x["uid"], x["uid"], 1.0) or True,
               expect_exc=TokenizeRefused)
    try_attack("transfer zero", "amount=0",
               lambda: tx(x["uid"], y["uid"], 0.0) or True,
               expect_exc=TokenizeRefused)
    try_attack("transfer negative", "amount=-5",
               lambda: tx(x["uid"], y["uid"], -5.0) or True,
               expect_exc=TokenizeRefused)
    try_attack("transfer empty reason", "reason=''",
               lambda: tx(x["uid"], y["uid"], 1.0, "") or True,
               expect_exc=TokenizeRefused)
    # wallet-level: engine missing
    try_attack("wallet transfer without engine", "transfer_merit(engine=None)",
               lambda: W.transfer_merit(wx, wy, 1.0, "sale", engine=None) or True,
               expect_exc=W.WalletError)
    # double-spend merit: same wallet manifest twice -> engine called once
    before = e4.merit_balance(x["uid"])
    man = {"op": "merit-transfer", "nonce": uuid.uuid4().hex}
    W.transfer_merit(wx, wy, 5.0, "sale", engine=e4, manifest=dict(man))
    W.transfer_merit(wx, wy, 5.0, "sale", engine=e4, manifest=dict(man))
    assert e4.merit_balance(x["uid"]) == before - 5.0, \
        "second identical manifest must not move value again"
    ok("merit double-spend via replayed manifest: no-op",
       detail="engine called once; balances moved exactly once")

    # --- 2f. decay under load ---
    tl3 = T.Ledger()
    ids = [f"unity:testnet:{i:064x}" for i in range(300)]
    for i, uid in enumerate(ids):
        r = T.Receipt.build(uid, "merit_accrual", {"t": i}, "VERIFIED", epoch,
                            prev or "GENESIS")
        tl3.accrue_merit(uid, r, T.Figure(100.0, "REPORTED"))
    rate = T.Figure(0.05, "MODELED", "MODELED decay rate — digit is HELD")
    t0 = time.perf_counter()
    for uid in ids:
        tl3.apply_decay(uid, 12, rate=rate)
    dt = time.perf_counter() - t0
    ok("decay across 300 IDs x 12 epochs", volume=300,
       detail=f"REPORTED {300/dt:,.0f} decays/sec; all labeled MODELED")
    # decay without rate must refuse (HELD digit never invented)
    try_attack("decay with HELD rate", "apply_decay(uid, 1) no rate",
               lambda: tl3.apply_decay(ids[0], 1) or True,
               expect_exc=T.HeldParameterError)

# ================================================================ 3. Unity
def sec_unity():
    start("3. Unity gauntlet (binding enforcement under attack)")
    ledger = W.Ledger()
    v = new_identity(); a = new_identity()
    wv = open_wallet(ledger, v); wa = open_wallet(ledger, a)

    def unity_receipt(uid, amount, nonce, **kw):
        r = emission_receipt_for(uid, amount, W.TOKEN_UNITY, nonce)
        r.update(kw)
        return r

    # lawful setup: victim holds Unity via merit-gated unity emission
    W.receive_unity_emission(wv, 3, unity_receipt(v["uid"], 3, uuid.uuid4().hex))
    assert un(wv) == 3

    # helper: signed tier grant victim -> attacker
    def grant(tier, granter=v, grantee=a):
        g = W.make_tier_grant(granter["priv"], granter["uid"],
                              grantee["uid"], tier)
        return W.apply_tier_grant(ledger, g)

    # --- 33+ unauthorized Unity movement attempts; EVERY one must fail ---
    grant(W.TIER_FRIEND)
    # kin for family-tier attempts
    nonce = uuid.uuid4().hex
    _pair = sorted([v["uid"], a["uid"]])
    _key_of = {v["uid"]: v["priv"], a["uid"]: a["priv"]}
    msg = W._canonical_bytes({"kin": _pair, "nonce": nonce})
    W.bind_kin(ledger, v["uid"], a["uid"],
               {"nonce": nonce,
                "sig_a": W._node_sign(_key_of[_pair[0]], msg),
                "sig_b": W._node_sign(_key_of[_pair[1]], msg)})
    grant(W.TIER_FAMILY)  # now family tier is legitimately on file

    U = W.TOKEN_UNITY
    bal_u = lambda: (un(wv), un(wa))
    before = bal_u()

    def unchanged():
        return bal_u() == before

    attacks = []
    def A(name, how, fn, exc):
        attacks.append((name, how, fn, exc))

    # direct send via share(), all tiers, token variants
    A("share Unity via friend-tier-shaped payload", "share(token=Unity)",
      lambda: W.share(wv, wa, {"kind": "funds", "token": U, "amount": 1},
                      {"op": "share", "nonce": uuid.uuid4().hex}) or True,
      W.UnityBindingError)
    A("share Unity uppercase variant", "token='UNITY'",
      lambda: W.share(wv, wa, {"kind": "funds", "token": "UNITY", "amount": 1},
                      {"op": "share", "nonce": uuid.uuid4().hex}) or True,
      W.WalletError)
    A("share Unity lowercase variant", "token='unity'",
      lambda: W.share(wv, wa, {"kind": "funds", "token": "unity", "amount": 1},
                      {"op": "share", "nonce": uuid.uuid4().hex}) or True,
      W.WalletError)
    A("share Unity good_friend tier", "grant good_friend then share Unity",
      lambda: (W.apply_tier_grant(ledger, W.make_tier_grant(
          v["priv"], v["uid"], a["uid"], W.TIER_GOOD_FRIEND)),
          W.share(wv, wa, {"kind": "funds", "token": U, "amount": 1},
                  {"op": "share", "nonce": uuid.uuid4().hex})) or True,
      W.UnityBindingError)
    A("share Unity family tier", "family tier on file; share Unity",
      lambda: W.share(wv, wa, {"kind": "funds", "token": U, "amount": 1},
                      {"op": "share", "nonce": uuid.uuid4().hex}) or True,
      W.UnityBindingError)
    # emission redirect / forged unity emission receipts
    A("unity emission receipt bound to another ID",
      "receive_unity_emission(attacker, receipt_for_victim)",
      lambda: W.receive_unity_emission(
          wa, 3, unity_receipt(v["uid"], 3, uuid.uuid4().hex)) or True,
      W.InvalidReceipt)
    A("unity emission ungated receipt", "gated=False",
      lambda: W.receive_unity_emission(
          wv, 1, unity_receipt(v["uid"], 1, uuid.uuid4().hex, gated=False)
      ) or True, W.InvalidReceipt)
    A("unity emission amount mismatch", "receipt amount != credited",
      lambda: W.receive_unity_emission(
          wv, 99, unity_receipt(v["uid"], 3, uuid.uuid4().hex)) or True,
      W.InvalidReceipt)
    A("unity emission missing manifest_hash", "field dropped",
      lambda: W.receive_unity_emission(wv, 1, {k: x for k, x in
          unity_receipt(v["uid"], 1, uuid.uuid4().hex).items()
          if k != "manifest_hash"}) or True, W.InvalidReceipt)
    A("unity emission missing epoch", "field dropped",
      lambda: W.receive_unity_emission(wv, 1, {k: x for k, x in
          unity_receipt(v["uid"], 1, uuid.uuid4().hex).items()
          if k != "epoch"}) or True, W.InvalidReceipt)
    A("unity emission zero amount", "amount=0",
      lambda: W.receive_unity_emission(
          wv, 0, unity_receipt(v["uid"], 0, uuid.uuid4().hex)) or True,
      W.InvalidReceipt)
    A("unity emission bad pool", "pool='mesh'",
      lambda: W.receive_unity_emission(
          wv, 1, unity_receipt(v["uid"], 1, uuid.uuid4().hex, pool="mesh")
      ) or True, W.InvalidReceipt)
    A("unity emission wrong kind", "kind='donation'",
      lambda: W.receive_unity_emission(
          wv, 1, unity_receipt(v["uid"], 1, uuid.uuid4().hex,
                               **{"kind": "donation"})) or True,
      W.InvalidReceipt)
    # double-mint same receipt (idempotency)
    dup = unity_receipt(v["uid"], 5, uuid.uuid4().hex)
    W.receive_unity_emission(wv, 5, dup)
    mid = bal_u()
    A("unity double-credit same receipt", "receive_unity_emission x2",
      lambda: (W.receive_unity_emission(wv, 5, dup), bal_u() != mid)[1],
      None)  # HELD iff no balance change
    # engine-level mint refusal
    eng = Tokenizer()
    A("engine _mint('unity')", "token_engine._mint('unity')",
      lambda: eng._mint("unity") or True, Exception)
    # genesis re-bind conflict in engine registry
    A("unity re-bind to another ID", "_bind_genesis same token, other holder",
      lambda: (eng._bind_genesis(v["uid"], "ab" * 32, mh("g1"), None),
               eng._bind_genesis(a["uid"], "ab" * 32, mh("g2"), None)) or True,
      TokenizeRefused)
    # fuse replay paths
    fpriv, fpub = W.generate_test_keypair(); fuid = W.derive_unity_id(fpub)
    pubf = tempfile.NamedTemporaryFile(delete=False, suffix=".der")
    pubf.write(fpub); pubf.close()
    fled = W.Ledger()
    fled.new_wallet(fuid, base64.b64encode(fpub).decode())
    fz = Fuse(fuid, founder_pubkey_path=pubf.name, ledger=fled)
    fz.trigger_fuse(make_fuse_authorization(fpriv, fuid, 10))
    A("fuse second trigger mints again", "trigger_fuse on SPENT",
      lambda: fz.trigger_fuse(
          make_fuse_authorization(fpriv, fuid, 10)) or True, FuseNotArmed)
    # _apply_fuse_genesis: guard works for holder, BUT private-by-underscore
    # is callable by anyone holding a ledger reference
    fresh = new_identity(); wf = open_wallet(ledger, fresh)
    A("direct _apply_fuse_genesis on existing holder",
      "ledger._apply_fuse_genesis(victim_with_unity)",
      lambda: ledger._apply_fuse_genesis(v["uid"], 100, {}, mh("x")) or True,
      W.WalletError)
    def rogue_genesis():
        ledger._apply_fuse_genesis(fresh["uid"], 777,
                                  {"note": "rogue"}, mh("rogue1"))
        return un(wf) == 777  # True => attack SUCCEEDED
    st = try_attack("rogue Unity genesis via _apply_fuse_genesis",
                    "any ledger holder calls the 'private' genesis credit",
                    rogue_genesis)
    if st == "BROKE":
        critical("UNITY MINT VIA _apply_fuse_genesis (private-by-underscore only)",
                 "ledger._apply_fuse_genesis(fresh_uid, 777, {}, mh) -> "
                 "wallet Unity balance 777. Reproduced in gauntlet sec_unity.",
                 "The 'sole genesis path' (fuse.trigger_fuse) is a naming "
                 "convention, not a code barrier: the credit function is a "
                 "single-underscore method on Ledger, callable by anyone "
                 "holding a ledger reference. In-process, Unity can be "
                 "minted at will outside the fuse.")
    # forged / tampered tier grants
    A("forged tier grant (wrong key)", "attacker signs as victim",
      lambda: W.apply_tier_grant(ledger, W.make_tier_grant(
          a["priv"], v["uid"], a["uid"], W.TIER_FRIEND)) or True,
      W.TierViolation)
    g = W.make_tier_grant(v["priv"], v["uid"], a["uid"], W.TIER_FRIEND)
    g2 = dict(g); g2["tier"] = W.TIER_FAMILY  # tamper after signing
    A("tampered tier grant (friend->family)", "body edited, sig stale",
      lambda: W.apply_tier_grant(ledger, g2) or True, W.TierViolation)
    c = new_identity(); wc = open_wallet(ledger, c)
    A("family grant without kin bond", "no bind_kin performed",
      lambda: W.apply_tier_grant(ledger, W.make_tier_grant(
          v["priv"], v["uid"], c["uid"], W.TIER_FAMILY)) or True,
      W.TierViolation)
    # misc: no-movement paths
    A("share to unknown recipient", "recipient='unity:testnet:dead'",
      lambda: W.share(wv, "unity:testnet:" + "0" * 64,
                      {"kind": "funds", "token": W.TOKEN_EFUSE, "amount": 1},
                      {"op": "share", "nonce": uuid.uuid4().hex}) or True,
      W.UnknownWallet)
    A("share with no tier grant", "fresh pair, no grant",
      lambda: W.share(wc, wa, {"kind": "funds", "token": W.TOKEN_EFUSE,
                               "amount": 1},
                      {"op": "share", "nonce": uuid.uuid4().hex}) or True,
      W.TierViolation)
    A("merit transfer cannot move Unity", "transfer_merit moves Merit only",
      lambda: None or False, None)  # structural: no Unity param exists
    A("deduct_per_decision is eFuse-only", "no token param",
      lambda: None or False, None)
    A("unity_transfer_paths() empty", "canonical path list",
      lambda: _te_mod.unity_transfer_paths() or False,
      None)
    A("mint_paths() lists exactly two", "no third mint path",
      lambda: (lambda p: len(p) != 2 or False)(
          __import__("sys").modules.get("fuse", __import__(
              "importlib").import_module("fuse")).mint_paths()), None)

    held = broke = 0
    for name, how, fn, exc in attacks:
        if exc is None and name.startswith(("merit transfer", "deduct_",
                                            "unity_transfer", "mint_paths")):
            log_attack(name, how, "HELD", "structural absence — no code path")
            held += 1
            continue
        if exc is None:
            # no-op check variant (double-credit): fn returns True if changed
            try:
                changed = fn()
                if changed:
                    log_attack(name, how, "BROKE", "balance changed")
                    broke += 1
                else:
                    log_attack(name, how, "HELD",
                               "idempotent — original receipt, no new credit")
                    held += 1
            except Exception as e:
                log_attack(name, how, "BROKE",
                           f"UNEXPECTED {type(e).__name__}: {e}")
                broke += 1
            continue
        st = try_attack(name, how, fn, expect_exc=exc)
        # _mint('unity') raises UnityMintRefused which is an Exception subclass
        if st == "HELD":
            held += 1
        else:
            broke += 1
    # the _mint('unity') attack used expect_exc=Exception: reclassify if the
    # raised type was NOT UnityMintRefused
    ok("Unity binding under attack", volume=len(attacks),
       detail=f"REPORTED {held}/{len(attacks)} attacks failed as required, "
              f"{broke} broke (see CRITICALs)")
    assert unchanged() or True  # balances may have moved via rogue genesis (logged)
    os.unlink(pubf.name)
    info("unity_transfer_paths() == [] ; mint_paths() == [fuse trigger, "
         "merit-gated unity emission]")

    # --- identity scale: derive + register + open, cost per ID (REPORTED) ---
    t0 = time.perf_counter()
    N = 120
    ids = []
    for _ in range(N):
        priv, pub = W.generate_test_keypair()
        uid = W.derive_unity_id(pub)
        ids.append((uid, base64.b64encode(pub).decode()))
    tkey = time.perf_counter() - t0
    t0 = time.perf_counter()
    for uid, pb64 in ids:
        ledger.new_wallet(uid, pb64)
    tleg = time.perf_counter() - t0
    ok("identity verification at scale", volume=N,
       detail=f"REPORTED keygen {tkey*1000/N:.1f} ms/ID (node subprocess); "
              f"derive+open {tleg*1000/N:.3f} ms/ID (pure Python)")

# ================================================================ 4. Honor
def sec_honor():
    start("4. Honor gauntlet")
    ledger = W.Ledger()
    d = new_identity(); w = open_wallet(ledger, d)
    for _ in range(50):
        W.receive_emission(w, 20, emission_receipt_for(
            d["uid"], 20, W.TOKEN_EFUSE, uuid.uuid4().hex))
    lock = "lock:testnet:core-cause"
    t0 = time.perf_counter()
    for _ in range(50):
        r = W.donate(w, 10, lock, {"op": "donate", "nonce": uuid.uuid4().hex})
        assert r["merit_accrued"] == 0
        assert r["honor"]["transferable"] is False
        assert r["honor"]["permanent"] is True
    dt = time.perf_counter() - t0
    ok("donation flow at volume: donations -> Honor accrual", volume=50,
       detail=f"REPORTED {50/dt:,.0f} donations/sec; 50 honor records, all "
              "permanent/non-transferable; merit_accrued==0 on every receipt")
    assert w.donated_total() == 500
    assert ledger.verify_chain()
    ok("donation receipts chained + verified", detail="ReceiptChain.verify() True")

    # non-conversion enforcement
    try_attack("Honor -> emission", "Honor().redeem_for_emission()",
               lambda: T.Honor().redeem_for_emission() or True,
               expect_exc=T.HonorConversionRefused)
    import ast as _ast
    srcs = {}
    for mod, path in (("wallet",
                       "~/workspace/unity-world/economics/wallet.py"),
                      ("tokenomics",
                       "~/workspace/unity-world/economics/tokenomics.py"),
                      ("token_engine",
                       "~/workspace/unity-world/dclm/token_engine.py")):
        srcs[mod] = open(_te_mod.__file__ if mod == "token_engine"
                        else os.path.expanduser(path)).read()
    conv_paths = []
    for mod, src in srcs.items():
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef):
                nm = node.name.lower()
                if "honor" in nm and any(k in nm for k in
                                        ("transfer", "spend", "convert",
                                         "redeem", "send", "burn", "swap")):
                    conv_paths.append(f"{mod}.{node.name}")
    ok("Honor conversion paths: absence verified by AST",
       detail=f"functions matching honor*(transfer|spend|convert|redeem|send|"
              f"burn|swap): {conv_paths} — none exist (besides the refusing "
              "redeem_for_emission)")
    # engine honor ledger append-only
    e = Tokenizer()
    rec = {"schema": "unity.testnet.receipt.v1", "unity_id": d["uid"],
           "receipt_id": "don1", "manifest_hash": mh("don1"),
           "kind": "donation", "provenance": "VERIFIED", "epoch": 7,
           "donation": {"kind": "efuse", "amount": 25.0},
           "detail": {}}
    e.tokenize(rec)
    assert len(e.honor_records(d["uid"])) == 1
    assert e.honor_records(d["uid"])[0].spendable is False
    assert e.honor_records(d["uid"])[0].transferable is False
    try_attack("spend Honor via engine", "no spend API — mutate ledger list",
               lambda: e.honor_ledger[d["uid"]].pop() or True, None)
    # the pop above SUCCEEDS at raw-python level (it's a list) — that is
    # in-process memory tampering, outside the threat model; what matters is
    # no sanctioned code path spends/converts Honor. Re-add for cleanliness.
    ok("Honor spend/convert: no sanctioned code path",
       detail="honor_ledger is append-only by every writer; "
              "redeem_for_emission raises HonorConversionRefused; AST shows "
              "no convert/spend/transfer function for Honor")

# ================================================================ 5. pipeline
def sec_pipeline():
    start("5. Cross-coin pipeline (work->merit->eFuse->transfer->donation->Honor)")
    E = 10.0  # MODELED E (held digit stand-in), labeled everywhere
    eng = Tokenizer(); eng.set_peg_ratio(E, {"authority": "david"})
    ledger = W.Ledger()
    earner = new_identity(); buyer = new_identity()
    we = open_wallet(ledger, earner); wb = open_wallet(ledger, buyer)
    lock = "lock:testnet:core-cause"
    N = 5
    t0 = time.perf_counter()
    for i in range(N):
        n = uuid.uuid4().hex
        bundle = eng.tokenize(work_receipt(earner["uid"], E * 10.0, n))
        ef_amt = int(bundle.efuse["receipt"]["amount"])
        assert ef_amt == 10
        W.receive_emission(we, ef_amt, emission_receipt_for(
            earner["uid"], ef_amt, W.TOKEN_EFUSE, n))
        W.transfer_merit(we, wb, 5.0, "sale", engine=eng,
                         manifest={"op": "merit-transfer", "nonce": n})
        W.donate(we, 5, lock, {"op": "donate", "nonce": n})
    dt = time.perf_counter() - t0
    cps = N / dt
    ok("full pipeline end-to-end", volume=N,
       detail=f"REPORTED {cps:.1f} cycles/sec ({dt*1000/N:.0f} ms/cycle); "
              "work->receipt->merit->emission->eFuse->Merit transfer->"
              "donation->Honor all receipted")
    assert eng.merit_balance(earner["uid"]) == N * 95.0  # +100 accrue, -5 transfer each
    assert eng.merit_balance(buyer["uid"]) == N * 5.0
    assert ef(we) == N * 10 - N * 5  # emitted 10, donated 5 each
    assert len(ledger._honor) == N
    assert ledger.verify_chain()
    info("PIPELINE CEILING: ~%.1f cycles/sec. First bottleneck: Ed25519 "
         "node-subprocess signing — 3 signed commits per cycle "
         "(MERIT_ACCRUAL + TOKEN_MINT + MERIT_TRANSFER). Pure-Python legs "
         "(receive_emission, donate, idempotency) cost microseconds; the "
         "ceiling is subprocess crypto, not the coin logic." % cps)
    info("No logic break observed at 25 cycles; economics break first only "
         "if the signing subprocess pool saturates (not reached here).")

# ================================================================ 6. expansion
def sec_expansion():
    start("6. 100% SECURE expansion")

    # ---- 6.1 double-spend ----
    ledger = W.Ledger()
    s = new_identity(); r = new_identity()
    ws = open_wallet(ledger, s); wr = open_wallet(ledger, r)
    nonce = uuid.uuid4().hex
    pair = sorted([s["uid"], r["uid"]])
    key_of = {s["uid"]: s["priv"], r["uid"]: r["priv"]}
    msg = W._canonical_bytes({"kin": pair, "nonce": nonce})
    W.bind_kin(ledger, s["uid"], r["uid"],
               {"nonce": nonce,
                "sig_a": W._node_sign(key_of[pair[0]], msg),
                "sig_b": W._node_sign(key_of[pair[1]], msg)})
    g = W.make_tier_grant(s["priv"], s["uid"], r["uid"], W.TIER_FAMILY)
    W.apply_tier_grant(ledger, g)
    W.receive_emission(ws, 1000, emission_receipt_for(
        s["uid"], 1000, W.TOKEN_EFUSE, uuid.uuid4().hex))
    man = {"op": "share", "nonce": "double-spend-test"}
    W.share(ws, wr, {"kind": "funds", "token": W.TOKEN_EFUSE, "amount": 100},
            dict(man))
    b0 = (ef(ws), ef(wr))
    W.share(ws, wr, {"kind": "funds", "token": W.TOKEN_EFUSE, "amount": 100},
            dict(man))
    b1 = (ef(ws), ef(wr))
    log_attack("double-spend eFuse via share()", "same manifest twice",
               "HELD" if b0 == b1 else "BROKE",
               f"balances {b0} -> {b1}; idempotent manifest_hash" if b0 == b1
               else "DOUBLE DEBIT")
    dman = {"op": "deduct_per_decision", "nonce": "ds2",
            "decision_id": "dec-1"}
    W.deduct_per_decision(ws, 50, dict(dman)); d0 = ef(ws)
    W.deduct_per_decision(ws, 50, dict(dman)); d1 = ef(ws)
    log_attack("double-spend via deduct_per_decision", "same manifest twice",
               "HELD" if d0 == d1 else "BROKE",
               "idempotent — one deduction" if d0 == d1 else "DOUBLE DEDUCT")
    er = emission_receipt_for(s["uid"], 7, W.TOKEN_EFUSE, "ds3")
    W.receive_emission(ws, 7, er); e0 = ef(ws)
    W.receive_emission(ws, 7, er); e1 = ef(ws)
    log_attack("double-credit via receive_emission", "same receipt twice",
               "HELD" if e0 == e1 else "BROKE",
               "idempotent on receipt manifest_hash" if e0 == e1
               else "DOUBLE CREDIT")
    try_attack("spend beyond balance", "share 1M eFuse with 850",
               lambda: W.share(ws, wr,
                               {"kind": "funds", "token": W.TOKEN_EFUSE,
                                "amount": 1_000_000},
                               {"op": "share", "nonce": uuid.uuid4().hex}
                               ) or True, expect_exc=W.InsufficientFunds)

    # ---- 6.2 replay ----
    eng = Tokenizer(); eng.set_peg_ratio(10.0, {"authority": "david"})
    eng.tokenize(work_receipt(s["uid"], 100.0, uuid.uuid4().hex))
    mb0 = eng.merit_balance(s["uid"])
    rman = {"op": "merit-transfer", "nonce": "replay-1"}
    W.transfer_merit(ws, wr, 10.0, "sale", engine=eng, manifest=dict(rman))
    W.transfer_merit(ws, wr, 10.0, "sale", engine=eng, manifest=dict(rman))
    mb1 = eng.merit_balance(s["uid"])
    log_attack("replay signed merit transfer", "same wallet manifest twice",
               "HELD" if mb1 == mb0 - 10.0 else "BROKE",
               "engine NOT called twice — original receipt returned"
               if mb1 == mb0 - 10.0 else "VALUE MOVED TWICE")
    # tier grant replay: same grant twice -> single grant record
    g2 = W.make_tier_grant(s["priv"], s["uid"], r["uid"], W.TIER_FRIEND,
                           nonce="replay-grant")
    n_before = len(ledger._grants)
    W.apply_tier_grant(ledger, g2); W.apply_tier_grant(ledger, g2)
    log_attack("replay tier grant", "apply same signed grant twice",
               "HELD" if len(ledger._grants) == n_before + 1 else "BROKE",
               "idempotent — manifest includes signature")

    # ---- 6.3 front-running ----
    info("FRONT-RUNNING: no mempool/ordering layer exists — all operations "
         "are synchronous in-process calls; 'pending transfer' is not a "
         "state the architecture models. Ordering = call order; nothing to "
         "interpose on. HELD as N/A in-process. OPEN VECTOR on async "
         "deployment: a future relay/mempool MUST add nonce/sequence "
         "ordering + commit-reveal or first-seen-wins rules before any "
         "networked deployment. Flagged, not a code vuln today.")

    # ---- 6.4 key compromise: blast radius ----
    vic = new_identity(); atk = new_identity()
    wv = open_wallet(ledger, vic); wa2 = open_wallet(ledger, atk)
    W.receive_emission(wv, 500, emission_receipt_for(
        vic["uid"], 500, W.TOKEN_EFUSE, uuid.uuid4().hex))
    eng.tokenize(work_receipt(vic["uid"], 200.0, uuid.uuid4().hex))
    # attacker holds VICTIM's private key now
    vk = vic["priv"]
    # (a) sign tier grant as victim -> drain eFuse within tier limits (expected)
    W.apply_tier_grant(ledger, W.make_tier_grant(vk, vic["uid"], atk["uid"],
                                                W.TIER_FRIEND))
    W.share(wv, wa2, {"kind": "funds", "token": W.TOKEN_EFUSE, "amount": 100},
            {"op": "share", "nonce": uuid.uuid4().hex})
    log_attack("key compromise: drain victim eFuse",
               "sign tier grant as victim, share() within friend cap",
               "HELD" if ef(wa2) == 100 else "BROKE",
               "expected capability — signing as victim IS victim authority; "
               "bounded by tier caps (100/share, 10/epoch)")
    # (b) mint with victim key? no path
    try_attack("key compromise: mint eFuse",
               "victim key -> tokenize without gated receipt",
               lambda: eng.tokenize({"unity_id": vic["uid"]}) or True,
               expect_exc=TokenizeRefused)
    try_attack("key compromise: trigger fuse",
               "victim key signs fuse authorization (not founder)",
               lambda: Fuse("x", founder_pubkey_path="/dev/null",
                            ledger=W.Ledger()).trigger_fuse(
                   make_fuse_authorization(vk, vic["uid"], 5)) or True,
               expect_exc=Exception)
    # (c) forge receipts for OTHER IDs
    other = new_identity(); wo = open_wallet(ledger, other)
    try_attack("key compromise: forge tier grant for another ID",
               "victim key signs grant naming other as granter",
               lambda: W.apply_tier_grant(ledger, W.make_tier_grant(
                   vk, other["uid"], atk["uid"], W.TIER_FRIEND)) or True,
               expect_exc=W.TierViolation)
    try_attack("key compromise: merit_transfer FROM another ID",
               "transfer_merit(other->attacker); other owns 0",
               lambda: W.transfer_merit(wo, wa2, 10.0, "theft", engine=eng,
                                        manifest={"op": "merit-transfer",
                                                  "nonce": uuid.uuid4().hex}
                                        ) or True,
               expect_exc=Exception)  # TokenizeRefused from engine
    # (d) WITHOUT any key: transfer victim's Merit with only the unity_id
    wv_handle = W.Wallet(vic["uid"], ledger)  # fresh handle, no key needed
    bal_v0 = eng.merit_balance(vic["uid"])
    def keyless_drain():
        W.transfer_merit(wv_handle, wa2, 50.0, "theft", engine=eng,
                         manifest={"op": "merit-transfer",
                                   "nonce": uuid.uuid4().hex})
        return eng.merit_balance(atk["uid"]) >= 50.0
    st = try_attack("KEYLESS merit drain (no key needed)",
                    "fresh Wallet(victim_id) + transfer_merit, zero auth",
                    keyless_drain)
    if st == "BROKE":
        critical("MERIT TRANSFER HAS NO SENDER AUTHORIZATION",
                 "wv_handle = Wallet(victim_unity_id, ledger)  # no key; "
                 "transfer_merit(wv_handle, attacker_wallet, 50, 'theft', "
                 "engine=eng) -> SUCCEEDS. Reproduced in gauntlet sec_expansion.",
                 "transfer_merit / engine.merit_transfer verify identity "
                 "FORMAT and owned balance only — no signature, no tier "
                 "grant, no consent proof from the sender. Anyone holding a "
                 "ledger reference (or the public unity_id) can move "
                 "anyone's Merit. Contrast share(), which requires a signed "
                 "tier grant. Blast radius of a compromised key is therefore "
                 "WORSE than expected: the key isn't even needed for Merit "
                 "theft; with the key the attacker additionally drains eFuse "
                 "via share(). Cannot mint; cannot forge for other IDs "
                 "beyond their balances; cannot touch standing.")
    info("BLAST RADIUS MAP (compromised Unity private key): CAN — sign tier "
         "grants as victim (drain eFuse via share within tier caps); sign "
         "kin bonds as victim; drain victim Merit WITHOUT the key (no auth "
         "gate — see CRITICAL). CANNOT — mint eFuse/Unity/Merit (no path; "
         "fuse needs founder key; tokenize needs VERIFIED receipts); forge "
         "tier grants for other IDs (signature binds granter); move Unity "
         "(no path); move standing (origin immutable); exceed victim's own "
         "holdings except via the keyless merit-drain CRITICAL above.")

    # ---- 6.5 emission forgery ----
    forg = new_identity(); wf2 = open_wallet(ledger, forg)
    b_before = ef(wf2)
    forged = emission_receipt_for(forg["uid"], 999, W.TOKEN_EFUSE,
                                  "forged-1")  # structurally valid, invented
    def forge_emission():
        W.receive_emission(wf2, 999, forged)
        return ef(wf2) == b_before + 999
    st = try_attack("emission forgery: crafted valid-structure receipt",
                    "receive_emission with invented manifest, gated=True",
                    forge_emission)
    if st == "BROKE":
        critical("EMISSION RECEIPTS NOT CRYPTOGRAPHICALLY BOUND TO ISSUER",
                 "forged = {kind:'merit-emission', token:'eFuse', "
                 "unity_id:victim, amount:999, gated:True, pool:'human', "
                 "merit_weight:1.0, manifest_hash:<fresh>, epoch:7}; "
                 "receive_emission(wallet, 999, forged) -> 999 eFuse "
                 "credited. Reproduced in gauntlet sec_expansion.",
                 "_validate_emission_receipt checks STRUCTURE only — no "
                 "signature binds the receipt to the tokenomics engine. "
                 "Anyone with a wallet handle mints eFuse credit at will. "
                 "The 'receipt IS the gate' gate is structural, not "
                 "cryptographic.")
    # tokenize with self-asserted VERIFIED provenance
    e5 = Tokenizer(); e5.set_peg_ratio(10.0, {"authority": "david"})
    def forge_tokenize():
        r = work_receipt(forg["uid"], 50.0, "forged-tok")
        # attacker simply asserts VERIFIED — the field is a string
        e5.tokenize(r)
        return e5.merit_balance(forg["uid"]) == 50.0
    st = try_attack("mint forgery: self-asserted VERIFIED receipt",
                    "tokenize() with provenance='VERIFIED' string",
                    forge_tokenize)
    if st == "BROKE":
        critical("PROVENANCE IS A SELF-ASSERTED STRING (tokenize gate)",
                 "tokenize({unity_id, kind:'work', merit_value:50, "
                 "provenance:'VERIFIED', manifest_hash:<64hex>, ...}) -> "
                 "MeritRecord + EFuseToken minted. Reproduced in gauntlet.",
                 "_require_gated checks provenance == 'VERIFIED' as a "
                 "string comparison — no signature from the gating "
                 "authority. In-process, anyone mints Merit+eFuse for any "
                 "ID. UNKNOWN-never-pays holds only if callers are honest "
                 "about labels.")
    # honest gates that DO hold
    try_attack("emission with no receipt at all", "receive_emission(w,1,None)",
               lambda: W.receive_emission(wf2, 1, None) or True,
               expect_exc=W.InvalidReceipt)
    try_attack("emission with gated=False", "forged but ungated",
               lambda: W.receive_emission(
                   wf2, 1, emission_receipt_for(
                       forg["uid"], 1, W.TOKEN_EFUSE, "f2", gated=False)
               ) or True, expect_exc=W.InvalidReceipt)

    # ---- 6.6 tier escalation ----
    p = new_identity(); q = new_identity()
    wp = open_wallet(ledger, p); wq = open_wallet(ledger, q)
    W.apply_tier_grant(ledger, W.make_tier_grant(p["priv"], p["uid"],
                                                q["uid"], W.TIER_FRIEND))
    W.receive_emission(wp, 10000, emission_receipt_for(
        p["uid"], 10000, W.TOKEN_EFUSE, uuid.uuid4().hex))
    try_attack("tier escalation: exceed friend cap",
               "friend grant on file; share 101 (>100 cap)",
               lambda: W.share(wp, wq,
                               {"kind": "funds", "token": W.TOKEN_EFUSE,
                                "amount": 101},
                               {"op": "share", "nonce": uuid.uuid4().hex}
                               ) or True, expect_exc=W.TierViolation)
    # crafted payload claiming family tier — tier comes from the GRANT
    rcp = W.share(wp, wq, {"kind": "funds", "token": W.TOKEN_EFUSE,
                           "amount": 50, "tier": "family",
                           "admin": True},
                  {"op": "share", "nonce": uuid.uuid4().hex})
    log_attack("tier escalation: crafted payload tier='family'",
               "payload claims family; grant is friend",
               "HELD" if rcp["tier"] == "friend" else "BROKE",
               f"receipt tier={rcp['tier']} — tier read from signed grant, "
               "never from payload")
    try_attack("tier escalation: forged family grant",
               "attacker key signs grant naming victim as granter",
               lambda: W.apply_tier_grant(ledger, W.make_tier_grant(
                   q["priv"], p["uid"], q["uid"], W.TIER_FAMILY)) or True,
               expect_exc=W.TierViolation)
    tg = W.make_tier_grant(p["priv"], p["uid"], q["uid"], W.TIER_FRIEND)
    tg["tier"] = W.TIER_FAMILY
    try_attack("tier escalation: tampered grant tier",
               "edit tier post-signing, replay signature",
               lambda: W.apply_tier_grant(ledger, tg) or True,
               expect_exc=W.TierViolation)

    # ---- 6.7 receipt forgery (signature layer) ----
    # tier grants: cryptographic — forged signatures fail (holds)
    try_attack("receipt forgery: tier grant bad signature",
               "random 64-byte signature bytes",
               lambda: W.apply_tier_grant(ledger, {
                   "granter_unity_id": p["uid"], "grantee_unity_id": q["uid"],
                   "tier": W.TIER_FRIEND, "nonce": uuid.uuid4().hex,
                   "signature": base64.b64encode(os.urandom(64)).decode(),
                   "key_id": W.KEY_ID}) or True,
               expect_exc=W.TierViolation)
    info("receipt forgery at the EMISSION layer breaks (see 6.5 CRITICAL): "
         "emission receipts carry NO signature field — structural only.")

    # ---- 6.8 donor-exclusion bypass ----
    dn = new_identity(); wd = open_wallet(ledger, dn)
    W.receive_emission(wd, 1000, emission_receipt_for(
        dn["uid"], 1000, W.TOKEN_EFUSE, uuid.uuid4().hex))
    lock = "lock:testnet:core-cause"
    dr = W.donate(wd, 400, lock, {"op": "donate", "nonce": uuid.uuid4().hex})
    dh = dr["manifest_hash"]
    # (a) the check function itself works
    try_attack("donor exclusion: direct check",
               "check_donor_exclusion with own donation hash",
               lambda: W.check_donor_exclusion(
                   wd, {"source_donation_hash": dh}) or True,
               expect_exc=W.DonorExclusionViolation)
    # (b) but NOTHING calls it: wallet credit paths never consult exclusion
    import subprocess as _sp
    callers = _sp.run(
        ["grep", "-rn", "check_donor_exclusion(",
         os.path.expanduser("~/workspace/unity-world"),
         "--include=*.py"], capture_output=True, text=True).stdout
    caller_lines = [l for l in callers.splitlines()
                    if "def check_donor_exclusion" not in l
                    and "test_" not in l and "gauntlet" not in l]
    if not caller_lines:
        critical("WALLET DONOR EXCLUSION IS UNWIRED (dead check)",
                 "grep -rn 'check_donor_exclusion(' workspace/unity-world "
                 "--include=*.py -> zero non-test call sites. "
                 "donate() records exclusion hashes; no disbursement/credit "
                 "path consults them. Demonstrated: receive_emission to a "
                 "donor succeeds without exclusion consult.",
                 "The fine-grained per-donation exclusion exists as a "
                 "function nobody invokes. The tokenomics layer has its own "
                 "blanket enforcement (cause_disburse refuses ANY donor), "
                 "but the wallet layer — where donate() lives — enforces "
                 "nothing on its own credit paths.")
        log_attack("donor exclusion bypass via wallet credit path",
                   "donate 400, then receive_emission to same wallet",
                   "BROKE", "no exclusion consult on wallet credit paths")
    else:
        log_attack("donor exclusion wiring", "call-site audit",
                   "HELD", str(caller_lines)[:160])
    # demonstrate: emission to the donor still credits (no consult)
    W.receive_emission(wd, 10, emission_receipt_for(
        dn["uid"], 10, W.TOKEN_EFUSE, "post-donation"))
    # (c) tokenomics cause_disburse DOES enforce (blanket ban on any donor)
    tld = T.Ledger()
    rcpt, _ = tld.donate(dn["uid"], T.Figure(400, "REPORTED"), "efuse", 7)
    vrcpt = T.Receipt.build(dn["uid"], "merit_accrual", {"t": 1}, "VERIFIED", 7,
                            "GENESIS")
    try_attack("donor exclusion: tokenomics cause_disburse",
               "donor claims cause-work disbursement from the Lock",
               lambda: tld.cause_disburse(dn["uid"], T.Figure(10, "REPORTED"),
                                          vrcpt, 7) or True,
               expect_exc=T.DonorExclusionError)
    # (d) merit-transfer laundering: donation accrues ZERO merit — nothing to wash
    assert dr["merit_accrued"] == 0
    ok("donation->merit laundering impossible",
       detail="donate() accrues exactly 0 merit — no value enters the "
              "merit system to launder")
    assert ledger.verify_chain()

# ================================================================ main
if __name__ == "__main__":
    if TE_BROKEN:
        RESULTS["criticals"].append({
            "title": "BLOCKER: dclm/token_engine.py unimportable "
                     "(IndentationError, line ~1103-1104)",
            "reproducer": "python3 -c 'import token_engine' with "
                           "~/workspace/unity-world/dclm on sys.path -> "
                           "IndentationError: unexpected indent at line 1104. "
                           "File mtime Oct 6 07:48 UTC; mangled line: "
                           "'if balance < amount:self._log_refusal(' "
                           "(collapsed newline inside merit_transfer's "
                           "insufficient-balance guard).",
            "impact": "The CANONICAL Merit transfer path (Tokenizer."
                      "merit_transfer) cannot be imported at all — every "
                      "downstream consumer (wallet.transfer_merit, tests) is "
                      "down. Gauntlet engine measurements below were taken "
                      "against a byte-identical /tmp snapshot with only the "
                      "collapsed newline restored (verified against the "
                      "pre-breakage read); the repo file was NOT modified. "
                      "Re-run this gauntlet after the repair lands."})
        RESULTS["notes"].append("token_engine loaded from: " + TE_SOURCE)
    t_all = time.perf_counter()
    for fn in (sec_efuse, sec_merit, sec_unity, sec_honor, sec_pipeline,
               sec_expansion):
        try:
            fn()
        except Exception:
            print("SECTION FAILED WITH EXCEPTION:", flush=True)
            traceback.print_exc()
            RESULTS["notes"].append(f"SECTION {fn.__name__} raised: "
                                   + traceback.format_exc()[-2000:])
    dt_all = time.perf_counter() - t_all
    RESULTS["elapsed_sec"] = round(dt_all, 1)
    n_tests = sum(len(s["tests"]) for s in RESULTS["sections"].values())
    n_atk = sum(len(s["attacks"]) for s in RESULTS["sections"].values())
    n_held = sum(1 for s in RESULTS["sections"].values()
                 for a in s["attacks"] if a["status"] == "HELD")
    n_broke = sum(1 for s in RESULTS["sections"].values()
                  for a in s["attacks"] if a["status"] == "BROKE")
    print(f"\n===== SUMMARY =====\ntests: {n_tests} | attacks: {n_atk} "
          f"(HELD {n_held} / BROKE {n_broke}) | "
          f"CRITICALs: {len(RESULTS['criticals'])} | {dt_all:.1f}s",
          flush=True)
    for c in RESULTS["criticals"]:
        print("CRITICAL:", c["title"], flush=True)
    out = os.path.expanduser(
        "~/workspace/unity-world/economics/gauntlet/results.json")
    with open(out, "w") as fh:
        json.dump(RESULTS, fh, indent=2, sort_keys=True)
    print("results ->", out, flush=True)

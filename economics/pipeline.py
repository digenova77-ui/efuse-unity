"""
PIPELINE — the end-to-end per-transaction orchestrator. TESTNET ONLY.

Fix Worker A4, COIN GAUNTLET closure loop (X1 — the missing integrated pass).

The conductor, not the orchestra. This module DRIVES the existing machinery
without reimplementing or redesigning any of it:

  pricing.per_decision_meter   — price the decision (the canon meter's flat
                                 COMPUTE rate; UNKNOWN never passes)
  tokenomics.Ledger.accrue_merit    — gated receipt -> merit
  tokenomics.Ledger.emission_close  — standing-gated (earned history,
                                      origin-based — never balances),
                                      peg-calibrated, authority-bounded,
                                      winter-throttled,
                                      reserve absorb/release (A2/A3)
  tokenomics.Ledger.disburse        — per-member eFuse, Unity-bound
  tokenomics.Ledger.transfer_merit  — Merit ownership transfer (A1 law),
                                      sender-authorized (S1b: the transfer
                                      input carries the sender's signed
                                      authorization; unsigned transfers
                                      are refused by the ledger)
  tokenomics.Ledger.donate          — donation -> Honor (never Merit)

One lawful pass, in order:
  price -> verify_receipt -> accrue_merit -> emission -> disburse
    -> merit_transfer -> donate -> seal (pipeline receipt)

Coordination with P1 (epoch_runner): P1 drives the per-epoch CYCLE
(receipts -> merit -> emission -> disbursement -> decay -> peg check ->
reserve -> winter -> close). The pipeline drives the per-transaction PASS
within it — one decision's work through the same modules, receipted as
one chain. Idempotency is per-pipeline-run here (the idempotency key);
P1's is per-epoch (closed-epoch record). The two never overlap: the
pipeline refuses to re-accrue a gated receipt that is already applied,
so a receipt P1 already accrued cannot be double-counted here.

Fail-closed, two phases (the epoch runner's precedent):
  Phase 1 — GATES. Every step's gates are checked BEFORE any mutation.
    Any gate failure aborts the pipeline: nothing is applied, and the
    abort is receipted (status "aborted") carrying the failing step and
    the reason.
  Phase 2 — APPLY. Steps execute in order; each mutation is receipted by
    its owning module. An apply-phase failure aborts with the step and
    the cause; the steps already applied stay receipted (each is lawful
    on its own), the pipeline is marked aborted, and the key is burned —
    the same key never re-executes.

Idempotency: the pipeline takes an idempotency key. The first run with a
key decides; every later run with the same key returns the recorded
pipeline receipt WITHOUT re-executing — no double-accrual, no
double-disbursement, no double-transfer. The registry lives on the
PipelineRunner (in-memory, optionally persisted to a JSONL file via
state_dir).

Provenance: the pipeline receipt carries the weakest ENGAGED input label —
any MODELED -> MODELED; all decided -> DERIVED (the emission calculator's
own weakest-input rule). UNKNOWN anywhere in the engaged inputs ->
the pipeline refuses at "provenance_gate": UNKNOWN never pays.
(An input that is not engaged — winter=None, holdback_fraction=None,
reserve_release=None, empty transfer/donation lists — contributes no
label; winter=None is the lawful SUMMER default, not an UNKNOWN input.)

One-owner rule (economic_state.py): receipt chains have exactly one owner.
The pipeline never re-derives tokenomics receipts — each called module
owns its receipts. The pipeline receipt CHAINS them (ordered step receipt
ids + manifest hashes sealed under one pipeline hash); it does not
duplicate them.

The pipeline receipt is a pipeline-level artifact, NOT a tokenomics
Ledger receipt: tokenomics.RECEIPT_KINDS has no "pipeline" kind and
Receipt.build refuses unknown kinds. Writing the seal as a ledger receipt
would require touching tokenomics.py, which this worker must not do —
see API GAPS below. Step receipts ARE all in the ledger chain;
verify_pipeline_run checks every chained step receipt against the ledger
and reseals the pipeline hash.

API GAPS (reported, not redesigned):
  G1. tokenomics.RECEIPT_KINDS lacks a "pipeline" kind. If a future worker
      adds it, the seal can move onto the ledger chain via Receipt.build /
      Ledger.apply_receipt, and the runner's registry can additionally
      recover from the ledger's own receipts (the epoch runner's
      precedent for closed epochs). Until then the registry is the
      runner's own (memory + optional JSONL).
  G2. Wallet-surface claim (wallet.receive_emission) is downstream of the
      pipeline by design: the pipeline disburses to the Unity ID on the
      tokenomics ledger; the wallet claim surface (gauntlet X6) is another
      worker's lane. The pipeline does not touch wallet.py.
  G3. Bounty escrow (mesh_escrow F2/F3) is not a pipeline step: bounties
      are commissioned and fulfilled through MeshClearing directly. A
      future worker may add an escrow step here; the step table is built
      to extend.
"""

import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pricing as _pricing
import tokenomics as _T
from tokenomics import (
    Figure,
    HeldParameter,
    PROVENANCE_LABELS,
    TokenomicsError,
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PipelineError(TokenomicsError):
    """Base for pipeline refusals. Gate failures do NOT raise — they abort
    with a receipted abort (status "aborted"). This is for caller bugs."""


class PipelineInputError(PipelineError):
    """The inputs object itself is malformed (not a gate failure — the
    caller built it wrong). Raised, never receipted."""


# ---------------------------------------------------------------------------
# Identities & constants
# ---------------------------------------------------------------------------

# System-level identity for the pipeline seal — the same precedent as the
# pool reserve identity ("pool:{pool}:...") and the epoch runner's
# RUNNER_IDENTITY: a system receipt binds a system identity, never a
# member, never blank. (The seal is not currently a ledger receipt — G1 —
# but the identity is reserved for when it can be.)
PIPELINE_IDENTITY = "system:pipeline"

PIPELINE_MODULE = "economics/pipeline.py"
PIPELINE_KIND = "pipeline"
REGISTRY_FILENAME = "pipeline_registry.jsonl"

# Provenance strength: the weakest ENGAGED input label wins.
# UNKNOWN is refused outright (never collected as a label).
_STRONG = ("VERIFIED", "REPORTED", "DERIVED")

STEP_ORDER = (
    "price",
    "verify_receipt",
    "accrue_merit",
    "emission",
    "disburse",
    "merit_transfer",
    "donate",
    "seal",
)


# ---------------------------------------------------------------------------
# Inputs — everything arrives as parameters; nothing is invented
# ---------------------------------------------------------------------------

@dataclass
class WorkInput:
    """One member's gated work for this pipeline run."""
    unity_id: str
    receipt: object          # tokenomics Receipt: VERIFIED, unity-bound, epoch-bound
    merit_weight: Figure     # explicit weight with its provenance (bands HELD)


@dataclass
class MeritTransferInput:
    """One ownership movement: from_unity_id -> to_unity_id.

    auth is the SENDER's signed transfer authorization (the
    wallet.make_merit_transfer_auth shape: canonical body + signature +
    pubkey_b64 + nonce). The ledger verifies it against the sender's
    registered transfer key and refuses unsigned transfers
    (MeritTransferAuthError) — the public Unity ID alone authorizes
    nothing. The sender's key must be registered on the run's ledger
    (Ledger.register_transfer_key) before the transfer step; each auth
    nonce may be used once."""
    from_unity_id: str
    to_unity_id: str
    amount: Figure
    reason: str
    auth: dict | None = None


@dataclass
class DonationInput:
    unity_id: str
    amount: Figure
    kind: str                # "efuse" | "fiat"


@dataclass
class PipelineInputs:
    idempotency_key: str
    decision: object          # {"decision_id": str} or a bare decision_id string
    work: list = field(default_factory=list)        # [WorkInput]
    pool: str = "human"                             # "human" | "machine"
    epoch: int = 1
    peg_ratio: Figure = None                        # decided Figure (David's digit)
    winter: object = None                           # None | winter.WinterSignal | winter.WinterState
    holdback_fraction: Figure = None                # None (not engaged) | Figure in [0, 1)
    reserve_release: Figure = None                  # None | Figure >= 0
    transfers: list = field(default_factory=list)   # [MeritTransferInput]
    donations: list = field(default_factory=list)   # [DonationInput]


def _coerce_figure(x, name):
    """Figures arrive labeled or not at all. A bare number is UNSIGNED ->
    UNKNOWN (the tokenomics convention) — which the provenance gate then
    refuses. HeldParameter passes through so the step gate can refuse it
    honestly."""
    if isinstance(x, HeldParameter):
        return x
    if isinstance(x, Figure):
        return x
    if isinstance(x, dict):
        return Figure(
            x["value"],
            x.get("provenance", "UNKNOWN"),
            x.get("note", f"{name} (coerced from dict)"),
        )
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return Figure(float(x), "UNKNOWN",
                      f"unsigned input for {name} treated as UNKNOWN — never pays")
    raise PipelineInputError(
        f"{name} must be a Figure, HeldParameter, dict, or number, "
        f"got {type(x).__name__!r}")


def _coerce_work(x):
    if isinstance(x, WorkInput):
        return x
    if isinstance(x, dict):
        return WorkInput(unity_id=x["unity_id"], receipt=x["receipt"],
                         merit_weight=_coerce_figure(x["merit_weight"],
                                                    "merit_weight"))
    raise PipelineInputError(
        f"work entries must be WorkInput or dict, got {type(x).__name__!r}")


def _coerce_transfer(x):
    if isinstance(x, MeritTransferInput):
        x.amount = _coerce_figure(x.amount, "transfer amount")
        if x.auth is not None and not isinstance(x.auth, dict):
            raise PipelineInputError(
                "transfer auth must be a dict (the sender's signed "
                f"transfer authorization), got {type(x.auth).__name__!r}")
        return x
    if isinstance(x, dict):
        auth = x.get("auth")
        if auth is not None and not isinstance(auth, dict):
            raise PipelineInputError(
                "transfer auth must be a dict (the sender's signed "
                f"transfer authorization), got {type(auth).__name__!r}")
        return MeritTransferInput(
            from_unity_id=x["from_unity_id"], to_unity_id=x["to_unity_id"],
            amount=_coerce_figure(x["amount"], "transfer amount"),
            reason=x["reason"], auth=auth)
    raise PipelineInputError(
        f"transfers must be MeritTransferInput or dict, got {type(x).__name__!r}")


def _coerce_donation(x):
    if isinstance(x, DonationInput):
        x.amount = _coerce_figure(x.amount, "donation amount")
        return x
    if isinstance(x, dict):
        return DonationInput(
            unity_id=x["unity_id"],
            amount=_coerce_figure(x["amount"], "donation amount"),
            kind=x["kind"])
    raise PipelineInputError(
        f"donations must be DonationInput or dict, got {type(x).__name__!r}")


def _coerce_inputs(inputs):
    if isinstance(inputs, PipelineInputs):
        work = [_coerce_work(w) for w in inputs.work]
        transfers = [_coerce_transfer(t) for t in inputs.transfers]
        donations = [_coerce_donation(d) for d in inputs.donations]
        return PipelineInputs(
            idempotency_key=inputs.idempotency_key,
            decision=inputs.decision, work=work, pool=inputs.pool,
            epoch=inputs.epoch, peg_ratio=_coerce_figure(inputs.peg_ratio, "peg_ratio")
            if inputs.peg_ratio is not None else None,
            winter=inputs.winter,
            holdback_fraction=_coerce_figure(inputs.holdback_fraction, "holdback_fraction")
            if inputs.holdback_fraction is not None else None,
            reserve_release=_coerce_figure(inputs.reserve_release, "reserve_release")
            if inputs.reserve_release is not None else None,
            transfers=transfers, donations=donations)
    if isinstance(inputs, dict):
        try:
            return PipelineInputs(
                idempotency_key=inputs["idempotency_key"],
                decision=inputs["decision"],
                work=[_coerce_work(w) for w in inputs.get("work", [])],
                pool=inputs.get("pool", "human"),
                epoch=inputs.get("epoch", 1),
                peg_ratio=_coerce_figure(inputs["peg_ratio"], "peg_ratio")
                if inputs.get("peg_ratio") is not None else None,
                winter=inputs.get("winter"),
                holdback_fraction=_coerce_figure(inputs["holdback_fraction"],
                                                "holdback_fraction")
                if inputs.get("holdback_fraction") is not None else None,
                reserve_release=_coerce_figure(inputs["reserve_release"],
                                              "reserve_release")
                if inputs.get("reserve_release") is not None else None,
                transfers=[_coerce_transfer(t) for t in inputs.get("transfers", [])],
                donations=[_coerce_donation(d) for d in inputs.get("donations", [])],
            )
        except KeyError as e:
            raise PipelineInputError(f"pipeline inputs missing required field: {e}")
    raise PipelineInputError(
        f"pipeline inputs must be PipelineInputs or dict, "
        f"got {type(inputs).__name__!r}")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _pipeline_hash(body):
    return hashlib.sha256(_canonical(body)).hexdigest()


def _winter_types():
    """The lawful winter types (dclm/winter.py). None if the module cannot
    be imported — then the pre-gate cannot type-check and emission_close
    refuses a bad winter in the apply phase (receipted abort)."""
    try:
        dclm_dir = os.path.normpath(os.path.join(_HERE, "..", "dclm"))
        if dclm_dir not in sys.path:
            sys.path.insert(0, dclm_dir)
        import winter as _w
        return (_w.WinterSignal, _w.WinterState)
    except Exception:
        return None


def _winter_provenances(winter):
    """Provenance labels actually engaged by the winter input. None or an
    unreadable signal -> the lawful SUMMER default (UNKNOWN never PASS) —
    not engaged, contributes no label. A readable signal contributes its
    per-input labels; a WinterState contributes its own."""
    if winter is None:
        return []
    types = _winter_types()
    if types is None:
        return []
    WinterSignal, WinterState = types
    if isinstance(winter, WinterState):
        return [getattr(winter, "provenance", "UNKNOWN")]
    if isinstance(winter, WinterSignal):
        if not winter.readable:
            return []  # unreadable -> SUMMER default; not an engaged input
        # Only the ENGAGED readings contribute labels: an undeclared crisis
        # is not an input (its UNKNOWN provenance is the lawful default,
        # not an UNKNOWN payment).
        out = []
        if winter.peg_deviation is not None:
            out.append(winter.peg_provenance)
        if winter.activity_delta is not None:
            out.append(winter.activity_provenance)
        if winter.crisis_declared and winter.crisis_verified:
            out.append(winter.crisis_provenance)
        return out
    return []


class _Abort(Exception):
    """Internal: a gate/apply failure carrying the failing step + reason.
    The runner converts it into a receipted abort — never raised to the
    caller."""

    def __init__(self, step, reason):
        self.step = step
        self.reason = reason
        super().__init__(f"pipeline ABORTED at step {step!r}: {reason}")


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class PipelineRunner:
    """Drives one integrated lawful pass per run_pipeline call.

    Holds the idempotency registry: idempotency_key -> pipeline receipt
    (completed or aborted). Re-running with a seen key returns the recorded
    receipt without executing anything. The registry is in-memory, and
    optionally persisted to state_dir/pipeline_registry.jsonl.
    """

    def __init__(self, ledger, state_dir=None):
        if not isinstance(ledger, _T.Ledger):
            raise PipelineInputError(
                "PipelineRunner needs a tokenomics.Ledger — the pipeline "
                "drives the ledger, it does not invent one")
        self.ledger = ledger
        self._registry = {}
        self._state_dir = state_dir
        self._registry_path = (os.path.join(state_dir, REGISTRY_FILENAME)
                               if state_dir else None)
        if self._registry_path and os.path.exists(self._registry_path):
            self._load_registry()

    # -- registry ------------------------------------------------------
    def _load_registry(self):
        try:
            with open(self._registry_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    key = rec.get("idempotency_key")
                    if key:
                        self._registry.setdefault(key, rec)
        except (OSError, ValueError):
            # A corrupt registry line never blocks the pipeline — the
            # in-memory registry is authoritative for this process.
            pass

    def _record(self, key, receipt):
        self._registry[key] = receipt
        if self._registry_path:
            os.makedirs(self._state_dir, exist_ok=True)
            with open(self._registry_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(receipt, sort_keys=True) + "\n")

    def get_receipt(self, idempotency_key):
        """The recorded pipeline receipt for a key, or None."""
        return self._registry.get(idempotency_key)

    # -- main entry ----------------------------------------------------
    def run_pipeline(self, inputs):
        """Execute ONE integrated lawful pass. Returns the pipeline receipt
        (dict): status "completed" or "aborted". A seen idempotency key
        returns the recorded receipt without executing.

        Raises PipelineInputError only for malformed caller input.
        Gate/apply failures abort with a receipted abort — never raise.
        """
        inp = _coerce_inputs(inputs)
        key = inp.idempotency_key
        if not isinstance(key, str) or not key.strip():
            raise PipelineInputError(
                "idempotency_key is required — a non-empty string; the "
                "pipeline never runs without one")
        key = key.strip()

        # ---- gate -1: idempotency — before anything else ----
        seen = self._registry.get(key)
        if seen is not None:
            return seen  # no double-execution, ever

        try:
            plan = self._gate_all(inp)      # Phase 1: gates, no mutation
            receipt = self._apply_all(inp, plan)  # Phase 2: apply in order
        except _Abort as a:
            receipt = self._seal_abort(inp, a.step, a.reason)
        self._record(key, receipt)
        return receipt

    # ------------------------------------------------------------------
    # Phase 1 — gates (no mutation)
    # ------------------------------------------------------------------
    def _gate_all(self, inp):
        """Check every step's gates before anything is applied. Returns the
        plan (cached pure computations). Raises _Abort on the first failing
        step, in step order."""
        plan = {"price_record": None, "provenance": "DERIVED",
                "accrued": {}, "step_notes": {}}

        # ---- gate 0: provenance — UNKNOWN anywhere in the ENGAGED inputs
        # refuses the whole pipeline (UNKNOWN never pays). ----
        provs = self._collect_provenances(inp)
        for label, where in provs:
            if label not in PROVENANCE_LABELS:
                raise _Abort("provenance_gate",
                             f"{where} carries invalid provenance {label!r} "
                             f"— downgraded to UNKNOWN; refusing")
            if label == "UNKNOWN":
                raise _Abort("provenance_gate",
                             f"{where} is UNKNOWN — UNKNOWN never pays; "
                             f"the pipeline refuses")
        plan["provenance"] = ("MODELED" if any(l == "MODELED" for l, _ in provs)
                              else "DERIVED")

        # ---- step: price — the pricing engine prices, fail-closed ----
        decision = inp.decision
        try:
            records = _pricing.per_decision_meter([decision])
        except KeyError as e:
            raise _Abort("price",
                         f"the pricing engine cannot price this decision — "
                         f"it never invents a price ({e})")
        except (TypeError, ValueError) as e:
            raise _Abort("price", f"unpriceable decision input: {e}")
        record = records[0]
        if not record.get("pass"):
            raise _Abort("price",
                         f"decision {record.get('decision_id')!r} did not pass "
                         f"the meter (UNKNOWN never passes, never pays)")
        plan["price_record"] = record

        # ---- step: verify_receipt — the gated receipt, structurally ----
        if not inp.work:
            raise _Abort("verify_receipt",
                         "no work inputs — the pipeline accrues merit from "
                         "gated receipts; no receipt, no pipeline")
        applied_ids = {r.receipt_id for r in self.ledger.receipts
                       if hasattr(r, "receipt_id")}
        for w in inp.work:
            uid = w.unity_id
            if not isinstance(uid, str) or not uid.strip():
                raise _Abort("verify_receipt",
                             "work binds a Unity ID — no anonymous flows")
            r = w.receipt
            for attr in ("provenance", "unity_id", "epoch", "receipt_id",
                         "manifest_hash"):
                if not hasattr(r, attr):
                    raise _Abort("verify_receipt",
                                 f"gated receipt lacks {attr!r} — not a "
                                 f"receipt the pipeline can verify")
            if r.provenance != "VERIFIED":
                raise _Abort("verify_receipt",
                             f"receipt {r.receipt_id[:8]}… is "
                             f"{r.provenance}, not VERIFIED — gated receipts "
                             f"only (UNKNOWN never pays)")
            if r.unity_id != uid.strip():
                raise _Abort("verify_receipt",
                             f"receipt {r.receipt_id[:8]}… is bound to "
                             f"{r.unity_id!r}, not the claimant {uid!r}")
            if r.epoch != inp.epoch:
                raise _Abort("verify_receipt",
                             f"receipt {r.receipt_id[:8]}… is epoch-bound to "
                             f"{r.epoch!r}, not this run's epoch {inp.epoch!r}")
            if r.receipt_id in applied_ids:
                raise _Abort("verify_receipt",
                             f"receipt {r.receipt_id[:8]}… is already applied "
                             f"— refusing double-accrual (the epoch cycle "
                             f"may already own this receipt)")

        # ---- step: accrue_merit — explicit, decided, positive weight ----
        for w in inp.work:
            wt = w.merit_weight
            if isinstance(wt, HeldParameter):
                raise _Abort("accrue_merit",
                             "merit weight bands are HELD_FOR_DAVID — "
                             "refusing an undecided weight")
            if wt.provenance in ("HELD", "UNKNOWN"):
                # (UNKNOWN is already refused by the provenance gate; this
                # is the HELD branch and defense in depth.)
                raise _Abort("accrue_merit",
                             f"merit weight is {wt.provenance} — refusing")
            if wt.value <= 0:
                raise _Abort("accrue_merit", "merit weight must be positive")
            plan["accrued"][w.unity_id.strip()] = \
                plan["accrued"].get(w.unity_id.strip(), 0.0) + wt.value

        # ---- step: emission — pool, peg, reserve, winter ----
        if inp.pool not in ("human", "machine"):
            raise _Abort("emission",
                         f"unknown pool {inp.pool!r} — pools are "
                         f"'human'/'machine' (DECIDED 50/50)")
        if not isinstance(inp.epoch, int) or isinstance(inp.epoch, bool) \
                or inp.epoch < 1:
            raise _Abort("emission",
                         f"epoch must be a positive int, got {inp.epoch!r}")
        peg = inp.peg_ratio
        if peg is None or isinstance(peg, HeldParameter):
            raise _Abort("emission",
                         "peg_ratio E is HELD/UNSET — E is David's digit; "
                         "nothing emits without it")
        if peg.provenance in ("HELD", "UNKNOWN"):
            raise _Abort("emission",
                         f"peg_ratio E is {peg.provenance} — E is David's "
                         f"digit; nothing emits without it")
        if peg.value <= 0:
            raise _Abort("emission", "peg_ratio must be positive")
        hb = inp.holdback_fraction
        if hb is not None:
            if isinstance(hb, HeldParameter):
                raise _Abort("emission",
                             "reserve_holdback_fraction is HELD_FOR_DAVID — "
                             "refusing to invent it")
            if hb.provenance in ("HELD", "UNKNOWN"):
                raise _Abort("emission",
                             "reserve_holdback_fraction is unsigned/unknown — "
                             "the Reserve never runs on an undecided digit")
            if not (0.0 <= hb.value < 1.0):
                raise _Abort("emission",
                             "reserve_holdback_fraction must be in [0, 1)")
        rel = inp.reserve_release
        if rel is not None:
            if isinstance(rel, HeldParameter):
                raise _Abort("emission",
                             "reserve_release amount is HELD/unsigned — "
                             "refusing an undecided release")
            if rel.provenance in ("HELD", "UNKNOWN"):
                raise _Abort("emission",
                             "reserve_release amount is UNKNOWN/unsigned — "
                             "UNKNOWN never pays, never releases")
            if rel.value < 0:
                raise _Abort("emission", "reserve_release cannot be negative")
        types = _winter_types()
        if types is not None and inp.winter is not None and \
                not isinstance(inp.winter, types):
            raise _Abort("emission",
                         "winter must be None or a dclm WinterSignal / "
                         "WinterState — no second trigger is invented here")

        # ---- step: merit_transfer — decided amount, real reason, covered --
        for t in inp.transfers:
            if not isinstance(t.from_unity_id, str) or not t.from_unity_id.strip() \
                    or not isinstance(t.to_unity_id, str) or not t.to_unity_id.strip():
                raise _Abort("merit_transfer",
                             "merit transfer requires two real Unity IDs — "
                             "no anonymous flows")
            if t.from_unity_id.strip() == t.to_unity_id.strip():
                raise _Abort("merit_transfer",
                             "self-transfer refused — a no-op disguised as "
                             "a transfer")
            a = t.amount
            if isinstance(a, HeldParameter) or a.provenance == "UNKNOWN":
                raise _Abort("merit_transfer",
                             "merit transfer amount is UNKNOWN/unsigned — "
                             "transferred value must be a real measured figure")
            if a.value <= 0:
                raise _Abort("merit_transfer",
                             "merit transfer amount must be positive")
            if not isinstance(t.reason, str) or not t.reason.strip():
                raise _Abort("merit_transfer",
                             "merit transfer needs a non-empty reason "
                             "(sale, gift, …) — every transfer is receipted "
                             "with its why")
            # S1b: an unsigned transfer never reaches the ledger — abort
            # here, in the plan gate, so the run refuses cleanly instead
            # of failing mid-apply. The ledger still verifies the full
            # cryptography (key binding, signature, nonce freshness) at
            # apply time.
            if not isinstance(t.auth, dict) or not t.auth.get("signature") \
                    or not t.auth.get("nonce") or not t.auth.get("pubkey_b64"):
                raise _Abort("merit_transfer",
                             "merit transfer needs the sender's signed "
                             "transfer authorization (auth) — unsigned "
                             "transfers are refused; the public Unity ID "
                             "alone authorizes nothing")
            sender = t.from_unity_id.strip()
            owned = self.ledger.merit_balances.get(sender, 0.0) \
                + plan["accrued"].get(sender, 0.0)
            if a.value > owned + 1e-9:
                raise _Abort("merit_transfer",
                             f"{sender!r} owns {owned} merit (incl. this "
                             f"run's accrual) — cannot transfer {a.value}; "
                             f"only owned value moves")

        # ---- step: donate — kind, decided positive amount ----
        for d in inp.donations:
            if not isinstance(d.unity_id, str) or not d.unity_id.strip():
                raise _Abort("donate",
                             "donation binds a Unity ID — no anonymous gifts")
            if d.kind not in _T.DONATION_KINDS:
                raise _Abort("donate",
                             f"donation kind must be one of "
                             f"{_T.DONATION_KINDS}, got {d.kind!r}")
            a = d.amount
            if isinstance(a, HeldParameter) or a.provenance == "UNKNOWN":
                raise _Abort("donate",
                             "donation amount is UNKNOWN/unsigned — refusing")
            if a.value <= 0:
                raise _Abort("donate",
                             "donation amount must be positive")

        return plan

    def _collect_provenances(self, inp):
        """(label, where) for every ENGAGED input. Unengaged inputs
        (winter=None, holdback=None, release=None, empty lists) contribute
        nothing — the lawful defaults are not UNKNOWN inputs."""
        out = []
        for w in inp.work:
            r = w.receipt
            out.append((getattr(r, "provenance", "UNKNOWN"),
                        f"work receipt {getattr(r, 'receipt_id', '?')[:8]}…"))
            if not isinstance(w.merit_weight, HeldParameter):
                out.append((w.merit_weight.provenance,
                            f"merit weight for {w.unity_id}"))
        if inp.peg_ratio is not None and \
                not isinstance(inp.peg_ratio, HeldParameter):
            out.append((inp.peg_ratio.provenance, "peg_ratio E"))
        if inp.holdback_fraction is not None and \
                not isinstance(inp.holdback_fraction, HeldParameter):
            out.append((inp.holdback_fraction.provenance,
                        "reserve holdback_fraction"))
        if inp.reserve_release is not None and \
                not isinstance(inp.reserve_release, HeldParameter):
            out.append((inp.reserve_release.provenance, "reserve_release"))
        for i, p in enumerate(_winter_provenances(inp.winter)):
            out.append((p, f"winter signal input #{i}"))
        for t in inp.transfers:
            if not isinstance(t.amount, HeldParameter):
                out.append((t.amount.provenance,
                            f"merit transfer {t.from_unity_id} -> "
                            f"{t.to_unity_id}"))
        for d in inp.donations:
            if not isinstance(d.amount, HeldParameter):
                out.append((d.amount.provenance,
                            f"donation by {d.unity_id}"))
        return out

    # ------------------------------------------------------------------
    # Phase 2 — apply, in step order (each mutation receipted by its owner)
    # ------------------------------------------------------------------
    def _new_since(self, before):
        """Receipts the ledger gained since index `before`."""
        return self.ledger.receipts[before:]

    @staticmethod
    def _step_receipt_refs(receipts):
        return [{"receipt_id": r.receipt_id, "kind": r.kind,
                 "manifest_hash": r.manifest_hash} for r in receipts]

    def _apply_all(self, inp, plan):
        steps = []
        prov = plan["provenance"]

        def run_step(name, fn):
            before = len(self.ledger.receipts)
            try:
                detail = fn() or {}
            except _Abort:
                raise
            except Exception as e:
                raise _Abort(name, f"{type(e).__name__}: {e}")
            new = self._new_since(before)
            entry = {"step": name, "ok": True,
                     "receipt_ids": [r.receipt_id for r in new],
                     "receipts": self._step_receipt_refs(new)}
            entry.update(detail)
            steps.append(entry)
            return entry

        # ---- price: the engine prices (pure — no ledger mutation) ----
        def do_price():
            rec = plan["price_record"]
            return {"decision_id": rec["decision_id"],
                    "price": {"amount": rec["billable_amount"],
                              "currency": rec.get("currency"),
                              "price_provenance": rec.get("price_provenance"),
                              "record_provenance": rec.get("provenance")},
                    "note": "canon meter flat COMPUTE rate; the price is "
                            "metered information on this receipt — the "
                            "wallet-side debit is the wallet's own step "
                            "(G2), not the pipeline's"}

        run_step("price", do_price)

        # ---- verify_receipt: declarative — the gates already ran ----
        def do_verify():
            return {"verified": [
                {"unity_id": w.unity_id.strip(),
                 "receipt_id": w.receipt.receipt_id,
                 "receipt_provenance": w.receipt.provenance}
                for w in inp.work],
                "note": "gated receipts: VERIFIED, unity-bound, epoch-bound, "
                        "not previously applied"}

        run_step("verify_receipt", do_verify)

        # ---- accrue_merit: gated receipt -> merit (module owns receipt) --
        def do_accrue():
            credited = {}
            for w in inp.work:
                uid = w.unity_id.strip()
                credit = self.ledger.accrue_merit(uid, w.receipt,
                                                  w.merit_weight)
                credited[uid] = credited.get(uid, 0.0) + credit.amount.value
            return {"merit_credited": credited,
                    "note": "the applied gated receipt IS the step receipt; "
                            "the MeritCredit carries the weight's provenance"}

        run_step("accrue_merit", do_accrue)

        # ---- emission: winter throttle + reserve absorb/release inside ----
        emission_out = {}

        def do_emission():
            # The gate's weight is EARNED STANDING (origin-based), never a
            # balance: the accruals above are already in the ledger's
            # merit_history, so each entry below restates that identity's
            # standing exactly — the standing cross-check passes, and the
            # gate derives every weight from standing. Bought Merit has
            # zero standing and buys zero emission weight. The weight's
            # own modeling rides on the pipeline provenance and the
            # MeritCredit, not the gate.
            merit_map = {
                uid: Figure(self.ledger.standing(uid).value, "DERIVED",
                            f"pipeline run {inp.idempotency_key}: earned "
                            "standing restatement — cross-checked against "
                            "standing, never read for weights")
                for uid in plan["accrued"]
            }
            out = self.ledger.emission_close(
                inp.pool, merit_map, inp.peg_ratio, inp.epoch,
                winter=inp.winter,
                holdback_fraction=inp.holdback_fraction,
                reserve_release=inp.reserve_release)
            emission_out["out"] = out
            return {
                "emission_canonical_sha256": out.canonical_sha256,
                "total": {"value": out.total.value,
                          "provenance": out.total.provenance},
                "per_member": {u: {"value": f.value,
                                   "provenance": f.provenance}
                               for u, f in out.per_member.items()},
                "excluded": dict(out.excluded),
                "authority_cap_applied": out.authority_cap_applied,
                "reserve_held": {"value": out.reserve_held.value,
                                 "provenance": out.reserve_held.provenance},
                "reserve_released": {"value": out.reserve_released.value,
                                     "provenance": out.reserve_released.provenance},
                "winter": {"gradient": out.winter_gradient,
                           "label": out.winter_label,
                           "multiplier": out.winter_multiplier,
                           "reasons": list(out.winter_reasons),
                           "provenance": out.winter_provenance},
                "emission_provenance": out.provenance,
                "note": out.note,
            }

        run_step("emission", do_emission)
        out = emission_out["out"]

        # ---- disburse: per-member eFuse, Unity-bound, authority-bounded --
        def do_disburse():
            disbursed = {}
            for uid, fig in out.per_member.items():
                if fig.value > 0:
                    self.ledger.disburse(
                        inp.pool, uid,
                        Figure(fig.value, fig.provenance,
                               f"pipeline run {inp.idempotency_key}: "
                               f"disbursing computed emission"),
                        inp.epoch)
                    disbursed[uid] = fig.value
            return {"disbursed": disbursed,
                    "disbursed_total": sum(disbursed.values()),
                    "note": "disbursement draws on the pool's remaining "
                            "authority — bounded by construction"}

        run_step("disburse", do_disburse)

        # ---- merit_transfer: ownership moves, standing never does ----
        def do_transfers():
            moved = []
            for t in inp.transfers:
                r = self.ledger.transfer_merit(
                    t.from_unity_id.strip(), t.to_unity_id.strip(),
                    t.amount, t.reason.strip(), inp.epoch, auth=t.auth)
                moved.append({"from": t.from_unity_id.strip(),
                              "to": t.to_unity_id.strip(),
                              "amount": t.amount.value,
                              "reason": t.reason.strip(),
                              "receipt_id": r.receipt_id})
            return {"transfers": moved,
                    "note": "OWNERSHIP ONLY — origin/earned-history never "
                            "moves with the token (module-enforced)"}

        run_step("merit_transfer", do_transfers)

        # ---- donate: Honor out, never Merit, never emission ----
        def do_donations():
            given = []
            for d in inp.donations:
                receipt, honor = self.ledger.donate(
                    d.unity_id.strip(), d.amount, d.kind, inp.epoch)
                given.append({"donor": d.unity_id.strip(),
                              "amount": d.amount.value,
                              "kind": d.kind,
                              "receipt_id": receipt.receipt_id,
                              "honor_receipt_id": honor.receipt_id})
            return {"donations": given,
                    "note": "donations accrue Honor, never Merit; no eFuse "
                            "is emitted and none is promised"}

        run_step("donate", do_donations)

        return self._seal_completed(inp, plan, steps, out)

    # ------------------------------------------------------------------
    # Sealing
    # ------------------------------------------------------------------
    def _seal_completed(self, inp, plan, steps, emission_out):
        disburse_step = next(s for s in steps if s["step"] == "disburse")
        transfer_step = next(s for s in steps if s["step"] == "merit_transfer")
        donate_step = next(s for s in steps if s["step"] == "donate")
        emission_step = next(s for s in steps if s["step"] == "emission")
        price_step = next(s for s in steps if s["step"] == "price")
        accrue_step = next(s for s in steps if s["step"] == "accrue_merit")

        step_manifests = [ref["manifest_hash"]
                          for s in steps for ref in s["receipts"]]
        body = {
            "kind": PIPELINE_KIND,
            "module": PIPELINE_MODULE,
            "pipeline_identity": PIPELINE_IDENTITY,
            "idempotency_key": inp.idempotency_key,
            "status": "completed",
            "epoch": inp.epoch,
            "pool": inp.pool,
            "provenance": plan["provenance"],
            "provenance_note": (
                "pipeline provenance follows the weakest ENGAGED input: any "
                "MODELED -> MODELED; all decided -> DERIVED. UNKNOWN anywhere "
                "refuses the pipeline (UNKNOWN never pays)."),
            "testnet": True,
            "ts": _now_iso(),
            "decision": {"decision_id": price_step["decision_id"],
                         **price_step["price"]},
            "steps": steps,
            "totals": {
                "merit_credited": accrue_step["merit_credited"],
                "emission_total": emission_step["total"],
                "disbursed_total": disburse_step["disbursed_total"],
                "disbursed": disburse_step["disbursed"],
                "reserve_held": emission_step["reserve_held"],
                "reserve_released": emission_step["reserve_released"],
                "transfers": transfer_step["transfers"],
                "donations": donate_step["donations"],
            },
            "winter": emission_step["winter"],
            "chain": {
                "step_manifest_hashes": step_manifests,
                "steps_chained": len(step_manifests),
                "note": "every step receipt lives in the tokenomics ledger "
                        "chain (the modules own their receipts); this seal "
                        "chains their manifest hashes under one pipeline hash",
            },
            "state_digest": self.ledger.state_digest(),
        }
        return {**body,
                "pipeline_id": uuid.uuid4().hex,
                "pipeline_hash": _pipeline_hash(body)}

    def _seal_abort(self, inp, failing_step, reason):
        """The receipted abort: which step failed and why. No economic
        mutation is implied — a pre-gate abort applied nothing; an
        apply-phase abort leaves only its owning modules' receipted steps,
        each lawful on its own. The key is burned: the same key never
        re-executes."""
        epoch = inp.epoch if isinstance(inp, PipelineInputs) else None
        pool = inp.pool if isinstance(inp, PipelineInputs) else None
        body = {
            "kind": PIPELINE_KIND,
            "module": PIPELINE_MODULE,
            "pipeline_identity": PIPELINE_IDENTITY,
            "idempotency_key": inp.idempotency_key
            if isinstance(inp, PipelineInputs) else None,
            "status": "aborted",
            "epoch": epoch,
            "pool": pool,
            "provenance": "DERIVED",
            "provenance_note": "the abort itself is machine-derived; the "
                               "refused inputs keep their own labels",
            "testnet": True,
            "ts": _now_iso(),
            "failing_step": failing_step,
            "reason": reason,
            "steps": [],
            "chain": {"step_manifest_hashes": [], "steps_chained": 0,
                      "note": "aborted before sealing — no step chain"},
            "state_digest": self.ledger.state_digest(),
        }
        return {**body,
                "pipeline_id": uuid.uuid4().hex,
                "pipeline_hash": _pipeline_hash(body)}


# ---------------------------------------------------------------------------
# Verification — the pipeline receipt against the ledger
# ---------------------------------------------------------------------------

def verify_pipeline_run(receipt, ledger):
    """Verify a pipeline receipt: the seal reseals, and every chained step
    receipt exists in the ledger. Returns {"ok": True} or
    {"ok": False, "reason": ...} — never raises on bad data."""
    if not isinstance(receipt, dict):
        return {"ok": False, "reason": "not a receipt object"}
    if receipt.get("kind") != PIPELINE_KIND:
        return {"ok": False,
                "reason": f"not a pipeline receipt (kind {receipt.get('kind')!r})"}
    sealed = receipt.get("pipeline_hash")
    body = {k: v for k, v in receipt.items()
            if k not in ("pipeline_hash", "pipeline_id")}
    try:
        recomputed = _pipeline_hash(body)
    except Exception as e:
        return {"ok": False, "reason": f"receipt body not hashable: {e}"}
    if sealed != recomputed:
        return {"ok": False,
                "reason": "pipeline_hash does not reseal — the receipt was "
                          "modified after sealing"}
    try:
        by_id = {r.receipt_id: r for r in ledger.receipts}
    except Exception:
        return {"ok": False, "reason": "ledger has no receipt chain to check"}
    chained_manifests = []
    for step in receipt.get("steps", []):
        for ref in step.get("receipts", []):
            rid = ref.get("receipt_id")
            if rid not in by_id:
                return {"ok": False,
                        "reason": f"step {step.get('step')!r} receipt "
                                  f"{rid[:8] if rid else '?'}… is not in the "
                                  f"ledger — the chain is broken"}
            if by_id[rid].manifest_hash != ref.get("manifest_hash"):
                return {"ok": False,
                        "reason": f"step {step.get('step')!r} receipt "
                                  f"{rid[:8]}… manifest mismatch — tampered"}
            chained_manifests.append(ref.get("manifest_hash"))
    if receipt.get("status") == "completed":
        sealed_chain = (receipt.get("chain") or {}).get("step_manifest_hashes", [])
        if chained_manifests != sealed_chain:
            return {"ok": False,
                    "reason": "sealed step chain does not match the step "
                              "receipts — tampered"}
    return {"ok": True}


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def run_pipeline(inputs, ledger):
    """Single-shot convenience: build a PipelineRunner on `ledger` and run
    once. NOTE: the idempotency registry lives on the runner — for
    cross-call idempotency, keep a PipelineRunner and call its
    run_pipeline. This convenience is one call, one registry."""
    return PipelineRunner(ledger).run_pipeline(inputs)

"""
EPOCH RUNNER — the heart for the heartbeat. TESTNET ONLY.

Gauntlet PERPETUITY hand point I-1: nothing in economics/ or dclm/ invoked
the epoch cycle — the pipeline (receipts -> merit -> emission -> disbursement
-> decay -> peg calibration -> reserve -> winter) was conceptual, and every
epoch close needed an external invoker. This module is the autonomous
epoch runner: it DRIVES the existing machinery (tokenomics.Ledger,
emission_calculator) without redesigning it.

The lawful per-epoch cycle, in order:
  1. ingest receipts   — gated (VERIFIED) receipts, epoch-bound, idempotent
  2. accrue merit      — gated receipt -> merit (accrue_merit)
  3. compute emission  — emission_close per pool: STANDING-gated (earned
                         history, origin-based — never balances; bought
                         Merit buys zero emission weight), peg-calibrated,
                         authority-bounded, winter-throttled, reserve absorb
  4. disburse          — per-member, per-pool, Unity-bound, authority-bounded
  5. apply decay       — per-member merit decay (fidelity is current)
  6. peg calibration   — verify the definitional peg (eFuse_i = merit_i / E)
                         holds on the computed emission; deviation fails the epoch
  7. reserve           — absorb/release operated inside emission_close,
                         receipted per pool; the runner verifies the accounting
  8. winter check      — the winter state threaded through emission is
                         collected per pool from the lawful source (dclm/winter.py)
  9. close epoch       — sealed with an "epoch_close" receipt; the epoch
                         number is recorded. Closing the same epoch twice
                         raises DoubleEpochCloseError (hand point I-3: the
                         drill proved double-close double-pays).

Failure semantics — fail CLOSED, never half-open:
  * Phase 1 (gates) runs BEFORE any mutation. Any gate failure raises and
    nothing of the epoch is applied: no partial epoch.
  * Phase 2 (apply) failures raise EpochFailedError carrying the step and
    the cause. The epoch is NOT recorded as closed and NO epoch-close
    receipt is written, so the epoch may be investigated and retried —
    never silently half-closed.
  * HeldParameterError is NEVER wrapped: a HELD parameter (David's digit)
    is an honest refusal, not an epoch failure.

No human hands: every input arrives as a parameter (receipts, weights,
peg_ratio, decay_rate, winter signals, reserve settings). The runner never
prompts, never blocks, never sleeps. run_epochs() drives a bounded batch;
next_epoch() runs the single next sequential epoch for a future scheduler.
The runner is the engine, not the daemon — it does not loop forever.
"""

import weakref
from dataclasses import dataclass, field

import tokenomics as _T
from tokenomics import (
    Figure,
    HeldParameter,
    HeldParameterError,
    Receipt,
    TokenomicsError,
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class EpochRunnerError(TokenomicsError):
    """Base for epoch-runner refusals and failures."""


class DoubleEpochCloseError(EpochRunnerError):
    """Refusing to close an epoch that is already closed.

    Gauntlet PERPETUITY I-3: Worker 4 proved a duplicate epoch close
    double-disburses (bounded only by the pool authority cap). The runner
    tracks closed epoch numbers and refuses the second close — no
    double-disbursement, ever."""


class EpochFailedError(EpochRunnerError):
    """An epoch failed a gate or a step and did NOT close.

    Carries the epoch number, the step that failed, and the original cause.
    No epoch-close receipt was written; the epoch was not recorded closed.
    """

    def __init__(self, epoch, step, cause):
        self.epoch = epoch
        self.step = step
        self.cause = cause
        super().__init__(
            f"epoch {epoch} FAILED at step {step!r}: {cause!r} — "
            "the epoch did NOT close and no epoch-close receipt was "
            "written; it may be investigated and retried, never silently "
            "half-closed."
        )


class PegDeviationError(EpochRunnerError):
    """The peg calibration check failed: computed emission does not satisfy
    the definitional peg (eFuse_i = merit_i / E) within tolerance."""


# ---------------------------------------------------------------------------
# Inputs — everything the runner needs arrives as parameters
# ---------------------------------------------------------------------------

@dataclass
class ReceiptInput:
    """One gated receipt to ingest and accrue merit from this epoch."""
    unity_id: str
    receipt: Receipt      # pre-built, VERIFIED, epoch-bound gated receipt
    weight: Figure        # merit weight with its provenance (bands are HELD)


@dataclass
class PoolEpochInputs:
    """Per-pool inputs for one epoch."""
    pool: str                        # "human" | "machine"
    members: list                    # roster whose merit counts toward emission
    receipts: list = field(default_factory=list)   # [ReceiptInput]
    winter: object = None            # None | winter.WinterSignal | winter.WinterState
    holdback_fraction: object = None  # None (not engaged) | Figure in [0,1)
    reserve_release: object = None    # None | Figure (explicit calibration release)


@dataclass
class EpochInputs:
    """The complete parameter set for one epoch. No prompts, no defaults
    invented: peg_ratio and decay_rate are required; HELD values refuse."""
    peg_ratio: object = None         # Figure (decided) — HeldParameter refuses
    decay_rate: object = None        # Figure (decided) — HeldParameter refuses
    pools: dict = field(default_factory=dict)  # pool name -> PoolEpochInputs
    decay_epochs: int = 1


@dataclass
class EpochReport:
    """What one closed epoch did, sealed and receipted."""
    epoch: int
    pools: dict              # pool -> per-pool results
    members_accrued: int
    members_decayed: int
    peg_check: dict
    receipts_added: int
    close_receipt_id: str
    close_manifest_hash: str
    state_digest: str
    provenance: str


# The runner's system identity for the epoch-close receipt. Not a member —
# the same precedent as the pool reserve identity ("pool:{pool}:..."): a
# system-level receipt binds a system identity, never a member, never blank.
RUNNER_IDENTITY = "system:epoch-runner"

# Relative tolerance for the peg calibration check. The drill measured max
# deviation 2.17e-16 over 1,200 epochs; 1e-9 leaves six orders of headroom
# for float arithmetic while catching any real break.
PEG_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# Input coercion (accept the dataclasses or plain dicts)
# ---------------------------------------------------------------------------

def _coerce_receipt_input(x):
    if isinstance(x, ReceiptInput):
        return x
    if isinstance(x, dict):
        return ReceiptInput(unity_id=x["unity_id"], receipt=x["receipt"],
                            weight=x["weight"])
    raise EpochRunnerError(
        f"receipt inputs must be ReceiptInput or dict, got {type(x).__name__!r}")


def _coerce_pool_inputs(x):
    if isinstance(x, PoolEpochInputs):
        return x
    if isinstance(x, dict):
        return PoolEpochInputs(
            pool=x["pool"], members=list(x.get("members", [])),
            receipts=[_coerce_receipt_input(r) for r in x.get("receipts", [])],
            winter=x.get("winter"),
            holdback_fraction=x.get("holdback_fraction"),
            reserve_release=x.get("reserve_release"),
        )
    raise EpochRunnerError(
        f"pool inputs must be PoolEpochInputs or dict, got {type(x).__name__!r}")


def _coerce_inputs(inputs):
    if isinstance(inputs, EpochInputs):
        pools = {p: _coerce_pool_inputs(v) for p, v in inputs.pools.items()}
        return EpochInputs(peg_ratio=inputs.peg_ratio,
                           decay_rate=inputs.decay_rate, pools=pools,
                           decay_epochs=inputs.decay_epochs)
    if isinstance(inputs, dict):
        pools = {p: _coerce_pool_inputs(v)
                 for p, v in inputs.get("pools", {}).items()}
        return EpochInputs(peg_ratio=inputs.get("peg_ratio"),
                           decay_rate=inputs.get("decay_rate"), pools=pools,
                           decay_epochs=inputs.get("decay_epochs", 1))
    raise EpochRunnerError(
        f"epoch inputs must be EpochInputs or dict, got {type(inputs).__name__!r}")


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class EpochRunner:
    """Drives the lawful per-epoch cycle on a tokenomics.Ledger.

    The runner holds no economic state of its own beyond the closed-epoch
    record (recovered from the ledger's own epoch_close receipts, so a
    reconstructed runner on the same ledger refuses the same double-closes).
    """

    def __init__(self, ledger, merit_provenance="VERIFIED"):
        self.ledger = ledger
        # merit_provenance is retained for API compatibility. Emission
        # weights derive from earned standing (origin-based), never from
        # balance maps — this label no longer feeds the emission gate.
        self.merit_provenance = merit_provenance
        self._closed_epochs = set()
        # Recover closed epochs from the ledger's own receipts: an epoch
        # sealed with an epoch_close receipt stays closed across runner
        # reconstruction (no new persistence machinery — the receipt chain
        # IS the record).
        for r in ledger.receipts:
            if r.kind == "epoch_close" and isinstance(r.epoch, int):
                self._closed_epochs.add(r.epoch)

    # -- idempotency ------------------------------------------------------
    @property
    def closed_epochs(self):
        return frozenset(self._closed_epochs)

    def is_epoch_closed(self, epoch):
        return epoch in self._closed_epochs

    @property
    def next_epoch_number(self):
        return max(self._closed_epochs) + 1 if self._closed_epochs else 1

    # -- main entry points ------------------------------------------------
    def run_epoch(self, epoch_number, inputs):
        """Execute the FULL lawful cycle for one epoch, then seal it.

        Raises DoubleEpochCloseError if the epoch already closed,
        HeldParameterError if a required HELD parameter is unset,
        EpochFailedError (with step + cause) on any other gate/step failure.
        On success returns an EpochReport; the epoch is recorded closed.
        """
        # ---- gate 0: idempotency (I-3) — before anything else ----
        if not isinstance(epoch_number, int) or isinstance(epoch_number, bool) \
                or epoch_number < 1:
            raise EpochRunnerError(
                f"epoch_number must be a positive int, got {epoch_number!r}")
        if epoch_number in self._closed_epochs:
            raise DoubleEpochCloseError(
                f"epoch {epoch_number} is already closed — refusing the "
                "second close (no double-disbursement)")
        step = "coerce_inputs"
        try:
            inp = _coerce_inputs(inputs)
            step = "gate_inputs"
            self._gate_inputs(inp)
            peg = inp.peg_ratio
            rate = inp.decay_rate

            # ---- Phase 1: gates — zero mutation -------------------------
            step = "gate_receipts"
            planned = self._gate_receipts(inp, epoch_number)
            step = "gate_emission"
            computed = self._gate_emission(inp, peg, planned)
            step = "gate_peg"
            peg_check = self._gate_peg(inp, peg, planned, computed)

            # ---- Phase 2: apply — ordered, each step receipted ----------
            receipts_before = len(self.ledger.receipts)
            step = "accrue_merit"
            accrued = self._apply_accruals(inp, epoch_number)
            step = "emission_close"
            outs = self._apply_emission_close(inp, peg, epoch_number)
            step = "disburse"
            disbursed = self._apply_disbursement(inp, outs, epoch_number)
            step = "decay"
            decayed = self._apply_decay(inp, rate, epoch_number)

            # ---- Phase 3: seal ------------------------------------------
            step = "seal_epoch"
            report = self._seal_epoch(epoch_number, inp, peg, rate, computed,
                                      outs, disbursed, accrued, decayed,
                                      peg_check, receipts_before)
            self._closed_epochs.add(epoch_number)
            return report
        except (DoubleEpochCloseError, HeldParameterError, EpochFailedError):
            # Honest refusals propagate unwrapped: a double-close, a HELD
            # parameter, or an already-classified epoch failure is the
            # signal — never re-wrapped into something vaguer. Every other
            # gate/step failure becomes EpochFailedError (the epoch failed
            # closed), carrying the step and the original cause.
            raise
        except Exception as exc:  # noqa: BLE001 — wrapped, never swallowed
            raise EpochFailedError(epoch_number, step, exc) from exc

    def next_epoch(self, inputs):
        """Run the single next sequential epoch (for a future scheduler)."""
        return self.run_epoch(self.next_epoch_number, inputs)

    def run_epochs(self, n, input_source, start_epoch=None):
        """Drive a bounded batch of n epochs. input_source is a callable
        taking the epoch number -> EpochInputs (or dict), or an iterable of
        EpochInputs. Driven, not polling: no sleeps, no infinite loop."""
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise EpochRunnerError(f"n must be a positive int, got {n!r}")
        epoch = start_epoch if start_epoch is not None else self.next_epoch_number
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 1:
            raise EpochRunnerError(
                f"start_epoch must be a positive int, got {epoch!r}")
        reports = []
        iterator = None
        if not callable(input_source):
            iterator = iter(input_source)
        for _ in range(n):
            if iterator is not None:
                try:
                    inputs = next(iterator)
                except StopIteration:
                    raise EpochRunnerError(
                        "input_source exhausted before n epochs ran — "
                        "the runner takes inputs as parameters; it does not "
                        "invent them") from None
            else:
                inputs = input_source(epoch)
            reports.append(self.run_epoch(epoch, inputs))
            epoch += 1
        return reports

    # -- Phase 1: gates ----------------------------------------------------
    def _gate_inputs(self, inp):
        if not inp.pools:
            raise EpochRunnerError("epoch inputs must name at least one pool")
        for name, pin in inp.pools.items():
            if name not in ("human", "machine"):
                raise EpochRunnerError(
                    f"unknown pool {name!r} — pools are 'human'/'machine'")
            if pin.pool != name:
                raise EpochRunnerError(
                    f"pool key {name!r} mismatches PoolEpochInputs.pool "
                    f"{pin.pool!r}")
            if not pin.members:
                raise EpochRunnerError(
                    f"pool {name!r} names no members — the merit roster is "
                    "required input, never invented")
            for uid in pin.members:
                if not isinstance(uid, str) or not uid.strip():
                    raise EpochRunnerError(
                        f"pool {name!r} roster holds an invalid unity_id "
                        f"{uid!r} — no anonymous flows")
        if not isinstance(inp.decay_epochs, int) or \
                isinstance(inp.decay_epochs, bool) or inp.decay_epochs < 1:
            raise EpochRunnerError(
                f"decay_epochs must be a positive int, got "
                f"{inp.decay_epochs!r} — merit decays per epoch, by law")
        # HELD parameters refuse here, before any mutation (honest refusal,
        # not a hang, not an invention).
        self._require_decided_figure(inp.peg_ratio, "peg_ratio")
        if inp.peg_ratio.value <= 0:
            raise EpochRunnerError("peg_ratio must be positive")
        self._require_decided_figure(inp.decay_rate, "decay_rate")
        if not (0.0 <= inp.decay_rate.value < 1.0):
            raise EpochRunnerError("decay_rate must lie in [0, 1)")

    @staticmethod
    def _require_decided_figure(x, name):
        """A required economic parameter: present, decided, positive-lawful.

        Missing, HeldParameter, HELD/UNKNOWN provenance -> HeldParameterError.
        """
        if x is None:
            raise HeldParameterError(
                f"{name} is required input for the epoch and was not "
                "provided — refusing to invent it (HELD_FOR_DAVID)")
        if isinstance(x, HeldParameter):
            raise HeldParameterError(
                f"{name} is HELD_FOR_DAVID ({x.name}) — refusing to invent it")
        if not isinstance(x, Figure):
            raise EpochRunnerError(
                f"{name} must be a Figure or HeldParameter, got "
                f"{type(x).__name__!r} — unsigned numbers never pay")
        if x.provenance in ("HELD", "UNKNOWN"):
            raise HeldParameterError(
                f"{name} is {x.provenance} — David's digit; refusing to "
                "invent it")
        return x

    def _gate_receipts(self, inp, epoch_number):
        """Validate every receipt/weight; return planned post-accrual merit
        balances {unity_id: float} for the epoch's rosters."""
        seen_manifests = {r.manifest_hash for r in self.ledger.receipts}
        batch_manifests = set()
        # planned balance = current ledger balance + this epoch's weights
        planned = {}
        for name, pin in inp.pools.items():
            for uid in pin.members:
                if uid not in planned:
                    planned[uid] = self.ledger.merit_balances.get(uid, 0.0)
            for ri in pin.receipts:
                if not isinstance(ri.receipt, Receipt):
                    raise EpochRunnerError(
                        f"pool {name!r}: receipt input for {ri.unity_id!r} "
                        "is not a tokenomics Receipt")
                if ri.receipt.unity_id != ri.unity_id.strip():
                    raise EpochRunnerError(
                        f"pool {name!r}: receipt is bound to "
                        f"{ri.receipt.unity_id!r}, not the claimant "
                        f"{ri.unity_id!r} — no cross-binding")
                if ri.receipt.provenance != "VERIFIED":
                    raise EpochRunnerError(
                        f"pool {name!r}: receipt "
                        f"{ri.receipt.receipt_id[:8]}… is "
                        f"{ri.receipt.provenance}, not VERIFIED — gated "
                        "receipts only; UNKNOWN never pays")
                if ri.receipt.epoch != epoch_number:
                    raise EpochRunnerError(
                        f"pool {name!r}: receipt "
                        f"{ri.receipt.receipt_id[:8]}… is epoch-bound to "
                        f"{ri.receipt.epoch}, not this epoch {epoch_number} "
                        "— epochs stay clean")
                mh = ri.receipt.manifest_hash
                if mh in seen_manifests:
                    raise _T.DuplicateReceiptError(
                        f"manifest {mh[:16]}… already applied — the same "
                        "work is never counted twice")
                if mh in batch_manifests:
                    raise _T.DuplicateReceiptError(
                        f"manifest {mh[:16]}… appears twice in this "
                        "epoch's inputs — refusing the double count")
                batch_manifests.add(mh)
                w = ri.weight
                if isinstance(w, HeldParameter) or not isinstance(w, Figure) \
                        or w.provenance in ("HELD", "UNKNOWN"):
                    raise HeldParameterError(
                        "merit weight bands are HELD_FOR_DAVID — refusing "
                        "an unsigned/unknown weight")
                if w.value <= 0:
                    raise EpochRunnerError("merit weight must be positive")
                uid = ri.unity_id.strip()
                planned[uid] = planned.get(
                    uid, self.ledger.merit_balances.get(uid, 0.0)) + w.value
        return planned

    def _planned_standing(self, planned):
        """Planned post-accrual STANDING weights for the epoch's rosters.

        Standing, not balances: the emission gate reads earned history
        (origin-based), never owned balances (which can be bought).
        planned maps uid -> planned post-accrual BALANCE; the planned
        standing increment is the balance delta (this epoch's gated
        accruals) added to the ledger's current earned standing."""
        weights = {}
        for uid, planned_bal in planned.items():
            inc = planned_bal - self.ledger.merit_balances.get(uid, 0.0)
            s = self.ledger.standing(uid).value + inc
            weights[uid] = Figure(
                s, "DERIVED",
                "planned standing: ledger earned standing + this epoch's "
                "gated accruals — balances never enter the emission gate")
        return weights

    def _gate_emission(self, inp, peg, planned):
        """Pure computation of the epoch's emission per pool (no mutation):
        winter throttle and reserve absorb are computed here so the peg gate
        below runs before anything is written. Emission weights are the
        PLANNED STANDING (earned history + this epoch's gated accruals) —
        never balances: bought Merit buys zero emission weight."""
        planned_weights = self._planned_standing(planned)
        computed = {}
        for name, pin in inp.pools.items():
            pool_weights = {uid: planned_weights[uid] for uid in pin.members}
            out = _T.emission_calculator(
                name, None, peg,
                self.ledger.remaining_authority(name),
                winter=pin.winter,
                holdback_fraction=pin.holdback_fraction,
                reserve_release=pin.reserve_release,
                reserve_balance=self.ledger.reserve_balance(name),
                standing_source=pool_weights,
            )
            computed[name] = (out, pool_weights)
        return computed

    def _gate_peg(self, inp, peg, planned, computed):
        """Peg calibration: the definitional peg must hold on the computed
        emission — eFuse_i = merit_i / E, winter-throttled, authority-bounded.
        Any deviation beyond tolerance fails the epoch (no partial epoch)."""
        E = peg.value
        max_dev = 0.0
        per_pool = {}
        for name, (out, merit_map) in computed.items():
            # merit_map here is the trusted standing-weight map the gate
            # computed from (DERIVED planned standing, never balances).
            shares = {u: f.value for u, f in merit_map.items()
                      if f.value > 0}
            total_merit = sum(shares.values())
            auth = self.ledger.remaining_authority(name).value
            if total_merit <= 0:
                if out.total.value != 0.0 or out.per_member:
                    raise PegDeviationError(
                        f"pool {name!r}: no verified merit but computed "
                        "emission is non-zero — refusing")
                dev = 0.0
            else:
                expected_total = min(total_merit / E, auth) * out.winter_multiplier
                dev = (abs(out.total.value - expected_total) / expected_total
                       if expected_total > 0 else 0.0)
                # Reserve accounting identity (from the emission contract):
                # total + released == sum(per_member) + held.
                lhs = out.total.value + out.reserve_released.value
                rhs = (sum(f.value for f in out.per_member.values())
                       + out.reserve_held.value)
                scale = max(1.0, abs(lhs))
                if abs(lhs - rhs) / scale > PEG_TOLERANCE:
                    raise PegDeviationError(
                        f"pool {name!r}: reserve accounting broken — "
                        f"total+released={lhs}, per_member+held={rhs}")
            max_dev = max(max_dev, dev)
            per_pool[name] = {
                "relative_deviation": dev,
                "winter_multiplier": out.winter_multiplier,
                "authority_bound": out.authority_cap_applied,
            }
            if dev > PEG_TOLERANCE:
                raise PegDeviationError(
                    f"pool {name!r}: peg deviation {dev:.3e} exceeds "
                    f"tolerance {PEG_TOLERANCE:.0e} — the peg is definitional "
                    "(eFuse_i = merit_i / E); refusing the epoch")
        return {"max_relative_deviation": max_dev, "tolerance": PEG_TOLERANCE,
                "pass": True, "per_pool": per_pool}

    # -- Phase 2: apply ----------------------------------------------------
    def _apply_accruals(self, inp, epoch_number):
        accrued = 0
        for pin in inp.pools.values():
            for ri in pin.receipts:
                self.ledger.accrue_merit(ri.unity_id.strip(), ri.receipt,
                                        ri.weight)
                accrued += 1
        return accrued

    def _roster_standing_map(self, roster):
        """The pool roster's earned-standing restatement: {uid: Figure}.

        UNTRUSTED-shaped but honest input for emission_close — each
        entry equals the ledger's standing for that identity, so the
        standing cross-check passes; the gate still derives every weight
        from standing, never from this map. Scopes the close to the
        pool's roster (the orchestrator's legitimate scope decision);
        bought balances cannot enter because any value != standing
        refuses."""
        return {uid: Figure(self.ledger.standing(uid).value, "DERIVED",
                            "pool roster standing restatement — "
                            "cross-checked against standing, never read "
                            "for weights")
                for uid in roster}

    def _apply_emission_close(self, inp, peg, epoch_number):
        outs = {}
        for name, pin in inp.pools.items():
            out = self.ledger.emission_close(
                name, self._roster_standing_map(pin.members), peg,
                epoch_number,
                winter=pin.winter,
                holdback_fraction=pin.holdback_fraction,
                reserve_release=pin.reserve_release,
            )
            outs[name] = out
        return outs

    def _apply_disbursement(self, inp, outs, epoch_number):
        disbursed = {}
        for name, out in outs.items():
            total = 0.0
            for uid, fig in out.per_member.items():
                self.ledger.disburse(name, uid, fig, epoch_number)
                total += fig.value
            disbursed[name] = {"members": len(out.per_member), "total": total}
        return disbursed

    def _apply_decay(self, inp, rate, epoch_number):
        members = []
        for pin in inp.pools.values():
            for uid in pin.members:
                if uid not in members:
                    members.append(uid)
        for uid in members:
            self.ledger.apply_decay(uid, inp.decay_epochs, rate)
        return members

    # -- Phase 3: seal ------------------------------------------------------
    def _epoch_provenance(self, inp):
        provs = [inp.peg_ratio.provenance, inp.decay_rate.provenance]
        for pin in inp.pools.values():
            for ri in pin.receipts:
                provs.append(ri.weight.provenance)
            for x in (pin.holdback_fraction, pin.reserve_release):
                if isinstance(x, Figure):
                    provs.append(x.provenance)
        # Weakest link: any MODELED input -> MODELED epoch (labeled honestly).
        return "MODELED" if "MODELED" in provs else "DERIVED"

    def _seal_epoch(self, epoch_number, inp, peg, rate, computed, outs,
                    disbursed, accrued, decayed, peg_check, receipts_before):
        pools_detail = {}
        for name, out in outs.items():
            pools_detail[name] = {
                "emission_total": out.total.value,
                "emission_provenance": out.total.provenance,
                "emission_sha256": out.canonical_sha256,
                "disbursed_total": disbursed[name]["total"],
                "members_disbursed": disbursed[name]["members"],
                "reserve_held": out.reserve_held.value,
                "reserve_released": out.reserve_released.value,
                "reserve_balance_after": self.ledger.reserve[name],
                "authority_cap_applied": out.authority_cap_applied,
                "winter": {
                    "gradient": out.winter_gradient,
                    "label": out.winter_label,
                    "multiplier": out.winter_multiplier,
                    "reasons": list(out.winter_reasons),
                    "provenance": out.winter_provenance,
                },
            }
        prov = self._epoch_provenance(inp)
        detail = {
            "epoch": epoch_number,
            "runner": "economics/epoch_runner.py",
            "runner_identity": RUNNER_IDENTITY,
            "pools": pools_detail,
            "accruals": accrued,
            "decay": {"rate": rate.value,
                      "rate_provenance": rate.provenance,
                      "epochs": inp.decay_epochs,
                      "members_decayed": len(decayed)},
            "peg_check": peg_check,
            "peg_ratio_E": peg.value,
            "peg_ratio_provenance": peg.provenance,
            "receipts_before": receipts_before,
            "receipts_after": len(self.ledger.receipts),
            "state_digest": self.ledger.state_digest(),
            "provenance_note": (
                "epoch provenance follows the weakest input: any MODELED "
                "figure among (peg_ratio, decay_rate, weights, reserve "
                "settings) -> MODELED epoch outputs; all decided -> DERIVED."),
        }
        head = (self.ledger.receipts[-1].manifest_hash
                if self.ledger.receipts else "GENESIS")
        close_receipt = Receipt.build(RUNNER_IDENTITY, "epoch_close", detail,
                                      prov, epoch_number, head)
        self.ledger.apply_receipt(close_receipt)
        return EpochReport(
            epoch=epoch_number,
            pools={name: {
                "emission_total": d["emission_total"],
                "disbursed_total": d["disbursed_total"],
                "members_disbursed": d["members_disbursed"],
                "reserve_held": d["reserve_held"],
                "reserve_released": d["reserve_released"],
                "winter_gradient": d["winter"]["gradient"],
                "winter_label": d["winter"]["label"],
                "winter_multiplier": d["winter"]["multiplier"],
            } for name, d in pools_detail.items()},
            members_accrued=accrued,
            members_decayed=len(decayed),
            peg_check=peg_check,
            receipts_added=len(self.ledger.receipts) - receipts_before,
            close_receipt_id=close_receipt.receipt_id,
            close_manifest_hash=close_receipt.manifest_hash,
            state_digest=self.ledger.state_digest(),
            provenance=prov,
        )


# ---------------------------------------------------------------------------
# Module-level API — ledger-bound runners (the engine behind the functions)
# ---------------------------------------------------------------------------

_runners = weakref.WeakKeyDictionary()


def get_runner(ledger):
    """The EpochRunner bound to this ledger (one runner per ledger; the
    closed-epoch record lives with the runner, recovered from the ledger's
    own epoch_close receipts)."""
    runner = _runners.get(ledger)
    if runner is None:
        runner = EpochRunner(ledger)
        _runners[ledger] = runner
    return runner


def run_epoch(ledger, epoch_number, inputs):
    """Execute the FULL lawful cycle for one epoch on the ledger, then seal
    it. See EpochRunner.run_epoch. Raises DoubleEpochCloseError on a second
    close of the same epoch; HeldParameterError on HELD parameters."""
    return get_runner(ledger).run_epoch(epoch_number, inputs)


def run_epochs(ledger, n, input_source, start_epoch=None):
    """Drive a bounded batch of n epochs. input_source: callable taking the
    epoch number -> EpochInputs (or dict), or an iterable of EpochInputs.
    Driven, not polling — no sleeps, no infinite loop."""
    return get_runner(ledger).run_epochs(n, input_source, start_epoch)

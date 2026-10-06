#!/usr/bin/env python3
"""
law.py — versioned law + lawful supersession (Perpetuity I-6).

The old law yields to the new law through its OWN lawful process.
Continuity preserved. Bypass = attack. (David's law.)

Status: TESTNET. The Trinity gate below uses MODELED stand-ins for the
real DCLM/Iris/Twain² judgment pipeline — each check is labeled honestly.
Production swaps the gate via TrinityGate subclasses; this module never
invents authority.

Process:  PROPOSE → VERIFY → ACTIVATE (at an epoch boundary only) →
HANDOFF (receipted). Constitutional laws cannot be touched by this
process at all: a proposal naming one is REFUSED at PROPOSE time.

In-flight rule: the stamp on the computation rules. A transaction stamped
with the law version under which it began completes under that version
even after a newer law activates. The new law is PROSPECTIVE ONLY — it
never rewrites history.

Every state change is receipted in the registry's append-only process
log. There is no public setter: any version whose activation is absent
from the process log is refused at use (bypass detection).

See: gauntlet/PERPETUITY.md, Drill 3.
Schema: unity.economics.supersession.v1.testnet
"""
import copy
import hashlib
import json
import re

import tokenomics as T
from wallet import _node_sign, _node_verify

# ---------------------------------------------------------------------------
# The constitutional set — David's laws. These CANNOT be superseded.
#
# Derived from the record (each entry carries its source; nothing here is
# invented). A proposal touching any of these names is REFUSED at PROPOSE
# time — before signatures are even checked. Raising a ceiling is not an
# upgrade; it needs David's direct act, a higher process.
# ---------------------------------------------------------------------------
CONSTITUTIONAL_SOURCES = {
    # The 50/50 architecture — David's decided constants (ED-DECIDED-
    # 20261004-5050-V1), recorded in tokenomics.PARAMS as DECIDED.
    "lifetime_cap": "tokenomics.PARAMS['lifetime_cap'] DECIDED: 100M eFuse "
        "lifetime emission cap. A ceiling, never a quota, never a treasury.",
    "human_pool_cap": "tokenomics.PARAMS['human_pool_cap'] DECIDED: 50M "
        "lifetime emission authority, human pool.",
    "machine_pool_cap": "tokenomics.PARAMS['machine_pool_cap'] DECIDED: 50M "
        "lifetime emission authority, machine pool.",
    "one_merged_rail": "tokenomics.PARAMS['one_merged_rail'] DECIDED: one "
        "merged 100M rail; the pool boundary is the gated frontier.",
    "no_pre_funding": "tokenomics.PARAMS['no_pre_funding'] DECIDED: coins "
        "come into existence only against gated receipts, over epochs. "
        "No receipts -> zero emission.",
    "no_pool_to_pool": "tokenomics.PARAMS['no_pool_to_pool'] DECIDED: no "
        "flow between the Human and Machine Emission Pools — enforced by "
        "absence of machinery.",
    "mesh_never_mints": "tokenomics.PARAMS['mesh_never_mints'] DECIDED: the "
        "mesh is a zone, not a pool: it routes, never mints.",
    "merit_transferable": "tokenomics.PARAMS['merit_transferable'] DECIDED "
        "(David's word, 2026-10-06 ~3:35 AM EDT; DECISIONS.md §13): Merit "
        "IS transferable — the old non-transferable merit law was superseded "
        "by David's direct act, recorded explicitly, never silently edited.",
    "honor_never_converts": "tokenomics.PARAMS['honor_never_converts'] "
        "DECIDED: Honor never converts to emission. No path from fiat to "
        "eFuse — not direct, not indirect, not clever.",
    "unity_binding": "tokenomics.PARAMS['unity_binding'] DECIDED: every "
        "eFuse movement and every Merit/Honor accrual binds a Unity ID. "
        "No anonymous flows.",
    "merit_interest_refused": "tokenomics.PARAMS['merit_interest_refused'] "
        "DECIDED: Merit never earns merit. No staking, no yield.",
    # David's laws recorded outside PARAMS (MEMORY.md / canon):
    "unity_non_transferable": "David's law, 2026-10-06 ~3:05 AM EDT "
        "(MEMORY.md; WALLET_DESIGN_LAW.md §7): Unity tokens are bound to "
        "their Unity ID — cannot be sent, sold, gifted, or moved between "
        "wallets, not even by David.",
    "efuse_never_bought_sold": "David's law (alignment synthesis): the "
        "eFuse is the +1 — the seed at the threshold, never bought or sold, "
        "pegged to real-world energy, donations only.",
    "unknown_never_pays": "tokenomics.Figure: 'No unsigned claims: a bare "
        "number passed into the engine is treated as UNKNOWN' — UNKNOWN "
        "refuses (HeldParameterError/UnknownFigureError). The engine "
        "refuses rather than invents (PERPETUITY.md S-1).",
}

CONSTITUTIONAL = frozenset(CONSTITUTIONAL_SOURCES)

# Mutable = the operational digits David holds. Supersession is the lawful
# way these change: a proposal must carry the authority's signature, which
# IS the word of the hand the law requires (PERPETUITY.md S-1). Derived
# from tokenomics.PARAMS so the registry cannot drift from the canon.
MUTABLE = frozenset(
    name for name, p in T.PARAMS.items() if p.status == T.PARAM_HELD
)

# Version identifiers are v1, v2, ...
_VERSION_RE = re.compile(r"^v(\d+)$")


class LawError(Exception):
    pass


class UnlawfulSupersession(LawError):
    """A supersession attempt that violated the lawful process. The law is
    unchanged; the refusal is receipted in the process log."""
    pass


# ---------------------------------------------------------------------------
# Value sanity bounds (Iris check). Each mutable param names its lawful
# domain; anything outside refuses. None = HELD_FOR_DAVID (the digit has
# not arrived — the proposal must supply it, or the law keeps refusing
# when it is used).
# ---------------------------------------------------------------------------
def _nonneg_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0


def _unit(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < 1


_SANITY = {
    "peg_ratio_E": lambda x: x is None or (isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0),
    "merit_decay_rate": lambda x: x is None or _unit(x),
    "reserve_holdback_fraction": lambda x: x is None or _unit(x),
    "epoch_length": lambda x: x is None or (isinstance(x, str) and x.strip() != ""),
    "tier_weights": lambda x: x is None or (
        isinstance(x, dict) and x and all(_nonneg_number(v) for v in x.values())),
    "bridge_premium_band": lambda x: x is None or _nonneg_number(x),
    "corroboration_thresholds": lambda x: x is None or _nonneg_number(x),
    "bounty_band_floors_widths": lambda x: x is None or _nonneg_number(x),
    "ring_depth_factor": lambda x: x is None or _nonneg_number(x),
    "bridge_eligibility_threshold": lambda x: x is None or _nonneg_number(x),
    "machine_proof_of_energy_params": lambda x: x is None or isinstance(x, (dict, str)),
    "honor_class_names": lambda x: x is None or (isinstance(x, (list, tuple)) and all(isinstance(s, str) for s in x)),
    "merit_definition": lambda x: x is None or (isinstance(x, str) and x.strip() != ""),
}


def _sanity_ok(name, value):
    check = _SANITY.get(name)
    return check is None or check(value)


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------------------
# LawVersion — one sealed version of the law.
# ---------------------------------------------------------------------------
class LawVersion:
    """A sealed law version. params are deep-copied at construction and
    never mutated afterwards: a version's digits are frozen at activation."""

    ACTIVE = "ACTIVE"
    PENDING_ACTIVATION = "PENDING_ACTIVATION"
    SUPERSEDED = "SUPERSEDED"

    def __init__(self, version, params, status, activated_at_epoch,
                 provenance=None):
        if not _VERSION_RE.match(version):
            raise LawError(f"malformed law version {version!r}")
        self.version = version
        # Sealed: the version's parameters frozen at activation.
        self.params = copy.deepcopy(dict(params))
        self.status = status
        self.activated_at_epoch = activated_at_epoch
        self.provenance = dict(provenance or {})

    def value(self, name):
        """Read a parameter under this law. HELD digits refuse — the law
        never invents a number David has not decided."""
        if name in self.params:
            v = self.params[name]
            if v is None:
                raise T.HeldParameterError(
                    f"parameter {name!r} is HELD_FOR_DAVID under law "
                    f"{self.version} — refusing to invent it")
            return v
        raise LawError(f"unknown parameter {name!r} under law {self.version}")

    def digest(self):
        return hashlib.sha256(_canonical({
            "version": self.version,
            "params": self.params,
            "status": self.status,
            "activated_at_epoch": self.activated_at_epoch,
        })).hexdigest()


# ---------------------------------------------------------------------------
# LawProposal — the signed act that begins supersession.
# ---------------------------------------------------------------------------
class LawProposal:
    SCHEMA = "unity.economics.supersession.v1.testnet"

    def __init__(self, proposal_id, from_version, to_version, param_changes,
                 rationale, proposer_key_id):
        self.proposal_id = proposal_id
        self.from_version = from_version
        self.to_version = to_version
        self.param_changes = copy.deepcopy(dict(param_changes))
        self.rationale = rationale
        self.proposer_key_id = proposer_key_id
        self.signature = None

    def body(self):
        return {
            "schema": self.SCHEMA,
            "proposal_id": self.proposal_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "param_changes": self.param_changes,
            "rationale": self.rationale,
            "proposer_key_id": self.proposer_key_id,
        }

    def sign(self, priv_der):
        self.signature = _node_sign(priv_der, _canonical(self.body()))
        return self

    def verify(self, pub_der):
        return bool(self.signature) and _node_verify(
            pub_der, _canonical(self.body()), self.signature)


# ---------------------------------------------------------------------------
# The Trinity gate. MODELED stand-ins for the real pipeline — labeled
# honestly. Production replaces these with the real DCLM/Iris/Twain²
# judgments by subclassing or injecting; the interface (verdicts keyed
# DCLM/IRIS/TWAIN2, "PASS" or GateRefusal) is the contract.
# ---------------------------------------------------------------------------
class GateRefusal(Exception):
    pass


class TrinityGate:
    """MODELED stand-ins for the real Trinity judgment pipeline."""

    NOTE = ("MODELED stand-ins for the real DCLM/Iris/Twain² judgment "
            "pipeline — production swaps in the real checks via subclassing")

    def dclm_check(self, registry, proposal, authority_pubkeys):
        """DCLM: logic-checks the proposal — authority proof, lineage,
        constitutional immutability, no unknown params."""
        pub = authority_pubkeys.get(proposal.proposer_key_id)
        if pub is None:
            raise GateRefusal("authority proof invalid: proposer key id "
                              f"{proposal.proposer_key_id!r} not in the "
                              "authority registry")
        if not proposal.verify(pub):
            raise GateRefusal("authority proof invalid: signature does not "
                              "verify against the registered key")
        if proposal.from_version != registry.current().version:
            raise GateRefusal(
                f"from_version {proposal.from_version!r} is not the current "
                f"law {registry.current().version!r} — stale proposal")
        bad = [p for p in proposal.param_changes if p in CONSTITUTIONAL]
        if bad:
            raise GateRefusal(f"constitutional params touched: {bad} — "
                              "immutable through supersession")
        unknown = [p for p in proposal.param_changes if p not in MUTABLE]
        if unknown:
            raise GateRefusal(f"unknown params: {unknown}")
        return "PASS"

    def iris_check(self, proposal):
        """Iris: verifies no fabricated claims — value sanity on every
        proposed digit."""
        for name, value in proposal.param_changes.items():
            if not _sanity_ok(name, value):
                raise GateRefusal(
                    f"value sanity failed for {name!r}={value!r} — "
                    "outside its lawful domain")
        return "PASS"

    def twain2_check(self, dry_run):
        """Twain²: the pragmatic filter — a migration dry-run on a COPY of
        live state must complete without corruption."""
        try:
            dry_run()
        except Exception as ex:
            raise GateRefusal(f"migration dry-run failed: {ex}") from ex
        return "PASS"

    def judge(self, registry, proposal, authority_pubkeys, dry_run):
        verdicts = {}
        for member, fn, args in (
                ("DCLM", self.dclm_check, (registry, proposal, authority_pubkeys)),
                ("IRIS", self.iris_check, (proposal,)),
                ("TWAIN2", self.twain2_check, (dry_run,))):
            try:
                verdicts[member] = fn(*args)
            except GateRefusal as ex:
                verdicts[member] = f"REFUSE: {ex}"
        verdicts["note"] = self.NOTE
        return verdicts


# ---------------------------------------------------------------------------
# LawRegistry — the versioned law. The CURRENT version is explicit state.
# ---------------------------------------------------------------------------
class LawRegistry:
    """Owns every law version and the append-only process log.

    No public setter exists: versions change ONLY through propose →
    verify → schedule_activation → advance_epoch (at the epoch boundary).
    The authority registry (key_id → pubkey) is sealed at genesis — it is
    not interceptable and cannot be edited here.
    """

    def __init__(self, genesis_params=None, genesis_provenance=None,
                 authority_pubkeys=None, gate=None):
        genesis_params = dict(genesis_params or {})
        unknown = [p for p in genesis_params if p not in MUTABLE]
        if unknown:
            raise LawError(f"genesis params not in the mutable set: {unknown}")
        full = {name: None for name in MUTABLE}
        full.update(genesis_params)
        self._versions = {
            "v1": LawVersion("v1", full, LawVersion.ACTIVE, 0,
                             provenance=genesis_provenance),
        }
        # The authority registry: sealed at genesis. Key rotation is not an
        # interception and not an edit — it goes through supersession's own
        # higher process (future work; deliberately no setter here).
        self._authority = dict(authority_pubkeys or {})
        self._gate = gate or TrinityGate()
        self._pending = None  # at most one proposal pending activation
        self._pending_info = None  # proposal metadata carried to the boundary
        self.process_log = [{
            "event": "GENESIS_LAW",
            "version": "v1",
            "digest": self._versions["v1"].digest(),
            "note": "initial law. Operational digits are HELD_FOR_DAVID "
                    "unless the genesis params supplied MODELED stand-ins; "
                    "the constitutional set is immutable through supersession.",
        }]

    # -- state ---------------------------------------------------------
    def current(self):
        for v in self._versions.values():
            if v.status == LawVersion.ACTIVE:
                return v
        raise LawError("no ACTIVE law version — registry corrupt")

    def get(self, version):
        try:
            return self._versions[version]
        except KeyError:
            raise UnlawfulSupersession(
                f"unknown law version {version!r}") from None

    def _assert_lawful(self, version):
        """Bypass detection: a version may be used only if its activation
        is receipted in the process log."""
        v = self.get(version)
        if not any(ev.get("version") == version and ev.get("event") in
                   ("GENESIS_LAW", "SUPERSESSION_ACTIVATED")
                   for ev in self.process_log):
            raise UnlawfulSupersession(
                f"law version {version!r} has no lawful activation in the "
                "process log — bypass detected; refusing")
        return v

    # -- PROPOSE --------------------------------------------------------
    def propose(self, proposal):
        """PROPOSE: constitutional touches are REFUSED here — at propose
        time, before any signature is even checked."""
        if self._pending is not None:
            raise UnlawfulSupersession(
                f"proposal {self._pending.proposal_id} is already pending "
                "activation — one supersession at a time")
        bad = [p for p in proposal.param_changes if p in CONSTITUTIONAL]
        if bad:
            self.process_log.append({
                "event": "PROPOSAL_REFUSED",
                "proposal": proposal.proposal_id,
                "reason": f"constitutional params touched at PROPOSE time: {bad}",
            })
            raise UnlawfulSupersession(
                f"proposal {proposal.proposal_id} touches constitutional "
                f"params {bad} — REFUSED at PROPOSE time")
        unknown = [p for p in proposal.param_changes if p not in MUTABLE]
        if unknown:
            self.process_log.append({
                "event": "PROPOSAL_REFUSED",
                "proposal": proposal.proposal_id,
                "reason": f"unknown params: {unknown}",
            })
            raise UnlawfulSupersession(
                f"proposal {proposal.proposal_id} names unknown params "
                f"{unknown} — REFUSED at PROPOSE time")
        if not _VERSION_RE.match(proposal.to_version):
            raise UnlawfulSupersession(
                f"malformed to_version {proposal.to_version!r}")
        if proposal.to_version in self._versions:
            raise UnlawfulSupersession(
                f"version {proposal.to_version!r} already exists")
        self.process_log.append({
            "event": "SUPERSESSION_PROPOSED",
            "proposal": proposal.proposal_id,
            "from": proposal.from_version,
            "to": proposal.to_version,
            "param_changes": proposal.param_changes,
            "rationale": proposal.rationale,
            "proposer": proposal.proposer_key_id,
        })
        return proposal

    # -- VERIFY ---------------------------------------------------------
    def verify(self, proposal, dry_run):
        """VERIFY: the Trinity gate judges the proposal. Refusal is
        receipted; the law does not move."""
        verdicts = self._gate.judge(self, proposal, self._authority, dry_run)
        ok = all(v == "PASS" for k, v in verdicts.items() if k != "note")
        self.process_log.append({
            "event": "SUPERSESSION_VERIFIED" if ok else "SUPERSESSION_REFUSED",
            "proposal": proposal.proposal_id,
            "verdicts": verdicts,
        })
        if not ok:
            raise UnlawfulSupersession(
                f"Trinity refused proposal {proposal.proposal_id}: {verdicts}")
        return verdicts

    # -- ACTIVATE (scheduled) -------------------------------------------
    def schedule_activation(self, proposal, verdicts, at_epoch,
                            activation_epoch):
        """Schedule activation at an epoch boundary. activation_epoch must
        be strictly after the current epoch — activation is never
        mid-epoch. The new version sits PENDING; the old law stays ACTIVE
        until the boundary."""
        if activation_epoch <= at_epoch:
            raise UnlawfulSupersession(
                f"activation_epoch {activation_epoch} is not after current "
                f"epoch {at_epoch} — activation at an epoch boundary only")
        old = self.current()
        if proposal.from_version != old.version:
            raise UnlawfulSupersession(
                f"proposal from_version {proposal.from_version!r} is no "
                f"longer the current law {old.version!r} — re-propose")
        new_params = dict(old.params)
        new_params.update(proposal.param_changes)
        new_provenance = dict(old.provenance)
        for n in proposal.param_changes:
            new_provenance[n] = f"supersession {proposal.proposal_id} (MODELED)"
        new = LawVersion(proposal.to_version, new_params,
                         LawVersion.PENDING_ACTIVATION, activation_epoch,
                         provenance=new_provenance)
        self._versions[new.version] = new
        self._pending = proposal
        # Carried to the boundary: the handoff receipt at activation must
        # name the verdicts and the authority proof, not just the schedule.
        self._pending_info = {
            "proposal_id": proposal.proposal_id,
            "trinity_verdicts": verdicts,
            "authority_proof": (f"Ed25519 by {proposal.proposer_key_id} "
                                "(verified)"),
            "proposal_signature": proposal.signature,
            "rationale": proposal.rationale,
        }
        self.process_log.append({
            "event": "SUPERSESSION_SCHEDULED",
            "proposal": proposal.proposal_id,
            "version": new.version,
            "from": old.version,
            "activation_epoch": activation_epoch,
            "trinity_verdicts": verdicts,
            "authority_proof": (f"Ed25519 by {proposal.proposer_key_id} "
                                "(verified)"),
            "proposal_signature": proposal.signature,
            "note": "PENDING until the epoch boundary — the old law stays "
                    "ACTIVE through the current epoch.",
        })
        return new

    # -- ACTIVATE (at the boundary) + HANDOFF ----------------------------
    def advance_epoch(self, epoch):
        """The epoch clock yields the old law at the boundary: a PENDING
        version whose activation_epoch has arrived becomes ACTIVE; the old
        ACTIVE version yields (SUPERSEDED). Receipted as LAW_YIELDED +
        SUPERSESSION_ACTIVATED."""
        activated = []
        for v in sorted(self._versions.values(),
                        key=lambda x: x.activated_at_epoch):
            if (v.status == LawVersion.PENDING_ACTIVATION
                    and v.activated_at_epoch <= epoch):
                old = self.current()
                old.status = LawVersion.SUPERSEDED
                v.status = LawVersion.ACTIVE
                info = self._pending_info or {}
                self.process_log.append({
                    "event": "LAW_YIELDED",
                    "from": old.version,
                    "to": v.version,
                    "at_epoch": epoch,
                    "note": "activation at the epoch boundary — the old law "
                            "yielded through its own lawful process; "
                            "in-flight computations stamped with the old "
                            "version still complete under it (the stamp "
                            "rules).",
                })
                self.process_log.append({
                    "event": "SUPERSESSION_ACTIVATED",
                    "version": v.version,
                    "from": old.version,
                    "param_changes": self._param_changes(old, v),
                    "activation_epoch": epoch,
                    "old_digest": old.digest(),
                    "new_digest": v.digest(),
                    "trinity_verdicts": info.get("trinity_verdicts"),
                    "authority_proof": info.get("authority_proof"),
                    "proposal_signature": info.get("proposal_signature"),
                    "proposal": info.get("proposal_id"),
                    "rationale": info.get("rationale"),
                    "note": "handoff receipted. The new law is prospective "
                            "only — balances, merit histories, and receipt "
                            "chains carry forward unchanged.",
                })
                if self._pending is not None and self._pending.to_version == v.version:
                    self._pending = None
                    self._pending_info = None
                activated.append(v)
        return activated

    @staticmethod
    def _param_changes(old, new):
        return {k: {"from": old.params.get(k), "to": new.params.get(k)}
                for k in new.params if new.params.get(k) != old.params.get(k)}

    # -- full pipeline ---------------------------------------------------
    def apply_supersession(self, proposal, dry_run, at_epoch,
                           activation_epoch):
        """PROPOSE → VERIFY → schedule ACTIVATE. The handoff completes at
        the epoch boundary via advance_epoch()."""
        self.propose(proposal)
        verdicts = self.verify(proposal, dry_run)
        return self.schedule_activation(proposal, verdicts, at_epoch,
                                        activation_epoch)


# ---------------------------------------------------------------------------
# VersionedLedger — the law-aware face of tokenomics.Ledger.
#
# Every computation is stamped with the law version under which it began.
# Fresh work under a yielded (SUPERSEDED) version refuses; in-flight work
# stamped before the handoff completes under its own stamp.
# ---------------------------------------------------------------------------
class VersionedLedger:
    def __init__(self, ledger, registry):
        self.ledger = ledger
        self.registry = registry

    def _law(self, version=None):
        v = version or self.registry.current().version
        return self.registry._assert_lawful(v)

    def _active_law(self, law, explicit):
        if law.status != LawVersion.ACTIVE:
            raise UnlawfulSupersession(
                f"law {law.version} is {law.status} — the old law has "
                "yielded; new work begins under the current law")
        return law

    def param(self, name, law_version=None):
        return self._law(law_version).value(name)

    def epoch_close(self, pool, merit_map=None, epoch=None,
                    law_version=None):
        """Epoch close under the given law (default: current). The
        computation is stamped with that law version.

        merit_map is UNTRUSTED input passed through to
        Ledger.emission_close: cross-checked against earned standing
        (exact restatement) and refused on any mismatch. None closes
        against every earner's standing."""
        law = self._law(law_version)
        self._active_law(law, law_version)
        out = self.ledger.emission_close(
            pool, merit_map, T.Figure(law.value("peg_ratio_E"), "MODELED"),
            epoch)
        out.law_version = law.version
        return out

    def disburse_under(self, pool, unity_id, amount, epoch, law_version):
        """In-flight rule: the stamp on the computation rules. A
        computation stamped under a lawfully-activated version completes
        under that version — including a SUPERSEDED one, for work that
        began before the handoff."""
        law = self._law(law_version)  # bypass detection still applies
        return self.ledger.disburse(pool, unity_id, amount, epoch)

    def apply_decay(self, unity_id, epochs, law_version=None):
        law = self._law(law_version)
        self._active_law(law, law_version)
        r = law.value("merit_decay_rate")
        return self.ledger.apply_decay(unity_id, epochs, T.Figure(r, "MODELED"))

    def build_receipt(self, unity_id, kind, detail, provenance, epoch,
                      law_version=None):
        """Build a tokenomics receipt stamped with the law version — the
        stamp is part of the receipt's detail, hence of its manifest hash."""
        law = self._law(law_version)
        stamped = dict(detail)
        stamped["law_version"] = law.version
        return T.Receipt.build(unity_id, kind, stamped, provenance, epoch,
                               self.ledger._chain_head)

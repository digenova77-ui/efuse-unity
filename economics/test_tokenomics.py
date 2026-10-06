"""
Tests for the tokenomics engine (~/workspace/unity-world/economics/).

All must pass. Testnet only. The suite proves the structural law:
  - no pre-funding possible
  - pool-to-pool impossible BY CONSTRUCTION (machinery absent)
  - mesh cannot mint (machinery absent; routes carry zero authority)
  - merit interest refused (machinery absent)
  - Merit TRANSFERABLE (David's word, 2026-10-06 ~3:35 AM EDT): ownership
    moves between Unity IDs, receipted; origin frozen at accrual — transfer
    receipts carry no origin fields; transfers are not interest
  - donation -> merit -> eFuse path absent (donations yield Honor only)
  - UNKNOWN merit emits zero, never a pass
  - every movement requires a unity_id (signature + runtime)

Run: python3 test_tokenomics.py
"""
import os
import sys
import base64
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# dclm compute core, for the provenance-register alignment check (worker 1)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "dclm")))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "core-rings")))

import tokenomics as T
import wallet as _wallet  # noqa: E402  (ephemeral emission keys, CRITICAL-4)
from tokenomics import (
    EFuse, Figure, HeldParameter, Honor, HonorConversionRefused, Ledger,
    Merit, MeritTransferAuthError, NonTransferableError, Receipt, Token,
    TokenomicsError, Unity, UnityBindingError, emission_calculator,
)


def v(value, prov="VERIFIED", note=""):
    return Figure(value, prov, note)


def modeled(value):
    return Figure(value, "MODELED", "testnet what-if — explicitly modeled")


def receipt(uid, kind="merit_accrual", provenance="VERIFIED", epoch=1,
            detail=None, prev="GENESIS"):
    return Receipt.build(uid, kind, detail or {"work": "test-fixture"},
                         provenance, epoch, prev)


_accrue_seq = [0]


def accrue(ledger, uid, amount, epoch=1, provenance="VERIFIED"):
    """Accrue merit with a unique receipt (distinct manifest per call)."""
    _accrue_seq[0] += 1
    r = receipt(uid, epoch=epoch,
                detail={"work": f"accrue-{uid}-{epoch}-{_accrue_seq[0]}"},
                provenance=provenance)
    return ledger.accrue_merit(
        uid, r, Figure(amount, provenance,
                       "test accrual weight"))


# -- S1b: sender-authorized transfer fixtures --------------------------
# Ledger Unity IDs are not key-derived ("u1", …), so transfer
# authorization binds via an EXPLICITLY registered transfer key
# (Ledger.register_transfer_key). Ephemeral Ed25519 keypairs, testnet
# only, /tmp via wallet._node_sign.
def _pub_b64(pub_der):
    return base64.b64encode(pub_der).decode()


def _funded_authed(uid="u1", amount=100.0, epoch=1):
    """A Ledger funded for uid with uid's transfer key registered.
    Returns (ledger, priv_der, pub_der)."""
    L = Ledger()
    accrue(L, uid, amount, epoch=epoch)
    priv, pub = _wallet.generate_test_keypair()
    L.register_transfer_key(uid, _pub_b64(pub))
    return L, priv, pub


def _signed_auth(priv, pub, from_id, to_id, amount, reason, nonce=None):
    """The sender's device signs the transfer authorization (the wallet
    path's canonical body — this ledger verifies the same shape)."""
    return _wallet.make_merit_transfer_auth(
        priv, pub, from_id, to_id, amount, reason, nonce=nonce)


def authed_transfer(L, from_id, to_id, amount, reason, epoch, priv, pub,
                    nonce=None):
    """Perform a lawful transfer_merit with a fresh sender signature."""
    return L.transfer_merit(
        from_id, to_id, amount, reason, epoch,
        auth=_signed_auth(priv, pub, from_id, to_id,
                          float(amount.value), reason, nonce=nonce))


# Machinery that must NOT exist — absence, not policy.
FORBIDDEN_MACHINERY = [
    "pool_to_pool", "transfer_pool", "move_between_pools",
    "mesh_mint", "mint",
    "fiat_to_efuse", "fiat_to_eFuse", "buy_efuse", "buy_eFuse",
    "convert_fiat", "fiat_to_honor_bypass",
    "accrue_interest", "merit_interest", "merit_yield", "stake_merit",
    "pre_fund", "seed_pool", "genesis_allocation",
    "reserve_disburse", "reserve_payout", "reserve_pay", "reserve_send",
    "reserve_transfer", "reserve_withdraw", "reserve_claim", "reserve_spend",
]


def assert_no_forbidden_machinery(testcase):
    names = [n.lower() for n in dir(T)]
    found = [f for f in FORBIDDEN_MACHINERY
             if any(f in n for n in names)]
    testcase.assertEqual(found, [],
                         f"forbidden machinery present: {found}")


# ---------------------------------------------------------------------------
class TestTokenClasses(unittest.TestCase):
    def test_trinity_kinds(self):
        self.assertEqual(EFuse().kind, "medium")
        self.assertEqual(Merit().kind, "measure")
        self.assertEqual(Unity().kind, "member")
        self.assertEqual(Honor().kind, "donation")

    def test_token_metadata_labeled_modeled(self):
        # Token classes implement a DESIGN doc (predicted, not sealed).
        for cls in (EFuse, Merit, Unity, Honor):
            d = cls().describe()
            self.assertEqual(d["provenance"], "MODELED")

    def test_merit_transferable(self):
        # David's word, 2026-10-06 ~3:35 AM EDT (LAW): Merit IS
        # transferable. The old non-transferable law is SUPERSEDED
        # (DECISIONS.md §13).
        self.assertTrue(Merit().transferable)
        self.assertTrue(Merit().describe()["transferable"])

    def test_merit_transfer_directs_to_canonical_path(self):
        # No DIRECT class-level transfer machinery exists (absence, not
        # policy — same pattern as EFuse.transfer). The refusal names
        # the canonical receipted path; it is NOT NonTransferableError.
        with self.assertRaises(T.TokenomicsError) as cm:
            Merit().transfer("u1", "u2", 10)
        self.assertNotIsInstance(cm.exception, NonTransferableError)
        self.assertIn("merit_transfer", str(cm.exception))

    def test_unity_non_transferable(self):
        # Living law (WALLET_DESIGN_LAW §7; DECISIONS.md §12): Unity is
        # the member — it never moves between identities.
        with self.assertRaises(NonTransferableError):
            Unity().transfer("u1", "u2", 1)

    def test_honor_non_transferable(self):
        # Living law: Honor is recognition, not currency — never moves.
        with self.assertRaises(NonTransferableError):
            Honor().transfer("u1", "u2", 1)

    def test_honor_never_converts_to_emission(self):
        with self.assertRaises(HonorConversionRefused):
            Honor().redeem_for_emission("u1", 100)
        self.assertFalse(Honor.converts_to_emission)

    def test_efuse_has_no_direct_transfer(self):
        # eFuse moves only through ledger movement functions — never
        # bought/sold, no market machinery.
        with self.assertRaises(T.TokenomicsError):
            EFuse().transfer("u1", "u2", 10)

    def test_base_token_is_abstract(self):
        self.assertIsInstance(EFuse(), Token)


# ---------------------------------------------------------------------------
class TestProvenanceRegister(unittest.TestCase):
    def test_labels_match_dclm_compute(self):
        from compute import PROVENANCE_LABELS as DCLM_LABELS
        self.assertEqual(T.PROVENANCE_LABELS, DCLM_LABELS)

    def test_figure_rejects_bad_provenance(self):
        with self.assertRaises(ValueError):
            Figure(1.0, "TRUST_ME")

    def test_unsigned_number_is_unknown(self):
        f = T._as_figure(42.0, "x")
        self.assertEqual(f.provenance, "UNKNOWN")


# ---------------------------------------------------------------------------
class TestEmissionCalculator(unittest.TestCase):
    def _calc(self, pool, merit, peg, auth, **kw):
        # The merit map restates the standing source exactly — the
        # cross-check passes and weights derive from standing.
        kw.setdefault("standing_source", dict(merit))
        return emission_calculator(pool, merit, peg, auth, **kw)

    def test_merit_weighted_split(self):
        merit = {"u1": v(300), "u2": v(100)}
        out = self._calc("human", merit, modeled(1000.0),
                         v(50_000_000.0, "DERIVED"))
        self.assertAlmostEqual(out.per_member["u1"].value, 0.30)
        self.assertAlmostEqual(out.per_member["u2"].value, 0.10)
        self.assertAlmostEqual(out.total.value, 0.40)
        self.assertFalse(out.authority_cap_applied)
        self.assertEqual(out.provenance, "MODELED")  # modeled peg in
        self.assertTrue(out.canonical_sha256)

    def test_authority_cap_scales_uniformly(self):
        merit = {"u1": v(300), "u2": v(100)}
        out = self._calc("human", merit, modeled(1000.0),
                         v(0.20, "DERIVED"))
        self.assertTrue(out.authority_cap_applied)
        self.assertAlmostEqual(out.total.value, 0.20)
        # 3:1 ratio preserved under the cap
        self.assertAlmostEqual(out.per_member["u1"].value,
                               out.per_member["u2"].value * 3)

    def test_no_standing_zero_emission(self):
        out = self._calc("human", {}, modeled(1000.0),
                         v(50_000_000.0, "DERIVED"))
        self.assertEqual(out.total.value, 0.0)
        self.assertEqual(out.per_member, {})

    def test_zero_standing_excluded(self):
        # A stated zero-standing identity is excluded — nothing earned,
        # nothing emitted.
        merit = {"u1": v(300), "u2": v(0)}
        out = self._calc("human", merit, modeled(1000.0),
                         v(50_000_000.0, "DERIVED"))
        self.assertNotIn("u2", out.per_member)
        self.assertEqual(out.excluded["u2"], "DERIVED")
        self.assertAlmostEqual(out.total.value, 0.30)

    def test_untrusted_map_with_junk_refused(self):
        # UNKNOWN/REPORTED claims in the caller map are not filtered —
        # the map must restate standing exactly, so junk REFUSES.
        # UNKNOWN never pays, never scores — now structurally.
        standing = {"u1": v(300)}
        junk = {"u1": v(300),
                "u2": Figure(500.0, "UNKNOWN", "unverified claim"),
                "u3": v(100, "REPORTED", "claimed but ungated")}
        with self.assertRaises(T.UntrustedMeritMapError):
            emission_calculator("human", junk, modeled(1000.0),
                                v(50_000_000.0, "DERIVED"),
                                standing_source=dict(standing))
        # the honest restatement computes
        out = self._calc("human", standing, modeled(1000.0),
                         v(50_000_000.0, "DERIVED"))
        self.assertAlmostEqual(out.total.value, 0.30)
        self.assertNotIn("u2", out.per_member)
        self.assertNotIn("u3", out.per_member)

    def test_all_junk_map_refused(self):
        with self.assertRaises(T.UntrustedMeritMapError):
            emission_calculator("human", {"u1": Figure(999.0, "UNKNOWN")},
                                modeled(1000.0),
                                v(50_000_000.0, "DERIVED"),
                                standing_source={})

    def test_standing_source_required(self):
        # No standing source -> refusal. A caller-supplied merit map
        # alone never drives emission weights.
        with self.assertRaises(T.TokenomicsError):
            emission_calculator("human", {"u1": v(100)}, modeled(1000.0),
                                v(50_000_000.0, "DERIVED"))

    def test_unknown_standing_source_refused(self):
        # Standing is earned history — an UNKNOWN standing claim in the
        # trusted source is refused, not filtered.
        with self.assertRaises(T.TokenomicsError):
            emission_calculator("human", None, modeled(1000.0),
                                v(50_000_000.0, "DERIVED"),
                                standing_source={"u1": Figure(5.0, "UNKNOWN")})

    def test_held_peg_refuses(self):
        with self.assertRaises(T.HeldParameterError):
            self._calc("human", {"u1": v(100)},
                       HeldParameter("peg_ratio_E"),
                       v(50_000_000.0, "DERIVED"))

    def test_unsigned_peg_refuses(self):
        # A bare number is an unsigned claim -> UNKNOWN -> refusal.
        with self.assertRaises(T.HeldParameterError):
            self._calc("human", {"u1": v(100)}, 1000.0,
                       v(50_000_000.0, "DERIVED"))

    def test_unknown_authority_refuses(self):
        with self.assertRaises(T.UnknownFigureError):
            self._calc("human", {"u1": v(100)}, modeled(1000.0),
                       Figure(50_000_000.0, "UNKNOWN"))

    def test_unknown_pool_refused(self):
        with self.assertRaises(ValueError):
            self._calc("sideways", {"u1": v(100)}, modeled(1000.0),
                       v(1.0, "DERIVED"))

    def test_anonymous_merit_key_refused(self):
        with self.assertRaises(UnityBindingError):
            self._calc("human", {"": v(100)}, modeled(1000.0),
                       v(50_000_000.0, "DERIVED"))

    def test_reserve_holdback_inactive_while_held(self):
        out = self._calc("human", {"u1": v(100)}, modeled(1000.0),
                         v(50_000_000.0, "DERIVED"))
        self.assertEqual(out.reserve_held.value, 0.0)
        self.assertIn("HELD_FOR_DAVID", out.reserve_held.note)

    def test_verified_peg_gives_derived_outputs(self):
        out = self._calc("machine", {"m1": v(50)},
                         v(1000.0, "VERIFIED"),
                         v(50_000_000.0, "DERIVED"))
        self.assertEqual(out.provenance, "DERIVED")
        self.assertAlmostEqual(out.per_member["m1"].value, 0.05)


# ---------------------------------------------------------------------------
class TestPegRegulationReserve(unittest.TestCase):
    """Gauntlet E13: Peg Regulation Reserve absorb/release machinery.

    - Absorb diverts fraction x computed emission to the per-pool Reserve
      (receipted, never disbursed).
    - Release re-injects held funds through the same merit-weighted,
      Unity-bound gate (receipted).
    - The holdback fraction is HELD_FOR_DAVID: unset -> HeldParameterError —
      never an invented digit, never a silent pass-through.
    - The Reserve is per-pool (never a sixth pool), never double-counted,
      and structurally incapable of disbursing to members (absence of path,
      not a policy check).
    """

    def _close_absorb(self, L, epoch=1, fraction=0.25, pool="human",
                      merits=None):
        merits = ({"u1": 300.0, "u2": 100.0} if merits is None
                  else merits)
        # Accrue first: standing is the emission weight source. The
        # explicit map restates standing exactly (cross-check path).
        # Accepts raw amounts or Figures.
        amounts = {uid: (a.value if isinstance(a, Figure) else a)
                   for uid, a in merits.items()}
        for uid, amt in amounts.items():
            accrue(L, uid, amt, epoch=epoch)
        restated = {uid: v(L.standing(uid).value) for uid in amounts}
        return L.emission_close(pool, restated, modeled(1000.0), epoch=epoch,
                                holdback_fraction=modeled(fraction))

    def test_absorb_diverts_excess_with_modeled_fraction(self):
        L = Ledger()
        out = self._close_absorb(L)
        # gross 0.40; holdback 0.10; disbursable 0.30 — all MODELED
        self.assertAlmostEqual(out.total.value, 0.40)
        self.assertAlmostEqual(out.reserve_held.value, 0.10)
        self.assertEqual(out.reserve_held.provenance, "MODELED")
        self.assertAlmostEqual(
            sum(f.value for f in out.per_member.values()), 0.30)
        # 3:1 merit ratio preserved through the absorb
        self.assertAlmostEqual(out.per_member["u1"].value,
                               out.per_member["u2"].value * 3)
        # ledger: reserve credited, nothing disbursed
        self.assertAlmostEqual(L.reserve["human"], 0.10)
        self.assertAlmostEqual(L.reserve_balance("human").value, 0.10)
        self.assertEqual(L.emitted["human"], 0.0)
        # receipted like any other movement (L5-visible in the chain)
        absorbs = [r for r in L.receipts
                   if r.kind == "reserve" and r.detail["direction"] == "absorb"]
        self.assertEqual(len(absorbs), 1)
        self.assertAlmostEqual(absorbs[0].detail["amount"], 0.10)
        self.assertEqual(absorbs[0].detail["pool"], "human")
        self.assertAlmostEqual(absorbs[0].detail["reserve_balance_after"], 0.10)
        self.assertEqual(absorbs[0].detail["fraction_provenance"], "MODELED")

    def test_absorb_never_double_counted(self):
        L = Ledger()
        out = self._close_absorb(L)
        # total + released == sum(per_member) + held
        self.assertAlmostEqual(
            out.total.value + out.reserve_released.value,
            sum(f.value for f in out.per_member.values())
            + out.reserve_held.value)

    def test_absorb_refuses_unset_fraction(self):
        L = Ledger()
        accrue(L, "u1", 100.0, epoch=1)
        merits = {"u1": v(100.0)}
        # HeldParameter, the held registry entry, UNKNOWN, and bare numbers
        # all refuse — the machinery never invents a fraction and never
        # silently passes through.
        for bad in (HeldParameter("reserve_holdback_fraction"),
                    T.PARAMS["reserve_holdback_fraction"],
                    Figure(0.25, "UNKNOWN"),
                    0.25):
            with self.assertRaises(T.HeldParameterError, msg=repr(bad)):
                emission_calculator("human", merits, modeled(1000.0),
                                    v(50_000_000.0, "DERIVED"),
                                    holdback_fraction=bad,
                                    standing_source=dict(merits))
            with self.assertRaises(T.HeldParameterError, msg=repr(bad)):
                L.emission_close("human", merits, modeled(1000.0), epoch=1,
                                 holdback_fraction=bad)
        # The refused attempts left no trace: no balance, no receipts.
        self.assertEqual(L.reserve["human"], 0.0)
        self.assertEqual([r for r in L.receipts if r.kind == "reserve"], [])

    def test_absorb_refuses_out_of_range_fraction(self):
        merits = {"u1": v(100.0)}
        for bad in (-0.1, 1.0, 2.0):
            with self.assertRaises(ValueError, msg=repr(bad)):
                emission_calculator("human", merits, modeled(1000.0),
                                    v(50_000_000.0, "DERIVED"),
                                    holdback_fraction=modeled(bad),
                                    standing_source=dict(merits))

    def test_no_fraction_no_machinery(self):
        # Not engaged -> the labeled zero, no receipt, no refusal.
        L = Ledger()
        accrue(L, "u1", 100.0, epoch=1)
        out = L.emission_close("human", None, modeled(1000.0), epoch=1)
        self.assertEqual(out.reserve_held.value, 0.0)
        self.assertIn("HELD_FOR_DAVID", out.reserve_held.note)
        self.assertEqual(out.reserve_released.value, 0.0)
        self.assertEqual(L.reserve["human"], 0.0)
        self.assertEqual([r for r in L.receipts if r.kind == "reserve"], [])

    def test_release_returns_held_funds_through_same_gate(self):
        L = Ledger()
        e1 = self._close_absorb(L, epoch=1)
        self.assertAlmostEqual(L.reserve["human"], 0.10)
        e2 = L.emission_close("human", {"u1": v(300.0), "u2": v(100.0)},
                              modeled(1000.0), epoch=2,
                              reserve_release=modeled(0.10))
        # full release, MODELED-labeled
        self.assertAlmostEqual(e2.reserve_released.value, 0.10)
        self.assertEqual(e2.reserve_released.provenance, "MODELED")
        self.assertAlmostEqual(L.reserve["human"], 0.0)
        # payout = 0.40 fresh + 0.10 released = 0.50, merit-weighted 3:1
        self.assertAlmostEqual(
            sum(f.value for f in e2.per_member.values()), 0.50)
        self.assertAlmostEqual(e2.per_member["u1"].value,
                               e2.per_member["u2"].value * 3)
        # release receipted
        rels = [r for r in L.receipts
                if r.kind == "reserve" and r.detail["direction"] == "release"]
        self.assertEqual(len(rels), 1)
        self.assertAlmostEqual(rels[0].detail["amount"], 0.10)
        self.assertAlmostEqual(rels[0].detail["reserve_balance_after"], 0.0)
        # disbursing the shares lands exactly the computed amounts
        for uid, fig in e1.per_member.items():
            L.disburse("human", uid, fig, epoch=1)
        for uid, fig in e2.per_member.items():
            L.disburse("human", uid, fig, epoch=2)
        self.assertAlmostEqual(L.emitted["human"], 0.30 + 0.50)

    def test_release_capped_at_balance(self):
        L = Ledger()
        self._close_absorb(L, epoch=1, fraction=0.5,
                           merits={"u1": v(100.0)})  # holds 0.05 of 0.10
        e2 = L.emission_close("human", {"u1": v(100.0)}, modeled(1000.0),
                              epoch=2, reserve_release=modeled(999.0))
        self.assertAlmostEqual(e2.reserve_released.value, 0.05)
        self.assertAlmostEqual(L.reserve["human"], 0.0)
        self.assertIn("capped", e2.reserve_released.note)

    def test_release_refuses_unknown_amount(self):
        L = Ledger()
        self._close_absorb(L, epoch=1)
        with self.assertRaises(T.UnknownFigureError):
            L.emission_close("human", {"u1": v(300.0), "u2": v(100.0)},
                             modeled(1000.0),
                             epoch=2, reserve_release=Figure(0.05, "UNKNOWN"))

    def test_release_held_when_merit_gate_closed(self):
        L = Ledger()
        self._close_absorb(L, epoch=1)
        bal = L.reserve["human"]
        self.assertGreater(bal, 0.0)
        e2 = L.emission_close("human", {}, modeled(1000.0), epoch=2,
                              reserve_release=modeled(bal))
        # Not dropped silently: held, noted, reserve untouched.
        self.assertEqual(e2.reserve_released.value, 0.0)
        self.assertAlmostEqual(L.reserve["human"], bal)
        self.assertIn("HELD", e2.note)

    def test_reserve_is_per_pool_never_sixth(self):
        L = Ledger()
        self._close_absorb(L, epoch=1, pool="human")
        self._close_absorb(L, epoch=1, pool="machine",
                           merits={"m1": v(100.0)}, fraction=0.5)
        self.assertEqual(set(L.reserve.keys()), {"human", "machine"})
        self.assertEqual(set(T.POOLS), {"human", "machine"})
        self.assertAlmostEqual(L.reserve["human"], 0.10)
        self.assertAlmostEqual(L.reserve["machine"], 0.05)
        # machine-pool absorb did not touch the human pool's authority
        self.assertAlmostEqual(
            L.remaining_authority("human").value, 50_000_000.0)

    def test_reserve_never_leaks_to_members(self):
        L = Ledger()
        out = self._close_absorb(L, epoch=1)
        held = out.reserve_held.value
        self.assertGreater(held, 0.0)
        # No named path pays a member from the Reserve — on the module or
        # on the Ledger. Absence, not policy.
        for name in ("reserve_disburse", "pay_from_reserve", "reserve_payout",
                     "reserve_transfer", "reserve_withdraw", "reserve_claim",
                     "reserve_send", "reserve_spend"):
            self.assertFalse(hasattr(T, name), name)
            self.assertFalse(hasattr(Ledger, name), name)
        assert_no_forbidden_machinery(self)
        # Disbursing the computed shares moves exactly the disbursable
        # amount; the held amount stays held.
        for uid, fig in out.per_member.items():
            L.disburse("human", uid, fig, epoch=1)
        self.assertAlmostEqual(L.emitted["human"], out.total.value - held)
        self.assertAlmostEqual(L.reserve["human"], held)

    def test_reserve_balance_never_flows_to_disburse(self):
        # Structural proof via AST: self.reserve is touched only by
        # __init__ (create), reserve_balance (read), emission_close
        # (absorb/release), and state_digest (read). No disbursement path
        # reads it — the Reserve is incapable of paying members by
        # construction, not by a runtime check.
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(Ledger))
        touches = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Attribute)
                            and isinstance(sub.value, ast.Name)
                            and sub.value.id == "self"
                            and sub.attr == "reserve"):
                        touches.add(node.name)
        allowed = {"__init__", "reserve_balance", "emission_close",
                   "state_digest"}
        self.assertEqual(touches - allowed, set(),
                         f"unexpected self.reserve touches: {touches - allowed}")
        self.assertTrue(allowed <= touches)

    def test_absorb_receipts_chain_with_rest(self):
        L = Ledger()
        self._close_absorb(L, epoch=1)
        kinds = [r.kind for r in L.receipts]
        self.assertIn("reserve", kinds)
        for r in L.receipts:
            self.assertTrue(r.manifest_hash)
        self.assertNotEqual(L.state_digest(), Ledger().state_digest())


# ---------------------------------------------------------------------------
class TestNoPreFunding(unittest.TestCase):
    def test_ledger_starts_empty(self):
        L = Ledger()
        self.assertEqual(L.emitted, {"human": 0.0, "machine": 0.0})
        self.assertEqual(L.reserve, {"human": 0.0, "machine": 0.0})
        self.assertEqual(L.lock_balance, 0.0)
        self.assertEqual(L.remaining_authority("human").value, 50_000_000.0)
        self.assertEqual(L.remaining_authority("machine").value, 50_000_000.0)
        self.assertEqual(L.remaining_authority("human").provenance, "DERIVED")

    def test_epoch_close_without_receipts_emits_zero(self):
        L = Ledger()
        out = L.emission_close("human", {}, modeled(1000.0), epoch=1)
        self.assertEqual(out.total.value, 0.0)
        self.assertEqual(L.emitted["human"], 0.0)

    def test_disbursement_without_computation_refused(self):
        L = Ledger()
        # Nothing computed, nothing to disburse against — and disbursing
        # more than remaining authority is refused by construction.
        with self.assertRaises(T.AuthorityExceededError):
            L.disburse("human", "u1", v(50_000_001.0, "DERIVED"), epoch=1)


# ---------------------------------------------------------------------------
class TestLedgerFlows(unittest.TestCase):
    def test_accrue_merit_happy_path(self):
        L = Ledger()
        r = receipt("u1")
        c = L.accrue_merit("u1", r, modeled(10.0))
        self.assertEqual(c.unity_id, "u1")
        self.assertEqual(c.amount.value, 10.0)
        self.assertAlmostEqual(L.merit_balance("u1").value, 10.0)

    def test_accrue_merit_requires_receipt(self):
        L = Ledger()
        with self.assertRaises(T.ReceiptRequiredError):
            L.accrue_merit("u1", None, modeled(10.0))

    def test_accrue_merit_requires_verified_receipt(self):
        L = Ledger()
        r = receipt("u1", provenance="REPORTED")
        with self.assertRaises(T.ReceiptRequiredError):
            L.accrue_merit("u1", r, modeled(10.0))

    def test_accrue_merit_receipt_unity_binding(self):
        L = Ledger()
        r = receipt("u1")
        with self.assertRaises(UnityBindingError):
            L.accrue_merit("u2", r, modeled(10.0))

    def test_receipt_idempotency(self):
        L = Ledger()
        r = receipt("u1")
        L.accrue_merit("u1", r, modeled(10.0))
        with self.assertRaises(T.DuplicateReceiptError):
            L.accrue_merit("u1", r, modeled(5.0))
        # Balance unchanged by the refused double-apply.
        self.assertAlmostEqual(L.merit_balance("u1").value, 10.0)

    def test_decay_refuses_without_rate(self):
        L = Ledger()
        L.accrue_merit("u1", receipt("u1"), modeled(100.0))
        with self.assertRaises(T.HeldParameterError):
            L.apply_decay("u1", 1)

    def test_decay_with_explicit_modeled_rate(self):
        L = Ledger()
        L.accrue_merit("u1", receipt("u1"), modeled(100.0))
        out = L.apply_decay("u1", 2, rate=modeled(0.5))
        self.assertAlmostEqual(out.value, 25.0)
        self.assertEqual(out.provenance, "MODELED")
        self.assertAlmostEqual(L.merit_balance("u1").value, 25.0)

    def test_merit_interest_machinery_absent(self):
        assert_no_forbidden_machinery(self)

    def test_full_epoch_flow(self):
        L = Ledger()
        L.accrue_merit("u1", receipt("u1"), modeled(300.0))
        L.accrue_merit("u2", receipt("u2"), modeled(100.0))
        merits = {"u1": v(300.0), "u2": v(100.0)}
        out = L.emission_close("human", merits, modeled(1000.0), epoch=1)
        for uid, fig in out.per_member.items():
            L.disburse("human", uid, fig, epoch=1)
        self.assertAlmostEqual(L.emitted["human"], 0.40)
        self.assertAlmostEqual(
            L.remaining_authority("human").value, 50_000_000.0 - 0.40)

    def test_disburse_over_authority_refused(self):
        L = Ledger()
        with self.assertRaises(T.AuthorityExceededError):
            L.disburse("machine", "m1", v(50_000_000.01, "DERIVED"), epoch=1)


class TestDisbursementSignatureBinding(unittest.TestCase):
    """CRITICAL-4: tokenomics disbursement receipts are cryptographically
    bound to the emission authority (this Ledger). Every issued
    disbursement carries the authority's Ed25519 signature over its
    canonical body; tampering or forging breaks verification."""

    def test_disburse_receipt_is_signed_and_verifies(self):
        L = Ledger()
        r = L.disburse("human", "u1", v(10.0, "DERIVED"), epoch=1)
        self.assertTrue(r.emitter_signature)
        self.assertEqual(r.emitter_key_id, _wallet.EMISSION_AUTHORITY_KEY_ID)
        self.assertTrue(L.disbursement_signature_valid(r))

    def test_tampered_disbursement_fails_verification(self):
        import dataclasses
        L = Ledger()
        r = L.disburse("human", "u1", v(10.0, "DERIVED"), epoch=1)
        tampered = dataclasses.replace(
            r, detail={**r.detail, "amount": 10_000_000.0})
        self.assertFalse(L.disbursement_signature_valid(tampered))
        # The ledger's own stored receipt still verifies — the tamper
        # was on the copy, not the record.
        self.assertTrue(L.disbursement_signature_valid(r))

    def test_forged_disbursement_signature_fails(self):
        """A receipt 'signed' by an attacker's key is not the authority's."""
        import dataclasses
        L = Ledger()
        r = L.disburse("human", "u1", v(10.0, "DERIVED"), epoch=1)
        attacker_priv, _ = _wallet.generate_test_keypair()
        forged_body = L._disbursement_signing_body(r)
        forged = _wallet.sign_emission_receipt(
            forged_body, attacker_priv, L.emission_authority_key_id)
        forged_receipt = dataclasses.replace(
            r, emitter_signature=forged["emitter_signature"],
            emitter_key_id=forged["emitter_key_id"])
        self.assertFalse(L.disbursement_signature_valid(forged_receipt))

    def test_ephemeral_authority_keypair(self):
        """A ledger constructed with an ephemeral authority keypair signs
        with it — and its receipts do NOT verify against the default
        testnet authority."""
        priv, pub = _wallet.generate_test_keypair()
        L = Ledger(emission_privkey_der=priv, emission_pubkey_der=pub,
                   emission_authority_key_id="test-ephemeral-authority")
        r = L.disburse("human", "u1", v(10.0, "DERIVED"), epoch=1)
        self.assertEqual(r.emitter_key_id, "test-ephemeral-authority")
        self.assertTrue(L.disbursement_signature_valid(r))
        default_ledger = Ledger()  # testnet authority keys
        self.assertFalse(default_ledger.disbursement_signature_valid(r))

    def test_unsigned_receipt_never_verifies(self):
        L = Ledger()
        r = receipt("u1", kind="disbursement", epoch=1)  # built, not issued
        self.assertFalse(L.disbursement_signature_valid(r))

    def test_cause_disburse_receipt_is_signed(self):
        """F6 Lock disbursements are bound too: cause_disburse signs its
        receipt, and the wallet-side path verifies the same envelope."""
        L = Ledger()
        L.donate("donor", modeled(50.0), "efuse", epoch=1)
        work = receipt("doer", detail={"work": "cause-work"})
        r = L.cause_disburse("doer", modeled(10.0), work, epoch=2)
        self.assertEqual(r.kind, "cause_disbursement")
        self.assertTrue(r.emitter_signature)
        self.assertTrue(L.disbursement_signature_valid(r))

    def test_wallet_accepts_authority_signed_emission_receipt(self):
        """End to end across the two ledgers: the tokenomics ledger is the
        lawful emitter; the wallet ledger (registered with the same
        authority pubkey) credits the signed receipt."""
        priv, pub = _wallet.generate_test_keypair()
        tledger = Ledger(emission_privkey_der=priv, emission_pubkey_der=pub,
                         emission_authority_key_id="test-e2e-authority")
        wledger = _wallet.Ledger(emission_authority_pubkey_der=pub,
                                 emission_authority_key_id="test-e2e-authority")
        # (wallets bind owner keys; use a fresh owner key for the wallet)
        import base64 as _b64mod
        opriv, opub = _wallet.generate_test_keypair()
        ouid = _wallet.derive_unity_id(opub)
        w = wledger.new_wallet(ouid, _b64mod.b64encode(opub).decode())
        tledger.disburse("human", ouid, v(50.0, "DERIVED"), epoch=3)
        body = {
            "kind": "merit-emission",
            "manifest_hash": "mh-e2e-1",
            "unity_id": ouid,
            "token": "eFuse",
            "amount": 50,
            "pool": "human",
            "merit_weight": 3,
            "gated": True,
            "epoch": 3,
            "provenance": "REPORTED",
        }
        signed = _wallet.sign_emission_receipt(
            body, priv, "test-e2e-authority")
        _wallet.receive_emission(w, 50, signed)
        self.assertEqual(w.balances()["eFuse"]["amount"], 50)


# ---------------------------------------------------------------------------
class TestMeritTransfer(unittest.TestCase):
    """David's word, 2026-10-06 ~3:35 AM EDT (LAW): Merit IS transferable.
    Transfers move OWNERSHIP (economic value) between Unity IDs; origin/
    earned-history is frozen at accrual and never moves with the token —
    this ledger holds owned balances only and carries no origin fields.

    S1b (2026-10-06): every transfer is SENDER-AUTHORIZED. This ledger's
    IDs are not key-derived ("u1", …), so authorization binds via an
    explicitly registered transfer key: no auth / unregistered sender /
    wrong key / body mismatch / bad signature / replayed nonce is
    refused — the public Unity ID alone authorizes nothing."""

    def test_transfer_moves_ownership(self):
        L, priv, pub = _funded_authed()
        r = authed_transfer(L, "u1", "u2", modeled(40.0), "sale", 2,
                            priv, pub)
        self.assertEqual(r.kind, "merit_transfer")
        self.assertAlmostEqual(L.merit_balance("u1").value, 60.0)
        self.assertAlmostEqual(L.merit_balance("u2").value, 40.0)

    def test_transfer_receipt_carries_reason_and_sides(self):
        L, priv, pub = _funded_authed()
        r = authed_transfer(L, "u1", "u2", modeled(25.0), "gift", 2,
                            priv, pub)
        self.assertEqual(r.detail["from"], "u1")
        self.assertEqual(r.detail["to"], "u2")
        self.assertEqual(r.detail["reason"], "gift")
        self.assertAlmostEqual(r.detail["sender_owned_after"], 75.0)
        self.assertAlmostEqual(r.detail["recipient_owned_after"], 25.0)
        # the authorization is linked on the receipt (audit trail)
        self.assertIn("auth_nonce", r.detail)
        self.assertIn("sender_key_sha256", r.detail)

    def test_transfer_receipt_carries_no_origin(self):
        # Structural, in code: origin fields are frozen at accrual and
        # never move with the token — this ledger must never carry them.
        L, priv, pub = _funded_authed()
        r = authed_transfer(L, "u1", "u2", modeled(10.0), "sale", 2,
                            priv, pub)
        for key in r.detail:
            self.assertNotIn("origin", key.lower(),
                             f"origin key on transfer receipt: {key!r}")
        for key in r.__dict__:
            self.assertNotIn("origin", key.lower())

    def test_transfer_insufficient_owned_refused(self):
        L, priv, pub = _funded_authed(amount=100.0)
        with self.assertRaises(T.TokenomicsError):
            authed_transfer(L, "u1", "u2", modeled(150.0), "sale", 2,
                            priv, pub)
        # Refused transfer moves nothing.
        self.assertAlmostEqual(L.merit_balance("u1").value, 100.0)
        self.assertAlmostEqual(L.merit_balance("u2").value, 0.0)

    def test_transfer_requires_two_distinct_identities(self):
        L, priv, pub = _funded_authed()
        with self.assertRaises(T.TokenomicsError):
            authed_transfer(L, "u1", "u1", modeled(10.0), "sale", 2,
                            priv, pub)

    def test_transfer_requires_nonempty_reason(self):
        L, priv, pub = _funded_authed()
        for bad in ("", "   "):
            auth = _signed_auth(priv, pub, "u1", "u2", 10.0, "sale")
            with self.assertRaises(T.TokenomicsError, msg=f"{bad!r}"):
                L.transfer_merit("u1", "u2", modeled(10.0), bad, epoch=2,
                                 auth=auth)

    def test_transfer_rejects_unknown_amount(self):
        L, priv, pub = _funded_authed()
        auth = _signed_auth(priv, pub, "u1", "u2", 10.0, "sale")
        # UNKNOWN/unsigned amounts never move value — refusal either way.
        with self.assertRaises(T.UnknownFigureError):
            L.transfer_merit("u1", "u2", Figure(10.0, "UNKNOWN"), "sale",
                             epoch=2, auth=auth)
        with self.assertRaises(T.UnknownFigureError):
            L.transfer_merit("u1", "u2", HeldParameter("merit_weight"),
                             "sale", epoch=2, auth=auth)

    def test_transfer_requires_unity_binding(self):
        L, priv, pub = _funded_authed()
        with self.assertRaises(UnityBindingError):
            authed_transfer(L, "", "u2", modeled(10.0), "sale", 2,
                            priv, pub)
        with self.assertRaises(UnityBindingError):
            authed_transfer(L, "u1", None, modeled(10.0), "sale", 2,
                            priv, pub)

    def test_transfer_nonpositive_amount_refused(self):
        L, priv, pub = _funded_authed()
        with self.assertRaises(ValueError):
            authed_transfer(L, "u1", "u2", modeled(0.0), "sale", 2,
                            priv, pub)

    def test_transfer_chains_in_receipt_log(self):
        L, priv, pub = _funded_authed()
        r1 = authed_transfer(L, "u1", "u2", modeled(10.0), "sale", 2,
                             priv, pub)
        r2 = L.mesh_route("u2", "human", "m-xfer-1", epoch=2)
        # The accrual receipt came first (GENESIS is behind it); the
        # transfer chains forward from the accrual and the mesh route
        # chains from the transfer.
        self.assertEqual(r2.prev_hash, r1.manifest_hash)
        self.assertNotEqual(r1.prev_hash, "GENESIS")

    def test_transfer_is_not_interest(self):
        # A transfer does not create merit — the ledger total is
        # conserved. Merit grows only via gated receipts.
        L, priv, pub = _funded_authed(amount=100.0)
        L.accrue_merit("u2", receipt("u2"), modeled(50.0))
        authed_transfer(L, "u1", "u2", modeled(40.0), "sale", 2,
                        priv, pub)
        total = (L.merit_balance("u1").value + L.merit_balance("u2").value)
        self.assertAlmostEqual(total, 150.0)


# ---------------------------------------------------------------------------
class TestMeritTransferAuthorization(unittest.TestCase):
    """S1b: the keyless drain is closed on the Ledger path. The gauntlet's
    reproducer shape — transfer_merit('victim','attacker',…) with NO
    auth — must refuse. Forged, tampered, and replayed authorizations
    must refuse too; a refused transfer never burns the nonce."""

    def _victim(self):
        return _funded_authed(uid="victim", amount=100.0)

    def test_no_auth_keyless_drain_refused(self):
        # THE S1 residual, reproduced and closed: the keyless call shape
        # that drained 100 -> 40 before S1b now refuses.
        L, _, _ = self._victim()
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("victim", "attacker", modeled(60.0),
                             "theft", epoch=2)
        # Nothing moved.
        self.assertAlmostEqual(L.merit_balance("victim").value, 100.0)
        self.assertAlmostEqual(L.merit_balance("attacker").value, 0.0)

    def test_none_and_malformed_auth_refused(self):
        L, _, _ = self._victim()
        for bad in (None, "signed-ok", {}, {"signature": "x"},
                    {"signature": "x", "nonce": "n"}):
            with self.assertRaises(MeritTransferAuthError, msg=f"{bad!r}"):
                L.transfer_merit("victim", "attacker", modeled(60.0),
                                 "theft", epoch=2, auth=bad)

    def test_unregistered_sender_refused(self):
        # A stranger holds no registered key — even their own valid
        # signature authorizes nothing here.
        L, vpriv, vpub = self._victim()
        apriv, apub = _wallet.generate_test_keypair()
        auth = _signed_auth(apriv, apub, "attacker", "victim", 10.0,
                            "theft")
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("attacker", "victim", modeled(10.0),
                             "theft", epoch=2, auth=auth)

    def test_attacker_cannot_sign_as_victim(self):
        # The attacker builds an auth naming the victim's registered key
        # but signs with their OWN private key — verification fails.
        L, vpriv, vpub = self._victim()
        apriv, apub = _wallet.generate_test_keypair()
        forged = _signed_auth(apriv, apub, "victim", "attacker", 60.0,
                              "theft")
        forged["pubkey_b64"] = _pub_b64(vpub)  # lie about the key
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("victim", "attacker", modeled(60.0),
                             "theft", epoch=2, auth=forged)
        # Wrong declared key (attacker's own) is a key mismatch, not a
        # crypto pass.
        mismatched = _signed_auth(apriv, apub, "victim", "attacker",
                                  60.0, "theft")
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("victim", "attacker", modeled(60.0),
                             "theft", epoch=2, auth=mismatched)
        self.assertAlmostEqual(L.merit_balance("victim").value, 100.0)

    def test_tampered_body_refused(self):
        # The signature binds the exact intent: a different amount,
        # recipient, or reason fails body verification.
        L, vpriv, vpub = self._victim()
        for tampered_amount in (61.0, 60.0000001):
            auth = _signed_auth(vpriv, vpub, "victim", "attacker",
                                 60.0, "theft")
            with self.assertRaises(MeritTransferAuthError):
                L.transfer_merit("victim", "attacker",
                                 modeled(tampered_amount), "theft",
                                 epoch=2, auth=auth)
        auth = _signed_auth(vpriv, vpub, "victim", "attacker", 60.0,
                            "theft")
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("victim", "attacker", modeled(60.0),
                             "sale", epoch=2, auth=auth)
        self.assertAlmostEqual(L.merit_balance("victim").value, 100.0)

    def test_bad_signature_refused(self):
        L, vpriv, vpub = self._victim()
        auth = _signed_auth(vpriv, vpub, "victim", "attacker", 60.0,
                            "theft")
        sig = bytearray(base64.b64decode(auth["signature"]))
        sig[0] ^= 0xFF
        auth["signature"] = base64.b64encode(bytes(sig)).decode()
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("victim", "attacker", modeled(60.0),
                             "theft", epoch=2, auth=auth)
        self.assertAlmostEqual(L.merit_balance("victim").value, 100.0)

    def test_replay_refused(self):
        L, vpriv, vpub = self._victim()
        auth = _signed_auth(vpriv, vpub, "victim", "attacker", 60.0,
                            "theft", nonce="one-shot-nonce")
        r = L.transfer_merit("victim", "attacker", modeled(60.0),
                             "theft", epoch=2, auth=auth)
        self.assertEqual(r.kind, "merit_transfer")
        with self.assertRaises(MeritTransferAuthError):
            L.transfer_merit("victim", "attacker", modeled(60.0),
                             "theft", epoch=3, auth=auth)
        # the replay moved nothing more
        self.assertAlmostEqual(L.merit_balance("victim").value, 40.0)
        self.assertAlmostEqual(L.merit_balance("attacker").value, 60.0)

    def test_refused_transfer_does_not_burn_nonce(self):
        # An authorization refused on balance grounds is NOT consumed:
        # the same auth retries cleanly once the balance covers it.
        L, vpriv, vpub = self._victim()
        auth = _signed_auth(vpriv, vpub, "victim", "attacker", 150.0,
                            "sale", nonce="retryable-nonce")
        with self.assertRaises(T.TokenomicsError):
            L.transfer_merit("victim", "attacker", modeled(150.0),
                             "sale", epoch=2, auth=auth)
        accrue(L, "victim", 100.0, epoch=3)
        r = L.transfer_merit("victim", "attacker", modeled(150.0),
                             "sale", epoch=3, auth=auth)
        self.assertEqual(r.kind, "merit_transfer")
        self.assertAlmostEqual(L.merit_balance("victim").value, 50.0)

    def test_register_transfer_key_validates(self):
        L, _, _ = self._victim()
        with self.assertRaises(T.TokenomicsError):
            L.register_transfer_key("victim", "not-valid-base64!!!")
        with self.assertRaises(T.TokenomicsError):
            L.register_transfer_key("victim", "")
        with self.assertRaises(UnityBindingError):
            L.register_transfer_key("", _pub_b64(
                _wallet.generate_test_keypair()[1]))


# ---------------------------------------------------------------------------
class TestStandingGate(unittest.TestCase):
    """CRITICAL-2 closure: bought Merit must not buy emission weight.

    Emission weight = f(earned standing) — origin-based accrual history
    that never moves on transfer. Token balance (which CAN be bought)
    has ZERO influence on emission weight. Structural, not a comment:
      - emission_calculator REQUIRES a standing_source;
      - a caller-supplied merit_map is cross-checked against standing
        (exact restatement) and refused on any mismatch;
      - Ledger.transfer_merit never touches merit_history, so standing
        never moves on transfer."""

    def _earned(self, uid="earner", amount=100.0, epoch=1):
        # The sender's transfer key is registered too (S1b): the public
        # Unity ID alone authorizes nothing. The keypair is stashed for
        # _authed_transfer.
        L = Ledger()
        accrue(L, uid, amount, epoch=epoch)
        self._epriv, self._epub = _wallet.generate_test_keypair()
        L.register_transfer_key(uid, _pub_b64(self._epub))
        return L

    def _authed_transfer(self, L, from_id, to_id, amount, reason, epoch):
        return authed_transfer(L, from_id, to_id, modeled(amount), reason,
                               epoch, self._epriv, self._epub)

    def test_standing_is_accrual_only(self):
        L = self._earned()
        self.assertAlmostEqual(L.standing("earner").value, 100.0)
        self.assertEqual(L.standing("earner").provenance, "DERIVED")
        # a stranger has zero standing
        self.assertEqual(L.standing("buyer").value, 0.0)

    def test_transfer_moves_balance_never_standing(self):
        L = self._earned()
        self._authed_transfer(L, "earner", "buyer", 100.0, "sale", 2)
        self.assertAlmostEqual(L.merit_balance("earner").value, 0.0)
        self.assertAlmostEqual(L.merit_balance("buyer").value, 100.0)
        # value moved; history stayed with the earner
        self.assertAlmostEqual(L.standing("earner").value, 100.0)
        self.assertAlmostEqual(L.standing("buyer").value, 0.0)

    def test_bought_merit_buys_zero_emission_weight(self):
        # The gauntlet's reproducer, closed: earner accrues 100, sells
        # the full balance to buyer. Emission before and after the
        # buyout must be IDENTICAL for the earner; the buyer — holding
        # 100 bought Merit — gets nothing.
        L = self._earned()
        pre = L.emission_close("human", None, modeled(1000.0), epoch=1)
        self._authed_transfer(L, "earner", "buyer", 100.0, "sale", 2)
        post = L.emission_close("human", None, modeled(1000.0), epoch=2)
        self.assertNotIn("buyer", post.per_member)
        self.assertAlmostEqual(post.per_member["earner"].value,
                               pre.per_member["earner"].value)
        self.assertAlmostEqual(post.total.value, pre.total.value)
        self.assertAlmostEqual(post.per_member["earner"].value, 0.10)

    def test_attacker_map_with_bought_balance_refused(self):
        # The exact CRITICAL-2 attack shape: present the buyer's OWNED
        # (bought) balance as the merit map. Refused — the buyer's
        # standing is 0, the presented 100 mismatches.
        L = self._earned()
        self._authed_transfer(L, "earner", "buyer", 100.0, "sale", 2)
        atk_map = {"buyer": Figure(L.merit_balance("buyer").value,
                                   "REPORTED", "attacker's owned balance")}
        with self.assertRaises(T.UntrustedMeritMapError):
            L.emission_close("human", atk_map, modeled(1000.0), epoch=7)
        # VERIFIED provenance doesn't help either — the VALUE mismatches
        # standing.
        with self.assertRaises(T.UntrustedMeritMapError):
            L.emission_close("human",
                             {"buyer": v(100.0)}, modeled(1000.0), epoch=7)
        # no partial state: nothing emitted, no reserve movement
        self.assertEqual(L.emitted["human"], 0.0)
        self.assertEqual(L.reserve["human"], 0.0)

    def test_inflated_earner_map_refused(self):
        # Even the earner cannot inflate their own presented weight past
        # standing.
        L = self._earned()
        with self.assertRaises(T.UntrustedMeritMapError):
            L.emission_close("human", {"earner": v(1000.0)},
                             modeled(1000.0), epoch=1)

    def test_exact_restatement_accepted_weights_from_standing(self):
        # A map that restates standing exactly is accepted — and the
        # weights used are the trusted standing figures, not the map's:
        # identical canonical hash to the derived (map=None) close.
        L = self._earned()
        accrue(L, "earner2", 300.0, epoch=1)
        derived = L.emission_close("human", None, modeled(1000.0), epoch=1)
        restated = L.emission_close(
            "human", {"earner": v(100.0), "earner2": v(300.0)},
            modeled(1000.0), epoch=1)
        self.assertEqual(restated.canonical_sha256,
                         derived.canonical_sha256)
        self.assertAlmostEqual(restated.per_member["earner2"].value,
                               restated.per_member["earner"].value * 3)

    def test_roster_scoping_keeps_pool_split(self):
        # A caller may scope the map to a roster (pool membership); each
        # scoped weight is still forced to equal standing.
        L = self._earned("h1", 300.0)
        accrue(L, "m1", 100.0, epoch=1)
        human = L.emission_close("human", {"h1": v(300.0)},
                                 modeled(1000.0), epoch=1)
        machine = L.emission_close("machine", {"m1": v(100.0)},
                                   modeled(1000.0), epoch=1)
        self.assertEqual(set(human.per_member), {"h1"})
        self.assertEqual(set(machine.per_member), {"m1"})
        self.assertAlmostEqual(human.total.value, 0.30)
        self.assertAlmostEqual(machine.total.value, 0.10)

    def test_earned_merit_drives_weight(self):
        # Earned (not bought) Merit follows standing into emission.
        L = Ledger()
        accrue(L, "u1", 300.0, epoch=1)
        accrue(L, "u2", 100.0, epoch=1)
        out = L.emission_close("human", None, modeled(1000.0), epoch=1)
        self.assertAlmostEqual(out.per_member["u1"].value, 0.30)
        self.assertAlmostEqual(out.per_member["u2"].value, 0.10)

    def test_decay_touches_balance_never_standing(self):
        # Decay acts on the owned (spendable) balance; earned history —
        # and therefore emission weight — is untouched. Documented
        # decision: standing is lifetime earned accrual.
        L = self._earned()
        L.apply_decay("earner", 2, rate=modeled(0.5))
        self.assertAlmostEqual(L.merit_balance("earner").value, 25.0)
        self.assertAlmostEqual(L.standing("earner").value, 100.0)
        out = L.emission_close("human", None, modeled(1000.0), epoch=1)
        self.assertAlmostEqual(out.per_member["earner"].value, 0.10)

    def test_emission_weights_ignores_balances(self):
        # Direct structural assertion: emission_weights reads
        # merit_history only. Inflate a balance without accrual (raw
        # in-ledger edit = memory tampering, outside the threat model)
        # and the weights don't move — the map comes from history.
        L = self._earned()
        L.merit_balances["buyer"] = 1_000_000.0  # no accrual, no history
        weights = L.emission_weights()
        self.assertNotIn("buyer", weights)
        self.assertAlmostEqual(weights["earner"].value, 100.0)


# ---------------------------------------------------------------------------
class TestDonationHonorPath(unittest.TestCase):
    def test_donation_yields_honor_not_merit(self):
        L = Ledger()
        before = L.merit_balance("u1").value
        r, honor = L.donate("u1", modeled(50.0), "efuse", epoch=1)
        self.assertEqual(r.kind, "donation")
        self.assertEqual(honor.unity_id, "u1")
        self.assertIsNone(honor.class_name)  # honor names HELD_FOR_DAVID
        self.assertAlmostEqual(L.merit_balance("u1").value, before)
        self.assertAlmostEqual(L.lock_balance, 50.0)

    def test_fiat_donation_yields_honor_only(self):
        L = Ledger()
        r, honor = L.donate("u1", modeled(1000.0), "fiat", epoch=1)
        self.assertEqual(r.detail["kind"], "fiat")
        self.assertAlmostEqual(L.lock_balance, 0.0)  # fiat lives off-rail
        self.assertEqual(len(L.honor["u1"]), 1)

    def test_donation_to_merit_to_efuse_path_absent(self):
        # No function converts a donation (or Honor) into Merit or eFuse.
        assert_no_forbidden_machinery(self)
        L = Ledger()
        L.donate("u1", modeled(50.0), "efuse", epoch=1)
        self.assertEqual(L.merit_balance("u1").value, 0.0)
        self.assertEqual(L.emitted["human"], 0.0)
        self.assertEqual(L.emitted["machine"], 0.0)

    def test_donor_exclusion(self):
        L = Ledger()
        L.donate("u1", modeled(50.0), "efuse", epoch=1)
        work = receipt("u1", detail={"work": "cause-work"})
        with self.assertRaises(T.DonorExclusionError):
            L.cause_disburse("u1", modeled(10.0), work, epoch=2)

    def test_cause_disburse_for_nondonor(self):
        L = Ledger()
        L.donate("donor", modeled(50.0), "efuse", epoch=1)
        work = receipt("doer", detail={"work": "cause-work"})
        r = L.cause_disburse("doer", modeled(10.0), work, epoch=2)
        self.assertEqual(r.kind, "cause_disbursement")
        self.assertAlmostEqual(L.lock_balance, 40.0)

    def test_cause_disburse_needs_gated_receipt(self):
        L = Ledger()
        L.donate("donor", modeled(50.0), "efuse", epoch=1)
        with self.assertRaises(T.ReceiptRequiredError):
            L.cause_disburse("doer", modeled(10.0), None, epoch=2)


# ---------------------------------------------------------------------------
class TestMeshNeverMints(unittest.TestCase):
    def test_mesh_route_carries_zero_authority(self):
        L = Ledger()
        r = L.mesh_route("u1", "human", "workmanifest-abc123", epoch=1)
        self.assertEqual(r.kind, "mesh_route")
        self.assertEqual(r.detail["emission_authority"], 0.0)
        self.assertFalse(r.detail["mints"])
        self.assertEqual(L.emitted["human"], 0.0)

    def test_mesh_mint_machinery_absent(self):
        self.assertFalse(hasattr(T, "mesh_mint"))
        assert_no_forbidden_machinery(self)

    def test_double_bridge_refused(self):
        L = Ledger()
        L.mesh_route("u1", "human", "workmanifest-abc123", epoch=1)
        with self.assertRaises(T.DuplicateReceiptError):
            L.mesh_route("u1", "human", "workmanifest-abc123", epoch=1)


# ---------------------------------------------------------------------------
class TestPoolBoundary(unittest.TestCase):
    def test_no_pool_to_pool_machinery(self):
        assert_no_forbidden_machinery(self)
        for name in ("transfer_pool_to_pool", "move_between_pools",
                     "pool_to_pool_transfer"):
            self.assertFalse(hasattr(T, name), name)
            self.assertFalse(hasattr(Ledger, name), name)

    def test_pools_are_independent_authorities(self):
        L = Ledger()
        L.disburse("human", "u1", v(10.0, "DERIVED"), epoch=1)
        self.assertAlmostEqual(L.emitted["human"], 10.0)
        self.assertAlmostEqual(L.emitted["machine"], 0.0)
        self.assertAlmostEqual(
            L.remaining_authority("machine").value, 50_000_000.0)


# ---------------------------------------------------------------------------
class TestUnityBinding(unittest.TestCase):
    def _ledger(self):
        return Ledger()

    def test_every_movement_requires_unity_id_by_signature(self):
        L = self._ledger()
        # Missing the required positional -> TypeError. No anonymous flows.
        with self.assertRaises(TypeError):
            L.accrue_merit(receipt("u1"), modeled(1.0))           # no uid
        with self.assertRaises(TypeError):
            L.apply_decay(1)                                      # no uid
        with self.assertRaises(TypeError):
            L.disburse("human", v(1.0, "DERIVED"), 1)             # no uid
        with self.assertRaises(TypeError):
            L.donate(modeled(1.0), "efuse", 1)                    # no uid
        with self.assertRaises(TypeError):
            L.cause_disburse(modeled(1.0), receipt("u1"), 1)       # no uid
        with self.assertRaises(TypeError):
            L.mesh_route("human", "m", 1)                         # no uid

    def test_blank_unity_id_refused_at_runtime(self):
        L = self._ledger()
        for bad in (None, "", "   "):
            with self.assertRaises(UnityBindingError, msg=f"{bad!r}"):
                L.accrue_merit(bad, receipt("u1"), modeled(1.0))
            with self.assertRaises(UnityBindingError, msg=f"{bad!r}"):
                L.donate(bad, modeled(1.0), "fiat", 1)
            with self.assertRaises(UnityBindingError, msg=f"{bad!r}"):
                L.mesh_route(bad, "human", "m", 1)
            with self.assertRaises(UnityBindingError, msg=f"{bad!r}"):
                L.apply_decay(bad, 1, rate=modeled(0.1))
            with self.assertRaises(UnityBindingError, msg=f"{bad!r}"):
                L.disburse("human", bad, v(1.0, "DERIVED"), 1)


# ---------------------------------------------------------------------------
class TestParamsRegistry(unittest.TestCase):
    def test_decided_params(self):
        for name in ("lifetime_cap", "human_pool_cap", "machine_pool_cap",
                     "one_merged_rail", "no_pre_funding", "no_pool_to_pool",
                     "mesh_never_mints", "merit_transferable",
                     "honor_never_converts", "unity_binding",
                     "merit_interest_refused"):
            self.assertEqual(T.param_status(name), "DECIDED", name)

    def test_held_params(self):
        for name in ("peg_ratio_E", "merit_decay_rate", "epoch_length",
                     "reserve_holdback_fraction", "tier_weights",
                     "bridge_premium_band"):
            self.assertEqual(T.param_status(name), "HELD_FOR_DAVID", name)

    def test_require_decided(self):
        self.assertEqual(T.require_decided("lifetime_cap"), 100_000_000.0)
        with self.assertRaises(T.HeldParameterError):
            T.require_decided("peg_ratio_E")

    def test_every_param_has_a_note(self):
        for name, p in T.PARAMS.items():
            self.assertTrue(p.note, name)
            self.assertIn(p.status, ("DECIDED", "HELD_FOR_DAVID"), name)


# ---------------------------------------------------------------------------
class TestReceiptChain(unittest.TestCase):
    def test_receipts_hash_chain(self):
        L = Ledger()
        r1, _ = L.donate("u1", modeled(10.0), "fiat", epoch=1)
        r2 = L.mesh_route("u1", "human", "m-1", epoch=1)
        self.assertEqual(r1.prev_hash, "GENESIS")
        self.assertEqual(r2.prev_hash, r1.manifest_hash)
        self.assertEqual(len({r1.manifest_hash, r2.manifest_hash}), 2)

    def test_state_digest_stable(self):
        L = Ledger()
        d1 = L.state_digest()
        L.donate("u1", modeled(10.0), "fiat", epoch=1)
        self.assertNotEqual(d1, L.state_digest())


class TestWinterThrottle(unittest.TestCase):
    """Gauntlet E16: the winter throttle is wired into the emission path.

    dclm/winter.py is the lawful source — these tests wire TO it:
    WinterSignal -> evaluate_trigger -> WinterState -> emission_multiplier.
    No second trigger is invented: a raw gradient is refused.
    """

    def setUp(self):
        import winter as W
        self.W = W

    def _merits(self):
        return {"u1": v(100), "u2": v(300)}

    def _base(self, **kw):
        # The merit map restates the standing source exactly.
        kw.setdefault("standing_source", self._merits())
        return emission_calculator("human", self._merits(), modeled(1000.0),
                                   v(50_000_000, "DERIVED"), **kw)

    def _deep_winter_signal(self):
        return self.W.WinterSignal(
            peg_deviation=0.10, peg_provenance="REPORTED",
            activity_delta=-0.50, activity_provenance="REPORTED",
            crisis_declared=True, crisis_verified=True,
            crisis_provenance="VERIFIED",
        )

    def test_winter_none_is_summer_noop(self):
        out = self._base()
        self.assertEqual(out.winter_multiplier, 1.0)
        self.assertEqual(out.winter_gradient, 0.0)
        self.assertEqual(out.winter_label, "SUMMER")
        self.assertAlmostEqual(out.total.value, 0.4)  # 400 merit / 1000 E
        self.assertIn("No winter throttle (summer)", out.note)

    def test_unreadable_signal_stays_summer_unknown_never_pass(self):
        out = self._base(winter=self.W.WinterSignal())
        plain = self._base()
        self.assertEqual(out.winter_multiplier, 1.0)
        self.assertEqual(out.winter_label, "SUMMER")
        self.assertEqual(out.winter_provenance, "UNKNOWN")
        self.assertEqual(out.total.value, plain.total.value)
        self.assertEqual(out.canonical_sha256, plain.canonical_sha256)

    def test_mild_summer_signal_no_throttle(self):
        sig = self.W.WinterSignal(peg_deviation=0.001,
                                  peg_provenance="REPORTED")
        out = self._base(winter=sig)
        plain = self._base()
        self.assertEqual(out.winter_multiplier, 1.0)
        self.assertEqual(out.total.value, plain.total.value)
        for uid in ("u1", "u2"):
            self.assertEqual(out.per_member[uid].value,
                             plain.per_member[uid].value)

    def test_winter_active_reduces_emission_by_multiplier(self):
        sig = self._deep_winter_signal()
        state = self.W.evaluate_trigger(sig)
        expected = self.W.emission_multiplier(state.gradient)
        self.assertLess(expected, 1.0)
        out = self._base(winter=sig)
        plain = self._base()
        self.assertAlmostEqual(out.winter_multiplier, expected)
        self.assertAlmostEqual(out.winter_gradient, state.gradient)
        self.assertEqual(out.winter_label, state.label)
        self.assertEqual(out.winter_provenance, "DERIVED")
        self.assertAlmostEqual(out.total.value,
                               plain.total.value * expected)
        for uid in ("u1", "u2"):
            self.assertAlmostEqual(out.per_member[uid].value,
                                   plain.per_member[uid].value * expected)

    def test_throttled_receipt_carries_winter_reason(self):
        out = self._base(winter=self._deep_winter_signal())
        plain = self._base()
        # the receipt shows WHY emission was reduced
        self.assertTrue(out.winter_reasons)
        joined = " ".join(out.winter_reasons)
        self.assertIn("peg", joined)
        self.assertIn("activity", joined)
        self.assertIn("crisis", joined)
        self.assertIn("WINTER THROTTLE", out.total.note)
        self.assertIn("dclm/winter.py::emission_multiplier", out.total.note)
        self.assertIn("Winter throttle", out.note)
        # sealed: the winter claim changes the canonical hash
        self.assertNotEqual(out.canonical_sha256, plain.canonical_sha256)

    def test_winter_floor_slows_never_stops(self):
        state = self.W.WinterState(gradient=1.0, label="WINTER",
                                   reasons=["full-winter test state"],
                                   provenance="DERIVED")
        out = self._base(winter=state)
        self.assertAlmostEqual(out.winter_multiplier, self.W.EMISSION_FLOOR)
        self.assertGreater(out.total.value, 0.0)
        for uid in ("u1", "u2"):
            self.assertGreater(out.per_member[uid].value, 0.0)

    def test_raw_gradient_refused_no_second_trigger(self):
        with self.assertRaises(TokenomicsError):
            self._base(winter=0.7)
        with self.assertRaises(TokenomicsError):
            self._base(winter={"gradient": 0.7})

    def test_emission_close_threads_winter(self):
        L = Ledger()
        accrue(L, "u1", 100.0, epoch=1)
        accrue(L, "u2", 300.0, epoch=1)
        out = L.emission_close("human", self._merits(), modeled(1000.0),
                               epoch=1, winter=self._deep_winter_signal())
        plain = L.emission_close("human", self._merits(), modeled(1000.0),
                                 epoch=1)
        self.assertLess(out.winter_multiplier, 1.0)
        self.assertTrue(out.winter_reasons)
        self.assertEqual(plain.winter_multiplier, 1.0)
        self.assertAlmostEqual(out.total.value,
                               plain.total.value * out.winter_multiplier)

    def test_winter_state_accepted_directly(self):
        state = self.W.evaluate_trigger(self._deep_winter_signal())
        via_signal = self._base(winter=self._deep_winter_signal())
        via_state = self._base(winter=state)
        self.assertEqual(via_state.canonical_sha256,
                         via_signal.canonical_sha256)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Tests for energy-indexed pricing.

The rule: prices are STATIC at base Merit until a fresh, honestly-graded
Joule marker exists for the lane — then the price moves with the measured
Joule ratio, clamped to [0.5x, 3.0x]. Fail-closed everywhere: anything
unknown falls back to base. The 1% residual and the receipt chain are
untouched; the receipt carries the quote that produced the gross.
"""
import json

import pytest

from rail import (
    DynamicPriceCatalog,
    EnergyIndex,
    LaneEnergyMarker,
    Price,
    PriceCatalog,
    ReceiptChain,
    X402Middleware,
    split_residual,
)
from rail.facilitator import LocalTestFacilitator

SERVICE = "0x1111111111111111111111111111111111111111"
RESIDUAL = "0x2222222222222222222222222222222222222222"

NOW = 1791774300.0  # 2026-10-12T03:05:00Z — fixed epoch for deterministic tests
TS = "2026-10-12T03:00:00Z"  # 5 min before NOW: within the 15-min marker TTL


def _catalog(**kw):
    idx = EnergyIndex(100.0, **kw)  # reference: 100 J/unit
    return DynamicPriceCatalog(
        prices={"/metered": Price(merit=10.0, description="metered api")},
        energy_index=idx,
    ), idx


def _marker(lane="DCLM", joules=80.0, ts=TS, grade="REAL"):
    return LaneEnergyMarker(
        lane=lane, joules_per_unit=joules, measured_at=ts,
        source="joule-meter", grade=grade,
    )


# --- marker validation: bad markers never enter the index ----------------

def test_marker_rejects_bad_ts():
    with pytest.raises(ValueError):
        _marker(ts="2020-26-10T1-:00:32Z")  # the malformed shape from the Oct 10 export


def test_marker_rejects_nonpositive_joules():
    with pytest.raises(ValueError):
        _marker(joules=0.0)


def test_marker_rejects_bad_grade():
    with pytest.raises(ValueError):
        _marker(grade="MAYBE")


# --- static by default -----------------------------------------------------

def test_no_lane_means_base():
    cat, _ = _catalog()
    assert cat.price_for("/metered").merit == 10.0


def test_unknown_lane_means_base():
    cat, idx = _catalog()
    idx.update_marker(_marker(lane="DCLM"))
    assert cat.price_for("/metered", lane="EUROPE", now=NOW).merit == 10.0


def test_no_index_means_base():
    cat = DynamicPriceCatalog(prices={"/metered": Price(merit=10.0)})
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == 10.0
    assert cat.quote("/metered", lane="DCLM", now=NOW)["mode"] == "STATIC"


def test_stale_marker_means_base():
    cat, idx = _catalog()
    idx.update_marker(_marker(ts="2026-10-11T00:00:00Z"))  # >15min old
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == 10.0
    assert idx.mode_for("DCLM", NOW) == "STATIC"


def test_inferred_marker_never_moves_money():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=10.0, grade="INFERRED"))
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == 10.0


def test_unpriced_path_stays_none():
    cat, idx = _catalog()
    idx.update_marker(_marker())
    assert cat.price_for("/free", lane="DCLM", now=NOW) is None
    assert cat.quote("/free", lane="DCLM", now=NOW) is None


# --- indexed movement ------------------------------------------------------

def test_cheaper_lane_lowers_price():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=80.0))  # 0.8x the reference
    p = cat.price_for("/metered", lane="DCLM", now=NOW)
    assert p.merit == pytest.approx(8.0)
    assert idx.mode_for("DCLM", NOW) == "INDEXED"


def test_costlier_lane_raises_price():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=150.0))  # 1.5x
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(15.0)


def test_reference_lane_prices_at_par():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=100.0))
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(10.0)


def test_floor_clamps():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=1.0))  # 0.01x -> clamped to 0.5x
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(5.0)


def test_ceiling_clamps():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=10_000.0))  # 100x -> clamped to 3x
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(30.0)


def test_reported_grade_moves_money():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=80.0, grade="REPORTED"))
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(8.0)


def test_markers_update_over_time():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=80.0))
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(8.0)
    idx.update_marker(_marker(joules=120.0))  # lane got costlier
    assert cat.price_for("/metered", lane="DCLM", now=NOW).merit == pytest.approx(12.0)


# --- the money laws are untouched ------------------------------------------

def test_residual_still_one_percent_of_indexed_gross():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=80.0))
    gross = cat.price_for("/metered", lane="DCLM", now=NOW).micros  # 8.0 Merit
    residual, net = split_residual(gross)
    assert gross == 8_000_000
    assert residual == 80_000  # exactly 1%
    assert residual + net == gross


def test_receipt_carries_the_quote_and_chain_verifies():
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=80.0))
    quote = cat.quote("/metered", lane="DCLM", now=NOW)
    assert quote["mode"] == "INDEXED"
    assert quote["multiplier"] == pytest.approx(0.8)
    assert quote["marker"]["joules_per_unit"] == 80.0
    assert quote["marker"]["grade"] == "REAL"

    chain = ReceiptChain(node_id="test")
    gross = quote["micros"]
    residual, net = split_residual(gross)
    trace = chain.append_payment(
        invoice_id="inv-1", payer="0xpayer", pay_to=SERVICE,
        residual_to=RESIDUAL, gross_micros=gross,
        residual_micros=residual, net_micros=net,
        asset="USDC", network="eip155:84532",
        settlement_kind="simulated", settlement_ref="sim:1",
        resource_url="/metered", pricing=quote,
    )
    assert trace["outcome"]["pricing"]["multiplier"] == pytest.approx(0.8)
    ok, reason = chain.verify_chain()
    assert ok, reason


# --- middleware: the 402 amount follows the lane ---------------------------

def _wsgi_call(app, path, lane=None):
    environ = {"PATH_INFO": path, "REQUEST_METHOD": "GET"}
    if lane:
        environ["x402.lane"] = lane
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response))
    return captured["status"], json.loads(body)


def test_middleware_402_moves_with_fresh_marker():
    from datetime import datetime, timezone
    fresh_ts = datetime.now(timezone.utc).isoformat()
    cat, idx = _catalog()
    idx.update_marker(_marker(joules=80.0, ts=fresh_ts))
    inner = lambda env, sr: (sr("200 OK", [("Content-Type", "text/plain")]), [b"ok"])[1]
    app = X402Middleware(
        inner, catalog=cat, pay_to=SERVICE, residual_to=RESIDUAL,
        facilitator=LocalTestFacilitator(),
    )
    status, body = _wsgi_call(app, "/metered", lane="DCLM")
    assert status.startswith("402")
    assert body["accepts"][0]["maxAmountRequired"] == "8000000"  # 8.0 Merit indexed

    status, body = _wsgi_call(app, "/metered")  # no lane -> base
    assert body["accepts"][0]["maxAmountRequired"] == "10000000"

    status, body = _wsgi_call(app, "/metered", lane="EUROPE")  # unknown lane -> base
    assert body["accepts"][0]["maxAmountRequired"] == "10000000"


def test_well_known_still_serves_base_catalog():
    cat, _ = _catalog()
    inner = lambda env, sr: (sr("200 OK", [("Content-Type", "text/plain")]), [b"ok"])[1]
    app = X402Middleware(
        inner, catalog=cat, pay_to=SERVICE, residual_to=RESIDUAL,
        facilitator=LocalTestFacilitator(),
    )
    status, body = _wsgi_call(app, "/.well-known/x402.json")
    assert status.startswith("200")
    assert body["prices"]["/metered"]["merit"] == 10.0


# --- rotation premium ------------------------------------------------------
from rail import RotationLedger, RotationRound  # noqa: E402


def _rcat(**kw):
    ledger = RotationLedger(**kw)
    cat = DynamicPriceCatalog(
        prices={"/decide": Price(merit=10.0, description="trinity verdict")},
        rotation_ledger=ledger,
    )
    return cat, ledger


def _novel_round(ledger, did, n, contributor="solver-a", premium=2_500_000):
    ledger.open_round(did, contributor, premium)
    ledger.certify_round(
        did, n, "NOVEL",
        option_hash="opt-%s-%d" % (did, n),
        evidence_ids=("ev-%s-%d" % (did, n),),
    )


def test_rotation_scales_linearly_and_caps():
    cat, ledger = _rcat()
    did = "d1"
    assert cat.price_for("/decide", decision_id=did).merit == 10.0
    for n in range(1, 5):
        _novel_round(ledger, did, n)
    assert ledger.multiplier_for(did) == 2.0  # 1 + 4*0.25
    assert cat.price_for("/decide", decision_id=did).merit == 20.0
    for n in range(5, 13):
        _novel_round(ledger, did, n)
    assert ledger.multiplier_for(did) == 3.0  # capped at r=8, stays there
    assert cat.price_for("/decide", decision_id=did).merit == 30.0


def test_no_decision_id_no_premium():
    cat, ledger = _rcat()
    _novel_round(ledger, "d1", 1)
    assert cat.price_for("/decide").merit == 10.0  # plain compute never sees it


def test_energy_and_rotation_multiply():
    cat, idx = _catalog()
    cat.rotation_ledger = RotationLedger()
    idx.update_marker(_marker(joules=80.0))  # 0.8x energy
    _novel_round(cat.rotation_ledger, "d1", 1)
    _novel_round(cat.rotation_ledger, "d1", 2)  # 1.5x rotation
    p = cat.price_for("/metered", lane="DCLM", decision_id="d1", now=NOW)
    assert p.merit == pytest.approx(10.0 * 0.8 * 1.5)  # 12.0


def test_combined_bounds():
    cat, idx = _catalog()
    cat.rotation_ledger = RotationLedger()
    idx.update_marker(_marker(joules=1.0))  # energy -> floor 0.5x
    for n in range(1, 13):
        _novel_round(cat.rotation_ledger, "d-cap", n)  # rotation -> cap 3.0x
    p = cat.price_for("/metered", lane="DCLM", decision_id="d-cap", now=NOW)
    assert p.merit == pytest.approx(10.0 * 0.5 * 3.0)  # 15.0, worst case 9x total


def test_novelty_bar_rejects_duplicate_option():
    _, ledger = _rcat()
    ledger.open_round("d1", "solver-a", 1_000_000)
    ledger.certify_round("d1", 1, "NOVEL", option_hash="same", evidence_ids=("e1",))
    ledger.open_round("d1", "solver-a", 1_000_000)
    with pytest.raises(ValueError, match="duplicate option_hash"):
        ledger.certify_round("d1", 2, "NOVEL", option_hash="same", evidence_ids=("e2",))
    assert ledger.multiplier_for("d1") == 1.25  # only the first round counts


def test_novelty_bar_rejects_rehashed_evidence():
    _, ledger = _rcat()
    ledger.open_round("d1", "solver-a", 1_000_000)
    ledger.certify_round("d1", 1, "NOVEL", option_hash="o1", evidence_ids=("e1",))
    ledger.open_round("d1", "solver-a", 1_000_000)
    with pytest.raises(ValueError, match="rehashed evidence"):
        ledger.certify_round("d1", 2, "NOVEL", option_hash="o2", evidence_ids=("e1",))


def test_novel_requires_option_hash():
    _, ledger = _rcat()
    ledger.open_round("d1", "solver-a", 1_000_000)
    with pytest.raises(ValueError, match="option_hash"):
        ledger.certify_round("d1", 1, "NOVEL")


def test_empty_round_earns_zero_rebates_payer():
    cat, ledger = _rcat()
    ledger.open_round("d1", "holder-x", 2_500_000)
    ledger.certify_round("d1", 1, "EMPTY")
    assert ledger.multiplier_for("d1") == 1.0  # stalling pays nothing
    assert ledger.rebate_due_micros("d1") == 2_500_000
    assert ledger.earned_pool("d1") == {}


def test_gamed_round_rebates_and_marks():
    cat, ledger = _rcat()
    ledger.open_round("d1", "holder-x", 2_500_000)
    ledger.certify_round("d1", 1, "GAMED")
    assert ledger.multiplier_for("d1") == 1.0
    assert ledger.rebate_due_micros("d1") == 2_500_000
    assert ledger.gamed_rounds("d1") == [1]  # the mark stays on the trace
    assert ledger.earned_pool("d1") == {}


def test_double_certify_rejected():
    _, ledger = _rcat()
    ledger.open_round("d1", "solver-a", 1_000_000)
    ledger.certify_round("d1", 1, "NOVEL", option_hash="o1", evidence_ids=("e1",))
    with pytest.raises(ValueError, match="already certified"):
        ledger.certify_round("d1", 1, "EMPTY")


def test_solver_earns_pro_rata_holder_gets_nothing():
    _, ledger = _rcat()
    # solver-a: 2 novel rounds; solver-b: 1 novel round; holder-x: 1 empty round
    ledger.open_round("d1", "solver-a", 2_500_000)
    ledger.certify_round("d1", 1, "NOVEL", option_hash="o1", evidence_ids=("e1",))
    ledger.open_round("d1", "holder-x", 5_000_000)
    ledger.certify_round("d1", 2, "EMPTY")
    ledger.open_round("d1", "solver-b", 7_500_000)
    ledger.certify_round("d1", 3, "NOVEL", option_hash="o3", evidence_ids=("e3",))
    ledger.open_round("d1", "solver-a", 7_500_000)
    ledger.certify_round("d1", 4, "NOVEL", option_hash="o4", evidence_ids=("e4",))
    pool = ledger.earned_pool("d1")
    # novel premium paid: 2.5M + 7.5M + 7.5M = 17.5M; solver-a 2/3, solver-b 1/3
    assert pool["solver-a"] + pool["solver-b"] == 17_500_000
    assert "holder-x" not in pool  # the holder earns nothing
    assert ledger.rebate_due_micros("d1") == 5_000_000  # holder's empty round rebated


def test_purity_clears_unresolved_freezes():
    _, ledger = _rcat()
    _novel_round(ledger, "d1", 1)
    ledger.seal("d1", "PURITY")
    assert ledger.multiplier_for("d1") == 1.0
    assert ledger.state_for("d1") == "CLEARED"

    _novel_round(ledger, "d2", 1)
    _novel_round(ledger, "d2", 2)
    ledger.seal("d2", "UNRESOLVED")
    assert ledger.multiplier_for("d2") == 1.5  # frozen final
    assert ledger.state_for("d2") == "TERMINAL"
    assert ledger.earned_pool("d2") != {}  # pool still queryable for the terminal trace
    with pytest.raises(ValueError, match="sealed UNRESOLVED"):
        ledger.open_round("d2", "solver-a", 1_000_000)


def test_quote_carries_rotation_block():
    cat, _ = _rcat()
    q = cat.quote("/decide", decision_id="d9")
    assert q["mode"] == "STATIC"
    assert q["rotation_multiplier"] == 1.0
    assert q["rotation"] is None

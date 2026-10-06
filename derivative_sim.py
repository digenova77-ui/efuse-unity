#!/usr/bin/env python3
"""
derivative_sim.py — validation simulation for DERIVATIVE_MAX_EFFECTS.md.

What this models (read the .md for the derivations; this file checks them):
  LAYER 1 (regeneration): Galton-Watson branching of *work opportunities*.
      One verified work-unit at the core spawns derivative work opportunities
      downstream. Each opportunity becomes verified work with probability p
      (the DCLM gate). Merit is EARNED per ring from each identity's OWN
      verified receipts — never passed, never skimmed. (Canon VI.)
  LAYER 2 (circulation, David's 2026-10-06 resolution): earned Merit tokens
      are TRANSFERABLE (sold, gifted — receipted, Unity-bound both ends).
      EARNED STANDING (origin history) stays with the earner and cannot be
      bought. Unity tokens are NOT transferable. Bound-transfer sales are dead.
      Transfer redistributes existing stock; it creates nothing.

All parameters are MODELED assumptions (see PARAMS). Nothing here is measured
from production. Testnet framing only. Labels: every output figure is a model
projection, never a reported measurement.
"""

import math
import random
from statistics import mean, stdev

# ---------------------------------------------------------------------------
# PARAMETERS — every one an [ASSUMPTION], labeled MODELED. The digits David
# holds (peg E, merit decay rate, ring-depth factor, epoch length) are NOT
# decided here; the values below are modeling stand-ins only.
# ---------------------------------------------------------------------------
PARAMS = {
    # Layer 1: regeneration
    "mu": 3.0,        # [ASSUMPTION] mean derivative work-opportunities spawned
                       #   per verified work-unit (mentoring / kin-share /
                       #   disciple channel). MODELED.
    "p": 0.4,         # [ASSUMPTION] DCLM gate passage probability: an
                       #   opportunity becomes VERIFIED work. MODELED (gate
                       #   is strict by law; the digit is a stand-in).
    "phi": 0.7,       # [ASSUMPTION] ring-depth factor: merit per work-unit
                       #   at ring n = v0 * phi**n. Canon contemplates
                       #   AMPLIFICATION (HELD digit); 0.7 models attenuation
                       #   to show the subcritical case. MODELED.
    "v0": 100.0,      # [ASSUMPTION] merit earned per core work-unit
                       #   (top band: verified real-world recovery work).
                       #   Band calibration is HELD-FOR-DAVID. MODELED.
    "delta": 0.10,    # [ASSUMPTION] merit decay per epoch (fidelity is
                       #   current — principle is LAW; the digit is HELD).
                       #   MODELED stand-in.
    "W0": 10,         # [ASSUMPTION] core verified work-units per epoch.
                       #   MODELED.
    "T": 12,          # [ASSUMPTION] epochs per seasonal year. MODELED.
    "alpha": 0.6,     # [ASSUMPTION] winter cut to merit-earning inflow
                       #   (bounty-funded work slows; distinct from winter.py's
                       #   EMISSION_FLOOR=0.25 (PROPOSED) which throttles the
                       #   merit->eFuse rail, not earning). MODELED.
    "N_max": None,     # retired: cumulative once-ever activation proved
                       #   unphysical (supercritical unit trees devour any
                       #   finite pool instantly, then inflow dies — an
                       #   artifact, not economics). Saturation is modeled
                       #   as per-epoch verification capacity instead (the
                       #   DCLM single commit path — canon III).
    "cap_loose": 10**9,  # [ASSUMPTION] per-epoch verified-work capacity,
                       #   loose case (effectively unbounded). MODELED.
    "cap_tight": 40,   # [ASSUMPTION] per-epoch verified-work capacity,
                       #   tight case: the commit path saturates and deep
                       #   rings are truncated. MODELED.
    "epochs": 400,    # simulation horizon (not a model parameter).
    "replicates": 2000,  # Monte-Carlo replicates for Sim A.
    "max_rings": 60,  # truncation depth for the branching tree.
    # Layer 2: circulation (David's resolution)
    "N_id": 2000,     # [ASSUMPTION] identities in the circulation sim.
                       #   MODELED.
    "tau": 0.05,      # [ASSUMPTION] per-epoch fraction of holdings each
                       #   identity transfers (to random recipients).
                       #   MODELED.
    "delta_s": 0.02,  # [ASSUMPTION] standing (origin-history) decay per
                       #   epoch — stickier than merit decay; origin history
                       #   is record-like. Digit HELD. MODELED.
    "gamma_attack": 0.01,  # [ASSUMPTION] stress-test: fraction of TOTAL
                       #   stock gifted per epoch to a zero-earning attacker.
                       #   MODELED.
}

LAM = PARAMS["mu"] * PARAMS["p"]          # effective branching factor
LAMPHI = LAM * PARAMS["phi"]              # growth x depth factor


# ---------------------------------------------------------------------------
# CLOSED FORMS (derived in DERIVATIVE_MAX_EFFECTS.md; asserted here)
# ---------------------------------------------------------------------------
def closed_forms(prm=PARAMS):
    lam = prm["mu"] * prm["p"]
    lphi = lam * prm["phi"]
    assert lphi < 1.0, "subcriticality guard violated: lam*phi must be < 1"
    K = 1.0 / (1.0 - lphi)                       # derivative multiplier
    downstream_per_core = K - 1.0                # downstream merit / core merit
    I0 = prm["W0"] * prm["v0"] * K               # earned inflow per epoch
    S_star = I0 / prm["delta"]                   # steady-state merit stock
    # Seasonal orbit: S*_{t} for w_t = (1-cos(2 pi t / T))/2, inflow
    # I_t = I0 (1 - alpha w_t). Closed periodic solution of the linear drive.
    T, d, a = prm["T"], prm["delta"], prm["alpha"]
    decay = 1.0 - d
    norm = 1.0 - decay ** T
    orbit = []
    for t in range(T):
        s = 0.0
        for j in range(T):
            w = (1.0 - math.cos(2.0 * math.pi * ((t - 1 - j) % T) / T)) / 2.0
            I = I0 * (1.0 - a * w)
            s += (decay ** j) * I
        orbit.append(s / norm)
    return {
        "lam": lam, "lamphi": lphi, "K": K,
        "downstream_per_core": downstream_per_core,
        "I0": I0, "S_star": S_star,
        "orbit": orbit,
        "orbit_mean": sum(orbit) / T,
        "orbit_max": max(orbit), "orbit_min": min(orbit),
    }


def closed_capped(prm=PARAMS, cap=None):
    """Saturated regime: at most `cap` verified work-units per epoch (the
    commit-path throughput bound). Units are verified ring-priority
    (ring 0 first): expected units at ring n = W0*lam**n, expected merit =
    W0*v0*(lam*phi)**n. Returns (I_cap, S_cap, K_cap). Closed form; the sim
    applies the same cap to REALIZED ring counts, so a small Jensen gap
    between E[min(X,cap)] and min(E[X],cap) is expected and reported."""
    cap = prm["cap_tight"] if cap is None else cap
    lam = prm["mu"] * prm["p"]
    lphi = lam * prm["phi"]
    cum_units, I_cap = 0.0, 0.0
    n = 0
    while n < 500:
        u = prm["W0"] * (lam ** n)
        m = prm["W0"] * prm["v0"] * (lphi ** n)
        if m < 1e-9 and cum_units >= cap:
            break
        if cum_units + u <= cap:
            cum_units += u
            I_cap += m
        else:
            frac = (cap - cum_units) / u if u > 0 else 0.0
            I_cap += frac * m
            cum_units = cap
            break
        if m < 1e-9:
            break
        n += 1
    return {
        "I_cap": I_cap,
        "S_cap": I_cap / prm["delta"],
        "K_cap": I_cap / (prm["W0"] * prm["v0"]),
        "rings_full": n,
    }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def poisson(rng, lam):
    """Knuth's method; fine for small lam (ours is 1.2)."""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, q = 0, 1.0
    while True:
        k += 1
        q *= rng.random()
        if q <= L:
            return k - 1


def poisson_agg(rng, mean):
    """Aggregate offspring of a whole ring: sum of iid Poisson(lam) over U
    units == Poisson(U*lam) exactly (additivity of Poisson). For mean < 30
    this is exact via Knuth; for larger means (explosive supercritical unit
    trees) it uses the Normal approximation N(mean, mean) — [ASSUMPTION],
    labeled: only the MEAN is asserted against the closed form, and the
    approximation is mean-exact. Needed because the UNIT tree is
    supercritical (lam = 1.2 > 1) while the MERIT tree is subcritical
    (lam*phi = 0.84 < 1): unit counts can explode even though merit
    converges, so per-unit sampling is computationally infeasible."""
    if mean <= 0:
        return 0
    if mean < 30:
        return poisson(rng, mean)
    return max(0, int(rng.gauss(mean, math.sqrt(mean)) + 0.5))


# ---------------------------------------------------------------------------
# SIM A — one core work-unit's derivative tree (multiplier check).
# No crowding, no decay: pure Galton-Watson + ring-depth merit.
# ---------------------------------------------------------------------------
def sim_a_tree(rng, prm=PARAMS):
    """Total merit (core + downstream) generated by ONE core work-unit.

    Per-ring aggregate sampling: ring n's unit count ~ Poisson(U_{n-1}*lam)
    (exact by Poisson additivity for small means; Normal-approximated for
    large — see poisson_agg). Merit at ring n = U_n * v0 * phi**n."""
    lam = prm["mu"] * prm["p"]
    total = prm["v0"]                       # ring 0: the core unit itself
    units = 1
    for n in range(1, prm["max_rings"] + 1):
        units = poisson_agg(rng, units * lam)
        if units == 0:
            break
        total += units * prm["v0"] * (prm["phi"] ** n)
    return total / prm["v0"]                 # as a multiple of core merit


def run_sim_a(prm=PARAMS, seed=7):
    rng = random.Random(seed)
    mults = [sim_a_tree(rng, prm) for _ in range(prm["replicates"])]
    m = mean(mults)
    se = stdev(mults) / math.sqrt(len(mults)) if len(mults) > 1 else 0.0
    return {"mean_K": m, "se": se, "n": len(mults)}


# ---------------------------------------------------------------------------
# SIM B — epoch stock dynamics with a per-epoch verification capacity cap
# (the DCLM single commit path — canon III: one commit path for every write).
# Each epoch: W0 core units arrive; rings generate in ring-priority order;
# verification truncates at `cap` units. Merit stock decays at delta.
# cap=None (or huge) = uncrowded regime -> must recover S*.
# ---------------------------------------------------------------------------
def run_sim_b(prm=PARAMS, cap=None, seed=11):
    rng = random.Random(seed)
    cap = prm["cap_loose"] if cap is None else cap
    lam = prm["mu"] * prm["p"]
    stock = 0.0
    trace = []
    for _ in range(prm["epochs"]):
        inflow, used = 0.0, 0
        units_prev = prm["W0"]          # ring 0: the exogenous core arrivals
        for n in range(0, prm["max_rings"] + 1):
            if n == 0:
                units = prm["W0"]
            else:
                units = poisson_agg(rng, units_prev * lam)
            if units <= 0:
                break
            take = min(units, cap - used)
            if take <= 0:
                break
            inflow += take * prm["v0"] * (prm["phi"] ** n)
            used += take
            units_prev = units          # next ring's expectation keys off the
                                        # realized count (branching truth)
            if used >= cap:
                break
        stock = (1.0 - prm["delta"]) * stock + inflow
        trace.append(stock)
    tail = trace[int(0.8 * prm["epochs"]):]
    return {
        "final_stock": trace[-1],
        "tail_mean": sum(tail) / len(tail),
        "cap": cap,
    }


# ---------------------------------------------------------------------------
# Inflow-mean check: long-run Monte Carlo of E[inflow/epoch] only (no stock
# recursion). The per-epoch inflow has enormous variance (SD ~ 2400) because
# the UNIT tree is supercritical (lam = 1.2 > 1) even though the MERIT tree
# is subcritical — so a short epoch run cannot pin the mean; this long run
# can. The stock recursion itself is linear and checked deterministically.
# ---------------------------------------------------------------------------
def inflow_check(prm=PARAMS, epochs=4000, seed=11):
    rng = random.Random(seed)
    lam = prm["mu"] * prm["p"]
    tot, tot2 = 0.0, 0.0
    for _ in range(epochs):
        inflow = 0.0
        units_prev = prm["W0"]
        for n in range(0, prm["max_rings"] + 1):
            units = prm["W0"] if n == 0 else poisson_agg(rng, units_prev * lam)
            if units <= 0:
                break
            inflow += units * prm["v0"] * (prm["phi"] ** n)
            units_prev = units
        tot += inflow
        tot2 += inflow * inflow
    m = tot / epochs
    var = max(0.0, tot2 / epochs - m * m)
    return {"mean_inflow": m, "sd_inflow": math.sqrt(var),
            "se": math.sqrt(var / epochs), "epochs": epochs}


def deterministic_stock(prm=PARAMS, inflow=None, epochs=400):
    """Exact recursion S_{t+1} = (1-delta) S_t + inflow (no noise)."""
    inflow = closed_forms(prm)["I0"] if inflow is None else inflow
    s = 0.0
    for _ in range(epochs):
        s = (1.0 - prm["delta"]) * s + inflow
    return s
# ---------------------------------------------------------------------------
# SIM C — secondary circulation (David's resolution).
# N identities. Each epoch: identities earn e_i (origin-credited), holdings
# decay at delta, each identity transfers fraction tau of holdings to random
# recipients (receipted, Unity-bound — the transfer ledger nets to zero).
# Standing s_i: origin history only — credited on EARN, never on receipt of
# a transfer; decays at delta_s. One attacker earns NOTHING but receives
# gamma_attack of total stock per epoch as gifts: holdings spike, standing
# must stay ~0 (the standing-buying attack, structurally closed).
# ---------------------------------------------------------------------------
def run_sim_c(prm=PARAMS, seed=23):
    rng = random.Random(seed)
    n = prm["N_id"]
    cf = closed_forms(prm)
    # Heterogeneous earning: 5% core-like earners, rest small. Calibrated so
    # total earned per epoch ~= I0 (the ring model's inflow).
    earn_rate = [0.0] * n
    n_core = max(1, n // 20)
    per_core = cf["I0"] * 0.6 / n_core
    per_rest = cf["I0"] * 0.4 / (n - n_core)
    for i in range(n):
        earn_rate[i] = per_core if i < n_core else per_rest
    attacker = n - 1
    earn_rate[attacker] = 0.0  # the attacker does no verified work

    holdings = [0.0] * n
    standing = [0.0] * n
    transfer_volume = 0.0
    for _ in range(prm["epochs"]):
        # 1. earn (origin-credited) + decay
        # earn_rate[i] is already in merit units/epoch; per-epoch noise is
        # multiplicative uniform (kept small so the conservation check reads
        # the structure, not the noise).
        for i in range(n):
            e = earn_rate[i] * (0.9 + 0.2 * rng.random())
            holdings[i] = (1.0 - prm["delta"]) * holdings[i] + e
            standing[i] = (1.0 - prm["delta_s"]) * standing[i] + e
        # 2. transfers: each identity sends tau of holdings to k recipients
        #    (k=3); attacker receives gamma_attack * total stock as gifts.
        total = sum(holdings)
        sent = [0.0] * n
        for i in range(n):
            out = prm["tau"] * holdings[i]
            sent[i] = out
            holdings[i] -= out
            for _ in range(3):
                j = rng.randrange(n)
                holdings[j] += out / 3.0
        gift = prm["gamma_attack"] * total
        others_total = total - holdings[attacker]  # pre-gift others' sum
        holdings[attacker] += gift          # gifted in...
        # ...funded proportionally from everyone else's post-transfer holdings
        # (a pure redistribution: nets to zero across the population)
        if others_total > 0:
            for i in range(n):
                if i != attacker:
                    holdings[i] -= gift * (holdings[i] / others_total)
        transfer_volume += sum(sent) + gift
        # conservation probe: transfers must net to zero
        # (checked at the end against earned/decay accounting)
    total_holdings = sum(holdings)
    total_standing = sum(standing)
    return {
        "total_holdings": total_holdings,
        "total_standing": total_standing,
        "S_star_closed": cf["S_star"],
        "attacker_holdings": holdings[attacker],
        "attacker_standing": standing[attacker],
        "mean_holding": total_holdings / n,
        "transfer_volume": transfer_volume,
        "attacker_bound": prm["gamma_attack"] * cf["S_star"] / prm["delta"],
    }


# ---------------------------------------------------------------------------
# Main: closed forms vs simulation, with honest discrepancy notes.
# ---------------------------------------------------------------------------
def main():
    prm = PARAMS
    cf = closed_forms(prm)
    print("=" * 72)
    print("DERIVATIVE MERIT REGENERATION — closed form vs simulation")
    print("ALL FIGURES MODELED (assumption stand-ins). Testnet framing only.")
    print("=" * 72)
    print(f"\nParameters (MODELED): mu={prm['mu']} p={prm['p']} "
          f"lam={cf['lam']:.2f} phi={prm['phi']} lam*phi={cf['lamphi']:.3f} "
          f"v0={prm['v0']} delta={prm['delta']} W0={prm['W0']}")
    print(f"Subcriticality guard: lam*phi = {cf['lamphi']:.3f} < 1  "
          f"{'OK' if cf['lamphi'] < 1 else 'VIOLATED'}")

    print("\n--- SIM A: derivative multiplier (one core work-unit) ---")
    a = run_sim_a(prm)
    print(f"Closed form K            = {cf['K']:.4f}")
    print(f"Sim mean K  (n={a['n']})     = {a['mean_K']:.4f} ± {a['se']:.4f} (SE)")
    print(f"Downstream per core unit: closed {cf['downstream_per_core']:.4f} "
          f"merit-units; sim {(a['mean_K']-1):.4f}")
    dk = abs(a["mean_K"] - cf["K"])
    print(f"|sim - closed| = {dk:.4f}  "
          f"{'AGREE (within 3 SE)' if dk < 3*a['se'] else 'DISCREPANCY — see notes'}")

    print("\n--- SIM B: steady-state stock (uncrowded: cap=%d/epoch) ---"
          % prm["cap_loose"])
    b = run_sim_b(prm)
    print(f"Closed form S*          = {cf['S_star']:,.1f}")
    print(f"Sim tail-mean stock     = {b['tail_mean']:,.1f} (400-epoch trace)")
    det = deterministic_stock(prm)
    print(f"Deterministic recursion = {det:,.1f} (exact inflow, no noise)")
    ic = inflow_check(prm)
    print(f"Long-run mean inflow    = {ic['mean_inflow']:,.1f} ± {ic['se']:.1f} "
          f"(SE, n={ic['epochs']}) vs closed I0={cf['I0']:,.1f}")
    dinf = abs(ic["mean_inflow"] - cf["I0"])
    print(f"|sim - closed| = {dinf:.1f}  "
          f"{'AGREE (within 3 SE)' if dinf < 3*ic['se'] else 'DISCREPANCY — see notes'}")
    print("NOTE (honest): per-epoch inflow SD is ~2,400 — the UNIT tree is")
    print("supercritical (lam=1.2>1) so inflow is heavy-tailed even though the")
    print("MERIT tree is subcritical. A 400-epoch stock trace cannot pin the")
    print("mean (AR(1) with rho=0.9: 80-epoch tail has effective n ~ 4). The")
    print("long-run inflow check above is the real validation; the recursion")
    print("S* = I0/delta is then algebraic, confirmed by the deterministic run.")

    print("\n--- SIM B2: saturation (tight commit path: cap=%d/epoch) ---"
          % prm["cap_tight"])
    cc = closed_capped(prm, prm["cap_tight"])
    b2 = run_sim_b(prm, cap=prm["cap_tight"])
    print(f"Closed S*_cap           = {cc['S_cap']:,.1f} "
          f"(I_cap={cc['I_cap']:,.1f}/epoch, K_cap={cc['K_cap']:.3f}, "
          f"{cc['rings_full']} full rings)")
    print(f"Sim tail-mean stock     = {b2['tail_mean']:,.1f}")
    rel2 = abs(b2["tail_mean"] - cc["S_cap"]) / cc["S_cap"]
    print(f"Relative gap            = {rel2:.3%}  "
          f"{'AGREE' if rel2 < 0.10 else 'DISCREPANCY — see notes'}")
    print(f"Realized multiplier under saturation: K_cap closed "
          f"{cc['K_cap']:.3f} vs uncrowded K {cf['K']:.2f} — the commit path")
    print("truncates deep rings first, so saturation ATTENUATES the realized")
    print("multiplier. Small Jensen gap E[min(X,cap)] vs min(E[X],cap) is")
    print("expected: the closed form caps expected ring counts, the sim caps")
    print("realized ones.")

    print("\n--- Seasonal orbit (closed form, T=%d epochs) ---" % prm["T"])
    print(f"Orbit mean              = {cf['orbit_mean']:,.1f}")
    print(f"Summer max              = {cf['orbit_max']:,.1f} "
          f"(+{(cf['orbit_max']/cf['orbit_mean']-1):.1%})")
    print(f"Winter min              = {cf['orbit_min']:,.1f} "
          f"({(cf['orbit_min']/cf['orbit_mean']-1):.1%})")

    print("\n--- SIM C: secondary circulation (transferable Merit) ---")
    c = run_sim_c(prm)
    print(f"Closed S* (no-transfer) = {c['S_star_closed']:,.1f}")
    print(f"Sim total holdings      = {c['total_holdings']:,.1f}")
    print(f"Transfer conservation   : "
          f"{'HOLDS' if abs(c['total_holdings']-c['S_star_closed'])/c['S_star_closed'] < 0.05 else 'CHECK'} "
          f"(transfer redistributes; stock law unchanged)")
    print(f"Attacker holdings       = {c['attacker_holdings']:,.1f} "
          f"(mean holding {c['mean_holding']:,.1f}; bound "
          f"{c['attacker_bound']:,.1f})")
    print(f"Attacker STANDING       = {c['attacker_standing']:,.2f} "
          f"(earned nothing -> standing ~0 despite bought holdings)")
    print(f"Total standing          = {c['total_standing']:,.1f} "
          f"(origin-credited only; invariant under transfer)")
    print("\nAll figures above are MODELED projections, not measurements.")
    print("=" * 72)


if __name__ == "__main__":
    main()

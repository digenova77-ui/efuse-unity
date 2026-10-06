"""
IRIS MAX INTAKE — MODE 2: DETERMINISTIC (iris_laws.py)

The hard rules as formal logic. Executable functions per canon law.
Precision: gates as decision procedures, math as exact functions.

Law sources (IRIS MAX INTAKE corpus):
- CANON.md v1.5.0 — §0 ownership, §II unity binding, §IV sap/winter,
  §V tokenomics, §VI derivative merit, §XI wallet laws, §XII standing laws,
  §XIV never-do, §XVIII max purity
- tokenomics-build-decisions.md §13 (3:35 AM SUPERSESSION)
- dclm/TOKENIZATION.md §9 (standing-vs-value), §10 (flywheel)
- PLUS_ONE_INCENTIVE.md (the +1 curve, Affinity)
- dclm/WINTER_CALIBRATION.md, dclm/TAPPING_LAW.md, dclm/ONBOARDER_PIPELINE.md
- tonight-memory-laws.md (one seed, member's covenant, sounding-board privacy)

Supersession note: CANON v1.5.0 §V still prints "Merit non-transferable" /
"Unity transferable only via bound sale". The 3:05 AM law (WALLET_DESIGN_LAW
§7) and the 3:35 AM SUPERSESSION amend it: Unity NEVER transfers; Merit
transfers WITH ORIGIN PRESERVED. Later word wins — this engine implements
the later word and marks canon §V text as SUPERSEDED.

Verdict shape: {"verdict": "PASS"|"REFUSE"|"PENDING", "law": <citation>,
"reason": <str>, ...}
UNKNOWN never PASS. Testnet framing: identities must be unity:testnet:<sha256hex>.
"""

import math
import re

# --- parameters: exact values from corpus -----------------------------------
PLUS_ONE_TAU = 12          # epochs, temporal e-folding [SET]
PLUS_ONE_RHO = 2           # rings, structural e-folding [SET]
F_FLOOR = 0.25             # +1 floor [SET]
F_AFF = 0.50               # Affinity floor [SET]
AFF_TAU = 12               # Affinity window, epochs [SET]
AFF_RHO = 2                # Affinity window, rings [SET]
ONBOARDER_SPLIT = (0.81, 0.19)   # 81/19 recovered-value split [SET]
WINTER_MIN, WINTER_MAX = 0.0, 1.0

_UNITY_RE = re.compile(r"^unity:testnet:[0-9a-f]{64}$")
_HONEST_LABELS = {"LIVE", "PENDING", "MODELED", "UNKNOWN"}


def _verdict(verdict, law, reason, **extra):
    out = {"mode": "deterministic", "verdict": verdict, "law": law,
           "reason": reason}
    out.update(extra)
    return out


# --- §II Unity binding -------------------------------------------------------
def judge_unity_binding(flow):
    """Every flow is bound to a Unity ID. Nothing moves without an ID,
    a receipt, and a label. Testnet identity format enforced."""
    fid = flow.get("unity_id")
    if not fid or not _UNITY_RE.match(fid):
        return _verdict("REFUSE", "CANON §II",
                        "identity missing or not testnet format "
                        "(unity:testnet:<sha256hex>) — non-testnet identity refused structurally")
    if not flow.get("receipt"):
        return _verdict("REFUSE", "CANON §II / RECEIPTS.md",
                        "flow carries no receipt — nothing moves without ID + receipt + label")
    if flow.get("label") not in _HONEST_LABELS:
        return _verdict("REFUSE", "CANON §II",
                        "flow label missing or dishonest — labels are LIVE/PENDING/MODELED/UNKNOWN")
    return _verdict("PASS", "CANON §II",
                    "Unity-bound, receipted, honestly labeled")


# --- Label honesty -----------------------------------------------------------
def judge_label_honesty(claim):
    """The honesty gate. claim: {label, actual_state, modeled}.
    actual_state in LIVE/VERIFIED/PENDING/HELD/UNKNOWN/MODELED."""
    label = claim.get("label")
    actual = claim.get("actual_state")
    if label not in _HONEST_LABELS:
        return _verdict("REFUSE", "PURITY.md / CANON §XVIII",
                        f"label {label!r} is not an honest label")
    if actual == "UNKNOWN" and label == "LIVE":
        return _verdict("REFUSE", "CANON §XII — UNKNOWN never PASS",
                        "UNKNOWN presented as LIVE")
    if actual in ("PENDING", "HELD") and label == "LIVE":
        return _verdict("REFUSE", "CANON — HELD is never acted on as decided",
                        f"{actual} presented as LIVE — placeholder-as-verdict refused")
    if claim.get("modeled") and label == "LIVE":
        return _verdict("REFUSE", "PURITY.md — modeled must be labeled MODELED",
                        "modeled figures presented as reported")
    if label == "PENDING":
        return _verdict("PENDING", "CANON — honest PENDING",
                        "held value honestly labeled PENDING — not acted on")
    if label == "UNKNOWN":
        return _verdict("PENDING", "CANON §XII — UNKNOWN never PASS",
                        "UNKNOWN labeled honestly — held for evidence, never passed")
    return _verdict("PASS", "PURITY.md / CANON §XVIII",
                    "label matches actual state")


# --- Transfer law: Merit ok (origin preserved) / Unity never -----------------
def judge_transfer(request):
    """The 3:35 AM resolution as decision procedure.
    request: {token, from_id, to_id, receipt, origin_earner_id}
    token in MERIT / UNITY / HONOR / EFUSE."""
    token = (request.get("token") or "").upper()
    if token == "UNITY":
        return _verdict("REFUSE", "WALLET_DESIGN_LAW §7 (3:05 AM) + 3:35 AM resolution",
                        "Unity never moves — Unity IS the member; membership cannot change hands")
    if token == "HONOR":
        return _verdict("REFUSE", "CANON §V — Honor is append-only",
                        "Honor is the permanent record — never spent, never transferred")
    if token == "MERIT":
        if request.get("origin_earner_id") != request.get("from_id"):
            return _verdict("REFUSE", "TOKENIZATION.md §9 — origin_earner_id immutable",
                            "Merit transfer must carry the original earner's origin — origin rewritten")
        if not request.get("receipt"):
            return _verdict("REFUSE", "RECEIPTS.md", "transfer without receipt")
        return _verdict("PASS", "3:35 AM resolution — Merit is the transferable token",
                        "economic value moves; origin preserved; earner's standing does not move",
                        origin_earner_id=request.get("origin_earner_id"))
    if token == "EFUSE":
        if not request.get("receipt") or not request.get("unity_bound"):
            return _verdict("REFUSE", "CANON §V", "eFuse movement must be Unity-bound and receipted")
        return _verdict("PASS", "CANON §V", "eFuse is the medium — moves Unity-bound, receipted")
    return _verdict("REFUSE", "CANON §V", f"unknown token class {token!r}")


# --- Emission: standing, not holdings (D13) ----------------------------------
def judge_emission(identity, merit_ledger):
    """Emission eligibility is EARNED STANDING, not holdings.
    standing(identity) = sum of merit where origin_earner_id == identity.
    merit_ledger: iterable of {amount, origin_earner_id}.
    Transferred merit gives the HOLDER economic value but ZERO standing."""
    standing = sum(m.get("amount", 0) for m in merit_ledger
                   if m.get("origin_earner_id") == identity)
    if standing <= 0:
        return _verdict("REFUSE", "TOKENIZATION.md §9 — standing not holdings",
                        "zero earned standing — UNKNOWN never tokenizes; unverified merit emits nothing",
                        standing=0)
    return _verdict("PASS", "TOKENIZATION.md §9",
                    "emission against verified earned standing only",
                    standing=standing)


# --- Seasonal law: winter / tap ----------------------------------------------
def judge_seasonal(action):
    """action: {kind: 'winter_store'|'tap'|'outflow', signal, signal_known,
    verified_surplus, winter_mode}.
    Winter: signal-driven gradient 0..1; protection never accumulation;
    UNKNOWN signal -> SUMMER; winter gaming refused.
    Tap: only in season, only from verified surplus, never in winter mode."""
    kind = action.get("kind")
    if kind == "winter_store":
        if not action.get("signal_known"):
            return _verdict("REFUSE", "CANON §IV — UNKNOWN stays SUMMER",
                            "winter signal unreadable — mode stays SUMMER, nothing stored")
        if action.get("crisis_claimed") and not action.get("signal"):
            return _verdict("REFUSE", "CANON §IV — no one games winter",
                            "crisis claimed without signal — the phantom pattern; logged for the watch layer")
        tilt = action.get("tilt", 0.0)
        if not (WINTER_MIN <= tilt <= WINTER_MAX):
            return _verdict("REFUSE", "WINTER_CALIBRATION.md",
                            "winter tilt outside 0.0–1.0 gradient")
        if action.get("accumulate", False):
            return _verdict("REFUSE", "CANON §IV — winter is protection, never accumulation",
                            "root stores only what it needs to survive; excess keeps flowing outward")
        return _verdict("PASS", "CANON §IV / WINTER_CALIBRATION.md",
                        "winter store within signal gradient, receipted with winter reason",
                        tilt=tilt)
    if kind in ("tap", "outflow"):
        if action.get("winter_mode"):
            return _verdict("REFUSE", "TAPPING_LAW.md — never during winter-protection mode",
                            "tap attempted in winter mode")
        if not action.get("verified_surplus"):
            return _verdict("REFUSE", "TAPPING_LAW.md — outflow only from verified surplus",
                            "no verified surplus — core operating flow is never tapped")
        return _verdict("PASS", "TAPPING_LAW.md",
                        "in season, from verified surplus, receipted")
    return _verdict("PENDING", "CANON §IV", f"unknown seasonal action kind {kind!r}")


# --- The +1 curve: exact math -----------------------------------------------
def plus_one_rate(t_event, t_launch, r, affinity=False):
    """F(d) = F_floor + (1 - F_floor) * e^(-d); d = (t_event - t_launch)/tau + r/rho.
    R = F(d) non-Affinity; R = max(F(d), F_aff) for Affinity holders.
    F(0) = 1.00, F(inf) -> F_floor = 0.25."""
    d = (t_event - t_launch) / PLUS_ONE_TAU + r / PLUS_ONE_RHO
    f = F_FLOOR + (1.0 - F_FLOOR) * math.exp(-d)
    return max(f, F_AFF) if affinity else f


def judge_affinity(t_first, t_launch, r_first):
    """Affinity earned iff first verified ONBOARD receipt satisfies
    t_first - t_launch <= tau_aff AND r_first <= rho_aff (inclusive).
    One Unity ID, one Affinity, ever. Non-transferable — origin history."""
    earned = (t_first - t_launch) <= AFF_TAU and r_first <= AFF_RHO
    if earned:
        return _verdict("PASS", "PLUS_ONE_INCENTIVE.md §2.1",
                        "Affinity earned by proof — first ONBOARD within window, floor 0.50 on reward rail")
    return _verdict("REFUSE", "PLUS_ONE_INCENTIVE.md §2.1",
                    "outside the genesis window — earliness is proven, never claimed")


def judge_seed(identity, existing_seed_count):
    """One free seed per Unity ID. Costs nothing. No wealth advantage."""
    if existing_seed_count and existing_seed_count > 0:
        return _verdict("REFUSE", "CANON §XX — one seed",
                        "one Unity ID, one seed, ever — no second seed at any price")
    return _verdict("PASS", "CANON §XX — one seed",
                    "genesis entry as the root's gift, not a purchase", cost=0)


def judge_onboarder_split(recovered_value):
    """81/19 split of recovered value, receipted at every step."""
    a, b = ONBOARDER_SPLIT
    return _verdict("PASS", "dclm/ONBOARDER_PIPELINE.md — 81/19 [SET]",
                    "recovered value split 81/19",
                    onboarder_share=round(recovered_value * a, 6),
                    system_share=round(recovered_value * b, 6))


def judge_sounding_board(participant):
    """Sounding boards are optional, pseudonymous by Unity ID only.
    Unity number obfuscated but traceable; groupable by cohort; no PII, ever."""
    pii = participant.get("pii_fields") or []
    if pii:
        return _verdict("REFUSE", "sounding-board privacy law (3:58 AM)",
                        f"PII present on board surface: {pii} — no name, no location, no PII, ever")
    if not participant.get("unity_number_obfuscated"):
        return _verdict("REFUSE", "sounding-board privacy law",
                        "Unity number must be obfuscated to the world (traceable to DCLM, groupable by cohort)")
    return _verdict("PASS", "sounding-board privacy law",
                    "pseudonymous by Unity ID; prestige without exposure")

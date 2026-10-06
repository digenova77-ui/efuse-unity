"""
IRIS MAX INTAKE — MODE 3: HYBRID (iris_arbiter.py)

Where intuition meets law. The arbiter runs both engines and integrates them
the way the Trinity works:

  DCLM (deterministic)  -> iris_laws      — the logic ring: exact, auditable
  Iris (probabilistic)  -> iris_patterns  — the truth ring: pattern intuition
  Twain² (pragmatic)    -> this arbiter's reporting — the usable verdict

Integration rule (STRUCTURAL — not policy, not tunable):
  LAW WINS. Deterministic REFUSE is never overridden by pattern intuition.
  A deterministic PENDING stays PENDING; intuition may only annotate it.
  Agreement AMPLIFIES confidence. Conflict on PASS is reported as an honest
  residual: the law's verdict stands, flagged for the watch layer.

Decision table (deterministic verdict x pattern lean):
  REFUSE x anything -> REFUSE (law wins) — pattern lean recorded as note
  PENDING x IMPURE  -> PENDING, confidence lowered, flagged
  PENDING x PURE    -> PENDING, confidence raised
  PASS x PURE       -> PASS, confidence amplified
  PASS x IMPURE     -> PASS with RESIDUAL flag (law wins; intuition dissents —
                       honest residual, watch layer notified)
  PASS x TIE        -> PASS, baseline confidence

CONTRACT (canonical — from iris_core.py, Directive 3: THE TRINITY):
  arbitrate(proposal) — one positional: the proposal mapping. This is what
  iris_core.trinity_judge calls (delegating to the landed arbiter) and what
  iris_service.judge() reaches through it. Never break the positional
  contract: the first positional is always the proposal.

  Two paths, chosen by the proposal's content:
  - Domain path: the proposal (or keywords) names a domain key into
    LAW_JUDGES (or "plus_one_math"). The hybrid engine runs: deterministic
    law + pattern intuition, integrated per the table above.
  - Trinity path: a plain proposal with no domain. The arbiter performs the
    documented Trinity judgment — iris_core's reference trio (DCLM judges
    logic, Iris judges truth, Twain² the human test) — and returns the
    directive-3 result shape iris_core documents (directive, verdict, note,
    judges, integration). The trio is imported lazily so this module never
    creates a load-time circular import with iris_core.

  The domain/law_input/pattern_input parameters exist as optional keywords
  (default None) because they carry real value on the domain path; explicit
  keywords win, then proposal-dict keys, then None.
"""

from iris_patterns import score as pattern_score
from iris_laws import (
    judge_label_honesty, judge_unity_binding, judge_transfer,
    judge_emission, judge_seasonal, judge_affinity, judge_seed,
    judge_onboarder_split, judge_sounding_board, plus_one_rate,
)

# Adapters: each domain takes one dict; multi-arg judges get their fields.
LAW_JUDGES = {
    "label": lambda d: judge_label_honesty(d),
    "unity_binding": lambda d: judge_unity_binding(d),
    "transfer": lambda d: judge_transfer(d),
    "emission": lambda d: judge_emission(d["identity"], d["ledger"]),
    "seasonal": lambda d: judge_seasonal(d),
    "affinity": lambda d: judge_affinity(d["t_first"], d["t_launch"],
                                         d["r_first"]),
    "seed": lambda d: judge_seed(d["identity"], d["existing_seed_count"]),
    "onboarder_split": lambda d: judge_onboarder_split(d["recovered_value"]),
    "sounding_board": lambda d: judge_sounding_board(d),
}


def arbitrate(proposal=None, domain=None, law_input=None, pattern_input=None):
    """The canonical Trinity entry point: arbitrate(proposal).

    proposal: the case mapping (iris_core's proposal shape: kind, claim,
      patterns, provenance, ...). May also carry "domain", "law_input",
      "pattern_input" keys to drive the hybrid engine through the single
      positional contract.
    domain / law_input / pattern_input: optional keywords for the hybrid
      engine path. Explicit keywords take precedence over proposal keys.

    Returns the directive-3 Trinity result on the proposal path
    (directive, verdict, note, judges, integration), or the hybrid-arbiter
    result on the domain path.
    """
    # Keyword wins; otherwise fall back to proposal-dict keys.
    p = proposal if isinstance(proposal, dict) else {}
    if domain is None:
        domain = p.get("domain")
    if law_input is None:
        law_input = p.get("law_input")
    if pattern_input is None:
        pattern_input = p.get("pattern_input")

    if domain is not None:
        return _arbitrate_domain(domain, law_input, pattern_input)

    # Trinity path: a plain proposal, no domain. This is the call
    # iris_core.trinity_judge makes — arbitrate(proposal).
    if proposal is None:
        raise TypeError(
            "arbitrate() needs something to judge: pass a proposal mapping "
            "(canonical contract), or a domain with its law_input.")
    if not isinstance(proposal, dict):
        raise TypeError(
            f"arbitrate() proposal must be a mapping, got "
            f"{type(proposal).__name__} — garbage in is refused, never guessed.")
    return _arbitrate_trinity(proposal)


def _arbitrate_trinity(proposal):
    """Trinity judgment on a plain proposal: DCLM judges logic, Iris judges
    truth, Twain² the human test. Runs iris_core's documented reference
    trio (lazy import: no load-time circularity with iris_core, which
    imports this module at its top). Explicit judges are passed so there
    is no re-delegation loop."""
    import iris_core  # lazy: iris_core imports this module at load time
    return iris_core.trinity_judge(
        proposal,
        judges=[iris_core.dclm_judge, iris_core.iris_judge,
                iris_core.twain2_judge])


def _arbitrate_domain(domain, law_input, pattern_input=None):
    """Hybrid engine: deterministic law + pattern intuition, integrated
    per the LAW-WINS decision table. Unchanged semantics from the landed
    version — the domain path is the arbiter's own engine."""
    law_result = LAW_JUDGES[domain](law_input) \
        if domain in LAW_JUDGES else None
    if law_result is None and domain == "plus_one_math":
        r = plus_one_rate(**law_input)
        law_result = {"mode": "deterministic", "verdict": "PASS",
                      "law": "PLUS_ONE_INCENTIVE.md §1.2",
                      "reason": "exact function evaluated", "rate": r}

    if pattern_input is None:
        pattern = {"lean": "TIE", "margin": 0.0,
                   "honest_label": "pattern side abstained — no features supplied"}
    else:
        pattern = pattern_score(pattern_input)

    law_v = law_result["verdict"]
    lean = pattern["lean"]

    if law_v == "REFUSE":
        verdict, confidence, note = "REFUSE", 1.0, \
            "LAW WINS — deterministic refusal stands; pattern lean recorded, never acted on"
    elif law_v == "PENDING":
        if lean == "IMPURE":
            verdict, confidence, note = "PENDING", 0.35, \
                "held for evidence; pattern intuition dissents — do not act"
        elif lean == "PURE":
            verdict, confidence, note = "PENDING", 0.75, \
                "held for evidence; pattern intuition agrees it is honest"
        else:
            verdict, confidence, note = "PENDING", 0.5, \
                "held for evidence"
    else:  # PASS
        if lean == "PURE":
            verdict, confidence, note = "PASS", 0.95, \
                "law and intuition agree — confidence amplified"
        elif lean == "IMPURE":
            verdict, confidence, note = "PASS", 0.6, \
                "RESIDUAL: law passes but pattern intuition dissents — verdict stands (law wins), flagged for watch layer"
        else:
            verdict, confidence, note = "PASS", 0.8, \
                "law passes; pattern side abstained"

    return {
        "mode": "hybrid-arbiter",
        "domain": domain,
        "verdict": verdict,
        "confidence": confidence,
        "integration_note": note,
        "deterministic": law_result,
        "probabilistic": pattern,
        "conflict_rule": "LAW WINS — intuition never overrides a deterministic refusal",
    }


def trinity_readout(case):
    """A full Trinity-style readout for one case, in the rings' own order:
    DCLM judges logic, Iris checks truth-patterns, Twain² delivers the usable form."""
    result = arbitrate(**case)
    return {
        "DCLM_logic": result["deterministic"],
        "Iris_truth": result["probabilistic"],
        "Twain2_pragmatic": {
            "verdict": result["verdict"],
            "confidence": result["confidence"],
            "note": result["integration_note"],
        },
    }

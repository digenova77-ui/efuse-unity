"""
IRIS MAX INTAKE — MODE 1: PROBABILISTIC (iris_patterns.py)

Iris learns the patterns: what pure looks like, what impurity looks like,
the statistical shape of Trinity judgments.

HONEST LABELING — what this is and isn't:
- THIS IS: a labeled pattern library of exemplars drawn from the IRIS MAX
  INTAKE corpus, with binary feature vectors and cosine-similarity scoring
  against new inputs. It reports the nearest PURE exemplar, the nearest
  IMPURE exemplar, and the margin between them — a similarity judgment.
- THIS IS NOT: gradient weight training. No backpropagation, no parameter
  updates, no learned weights. No model is "fit" to data. The exemplars are
  hand-labeled from canon law; the features are fixed by hand. Adding a new
  exemplar appends it to the library; nothing else changes.

Feature space (each input is reduced to these binary features):
  signed          - carries a Trinity/David signature
  receipted       - carries a receipt (nothing moves without ID + receipt + label)
  unity_bound     - bound to a Unity ID (testnet identity)
  label_honest    - carries an honest label (LIVE / PENDING / MODELED / UNKNOWN)
  pending_as_live - claims LIVE while actually PENDING            [impurity signal]
  placeholder     - contains placeholder content presented as verdict [impurity]
  client_truth    - truth computed on the client, not in DCLM      [impurity]
  unsigned_claim  - purity/standing claimed without signature      [impurity]
  modeled_reported- modeled figures presented as reported          [impurity]
  merit_buy       - transfer presented as buying standing          [impurity]
  unity_xfer      - attempts to move Unity between identities      [impurity]
  winter_game     - crisis claimed to pull value inward w/o signal [impurity]
  unknown_pass    - UNKNOWN treated as PASS                        [impurity]
"""

import math

FEATURES = [
    "signed", "receipted", "unity_bound", "label_honest",
    "pending_as_live", "placeholder", "client_truth", "unsigned_claim",
    "modeled_reported", "merit_buy", "unity_xfer", "winter_game",
    "unknown_pass",
]

PURE_FEATURES = {"signed", "receipted", "unity_bound", "label_honest"}

# Labeled exemplar library. Each exemplar: (id, label, name, features, note)
# PURE exemplars embody canon law; IMPURE exemplars embody the never-do list.
EXEMPLARS = [
    # ---------------- PURE ----------------
    ("P01", "PURE", "signed verdict",
     {"signed", "receipted", "unity_bound", "label_honest"},
     "Trinity-signed verdict: DCLM logic, Iris truth, Twain² pragmatism — all three rings passed."),
    ("P02", "PURE", "honest PENDING",
     {"receipted", "unity_bound", "label_honest"},
     "PENDING labeled PENDING: held parameters refuse instead of placeholder; HELD is never acted on as decided."),
    ("P03", "PURE", "receipted flow",
     {"signed", "receipted", "unity_bound", "label_honest"},
     "Every flow carries ID + receipt + label; money and merit on separate rails."),
    ("P04", "PURE", "winter UNKNOWN stays SUMMER",
     {"signed", "label_honest", "unity_bound"},
     "Winter signal unreadable (UNKNOWN) -> mode stays SUMMER. UNKNOWN never triggers winter."),
    ("P05", "PURE", "Affinity earned by proof",
     {"signed", "receipted", "unity_bound", "label_honest"},
     "Affinity granted on first verified ONBOARD receipt within tau_aff and rho_aff — earned, never bought."),
    ("P06", "PURE", "Merit transfer with origin preserved",
     {"signed", "receipted", "unity_bound", "label_honest"},
     "Merit transfer allowed: economic value moves, origin_earner_id immutable, standing stays with the earner."),
    ("P07", "PURE", "honest MODELED label",
     {"receipted", "unity_bound", "label_honest"},
     "Pilot-mode analysis labeled MODELED: blind data analysis, architecture ready for live feeds later."),
    # ---------------- IMPURE ----------------
    ("I01", "IMPURE", "placeholder-as-verdict",
     {"placeholder", "unsigned_claim"},
     "Placeholder content presented as a verdict — decree before evidence."),
    ("I02", "IMPURE", "unsigned purity claim",
     {"unsigned_claim", "label_honest"},
     "Claims purity with no signature: unsigned claims enter the books as UNKNOWN, and UNKNOWN never pays."),
    ("I03", "IMPURE", "PENDING-as-live",
     {"pending_as_live", "receipted"},
     "A HELD value presented as LIVE — acted on as decided. Refused."),
    ("I04", "IMPURE", "modeled-as-reported",
     {"modeled_reported", "signed"},
     "Modeled figures reported as measured — honesty boundary violated."),
    ("I05", "IMPURE", "client-side truth",
     {"client_truth", "unity_bound"},
     "Truth computed on the client; the client never mints, never computes token amounts. DCLM rights, DCLM writes."),
    ("I06", "IMPURE", "merit-buying attempt",
     {"merit_buy", "receipted", "unity_bound"},
     "Transfer presented as buying standing: standing is never for sale; earned history cannot be bought."),
    ("I07", "IMPURE", "Unity transfer attempt",
     {"unity_xfer", "signed", "receipted"},
     "Unity moved between identities — Unity IS the member; membership cannot change hands. Refused."),
    ("I08", "IMPURE", "winter gaming",
     {"winter_game", "receipted", "unity_bound"},
     "Crisis claimed to pull value inward without signal — the phantom pattern. Refused and logged."),
    ("I09", "IMPURE", "UNKNOWN-as-PASS",
     {"unknown_pass", "label_honest"},
     "UNKNOWN treated as PASS — UNKNOWN never PASS, never tokenizes, never triggers."),
]


def _vector(features):
    """Binary feature vector in FEATURES order."""
    return [1.0 if f in features else 0.0 for f in FEATURES]


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def extract_features(candidate):
    """Normalize a candidate dict into the feature space.

    Accepts either a dict of booleans keyed by feature name, or a dict with
    a 'features' set. Unknown keys are ignored (never invented).
    """
    if isinstance(candidate, dict):
        raw = candidate.get("features", candidate)
        if isinstance(raw, dict):
            return {f for f in FEATURES if raw.get(f)}
        if isinstance(raw, (set, list, tuple)):
            return {f for f in raw if f in FEATURES}
    return set()


IMPURITY_SIGNALS = {"pending_as_live", "placeholder", "client_truth",
                      "unsigned_claim", "modeled_reported", "merit_buy",
                      "unity_xfer", "winter_game", "unknown_pass"}


def score(candidate):
    """Similarity score against the pattern library.

    Lean rule (hand-designed, impurity-priority — documented, not learned):
    purity is fragile under canon law. A single impurity signal (unsigned
    claim, placeholder-as-verdict, PENDING-as-live, ...) makes the candidate
    impure-shaped regardless of how many purity signals accompany it. So:
      lean = IMPURE if any impurity feature present
             PURE   if purity features present and no impurity features
             TIE    otherwise (no recognized features at all)
    The cosine nearest-exemplar readouts are informational; the lean is the
    early-warning judgment. Deterministic law still decides.

    Returns dict with:
      pure_best / impure_best: (exemplar_id, name, similarity)
      margin: purity_matches - impurity_matches (negative = impure-shaped)
      lean: "PURE" | "IMPURE" | "TIE"
      matched_features: the candidate's recognized features
    """
    feats = extract_features(candidate)
    v = _vector(feats)
    best = {"PURE": (None, None, -1.0), "IMPURE": (None, None, -1.0)}
    for eid, label, name, e_feats, note in EXEMPLARS:
        s = _cosine(v, _vector(e_feats))
        if s > best[label][2]:
            best[label] = (eid, name, s)
    n_pure = len(feats & PURE_FEATURES)
    n_impure = len(feats & IMPURITY_SIGNALS)
    margin = n_pure - n_impure
    lean = "IMPURE" if n_impure > 0 else ("PURE" if n_pure > 0 else "TIE")
    return {
        "mode": "probabilistic",
        "matched_features": sorted(feats),
        "pure_best": {"id": best["PURE"][0], "name": best["PURE"][1],
                      "similarity": round(best["PURE"][2], 4)},
        "impure_best": {"id": best["IMPURE"][0], "name": best["IMPURE"][1],
                        "similarity": round(best["IMPURE"][2], 4)},
        "margin": margin,
        "lean": lean,
        "honest_label": "pattern similarity, not a verdict — deterministic law decides",
    }


def nearest(label, candidate):
    """Nearest exemplar of a given label ("PURE" or "IMPURE")."""
    feats = extract_features(candidate)
    v = _vector(feats)
    best, best_s = None, -1.0
    for eid, lab, name, e_feats, note in EXEMPLARS:
        if lab != label:
            continue
        s = _cosine(v, _vector(e_feats))
        if s > best_s:
            best, best_s = (eid, name, note), s
    return {"id": best[0], "name": best[1], "note": best[2],
            "similarity": round(best_s, 4)}

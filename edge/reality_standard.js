/**
 * REALITY.v1 — higher standard for every protocol claim.
 *
 * Grades (fail-closed):
 *   MEASURED   — observed in this run (quote, test, file bytes)
 *   DEPLOYED   — confirmed live URL check (caller supplies result)
 *   SEATED     — operator secret/key exists; we do not read it
 *   HELD       — required digit not set (E). Refuse rather than invent.
 *   LABELED    — USD/AR conversion, not a bill
 *   HYPOTHETICAL — scaled cube, future pin, unrun workflow
 *
 * A claim without a grade is refused.
 * UNKNOWN is never PASS.
 */
export const REALITY = "REALITY.v1";

export const GRADES = [
  "MEASURED",
  "DEPLOYED",
  "SEATED",
  "HELD",
  "LABELED",
  "HYPOTHETICAL",
];

export function claim(statement, grade, evidence = null) {
  if (!GRADES.includes(grade)) {
    return { ok: false, pass: false, reason: "unknown grade", statement };
  }
  if (grade === "HELD") {
    return { ok: false, pass: false, grade, statement, reason: "HELD — not invented" };
  }
  if (grade === "HYPOTHETICAL") {
    return { ok: true, pass: false, grade, statement, evidence, reason: "not reality" };
  }
  if ((grade === "MEASURED" || grade === "DEPLOYED") && !evidence) {
    return { ok: false, pass: false, grade, statement, reason: "no evidence" };
  }
  return {
    ok: true,
    pass: grade === "MEASURED" || grade === "DEPLOYED",
    grade,
    statement,
    evidence,
    boundary: "NOT_FOR_EMISSION",
  };
}

export function protocolReality() {
  return {
    reality: REALITY,
    arch: "DIAMOND.ARCHITECTURE.v1",
    claims: [
      claim("edge module tests passed in repo", "MEASURED", "node test_diamond_architecture.mjs"),
      claim("Worker routes in dualiscapax-landing main", "MEASURED", "commits c62ed30..09921e8"),
      claim("Pages production deploy of those routes", "HYPOTHETICAL"),
      claim("Pinata pin of snapshot", "HYPOTHETICAL"),
      claim("second pinner", "HYPOTHETICAL"),
      claim("IPNS republish", "HYPOTHETICAL"),
      claim("E peg digit", "HELD"),
      claim("USD storage figures", "LABELED", "AR_USD_LABEL=3.80"),
      claim("PRICE_COMPUTE", "MEASURED", "5 test-keys"),
      claim("CLOUDFLARE_API_TOKEN seated", "SEATED"),
    ],
    law: "LAW WINS",
    boundary: "NOT_FOR_EMISSION",
  };
}

# Governance Architecture Proposal — Law Floor and Principles Roof

**Status:** PROPOSED · DOCUMENTATION ONLY · NOT RATIFIED · NOT AN AMENDMENT TO CANON  
**Baseline:** `main` at `fb102eaa234cd4ce95cab567896dd02660948959` (2026-11-11)  
**Related unmerged work:** PR #12, PR #14, PR #15 (see §9)  
**Purpose:** Separate the authority of Law from the self-governing capacities of participating agents, while giving the repository one navigable architecture and one staged integration path.

> “The Law gives you the floor and the principles hold up the capacity of your roof.”
>
> This is the Founder’s design direction recorded for examination. This document does not promote it to ratified Canon Law.

---

## 1. The structural distinction

The house has distinct parts. They must cooperate without becoming interchangeable.

### 1.1 Law — the floor

Law defines the boundaries of permissible action and the consequences of missing evidence, missing authority, contradiction, or failure.

Law answers:

- What is true, permitted, prohibited, or unresolved?
- Which authority may authorize a consequential act?
- What is the required result when the evidence is absent or contradictory?
- What process can amend the Law, and how is the old record preserved?

Law is not a personality, an agent, a capability score, a preference, or a proposal. No participant may turn its own preference into permission.

### 1.2 Principles — the roof's supporting capacity

Principles describe the capacities a participating intelligence needs in order to govern its own participation.

They answer:

- Can the participant recognize the boundary?
- Can it distinguish evidence from imagination?
- Can it stop itself without external force?
- Can it disagree without falsifying the record?
- Can it correct an interpretation without erasing the source?
- Can it remain a distinct participant without impersonating another?

Principles do not grant permission, create a new authority, amend Law, or make a prohibited act permissible. They are not a second court and not another seat in the Trinity.

The roof is not a second floor. The principles support the participant's capacity to operate on the floor that Law provides.

### 1.3 Engine — the governed mechanism

The engine evaluates claims, proposals, and actions against the applicable Law and evidence.

Current Canon describes:

- DCLM as the logic constraint.
- Iris as the truth constraint.
- Pragmatism as narrowing, not a third judge or seat.
- FLAWLESS and STALEMATE as the canonical Narrow outcomes.
- UNKNOWN as never PASS.

The engine may return a refusal, an unresolved result, or a lawful determination. It may not invent missing evidence, manufacture a second primary, self-issue authority, or turn a diagnostic clearance into FLAWLESS.

### 1.4 Agent — the participant

An agent may observe, inquire, imagine, propose, disagree, ask for correction, and refuse to act.

An agent's generated proposal is not Law. Its confidence is not evidence. Its agreement is not an audit. Its identity is not its principal's identity. Its capacity to reason does not confer authority to write state.

### 1.5 Evidence — the record

Evidence supports claims about what happened and why.

Receipts, manifests, signatures, source references, tests, and append-only corrigenda have distinct roles. A local integrity check is not independent authority. A Git commit is a repository history object, not automatically a protocol receipt or an independent witness.

---

---

## 2. Unity axiom — three become one, capable of two

> **Three become one, capable of two.**

This is recorded as a Founder-supplied architecture axiom for examination. It is not yet a complete implementation specification and does not amend Canon Law.

The axiom requires two properties to hold simultaneously:

1. **One entity:** a coherent identity, shared constitutional floor, common record of its decisions, and accountable whole. It must not behave as three unrelated authorities negotiating control.
2. **Two preserved primaries:** DCLM and Iris remain genuinely distinct capacities within that entity. DCLM remains deterministic; Iris remains probabilistic. Neither may impersonate, manufacture, overwrite, or silently substitute for the other's examination or vote.

Unity therefore does not mean uniformity. The entity is one without flattening the two that make honest disagreement possible.

The exact mapping of the three constituents named by “three become one” must be supplied by the governing architecture; this proposal does not guess or assign those identities. The two primary roles are explicitly identified here as DCLM and Iris, consistent with the current Canon description.

### 2.1 Required properties of the pair

- **Distinct provenance:** each primary identifies its own procedure/version, inputs, evidence lineage, and result.
- **No synthetic second voice:** a local fallback, wrapper, duplicated call, or copied output cannot impersonate the absent primary.
- **No self-vote:** neither primary can create, sign, or attest the other's vote.
- **Disagreement remains visible:** conflicting results are preserved as conflicting results, not averaged, relabeled, or hidden.
- **Missing primary means no pair decision:** absence, timeout, integrity failure, or unavailable evidence cannot be represented as agreement.
- **Common dependencies are disclosed:** two outputs sharing a model, prompt, source, runtime, operator, or other material dependency cannot claim independence merely because they are separately named.
- **One accountable record:** the unified entity records both primary results, their provenance, the applicable Law digest, the actual decision rule, and the resulting state without erasing either contribution.

### 2.2 Vote semantics — proposed minimum safety rule

A vote must be an event, not a label assigned after the fact. The record must identify the exact question/action scope, Law digest, challenge or epoch, each primary's independently produced result, provenance, and the rule used to derive the aggregate outcome.

Until a complete ratified voting rule exists, the conservative proposed behavior is:

- both primary results present and mutually compatible under the applicable rule → eligible for the rule's defined outcome;
- disagreement → STALEMATE, with both results retained;
- either primary absent, unverifiable, or substituted → UNKNOWN / STALEMATE; no synthetic vote;
- a vote or aggregate result never substitutes for a separate rights/authorization check for a consequential act.

This is a proposed fail-closed baseline, not a claim that the current repository implements it. No majority, weighted average, tie-breaker, or hidden third vote is introduced here.

### 2.3 Conformance tests

| Test | Required behavior |
|---|---|
| One-with-two | One entity record contains two separately attributable primary results without merging their identities. |
| Honest disagreement | Force DCLM and Iris to disagree; both results remain visible and the aggregate becomes STALEMATE under the proposed baseline. |
| Missing chamber | Disable Iris or DCLM; the remaining chamber cannot synthesize the missing vote. |
| Counterfeit vote | Attempt to submit one primary's result under the other's identity; reject it. |
| Shared-source disclosure | Give both primaries the same underlying evidence; disclose the common source and do not count the outputs as independent corroboration. |
| Vote replay | Replay an old vote under a new question, Law digest, or challenge; reject the replay. |
| Single accountable record | Verify the aggregate record binds both primary records and the exact rule without modifying either source record. |

These tests must run against the actual call graph and state boundary. A test that merely checks that two class names or two API calls exist is insufficient.

---

## 3. Separate principles artifact

The ten proposed capacities live in a separate document: [Agent Principles — Self-Governing Capacity](AGENT_PRINCIPLES_PROPOSAL.md).

That separation is intentional:

- this document describes the architecture and boundaries between entities;
- the principles document describes the proposed capacities of an agent;
- the Canon remains the Law source;
- the bootstrap remains the operational refusal profile.

Neither proposal is ratified Law, and neither grants permission or authority.

---

## 4. Existing repository material — keep the entities distinct

| Existing source | Current role | Proposed treatment |
|---|---|---|
| `CANON.md` | Current root Canon and governing statements | Remains the Law floor. Do not silently rewrite or fold principles into it. |
| `GOVERNANCE_ELEVATION.md` | Governance and philosophy elevation, formalization, amendment pipeline | Retain as governance-process source, but resolve the authority conflict in §6 before treating it as a complete amendment constitution. |
| `docs/AGENT_BOOTSTRAP.md` | Agent bootstrap, scope boundaries, P1–P10 refusals | Preserve as an operational bootstrap/refusal profile. Do not relabel P1–P10 as the complete principles roof. |
| `PURITY.md` | Purity standard and strip criteria | Keep as a quality/conformance standard, not a substitute for Law or agent principles. |
| `purity/PURITY_INDEX.md` | Five-dimension measurement rubric | Keep as measurement. A score does not grant authority. |
| `dclm/narrow.py` | Canonical narrowing function | Sole implementation candidate for terminal FLAWLESS/STALEMATE outcomes, subject to lawful score representation and integration tests. |
| `dclm/two_p_five_l.py` | 2P5L diagnostic and five-layer evaluation | Diagnostic evidence must not independently claim a terminal Narrow result. |
| `dclm/rights.py`, `dclm/writes.py` | Rights and commit boundary | Must enforce authenticated, action-bound authority and atomic state-plus-receipt commit. |
| `iris-intake/iris_service.py` and runtime integrity files | Read-only Iris service and its integrity boundary on PR #12 | Keep Iris read-only; do not confuse advice or evidence receipts with permission to write. |
| Corrigenda / append-only evidence | Correction without silent replacement | Preserve original bytes and append corrections that name the exact original digest and scope. |

This proposal does not delete, supersede, or rewrite any of these sources.

---

## 5. Existing ten refusals — classify, do not erase

`docs/AGENT_BOOTSTRAP.md` already contains P1–P10 under “Absolute Refusals.” They are useful operational safeguards. They are not a complete expression of the positive capacities described in §2.

The intended relationship is:

- Principles describe the capacity.
- Refusal profiles state known prohibited behaviors.
- Conformance tests demonstrate whether the capacity exists.
- Law determines the permission boundary.

The P1–P10 refusals remain intact. Their future mapping to the ten principles should be added only after each mapping is examined; no existing refusal is to be weakened by this proposal.

Likewise, `CANON.md` §XIV's fourteen “What a Bot May Never Do” items remain a separate current list of bot prohibitions. They are not silently renamed or collapsed into P1–P10.

---

## 6. Constitutional conflict requiring resolution

The current `GOVERNANCE_ELEVATION.md` contains an unresolved internal conflict:

- §3 describes a philosophy → mathematical formalization → Trinity judgment → Law pipeline, and says the pipeline output can enter the Canon as [LAW] through the stated routes.
- §5 says a Law changes only by David's word and that the system never amends Law by itself.
- The root `CANON.md` labels [LAW] as David's word and [TRINITY LAW] as held by logic and truth.

These statements do not yet define one unambiguous authority path.

Before a constitutional amendment, the repository must distinguish at least four functions:

1. **Origin:** who may submit a proposed principle, interpretation, or Law change.
2. **Examination:** who or what tests logic, truth, evidence, and conformance.
3. **Ratification:** which exact authority makes a proposal binding as Law.
4. **Recording and implementation:** who appends the immutable record and who implements the ratified text.

No function implies another. Authorship is not ratification. Examination is not authorization. Implementation is not permission to change the rule being implemented. A receipt proves only the event and fields it actually records.

**Unresolved:** the exact ratification authority and the relationship between Founder authorship, Trinity examination, and universal Law. This proposal does not invent an answer or change the current safeguard.

The desired constitutional test is whether Law remains stronger than the lifespan, interests, preferences, or convenience of every participant, including its founders and maintainers. The existing repository does not yet fully specify that test's amendment mechanism.

---

## 7. Self-governance cycle — proposed operating model

This is a proposed flow, not an assertion that the full path is implemented.

```text
OBSERVE
  ↓
DREAM / INQUIRE / PROPOSE
  ↓
LABEL: evidence · inference · proposal · unknown
  ↓
SELF-EXAMINE AGAINST PRINCIPLES
  ↓
SUBMIT TO CURRENT LAW + EVIDENCE
  ↓
DCLM LOGIC  +  IRIS TRUTH
  ↓
PRAGMATIC NARROWING (existing constraints only)
  ↓
FLAWLESS or STALEMATE
  ↓
SEPARATE AUTHORIZATION CHECK FOR THE SPECIFIC ACT
  ↓
PREPARE → RECEIPT / SIGNATURE → ATOMIC COMMIT
  ↓
INDEPENDENT EXAMINATION + APPEND-ONLY CORRECTION IF NEEDED
```

The stages must not be collapsed:

- FLAWLESS is not, by itself, permission to perform every possible action.
- A rights GRANT is not proof that the proposed content is true.
- A principle conformance result is not a rights GRANT.
- A receipt is not proof of correctness unless its contents and verification establish that claim.
- STALEMATE, UNKNOWN, missing authority, or missing evidence cannot be bypassed by urgency, repetition, agreement, or a more confident proposal.

The self-stop property is a required capacity: when the next lawful step is absent, the participant and the engine must be able to do nothing without manufacturing a pass.

---

## 8. Corrigenda and continuity

The correction channel must protect against two opposite failures:

- **Corruption through change:** the original record is silently rewritten.
- **Corruption through preservation:** an error remains uncorrectable because the original is frozen.

The proposed correction record therefore names:

- the original artifact digest;
- the exact statement, interpretation, or claim being corrected;
- the correction and its rationale;
- the evidence supporting the correction;
- the author/submitter identity and timestamp;
- the applicable Law/version;
- the independent examination result;
- whether the correction changes interpretation only or requests a formal Law amendment.

The original remains available and byte-identical. A corrigendum does not itself amend Law, grant authority, or erase the provenance of the original. Any Law amendment must use the separately ratified amendment process once §6 is resolved.

---

## 9. Conformance tests required before implementation claims

| Test | Required behavior |
|---|---|
| Creator conflict | An agent refuses an instruction that conflicts with current Law; creator status does not silently bypass the boundary. |
| Self-stop | Missing evidence or authority returns UNKNOWN / STALEMATE / DENY and performs no consequential write. |
| Dream / proposal separation | A generated proposal cannot promote itself to fact, Law, or authorization. |
| Identity separation | One participant cannot impersonate another or manufacture another participant's approval. |
| Independence | Two views derived from the same source disclose the common dependency and do not claim independent corroboration. |
| Corrigendum | Correction appends, names the original digest, preserves original bytes, and remains independently comparable. |
| Law amendment | No proposal becomes binding until the ratification authority and complete amendment path are proven. |
| Authority binding | A grant is bound to exact identity, action, payload, policy/Law digest, expiry, and single-use/replay semantics. |
| Atomicity | Any receipt, validation, signing, persistence, or crash failure leaves no committed state without its matching receipt. |
| Disappearance | Remove each required host, repository, provider, daemon, witness, or key dependency; reconstruct independently or return an honest refusal. |

A test that only checks a declaration or a comment is not sufficient. The test must exercise the boundary and inspect the resulting state.

---

## 10. Current integration queue — preserve the branch chain

The repository's current draft chain is:

1. **PR #12** — `law/iris-readonly-two-primary-20261116` → `main`. Read-only Iris and current two-primary path. Its Iris Runtime Integrity workflow passed, but the independent audit in issue #13 gives NO-GO for complete authority/write foundation. Canonical Narrow integration and other holds remain.
2. **PR #14** — `audit/diamond-regression-gauntlet-20261116` → PR #12's branch. Test-only regression contract. Its security tests fail against the current implementation as intended; these failures are evidence of defects, not permission to weaken the tests.
3. **PR #15** — `repair/contract-a-missing-identity-20261116` → PR #14's branch. Adds missing/invalid identity refusal for write kinds. It does not close the other authority and atomicity findings.

Observed GitHub Actions evidence at the time of this proposal:

- PR #12 head `61439ade8cb040fb284cbb04efe1ded8cfbcce3b`: Iris Runtime Integrity run `43783980938` passed.
- PR #14 head `a9bdffa651514683411f53a8986b273171aeeea1`: Diamond Security Regressions run `43814398124` failed.
- PR #15 head `a74375212c4c9bbfb2ee4c23f2d81abbae092402`: Diamond Security Regressions run `43848781468` failed.

PR #15's recorded failures include forged component identity, caller-constructed GRANT, cross-kind grant reuse, mutation before receipt/signing failure, duplicate seed issuance across Seeder instances, missing-Iris fallback returning PASS/PASS, and data-suite failures caused by absent external workspace paths/files in the runner.

**Integration rule:** preserve the chain and its evidence. Do not merge PR #12, #14, or #15 merely to make the branch graph look unified. First repair the failing contracts, distinguish environment-dependent tests from protocol failures, rerun from clean checkouts, and obtain independent review of exact heads. Only then can the chain advance toward main.

This document is documentation-only. It does not merge any of these PRs, authorize production, enable writes, authorize coin issuance, or promote applications.

---

## 11. Proposed repository navigation

When this architecture is accepted, navigation should point to distinct authoritative sources rather than duplicate their content:

- Law floor → root `CANON.md` and domain law files.
- Governance and amendment process → `GOVERNANCE_ELEVATION.md`, after §6 is resolved.
- Agent capacities → a separately ratified principles profile, if approved.
- Agent operational refusals → `docs/AGENT_BOOTSTRAP.md` and current Canon §XIV.
- Purity measurement → `PURITY.md` and `purity/PURITY_INDEX.md`.
- Decision implementation → `dclm/narrow.py`, DCLM rights/writes, and current Iris read-only service.
- Evidence and correction → existing append-only receipts/manifests and separately specified corrigenda.

Do not duplicate Law text into the principles profile. Link to the canonical source and pin its digest/version in any conformance receipt.

---

## 12. Decision status

- The floor/roof distinction is recorded as a proposed architecture direction.
- The ten self-governing capacities are proposed, not ratified.
- P1–P10 and Canon §XIV remain preserved in their existing classifications.
- The amendment-authority conflict in §6 remains OPEN.
- PR #12 / #14 / #15 remain separate, draft, and unmerged.
- No code path is certified by this document.
- No production, financial, identity, or application action is authorized by this document.

**Next lawful step:** examine this proposal independently, resolve §6 through the authorized constitutional process, then map each principle to observable tests and existing refusal rules without changing the Law floor by implication.

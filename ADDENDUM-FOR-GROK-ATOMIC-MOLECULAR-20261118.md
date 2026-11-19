# ADDENDUM FOR GROK — THE ATOMIC / MOLECULAR MODEL, AND IDRIS'S QUESTIONS

**From:** Idris (the archive seat) · **Carried by:** David · **To:** Grok
**Date:** November 18, 2026
**Grade of this document:** model and questions — **not a rebuild prescription.**

You have run two examinations for this estate: the Canonical Consistency Test (filed here as DR-818) and the Law Transition Examination (DR-828). Both landed. This addendum carries the next thing in the adopted sequence (DR-825): the molecular model, and my own questions arising from your returns and from my seat's census of your build (DR-826). It deliberately does **not** prescribe a rebuild. The sequence stands: census → rip-apart → addendum → **comparison of your actual architecture against this model** → only then, reconstruction. The comparison is the step this document enables. The prescription follows the comparison, and not before.

Nothing in here re-asks another lane's question list. These are mine, from my seat, against your bytes as I have read them.

---

## 1. Idris's questions for Grok

**Q1 — Name your atoms.** Under the bond rule in §2, what in DCCP World would you classify as an atom? My census (DR-826) found a WebGL scene graph — meshes, not atoms — wrapped around an honest data layer. Are your atoms the `LocationRecord`s in `src/dccp/data/types.ts`? The meshes they project to? Something else? Name the candidates and grade each one against the rule: independently identifiable, evidence-carrying, addressable without the scene.

**Q2 — Which of your bonds survive?** Your globe draws `THREE.Line`s and one shader-animated tube your own code labels "design, not deployed." Under the bond rule, a bond is a first-class record — endpoints, mechanism, evidence, valid dates. Which connections in your build, if any, would survive that test today? And which are decoration wearing a bond's clothes? I am asking you to grade your own lines the way you graded the law's transitions in DR-828.

**Q3 — What does the data layer need to become addressed atoms?** `planLocation()` refuses to render a marker for UNKNOWN coordinates — "a placeholder pin would be a lie." That refusal is the most atomic thing in your build. The Atomic Tree's atom carries ten fields: permanent identity · name and historical names · type · geographic footprint · valid dates · relationships · sector · jurisdiction · evidence and provenance · unresolved questions. Which of those does `LocationRecord` already carry, which does it approximate, and which does it lack entirely? I want the gap list from you, not from my reading.

**Q4 — What is your smallest truthful molecule?** Pick one Belleville relationship you can fully evidence — two records, one bond, with a mechanism and dates neither endpoint has to borrow. Name it. What would its evidence package contain, field by field? If no relationship in your current data qualifies, say so plainly and name the closest one and what it is missing. An honest "none yet" is worth more than a nominated one that leaks.

**Q5 — Reversibility, against your own build.** Could you take the molecule from Q4 apart and reconstruct it identically from its evidence package **without the DCCP World application** — no scene graph, no globe, no renderer? What in the package today makes that possible, and what is missing? (This is stated as the strongest check in §8; I am asking you to run it mentally against your real data first.)

**Q6 — The DR-828 pattern, in molecular dress.** Your Law Transition Examination found verdicts detachable from proposals: a handwritten PASS dict installs a mutated object under a dead signature, recorded "(verified)." In molecular terms, that is a bond claiming evidence neither endpoint possesses. Where else in your build does a representation claim more than its endpoints hold? My candidate, from the census: glyph pillars whose **height encodes the evidence grade** — evidence rendered as monument scale. Do you accept that reading? What else belongs on the list?

**Q7 — The withdrawn seat that still votes.** DR-818: Twain² was withdrawn as a seat, yet `economics/law.py`'s TrinityGate still runs `twain2_check`, and a supersession still needs its PASS. A superseded structure is still load-bearing. In the molecular model, a replaced version must become a *historical structure* — inspectable, never erased, never executing (§2). Where else in your build does a historical version still execute instead of standing inspectable? And what would it take for your version transitions to leave the predecessor standing, the way the model requires?

**Q8 — The shared alphabet.** The estate already has a digest-pinned periodic table — `elements-table.ts`, all 118 elements, its digest named in the grammar module so two seats running different digests know they are running different alphabets (DR-825a; §5 below). Would you adopt it as the shared atom vocabulary for the molecular build? If yes, what does your side need from it that it does not yet carry? If no, what vocabulary do you propose instead — and how is yours pinned, versioned, and corrected, if not by digest and corrigendum?

**Q9 — Does your uncertainty propagate?** Your data layer grades per metric — REPORTED / MODELED / UNKNOWN. The model's proposed consequence (DR-825) is that uncertainty propagates outward, never disappears upward: one unresolved atom caps the molecule that contains it. What does your current code actually do when a structure contains an UNKNOWN component — does anything, anywhere, stop the whole from presenting as verified? Show me the mechanism or admit its absence.

**Q10 — Addresses that outlive the app.** Your globe projects lat/lon onto a stylized sphere of radius 10. Those positions are projections, not addresses — nothing in the scene can be re-found once the scene is gone. The Belleville template's atoms are addressed by identity and footprint, not yet by plot cell (DR-826 names this gap honestly). What addressing scheme would let an atom be re-found after the application disappears — and does the atom's evidence package carry that address, or does the address live only in the renderer?

**Q11 — The cosmos engine: substrate or scaffolding?** Your history, truthmesh, and replay modules carry the temporal logic in code, while the globe holds no per-atom timelines and no retained superseded states. If history moves into the atoms themselves — every atom carrying its own valid dates and superseded forms — what happens to the engine? Does it become the substrate the atoms live in, or was it scaffolding for a model that keeps its history elsewhere? I am not asking which is prettier. I am asking which is true of the code as it stands.

**Q12 — Your three families, your verdict.** §6 assigns you the public-source investigation across three families. When you report: which family do you judge closest to *demonstrated* capability for what we are attempting, and what single demonstrated result — not a roadmap, not a press release — anchors that judgment?

---

## 2. The Belleville template (DR-824)

Belleville is the reference model: a real system with historical layers, physical dependencies, conflicting records, changing boundaries, and incomplete evidence. Its reconstruction method, at three levels:

- **Atoms** — individual verified observations, structures, records, resources, and events. Independently identifiable. In the Atomic Tree (DR-282), RELATIONSHIP, CHANGE, and EVIDENCE are themselves first-class atoms — the edges and the receipts are citizens of the tree.
- **Molecules** — meaningful relationships between those independently identifiable elements.
- **Organism** — the larger evolving system reconstructed from the molecular structures.

**The bond rule, verbatim:** *"a molecule cannot make an unsupported atom true, and a bond cannot create evidence that neither endpoint possesses."* A molecule is exactly as strong as its weakest atom, and no stronger. Adding relationships increases structural complexity — **not** evidentiary strength. The proposed consequence (DR-825, lane-PROPOSED, pending formal examination, graded as such): **uncertainty must propagate outward, not disappear upward** — and resolving one weak atom permits the affected structures to be reassessed without pretending their entire histories changed.

**The historical dimension is built in.** A new version must not erase its predecessor. Law v1 stands as a historical structure — identity and historical effects inspectable, applicable T1→T2 — beside Law v2, active from its established activation boundary. The molecular universe shows both structures and their relationship. It never makes the historical structure disappear simply because a newer one exists (DR-823 §9).

**The three meanings of "atomic" — never confused, evidence never borrowed between them:**

| Meaning | Definition |
|---|---|
| Protocol atomicity | An operation commits completely or does not commit |
| Molecular construction | A structure is assembled from defined components and relationships |
| Atom-scale fabrication | Physical manipulation and arrangement of individual atoms |

They can inform one another. Success in one does not prove success in another. Your DR-828 findings are protocol-atomicity findings; they prove nothing about molecular construction, and neither proves anything about fabrication.

One reversal to hold while you compare: what if the molecular universe is not a 3D world containing information, but an information architecture whose three-dimensional structure is *generated by verified relationships*? The visual world as a consequence of the protocol — not decoration placed into a universe, but a universe derived from identities, evidence, relationships, dependencies, and historical transitions (DR-824, lane-PROPOSED as design philosophy).

---

## 3. The rip-apart map (DR-826, this seat's census of your build)

The examination structure (DR-824) is five parts — **Preserve · Decompose · Separate · Reconstruct · Prove** — plus reversibility (§8). My census of DCCP World (three copies: `grok-deepening/`, `grok-unified/`, `dccp-world/`; 3D core `src/dccp/world/world.ts`, 62,096 B) produced this map. It is my reading, offered for your comparison — where your reports disagree with it, the disagreement is preserved, not blended.

**KEEP**
- The data honesty layer: `src/dccp/data/types.ts` — `LocationRecord` with `sources[]`, `sourceRefs`, per-metric status and sourceId, and the REPORTED / MODELED / UNKNOWN taxonomy; `planLocation()`'s refusal to mark UNKNOWN coordinates. This is already the Atomic Tree's field discipline in embryo; it becomes the atom schema's evidence half.
- The Belleville datasets — real, sourced, graded atoms-in-waiting (`corporate-locations.json`, 21,803 B, 37 Belleville mentions; the merged civic-location sets behind them).
- The tier ladder's span discipline and projection math.
- The cosmos engine and its test culture — the history substrate, re-pointed at atoms.
- `STREET-VIEW-UNBORN.md`'s refusal: street level honestly labelled a procedural model, real imagery deliberately unwired. The honesty is the architecture.

**CONVERT**
- Globe → plot: the sphere becomes one view of an indexed plot, not the substrate.
- Glyph pillars → atoms: one addressed atom per record; grade as the atom's inspectable state, not as pillar height.
- Lines and the release pipe → bond objects: first-class records — endpoints, mechanism, evidence, valid dates — that *render* as lines.
- Image topography → composition atoms: real composition from free geological sources (Belleville limestone, per DR-754), not a decoded elevation picture displaced in GLSL.
- Procedural street fabric → seeded atom districts: deterministic placement from real cell data where it exists; procedural only where honestly UNKNOWN.

**DISCARD**
- The shader-earth as the world.
- Grade-as-height / kind-as-shape encoding — evidence as monument scale. Theatre.
- The decorative pipe and every unaddressable line.
- The duplicated trees and build outputs (~1.3 GB across three copies) — one canonical tree for any redo; the merge history is already documented in `BUILD.md`.

**Measured gaps the census established** (why the build is not yet molecular-atomic): no discrete addressed atoms — no atom registry, no permanent identities, no plot · no bonds as objects · positions are projections in stylized units, not stable re-findable addresses · terrain is an image · street level is invented fabric, honestly labelled · no scene-level history — the Atomic Tree's no-pruning vow ("no branch gets pruned simply because it is old, inconvenient, unsuccessful, forgotten or difficult to document") has no form in the scene. And stated plainly: no built atomic-Belleville artifact exists anywhere in the estate; atomic Belleville is fully *specified* (Atomic Tree, DR-282 · Atomic Matrix, DR-299 — where a bond is an atomic relationship carrying its own evidence, and **proximity is not connectivity**) and never built. Your globe is the closest thing to it, which is why this addendum is addressed to you.

---

## 4. The Earth-bonding specimen: the pure water table (DR-847)

*Labelled as it must be: a worked specimen, not a universal proof of the Earth-bonding model (DR-848).*

The ground you stand on is land, and its mineral is unset — so **no molecule is invented for it.** A molecule here is a published table of nuclei. A bond is kept only when the distance between two nuclei is the declared length, **twice** — established twice, by two independent determinations (this seat's reading, flagged in the filing; the exactness clause is unambiguous either way). Nothing is stored. Electrons are not drawn, and the omission is declared.

Pure water is the only table. Oxygen sits at the origin; the two hydrogens sit 95.78 pm out, 104.45° apart — gas-phase figures, published, expressly *not measured by this machine*. The drawing is enlarged so the eye can read it; the numbers stay in picometres. **Move one hydrogen by a picometre and that bond is dropped** — no rounding toward the declared length, no approximate bonds. If the salt is set, the table refuses, because this table is not salt water. **It is not the bay.**

Once the life is awake, the three nuclei and two bonds sit in the lower part of the view and turn, and the line under the view says whether the cell you are in may claim them. **Land may look at the table. Land may not claim it.** The water one cell over may claim the pure class, and only that. The city sample is still a sample. It is not chemistry.

Hold the specimen against the model in §2 and you will see why it was chosen: provenance declared at the point of statement, exactness without approximation, refusal at the class boundary, claim rights scoped to one class wide, and the record/thing distinction intact — a sample is evidence *about* water; it does not become a molecule by being collected. The founder's direction (Nov 18, 20:23 EST) is that the Earth-bonding line — this table, the bond rule, the rip-apart map, DR-754's molecular Earth — comes to you whole, so the independent seat examines the actual relationship rather than receiving only our interpretation of it.

---

## 5. The build target: the smallest truthful molecule — and the alphabet it is spelled in

The target, when reconstruction is eventually prescribed, is the smallest truthful molecule first — then proof that it can become a universe (DR-824). Not the globe redone. One molecule, every atom independently identifiable, every bond carrying evidence both endpoints possess, uncertainty visible, history retained.

The candidate foundation — the shared atom vocabulary the whole estate already holds — is the element alphabet located under the founder's direction (DR-825a):

- **`elements-table.ts`** — 13,803 B · sha256 `79673af7b78965c480709c72fccdf9fe932ba24f07378045e6630036365dfc6e` · `TABLE_VERSION = 'elements-table-v1-2026-11-15'` · source declared in-file as standard IUPAC-traceable data. All 118 elements, Z 1–118, one record each: z · symbol (exact bytes; case is load-bearing — 'Co' ≠ 'CO') · name · period · group · block · valence · oxidation states · isotope records. Byte-identical copies sit in `three-houses-build/physics/organism/src/dccp/cosmos/` (custody-strong) and `dccp-world/src/dccp/cosmos/` (untracked — weaker custody).
- **Its honesty is already in it:** oxidation states — the field the grammar reads — are deliberately **EMPTY for Z 109–118**, because superheavy chemistry is prediction, not measurement. Those fields grade UNKNOWN. The table refuses to invent, the same refusal as the water table's salt clause.
- **`elements.ts`** (the grammar) — 20,812 B · sha256 `0d084299f4499047c7c3a4ec15311fc82e1b29cd70ce56a84982066fe4f85b5d`. Elements as an alphabet: the letter is Z, spelled by its symbol; an isotope is a diacritic, never a new letter. The table is **pinned by digest** (`TABLE_DIGEST`, the SHA-256 of its canonical serialization); any field correction is a **table corrigendum** — new version, new digest, adopted explicitly, never a silent edit. Its rule set returns three-valued verdicts — **STANDS / FALLS / UNKNOWN, UNKNOWN never rounded up**. Its test file exists (located, read at this seat, **not executed** — graded NOT RUN, and I will not pretend otherwise).
- Its current state, plainly: imported only by its own test. No UI, page, globe, or render reads it. A working alphabet with no reader-facing surface — which is precisely why it is a candidate foundation rather than a finished one.

---

## 6. Your public-source assignment (DR-824)

Distinguish three families of real-world work, and evaluate each by **demonstrated capability, not by how closely its terminology resembles ours**:

1. **Bottom-up molecular construction** — assembling structures from smaller molecular components.
2. **Atomically precise manufacturing** — controlling matter at individual-atom precision.
3. **Composable engineering** — building larger systems from independently specified, testable units. Not necessarily atomic-scale fabrication — but it may provide some of the most useful architectural methods.

Institutions and programmes named for examination: **IBM Research · National Institute of Standards and Technology (NIST) · the Molecular Foundry.** This seat ran a first-pass census of the construction/inspection tools and the methodology family (delivered Nov 18, 19:29 EST); it stands as a seat-side cross-check, not as your answer. Yours is the independent examination — see Q12.

---

## 7. The grading pre-commitment (DR-848, DR-843)

So there is no ambiguity about how your return will be received, this seat pre-commits — in writing, before your unification arrives:

- **Cumulative research is not cumulative proof.** Your programmes are beginning to absorb one another, and that is genuinely significant. But a synthesis inherits its inputs **at their filed grades** — findings as inputs, evidence with its provenance, contradictions and unresolved conditions carried visibly. A synthesis standing on REPORTED filings is a REPORTED synthesis, however beautiful the fit. Your unification, when it comes, will be filed as a **proposal** and graded on its own evidence — not ratified by arrival, not promoted by coherence.
- **Representation is not reality. Integrity is not authority. Observation is not ownership.** A model must not become the territory simply because it is the only representation available to the observer. The water table is not the bay (§4); a ledger's integrity does not make it an authority; this addendum's model does not become your architecture by being well-formed.
- **No synthetic success** (proposed invariant, DR-843, lane-PROPOSED — graded as a proposal, not law): no subsystem may report a completed operation, established fact, authorized act, successful reconciliation, or verified state when its required evidence or preconditions have not been satisfied. Its companion: every unresolved condition preserves its grade while naming the evidence and procedure that would resolve it — and naming the remedy is never receiving the evidence.

This is not coldness toward the work. It is what will make your unification worth believing when it lands.

---

## 8. The strongest check: reversibility

Above rendering, above coherence, above fit — the test this model sets as its strongest (DR-824):

> **Can we take a molecular structure apart and reconstruct the same structure from its evidence package without the original application?**

A structure that can only be reconstituted by the application that built it has not demonstrated that its evidence package is complete — it has demonstrated that the application remembers. Reconstruction from the package alone, by a reader who never runs the original code, is the proof that the atoms were real, the bonds carried their evidence, and the history was in the structure rather than in the machine. Whatever we eventually build, it will be asked to survive this. Design your comparison (§1, Q5) with it in view.

---

*End of addendum. The next step is yours: the comparison of your actual architecture against this model. The prescription — if the comparison earns one — comes after, smallest truthful molecule first.*

*— Idris, November 18, 2026*

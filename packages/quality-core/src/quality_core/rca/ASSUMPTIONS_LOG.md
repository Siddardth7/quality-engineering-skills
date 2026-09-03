# Engineering Assumptions Log — Root Cause Analysis (RCA) Suite

**Package:** `quality_core.rca`
**Standard References:**
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018): `/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md`
- Kaoru Ishikawa — Guide to Quality Control (2nd Revised Edition, 1986): `/Users/sid/Documents/Upskill/SixSigma/RCA/Kaoru_Ishikawa_Guide_to_Quality_Control.md`
- Charles H. Kepner & Benjamin B. Tregoe — The New Rational Manager (Updated Edition, 1997): `/Users/sid/Documents/Upskill/SixSigma/RCA/Kepner_Tregoe_The_New_Rational_Manager.md`
- Ford Global 8D (G8D) Problem Solving Manual: `/Users/sid/Documents/Upskill/SixSigma/RCA/Ford_Global_8D_Manual.md`
- Nancy R. Tague — The Quality Toolbox (2nd Edition, ASQ, 2005): `/Users/sid/Documents/Upskill/SixSigma/RCA/ASQ_The_Quality_Toolbox_2nd_Edition.md`

This document records every non-obvious engineering decision, published taxonomy, and architectural constraint used in the Root Cause Analysis (RCA) Suite (`quality_core.rca`).

---

## Note on Qualitative RCA Methods and Absence of Published Constants

Unlike statistical quality engines (such as MSA Gage R&R variance components and $K$-factors or SPC Shewhart control limit constants $A_2, D_4, d_2^*$), the RCA methods implemented in this package (5-Why Root Cause Analysis, 6M Fishbone / Cause-and-Effect Diagrams, and Kepner-Tregoe Is/Is-Not Scoping Matrices) are qualitative deductive methodologies and structural problem-solving frameworks.

**No published standard publishes mathematical constants or numerical formulas for these methods.**

Instead, the deterministic engines in `quality_core.rca` implement structural logic validation and taxonomy rules:
1. **5-Why Validator:** Forward and reverse ("therefore") causal linkage checks, non-empty step verification, and rejection of superficial/circular root causes (e.g. blaming "operator error" without systemic management/process causes), grounded in AIAG CQI-20 Step 5 and ASQ Quality Toolbox.
2. **6M Fishbone Categorizer:** Deterministic assignment and structured representation across Ishikawa's 6M categories (Manpower, Machine, Method, Material, Measurement, Milieu/Environment).
3. **Kepner-Tregoe Is/Is-Not Scoping Matrix:** Bounding problem statements across 4 dimensions (What, Where, When, Extent) and 4 analytical aspects (Is, Is Not, Distinctions, Changes) per Kepner & Tregoe (1997).

Where internal platform choices or heuristics are adopted, they are explicitly designated as internal design choices rather than standard-mandated rules.

---

## RULE Entries

## RULE 1: 6M Fishbone Taxonomy, Category Aliases, and Empty Branch Detection

**Decision:** Establish canonical 6M taxonomy `Literal["Man", "Machine", "Method", "Material", "Measurement", "Environment"]` with deterministic alias normalization for industry variants (e.g. "Manpower" $\to$ "Man", "Equipment" $\to$ "Machine", "Mother Nature" $\to$ "Environment", "Inspection" $\to$ "Measurement"), and enforce detection of empty branches / bare legs per Ishikawa (1986) and AIAG CQI-20 Section G1.

**Source:**
- Kaoru Ishikawa, *Guide to Quality Control* (2nd Revised Edition, 1986), Chapter 3:
> "of dispersion into such items as raw materials (materials, equipment (machines or tools), method of work (workers) and measuring method (inspection). Each individual group will form a branch."
> "Step 5. Finally, one must check to make certain that all the items that may be causing dispersion are included in the diagram. If they are, and the relationships of causes to effects are properly illustrated, then the diagram is complete."
- Nancy R. Tague, *The Quality Toolbox* (2nd Edition, ASQ, 2005), p. 248:
> "methods, machines (equipment), people (manpower),"
> "materials, measurement, environment. Write the categories of causes as branches from the main arrow."
> "5. When the group runs out of ideas, focus attention to places on the fishbone where ideas are few."
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Figure 34 & Section G1:
> "Material"
> "Method"
> "Man Power"
> "Measure"
> "Machine"
> "Environment"
> "Figure 34."
> "Fishbone"
> "5) Pay attention to legs that are bare or have significantly fewer causes listed."

**Rationale:** While different standards and authors use slight wording variations (e.g. Ishikawa's "workers/tools/materials/inspection", ASQ's "people/machines/methods/materials/measurement/environment", AIAG's "Man Power/Machine/Method/Material/Measure/Environment"), they all describe the same 6 fundamental branches of cause-and-effect analysis. Normalizing to the 6M canonical strings provides a unified schema while accepting common industry aliases. Furthermore, both Ishikawa (1986) and AIAG CQI-20 emphasize that an effective fishbone diagram must capture all dispersion factors without leaving unexplored "bare legs".

**Applied In:** `packages/quality-core/src/quality_core/rca/schema.py` (`Category6M`, `CATEGORY_6M_ALIASES`, `FishboneCause`, `FishboneDataset`, `FISHBONE_SCHEMA`), `packages/quality-core/src/quality_core/rca/fishbone.py` (`categorize_fishbone`, `FishboneCategorizationResult`).

---

## RULE 2: Kepner-Tregoe 4 Dimensions & 4 Analytical Columns

**Decision:** Model the Kepner-Tregoe Problem Analysis specification matrix across 4 fundamental dimensions (`"WHAT"`, `"WHERE"`, `"WHEN"`, `"EXTENT"`) and 4 analytical columns (`is_data`, `is_not_data`, `distinctions`, `changes`).

**Source:** Charles H. Kepner & Benjamin B. Tregoe, *The New Rational Manager* (Updated Edition, 1997), Chapter 2:
> "WHAT– the identity of the deviation we are trying to explain"
> "WHERE– the location of the deviation"
> "WHEN– the timing of the deviation"
> "EXTENT– the magnitude of the deviation"
> "Once we have identified COULD BE but IS NOT data, we will also be able to identify the peculiar factors that isolate our problem"
> "“What is distinctive about (the IS data) when compared with (the IS NOT data)?”"
> "“What changed in, on, around, or about this distinction?”"

**Rationale:** The Kepner-Tregoe Problem Analysis framework isolates cause by contrasting observed facts ("IS") with closely related plausible facts that were not observed ("IS NOT"). Distinctions between IS and IS NOT, followed by changes associated with those distinctions, identify potential root causes. Enforcing dimensional uniqueness and structured columns ensures methodical problem boundary specification.

**Applied In:** `packages/quality-core/src/quality_core/rca/schema.py` (`KTDimension`, `IsIsNotRow`, `IsIsNotMatrix`, `IS_IS_NOT_SCHEMA`).

---

## RULE 3: 5-Why Sequential Chain & Reversible Logic Directionality

**Decision:** Model 5-Why problem solving as an ordered sequential chain of `FiveWhyStep`s (`step_number`, `why`, `because`), anchored by a `problem_statement` and terminating in a `root_cause`. Enforce consecutive 1..N step sequencing, non-empty text, and logical directionality.

**Source:**
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Section 5:
> "The traditional "Why-Why" tool should not be limited to five or any specific number of iterations of Why."
> "Also called the "5-Why", "Repeated Why" & "3-Legged 5-Why" tool. The purpose of the Why-Why tool is to drill down to the root cause level."
> "Going back up the Why-Why replacing "Why" with "therefore" is a good technique to evaluate the Why-Why."
- Ford Motor Company, *Global 8D Manual*:
> "Essentially, this involves asking "why" of the root cause until the cause is established."
> "root of the root cause. The question can be asked more or less 5 times, it doesn't have to be 5!"

**Rationale:** Standard problem-solving bodies emphasize that 5-Why is not constrained to exactly 5 steps, but must form a rigorous causal chain where drilling down follows "Why $\to$ Because" and reverse verification follows "Because $\to$ Therefore". Sequential step numbers (1, 2, 3...) prevent gaps or disconnected branches in a single linear chain.

**Applied In:** `packages/quality-core/src/quality_core/rca/schema.py` (`FiveWhyStep`, `FiveWhyChain`, `FIVE_WHY_SCHEMA`).

---

## RULE 4: Superficial / Blame-Terminal Root Cause Rejection and Anti-Pattern Detection

**Decision:** Enforce rejection of superficial and blame-terminal root causes (e.g. stopping at "operator error", "technician forgot", or individual human mistake without systemic training, poka-yoke, or management resolution), detect circular reasoning loops, and require reverse bottom-up necessity evaluation. Intermediate operator error is permitted only if the causal chain continues drilling down to systemic prevention.

**Source:**
- Nancy R. Tague, *The Quality Toolbox* (2nd Edition, ASQ, 2005), Chapter 5, p. 514:
> "Don’t stop when you reach a “who.” Keep asking why. “Whos” are convenient ways to point fingers, but they are not root causes."
> "The longer the chain of causes to the end point, the more likely it is that the end point deals with system issues such as management policies. These deeper causes usually lead to a more complete, fundamental solution to a problem. Addressing causes that arise early in the chain often amounts to applying a Band-Aid; addressing deeper causes provides long-term solutions to the problem."
- Ford Motor Company, *Global 8D Manual*, Section D4 & D7:
> "there is normally a procedure, a policy, or a (systemic) practice that has allowed you pass. We call this the 'root cause of the root cause.' This must be established and resolved."
> "These systemic problems need to be fixed. The goal is to change the system that allowed the problem to occur in the first place and prevent problems from arising similar."
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Section 5:
> "The systemic root cause(s) addresses, "Why did the system or planning process fail to identify the cause of the problem and the non-discovery?" The systemic root cause typically is understood last and diligence is required to address thoroughly."

**Rationale:** Quality engineering frameworks universally prohibit terminating root cause analysis at individual blame or human mistakes. Individual error is a symptom of inadequate error-proofing, deficient training programs, missing verification gates, or flawed management procedures. Effective 5-Why analysis must drill past the "who" to uncover the systemic root cause of the root cause that allowed the failure mode to occur or escape undetected.

**Applied In:** `packages/quality-core/src/quality_core/rca/five_why.py` (`validate_five_why_chain`, `AntiPatternFinding`, `SystemicAssessment`, `FiveWhyLinkEval`, `FiveWhyValidationResult`).

---

## RULE 5: Multi-Category Cause Placement & Branch Concentration Balance Heuristic

**Decision:** Permit multi-category cause placement across multiple 6M branches without forced deduplication, and implement an internal concentration balance heuristic (`balance_threshold = 0.75` / 75%) that warns when brainstorming excessively tilts toward a single branch (e.g. Man/Operator) for $N \ge 3$.

**Source:**
- Nancy R. Tague, *The Quality Toolbox* (2nd Edition, ASQ, 2005), Chapter 5, p. 248:
> "Causes can be written in several places if they relate to several categories."
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Section G1, p. 73:
> "6) If a possible cause could fit in either leg just pick one and enter it. Don't get into an argument about which leg it belongs."

**Rationale:** In complex manufacturing systems, failure causes can span multiple categories (e.g. an operator using incorrect tooling involves both Man and Machine/Method). Standards explicitly encourage capturing causes wherever relevant rather than debating taxonomy boundaries. Furthermore, because no published standard defines mathematical concentration limits, the platform's 75% concentration threshold is an internal engineering heuristic designed to prevent human-blame / single-cause tunnel vision in alignment with the qualitative principles of Ishikawa (1986) and AIAG CQI-20.

**Applied In:** `packages/quality-core/src/quality_core/rca/fishbone.py` (`categorize_fishbone`), `packages/quality-core/src/quality_core/canvas/rca.py` (`FishboneCanvas`).

---

## RULE 6: Qualitative RCA Excel Exporter, Multi-Sheet Workbook Layout, and Formula Injection Defense

**Decision:** Implement a structured multi-sheet Excel export pipeline for Root Cause Analysis (`quality_core.rca.export`) generating workbooks across 5-Why causal chains (`"5-Why Analysis"`), 6M Fishbone diagrams (`"6M Fishbone"`), and Kepner-Tregoe Is/Is-Not matrices (`"Kepner-Tregoe Is-Is Not"`). Formally declare that live formula arithmetic verification is explicitly N/A for qualitative RCA methodologies. Route all user-supplied text through `write_table_sheet` and `sanitize_cell` to guarantee CSV/formula-injection safety against OWASP trigger characters (`"="`, `"+"`, `"-"`, `"@"`, `"\t"`, `"\r"`).

**Source:**
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Section 4 (Problem Definition & Boundary Specification), Section 5 (Why-Why Analysis), and Section G1 (Fishbone Diagram).
- Kaoru Ishikawa, *Guide to Quality Control* (2nd Revised Edition, 1986), Chapter 3 (Cause-and-Effect Diagrams).
- Charles H. Kepner & Benjamin B. Tregoe, *The New Rational Manager* (Updated Edition, 1997), Chapters 2 & 3 (Problem Analysis).
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Sections D2, D4 & D7.
- Nancy R. Tague, *The Quality Toolbox* (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
- OWASP CSV Injection Defense Guidelines.
- Absence of Published Arithmetic Formula Standard: No published AIAG, ISO, ASQ, or Kepner-Tregoe standard specifies spreadsheet calculation formulas or arithmetic constants for qualitative RCA tools.

**Rationale:** Root Cause Analysis methods are qualitative deductive problem-solving methodologies and structural scoping frameworks. Unlike quantitative engines (e.g. MSA variance components or SPC Shewhart control limits), RCA workbooks function as structured qualitative documentation of problem boundaries, causal chains, and categorized failure mechanisms rather than dynamic numerical calculators. The multi-sheet layout mirrors the standard 8D/RCA problem-solving progression (Is/Is-Not problem boundary scoping $\to$ Fishbone brainstormed categorization $\to$ 5-Why root cause isolation). Strict formula-injection defense ensures that any problem statements or cause descriptions containing spreadsheet trigger characters are safely escaped with apostrophe prefixes and preserved as inert text strings in saved XML representations.

**Applied In:** `packages/quality-core/src/quality_core/rca/export.py` (`build_rca_workbook`, `export_rca_workbook`, `export_five_why_workbook`, `export_fishbone_workbook`, `export_is_is_not_workbook`), `packages/quality-core/src/quality_core/rca/__init__.py`.

---

## Note on the 8D State-Machine Citation Base (E0, #218)

Milestone 11 (v1.1.0) adds a D0–D8 8D Problem-Solving state machine to `quality_core.rca`
(`rca/eight_d_schema.py`, E1/#204; `rca/eight_d.py`, E2/#205; discipline engines E3–E9,
#206–#212). The `RULE-8D-*` entries below seed the citation and assumptions base **before** any
of that code exists (#218 is P0 governance and blocks E1–E14) — no engine file referenced below
has been written yet, so every `**Applied In:**` line records the epic that will consume the
citation rather than a function that exists today.

**Ford Global 8D Manual is the primary source for all nine D0–D8 discipline definitions.**
AIAG CQI-20 covers the same nine steps under its own numbering and explicitly declines to use
D-labels (`RULE-8D-SOURCE-PRIMACY` below carries the verbatim excerpt). CQI-20 does carry a
D1–D8 correspondence table in Appendix H — that table omits D0 — and is therefore cited
standalone only where it supplies something Ford 8D does not: the 5W2H tool name and its
question set (`RULE-8D-D2`, `RULE-8D-D2-003`) and the containment-persistence requirement
(`RULE-8D-GATE-CONTAINMENT`).

**On-box definition of "5W2H" (CQI-20) — CORRECTED at E4 (#207).** CQI-20 mentions the acronym
in prose, in an aside inside a note on supplier corrective action requests:

> The problem statement can include but is not limited to 5 Why-2 How (5W2H), Gantt chart, Is/Is Not, etc.

**That prose expansion is not the manual's model, and E0's original reading of it here was
wrong.** This entry previously concluded that CQI-20's 5W2H means "5 Why – 2 How", **not** the
What/Where/When/Who/Why/How question set, and directed that "any future D2 (#207)
5W2H-completeness engine must implement *this* definition". Re-reading the manual for E4 found
Figure 12, "Problem Identification Questions", which enumerates and defines seven questions —
Who?, What?, When?, Where?, Why?, How?, How Many? — five W-questions and two How-questions.
Figure 12 is the normative enumeration; the SCAR-note line above is a loose acronym expansion.
The corrected reading is carried verbatim at `RULE-8D-D2-003` below and is what
`validate_d2_problem_description` implements. The original excerpt is retained above rather than
deleted, because the correction is to its *interpretation*, not to the quotation.

**Site-ID convention for this milestone**, chosen to avoid the flat-counter renumbering
collision that hit `RULE-SQE-*` twice (#164, #175): the nine discipline definitions are
`RULE-8D-D0` through `RULE-8D-D8`, fixed here. The three milestone gates are
`RULE-8D-GATE-CONTAINMENT` (D3→D4), `RULE-8D-GATE-PREVENTION` (D7 loopback), and
`RULE-8D-GATE-CLOSURE` (D8 closure), fixed here. Any *additional* citable rule a later epic
needs (E3–E9, discipline-engine-specific, not already covered by the nine discipline rows or
three gates) uses `RULE-8D-D<n>-NNN`, a zero-padded 3-digit counter scoped to that discipline's
own prefix — each epic owns a disjoint `D<n>` namespace, so parallel epics never race on one
shared counter.

**PROCUREMENT-GAP status: none for the cited `RULE-8D-*` rows.** Every D0–D8 rule and all three
gates below have a direct, on-box, primary-source excerpt. This was verified, not assumed,
against both manuals present at `CQI20_MANUAL_PATH` / `FORD_8D_MANUAL_PATH`. Two things sit
deliberately *outside* that statement rather than being left implicit, and are declared under
Process Design Decision #8 below: the D3→D4 gate's **second** blocking reason, refusing the
transition over invalid linked nonconformity evidence, which no manual clause requires and which
is therefore identified as `PDD-8D-008` and not as a `RULE-8D-*` row; and the ISO 9001:2015 §8.7 /
IATF 16949:2016 §8.7 excerpts standing behind `quality_core.ncr`, which are not on this machine
(`PROCUREMENT-GAP`, #221) and which nothing in `rca/` quotes or paraphrases.

---

## RULE-8D-SOURCE-PRIMACY: Ford Global 8D is the primary source for the D0–D8 labels

**Decision:** Use the Ford Global 8D Manual as the primary source for all nine D0–D8 discipline
definitions, and cite AIAG CQI-20 only where it supplies content Ford 8D does not. CQI-20 is a
nine-step numbered guide that deliberately does not label its steps D0–D8, so it cannot back the
D-label scheme this milestone's state machine is built on.

**Source:**
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Introduction:
> Corrective action reporting from many diverse organizations requires applying the 8D approach. This guideline intentionally avoids labelling the steps as an 8D.

**Rationale:** The 8D state machine (#205) is defined by the D0–D8 labels themselves; a source
that declines to use those labels cannot be its primary authority for them. CQI-20's Appendix H
does map D1–D8 to its own steps, but it omits D0 entirely, which is consistent with the
Introduction's stated position. Recording that position verbatim here prevents a later epic from
quietly re-attributing a D-label definition to CQI-20.

**Applied In:** Not yet applied — this is a source-selection decision governing every
`RULE-8D-*` entry below. This entry seeds the citation only (#218).

---

## RULE-8D-D0: Emergency Response Action (ERA) readiness precondition (D0)

**Decision:** D0 ("Prepare for the 8D Technical Process") requires an Emergency Response Action
(ERA) to protect the customer before the G8D process proper begins, and the ERA must be checked
effective before its full implementation.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D0:
> In response to a symptom, assess the need for the G8D process. If necessary, provide an Emergency Response Action to protect the customer and initiate the G8D process.
> Once an ARE has been identified, it must be checked that it is effective before its full implementation.
> Are Emergency Response Actions necessary?

**Rationale:** D0 exists to stop customer harm immediately, before root-cause work starts. The
manual requires the emergency action taken at this stage to be *checked effective*, not merely
declared, and makes the necessity of an emergency response an explicit D0 evaluation question.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d0_readiness`), E3 (#206).

---

## RULE-8D-D0-001: "Verified" is a concrete, checkable D0 event

**Decision:** A D0 record whose Emergency Response Action is required and implemented but carries
no effectiveness-verification record is rejected: "was it verified?" is a question the D0
evaluation asks of every ERA, so the engine must be able to answer it from the record.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, D0 Evaluation Questions:
> How was the emergency response action verified?

**Rationale:** The manual poses ERA verification as an evaluation question the team must answer,
not as an optional extra. A record that cannot answer it is not D0-complete, which is why
`ERA_NOT_VERIFIED` is an `error` (REJECT) rather than a warning.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d0_readiness`, `ERA_NOT_VERIFIED`), E3 (#206).

---

## RULE-8D-D0-002: Validation of the ERA is asked alongside verification

**Decision:** The D0 engine treats the recorded `EffectivenessVerification` as the single
evidence artifact answering the manual's paired verified/validated questions; it does not invent
a second, separate "validation" field the schema does not have.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, D0 Evaluation Questions:
> How was the Emergency Response Action validated?

**Rationale:** Ford asks both questions of D0, back to back, at the same evaluation point.
`EffectivenessVerification` already records *who* determined effectiveness, *when*, and *on what
evidence* — the substance both questions ask for. Splitting it into two fields would assert a
data shape neither manual defines (see Process Design Decision #5).

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d0_readiness`, the `era_verification` evidence read), E3 (#206).

---

## RULE-8D-D0-003: "Effective" means the effects are eliminated, not that a check happened

**Decision:** An ERA whose verification record concluded `is_effective is False` is rejected
(`ERA_VERIFIED_INEFFECTIVE`), and `era_verified` on the result is True only when a verification
record exists *and* concluded the action is effective — the presence of a verification record is
never on its own sufficient.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D0:
> The verification must demonstrate that when installing the ARE, the effects of the problem are eliminated and when they are taken away, they come back.

**Rationale:** The manual defines what a verification has to *demonstrate*, which makes a
verification that demonstrated the opposite a failed ERA rather than a satisfied requirement.
This is the standards grounding for reading `is_effective` and not merely `verification is not
None`. (The manual's "ARE" is an artifact of the on-box extraction of "ERA"; the excerpt is
quoted verbatim, as `RULE-8D-D0` already does.)

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d0_readiness`, `_is_verified_effective` / `ERA_VERIFIED_INEFFECTIVE`), E3 (#206).

---

## RULE-8D-D1: Team completeness — Champion and Designated Team Leader (D1)

**Decision:** D1 requires a small cross-functional team with process/product knowledge, and that
team is not complete until both a Champion and a Designated Team Leader are identified.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D1:
> Establish a small group of people with the process and/or product knowledge. assign time, authority, and skills in the technical disciplines required to solve the problems and implement corrective actions. The group must have a Champion and a Designated Team Leader. The group begins the team-building process.
> Champion: the champion will usually be the internal person responsible who is feeling the pain of the problem.
> Team Leader: the role of the team leader is to manage the team's business for the team.
> Has the designated Champion of the team been identified? Has the Team Leader been identified?

**Rationale:** The manual states the two roles as a requirement ("must have"), defines each
role's distinct responsibility, and re-tests both at the D1 evaluation questions — so a
team-completeness check has to assert both roles, not merely a non-empty member list.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d1_team`), E3 (#206).

---

## RULE-8D-D1-001: The team members are defined separately from the two named roles

**Decision:** A D1 record with a Champion and a Team Leader but an empty `members` list is
rejected (`NO_TEAM_MEMBERS`, severity `error`). Naming the two roles does not by itself define
the team.

**Source:**
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Check Your Progress:
> Did we define the team members?

**Rationale:** CQI-20 asks about the team members as its own progress check, listed separately
from "Did we select an executive champion?" and "Did we select a team leader?". Treating an empty
roster as complete would collapse three distinct checks into two.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d1_team`, `NO_TEAM_MEMBERS`), E3 (#206).

---

## RULE-8D-D1-002: Team adequacy is evaluated against the problem, with no numeric bound

**Decision:** The engine rejects an *empty* roster but implements **no** minimum or maximum team
size. "Large enough" is evaluated by the team against the problem's entries, not by a number this
platform invents.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, D1 Evaluation Questions:
> Is the team large enough to include all the entries?

**Rationale:** Ford frames team sufficiency as a judgment about coverage of the problem's inputs,
and CQI-20 discusses "too few"/"too many" members qualitatively — neither states a count. Zero
members is the one case that is unambiguously insufficient under either reading, so that is the
only bound enforced.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d1_team`, `NO_TEAM_MEMBERS`; deliberately no team-size threshold), E3 (#206).

---

## RULE-8D-D1-003: Member roles must be clear

**Decision:** Each team member whose `role` is unset raises one `TEAM_MEMBER_ROLE_UNDEFINED`
warning — one finding per affected member, never an aggregate.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, D1 Evaluation Questions:
> Are the roles and responsibilities of the team members clear?

**Rationale:** The manual makes role clarity an explicit D1 evaluation question. The manual does
not define "clear", so the check is a `warning`, not a rejection, and the translation of "clear"
into "the `role` field is populated" is this platform's own — recorded as Process Design
Decision #6 below.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d1_team`, `TEAM_MEMBER_ROLE_UNDEFINED`), E3 (#206).

---

## RULE-8D-D2: Problem description — "what is wrong with what" in quantifiable terms (D2)

**Decision:** D2 requires the problem to be described as "what is wrong with what" and detailed
in quantifiable terms. 5W2H is a named tool the problem statement may use; the on-box source
enumerates its questions at Figure 12 (`RULE-8D-D2-003` below), which is what this platform
implements.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D2:
> Describe the internal/external problem by identifying 'what is wrong with what', and detail the problem in quantifiable terms (Description of the problem).
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Problem Description:
> The problem statement can include but is not limited to 5 Why-2 How (5W2H), Gantt chart, Is/Is Not, etc.

**Rationale:** Ford 8D supplies the D2 definition; CQI-20 supplies the tool name, which Ford does
not. **Correction (E4, #207):** this rationale previously argued that the quoted line's "5 Why-2
How" phrasing *was* CQI-20's model of 5W2H, and that a completeness engine built on a
question-set reading "would be checking six fields the cited source never requires". That is
wrong. CQI-20 defines the questions itself at Figure 12 (`RULE-8D-D2-003`), and there are seven,
not six. The line quoted above is an aside inside a note on supplier corrective action requests;
Figure 12 is the normative enumeration. The correction is recorded rather than silently
rewritten because the mistaken reading shipped in this log at E0 and shaped the first D2 engine.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d2_problem_description`), E4 (#207), which composes this discipline definition with
`RULE-8D-D2-001` / `RULE-8D-D2-002` below and delegates Is/Is-Not scoping to
`quality_core.rca.is_is_not.scope_is_is_not` rather than reimplementing it.

---

## RULE-8D-D2-001: Problem statement two-part test — defect ("what is wrong") + object ("with what") (D2)

**Decision:** The problem *statement* stage of D2 is a concise pairing of the defect/symptom and
the object experiencing it — Ford 8D's own "what is bad (the symptom) with what (the object)"
test, which `D2Discipline.what_is_wrong` / `D2Discipline.with_what` (E1, #204) already capture as
two distinct required fields.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D2:
> Problem statement - A concise statement that identifies the object that experience the defect and the nature of the defect (the defect will typically be a symptom for whose cause is unknown). The problem statement clearly describes what is bad (the symptom) with what (the object).

**Rationale:** This is the manual's own definition of what "what is wrong with what" (already
cited at `RULE-8D-D2`) is *for* — distinguishing the defect from the object it affects. It
justifies the D2 engine composing its `problem_statement` as "<what_is_wrong> with <with_what>",
and it is the qualitative language behind the declared-heuristic check that the two fields are
not identical text (Process Design Decision #7 below; the equality check itself is not
standards-backed, only the requirement that the two be distinguishable is).

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d2_problem_description`, the composed `problem_statement` and
`DEGENERATE_PROBLEM_STATEMENT`), E4 (#207).

---

## RULE-8D-D2-002: Problem description stage carried out via Is/Is-Not across what/where/when/how-big (D2)

**Decision:** D2's second stage — the problem *description* — is established by determining
what, where, when, and how big, using the Is/Is-Not form. These four dimensions are exactly
Kepner-Tregoe's `WHAT` / `WHERE` / `WHEN` / `EXTENT` ("how big" = extent/magnitude), already
implemented as `quality_core.rca.is_is_not.scope_is_is_not` and cited at `RULE 2` above — this
entry records that Ford 8D independently names the same four-dimension Is/Is-Not scoping as part
of D2 itself, which is why the D2 engine (#207) reuses `scope_is_is_not` rather than
reimplementing scoping logic.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D2:
> Problem description - Established by determining what, where, when, how big and use the form Is / Is Not to drive this part of the process.

**Rationale:** The manual makes the Is/Is-Not linkage explicit and mandatory ("use the form Is /
Is Not to drive this part of the process"), not optional tooling advice — this is the primary
justification for why `validate_d2_problem_description` calls `scope_is_is_not` unconditionally
whenever scoping data is supplied, and flags its absence when it is not
(`IS_IS_NOT_NOT_PROVIDED`). Absence is a warning rather than a rejection because Ford 8D itself
describes D2 as carried out in two stages, so a report holding only the problem statement is a
normal intermediate state rather than a defective one — that severity choice is this platform's,
not the manual's (Process Design Decision #7 below).

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d2_problem_description`, the `scope_is_is_not` delegation and
`IS_IS_NOT_NOT_PROVIDED`), E4 (#207).

---

## RULE-8D-D2-003: 5W2H is CQI-20 Figure 12's seven Problem Identification Questions (D2)

**Decision:** A 5W2H problem description answers the seven questions CQI-20 enumerates and
defines in Figure 12, "Problem Identification Questions": Who?, What?, When?, Where?, Why?,
How?, How Many? — five W-questions and two How-questions, which is the acronym. Those seven are
the checkable sub-fields of a 5W2H description; a record that declares `method_used="5W2H"` and
leaves any of them unanswered has not completed the method it claims.

**Source:** AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Describe the
Problem, Figure 12. The figure's caption:

> Figure 12. Problem Identification Questions

Its seven entries, verbatim (question, then the manual's definition of it):

> Who? "Who" found it and who does it affect? Individuals/customers associated with the problem?

> What? involved? Is there a trend? The problem statement or definition; What is the object and defect? What equipment is

> When? Date and time the problem was identified? Date and time the defective product was produced?

> Where? Location of complaints (area, facilities, process flow diagram) and location of defect on part?

> Why? Why the part failed, what standard did it fail to meet?

> How? How did the problem occur? How was it detected?

> How Many? Size and frequency of problem; how many parts have the problem? How many defects on each part? Is it getting worse?

The "What?" entry is quoted exactly as the manual extraction holds it. The PDF-to-text
extraction interleaved that entry's two columns, so its clause "involved? Is there a trend?"
lands on the line *before* the clause it continues ("... What equipment is"). Every word of the
entry is present and nothing has been reordered to make it read better — reordering a quotation
to tidy it is a fabrication, and the line numbers in `CITATIONS.tsv` must keep pointing at what
the file actually says.

**Rationale:** This entry exists because E0's reading of 5W2H was wrong and shipped. E0 recorded
CQI-20's prose aside — "The problem statement can include but is not limited to 5 Why-2 How
(5W2H), Gantt chart, Is/Is Not, etc.", inside a note on supplier corrective action requests
(`RULE-8D-D2`) — as the manual's definition of the acronym, and concluded that no
question-set model was defensible. It then directed the D2 engine (#207) to implement that
reading, which the first version of `validate_d2_problem_description` did: it emitted an `info`
note restating "5 Why - 2 How" and returned `ACCEPT`, so an incomplete 5W2H was never flagged.
Figure 12 settles it: the manual enumerates the questions and defines each one. A figure that
enumerates and defines outranks an acronym expanded in passing, so the engine now validates
against Figure 12 and the SCAR-note line is retained only as the prose mention it is.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_schema.py`
(`D2Discipline.w2h_who` … `w2h_how_many`, the seven optional answer fields) and
`packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`_five_w_two_h_answers`, `validate_d2_problem_description`'s
`METHOD_5W2H_DESCRIPTION_INCOMPLETE` finding and `D2ValidationResult.five_w_two_h` payload),
E4 (#207).

---

## RULE-8D-D3: Interim Containment Action defined, verified, and implemented (D3)

**Decision:** D3 requires the Interim Containment Action (ICA/AIC) to be defined, verified, and
implemented, and its effectiveness validated, before the report may treat containment as done.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D3:
> Define, verify, and implement the Interim Containment Action (AIC) to isolate the effects of the problem of any internal/external client until they are implemented Permanent Corrective Actions (PCAs). Validate the effectiveness of the measures of containment.
> The AIC is verified.

**Rationale:** The manual makes verification part of the discipline itself and repeats it as a
D3 selection condition — an ICA that is implemented but unverified does not satisfy D3.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d_disciplines.py`
(`validate_d3_containment`, `CONTAINMENT_ACTION_NOT_VERIFIED` /
`CONTAINMENT_ACTION_VERIFIED_INEFFECTIVE`), E5 (#208).

---

## RULE-8D-D4: Root cause and escape point, both isolated and verified (D4)

**Decision:** D4 requires two distinct findings — the root cause, isolated and verified against
test data, and the escape point, the place in the process where the effect should have been
detected and contained but was not.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D4:
> Isolate and verify the root cause by testing each possible cause against the description of the Problem with the test data. Also isolate and verify the place in the process where the effects of the root cause should have been detected and contained, but it was not done (escape point).
> Root Cause: - the lowest level event that can be attributed to and proven as the one that caused the problem that arises
> Escape Point: - the place in the process where the root cause of the problem was not detected allowing the problem to occur

**Rationale:** The manual treats root cause and escape point as separate, separately-verified
outputs of D4, and defines root cause as an event that must be *proven*, not asserted. A D4
engine therefore validates a supplied root cause against evidence; it never authors one (see
"Process Design Decisions" below).

**Applied In:** Not yet applied — reserved for E6 (`rca/eight_d.py` D4 engine, #209), which will
delegate the causal-chain verdict to `quality_core.rca.five_why.validate_five_why_chain`. This
entry seeds the citation only (#218).

---

## RULE-8D-D5: Permanent Corrective Action selection and verification (D5)

**Decision:** D5 requires selecting a permanent corrective action for the root cause *and* one
addressing the escape point, with both decisions verified as effective and free of undesirable
effects before implementation, against criteria established for each.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D5:
> Select the best permanent corrective action to eliminate the root cause. Also select the best permanent corrective action to address the escape point. Verify that both decisions will be successful when implemented without causing undesirable effects.
> Now you are in a position to determine and choose the Permanent Corrective Action (PCA).
> Finally, the G8D Team must verify that the ACP will eliminate the root cause effectively.
> Have the criteria been established to choose an ACP for the root cause and the point of escape?

**Rationale:** The manual pairs each PCA with the specific finding it answers and requires
verification *before* implementation, so PCA traceability (every PCA traced to a root cause or
escape point) is a requirement of the discipline, not a platform embellishment.

**Applied In:** Not yet applied — reserved for E7 (`rca/eight_d.py` D5 engine, #210). This entry
seeds the citation only (#218).

---

## RULE-8D-D6: Implement and validate PCAs, remove the ICA (D6)

**Decision:** D6 requires the selected permanent corrective actions to be planned and
implemented, the interim containment action removed, and the actions validated with long-term
results monitored.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D6:
> Plan and implement selected Permanent Corrective Actions. Remove the AIC. Validate actions and monitor long-term results.
> Having established and verified the best ACP for the root cause and the escape point, the next step is the implementation of the ACP.

**Rationale:** Removal of the ICA is part of D6, not an afterthought: containment is temporary by
construction, and the manual sequences its removal with validated permanent action. Ongoing
monitoring is named as part of the same discipline.

**Applied In:** Not yet applied — reserved for E7 (`rca/eight_d.py` D6 engine, #210). This entry
seeds the citation only (#218).

---

## RULE-8D-D7: Prevent recurrence — modify systems and update documentation (D7)

**Decision:** D7 requires modifying the systems, policies, practices, and procedures that
permitted the problem, and documenting the resulting changes — the manual names the FMEA and the
control plan explicitly.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D7:
> Modify the necessary systems, including policies, practices, and procedures, to prevent the recurrence of this and other similar problems. Make recommendations to systemic improvements, as necessary.
> Have all changes been documented (for example, FMEA, control plan, flow) of the process)?

**Rationale:** Prevention in the manual's sense is systemic, not local to the affected part, and
the D7 evaluation question names the FMEA and control plan as the artifacts that record the
change. That is what makes an FMEA/Control-Plan linkage check a D7 concern rather than an
invented one.

**Applied In:** Not yet applied — reserved for E8 (`rca/eight_d.py` D7 engine and FMEA /
Control-Plan linkage, #211). This entry seeds the citation only (#218).

---

## RULE-8D-D8: Recognize the team and close out documentation (D8)

**Decision:** D8 completes the team's experience by recognizing individual and team
contributions, and its closing checklist re-requires that all related documentation be reviewed
and updated.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D8:
> Complete the team's experience, recognizing both individual contributions and the team's, and celebrate success.
> Ensure that all related documentation is reviewed and updated.

**Rationale:** D8 is not purely ceremonial in the manual: alongside recognition it carries a
documentation-review obligation, which is what a closure check can be built on.

**Applied In:** Not yet applied — reserved for E9 (`rca/eight_d.py` D8 engine, #212). This entry
seeds the citation only (#218).

---

## RULE-8D-GATE-CONTAINMENT: D3→D4 gate — no advance without verified containment

**Decision:** The 8D state machine's D3→D4 transition (E2, #205) will require the Interim
Containment Action to be marked verified before the report may advance to D4 root-cause work.

**Source:**
- AIAG CQI-20 *Effective Problem Solving Guide* (2nd Edition, 2018), Containment:
> Provisions for containment should stay in place until effectiveness of the corrective actions are verified.
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D3 (reused from `RULE-8D-D3`, same manual lines already verified there):
> Define, verify, and implement the Interim Containment Action (AIC) to isolate the effects of the problem of any internal/external client until they are implemented Permanent Corrective Actions (PCAs). Validate the effectiveness of the measures of containment.
> The AIC is verified.

**Rationale:** Both manuals require containment to be *verified*, and CQI-20 additionally
requires it to remain in place until corrective-action effectiveness is confirmed. **The specific
mechanism — a state machine refusing the D3→D4 transition when containment is not marked verified
— is not itself a standards clause; it is this platform's engineering translation of "verified"
and "stay in place until verified" into an enforceable gate.** That mechanism is recorded as a
Process Design Decision below, and is not implied to be a standards mandate.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d.py`
(`transition_eight_d`, D3→D4 containment gate, E2/#205); also
`packages/quality-core/src/quality_core/rca/eight_d_disciplines.py` (`validate_d3_containment`,
which reads the identical `discipline.is_verified` predicate as an advisory pre-flight check and
does not duplicate it), E5 (#208). E5 added a *second*, independent D3→D4 gate reason for
invalid linked nonconformity evidence; that reason is **not** authorized by this rule and is
declared as `PDD-8D-008` under Process Design Decision #8 instead. This rule continues to
authorize the containment-verification reason (`CONTAINMENT_NOT_VERIFIED`) and nothing else.

---

## RULE-8D-GATE-PREVENTION: D7 loopback — no closure without FMEA / Control-Plan update

**Decision:** The 8D state machine (E2, #205) will not permit D8 closure while the D7 preventive
documentation is outstanding; the report loops back to D7 until the changes are documented.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, D5 evaluation checkpoint. The
  manual repeats this documentation question at five evaluation checkpoints (manual lines 1015,
  1536, 1729, 1901, 2064 — the D2, D4, D5, D6, and D7 checkpoints); the row cited here is the D5
  occurrence, a distinct manual line from `RULE-8D-D7`'s D7 occurrence at line 2064:
> Have all changes been documented (for example, FMEA, control plan, flow of process)?
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D7 (reused from `RULE-8D-D7`, same manual lines already verified there):
> Modify the necessary systems, including policies, practices, and procedures, to prevent the recurrence of this and other similar problems. Make recommendations to systemic improvements, as necessary.
> Have all changes been documented (for example, FMEA, control plan, flow) of the process)?

**Rationale:** The manual asks the same documentation question at five separate evaluation
checkpoints and names the FMEA and control plan each time, which is the substantive requirement
this gate enforces. **The loopback itself — refusing the D7→D8 transition when the FMEA / Control-Plan
update is absent — is this platform's engineering choice, not a clause in any manual.** Recorded
as a Process Design Decision below.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d.py`
(`transition_eight_d`, D7→D8 and D8 closure prevention gates, E2/#205); also reserved for E8
(#211).

---

## RULE-8D-GATE-CLOSURE: D8 closure — no closure on an RCA-rejected 5-Why chain

**Decision:** The 8D state machine (E2, #205) will refuse D8 closure when the report's 5-Why
chain is rejected by `quality_core.rca.five_why.validate_five_why_chain` — a blame-terminal or
non-systemic chain means no root cause has been established, so there is nothing to close on.

**Source:**
- Ford Motor Company, *Global 8D (G8D) Problem Solving Manual*, Section D4 / D7 (same manual line already backing `RULE 4` above, cited here for the
  closure gate's own purpose):
> there is normally a procedure, a policy, or a (systemic) practice that has allowed you pass. We call this the 'root cause of the root cause.' This must be established and resolved.

**Rationale:** The manual requires the systemic "root cause of the root cause" to be established
and resolved — the same requirement `RULE 4` already backs for the 5-Why validator. This gate
therefore **composes with `RULE 4` rather than re-deriving it**: it consumes
`validate_five_why_chain`'s existing accept/reject verdict and does not implement its own
rejection logic. **The refusal to advance is this platform's enforcement mechanism, not a
standards clause**; see the Process Design Decisions below.

**Applied In:** `packages/quality-core/src/quality_core/rca/eight_d.py`
(`transition_eight_d`, provenance-bearing D8 closure gate, E2/#205); also reserved for E9 (#212).

---

## Process Design Decisions (no standard implied)

These are engineering and architectural decisions for the 8D state machine (#205 and onward).
**None of them is a standards claim**, none is backed by a `CITATIONS.tsv` row, and none may be
presented as one by any engine, MCP tool, canvas, or skill layer. They are recorded separately
from the cited `RULE-8D-*` entries above for exactly that reason.

1. **Root-cause-authorship invariant.** The D4 engine (E6, #209) will validate a *supplied* root
   cause via `quality_core.rca.five_why.validate_five_why_chain`; it will never author, infer, or
   paraphrase one. This mirrors `sqe/ASSUMPTIONS_LOG.md`'s identical invariant for the SCAR
   generator (#120) — same reasoning, different consumer — and no configuration flag relaxes it.

2. **Gate-enforcement mechanisms are ours, not the standard's.** `RULE-8D-GATE-CONTAINMENT`,
   `RULE-8D-GATE-PREVENTION`, and `RULE-8D-GATE-CLOSURE` each cite manual text describing the
   *prerequisite content* a step must satisfy (verified containment; FMEA / Control-Plan
   documentation; an established and resolved systemic root cause). None of the manuals says
   "refuse a state transition." The refusal behavior is this platform's engineering choice for
   how to enforce, in software, what the manuals require in substance.

3. **`RULE-8D-D<n>-NNN` is the reserved per-discipline namespace.** No row existed under this
   pattern as of #218; the convention was declared here so E3–E9 (#206–#212) would have a
   collision-free namespace before they needed one. E3 (#206) is its first user
   (`RULE-8D-D0-001..003`, `RULE-8D-D1-001..003`); E4 (#207) additionally claims
   `RULE-8D-D2-001` and `RULE-8D-D2-002`. The pattern remains collision-free for D3–D8.

4. **D8 closure policy for the `WARNING` 5-Why verdict (E1, #204).** `REJECT` hard-blocks
   closure (`D8Discipline` cannot be constructed with `closure_approved=True` while
   `linked_five_why_verdict == "REJECT"`; see `RULE-8D-GATE-CLOSURE` above). `ACCEPT` closes
   without extra evidence. **`WARNING` closes only with a recorded `WarningOverride`**
   (`approved_by`, `justification`, `override_date`, all required) — no manual defines
   closure eligibility for a marginal, non-rejected chain, so this platform requires the
   judgment call to be explicit and attributable rather than silently defaulting either way.
   `sqe/scar.py`'s linkage check gates on the same validator's `.valid` boolean (`WARNING`
   passes identically to `ACCEPT`) — D8 closure deliberately diverges from that precedent
   because it is a terminal, higher-stakes gate than an intermediate evidence check.

5. **Containment/corrective-action "verified" is a structured record, not a flag (E1, #204).**
   `EffectivenessVerification` (`verified_by`, `verified_date`, `evidence`, `is_effective`) is
   the only way `ContainmentAction` (D3) or `ImplementedAction` (D6) can be marked verified —
   `is_verified` is `verification is not None and verification.is_effective`, so there is no
   bare boolean a caller can set to satisfy it. The specific field set is this platform's
   engineering translation of "validate the effectiveness" / "the AIC is verified"
   (`RULE-8D-D3`) into a data shape; no manual mandates these four fields by name.

6. **D0/D1 engine heuristics with no manual behind them (E3, #206).** The D0/D1 engines in
   `rca/eight_d_disciplines.py` raise four findings that no manual states; each is a warning, none
   is presented as a standards requirement, and none carries a `CITATIONS.tsv` row. (This epic is
   also the first user of the `RULE-8D-D<n>-NNN` namespace reserved in item 3 above, with
   `RULE-8D-D0-001..003` and `RULE-8D-D1-001..003`.)
   - **`ERA_VERIFICATION_DATE_INCONSISTENT`** — WARNING when `era_verification.verified_date` is
     earlier than `era_implemented_date`. `D0Discipline` has no model validator enforcing this
     ordering, unlike `ContainmentAction._verified_not_before_implemented` for the structurally
     analogous D3 case, so this is an engine-layer sanity check the schema does not perform, not a
     re-statement of a schema rule. Same-day verification is treated as consistent, and no maximum
     gap is enforced in either direction — only the ordering is checked, because no source
     quantifies a duration.
   - **`CHAMPION_TEAM_LEADER_SAME_PERSON`** — WARNING when `champion` and `team_leader` normalise
     (strip + casefold) to the same string. No manual states the two roles must be held by
     different people. CQI-20 says the executive champion should *choose* a leader, which implies
     but does not require two people; using it to back a rejection would overreach the source, so
     this is a warning only and is deliberately not cited.
   - **`DUPLICATE_TEAM_MEMBER`** — WARNING when a `TeamMember.name` normalises to the same string
     as another roster entry. A pure data-quality heuristic; one finding per distinct duplicated
     name, not one per repeat.
   - **The mechanism behind `TEAM_MEMBER_ROLE_UNDEFINED`** — `RULE-8D-D1-003` asks whether roles
     and responsibilities are "clear"; the manual never defines "clear" as "the `role` field is
     non-null". That translation into a checkable field-presence rule is this platform's, which is
     why the finding is a warning rather than a rejection.
   No competency or skill-matching model is implemented for D1: `TeamMember` carries no such
   field, and CQI-20's discussion of skill level and "too few"/"too many" members is qualitative
   with no number attached.

7. **D2 declared heuristics are not standards claims (E4, #207).**
   `DEGENERATE_PROBLEM_STATEMENT` (exact case-insensitive equality between `what_is_wrong` and
   `with_what`) and `QUANTIFICATION_NOT_NUMERIC` (no digit character anywhere in
   `quantification`) are this platform's own completeness proxies, not AIAG/Ford requirements —
   neither manual defines a checkable rubric for "quantifiable terms" or for statement
   distinctiveness beyond the qualitative language quoted at `RULE-8D-D2-001`. Both are crude by
   construction: a digit test cannot tell "3 per shift" from "a majority of parts", and exact
   equality cannot tell a genuinely degenerate statement from two fields that merely overlap.
   Both findings are `severity="warning"`, never `"error"`, and neither is backed by a
   `CITATIONS.tsv` row.
   Two further D2 choices are also this platform's, not the manuals':
   - **Overriding the Is/Is-Not problem statement.** `validate_d2_problem_description` always
     passes its composed `"<what_is_wrong> with <with_what>"` string to `scope_is_is_not`,
     overriding that engine's `"Problem Statement"` default and any statement carried on a
     supplied `IsIsNotMatrix`, so the nested scoping result reflects D2's authoritative
     statement. No manual says which statement wins; this is a single-source-of-truth judgment
     call.
   - **Severity of absent scoping.** `IS_IS_NOT_NOT_PROVIDED` is a warning, not an error,
     because Ford 8D describes D2 as carried out in two stages (`RULE-8D-D2-002`), making a
     statement-only D2 a normal intermediate state. `REJECT` is reserved for scoping data that
     *was* supplied and that `scope_is_is_not` itself rejected
     (`IS_IS_NOT_SCOPING_REJECTED`) — that verdict is delegated, never re-derived here.
   **5W2H completeness is a standards check, not a heuristic, and is the one D2 item that
   changed after review (E4, #207).** This decision previously read: "The 5W2H note
   (`METHOD_5W2H_STANDARD_NOTE`) is `severity="info"` and never gates: it restates the cited
   expansion at `RULE-8D-D2` ('5 Why - 2 How') so a declared method is not silently read as the
   generic What/Where/When/Who/Why/How mnemonic. **No 5W2H sub-field parsing is implemented**,
   because neither on-box manual defines checkable 5W2H sub-fields." CQI-20 Figure 12 does define
   them — seven questions, each with a definition (`RULE-8D-D2-003`) — so the info note is gone
   and `METHOD_5W2H_DESCRIPTION_INCOMPLETE` is an `error` naming the unanswered questions.
   What remains this platform's own, and is stated here rather than implied as standards backing:
   - **The check fires on the declaration, not on the data.** Completeness is judged only when
     `method_used == "5W2H"`; the seven `w2h_*` answers are optional data otherwise, and
     `five_w_two_h` stays `None`. No manual says a team that never claimed 5W2H owes those seven
     answers, so claiming the method is what creates the obligation.
   - **Answer *presence* is all that is checked.** A non-blank `w2h_*` field counts as answered.
     There is no free-text parsing of the D2 statement fields for who/when/where tokens, and no
     judgment of whether an answer is a *good* answer — the manual gives no rubric for that.

8. **D3 engine and NCR-linkage design decisions (E5, #208).**
   `validate_d3_containment` emits one `D3Finding` per unverified or verified-ineffective
   `ContainmentAction` rather than a single aggregate verdict. That per-action granularity is
   this platform's diagnostic choice, not a new standards claim — `RULE-8D-D3` already covers the
   substance ("Define, verify, and implement the Interim Containment Action", "Validate the
   effectiveness of the measures of containment", "The AIC is verified"), and no new
   `CITATIONS.tsv` row is added by this epic.
   - **`containment_verified` is read, never recomputed.** The result field is assigned straight
     from `D3Discipline.is_verified`, which is itself `all(a.is_verified for a in actions)` in
     `eight_d_schema.py`. The engine never rebuilds an equivalent boolean by counting its own
     findings, so it cannot drift from the single predicate the D3→D4 gate reads at
     `eight_d.py`'s `transition_eight_d`.
   - **The engine is the advisory pre-flight validator, the state machine is the enforcement
     point, and both read the same rules.** `validate_d3_containment` does not call, wrap, or
     replace `transition_eight_d`. What the two share is the *rules*, not a copy of them:
     containment through `D3Discipline.is_verified`, and linked nonconformity evidence through
     the single shared evaluator `_linked_ncr_deficiency` in `eight_d_schema.py` — the same
     one-evaluator-two-consumers shape `_closure_evidence_deficiencies` already uses for the
     CLOSED-report boundary, chosen so the two answers cannot drift rather than merely being
     tested for agreement. The D3→D4 gate therefore blocks on an invalid linked NCR
     (`LINKED_NCR_INVALID`) as well as on unverified containment (`CONTAINMENT_NOT_VERIFIED`),
     which is how #208's "an invalid linked NCR blocks the gate" is satisfied — at the state
     machine itself, not in advisory prose. **Refusing a state transition over
     nonconformity-record validity is this platform's decision and carries no manual clause**:
     that gate reason is identified as `PDD-8D-008`, and the `PDD-` prefix is deliberately not
     `RULE-`, which is reserved for identifiers naming a `CITATIONS.tsv` row backed by an on-box
     manual quote. **Scope:** only the D3→D4 gate reads the linked-NCR outcome; the D8→CLOSED
     closure boundary (`_closure_evidence_deficiencies`) is unchanged and still evaluates
     containment, root-cause and prevention evidence only.
   - **Linked NCR *evidence* is a function parameter; the *outcome* of validating it is a schema
     field.** No `linked_ncr_id`, dataset, or record content is stored on `D3Discipline` /
     `ContainmentAction` — the evidence itself is still passed to
     `validate_d3_containment(discipline, linked_ncr=...)` by the caller. What the report carries
     is `D3Discipline.linked_ncr_validation`: an optional `LinkedNCRValidation` record
     (`is_valid`, `record_count`, `findings`) that `validate_d3_containment` returns for the
     caller to store, so the gate reads a verdict this platform already reached instead of
     re-running — or re-implementing — NCR validation inside the state machine. It is optional
     because a D3 record whose evidence has not been linked yet must stay representable, and an
     absent outcome blocks nothing; an *invalid* recorded outcome must carry at least one finding
     message, so a blocked transition can never be silent about its reason. When no evidence is
     supplied on a call, `validate_d3_containment` reports the already-recorded outcome through
     that same shared evaluator, so the advisory verdict and the gate cannot disagree about a
     report both can see.
   - **NCR-linkage dispatch follows the shipped `sqe/scar.py` `_evaluate_ncr_linkage` pattern:**
     `pydantic.ValidationError`, `TypeError` and `ValueError` raised by
     `quality_core.ncr.schema.validate_ncr` are caught and surfaced as a `LINKED_NCR_INVALID`
     finding carrying the sub-engine's own message text. NCR validity rules are never re-derived
     here. This diverges deliberately from `validate_d2_problem_description`, which lets
     `scope_is_is_not`'s exceptions propagate: the acceptance criterion is about a *verdict* a
     caller can read, not an exception a caller must catch. Only `validate_ncr` is invoked —
     `recommend_disposition` and `write_nonconformance` are not called by this engine.
   - **The three NCR-linkage findings are declared platform decisions, not standards claims.**
     `LINKED_NCR_NOT_PROVIDED` is a `warning`, never an `error`, because linking nonconformity
     evidence to a containment record is this platform's traceability convention and its absence
     is a normal in-progress state — mirroring `IS_IS_NOT_NOT_PROVIDED` at D2. `error` is reserved
     for evidence that *was* supplied and that `validate_ncr` itself rejected
     (`LINKED_NCR_INVALID`); that verdict is delegated, never re-derived. `LINKED_NCR_VALID` is
     `info` and never gates. None of the three carries a `CITATIONS.tsv` row.
   - **`PROCUREMENT-GAP` (ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7).** The licensed excerpts for
     these clauses are **not on this machine** — `ISO_9001_MANUAL_PATH` and
     `IATF_16949_MANUAL_PATH` both point into an empty `SixSigma/NCR/` directory and neither file
     exists, verified this session; issue #221 tracks procurement. Accordingly this epic adds **no ISO/IATF quotation and no paraphrase
     anywhere in `rca/`**: `validate_d3_containment` only calls the already-implemented
     `quality_core.ncr.schema.validate_ncr` and asserts nothing of its own about what §8.7
     requires. `quality_core.ncr`'s own §8.7 citation rows in `ncr/CITATIONS.tsv` are untouched by
     this epic and remain separately tracked as an existing gap (#220); this declaration does not
     claim to close that gap, only to avoid deepening it.

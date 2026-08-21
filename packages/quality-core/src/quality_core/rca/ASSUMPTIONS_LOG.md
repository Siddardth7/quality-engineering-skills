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


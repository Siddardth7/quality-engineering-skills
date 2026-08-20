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

*(No `## RULE N` entries are defined in this scaffold. Rules will be added sequentially during engine implementation in Issues #75, #76, #77, and #78.)*

# Engineering Assumptions Log — Production Part Approval Process (PPAP) Core

**Package:** `quality_core.ppap`  
**Domain:** Production Part Approval Process (PPAP) 18-Element Completeness Auditor, Table 4.1 Matrix, Applicability Rules, Initial Process Studies Gate, PSW Validator, and Cross-Engine Linkage.  
**Release Target:** `v0.8.0`  
**Tracking Issue:** [#98](https://github.com/Siddardth7/quality-engineering-skills/issues/98) (Epic 0)

---

## Standard References

1. **AIAG *Production Part Approval Process (PPAP)* Reference Manual, 4th Edition (June 2006)**  
   - Primary reference standard for all 18 element requirements (§2.2.1–§2.2.18), Table 4.1 submission/retention requirements, Section 3 customer notifications, Section 4 evidence levels, Section 5 part submission status, Section 6 record retention, and Appendix A Part Submission Warrant (PSW) instructions.  
   - On-machine path: `/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG_PPAP_4th_Edition.md`

2. **AIAG Production Part Approval Process (PPAP), 4th Edition (2006) Training Deck (Secondary / Non-Authoritative)**  
   - Secondary cross-reference only.  
   - On-machine path: `/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG Production Part Approval Process (PPAP), 4th Edition (2006).pdf`  
   - **Training Deck Inventory:**  
     - *Verified present in deck:* The 18 canonical element names, the five Submission Level definitions (Levels 1–5), and the 27-field Part Submission Warrant field list.  
     - *Missing from deck (not authoritative for):* Table 4.1 submission/retention matrix, Section 5 Part Submission Status body text (Approved / Interim Approval / Rejected definitions), Section 2.2.11 Initial Process Studies numeric acceptance criteria ($P_{pk}/C_{pk}$ bands and actions), Section 3 Customer Notification and Submission Requirements, Section 6 Record Retention, and Appendix A field completion instructions.

---

## Honesty & Scoping Declarations

1. **ISO 9001:2015 & IATF 16949:2016 Non-Citability Limitation:**  
   The on-machine files `/Users/sid/Documents/Upskill/SixSigma/NCR/ISO-9001-2015.pdf` and `/Users/sid/Documents/Upskill/SixSigma/NCR/pdfcoffee.com_iatf16949-2016-standard-pdf-free.pdf` are scanned images with no text layer. IATF 16949:2016 §8.3.4.4 ("Product approval process") is therefore **not citable in Milestone 8**. Any mention in code or documentation is context-only and must be marked as uncited.

2. **OEM Customer-Specific Requirements Out of Scope:**  
   Per `ROADMAP.md`, OEM Customer-Specific Requirement (CSR) overlays (Ford, GM, Stellantis, VW, BMW) are explicitly **v2 backlog** and out of scope for `v0.8.0`.

3. **Submission Level 4 Indeterminacy Gate:**  
   Submission Level 4 is defined by AIAG PPAP 4th Edition Table 4.1 as customer-defined evidence. When no explicit customer requirement set is supplied, the engine and tools resolve `INDETERMINATE` rather than defaulting to Level 3 or guessing an OEM default.

4. **🔒 The Authority Invariant:**  
   Per Section 5 (Part Submission Status), the dispositions **Approved**, **Interim Approval**, and **Rejected** are reserved exclusively for the customer's authorized representative. No engine, canvas, MCP tool, or skill delivered in this repository may emit, infer, or imply customer approval as a system-produced verdict. The platform evaluates and reports supplier **submission readiness** (`SUBMISSION_READY`, `NOT_READY`, `INDETERMINATE`).

5. **Engineering Heuristics Declaration:**  
   Any threshold, default, or validation rule introduced without an explicit published standard behind it is declared and labeled an **engineering heuristic**, never implied to be an industry standard.

---

## RULE Entries

## RULE 1: Table 4.1 Submission Levels & Table 4.2 Retention/Submission Matrix

**Decision:** Encode the 18-element Production Part Approval Process submission and retention requirements across all five submission levels (Levels 1–5) exactly per AIAG PPAP 4th Edition Section 4, Table 4.1 and Table 4.2. Default to Level 3 when no level is specified. Model requirement codes as `"S"` (Submit), `"R"` (Retain), `"*"`, and `"CUSTOMER_DEFINED"` (for Level 4 non-warrant items when customer requirements are not yet specified).

**Source:**
- AIAG *Production Part Approval Process (PPAP)* Reference Manual, 4th Edition (June 2006), Section 4 (Table 4.1 & Table 4.2), pp. 17–19:
> "The organization shall submit the items and/or records specified in the level identified below in Table 4.1 :"
> "Level 1: Warrant only (and for designated appearance items, an Appearance Approval Report) submitted to the customer."
> "Level 2: Warrant with product samples and limited supporting data submitted to the customer."
> "Level 3: Warrant with product samples and complete supporting data submitted to the customer."
> "Level 4: Warrant and other requirements as defined by the customer."
> "Level 5: Warrant with product samples and complete supporting data reviewed at the organization's manufacturing location."
> "See Retention/Submission Requirements Table 4.2 for exact retention/submission requirements for each submission level."
> "The organization shall use level 3 as the default level for all submissions unless otherwise specified by the authorized customer representative."
> "Table 4.2 lists submission and retention requirements. Mandatory and applicable requirements for a PPAP record are defined in the PPAP manual and by the customer."
> "S = The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations."
> "R = The organization shall retain at appropriate locations and make available to the customer upon request."
> "* = The organization shall retain at appropriate locations and submit to the customer upon request."

**Rationale:** Table 4.1 defines the five standardized submission levels and their core scope. Table 4.2 specifies the exact 18-element retention vs. submission matrix. The standard explicitly states that Level 3 is the default submission level for all submissions unless otherwise agreed with the customer. Level 4 specifies that warrant is submitted and other requirements are defined by customer. Level 5 requires all records to be retained and reviewed at the organization's manufacturing location.

**Applied In:** `packages/quality-core/src/quality_core/ppap/table_4_1.py` (`RequirementCode`, `REQUIREMENT_CODES`, `SUBMISSION_LEVELS`, `ELEMENT_IDS`, `TABLE_4_1_MATRIX`, `TABLE_4_1_LEGEND`, `SUBMISSION_LEVEL_DESCRIPTIONS`, `lookup_requirement`, `requirement_legend`, `elements_required_at_level`, `submission_level_description`).

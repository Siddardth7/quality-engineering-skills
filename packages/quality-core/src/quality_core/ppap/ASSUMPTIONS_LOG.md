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

## RULE 1: Initial Process Studies (§2.2.11) Capability Acceptance Criteria, Quality Indices, Stability Gate & Attribute Data Guard

**Decision:** Implement the statistical acceptance gate for PPAP Element §2.2.11 Initial Process Studies strictly according to AIAG PPAP 4th Edition §2.2.11.1–§2.2.11.6:
1. **Index Selection:** Use $P_{pk}$ (performance index based on total variation) for initial process studies and short-term data; allow $C_{pk}$ (capability index based on within-subgroup variation) only when historical data or sufficient initial data demonstrate a stable process (§2.2.11.2).
2. **Acceptance Criteria Bands:** Evaluate against Table 2.2.11.3:
   - $\text{Index} > 1.67$: `ACCEPTABLE` ("The process currently meets the acceptance criteria.").
   - $1.33 \le \text{Index} \le 1.67$: `POTENTIALLY_ACCEPTABLE` ("The process may be acceptable. Contact the authorized customer representative for a review of the study results.").
   - $\text{Index} < 1.33$: `UNACCEPTABLE` ("The process does not currently meet the acceptance criteria. Contact the authorized customer representative for a review of the study results. The organization shall submit to the authorized customer representative for approval a corrective action plan and a modified Control Plan normally providing for 100% inspection.").
3. **Stability Gate:** Processes exhibiting out-of-control signals or instability yield `INDETERMINATE`, requiring special causes to be eliminated and corrective action plans submitted prior to PPAP submission (§2.2.11.4).
4. **Attribute Data Guard:** Attribute data (counts, pass/fail) cannot yield variables capability indices and resolve `NOT_APPLICABLE_ATTRIBUTE_DATA` (§2.2.11.1 Note 2).
5. **Sample Size Adequacy:** Minimum sample size is 100 readings across at least 25 subgroups; smaller datasets without customer concurrence resolve `INDETERMINATE` (§2.2.11.1 Note 5, §2.2.11.2).

**Source:**
- AIAG *Production Part Approval Process (PPAP)* Reference Manual, 4th Edition (June 2006), §2.2.11 (pp. 7–9):
> "The level of initial process capability or performance shall be determined to be acceptable prior to submission"
> "The initial process study is focused on variables not attribute data"
> "Unless approved by the authorized customer representative, attribute data are not acceptable for PPAP submissions."
> "a short-term study should be based on a minimum of 25 subgroups containing at least 100 readings"
> "Cpk - The capability index for a stable process"
> "Ppk - The performance index"
> "When historical data are available or enough initial data exist to plot a control chart"
> "When not enough data are available (< 100 samples) or there are unknown sources of variation, contact the authorized customer representative"
> "Index>1.67 The process currently meets the acceptance criteria."
> "1.33_5_Index_5_1.67 The process may be acceptable. Contact the authorized customer representative for a review of the study results."
> "Index<1.3 3 The process does not currently meet the acceptance criteria. Contact the authorized customer representative for a review of the study results."
> "The organization shall notify the authorized customer representative of any unstable processes that exist and shall submit a corrective action plan"
> "The organization shall determine with the authorized customer representative alternative acceptance criteria for processes with one-sided specifications or non-normal distributions."
> "The above mentioned acceptance criteria (2.2.1 1.3) assume normality and a two-sided specification"
> "The organization shall submit to the authorized customer representative for approval a corrective action plan and a modified Control Plan normally providing for 100% inspection."

**Rationale:** Initial process studies evaluate process variation and statistical capability against published acceptance thresholds. Reusing `quality_core.spc` guarantees that capability formulas ($C_p, C_{pk}, P_p, P_{pk}$) and Western Electric stability gates are applied deterministically without math duplication.

**Applied In:** `packages/quality-core/src/quality_core/ppap/process_study.py` (`StudyVerdict`, `AcceptanceBand`, `IndexType`, `ProcessStudyResult`, `assess_initial_process_study`, `MINIMUM_INITIAL_STUDY_SAMPLES`, `MINIMUM_INITIAL_STUDY_SUBGROUPS`, `ACCEPTANCE_THRESHOLD_CAPABLE`, `ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE`).

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
   - On-machine path: `/Users/sid/Documents/Upskill/SixSigma/AIAG Production Part Approval Process (PPAP), 4th Edition (2006).pdf`  
   - **Training Deck Inventory:**  
     - *Verified present in deck:* The 18 canonical element names, the five Submission Level definitions (Levels 1–5), and the 27-field Part Submission Warrant field list.  
     - *Missing from deck (not authoritative for):* Table 4.1 submission/retention matrix, Section 5 Part Submission Status body text (Approved / Interim Approval / Rejected definitions), Section 2.2.11 Initial Process Studies numeric acceptance criteria ($P_{pk}/C_{pk}$ bands and actions), Section 3 Customer Notification and Submission Requirements, Section 6 Record Retention, and Appendix A field completion instructions.

---

## Honesty & Scoping Declarations

1. **ISO 9001:2015 & IATF 16949:2016 Non-Citability Limitation:**  
   The on-machine files `/Users/sid/Documents/Upskill/SixSigma/ISO-9001-2015.pdf` and `/Users/sid/Documents/Upskill/SixSigma/pdfcoffee.com_iatf16949-2016-standard-pdf-free.pdf` are scanned images with no text layer. IATF 16949:2016 §8.3.4.4 ("Product approval process") is therefore **not citable in Milestone 8**. Any mention in code or documentation is context-only and must be marked as uncited.

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

<!-- RULE entries are introduced starting in Epic 1 (E1) through Epic 7 (E7) as each schema and calculation module lands. -->

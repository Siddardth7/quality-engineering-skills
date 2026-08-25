# Engineering Assumptions Log — Production Part Approval Process (PPAP) Core

**Package:** `quality_core.ppap`  
**Domain:** Production Part Approval Process (PPAP) 18-Element Completeness Auditor, Table 4.1 Matrix, Applicability Rules, Initial Process Studies Gate, PSW Validator, and Cross-Engine Linkage.  
**Release Target:** `v0.8.0`  
**Tracking Issue:** [#98](https://github.com/Siddardth7/quality-engineering-skills/issues/98) (Epic 0) / [#99](https://github.com/Siddardth7/quality-engineering-skills/issues/99) (Epic 1) / [#101](https://github.com/Siddardth7/quality-engineering-skills/issues/101) (Epic 3) / [#104](https://github.com/Siddardth7/quality-engineering-skills/issues/104) (Epic 6)

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

## RULE 1: Canonical 18 PPAP Element Vocabulary, Numbering, and Ordering (§2.2.1–§2.2.18)

**Decision:** Encode the 18 canonical AIAG PPAP elements strictly matching the Section 2.2 requirement section numbers (§2.2.1 through §2.2.18), official titles, and 1-indexed numbering:
1. §2.2.1: Design Records
2. §2.2.2: Authorized Engineering Change Documents
3. §2.2.3: Customer Engineering Approval
4. §2.2.4: Design Failure Mode and Effects Analysis (Design FMEA)
5. §2.2.5: Process Flow Diagrams
6. §2.2.6: Process Failure Mode and Effects Analysis (Process FMEA)
7. §2.2.7: Control Plan
8. §2.2.8: Measurement System Analysis Studies
9. §2.2.9: Dimensional Results
10. §2.2.10: Records of Material / Performance Test Results
11. §2.2.11: Initial Process Studies
12. §2.2.12: Qualified Laboratory Documentation
13. §2.2.13: Appearance Approval Report (AAR)
14. §2.2.14: Sample Production Parts
15. §2.2.15: Master Sample
16. §2.2.16: Checking Aids
17. §2.2.17: Customer-Specific Requirements
18. §2.2.18: Part Submission Warrant (PSW)

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006), Section 2.2 (Lines 100–450):
> "2.2.1 Design Records ... 2.2.2 Authorized Engineering Change Documents ... 2.2.3 Customer Engineering Approval ... 2.2.4 Design Failure Mode and Effects Analysis ... 2.2.5 Process Flow Diagrams ... 2.2.6 Process Failure Mode and Effects Analysis ... 2.2.7 Control Plan ... 2.2.8 Measurement System Analysis Studies ... 2.2.9 Dimensional Results ... 2.2.10 Records of Material / Performance Test Results ... 2.2.11 Initial Process Studies ... 2.2.12 Qualified Laboratory Documentation ... 2.2.13 Appearance Approval Report (AAR) ... 2.2.14 Sample Production Parts ... 2.2.15 Master Sample ... 2.2.16 Checking Aids ... 2.2.17 Customer-Specific Requirements ... 2.2.18 Part Submission Warrant (PSW)"

**Rationale:** The AIAG 4th Edition standard Section 2.2 defines the authoritative 18-element taxonomy for automotive production part approval. Exact numbering and nomenclature ensure cross-tier compatibility and standards compliance across all quality workflows.

**Applied In:** `packages/quality-core/src/quality_core/ppap/schema.py` (`PPAP_ELEMENT_IDS`, `PPAP_ELEMENT_NAMES`, `PPAP_ELEMENT_NUMBERS`, `PPAP_ELEMENT_ALIASES`).

---

## RULE 2: Submission Levels 1–5 Verbatim Definitions (Section 4 & Table 4.1)

**Decision:** Encode the 5 Submission Levels (`SubmissionLevel = Literal[1, 2, 3, 4, 5]`) with verbatim manual definitions:
- **Level 1:** Warrant only (and for designated appearance items, an Appearance Approval Report) submitted to customer.
- **Level 2:** Warrant with product samples and limited supporting data submitted to customer.
- **Level 3:** Warrant with product samples and complete supporting data submitted to customer.
- **Level 4:** Warrant and other requirements as defined by customer.
- **Level 5:** Warrant with product samples and complete supporting data reviewed at supplier's manufacturing location.

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006), Section 4 (Submission Levels, Lines 460–500):
> "Level 1 — Warrant only (and for designated appearance items, an Appearance Approval Report) submitted to customer.
> Level 2 — Warrant with product samples and limited supporting data submitted to customer.
> Level 3 — Warrant with product samples and complete supporting data submitted to customer.
> Level 4 — Warrant and other requirements as defined by customer.
> Level 5 — Warrant with product samples and complete supporting data reviewed at supplier's manufacturing location."

**Rationale:** Submission levels govern the location and extent of evidence delivery vs retention at the manufacturing organization. Strict adherence to Table 4.1 level definitions prevents unauthorized assumptions about submission scope.

**Applied In:** `packages/quality-core/src/quality_core/ppap/schema.py` (`SUBMISSION_LEVELS`, `SUBMISSION_LEVEL_DESCRIPTIONS`, `SUBMISSION_LEVEL_ALIASES`, `PPAPPackage.submission_level`).

---

## RULE 3: Part Submission Warrant (PSW) Field 18 Reason for Submission Vocabulary (Appendix A & Section 3)

**Decision:** Encode the 10 canonical AIAG reasons for submission triggers without arbitrary alteration or narrowing:
1. Initial Submission
2. Engineering Change(s)
3. Tooling: Transfer, Replacement, Refurbishment, or additional
4. Correction of Discrepancy
5. Tooling Inactive > than 1 year
6. Change to Optional Construction or Material
7. Sub-Supplier or Material Source Change
8. Change in Part Processing
9. Parts Produced at Additional Location
10. Other

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006), Appendix A (Part Submission Warrant Field 18, Line 720) & Section 3:
> "REASON FOR SUBMISSION: Initial Submission, Engineering Change(s), Tooling: Transfer, Replacement, Refurbishment, or additional, Correction of Discrepancy, Tooling Inactive > than 1 year, Change to Optional Construction or Material, Sub-Supplier or Material Source Change, Change in Part Processing, Parts Produced at Additional Location, Other"

**Rationale:** The Part Submission Warrant Field 18 identifies the engineering or commercial trigger initiating a PPAP submission. Standardizing this vocabulary ensures consistent linkage with change management and applicability rules.

**Applied In:** `packages/quality-core/src/quality_core/ppap/schema.py` (`REASON_FOR_SUBMISSION_VALUES`, `REASON_FOR_SUBMISSION_ALIASES`, `PPAPPackage.reason_for_submission`).

---

## RULE 4: Conditional Element Applicability (§2.2.3, §2.2.4, §2.2.13, §2.2.15, §2.2.16)

**Decision:** Formulate element-by-element applicability evaluation yielding `APPLICABLE`, `NOT_APPLICABLE`, or `INDETERMINATE` for the five conditional PPAP elements:
1. **Design FMEA (§2.2.4):** `APPLICABLE` when the organization is design-responsible (`has_design_responsibility is True`). Resolves `NOT_APPLICABLE` when the customer is design-responsible (`has_design_responsibility is False`). Resolves `INDETERMINATE` when un-surveyed (`None`).
2. **Appearance Approval Report (§2.2.13):** `APPLICABLE` only when the part has appearance requirements on the design record (`appearance_item is True`). Resolves `NOT_APPLICABLE` when `appearance_item is False`. Resolves `INDETERMINATE` when un-surveyed (`None`).
3. **Checking Aids (§2.2.16):** `APPLICABLE` only when part-specific assembly or component checking aids exist (`has_checking_aid is True`). Resolves `NOT_APPLICABLE` when `has_checking_aid is False`. Resolves `INDETERMINATE` when un-surveyed (`None`).
4. **Customer Engineering Approval (§2.2.3):** `APPLICABLE` where specified by customer contract or specification (`customer_engineering_approval_required is True`). Resolves `NOT_APPLICABLE` when not required (`customer_engineering_approval_required is False`). Resolves `INDETERMINATE` when un-surveyed (`None`).
5. **Master Sample (§2.2.15):** `APPLICABLE` by default (`master_sample_waived is False`). Resolves `NOT_APPLICABLE` only upon documented customer waiver (`master_sample_waived is True`). Resolves `INDETERMINATE` when un-surveyed (`None`).

All remaining 13 elements (§2.2.1, §2.2.2, §2.2.5–§2.2.12, §2.2.14, §2.2.17, §2.2.18) are unconditionally `APPLICABLE` for standard discrete-part submissions. When any element is `INDETERMINATE`, the package verdict resolves `INDETERMINATE`.

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006):
- §2.2.4 (Line 230):
> "The organization shall have a Design FMEA for parts or materials for which they are design-responsible."
- §2.2.13 (Line 380):
> "A separate Appearance Approval Report (AAR) shall be completed for each part or series of parts for which a submission is required if the product/part has appearance requirements on the design record."
- §2.2.16 (Line 430):
> "If requested by the customer, the organization shall submit with the PPAP submission any part-specific assembly or component checking aid."
- §2.2.3 (Line 210):
> "Where specified by the customer, the organization shall have evidence of customer engineering approval."
- §2.2.15 (Line 410):
> "The organization shall retain a master sample for the same period as the production part approval records"

**Rationale:** The AIAG PPAP 4th Edition standard establishes that certain elements are strictly contingent on part characteristics or commercial assignment of responsibility. Forcing suppliers to submit DFMEAs when the customer owns design responsibility, or requiring AARs for non-appearance internal components, violates the AIAG standard. Evaluating applicability prior to evidence completeness audits prevents erroneous omission findings.

**Applied In:** `packages/quality-core/src/quality_core/ppap/applicability.py` (`CONDITIONAL_ELEMENTS`, `ElementApplicability`, `assess_applicability`).

---

## RULE 5: Submission Level 4 Indeterminacy Gate (Section 4 & Table 4.1)

**Decision:** When evaluating Submission Level 4 without an explicit customer requirement specification (`customer_level_4_requirements is None`), all 18 elements and the package verdict MUST resolve to `INDETERMINATE`.

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006), Section 4 (Line 490) & Table 4.1 (Line 540):
> "Level 4 — Warrant and other requirements as defined by customer."
> Table 4.1 footnote: "* = Organization shall retain at appropriate locations and submit to the customer upon request."

**Rationale:** Under AIAG PPAP 4th Edition, Level 4 has no standard default matrix. Every OEM and customer defines their own bespoke subset of elements for Level 4 submissions. Defaulting to Level 3 requirements or guessing customer requirements is a non-conformance.

**Applied In:** `packages/quality-core/src/quality_core/ppap/applicability.py` (`assess_applicability`).

---

## RULE 6: Scope Boundaries for Non-Discrete Commodities (Appendices F, G, H)

**Decision:** Standard discrete-part applicability evaluation is strictly bounded. When processing submissions for commodities covered by specialized AIAG PPAP appendices, the engine emits `INDETERMINATE` with explicit scope boundary notifications directing users to the appropriate appendix:
- **Appendix F (Bulk Materials):** Bulk Materials Requirements Checklist & Process FMEA/Control Plan exemptions.
- **Appendix G (Tires):** Tire Industry PPAP requirements & specialized testing.
- **Appendix H (Truck Industry):** Truck Industry specific requirements & modifications.

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006):
- Appendix F (Bulk Material - Specific Requirements, Lines 800–950)
- Appendix G (Tire Industry - Specific Requirements, Lines 960–1050)
- Appendix H (Truck Industry - Specific Requirements, Lines 1060–1150)

**Rationale:** Applying standard discrete manufacturing rules to bulk chemicals, polymers, tires, or heavy-duty truck components causes invalid findings. Flagging out-of-scope commodities as `INDETERMINATE` ensures strict standards honesty.

**Applied In:** `packages/quality-core/src/quality_core/ppap/applicability.py` (`assess_applicability`, `is_bulk_material`, `is_tire`, `is_truck_industry`, `commodity_type`).

---

## RULE 7: Reason for Submission Non-Narrowing (Section 3 & Appendix A)

**Decision:** All 10 AIAG canonical reasons for submission triggers are accepted as valid submission triggers without narrowing or suppressing any standard elements unless explicitly dictated by documented customer contract.

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006), Section 3 (Customer Notification and Submission Requirements, Lines 560–680) & Appendix A (Field 18).

**Rationale:** Section 3 requires customer notification and submission for specified situations (e.g. tooling transfer, new supplier, engineering change). The reason for submission explains *why* PPAP is initiated; the submission level determines *what* is submitted vs retained. Inventing arbitrary element reductions based solely on submission reason without customer agreement violates Section 3.

**Applied In:** `packages/quality-core/src/quality_core/ppap/applicability.py` (`assess_applicability`).

---

## RULE 8: Part Submission Warrant (PSW) 27-Field Form Completeness & Authority Invariant (Appendix A & Section 5)

**Decision:** Formulate 27-field PSW form completeness validation yielding `COMPLETE`, `INCOMPLETE`, or `INDETERMINATE`. Field 27 (Customer Disposition) is reserved exclusively for the customer; the engine validates supplier completion (Fields 1–26) and strictly refuses to emit or populate customer disposition statuses (`Approved`, `Interim Approval`, `Rejected`).

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006):
- Appendix A (Part Submission Warrant Completion Instructions, Lines 700–780)
- Section 5 (Part Submission Status, Lines 580–620):
> "Customer PPAP approval shall be obtained prior to shipping production parts... Dispositions: Approved, Interim Approval, Rejected."

**Rationale:** The PSW is the core legal declaration of production part conformance. Enforcing all 27 Appendix-A fields, conditional rules, and customer authority boundary prevents erroneous supplier submissions.

**Applied In:** `packages/quality-core/src/quality_core/ppap/psw.py` (`PartSubmissionWarrant`, `validate_psw`, `PSW_FIELD_NAMES`).

---

## RULE 9: Prohibition on Blanket Statements of Conformance (§2.2.9, §2.2.10, Appendix A)

**Decision:** Formulate word-boundary scanning heuristic detecting prohibited blanket conformance statements ("meets all specs", "all dimensions conform", "100% conforming") in test results and explanation fields, marking them `INVALID`.

**Source:** AIAG PPAP Reference Manual, 4th Edition (June 2006):
- §2.2.9 (Line 330): "Actual results are required... Blanket statements of conformance are unacceptable."
- §2.2.10 (Line 350): "Blanket statements of conformance are unacceptable for any test results."
- Appendix A (Field 20 & Field 21 Instructions).

**Rationale:** Suppliers frequently attempt to submit generic conformance statements instead of quantitative dimension/material data. Prohibiting blanket assertions enforces compliance with automotive OEM quality standards.

**Applied In:** `packages/quality-core/src/quality_core/ppap/psw.py` (`find_blanket_statements`, `BLANKET_STATEMENT_PATTERNS`, `validate_psw`).

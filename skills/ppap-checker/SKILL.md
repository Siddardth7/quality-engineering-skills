---
name: ppap-checker
description: AIAG PPAP (4th Edition) 18-element package completeness auditing, Table 4.1 submission/retention requirement lookup, PSW 27-field validation, and Initial Process Study capability assessment routing all checks to audit_ppap_package, lookup_ppap_requirement, validate_psw, assess_ppap_capability, and render_ppap_canvas on quality-mcp.
---

# PPAP Completeness & Readiness Checker: AIAG 4th Edition 18-Element Package Auditing

## Overview

The `ppap-checker` skill guides AI agents in authoring, surveying, auditing, and validating Production Part Approval Process (PPAP) submission packages according to the **AIAG Production Part Approval Process (PPAP) Reference Manual (4th Edition, June 2006)**.

The primary purpose of PPAP is to determine whether all customer engineering design record and specification requirements are properly understood by the supplier, and that the manufacturing process has the potential to produce product consistently meeting these requirements during an actual production run at the quoted production rate.

### The 18 AIAG PPAP Elements (§2.2.1–§2.2.18)

AIAG PPAP 4th Edition Section 2.2 defines 18 documentation and physical verification elements:

1. **§2.2.1 Design Records:** Verifiable engineering drawings, CAD models, part specifications, and material definitions.
2. **§2.2.2 Authorized Engineering Change Documents:** Authorized engineering change notices (ECN/ECO) not yet recorded in design records.
3. **§2.2.3 Customer Engineering Approval:** Formal evidence of customer engineering approval where required by the customer.
4. **§2.2.4 Design FMEA (DFMEA):** Design Failure Mode and Effects Analysis where the supplier is design-responsible.
5. **§2.2.5 Process Flow Diagrams:** Sequential description of the manufacturing process from receiving through shipping.
6. **§2.2.6 Process FMEA (PFMEA):** Process Failure Mode and Effects Analysis following AIAG-VDA Action Priority criteria.
7. **§2.2.7 Control Plan:** Pre-launch and production control plans defining operational controls, inspection methods, and reaction plans linked to PFMEA failure causes.
8. **§2.2.8 Measurement System Analysis (MSA) Studies:** Gage R&R, bias, linearity, and stability studies on measurement systems referenced in the Control Plan.
9. **§2.2.9 Dimensional Results:** Full ballooned dimensional evaluation of sample parts demonstrating conformance to design records.
10. **§2.2.10 Records of Material / Performance Test Results:** Chemical, physical, metallurgical, and functional test reports with certified laboratory scope documentation.
11. **§2.2.11 Initial Process Studies:** Statistical process capability evaluation on all Special and Critical Characteristics.
12. **§2.2.12 Qualified Laboratory Documentation:** Scope and ISO/IEC 17025 accreditation credentials of internal and external testing laboratories.
13. **§2.2.13 Appearance Approval Report (AAR):** Dedicated inspection report for parts with color, grain, gloss, or surface appearance criteria.
14. **§2.2.14 Sample Production Parts:** Physical production parts manufactured during the significant production run.
15. **§2.2.15 Master Sample:** Retained physical reference sample identified and preserved per customer agreement.
16. **§2.2.16 Checking Aids:** Detailed records, certification, and calibration of inspection fixtures, templates, and gages.
17. **§2.2.17 Customer-Specific Requirements:** Compliance records for OEM and customer-specific quality overlays.
18. **§2.2.18 Part Submission Warrant (PSW):** Formal declaration warrant summarizing compliance across all 27 Appendix A fields.

### Table 4.1 Submission Levels (Levels 1–5)

AIAG PPAP 4th Edition Table 4.1 establishes five standard submission levels defining which of the 18 elements must be submitted to the customer vs retained at the supplier facility:

- **Level 1:** Warrant only (and for designated appearance items, an Appearance Approval Report) submitted to customer.
- **Level 2:** Warrant with product samples and limited supporting data submitted to customer.
- **Level 3:** Warrant with product samples and complete supporting data submitted to customer (**Default industry standard level**).
- **Level 4:** Warrant and other requirements as defined by the customer.
- **Level 5:** Warrant with product samples and complete supporting data reviewed at the supplier's manufacturing location.

Table 4.1 specifies four requirement codes:
- `S`: Submit to customer and retain a copy at the manufacturing location.
- `R`: Retain at the manufacturing location and make readily available to customer upon request.
- `*`: Retain at the manufacturing location and submit to customer upon request.
- `CUSTOMER_DEFINED`: Explicit requirement defined by customer agreement (Submission Level 4).

### Part Submission Warrant (Appendix A)

The Part Submission Warrant (PSW) contains 27 structured fields encompassing part identification, organization location, customer contact, materials reporting (IMDS), polymeric marking (ISO 11469/ISO 1043), reason for submission, submission level, declaration of conformance, significant production run rate, and authorized management sign-off. Blanket statements of conformance (e.g., *"meets all specs"*, *"100% conforming"*) are strictly prohibited by AIAG standards.

### 🔒 Section 5 Customer Authority Invariant

Under **AIAG PPAP 4th Edition Section 5 (Part Submission Status)**, final part approval dispositions (`Approved`, `Interim Approval`, `Rejected`) are the exclusive legal authority of the customer's authorized representative. Field 27 on the Part Submission Warrant is explicitly marked `"FOR CUSTOMER USE ONLY"`.

AI agents and automated tools must **never** award customer approval dispositions. The skill and backing MCP tools evaluate and report supplier submission readiness only:
- `SUBMISSION_READY`: All required Table 4.1 elements are present, valid, and compliant for the target submission level.
- `NOT_READY`: One or more required Table 4.1 elements are missing, incomplete, or non-conforming.
- `INDETERMINATE`: Missing mandatory information (such as undefined Level 4 customer requirements or unresolved applicability conditions) prevents a deterministic readiness verdict.

### Cross-Engine Linkage & Zero Inline Math/Adjudication

This skill integrates upstream quality-core calculation engines:
- **§2.2.4 / §2.2.6 FMEA:** Connects to AIAG-VDA Action Priority scoring via `quality_core.scoring`.
- **§2.2.7 Control Plan:** Validates APQP Control Plan schemas and PFMEA linkage via `quality_core.controlplan`.
- **§2.2.8 MSA:** Evaluates Gage R&R studies via `quality_core.msa`.
- **§2.2.11 Initial Process Studies:** Evaluates capability indices and Western Electric stability rules via `quality_core.ppap.process_study` and `quality_core.spc`.

---

## When to Use

### When to Use:
- **PPAP Package Completeness Audits:** Surveying the 18 AIAG elements for a new part introduction, engineering change, or tooling transfer across Submission Levels 1–5.
- **Supplier Submission Readiness Verification:** Assessing whether an assembled PPAP package is complete and ready for customer submission or if blocking gaps remain.
- **Table 4.1 Requirement Inquiries:** Looking up exact AIAG retention and submission codes (`S`, `R`, `*`) for specific elements at requested submission levels.
- **Part Submission Warrant (PSW) Auditing:** Validating the 27 Appendix A form fields for completeness, consistency, and prohibited blanket statements.
- **Initial Process Study Capability Gating (§2.2.11):** Evaluating process performance indices against AIAG acceptance criteria with sample adequacy and stability gates.
- **Interactive Visual PPAP Canvas Reporting:** Generating single-writer dark/light HTML checklist matrices and KPI summary cards for cross-functional APQP gate reviews.

### Do NOT Use When:
- Drafting operational Shop-Floor Control Plans (use [`control-plan`](../control-plan/SKILL.md)).
- Performing raw crossed Gage R&R ANOVA computations (use [`msa-gauge-rr`](../msa-gauge-rr/SKILL.md)).
- Conducting standalone 5-Why root cause investigations (use [`5why-root-cause`](../5why-root-cause/SKILL.md)).
- Writing shop-floor Nonconformance Reports (use [`ncr-writing`](../ncr-writing/SKILL.md)).

### Input Requirements

To audit a PPAP package or validate specific elements, gather:
1. **PPAP Package Dictionary (`package`):**
   - Header metadata: `part_number`, `part_name`, `submission_level` (1–5), `reason_for_submission`, and optional applicability flags (`has_design_responsibility`, `appearance_item`, `has_checking_aid`, `customer_engineering_approval_required`, `master_sample_waived`, `is_bulk_material`, `is_tire`, `is_truck_industry`).
   - `elements`: List of element evidence dictionaries containing `element_id` (`"2.2.1"`–`"2.2.18"`), `status` (`"PRESENT"`, `"MISSING"`, `"NOT_APPLICABLE"`, `"UNDECIDED"`), `artifact_ref`, and optional sub-engine payloads (`control_plan`, `fmea`, `msa`, `process_study`).
2. **Table 4.1 Lookup Parameters:**
   - `submission_level` (integer 1–5 or alias `"Level 1"`–`"Level 5"`).
   - `element_id` (canonical ID `"2.2.1"`–`"2.2.18"`, element number 1–18, or name alias).
   - `code` (optional requirement code filter: `"S"`, `"R"`, `"*"`, `"CUSTOMER_DEFINED"`).
3. **Part Submission Warrant Dictionary (`psw`):**
   - Fields 1–26 matching AIAG Appendix A requirements, including part identification, organization details, IMDS reporting, declaration of conformance, production rate, and authorized signature.
4. **Initial Process Study Data (`data`, `lsl`, `usl`):**
   - 1D raw readings or 2D subgroup array, lower and upper specification limits, and optional stability violation signals.

### Prerequisites

- Active `quality-mcp` server connection providing `audit_ppap_package`, `lookup_ppap_requirement`, `validate_psw`, `assess_ppap_capability`, and `render_ppap_canvas`.

---

## Step-by-Step Methodology

Follow the 7-step AIAG PPAP evaluation framework:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   7-STEP AIAG PPAP AUDIT METHODOLOGY                   │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Gather Package & Metadata     │ Collect part info, level, reason    │
│ 2. Confirm Submission Level      │ Query Table 4.1 via quality-mcp     │
│ 3. Assess Applicability          │ Evaluate conditional rules §2.2.1-18│
│ 4. Look Up Table 4.1 Codes       │ Route codes to lookup_ppap_req      │
│ 5. Audit Package Completeness    │ Route audit to audit_ppap_package   │
│ 6. Validate PSW Warrant Fields   │ Route form check to validate_psw    │
│ 7. Report Submission Readiness   │ Render canvas & synthesize findings │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Package Ingestion & Metadata Collection
- Assemble the PPAP submission package metadata: part name, part number, engineering change level, purchasing order, target submission level (1–5), and reason for submission per AIAG Section 3.
- Collate available element evidence, document references, and cross-engine attachments (DFMEA, Process Flow, PFMEA, Control Plan, MSA Gage R&R, CMM inspection reports, Material certifications, Capability studies).

### 2. Step 2: Submission Level Confirmation & Requirement Lookup
- Identify the customer-mandated Submission Level (Level 1, 2, 3, 4, or 5). If unspecified, default to Level 3.
- Invoke `lookup_ppap_requirement` on `quality-mcp` to retrieve the exact Table 4.1 requirement codes (`S`, `R`, `*`) and verbatim legend descriptions.
- For **Submission Level 4**, note that requirements are customer-defined. If customer requirements are not provided, flag as `INDETERMINATE` and prompt the user for the customer's requirement set.

### 3. Step 3: Conditional Element Applicability Assessment
- Assess part characteristics and contractual scope against AIAG conditional applicability rules:
  - §2.2.4 DFMEA: Resolves `NOT_APPLICABLE` if supplier lacks product design responsibility.
  - §2.2.13 Appearance Approval Report: Applicable only for designated appearance items.
  - §2.2.16 Checking Aids: Applicable only when checking fixtures, gages, or templates are utilized.
  - §2.2.3 Customer Engineering Approval: Applicable only where customer engineering approval is required.
  - §2.2.15 Master Sample: Applicable unless formally waived in writing by customer.

### 4. Step 4: Initial Process Study Capability Evaluation (§2.2.11)
- For all Special and Critical Characteristics, invoke `assess_ppap_capability` on `quality-mcp`.
- The tool deterministically validates sample adequacy, stability signals, specification limits, and evaluates capability indices (Ppk or Cpk) against AIAG acceptance criteria.
- The agent interprets only the returned `verdict` and executes the returned `required_action`.
- Attribute data submitted for variables capability indices is rejected per §2.2.11.1 Note 2.

### 5. Step 5: Package Completeness & Evidence Linkage Audit
- Invoke `audit_ppap_package` on `quality-mcp` passing the package dictionary and applicability parameters.
- The engine evaluates each of the 18 elements by joining evidence status x Table 4.1 requirement code x applicability:
  - `SUBMITTED`: Evidence is present and satisfies `S` requirement.
  - `RETAINED_ON_FILE`: Evidence is retained at manufacturing facility satisfying `R` or `*` requirement.
  - `MISSING`: Mandatory element evidence is absent (blocking element).
  - `NOT_APPLICABLE`: Element does not apply per AIAG conditional rules.
  - `INDETERMINATE`: Missing metadata, undecided status, or unconfigured Level 4 customer rules.
  - `EVIDENCE_INVALID`: Attached sub-engine evidence (Control Plan, PFMEA, MSA, SPC) failed technical validation.
- The overall package readiness resolves to `SUBMISSION_READY`, `NOT_READY`, or `INDETERMINATE`.

### 6. Step 6: Part Submission Warrant (PSW) Validation (Appendix A)
- Invoke `validate_psw` on `quality-mcp` passing the 27 Appendix A form fields.
- The tool verifies that all mandatory fields are populated, validates production run rate and duration, checks authorized signature entries, screens for prohibited blanket statements of conformance, and flags any attempted population of the customer-only disposition block (Field 27).

### 7. Step 7: Visual Canvas Rendering & Readiness Synthesis
- Invoke `render_ppap_canvas` on `quality-mcp` to generate an interactive visual HTML checklist matrix canvas.
- Synthesize an engineering disposition:
  - State the supplier submission readiness verdict (`SUBMISSION_READY`, `NOT_READY`, or `INDETERMINATE`).
  - Name all blocking elements and missing artifacts with AIAG section numbers.
  - Follow the required actions returned by `assess_ppap_capability` and `validate_psw`.

---

## Tool Invocations

### `audit_ppap_package`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic 18-element completeness auditing and supplier submission readiness assessment per AIAG PPAP 4th Edition.
- **Parameters:**
  - `package` (`dict[str, Any] | None`): PPAP package dictionary containing header metadata and 18-element evidence records. If `None`, falls back to benchmark Level 3 automotive sample dataset.
  - `submission_level` (`int | str | None`): Submission Level (1–5) per AIAG Section 4.
  - `reason_for_submission` (`str | None`): Reason for submission per AIAG Section 3 (e.g., `'Initial Submission'`).
  - `has_design_responsibility` (`bool | None`): Flag indicating product design responsibility (§2.2.4 DFMEA).
  - `appearance_item` (`bool | None`): Flag indicating appearance item (§2.2.13 AAR).
  - `has_checking_aid` (`bool | None`): Flag indicating checking aid usage (§2.2.16).
  - `customer_engineering_approval_required` (`bool | None`): Flag indicating customer engineering approval requirement (§2.2.3).
  - `master_sample_waived` (`bool | None`): Flag indicating master sample waiver (§2.2.15).
  - `is_bulk_material` (`bool | None`): Flag for bulk materials (Appendix F).
  - `is_tire` (`bool | None`): Flag for tires (Appendix G).
  - `is_truck_industry` (`bool | None`): Flag for truck industry (Appendix H).
  - `customer_level_4_requirements` (`dict[str, str] | None`): Customer-defined requirement codes for Level 4 submissions.
  - `commodity_type` (`str | None`): Commodity type classification.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards attribution string (`"AIAG PPAP Reference Manual, 4th Edition (2006)"`).
  - `package_verdict` (`string`): Supplier readiness verdict (`"SUBMISSION_READY"`, `"NOT_READY"`, `"INDETERMINATE"`).
  - `submission_level` (`integer`): Evaluated submission level (1–5).
  - `reason_for_submission` (`string`): Evaluated reason for submission.
  - `elements` (`dict[string, dict]`): 18 element audit results keyed by canonical ID (`"2.2.1"`–`"2.2.18"`), containing `element_id`, `element_name`, `verdict`, `requirement_code`, `applicability_verdict`, `rationale`, `is_blocking`, `evidence_status`, `artifact_ref`, `document_reference`, `evidence_valid`.
  - `verdict_counts` (`dict[string, integer]`): Counts of elements across verdicts (`SUBMITTED`, `RETAINED_ON_FILE`, `MISSING`, `NOT_APPLICABLE`, `INDETERMINATE`, `EVIDENCE_INVALID`).
  - `blocking_elements` (`list[string]`): Canonical IDs of blocking elements preventing submission readiness.
  - `blocking_element_names` (`list[string]`): Names of blocking elements.
  - `submitted_elements` (`list[string]`): Elements submitted to customer.
  - `retained_elements` (`list[string]`): Elements retained at supplier facility.
  - `missing_elements` (`list[string]`): Missing elements.
  - `not_applicable_elements` (`list[string]`): Not applicable elements.
  - `indeterminate_elements` (`list[string]`): Indeterminate elements.
  - `invalid_elements` (`list[string]`): Elements with invalid attached evidence.
  - `standards_basis` (`string`): Standards citation.
  - `applicability_result` (`dict | null`): Detailed element applicability breakdown.

#### Invocation
```json
{
  "package": {
    "part_number": "TOS-8842-A",
    "part_name": "Transmission Output Shaft",
    "submission_level": 3,
    "reason_for_submission": "Initial Submission",
    "elements": [
      {
        "element_id": "2.2.1",
        "status": "PRESENT",
        "artifact_ref": "DWG-TOS-8842-RevC.pdf"
      },
      {
        "element_id": "2.2.2",
        "status": "PRESENT",
        "artifact_ref": "ECN-2026-015.pdf"
      },
      {
        "element_id": "2.2.3",
        "status": "NOT_APPLICABLE"
      },
      {
        "element_id": "2.2.4",
        "status": "PRESENT",
        "artifact_ref": "DFMEA-TOS-004.pdf"
      },
      {
        "element_id": "2.2.5",
        "status": "PRESENT",
        "artifact_ref": "PFD-TOS-001.pdf"
      },
      {
        "element_id": "2.2.6",
        "status": "PRESENT",
        "artifact_ref": "PFMEA-TOS-002.pdf"
      },
      {
        "element_id": "2.2.7",
        "status": "PRESENT",
        "artifact_ref": "CP-TOS-003.pdf"
      },
      {
        "element_id": "2.2.8",
        "status": "PRESENT",
        "artifact_ref": "MSA-TOS-GRR.pdf"
      },
      {
        "element_id": "2.2.9",
        "status": "PRESENT",
        "artifact_ref": "DIM-TOS-CMM.pdf"
      },
      {
        "element_id": "2.2.10",
        "status": "PRESENT",
        "artifact_ref": "MAT-TOS-CERT.pdf"
      },
      {
        "element_id": "2.2.11",
        "status": "PRESENT",
        "artifact_ref": "SPC-TOS-STUDY.pdf"
      },
      {
        "element_id": "2.2.12",
        "status": "PRESENT",
        "artifact_ref": "LAB-ISO17025.pdf"
      },
      {
        "element_id": "2.2.13",
        "status": "NOT_APPLICABLE"
      },
      {
        "element_id": "2.2.14",
        "status": "PRESENT",
        "artifact_ref": "SAMPLE-PARTS-6PCS"
      },
      {
        "element_id": "2.2.15",
        "status": "PRESENT",
        "artifact_ref": "MASTER-SAMPLE-TAG-01"
      },
      {
        "element_id": "2.2.16",
        "status": "PRESENT",
        "artifact_ref": "CHK-AID-TOS-01.pdf"
      },
      {
        "element_id": "2.2.17",
        "status": "PRESENT",
        "artifact_ref": "CSR-APEX-REV4.pdf"
      },
      {
        "element_id": "2.2.18",
        "status": "PRESENT",
        "artifact_ref": "PSW-TOS-8842.pdf"
      }
    ]
  },
  "submission_level": 3,
  "reason_for_submission": "Initial Submission",
  "has_design_responsibility": true,
  "appearance_item": false,
  "has_checking_aid": true,
  "customer_engineering_approval_required": false,
  "master_sample_waived": false
}
```

#### Successful Response
```json
{
  "package_verdict": "SUBMISSION_READY",
  "submission_level": 3,
  "reason_for_submission": "Initial Submission",
  "verdict_counts": {
    "SUBMITTED": 13,
    "RETAINED_ON_FILE": 3,
    "MISSING": 0,
    "NOT_APPLICABLE": 2,
    "INDETERMINATE": 0,
    "EVIDENCE_INVALID": 0
  },
  "blocking_elements": [],
  "blocking_element_names": [],
  "submitted_elements": [
    "2.2.1",
    "2.2.2",
    "2.2.4",
    "2.2.5",
    "2.2.6",
    "2.2.7",
    "2.2.8",
    "2.2.9",
    "2.2.10",
    "2.2.11",
    "2.2.12",
    "2.2.14",
    "2.2.18"
  ],
  "retained_elements": [
    "2.2.15",
    "2.2.16",
    "2.2.17"
  ],
  "missing_elements": [],
  "not_applicable_elements": [
    "2.2.3",
    "2.2.13"
  ],
  "indeterminate_elements": [],
  "invalid_elements": [],
  "standards_basis": "AIAG PPAP 4th Edition (June 2006)",
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "elements": {
    "2.2.1": {
      "element_id": "2.2.1",
      "element_name": "Design Records",
      "verdict": "SUBMITTED",
      "requirement_code": "S",
      "applicability_verdict": "APPLICABLE",
      "rationale": "The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations (Table 4.1 coded 'S'); evidence present and submitted.",
      "is_blocking": false,
      "evidence_status": "submitted",
      "evidence_present": null,
      "artifact_ref": "DWG-TOS-8842-RevC.pdf",
      "document_reference": "DWG-TOS-8842-RevC.pdf",
      "evidence_valid": null
    },
    "2.2.7": {
      "element_id": "2.2.7",
      "element_name": "Control Plan",
      "verdict": "SUBMITTED",
      "requirement_code": "S",
      "applicability_verdict": "APPLICABLE",
      "rationale": "The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations (Table 4.1 coded 'S'); evidence present and submitted.",
      "is_blocking": false,
      "evidence_status": "submitted",
      "evidence_present": null,
      "artifact_ref": "CP-TOS-003.pdf",
      "document_reference": "CP-TOS-003.pdf",
      "evidence_valid": null
    },
    "2.2.13": {
      "element_id": "2.2.13",
      "element_name": "Appearance Approval Report (AAR)",
      "verdict": "NOT_APPLICABLE",
      "requirement_code": "S",
      "applicability_verdict": "NOT_APPLICABLE",
      "rationale": "Part does not have appearance requirements on design record; Appearance Approval Report (AAR) is not applicable (\u00a72.2.13).",
      "is_blocking": false,
      "evidence_status": "not_applicable",
      "evidence_present": null,
      "artifact_ref": null,
      "document_reference": null,
      "evidence_valid": null
    },
    "2.2.18": {
      "element_id": "2.2.18",
      "element_name": "Part Submission Warrant (PSW)",
      "verdict": "SUBMITTED",
      "requirement_code": "S",
      "applicability_verdict": "APPLICABLE",
      "rationale": "The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations (Table 4.1 coded 'S'); evidence present and submitted.",
      "is_blocking": false,
      "evidence_status": "submitted",
      "evidence_present": null,
      "artifact_ref": "PSW-TOS-8842.pdf",
      "document_reference": "PSW-TOS-8842.pdf",
      "evidence_valid": null
    }
  }
}
```

---

### `lookup_ppap_requirement`
- **MCP Server:** `quality-mcp`
- **Purpose:** Look up AIAG PPAP 4th Edition Table 4.1 submission/retention requirement codes (`S`, `R`, `*`) and verbatim standard legend descriptions for any element across Submission Levels 1–5.
- **Parameters:**
  - `element_id` (`str | int | None`): Canonical PPAP element ID (`"2.2.1"`–`"2.2.18"`), element number (1–18), or name alias (e.g. `"dfmea"`, `"control_plan"`). If `None`, returns all 18 elements for the submission level.
  - `submission_level` (`int | str`, default `3`): PPAP submission level (1–5) or alias (`"Level 1"`–`"Level 5"`).
  - `code` (`str | None`): Optional requirement code filter (`"S"`, `"R"`, `"*"`, `"CUSTOMER_DEFINED"`).
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards citation.
  - `submission_level` (`integer`): Evaluated submission level (1–5).
  - `submission_level_description` (`string`): Verbatim standard definition of the submission level.
  - `element_id` (`string`, for single element): Canonical element ID.
  - `element_name` (`string`, for single element): Verbatim AIAG element name.
  - `requirement_code` (`string`, for single element): Table 4.1 code (`"S"`, `"R"`, `"*"`, `"CUSTOMER_DEFINED"`).
  - `requirement_description` (`string`, for single element): Verbatim standard requirement description.
  - `elements` (`list[dict]`, for all elements): List of element requirement objects.
  - `total_elements` (`integer`, for all elements): Total element count.
  - `required_submit_count` (`integer`, for all elements): Count of elements requiring submission (`S`).
  - `required_retain_count` (`integer`, for all elements): Count of elements requiring retention (`R`).
  - `legend` (`dict[string, string]`): Verbatim Table 4.1 requirement code legend.

#### Invocation
```json
{
  "element_id": "2.2.7",
  "submission_level": 3
}
```

#### Successful Response
```json
{
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "submission_level": 3,
  "submission_level_description": "Warrant with product samples and complete supporting data submitted to the customer.",
  "element_id": "2.2.7",
  "element_name": "Control Plan",
  "requirement_code": "S",
  "requirement_description": "The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations.",
  "legend": {
    "S": "The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations.",
    "R": "The organization shall retain at appropriate locations and make available to the customer upon request.",
    "*": "The organization shall retain at appropriate locations and submit to the customer upon request.",
    "CUSTOMER_DEFINED": "Warrant and other requirements as defined by the customer."
  }
}
```

---

### `validate_psw`
- **MCP Server:** `quality-mcp`
- **Purpose:** Validate Part Submission Warrant (PSW) fields per AIAG PPAP 4th Edition Appendix A, detecting prohibited blanket statements, checking cross-consistency, and verifying customer authority isolation.
- **Parameters:**
  - `psw` (`dict[str, Any] | None`): Part Submission Warrant field dictionary matching Appendix A (Fields 1–26) or aliases. If `None`, falls back to benchmark sample PSW dataset.
  - `has_checking_aid` (`bool | None`): Optional boolean indicating whether a checking aid is used for the part.
  - `package` (`dict[str, Any] | None`): Optional PPAP package dictionary for cross-consistency verification.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards citation.
  - `verdict` (`string`): Warrant validation verdict (`"COMPLETE"`, `"INCOMPLETE"`, `"INVALID"`, `"INDETERMINATE"`).
  - `fields` (`dict[integer, dict]`): Field validation objects for Fields 1–27 (`field_number`, `field_name`, `verdict`, `value`, `details`, `is_required`, `standard_reference`).
  - `missing_fields` (`list[integer]`): Numbers of missing required fields.
  - `invalid_fields` (`list[integer]`): Numbers of invalid fields.
  - `indeterminate_fields` (`list[integer]`): Numbers of indeterminate fields.
  - `blanket_statement_detected` (`boolean`): Flag indicating whether prohibited blanket statements were found.
  - `blanket_statement_findings` (`list[string]`): Detailed findings for detected blanket statements.
  - `cross_consistency_findings` (`list[string]`): Findings for package/warrant discrepancies.
  - `customer_disposition_present` (`boolean`): Flag indicating if Field 27 was populated.
  - `customer_disposition_warning` (`string | null`): Warning regarding customer-only authority for Field 27.
  - `warnings` (`list[string]`): Non-fatal validation warnings.
  - `standards_basis` (`string`): Standards citation.

#### Invocation
```json
{
  "psw": {
    "part_name": "Transmission Output Shaft",
    "customer_part_number": "TOS-8842-A",
    "part_drawing_number": "DWG-TOS-8842",
    "engineering_change_level": "Rev C",
    "engineering_change_date": "2026-01-15",
    "purchase_order_number": "PO-99281-2026",
    "part_weight_kg": 2.45,
    "organization_name": "Acme Precision Drivetrain Inc.",
    "organization_code": "V-12345",
    "organization_address": "100 Precision Way, Detroit, MI 48202",
    "customer_name": "Apex Motors Corporation",
    "customer_division": "Powertrain Division",
    "customer_contact": "Jane Doe, Senior Quality Engineer",
    "application": "6-Speed Automatic Transmission Model 6T70",
    "materials_reporting": "IMDS ID #12948281",
    "polymeric_parts_marking": "ISO 11469 / ISO 1043",
    "reason_for_submission": "Initial Submission",
    "submission_level": 3,
    "declaration_of_conformance": true,
    "production_rate": 120.0,
    "production_duration_hours": 8.0,
    "explanation_comments": "Initial PPAP Level 3 submission. All dimensional and material specifications verified.",
    "authorized_signature": "John Smith",
    "authorized_signature_name": "John Smith",
    "authorized_signature_title": "Quality Assurance Manager",
    "authorized_signature_date": "2026-02-01",
    "authorized_signature_phone": "+1-313-555-0199",
    "authorized_signature_email": "jsmith@acmeprecision.com"
  }
}
```

#### Successful Response
```json
{
  "verdict": "INCOMPLETE",
  "missing_fields": [
    20,
    22
  ],
  "invalid_fields": [],
  "indeterminate_fields": [],
  "blanket_statement_detected": false,
  "blanket_statement_findings": [],
  "cross_consistency_findings": [],
  "customer_disposition_present": false,
  "customer_disposition_warning": null,
  "warnings": [],
  "standards_basis": "AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition (June 2006), Appendix A \u2014 Part Submission Warrant (PSW) Completion Instructions and Section 5 \u2014 Part Submission Status.",
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "fields": {
    "1": {
      "field_number": 1,
      "field_name": "Part Name",
      "verdict": "VALID",
      "value": "Transmission Output Shaft",
      "details": "Part Name provided.",
      "is_required": true,
      "standard_reference": "AIAG PPAP 4th Edition Appendix A Field 1"
    },
    "18": {
      "field_number": 18,
      "field_name": "Reason for Submission",
      "verdict": "VALID",
      "value": "Initial Submission",
      "details": "Valid Reason for Submission: 'Initial Submission'.",
      "is_required": true,
      "standard_reference": "AIAG PPAP 4th Edition Appendix A Field 18"
    },
    "19": {
      "field_number": 19,
      "field_name": "Submission Level",
      "verdict": "VALID",
      "value": 3,
      "details": "Submission Level 3 specified.",
      "is_required": true,
      "standard_reference": "AIAG PPAP 4th Edition Appendix A Field 19 & Section 4"
    },
    "20": {
      "field_number": 20,
      "field_name": "Submission Results",
      "verdict": "MISSING",
      "value": null,
      "details": "Submission Results declaration is required.",
      "is_required": true,
      "standard_reference": "AIAG PPAP 4th Edition Appendix A Field 20"
    }
  }
}
```

---

### `assess_ppap_capability`
- **MCP Server:** `quality-mcp`
- **Purpose:** Assess Initial Process Studies (§2.2.11) against AIAG PPAP 4th Edition capability criteria (acceptance bands, sample adequacy, stability gating).
- **Parameters:**
  - `data` (`list[float] | list[list[float]] | None`): Sample measurement data as 1D list or 2D list of subgroups. If `None`, loads benchmark dataset.
  - `lsl` (`float | None`): Lower Specification Limit.
  - `usl` (`float | None`): Upper Specification Limit.
  - `is_attribute` (`bool`, default `false`): Flag indicating attribute data (§2.2.11.1 Note 2).
  - `is_ongoing_stable_process` (`bool`, default `false`): If True, evaluates Cpk (within-subgroup); otherwise evaluates Ppk (total variation).
  - `violations` (`list[dict[str, Any]] | None`): Control-chart out-of-control signals from stability assessment.
  - `customer_concurrence` (`bool`, default `false`): Customer concurrence flag.
  - `custom_threshold_capable` (`float`, default `1.67`): Acceptance threshold for capable process per §2.2.11.3.
  - `custom_threshold_potentially_capable` (`float`, default `1.33`): Acceptance threshold for potentially capable process per §2.2.11.3.
  - `precomputed_index_type` (`str | None`): Precomputed index type (`'Ppk'` or `'Cpk'`) when raw data is omitted.
  - `precomputed_index_value` (`float | None`): Precomputed index value.
  - `precomputed_sample_size` (`int | None`): Precomputed sample size.
  - `precomputed_subgroup_count` (`int | None`): Precomputed subgroup count.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards citation.
  - `verdict` (`string`): Capability verdict (`"ACCEPTABLE"`, `"POTENTIALLY_ACCEPTABLE"`, `"UNACCEPTABLE"`, `"INDETERMINATE"`).
  - `index_type` (`string | null`): Evaluated index type (`"Ppk"` or `"Cpk"`).
  - `index_value` (`float | null`): Calculated capability index value.
  - `band` (`string | null`): AIAG acceptance band classification.
  - `required_action` (`string`): Verbatim AIAG PPAP 4th Edition mandated action for the evaluated result.
  - `rationales` (`list[string]`): Engineering rationales supporting the verdict.
  - `citations` (`list[string]`): Standards citations (§2.2.11).
  - `stable` (`boolean | null`): Process stability determination.
  - `violations` (`list[dict] | null`): Detected out-of-control signals.
  - `sample_size` (`integer`): Total sample readings.
  - `subgroup_count` (`integer | null`): Number of subgroups.
  - `is_attribute` (`boolean`): Attribute data flag.
  - `customer_concurrence` (`boolean`): Customer concurrence flag.

#### Invocation
```json
{
  "lsl": 9.5,
  "usl": 10.5,
  "is_ongoing_stable_process": false,
  "customer_concurrence": false
}
```

#### Successful Response
```json
{
  "verdict": "ACCEPTABLE",
  "index_type": "Ppk",
  "index_value": 2.0937234257745576,
  "band": "GREATER_THAN_1_67",
  "required_action": "The process currently meets the acceptance criteria.",
  "rationales": [
    "Ppk = 2.0937 > 1.67: Process meets acceptance criteria.",
    "Used Ppk based on initial process study short-term data (\u00a72.2.11.2)."
  ],
  "citations": [
    "AIAG PPAP 4th Edition \u00a72.2.11.3 (Table 2.2.11.3: Index > 1.67)"
  ],
  "stable": null,
  "violations": null,
  "sample_size": 125,
  "subgroup_count": 25,
  "is_attribute": false,
  "customer_concurrence": false,
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)"
}
```

---

### `render_ppap_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Render an interactive visual HTML checklist matrix canvas for an 18-element PPAP package with dark/light themes and KPI cards.
- **Parameters:**
  - `package` (`dict[str, Any] | None`): PPAP package dictionary or canvas elements dictionary. If `None`, loads benchmark Level 3 sample dataset.
  - `submission_level` (`int | str`, default `3`): Active submission level (1–5) to highlight.
  - `title` (`str`, default `"AIAG PPAP 4th Edition 18-Element Checklist Canvas"`): Title displayed on canvas header.
  - `theme` (`str`, default `"dark"`): Theme mode (`"dark"` or `"light"`).
  - `standalone` (`bool`, default `true`): If True, returns standalone HTML5 document; if False, embeddable container.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards citation.
  - `title` (`string`): Canvas title.
  - `rows_count` (`integer`): Number of rendered element rows (18).
  - `submission_level` (`integer`): Highlighted submission level.
  - `summary` (`dict[string, Any]`): KPI summary counts (`total_elements`, `submission_level`, `submission_level_description`, `reason_for_submission`, `part_name`, `part_number`, `organization`, `customer`, `status_counts`, `required_elements_count`, `required_submitted_count`, `required_missing_count`, `required_undecided_count`, `submission_readiness`, `standards_basis`, `authority_notice`).
  - `html` (`string`): Rendered HTML string.

#### Invocation
```json
{
  "submission_level": 3,
  "theme": "dark",
  "standalone": true
}
```

#### Successful Response
```json
{
  "title": "AIAG PPAP 4th Edition 18-Element Checklist Canvas",
  "rows_count": 18,
  "submission_level": 3,
  "summary": {
    "total_elements": 18,
    "submission_level": 3,
    "submission_level_description": "Warrant with product samples and complete supporting data submitted to the customer.",
    "reason_for_submission": "Initial Submission",
    "part_name": "Transmission Output Shaft",
    "part_number": "PART-SFT-4410",
    "organization": "Acme Precision Driveline Systems",
    "customer": "Apex Automotive Group",
    "status_counts": {
      "submitted": 16,
      "retained": 1,
      "not_applicable": 1,
      "missing": 0,
      "undecided": 0
    },
    "required_elements_count": 15,
    "required_submitted_count": 15,
    "required_missing_count": 0,
    "required_undecided_count": 0,
    "submission_readiness": "SUBMISSION_READY",
    "standards_basis": "AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition (June 2006), Table 4.1 & Table 4.2 Submission and Retention Matrix, Section 2.2 Element Requirements, and Section 5 Part Submission Status.",
    "authority_notice": "Customer approval dispositions ('Approved', 'Interim Approval', 'Rejected') are reserved exclusively for the customer's authorized representative per AIAG PPAP 4th Edition Section 5. This canvas evaluates supplier submission readiness only."
  },
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "html": "<!DOCTYPE html><html><head><title>AIAG PPAP Canvas</title>...</head><body><div class=\"ppap-canvas-container\">...</div></body></html>"
}
```

---

### Worked Examples

#### Example 1: Level 3 Package with Missing Element (`NOT_READY`)

##### Invocation
```json
{
  "package": {
    "part_number": "TOS-8842-A",
    "part_name": "Transmission Output Shaft",
    "submission_level": 3,
    "reason_for_submission": "Initial Submission",
    "elements": [
      {
        "element_id": "2.2.1",
        "status": "PRESENT",
        "artifact_ref": "DWG-TOS-8842-RevC.pdf"
      },
      {
        "element_id": "2.2.2",
        "status": "PRESENT",
        "artifact_ref": "ECN-2026-015.pdf"
      },
      {
        "element_id": "2.2.3",
        "status": "NOT_APPLICABLE"
      },
      {
        "element_id": "2.2.4",
        "status": "PRESENT",
        "artifact_ref": "DFMEA-TOS-004.pdf"
      },
      {
        "element_id": "2.2.5",
        "status": "PRESENT",
        "artifact_ref": "PFD-TOS-001.pdf"
      },
      {
        "element_id": "2.2.6",
        "status": "PRESENT",
        "artifact_ref": "PFMEA-TOS-002.pdf"
      },
      {
        "element_id": "2.2.7",
        "status": "MISSING"
      },
      {
        "element_id": "2.2.8",
        "status": "PRESENT",
        "artifact_ref": "MSA-TOS-GRR.pdf"
      },
      {
        "element_id": "2.2.9",
        "status": "PRESENT",
        "artifact_ref": "DIM-TOS-CMM.pdf"
      },
      {
        "element_id": "2.2.10",
        "status": "PRESENT",
        "artifact_ref": "MAT-TOS-CERT.pdf"
      },
      {
        "element_id": "2.2.11",
        "status": "PRESENT",
        "artifact_ref": "SPC-TOS-STUDY.pdf"
      },
      {
        "element_id": "2.2.12",
        "status": "PRESENT",
        "artifact_ref": "LAB-ISO17025.pdf"
      },
      {
        "element_id": "2.2.13",
        "status": "NOT_APPLICABLE"
      },
      {
        "element_id": "2.2.14",
        "status": "PRESENT",
        "artifact_ref": "SAMPLE-PARTS-6PCS"
      },
      {
        "element_id": "2.2.15",
        "status": "PRESENT",
        "artifact_ref": "MASTER-SAMPLE-TAG-01"
      },
      {
        "element_id": "2.2.16",
        "status": "PRESENT",
        "artifact_ref": "CHK-AID-TOS-01.pdf"
      },
      {
        "element_id": "2.2.17",
        "status": "PRESENT",
        "artifact_ref": "CSR-APEX-REV4.pdf"
      },
      {
        "element_id": "2.2.18",
        "status": "PRESENT",
        "artifact_ref": "PSW-TOS-8842.pdf"
      }
    ]
  },
  "submission_level": 3,
  "reason_for_submission": "Initial Submission",
  "has_design_responsibility": true,
  "appearance_item": false,
  "has_checking_aid": true,
  "customer_engineering_approval_required": false,
  "master_sample_waived": false
}
```

##### Successful Response
```json
{
  "package_verdict": "NOT_READY",
  "submission_level": 3,
  "reason_for_submission": "Initial Submission",
  "verdict_counts": {
    "SUBMITTED": 12,
    "RETAINED_ON_FILE": 3,
    "MISSING": 1,
    "NOT_APPLICABLE": 2,
    "INDETERMINATE": 0,
    "EVIDENCE_INVALID": 0
  },
  "blocking_elements": [
    "2.2.7"
  ],
  "blocking_element_names": [
    "Control Plan"
  ],
  "submitted_elements": [
    "2.2.1",
    "2.2.2",
    "2.2.4",
    "2.2.5",
    "2.2.6",
    "2.2.8",
    "2.2.9",
    "2.2.10",
    "2.2.11",
    "2.2.12",
    "2.2.14",
    "2.2.18"
  ],
  "retained_elements": [
    "2.2.15",
    "2.2.16",
    "2.2.17"
  ],
  "missing_elements": [
    "2.2.7"
  ],
  "not_applicable_elements": [
    "2.2.3",
    "2.2.13"
  ],
  "indeterminate_elements": [],
  "invalid_elements": [],
  "standards_basis": "AIAG PPAP 4th Edition (June 2006)",
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "elements": {
    "2.2.7": {
      "element_id": "2.2.7",
      "element_name": "Control Plan",
      "verdict": "MISSING",
      "requirement_code": "S",
      "applicability_verdict": "APPLICABLE",
      "rationale": "Element is applicable and required to be submitted to customer (Table 4.1 coded 'S'), but evidence is missing.",
      "is_blocking": true,
      "evidence_status": "missing",
      "evidence_present": null,
      "artifact_ref": null,
      "document_reference": null,
      "evidence_valid": null
    }
  }
}
```

##### Interpretation
The package readiness verdict is deterministically evaluated as `NOT_READY`. Under AIAG PPAP 4th Edition Table 4.1, Element §2.2.7 (Control Plan) is mandatory for submission (`S`) at Level 3. The package cannot be submitted to the customer until the Control Plan is completed, approved, and integrated into the submission package.

---

#### Example 2: Negative Control (Level 4 Package with No Customer Requirement Set)

##### Invocation
```json
{
  "package": {
    "part_number": "BRK-4011",
    "part_name": "Brake Caliper Housing",
    "submission_level": 4,
    "reason_for_submission": "Initial Submission"
  },
  "submission_level": 4,
  "reason_for_submission": "Initial Submission",
  "customer_level_4_requirements": null
}
```

##### Successful Response
```json
{
  "package_verdict": "INDETERMINATE",
  "submission_level": 4,
  "reason_for_submission": "Initial Submission",
  "verdict_counts": {
    "SUBMITTED": 0,
    "RETAINED_ON_FILE": 0,
    "MISSING": 0,
    "NOT_APPLICABLE": 0,
    "INDETERMINATE": 18,
    "EVIDENCE_INVALID": 0
  },
  "blocking_elements": [
    "2.2.1",
    "2.2.2",
    "2.2.3",
    "2.2.4",
    "2.2.5",
    "2.2.6",
    "2.2.7",
    "2.2.8",
    "2.2.9",
    "2.2.10",
    "2.2.11",
    "2.2.12",
    "2.2.13",
    "2.2.14",
    "2.2.15",
    "2.2.16",
    "2.2.17",
    "2.2.18"
  ],
  "blocking_element_names": [
    "Design Records",
    "Authorized Engineering Change Documents",
    "Customer Engineering Approval",
    "Design Failure Mode and Effects Analysis (Design FMEA)",
    "Process Flow Diagrams",
    "Process Failure Mode and Effects Analysis (Process FMEA)",
    "Control Plan",
    "Measurement System Analysis Studies",
    "Dimensional Results",
    "Records of Material / Performance Test Results",
    "Initial Process Studies",
    "Qualified Laboratory Documentation",
    "Appearance Approval Report (AAR)",
    "Sample Production Parts",
    "Master Sample",
    "Checking Aids",
    "Customer-Specific Requirements",
    "Part Submission Warrant (PSW)"
  ],
  "submitted_elements": [],
  "retained_elements": [],
  "missing_elements": [],
  "not_applicable_elements": [],
  "indeterminate_elements": [
    "2.2.1",
    "2.2.2",
    "2.2.3",
    "2.2.4",
    "2.2.5",
    "2.2.6",
    "2.2.7",
    "2.2.8",
    "2.2.9",
    "2.2.10",
    "2.2.11",
    "2.2.12",
    "2.2.13",
    "2.2.14",
    "2.2.15",
    "2.2.16",
    "2.2.17",
    "2.2.18"
  ],
  "invalid_elements": [],
  "standards_basis": "AIAG PPAP 4th Edition (June 2006)",
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)"
}
```

##### Interpretation
Per AIAG PPAP 4th Edition Table 4.1, Submission Level 4 is defined as *"Warrant and other requirements as defined by the customer."* When no customer requirement set is provided (`customer_level_4_requirements: null`), the requirement codes for all 18 elements are unknown, and the package readiness resolves to `INDETERMINATE`.

**CRITICAL RULE FOR AI AGENTS:** The agent must **NEVER** fall back to Level 3 rules, invent default OEM requirements, or guess customer submission expectations. The correct and only valid response is to inform the user that Level 4 submission requirements are customer-defined and request the customer's specific submission requirement matrix.

---

## Best Practices

1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** AI agents must strictly observe the five core domain invariants:
   - 1. Never recite a Table 4.1 cell from memory. Every submission/retention code comes from `lookup_ppap_requirement`. If the tool is unavailable, say so — do not answer from recall.
   - 2. Never decide an element's completeness inline. Every verdict comes from `audit_ppap_package`.
   - 3. Never compute a capability index. `assess_ppap_capability` owns §2.2.11.
   - 4. Never state or imply a customer approval. `Approved`, `Interim Approval`, and `Rejected` are assigned by the customer's authorized representative under the PSW's "FOR CUSTOMER USE ONLY" block. The skill reports submission readiness only. This mirrors the [E4] #102 / [E6] #104 / [E9] #107 authority invariant, at the prompt layer.
   - 5. Never substitute an OEM Customer-Specific Requirement. Ford / GM / Stellantis / VW / BMW overlays are out of scope for `v0.8.0` (v2 backlog per ROADMAP.md); an unsupplied Level 4 requirement set is a question for the user, not a gap to fill.

2. **Reject Blanket Statements of Conformance:** Enforce the AIAG PPAP 4th Edition Appendix A prohibition on blanket statements (*"meets all specs"*, *"100% conforming"*). Actual dimensional readings, lab test data, and CMM certificates must be referenced.

3. **Stability Gate Precedes Capability Indexing:** Never report capability for an out-of-control manufacturing process. All stability gating and capability acceptance determinations are performed by `assess_ppap_capability`.

4. **Attribute Data Guard (§2.2.11.1 Note 2):** Attribute data (go/no-go, pass/fail counts) cannot yield capability indices and is rejected by `assess_ppap_capability`.

5. **Cross-Engine Evidence Verification:** Treat attached technical evidence (Control Plan, PFMEA, Gage R&R) as verdict-affecting. A PPAP package cannot be submission-ready if an attached Control Plan fails validation.

6. **Master Sample Retention Discipline (§2.2.15):** Ensure physical master samples are properly tagged, preserved, and retained for each cavity, mold, or die unless formally waived by the customer.

7. **Qualified Laboratory Scope (§2.2.12):** Verify that internal or external testing laboratories possess an accredited laboratory scope (e.g. ISO/IEC 17025) covering the specific test methods cited.

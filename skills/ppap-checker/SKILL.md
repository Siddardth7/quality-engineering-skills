---
name: ppap-checker
description: AIAG PPAP (4th Edition) 18-element package completeness auditing, Table 4.1 submission/retention requirement lookup, PSW 27-field validation, and Initial Process Study capability assessment routing all checks to audit_ppap_package, lookup_ppap_requirement, validate_psw, assess_ppap_capability, and render_ppap_canvas on quality-mcp.
---

# PPAP Checker: AIAG PPAP (4th Edition) 18-Element Completeness & Validation

## Overview

The `ppap-checker` skill guides AI agents in authoring, auditing, validating, and reviewing Production Part Approval Process (PPAP) submission packages according to the **AIAG Production Part Approval Process (PPAP) Reference Manual (4th Edition, June 2006)**.

The primary purpose of PPAP is to determine whether all customer engineering design record and specification requirements are properly understood by the supplier, and that the manufacturing process has the potential to produce product consistently meeting these requirements during an actual production run at the quoted production rate.

### The 18 AIAG PPAP Elements (§2.2.1–§2.2.18)

AIAG PPAP 4th Edition Section 2.2 defines 18 mandatory documentation and physical verification elements:

1. **§2.2.1 Design Records:** Fully ballooned part drawings, CAD models, specifications, and material definitions.
2. **§2.2.2 Engineering Change Documents:** Authorized Engineering Change Orders (ECO/ECN) not yet incorporated into design records.
3. **§2.2.3 Customer Engineering Approval:** Formal customer engineering sign-offs when mandated by customer specifications.
4. **§2.2.4 Design Failure Mode and Effects Analysis (DFMEA):** Product risk analysis (mandatory when the supplier has design responsibility per §2.2.4).
5. **§2.2.5 Process Flow Diagrams:** Step-by-step manufacturing sequence from receiving through shipping, including rework and quarantine loops.
6. **§2.2.6 Process Failure Mode and Effects Analysis (PFMEA):** Manufacturing process risk analysis following AIAG & VDA guidelines.
7. **§2.2.7 Control Plan:** Pre-launch and Production Control Plans defining characteristic controls, sample sizes, frequencies, and reaction plans.
8. **§2.2.8 Measurement System Analysis (MSA) Studies:** Gage Repeatability & Reproducibility ($\%GRR \le 30\%$, $ndc \ge 5$), bias, linearity, and stability studies on all measurement equipment referenced in the Control Plan.
9. **§2.2.9 Dimensional Results:** Full dimensional inspection verification across all ballooned drawing characteristics on sample parts.
10. **§2.2.10 Material / Performance Test Results:** Chemical, physical, metallurgical, and functional DVP&R test records with accredited laboratory scope documentation.
11. **§2.2.11 Initial Process Studies:** Short-term statistical capability assessments ($P_{pk} \ge 1.67$, $C_{pk} \ge 1.67$) on all Special and Critical Characteristics.
12. **§2.2.12 Qualified Laboratory Documentation:** Laboratory scope and ISO/IEC 17025 accreditation certificates for all internal and external testing facilities.
13. **§2.2.13 Appearance Approval Report (AAR):** Dedicated appearance inspection report for parts with color, grain, luster, or surface appearance criteria.
14. **§2.2.14 Sample Production Parts:** Physical production parts manufactured during the significant production run.
15. **§2.2.15 Master Sample:** Retained physical reference sample identified and preserved at the manufacturing facility.
16. **§2.2.16 Checking Aids:** Part-specific fixtures, gages, contours, check fixtures, and templates with calibration records and MSA studies.
17. **§2.2.17 Customer-Specific Requirements (CSR):** Records documenting compliance with OEM/Tier-1 specific quality standards and audit requirements.
18. **§2.2.18 Part Submission Warrant (PSW):** Appendix A declaration form summarizing the submission, production run details, declaration of conformance, and authorized supplier signature.

### Table 4.1 Submission Levels (Levels 1–5)

AIAG PPAP 4th Edition Table 4.1 establishes five standard submission levels defining which of the 18 elements must be submitted to the customer vs retained at the supplier facility:

- **Level 1:** Part Submission Warrant (PSW) only (and Appearance Approval Report if applicable) submitted to customer.
- **Level 2:** PSW with product samples and limited supporting data submitted to customer.
- **Level 3:** PSW with product samples and complete supporting data submitted to customer (**Default industry standard level**).
- **Level 4:** PSW and other requirements as defined by the customer.
- **Level 5:** PSW with product samples and complete supporting data reviewed at the supplier's manufacturing location.

Table 4.1 specifies four requirement codes:
- `S`: Submit to customer and retain a copy at the manufacturing location.
- `R`: Retain at the manufacturing location and make readily available to customer upon request.
- `*`: Retain at the manufacturing location and submit to customer upon request.
- `CUSTOMER_DEFINED`: Explicit requirement defined by customer agreement (Submission Level 4).

### Part Submission Warrant (Appendix A)

The Part Submission Warrant (PSW) contains 27 structured fields encompassing part identification, organization location, customer contact, materials reporting (IMDS/CAMDS), polymeric marking (ISO 11469/ISO 1043), reason for submission, submission level, declaration of conformance, significant production run rate, and authorized management sign-off. Blanket statements of conformance (e.g., *"meets all specs"*, *"100% conforming"*) are strictly prohibited by AIAG standards.

### 🔒 Section 5 Customer Authority Invariant

Under **AIAG PPAP 4th Edition Section 5 (Part Submission Status)**, final part approval dispositions (`Approved`, `Interim Approval`, `Rejected`) are the exclusive legal authority of the customer's authorized representative. Field 27 on the Part Submission Warrant is explicitly marked `"FOR CUSTOMER USE ONLY"`.

AI agents and automated tools must **never** award customer approval dispositions. The skill and backing MCP tools evaluate and report supplier submission readiness only:
- `SUBMISSION_READY`: All required Table 4.1 elements are present, valid, and compliant for the target submission level.
- `NOT_READY`: One or more required Table 4.1 elements are missing, incomplete, or non-conforming.
- `INDETERMINATE`: Missing mandatory information (such as undefined Level 4 customer requirements or unresolved applicability conditions) prevents a deterministic readiness verdict.

### Cross-Engine Linkage & Zero Inline Math/Adjudication

This skill integrates upstream quality-core calculation engines:
- **§2.2.4 / §2.2.6 FMEA:** Connects to AIAG & VDA Action Priority (AP) scoring via `quality_core.scoring`.
- **§2.2.7 Control Plan:** Validates APQP Control Plan schemas and PFMEA linkage via `quality_core.controlplan`.
- **§2.2.8 MSA:** Evaluates Gage R&R $\%GRR \le 30\%$ and $ndc \ge 5$ acceptance criteria via `quality_core.msa`.
- **§2.2.11 Initial Process Studies:** Evaluates $P_{pk}/C_{pk}$ capability indices and Western Electric stability rules via `quality_core.ppap.process_study` and `quality_core.spc`.

> [!IMPORTANT]
> **Strict Invariant: Zero Inline Math & Zero Inline Adjudication.** AI agents must **never** calculate capability indices ($P_{pk}, C_{pk}$), audit 18-element completeness, look up Table 4.1 requirement codes, evaluate PSW field rules, or render canvases directly in prompt text. All evaluation logic must be routed through deterministic `quality-mcp` tools.

---

## When to Use

### Use When:
- Auditing draft or assembled PPAP packages for AIAG 18-element completeness prior to customer submission.
- Determining exact Table 4.1 submission (`S`), retention (`R`), or request (`*`) requirements across Submission Levels 1 through 5.
- Validating Part Submission Warrant (PSW) fields across all 27 Appendix A form entries and screening for prohibited blanket statements.
- Evaluating Initial Process Studies (§2.2.11) $P_{pk}/C_{pk}$ statistical capability data against AIAG acceptance bands and stability gates.
- Generating interactive visual HTML checklist matrix canvases for cross-functional APQP gate sign-offs.
- Evaluating Engineering Change Orders (ECO/ECN), tooling transfers, or new supplier onboarding PPAP requirements.

### Do NOT Use When:
- Drafting operational Shop-Floor Control Plans (use [`control-plan`](../control-plan/SKILL.md)).
- Performing raw crossed Gage R&R ANOVA computations (use [`msa-gauge-rr`](../msa-gauge-rr/SKILL.md)).
- Conducting standalone 5-Why root cause investigations (use [`5why-root-cause`](../5why-root-cause/SKILL.md)).
- Writing shop-floor Nonconformance Reports (use [`ncr-writing`](../ncr-writing/SKILL.md)).

### Input Requirements

To audit a PPAP package or validate sub-elements, collect:
1. **PPAP Package Dictionary (`package`):**
   - `header`: Metadata including `part_number`, `part_name`, `revision`, `supplier_name`, `supplier_code`, `submission_level` (1–5), `reason_for_submission`, and optional applicability flags (`has_design_responsibility`, `appearance_item`, `has_checking_aid`, `customer_engineering_approval_required`, `master_sample_waived`, `is_bulk_material`, `is_tire`, `is_truck_industry`).
   - `elements`: Dictionary keyed by element ID (`"2.2.1"`–`"2.2.18"`) or alias (`"design_records"`, `"psw"`), with each element containing `status` (`"PRESENT"`, `"MISSING"`, `"NOT_APPLICABLE"`, `"WAIVED"`, `"UNDECIDED"`), `file_path`, `comments`, and optional technical payload.
2. **Table 4.1 Lookup Parameters:**
   - `submission_level` (integer 1–5 or alias `"Level 1"`–`"Level 5"`).
   - `element_id` (canonical ID `"2.2.1"`–`"2.2.18"`, element number 1–18, or name alias).
   - `code` (optional requirement code filter: `"S"`, `"R"`, `"*"`, `"CUSTOMER_DEFINED"`).
3. **Part Submission Warrant Dictionary (`psw`):**
   - Fields 1–26 matching AIAG Appendix A requirements, including part numbers, organization info, IMDS reporting, declaration of conformance, production rate, and authorized signature.
4. **Initial Process Study Data (`data`, `lsl`, `usl`):**
   - 1D raw readings or 2D subgroup array ($n \ge 100$, $k \ge 25$), lower and upper specification limits, and optional stability violation signals.

### Prerequisites

- Active `quality-mcp` server connection providing `audit_ppap_package`, `lookup_ppap_requirement`, `validate_psw`, `assess_ppap_capability`, and `render_ppap_canvas`.

---

## Step-by-Step Methodology

Follow the 7-step AIAG PPAP evaluation framework:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   7-STEP AIAG PPAP AUDIT METHODOLOGY                   │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Submission Scope & Level      │ Identify Level (1–5) & Applicability│
│ 2. Requirement Lookup (Table 4.1)│ Query Table 4.1 via quality-mcp     │
│ 3. Package Evidence Ingestion    │ Collect 18 element artifacts & logs │
│ 4. Deterministic Package Audit   │ Call audit_ppap_package on MCP      │
│ 5. PSW Form & Warrant Validation │ Validate 27 fields via validate_psw │
│ 6. Initial Process Capability    │ Assess Ppk/Cpk via assess_ppap_cap  │
│ 7. Canvas Render & Action Plan   │ Call render_ppap_canvas & triage    │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Submission Scope, Reason & Level Identification
- Identify the designated **Submission Level** (Levels 1–5). If unspecified, default to **Level 3** (full submission).
- Identify the **Reason for Submission** per AIAG Section 3: `INITIAL_SUBMISSION`, `ENGINEERING_CHANGE`, `TOOLING_CHANGE`, `CORRECTION_OF_DISCREPANCY`, `TOOLING_INACTIVE_EXCEEDING_ONE_YEAR`, `SUB_SUPPLIER_CHANGE`, `OPTIONAL_LOCATION_CHANGE`, or `OTHER`.
- Establish conditional applicability parameters:
  - `has_design_responsibility`: If false, §2.2.4 (DFMEA) is `NOT_APPLICABLE`.
  - `appearance_item`: If true, §2.2.13 (Appearance Approval Report) is mandatory.
  - `has_checking_aid`: If true, §2.2.16 (Checking Aids) is mandatory.
  - `customer_engineering_approval_required`: Governs §2.2.3.
  - `master_sample_waived`: If true, §2.2.15 may be waived.
  - Specialized industry flags: `is_bulk_material` (App F), `is_tire` (App G), `is_truck_industry` (App H).

### 2. Step 2: Table 4.1 Requirement Determination
- Query `lookup_ppap_requirement` on `quality-mcp` for the target submission level.
- Review the required submission (`S`) and retention (`R` / `*`) expectations for all 18 elements.
- For **Submission Level 4**, note that requirements are customer-defined. If customer requirements are not provided, flag as `INDETERMINATE` and prompt the user.

### 3. Step 3: Package Evidence Ingestion & Normalization
- Gather documentation records, files, test reports, and verification artifacts across all 18 elements.
- Map evidence availability status to canonical states:
  - `PRESENT`: Document or sample is verified and attached.
  - `MISSING`: Required item is absent from the submission package.
  - `NOT_APPLICABLE`: Item is formally excluded due to design responsibility or part characteristics.
  - `WAIVED`: Item requirement is formally waived with documented customer concurrence.
  - `UNDECIDED`: Evidence status has not been evaluated or verified.

### 4. Step 4: Deterministic Package Auditing via MCP
- Call `audit_ppap_package` on `quality-mcp` passing `package`, `submission_level`, `reason_for_submission`, and applicability flags.
- Inspect the audit verdict:
  - `SUBMISSION_READY`: All required Table 4.1 elements are satisfied.
  - `NOT_READY`: One or more required elements are missing or non-compliant.
  - `INDETERMINATE`: Missing customer definitions (Level 4) or unverified applicability gates.
- *Strict Invariant:* Never determine readiness status in prompt text. Always rely on `audit_ppap_package`.

### 5. Step 5: Part Submission Warrant (PSW) Validation
- Call `validate_psw` on `quality-mcp` to audit the 27 Appendix A form fields.
- Verify that:
  - Mandatory fields (part name, part numbers, organization name, plant address, customer contact, purchase order, submission level, reason for submission) are populated.
  - Materials reporting (IMDS) and polymeric marking checkboxes are completed.
  - Significant production run details (production rate $\ge 1$, duration $\ge 1$ hour) are recorded.
  - Authorized supplier representative name, title, date, and contact details are signed.
  - Blanket statements of conformance (e.g., *"100% conforming"*, *"meets all specs"*) are absent.
  - Field 27 ("FOR CUSTOMER USE ONLY") is left unassigned by the supplier.

### 6. Step 6: Initial Process Study (§2.2.11) Capability & Stability Assessment
- For all Special and Critical Characteristics, invoke `assess_ppap_capability` on `quality-mcp`:
  - Pass raw subgroup data ($n \ge 100$, $k \ge 25$) or precomputed index values, along with LSL and USL.
  - Verify statistical stability (absence of Western Electric out-of-control rules).
  - Verify capability thresholds per §2.2.11.3:
    - $P_{pk} \ge 1.67$: Capable (Meets acceptance criteria).
    - $1.33 \le P_{pk} < 1.67$: Potentially acceptable (Requires customer concurrence and corrective action plan).
    - $P_{pk} < 1.33$: Unacceptable (Requires 100% containment, corrective action, revised Control Plan).
  - Reject attribute data submitted for variables capability indices per §2.2.11.1 Note 2.

### 7. Step 7: Visual Canvas Rendering & Engineering Disposition
- Call `render_ppap_canvas` on `quality-mcp` to generate an interactive HTML checklist canvas.
- Synthesize actionable engineering recommendations:
  - Identify missing elements and assign responsible owners and completion deadlines.
  - Formulate containment and 100% inspection plans for any characteristics with $P_{pk} < 1.67$.
  - Prepare the final submission package for formal customer review.

---

## Tool Invocations

### 1. `audit_ppap_package`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic 18-element completeness auditing and supplier submission readiness assessment per AIAG PPAP 4th Edition.
- **Parameters:**
  - `package` (`dict[str, Any] | None`): PPAP package dictionary containing header metadata and 18-element evidence records. If `None`, falls back to benchmark Level 3 automotive sample dataset.
  - `submission_level` (`int | str | None`): Submission Level (1–5) per AIAG Section 4.
  - `reason_for_submission` (`str | None`): Reason for submission (e.g., `'INITIAL_SUBMISSION'`, `'ENGINEERING_CHANGE'`).
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
  - `basis` (`string`): Cited standards basis (`"AIAG PPAP Reference Manual, 4th Edition (2006)"`).
  - `readiness_verdict` (`string`): Supplier readiness verdict (`"SUBMISSION_READY"`, `"NOT_READY"`, `"INDETERMINATE"`).
  - `submission_level` (`integer`): Validated submission level (1–5).
  - `total_elements` (`integer`): Total number of evaluated elements (18).
  - `elements_submitted` (`integer`): Count of elements marked `PRESENT` for submission.
  - `elements_retained` (`integer`): Count of elements retained at manufacturing location.
  - `elements_missing` (`integer`): Count of mandatory elements currently `MISSING`.
  - `element_findings` (`list[dict]`): Element-by-element findings, Table 4.1 requirement code, evidence status, and compliance.
  - `remediation_items` (`list[string]`): Actionable steps to resolve missing or non-compliant elements.

#### Example Call:
```json
{
  "submission_level": 3,
  "reason_for_submission": "INITIAL_SUBMISSION",
  "has_design_responsibility": true,
  "appearance_item": false,
  "has_checking_aid": true
}
```

---

### 2. `lookup_ppap_requirement`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic retrieval of AIAG Table 4.1 submission/retention requirement codes (`S`, `R`, `*`) and verbatim standard legend descriptions.
- **Parameters:**
  - `element_id` (`str | int | None`): Canonical element ID (`"2.2.1"`–`"2.2.18"`), element number (1–18), or alias (`"dfmea"`, `"psw"`). If `None`, returns all 18 elements for the level.
  - `submission_level` (`int | str`, default `3`): PPAP submission level (1–5) or alias (`"Level 1"`–`"Level 5"`).
  - `code` (`str | None`): Optional requirement code filter (`"S"`, `"R"`, `"*"`, `"CUSTOMER_DEFINED"`).
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards basis citation.
  - `submission_level` (`integer`): Evaluated submission level (1–5).
  - `submission_level_description` (`string`): Verbatim AIAG Section 4 description.
  - `element_id` (`string`, optional): Requested element identifier.
  - `element_name` (`string`, optional): Element title.
  - `requirement_code` (`string`, optional): Table 4.1 requirement code (`"S"`, `"R"`, `"*"`, `"CUSTOMER_DEFINED"`).
  - `requirement_description` (`string`, optional): Verbatim requirement meaning.
  - `elements` (`list[dict]`, optional): Full 18-element requirement list when `element_id=None`.
  - `legend` (`dict[str, str]`): Full Table 4.1 code definitions.

#### Example Call:
```json
{
  "element_id": "2.2.7",
  "submission_level": 3
}
```

---

### 3. `validate_psw`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic validation of all 27 Part Submission Warrant (PSW) fields per Appendix A, blanket statement detection, cross-consistency checks, and customer authority invariant verification.
- **Parameters:**
  - `psw` (`dict[str, Any] | None`): PSW dictionary containing Fields 1–26. If `None`, uses benchmark sample dataset.
  - `has_checking_aid` (`bool | None`): Optional flag indicating if checking aid is used for the part.
  - `package` (`dict[str, Any] | None`): Optional PPAP package dictionary for cross-consistency verification.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards basis citation.
  - `is_valid` (`boolean`): True if all mandatory fields are valid and no critical errors exist.
  - `validation_status` (`string`): Overall warrant status (`"COMPLETE"`, `"INCOMPLETE"`, `"INVALID"`).
  - `missing_fields` (`list[string]`): List of omitted required fields.
  - `blanket_statement_detected` (`boolean`): True if prohibited blanket phrases were detected.
  - `blanket_statement_findings` (`list[string]`): Identified blanket phrasing locations.
  - `customer_disposition_flagged` (`boolean`): True if Field 27 was populated by supplier (warning).
  - `cross_consistency_findings` (`list[string]`): Discrepancies between PSW and package metadata.

#### Example Call:
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
    "explanation_comments": "Initial PPAP Level 3 submission.",
    "authorized_signature": "John Smith",
    "authorized_signature_name": "John Smith",
    "authorized_signature_title": "Quality Assurance Manager",
    "authorized_signature_date": "2026-02-01",
    "authorized_signature_phone": "+1-313-555-0199",
    "authorized_signature_email": "jsmith@acmeprecision.com"
  }
}
```

---

### 4. `assess_ppap_capability`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic capability evaluation for Initial Process Studies (§2.2.11) against AIAG acceptance criteria ($P_{pk} \ge 1.67$, $1.33 \le P_{pk} < 1.67$, $P_{pk} < 1.33$), stability gating, sample size verification ($n \ge 100, k \ge 25$), and standard action assignment.
- **Parameters:**
  - `data` (`list[float] | list[list[float]] | None`): 1D individual readings or 2D subgroup array. If `None`, loads benchmark dataset.
  - `lsl` (`float | None`): Lower Specification Limit.
  - `usl` (`float | None`): Upper Specification Limit.
  - `is_attribute` (`bool`, default `false`): Flag for attribute data (rejected from $P_{pk}/C_{pk}$ per §2.2.11.1 Note 2).
  - `is_ongoing_stable_process` (`bool`, default `false`): If True, evaluates $C_{pk}$ (within-subgroup); otherwise evaluates $P_{pk}$ (total variation).
  - `violations` (`list[dict] | None`): Optional list of control chart out-of-control rule violations.
  - `customer_concurrence` (`bool`, default `false`): Flag indicating customer concurrence for alternative sample sizes or interim plans.
  - `custom_threshold_capable` (`float`, default `1.67`): Capable acceptance threshold.
  - `custom_threshold_potentially_capable` (`float`, default `1.33`): Potentially capable threshold.
  - `precomputed_index_type` (`str | None`): `'Ppk'` or `'Cpk'` when raw data is omitted.
  - `precomputed_index_value` (`float | None`): Precomputed numeric index value.
  - `precomputed_sample_size` (`int | None`): Precomputed total sample size.
  - `precomputed_subgroup_count` (`int | None`): Precomputed subgroup count.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards basis citation.
  - `verdict` (`string`): Assessment verdict (`"CAPABLE"`, `"POTENTIALLY_ACCEPTABLE"`, `"UNACCEPTABLE"`, `"INDETERMINATE"`).
  - `index_type` (`string`): Evaluated index type (`"Ppk"` or `"Cpk"`).
  - `index_value` (`float`): Computed or verified index value.
  - `band` (`string`): Acceptance band classification.
  - `required_action` (`string`): Verbatim AIAG PPAP 4th Edition mandated action.
  - `rationales` (`list[string]`): Engineering justification points.
  - `citations` (`list[string]`): Standards section citations.
  - `stable` (`boolean | None`): Process stability determination.
  - `sample_size` (`integer`): Total number of evaluated readings ($n$).
  - `subgroup_count` (`integer | None`): Subgroup count ($k$).

#### Example Call:
```json
{
  "lsl": 9.5,
  "usl": 10.5,
  "is_ongoing_stable_process": false,
  "customer_concurrence": false
}
```

---

### 5. `render_ppap_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Render responsive, interactive visual HTML checklist matrix canvas displaying the 18 AIAG PPAP elements across Submission Levels 1–5 with active level highlighting, evidence badges, and Section 5 notice.
- **Parameters:**
  - `package` (`dict[str, Any] | None`): PPAP package dictionary. If `None`, renders benchmark Level 3 transmission shaft canvas.
  - `submission_level` (`int | str`, default `3`): Active submission level to highlight (1–5).
  - `title` (`str`, default `"AIAG PPAP 4th Edition 18-Element Checklist Canvas"`): Header title.
  - `theme` (`str`, default `"dark"`): Styling theme (`"dark"` or `"light"`).
  - `standalone` (`bool`, default `true`): If True, returns full standalone HTML document; if False, returns embeddable container.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards basis citation.
  - `title` (`string`): Canvas header title.
  - `rows_count` (`integer`): Total rows displayed (18).
  - `submission_level` (`integer`): Highlighted submission level (1–5).
  - `summary` (`dict[str, int]`): Element count breakdown (`total`, `present`, `missing`, `not_applicable`, `waived`).
  - `html` (`string`): Responsive styled HTML content.

#### Example Call:
```json
{
  "submission_level": 3,
  "theme": "dark",
  "standalone": true
}
```

---

### Worked Examples

#### Worked Example 1: Level 3 Package with Missing Element (`NOT_READY`)

**Scenario:** A supplier is preparing an AIAG Level 3 PPAP submission for an automotive machined transmission shaft. The package contains completed design records, PFMEA, dimensional results, and test reports, but the **Control Plan (§2.2.7)** is missing.

**Tool Invocation:**
```json
{
  "submission_level": 3,
  "reason_for_submission": "INITIAL_SUBMISSION",
  "has_design_responsibility": false,
  "appearance_item": false,
  "has_checking_aid": true,
  "package": {
    "header": {
      "part_number": "TOS-8842-A",
      "part_name": "Transmission Output Shaft",
      "submission_level": 3,
      "reason_for_submission": "INITIAL_SUBMISSION"
    },
    "elements": {
      "2.2.1": {"status": "PRESENT", "file_path": "docs/ballooned_dwg.pdf"},
      "2.2.2": {"status": "PRESENT", "file_path": "docs/eco_1042.pdf"},
      "2.2.3": {"status": "NOT_APPLICABLE"},
      "2.2.4": {"status": "NOT_APPLICABLE", "comments": "No design responsibility"},
      "2.2.5": {"status": "PRESENT", "file_path": "docs/process_flow.pdf"},
      "2.2.6": {"status": "PRESENT", "file_path": "docs/pfmea_rev_b.pdf"},
      "2.2.7": {"status": "MISSING", "comments": "Control plan under final revision"},
      "2.2.8": {"status": "PRESENT", "file_path": "docs/gage_rr.pdf"},
      "2.2.9": {"status": "PRESENT", "file_path": "docs/dimensional_report.pdf"},
      "2.2.10": {"status": "PRESENT", "file_path": "docs/material_cert.pdf"},
      "2.2.11": {"status": "PRESENT", "file_path": "docs/initial_process_study.pdf"},
      "2.2.12": {"status": "PRESENT", "file_path": "docs/iso17025_cert.pdf"},
      "2.2.13": {"status": "NOT_APPLICABLE"},
      "2.2.14": {"status": "PRESENT", "file_path": "samples/parts_lot_01.jpg"},
      "2.2.15": {"status": "PRESENT", "file_path": "samples/master_shaft.jpg"},
      "2.2.16": {"status": "PRESENT", "file_path": "docs/checking_aid_cal.pdf"},
      "2.2.17": {"status": "PRESENT", "file_path": "docs/csr_compliance.pdf"},
      "2.2.18": {"status": "PRESENT", "file_path": "docs/psw_signed.pdf"}
    }
  }
}
```

**Tool Response (`audit_ppap_package`):**
```json
{
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "readiness_verdict": "NOT_READY",
  "submission_level": 3,
  "total_elements": 18,
  "elements_submitted": 13,
  "elements_retained": 1,
  "elements_missing": 1,
  "remediation_items": [
    "Element 2.2.7 (Control Plan) is required for submission ('S') at Level 3 but is currently MISSING."
  ]
}
```

**Engineering Interpretation:**
The readiness verdict is deterministically evaluated as `NOT_READY`. Under AIAG PPAP 4th Edition Table 4.1, Element 2.2.7 is mandatory for submission (`S`) at Level 3. The PPAP package cannot be submitted to the customer until the Control Plan is completed, approved, and integrated into the submission package.

---

#### Worked Example 2 (Negative Control): Level 4 Package with Unspecified Customer Requirements (`INDETERMINATE`)

**Scenario:** A supplier is asked to submit a PPAP under **Submission Level 4**, but the customer has not yet provided the specific submission and retention requirements matrix.

**Tool Invocation:**
```json
{
  "submission_level": 4,
  "reason_for_submission": "TOOLING_CHANGE",
  "customer_level_4_requirements": null
}
```

**Tool Response (`audit_ppap_package`):**
```json
{
  "basis": "AIAG PPAP Reference Manual, 4th Edition (2006)",
  "readiness_verdict": "INDETERMINATE",
  "submission_level": 4,
  "total_elements": 18,
  "rationales": [
    "Submission Level 4 requires customer-defined submission and retention requirements per AIAG PPAP 4th Edition Section 4.",
    "No customer Level 4 requirements dictionary (customer_level_4_requirements) was provided."
  ],
  "remediation_items": [
    "Contact the authorized customer quality representative to obtain the specific Level 4 submission and retention requirements matrix."
  ]
}
```

**Engineering Interpretation:**
The readiness verdict is `INDETERMINATE`. Under AIAG PPAP 4th Edition Section 4, Level 4 submission requirements are strictly customer-defined. It is impossible to audit compliance or determine readiness without explicit customer instructions.

**Correct Agent Behavior:** The agent must **stop and ask the user** to supply the customer-defined Level 4 requirement set. The agent must **never** assume, guess, or hallucinate Level 4 requirements.

---

## Best Practices

1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** AI agents must **never** perform manual capability calculations ($P_{pk}, C_{pk}$), estimate Table 4.1 requirement codes, evaluate PSW field rules, or adjudicate submission readiness in prompt text. Always execute calculations and audits through the deterministic FastMCP tools on `quality-mcp`.
   - *Domain Invariant 1:* All 18 element requirement lookups must route to `lookup_ppap_requirement`.
   - *Domain Invariant 2:* Package completeness auditing must route to `audit_ppap_package`.
   - *Domain Invariant 3:* Part Submission Warrant (PSW) field validation must route to `validate_psw`.
   - *Domain Invariant 4:* Initial Process Studies statistical capability evaluation must route to `assess_ppap_capability`.
   - *Domain Invariant 5:* Visual checklist matrix rendering must route to `render_ppap_canvas`.

2. **🔒 Preserve Customer Authority (Section 5 Invariant):** Part submission status dispositions (`Approved`, `Interim Approval`, `Rejected`) are the exclusive legal authority of the customer's designated quality representative. Field 27 on the PSW must never be populated by the supplier. AI agents evaluate supplier readiness only (`SUBMISSION_READY`, `NOT_READY`, `INDETERMINATE`).

3. **Strict Prohibition of Blanket Statements:** The Part Submission Warrant prohibits blanket statements of conformance (e.g., *"meets all customer specifications"*, *"100% conforming"*). Every specification characteristic must be backed by traceable measurement data, inspection results, or certified test records.

4. **Statistical Rigor in Initial Process Studies (§2.2.11):** Initial process capability ($P_{pk}$) evaluations require variable measurement data from a significant production run (1 to 8 hours, minimum 300 consecutive parts) with at least 100 individual readings across 25 subgroups ($n \ge 100, k \ge 25$). Never evaluate attribute data (pass/fail) using $P_{pk}/C_{pk}$ formulas; attribute data requires 100% inspection or customer-concurred containment plans per §2.2.11.1 Note 2.

5. **Submission Level 4 Indeterminacy Gate:** When evaluating Submission Level 4 packages without customer-defined requirement agreements, always return `INDETERMINATE` and prompt the customer quality engineer for the approved requirement matrix. Never assume default Level 3 requirements for a Level 4 submission.

6. **Cross-Engine Traceability:** Maintain bidirectional traceability across all PPAP elements:
   $$\text{DFMEA (§2.2.4)} \longleftrightarrow \text{PFMEA (§2.2.6)} \longleftrightarrow \text{Control Plan (§2.2.7)} \longleftrightarrow \text{MSA (§2.2.8)} \longleftrightarrow \text{Capability (§2.2.11)} \longleftrightarrow \text{PSW (§2.2.18)}$$

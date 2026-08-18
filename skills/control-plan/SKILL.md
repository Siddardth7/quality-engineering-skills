---
name: control-plan
description: AIAG APQP & Control Plan (2nd Edition) validation, PFMEA bidirectional linkage verification, and SPC chart recommendation routing all schema and linkage checks to validate_control_plan on quality-mcp.
---

# Control Plan: AIAG APQP & Control Plan (2nd Edition) Validation & PFMEA Linkage

## Overview
The `control-plan` skill guides AI agents in authoring, reviewing, validating, and auditing Control Plans according to the **AIAG APQP and Control Plan Reference Manual (2nd Edition)**, the **AIAG-VDA FMEA Handbook (1st Edition, 2019)**, and the **AIAG Statistical Process Control (SPC) Reference Manual (4th Edition, 2005)**.

A Control Plan is a living engineering document that establishes operational controls, inspection methods, sample plans, control limits, and reaction mechanisms across all phases of product manufacturing:
1. **Prototype Control Plan:** Describes dimensional measurements, material verifications, and performance tests conducted during early prototype build cycles.
2. **Pre-Launch Control Plan:** Documents dimensional, material, and functional testing conducted prior to full-rate production, including containment screening, heightened sampling frequencies, and initial process capability evaluations.
3. **Production Control Plan:** Formalizes steady-state process controls, characteristic monitoring methods, sample plans, SPC control charts, and reaction plans for ongoing volume manufacturing.

According to AIAG-VDA FMEA (2019) Section 1.4 and Section 5, every critical process control and Special Characteristic identified in a Process FMEA (PFMEA) must possess verifiable, bidirectional traceability to the corresponding Control Plan. Failure to align PFMEA failure causes with Control Plan inspection methods creates unmitigated risks on the shop floor.

This skill equips agents to:
- Decompose and audit Control Plan documents for AIAG structural and schema completeness.
- Enforce bidirectional traceability between Process FMEA causes and Control Plan characteristic rows via durable join keys (`source_cause_id`).
- Detect orphan characteristics (controls lacking FMEA backing) and uncovered FMEA failure modes (risks missing control rows).
- Verify consistency across numeric tolerance limits ($\text{LSL}, \text{Target}, \text{USL}$), sampling plans, and SPC control methods.
- Delegate all deterministic schema validation, tolerance rule verification, and PFMEA linkage audits to the `validate_control_plan` tool on `quality-mcp`.
- Formulate prioritized engineering remediations for unlinked failure modes, placeholder sample plans, and insufficient reaction plans.

## When to Use
Activate this skill in the following quality engineering scenarios:
- **Pre-Launch & Production Control Plan Audits:** Auditing draft or operational Control Plans for mandatory columns, valid data types, coherent tolerance bounds, and non-blank containment procedures.
- **PPAP Submission Verification (Element 7):** Verifying that Control Plan documentation submitted as part of the AIAG 18-element Production Part Approval Process (PPAP) package satisfies all APQP requirements.
- **PFMEA-to-Control Plan Alignment Reviews:** Auditing bidirectional consistency between the PFMEA and the Control Plan to verify that all High and Medium Action Priority (AP) failure modes have corresponding operational controls.
- **SPC Control Method Qualification:** Recommending and verifying appropriate Statistical Process Control charts (I-MR, Xbar-R, Xbar-S, p, c, u) based on measurement data type (variable vs attribute) and subgroup size ($n$).
- **Engineering Change Management (ECO / MOC):** Evaluating revisions to manufacturing processes, tooling, or inspection equipment to ensure Control Plans are updated without creating orphan controls or uncovered failure modes.

### Input Requirements
To validate a Control Plan, collect the following domain inputs:
- **Control Plan Records (`plan`):** List of dictionary rows containing:
  - `characteristic` (`string`, required): Name of the product or process characteristic (non-blank, unique within dataset).
  - `measurement_method` (`string`, required): Gauge, fixture, instrument, or inspection method (non-blank).
  - `sample_size` (`integer`, required): Subgroup or sample size per inspection check ($n \ge 1$).
  - `frequency` (`string`, required): Inspection cadence, e.g. `"5 parts per hour"`, `"1 per shift"`, `"100% automated"` (non-blank).
  - `reaction_plan` (`string`, required): Explicit containment, quarantine, root cause investigation, and escalation actions (non-blank).
  - `lsl` (`float`, optional): Lower Specification Limit.
  - `usl` (`float`, optional): Upper Specification Limit (must satisfy $\text{USL} > \text{LSL}$ when both provided).
  - `target` (`float`, optional): Nominal design target (must satisfy $\text{LSL} \le \text{Target} \le \text{USL}$ when limits provided).
  - `recommended_chart` (`string`, optional): SPC chart classification (`"I-MR"`, `"Xbar-R"`, `"Xbar-S"`, `"p"`, `"c"`, `"u"`).
  - `source_cause_id` (`string`, optional): Relational join key to the backing PFMEA cause (`"function_id::failure_mode_id::cause_id"`).
  - `sample_plan_is_placeholder` (`boolean`, optional): Flag indicating whether sample size and frequency are default placeholders requiring engineering refinement (defaults to `false`).
- **PFMEA Records (`fmea`, optional):** List of flat FMEA record dictionaries for bidirectional linkage verification, containing `function_id`, `function_component`, `function_requirement`, `failure_mode_id`, `failure_mode_description`, `effect_id`, `effect_description`, `severity`, `cause_id`, `cause_description`, `occurrence`, `control_id`, `control_description`, `control_type`, and `detection`.

### Prerequisites
- Active `quality-mcp` server connection providing the `validate_control_plan` tool.

## Step-by-Step Methodology
Follow the 5-step Control Plan validation and linkage review framework:

```
┌────────────────────────────────────────────────────────────────────────┐
│               5-STEP AIAG CONTROL PLAN REVIEW METHODOLOGY              │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Ingestion & Structure Audit   │ Verify columns, types, tolerances   │
│ 2. PFMEA Linkage Preparation     │ Extract cause IDs & join keys       │
│ 3. Tool Execution                │ Call validate_control_plan on MCP   │
│ 4. Findings & Orphan Triage      │ Audit schema errors, orphans, gaps  │
│ 5. Engineering Remediation       │ Formulate action plan & containment │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Ingestion & Control Plan Structure Inspection
- Parse the list of Control Plan rows and verify that core AIAG columns are populated: `characteristic`, `measurement_method`, `sample_size`, `frequency`, and `reaction_plan`.
- Verify that characteristic names are distinct across the dataset (duplicate characteristics represent redundant or conflicting controls).
- Check numeric tolerance bounds: when both LSL and USL are specified, verify $\text{USL} > \text{LSL}$, and when nominal target is specified, verify $\text{LSL} \le \text{Target} \le \text{USL}$.
- Inspect `sample_plan_is_placeholder` flags to identify auto-generated rows whose sample size ($n=1$) and frequency (`"per shift"`) have not yet been engineered for production.

### 2. Step 2: PFMEA Linkage Preparation & Cause Mapping
- When evaluating a paired PFMEA, extract relational failure chains (Function $\to$ Failure Mode $\to$ Cause $\to$ Effect).
- Ensure durable join keys are structured using the standard delimited format:
  $$\text{source\_cause\_id} = \text{function\_id}::\text{failure\_mode\_id}::\text{cause\_id}$$
- Assemble the dual payload containing the `plan` rows and the flat `fmea` records.

### 3. Step 3: Tool Execution & Deterministic Validation
- Invoke `validate_control_plan` on `quality-mcp`, passing `plan` (and `fmea` when available).
- *Strict Invariant:* Never evaluate schema validity, calculate tolerance spans, or adjudicate PFMEA linkage in prompt text. All validation must execute through `validate_control_plan`.

### 4. Step 4: Findings Analysis & Orphan Characteristic Triage
Examine the returned validation payload from `validate_control_plan`:
- **`schema_valid` & `schema_findings`:** If false, review specific column-level errors (e.g. inverted tolerances $\text{USL} \le \text{LSL}$, target outside bounds, negative sample size, blank mandatory fields).
- **`linkage_valid` & `orphan_characteristics`:** If false or orphans exist:
  - **Orphan Characteristic:** A Control Plan row whose `source_cause_id` is missing or fails to resolve to a known cause in the PFMEA. Orphan controls may indicate unverified inspections, obsolete checks, or undocumented failure mechanisms.
  - **Uncovered Failure Mode:** A PFMEA failure mode that has no corresponding Control Plan row. Represents an unmitigated operational risk that could reach downstream stations or customers.
- **`linked_rows` / `total_rows`:** Evaluate linkage coverage ratio ($100 \times \text{linked\_rows} / \text{total\_rows}$).

### 5. Step 5: Engineering Synthesis & Actionable Remediation
Formulate an engineering disposition based on the validation results:
- **Schema Corrections:** Fix invalid tolerance limits, eliminate duplicate characteristic descriptions, and provide explicit measurement methods.
- **Linkage Remediation:**
  - For each **Orphan Characteristic**, investigate whether it addresses an uncatalogued process failure cause (update PFMEA) or carries a malformed `source_cause_id` (correct join key).
  - For each **Uncovered Failure Mode**, generate a dedicated Control Plan row specifying measurement technique, sample size, frequency, and containment reaction plan—prioritizing High and Medium Action Priority (AP) items.
- **Placeholder Plan Upgrades:** Replace placeholder sample plans (`sample_plan_is_placeholder: true`) with statistically justified sample sizes and frequencies based on process capability ($C_{pk}$), defect detection capability, and production cycle times.
- **Reaction Plan Specificity Audit:** Ensure reaction plans mandate containment, quarantine of nonconforming product, station halt / interlock activation, root cause investigation, and escalation path—rejecting vague phrases such as *"notify supervisor"*.

## Tool Invocations

### `validate_control_plan`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic validation of AIAG Control Plan schema compliance, numeric tolerance limits, and bidirectional PFMEA cause linkage.
- **Parameters:**
  - `plan` (`list[dict[str, Any]]`, required): List of Control Plan row dictionaries.
    - `characteristic` (`string`, required): Name of the characteristic ($1 \le \text{length} \le 200$, non-blank).
    - `measurement_method` (`string`, required): Inspection method or gauge ($1 \le \text{length} \le 200$, non-blank).
    - `sample_size` (`integer`, required): Sample size per inspection check ($n \ge 1$).
    - `frequency` (`string`, required): Inspection cadence ($1 \le \text{length} \le 200$, non-blank).
    - `reaction_plan` (`string`, required): Containment and escalation instruction ($1 \le \text{length} \le 2000$, non-blank).
    - `lsl` (`float | null`, optional): Lower Specification Limit.
    - `usl` (`float | null`, optional): Upper Specification Limit ($\text{USL} > \text{LSL}$).
    - `target` (`float | null`, optional): Nominal design target ($\text{LSL} \le \text{Target} \le \text{USL}$).
    - `recommended_chart` (`string | null`, optional): SPC chart type (`"I-MR"`, `"Xbar-R"`, `"Xbar-S"`, `"p"`, `"c"`, `"u"`).
    - `source_cause_id` (`string | null`, optional): PFMEA join key (`"function_id::failure_mode_id::cause_id"`).
    - `sample_plan_is_placeholder` (`boolean`, optional): True if sample plan contains placeholder values (defaults to `false`).
  - `fmea` (`list[dict[str, Any]] | null`, optional): List of flat FMEA record dictionaries for bidirectional linkage verification.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards attribution string (`"AIAG Control Plan"`).
  - `valid` (`boolean`): Overall validity (`true` if `schema_valid` is true and `linkage_valid` is not false).
  - `total_rows` (`integer`): Total number of rows in the Control Plan.
  - `schema_valid` (`boolean`): Indicates whether all row and dataset schema rules passed.
  - `schema_findings` (`list[string]`): Detailed error messages for any schema violations.
  - `linkage_checked` (`boolean`): Indicates whether PFMEA linkage verification was executed.
  - `linkage_valid` (`boolean | null`): Indicates whether all rows have valid linkage (`null` if `fmea` omitted).
  - `linked_rows` (`integer | null`): Count of successfully linked Control Plan rows (`null` if `fmea` omitted).
  - `orphan_characteristics` (`list[string]`): Names of characteristics lacking valid FMEA cause linkage.
  - `uncovered_failure_modes` (`list[string]`): FMEA failure mode identifiers lacking Control Plan coverage.
  - `linkage_findings` (`list[string]`): Detailed diagnostic messages for orphan or uncovered items.

---

### Example 1: Schema-Only Validation

#### Invocation
```json
{
  "name": "validate_control_plan",
  "arguments": {
    "plan": [
      {
        "characteristic": "Shaft Outer Diameter",
        "lsl": 24.95,
        "usl": 25.05,
        "target": 25.0,
        "measurement_method": "Digital Micrometer (0.001 mm)",
        "sample_size": 5,
        "frequency": "5 parts per hour",
        "recommended_chart": "Xbar-R",
        "reaction_plan": "Quarantine last hour of production, adjust CNC offset, re-inspect 100% of quarantined lot.",
        "source_cause_id": null,
        "sample_plan_is_placeholder": false
      }
    ]
  }
}
```

#### Successful Response
```json
{
  "basis": "AIAG Control Plan",
  "valid": true,
  "total_rows": 1,
  "schema_valid": true,
  "schema_findings": [],
  "linkage_checked": false,
  "linkage_valid": null,
  "linked_rows": null,
  "orphan_characteristics": [],
  "uncovered_failure_modes": [],
  "linkage_findings": []
}
```

---

### Example 2: Bidirectional PFMEA Linkage Validation

#### Invocation
```json
{
  "name": "validate_control_plan",
  "arguments": {
    "plan": [
      {
        "characteristic": "CNC Turning — Tool Insert Wear",
        "lsl": 24.95,
        "usl": 25.05,
        "target": 25.0,
        "measurement_method": "Air Gaging Station",
        "sample_size": 5,
        "frequency": "Every 30 minutes",
        "recommended_chart": "Xbar-R",
        "reaction_plan": "Halt station, index tool insert, quarantine lot back to last good check.",
        "source_cause_id": "FN-01::FM-01::C-01",
        "sample_plan_is_placeholder": false
      }
    ],
    "fmea": [
      {
        "function_id": "FN-01",
        "function_component": "CNC Turning Station",
        "function_requirement": "Maintain shaft diameter 25.0 +/- 0.05 mm",
        "failure_mode_id": "FM-01",
        "failure_mode_description": "Shaft Outer Diameter Oversize",
        "effect_id": "EF-01",
        "effect_description": "Bearing assembly interference at customer line",
        "severity": 8,
        "cause_id": "C-01",
        "cause_description": "Tool insert flank wear exceeds threshold",
        "occurrence": 4,
        "control_id": "DC-01",
        "control_description": "Periodic air gaging of turned shaft",
        "control_type": "detection",
        "detection": 3
      }
    ]
  }
}
```

#### Successful Response
```json
{
  "basis": "AIAG Control Plan",
  "valid": true,
  "total_rows": 1,
  "schema_valid": true,
  "schema_findings": [],
  "linkage_checked": true,
  "linkage_valid": true,
  "linked_rows": 1,
  "orphan_characteristics": [],
  "uncovered_failure_modes": [],
  "linkage_findings": []
}
```

---

### Protocol Error Handling
- **Invalid Payload Type:** If `plan` is not a list or `fmea` is neither a list nor null, the tool raises a `TypeError`.
- **Empty Dataset:** If `plan` contains zero rows, `schema_valid` is set to `false` with finding `"Control Plan dataset must contain at least one characteristic row."`.
- **Validation Violations:** If required fields are missing, empty, or bounds are inverted ($\text{USL} \le \text{LSL}$), `schema_valid` is set to `false` and detailed error paths are enumerated in `schema_findings`.
- When encountering schema or linkage errors, the agent must present the exact diagnostic findings to the user and outline concrete remediation steps rather than attempting to bypass tool results.

## Best Practices
1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** Never compute tolerance spans, evaluate whether nominal targets lie within limits, or verify PFMEA join keys using prompt-based heuristics. Always delegate verification to `validate_control_plan` on `quality-mcp`.
2. **Enforce Bidirectional PFMEA Traceability:** Ensure every Special Characteristic and critical process control in the Control Plan links to a verified PFMEA cause via `source_cause_id`. Unlinked characteristics represent unmitigated failure risks.
3. **Actionable & Specific Reaction Plans:** Require explicit containment instructions (e.g. *"quarantine suspect material from last good check, tag nonconforming bins, adjust tool offset, notify quality engineer"*). Reject vague reaction plans such as *"inform supervisor"* or *"recheck part"*.
4. **Tolerance Coherence Verification:** Always verify that specification limits are mathematically coherent ($\text{USL} > \text{LSL}$ and $\text{LSL} \le \text{Target} \le \text{USL}$). Attribute or one-sided limits should omit the irrelevant limit rather than inserting dummy zeros.
5. **AIAG SPC Decision Tree Adherence:** Align recommended SPC charts with data characteristics per the AIAG SPC Reference Manual (4th Edition):
   - **Variable Data ($n=1$):** Individuals and Moving Range (`I-MR`).
   - **Variable Data ($2 \le n \le 9$):** Average and Range (`Xbar-R`).
   - **Variable Data ($10 \le n \le 12$):** Average and Standard Deviation (`Xbar-S`).
   - **Attribute Data (Defective Units):** Proportion Nonconforming (`p` chart).
   - **Attribute Data (Defect Counts):** Constant sample size $\to$ `c` chart; variable sample size $\to$ `u` chart.
6. **Placeholder Plan Remediation:** Proactively identify auto-generated rows where `sample_plan_is_placeholder: true` and guide the user to replace placeholder sampling frequencies (`"per shift"`) and sample sizes ($n=1$) with capability-justified production parameters.

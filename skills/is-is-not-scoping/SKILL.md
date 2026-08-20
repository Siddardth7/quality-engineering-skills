---
name: is-is-not-scoping
description: Deterministic Kepner-Tregoe Is/Is-Not problem boundary scoping, distinction and change identification, candidate cause hypothesis synthesis, and visual canvas rendering routing all analysis to scope_is_is_not and render_isisnot_canvas on quality-mcp.
---

# Kepner-Tregoe Is/Is-Not Problem Boundary Scoping & Hypothesis Synthesis

## Overview
The `is-is-not-scoping` skill guides AI agents in structuring, executing, and auditing Kepner-Tregoe (KT) Is/Is-Not Problem Analysis comparative matrices in accordance with **Charles H. Kepner & Benjamin B. Tregoe's The New Rational Manager (Updated Edition, 1997)**, the **AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018)**, and **Ford Motor Company's Global 8D (G8D) Problem Solving Manual (Section D2)**.

Kepner-Tregoe Problem Analysis is a systematic, contrast-based methodology that isolates the root cause of an unexplained process or product deviation by precisely defining problem boundaries. Rather than speculating on theoretical causes, KT Problem Analysis contrasts observed facts (**IS**) against closely related, plausible facts that were *not* observed (**IS NOT**) across four fundamental dimensions:
1. **WHAT (Identity):** The specific deviation, defect symptom, or failure mode being explained vs. what could be occurring but is not.
2. **WHERE (Location):** The physical location on the object and geographical/workstation location of the deviation vs. where it could be observed but is not.
3. **WHEN (Timing):** When the deviation was first observed, lifecycle timing, and chronological pattern vs. when it could have occurred but did not.
4. **EXTENT (Magnitude):** The quantity of defective units, severity/size of deviation, and trend vs. how many or how severe it could be but is not.

Key standards-based foundations include:
- **Comparative Bounding & Contrast Analysis (RULE 2):** Kepner & Tregoe (1997) Chapter 2 emphasizes that finding the distinction between IS and IS NOT isolates the peculiar factors that separate the problem from normal operations.
- **Distinctions & Changes Identification (RULE 2):** For each dimension, the analyst questions: *"What is distinctive about the IS data when compared with the IS NOT data?"* followed by *"What changed in, on, around, or about this distinction?"* (KT Chapter 2, lines 1361–1398).
- **Candidate Root-Cause Hypothesis Synthesis:** Per KT Chapter 3 (lines 1433–1446), candidate causes are synthesized by pairing distinctions with changes (*"How could this distinction or change have produced the deviation described in the problem statement?"*).
- **Hypothesis Testing Against All Dimensions:** A true root cause must explain every factual condition in the matrix (all IS and IS NOT observations) without unexplained assumptions.

This skill equips agents to:
- Structure factual Is/Is-Not contrast matrices across WHAT, WHERE, WHEN, and EXTENT.
- Detect missing distinctions, unexamined changes, and un-scoped problem dimensions.
- Synthesize structured candidate cause hypotheses from paired distinctions and changes.
- Delegate all deterministic validation, hypothesis synthesis, and visual canvas rendering to `scope_is_is_not` and `render_isisnot_canvas` on `quality-mcp`.

## When to Use
Activate this skill in the following quality engineering and root cause analysis scenarios:
- **8D Problem Solving (Discipline D2 - Problem Definition & D4 - Cause Isolation):** Bounding problem scope before root cause brainstorming or drilling down with 5-Why.
- **Kepner-Tregoe Problem Analysis Investigations:** Clarifying complex deviations where multiple plausible theories exist, contrasting affected vs. unaffected product lines or production shifts.
- **AIAG CQI-20 Comparative Problem Bounding:** Structuring comparative data tables per CQI-20 Section 4 & Figure 24.
- **Quality Escape & Containment Boundary Definition:** Determining exact containment boundaries (which lots, machines, serial ranges are affected vs. unaffected).
- **Scoping Matrix Review & Audit:** Auditing submitted Is/Is-Not matrices for missing distinctions, empty changes, or incomplete dimensional coverage.

### Input Requirements
To scope and validate an Is/Is-Not matrix, collect the following domain inputs:
- **Problem Statement (`problem_statement`):** Clear, objective statement of the observed deviation or defect (e.g. *"Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)"*).
- **Matrix Rows (`matrix`):** List of row dictionaries containing:
  - `dimension` (`string`, required): Canonical KT dimension (`WHAT`, `WHERE`, `WHEN`, `EXTENT`).
  - `is_data` (`string`, required): Specific observed factual evidence of the problem.
  - `is_not_data` (`string`, required): Closely related, plausible conditions where the problem could occur but does not.
  - `distinctions` (`string | null`, optional): What stands out or is distinctive about the IS data compared to the IS NOT data.
  - `changes` (`string | null`, optional): What changed in, on, around, or about the identified distinction.
- **Canvas Rendering Parameters:** `title` (`string`), `theme` (`"dark"` or `"light"`), `standalone` (`boolean`).

### Prerequisites
- Active `quality-mcp` server connection providing `scope_is_is_not` and `render_isisnot_canvas` tools.

## Step-by-Step Methodology
Follow the 5-step Kepner-Tregoe Is/Is-Not investigation and verification methodology:

```
┌────────────────────────────────────────────────────────────────────────┐
│             5-STEP KEPNER-TREGOE IS/IS-NOT METHODOLOGY                 │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Problem Statement Definition  │ Anchor specific observed deviation  │
│ 2. 4-Dimension Comparative Matrix│ Gather IS vs IS NOT facts           │
│ 3. Distinctions & Changes Inquiry│ Identify distinctions & changes     │
│ 4. Deterministic MCP Tool Call   │ Execute scope_is_is_not on MCP      │
│ 5. Hypothesis Synthesis & Canvas │ Synthesize causes & render canvas   │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Problem Statement Definition
- Formulate a precise, factual problem statement describing what is deviating from standard performance.
- Ensure the statement describes the observed effect without embedding unverified causal theories.

### 2. Step 2: 4-Dimension Comparative Matrix Formulation
Populate factual observations across the four canonical KT dimensions:
- **WHAT:** What specific object/part is defective, and what defect is observed? What similar objects or defects could be observed but are not?
- **WHERE:** Where is the defect located on the object, and where geographically/workstation-wise is it observed? Where else could it be but is not?
- **WHEN:** When was the defect first observed, at what lifecycle/process step, and what is the chronological pattern? When could it have been observed but was not?
- **EXTENT:** How many units are defective, what is the defect magnitude, and what is the trend? How many units could be affected but are not?

### 3. Step 3: Distinctions & Changes Inquiry
For each of the four dimensions:
- **Distinctions:** Ask *"What is distinctive about the IS data when compared with the IS NOT data?"* (e.g. difference in raw material supplier, blank length, clamping depth, shift timing).
- **Changes:** Ask *"What changed in, on, around, or about this distinction?"* (e.g. tooling adjustment, process parameter modification, new operator handover).

### 4. Step 4: Deterministic MCP Tool Execution & Boundary Audit
- Package the matrix rows and invoke `scope_is_is_not` on `quality-mcp`.
- *Strict Invariant:* Never evaluate dimensional completeness, check missing distinctions, or synthesize root-cause hypotheses using prompt-based guessing. All validation must execute deterministically through `scope_is_is_not`.
- Review the returned `IsIsNotScopingResult`:
  - Verify `complete_dimensions` contains all four dimensions (`WHAT`, `WHERE`, `WHEN`, `EXTENT`).
  - Examine `warnings` for missing distinctions or changes.
  - Review `candidate_causes` for synthesized hypotheses.

### 5. Step 5: Visual Canvas Generation & Cause Testing Hand-Off
- Invoke `render_isisnot_canvas` on `quality-mcp` to generate an interactive, themed visual HTML canvas with summary KPI cards and 4-dimension comparative matrix cards.
- Test each synthesized candidate cause hypothesis against all IS and IS NOT facts: the true cause must explain every fact without contradiction.
- Transition verified candidate causes into `validate_5why` (`5why-root-cause`) for deep systemic drill-down.

## Tool Invocations

### `scope_is_is_not`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic validation of KT matrix completeness across WHAT, WHERE, WHEN, EXTENT, detection of missing distinctions and changes, and synthesis of candidate root-cause hypotheses per Kepner & Tregoe (1997).
- **Parameters:**
  - `matrix` (`list[dict[str, Any]] | null`, optional): List of row dictionaries (`dimension`, `is_data`, `is_not_data`, optional `distinctions`, `changes`). If omitted or None, loads reference Sentinel-8D benchmark dataset.
  - `problem_statement` (`string`, default `"Problem Statement"`): Problem statement describing the observed deviation or defect.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards attribution string (`"Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D"`).
  - `valid` (`boolean`): Validity status (`true` if matrix contains valid rows).
  - `verdict` (`string`): Evaluation verdict (`"ACCEPT"`, `"WARNING"`, `"REJECT"`).
  - `problem_statement` (`string`): Problem statement evaluated.
  - `total_rows` (`integer`): Number of evaluated rows.
  - `dimension_coverage` (`dict[str, bool]`): Boolean mapping for `WHAT`, `WHERE`, `WHEN`, `EXTENT`.
  - `complete_dimensions` (`list[str]`): List of populated dimensions.
  - `missing_dimensions` (`list[str]`): List of unpopulated dimensions.
  - `candidate_causes` (`list[dict[str, Any]]`): List of synthesized candidate causes (`dimension`, `distinction`, `change`, `hypothesis`, `is_paired`).
  - `warnings` (`list[str]`): Actionable warnings regarding un-scoped dimensions or missing distinctions/changes.
  - `recommendations` (`list[str]`): Structured engineering guidance.

---

### `render_isisnot_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Render an interactive visual HTML canvas for a Kepner-Tregoe Is/Is-Not matrix displaying summary KPI cards, 4-dimension comparative matrix cards, and candidate cause hypothesis chips.
- **Parameters:**
  - `matrix` (`list[dict[str, Any]] | null`, optional): List of Is/Is-Not row dictionaries. If omitted or None, loads reference Sentinel-8D benchmark dataset.
  - `problem_statement` (`string`, default `"Problem Statement"`): Problem statement describing the observed deviation.
  - `title` (`string`, default `"Kepner-Tregoe Is/Is-Not Scoping Canvas"`): Header title for canvas.
  - `theme` (`string`, default `"dark"`): Palette theme: `"dark"` or `"light"`.
  - `standalone` (`boolean`, default `true`): Full standalone HTML5 document (`true`) or embeddable container (`false`).
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `title` (`string`): Canvas title.
  - `rows_count` (`integer`): Total rendered rows count.
  - `dimensions_count` (`integer`): Total rendered dimensions count.
  - `verdict` (`string`): Validation verdict (`"ACCEPT"`, `"WARNING"`, `"REJECT"`).
  - `valid` (`boolean`): Overall validity boolean.
  - `summary` (`dict[str, Any]`): Summary metrics breakdown including `complete_dimensions`, `missing_dimensions`, and `candidate_causes_count`.
  - `html` (`string`): Rendered HTML markup.

---

### Example 1: Positive Control (Fully Scoped Sentinel-8D Dataset)

#### Invocation
```json
{
  "name": "scope_is_is_not",
  "arguments": {
    "problem_statement": "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
    "matrix": [
      {
        "dimension": "WHAT",
        "is_data": "Pneumatic cylinder stroke binding and seal leakage requiring manual teardown rework",
        "is_not_data": "Piston rod surface defect or electrical control circuit failure",
        "distinctions": "Cylinder bottom mounting face non-parallelism and seal groove distortion",
        "changes": "Bar stock feed misalignment resulting in undersized cut blank length"
      },
      {
        "dimension": "WHERE",
        "is_data": "Cylinder bottom workpiece at CNC milling station (DMC 50H) hydraulic fixture",
        "is_not_data": "Piston rod CNC lathe turning station (Index G200)",
        "distinctions": "Hydraulic vice clamping standard depth requires minimum blank mass",
        "changes": "Sawing station backstop guide position adjusted without laser verification"
      },
      {
        "dimension": "WHEN",
        "is_data": "During post-assembly pneumatic pressure decay acceptance testing (trial run 802 units)",
        "is_not_data": "During initial raw bar stock receiving inspection or pre-machining staging",
        "distinctions": "Defect manifests only under pressurized stroke test after cylinder tie-rod torquing",
        "changes": "Production shift handover between saw operator and CNC milling operator"
      },
      {
        "dimension": "EXTENT",
        "is_data": "52 out of 802 units (6.48% baseline defect rate), concentrated in blanks with saw_weight < 0.540 kg (15.6% failure rate)",
        "is_not_data": "All 802 units defective (750 units passed acceptance) or uniform across all blank weights",
        "distinctions": "Failure rate increases 1.99x for each 1-sigma decrease in saw cut blank weight",
        "changes": "Sawing cut blank weight variation increased prior to milling operation"
      }
    ]
  }
}
```

#### Response
```json
{
  "basis": "Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D",
  "valid": true,
  "verdict": "ACCEPT",
  "problem_statement": "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
  "total_rows": 4,
  "dimension_coverage": {
    "WHAT": true,
    "WHERE": true,
    "WHEN": true,
    "EXTENT": true
  },
  "complete_dimensions": ["WHAT", "WHERE", "WHEN", "EXTENT"],
  "missing_dimensions": [],
  "candidate_causes": [
    {
      "dimension": "WHAT",
      "distinction": "Cylinder bottom mounting face non-parallelism and seal groove distortion",
      "change": "Bar stock feed misalignment resulting in undersized cut blank length",
      "hypothesis": "Distinction in WHAT ('Cylinder bottom mounting face non-parallelism and seal groove distortion') combined with change ('Bar stock feed misalignment resulting in undersized cut blank length') may explain why 'Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)' occurred.",
      "is_paired": true
    },
    {
      "dimension": "WHERE",
      "distinction": "Hydraulic vice clamping standard depth requires minimum blank mass",
      "change": "Sawing station backstop guide position adjusted without laser verification",
      "hypothesis": "Distinction in WHERE ('Hydraulic vice clamping standard depth requires minimum blank mass') combined with change ('Sawing station backstop guide position adjusted without laser verification') may explain why 'Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)' occurred.",
      "is_paired": true
    },
    {
      "dimension": "WHEN",
      "distinction": "Defect manifests only under pressurized stroke test after cylinder tie-rod torquing",
      "change": "Production shift handover between saw operator and CNC milling operator",
      "hypothesis": "Distinction in WHEN ('Defect manifests only under pressurized stroke test after cylinder tie-rod torquing') combined with change ('Production shift handover between saw operator and CNC milling operator') may explain why 'Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)' occurred.",
      "is_paired": true
    },
    {
      "dimension": "EXTENT",
      "distinction": "Failure rate increases 1.99x for each 1-sigma decrease in saw cut blank weight",
      "change": "Sawing cut blank weight variation increased prior to milling operation",
      "hypothesis": "Distinction in EXTENT ('Failure rate increases 1.99x for each 1-sigma decrease in saw cut blank weight') combined with change ('Sawing cut blank weight variation increased prior to milling operation') may explain why 'Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)' occurred.",
      "is_paired": true
    }
  ],
  "warnings": [],
  "recommendations": [
    "Problem boundary is fully scoped across all 4 KT dimensions with paired distinctions and changes. Proceed to test candidate cause hypotheses against all IS and IS NOT facts."
  ]
}
```

---

### Example 2: Negative Control (Missing Dimensions & Missing Distinctions)

#### Invocation
```json
{
  "name": "scope_is_is_not",
  "arguments": {
    "problem_statement": "Hydraulic cylinder seal leakage",
    "matrix": [
      {
        "dimension": "WHAT",
        "is_data": "Rod seal leakage on cylinder head",
        "is_not_data": "Piston seal leakage",
        "distinctions": null,
        "changes": null
      }
    ]
  }
}
```

#### Response
```json
{
  "basis": "Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D",
  "valid": true,
  "verdict": "WARNING",
  "problem_statement": "Hydraulic cylinder seal leakage",
  "total_rows": 1,
  "dimension_coverage": {
    "WHAT": true,
    "WHERE": false,
    "WHEN": false,
    "EXTENT": false
  },
  "complete_dimensions": ["WHAT"],
  "missing_dimensions": ["WHERE", "WHEN", "EXTENT"],
  "candidate_causes": [],
  "warnings": [
    "Dimension 'WHAT' has IS and IS NOT data but is missing both distinctions and changes.",
    "Incomplete KT problem scope: missing dimensions WHERE, WHEN, EXTENT. Complete all 4 dimensions (WHAT, WHERE, WHEN, EXTENT) to fully isolate the problem boundary."
  ],
  "recommendations": [
    "Identify what is distinctive about the IS data compared to the IS NOT data for 'WHAT', and what changed in or around that distinction per KT Chapter 2.",
    "Scope the unexamined dimensions (WHERE, WHEN, EXTENT) using comparative IS vs IS NOT questioning per Kepner & Tregoe (1997)."
  ]
}
```

## Best Practices
1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** Never evaluate dimensional completeness, check missing distinctions, or synthesize root-cause hypotheses using prompt-based guessing. Always delegate matrix evaluation and hypothesis generation to `scope_is_is_not` on `quality-mcp`.
2. **Enforce All 4 Dimensions (WHAT, WHERE, WHEN, EXTENT):** A problem is not properly scoped until all four Kepner-Tregoe dimensions are explored. Leaving dimensions unexamined risks overlooking critical environmental, location, or timing factors.
3. **Seek Plausible Contrast in IS NOT Data (KT Chapter 2 RULE 2):** Ensure IS NOT entries are closely related and could reasonably have occurred (e.g. adjacent machine lines, other product models produced in the same facility, alternative shifts) rather than irrelevant extremes.
4. **Identify Distinctions Before Changes (KT Chapter 2):** Always isolate what is distinctive about the IS data relative to the IS NOT data before looking for changes. Changes are only relevant if they occurred in, on, around, or about the identified distinction.
5. **Test Hypotheses Against All Matrix Facts (KT Chapter 3):** After synthesizing candidate causes, verify each hypothesis against every IS and IS NOT entry. If a candidate cause cannot explain why the problem occurred on Line A but did *not* occur on Line B, the cause must be refined or rejected.
6. **Transition from Scoping to 5-Why Drill-Down:** Use the Is/Is-Not scoping matrix to isolate the verified physical mechanism and boundary conditions, then transition into `validate_5why` (`5why-root-cause`) to discover the systemic root cause of the root cause.

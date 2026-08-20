---
name: fishbone-analysis
description: Deterministic 6M Fishbone (Ishikawa) cause-and-effect diagram categorization, empty branch detection, and visual canvas rendering routing all analysis to categorize_fishbone and render_fishbone_canvas on quality-mcp.
---

# 6M Fishbone Cause-and-Effect Analysis: Dispersion Structuring & Gap Detection

## Overview
The `fishbone-analysis` skill guides AI agents in conducting, structuring, categorizing, and auditing 6M Fishbone (Cause-and-Effect / Ishikawa) analyses according to **Kaoru Ishikawa's Guide to Quality Control (2nd Revised Edition, 1986)**, the **AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018)**, and **Nancy R. Tague's The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005)**.

The 6M Fishbone diagram is a structured graphical brainstorming and dispersion analysis technique used to discover, group, and examine all potential failure causes contributing to a specific quality defect, process variation, or manufacturing escape. Rather than jumping directly to isolated assumptions or focusing exclusively on human error, the 6M framework organizes causal hypotheses into six canonical branches:
1. **Man (People / Manpower):** Operator techniques, shift handovers, training competency, ergonomics, and fatigue.
2. **Machine (Equipment / Tooling):** Machine alignment, CNC spindle runout, fixture wear, pneumatic pressure, calibration, and maintenance.
3. **Method (Process / Procedure):** Standard work instructions, torque sequences, parameter settings, operating speeds, and changeover protocols.
4. **Material (Raw Material / Parts / Consumables):** Supplier batches, durometer hardness, alloy composition, surface roughness, and shelf life.
5. **Measurement (Inspection / Gaging / Metrology):** Gage calibration drift, fixture deflection, measurement resolution, operator inspection bias, and Gage R&R repeatability.
6. **Environment (Milieu / Ambient Conditions):** Cleanroom temperature fluctuations, humidity, airborne particulate contamination, lighting, and vibration.

Key standards-based foundations include:
- **Canonical 6M Taxonomy & Alias Resolution (RULE 1):** Normalizes industry variants (e.g., *"manpower"* $\to$ `Man`, *"equipment"* $\to$ `Machine`, *"mother nature"* $\to$ `Environment`, *"inspection"* $\to$ `Measurement`) into a deterministic schema per Ishikawa (1986) Chapter 3 and AIAG CQI-20 Figure 34.
- **Empty Branch & Bare Leg Exploration (RULE 1 / RULE 5):** AIAG CQI-20 Section G1 ("Pay attention to legs that are bare") and Ishikawa (1986) Chapter 3 emphasize that brainstorming is incomplete if major branches remain unexamined. Bare branches represent potential blind spots in the investigation.
- **Multi-Category Cause Placement (RULE 5):** Per ASQ Quality Toolbox (p. 248) and AIAG CQI-20 Section G1, causes that span multiple categories can be placed in each relevant branch without getting bogged down in taxonomy debates.
- **Branch Concentration Balance Heuristic:** Detects when brainstorming tilts excessively ($\ge 75\%$) toward a single branch (such as `Man`), mitigating operator-blame tunnel vision and encouraging cross-functional inquiry.

This skill equips agents to:
- Guide multi-disciplinary teams in decomposing complex quality defects across all 6M categories.
- Validate cause datasets for proper category normalization, duplicate entries, and branch balance.
- Identify unexamined bare branches and prompt targeted brainstorming questions.
- Delegate all deterministic categorization, balance auditing, and canvas rendering to `categorize_fishbone` and `render_fishbone_canvas` on `quality-mcp`.

## When to Use
Activate this skill in the following quality engineering and root cause analysis scenarios:
- **8D Problem Solving (Discipline D4 - Cause Brainstorming):** Mapping potential failure causes across all manufacturing factors before drilling down into 5-Why root causes.
- **CAPA & Nonconformance Investigation (ISO 9001 §10.2 / IATF 16949 §10.2.3):** Brainstorming dispersion factors for internal scrap spikes, customer returns, or audit findings.
- **PFMEA & Control Plan Risk Discovery:** Identifying unaddressed process failure mechanisms during FMEA reviews or Control Plan updates.
- **Quality Escape & Containment Analysis:** Examining both occurrence and escape mechanisms across the 6M taxonomy per AIAG CQI-20.
- **Fishbone Diagram Review & Audit:** Evaluating submitted Ishikawa diagrams for empty branches, operator-bias concentration, or duplicate cause statements.

### Input Requirements
To categorize and validate a 6M Fishbone diagram, collect the following domain inputs:
- **Problem Effect Statement (`effect` / `effect_statement`):** Precise description of the observed defect, symptom, or failure mode (e.g. *"Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)"*).
- **Cause Records (`causes`):** List of cause dictionaries containing:
  - `category` (`string`, required): Canonical 6M category (`Man`, `Machine`, `Method`, `Material`, `Measurement`, `Environment`) or recognized industry alias (e.g. `equipment`, `personnel`, `inspection`).
  - `cause` (`string`, required): Clear, non-blank description of the potential cause or failure mechanism.
  - `sub_category` (`string`, optional): Specific sub-system or factor tag (e.g. `Tooling`, `Training`, `Calibration`).
- **Balance Threshold (`balance_threshold`, optional):** Fraction threshold (default `0.75` / 75%) above which single-branch concentration triggers an imbalance warning when $N \ge 3$.

### Prerequisites
- Active `quality-mcp` server connection providing `categorize_fishbone` and `render_fishbone_canvas` tools.

## Step-by-Step Methodology
Follow the 5-step 6M Fishbone investigation and verification methodology:

```
┌────────────────────────────────────────────────────────────────────────┐
│               5-STEP 6M FISHBONE RCA METHODOLOGY                       │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Problem Effect Definition     │ Anchor clear, factual effect box    │
│ 2. 6M Cross-Functional Ideation  │ Brainstorm causes across all 6M legs│
│ 3. Deterministic MCP Tool Call   │ Execute categorize_fishbone on MCP  │
│ 4. Empty Branch & Bias Audit     │ Address bare legs & operator bias   │
│ 5. Visual Canvas & 5-Why Hand-Off│ Render diagram & select top causes  │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Problem Effect Definition
- Formulate a specific, measurable problem statement describing what went wrong and where (e.g., from Kepner-Tregoe Is/Is-Not matrix or defect logging).
- Place this statement into the Fishbone "head" (Effect Box). Ensure it describes the observed deviation rather than speculative causes.

### 2. Step 2: 6M Cross-Functional Brainstorming & Data Collection
- Engage cross-functional team members (operators, manufacturing engineers, quality inspectors, maintenance technicians).
- Systematically explore all 6M categories using targeted inquiry:
  - *Man:* Did shift changeovers, operator fatigue, or training gaps contribute?
  - *Machine:* Did fixture misalignment, CNC spindle runout, or air pressure drop occur?
  - *Method:* Were work instructions ambiguous, torque sequences skipped, or feeds/speeds changed?
  - *Material:* Was there raw material hardness variation, supplier batch inconsistency, or surface roughness out of spec?
  - *Measurement:* Was the test gage out of calibration, fixture flexing, or visual inspection criteria subjective?
  - *Environment:* Did cleanroom temperature swings, humidity changes, or airborne particulates affect the process?

### 3. Step 3: Tool Execution & Deterministic Validation
- Package the brainstormed causes into the `causes` list and invoke `categorize_fishbone` on `quality-mcp`.
- *Strict Invariant:* Never compute branch counts, balance ratios, or adjudicate 6M aliases in prompt context. All categorization must execute through `categorize_fishbone`.

### 4. Step 4: Empty Branch & Bias Audit
Examine the returned validation payload from `categorize_fishbone`:
- **`empty_branches`:** If any branches have 0 causes listed, convene the team to examine the bare legs per AIAG CQI-20 Section G1 ("Pay attention to legs that are bare").
- **`branch_counts` & Imbalance Warning:** If a single branch accounts for $\ge 75\%$ of causes ($N \ge 3$), investigate whether the team has succumbed to operator-blame tunnel vision.
- **`duplicate_causes`:** Review causes appearing in multiple branches to determine if they represent multi-category interactions (permitted per ASQ Quality Toolbox p. 248) or redundant entries.
- **`uncategorized_causes`:** Reassign unmapped categories to the canonical 6M taxonomy.

### 5. Step 5: Visual Canvas Generation & 5-Why Transition
- Invoke `render_fishbone_canvas` on `quality-mcp` to generate an interactive, themed visual HTML/SVG Ishikawa diagram with summary KPI cards and branch breakdown grids.
- Select the highest-priority, evidence-supported causes from the fishbone diagram and transition them into `validate_5why` for deep root cause drill-down.

## Tool Invocations

### `categorize_fishbone`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic categorization, category alias normalization, empty branch detection, duplicate identification, and branch balance analysis for 6M Fishbone diagrams.
- **Parameters:**
  - `causes` (`list[dict[str, Any]] | null`, optional): List of cause dictionaries (`category`, `cause`, optional `sub_category`). If omitted or None, loads standard reference Sentinel-8D benchmark dataset.
  - `effect` (`string`, default `"Problem Effect"`): Problem effect statement describing the failure mode.
  - `effect_statement` (`string | null`, optional): Optional alias for effect statement.
  - `check_balance` (`boolean`, default `true`): Whether to check for branch concentration / imbalance.
  - `balance_threshold` (`float`, default `0.75`): Fractional threshold for single-branch concentration warning.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards attribution string (`"Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"`).
  - `valid` (`boolean`): Validity status (`true` if dataset contains causes).
  - `verdict` (`string`): Evaluation verdict (`"ACCEPT"`, `"WARNING"`, `"REJECT"`).
  - `effect_statement` (`string`): Problem effect statement evaluated.
  - `total_causes` (`integer`): Total number of causes analyzed.
  - `branch_counts` (`dict[str, int]`): Count of causes across all 6 canonical branches (`Man`, `Machine`, `Method`, `Material`, `Measurement`, `Environment`).
  - `grouped_causes` (`dict[str, list[dict]]`): Causes grouped by canonical 6M category.
  - `empty_branches` (`list[str]`): List of branches with 0 causes.
  - `duplicate_causes` (`list[dict]`): List of duplicate cause records.
  - `uncategorized_causes` (`list[dict]`): List of causes with unrecognized category strings.
  - `warnings` (`list[str]`): Actionable warnings regarding empty branches, duplicates, or imbalance.
  - `recommendations` (`list[str]`): Structured engineering guidance.

---

### `render_fishbone_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Render an interactive visual HTML/SVG canvas displaying the horizontal central spine, 6 diagonal ribs, cause callouts, summary KPI cards, and findings container.
- **Parameters:**
  - `causes` (`list[dict[str, Any]] | null`, optional): List of cause dictionaries. If omitted or None, loads standard reference Sentinel-8D benchmark dataset.
  - `effect` (`string`, default `"Problem Effect"`): Problem effect statement.
  - `effect_statement` (`string | null`, optional): Optional alias for effect statement.
  - `title` (`string`, default `"6M Fishbone Cause-and-Effect Canvas"`): Header title for canvas.
  - `theme` (`string`, default `"dark"`): Palette theme: `"dark"` or `"light"`.
  - `standalone` (`boolean`, default `true`): Full HTML5 document (`true`) or embeddable `<div>` (`false`).
  - `balance_threshold` (`float`, default `0.75`): Branch balance threshold.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `title` (`string`): Canvas title.
  - `rows_count` (`integer`): Total rendered causes count.
  - `causes_count` (`integer`): Total rendered causes count.
  - `verdict` (`string`): Validation verdict (`"ACCEPT"`, `"WARNING"`, `"REJECT"`).
  - `valid` (`boolean`): Overall validity boolean.
  - `summary` (`dict[str, Any]`): Summary metrics breakdown including `branch_counts`, `empty_branches`, and `top_branch`.
  - `html` (`string`): Rendered HTML/SVG markup.

---

### Example 1: Positive Control (Balanced 6M Analysis)

#### Invocation
```json
{
  "name": "categorize_fishbone",
  "arguments": {
    "effect": "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
    "causes": [
      {"category": "Man", "cause": "Operator fatigue during end-of-shift assembly cycle", "sub_category": "Fatigue"},
      {"category": "Man", "cause": "Inconsistent rod seal insertion technique across shifts", "sub_category": "Training"},
      {"category": "Machine", "cause": "CNC rod turning lathe spindle runout exceeding 0.015 mm", "sub_category": "Tooling"},
      {"category": "Machine", "cause": "Pneumatic seal crimping fixture misalignment", "sub_category": "Equipment"},
      {"category": "Method", "cause": "Work instruction missing torque sequence for cylinder tie-rods", "sub_category": "Standard Work"},
      {"category": "Method", "cause": "Inadequate lubrication specification for rod wiper assembly", "sub_category": "Process"},
      {"category": "Material", "cause": "NBR rod seal batch hardness variation (Durometer 65 vs 75 Shore A)", "sub_category": "Incoming Material"},
      {"category": "Material", "cause": "Anodized aluminum barrel bore surface roughness out of spec", "sub_category": "Raw Material"},
      {"category": "Measurement", "cause": "Air leakage test pressure decay gage uncalibrated (drift > 0.05 bar)", "sub_category": "Calibration"},
      {"category": "Measurement", "cause": "Dial indicator rod concentricity fixture deflection", "sub_category": "Gage R&R"},
      {"category": "Environment", "cause": "Assembly cleanroom ambient temperature fluctuation (+/- 8 deg C)", "sub_category": "Temperature"},
      {"category": "Environment", "cause": "Airborne particulate contamination in seal staging area", "sub_category": "Cleanliness"}
    ]
  }
}
```

#### Response
```json
{
  "basis": "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox",
  "valid": true,
  "verdict": "ACCEPT",
  "effect_statement": "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
  "total_causes": 12,
  "branch_counts": {
    "Man": 2,
    "Machine": 2,
    "Method": 2,
    "Material": 2,
    "Measurement": 2,
    "Environment": 2
  },
  "empty_branches": [],
  "duplicate_causes": [],
  "uncategorized_causes": [],
  "warnings": [],
  "recommendations": [
    "6M Fishbone diagram is well-balanced across all categories. Proceed to prioritize high-potential causes for 5-Why root cause analysis or verification testing."
  ]
}
```

---

### Example 2: Negative Control (Empty Branches & Imbalance Warning)

#### Invocation
```json
{
  "name": "categorize_fishbone",
  "arguments": {
    "effect": "Bearing wear out during operational test",
    "causes": [
      {"category": "Man", "cause": "Operator did not follow maintenance routine"},
      {"category": "Man", "cause": "Operator forgot to lubricate bearing"},
      {"category": "Man", "cause": "Operator skipped shift checklist"},
      {"category": "Machine", "cause": "Grease pump pressure low"}
    ]
  }
}
```

#### Response
```json
{
  "basis": "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox",
  "valid": true,
  "verdict": "WARNING",
  "effect_statement": "Bearing wear out during operational test",
  "total_causes": 4,
  "branch_counts": {
    "Man": 3,
    "Machine": 1,
    "Method": 0,
    "Material": 0,
    "Measurement": 0,
    "Environment": 0
  },
  "empty_branches": ["Method", "Material", "Measurement", "Environment"],
  "duplicate_causes": [],
  "uncategorized_causes": [],
  "warnings": [
    "Branch concentration imbalance: 'Man' contains 3/4 (75.0%) of total causes (threshold: 75%). Consider broadening brainstorming across other 6M branches to prevent tunnel vision.",
    "Empty branches detected: Method, Material, Measurement, Environment. Ishikawa (1986) and AIAG CQI-20 recommend exploring bare legs to ensure no critical failure causes are overlooked."
  ],
  "recommendations": [
    "Broaden brainstorming across underrepresented branches (Method, Material, Measurement, Environment) to avoid single-branch bias.",
    "Review bare branches (Method, Material, Measurement, Environment) with the cross-functional team to identify potential latent causes per AIAG CQI-20 Section G1."
  ]
}
```

## Best Practices
1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** Never compute branch percentage concentrations, evaluate branch balance, or adjudicate 6M category alias mappings using prompt-based heuristics. Always delegate categorization and audit evaluation to `categorize_fishbone` on `quality-mcp`.
2. **Explore Bare Legs / Empty Branches (Ishikawa 1986 & AIAG CQI-20 RULE 1):** When a fishbone diagram has empty branches, actively prompt the cross-functional team to brainstorm factors in those categories before concluding the ideation phase. Bare legs frequently conceal critical contributing factors.
3. **Counteract Operator-Blame Bias:** If brainstorming tilts heavily toward `Man` ($\ge 75\%$), challenge the team to investigate the systemic process, tooling, maintenance, and environmental conditions that allowed or induced operator errors.
4. **Allow Multi-Category Cause Placement (ASQ Quality Toolbox & AIAG CQI-20 RULE 5):** When a potential cause spans multiple categories (e.g., inadequate work instructions spanning `Method` and `Man`), place it in all relevant branches without spending time arguing about category boundaries.
5. **Anchor Problem Effect Statement in Measurable Facts:** Ensure the problem effect in the fishbone head is clearly defined, objective, and specific (e.g. derived from Kepner-Tregoe Is/Is-Not matrix or CMM inspection data) rather than vague symptoms like *"quality is bad"*.
6. **Transition from Fishbone Dispersion to 5-Why Drill-Down:** Use the 6M fishbone diagram for broad horizontal cause dispersion discovery, then select high-potential verified causes to drill down vertically into systemic root causes using `5why-root-cause` (`validate_5why`).

---
name: 5why-root-cause
description: Deterministic 5-Why root cause analysis validation, bottom-up reversible logic verification, and systemic root cause classification routing all chain evaluations to validate_5why and render_5why_canvas on quality-mcp.
---

# 5-Why Root Cause Analysis: Reversible Causal Logic & Systemic Prevention

## Overview
The `5why-root-cause` skill guides AI agents in conducting, evaluating, structuring, and auditing 5-Why Root Cause Analyses (RCA) according to the **AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018)**, the **Ford Motor Company Global 8D (G8D) Problem Solving Manual**, and **Nancy R. Tague's The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005)**.

The 5-Why technique is an iterative deductive question-asking method used to explore the cause-and-effect relationships underlying a particular manufacturing defect, process deviation, or quality escape. Rather than stopping at immediate physical symptoms or superficial human error, 5-Why analysis drills down to the underlying systemic policies, training programs, maintenance routines, or error-proofing mechanisms that allowed the problem to occur or escape undetected.

Key standards-based foundations include:
1. **Not Constrained to Exactly Five Steps:** Per AIAG CQI-20 Section 5 and Ford G8D Section D4, the inquiry should continue until the true root cause is established—it may require more or fewer than 5 iterations.
2. **Reversible Logic Directionality (RULE 3):** AIAG CQI-20 emphasizes that moving forward follows *"Why $\to$ Because"*, while reverse evaluation replaces *"Why"* with *"Therefore"* (*"Because [Cause], therefore [Symptom]"*). A valid 5-Why chain must demonstrate logical necessity in both directions.
3. **Rejection of Blame-Terminal Operator Error (RULE 4):** Per ASQ Quality Toolbox Chapter 5 (p. 514) and Ford G8D Section D7, stopping at individual human mistake (*"operator forgot"*, *"technician error"*) is a failure of root cause analysis. Individual error is a symptom; the true root cause resides in the management systems, training induction, standard work instructions, or poka-yoke devices that failed to prevent or detect the deviation.
4. **3-Legged 5-Why Model:** AIAG CQI-20 structures comprehensive problem solving across three distinct causal legs:
   - **Occurrence:** Why did the physical/technical process failure occur?
   - **Escape (Non-Discovery):** Why did the inspection/control system fail to detect the defect before reaching the customer?
   - **Systemic:** Why did the planning, engineering governance, or management system fail to anticipate and prevent the breakdown?

This skill equips agents to:
- Guide multi-disciplinary teams through rigorous 5-Why inquiry without hallucinating causal leaps.
- Validate causal chains for forward consistency, reverse "therefore" logic, circular reasoning, and premature termination.
- Detect and reject superficial operator blame, guiding the investigation toward systemic root causes.
- Delegate all deterministic chain validation, reversibility scoring, and canvas rendering to `validate_5why` and `render_5why_canvas` on `quality-mcp`.

## When to Use
Activate this skill in the following quality engineering and problem-solving scenarios:
- **8D Problem Solving (Discipline D4 - Root Cause Analysis):** Investigating customer complaints, warranty returns, or internal defect spikes during 8D investigations.
- **Nonconformance (NCR) & Corrective Action (CAPA):** Performing root cause investigations required by ISO 9001:2015 §10.2 and IATF 16949:2016 §10.2.3.
- **3-Legged 5-Why Investigations:** Systematically evaluating Occurrence, Escape, and Systemic causal paths for complex manufacturing deviations per AIAG CQI-20.
- **Root Cause Audit & Peer Review:** Auditing submitted 5-Why reports for circular reasoning, premature termination at physical symptoms, or superficial operator blame.
- **Corrective Action Formulation:** Transitioning from identified systemic root causes to permanent preventive actions and poke-yoke implementations.

### Input Requirements
To validate a 5-Why analysis, collect the following domain inputs:
- **Problem Statement (`problem_statement`):** Clear, factual description of the observed defect, symptom, or failure mode (e.g. *"Hole positions outside of tolerance on CNC drilling station"*).
- **5-Why Step Sequence (`steps`):** List of sequential step dictionaries containing:
  - `step_number` (`integer`, required): Consecutive integer starting from 1 ($1, 2, 3\dots N$).
  - `why` (`string`, required): The specific question asked at this step (non-blank).
  - `because` (`string`, required): The factual causal explanation answering the why question (non-blank).
- **Explicit Root Cause (`root_cause`, optional):** Final root cause statement if distinct from the terminal step's explanation.
- **Leg Type (`leg_type`, optional):** Causal leg classification: `"occurrence"`, `"escape"`, or `"systemic"`.

### Prerequisites
- Active `quality-mcp` server connection providing `validate_5why` and `render_5why_canvas` tools.

## Step-by-Step Methodology
Follow the 5-step 5-Why investigation and verification methodology:

```
┌────────────────────────────────────────────────────────────────────────┐
│               5-STEP REVERSIBLE 5-WHY RCA METHODOLOGY                 │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Problem Statement Scoping     │ Define clear, non-blaming symptom   │
│ 2. Forward Causal Drill-Down     │ Ask Why -> Because iteratively      │
│ 3. Deterministic Tool Validation │ Execute validate_5why on MCP        │
│ 4. Reverse Logic & Anti-Patterns │ Audit "Therefore" flow & blame tags │
│ 5. Visual Canvas & Synthesis     │ Render canvas & systemic CAPA plan  │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Problem Statement Scoping & Fact Anchoring
- Formulate a precise, measurable problem statement describing what went wrong, where it was observed, and the physical deviation (anchored in KT Is/Is-Not or inspection data).
- Ensure the problem statement describes the symptom/effect without embedding speculative causes or assigning blame.

### 2. Step 2: Forward Causal Drill-Down ("Why $\to$ Because")
- Begin at Step 1 by asking why the problem statement occurred.
- For each subsequent step $i+1$, formulate the `why` question directly from the `because` explanation of step $i$.
- Enforce factual, evidence-backed answers rather than hypotheses.
- Continue drilling down until reaching a management policy, training system, maintenance procedure, or design standard (systemic level).

### 3. Step 3: Tool Execution & Deterministic Validation
- Package the sequence into `steps` and invoke `validate_5why` on `quality-mcp`.
- *Strict Invariant:* Never evaluate causal reversibility, compute reversibility scores, or adjudicate operator blame in prompt text. All validation must execute through `validate_5why`.

### 4. Step 4: Reverse Logic & Anti-Pattern Analysis
Examine the returned validation payload from `validate_5why`:
- **`verdict` & `reversibility_score`:**
  - `ACCEPT` ($\ge 0.80$, no hard anti-patterns): Chain is logically reversible and sound.
  - `WARNING` ($0.50 \le \text{score} < 0.80$): Chain has minor leaps or non-causal transitions requiring refinement.
  - `REJECT` ($< 0.50$ or hard anti-pattern): Chain contains circular loops or terminal operator blame.
- **Anti-Pattern Findings:**
  - `CIRCULAR_REASONING`: Step explanation restates the problem statement or loops back to an earlier step.
  - `BLAME_TERMINAL_OPERATOR_ERROR`: Chain terminates at individual human error without addressing systemic controls.
  - `PREMATURE_TERMINATION`: Chain stops prematurely at a physical symptom ($N < 3$) without reaching systemic cause.
  - `NON_CAUSAL_JUMP`: Step introduces disjoint vocabulary with weak lexical/semantic linkage to the prior step.
- **Systemic Assessment:** Review `classification` (`SYSTEMIC`, `TECHNICAL_PROCESS`, `HUMAN_INDIVIDUAL`) and `is_systemic`.

### 5. Step 5: Visual Canvas Generation & Corrective Action Synthesis
- Invoke `render_5why_canvas` on `quality-mcp` to generate an interactive, themed visual HTML report displaying the causal cascade, reverse check arrows, and summary KPI cards.
- Formulate permanent corrective actions (CAPA) addressing the identified systemic root cause:
  - **Poka-Yoke / Error-Proofing:** Mechanical interlocks, sensor gates, fixture guides.
  - **Standardized Work & Procedures:** Revised work instructions, sign-off requirements, maintenance cadence.
  - **Training & Qualification:** Induction checklists, competency verification, training tracking systems.

## Tool Invocations

### `validate_5why`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic validation of 5-Why causal chain reversibility, reverse "therefore" logic, anti-pattern detection, and systemic classification.
- **Parameters:**
  - `steps` (`list[dict[str, Any]] | null`, optional): List of step dictionaries. If omitted, loads reference benchmark dataset.
    - `step_number` (`integer`, required): Step sequence number ($1, 2, \dots N$).
    - `why` (`string`, required): Why question text.
    - `because` (`string`, required): Causal explanation text.
  - `problem_statement` (`string`, default `"Problem Statement"`): Description of the observed defect/symptom.
  - `root_cause` (`string | null`, optional): Explicit terminal root cause statement.
  - `leg_type` (`string | null`, optional): Leg classification (`"occurrence"`, `"escape"`, `"systemic"`).
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `basis` (`string`): Standards attribution string (`"AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox"`).
  - `valid` (`boolean`): Overall validity status (`true` if verdict is `ACCEPT` or `WARNING` without hard anti-patterns).
  - `verdict` (`string`): Categorical evaluation (`"ACCEPT"`, `"WARNING"`, `"REJECT"`).
  - `reversibility_score` (`float`): Numerical reversibility score in $[0.0, 1.0]$.
  - `problem_statement` (`string`): Evaluated problem statement.
  - `root_cause` (`string`): Isolated terminal root cause.
  - `total_steps` (`integer`): Number of steps in the chain.
  - `link_evaluations` (`list[dict]`): Step-by-step evaluations with `reverse_statement`, `is_reversible`, `reversibility_score`, and `notes`.
  - `anti_patterns` (`list[dict]`): Findings with `code`, `severity`, `step_number`, `message`, and `recommendation`.
  - `systemic_assessment` (`dict`): `classification`, `is_systemic`, `terminal_cause`, `systemic_factors`, and `recommendations`.
  - `recommendations` (`list[string]`): Prioritized engineering recommendations.
  - `leg_type` (`string | null`): Leg type if provided.

---

### `render_5why_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Renders an interactive visual HTML canvas for a 5-Why causal chain with dark/light themes, summary KPI cards, and reverse check cascades.
- **Parameters:**
  - `steps` (`list[dict[str, Any]] | null`, optional): List of step dictionaries. If omitted, loads reference benchmark dataset.
  - `problem_statement` (`string`, default `"Problem Statement"`): Problem statement.
  - `root_cause` (`string | null`, optional): Root cause statement.
  - `leg_type` (`string | null`, optional): Leg classification.
  - `title` (`string`, default `"5-Why Root Cause Analysis Canvas"`): Canvas header title.
  - `theme` (`string`, default `"dark"`): Color theme palette (`"dark"` or `"light"`).
  - `standalone` (`boolean`, default `true`): If true, returns standalone HTML5 document; if false, embeddable container.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `title` (`string`): Canvas title.
  - `rows_count` (`integer`): Total rendered steps.
  - `steps_count` (`integer`): Total rendered steps.
  - `verdict` (`string`): Validation verdict.
  - `valid` (`boolean`): Boolean validity.
  - `reversibility_score` (`float`): Reversibility score.
  - `summary` (`dict`): Summary metrics.
  - `html` (`string`): Rendered HTML string.

---

### Example 1: Valid 5-Why Chain Validation (Ford Global 8D Bearing Case)

#### Invocation
```json
{
  "name": "validate_5why",
  "arguments": {
    "problem_statement": "Hole positions outside of tolerance on CNC drilling station",
    "steps": [
      {
        "step_number": 1,
        "why": "Why was the bearing worn out?",
        "because": "It had dried up."
      },
      {
        "step_number": 2,
        "why": "Why did the bearing dry out?",
        "because": "The operator did not carry out shift autonomous maintenance routines."
      },
      {
        "step_number": 3,
        "why": "Why did the operator not follow the maintenance routine completely?",
        "because": "He was not properly trained during the induction."
      },
      {
        "step_number": 4,
        "why": "Why was he not trained in the induction?",
        "because": "Its induction program lost this outside the sheet."
      },
      {
        "step_number": 5,
        "why": "Why was this missing on the sheet?",
        "because": "The induction plan was not signed by Engineering."
      }
    ],
    "leg_type": "occurrence"
  }
}
```

#### Successful Response
```json
{
  "basis": "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox",
  "valid": true,
  "verdict": "ACCEPT",
  "reversibility_score": 1.0,
  "problem_statement": "Hole positions outside of tolerance on CNC drilling station",
  "root_cause": "The induction plan was not signed by Engineering.",
  "total_steps": 5,
  "link_evaluations": [
    {
      "step_number": 1,
      "why": "Why was the bearing worn out?",
      "because": "It had dried up.",
      "reverse_statement": "Because It had dried up, therefore Hole positions outside of tolerance on CNC drilling station.",
      "is_reversible": true,
      "reversibility_score": 1.0,
      "notes": null
    },
    {
      "step_number": 2,
      "why": "Why did the bearing dry out?",
      "because": "The operator did not carry out shift autonomous maintenance routines.",
      "reverse_statement": "Because The operator did not carry out shift autonomous maintenance routines, therefore It had dried up.",
      "is_reversible": true,
      "reversibility_score": 1.0,
      "notes": "Intermediate human factor identified; resolved systemically in subsequent steps."
    },
    {
      "step_number": 3,
      "why": "Why did the operator not follow the maintenance routine completely?",
      "because": "He was not properly trained during the induction.",
      "reverse_statement": "Because He was not properly trained during the induction, therefore The operator did not carry out shift autonomous maintenance routines.",
      "is_reversible": true,
      "reversibility_score": 1.0,
      "notes": null
    },
    {
      "step_number": 4,
      "why": "Why was he not trained in the induction?",
      "because": "Its induction program lost this outside the sheet.",
      "reverse_statement": "Because Its induction program lost this outside the sheet, therefore He was not trained during the induction.",
      "is_reversible": true,
      "reversibility_score": 1.0,
      "notes": null
    },
    {
      "step_number": 5,
      "why": "Why was this missing on the sheet?",
      "because": "The induction plan was not signed by Engineering.",
      "reverse_statement": "Because The induction plan was not signed by Engineering, therefore Its induction program lost this outside the sheet.",
      "is_reversible": true,
      "reversibility_score": 1.0,
      "notes": null
    }
  ],
  "anti_patterns": [],
  "systemic_assessment": {
    "classification": "SYSTEMIC",
    "is_systemic": true,
    "terminal_cause": "The induction plan was not signed by Engineering.",
    "systemic_factors": ["engineering", "induction", "induction plan", "maintenance routine", "plan", "training"],
    "recommendations": ["Implement and verify permanent corrective action addressing the systemic policy/procedure."]
  },
  "recommendations": ["Implement and verify permanent corrective action addressing the systemic policy/procedure."],
  "leg_type": "occurrence"
}
```

---

### Example 2: Negative Control (Rejection of Terminal Operator Blame)

#### Invocation
```json
{
  "name": "validate_5why",
  "arguments": {
    "problem_statement": "Part dimension out of tolerance",
    "steps": [
      {
        "step_number": 1,
        "why": "Why was the dimension out of tolerance?",
        "because": "CNC offset was not adjusted."
      },
      {
        "step_number": 2,
        "why": "Why was CNC offset not adjusted?",
        "because": "Operator forgot to check the micrometer."
      }
    ]
  }
}
```

#### Rejection Response
```json
{
  "basis": "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox",
  "valid": false,
  "verdict": "REJECT",
  "reversibility_score": 0.5,
  "problem_statement": "Part dimension out of tolerance",
  "root_cause": "Operator forgot to check the micrometer.",
  "total_steps": 2,
  "anti_patterns": [
    {
      "code": "BLAME_TERMINAL_OPERATOR_ERROR",
      "severity": "error",
      "step_number": 2,
      "message": "Terminal root cause 'Operator forgot to check the micrometer.' terminates at individual operator/human error without systemic management, training, or poka-yoke resolution.",
      "recommendation": "Continue drilling down per ASQ Quality Toolbox & Ford Global 8D (RULE 4) to identify why the system, training program, or error-proofing failed to prevent or detect the human error."
    },
    {
      "code": "PREMATURE_TERMINATION",
      "severity": "warning",
      "step_number": 2,
      "message": "Chain terminated at Step 2 with non-systemic cause 'Operator forgot to check the micrometer.'. 5-Why typically requires 3 to 5 iterations to reach systemic root cause.",
      "recommendation": "Continue asking 'Why' to drill down past immediate physical/technical causes to systemic policy, maintenance, or procedural safeguards."
    }
  ],
  "systemic_assessment": {
    "classification": "HUMAN_INDIVIDUAL",
    "is_systemic": false,
    "terminal_cause": "Operator forgot to check the micrometer.",
    "systemic_factors": [],
    "recommendations": ["Drill down past individual error to identify management system, training, or poka-yoke root cause."]
  },
  "recommendations": [
    "Continue drilling down per ASQ Quality Toolbox & Ford Global 8D (RULE 4) to identify why the system, training program, or error-proofing failed to prevent or detect the human error.",
    "Continue asking 'Why' to drill down past immediate physical/technical causes to systemic policy, maintenance, or procedural safeguards.",
    "Drill down past individual error to identify management system, training, or poka-yoke root cause."
  ],
  "leg_type": null
}
```

## Best Practices
1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** Never evaluate causal reversibility, compute reversibility scores, or adjudicate operator blame using prompt-based heuristics. Always delegate verification to `validate_5why` on `quality-mcp`.
2. **Enforce Reverse "Therefore" Verification (AIAG CQI-20 RULE 3):** Always test the chain in reverse order (*"Because [Root Cause], therefore [Step 4]... therefore [Problem Statement]"*). If a reverse transition fails to demonstrate logical necessity, insert missing intermediate causal links.
3. **Never Terminate at Individual Operator Error (RULE 4):** Adhere strictly to ASQ Quality Toolbox (*"Don’t stop when you reach a 'who'"*) and Ford Global 8D (*"Establish the root cause of the root cause"*). If operator error is identified at an intermediate step, continue asking why until uncovering the systemic training, procedure, or error-proofing gap.
4. **Distinguish Occurrence, Escape, and Systemic Legs (3-Legged 5-Why):** For complex customer escapes, conduct three independent 5-Why chains:
   - **Occurrence Leg:** Why did the manufacturing process generate the nonconformance?
   - **Escape Leg:** Why did the quality inspection or containment screen fail to catch it?
   - **Systemic Leg:** Why did the management or engineering planning system fail to anticipate the failure mode?
5. **Eliminate Circular Reasoning:** Verify that step explanations do not merely restate the problem statement in different words or create infinite circular loops between two steps.
6. **Ground Explanations in Objective Evidence:** Reject speculative or unverified claims. Every "Because" statement should be backed by physical inspection, machine logs, tool wear data, or documented records.
7. **Deploy Poka-Yoke & Systemic CAPA:** Align corrective actions with the systemic root cause rather than relying on superficial remedies like *"retrain operator"* or *"remind team to be careful"*.

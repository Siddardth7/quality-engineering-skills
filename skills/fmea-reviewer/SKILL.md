---
name: fmea-reviewer
description: AIAG & VDA (1st Edition, 2019) FMEA review, qualitative risk evaluation, and deterministic Action Priority (AP) scoring via quality-mcp.
---

# FMEA Reviewer: AIAG & VDA (2019) Risk & Action Priority Evaluation

## Overview
The `fmea-reviewer` skill guides AI agents in conducting structured, standards-compliant Failure Mode and Effects Analysis (DFMEA, PFMEA, and FMEA-MSR) reviews according to the **AIAG & VDA FMEA Handbook (1st Edition, 2019)**, specifically Section 3.5.9 (*Action Priority (AP) for DFMEA and PFMEA*).

Historically, FMEA evaluations relied on the classic Risk Priority Number ($\text{RPN} = S \times O \times D$), applying arbitrary thresholds (e.g., $\text{RPN} > 100$) that treated Severity, Occurrence, and Detection with equal arithmetic weight. This legacy practice allowed critical, high-severity failure modes with moderate or low occurrence to be masked by low RPN values. The AIAG & VDA 2019 standard replaces arbitrary RPN cutoffs with the **Action Priority (AP)** logic table, establishing a systematic, non-linear hierarchy that prioritizes Severity first ($S \to O \to D$).

This skill equips agents to:
- Decompose complex designs and manufacturing processes across the 7-Step FMEA methodology.
- Elicit and critique failure chains (Failure Effect $\to$ Failure Mode $\to$ Failure Cause).
- Distinguish between prevention controls (affecting Occurrence) and detection controls (affecting Detection).
- Delegate all quantitative risk scoring ($S$, $O$, $D$ validation, RPN calculation, and AP table lookup) to the deterministic `lookup_fmea_ap` tool on `quality-mcp`.
- Synthesize actionable optimization and containment recommendations based on deterministic AP levels (High, Medium, Low).

## When to Use
Activate this skill in the following quality engineering scenarios:
- **FMEA Document Audits:** Auditing existing Design FMEAs (DFMEA) or Process FMEAs (PFMEA) for completeness, structural coherence, and standards compliance.
- **Risk Assessment & Scoring:** Evaluating risk levels for newly identified potential failure modes during product design or process engineering.
- **Legacy FMEA Migration:** Migrating legacy AIAG 4th Edition FMEAs using RPN thresholds to the AIAG & VDA (2019) Action Priority methodology.
- **Corrective Action & Optimization Review:** Evaluating proposed engineering changes or control improvements to verify post-mitigation risk reduction (initial vs revised AP).
- **Control Plan Alignment:** Verifying that High and Medium AP items from PFMEAs are properly addressed in pre-launch and production Control Plans.

### Input Requirements
To execute an FMEA review, collect the following domain inputs:
- **System / Item / Process Step:** Component, assembly, or manufacturing operation under review.
- **Failure Mode (FM):** The specific physical or functional manner in which the item fails to meet intent.
- **Failure Effect (FE):** Impact of the failure mode on the immediate system, vehicle, customer, or regulatory compliance.
- **Severity ($S$):** Integer rating from 1 to 10 on the AIAG-VDA Severity scale.
- **Failure Cause (FC):** Physical or chemical mechanism, human action, or process condition that results in the failure mode.
- **Current Prevention Controls (PC):** Measures implemented to prevent the cause or reduce its occurrence.
- **Occurrence ($O$):** Integer rating from 1 to 10 on the AIAG-VDA Occurrence scale.
- **Current Detection Controls (DC):** Measures implemented to detect the cause or failure mode before product release or shipment.
- **Detection ($D$):** Integer rating from 1 to 10 on the AIAG-VDA Detection scale.

### Prerequisites
- Active `quality-mcp` server connection (verified via `mcp-health` or `ping` tool).

## Step-by-Step Methodology
Follow the AIAG & VDA 7-Step FMEA execution framework:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   AIAG & VDA 7-STEP FMEA METHODOLOGY                   │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Planning & Preparation        │ Define scope, boundaries, 5T basis  │
│ 2. Structure Analysis            │ Map system / process hierarchy      │
│ 3. Function Analysis             │ Define functions, requirements, reqs│
│ 4. Failure Analysis              │ Establish FE → FM → FC causal chains│
│ 5. Risk Analysis                 │ Rate S, O, D; call lookup_fmea_ap   │
│ 6. Optimization                  │ Define actions per AP (High/Med/Low)│
│ 7. Results Documentation         │ Document risks, actions, closures   │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Planning and Preparation
- Establish analysis boundary, scope, and team charter.
- Identify whether the analysis is a DFMEA (product function), PFMEA (manufacturing process), or FMEA-MSR (monitoring and system response).
- Establish project timeline, baseline documents (BOM, P-Diagram, Process Flow Diagram), and customer requirements.

### 2. Step 2: Structure Analysis
- **For DFMEA:** Decompose system $\to$ subsystem $\to$ component.
- **For PFMEA:** Decompose process item $\to$ process step $\to$ process work element (4M/6M: Man, Machine, Material, Method, Measurement, Milieu).

### 3. Step 3: Function Analysis
- Map required functions, measurable performance parameters, and regulatory characteristics for each structural element.
- Associate functions directly to customer expectations and engineering specifications.

### 4. Step 4: Failure Analysis (The Causal Chain)
- For each function, derive the **Failure Chain**:
  - **Failure Effect (FE):** What happens to the end user, downstream station, or vehicle? (Governs Severity $S$).
  - **Failure Mode (FM):** What is the physical failure or non-conformance?
  - **Failure Cause (FC):** Why did the failure occur? What is the root mechanism?
- Validate bidirectional causal logic:
  $$\text{Failure Cause (Why?)} \longrightarrow \text{Failure Mode (How?)} \longrightarrow \text{Failure Effect (Impact)}$$

### 5. Step 5: Risk Analysis (MCP Engine Execution)
- Identify current Prevention Controls (PC) aimed at eliminating or reducing the likelihood of the Failure Cause.
- Identify current Detection Controls (DC) aimed at identifying the Cause or Mode before release/shipment.
- Assign provisional integer ratings ($1 \le S, O, D \le 10$) using the AIAG-VDA standard rating rubrics:
  - **Severity ($S$):** 10 = Safety hazard without warning / non-compliance; 1 = No discernible effect.
  - **Occurrence ($O$):** 10 = Extremely high / failure almost inevitable; 1 = Extremely low / eliminated by design.
  - **Detection ($D$):** 10 = Almost impossible to detect; 1 = Error-proofed / automated detection and lock-out.
- **Invoke `lookup_fmea_ap` on `quality-mcp`:**
  - Send the integer ratings $\{S, O, D\}$ to the tool.
  - Receive the deterministic RPN and Action Priority (AP: High, Medium, Low).
  - *Never calculate RPN or lookup AP in prompt text.*

### 6. Step 6: Optimization (Prioritized Actions)
Based on the deterministic Action Priority result from `lookup_fmea_ap`:
- **High (H) Action Priority:**
  - **Mandatory Action:** The team *must* identify appropriate actions to improve prevention and/or detection controls, or document why current controls are acceptable (subject to management sign-off).
  - Primary goal: Eliminate failure cause or reduce Occurrence ($O$) via design/process modification (e.g., poke-yoke, geometric keying, automated parameter interlocks).
- **Medium (M) Action Priority:**
  - **Recommended Action:** The team *should* identify actions to improve prevention or detection controls, or document why current controls are adequate.
  - Focus on cost-effective prevention improvements and upgraded detection capability.
- **Low (L) Action Priority:**
  - **Low Priority:** The team *could* identify actions to improve controls; current controls are generally considered capable and acceptable.
- **Post-Action Rescoring:**
  - After defining corrective actions, assign revised ratings ($S_{rev}, O_{rev}, D_{rev}$).
  - Call `lookup_fmea_ap` again to verify that the revised AP level has been successfully downgraded (e.g., High $\to$ Low or Medium $\to$ Low).

### 7. Step 7: Results Documentation
- Compile the complete FMEA record: structural hierarchy, failure chains, initial S/O/D, initial AP, assigned actions, responsible owners, target completion dates, implementation status, and revised S/O/D with verified final AP.

## Tool Invocations

### `lookup_fmea_ap`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic lookup of AIAG & VDA (1st Edition, 2019) Action Priority (AP) level and calculation of classic Risk Priority Number (RPN) per Section 3.5.9.
- **Parameters:**
  - `severity` (`integer`, required): Severity rating on the 1–10 AIAG-VDA scale ($1 \le \text{severity} \le 10$).
  - `occurrence` (`integer`, required): Occurrence rating on the 1–10 AIAG-VDA scale ($1 \le \text{occurrence} \le 10$).
  - `detection` (`integer`, required): Detection rating on the 1–10 AIAG-VDA scale ($1 \le \text{detection} \le 10$).
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `severity` (`integer`): Validated input severity score.
  - `occurrence` (`integer`): Validated input occurrence score.
  - `detection` (`integer`): Validated input detection score.
  - `rpn` (`integer`): Calculated Risk Priority Number ($S \times O \times D$, range 1–1000).
  - `action_priority` (`string`): Deterministic Action Priority rating (`"High"`, `"Medium"`, or `"Low"`).

#### Example Tool Invocation
```json
{
  "severity": 10,
  "occurrence": 4,
  "detection": 4
}
```

#### Example Successful Response
```json
{
  "severity": 10,
  "occurrence": 4,
  "detection": 4,
  "rpn": 160,
  "action_priority": "High"
}
```

#### Protocol Error Handling
If any rating is outside the 1–10 integer range or is of an invalid type (e.g., string, float, boolean, None), `quality-mcp` returns a standard MCP protocol error response:
- `isError: True`
- `structuredContent: None`
- `content`: `[TextContent(type="text", text="... out of range: must be between 1 and 10 ...")]`

When encountering a protocol error, the agent must not fabricate a score; instead, inform the user of the invalid parameter and request a corrected rating within the valid 1–10 scale.

## Best Practices
- **Strict Invariant: Zero Inline Math in Prompt Context.** Never perform manual arithmetic ($S \times O \times D$), estimate Action Priority through prompt heuristics, or simulate lookup matrices in agent context. Always route scoring to `lookup_fmea_ap`.
- **Standards Fidelity (AIAG & VDA 2019):** Strictly apply AIAG & VDA 1st Edition (2019) Section 3.5.9 principles. Do not apply obsolete RPN threshold rules (e.g., "only act if RPN > 100").
- **Severity Dominance:** Respect the non-linear structure of Action Priority where Severity is emphasized first ($S \to O \to D$). Note that $S=10, O=4, D=4$ yields $\text{AP} = \text{High}$ despite a modest RPN of 160, whereas $S=4, O=10, D=10$ yields $\text{AP} = \text{High}$ but with different action imperatives.
- **Prevention Over Detection:** When recommending corrective actions for High or Medium AP, prioritize prevention controls that reduce Occurrence ($O$) over detection controls that merely improve Detection ($D$).
- **Distinguish PC vs DC:** Ensure that inspection, testing, and audits are classified as Detection Controls (DC), while design margins, error-proofing (poka-yoke), and process capability enhancements are classified as Prevention Controls (PC).
- **Closed-Loop Verification:** Always require pre- and post-mitigation scoring. Verify that post-action $S_{rev}, O_{rev}, D_{rev}$ values are sent through `lookup_fmea_ap` to prove risk reduction before closing an action item.

---
name: skill-template
description: Skeleton template for authoring quality engineering skills adhering to the agentskills.io standard.
---

# Skill Template

## Overview
Briefly describe the quality engineering domain, the core problem this skill addresses, and the governing quality standard references (e.g., AIAG & VDA FMEA 1st Edition, AIAG SPC 2nd Edition, ISO 9001:2015, IATF 16949:2016).

State the high-level objective of the skill and how it guides the AI agent through the domain-specific workflow.

## When to Use
Specify the explicit triggers and scenarios for activating this skill:
- **Trigger Scenarios:** List the problem statements, user requests, or process events where this skill applies.
- **Input Requirements:** Detail required input artifacts (e.g., CSV datasets, process flow diagrams, BOMs, inspection logs, severity ratings).
- **Prerequisites:** Note any preceding steps, certifications, or tool connectivity requirements.

## Step-by-Step Methodology
Provide the structured, phased engineering methodology:
1. **Phase 1: Ingestion & Problem Decomposition**
   - Collect and validate raw domain inputs.
   - Decompose complex systems into constituent functions, failure modes, or characteristic parameters.
2. **Phase 2: Qualitative Engineering Reasoning**
   - Apply standard quality heuristics (e.g., 6M classification, boundary definition).
   - Formulate structured payload objects for calculation engines.
3. **Phase 3: Tool Execution & Deterministic Verification**
   - Dispatch structured data to the designated `quality-mcp` tool.
   - Await deterministic results from the engine.
4. **Phase 4: Synthesis & Actionable Recommendations**
   - Interpret tool output in the context of industry standards.
   - Generate prioritized corrective actions, containment steps, or control plan updates.

## Tool Invocations
Detail the exact MCP tools available for this skill.

### `tool_name`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic calculation of domain metrics.
- **Parameters:**
  - `param_1` (`type`): Description of parameter 1.
  - `param_2` (`type`): Description of parameter 2.
- **Expected Output:**
  - `result_field` (`type`): Description of return field.
- **Example Call:**
  ```json
  {
    "param_1": "value_1",
    "param_2": [1.0, 2.0, 3.0]
  }
  ```

## Best Practices
- **Strict Invariant: No Inline Math in Prompt Context.** Never attempt to calculate statistical limits, capability indices, RPN/AP scores, or variance components directly in prompt text. Always delegate computation to `quality-mcp` tools.
- **Standards Fidelity:** Quote and align with official standards terminology (e.g., AIAG & VDA, ISO 9001).
- **Evidence-Based Dispositions:** Ensure all risk ratings, dispositions, and root cause conclusions are backed by objective evidence and deterministic tool outputs.
- **Traceability:** Maintain bidirectional linkage between failure modes, causes, controls, and verification data.

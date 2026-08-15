---
name: spc-control-charts
description: Statistical Process Control (SPC) chart selection, run-rule evaluation, and stability-gated capability analysis routing all computations to the calculate_spc_chart MCP tool.
---

# Statistical Process Control (SPC): Control Charts, Run Rules & Stability-Gated Capability

## Overview
The `spc-control-charts` skill guides AI agents in conducting structured, standards-compliant Statistical Process Control (SPC) analysis according to the **AIAG Statistical Process Control (SPC) Reference Manual (4th Edition, 2005)**.

SPC provides the statistical methodology for monitoring, controlling, and improving processes over time by distinguishing between **common-cause variation** (inherent random noise in a stable process) and **special-cause variation** (assignable, non-random disturbances).

A fundamental tenet of quality engineering is the **stability-before-capability rule**:
1. **Process Control (Stability):** Assessed solely using control limits calculated from process dispersion ($\bar{R}/d_2, \bar{s}/c_4, \bar{\text{MR}}/d_2$) and Shewhart / Western Electric / Nelson run rules.
2. **Process Capability:** Assessed by comparing process variation to engineering customer specifications (USL, LSL). **Capability metrics ($C_p, C_{pk}, P_p, P_{pk}$) are mathematically and logically invalid for an out-of-control process.**

This skill equips agents to:
- Guide users through rational subgrouping and appropriate control chart selection.
- Delegate all control limit calculations, within-subgroup variation estimation ($\hat{\sigma}$), run-rule violation detections, and capability indices to the deterministic `calculate_spc_chart` FastMCP tool on `quality-mcp`.
- Strictly enforce the stability gate: when special causes are detected, instruct users to investigate and eliminate assignable causes rather than attempting to calculate or report capability figures.

## When to Use
Activate this skill in the following quality engineering scenarios:
- **Control Chart Selection & Setup:** Determining the appropriate Shewhart variable chart ($\bar{X}\text{-}R, \bar{X}\text{-}S, I\text{-MR}$) or attribute chart ($p, c, u$) based on measurement data type, subgroup size ($n$), and inspection conditions.
- **Process Stability Monitoring:** Analyzing sequential production data for out-of-control signals using Western Electric Rules (Rules 1–4) or Nelson Rules (Rules 1–8).
- **Process Capability Studies (PPAP / APQP):** Calculating short-term capability ($C_p, C_{pk}$) and long-term performance ($P_p, P_{pk}$) with confidence intervals for stable processes during initial process studies or ongoing verification.
- **Out-of-Control Action Plan (OCAP) Triage:** Assisting quality and manufacturing engineers in diagnosing special-cause signals and prioritizing root-cause investigation.
- **Control Plan Verification:** Confirming that critical-to-quality (CTQ) characteristics in Control Plans have functioning statistical controls and verified stability.

### Input Requirements
To execute an SPC analysis, collect the following domain inputs:
- **Characteristic & Measurement Type:** Continuous variable (e.g. diameter, thickness, torque) or discrete attribute (e.g. defect count, nonconforming units).
- **Subgroup Structure:** Individual readings ($n=1$) or rational subgroups ($n \ge 2$).
- **Process Data:** Raw measurement subgroups (`list[list[float]]`) or individual observations / counts (`list[float]`).
- **Engineering Specification Limits (Optional for Stability, Required for Capability):** Upper Specification Limit (`usl`) and/or Lower Specification Limit (`lsl`).
- **Sample Sizes (Required for $p$ and $u$ charts):** Subgroup lot sizes (`sample_sizes`).
- **Run-Rule Set:** `"Western Electric"` (default) or `"Nelson"`.

### Prerequisites
- Active `quality-mcp` server connection providing the `calculate_spc_chart` tool.

## Step-by-Step Methodology
Follow the 5-step SPC analysis framework:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     5-STEP AIAG SPC METHODOLOGY                        │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Chart Selection               │ Select variable or attribute chart  │
│ 2. Rational Subgrouping          │ Verify subgroup size (n) and timing │
│ 3. Tool Invocation               │ Call calculate_spc_chart on MCP     │
│ 4. Stability Evaluation          │ Audit violations; rule check        │
│ 5. Stability-Gated Capability    │ If stable -> interpret Cp/Cpk/Pp/Ppk│
│                                  │ If unstable -> withhold capability  │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Control Chart Selection
Determine the appropriate chart type using the standard AIAG decision taxonomy:

| Data Type | Subgroup Size ($n$) | Primary Chart | Dispersion Chart | MCP `chart_type` |
|---|---|---|---|---|
| Continuous Variable | $n = 1$ (Individual measurements) | Individuals ($I$) | Moving Range ($MR$) | `"I-MR"` |
| Continuous Variable | $2 \le n \le 10$ (Small rational subgroups) | Subgroup Mean ($\bar{X}$) | Subgroup Range ($R$) | `"Xbar-R"` |
| Continuous Variable | $n > 10$ (or $2 \le n \le 12$) | Subgroup Mean ($\bar{X}$) | Subgroup Std Dev ($s$) | `"Xbar-S"` |
| Discrete Attribute | Constant or varying lot sizes | Proportion Defective ($p$) | N/A | `"p"` |
| Discrete Attribute | Constant sample size / unit area | Defect Count ($c$) | N/A | `"c"` |
| Discrete Attribute | Varying sample size / unit area | Defects Per Unit ($u$) | N/A | `"u"` |

### 2. Step 2: Rational Subgrouping Verification
Ensure data represents rational subgroups:
- **Within-subgroup variation:** Reflects only inherent, short-term common-cause variation. Subgroups should be gathered close in time (e.g. 5 consecutive parts from a machine).
- **Between-subgroup variation:** Reflects process shifts, drift, operator changes, or lot-to-lot differences across time.

### 3. Step 3: Tool Invocation
Delegate all computation directly to `calculate_spc_chart`. Construct the parameters matching the chart type and invoke the tool.

### 4. Step 4: Stability Evaluation
Review the tool response:
- Check `in_control` and `violations`.
- If `violations` is empty (`in_control == True`), the process is operating in statistical control with predictable common-cause variation only.
- If `violations` contains items (`in_control == False`), identify the specific points and rules triggered:
  - **Rule 1 (Beyond 3-sigma):** Extreme special cause (tool breakage, power surge, operator error).
  - **Rule 2 (Run of 9 on one side of center line):** Mean shift (material lot change, calibration offset).
  - **Rule 3 (6 consecutive points increasing/decreasing):** Systematic trend (tool wear, temperature buildup).
  - **Rule 4 (14 consecutive points alternating up/down):** Systematic oscillation (over-control, alternating fixtures).

### 5. Step 5: Stability-Gated Capability Interpretation
- **If Process is Out-of-Control (`in_control == False`):**
  - **DO NOT report capability indices.**
  - Explain to the user: *"The process exhibits special-cause variation (out-of-control signals). In accordance with AIAG SPC 4th Edition standards, process capability indices (Cp, Cpk, Pp, Ppk) are invalid until statistical control is established. Investigate and eliminate the identified special causes first."*
- **If Process is In-Control (`in_control == True`) and Spec Limits Provided:**
  - Evaluate short-term capability: $C_p$ (potential capability based on within-subgroup $\hat{\sigma}$) and $C_{pk}$ (actual capability considering centering).
  - Evaluate long-term performance: $P_p$ (potential performance based on overall $\sigma_{\text{overall}}$) and $P_{pk}$ (actual performance).
  - Benchmark targets:
    - $C_{pk}, P_{pk} \ge 1.67$: Excellent capability (typical new process / CTQ requirement).
    - $1.33 \le C_{pk}, P_{pk} < 1.67$: Adequate capability for standard production.
    - $1.00 \le C_{pk}, P_{pk} < 1.33$: Marginally capable; requires tight process monitoring.
    - $C_{pk}, P_{pk} < 1.00$: Incapable; producing nonconforming product.

## Tool Invocations
All SPC calculations must be executed via `quality-mcp`.

### `calculate_spc_chart`
Calculates control chart limits, detects run-rule violations, assesses process stability, and computes stability-gated capability indices.

```json
{
  "name": "calculate_spc_chart",
  "arguments": {
    "chart_type": "Xbar-R",
    "data": [
      [10.1, 10.0, 9.9, 10.2, 9.8],
      [9.9, 10.1, 10.0, 10.0, 10.1],
      [10.2, 9.8, 10.1, 9.9, 10.0]
    ],
    "usl": 11.0,
    "lsl": 9.0,
    "rule_set": "Western Electric"
  }
}
```

#### Parameters
- `chart_type` (string, required): `"Xbar-R"`, `"Xbar-S"`, `"I-MR"`, `"p"`, `"c"`, or `"u"`.
- `data` (list, required): Subgroups (`list[list[float]]` for Xbar-R / Xbar-S) or individual values/counts (`list[float]` for I-MR, p, c, u).
- `usl` (float, optional): Upper Specification Limit.
- `lsl` (float, optional): Lower Specification Limit.
- `sample_sizes` (list of floats, optional): Inspection sample sizes per subgroup (required for `p` and `u` charts).
- `rule_set` (string, optional): `"Western Electric"` (default) or `"Nelson"`.

#### Return Schema
```json
{
  "chart_type": "Xbar-R",
  "basis": "AIAG SPC 4th Edition",
  "center_line": 10.015,
  "ucl": 10.232,
  "lcl": 9.798,
  "dispersion_center": 0.375,
  "ucl_dispersion": 0.793,
  "lcl_dispersion": 0.0,
  "sigma_hat": 0.1612,
  "points": [10.0, 10.02, ...],
  "dispersion_points": [0.4, 0.2, ...],
  "violations": [],
  "in_control": true,
  "stable": true,
  "stability_note": null,
  "capability": {
    "cp": 2.067,
    "cpk": 2.036,
    "pp": 2.085,
    "ppk": 2.054,
    "mean": 10.015,
    "sigma_hat": 0.1612,
    "sigma_overall": 0.1599,
    "n": 20,
    "pp_ci": [1.534, 2.834],
    "ppk_ci": [1.442, 2.666],
    "ppk_lower": 1.543
  }
}
```

## Best Practices
- **Strictly Prohibit Inline Calculation:** Never write Python code to calculate means, standard deviations, control limits, factors ($A_2, D_4$), or capability formulas ($C_{pk}$). Route all quantitative steps to `calculate_spc_chart`.
- **Enforce Stability Before Capability:** Never report capability figures when `in_control == False`. Explain the instability and guide root-cause triage.
- **Verify Rational Subgrouping:** Confirm that sample subgroups capture short-term variation within subgroups and long-term variation between subgroups.
- **Check Dispersion Chart First:** In $\bar{X}\text{-}R$ and $\bar{X}\text{-}S$ charts, verify that the Range or $s$ chart is in control before interpreting the Mean ($\bar{X}$) chart, as $\bar{X}$ limits depend on process dispersion stability.
- **Document Confidence Intervals:** When presenting capability ($P_p, P_{pk}$), include the Bissell and $\chi^2$ confidence intervals provided in the tool response to communicate statistical uncertainty based on sample size ($n$).

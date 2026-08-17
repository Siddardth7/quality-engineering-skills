---
name: msa-gauge-rr
description: Measurement Systems Analysis (MSA) Gage R&R study design, ANOVA and Average-and-Range evaluation, and AIAG acceptance interpretation routing all calculations to calculate_gage_rr on quality-mcp.
---

# Measurement Systems Analysis (MSA): Crossed Gage R&R & AIAG Acceptance

## Overview
The `msa-gauge-rr` skill guides AI agents in planning, executing, and evaluating crossed Gage Repeatability and Reproducibility (Gage R&R) studies according to the **AIAG Measurement Systems Analysis (MSA) Reference Manual (4th Edition)**.

Measurement Systems Analysis quantifies the amount of variation contributed by the measurement process itself relative to the total process variation and product tolerance specifications. Observed total variation in manufacturing data is the sum of actual part-to-part process variation and measurement system variation:

$$\sigma^2_{\text{total}} = \sigma^2_{\text{process}} + \sigma^2_{\text{measurement}}$$

The primary purpose of a Gage R&R study is to decompose measurement error into two fundamental components:
1. **Equipment Variation (EV / Repeatability):** The inherent precision or short-term within-system variation observed when a single operator measures the identical characteristic on the same part multiple times using the same gauge.
2. **Appraiser Variation (AV / Reproducibility):** The between-operator variation observed when different appraisers measure the identical characteristic on the same parts using the same gauge.

This skill equips agents to:
- Guide quality engineers in designing balanced, randomized crossed Gage R&R studies.
- Delegate all variance component estimations, K-constant adjustments, ANOVA sums of squares decompositions, interaction F-tests, and number of distinct categories ($ndc$) determinations to the deterministic `calculate_gage_rr` FastMCP tool on `quality-mcp`.
- Interpret AIAG acceptance verdicts and provide actionable engineering recommendations for gauge qualification, repair, operator retraining, or fixture redesign.

## When to Use
Activate this skill in the following quality engineering scenarios:
- **New Gauge / Instrument Qualification:** Verifying that a newly purchased, modified, or relocated measurement fixture meets AIAG measurement capability requirements prior to production release.
- **Production Part Approval Process (PPAP / APQP Element):** Generating standard Gage R&R verification evidence for Customer Engineering submissions.
- **Pre-SPC / Pre-Capability Screening:** Verifying measurement system adequacy before collecting control chart data or conducting process capability studies ($C_p, C_{pk}, P_p, P_{pk}$). If measurement error is high (%GRR > 30% or $ndc < 5$), control charts will display false alarms or mask true out-of-control conditions.
- **Root Cause Investigation of High Process Variation:** Determining whether unexpected process capability drops or out-of-spec readings are caused by manufacturing process shifts versus gauge degradation or operator measurement inconsistency.
- **Gauge Calibration & Preventative Maintenance Review:** Evaluating measurement system drift or wear over time across different shifts and operators.

### Input Requirements
To execute a Gage R&R analysis, collect the following domain inputs:
- **Measurement Study Data:** List of measurement records with keys `part` (str), `appraiser` (str), `trial` (int $\ge 1$), and `measurement` (float numeric observed value).
- **Study Layout:** Recommended AIAG standard crossed layout (10 parts $\times$ 3 appraisers $\times$ 3 trials = 90 measurements), or valid minimal crossed layout ($\ge 2$ parts $\times \ge 2$ appraisers $\times \ge 2$ trials). Must be balanced (identical trial count per part-appraiser cell).
- **Engineering Specification Tolerance (Optional):** Upper Specification Limit minus Lower Specification Limit ($\text{USL} - \text{LSL}$). When supplied, %GRR, %EV, %AV, and %PV are evaluated against process tolerance using the AIAG $6\sigma$ study variation multiplier.
- **Analysis Method:** `"anova"` (recommended; crossed two-factor ANOVA with part $\times$ appraiser interaction test at $\alpha = 0.05$ and auto-pooling) or `"average_and_range"` (classical range method without interaction estimation).

### Prerequisites
- Active `quality-mcp` server connection providing the `calculate_gage_rr` tool.

## Step-by-Step Methodology
Follow the 5-step MSA Gage R&R analysis framework:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     5-STEP AIAG MSA METHODOLOGY                        │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Study Design & Sampling       │ Select parts spanning process spread│
│ 2. Blind Randomized Execution    │ Randomize part order across trials  │
│ 3. Tool Invocation               │ Call calculate_gage_rr on MCP       │
│ 4. Decomposition Audit           │ Review EV, AV, INT, %GRR, and ndc   │
│ 5. AIAG Decision & Action Plan   │ Accept, Marginal (evaluate), Reject │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Study Design & Part Sampling
Ensure the study design satisfies AIAG standards:
- **Part Selection:** Select 10 parts representing the full expected range of process variation (including parts near lower, nominal, and upper process boundaries). Do not select consecutive parts or master standards only; part variation ($PV$) must reflect true production spread.
- **Appraiser Selection:** Select 2 to 3 operators who normally operate the gauge in daily production.
- **Replication Count:** Plan for 2 to 3 repeated trials per appraiser per part.

### 2. Step 2: Blind Randomized Data Collection
To prevent operator memory bias:
- Number parts discretely on non-visible surfaces.
- Present parts to each operator in a randomized order within each trial.
- Record readings without allowing operators to observe previous measurement results or peer readings.

### 3. Step 3: Tool Invocation
Delegate all mathematical computation to `calculate_gage_rr`. Pass the structured study records, the desired method (`"anova"` or `"average_and_range"`), and the engineering tolerance if available.

### 4. Step 4: Metric Audit & Decomposition Review
Examine the returned metrics:
- **ANOVA Interaction ($F_{\text{int}}$ and $p$-value):** Check `interaction_significant`. If significant, operator measurement techniques differ depending on part geometry, surface finish, or clamping location.
- **Equipment Variation vs Appraiser Variation:**
  - If $EV \gg AV$: Gauge hardware issues (instrument resolution, clamping play, probe wear, thermal drift).
  - If $AV \gg EV$: Operator technique differences (sight alignment, parallax error, clamping force, training gaps).
- **Number of Distinct Categories ($ndc$):** Represents the number of non-overlapping confidence intervals the gauge can distinguish across the part variation range ($1.41 \times PV / GRR$).
  - $ndc \ge 5$: Adequate discrimination for process control and capability analysis.
  - $ndc < 5$: Inadequate resolution; gauge cannot reliably distinguish process variation.

### 5. Step 5: AIAG Acceptance Interpretation & Action Plan
Interpret the overall acceptance verdict based on AIAG MSA 4th Edition criteria:

| Metric | Threshold | AIAG Category | Action Required |
|---|---|---|---|
| **%GRR** | $< 10.0\%$ | **Acceptable** | Measurement system is fully capable. Approved for production and SPC monitoring. |
| **%GRR** | $10.0\% \le \%\text{GRR} \le 30.0\%$ | **Marginal / Conditionally Acceptable** | May be acceptable based on application importance, gauge cost, or customer agreement. Action plan recommended for critical characteristics. |
| **%GRR** | $> 30.0\%$ | **Unacceptable (Reject)** | Measurement system requires improvement. Identify root cause ($EV$ vs $AV$ vs Interaction), repair/replace gauge, or retrain operators before release. |
| **$ndc$** | $\ge 5$ | **Adequate Discrimination** | Capable of detecting process shifts and estimating $C_p / C_{pk}$. |
| **$ndc$** | $< 5$ | **Inadequate Discrimination** | Insufficient measurement resolution. Withhold capability claims. |

## Tool Invocations
All Gage R&R calculations must be executed via `quality-mcp`.

### `calculate_gage_rr`
Calculates crossed Gage R&R variance components ($EV, AV, GRR, PV, TV$), study-variation and tolerance-basis percentages, $ndc$, and AIAG acceptance verdicts.

```json
{
  "name": "calculate_gage_rr",
  "arguments": {
    "measurements": [
      {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.054},
      {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.048},
      {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.057},
      {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.068},
      {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.112},
      {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 10.109},
      {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 10.133},
      {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 10.118}
    ],
    "method": "anova",
    "tolerance": 0.5
  }
}
```

### Response Schema & Key Fields
- `basis`: Standards attribution (`"AIAG MSA 4th Edition"`).
- `ev`: Equipment Variation (Repeatability standard deviation).
- `av`: Appraiser Variation (Reproducibility standard deviation).
- `grr`: Combined Gage R&R standard deviation.
- `pv`: Part Variation standard deviation.
- `tv`: Total Variation standard deviation.
- `pev_study`, `pav_study`, `pgrr_study`, `ppv_study`: Percentages of total study variation ($100 \times \text{Component} / TV$).
- `pev_tolerance`, `pav_tolerance`, `pgrr_tolerance`, `ppv_tolerance`: Percentages of product tolerance ($100 \times 6 \times \text{Component} / \text{Tolerance}$).
- `ndc`: Number of Distinct Categories (integer).
- `verdict`: AIAG acceptance evaluation (`"Accept"`, `"Marginal"`, `"Reject"`).
- `interaction`, `interaction_f`, `interaction_significant`: ANOVA interaction evaluation metrics.

## Best Practices
1. **Never Calculate Metrics Inline:** Strictly avoid computing means, ranges, standard deviations, sums of squares, or F statistics in prompt context. Delegate all analysis to `calculate_gage_rr`.
2. **Prioritize ANOVA over Average-and-Range:** Always default to `"anova"`. ANOVA isolates the part $\times$ appraiser interaction term, whereas Average-and-Range absorbs interaction into repeatability and biases %GRR low when interactions exist.
3. **Always Qualify Measurement Systems Before SPC:** An out-of-control signal on a control chart or low $C_{pk}$ can stem from an inadequate measurement system ($ndc < 5$ or %GRR > 30%). Verify gauge capability first.
4. **Use True Production Parts:** Do not calibrate or evaluate Gage R&R using lab artifacts or gauge blocks alone; parts must span the natural operating variation of the manufacturing process.
5. **Enforce Balance:** Ensure all part-appraiser cells have identical trial counts. Unbalanced designs violate classical ANOVA assumptions and cause `calculate_gage_rr` to return structured validation errors.

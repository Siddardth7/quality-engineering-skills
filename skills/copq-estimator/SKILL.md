---
name: copq-estimator
description: Deterministic Cost of Poor Quality (COPQ) financial estimator over the PAF (Prevention-Appraisal-Failure) model.
---

# Cost of Poor Quality (COPQ) Financial Estimator

## Overview

The **Cost of Poor Quality (COPQ) Estimator** provides deterministic financial quantification of quality nonconformances, defects, and appraisal/prevention activities using the classical **Prevention-Appraisal-Failure (PAF)** cost accounting model.

Developed originally by Armand Feigenbaum and Joseph Juran and codified in the **ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge** and the **Council for Six Sigma Certification (CSSC) Lean Six Sigma Manual (2018)**, Cost of Quality (CoQ) categorizes quality-related expenditures into four distinct quadrants:

1. **Prevention Costs:** Investments made to avoid nonconformances, errors, and defects upstream (e.g., APQP quality planning, DFM reviews, poka-yoke error-proofing, operator training, supplier capability audits).
2. **Appraisal Costs:** Expenses incurred to measure, audit, or evaluate products and processes to assure conformance to standards (e.g., receiving inspection, CMM dimensional checks, in-process AOI testing, gage calibration, laboratory analysis).
3. **Internal Failure Costs:** Waste and losses resulting from defects identified *prior* to delivery or transfer to the customer (e.g., scrap, rework labor and added materials, sorting/containment, retesting, production downtime).
4. **External Failure Costs:** Losses and liabilities resulting from defects identified *after* shipment or customer delivery (e.g., warranty claims, customer returns, product recalls, field service, price concessions / deviations).

### Core Financial Formulas

- **Cost of Poor Quality (COPQ):**
  $$\text{COPQ} = \text{Internal Failure Costs} + \text{External Failure Costs}$$
- **Cost of Good Quality (CoGQ) / Conformance Cost:**
  $$\text{CoGQ} = \text{Prevention Costs} + \text{Appraisal Costs}$$
- **Total Cost of Quality (CoQ):**
  $$\text{Total CoQ} = \text{COPQ} + \text{CoGQ} = \text{Prevention} + \text{Appraisal} + \text{Internal Failure} + \text{External Failure}$$
- **COPQ Percentage of Revenue / Sales:**
  $$\text{COPQ \%} = \left(\frac{\text{COPQ}}{\text{Total Revenue}}\right) \times 100$$

> [!IMPORTANT]
> **Zero Inline Math Invariant:** AI agents must **never** execute arithmetic or evaluate formulas inside prompts or chat outputs. All cost rollups, driver multiplications, and revenue percentage calculations **must** be executed via the deterministic `estimate_copq` MCP tool.

---

## When to Use

### Use When:
- Quantifying the financial impact of nonconformance reports (NCRs), scrap spikes, or customer warranty escapes.
- Building a business case for Six Sigma DMAIC projects, Kaizen events, or capital poka-yoke investments.
- Performing Pareto cost ranking across multiple nonconformance items to identify the top 20% of defects driving 80% of losses.
- Calculating COPQ as a percentage of sales revenue for executive quality reviews.
- Evaluating the balance between Conformance Investments (Prevention + Appraisal) and Failure Costs.

### Do NOT Use When:
- Drafting descriptive nonconformance statements (use [`ncr-writing`](../ncr-writing/SKILL.md) instead).
- Performing root-cause drill-downs or 5-Why analysis (use [`5why-root-cause`](../5why-root-cause/SKILL.md) or [`fishbone-analysis`](../fishbone-analysis/SKILL.md)).
- Developing operational Control Plans (use [`control-plan`](../control-plan/SKILL.md)).

---

## Step-by-Step Methodology

### Step 1: Collect Defect Cost Drivers
Gather objective shop-floor and financial accounting facts:
- **Scrap:** Scrap quantity and standard unit manufacturing cost.
- **Rework:** Labor hours spent, direct shop labor rate ($/hr), and replacement material cost.
- **Containment:** Sorting and 100% inspection hours.
- **Downtime:** Line/cell stoppage hours and downtime hourly rate.
- **Warranty:** Claim count and average field service/replacement unit cost.
- **Returns & Concessions:** Customer return quantity or price concession discount.

### Step 2: Ingest Itemized PAF Records or Parameters
Format inputs as either:
1. Direct keyword arguments for single nonconformance incidents (`scrap_qty`, `unit_cost`, `rework_hours`, `labor_rate`, etc.).
2. Itemized dictionary records containing PAF categories (`Prevention`, `Appraisal`, `InternalFailure`, `ExternalFailure`).

### Step 3: Execute `estimate_copq` MCP Tool
Call `estimate_copq` on the `quality-mcp` server. Inspect the structured financial breakdown:
- Verify `total_copq`, `cogq_total`, and `total_coq`.
- Check `failure_cost_ratio` to assess internal vs external failure split.
- Check `copq_percentage_of_revenue` if `revenue_base` was supplied.

### Step 4: Render Interactive Visual Canvas
Call `render_copq_canvas` to generate styled HTML Pareto tables and proportional PAF distribution waterfall charts for presentation.

---

## Tool Invocations

### 1. `estimate_copq`
Calculates PAF financial metrics and failure cost ratios.

```json
{
  "scrap_qty": 45,
  "unit_cost": 120.0,
  "rework_hours": 35.0,
  "labor_rate": 65.0,
  "added_material_cost": 450.0,
  "sort_hours": 40.0,
  "warranty_units": 12,
  "warranty_cost_per_unit": 850.0,
  "prevention_cost": 7300.0,
  "appraisal_cost": 11300.0,
  "revenue_base": 500000.0,
  "title": "Plant 1 Q3 COPQ Financial Rollup"
}
```

**Output Structure:**
```json
{
  "title": "Plant 1 Q3 COPQ Financial Rollup",
  "total_copq": 22325.0,
  "internal_failure_total": 12125.0,
  "external_failure_total": 10200.0,
  "prevention_total": 7300.0,
  "appraisal_total": 11300.0,
  "cogq_total": 18600.0,
  "total_coq": 40925.0,
  "copq_percentage_of_revenue": 4.465,
  "revenue_base": 500000.0,
  "failure_cost_ratio": {
    "internal_failure_pct": 54.31,
    "external_failure_pct": 45.69
  },
  "cost_breakdown": {
    "internal_failure": {
      "scrap": 5400.0,
      "rework": 2725.0,
      "containment": 1800.0,
      "retest": 0.0,
      "downtime": 0.0,
      "itemized_additional": 0.0,
      "total": 12125.0
    },
    "external_failure": {
      "warranty": 10200.0,
      "returns": 0.0,
      "recall": 0.0,
      "concessions": 0.0,
      "itemized_additional": 0.0,
      "total": 10200.0
    },
    "prevention": {
      "direct": 7300.0,
      "itemized": 0.0,
      "total": 7300.0
    },
    "appraisal": {
      "direct": 11300.0,
      "itemized": 0.0,
      "total": 11300.0
    }
  },
  "item_count": 0,
  "warnings": [],
  "recommendations": [],
  "standards_basis": "ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge / PAF Model (Feigenbaum & Juran) / CSSC Lean Six Sigma Manual (2018)"
}
```

### 2. `render_copq_canvas`
Renders an interactive HTML canvas with KPI badges, PAF proportional distribution bar, and Pareto item ranking.

```json
{
  "revenue_base": 500000.0,
  "title": "Manufacturing Operations COPQ Canvas",
  "standalone": true
}
```

---

## Best Practices

1. **Zero Inline Math Invariant:** Never estimate or multiply cost figures manually. Always invoke `estimate_copq`.
2. **True Labor Burdening:** When supplying `labor_rate`, use standard burdened manufacturing labor rates ($/hr including fringe and direct overhead) to avoid underestimating rework and sorting losses.
3. **Shift Upstream (Failure to Prevention):** High COPQ (especially External Failure) signals an over-reliance on downstream inspection. Quality leaders recommend shifting capital into Prevention (Poka-Yoke, DFMEA, PFMEA, Capability Studies) where defect eradication costs orders of magnitude less (1-10-100 Rule).
4. **Distinguish Conformance vs Nonconformance:** Keep Prevention and Appraisal (Cost of Good Quality) strictly segregated from Internal and External Failure (Cost of Poor Quality).
5. **Standards Fidelity:** All calculations follow the ASQ CSSGB BoK PAF framework and CSSC 2018 guidelines.

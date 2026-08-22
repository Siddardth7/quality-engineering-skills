---
name: ncr-writing
description: Deterministic ISO 9001:2015 §8.7 nonconformance statement drafting and IATF 16949:2016 §8.7 disposition recommendation routing all phrasing, blame filtering, and disposition decisions to write_ncr, recommend_disposition, and render_ncr_canvas on quality-mcp.
---

# Nonconformance Reporting (NCR): ISO 9001 §8.7 Objective Evidence & IATF 16949 §8.7 Dispositioning

## Overview
The `ncr-writing` skill guides AI agents in capturing, structuring, rewriting, and dispositioning Nonconformance Reports (NCR) in strict accordance with **ISO 9001:2015 Clause 8.7 ("Control of nonconforming outputs")** and **IATF 16949:2016 Clause 8.7 ("Control of nonconforming outputs")**.

A Nonconformance Report is a formal quality control document that records an identified deviation from specified engineering drawings, standard operating procedures, purchase orders, or customer contractual requirements. Under international quality standards, nonconformance capture must remain rigorously objective, verifiable, and strictly segregated from root cause speculation and personnel fault attribution.

Key standards-based foundations include:
1. **Objective-Evidence Phrasing (ISO 9001:2015 §8.7.2):** Nonconformance records must retain documented information that objectively describes the nonconformity, the actions taken, concessions obtained, and the deciding authority. Every statement must articulate:
   - **What deviated:** The observed nonconforming condition on the product/lot.
   - **Requirement violated:** The specific engineering drawing, specification limit, or standard.
   - **Measured evidence:** Quantitative or qualitative inspection findings (e.g. *"12.45 mm vs 12.00 ± 0.10 mm"*).
   - **Quantity affected:** Total count or batch volume of nonconforming/suspect material.
   - **Detection point:** The manufacturing operation, cell, or inspection station where identified.
2. **Strict Elimination of Operator Blame (Zero Human Fault):** Per ASQ Quality Toolbox and Ford Global 8D principles, nonconformance statements must describe physical output conditions, never operator carelessness or personnel mistakes (*"operator forgot"*, *"worker error"*). Personnel factors belong strictly in systemic RCA, not the initial defect record.
3. **Segregation of Root Cause Speculation:** An NCR records *what* deviated, not *why* it deviated. Speculative causal explanations (*"due to worn tooling"*, *"caused by bad vendor material"*) must be stripped from the statement and routed to the RCA suite (5-Why, Fishbone, KT Is/Is-Not).
4. **Canonical Disposition Taxonomy (ISO 9001 §8.7.1 & IATF 16949 §8.7):** Nonconforming product must be controlled via one of 5 standard dispositions:
   - **`Scrap`:** Product cannot be reworked to specification or rework cost exceeds part value; must be rendered unusable prior to disposal per IATF 16949 §8.7.1.7.
   - **`Rework`:** Product can be corrected to meet original specification per ISO 9001 §8.7.1(a); requires FMEA risk analysis prior to rework per IATF 16949 §8.7.1.4.
   - **`UseAsIs`:** Deviation does not impair fit, form, function, or safety; requires documented Material Review Board (MRB) review and Customer Concession authorization per ISO 9001 §8.7.1(d) and IATF 16949 §8.7.1.1.
   - **`ReturnToVendor` (RTV):** Nonconformance originated from external supplier/vendor; product segregated for return per ISO 9001 §8.7.1(b).
   - **`Regrade`:** Product does not meet primary specification but satisfies an authorized secondary grade specification per IATF 16949 §8.7.1.7.
5. **No Silent Disposition Guessing (Negative Control):** Ambiguous or incomplete defect information must never yield an automated guess; the engine returns `INSUFFICIENT_DATA` and mandates MRB fact-finding.

This skill equips agents to:
- Convert rough, colloquial, or blaming defect notes into professional ISO 9001 §8.7 objective-evidence statements.
- Recommend defensible, standards-cited dispositions with required approval authorities and risk analysis flags.
- Generate single-writer visual HTML NCR cards and logs.
- Delegate all deterministic statement formatting, blame filtration, and disposition routing to `write_ncr`, `recommend_disposition`, and `render_ncr_canvas` on `quality-mcp`.

## When to Use
Activate this skill in the following quality engineering and shop-floor scenarios:
- **Shop-Floor Defect Logging:** Rewriting rough inspection notes or operator callouts into clean ISO 9001 §8.7 nonconformance statements.
- **Receiving / Incoming Inspection:** Processing nonconforming purchased lots, segregating suspect material, and recommending `ReturnToVendor` with SCAR escalation.
- **Material Review Board (MRB) Governance:** Evaluating nonconforming batches for technical rework feasibility, customer concession eligibility (`UseAsIs`), or secondary grade downgrade (`Regrade`).
- **Scrap Authorization & Defacing Verification:** Recommending scrap disposition and ensuring compliance with IATF 16949 §8.7.1.7 rendering-unusable mandates.
- **NCR Visual Reporting:** Rendering dark/light HTML statement cards and summary metrics for quality dashboards and audit documentation.

### Input Requirements
- **Defect Description / Raw Note (`raw_defect_note` or `what_deviated`):** Text description of observed defect.
- **Requirement Violated (`requirement_violated`):** Drawing dimension, tolerance, or standard clause.
- **Measured Evidence (`measured_evidence`):** Actual measured values vs nominal limits.
- **Quantity Affected (`quantity_affected`):** Integer count of affected or suspect parts.
- **Detection Point (`detection_point`):** Station, line, or inspection area.
- **Disposition Routing Attributes:** `is_reworkable` (`bool`), `defect_origin` (`str`), `meets_secondary_spec` (`bool`), `customer_concession_eligible` (`bool`), `rework_cost` (`float`), `part_value` (`float`), `safety_critical` (`bool`).

### Prerequisites
- Active `quality-mcp` server connection providing `write_ncr`, `recommend_disposition`, and `render_ncr_canvas` tools.

## Step-by-Step Methodology
Follow the 5-step nonconformance handling and documentation methodology:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   5-STEP NCR WRITING & DISPOSITION METHODOLOGY         │
├──────────────────────────────────┬─────────────────────────────────────┤
│ 1. Evidence Collection           │ Gather measured facts, spec & qty   │
│ 2. Objective Statement Drafting  │ Execute write_ncr on MCP            │
│ 3. Deterministic Disposition     │ Execute recommend_disposition       │
│ 4. Authority & MRB Gating        │ Verify approvals & FMEA risk checks │
│ 5. Canvas Rendering & Storage    │ Render visual card via render_ncr   │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Evidence Collection & Fact Gathering
- Gather the physical evidence: affected part/lot ID, the violated drawing requirement or specification, quantitative gauge/CMM readings, affected batch quantity, and detection point.
- Note whether the defect was introduced internally or supplied externally.

### 2. Step 2: Objective Statement Formulation
- Invoke `write_ncr` on `quality-mcp` passing the raw notes and structured parameters.
- *Strict Invariant:* Never write or sanitize nonconformance statements manually in prompt text. All statement drafting, blame detection, and speculation filtering must execute through `write_ncr`.
- Check `valid` and review `blame_phrases_detected` and `speculation_detected`. If premature causes were detected, route root cause investigation to the RCA suite (5-Why / Fishbone).

### 3. Step 3: Deterministic Disposition Evaluation
- Invoke `recommend_disposition` on `quality-mcp` with technical facts (`is_reworkable`, `defect_origin`, `customer_concession_eligible`, `meets_secondary_spec`, `rework_cost`, `part_value`, `safety_critical`).
- *Strict Invariant:* Never adjudicate or guess a disposition inline. All disposition logic must execute through `recommend_disposition`.
- If `verdict == "INSUFFICIENT_DATA"`, do not assume a disposition; convene the Material Review Board to determine the missing facts listed in `missing_evidence`.

### 4. Step 4: Approval Authority & Risk Analysis Gating
Examine the returned disposition payload:
- **`Scrap`:** Route to Quality Manager. Enforce IATF 16949 §8.7.1.7 defacing/destruction prior to disposal.
- **`Rework`:** Route to Manufacturing & Quality Engineering. Enforce mandatory FMEA risk analysis per IATF 16949 §8.7.1.4 before reworking.
- **`UseAsIs`:** Route to MRB. Require formal customer concession authorization per IATF 16949 §8.7.1.1 prior to product release.
- **`ReturnToVendor`:** Route to Supplier Quality Assurance / Purchasing. Issue SCAR.
- **`Regrade`:** Route to MRB & Customer Approval. Transfer to secondary grade stock.

### 5. Step 5: Visual Canvas Generation & Documentation
- Invoke `render_ncr_canvas` on `quality-mcp` to generate a responsive, styled HTML statement card and summary log.
- Retain documented information in quality records per ISO 9001:2015 §8.7.2.

## Tool Invocations

### `write_ncr`
```json
{
  "raw_defect_note": "Operator forgot to check tool wear, 45 shafts turned at 35.035 mm exceeding drawing spec 35.000 +0.005/-0.000 mm at turning cell 3.",
  "part_lot_id": "LOT-SHAFT-4410",
  "requirement_violated": "DWG-35: 35.000 +0.005/-0.000 mm",
  "measured_evidence": "35.035 mm (+0.030 mm oversized)",
  "quantity_affected": 45,
  "detection_point": "Turning Cell 3 In-Process Gauge"
}
```

### `recommend_disposition`
```json
{
  "is_reworkable": true,
  "defect_origin": "Internal",
  "rework_cost": 2.50,
  "part_value": 45.00,
  "severity": "Moderate",
  "safety_critical": false,
  "defect_description": "Shaft bearing journal oversized +0.030 mm above tolerance."
}
```

### `render_ncr_canvas`
```json
{
  "records": null,
  "title": "Plant 1 Automotive Machining Nonconformance Log",
  "standalone": true
}
```

## Best Practices
1. **Focus on the Nonconforming Characteristic:** Document what is out of specification with numerical readings, units of measure, and drawing limits.
2. **Strictly Blame-Free Phrasing:** Never reference individual operators, carelessness, or lack of attention in NCR documentation.
3. **No Premature Causal Claims:** Do not speculate on machine wear, vendor fault, or process breakdowns in the NCR; address root cause through structured 8D/5-Why.
4. **Mandatory Concession Permits:** Never release `UseAsIs` material without customer concession authorization when required by IATF 16949 §8.7.1.1.
5. **Scrap Destruction Witnessing:** Verify and record that scrapped items are rendered permanently unusable before disposal per IATF 16949 §8.7.1.7.

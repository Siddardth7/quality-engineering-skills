---
name: supplier-scar
description: Deterministic supplier PPM/OTIF/vendor-scorecard measurement, threshold-triggered escalation, and CQI-20/Ford Global 8D SCAR generation routing every metric, band, tier, and root-cause validation to calculate_supplier_ppm, calculate_otif, calculate_vendor_scorecard, evaluate_escalation, generate_scar, and render_sqe_canvas on quality-mcp.
---

# Supplier Corrective Action Request (SCAR) & Vendor Rating: Measured Performance, Evidenced Escalation, Supplier-Owned Root Cause

## Overview
The `supplier-scar` skill guides AI agents in measuring supplier performance, rating a supplier against organization-determined criteria, recommending an escalation tier, and issuing a structured Supplier Corrective Action Request. Five deterministic quantities are produced, and every one of them is produced by a tool on `quality-mcp`, never in prompt text: a supplier defect rate (PPM, and separately-named DPMO) via `calculate_supplier_ppm`; delivery performance (on-time, in-full, and the strict-conjunction OTIF) via `calculate_otif`; a weighted A/B/C vendor scorecard via `calculate_vendor_scorecard`; a threshold-triggered escalation tier via `evaluate_escalation`; and a CQI-20/Ford Global 8D SCAR via `generate_scar`. The already-evaluated results are presented as a supplier × dimension HTML matrix by `render_sqe_canvas`.

**ISO 9001:2015 §8.4** ("Control of externally provided processes, products and services"), **ISO 9001:2015 §10.2** ("Nonconformity and corrective action"), and **IATF 16949:2016 §8.4** require that external providers be evaluated, selected, monitored, and re-evaluated against *criteria the organization itself determines*, and that nonconformity drive corrective action — and they name **no** PPM threshold, no OTIF window, no in-full tolerance, no scorecard weight, no rating-band boundary, and no escalation trigger. Every such number in this platform is the platform's own declared **engineering heuristic**, caller-configurable, labelled `is_heuristic: true` in the tool payload, and recorded in `quality_core/sqe/ASSUMPTIONS_LOG.md` (RULE-SQE-001 through RULE-SQE-013). Presenting any of them to a supplier or an auditor as an ISO 9001 or IATF 16949 requirement is a fabrication.

**AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018)** and the **Ford Global 8D Manual** back the *structure* of the corrective-action ladder and the three rendered SCAR sections — **Root-Cause Requirement**, **Corrective-Action Requirement**, and **Prevention / Read-Across** — and nothing else. They do not supply the escalation ladder's numeric triggers, which are heuristics like every other threshold here.

**The supplier owns the root cause.** This skill and `generate_scar` never author, infer, or paraphrase one — they request it and validate the supplier's own response by dispatching it to `quality_core.rca`'s reversible 5-Why validator. A SCAR with no supplier response carries `root_cause: null` and can never reach `CLOSABLE`.

Two further authority boundaries hold throughout:
1. **Missing data is undecided, never zero.** A supplier with no receipts in the period is `INDETERMINATE`, not a 0 PPM "A" performer; a positively-weighted `INDETERMINATE` dimension suppresses the entire composite and band; an `INDETERMINATE` scorecard is neither escalated nor cleared.
2. **Commercial authority is not a quality-engineering verdict.** `evaluate_escalation` recommends a quality tier and always returns a `commercial_authority` disclaimer with it. New-business hold, de-sourcing, resourcing, and charge-back are business decisions made by authorized people, and this skill never states or implies one.

This skill equips agents to:
- Measure a supplier period from receipt lots and delivery records without ever quoting an unmeasured figure.
- Compose a defensible, fully heuristic-labelled vendor rating and a single highest evidenced escalation tier.
- Issue and track a CQI-20/Ford Global 8D SCAR whose root cause is supplied and validated, never authored.
- Delegate all measurement, scoring, adjudication, and rendering to `calculate_supplier_ppm`, `calculate_otif`, `calculate_vendor_scorecard`, `evaluate_escalation`, `generate_scar`, and `render_sqe_canvas` on `quality-mcp`.

## When to Use
Activate this skill in the following supplier quality scenarios:
- **Periodic Supplier Scorecarding:** Monthly/quarterly vendor rating reviews producing an A/B/C band and a supporting evidence trail.
- **Incoming-Receipt PPM Review:** Reviewing a supplier's defect rate over a receiving window from inspected receipt lots.
- **Delivery Performance Review:** Assessing on-time, in-full, and strict-conjunction OTIF performance against promised dates and ordered quantities.
- **Threshold-Triggered Escalation Decisions:** Determining the quality-engineering escalation tier evidenced by a rated scorecard (and, when the caller supplies one, a recurrence count).
- **Opening and Tracking a SCAR:** Issuing a structured corrective action request, receiving the supplier's root cause, validating it, and tracking the request toward closure.

### Input Requirements
- **Supplier Period (`period`):** `supplier_id`, `period_start`, `period_end` (inclusive window), optional `period_label`.
- **Receipt Lots (`lots`):** `supplier_id`, `lot_id`, `quantity_received`, `receipt_date`, `defect_count` (`null` = not yet counted, an undecided sentinel — never a zero), optional `opportunities_per_unit` (required on *every* in-scope lot for DPMO to be reported).
- **Delivery Records (`deliveries`):** `supplier_id`, `order_id`, `quantity_ordered`, `quantity_delivered`, optional `requested_date`, `promised_date`, `actual_delivery_date`.
- **Cost Dimension (optional):** `copq_items` plus a `revenue_base`, only when the caller has configured a positive cost weight and a cost curve.
- **SCAR Request (`request`):** `supplier_id`, `issue_description`, optional `scar_id`, `linked_ncr_id`, `date_issued`, `due_date`, `requested_by`.
- **SCAR Evidence (optional):** `linked_ncr_evidence`, `supplier_root_cause_evidence` (the supplier's own 5-Why chain), `cost_impact_evidence`, and a `verification_of_effectiveness` statement.

### Prerequisites
- Active `quality-mcp` server connection providing `calculate_supplier_ppm`, `calculate_otif`, `calculate_vendor_scorecard`, `evaluate_escalation`, `generate_scar`, and `render_sqe_canvas`.

## Step-by-Step Methodology
Follow the 5-step supplier rating and corrective-action methodology:

```
┌─────────────────────────────────────────────────────────────────────────┐
│           5-STEP SUPPLIER SCAR & VENDOR RATING METHODOLOGY              │
├───────────────────────────────────┬─────────────────────────────────────┤
│ 1. Evidence Collection            │ Gather receipts, deliveries, period │
│ 2. Deterministic Measurement      │ Execute calculate_supplier_ppm /    │
│                                   │ calculate_otif on MCP               │
│ 3. Composite Rating               │ Execute calculate_vendor_scorecard  │
│ 4. Escalation & Corrective Action │ Execute evaluate_escalation /       │
│                                   │ generate_scar                       │
│ 5. Visual Canvas & Reporting      │ Render via render_sqe_canvas        │
└───────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Evidence Collection & Period Definition
- Establish the exact evaluation window (`period_start`, `period_end`) and the `supplier_id` the evidence belongs to; lots and deliveries are matched on both.
- Collect inspected receipt lots and delivery records. Leave a value undecided (`null`) when it is genuinely unknown — an uninspected lot's `defect_count` is `null`, never `0`.
- *Strict Invariant:* Never substitute, impute, or estimate a missing receipt date, defect count, promised date, or delivered quantity. The engines resolve undecided evidence to `INDETERMINATE` by design; that verdict is the answer, not an obstacle to work around.

### 2. Step 2: Deterministic Measurement
- Invoke `calculate_supplier_ppm` and `calculate_otif` on `quality-mcp` with the period and its evidence.
- *Strict Invariant:* Never compute a PPM, DPMO, on-time percentage, in-full percentage, or OTIF conjunction inline. All measurement must execute through `calculate_supplier_ppm` / `calculate_otif`, and every figure reported to the user must be quoted from the tool's returned payload.
- Read `verdict` first. On `INDETERMINATE`, quote the tool's `reason` and stop — do not report a rate.
- Read `sample_adequacy.meets_minimum` and the `warnings` list. A below-minimum received quantity is a signal to gather more evidence; the minimum itself is a declared heuristic with no standards basis.
- Treat `on_time_pct`, `in_full_pct`, and `otif_pct` as three separate figures. `otif_pct` is the strict conjunction (a delivery counts only when it is both on-time *and* in-full) and is never the average of the other two.

### 3. Step 3: Composite Rating
- Invoke `calculate_vendor_scorecard` on `quality-mcp` with the same period and evidence, plus `copq_items`/`revenue_base` when a cost dimension is configured.
- *Strict Invariant:* Never assign a composite score or an A/B/C band from memory, and never re-derive a sub-score from a raw metric. All scoring must execute through `calculate_vendor_scorecard`.
- If `verdict` is `INDETERMINATE`, report `composite_score: null` and `band: null` with the tool's `reason`: a positively-weighted undecided dimension suppresses the whole rating and its weight is never redistributed across the remaining dimensions.
- When quoting weights, curves, or band boundaries, quote them from `heuristic_configuration` together with their `is_heuristic` / `basis` labels — they are this platform's engineering heuristic, not a standards requirement.

### 4. Step 4: Escalation & Corrective Action
- Invoke `evaluate_escalation` on `quality-mcp` with the scorecard result, and a caller-supplied `recurrence_count` only when the user has actually stated one.
- *Strict Invariant:* Never assign an escalation tier from memory and never state a commercial action as this skill's own recommendation. All escalation must execute through `evaluate_escalation`, and any root cause must come from the supplier via `generate_scar`'s linkage — never authored here.
- Present `evaluated_triggers` (the complete set, fired or not) alongside `selected_evidence` (only the winning tier's triggers), and repeat the returned `commercial_authority` disclaimer verbatim whenever a tier is communicated.
- Invoke `generate_scar` to issue the request. Route the supplier's returned 5-Why chain into `supplier_root_cause_evidence` and let the tool adjudicate it; if a linkage slot resolves `EVIDENCE_INVALID`, surface that sub-engine's own `findings` text unchanged.

### 5. Step 5: Visual Canvas & Reporting
- Invoke `render_sqe_canvas` on `quality-mcp` with the already-evaluated scorecard and escalation results — never with raw lots, deliveries, or metrics.
- The canvas performs no arithmetic and no adjudication; an `INDETERMINATE` supplier renders explicitly unrated rather than as a blank or zeroed cell.
- Retain the tool payloads alongside the rendered report so every published figure remains traceable to the call that produced it.

## Tool Invocations

### `calculate_supplier_ppm`
- **MCP Server:** `quality-mcp`
- **Purpose:** Deterministic supplier defect rate (PPM) and, when every in-scope lot carries an opportunity count, DPMO for one supplier period from receipt lots. A zero denominator, an undated in-scope lot, or an undecided `defect_count` resolves `INDETERMINATE` with `ppm: null` — never `0.0`.
- **Parameters:**
  - `period` (`dict[str, Any]`, required): Supplier identity and inclusive window.
    - `supplier_id` (`string`, required): Supplier identifier; lots are matched on it exactly.
    - `period_start` (`string`, required): ISO-8601 window start (inclusive).
    - `period_end` (`string`, required): ISO-8601 window end (inclusive).
    - `period_label` (`string | null`, optional): Human-facing label such as `"2026-07"`.
  - `lots` (`list[dict[str, Any]]`, optional, default `[]`): Receipt lots — `supplier_id`, `lot_id`, `quantity_received`, `receipt_date`, `defect_count` (`null` = undecided), `opportunities_per_unit`.
  - `config` (`dict[str, Any] | null`, optional): `sample_adequacy_minimum` (`integer`, default `1000`) — a declared engineering heuristic labelled `is_heuristic: true`, with no standards basis.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `supplier_id`, `period_start`, `period_end`, `period_label`: Echoed period identity.
  - `verdict` (`string`): `"MEASURED"` or `"INDETERMINATE"`.
  - `ppm` (`float | null`): Defect rate in parts per million; `null` on every `INDETERMINATE` verdict.
  - `numerator` (`integer | null`): Total defective units counted; `null` when undecided.
  - `denominator` (`integer`): Total in-scope received quantity; always reported.
  - `lot_count` (`integer`): Number of in-scope receipt lots; always reported.
  - `dpmo` (`float | null`): Defects per million opportunities; `null` unless every in-scope lot carries `opportunities_per_unit`.
  - `dpmo_opportunity_count` (`integer | null`): Total opportunities behind `dpmo`.
  - `sample_adequacy` (`dict`): `minimum`, `meets_minimum`, `is_heuristic`, `basis`.
  - `reason` (`string | null`): The engine's own explanation of an `INDETERMINATE` verdict.
  - `warnings` (`list[string]`), `recommendations` (`list[string]`): Engine-authored guidance.
  - `standards_basis` (`string`): Explicit statement that no published standard defines this arithmetic or threshold.

---

### `calculate_otif`
- **MCP Server:** `quality-mcp`
- **Purpose:** On-time, in-full, and strict-conjunction OTIF delivery performance for one supplier period. `otif_pct` counts a delivery only when it is on-time **and** in-full; it is never an average of `on_time_pct` and `in_full_pct`. No matched delivery, or any absent date or undecided delivered quantity, resolves the whole period `INDETERMINATE`.
- **Parameters:**
  - `period` (`dict[str, Any]`, required): Same shape as `calculate_supplier_ppm`'s `period`.
  - `deliveries` (`list[dict[str, Any]]`, optional, default `[]`): Delivery records — `supplier_id`, `order_id`, `quantity_ordered`, `quantity_delivered` (`null` = undecided), `requested_date`, `promised_date`, `actual_delivery_date`.
  - `config` (`dict[str, Any] | null`, optional): `OTIFConfig` — `early_tolerance_days` (default `0`), `late_tolerance_days` (default `2`), `early_counts_as_on_time` (default `false`), `in_full_tolerance_pct` (default `0.0`), `over_delivery_counts_as_in_full` (default `true`). All five are declared engineering heuristics with no standards citation.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `supplier_id`, `period_start`, `period_end`, `period_label`: Echoed period identity.
  - `verdict` (`string`): `"MEASURED"` or `"INDETERMINATE"`.
  - `delivery_count` (`integer`): Matched deliveries — the single shared denominator of all three percentages.
  - `on_time_count`, `in_full_count`, `otif_count` (`integer | null`): Component counts.
  - `on_time_pct`, `in_full_pct` (`float | null`): The two component percentages, reported separately.
  - `otif_pct` (`float | null`): The **strict conjunction** percentage, derived from `otif_count`, not from the other two percentages.
  - `delivery_breakdown` (`list[dict]`): Per delivery — `order_id`, `is_on_time`, `is_in_full`, `is_otif`, `shortfall_qty`.
  - `heuristic_configuration` (`dict`): The five active config values plus `is_heuristic` and `basis`.
  - `reason` (`string | null`), `warnings` (`list[string]`), `recommendations` (`list[string]`), `standards_basis` (`string`).

---

### `calculate_vendor_scorecard`
- **MCP Server:** `quality-mcp`
- **Purpose:** Weighted composite of the PPM (quality) and OTIF (delivery) dimensions, plus an optional COPQ (cost) dimension, mapped to an A/B/C band. Each source engine is invoked once and stays authoritative for its own arithmetic. **Any positively weighted `INDETERMINATE` dimension suppresses the entire composite and band**, and its weight is never redistributed.
- **Parameters:**
  - `period` (`dict[str, Any]`, required): Same shape as above.
  - `lots` (`list[dict[str, Any]]`, optional): Receipt lots for the quality dimension.
  - `deliveries` (`list[dict[str, Any]]`, optional): Delivery records for the delivery dimension.
  - `copq_items` (`list[dict[str, Any]] | null`, optional): Cost-of-poor-quality items, delegated to the COPQ engine — never re-implemented here.
  - `revenue_base` (`float | null`, optional): Revenue base for the cost dimension's percentage-of-revenue metric.
  - `config` (`dict[str, Any] | null`, optional): `ScorecardConfig` — `quality_weight` (default `0.60`), `delivery_weight` (default `0.40`), `cost_weight` (default `0.0`, and a `cost_curve` is required when it is positive), `quality_curve` / `delivery_curve` / `cost_curve` (`best_value`, `worst_value`), `a_band_minimum` (default `90.0`), `b_band_minimum` (default `75.0`), plus nested `ppm_config` and `otif_config`. The three weights must sum to `1.0` or the tool raises. Every value is a declared engineering heuristic.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `supplier_id`, `period_start`, `period_end`, `period_label`: Echoed period identity.
  - `verdict` (`string`): `"RATED"` or `"INDETERMINATE"`.
  - `composite_score` (`float | null`): Sum of the weighted contributions; `null` when suppressed.
  - `band` (`string | null`): `"A"`, `"B"`, `"C"`, or `null` when suppressed.
  - `dimensions` (`list[dict]`): Per dimension — `name`, `source_metric_name`, `raw_metric`, `sub_score`, `weight`, `weighted_contribution`, `source_verdict`, `source_reason`, `source_evidence` (the source engine's own full payload), `warnings`, `recommendations`, `is_heuristic`, `basis`.
  - `heuristic_configuration` (`dict`): `weights`, `curves`, and `rating_bands`, each criterion individually labelled `is_heuristic` / `basis`.
  - `omitted_dimensions` (`list[dict]`): Dimensions carrying zero weight, with the reason they were not scored.
  - `reason` (`string | null`), `warnings` (`list[string]`), `recommendations` (`list[string]`).
  - `standards_basis` (`string`): States that ISO 9001:2015 §8.4 and IATF 16949:2016 §8.4 require supplier evaluation against organization-determined criteria and define no weight, curve, or band.

---

### `evaluate_escalation`
- **MCP Server:** `quality-mcp`
- **Purpose:** Recommend the single highest evidenced quality-engineering escalation tier — `NONE` → `MONITOR` → `SCAR_REQUIRED` → `CONTAINMENT_REQUIRED` → `EXECUTIVE_REVIEW`, or `INDETERMINATE` when the scorecard itself is `INDETERMINATE` (the supplier is then neither escalated nor cleared). Highest tier wins on ties. **Never a commercial disposition.**
- **Parameters:**
  - `scorecard` (`dict[str, Any]`, required): A `calculate_vendor_scorecard` result. Only a `RATED` or `INDETERMINATE` verdict is accepted.
  - `config` (`dict[str, Any] | null`, optional): `EscalationConfig` — `monitor_score_maximum` (default `89.0`), `scar_score_maximum` (default `74.0`), `containment_score_maximum` (default `59.0`), `executive_score_maximum` (default `39.0`), `monitor_recurrence_minimum` (default `1`), `scar_recurrence_minimum` (default `2`), `containment_recurrence_minimum` (default `3`), `executive_recurrence_minimum` (default `4`). All eight are declared engineering heuristics.
  - `recurrence_count` (`integer | null`, optional): Caller-supplied only; recurrence is never inferred, and its triggers are evaluated only when a count is actually supplied.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `supplier_id` (`string`), `tier` (`string`), `scorecard_verdict` (`string`).
  - `evaluated_triggers` (`list[dict]`): **The full set, fired or not** — each with `tier`, `metric`, `comparison`, `observed_value`, `threshold`, `fired`, `is_heuristic`, `basis`.
  - `selected_evidence` (`list[dict]`): **Only** the fired triggers belonging to the winning tier.
  - `recurrence_count` (`integer | null`), `reason` (`string | null`).
  - `heuristic_configuration` (`dict`): All eight thresholds, each labelled `is_heuristic` / `basis`.
  - `standards_basis` (`string`): AIAG CQI-20 backs the tier structure only, not the numeric thresholds.
  - `commercial_authority` (`string`): Always present — *"Any commercial response remains a business decision made by authorized people; this result recommends only a quality-engineering tier."*

---

### `generate_scar`
- **MCP Server:** `quality-mcp`
- **Purpose:** Generate a CQI-20/Ford Global 8D structured Supplier Corrective Action Request and adjudicate its linked evidence. The tool **requests and validates a supplier root cause and never authors, infers, or paraphrases one**: `root_cause` is only ever a verbatim copy of the terminal cause in a supplier-returned chain that `quality_core.rca` accepts.
- **Parameters:**
  - `request` (`dict[str, Any]`, required): `supplier_id`, `issue_description`, optional `scar_id`, `linked_ncr_id`, `date_issued`, `due_date`, `requested_by`. An empty request returns an `INDETERMINATE` SCAR naming the fields a usable request must carry; a non-empty request holding an invalid value returns a clean error.
  - `config` (`dict[str, Any] | null`, optional): `SCARConfig` — `evaluate_vendor_scorecard_linkage` (`bool`, default `true`).
  - `linked_ncr_evidence` (`dict[str, Any] | null`, optional): Nonconformance evidence, dispatched to `quality_core.ncr`.
  - `supplier_root_cause_evidence` (`dict[str, Any] | null`, optional): The supplier's own 5-Why chain, dispatched to `quality_core.rca`'s reversible validator.
  - `cost_impact_evidence` (`dict[str, Any] | null`, optional): Cost evidence, dispatched to `quality_core.copq`.
  - `verification_of_effectiveness` (`string | null`, optional): The supplier's stated verification; a blank statement normalises to `null` and never satisfies closure.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `supplier_id`, `scar_id`, `issue_description`: Echoed request identity.
  - `status` (`string`): `"DRAFT"`, `"ISSUABLE"`, `"AWAITING_SUPPLIER_RESPONSE"`, `"RESPONSE_REJECTED"`, `"CLOSABLE"`, or `"INDETERMINATE"`. `CLOSABLE` requires an accepted supplier root cause **and** a stated `verification_of_effectiveness` **and** no other linkage resolving `EVIDENCE_INVALID`.
  - `sections` (`list[dict]`): The three rendered sections — **Root-Cause Requirement** (`RULE-SQE-011`), **Corrective-Action Requirement** (`RULE-SQE-012`), **Prevention / Read-Across** (`RULE-SQE-013`) — each with `heading`, `rule_id`, `content`.
  - `linkage` (`dict`): Keyed `linked_ncr`, `supplier_root_cause`, `cost_impact`, `vendor_scorecard`; each slot carries `linkage_key`, `verdict` (`EVIDENCE_VALID` / `EVIDENCE_INVALID` / `EVIDENCE_NOT_SUPPLIED` / `LINKAGE_NOT_AVAILABLE`), `engine`, `findings` (the sub-engine's own text, verbatim), `rationale`, `raw_result`.
  - `root_cause` (`string | null`): The supplier's own words, or `null` until a chain `quality_core.rca` accepts is supplied.
  - `verification_of_effectiveness`, `due_date`, `date_issued` (`string | null`).
  - `reason` (`string | null`), `warnings` (`list[string]`), `recommendations` (`list[string]`), `standards_basis` (`string`).

---

### `render_sqe_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Render a single-writer HTML canvas presenting the supplier × dimension matrix — PPM, OTIF on-time/in-full, cost, composite score, band, and escalation tier. It performs **no arithmetic and no adjudication**: it presents already-computed results only, and an `INDETERMINATE` supplier renders explicitly unrated rather than as a blank cell.
- **Parameters:**
  - `rows` (`list[dict[str, Any]] | null`, optional): One entry per supplier — `supplier_id`, `scorecard` (a `calculate_vendor_scorecard` result), `escalation` (an `evaluate_escalation` result), optional `supplier_name`. Never raw lots, deliveries, or metrics.
  - `theme` (`string`, default `"dark"`): Colour theme palette (`"dark"` or `"light"`).
  - `standalone` (`boolean`, default `true`): If true, returns a standalone HTML5 document; if false, an embeddable container.
  - `title` (`string`, default `"SQE Vendor Scorecard Canvas"`): Canvas header title.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `title` (`string`): Canvas title.
  - `verdict` (`string`): `"RENDERED"`, or `"INDETERMINATE"` when `rows` was supplied as an empty list — zero supplier results is never presented as a supplier population with nothing wrong in it.
  - `reason` (`string | null`): The explanation of an `INDETERMINATE` verdict; `null` when rendered.
  - `rows_count` (`integer`): Number of supplier rows rendered.
  - `html` (`string`): Rendered HTML string.

---

### Example 1: Rated Supplier — PPM → OTIF → Scorecard → Escalation → SCAR

Every figure and verdict below is quoted from the tool response immediately above it. Nothing in this example is derived in prose.

#### Step 1 Invocation — `calculate_supplier_ppm`
```json
{
  "name": "calculate_supplier_ppm",
  "arguments": {
    "period": {
      "supplier_id": "SUP-4410",
      "period_start": "2026-07-01",
      "period_end": "2026-07-31",
      "period_label": "2026-07"
    },
    "lots": [
      {
        "supplier_id": "SUP-4410",
        "lot_id": "LOT-7701",
        "quantity_received": 18000,
        "receipt_date": "2026-07-06",
        "defect_count": 42,
        "opportunities_per_unit": 4
      },
      {
        "supplier_id": "SUP-4410",
        "lot_id": "LOT-7702",
        "quantity_received": 22000,
        "receipt_date": "2026-07-17",
        "defect_count": 58,
        "opportunities_per_unit": 4
      }
    ]
  }
}
```

#### Successful Response
```json
{
  "supplier_id": "SUP-4410",
  "period_start": "2026-07-01",
  "period_end": "2026-07-31",
  "period_label": "2026-07",
  "verdict": "MEASURED",
  "ppm": 2500.0,
  "numerator": 100,
  "denominator": 40000,
  "lot_count": 2,
  "dpmo": 625.0,
  "dpmo_opportunity_count": 160000,
  "sample_adequacy": {
    "minimum": 1000,
    "meets_minimum": true,
    "is_heuristic": true,
    "basis": "declared engineering default, no standards citation — see ASSUMPTIONS_LOG.md"
  },
  "reason": null,
  "warnings": [],
  "recommendations": [],
  "standards_basis": "No published AIAG/ISO/IATF standard defines a PPM formula, DPMO opportunity model, or sample-adequacy threshold; the arithmetic here is generic industry practice and the sample-adequacy minimum is a declared engineering heuristic (see ASSUMPTIONS_LOG.md)."
}
```

Report the returned `verdict` of `"MEASURED"`, the returned `ppm` figure, and the separately named `dpmo` figure exactly as the tool emitted them. `sample_adequacy.meets_minimum` came back `true`, so no adequacy warning applies — and that minimum is a heuristic, not a standards threshold.

#### Step 2 Invocation — `calculate_otif`
```json
{
  "name": "calculate_otif",
  "arguments": {
    "period": {
      "supplier_id": "SUP-4410",
      "period_start": "2026-07-01",
      "period_end": "2026-07-31",
      "period_label": "2026-07"
    },
    "deliveries": [
      {
        "supplier_id": "SUP-4410",
        "order_id": "PO-55120",
        "quantity_ordered": 4000,
        "quantity_delivered": 4000,
        "promised_date": "2026-07-08",
        "actual_delivery_date": "2026-07-08"
      },
      {
        "supplier_id": "SUP-4410",
        "order_id": "PO-55121",
        "quantity_ordered": 4000,
        "quantity_delivered": 3800,
        "promised_date": "2026-07-15",
        "actual_delivery_date": "2026-07-15"
      }
    ]
  }
}
```

#### Successful Response (abridged — `delivery_breakdown` shows the two orders passed above; the full period contained 16 matched deliveries)
```json
{
  "supplier_id": "SUP-4410",
  "period_start": "2026-07-01",
  "period_end": "2026-07-31",
  "period_label": "2026-07",
  "verdict": "MEASURED",
  "delivery_count": 16,
  "on_time_count": 15,
  "in_full_count": 15,
  "otif_count": 14,
  "on_time_pct": 93.75,
  "in_full_pct": 93.75,
  "otif_pct": 87.5,
  "delivery_breakdown": [
    {
      "order_id": "PO-55120",
      "is_on_time": true,
      "is_in_full": true,
      "is_otif": true,
      "shortfall_qty": 0
    },
    {
      "order_id": "PO-55121",
      "is_on_time": true,
      "is_in_full": false,
      "is_otif": false,
      "shortfall_qty": 200
    }
  ],
  "heuristic_configuration": {
    "early_tolerance_days": 0,
    "late_tolerance_days": 2,
    "early_counts_as_on_time": false,
    "in_full_tolerance_pct": 0.0,
    "over_delivery_counts_as_in_full": true,
    "is_heuristic": true,
    "basis": "declared engineering default, no standards citation — see ASSUMPTIONS_LOG.md"
  },
  "reason": null,
  "warnings": [],
  "recommendations": [],
  "standards_basis": "No published AIAG/ISO/IATF standard defines an on-time window, an in-full tolerance, or whether early delivery counts as on-time; every OTIFConfig value here is a declared engineering heuristic, caller-configurable (see ASSUMPTIONS_LOG.md, RULE-SQE-001/002)."
}
```

Quote all three returned percentages separately. The returned `otif_pct` is lower than both the returned `on_time_pct` and the returned `in_full_pct` because the tool applied the strict conjunction — do not restate it as an average, and do not reconcile the three figures in prose.

#### Step 3 Invocation — `calculate_vendor_scorecard`
```json
{
  "name": "calculate_vendor_scorecard",
  "arguments": {
    "period": {
      "supplier_id": "SUP-4410",
      "period_start": "2026-07-01",
      "period_end": "2026-07-31",
      "period_label": "2026-07"
    },
    "lots": "<the same receipt lots passed to calculate_supplier_ppm>",
    "deliveries": "<the same delivery records passed to calculate_otif>"
  }
}
```

#### Successful Response (each dimension's `source_evidence` is omitted here for brevity — it repeats the `calculate_supplier_ppm` and `calculate_otif` payloads above verbatim)
```json
{
  "supplier_id": "SUP-4410",
  "period_start": "2026-07-01",
  "period_end": "2026-07-31",
  "period_label": "2026-07",
  "verdict": "RATED",
  "composite_score": 80.0,
  "band": "B",
  "dimensions": [
    {
      "name": "quality",
      "source_metric_name": "ppm",
      "raw_metric": 2500.0,
      "sub_score": 75.0,
      "weight": 0.6,
      "weighted_contribution": 45.0,
      "source_verdict": "MEASURED",
      "source_reason": null,
      "warnings": [],
      "recommendations": [],
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    },
    {
      "name": "delivery",
      "source_metric_name": "otif_pct",
      "raw_metric": 87.5,
      "sub_score": 87.5,
      "weight": 0.4,
      "weighted_contribution": 35.0,
      "source_verdict": "MEASURED",
      "source_reason": null,
      "warnings": [],
      "recommendations": [],
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    }
  ],
  "heuristic_configuration": {
    "weights": {
      "quality": {"value": 0.6, "is_heuristic": true, "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"},
      "delivery": {"value": 0.4, "is_heuristic": true, "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"},
      "cost": {"value": 0.0, "is_heuristic": true, "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"},
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    },
    "rating_bands": {
      "a_band_minimum": {"value": 90.0, "is_heuristic": true, "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"},
      "b_band_minimum": {"value": 75.0, "is_heuristic": true, "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"},
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    },
    "is_heuristic": true,
    "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
  },
  "omitted_dimensions": [
    {"name": "cost", "reason": "cost_weight is 0.0; not scored"}
  ],
  "reason": null,
  "warnings": [],
  "recommendations": [],
  "standards_basis": "ISO 9001:2015 section 8.4 and IATF 16949:2016 section 8.4 require supplier evaluation against criteria determined by the organization; those clauses do not define any scorecard weight, scoring curve, or A/B/C band."
}
```

Report the returned `verdict` of `"RATED"`, the returned `composite_score`, and the returned `band` of `"B"` exactly as emitted, and state that the band boundaries quoted from `heuristic_configuration.rating_bands` are this platform's engineering heuristic — not an ISO 9001 or IATF 16949 requirement. The cost dimension appears under `omitted_dimensions` because it carried zero weight; it was not silently folded into the other two.

#### Step 4 Invocation — `evaluate_escalation`
```json
{
  "name": "evaluate_escalation",
  "arguments": {
    "scorecard": "<the calculate_vendor_scorecard result above, passed through unmodified>"
  }
}
```

#### Successful Response (`heuristic_configuration` omitted here for brevity — it lists all eight thresholds, each labelled `is_heuristic`)
```json
{
  "supplier_id": "SUP-4410",
  "tier": "MONITOR",
  "scorecard_verdict": "RATED",
  "evaluated_triggers": [
    {
      "tier": "MONITOR",
      "metric": "composite_score",
      "comparison": "<=",
      "observed_value": 80.0,
      "threshold": 89.0,
      "fired": true,
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    },
    {
      "tier": "SCAR_REQUIRED",
      "metric": "composite_score",
      "comparison": "<=",
      "observed_value": 80.0,
      "threshold": 74.0,
      "fired": false,
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    },
    {
      "tier": "CONTAINMENT_REQUIRED",
      "metric": "composite_score",
      "comparison": "<=",
      "observed_value": 80.0,
      "threshold": 59.0,
      "fired": false,
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    },
    {
      "tier": "EXECUTIVE_REVIEW",
      "metric": "composite_score",
      "comparison": "<=",
      "observed_value": 80.0,
      "threshold": 39.0,
      "fired": false,
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    }
  ],
  "selected_evidence": [
    {
      "tier": "MONITOR",
      "metric": "composite_score",
      "comparison": "<=",
      "observed_value": 80.0,
      "threshold": 89.0,
      "fired": true,
      "is_heuristic": true,
      "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md"
    }
  ],
  "recurrence_count": null,
  "reason": null,
  "standards_basis": "AIAG CQI-20 corrective-action escalation discipline; organizational tier structure only, not numeric thresholds.",
  "commercial_authority": "Any commercial response remains a business decision made by authorized people; this result recommends only a quality-engineering tier."
}
```

Report the returned `tier` of `"MONITOR"`, show the full `evaluated_triggers` list so the reviewer can see which triggers did *not* fire, and repeat the returned `commercial_authority` string verbatim. Do not translate the tier into a commercial action of any kind.

#### Step 5 Invocation — `generate_scar`
```json
{
  "name": "generate_scar",
  "arguments": {
    "request": {
      "supplier_id": "SUP-4410",
      "scar_id": "SCAR-2026-018",
      "issue_description": "Bearing journal diameter above drawing limit on receipt lot LOT-7702, 58 units rejected at incoming inspection.",
      "linked_ncr_id": "NCR-2026-311",
      "date_issued": "2026-08-03",
      "due_date": "2026-08-31",
      "requested_by": "Supplier Quality Engineering"
    }
  }
}
```

#### Successful Response (section `content` and `linkage.raw_result` bodies abridged; `linkage.linked_ncr` and `linkage.cost_impact` resolved `EVIDENCE_NOT_SUPPLIED` because no evidence was passed for them)
```json
{
  "supplier_id": "SUP-4410",
  "scar_id": "SCAR-2026-018",
  "issue_description": "Bearing journal diameter above drawing limit on receipt lot LOT-7702, 58 units rejected at incoming inspection.",
  "status": "AWAITING_SUPPLIER_RESPONSE",
  "sections": [
    {
      "heading": "Root-Cause Requirement",
      "rule_id": "RULE-SQE-011",
      "content": "State the systemic root cause of this nonconformity. ... The root cause is stated by the supplier and validated here; this generator never authors, infers, or substitutes one."
    },
    {
      "heading": "Corrective-Action Requirement",
      "rule_id": "RULE-SQE-012",
      "content": "Define and implement the permanent corrective action(s) that resolve the established systemic root cause. ..."
    },
    {
      "heading": "Prevention / Read-Across",
      "rule_id": "RULE-SQE-013",
      "content": "Identify every other part, product, line, and process to which the same systemic root cause applies, ..."
    }
  ],
  "linkage": {
    "linked_ncr": {
      "linkage_key": "linked_ncr",
      "verdict": "EVIDENCE_NOT_SUPPLIED",
      "engine": "quality_core.ncr",
      "findings": [],
      "rationale": "no nonconformance evidence was supplied for this slot",
      "raw_result": null
    },
    "supplier_root_cause": {
      "linkage_key": "supplier_root_cause",
      "verdict": "EVIDENCE_NOT_SUPPLIED",
      "engine": "quality_core.rca",
      "findings": [],
      "rationale": "no supplier root-cause response has been received for this slot",
      "raw_result": null
    },
    "cost_impact": {
      "linkage_key": "cost_impact",
      "verdict": "EVIDENCE_NOT_SUPPLIED",
      "engine": "quality_core.copq",
      "findings": [],
      "rationale": "no cost evidence was supplied for this slot",
      "raw_result": null
    },
    "vendor_scorecard": {
      "linkage_key": "vendor_scorecard",
      "verdict": "LINKAGE_NOT_AVAILABLE",
      "engine": null,
      "findings": [],
      "rationale": "vendor scorecard linkage is deferred this release and is never verdict-affecting",
      "raw_result": null
    }
  },
  "root_cause": null,
  "verification_of_effectiveness": null,
  "due_date": "2026-08-31",
  "date_issued": "2026-08-03",
  "reason": "this SCAR has been issued and no supplier root-cause response has been received.",
  "warnings": [],
  "recommendations": [],
  "standards_basis": "AIAG CQI-20 Effective Problem Solving (2nd Edition, 2018) and the Ford Global 8D Manual back the three rendered section headings only ..."
}
```

Report the returned `status` of `"AWAITING_SUPPLIER_RESPONSE"` and the returned `root_cause` of `null`. **Do not fill that field in.** The SCAR requests a root cause from the supplier; when the supplier returns a 5-Why chain, pass it as `supplier_root_cause_evidence` and let `generate_scar` adjudicate it — a chain the validator rejects yields `RESPONSE_REJECTED` with the validator's own findings, which you surface unchanged.

---

### Example 2: Negative Control — Zero Receipts in Period

The supplier has no matched receipt lots in the requested window (the lots on hand belong to a different supplier or a different period).

#### Invocation
```json
{
  "name": "calculate_supplier_ppm",
  "arguments": {
    "period": {
      "supplier_id": "SUP-9004",
      "period_start": "2026-07-01",
      "period_end": "2026-07-31",
      "period_label": "2026-07"
    },
    "lots": []
  }
}
```

#### Indeterminate Response
```json
{
  "supplier_id": "SUP-9004",
  "period_start": "2026-07-01",
  "period_end": "2026-07-31",
  "period_label": "2026-07",
  "verdict": "INDETERMINATE",
  "ppm": null,
  "numerator": null,
  "denominator": 0,
  "lot_count": 0,
  "dpmo": null,
  "dpmo_opportunity_count": null,
  "sample_adequacy": {
    "minimum": 1000,
    "meets_minimum": false,
    "is_heuristic": true,
    "basis": "declared engineering default, no standards citation — see ASSUMPTIONS_LOG.md"
  },
  "reason": "no in-scope received quantity: 0 receipt lot(s) matched supplier_id 'SUP-9004' in window [2026-07-01, 2026-07-31], totalling 0 unit(s) received; PPM is undefined over a zero denominator and is not reported as 0.0",
  "warnings": [],
  "recommendations": [
    "Supply the receipt lots for this supplier and window before quoting a PPM figure."
  ],
  "standards_basis": "No published AIAG/ISO/IATF standard defines a PPM formula, DPMO opportunity model, or sample-adequacy threshold; the arithmetic here is generic industry practice and the sample-adequacy minimum is a declared engineering heuristic (see ASSUMPTIONS_LOG.md)."
}
```

**Correct agent behaviour.** Report the period as `INDETERMINATE`, quote the tool's own `reason` and its `recommendations` entry, and **ask the user to supply a valid receipt period or the missing lot data** before any figure is published. Stop there.

**The behaviour this negative control rules out.** Reporting `0` PPM and inferring an `A` rating. A supplier that shipped nothing — or whose receipts were simply not provided — has an undefined defect rate, not a perfect one. Do not proceed to `calculate_vendor_scorecard`, `evaluate_escalation`, or a SCAR on this evidence: the correct next move is a question to the user, not another tool call.

## Best Practices
1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** Never compute a PPM, DPMO, OTIF, or composite score inline — always delegate to `calculate_supplier_ppm`, `calculate_otif`, or `calculate_vendor_scorecard` on `quality-mcp`. Never assign a rating band or escalation tier from memory — delegate to `calculate_vendor_scorecard` and `evaluate_escalation`. Never present a weight, band boundary, or threshold as an **ISO 9001** or **IATF 16949** requirement — every one is this platform's own declared **engineering heuristic**, not a standards requirement (see `ASSUMPTIONS_LOG.md`). Never state or imply a commercial action (new-business hold, de-sourcing, resourcing, charge-back) as a recommendation — that is a business decision, not a quality-engineering verdict. **Never author, infer, or paraphrase a supplier's root cause** — `generate_scar` requests one and validates the supplier's own response; the supplier owns the root cause.
2. **Sample-Adequacy & Conjunction Discipline:** Treat `sample_adequacy.meets_minimum: false` and a suppressed scorecard band as signals to gather more evidence, never as licence to force a rating. Report `on_time_pct`, `in_full_pct`, and `otif_pct` as three distinct figures, and never present the conjunction as an average of the other two.
3. **Full-Trigger-Set Review:** Always show `evaluated_triggers`, not just `selected_evidence`, so a reviewer can see which thresholds did *not* fire — that completeness is the escalation engine's own design intent, and it is what makes a tier auditable.
4. **SCAR Closure Discipline:** Never mark or imply a SCAR closed without both a `quality_core.rca`-accepted supplier root cause and a supplier-stated `verification_of_effectiveness`. `CLOSABLE` is the tool's verdict to issue, not the agent's.
5. **Verbatim Findings:** When any linkage slot resolves `EVIDENCE_INVALID`, surface the sub-engine's own `findings` text to the user rather than re-explaining, summarizing, or softening it — the owning engine's wording is the record.

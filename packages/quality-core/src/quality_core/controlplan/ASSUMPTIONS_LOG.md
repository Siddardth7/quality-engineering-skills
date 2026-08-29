# Engineering Assumptions Log — Control Plan Engine

**Package:** `quality_core.controlplan`
**Standard References:**
- AIAG APQP and Control Plan Reference Manual (2nd Edition)
- AIAG-VDA FMEA Handbook (1st Edition, 2019)
- AIAG SPC Reference Manual (4th Edition, 2005)

This document records every non-obvious engineering decision, published constant, and architectural constraint used in the Control Plan engine.

---

## RULE 1 — SPC Chart-Selection Rule Table (`recommend_chart`)

**Decision:** Select a control chart from data type + subgroup size (+ attribute counting mode), per the AIAG chart-selection decision tree:
- Variable data: `n == 1` → `I-MR`; `2 <= n <= 9` → `Xbar-R`; `10 <= n <= 12` → `Xbar-S`; `n > 12` → `ValueError`.
- Attribute data: classifying units defective → `p` (`np` folds into `p`); counting defects per unit, constant sample → `c`; counting defects per unit, variable sample → `u`.

**Source:** AIAG SPC Reference Manual, 4th Ed. (2005), control-chart selection logic.

**Upper bound (`n > 12` raises):** `Xbar-S` is only computable for subgroup sizes the AIAG X-bar/S constants table covers (`quality_core.spc.constants.XBAR_S_CONSTANTS`, keys 2–12). Above $n=12$, AIAG publishes no $A_3/B_3/B_4/c_4$ constants, so `recommend_chart` raises `ValueError` rather than naming a chart the engine cannot compute.

**Applied In:** `quality_core.controlplan.connector::recommend_chart`.

---

## RULE 2 — FMEA → Control Plan Field Defaults & Placeholders

**Decision:** `build_control_plan` derives `characteristic` and `measurement_method` from the relational FMEA, but `sample_size`, `frequency`, and `reaction_plan` have no FMEA-model equivalent. Defaulted to `sample_size=1`, `frequency="per shift"`, and a templated `reaction_plan` built from the failure mode's worst effect. `recommended_chart` is emitted `None` by default.

**Provenance flag:** Every row `build_control_plan` emits carries `sample_plan_is_placeholder=True` (`ControlPlanRow`), so a downstream consumer can distinguish default stubs from engineered values.

**Applied In:** `quality_core.controlplan.connector::build_control_plan`.

---

## RULE 3 — PFMEA Linkage & Orphan Detection Contract

**Decision:** `validate_pfmea_linkage` evaluates whether every Control Plan row resolves to a valid FMEA cause via its `source_cause_id`. Rows with missing or unresolvable `source_cause_id` are flagged as `orphan_characteristics` with `valid = False`. Uncovered FMEA failure modes are reported in `uncovered_failure_modes`.

**Source:** AIAG-VDA FMEA Handbook (2019), Section 1.4 & Section 5:
> "It supports the development of comprehensive specifications, test plans, and Control Plans." (Line 242)
> "Special Characteristics are marked with abbreviations or symbols* in documents such as Product documents (as required), Process FMEA (Special Characteristics column) and Control Plans." (Line 5100)
> "Evidence for the implementation of process controls for Special Characteristics should be monitored, documented, and accessible." (Line 5100)

**Applied In:** `quality_core.controlplan.connector::validate_pfmea_linkage`.

---

## RULE 4 — Excel Exporter Introduces No Standards Constant; Coverage Roll-Up Counts *Declared* Linkage

**Decision:** `export.py` writes a Control Plan dataset to `.xlsx` without defining, deriving, or transcribing any AIAG/VDA value. Its three roll-up cells (`Coverage!B2`/`B3`/`B4`) are live spreadsheet formulas — `COUNTA`, `COUNTIF`, and a ratio of the two — counting rows already present in the exported matrix. Column letters are derived from `CONTROLPLAN_EXPORT_COLUMNS` via `get_column_letter`, never hand-typed.

**Declared linkage, not validated linkage:** the `PFMEA_Linked` column the roll-ups count against is a plain presence check (`source_cause_id is not None`). It is **not** RULE 3's `validate_pfmea_linkage` check, which additionally verifies the ID resolves against a specific `RelationalFMEA` — that needs both objects and is out of reach of a dataset-only exporter call. The exported "Linkage Coverage %" is therefore a strictly weaker claim than RULE 3's `linked_rows`, and must never be read as a validated-linkage number.

**Source:** None. `COUNTA`/`COUNTIF`/ratio are elementary spreadsheet arithmetic; no published standard specifies them, so this rule adds no row to `CITATIONS.tsv`. The underlying linkage/orphan concept remains governed by RULE 3 above (AIAG-VDA FMEA Handbook 2019, §1.4 & §5) — that citation is unchanged.

**Rationale:** An exporter is a presentation boundary. Re-deriving a standards claim inside it would create a second copy that could drift from the engine's, so the roll-up is kept to elementary counting against exporter-controlled column letters and the stronger, standards-governed check stays solely in `connector.py`.

**Applied In:** `quality_core.controlplan.export` (`CONTROLPLAN_EXPORT_COLUMNS`, `_coverage_formulas`, `_row_record`, `export_controlplan_workbook`).

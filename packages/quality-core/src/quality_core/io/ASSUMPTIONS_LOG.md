# Engineering Assumptions Log — Export / Ingest Boundary (io)

**Package:** `quality_core.io`
**Domain:** Cross-cutting export/ingest machinery — CSV/Excel formula-injection
escaping (`sanitize_for_export`, `export_csv`), openpyxl workbook styling, and the
tabular validation helpers shared by every domain exporter.

This document records every non-obvious engineering decision and constraint used in
the export/ingest boundary. It is deliberately co-located with the code it governs so
that at v1.0.0 no constant in this module is untraceable or half-remembered.

---

## NO-STANDARD-DECLARATION

**No published AIAG / ISO / IATF quality standard governs the `quality_core.io`
boundary, and this module encodes no standards constant, threshold, or quotation.**
Per `CLAUDE.md` ("where no published standard exists, say so"), that fact is recorded
here explicitly rather than implied by the absence of a citation manifest. This module
carries **no `CITATIONS.tsv`**: there is nothing from a licensed manual to cite.

The one security-relevant constant in this module, `FORMULA_PREFIXES`, is sourced from
an open web-security convention, **not** a licensed standards manual, and is documented
as such below. It is therefore *not* a candidate for the on-machine-manual citation
trail; recording it here is the honest home for its rationale.

---

## RULE Entries

## RULE-IO-001: `FORMULA_PREFIXES` is an OWASP CSV-injection convention, not a quality standard

**Decision:** `export.py` treats a cell whose leading character is one of
`("=", "+", "-", "@", "\t", "\r")` as a formula-injection risk and escapes it before it
reaches a CSV or Excel file (`FORMULA_PREFIXES`, `_is_injection_risk`,
`sanitize_for_export`).

**Source:** The OWASP "CSV Injection" (a.k.a. Formula Injection) guidance — a
web-security community convention, **not** an AIAG/ISO/IATF manual and **not** an
on-machine licensed reference. Because it is not a licensed standards claim, it is
governed by this rule rather than by a `CITATIONS.tsv` row, and it must never be
presented as a quality-standard requirement.

**Rationale:** A spreadsheet application may evaluate a cell that begins with one of
these characters as a formula when the exported file is opened, which turns
attacker-controlled field content into code execution or data exfiltration in the
recipient's spreadsheet. Escaping at the export boundary is the standard mitigation and
belongs to the shared io layer so that every domain exporter inherits it uniformly
rather than re-implementing (and mis-implementing) it.

**Applied In:** `packages/quality-core/src/quality_core/io/export.py`
(`FORMULA_PREFIXES`, `_is_injection_risk`, `sanitize_for_export`, `export_csv`).

---

## RULE-IO-002: openpyxl styling and tabular validation carry no standards claim

**Decision:** The workbook-styling helpers (column widths, header fills, freeze panes)
and the tabular validation helpers in `validate.py` implement presentation and
data-shape checks only.

**Source:** None. No published quality standard specifies workbook cosmetics or the
DataFrame-shape guards used here.

**Rationale:** These are engineering conveniences for legible exports and fail-fast
ingestion. They set no threshold and quote no manual, so there is nothing to cite; this
declaration is the record that their absence from any citation manifest is intentional.

**Applied In:** `packages/quality-core/src/quality_core/io/export.py`,
`packages/quality-core/src/quality_core/io/validate.py`.

---

## RULE-IO-003: the FMEA exporter introduces no standards constant of its own

**Decision:** `export_fmea.py` writes an FMEA dataset to .xlsx without defining, deriving,
or transcribing any AIAG/VDA value. Its RPN column is a live spreadsheet formula
`=S*O*D` referencing that row's own Severity/Occurrence/Detection data cells — the same
elementary product `quality_core.scoring.rpn` computes. Its Action Priority column is the
string returned by calling `quality_core.scoring.action_priority(...)` in Python and
passing the result through unchanged.

**Source:** None in this module. The RPN product is elementary arithmetic already
documented under `RULE-SCORING-002` in
`packages/quality-core/src/quality_core/scoring_ASSUMPTIONS_LOG.md`, which records that
the product itself carries no threshold. The AIAG-VDA 2019 Action Priority table lives in
`scoring.py` and its citation is tracked as a `PROCUREMENT-GAP` in that same log; this
exporter takes no position on it.

**Rationale:** An exporter is a presentation boundary. Re-deriving or re-transcribing the
AP table here would create a second copy of a standards claim that could drift from the
engine's, and would move a licensed-manual citation obligation into a module whose whole
job is layout. Calling the engine keeps exactly one home for that claim. The column
letters in the RPN formula are likewise derived from `FMEA_EXPORT_COLUMNS` via
`get_column_letter` rather than hand-typed, so the formula cannot silently reference the
wrong column after a layout change.

**Applied In:** `packages/quality-core/src/quality_core/io/export_fmea.py`
(`FMEA_EXPORT_COLUMNS`, `_rpn_formula`, `_row_record`, `export_fmea_workbook`).

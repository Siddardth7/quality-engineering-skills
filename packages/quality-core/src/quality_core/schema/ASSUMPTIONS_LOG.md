# Engineering Assumptions Log — FMEA Domain Schema (schema)

**Package:** `quality_core.schema`
**Domain:** Pydantic FMEA domain contracts — row/dataset models (`fmea.py`), the
optimization/action-tracking model (`action.py`), and the AIAG/VDA-structured relational
model (`relational.py`): Function → Failure → Effect / Cause / Control.

This document records every non-obvious engineering decision and constraint used in the
FMEA schema layer, co-located with the code it governs.

---

## NO-STANDARD-DECLARATION

**The `quality_core.schema` module encodes no standards constant, threshold, or numeric
value, and therefore carries no `CITATIONS.tsv`.** It defines data *contracts* — field
names, types, relationships, and validation invariants — not scored values. There is no
figure from a licensed manual to quote here.

The module *does* follow the AIAG/VDA FMEA structural convention (Severity is an attribute
of the Effect, Occurrence of the Cause, Detection of the Control), which is a design
decision derived from a published standard. **That structural convention carries no
citable numeric constant**; the authoritative prose describing it lives with the FMEA
scoring engine, whose verifiable citation rows are tracked as a **PROCUREMENT-GAP** in
`scoring_ASSUMPTIONS_LOG.md` (the AIAG-VDA FMEA Handbook is not on this machine). Recording
the structural basis here — without inventing a manual quote for it — is the honest
treatment per `CLAUDE.md` ("never verify a standards claim by web search").

---

## RULE Entries

## RULE-SCHEMA-001: AIAG/VDA S/O/D attribute placement is structural, not a scored constant

**Decision:** `relational.py` places Severity on the `Effect`, Occurrence on the `Cause`,
and Detection on the `Control`, and `action.py` models the AIAG/VDA "optimization" loop as
a recorded action against a failure mode.

**Source:** The attribute placement mirrors the AIAG & VDA FMEA Handbook (1st Edition,
2019) relational structure. This is a structural convention with **no numeric value**;
the handbook's scored content (the Action Priority table, the S/O/D rating scales) lives
in `quality_core.scoring` and its verifiable quotation rows are a declared procurement
gap there. No `CITATIONS.tsv` row is authored in this module because there is no numeric
standard constant defined here to cite.

**Rationale:** Encoding S/O/D on the correct entities is what makes the relational model
faithful to the standard's intent (a single Cause can drive several Effects at different
Severities). The placement is enforced by the Pydantic types; it sets no threshold and
computes no score, so it is documented rather than cited.

**Applied In:** `packages/quality-core/src/quality_core/schema/relational.py`,
`packages/quality-core/src/quality_core/schema/action.py`,
`packages/quality-core/src/quality_core/schema/fmea.py`.

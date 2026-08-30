# Engineering Assumptions Log — Theme (theme)

**Package:** `quality_core.theme`
**Domain:** Presentation styling only — the shared colour palette (`palette.py`) and
figure/style helpers (`style.py`) used to render canvases and exports consistently.

This document is co-located with the code it governs so that at v1.0.0 no module in the
package is silently missing a standards declaration.

---

## NO-STANDARD-DECLARATION

**The `quality_core.theme` module is presentation-only and encodes no standards constant,
threshold, or quotation; it therefore carries no `CITATIONS.tsv`.** Per `CLAUDE.md` ("where
no published standard exists, say so"), that fact is recorded here explicitly rather than
implied by the absence of a citation manifest.

Colours, fonts, and figure dimensions are brand/legibility choices. No AIAG/ISO/IATF
standard specifies them, so there is nothing from a licensed manual to cite.

---

## RULE Entries

## RULE-THEME-001: Palette and figure styling carry no standards claim

**Decision:** `palette.py` and `style.py` define the colour tokens and matplotlib/openpyxl
styling shared across the rendered canvases and exports.

**Source:** None. These are design decisions for a consistent, legible visual system.

**Rationale:** Standardising the palette in one module keeps every domain's output visually
coherent; it sets no threshold and quotes no manual, so it is documented rather than cited.

**Applied In:** `packages/quality-core/src/quality_core/theme/palette.py`,
`packages/quality-core/src/quality_core/theme/style.py`.

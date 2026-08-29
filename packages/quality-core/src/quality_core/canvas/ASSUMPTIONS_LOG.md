# Engineering Assumptions Log — Canvas Controllers (canvas)

**Package:** `quality_core.canvas`
**Domain:** Presentation-layer canvas controllers for the eight quality domains
(FMEA, SPC, MSA, Control Plan, RCA, NCR, COPQ, and the SQE suite): in-memory
collection management, CRUD, benchmark-dataset loading, and render-payload shaping.

This document records every non-obvious engineering decision and constraint used in the
canvas layer, co-located with the code it governs.

---

## NO-STANDARD-DECLARATION

**The `quality_core.canvas` module is presentation-only and encodes no standards
constant, threshold, or quotation of its own; it therefore carries no `CITATIONS.tsv`.**
Per `CLAUDE.md` ("where no published standard exists, say so"), that is recorded here
explicitly.

Some canvas controllers embed standards *clause references* inside their seed/benchmark
datasets — for example `canvas/ncr.py` labels its example dispositions with ISO 9001:2015
§8.7 and IATF 16949:2016 §8.7 clause tags. **Those references are illustrative captions on
demo data, and the authoritative citation for each lives with the owning engine**, not
here: ISO/IATF §8.7 is cited and manual-verified under `quality_core.ncr`
(`ncr/CITATIONS.tsv`, `test_ncr_citations.py`). The canvas layer restates a clause tag for
display; it does not originate a standards claim, so it does not open a second, divergent
citation trail for the same clause.

---

## RULE Entries

## RULE-CANVAS-001: Clause tags in seed data are display captions, cited by the owning engine

**Decision:** Canvas seed/benchmark rows may carry a human-readable standards clause tag
(e.g. "per ISO 9001:2015 Clause 8.7.1(a)") in a rationale string for demonstration.

**Source:** Each such tag's authoritative, manual-verified citation lives in the owning
engine's `CITATIONS.tsv` (ISO/IATF §8.7 → `quality_core.ncr`). The canvas layer adds no
new licensed-manual claim and quotes no manual, so it authors no `CITATIONS.tsv` row.

**Rationale:** Duplicating the citation into the canvas layer would create two manifests
for one clause that could drift apart. Keeping the citation with the engine and treating
the canvas tag as a display caption means there is exactly one verified source of truth
per clause.

**Applied In:** `packages/quality-core/src/quality_core/canvas/` (all controllers;
`canvas/ncr.py` is the representative case).

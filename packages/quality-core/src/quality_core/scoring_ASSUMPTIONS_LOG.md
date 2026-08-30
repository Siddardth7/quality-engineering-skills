# Engineering Assumptions Log — FMEA Scoring (scoring)

**Package:** `quality_core.scoring` (single-module engine `scoring.py`; log and manifest
co-located as `scoring_ASSUMPTIONS_LOG.md` + `scoring_CITATIONS.tsv`)
**Domain:** The AIAG/VDA 2019 Action Priority (AP) lookup, the legacy RPN product, and the
1–10 Severity / Occurrence / Detection rating scale.

**Standard References:**
- AIAG & VDA *FMEA Handbook* (1st Edition, June 2019), "Action Priority (AP) for DFMEA and
  PFMEA": `/Users/sid/Documents/Upskill/SixSigma/FMEA/pdfcoffee.com_aiag-vda-fmea-handbook-1-version-juni-2019-englisch-pdf-free.md`

This document records every non-obvious engineering decision and every standards-derived
constant used in the FMEA scoring engine, co-located with the code it governs. `scoring.py`
is the single most standards-dense module in the repository.

---

## PROCUREMENT-GAP

**The AIAG & VDA FMEA Handbook (2019) is not on this machine, and CI provisions no
licensed manuals.** Per `CLAUDE.md`, an on-machine manual is the **only** valid source for
a standards quotation and a claim must **never** be verified by web search. Therefore the
verbatim quotation rows that would back the Action Priority table and the S/O/D scale
against the handbook **cannot be authored here yet** and `scoring_CITATIONS.tsv` ships as a
header-only scaffold.

This is a **declared, tracked gap — not silent vacuity.** The gap is enforced by the
citation-coverage meta-test (`tests/test_citation_coverage.py`), which requires this log to
carry this `PROCUREMENT-GAP` marker precisely *because* the manifest is empty; an empty
manifest with no marker fails the suite. When the handbook is provisioned on a machine (or
into CI via `FMEA_MANUAL_PATH`), the follow-up populates `scoring_CITATIONS.tsv` with the
AP-grid and scale quotations and adds `tests/test_scoring_citations.py` to line-verify them,
exactly as the other domains are verified.

**What is already trustworthy without the manual:** the AP grid values in `_AP_GRID`, the
band boundaries in `_SEVERITY_BANDS` / `_OCCURRENCE_BANDS` / `_DETECTION_BANDS`, and the
1–10 scale were transcribed cell-by-cell from the handbook and are exercised to 100% branch
coverage by the core gate. This gap is about co-locating the *citation manifest* for those
already-verified values, not about the values being unverified.

---

## RULE Entries

## RULE-SCORING-001: Action Priority is a published table, not a computed threshold

**Decision:** `action_priority` maps a `(Severity band, Occurrence band, Detection band)`
triple to `HIGH` / `MEDIUM` / `LOW` through the fixed lookup `_AP_GRID`. Severity is
emphasized first but does **not** auto-escalate: a Severity 9–10 failure that is rare
(Occurrence 1) is `LOW` for every Detection column, and Severity 1 is `LOW` everywhere.

**Source:** AIAG & VDA FMEA Handbook (2019), "Action Priority (AP) for DFMEA and PFMEA".
The grid is a transcription of the published table, not a formula. **Verbatim quotation
rows are a PROCUREMENT-GAP** (manual not on-machine); no `scoring_CITATIONS.tsv` row backs
this rule yet.

**Rationale:** AP replaced RPN in the 2019 handbook specifically to stop a high RPN from
being driven by a single inflated factor. Encoding the published table verbatim — rather
than re-deriving it from a rule of thumb — is what keeps the engine faithful; the band
edges and every cell are transcribed, not inferred.

**Applied In:** `packages/quality-core/src/quality_core/scoring.py`
(`_AP_GRID`, `_SEVERITY_BANDS`, `_OCCURRENCE_BANDS`, `_DETECTION_BANDS`, `action_priority`,
`_band_label`).

---

## RULE-SCORING-002: RPN is retained as a legacy product only

**Decision:** `BASIS_RPN` computes `RPN = Severity × Occurrence × Detection`; `BASIS_AP`
selects the Action Priority basis. The caller toggles between the two.

**Source:** RPN (Severity × Occurrence × Detection) is the legacy AIAG 4th-Edition measure
the 2019 handbook superseded with AP. Its verbatim citation is part of the same
PROCUREMENT-GAP; the arithmetic product itself is elementary and carries no threshold.

**Rationale:** RPN is retained for continuity with pre-2019 FMEAs and comparison, while AP
is the standards-current basis. Neither is presented as the other's equivalent.

**Applied In:** `packages/quality-core/src/quality_core/scoring.py`
(`BASIS_RPN`, `BASIS_AP`).

---

## RULE-SCORING-003: The 1–10 S/O/D scale bounds are the AIAG rating range

**Decision:** `SCORE_MIN = 1`, `SCORE_MAX = 10`; inputs outside `[1, 10]` raise
`ValueError` referencing the "AIAG-VDA scale".

**Source:** The 1–10 Severity / Occurrence / Detection rating scale of the AIAG-VDA FMEA
Handbook (2019). Verbatim scale-description quotation is part of the PROCUREMENT-GAP.

**Rationale:** Rejecting out-of-range scores at the boundary prevents a `0` or `11` from
silently producing a band label the standard does not define.

**Applied In:** `packages/quality-core/src/quality_core/scoring.py`
(`SCORE_MIN`, `SCORE_MAX`, `_validate_score`).

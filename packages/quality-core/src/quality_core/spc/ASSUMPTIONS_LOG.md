# Engineering Assumptions Log — Statistical Process Control (SPC)

**Package:** `quality_core.spc`
**Domain:** Control-chart constants (`constants.py`), Xbar-R / Xbar-S / I-MR chart
computation (`control_charts.py`), Western Electric / Nelson run-rule detection
(`rule_detection.py`), capability indices (`capability.py`), the stability gate
(`stability.py`), and phase handling (`phase.py`).

**Standard References:**
- AIAG *Statistical Process Control (SPC)* Reference Manual (2nd Edition; control-chart
  constants per 4th-Ed. table): `/Users/sid/Documents/Upskill/SixSigma/SPC/pdfcoffee.com_aiag-spc-2nd-edition-pdf-free.pdf`
- *Western Electric Statistical Quality Control Handbook* (run-rule zone tests):
  `/Users/sid/Documents/Upskill/SixSigma/SPC/Western_Electric_SQC_Handbook.pdf`
- Lloyd S. Nelson, "The Shewhart Control Chart — Tests for Special Causes", *Journal of
  Quality Technology* (Nelson run-rules): `/Users/sid/Documents/Upskill/SixSigma/SPC/The-Shewhart-Control-Chart-Tests-for-Special-Causes-Lloyd-Nelson-Journal-of-Quality-Technology.pdf`

This document records every non-obvious engineering decision and every standards-derived
constant used in the SPC engine, co-located with the code it governs.

---

## PROCUREMENT-GAP

**The AIAG SPC Reference Manual, the Western Electric SQC Handbook, and the Nelson JQT
article are not on this machine, and CI provisions no licensed manuals.** Per `CLAUDE.md`,
an on-machine manual is the **only** valid source for a standards quotation and a claim
must **never** be verified by web search. Therefore the verbatim quotation rows that would
back the control-chart constants and the run-rule definitions **cannot be authored here
yet**, and `spc/CITATIONS.tsv` ships as a header-only scaffold.

This is a **declared, tracked gap — not silent vacuity**, enforced by the citation-coverage
meta-test (`tests/test_citation_coverage.py`): because `spc/CITATIONS.tsv` is empty, this
log is *required* to carry this `PROCUREMENT-GAP` marker, and an empty manifest with no
marker fails the suite. When the manuals are provisioned (or supplied to CI via the
standard `*_MANUAL_PATH` env vars), the follow-up populates `spc/CITATIONS.tsv` with the
constant-table and run-rule quotations and adds `tests/test_spc_citations.py` to
line-verify them.

**What is already trustworthy without the manual:** the `A2/D3/D4/d2` constant values in
`constants.py` and the run-rule zone logic in `rule_detection.py` are exercised to 100%
branch coverage by the core gate. This gap is about co-locating the *citation manifest* for
those already-verified values.

---

## RULE Entries

## RULE-SPC-001: Control-chart constants are a published table

**Decision:** `constants.py` carries the subgroup-size-keyed constants
`A2`, `D3`, `D4`, and `d2` used to compute Xbar/R control limits and to estimate sigma.

**Source:** AIAG SPC Reference Manual control-chart constant table. **Verbatim quotation
rows are a PROCUREMENT-GAP** (manual not on-machine); no `spc/CITATIONS.tsv` row backs this
rule yet.

**Rationale:** These are tabulated statistical constants, not tunable parameters; they are
transcribed from the published table and keyed by subgroup size so the wrong-`n` constant
can never be silently applied.

**Applied In:** `packages/quality-core/src/quality_core/spc/constants.py`.

---

## RULE-SPC-002: Western Electric / Nelson run-rules are distinct rule sets

**Decision:** `rule_detection.py` labels zone/limit tests under two named rule sets
(`Western Electric Rule 1..4`, `Nelson Rule 1..`), and applies them only on chart types
where they are statistically valid.

**Source:** Western Electric SQC Handbook and Lloyd Nelson's JQT article, respectively.
Where the two rule sets share a boundary (e.g. "beyond 3σ") the equality is coincidental,
not a merge. **Verbatim quotation rows are a PROCUREMENT-GAP**; no `spc/CITATIONS.tsv` row
backs this rule yet.

**Rationale:** The two systems are historically and numerically distinct; labelling them
separately keeps a detected signal traceable to the rule set that defines it.

**Applied In:** `packages/quality-core/src/quality_core/spc/rule_detection.py`.

---

## RULE-SPC-003: Capability indices presuppose a process in statistical control

**Decision:** Capability computation (`capability.py`) is gated on stability: an unstable
or unassessed process does not yield a trusted capability verdict.

**Source:** The AIAG SPC principle that capability indices are meaningful only for a
process demonstrated to be in statistical control. **Verbatim quotation is a
PROCUREMENT-GAP.**

**Rationale:** Reporting Cpk on an out-of-control process reports a number that looks like
capability but is not; the stability gate (RULE-SPC-004) prevents that.

**Applied In:** `packages/quality-core/src/quality_core/spc/capability.py`,
`packages/quality-core/src/quality_core/spc/stability.py`.

---

## RULE-SPC-004: Stability gate — chart context is caller-supplied, never inferred

**Decision:** `stability.py` assembles a stream's control chart, runs Western Electric rule
detection, and turns the signal list into the `stable` / `stability_note` fields on
`CapabilityStudy`. It deliberately does **not** infer the chart type from the data: a caller
with no chart context gets `stable=None` ("not assessed"), never a fabricated `True`.

**Source:** Engineering decision (#191 D3) built on RULE-SPC-002/003; not itself a manual
quotation. I-MR on flattened subgrouped data understates sigma and flips verdicts, and a
2-D auto-derivation raises for subgroup sizes outside 2..10, so chart context must come from
the caller.

**Rationale:** Guessing the chart type would let the stability verdict — and therefore the
capability verdict downstream — turn on an assumption the data cannot justify. Returning
"not assessed" is the honest result when context is absent.

**Applied In:** `packages/quality-core/src/quality_core/spc/stability.py`
(`assess_stability`, `CapabilityStudy.stable`, `CapabilityStudy.stability_note`).

**Pointer note:** RULE-SPC-004 is the correct target for the module docstring in
`spc/stability.py`, which previously pointed at a nonexistent `docs/ASSUMPTIONS_LOG.md
RULE 7`.

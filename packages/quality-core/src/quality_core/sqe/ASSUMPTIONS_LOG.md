# Engineering Assumptions Log — Supplier Quality Engineering (SQE) Suite

**Package:** `quality_core.sqe`
**Standard References:**
- ISO 9001:2015 §8.4 (Control of externally provided processes, products and services) and §10.2 (Nonconformity and corrective action): `/Users/sid/Documents/Upskill/SixSigma/SQE/ISO_9001_2015_Section_8_4_and_10_2.md`
- IATF 16949:2016 §8.4 (supplemental supplier management requirements): `/Users/sid/Documents/Upskill/SixSigma/SQE/IATF_16949_2016_Section_8_4.md`
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018) — corrective-action discipline authority for E6: `/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md`
- Ford Global 8D Manual — D1–D8 structure authority for E6: `/Users/sid/Documents/Upskill/SixSigma/RCA/Ford_Global_8D_Manual.md`

This document records every non-obvious engineering decision, published clause requirement, and
architectural constraint used in the Supplier Quality Engineering (SQE) Suite (`quality_core.sqe`).

The first two references above are **forward references**: the excerpt files are hand-produced by the
SME from the licensed standards and are not on-machine at the time this scaffold lands. Recording the
path here does not assert the file exists.

**PROCUREMENT-GAP (ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4):** the licensed excerpt
files for these two clauses were never procured and are on no machine, so **no verbatim quotation
from §8.4/§10.2 backs any statement in this log**. Every reference to what these clauses "require"
(including the "No-Standard-Implied Invariant" section below) is a good-faith paraphrase of the
clause intent, **not** a manual-verified quotation, and must not be presented as one. The rows that
`sqe/CITATIONS.tsv` *does* carry (RULE-SQE-011..016) are backed by the on-machine AIAG CQI-20 and
Ford Global 8D manuals — the SCAR corrective-action discipline — and are verified by
`tests/test_sqe_scar_citations.py`; the ISO/IATF §8.4 excerpts remain a tracked gap for the E0 follow-up.
Per `CLAUDE.md`, these clauses will **never** be verified by web search.

---

## Note on the No-Standard-Implied Invariant

ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4 require that externally provided processes,
products and services be controlled, and that external providers be evaluated, selected, monitored
and re-evaluated **against criteria the organization determines**. The published clauses require the
evaluation; they do not supply the criteria. No published standard names a PPM acceptance level, an
on-time-in-full window, a scorecard weight, a rating-band boundary, or an escalation trigger.

Every engine in this package (PPM, OTIF, vendor scorecard, escalation ladder, SCAR) therefore keeps
two things separate:

1. **What ISO/IATF require** — that suppliers be evaluated and monitored against determined criteria,
   and that nonconformity drive corrective action. This is citable and is cited.
2. **The numeric criteria used to do the evaluating** — thresholds, weights, windows, and bands.
   These have no published source and are **engineering heuristics**, caller-configurable, and
   labelled as such in every payload.

This section is placed ahead of any RULE entry because the honesty requirement it states is
definitional for the package, not tied to a specific rule. It applies to every constant this package
will ever carry.

---

## RULE Entries

## RULE-SQE-017: Escalation tiers are evidence recommendations, not commercial decisions (`escalation.py`, #119)

**Decision:** `evaluate_escalation` recommends only one quality-engineering tier: `NONE`,
`MONITOR`, `SCAR_REQUIRED`, `CONTAINMENT_REQUIRED`, or `EXECUTIVE_REVIEW`. It retains every
evaluated score and optional recurrence trigger, selects the highest fired tier, and returns
`INDETERMINATE` for an unrated scorecard. The tier-ladder structure is informed by AIAG CQI-20's
corrective-action escalation discipline; all numeric thresholds are caller-configurable engineering
heuristics with no standards citation.

**Basis:** AIAG CQI-20 supports disciplined corrective-action escalation, but it supplies no
numeric supplier score or recurrence threshold. ISO 9001 §8.4 / §10.2 and IATF 16949 §8.4 require
organization-determined supplier controls; they do not authorize this engine to make commercial
decisions.

**Consequence:** The engine never recommends a commercial action. Any commercial response remains
the decision of an authorized business owner. An indeterminate supplier is neither cleared nor
escalated.

## RULE-SQE-001: On-time / in-full / OTIF arithmetic has no published source

**Decision:** `quality_core.sqe.otif` reports three separate figures over one shared denominator
(`delivery_count`, the number of matched deliveries): `on_time_pct` (deliveries arriving inside the
configured window around `promised_date`), `in_full_pct` (deliveries meeting the configured in-full
tolerance against `quantity_ordered`), and `otif_pct` (the **strict conjunction** — a delivery
counts only when `is_on_time and is_in_full`). `otif_pct` is never the average of the other two.

**Source:** None. No AIAG, ISO, IATF, or CQI-20 clause defines on-time, in-full, or OTIF
arithmetic. ISO 9001:2015 §8.4 and IATF 16949:2016 §8.4 require that external providers be
evaluated and monitored against criteria the organization determines; they supply no window, no
tolerance, and no formula. No `CITATIONS.tsv` row backs this rule.

**Rationale:** Delivery performance is a commercially negotiated measure, not a standardised one.
Reporting the three figures separately keeps the two independent failure modes (late but complete,
on-time but short) visible; collapsing them into an average would let a supplier that is 100%
on-time and 0% in-full read as 50% OTIF, which no purchaser would accept as delivery performance.
The conjunction is computed per delivery, before any percentage exists, so no averaging path is
reachable: percentages are produced only by `_pct(numerator: int, denominator: int)`, which takes
counts and never accepts a percentage.

**Applied In:** `packages/quality-core/src/quality_core/sqe/otif.py`
(`calculate_otif`, `_evaluate_delivery`, `_pct`, `OTIFResult`).

---

## RULE-SQE-002: The five `OTIFConfig` defaults are declared engineering heuristics

**Decision:** `OTIFConfig` ships these defaults, all caller-overridable and all labelled
`is_heuristic: True` in every result payload:

| Field | Default | Basis (no citation) |
|---|---|---|
| `early_tolerance_days` | `0` | An early arrival is a schedule deviation like any other; the permissive case is opted into via `early_counts_as_on_time`, not baked into the default window. |
| `late_tolerance_days` | `2` | A small non-zero grace period so ordinary transit/receiving-booking noise does not read as a delivery failure; two days is a declared default, not a measured or published value. |
| `early_counts_as_on_time` | `False` | Early delivery consumes inventory and space ahead of plan; treating it as on-time by default would hide it. Suppliers whose agreement permits early receipt set this `True`. |
| `in_full_tolerance_pct` | `0.0` | "In full" defaults to literally full — any shortfall is a shortfall. A non-zero tolerance is a commercial concession the caller must state explicitly. |
| `over_delivery_counts_as_in_full` | `True` | An over-delivery has met the ordered quantity. Under schema-valid data this never differs: `DeliveryRecord.reject_delivered_exceeding_ordered` forbids `quantity_delivered > quantity_ordered`, so the flag only diverges on a record built via `model_construct()`. |

**Source:** None. Every value above is an engineering default chosen for defensible behaviour. No
published standard names an on-time window, an in-full tolerance, or an early-delivery rule; these
values must not be presented as a standards requirement by any engine, MCP tool, canvas, or skill
layer. No `CITATIONS.tsv` row backs this rule.

**Rationale:** OTIF thresholds are set per supplier agreement. Encoding a default is unavoidable
(the engine must compute something when the caller supplies no config), so the defaults are chosen
to be the *strict* reading in each case — a figure produced with these defaults can only understate
supplier performance relative to a negotiated agreement, never overstate it. Every value is echoed
into `OTIFResult.heuristic_configuration` alongside `is_heuristic: True` and a shared `basis`
string, so a consumer can always see which rules produced a number and that they are heuristics.

**Applied In:** `packages/quality-core/src/quality_core/sqe/otif.py`
(`OTIFConfig`, `_heuristic_configuration`, `_HEURISTIC_BASIS`, `_STANDARDS_BASIS`).

---

## RULE-SQE-003: INDETERMINATE trigger set and whole-period rollup

**Decision:** `calculate_otif` returns `verdict="INDETERMINATE"` with every count and percentage
`None` when any of the following holds:

1. No delivery record matches `period.supplier_id` and the inclusive window
   `[period_start, period_end]` (including the empty-`deliveries` case).
2. Any matched delivery has a missing or unparseable `promised_date`.
3. Any matched delivery has a missing or unparseable `actual_delivery_date`.
4. Any matched delivery has `quantity_delivered is None` (the undecided sentinel).

Window membership is anchored on `promised_date` — the field the on-time math is measured against.
A matched-supplier delivery whose `promised_date` is `None` is held **in scope** and drives
INDETERMINATE; it is never silently dropped from the population. One blocking delivery makes the
**whole period** INDETERMINATE: no percentage is computed over the deliveries that do have complete
data.

**Source:** None — this is a data-honesty rule, not a standards requirement. It follows
`DeliveryRecord`'s own contract (`schema.py`): `quantity_delivered=None` is the undecided sentinel
and must never be coerced to `0` or to `quantity_ordered`, and `_parse_date_lenient` resolves a
missing or unparseable date to `None` rather than imputing one.

**Rationale:** Silent exclusion and partial computation are both confident verdicts on absent data.
Dropping an undated delivery would shrink the denominator and *raise* the reported percentages;
computing over the decided remainder would report a figure that looks like a measurement of the
period but is a measurement of an unstated subset. A caller who needs a partial figure can filter
the input themselves and see exactly what they excluded. No date is ever imputed from
`requested_date`, from `promised_date`, or from the period bounds.

**Applied In:** `packages/quality-core/src/quality_core/sqe/otif.py`
(`calculate_otif`, `_indeterminate`, `OTIFResult.verdict`, `OTIFResult.reason`).

---

## RULE-SQE-004: Supplier PPM / DPMO arithmetic has no published source (`ppm.py`, #116)

**Decision:** `quality_core.sqe.ppm.calculate_supplier_ppm` computes
`ppm = (total_defective / total_received) * 1_000_000` and, when every in-scope lot states
`opportunities_per_unit`, `dpmo = (total_defective / total_opportunities) * 1_000_000` where
`total_opportunities = sum(quantity_received * opportunities_per_unit)`.

**Basis:** None. This is generic industry arithmetic. No AIAG, ISO, IATF, or CQI-20 clause defines
a PPM formula or a DPMO opportunity model. ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4
require that external providers be evaluated and monitored against criteria the organization
determines; they establish *that* suppliers are evaluated, never any arithmetic. Those clauses are
therefore **not** cited as the source of this formula, and `CITATIONS.tsv` gains no row for it —
there is no standards quotation to check. The module docstring states the same thing.

**Consequence:** PPM and DPMO are reported in separately named fields and are never substituted for
one another: a DPMO figure quoted as PPM understates the rate by the opportunity multiplier.

---

## RULE-SQE-005: `sample_adequacy_minimum` default = 1000 received units (heuristic, `ppm.py`, #116)

**Decision:** `PPMConfig.sample_adequacy_minimum` defaults to **1000 received units**. A period
whose received total is below the minimum still returns its computed rate, flagged with a warning
and a recommendation; the figure is never suppressed and the minimum never changes the verdict.

**Basis:** None — this is a declared engineering heuristic, not a standard. There is no
published PPM sample-size standard (see E0, #114). The rationale is arithmetic volatility, not
authority: PPM is a per-million projection, so at low denominators a single defect swings it
enormously (1 defect in 100 units reads as 10,000 PPM; the same defect in 10,000 units reads as
100 PPM). 1000 units is the round order of magnitude at which one defect moves the figure by
1000 PPM rather than by tens of thousands. Any customer-agreed sample basis outranks it.

**Consequence:** The value is caller-overridable via `PPMConfig(sample_adequacy_minimum=...)`, and
every result payload carries `sample_adequacy = {"minimum": ..., "meets_minimum": ...,
"is_heuristic": True, "basis": "declared engineering default, no standards citation — see
ASSUMPTIONS_LOG.md"}`. The `is_heuristic` flag and the `basis` string are part of the contract:
relabelling either as a standards citation is a defect, not a wording change.

---

## RULE-SQE-006: INDETERMINATE trigger set for supplier PPM (`ppm.py`, #116)

**Decision:** `calculate_supplier_ppm` returns `verdict="INDETERMINATE"` with `ppm=None` and
`numerator=None` (never `0.0`, never a partial rate) when any of the following holds:

1. No lot matches `period.supplier_id` inside the inclusive window — an empty period.
2. The in-scope lots total zero received units — a zero denominator.
3. Any in-scope lot carries `defect_count is None`, the undecided sentinel — the period is
   INDETERMINATE as a whole and **no rate is computed over the decided remainder**.
4. Any lot matching `period.supplier_id` carries `receipt_date is None` — it cannot be confirmed
   inside the window, so it is held **in scope** and drives INDETERMINATE rather than being
   silently excluded.

**Basis:** None — undecided-sentinel software contract / data-honesty rule declared in `schema.py`
("downstream engines must resolve `None` to INDETERMINATE; they must never coerce it to `0`"),
extended to `receipt_date` by the same reasoning. Trigger 4 is the non-obvious one: silently dropping
an undated lot would be a confident verdict built on absent data — the precise failure this engine
exists to prevent.

**Consequence:** `0.0` PPM is emitted only from lots that were decided and decided clean. The
INDETERMINATE result is built through the same dataclass constructor as the MEASURED result — same
fields, `None` where unknown — and `denominator`/`lot_count` are still reported when knowable,
because what was received remains knowable even when what was defective does not.

---


## RULE-SQE-007: Vendor-scorecard weights are configurable engineering heuristics (`scorecard.py`, #118)

**Decision:** `ScorecardConfig` defaults to quality / delivery / cost weights of **0.60 / 0.40 /
0.0**. The three finite, non-boolean weights must each lie in `[0, 1]` and must total 1.0 within a
tight floating-point tolerance. The engine raises for a non-summing configuration; it never
normalizes or redistributes weights.

**Basis:** **None — these values are SME-approved engineering heuristics with no standards
citation.** ISO 9001:2015 §8.4 and IATF 16949:2016 §8.4 require supplier evaluation against
organization-determined criteria but define no dimension weight.

**Consequence:** The top-level heuristic-configuration payload labels the weight object and each
individual weight with `is_heuristic: True` and a basis containing `no standards citation`.

---

## RULE-SQE-008: Linear score curves and A/B/C bands are configurable engineering heuristics (`scorecard.py`, #118)

**Decision:** The default PPM curve maps **0 PPM to 100** and **10,000 PPM to 0**. The default
delivery curve maps **100% strict-conjunction OTIF to 100** and **0% OTIF to 0**. Both interpolate
linearly and clamp beyond their endpoints. Bands default to **A at 90.0 or above**, **B at 75.0
through below 90.0**, and **C below 75.0**. Band assignment uses the unrounded composite.

**Basis:** **None — every endpoint and boundary is an engineering heuristic with no standards
citation.** The defaults provide an explicit, testable starting contract approved for #118; a
supplier agreement or organization-specific calibration outranks each one.

**Consequence:** Curves and bands are caller-configurable. Every serialized endpoint and boundary,
plus its containing object, carries `is_heuristic: True` and `no standards citation` basis text.

---

## RULE-SQE-009: A weighted undecided dimension suppresses the whole scorecard (`scorecard.py`, #118)

**Decision:** Every positively weighted dimension must have measured source evidence. An
`INDETERMINATE` PPM or OTIF result, or unusable weighted COPQ evidence, makes the scorecard
`INDETERMINATE` with `composite_score=None` and `band=None`. Source evidence and blocker reasons
remain in the dimension payload. A zero-weight dimension is omitted; its weight is not reassigned.

**Basis:** This is the no-imputation policy already used by the PPM and OTIF engines, applied to
their composite. A rating built by dropping an undecided weighted input would overstate confidence.
It is a data-honesty rule with no standards citation, not a numeric standards criterion.

**Consequence:** No source metric is replaced with zero or a perfect score, no band is emitted for
partial evidence, and omitted dimensions are stated explicitly.

---

## RULE-SQE-010: COPQ is optional and has no default score curve (`scorecard.py`, #118)

**Decision:** Cost defaults to zero weight and is omitted without changing the 0.60 / 0.40 quality
and delivery weights. Supplied COPQ evidence is not scored at zero cost weight. A positive cost
weight requires an explicit `LinearScoringCurve`, cost items, and usable revenue evidence; the
engine delegates the arithmetic to `estimate_copq` and scores only
`copq_percentage_of_revenue`. Missing or unusable weighted cost evidence makes the scorecard
`INDETERMINATE`; its weight is never redistributed.

**Basis:** COPQ arithmetic is owned by `quality_core.copq`. There is no defensible universal COPQ
percentage-of-revenue threshold, so a default cost curve would imply authority that does not exist.
This scorecard policy is an engineering heuristic with no standards citation.

**Consequence:** Callers that elect to weight cost must provide their own defensible curve and
revenue basis. `scorecard.py` contains no COPQ arithmetic.

---

## RULE-SQE-011: SCAR "Root-Cause Requirement" section heading (`scar.py`, #120)

**Decision.** The generated SCAR carries a **Root-Cause Requirement** section stating that the
supplier must establish and state the *systemic* root cause — continuing to ask why past any
individual- or task-level explanation until the procedure, policy, or practice that allowed the
problem to occur and to escape is identified. The engine requests and validates that root cause; it
never authors, infers, or substitutes one (see "Process Design Decisions" below).

**Source.** Ford Global 8D Manual and AIAG CQI-20 (2nd Edition, 2018), reused verbatim from
`rca/ASSUMPTIONS_LOG.md` RULE 3 / RULE 4 — the same manuals at the same lines already verified
during the RCA milestone, cited here for a new purpose (the SCAR heading text, not the 5-Why
validator's own logic):

> Essentially, this involves asking "why" of the root cause until the cause is established.

> root of the root cause. The question can be asked more or less 5 times, it doesn't have to be 5!

> The systemic root cause(s) addresses, "Why did the system or planning process fail to identify the cause of the problem and the non-discovery?" The systemic root cause typically is understood last and diligence is required to address thoroughly.

**Applied In:** `packages/quality-core/src/quality_core/sqe/scar.py`
(`_build_sections`, `SCARSection(rule_id="RULE-SQE-011")`). Manifest rows: `CITATIONS.tsv`
`RULE-SQE-011` at Ford Global 8D src_line 2003 / 2004 and AIAG CQI-20 src_line 1685.

---

## RULE-SQE-012: SCAR "Corrective-Action Requirement" section heading (`scar.py`, #120)

**Decision.** The generated SCAR carries a **Corrective-Action Requirement** section stating that
the supplier must define and implement the permanent corrective action(s) that resolve the
established systemic root cause — changing only the affected product is not a corrective action.

**Source.** Ford Global 8D Manual, reused verbatim from `rca/ASSUMPTIONS_LOG.md` RULE 4 (same
manual, same lines):

> there is normally a procedure, a policy, or a (systemic) practice that has allowed you pass. We call this the 'root cause of the root cause.' This must be established and resolved.

> These systemic problems need to be fixed. The goal is to change the system that allowed the problem to occur in the first place and prevent problems from arising similar.

**Applied In:** `packages/quality-core/src/quality_core/sqe/scar.py`
(`_build_sections`, `SCARSection(rule_id="RULE-SQE-012")`). Manifest rows: `CITATIONS.tsv`
`RULE-SQE-012` at Ford Global 8D src_line 1991 / 2026.

---

## RULE-SQE-013: SCAR "Prevention / Read-Across" section heading (`scar.py`, #120)

**Decision.** The generated SCAR carries a **Prevention / Read-Across** section requiring the
supplier to identify every other part, product, line, and process to which the same systemic root
cause applies, and to extend the corrective action to them so a similar problem cannot arise there.

**Source.** Ford Global 8D Manual src_line 2026, reused verbatim from `rca/ASSUMPTIONS_LOG.md`
RULE 4. This is the same sentence cited by RULE-SQE-012: it genuinely supports both corrective
action ("need to be fixed" / "change the system") and prevention ("prevent problems from arising
similar") in one statement, so it is recorded under both sites in `CITATIONS.tsv` — the manifest's
duplicate check is on the `(site, quote)` pair, not on the quote alone.

> These systemic problems need to be fixed. The goal is to change the system that allowed the problem to occur in the first place and prevent problems from arising similar.

**Applied In:** `packages/quality-core/src/quality_core/sqe/scar.py`
(`_build_sections`, `SCARSection(rule_id="RULE-SQE-013")`). Manifest row: `CITATIONS.tsv`
`RULE-SQE-013` at Ford Global 8D src_line 2026.

---

## RULE-SQE-014: SCAR "Problem Definition" section heading (`scar.py`, #181)

**Decision.** The generated SCAR carries a **Problem Definition** section requiring the supplier
to describe the stated problem factually and in quantifiable terms by identifying what is wrong
with what. It does not infer or state a cause.

**Source.** Ford Global 8D Manual src_line 277:

> Describe the internal/external problem by identifying 'what is wrong with what', and detail the problem in quantifiable terms (Description of the problem).

**Applied In:** `packages/quality-core/src/quality_core/sqe/scar.py`
(`_build_sections`, `SCARSection(rule_id="RULE-SQE-014")`). Manifest row: `CITATIONS.tsv`
`RULE-SQE-014` at Ford Global 8D src_line 277.

---

## RULE-SQE-015: SCAR "Interim Containment Requirement" section heading (`scar.py`, #181)

**Decision.** The generated SCAR carries an **Interim Containment Requirement** section requiring
the supplier to define, verify, and implement interim containment while permanent corrective
action is pending, and to validate the containment's effectiveness. A supplied `due_date` is
caller-provided SCAR data, not a Ford or CQI-20 deadline mandate.

**Source.** Ford Global 8D Manual src_line 282:

> Define, verify, and implement the Interim Containment Action (AIC) to isolate the effects of the problem of any internal/external client until they are implemented Permanent Corrective Actions (PCAs). Validate the effectiveness of the measures of containment.

**Applied In:** `packages/quality-core/src/quality_core/sqe/scar.py`
(`_build_sections`, `SCARSection(rule_id="RULE-SQE-015")`). Manifest row: `CITATIONS.tsv`
`RULE-SQE-015` at Ford Global 8D src_line 282.

---

## RULE-SQE-016: SCAR "Verification-of-Effectiveness Requirement" section heading (`scar.py`, #181)

**Decision.** The generated SCAR carries a **Verification-of-Effectiveness Requirement** section
requiring the supplier to provide an effectiveness statement supported by measured results. The
existing `CLOSABLE` gate remains an engineering closure policy; this section does not alter it.

**Source.** AIAG CQI-20 Effective Problem Solving (2nd Edition, 2018) src_line 2287:

> Success of corrective actions is to be validated by gathering and analyzing quantifiable data.

**Applied In:** `packages/quality-core/src/quality_core/sqe/scar.py`
(`_build_sections`, `SCARSection(rule_id="RULE-SQE-016")`). Manifest row: `CITATIONS.tsv`
`RULE-SQE-016` at AIAG CQI-20 src_line 2287.

---

## RULE-SQE-018: Vendor-rating Excel export renders no new standard or threshold (`export.py`, #149)

**Decision:** `quality_core.sqe.export` (`build_sqe_workbook` / `export_sqe_workbook`)
presents the already-computed PPM, OTIF, and vendor-scorecard results as a live-formula
`.xlsx` workbook. It introduces no new numeric constant: PPM (`=defects/total*1000000`),
OTIF (`=on_time_in_full/total_deliveries`), and the weighted composite
(`=SUMPRODUCT(weights, metrics)`) are the same arithmetic `ppm.py`/`otif.py`/`scorecard.py`
already perform, re-expressed as live Excel formulas over cells populated from each engine's
own result payload. Every heuristic value the workbook renders (PPM sample-adequacy minimum,
OTIF window/tolerance, scorecard weights/curves/bands, escalation thresholds) is copied
verbatim from that engine payload's own `is_heuristic`/`basis` disclosure and is never
re-typed or re-derived in the exporter, and every such column/row is visibly labelled
`(HEURISTIC)` — carrying forward the v0.9.0 no-standard-implied invariant into the export
surface.

**Source:** None new. See the "Note on the No-Standard-Implied Invariant" section above this
log and `RULE-SQE-001`/`RULE-SQE-004`/`RULE-SQE-007`/`RULE-SQE-014`.

**Applied In:** `packages/quality-core/src/quality_core/sqe/export.py`
(`build_sqe_workbook`, `_row_record`, `_metadata_rows`).

---

## Process Design Decisions (no standard implied)

These are engineering and process decisions taken while building `scar.py` (#120). **None of them
is a standards claim**, none is backed by a `CITATIONS.tsv` row, and none may be presented as one
by any engine, MCP tool, canvas, or skill layer. They are recorded separately from the cited RULE
entries above for exactly that reason.

1. **All six SCAR section headings carry citations.** The generator renders the D2–D7 sequence:
   problem definition, interim containment, root cause, corrective action, verification of
   effectiveness, and prevention/read-across. `SCARRequest.due_date` remains caller-provided SCAR
   data: it is carried onto `SCARResult.due_date`, may be presented with containment when supplied,
   and its absence raises a warning rather than inventing a date. The `CLOSABLE` gate remains the
   existing engineering closure policy; the D6 citation does not turn a supplier statement into an
   authoritative closure verdict.

2. **The root-cause authorship invariant is not configurable.** `generate_scar` never authors,
   infers, or synthesizes a root cause. `SCARResult.root_cause` is assigned only by
   `_root_cause_from_linkage`, which copies `linkage["supplier_root_cause"].raw_result`'s own
   `root_cause` value verbatim, and is `None` whenever no supplier chain could be parsed. There is
   no fallback string, no template, and no `SCARConfig` flag that relaxes this.

3. **RCA linkage validates 5-Why only, not Is/Is-Not.** `quality_core.rca.five_why.
   validate_five_why_chain` returns an accept/reject verdict that a SCAR status can be gated on;
   `quality_core.rca.is_is_not.scope_is_is_not` is a scoping tool with no such verdict, so gating
   on it would mean inventing an acceptance rule that neither the standard nor that engine states.
   Is/Is-Not evidence is therefore out of scope for E6 linkage.

4. **The `vendor_scorecard` linkage slot is deliberately `LINKAGE_NOT_AVAILABLE`.** The vendor
   scorecard engine (#118) is on `test`, but this SCAR release defers wiring it. The slot is
   present, fully tested, takes no input, has
   no branches, and never affects the SCAR status; `SCARConfig.evaluate_vendor_scorecard_linkage`
   only controls whether the placeholder key appears in the payload at all.

5. **`AWAITING_SUPPLIER_RESPONSE` is deliberately overloaded.** It covers both "issued, no response
   received yet" and "root cause accepted, but closure is blocked (no verification-of-effectiveness
   statement, or other linked evidence currently invalid)". The status vocabulary is fixed at six
   values and there is no seventh name for the second state, which is genuinely still open, not
   rejected, and not closable. The distinction is carried in `SCARResult.reason`.

6. **`INDETERMINATE` is a temporal-contradiction verdict, not a failure verdict.** A SCAR with no
   `date_issued` that nevertheless carries a supplier response and/or a verification statement is
   internally contradictory. The engine reports the contradiction rather than guessing which
   record is wrong — the same "undecided is never imputed" discipline as RULE-SQE-003/006.

7. **No sub-engine rule is re-encoded in `scar.py`.** No RCA anti-pattern code, NCR disposition
   value, or COPQ PAF category literal appears in this module; the sub-engines' findings are
   surfaced verbatim, so a rule can only ever change in the engine that owns it.


---

## No-Standard-Implied Declarations

- **PPM acceptance thresholds have no published standard.** Customer-specific PPM targets exist per OEM contract; none is a standard this repository may encode as authoritative.
- **The PPM and DPMO formulas themselves have no published standard.** They are generic industry arithmetic, attributable to no AIAG/ISO/IATF/CQI-20 clause, and are cited to nothing (RULE-SQE-004).
- **The PPM sample-adequacy minimum has no published standard.** `PPMConfig.sample_adequacy_minimum` defaults to **1000 received units** — a declared engineering heuristic justified by the volatility of a per-million rate at low denominators, caller-overridable, and labelled `is_heuristic: True` in every payload (RULE-SQE-005).
- **OTIF has no published standard.** The on-time window, the in-full tolerance, and whether early delivery counts as on-time are all **engineering heuristics** and must be caller-configurable. As implemented in `quality_core.sqe.otif` (E3, #117), the five `OTIFConfig` defaults — `early_tolerance_days=0`, `late_tolerance_days=2`, `early_counts_as_on_time=False`, `in_full_tolerance_pct=0.0`, `over_delivery_counts_as_in_full=True` — are declared engineering defaults carrying **no citation**; each is labelled `is_heuristic: True` in every result payload and is documented in RULE-SQE-002 above. Neither the on-time/in-full/OTIF arithmetic itself (RULE-SQE-001) nor these values may be presented as a standards requirement by any engine, MCP tool, canvas, or skill layer.
- **Vendor scorecard weights and A/B/C rating-band boundaries have no published standard.** The 0.60 / 0.40 / 0.0 weights, 0-to-10,000 PPM and 100%-to-0% OTIF curves, and 90 / 75 band boundaries are declared caller-configurable engineering heuristics labelled individually in every payload (RULE-SQE-007/008). Weighted undecided evidence suppresses the composite and band (RULE-SQE-009); COPQ remains omitted at zero weight and requires an explicit curve when weighted (RULE-SQE-010).
- **Escalation trigger levels have no published standard.** The escalation *ladder* is informed by CQI-20's problem-solving escalation discipline; the numeric triggers are not.
- **The SCAR status vocabulary, closure criteria, and deadline semantics have no published standard.** ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4 require that nonconformity drive corrective action; they name no status set, no closure test, and no package deadline semantics. `DRAFT`/`ISSUABLE`/`AWAITING_SUPPLIER_RESPONSE`/`RESPONSE_REJECTED`/`CLOSABLE`/`INDETERMINATE`, the order the status rules are evaluated in, and the rule that `CLOSABLE` requires a stated verification of effectiveness are engineering decisions recorded under "Process Design Decisions" above (#120). All six SCAR section headings (RULE-SQE-011/012/013/014/015/016) carry citations.
- Any constant introduced later without a published source behind it is to be labelled an **engineering heuristic**, never implied to be a standard.

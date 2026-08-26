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

## No-Standard-Implied Declarations

- **PPM acceptance thresholds have no published standard.** Customer-specific PPM targets exist per OEM contract; none is a standard this repository may encode as authoritative.
- **The PPM and DPMO formulas themselves have no published standard.** They are generic industry arithmetic, attributable to no AIAG/ISO/IATF/CQI-20 clause, and are cited to nothing (RULE-SQE-004).
- **The PPM sample-adequacy minimum has no published standard.** `PPMConfig.sample_adequacy_minimum` defaults to **1000 received units** — a declared engineering heuristic justified by the volatility of a per-million rate at low denominators, caller-overridable, and labelled `is_heuristic: True` in every payload (RULE-SQE-005).
- **OTIF has no published standard.** The on-time window, the in-full tolerance, and whether early delivery counts as on-time are all **engineering heuristics** and must be caller-configurable. As implemented in `quality_core.sqe.otif` (E3, #117), the five `OTIFConfig` defaults — `early_tolerance_days=0`, `late_tolerance_days=2`, `early_counts_as_on_time=False`, `in_full_tolerance_pct=0.0`, `over_delivery_counts_as_in_full=True` — are declared engineering defaults carrying **no citation**; each is labelled `is_heuristic: True` in every result payload and is documented in RULE-SQE-002 above. Neither the on-time/in-full/OTIF arithmetic itself (RULE-SQE-001) nor these values may be presented as a standards requirement by any engine, MCP tool, canvas, or skill layer.
- **Vendor scorecard weights and A/B/C rating-band boundaries have no published standard.** They are declared defaults, labelled as heuristics in every payload.
- **Escalation trigger levels have no published standard.** The escalation *ladder* is informed by CQI-20's problem-solving escalation discipline; the numeric triggers are not.
- Any constant introduced later without a published source behind it is to be labelled an **engineering heuristic**, never implied to be a standard.

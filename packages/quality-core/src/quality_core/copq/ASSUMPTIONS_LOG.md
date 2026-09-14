# Engineering Assumptions Log — Cost of Poor Quality (COPQ) Suite

**Package:** `quality_core.copq`
**Standard References:**
- ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge & *The Certified Six Sigma Green Belt Handbook* (2nd Edition, ASQ Quality Press): `/Users/sid/Documents/Upskill/SixSigma/COPQ/ASQ_six_sigma_green_belt_handb.md` (text layer extracted with `pdftotext -layout`; the line-matched source for `CITATIONS.tsv`), `/Users/sid/Documents/Upskill/SixSigma/COPQ/ASQ_six_sigma_green_belt_handb.pdf`, `/Users/sid/Documents/Upskill/SixSigma/COPQ/_new/ASQ-CSSGB-BoK-2014.pdf`
- Council for Six Sigma Certification (CSSC) *Lean Six Sigma Green Belt Certification Training Manual* (2018): `/Users/sid/Documents/Upskill/SixSigma/COPQ/Lean-Six-Sigma-Green-Belt-Certification-Training-Manual-CSSC-2018-06b.md` (text layer extracted with `pdftotext -layout`; the line-matched source for `CITATIONS.tsv`), `/Users/sid/Documents/Upskill/SixSigma/COPQ/Lean-Six-Sigma-Green-Belt-Certification-Training-Manual-CSSC-2018-06b.pdf`
- Lumafield Cost of Quality Report (2024, non-standard industry cross-reference benchmark): `/Users/sid/Documents/Upskill/SixSigma/COPQ/TheLumafieldCostofQualityReportpdf.pdf`

This document records every non-obvious engineering decision, published taxonomy, and architectural constraint used in the Cost of Poor Quality (COPQ) Suite (`quality_core.copq`).

---

## Note on the PAF Cost Model and Arithmetic Rollup Definitions

The Cost of Poor Quality suite implements the classical Prevention-Appraisal-Failure (PAF) cost model established by Feigenbaum and Juran and codified in the ASQ CSSGB Body of Knowledge and CSSC Lean Six Sigma curricula:

1. **Prevention Costs:** Investments incurred to prevent nonconformances and defects (e.g., quality planning, process capability evaluations, training, design reviews, error-proofing / poka-yoke).
2. **Appraisal Costs:** Expenses incurred to measure, inspect, or audit products and processes to evaluate conformance to requirements (e.g., receiving inspection, in-process testing, final inspection, gage calibration, quality audits).
3. **Internal Failure Costs:** Costs resulting from nonconformances detected prior to product delivery or service provision to the customer (e.g., scrap, rework, reinspection, sorting/containment, scrap material disposal, downtime).
4. **External Failure Costs:** Costs resulting from nonconformances detected after shipment or delivery to the customer (e.g., warranty claims, customer complaints, returns/recalls, field servicing, customer concessions).

### Core Arithmetic Rollups

- **Total Cost of Quality (CoQ):**
  $$\text{Total CoQ} = \text{Prevention} + \text{Appraisal} + \text{Internal Failure} + \text{External Failure}$$
- **Cost of Poor Quality (COPQ):**
  $$\text{COPQ} = \text{Internal Failure} + \text{External Failure}$$
- **Cost of Good Quality (CoGQ) / Conformance Cost:**
  $$\text{CoGQ} = \text{Prevention} + \text{Appraisal}$$
- **COPQ Percentage of Revenue / Sales:**
  $$\text{COPQ \%} = \frac{\text{COPQ}}{\text{Total Revenue}} \times 100$$

### Note on Industry Benchmarks and Engineering Heuristics

While the PAF categories and summation formulas are standardized, specific business multipliers (e.g., hourly labor rework rates, default overhead burden percentages, warranty exposure multipliers) are user-provided inputs or engineering heuristics. The Lumafield Cost of Quality Report is utilized strictly as an empirical industry cross-reference benchmark, not as an authoring standard.

---

## RULE Entries

## RULE 1: Prevention-Appraisal-Failure (PAF) Cost Category Taxonomy & Arithmetic Rollup Definitions

**Decision:** Establish canonical PAF cost taxonomy `Literal["Prevention", "Appraisal", "InternalFailure", "ExternalFailure"]` with case-insensitive alias normalization and deterministic arithmetic rollup properties (`total_cost`, `copq`, `cogq`, `copq_pct_revenue`) cited against the ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge and CSSC Lean Six Sigma curricula.

**Source:**
- *The Certified Six Sigma Green Belt Handbook* (2nd Ed.), Glossary, entry "cost of poor quality (COPQ)" (`ASQ_six_sigma_green_belt_handb.md` lines 27249–27255). The four category definitions are the parentheticals of that one entry; the prevention-cost parenthetical is quoted without its label because the extraction hyphenates "preven-tion" across a line break:
> "cost of poor quality (COPQ)—The costs associated with providing poor-quality products or services. There are four categories:"
> "internal failure costs (costs associated with defects found before the customer receives the product or service)"
> "external failure costs (costs associated with defects found after the customer receives the product or service)"
> "appraisal costs (costs incurred to determine the degree of conformance to quality requirements)"
> "costs incurred to keep failure and appraisal costs to a minimum"
- CSSC *Lean Six Sigma Green Belt Certification Training Manual* (2018), "The CoQ and the CoPQ" (`Lean-Six-Sigma-Green-Belt-Certification-Training-Manual-CSSC-2018-06b.md` lines 3920 and 3989):
> "CoPQ = External Failure Costs + Internal Failure Costs"
> "CoQ = CoPQ + Prevention Costs + Appraisal Costs"

**Source tension (recorded 2026-09-13, #245):** the two manuals do not agree on what "COPQ" denotes. The ASQ Handbook glossary defines COPQ as the costs of providing poor-quality products or services and lists *all four* PAF categories under it ("There are four categories: internal failure costs ..., external failure costs ..., appraisal costs ..., and prevention costs ..."). The CSSC manual defines COPQ as failure costs only ("CoPQ = External Failure Costs + Internal Failure Costs") and treats prevention and appraisal as the remainder of CoQ ("CoQ = CoPQ + Prevention Costs + Appraisal Costs"). The engine follows CSSC: `estimator.py` (module docstring, "COPQ (Internal + External Failure), Total Cost of Quality (CoQ = CoGQ + COPQ)") computes `total_copq = internal_failure_total + external_failure_total` and `total_coq = total_copq + cogq_total`, and the Core Arithmetic Rollups above are the same identities. This is a deliberate choice, not an oversight: the failure-only reading is the one both curricula use when they *calculate* COPQ, and it is the one the `copq_pct_revenue` and `internal_pct` / `external_pct` ratios need to be meaningful. Before 2026-09-13 the six quotations in this entry were paraphrases that appeared in no on-machine source (the manifest `src_line` values were placeholders 1–6); they were replaced with the verbatim passages above on the SME's ruling, and `test_copq_citations.py` now line-matches them against the extracted `.md` files.

**Rationale:** The Prevention-Appraisal-Failure (PAF) model, originally formulated by Armand Feigenbaum and Joseph Juran, is the globally recognized standard for Cost of Quality (CoQ) accounting in Six Sigma and Lean manufacturing frameworks. Conformance costs (Prevention and Appraisal) represent proactive investments in quality, whereas Nonconformance costs / COPQ (Internal and External Failure) represent financial waste resulting from defects. Providing structured row models with cost drivers (scrap, rework, containment, warranty, direct costs) and dataset aggregations ensures standard-compliant financial rollup.

**Applied In:** `packages/quality-core/src/quality_core/copq/schema.py` (`PAFCategory`, `PAF_CATEGORY_VALUES`, `PAF_CATEGORY_ALIASES`, `CostItem`, `COPQDataset`, `COPQ_SCHEMA`, `load_copq_csv`, `validate_copq`) and `packages/quality-core/src/quality_core/copq/estimator.py` (`estimate_copq`, `COPQEstimationResult`).

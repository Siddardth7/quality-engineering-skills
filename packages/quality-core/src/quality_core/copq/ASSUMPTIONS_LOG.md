# Engineering Assumptions Log — Cost of Poor Quality (COPQ) Suite

**Package:** `quality_core.copq`
**Standard References:**
- ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge & *The Certified Six Sigma Green Belt Handbook* (2nd Edition, ASQ Quality Press): `/Users/sid/Documents/Upskill/SixSigma/ASQ_six_sigma_green_belt_handb.pdf`, `/Users/sid/Documents/Upskill/SixSigma/_new/ASQ-CSSGB-BoK-2014.pdf`
- Council for Six Sigma Certification (CSSC) *Lean Six Sigma Green Belt Certification Training Manual* (2018): `/Users/sid/Documents/Upskill/SixSigma/Lean-Six-Sigma-Green-Belt-Certification-Training-Manual-CSSC-2018-06b.pdf`
- Lumafield Cost of Quality Report (2024, non-standard industry cross-reference benchmark): `/Users/sid/Documents/Upskill/SixSigma/TheLumafieldCostofQualityReportpdf.pdf`

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

*(Header-only state: specific RULE entries will be populated in subsequent epics).*

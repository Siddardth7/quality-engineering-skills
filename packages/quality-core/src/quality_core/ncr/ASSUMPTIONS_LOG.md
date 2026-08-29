# Engineering Assumptions Log — Nonconformance Reporting (NCR) Suite

**Package:** `quality_core.ncr`
**Standard References:**
- ISO 9001:2015 Clause 8.7 "Control of nonconforming outputs": `/Users/sid/Documents/Upskill/SixSigma/NCR/ISO_9001_2015_Section_8_7.md` (or `/Users/sid/Documents/Upskill/SixSigma/NCR/ISO-9001-2015.pdf`)
- IATF 16949:2016 Clause 8.7 "Control of nonconforming outputs": `/Users/sid/Documents/Upskill/SixSigma/NCR/IATF_16949_2016_Section_8_7.md` (or `/Users/sid/Documents/Upskill/SixSigma/NCR/pdfcoffee.com_iatf16949-2016-standard-pdf-free.pdf`)

This document records every non-obvious engineering decision, published taxonomy, and architectural constraint used in the Nonconformance Reporting (NCR) Suite (`quality_core.ncr`).

---

## Note on Qualitative NCR Governance and Engineering Heuristics

Unlike statistical quality engines (such as MSA Gage R&R variance components and $K$-factors or SPC Shewhart control limit constants $A_2, D_4, d_2^*$), Nonconformance Reporting under ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7 is a qualitative compliance, containment, and disposition governance framework.

**No published standard mandates specific mathematical formulas or numerical thresholds for disposition routing.**

Instead, the deterministic engines in `quality_core.ncr` implement structural logic validation and workflow routing:
1. **ISO 9001:2015 §8.7 Compliance:** Mandates nonconforming output identification, segregation/containment, customer notification, documented information (description, actions taken, concessions obtained, deciding authority), and reverification upon correction.
2. **IATF 16949:2016 §8.7 Automotive Extensions:** Enforces mandatory customer concession permits for "Use-As-Is" and rework dispositions (§8.7.1.1), suspect product containment (§8.7.1.3), risk analysis prior to rework/repair (§8.7.1.4, §8.7.1.5), and rendering scrap unusable prior to disposal (§8.7.1.7).
3. **Disposition Logic & Engineering Heuristics:** Specific business rules (e.g., disposition authority levels, containment urgency escalation, recurring defect severity thresholds) are engineering heuristics and are explicitly labeled as internal platform design choices rather than standard-mandated constants.

---

## RULE Entries

## RULE 1: Disposition Vocabulary & Objective-Evidence Nonconformance Statement Standards

**Decision:** Define canonical disposition categories `Literal["Scrap", "Rework", "UseAsIs", "ReturnToVendor", "Regrade"]` (with `None` representing undecided/pending records prior to adjudication) and enforce objective-evidence statement fields (`part_lot_id`, `defect_description`, `requirement_violated`, `quantity_affected`, `detection_point`) cited against ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7.

**Source:**
- ISO 9001:2015 Clause 8.7.1 & 8.7.2:
> "The organization shall deal with nonconforming outputs in one or more of the following ways: a) correction; b) segregation, containment, return or suspension of provision of products and services; c) informing the customer; d) obtaining authorization for acceptance under concession."
> "The organization shall retain documented information that: a) describes the nonconformity; b) describes the actions taken; c) describes any concessions obtained; d) identifies the authority deciding the action in respect of the nonconformity."
- IATF 16949:2016 Clause 8.7.1.1, 8.7.1.3, 8.7.1.4, 8.7.1.7:
> "The organization shall obtain customer authorization prior to further processing for "use as is" and rework dispositions of nonconforming product."
> "The organization shall ensure that product with unidentified or suspect status is classified and controlled as nonconforming product. The organization shall ensure that all appropriate manufacturing personnel receive training for containment of suspect and nonconforming product."
> "The organization shall utilize risk analysis (such as FMEA) methodology to assess risks in the rework process prior to a decision to rework the product."
> "The organization shall have a documented process for disposition of nonconforming product not eligible for rework or repair. For product not meeting requirements, the organization shall verify that the product to be scrapped is rendered unusable prior to disposal."

**Rationale:** ISO 9001:2015 §8.7.1 and IATF 16949:2016 §8.7 define the fundamental taxonomy of nonconformance control actions: correction (rework), concession/authorization ("use as is", regrade), segregation/return ("return to vendor"), and rendering scrap unusable prior to disposal ("scrap"). ISO 9001:2015 §8.7.2 mandates retained documented information describing the nonconformity, actions taken, concessions obtained, and the deciding authority. Adopting these 5 canonical disposition states and 5 required objective-evidence fields aligns nonconformance capture with international quality standards.

**Applied In:** `packages/quality-core/src/quality_core/ncr/schema.py` (`Disposition`, `DISPOSITION_VALUES`, `DISPOSITION_ALIASES`, `NonconformanceRecord`, `NCRDataset`, `NCR_SCHEMA`, `load_ncr_csv`, `validate_ncr`); `packages/quality-core/src/quality_core/ncr/nonconformance.py` (`write_nonconformance`, `recommend_disposition`, `NonconformanceWriteResult`, `DispositionRecommendation`).

## RULE 2: Safety-Critical Disposition Gate Precedence Over Supplier Origin

**Decision:** Prioritize the safety-critical disposition evaluation gate (`safety_critical is True`) over supplier defect origin routing (`is_supplier_origin`). When a defect involves a safety or regulatory critical characteristic and is not reworkable (`is_reworkable is not True`), the disposition engine strictly recommends `disposition="Scrap"` with mandatory defacing/destruction and Material Review Board (MRB) / Safety Officer approval authority, rather than releasing the part for vendor return (`ReturnToVendor`). Commercial recovery is preserved by issuing a Supplier Corrective Action Request (SCAR) and debit memo recommendation.

**Source:**
- IATF 16949:2016 Clause 8.7.1.7:
> "The organization shall have a documented process for disposition of nonconforming product not eligible for rework or repair. For product not meeting requirements, the organization shall verify that the product to be scrapped is rendered unusable prior to disposal."
- IATF 16949:2016 Clause 8.7.1.3:
> "The organization shall ensure that product with unidentified or suspect status is classified and controlled as nonconforming product. The organization shall ensure that all appropriate manufacturing personnel receive training for containment of suspect and nonconforming product."
- ISO 9001:2015 Clause 8.7.1:
> "The organization shall deal with nonconforming outputs in one or more of the following ways: a) correction; b) segregation, containment, return or suspension of provision of products and services; c) informing the customer; d) obtaining authorization for acceptance under concession."

**Rationale:** Under IATF 16949:2016 §8.7.1.7, nonconforming automotive products ineligible for rework or repair must be verified as rendered unusable prior to disposal. Returning non-reworkable safety-critical components to external suppliers without mandatory defacing creates a severe risk of inadvertent re-entry into the manufacturing supply chain. Safety-critical non-reworkable defects therefore mandate immediate scrap rendering, witnessing, and MRB / Safety Officer oversight. Commercial remedy (SCAR and debit memo) is issued in parallel to recover costs without compromising physical containment.

**Applied In:** `packages/quality-core/src/quality_core/ncr/nonconformance.py` (`recommend_disposition`).


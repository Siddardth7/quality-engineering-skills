# Engineering Assumptions Log — Nonconformance Reporting (NCR) Suite

**Package:** `quality_core.ncr`
**Standard References:**
- ISO 9001:2015 Clause 8.7 "Control of nonconforming outputs": `/Users/sid/Documents/Upskill/SixSigma/ISO_9001_2015_Section_8_7.md` (or `/Users/sid/Documents/Upskill/SixSigma/ISO-9001-2015.pdf`)
- IATF 16949:2016 Clause 8.7 "Control of nonconforming outputs": `/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_7.md` (or `/Users/sid/Documents/Upskill/SixSigma/pdfcoffee.com_iatf16949-2016-standard-pdf-free.pdf`)

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

*(Header-only state: specific RULE entries will be populated in subsequent epics).*

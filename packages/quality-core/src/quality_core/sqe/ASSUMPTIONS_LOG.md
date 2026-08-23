# Engineering Assumptions Log — Supplier Quality Engineering (SQE) Suite

**Package:** `quality_core.sqe`
**Standard References:**
- ISO 9001:2015 §8.4 (Control of externally provided processes, products and services) and §10.2 (Nonconformity and corrective action): `/Users/sid/Documents/Upskill/SixSigma/ISO_9001_2015_Section_8_4_and_10_2.md`
- IATF 16949:2016 §8.4 (supplemental supplier management requirements): `/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_4.md`
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

---

## No-Standard-Implied Declarations

- **PPM acceptance thresholds have no published standard.** Customer-specific PPM targets exist per OEM contract; none is a standard this repository may encode as authoritative.
- **OTIF has no published standard.** The on-time window, the in-full tolerance, and whether early delivery counts as on-time are all **engineering heuristics** and must be caller-configurable.
- **Vendor scorecard weights and A/B/C rating-band boundaries have no published standard.** They are declared defaults, labelled as heuristics in every payload.
- **Escalation trigger levels have no published standard.** The escalation *ladder* is informed by CQI-20's problem-solving escalation discipline; the numeric triggers are not.
- Any constant introduced later without a published source behind it is to be labelled an **engineering heuristic**, never implied to be a standard.

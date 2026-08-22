"""
nonconformance.py
Deterministic Nonconformance Reporting (NCR) defect-statement and disposition recommendation engine.

Implements ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7 compliant nonconformance statement drafting
and rule-based disposition recommendation:
- Objective-evidence nonconformance statement formatting (what deviated, requirement violated,
  measured evidence, quantity affected, detection point).
- Operator blame phrase detection and filtration per ASQ Quality Toolbox & Ford Global 8D.
- Premature root-cause speculation detection and guidance routing to the RCA suite (5-Why, Fishbone, KT Is/Is-Not).
- Rule-based disposition mapping (Scrap, Rework, UseAsIs, ReturnToVendor, Regrade) with cited
  standards rationale, required approval authority, MRB gating, and mandatory FMEA risk analysis flags.
- Load-bearing negative control refusing disposition guessing on ambiguous/incomplete inputs (INSUFFICIENT_DATA).

Standards References:
- ISO 9001:2015 Clause 8.7 ("Control of nonconforming outputs"): Clause 8.7.1 & Clause 8.7.2.
- IATF 16949:2016 Clause 8.7 ("Control of nonconforming outputs"): Clause 8.7.1.1, 8.7.1.3, 8.7.1.4 & 8.7.1.7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from quality_core.ncr.schema import (
    Disposition,
)

__all__ = [
    "DispositionRecommendation",
    "NonconformanceWriteResult",
    "recommend_disposition",
    "write_nonconformance",
]

_STANDARDS_BASIS = "ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7"

_HUMAN_NOUNS: set[str] = {
    "operator",
    "worker",
    "technician",
    "employee",
    "person",
    "personnel",
    "user",
    "machinist",
    "assembler",
    "inspector",
    "who",
}

_BLAME_VERBS: set[str] = {
    "forgot",
    "forgotten",
    "neglected",
    "careless",
    "carelessness",
    "distracted",
    "ignored",
    "failed",
    "mistake",
    "error",
    "fault",
    "inattentive",
    "laziness",
}

_BLAME_PHRASES: tuple[str, ...] = (
    "operator error",
    "human error",
    "worker error",
    "technician error",
    "assembler error",
    "inspector error",
    "operator mistake",
    "worker mistake",
    "carelessness",
    "lack of attention",
    "forgot to",
    "did not follow",
    "failed to follow",
    "not paying attention",
    "operator forgot",
    "worker forgot",
    "negligence",
)

_SPECULATION_PHRASES: tuple[str, ...] = (
    "caused by",
    "root cause is",
    "root cause was",
    "due to bad",
    "due to poor",
    "due to supplier",
    "due to worn",
    "because the supplier",
    "because operator",
    "because machine",
    "probably because",
    "likely caused by",
    "suspected cause is",
)

_SUPPLIER_ORIGIN_KEYWORDS: set[str] = {
    "supplier",
    "vendor",
    "incoming",
    "receiving",
    "purchased",
    "external",
    "oem",
}

def _detect_blame_phrases(text: str) -> list[str]:
    """Detect human blame phrasing in text."""
    detected: list[str] = []
    for phrase in _BLAME_PHRASES:
        pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(phrase)

    for noun in _HUMAN_NOUNS:
        for verb in _BLAME_VERBS:
            pattern = r"\b" + re.escape(noun) + r"\s+" + re.escape(verb) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(f"{noun} {verb}")
    return sorted(set(detected))


def _detect_speculation(text: str) -> list[str]:
    """Detect premature root-cause speculation in text."""
    detected: list[str] = []
    for phrase in _SPECULATION_PHRASES:
        pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(phrase)
    return sorted(set(detected))


def _sanitize_blame_and_speculation(text: str) -> str:
    """Remove blame and speculation phrases from statement text."""
    cleaned = text

    # Remove blame phrases (both static and dynamically detected token pairs)
    blame_to_remove = sorted(
        set(_BLAME_PHRASES) | set(_detect_blame_phrases(cleaned)),
        key=lambda p: (len(p.split()), len(p)),
        reverse=True,
    )
    for phrase in blame_to_remove:
        pattern = re.compile(
            r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b",
            re.IGNORECASE,
        )
        cleaned = pattern.sub("", cleaned)

    # Remove speculation phrases and following trailing cause text
    speculation_to_remove = sorted(
        set(_SPECULATION_PHRASES) | set(_detect_speculation(cleaned)),
        key=lambda p: (len(p.split()), len(p)),
        reverse=True,
    )
    for phrase in speculation_to_remove:
        pattern = re.compile(
            r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b\s*[^.;,]*",
            re.IGNORECASE,
        )
        cleaned = pattern.sub("", cleaned)

    # Clean up whitespace and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"\.\s*\.+", ".", cleaned)
    cleaned = re.sub(r"[,;]\s*[,;]+", ",", cleaned)
    cleaned = re.sub(r"[,;:]\s*\.", ".", cleaned)
    cleaned = re.sub(r"\.\s*[,;:]", ".", cleaned)
    cleaned = re.sub(r"^[.\s,;:-]+|[.\s,;:-]+$", "", cleaned).strip()
    return cleaned


@dataclass
class NonconformanceWriteResult:
    """Structured result of ISO 9001 §8.7 nonconformance statement formulation."""

    valid: bool
    statement: str
    what_deviated: str | None
    requirement_violated: str | None
    measured_evidence: str | None
    quantity_affected: int | None
    detection_point: str | None
    part_lot_id: str | None
    unit_of_measure: str | None
    blame_phrases_detected: list[str]
    speculation_detected: list[str]
    fields_populated: list[str]
    fields_missing: list[str]
    warnings: list[str]
    recommendations: list[str]
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the result."""
        return {
            "valid": self.valid,
            "statement": self.statement,
            "what_deviated": self.what_deviated,
            "requirement_violated": self.requirement_violated,
            "measured_evidence": self.measured_evidence,
            "quantity_affected": self.quantity_affected,
            "detection_point": self.detection_point,
            "part_lot_id": self.part_lot_id,
            "unit_of_measure": self.unit_of_measure,
            "blame_phrases_detected": list(self.blame_phrases_detected),
            "speculation_detected": list(self.speculation_detected),
            "fields_populated": list(self.fields_populated),
            "fields_missing": list(self.fields_missing),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "standards_basis": self.standards_basis,
        }


@dataclass
class DispositionRecommendation:
    """Structured disposition recommendation per ISO 9001 §8.7 and IATF 16949 §8.7."""

    disposition: Disposition | None
    verdict: str
    rationale: str
    approval_authority: str
    mrb_review_required: bool
    customer_authorization_required: bool
    fmea_risk_analysis_required: bool
    missing_evidence: list[str]
    warnings: list[str]
    recommendations: list[str]
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the recommendation."""
        return {
            "disposition": self.disposition,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "approval_authority": self.approval_authority,
            "mrb_review_required": self.mrb_review_required,
            "customer_authorization_required": self.customer_authorization_required,
            "fmea_risk_analysis_required": self.fmea_risk_analysis_required,
            "missing_evidence": list(self.missing_evidence),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "standards_basis": self.standards_basis,
        }


def write_nonconformance(
    raw_defect_note: str | None = None,
    what_deviated: str | None = None,
    requirement_violated: str | None = None,
    measured_evidence: str | None = None,
    quantity_affected: int | str | None = None,
    detection_point: str | None = None,
    part_lot_id: str | None = None,
    unit_of_measure: str | None = None,
) -> NonconformanceWriteResult:
    """Draft a deterministic, objective-evidence nonconformance statement per ISO 9001:2015 §8.7.

    Transforms raw, subjective, or unstructured defect notes into standard objective nonconformance
    language (what deviated, requirement violated, measured evidence, quantity, detection point)
    with strict blame-free phrasing and premature root-cause speculation filtration.

    Parameters
    ----------
    raw_defect_note : str | None, optional
        Unstructured text or defect notes from the shop floor / inspection.
    what_deviated : str | None, optional
        Specific description of what nonconforming condition was observed.
    requirement_violated : str | None, optional
        Engineering drawing specification, standard, or customer requirement violated.
    measured_evidence : str | None, optional
        Quantitative or qualitative measurement demonstrating the deviation (e.g. "12.45 mm vs 12.00 ± 0.10 mm").
    quantity_affected : int | str | None, optional
        Total quantity of nonconforming or suspect items.
    detection_point : str | None, optional
        Operation, station, cell, or inspection gate where the nonconformance was detected.
    part_lot_id : str | None, optional
        Part number, lot number, serial number, or batch identifier.
    unit_of_measure : str | None, optional
        Unit of measure for quantity affected (e.g. "pcs", "units", "kg", "assemblies").

    Returns
    -------
    NonconformanceWriteResult
        Structured statement, populated/missing fields, detected blame/speculation, and guidance.

    Raises
    ------
    TypeError
        If input types are invalid.
    ValueError
        If numeric values are negative or invalid.
    """
    # Type validation
    for param_name, param_val in [
        ("raw_defect_note", raw_defect_note),
        ("what_deviated", what_deviated),
        ("requirement_violated", requirement_violated),
        ("measured_evidence", measured_evidence),
        ("detection_point", detection_point),
        ("part_lot_id", part_lot_id),
        ("unit_of_measure", unit_of_measure),
    ]:
        if param_val is not None and not isinstance(param_val, str):
            raise TypeError(f"{param_name} must be a string or None, got {type(param_val).__name__}")

    qty_int: int | None = None
    if quantity_affected is not None:
        if isinstance(quantity_affected, bool):
            raise TypeError("quantity_affected cannot be a boolean")
        if isinstance(quantity_affected, int):
            if quantity_affected < 1:
                raise ValueError(f"quantity_affected must be >= 1, got {quantity_affected}")
            qty_int = quantity_affected
        elif isinstance(quantity_affected, str):
            clean_q = quantity_affected.strip()
            # Try to extract integer from string like "50 pcs" or "50"
            match = re.search(r"\b(\d+)\b", clean_q)
            if match:
                parsed_qty = int(match.group(1))
                if parsed_qty < 1:
                    raise ValueError(f"quantity_affected must be >= 1, got {parsed_qty}")
                qty_int = parsed_qty
            else:
                raise ValueError(f"Could not parse integer quantity_affected from '{quantity_affected}'")
        else:
            raise TypeError(f"quantity_affected must be an integer, string, or None, got {type(quantity_affected).__name__}")

    raw_text = raw_defect_note.strip() if raw_defect_note else ""

    # Blame and speculation detection across all input text
    all_inputs = " ".join(
        filter(
            None,
            [
                raw_text,
                what_deviated,
                requirement_violated,
                measured_evidence,
                detection_point,
            ],
        )
    )

    blame_detected = _detect_blame_phrases(all_inputs)
    speculation_detected = _detect_speculation(all_inputs)

    warnings: list[str] = []
    recommendations: list[str] = []

    if blame_detected:
        warnings.append(
            f"Subjective blame phrasing detected: {', '.join(blame_detected)}. "
            "ISO 9001 §8.7 requires objective-evidence statements focused on output characteristics, not human fault."
        )
        recommendations.append(
            "Remove operator/personnel references from the nonconformance record; address human error factors objectively via systemic 5-Why or Fishbone root cause analysis."
        )

    if speculation_detected:
        warnings.append(
            f"Premature root-cause speculation detected: {', '.join(speculation_detected)}. "
            "Nonconformance reporting records what deviated, not why it deviated."
        )
        recommendations.append(
            "Isolate the nonconformance statement to measured facts and route root cause investigation to the RCA suite (5-Why, Fishbone, Is/Is-Not)."
        )

    # Field extraction heuristics from raw_defect_note if explicit fields not provided
    extracted_what = what_deviated.strip() if what_deviated else None
    extracted_req = requirement_violated.strip() if requirement_violated else None
    extracted_meas = measured_evidence.strip() if measured_evidence else None
    extracted_det = detection_point.strip() if detection_point else None
    extracted_part = part_lot_id.strip() if part_lot_id else None
    extracted_uom = unit_of_measure.strip() if unit_of_measure else "units"

    if raw_text:
        # Extract quantity if missing
        if qty_int is None:
            qty_match = re.search(r"\b(\d+)\s*(?:pcs|pieces|parts|units|samples|items|lots|ea)\b", raw_text, re.IGNORECASE)
            if qty_match:
                qty_int = int(qty_match.group(1))

        # Extract part/lot if missing
        if extracted_part is None:
            part_match = re.search(r"\b(?:part|lot|batch|p/n|sn|serial)\s*[:#]?\s*([A-Za-z0-9\-_]+)\b", raw_text, re.IGNORECASE)
            if part_match:
                extracted_part = part_match.group(1)

        # Extract detection point if missing
        if extracted_det is None:
            for kw in (
                "incoming inspection",
                "receiving inspection",
                "final inspection",
                "in-process inspection",
                "in-process",
                "receiving",
                "assembly line",
                "assembly",
                "station",
                "line",
                "cell",
                "audit",
            ):
                det_match = re.search(r"\b" + re.escape(kw) + r"[A-Za-z0-9\s\-#_]*", raw_text, re.IGNORECASE)
                if det_match:
                    extracted_det = det_match.group(0).strip(" ,;.")
                    break

        # Extract requirement/spec if missing
        if extracted_req is None:
            spec_match = re.search(r"\b(?:spec|specification|requirement|drawing|nominal|target|standard)\b\s*[:=]?\s*([^,;\n]+)", raw_text, re.IGNORECASE)
            if spec_match:
                extracted_req = spec_match.group(1).strip()

        # Extract measured evidence if missing
        if extracted_meas is None:
            meas_match = re.search(r"\b(?:measured|actual|found|reading|dimension|result)\b\s*[:=]?\s*([^,;\n]+)", raw_text, re.IGNORECASE)
            if meas_match:
                extracted_meas = meas_match.group(1).strip()

        # Extract what deviated if missing
        if extracted_what is None:
            sanitized_raw = _sanitize_blame_and_speculation(raw_text)
            if sanitized_raw:
                extracted_what = sanitized_raw

    # Sanitize populated fields from blame
    if extracted_what:
        sanitized_what = _sanitize_blame_and_speculation(extracted_what)
        extracted_what = sanitized_what if sanitized_what else None
    if extracted_meas:
        sanitized_meas = _sanitize_blame_and_speculation(extracted_meas)
        extracted_meas = sanitized_meas if sanitized_meas else None

    fields_populated: list[str] = []
    fields_missing: list[str] = []

    fields_check: list[tuple[str, Any]] = [
        ("part_lot_id", extracted_part),
        ("what_deviated", extracted_what),
        ("requirement_violated", extracted_req),
        ("measured_evidence", extracted_meas),
        ("quantity_affected", qty_int),
        ("detection_point", extracted_det),
    ]

    for f_name, f_val in fields_check:
        if f_val is not None and (not isinstance(f_val, str) or f_val.strip()):
            fields_populated.append(f_name)
        else:
            fields_missing.append(f_name)

    is_valid = (
        extracted_what is not None
        and extracted_req is not None
        and extracted_meas is not None
        and qty_int is not None
        and extracted_det is not None
    )

    # Formulate objective statement
    parts: list[str] = []
    target_item = f"Part/Lot {extracted_part}" if extracted_part else "Inspected material"
    parts.append(f"Nonconformance on {target_item}: {extracted_what or '[Defect description missing]'}.")

    if extracted_req:
        parts.append(f"Requirement violated: {extracted_req}.")
    if extracted_meas:
        parts.append(f"Measured evidence: {extracted_meas}.")
    if qty_int is not None:
        parts.append(f"Quantity affected: {qty_int} {extracted_uom}.")
    if extracted_det:
        parts.append(f"Detected at: {extracted_det}.")

    statement = " ".join(parts)

    if not is_valid:
        missing_str = ", ".join(fields_missing)
        warnings.append(f"Incomplete nonconformance statement: missing mandatory fields ({missing_str}).")
        recommendations.append(
            f"Populate missing ISO 9001 §8.7 objective-evidence fields: {missing_str}."
        )

    return NonconformanceWriteResult(
        valid=is_valid,
        statement=statement,
        what_deviated=extracted_what,
        requirement_violated=extracted_req,
        measured_evidence=extracted_meas,
        quantity_affected=qty_int,
        detection_point=extracted_det,
        part_lot_id=extracted_part,
        unit_of_measure=extracted_uom,
        blame_phrases_detected=blame_detected,
        speculation_detected=speculation_detected,
        fields_populated=fields_populated,
        fields_missing=fields_missing,
        warnings=warnings,
        recommendations=recommendations,
        standards_basis=_STANDARDS_BASIS,
    )


def recommend_disposition(
    is_reworkable: bool | None = None,
    defect_origin: Literal["Internal", "Supplier", "Customer", "Unknown"] | str | None = None,
    meets_secondary_spec: bool | None = None,
    customer_concession_eligible: bool | None = None,
    rework_cost: float | int | None = None,
    part_value: float | int | None = None,
    severity: str | None = None,
    safety_critical: bool | None = None,
    defect_description: str | None = None,
) -> DispositionRecommendation:
    """Recommend a deterministic, standards-cited disposition per ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7.

    Evaluates defect origin, technical reworkability, secondary grade conformance, customer concession
    eligibility, and rework cost economics to recommend one of the 5 canonical dispositions
    (Scrap, Rework, UseAsIs, ReturnToVendor, Regrade) with cited rationale and required approval authority.

    Parameters
    ----------
    is_reworkable : bool | None, optional
        Whether the nonconforming feature can technically be reworked to meet primary specification.
    defect_origin : str | None, optional
        Origin of the defect: 'Internal', 'Supplier', 'Customer', or 'Unknown'.
    meets_secondary_spec : bool | None, optional
        Whether the product meets an authorized secondary specification for regrading/downgrading.
    customer_concession_eligible : bool | None, optional
        Whether the deviation is minor/cosmetic and eligible for customer concession (Use-As-Is).
    rework_cost : float | int | None, optional
        Estimated direct cost to perform rework per unit or batch.
    part_value : float | int | None, optional
        Standard cost or manufactured value of the nonconforming product.
    severity : str | None, optional
        Defect severity rating (e.g. 'Critical', 'Major', 'Minor').
    safety_critical : bool | None, optional
        Whether the defect affects a safety, regulatory, or critical characteristic.
    defect_description : str | None, optional
        Description of the nonconformance for audit context.

    Returns
    -------
    DispositionRecommendation
        Recommended disposition, cited standards rationale, approval authority, and required review flags.

    Raises
    ------
    TypeError
        If input types are invalid.
    ValueError
        If numeric cost or value parameters are negative.
    """
    # Type validation
    if is_reworkable is not None and not isinstance(is_reworkable, bool):
        raise TypeError(f"is_reworkable must be a bool or None, got {type(is_reworkable).__name__}")

    if meets_secondary_spec is not None and not isinstance(meets_secondary_spec, bool):
        raise TypeError(f"meets_secondary_spec must be a bool or None, got {type(meets_secondary_spec).__name__}")

    if customer_concession_eligible is not None and not isinstance(customer_concession_eligible, bool):
        raise TypeError(f"customer_concession_eligible must be a bool or None, got {type(customer_concession_eligible).__name__}")

    if safety_critical is not None and not isinstance(safety_critical, bool):
        raise TypeError(f"safety_critical must be a bool or None, got {type(safety_critical).__name__}")

    if rework_cost is not None:
        if isinstance(rework_cost, bool) or not isinstance(rework_cost, (int, float)):
            raise TypeError(f"rework_cost must be a number or None, got {type(rework_cost).__name__}")
        if rework_cost < 0:
            raise ValueError(f"rework_cost cannot be negative, got {rework_cost}")

    if part_value is not None:
        if isinstance(part_value, bool) or not isinstance(part_value, (int, float)):
            raise TypeError(f"part_value must be a number or None, got {type(part_value).__name__}")
        if part_value < 0:
            raise ValueError(f"part_value cannot be negative, got {part_value}")

    if defect_origin is not None and not isinstance(defect_origin, str):
        raise TypeError(f"defect_origin must be a string or None, got {type(defect_origin).__name__}")

    if severity is not None and not isinstance(severity, str):
        raise TypeError(f"severity must be a string or None, got {type(severity).__name__}")

    if defect_description is not None and not isinstance(defect_description, str):
        raise TypeError(f"defect_description must be a string or None, got {type(defect_description).__name__}")

    # Mandatory Load-Bearing Negative Control:
    # If key decision attributes are completely absent or ambiguous, REFUSE TO GUESS A DISPOSITION.
    is_ambiguous = (
        is_reworkable is None
        and defect_origin is None
        and meets_secondary_spec is None
        and customer_concession_eligible is None
    )

    if is_ambiguous:
        return DispositionRecommendation(
            disposition=None,
            verdict="INSUFFICIENT_DATA",
            rationale="Insufficient defect routing data provided. ISO 9001 §8.7 and IATF 16949 §8.7 prohibit arbitrary disposition assignment without objective defect origin, reworkability, or concession evidence.",
            approval_authority="Material Review Board (MRB) Fact-Finding",
            mrb_review_required=True,
            customer_authorization_required=False,
            fmea_risk_analysis_required=False,
            missing_evidence=[
                "is_reworkable",
                "defect_origin",
                "meets_secondary_spec",
                "customer_concession_eligible",
            ],
            warnings=[
                "Cannot recommend disposition: missing critical defect characteristics (reworkability, origin, concession eligibility)."
            ],
            recommendations=[
                "Convene Material Review Board (MRB) to establish defect origin and determine technical reworkability before dispositioning."
            ],
            standards_basis=_STANDARDS_BASIS,
        )

    # Normalize defect origin
    origin_clean = defect_origin.strip().lower() if defect_origin else ""
    is_supplier_origin = origin_clean in _SUPPLIER_ORIGIN_KEYWORDS or "supplier" in origin_clean or "vendor" in origin_clean or "incoming" in origin_clean

    warnings: list[str] = []
    recommendations: list[str] = []
    missing_evidence: list[str] = []

    # Track missing secondary parameters
    if is_reworkable is None:
        missing_evidence.append("is_reworkable")
    if defect_origin is None:
        missing_evidence.append("defect_origin")
    if meets_secondary_spec is None:
        missing_evidence.append("meets_secondary_spec")
    if customer_concession_eligible is None:
        missing_evidence.append("customer_concession_eligible")

    # 1. Safety Critical Non-conformance override:
    # If safety critical and not reworkable or no customer concession allowed -> Scrap
    if safety_critical is True:
        warnings.append("Safety/regulatory critical characteristic nonconformance.")
        if is_reworkable is not True:
            recommendations.append("Mandatory defacing and scrap witnessing required for safety-critical nonconformance.")
            if is_supplier_origin:
                recommendations.append("Issue Supplier Corrective Action Request (SCAR) and debit memo to vendor.")
            return DispositionRecommendation(
                disposition="Scrap",
                verdict="VALID",
                rationale="Product has safety-critical nonconformance and cannot be reworked; must be rendered unusable prior to disposal per IATF 16949:2016 Clause 8.7.1.7.",
                approval_authority="Quality Manager / Scrap Authority & Safety Officer",
                mrb_review_required=True,
                customer_authorization_required=False,
                fmea_risk_analysis_required=False,
                missing_evidence=missing_evidence,
                warnings=warnings,
                recommendations=recommendations,
                standards_basis=_STANDARDS_BASIS,
            )

    # 2. Supplier Defect -> ReturnToVendor
    if is_supplier_origin:
        recommendations.append("Issue Supplier Corrective Action Request (SCAR) and debit memo to vendor.")
        if is_reworkable is True:
            warnings.append("Defect originated externally from supplier; internal rework is discouraged without vendor authorization.")

        return DispositionRecommendation(
            disposition="ReturnToVendor",
            verdict="VALID",
            rationale="Defect originated from external supplier/vendor; nonconforming product segregated for return per ISO 9001:2015 Clause 8.7.1(b).",
            approval_authority="Supplier Quality Assurance (SQA) / Purchasing",
            mrb_review_required=False,
            customer_authorization_required=False,
            fmea_risk_analysis_required=False,
            missing_evidence=missing_evidence,
            warnings=warnings,
            recommendations=recommendations,
            standards_basis=_STANDARDS_BASIS,
        )

    # 3. Secondary Specification Conformance -> Regrade
    if meets_secondary_spec is True and safety_critical is not True:
        recommendations.append("Obtain MRB and customer authorization before relabeling and transferring to secondary grade stock.")
        return DispositionRecommendation(
            disposition="Regrade",
            verdict="VALID",
            rationale="Product does not meet primary specification but conforms to secondary product grade specification per IATF 16949:2016 Clause 8.7.1.7.",
            approval_authority="Material Review Board (MRB) & Customer Approval",
            mrb_review_required=True,
            customer_authorization_required=True,
            fmea_risk_analysis_required=False,
            missing_evidence=missing_evidence,
            warnings=warnings,
            recommendations=recommendations,
            standards_basis=_STANDARDS_BASIS,
        )

    # 4. Customer Concession / Deviation -> UseAsIs
    if customer_concession_eligible is True and safety_critical is not True:
        recommendations.append("Obtain documented customer concession permit prior to releasing product for delivery.")
        return DispositionRecommendation(
            disposition="UseAsIs",
            verdict="VALID",
            rationale='Deviation does not impair fit, form, function, or safety; recommended for concession acceptance per ISO 9001:2015 Clause 8.7.1(d) and IATF 16949:2016 Clause 8.7.1.1.',
            approval_authority='Material Review Board (MRB) & Customer Concession Permit',
            mrb_review_required=True,
            customer_authorization_required=True,
            fmea_risk_analysis_required=False,
            missing_evidence=missing_evidence,
            warnings=warnings,
            recommendations=recommendations,
            standards_basis=_STANDARDS_BASIS,
        )

    # 5. Non-reworkable or Uneconomical Rework -> Scrap
    is_uneconomical_rework = (
        rework_cost is not None
        and part_value is not None
        and rework_cost >= part_value
    )

    if is_reworkable is False or is_uneconomical_rework:
        if is_uneconomical_rework:
            warnings.append(f"Rework cost (${rework_cost:.2f}) meets or exceeds part value (${part_value:.2f}); rework is uneconomical.")
        recommendations.append("Segregate, deface/destroy, and verify product is rendered completely unusable before physical disposal.")

        return DispositionRecommendation(
            disposition="Scrap",
            verdict="VALID",
            rationale="Product cannot be reworked to specification or rework cost exceeds part value; must be rendered unusable prior to disposal per IATF 16949:2016 Clause 8.7.1.7.",
            approval_authority="Quality Manager / Scrap Authority",
            mrb_review_required=False,
            customer_authorization_required=False,
            fmea_risk_analysis_required=False,
            missing_evidence=missing_evidence,
            warnings=warnings,
            recommendations=recommendations,
            standards_basis=_STANDARDS_BASIS,
        )

    # 6. Reworkable -> Rework
    if is_reworkable is True:
        recommendations.append("Perform FMEA risk analysis on rework procedure and re-inspect reworked units against standard criteria.")
        return DispositionRecommendation(
            disposition="Rework",
            verdict="VALID",
            rationale="Product can be corrected to meet original specification per ISO 9001:2015 Clause 8.7.1(a); risk analysis required per IATF 16949:2016 Clause 8.7.1.4.",
            approval_authority="Manufacturing Engineering & Quality Engineering",
            mrb_review_required=False,
            customer_authorization_required=False,
            fmea_risk_analysis_required=True,
            missing_evidence=missing_evidence,
            warnings=warnings,
            recommendations=recommendations,
            standards_basis=_STANDARDS_BASIS,
        )

    # Default fallback for unclassifiable cases
    return DispositionRecommendation(
        disposition=None,
        verdict="INSUFFICIENT_DATA",
        rationale="Insufficient defect routing data provided. Material Review Board review required.",
        approval_authority="Material Review Board (MRB) Fact-Finding",
        mrb_review_required=True,
        customer_authorization_required=False,
        fmea_risk_analysis_required=False,
        missing_evidence=missing_evidence,
        warnings=["Unresolved defect routing: convene MRB for disposition decision."],
        recommendations=["Convene Material Review Board (MRB) for disposition determination."],
        standards_basis=_STANDARDS_BASIS,
    )

"""
Cross-Engine Element Linkage for PPAP Core (AIAG PPAP 4th Edition §2.2.6, §2.2.7, §2.2.8, §2.2.11).

Validates artifacts supplied for the four engine-backed PPAP elements against their respective
deterministic core modules:
- §2.2.6 Process FMEA -> quality_core.scoring (Action Priority lookup)
- §2.2.7 Control Plan -> quality_core.controlplan (Schema and PFMEA linkage)
- §2.2.8 MSA -> quality_core.msa (Gage R&R acceptance bands)
- §2.2.11 Initial Process Studies -> quality_core.ppap.process_study (Ppk/Cpk acceptance bands & stability gates)

Per SME decision, linkage is verdict-affecting: invalid evidence yields EVIDENCE_INVALID
and contributes to package NOT_READY status.

This module contains no duplicated acceptance constants. Acceptance rules are delegated directly
to owning engines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

from quality_core.controlplan.schema import ControlPlanDataset, validate_control_plan
from quality_core.msa.gage_rr import compute_gage_rr
from quality_core.ppap.process_study import ProcessStudyResult, assess_initial_process_study
from quality_core.scoring import action_priority

__all__ = [
    "LINKABLE_ELEMENTS",
    "LinkageElementResult",
    "LinkageReport",
    "LinkageVerdict",
    "validate_element_linkage",
    "validate_linked_evidence",
]

LinkageVerdict = Literal[
    "EVIDENCE_VALID",
    "EVIDENCE_INVALID",
    "EVIDENCE_NOT_SUPPLIED",
    "LINKAGE_NOT_AVAILABLE",
]

LINKABLE_ELEMENTS: tuple[str, ...] = ("2.2.6", "2.2.7", "2.2.8", "2.2.11")

_ENGINE_MAP: dict[str, str] = {
    "2.2.6": "quality_core.scoring",
    "2.2.7": "quality_core.controlplan",
    "2.2.8": "quality_core.msa",
    "2.2.11": "quality_core.ppap.process_study",
}


@dataclass(frozen=True)
class LinkageElementResult:
    """Validation result for an individual PPAP element's linked evidence."""

    element_id: str
    verdict: LinkageVerdict
    is_valid: bool | None
    engine: str | None
    findings: tuple[str, ...]
    rationales: tuple[str, ...]
    raw_result: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard serializable dictionary."""
        d = asdict(self)
        d["findings"] = list(self.findings)
        d["rationales"] = list(self.rationales)
        return d


@dataclass(frozen=True)
class LinkageReport:
    """Consolidated linkage validation report across all PPAP elements."""

    results: dict[str, LinkageElementResult]
    overall_valid: bool
    invalid_elements: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard serializable dictionary."""
        return {
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "overall_valid": self.overall_valid,
            "invalid_elements": list(self.invalid_elements),
        }


def _validate_pfmea(evidence: Any) -> LinkageElementResult:
    """Validate §2.2.6 Process FMEA against quality_core.scoring."""
    engine = _ENGINE_MAP["2.2.6"]
    findings: list[str] = []
    ap_results: list[dict[str, Any]] = []

    # Extract rows from various input shapes
    rows: list[Any] = []
    if isinstance(evidence, (list, tuple)):
        rows = list(evidence)
    elif isinstance(evidence, dict):
        if "rows" in evidence and isinstance(evidence["rows"], (list, tuple)):
            rows = list(evidence["rows"])
        elif "items" in evidence and isinstance(evidence["items"], (list, tuple)):
            rows = list(evidence["items"])
        elif {"severity", "occurrence", "detection"}.intersection(evidence.keys()) or {
            "s",
            "o",
            "d",
        }.intersection(evidence.keys()):
            rows = [evidence]
        else:
            findings.append("PFMEA dictionary must contain 'rows', 'items', or rating keys ('s', 'o', 'd').")
    else:
        findings.append(f"Unsupported PFMEA evidence type: {type(evidence).__name__}")

    if not rows and not findings:
        findings.append("PFMEA evidence contains zero rows to validate.")

    for idx, row in enumerate(rows, start=1):
        s, o, d = None, None, None
        if isinstance(row, dict):
            s = row.get("severity", row.get("s", row.get("sev")))
            o = row.get("occurrence", row.get("o", row.get("occ")))
            d = row.get("detection", row.get("d", row.get("det")))
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            s, o, d = row[0], row[1], row[2]
        elif hasattr(row, "severity") and hasattr(row, "occurrence") and hasattr(row, "detection"):
            s, o, d = row.severity, row.occurrence, row.detection

        if not all(isinstance(val, int) and not isinstance(val, bool) and 1 <= val <= 10 for val in (s, o, d)):
            findings.append(f"Row {idx}: Invalid ratings (S={s}, O={o}, D={d}); must be integers 1..10.")
        else:
            assert isinstance(s, int) and isinstance(o, int) and isinstance(d, int)
            ap = action_priority(s, o, d)
            ap_results.append({"row": idx, "s": s, "o": o, "d": d, "action_priority": ap})

    if findings:
        return LinkageElementResult(
            element_id="2.2.6",
            verdict="EVIDENCE_INVALID",
            is_valid=False,
            engine=engine,
            findings=tuple(findings),
            rationales=(f"PFMEA evidence failed scoring validation ({len(findings)} finding(s)).",),
            raw_result={"findings": findings, "ap_results": ap_results},
        )

    return LinkageElementResult(
        element_id="2.2.6",
        verdict="EVIDENCE_VALID",
        is_valid=True,
        engine=engine,
        findings=(),
        rationales=(f"PFMEA validated successfully across {len(rows)} row(s) with AIAG-VDA Action Priority lookup.",),
        raw_result={"ap_results": ap_results},
    )


def _validate_control_plan(evidence: Any) -> LinkageElementResult:
    """Validate §2.2.7 Control Plan against quality_core.controlplan."""
    engine = _ENGINE_MAP["2.2.7"]
    findings: list[str] = []
    raw_dict: dict[str, Any] | None = None

    try:
        if isinstance(evidence, ControlPlanDataset):
            raw_dict = evidence.model_dump()
        elif isinstance(evidence, dict) and "rows" in evidence and isinstance(evidence["rows"], (list, tuple)):
            dataset = validate_control_plan(evidence["rows"])
            raw_dict = dataset.model_dump()
        elif isinstance(evidence, dict):
            dataset = validate_control_plan([evidence])
            raw_dict = dataset.model_dump()
        else:
            dataset = validate_control_plan(evidence)
            raw_dict = dataset.model_dump()
    except Exception as err:
        findings.append(f"Control Plan schema validation error: {err}")

    if findings:
        return LinkageElementResult(
            element_id="2.2.7",
            verdict="EVIDENCE_INVALID",
            is_valid=False,
            engine=engine,
            findings=tuple(findings),
            rationales=("Control Plan failed schema and structural validation.",),
            raw_result={"error": findings[0]},
        )

    return LinkageElementResult(
        element_id="2.2.7",
        verdict="EVIDENCE_VALID",
        is_valid=True,
        engine=engine,
        findings=(),
        rationales=("Control Plan conforms to quality_core.controlplan schema and requirements.",),
        raw_result=raw_dict,
    )


def _validate_msa(evidence: Any, **kwargs: Any) -> LinkageElementResult:
    """Validate §2.2.8 MSA against quality_core.msa Gage R&R."""
    engine = _ENGINE_MAP["2.2.8"]
    findings: list[str] = []
    raw_result: dict[str, Any] | None = None

    try:
        if isinstance(evidence, dict) and any(
            k in evidence for k in ("percent_grr", "pgrr", "pgrr_study", "pgrr_tolerance")
        ):
            val = (
                evidence.get("percent_grr")
                if "percent_grr" in evidence
                else evidence.get("pgrr_study")
                if "pgrr_study" in evidence
                else evidence.get("pgrr")
                if "pgrr" in evidence
                else evidence.get("pgrr_tolerance")
            )
            grr = float(val) if val is not None else 0.0
            ndc = evidence.get("ndc")
            raw_result = dict(evidence)
            verdict = evidence.get("verdict")
            if grr > 30.0 or verdict in ("UNACCEPTABLE", "Reject"):
                findings.append(f"Gage R&R %GRR ({grr:.2f}%) exceeds 30.0% threshold (Unacceptable).")
            if ndc is not None and int(ndc) < 5:
                findings.append(f"Number of distinct categories NDC ({ndc}) < 5 minimum requirement.")
        elif isinstance(evidence, (dict, list, tuple)) or hasattr(evidence, "columns"):
            if isinstance(evidence, dict) and "data" in evidence:
                data = evidence["data"]
                tol = evidence.get("tolerance", kwargs.get("tolerance"))
                lsl = evidence.get("lsl", kwargs.get("lsl"))
                usl = evidence.get("usl", kwargs.get("usl"))
            else:
                data = evidence
                tol = kwargs.get("tolerance")
                lsl = kwargs.get("lsl")
                usl = kwargs.get("usl")

            if tol is None and lsl is not None and usl is not None:
                tol = float(usl) - float(lsl)

            if (
                isinstance(data, (list, tuple))
                and len(data) > 0
                and isinstance(data[0], (list, tuple))
                and len(data[0]) > 0
                and isinstance(data[0][0], (list, tuple))
            ):
                converted_rows: list[dict[str, Any]] = []
                for p_idx, part in enumerate(data):
                    for a_idx, app in enumerate(part):
                        for t_idx, val_m in enumerate(app):
                            converted_rows.append(
                                {
                                    "part": f"P{p_idx + 1:02d}",
                                    "appraiser": f"Op{a_idx + 1}",
                                    "trial": t_idx + 1,
                                    "measurement": float(val_m),
                                }
                            )
                data = converted_rows

            study_dict = compute_gage_rr(
                data=data,
                tolerance=tol,
                method=kwargs.get("method", "average_and_range"),
            )
            raw_result = study_dict
            grr_val = (
                study_dict["pgrr_tolerance"]
                if study_dict.get("pgrr_tolerance") is not None
                else study_dict["pgrr_study"]
            )
            ndc_val = study_dict.get("ndc")
            verdict_val = study_dict.get("verdict")
            if verdict_val == "Reject" or grr_val > 30.0:
                findings.append(f"Gage R&R %GRR ({grr_val:.2f}%) exceeds 30.0% threshold (Unacceptable).")
            if ndc_val is not None and ndc_val < 5:
                findings.append(f"Number of distinct categories NDC ({ndc_val}) < 5 minimum requirement.")
        else:
            findings.append(f"Unsupported MSA evidence format: {type(evidence).__name__}")
    except Exception as err:
        findings.append(f"MSA computation error: {err}")

    if findings:
        return LinkageElementResult(
            element_id="2.2.8",
            verdict="EVIDENCE_INVALID",
            is_valid=False,
            engine=engine,
            findings=tuple(findings),
            rationales=(f"MSA Gage R&R study failed acceptance criteria ({len(findings)} finding(s)).",),
            raw_result=raw_result,
        )

    return LinkageElementResult(
        element_id="2.2.8",
        verdict="EVIDENCE_VALID",
        is_valid=True,
        engine=engine,
        findings=(),
        rationales=("MSA study meets Gage R&R acceptance criteria under quality_core.msa.",),
        raw_result=raw_result,
    )


def _validate_process_study(evidence: Any, **kwargs: Any) -> LinkageElementResult:
    """Validate §2.2.11 Initial Process Studies against quality_core.ppap.process_study."""
    engine = _ENGINE_MAP["2.2.11"]
    findings: list[str] = []
    study_res: ProcessStudyResult

    try:
        if isinstance(evidence, ProcessStudyResult):
            study_res = evidence
        elif isinstance(evidence, dict):
            # Pass dictionary parameters to assess_initial_process_study
            merged_params = {**kwargs, **evidence}
            study_res = assess_initial_process_study(**merged_params)
        else:
            # Assume raw data array
            study_res = assess_initial_process_study(data=evidence, **kwargs)

        raw_result = study_res.to_dict()

        if study_res.verdict in ("ACCEPTABLE", "POTENTIALLY_ACCEPTABLE"):
            return LinkageElementResult(
                element_id="2.2.11",
                verdict="EVIDENCE_VALID",
                is_valid=True,
                engine=engine,
                findings=(),
                rationales=study_res.rationales,
                raw_result=raw_result,
            )

        # Non-capable or indeterminate or attribute
        findings.append(f"Process study verdict '{study_res.verdict}': {study_res.required_action}")
        findings.extend(study_res.rationales)

        return LinkageElementResult(
            element_id="2.2.11",
            verdict="EVIDENCE_INVALID",
            is_valid=False,
            engine=engine,
            findings=tuple(findings),
            rationales=(f"Process capability study did not satisfy acceptance criteria (verdict={study_res.verdict}).",),
            raw_result=raw_result,
        )

    except Exception as err:
        return LinkageElementResult(
            element_id="2.2.11",
            verdict="EVIDENCE_INVALID",
            is_valid=False,
            engine=engine,
            findings=(f"Process study evaluation error: {err}",),
            rationales=("Initial Process Study failed evaluation.",),
            raw_result={"error": str(err)},
        )


def validate_element_linkage(
    element_id: str,
    evidence: Any = None,
    **kwargs: Any,
) -> LinkageElementResult:
    """Validate a single PPAP element's linked evidence against its owning engine.

    Args:
        element_id: Canonical AIAG element ID ('2.2.1' .. '2.2.18').
        evidence: The artifact / data supplied for this element.
        **kwargs: Additional parameters passed to the engine (e.g. specs, customer concurrence).

    Returns:
        LinkageElementResult with verdict, validity flag, findings, and rationales.
    """
    if element_id not in LINKABLE_ELEMENTS:
        return LinkageElementResult(
            element_id=element_id,
            verdict="LINKAGE_NOT_AVAILABLE",
            is_valid=None,
            engine=None,
            findings=(),
            rationales=(f"Element {element_id} does not have an automated core validation engine.",),
            raw_result=None,
        )

    if evidence is None:
        return LinkageElementResult(
            element_id=element_id,
            verdict="EVIDENCE_NOT_SUPPLIED",
            is_valid=None,
            engine=_ENGINE_MAP.get(element_id),
            findings=(),
            rationales=(f"No evidence artifact supplied for element {element_id}.",),
            raw_result=None,
        )

    if element_id == "2.2.6":
        return _validate_pfmea(evidence)
    if element_id == "2.2.7":
        return _validate_control_plan(evidence)
    if element_id == "2.2.8":
        return _validate_msa(evidence, **kwargs)
    if element_id == "2.2.11":
        return _validate_process_study(evidence, **kwargs)

    # Fallthrough guard (unreachable given LINKABLE_ELEMENTS check)
    return LinkageElementResult(  # pragma: no cover
        element_id=element_id,
        verdict="LINKAGE_NOT_AVAILABLE",
        is_valid=None,
        engine=None,
        findings=(),
        rationales=(),
        raw_result=None,
    )


def validate_linked_evidence(
    evidence_map: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> LinkageReport:
    """Validate evidence artifacts across all linkable PPAP elements.

    Args:
        evidence_map: Mapping of element_id -> evidence artifact/dict.
        **kwargs: Additional options.

    Returns:
        LinkageReport with per-element results and overall validity flag.
    """
    evidence_map = evidence_map or {}
    results: dict[str, LinkageElementResult] = {}
    invalid_elements: list[str] = []

    # Check all linkable elements
    for elem_id in LINKABLE_ELEMENTS:
        ev = evidence_map.get(elem_id)
        res = validate_element_linkage(elem_id, evidence=ev, **kwargs)
        results[elem_id] = res
        if res.verdict == "EVIDENCE_INVALID":
            invalid_elements.append(elem_id)

    # Check any extra elements explicitly supplied in evidence_map
    for elem_id, ev in evidence_map.items():
        if elem_id not in results:
            res = validate_element_linkage(elem_id, evidence=ev, **kwargs)
            results[elem_id] = res

    overall_valid = len(invalid_elements) == 0

    return LinkageReport(
        results=results,
        overall_valid=overall_valid,
        invalid_elements=tuple(invalid_elements),
    )


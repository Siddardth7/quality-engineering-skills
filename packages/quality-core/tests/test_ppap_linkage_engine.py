"""Unit tests for AIAG PPAP 4th Edition Cross-Engine Element Linkage (Issue #105).

Validates:
1. Dispatch and validation of §2.2.6 Process FMEA via quality_core.scoring
2. Dispatch and validation of §2.2.7 Control Plan via quality_core.controlplan
3. Dispatch and validation of §2.2.8 Measurement System Analysis via quality_core.msa
4. Dispatch and validation of §2.2.11 Initial Process Studies via quality_core.ppap.process_study
5. Handling of non-linkable elements (§2.2.1-§2.2.5, §2.2.9-§2.2.10, §2.2.12-§2.2.18) -> LINKAGE_NOT_AVAILABLE
6. Handling of unsupplied evidence -> EVIDENCE_NOT_SUPPLIED
7. Consolidated report generation via validate_linked_evidence
8. Downward-only import invariant: ppap imports scoring, controlplan, msa, spc; none of them import ppap
9. Zero duplicated threshold constants in linkage.py
10. Negative controls: invalid control plan, invalid PFMEA ratings, unacceptable %GRR, out-of-control capability
"""

from __future__ import annotations

import importlib
import sys

import numpy as np
import pytest
from quality_core.controlplan.schema import ControlPlanDataset, ControlPlanRow
from quality_core.ppap import linkage
from quality_core.ppap.linkage import (
    LINKABLE_ELEMENTS,
    validate_element_linkage,
    validate_linked_evidence,
)

# ==============================================================================
# Downward Import Invariant & Constants Invariant
# ==============================================================================


def test_linked_engines_do_not_import_ppap() -> None:
    """Verify downward-only import invariant: scoring, controlplan, msa, spc must not import ppap."""
    checked_modules = ("quality_core.scoring", "quality_core.controlplan", "quality_core.msa", "quality_core.spc")
    for mod_name in checked_modules:
        importlib.import_module(mod_name)

    for mod_name, mod in sys.modules.items():
        if any(mod_name == prefix or mod_name.startswith(f"{prefix}.") for prefix in checked_modules) and mod is not None:
            mod_file = getattr(mod, "__file__", "")
            if mod_file and mod_file.endswith(".py"):
                with open(mod_file, encoding="utf-8") as f:
                    code = f.read()
                assert "quality_core.ppap" not in code, f"Import violation in {mod_name}: imports quality_core.ppap"


def test_no_duplicated_threshold_constants_in_linkage_py() -> None:
    """Verify linkage.py contains no duplicated acceptance threshold constants."""
    module_dict = vars(linkage)
    # Ensure acceptance constants are not duplicated from owning modules
    forbidden_constants = (
        "ACCEPTANCE_THRESHOLD_CAPABLE",
        "ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE",
        "MINIMUM_INITIAL_STUDY_SAMPLES",
        "MINIMUM_INITIAL_STUDY_SUBGROUPS",
    )
    for const in forbidden_constants:
        assert const not in module_dict, f"Duplicated constant {const} found in linkage.py"


# ==============================================================================
# §2.2.6 Process FMEA Linkage (quality_core.scoring)
# ==============================================================================


def test_pfmea_valid_list_of_dicts() -> None:
    """Verify valid PFMEA row dicts yield EVIDENCE_VALID."""
    evidence = [
        {"severity": 7, "occurrence": 3, "detection": 4},
        {"severity": 5, "occurrence": 2, "detection": 2},
    ]
    res = validate_element_linkage("2.2.6", evidence)
    assert res.verdict == "EVIDENCE_VALID"
    assert res.is_valid is True
    assert res.engine == "quality_core.scoring"
    assert len(res.findings) == 0
    assert res.raw_result is not None
    assert len(res.raw_result["ap_results"]) == 2


def test_pfmea_valid_nested_dict_and_tuples() -> None:
    """Verify valid PFMEA dict with rows/items or tuple format."""
    ev_dict = {"rows": [{"s": 8, "o": 5, "d": 3}]}
    res = validate_element_linkage("2.2.6", ev_dict)
    assert res.verdict == "EVIDENCE_VALID"

    ev_items = {"items": [(6, 4, 3)]}
    res_items = validate_element_linkage("2.2.6", ev_items)
    assert res_items.verdict == "EVIDENCE_VALID"

    ev_single = {"s": 7, "o": 4, "d": 3}
    res_single = validate_element_linkage("2.2.6", ev_single)
    assert res_single.verdict == "EVIDENCE_VALID"


def test_pfmea_invalid_ratings_yields_evidence_invalid() -> None:
    """Verify out-of-range or non-integer ratings yield EVIDENCE_INVALID."""
    invalid_rows = [
        {"severity": 11, "occurrence": 4, "detection": 3},  # S > 10
        {"severity": 5, "occurrence": 0, "detection": 2},   # O < 1
        {"severity": "high", "occurrence": 3, "detection": 2},  # Non-int
        [1, 2],  # Short tuple
        "invalid_shape_row",  # Unsupported row shape
    ]
    res = validate_element_linkage("2.2.6", invalid_rows)
    assert res.verdict == "EVIDENCE_INVALID"
    assert res.is_valid is False
    assert len(res.findings) == 5
    assert "Row 1: Invalid ratings" in res.findings[0]


def test_pfmea_empty_rows_or_invalid_type_yields_evidence_invalid() -> None:
    """Verify empty rows list or unsupported type yields EVIDENCE_INVALID."""
    res_empty = validate_element_linkage("2.2.6", [])
    assert res_empty.verdict == "EVIDENCE_INVALID"
    assert "zero rows" in res_empty.findings[0]

    res_type = validate_element_linkage("2.2.6", 12345)
    assert res_type.verdict == "EVIDENCE_INVALID"
    assert "Unsupported PFMEA evidence type" in res_type.findings[0]

    res_bad_dict = validate_element_linkage("2.2.6", {"unrelated_key": "val"})
    assert res_bad_dict.verdict == "EVIDENCE_INVALID"


class _FMEARowObj:
    def __init__(self, s: int, o: int, d: int) -> None:
        self.severity = s
        self.occurrence = o
        self.detection = d


def test_pfmea_object_rows() -> None:
    """Verify PFMEA row objects with severity/occurrence/detection attributes yield EVIDENCE_VALID."""
    res = validate_element_linkage("2.2.6", [_FMEARowObj(7, 3, 2)])
    assert res.verdict == "EVIDENCE_VALID"
    assert res.is_valid is True


# ==============================================================================
# §2.2.7 Control Plan Linkage (quality_core.controlplan)
# ==============================================================================


def _make_valid_control_plan() -> ControlPlanDataset:
    """Create a minimal valid ControlPlanDataset instance."""
    row = ControlPlanRow(
        characteristic="Thickness",
        measurement_method="Micrometer",
        sample_size=5,
        frequency="1/hr",
        reaction_plan="Adjust press pressure",
        lsl=1.9,
        usl=2.1,
    )
    return ControlPlanDataset(rows=[row])


def test_control_plan_valid_model_and_dict() -> None:
    """Verify valid ControlPlanDataset instance and valid dictionary yield EVIDENCE_VALID."""
    cp = _make_valid_control_plan()
    res_obj = validate_element_linkage("2.2.7", cp)
    assert res_obj.verdict == "EVIDENCE_VALID"
    assert res_obj.is_valid is True
    assert res_obj.engine == "quality_core.controlplan"

    res_dict = validate_element_linkage("2.2.7", cp.model_dump())
    assert res_dict.verdict == "EVIDENCE_VALID"
    assert res_dict.is_valid is True


def test_control_plan_single_dict_and_list() -> None:
    """Verify single dict and list of row dicts yield EVIDENCE_VALID."""
    row_dict = {
        "characteristic": "Diameter",
        "measurement_method": "Caliper",
        "sample_size": 5,
        "frequency": "1/shift",
        "reaction_plan": "Adjust setting",
        "lsl": 10.0,
        "usl": 12.0,
    }
    res_single = validate_element_linkage("2.2.7", row_dict)
    assert res_single.verdict == "EVIDENCE_VALID"

    res_list = validate_element_linkage("2.2.7", [row_dict])
    assert res_list.verdict == "EVIDENCE_VALID"


def test_control_plan_invalid_schema_yields_evidence_invalid() -> None:
    """Verify missing required fields or bad types yield EVIDENCE_INVALID."""
    invalid_dict = {"rows": [{"characteristic": "Blank", "reaction_plan": ""}]}
    res = validate_element_linkage("2.2.7", invalid_dict)
    assert res.verdict == "EVIDENCE_INVALID"
    assert res.is_valid is False
    assert len(res.findings) > 0
    assert "schema validation error" in res.findings[0].lower()

    res_bad_type = validate_element_linkage("2.2.7", [123, 456])
    assert res_bad_type.verdict == "EVIDENCE_INVALID"
    assert "validation error" in res_bad_type.findings[0].lower()


# ==============================================================================
# §2.2.8 Measurement System Analysis Linkage (quality_core.msa)
# ==============================================================================


def test_msa_valid_study_data() -> None:
    """Verify valid Gage R&R raw data array yields EVIDENCE_VALID."""
    # 10 parts x 3 operators x 3 trials with good gage repeatability and part-to-part spread
    rng = np.random.default_rng(42)
    part_means = np.linspace(9.5, 10.5, 10)
    data = []
    for pm in part_means:
        part_data = []
        for _ in range(3):
            app_data = []
            for _ in range(3):
                app_data.append(float(pm + rng.normal(0, 0.005)))
            part_data.append(app_data)
        data.append(part_data)

    res = validate_element_linkage("2.2.8", data, lsl=9.0, usl=11.0)
    assert res.verdict == "EVIDENCE_VALID"
    assert res.is_valid is True
    assert res.engine == "quality_core.msa"


def test_msa_dict_with_data_and_tolerance() -> None:
    """Verify MSA dict with data and tolerance or LSL/USL yields EVIDENCE_VALID."""
    rng = np.random.default_rng(42)
    part_means = np.linspace(9.5, 10.5, 10)
    data = []
    for pm in part_means:
        part_data = []
        for _ in range(3):
            app_data = []
            for _ in range(3):
                app_data.append(float(pm + rng.normal(0, 0.005)))
            part_data.append(app_data)
        data.append(part_data)

    ev_dict = {"data": data, "tolerance": 2.0}
    res = validate_element_linkage("2.2.8", ev_dict)
    assert res.verdict == "EVIDENCE_VALID"

    ev_dict_lsl_usl = {"data": data, "lsl": 9.0, "usl": 11.0}
    res2 = validate_element_linkage("2.2.8", ev_dict_lsl_usl)
    assert res2.verdict == "EVIDENCE_VALID"


def test_msa_raw_data_unacceptable_grr() -> None:
    """Verify raw data with severe noise yields %GRR > 30% and EVIDENCE_INVALID."""
    rng = np.random.default_rng(42)
    data = []
    for _ in range(10):
        part_data = []
        for _ in range(3):
            app_data = []
            for _ in range(3):
                app_data.append(float(10.0 + rng.normal(0, 5.0)))
            part_data.append(app_data)
        data.append(part_data)

    res = validate_element_linkage("2.2.8", data, tolerance=1.0)
    assert res.verdict == "EVIDENCE_INVALID"
    assert res.is_valid is False
    assert any("exceeds 30.0%" in f for f in res.findings)


def test_msa_computation_error() -> None:
    """Verify invalid study data raising computation exception yields EVIDENCE_INVALID."""
    res = validate_element_linkage("2.2.8", [{"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0}])
    assert res.verdict == "EVIDENCE_INVALID"
    assert "MSA computation error" in res.findings[0]


def test_msa_valid_precomputed_dict() -> None:
    """Verify valid precomputed %GRR dict yields EVIDENCE_VALID."""
    ev_good = {"percent_grr": 8.5, "ndc": 12, "verdict": "ACCEPTABLE"}
    res = validate_element_linkage("2.2.8", ev_good)
    assert res.verdict == "EVIDENCE_VALID"
    assert res.is_valid is True


def test_msa_unacceptable_grr_yields_evidence_invalid() -> None:
    """Verify %GRR > 30.0% or NDC < 5 yields EVIDENCE_INVALID."""
    ev_bad = {"percent_grr": 34.5, "ndc": 3, "verdict": "UNACCEPTABLE"}
    res = validate_element_linkage("2.2.8", ev_bad)
    assert res.verdict == "EVIDENCE_INVALID"
    assert res.is_valid is False
    assert any("exceeds 30.0%" in f for f in res.findings)
    assert any("NDC (3) < 5" in f for f in res.findings)


def test_msa_invalid_evidence_type_yields_evidence_invalid() -> None:
    """Verify invalid format string or bad compute parameters yields EVIDENCE_INVALID."""
    res = validate_element_linkage("2.2.8", "not_a_valid_msa_study")
    assert res.verdict == "EVIDENCE_INVALID"
    assert "Unsupported MSA evidence format" in res.findings[0]


# ==============================================================================
# §2.2.11 Initial Process Studies Linkage (quality_core.ppap.process_study)
# ==============================================================================


def test_process_study_valid_ppk_acceptable() -> None:
    """Verify capable process study yields EVIDENCE_VALID."""
    rng = np.random.default_rng(42)
    data = rng.normal(loc=10.0, scale=0.1, size=120).tolist()
    res = validate_element_linkage("2.2.11", data, lsl=9.0, usl=11.0)
    assert res.verdict == "EVIDENCE_VALID"
    assert res.is_valid is True
    assert res.engine == "quality_core.ppap.process_study"


def test_process_study_valid_precomputed_dict_and_result() -> None:
    """Verify precomputed dictionary and ProcessStudyResult object yield EVIDENCE_VALID."""
    ev_dict = {
        "precomputed_index_type": "Ppk",
        "precomputed_index_value": 1.85,
        "precomputed_sample_size": 125,
    }
    res_dict = validate_element_linkage("2.2.11", ev_dict)
    assert res_dict.verdict == "EVIDENCE_VALID"

    # Direct ProcessStudyResult object
    from quality_core.ppap.process_study import assess_initial_process_study
    study = assess_initial_process_study(precomputed_index_type="Ppk", precomputed_index_value=1.75)
    res_obj = validate_element_linkage("2.2.11", study)
    assert res_obj.verdict == "EVIDENCE_VALID"


def test_process_study_incapable_or_unstable_yields_evidence_invalid() -> None:
    """Verify incapable (Ppk < 1.33) or unstable process yields EVIDENCE_INVALID."""
    # Incapable
    ev_poor = {"precomputed_index_type": "Ppk", "precomputed_index_value": 1.10}
    res_poor = validate_element_linkage("2.2.11", ev_poor)
    assert res_poor.verdict == "EVIDENCE_INVALID"
    assert res_poor.is_valid is False
    assert any("UNACCEPTABLE" in f for f in res_poor.findings)

    # Unstable with out-of-control violation
    ev_unstable = {
        "precomputed_index_type": "Ppk",
        "precomputed_index_value": 1.95,
        "violations": [{"rule": 1, "point": 5}],
    }
    res_unstable = validate_element_linkage("2.2.11", ev_unstable)
    assert res_unstable.verdict == "EVIDENCE_INVALID"
    assert res_unstable.is_valid is False
    assert any("INDETERMINATE" in f for f in res_unstable.findings)


def test_process_study_evaluation_exception_yields_evidence_invalid() -> None:
    """Verify invalid parameters raising ValueError yields EVIDENCE_INVALID."""
    res_err = validate_element_linkage("2.2.11", {"invalid_param_name": True})
    assert res_err.verdict == "EVIDENCE_INVALID"
    assert "evaluation error" in res_err.findings[0]


# ==============================================================================
# Non-Linkable Elements and Unsupplied Evidence
# ==============================================================================


@pytest.mark.parametrize(
    "elem_id",
    ["2.2.1", "2.2.2", "2.2.3", "2.2.4", "2.2.5", "2.2.9", "2.2.10", "2.2.12", "2.2.18"],
)
def test_non_linkable_elements_return_linkage_not_available(elem_id: str) -> None:
    """Verify elements without core engine backing return LINKAGE_NOT_AVAILABLE."""
    res = validate_element_linkage(elem_id, {"some_doc": "attached"})
    assert res.verdict == "LINKAGE_NOT_AVAILABLE"
    assert res.is_valid is None
    assert res.engine is None


@pytest.mark.parametrize("elem_id", LINKABLE_ELEMENTS)
def test_unsupplied_evidence_returns_evidence_not_supplied(elem_id: str) -> None:
    """Verify None evidence for linkable elements returns EVIDENCE_NOT_SUPPLIED."""
    res = validate_element_linkage(elem_id, None)
    assert res.verdict == "EVIDENCE_NOT_SUPPLIED"
    assert res.is_valid is None


# ==============================================================================
# Full Linked Evidence Package Validation (validate_linked_evidence)
# ==============================================================================


def test_validate_linked_evidence_all_valid() -> None:
    """Verify package with all 4 linkable artifacts valid yields overall_valid=True."""
    cp = _make_valid_control_plan()
    ev_map = {
        "2.2.6": [{"s": 5, "o": 2, "d": 2}],
        "2.2.7": cp,
        "2.2.8": {"percent_grr": 8.0, "ndc": 10},
        "2.2.11": {"precomputed_index_type": "Ppk", "precomputed_index_value": 1.75},
    }
    report = validate_linked_evidence(ev_map)
    assert report.overall_valid is True
    assert len(report.invalid_elements) == 0
    assert report.results["2.2.6"].verdict == "EVIDENCE_VALID"
    assert report.results["2.2.7"].verdict == "EVIDENCE_VALID"
    assert report.results["2.2.8"].verdict == "EVIDENCE_VALID"
    assert report.results["2.2.11"].verdict == "EVIDENCE_VALID"


def test_validate_linked_evidence_mixed_with_invalid() -> None:
    """Verify presence of any invalid evidence drives overall_valid=False and lists element."""
    ev_map = {
        "2.2.6": [{"s": 15, "o": 2, "d": 2}],  # Invalid S > 10
        "2.2.7": None,  # Not supplied
        "2.2.8": {"percent_grr": 35.0},  # Unacceptable > 30%
        "2.2.1": {"design_record": "file.dwg"},  # Non-linkable
    }
    report = validate_linked_evidence(ev_map)
    assert report.overall_valid is False
    assert "2.2.6" in report.invalid_elements
    assert "2.2.8" in report.invalid_elements
    assert report.results["2.2.7"].verdict == "EVIDENCE_NOT_SUPPLIED"
    assert report.results["2.2.1"].verdict == "LINKAGE_NOT_AVAILABLE"


def test_to_dict_structures() -> None:
    """Verify to_dict produces clean serializable output for element and report."""
    elem_res = validate_element_linkage("2.2.6", [{"s": 5, "o": 2, "d": 2}])
    elem_dict = elem_res.to_dict()
    assert elem_dict["verdict"] == "EVIDENCE_VALID"
    assert isinstance(elem_dict["findings"], list)

    report = validate_linked_evidence({"2.2.6": [{"s": 5, "o": 2, "d": 2}]})
    rep_dict = report.to_dict()
    assert isinstance(rep_dict["results"], dict)
    assert rep_dict["overall_valid"] is True
    assert isinstance(rep_dict["invalid_elements"], list)

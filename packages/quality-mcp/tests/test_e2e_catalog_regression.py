"""
test_e2e_catalog_regression.py
End-to-end regression across the whole 8-domain skill catalog (#150 / E10, v1.0.0).

This suite adds no new engine, tool, canvas, or skill — it exercises what E0–E9 already
shipped, once, together:

1. **AC1** — every registered MCP tool (all 31: 30 domain tools plus ``ping``) is called in
   ONE in-process FastMCP client session, over each domain's own benchmark/default input,
   and asserted to return a well-formed non-error payload. One session, not the sum of
   per-domain sessions, is the point: it proves the catalog coexists on a single server.
2. **AC2** — each domain's ``quality_core`` exporter is invoked directly (no exporter is
   registered as an MCP tool; ``quality_mcp`` has zero export bindings) and its workbook is
   put through the E1 verifier ``assert_cell_is_formula``:
   - the seven live-formula domains must PASS on the exact coords their own
     ``test_*_export.py`` already proved;
   - RCA is a **qualitative, structured-only** domain by design
     (``quality_core/rca/export.py`` says so, and ``rca/ASSUMPTIONS_LOG.md`` RULE 6 records
     it), so the verifier must RAISE on its cells. Asserting a formula there would assert a
     defect. The raise is the enforcement of the "N/A" declaration, not a skip.
3. **AC3** — a malformed dataset sent to a live tool surfaces ``isError`` rather than
   silently passing, and the same session keeps serving valid calls afterwards.

The 8 domains are FMEA, SPC, MSA, Control Plan, RCA, NCR+COPQ (one combined domain, shipped
as a single epic in #147), PPAP, and SQE.

The FastMCP client-session pattern, the ``_parsed_payload`` helper, and the direct
``quality_core`` engine imports all mirror ``test_ppap_client_roundtrip.py`` and
``test_sqe_client_roundtrip.py``; the helper is duplicated rather than shared because the
quality-mcp test package has no ``conftest.py``, as those two modules also note.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import pandas as pd
import pytest
from _xlsx_formula_audit import assert_cell_is_formula
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from openpyxl.utils import get_column_letter
from quality_core.canvas.msa import SAMPLE_MSA_STUDY_DATA
from quality_core.canvas.spc import SAMPLE_SPC_XBAR_R_DATA
from quality_core.controlplan import (
    benchmark_controlplan_dataset,
    export_controlplan_workbook,
)
from quality_core.copq import benchmark_copq_dataset, export_copq_workbook
from quality_core.io.export_fmea import (
    FMEA_EXPORT_COLUMNS,
    benchmark_fmea_dataset,
    export_fmea_workbook,
)
from quality_core.io.export_spc import export_spc_excel
from quality_core.msa.export import export_msa_workbook
from quality_core.msa.gage_rr import METHOD
from quality_core.ncr import benchmark_ncr_dataset, export_ncr_workbook
from quality_core.ppap import benchmark_ppap_package, export_ppap_workbook
from quality_core.rca import (
    FISHBONE_SHEET_TITLE,
    FIVE_WHY_SHEET_TITLE,
    IS_IS_NOT_SHEET_TITLE,
    benchmark_rca_datasets,
    export_rca_workbook,
)
from quality_core.sqe.export import (
    VENDOR_SCORECARD_COLUMNS,
    benchmark_sqe_vendor_rows,
    export_sqe_workbook,
)
from quality_mcp.server import mcp

# ---------------------------------------------------------------------------
# Tool-call inputs
#
# Only four tools have required arguments; every other tool falls back to its own shipped
# benchmark default on ``{}``, which is the path this suite wants to prove (same reason
# test_ppap_client_roundtrip.py / test_sqe_client_roundtrip.py call with ``{}``).
# ---------------------------------------------------------------------------

_MSA_MEASUREMENTS: list[dict[str, Any]] = list(SAMPLE_MSA_STUDY_DATA)

_CONTROL_PLAN_ROWS: list[dict[str, Any]] = [
    {
        "characteristic": row.characteristic,
        "measurement_method": row.measurement_method,
        "sample_size": row.sample_size,
        "frequency": row.frequency,
        "reaction_plan": row.reaction_plan,
        "lsl": row.lsl,
        "usl": row.usl,
        "target": row.target,
        "recommended_chart": row.recommended_chart,
        "source_cause_id": row.source_cause_id,
        "sample_plan_is_placeholder": row.sample_plan_is_placeholder,
    }
    for row in benchmark_controlplan_dataset().rows
]

# (domain, tool_name, arguments, a top-level key the payload must carry)
# The key is the minimal shape assertion AC1 asks for: it fails if a tool starts returning
# an empty or renamed payload, without duplicating the per-domain round-trip suites'
# full parity assertions.
_CATALOG: tuple[tuple[str, str, dict[str, Any], str], ...] = (
    # --- 1. FMEA ---------------------------------------------------------------
    ("FMEA", "lookup_fmea_ap", {"severity": 9, "occurrence": 4, "detection": 3}, "action_priority"),
    ("FMEA", "render_fmea_canvas", {}, "html"),
    # --- 2. SPC ----------------------------------------------------------------
    ("SPC", "calculate_spc_chart", {"chart_type": "Xbar-R", "data": SAMPLE_SPC_XBAR_R_DATA}, "in_control"),
    ("SPC", "render_spc_canvas", {}, "html"),
    # --- 3. MSA ----------------------------------------------------------------
    ("MSA", "calculate_gage_rr", {"measurements": _MSA_MEASUREMENTS}, "ndc"),
    ("MSA", "render_msa_canvas", {}, "html"),
    # --- 4. Control Plan -------------------------------------------------------
    ("ControlPlan", "validate_control_plan", {"plan": _CONTROL_PLAN_ROWS}, "schema_valid"),
    ("ControlPlan", "render_controlplan_canvas", {}, "html"),
    # --- 5. RCA ----------------------------------------------------------------
    ("RCA", "validate_5why", {}, "root_cause"),
    ("RCA", "categorize_fishbone", {}, "grouped_causes"),
    ("RCA", "scope_is_is_not", {}, "dimension_coverage"),
    ("RCA", "render_5why_canvas", {}, "html"),
    ("RCA", "render_fishbone_canvas", {}, "html"),
    ("RCA", "render_isisnot_canvas", {}, "html"),
    # --- 6. NCR + COPQ (one combined domain per E7/#147) -----------------------
    ("NCR+COPQ", "write_ncr", {}, "fields_populated"),
    # ``disposition`` is legitimately null on the benchmark (the engine withholds a
    # disposition until the evidence supports one), so the verdict is the shape assertion.
    ("NCR+COPQ", "recommend_disposition", {}, "verdict"),
    ("NCR+COPQ", "estimate_copq", {}, "cost_breakdown"),
    ("NCR+COPQ", "render_ncr_canvas", {}, "html"),
    ("NCR+COPQ", "render_copq_canvas", {}, "html"),
    # --- 7. PPAP ---------------------------------------------------------------
    ("PPAP", "audit_ppap_package", {}, "package_verdict"),
    ("PPAP", "lookup_ppap_requirement", {}, "elements"),
    ("PPAP", "validate_psw", {}, "fields"),
    ("PPAP", "assess_ppap_capability", {}, "band"),
    ("PPAP", "render_ppap_canvas", {}, "html"),
    # --- 8. SQE ----------------------------------------------------------------
    ("SQE", "calculate_supplier_ppm", {}, "ppm"),
    ("SQE", "calculate_otif", {}, "otif_pct"),
    ("SQE", "calculate_vendor_scorecard", {}, "composite_score"),
    ("SQE", "evaluate_escalation", {}, "evaluated_triggers"),
    ("SQE", "generate_scar", {}, "sections"),
    ("SQE", "render_sqe_canvas", {}, "html"),
    # --- server health ---------------------------------------------------------
    ("server", "ping", {}, "version"),
)


# ---------------------------------------------------------------------------
# Exporter legs
#
# No exporter is an MCP tool, so each is called directly on its domain's own benchmark
# constructor — the same standards-conformant data the tool leg above ran on. The coords
# are the ones each domain's own test_*_export.py already proved live, not new guesses.
# ---------------------------------------------------------------------------


def _col(columns: tuple[str, ...] | list[str], name: str) -> str:
    """Column letter for ``name``, derived exactly as the exporters derive it."""
    return get_column_letter(list(columns).index(name) + 1)


_FMEA_RPN_COL = _col(FMEA_EXPORT_COLUMNS, "RPN")
_SQE_SHEET = "SQE Vendor Scorecard"

# (domain, exporter label, workbook factory, ((sheet, coord), ...))
_LIVE_FORMULA_EXPORTS: tuple[
    tuple[str, str, Callable[[], bytes], tuple[tuple[str, str], ...]], ...
] = (
    (
        "FMEA",
        "export_fmea_workbook",
        lambda: export_fmea_workbook(benchmark_fmea_dataset()),
        (("FMEA", f"{_FMEA_RPN_COL}2"),),
    ),
    (
        "SPC",
        "export_spc_excel",
        lambda: export_spc_excel("Xbar-R", SAMPLE_SPC_XBAR_R_DATA, usl=11.0, lsl=9.0),
        (
            ("Control Chart Data", "G2"),
            ("Process Capability", "B7"),  # Cp
            ("Process Capability", "B8"),  # Cpk
        ),
    ),
    (
        "MSA",
        "export_msa_workbook",
        lambda: export_msa_workbook(
            pd.DataFrame(SAMPLE_MSA_STUDY_DATA), tolerance=4.42, method=METHOD
        ),
        (
            ("Gage R&R Summary", "B10"),  # ndc
            ("Gage R&R Summary", "D13"),  # EV %SV
        ),
    ),
    (
        "ControlPlan",
        "export_controlplan_workbook",
        lambda: export_controlplan_workbook(benchmark_controlplan_dataset()),
        (("Coverage", "B2"), ("Coverage", "B3"), ("Coverage", "B4")),
    ),
    (
        "NCR",
        "export_ncr_workbook",
        lambda: export_ncr_workbook(benchmark_ncr_dataset()),
        (
            ("Dispositions & Containment", "B2"),  # COUNTIF roll-up
            ("Dispositions & Containment", "C2"),  # SUMIF roll-up
            ("Summary & Metadata", "B4"),
            ("Summary & Metadata", "B5"),
        ),
    ),
    (
        "COPQ",
        "export_copq_workbook",
        lambda: export_copq_workbook(benchmark_copq_dataset()),
        (
            ("COPQ Ledger", "F2"),
            ("PAF Category Summary", "C2"),
            ("PAF Category Summary", "D2"),
            ("Executive Summary & Metadata", "B4"),
        ),
    ),
    (
        "PPAP",
        "export_ppap_workbook",
        lambda: export_ppap_workbook(benchmark_ppap_package()),
        (("Completeness", "B6"), ("Completeness", "B7")),
    ),
    (
        "SQE",
        "export_sqe_workbook",
        lambda: export_sqe_workbook(benchmark_sqe_vendor_rows()),
        (
            (_SQE_SHEET, f"{_col(VENDOR_SCORECARD_COLUMNS, 'PPM')}2"),
            (_SQE_SHEET, f"{_col(VENDOR_SCORECARD_COLUMNS, 'OTIF')}2"),
            (_SQE_SHEET, f"{_col(VENDOR_SCORECARD_COLUMNS, 'Composite_Score')}2"),
        ),
    ),
)

# RCA's three sheets. Every one of these cells is a structured literal by design.
_RCA_STRUCTURED_CELLS: tuple[tuple[str, str], ...] = (
    (FIVE_WHY_SHEET_TITLE, "B2"),
    (FISHBONE_SHEET_TITLE, "B2"),
    (IS_IS_NOT_SHEET_TITLE, "B2"),
)


def _parsed_payload(result: Any) -> dict[str, Any]:
    """Assert the single-TextContent wire shape and return the deserialized payload.

    Also asserts dual-payload parity (structuredContent == JSON of content[0].text) whenever
    the client surfaced a structuredContent at all; the guard is deliberate, since
    structuredContent is absent on some MCP client versions.

    Duplicated from ``test_ppap_client_roundtrip.py`` / ``test_sqe_client_roundtrip.py``
    because the quality-mcp test package has no ``conftest.py`` to share fixtures through.
    """
    assert not result.isError
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    if hasattr(result, "structuredContent") and result.structuredContent is not None:
        assert result.structuredContent == parsed
    return parsed


# ==============================================================================
# AC1 — every registered tool in ONE FastMCP client session
# ==============================================================================


def test_full_catalog_walk_in_one_client_session() -> None:
    """All 8 domains' compute and canvas tools succeed inside a single client session.

    The registration list itself is the completeness check: the walk asserts that the set of
    tools it exercised equals the set the server advertises, so a tool added to
    ``server.py`` without a catalog entry fails this test rather than silently going
    unexercised.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            init_result = await client.initialize()
            assert init_result.serverInfo.name == "quality-mcp"

            advertised = {t.name for t in (await client.list_tools()).tools}
            assert {name for _domain, name, _args, _key in _CATALOG} == advertised

            for domain, name, args, expected_key in _CATALOG:
                payload = _parsed_payload(await client.call_tool(name, args))
                assert expected_key in payload, f"{domain}/{name} lost {expected_key!r}"
                assert payload[expected_key] is not None, f"{domain}/{name}: {expected_key} is null"

    asyncio.run(_run())


# ==============================================================================
# AC2 — each domain's exporter through the E1 live-formula verifier
# ==============================================================================


@pytest.mark.parametrize(
    ("domain", "exporter", "factory", "cells"),
    _LIVE_FORMULA_EXPORTS,
    ids=[row[0] for row in _LIVE_FORMULA_EXPORTS],
)
def test_domain_exporter_emits_live_formulas(
    domain: str,
    exporter: str,
    factory: Callable[[], bytes],
    cells: tuple[tuple[str, str], ...],
) -> None:
    """The exporter produces a workbook whose computed cells carry live OOXML ``<f>``."""
    workbook_bytes = factory()
    assert workbook_bytes[:2] == b"PK", f"{domain}/{exporter} did not produce a .xlsx"
    for sheet, coord in cells:
        # Does not raise: the cell carries a live <f> element.
        assert_cell_is_formula(workbook_bytes, sheet, coord)


def test_rca_exporter_is_structured_only_and_the_verifier_proves_it() -> None:
    """RCA is qualitative: its workbook is produced, and every computed slot is a literal.

    ``quality_core/rca/export.py`` declares arithmetic live-formula verification N/A for this
    domain (RULE 6 in ``rca/ASSUMPTIONS_LOG.md``). Asserting a formula here would assert a
    defect, so the E1 verifier is asserted to RAISE — the same proof ``test_rca_export.py``
    uses. That makes the "N/A" carve-out enforced rather than merely claimed.
    """
    workbook_bytes = export_rca_workbook(*benchmark_rca_datasets())
    assert workbook_bytes[:2] == b"PK"

    for sheet, coord in _RCA_STRUCTURED_CELLS:
        with pytest.raises(AssertionError, match="is a literal, not a live formula"):
            assert_cell_is_formula(workbook_bytes, sheet, coord)


# ==============================================================================
# AC3 — negative control: a malformed dataset must surface as an error
# ==============================================================================


def test_malformed_dataset_surfaces_as_error_and_does_not_poison_the_session() -> None:
    """A structurally wrong SPC dataset errors, and the session keeps serving valid calls.

    ``data`` is typed as a sequence of observations; handing it a bare string is the
    malformed-dataset case. A silent pass here — a payload computed from garbage — is exactly
    what this regression exists to catch, so the assertion is on ``isError`` being True, not
    merely on "no exception escaped".

    The follow-up valid call is asserted equal to the pre-error baseline, so the negative
    control also proves the failure did not corrupt the session.
    """
    good_args: dict[str, Any] = {"chart_type": "Xbar-R", "data": SAMPLE_SPC_XBAR_R_DATA}

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            baseline = _parsed_payload(await client.call_tool("calculate_spc_chart", good_args))

            bad = await client.call_tool(
                "calculate_spc_chart", {"chart_type": "Xbar-R", "data": "not-a-list"}
            )
            assert bad.isError is True

            after = _parsed_payload(await client.call_tool("calculate_spc_chart", good_args))
            assert after == baseline

    asyncio.run(_run())

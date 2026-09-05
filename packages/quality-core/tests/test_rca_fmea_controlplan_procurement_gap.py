"""Guard for the RCA D7 FMEA / Control-Plan citation vacuity (#211, E8).

`validate_d7_prevention` reports optional Control Plan and FMEA residual-risk context by *calling*
`quality_core.controlplan.schema.validate_control_plan` and
`quality_core.schema.action.Action.effectiveness` (which reuses `quality_core.scoring`). The
AIAG-VDA FMEA Handbook and the AIAG APQP and Control Plan Reference Manual were never procured
onto this box, so **no FMEA or APQP quotation backs any paraphrase in `rca/`**. The engine
deliberately asserts nothing of its own about FMEA rating methodology, Action Priority, or Control
Plan structure.

This test ensures that gap stays honestly declared (a `PROCUREMENT-GAP` naming the FMEA and
Control-Plan manuals specifically) rather than passing by vacuity, or by an unrelated
`PROCUREMENT-GAP` string elsewhere in the same file — the same failure mode guarded for the
ISO/IATF §8.7 gap in `test_rca_iso_iatf_procurement_gap.py` and the COPQ gap in
`test_rca_copq_procurement_gap.py`. It is a fourth, independent guard file, not a replacement for
either of those.
"""

from __future__ import annotations

from _citation_audit import QUALITY_CORE_SRC

ASSUMPTIONS_LOG = QUALITY_CORE_SRC / "rca" / "ASSUMPTIONS_LOG.md"

#: Deliberately tight. A wide window bleeds into the neighbouring COPQ / ISO declarations and
#: into Process Design Decision #12's own heading, which would let this guard pass on text it is
#: not guarding — the exact vacuity failure the module docstring warns about. The declaration's
#: own parenthetical (which names both manuals) sits well inside this many characters.
_WINDOW = 200


def test_fmea_controlplan_procurement_gap_is_declared_and_names_them() -> None:
    log_text = ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "PROCUREMENT-GAP" in log_text, (
        "rca/ASSUMPTIONS_LOG.md must carry an explicit PROCUREMENT-GAP declaration for the "
        "unprocured AIAG-VDA FMEA and AIAG APQP/Control-Plan manuals behind the D7 FMEA / "
        "Control-Plan integration; otherwise the integration would read as manual-verified when "
        "no FMEA or APQP quotation backs it."
    )

    # The declaration must name BOTH manuals in its own heading, so an unrelated PROCUREMENT-GAP
    # elsewhere in the file (the ISO/IATF §8.7 one, or the COPQ one) cannot satisfy this guard by
    # having the words "FMEA" or "Control-Plan" somewhere downstream of it.
    named = any(
        "AIAG-VDA FMEA" in log_text[start : start + _WINDOW]
        and "APQP" in log_text[start : start + _WINDOW]
        for start in _occurrences(log_text, "PROCUREMENT-GAP")
    )
    assert named, (
        "no PROCUREMENT-GAP declaration in rca/ASSUMPTIONS_LOG.md names the AIAG-VDA FMEA "
        "Handbook and the AIAG APQP/Control-Plan manual; the D7 FMEA / Control-Plan delegation "
        "gap is not declared."
    )


def test_rca_authors_no_new_fmea_or_apqp_citation_rows() -> None:
    """`rca/` must delegate to `quality_core.controlplan` / `.scoring`, never re-cite their sources."""
    manifest = (QUALITY_CORE_SRC / "rca" / "CITATIONS.tsv").read_text(encoding="utf-8")
    for token in ("AIAG-VDA", "APQP", "Action Priority", "Control Plan Reference"):
        assert token not in manifest, (
            f"rca/CITATIONS.tsv must not carry a {token!r} row — the AIAG-VDA FMEA Handbook and "
            "the AIAG APQP/Control-Plan manual are not on this machine, and "
            "quality_core.controlplan / quality_core.scoring own their own citation bases."
        )


def _occurrences(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = text.find(needle)
    while start >= 0:
        positions.append(start)
        start = text.find(needle, start + 1)
    return positions

"""Guard for the RCA D6/COPQ citation vacuity (#210, E7).

`validate_d6_implementation_validation` reports optional cost-of-quality context by *calling*
`quality_core.copq.estimator.estimate_copq`. The PAF / Cost of Poor Quality sources that stand
behind `quality_core.copq` (the ASQ CSSGB Body of Knowledge and the CSSC Lean Six Sigma manual)
were never procured onto this box, so **no COPQ quotation backs any paraphrase in `rca/`**. The
engine deliberately asserts nothing of its own about PAF/COPQ methodology.

This test ensures that gap stays honestly declared (a `PROCUREMENT-GAP` naming COPQ specifically)
rather than passing by vacuity, or by an unrelated `PROCUREMENT-GAP` string elsewhere in the same
file — the same failure mode guarded for the ISO/IATF §8.7 gap in
`test_rca_iso_iatf_procurement_gap.py`.
"""

from __future__ import annotations

from _citation_audit import QUALITY_CORE_SRC

ASSUMPTIONS_LOG = QUALITY_CORE_SRC / "rca" / "ASSUMPTIONS_LOG.md"

_WINDOW = 2000


def test_copq_procurement_gap_is_declared_and_names_copq() -> None:
    log_text = ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "PROCUREMENT-GAP" in log_text, (
        "rca/ASSUMPTIONS_LOG.md must carry an explicit PROCUREMENT-GAP declaration for the "
        "unprocured Cost of Poor Quality sources behind the D6 COPQ integration; otherwise the "
        "integration would read as manual-verified when no COPQ quotation backs it."
    )

    # The declaration must name COPQ near the token, so an unrelated PROCUREMENT-GAP elsewhere in
    # the file (the ISO/IATF §8.7 one) cannot satisfy this guard by itself.
    named = any(
        "COPQ" in log_text[start : start + _WINDOW]
        or "Cost of Poor Quality" in log_text[start : start + _WINDOW]
        for start in _occurrences(log_text, "PROCUREMENT-GAP")
    )
    assert named, (
        "no PROCUREMENT-GAP declaration in rca/ASSUMPTIONS_LOG.md names COPQ / Cost of Poor "
        "Quality; the D6 COPQ delegation gap is not declared."
    )


def test_rca_authors_no_copq_citation_rows() -> None:
    """`rca/` must delegate to `quality_core.copq`, never re-cite its sources."""
    manifest = (QUALITY_CORE_SRC / "rca" / "CITATIONS.tsv").read_text(encoding="utf-8")
    assert "COPQ" not in manifest and "PAF" not in manifest, (
        "rca/CITATIONS.tsv must not carry COPQ/PAF rows — the COPQ manuals are not on this "
        "machine and quality_core.copq owns its own citation base."
    )


def _occurrences(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = text.find(needle)
    while start >= 0:
        positions.append(start)
        start = text.find(needle, start + 1)
    return positions

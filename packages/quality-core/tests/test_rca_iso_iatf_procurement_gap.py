"""Guard for the RCA D3/NCR-linkage ISO/IATF §8.7 citation vacuity (#208, E5).

`validate_d3_containment` links a D3 interim-containment record to a Nonconformance Record by
*calling* `quality_core.ncr.schema.validate_ncr`. The nonconforming-output clauses that stand
behind `quality_core.ncr` are ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7 — and those licensed
excerpts were never procured onto this box, so **no §8.7 quotation backs any paraphrase in
`rca/`**. The engine deliberately asserts nothing of its own about what §8.7 requires.

This test ensures that gap stays honestly declared (a `PROCUREMENT-GAP`) rather than passing by
vacuity — the same failure mode guarded for `sqe/ASSUMPTIONS_LOG.md` (§8.4) in
`test_sqe_iso_iatf_procurement_gap.py`.
"""

from __future__ import annotations

from _citation_audit import QUALITY_CORE_SRC

ASSUMPTIONS_LOG = QUALITY_CORE_SRC / "rca" / "ASSUMPTIONS_LOG.md"


def test_iso_iatf_8_7_procurement_gap_is_declared() -> None:
    log_text = ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "PROCUREMENT-GAP" in log_text, (
        "rca/ASSUMPTIONS_LOG.md must carry an explicit PROCUREMENT-GAP declaration for the "
        "unprocured ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7 excerpts behind the NCR-linkage "
        "check; otherwise the linkage would read as manual-verified when no §8.7 quotation backs "
        "it."
    )
    # The declaration must name the clauses it is disclaiming, not merely the token.
    assert "§8.7" in log_text or "8.7" in log_text, (
        "the PROCUREMENT-GAP declaration must identify the ISO/IATF §8.7 clauses it covers."
    )

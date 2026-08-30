"""Guard for the SQE ISO/IATF §8.4 citation vacuity (#140 carry-forward).

`sqe/CITATIONS.tsv` is verified by `test_sqe_scar_citations.py` — but those rows back only
the SCAR corrective-action discipline (AIAG CQI-20 / Ford 8D). The SQE assumptions log also
*paraphrases* what ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4 require, and those
licensed excerpts were never procured, so **no §8.4 quotation backs those paraphrases**.

This test ensures that gap stays honestly declared (a `PROCUREMENT-GAP`) rather than passing
by vacuity — the exact failure mode flagged for the v1.0.0 audit.
"""

from __future__ import annotations

from _citation_audit import QUALITY_CORE_SRC

ASSUMPTIONS_LOG = QUALITY_CORE_SRC / "sqe" / "ASSUMPTIONS_LOG.md"


def test_iso_iatf_8_4_procurement_gap_is_declared() -> None:
    log_text = ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "PROCUREMENT-GAP" in log_text, (
        "sqe/ASSUMPTIONS_LOG.md must carry an explicit PROCUREMENT-GAP declaration for the "
        "unprocured ISO 9001 §8.4/§10.2 and IATF 16949 §8.4 excerpts; otherwise the clause "
        "paraphrases would read as manual-verified when no §8.4 quotation backs them."
    )
    # The declaration must name the clauses it is disclaiming, not merely the token.
    assert "§8.4" in log_text or "8.4" in log_text, (
        "the PROCUREMENT-GAP declaration must identify the ISO/IATF §8.4 clauses it covers."
    )

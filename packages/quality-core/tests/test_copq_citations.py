"""Citation integrity for Cost of Poor Quality (COPQ) against its on-machine manuals.

`copq/CITATIONS.tsv` shipped with real rows but no dedicated verifying test — its manifest
was unverified (#140). This adds the missing test, mirroring the per-domain pattern.

COPQ's manifest rows are line-matched against `pdftotext -layout` extractions of the ASQ
CSSGB Handbook and the CSSC manual (#245), wired through `COPQ_ASQ_CSSGB_MANUAL_PATH` /
`COPQ_CSSC_MANUAL_PATH`. The Lumafield report stays PDF-only and is cited by no row.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _citation_audit import (
    QUALITY_CORE_SRC,
    assert_blockquotes_backed,
    assert_manifest_rows_present_in_log,
    assert_no_duplicate_rows,
    assert_no_unverified_page_refs,
    assert_quote_in_any_manual,
    load_citations,
    manual_path,
    normalise,
)

_COPQ_DIR = QUALITY_CORE_SRC / "copq"
MANIFEST = _COPQ_DIR / "CITATIONS.tsv"
ASSUMPTIONS_LOG = _COPQ_DIR / "ASSUMPTIONS_LOG.md"

MANUAL_PATHS: dict[str, Path] = {
    "ASQ_CSSGB": manual_path("COPQ_ASQ_CSSGB_MANUAL_PATH"),
    "CSSC": manual_path("COPQ_CSSC_MANUAL_PATH"),
    "Lumafield": manual_path("COPQ_LUMAFIELD_MANUAL_PATH"),
}

MANIFEST_ROWS = load_citations(MANIFEST)


def test_manifest_exists() -> None:
    assert MANIFEST.exists(), f"COPQ CITATIONS.tsv not found at {MANIFEST}"
    assert MANIFEST_ROWS, f"{MANIFEST} is empty — citation checks would be vacuous."


def test_no_duplicate_rows() -> None:
    assert_no_duplicate_rows(MANIFEST_ROWS, MANIFEST)


@pytest.mark.parametrize(
    ("site", "src_line", "quote"),
    MANIFEST_ROWS,
    ids=[f"COPQ:{s}:{ln}:{normalise(q)[:30]}" for s, ln, q in MANIFEST_ROWS],
)
def test_citation_matches_manual(site: str, src_line: int, quote: str) -> None:
    assert_quote_in_any_manual(site, src_line, quote, MANUAL_PATHS)


def test_every_live_quotation_in_log_has_manifest_row() -> None:
    assert_blockquotes_backed(ASSUMPTIONS_LOG, MANIFEST_ROWS)


def test_every_manifest_row_is_present_in_log() -> None:
    """Load-bearing content check without a manual: this binds each manifest row to the log
    so corrupting any single row fails even where no manual is mounted (the issue's
    negative-control AC for copq)."""
    assert_manifest_rows_present_in_log(ASSUMPTIONS_LOG, MANIFEST_ROWS)


def test_no_unverified_page_numbers_in_engine_strings() -> None:
    assert_no_unverified_page_refs([_COPQ_DIR])

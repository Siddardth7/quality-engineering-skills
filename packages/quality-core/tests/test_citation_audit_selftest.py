"""Negative controls proving the citation-audit machinery is load-bearing (#140).

The licensed manuals are on-machine only, so on this box (and in CI) the real per-domain
manual-match tests *skip*. These self-tests use a synthetic in-repo manual fixture and a
synthetic log/manifest to prove — with no licensed manual present — that:

- a correct quote at the correct line PASSES, and corrupting the quote or the line FAILS
  (`assert_quote_in_any_manual`); and
- corrupting a manifest quote that backs a live blockquote FAILS the log↔manifest binding
  (`assert_blockquotes_backed`) — the manual-independent negative control the real domain
  tests inherit.

On Sid's machine, where the licensed manuals exist, the domain tests additionally exercise
the manual-match path against the real corpus.
"""

from __future__ import annotations

from pathlib import Path

import _citation_audit as ca
import pytest

_SYNTHETIC_MANUAL = (
    "Quality manual — synthetic fixture, line 1.\n"
    "Prevention costs are incurred to prevent nonconformances and defects.\n"
    "Appraisal costs measure conformance to requirements.\n"
)
# The quote sits on line 2 of the fixture.
_GOOD_QUOTE = "Prevention costs are incurred to prevent nonconformances and defects."
_GOOD_LINE = 2


def _write_manual(tmp_path: Path) -> dict[str, Path]:
    p = tmp_path / "synthetic_manual.md"
    p.write_text(_SYNTHETIC_MANUAL, encoding="utf-8")
    return {"SYNTHETIC": p}


def test_correct_quote_at_correct_line_passes(tmp_path: Path) -> None:
    manuals = _write_manual(tmp_path)
    ca.assert_quote_in_any_manual("RULE 1", _GOOD_LINE, _GOOD_QUOTE, manuals)  # no raise


def test_corrupted_quote_fails(tmp_path: Path) -> None:
    manuals = _write_manual(tmp_path)
    corrupted = "Prevention costs are incurred to CAUSE nonconformances and defects."
    with pytest.raises(AssertionError):
        ca.assert_quote_in_any_manual("RULE 1", _GOOD_LINE, corrupted, manuals)


def test_correct_quote_at_wrong_line_fails(tmp_path: Path) -> None:
    manuals = _write_manual(tmp_path)
    with pytest.raises(AssertionError):
        ca.assert_quote_in_any_manual("RULE 1", _GOOD_LINE + 50, _GOOD_QUOTE, manuals)


def test_skips_when_no_text_manual_present() -> None:
    absent = {"MISSING": Path("/nonexistent/manual.md")}
    with pytest.raises(pytest.skip.Exception):
        ca.assert_quote_in_any_manual("RULE 1", 1, "anything at all here", absent)


def test_pdf_only_source_is_skipped_not_read(tmp_path: Path) -> None:
    # A .pdf path that "exists" must be excluded from line-matching (would be binary noise).
    pdf = tmp_path / "manual.pdf"
    pdf.write_text("not really a pdf", encoding="utf-8")
    with pytest.raises(pytest.skip.Exception):
        ca.assert_quote_in_any_manual("RULE 1", 1, "anything", {"PDF": pdf})


def test_blockquote_binding_is_load_bearing(tmp_path: Path) -> None:
    """Corrupting the manifest row that backs a blockquote must fail the binding check."""
    log = tmp_path / "ASSUMPTIONS_LOG.md"
    log.write_text(
        "# Log\n\n## RULE 1\n\n> Prevention costs are incurred to prevent nonconformances.\n",
        encoding="utf-8",
    )
    backing = [("RULE 1", 2, "Prevention costs are incurred to prevent nonconformances.")]
    ca.assert_blockquotes_backed(log, backing)  # backed → no raise

    unbacked = [("RULE 1", 2, "A completely unrelated quotation about something else.")]
    with pytest.raises(AssertionError):
        ca.assert_blockquotes_backed(log, unbacked)


def test_per_row_binding_bites_on_contiguous_block(tmp_path: Path) -> None:
    """The negative control that `assert_blockquotes_backed` alone misses.

    Several manifest rows sharing ONE contiguous blockquote block: corrupting a single row
    must still fail `assert_manifest_rows_present_in_log`, even though the block as a whole
    is still 'backed' by the other rows (the exact hole flagged for COPQ).
    """
    log = tmp_path / "ASSUMPTIONS_LOG.md"
    log.write_text(
        "# Log\n\n## RULE 1\n\n"
        "> Prevention costs are incurred to prevent nonconformances.\n"
        "> Appraisal costs measure conformance to requirements.\n"
        "> Internal failure costs arise before delivery.\n",
        encoding="utf-8",
    )
    good = [
        ("RULE 1", 1, "Prevention costs are incurred to prevent nonconformances."),
        ("RULE 1", 2, "Appraisal costs measure conformance to requirements."),
        ("RULE 1", 3, "Internal failure costs arise before delivery."),
    ]
    # Sanity: the block IS 'backed' (each row substrings the joined block), so the weaker
    # check would pass even with a corrupted row — demonstrating why per-row binding matters.
    ca.assert_blockquotes_backed(log, good)
    ca.assert_manifest_rows_present_in_log(log, good)  # all present → no raise

    corrupted_one = [
        ("RULE 1", 1, "Prevention costs are incurred to prevent nonconformances."),
        ("RULE 1", 2, "Appraisal costs measure conformance to requirements."),
        ("RULE 1", 3, "Internal failure costs arise AFTER shipment to the customer."),  # corrupted
    ]
    ca.assert_blockquotes_backed(log, corrupted_one)  # weaker check STILL passes (the hole)
    with pytest.raises(AssertionError):
        ca.assert_manifest_rows_present_in_log(log, corrupted_one)  # per-row check bites


def test_formatting_tolerant_matching() -> None:
    """Markdown emphasis and HTML tags must not cause a false fabrication verdict."""
    marked = "**Prevention costs** are _incurred_ to prevent nonconformances."
    plain = "Prevention costs are incurred to prevent nonconformances."
    assert ca.normalise(marked) == ca.normalise(plain)
    # Angle-bracket markup (e.g. an inline <sup> footnote tag) never survives normalisation.
    normalised = ca.normalise("cost<sup>x</sup>")
    assert "<" not in normalised and "sup" not in normalised

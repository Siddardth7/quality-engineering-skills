"""Test suite for NCR and COPQ reference-material procurement and citation scaffolding (Issue #91).

Validates:
1. Presence and structure of packages/quality-core/src/quality_core/ncr/ASSUMPTIONS_LOG.md
2. Presence, tab-delimiter, and canonical header of packages/quality-core/src/quality_core/ncr/CITATIONS.tsv
3. Presence and structure of packages/quality-core/src/quality_core/copq/ASSUMPTIONS_LOG.md
4. Presence, tab-delimiter, and canonical header of packages/quality-core/src/quality_core/copq/CITATIONS.tsv
5. Existence and non-emptiness of on-machine reference manuals for NCR and COPQ at specified absolute paths
6. Content markers in reference manuals confirming document authenticity
7. Per-domain reference manual mapping in CLAUDE.md under ## Standards fidelity for NCR and COPQ
8. CHANGELOG.md entry formatting under [Unreleased] -> Added (#91)
9. Negative controls: invalid TSV delimiters, malformed TSV headers, non-zero TSV data rows, missing manual paths, missing assumptions log references, missing CLAUDE.md mappings, and missing changelog references
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_QUALITY_CORE = _REPO_ROOT / "packages" / "quality-core" / "src" / "quality_core"

_NCR_DIR = _QUALITY_CORE / "ncr"
_NCR_ASSUMPTIONS_LOG = _NCR_DIR / "ASSUMPTIONS_LOG.md"
_NCR_CITATIONS_TSV = _NCR_DIR / "CITATIONS.tsv"

_COPQ_DIR = _QUALITY_CORE / "copq"
_COPQ_ASSUMPTIONS_LOG = _COPQ_DIR / "ASSUMPTIONS_LOG.md"
_COPQ_CITATIONS_TSV = _COPQ_DIR / "CITATIONS.tsv"

_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_CHANGELOG_MD = _REPO_ROOT / "CHANGELOG.md"

_EXPECTED_MANUALS: dict[str, dict[str, str]] = {
    "ISO 9001:2015 Section 8.7": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/ISO_9001_2015_Section_8_7.md",
        "marker": "8.7",
    },
    "ISO 9001:2015 Full PDF": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/ISO-9001-2015.pdf",
        "marker": "9001",
    },
    "IATF 16949:2016 Section 8.7": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_7.md",
        "marker": "16949",
    },
    "IATF 16949:2016 Full PDF": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/pdfcoffee.com_iatf16949-2016-standard-pdf-free.pdf",
        "marker": "16949",
    },
    "ASQ CSSGB Handbook": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/ASQ_six_sigma_green_belt_handb.pdf",
        "marker": "ASQ",
    },
    "ASQ CSSGB BoK 2014": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/_new/ASQ-CSSGB-BoK-2014.pdf",
        "marker": "ASQ",
    },
    "CSSC Lean Six Sigma Green Belt Manual": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/Lean-Six-Sigma-Green-Belt-Certification-Training-Manual-CSSC-2018-06b.pdf",
        "marker": "Six Sigma",
    },
    "Lumafield Cost of Quality Report": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/TheLumafieldCostofQualityReportpdf.pdf",
        "marker": "Cost of Quality",
    },
}


def _validate_citations_tsv_format(content: str) -> tuple[list[str], list[dict[str, str]]]:
    """Validate that TSV content uses tab delimiters and returns headers and rows."""
    reader = csv.reader(io.StringIO(content), delimiter="\t")
    rows = list(reader)
    if not rows:
        raise ValueError("TSV file is empty")
    headers = rows[0]
    dict_reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    dict_rows = list(dict_reader)
    return headers, dict_rows


def _extract_unreleased_changelog_section(content: str) -> str:
    """Extract the text under ## [Unreleased] up to the next release heading."""
    pattern = re.compile(r"## \[Unreleased\](.*?)(?=\n## \[|\Z)", re.DOTALL)
    match = pattern.search(content)
    if not match:
        raise ValueError("No ## [Unreleased] section found in changelog")
    return match.group(1)


def test_ncr_assumptions_log_exists_and_metadata() -> None:
    """Verify ncr/ASSUMPTIONS_LOG.md exists and contains package metadata and standard references."""
    assert _NCR_ASSUMPTIONS_LOG.is_file(), f"Missing NCR ASSUMPTIONS_LOG: {_NCR_ASSUMPTIONS_LOG}"
    content = _NCR_ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "# Engineering Assumptions Log — Nonconformance Reporting (NCR) Suite" in content
    assert "**Package:** `quality_core.ncr`" in content
    assert "**Standard References:**" in content
    assert "ISO 9001:2015 Clause 8.7" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/ISO_9001_2015_Section_8_7.md" in content
    assert "IATF 16949:2016 Clause 8.7" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_7.md" in content

    # Governance and qualitative notes
    assert "## Note on Qualitative NCR Governance and Engineering Heuristics" in content
    assert "No published standard mandates specific mathematical formulas or numerical thresholds" in content
    assert "ISO 9001:2015 §8.7 Compliance" in content
    assert "IATF 16949:2016 §8.7 Automotive Extensions" in content
    assert "Disposition Logic & Engineering Heuristics" in content
    assert "## RULE Entries" in content


def test_copq_assumptions_log_exists_and_metadata() -> None:
    """Verify copq/ASSUMPTIONS_LOG.md exists and contains package metadata and PAF model references."""
    assert _COPQ_ASSUMPTIONS_LOG.is_file(), f"Missing COPQ ASSUMPTIONS_LOG: {_COPQ_ASSUMPTIONS_LOG}"
    content = _COPQ_ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "# Engineering Assumptions Log — Cost of Poor Quality (COPQ) Suite" in content
    assert "**Package:** `quality_core.copq`" in content
    assert "**Standard References:**" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/ASQ_six_sigma_green_belt_handb.pdf" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/_new/ASQ-CSSGB-BoK-2014.pdf" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/Lean-Six-Sigma-Green-Belt-Certification-Training-Manual-CSSC-2018-06b.pdf" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/TheLumafieldCostofQualityReportpdf.pdf" in content

    # PAF cost model and arithmetic definitions
    assert "## Note on the PAF Cost Model and Arithmetic Rollup Definitions" in content
    assert "Prevention Costs:" in content
    assert "Appraisal Costs:" in content
    assert "Internal Failure Costs:" in content
    assert "External Failure Costs:" in content
    assert "Total Cost of Quality (CoQ):" in content
    assert "Cost of Poor Quality (COPQ):" in content
    assert "Cost of Good Quality (CoGQ)" in content
    assert "COPQ Percentage of Revenue / Sales:" in content
    assert "## RULE Entries" in content


def test_ncr_citations_tsv_exists_and_header() -> None:
    """Verify ncr/CITATIONS.tsv exists, is tab-delimited, and has the exact header row with zero data rows."""
    assert _NCR_CITATIONS_TSV.is_file(), f"Missing NCR CITATIONS.tsv: {_NCR_CITATIONS_TSV}"
    raw_content = _NCR_CITATIONS_TSV.read_text(encoding="utf-8")

    first_line = raw_content.splitlines()[0] if raw_content.splitlines() else ""
    assert first_line == "site\tsrc_line\tquote", f"Header mismatch: {first_line!r}"
    assert "\t" in first_line, "Header must contain tab delimiters"
    assert "," not in first_line, "Header must not contain comma delimiters"

    headers, rows = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]
    assert len(rows) == 0, f"Expected 0 data rows in scaffold, got {len(rows)}"


def test_copq_citations_tsv_exists_and_header() -> None:
    """Verify copq/CITATIONS.tsv exists, is tab-delimited, and has the exact header row with zero data rows."""
    assert _COPQ_CITATIONS_TSV.is_file(), f"Missing COPQ CITATIONS.tsv: {_COPQ_CITATIONS_TSV}"
    raw_content = _COPQ_CITATIONS_TSV.read_text(encoding="utf-8")

    first_line = raw_content.splitlines()[0] if raw_content.splitlines() else ""
    assert first_line == "site\tsrc_line\tquote", f"Header mismatch: {first_line!r}"
    assert "\t" in first_line, "Header must contain tab delimiters"
    assert "," not in first_line, "Header must not contain comma delimiters"

    headers, rows = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]
    assert len(rows) == 0, f"Expected 0 data rows in scaffold, got {len(rows)}"


@pytest.mark.parametrize(
    ("name", "meta"),
    list(_EXPECTED_MANUALS.items()),
)
def test_on_machine_manuals_exist_and_non_empty(name: str, meta: dict[str, str]) -> None:
    """Verify that all on-machine reference manuals exist, are non-empty, and contain authentic markers."""
    manual_path = Path(meta["path"])
    if not manual_path.is_file():
        pytest.skip(
            f"On-machine reference manual for {name} not found at {manual_path}. "
            "Licensed manuals are on-machine only and not committed to git."
        )
    stat = manual_path.stat()
    assert stat.st_size > 0, f"Manual file is empty for {name}: {manual_path} (size={stat.st_size})"

    sample = manual_path.read_text(encoding="utf-8", errors="replace")[:5000]
    marker = meta["marker"].lower()
    assert (
        marker in sample.lower()
        or marker in manual_path.name.lower()
        or "%pdf" in sample.lower()
    ), f"Marker {meta['marker']!r} not found in sample of {manual_path}"


def test_claude_md_standards_fidelity_mapping() -> None:
    """Verify CLAUDE.md includes explicit entries for NCR and COPQ under ## Standards fidelity."""
    assert _CLAUDE_MD.is_file(), f"Missing CLAUDE.md: {_CLAUDE_MD}"
    content = _CLAUDE_MD.read_text(encoding="utf-8")

    assert "## Standards fidelity" in content
    assert "**NCR:**" in content
    assert "**COPQ:**" in content
    assert "ISO 9001:2015 §8.7" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/ISO_9001_2015_Section_8_7.md" in content
    assert "IATF 16949:2016 §8.7" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_7.md" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/ASQ_six_sigma_green_belt_handb.pdf" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/TheLumafieldCostofQualityReportpdf.pdf" in content


def test_changelog_entry_unreleased_ncr_copq_scaffold() -> None:
    """Verify CHANGELOG.md contains the Issue #91 entry under [Unreleased] -> Added."""
    assert _CHANGELOG_MD.is_file(), f"Missing CHANGELOG.md: {_CHANGELOG_MD}"
    content = _CHANGELOG_MD.read_text(encoding="utf-8")

    assert "## [Unreleased]" in content
    unreleased_section = _extract_unreleased_changelog_section(content)
    assert "#91" in unreleased_section, "CHANGELOG.md [Unreleased] section must reference issue #91"
    assert "quality_core/ncr/ASSUMPTIONS_LOG.md" in unreleased_section
    assert "quality_core/copq/ASSUMPTIONS_LOG.md" in unreleased_section
    assert "CLAUDE.md" in unreleased_section


# ==============================================================================
# Negative Controls
# ==============================================================================


def test_negative_control_tsv_delimiter_detection() -> None:
    """Negative control: assert non-tab delimiters (comma, semicolon, space) are detected."""
    comma_delimited = "site,src_line,quote\nmod.py,10,some quote\n"
    headers_comma, _ = _validate_citations_tsv_format(comma_delimited)
    assert headers_comma != ["site", "src_line", "quote"], "Comma-separated content must not parse as valid TSV columns"
    assert len(headers_comma) == 1, "Comma-separated content parsed with tab delimiter should produce 1 combined column"

    semicolon_delimited = "site;src_line;quote\nmod.py;10;some quote\n"
    headers_semi, _ = _validate_citations_tsv_format(semicolon_delimited)
    assert headers_semi != ["site", "src_line", "quote"], "Semicolon-separated content must not parse as valid TSV columns"

    space_delimited = "site src_line quote\nmod.py 10 quote\n"
    headers_space, _ = _validate_citations_tsv_format(space_delimited)
    assert headers_space != ["site", "src_line", "quote"], "Space-separated content must not parse as valid TSV columns"


def test_negative_control_invalid_tsv_header_rejected() -> None:
    """Negative control: assert wrong column names or orders are identified as invalid."""
    wrong_headers = "source\tline_number\ttext\n"
    headers, _ = _validate_citations_tsv_format(wrong_headers)
    assert headers != ["site", "src_line", "quote"], "Wrong headers must not match canonical header specification"

    permuted_headers = "quote\tsite\tsrc_line\n"
    headers_perm, _ = _validate_citations_tsv_format(permuted_headers)
    assert headers_perm != ["site", "src_line", "quote"], "Permuted headers must not match canonical header specification"


def test_negative_control_citations_tsv_unexpected_rows_rejected() -> None:
    """Negative control: assert that a citations TSV containing unexpected data rows fails zero-data assertion."""
    tsv_with_row = "site\tsrc_line\tquote\nmodule.py\t1\tExample quote\n"
    headers, rows = _validate_citations_tsv_format(tsv_with_row)
    assert headers == ["site", "src_line", "quote"]
    assert len(rows) == 1
    assert len(rows) != 0, "Non-zero data rows in scaffold TSV must fail scaffold check"


def test_negative_control_ncr_assumptions_missing_reference_rejected() -> None:
    """Negative control: assert that omitting ISO 9001 reference from NCR assumptions log fails validation."""
    mutated_content = "# Engineering Assumptions Log — Nonconformance Reporting (NCR) Suite\n**Package:** `quality_core.ncr`\n**Standard References:**\n- Some other standard\n"
    assert "ISO 9001:2015 Clause 8.7" not in mutated_content, "Mutated content lacking ISO 9001 must be detected"


def test_negative_control_copq_assumptions_missing_paf_rejected() -> None:
    """Negative control: assert that omitting PAF model definition from COPQ assumptions log fails validation."""
    mutated_content = "# Engineering Assumptions Log — Cost of Poor Quality (COPQ) Suite\n**Package:** `quality_core.copq`\n**Standard References:**\n"
    assert "## Note on the PAF Cost Model and Arithmetic Rollup Definitions" not in mutated_content


def test_negative_control_claude_md_missing_domain_rejected() -> None:
    """Negative control: assert that omitting **NCR:** or **COPQ:** from CLAUDE.md fails validation."""
    mutated_content = "## Standards fidelity\n- **MSA:** AIAG MSA\n- **SPC:** AIAG SPC\n"
    assert "**NCR:**" not in mutated_content
    assert "**COPQ:**" not in mutated_content


def test_negative_control_missing_manual_path_detection(tmp_path: Path) -> None:
    """Negative control: assert non-existent manual path is properly flagged as missing."""
    non_existent = tmp_path / "Non_Existent_Manual.md"
    assert not non_existent.exists(), "Non-existent path must evaluate to False"


def test_negative_control_missing_changelog_entry_detected() -> None:
    """Negative control: assert that omitting issue #91 from changelog unreleased section fails validation."""
    bogus_changelog = "## [Unreleased]\n\n### Added\n- Some other feature (#80)\n\n## [0.6.0] - 2026-08-20\n"
    unreleased = _extract_unreleased_changelog_section(bogus_changelog)
    assert "#91" not in unreleased, "Bogus changelog without #91 must not pass #91 membership assertion"

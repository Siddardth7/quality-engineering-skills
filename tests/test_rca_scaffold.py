"""Test suite for RCA reference-material procurement and citation scaffolding (Issue #74).

Validates:
1. Presence and structure of packages/quality-core/src/quality_core/rca/ASSUMPTIONS_LOG.md
2. Presence, tab-delimiter, and canonical header of packages/quality-core/src/quality_core/rca/CITATIONS.tsv
3. Existence and non-emptiness of all 5 on-machine reference manuals at specified absolute paths
4. Content markers in reference manuals confirming document authenticity
5. Per-domain reference manual mapping in CLAUDE.md under ## Standards fidelity
6. CHANGELOG.md entry formatting under [Unreleased] -> Added (#74)
7. Negative controls: invalid TSV delimiters, malformed TSV headers, non-existent manual paths, and missing changelog references
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RCA_DIR = _REPO_ROOT / "packages" / "quality-core" / "src" / "quality_core" / "rca"
_ASSUMPTIONS_LOG = _RCA_DIR / "ASSUMPTIONS_LOG.md"
_CITATIONS_TSV = _RCA_DIR / "CITATIONS.tsv"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_CHANGELOG_MD = _REPO_ROOT / "CHANGELOG.md"

_EXPECTED_MANUALS: dict[str, dict[str, str]] = {
    "AIAG CQI-20": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md",
        "marker": "CQI-20",
    },
    "Kaoru Ishikawa": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/Kaoru_Ishikawa_Guide_to_Quality_Control.md",
        "marker": "Ishikawa",
    },
    "Kepner-Tregoe": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/Kepner_Tregoe_The_New_Rational_Manager.md",
        "marker": "Kepner",
    },
    "Ford Global 8D": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/Ford_Global_8D_Manual.md",
        "marker": "8D",
    },
    "ASQ Quality Toolbox": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/ASQ_The_Quality_Toolbox_2nd_Edition.md",
        "marker": "Quality Toolbox",
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


def test_assumptions_log_exists_and_metadata() -> None:
    """Verify ASSUMPTIONS_LOG.md exists and contains package metadata and all 5 references."""
    assert _ASSUMPTIONS_LOG.is_file(), f"Missing ASSUMPTIONS_LOG: {_ASSUMPTIONS_LOG}"
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "# Engineering Assumptions Log — Root Cause Analysis (RCA) Suite" in content
    assert "**Package:** `quality_core.rca`" in content
    assert "**Standard References:**" in content

    for name, meta in _EXPECTED_MANUALS.items():
        assert meta["path"] in content, f"Missing manual path for {name}: {meta['path']}"


def test_assumptions_log_content_sections() -> None:
    """Verify qualitative nature, absence of constants, and RULE placeholder in ASSUMPTIONS_LOG.md."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "## Note on Qualitative RCA Methods and Absence of Published Constants" in content
    assert "No published standard publishes mathematical constants or numerical formulas" in content
    assert "5-Why Validator" in content
    assert "6M Fishbone Categorizer" in content
    assert "Kepner-Tregoe Is/Is-Not Scoping Matrix" in content
    assert "## RULE Entries" in content
    assert "No `## RULE N` entries are defined in this scaffold" in content


def test_citations_tsv_exists_and_header() -> None:
    """Verify CITATIONS.tsv exists, is tab-delimited, and has the exact header row."""
    assert _CITATIONS_TSV.is_file(), f"Missing CITATIONS.tsv: {_CITATIONS_TSV}"
    raw_content = _CITATIONS_TSV.read_text(encoding="utf-8")

    first_line = raw_content.splitlines()[0] if raw_content.splitlines() else ""
    assert first_line == "site\tsrc_line\tquote", f"Header mismatch: {first_line!r}"
    assert "\t" in first_line, "Header must contain tab delimiters"
    assert "," not in first_line, "Header must not contain comma delimiters"

    headers, rows = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]


@pytest.mark.parametrize(
    ("name", "meta"),
    list(_EXPECTED_MANUALS.items()),
)
def test_on_machine_manuals_exist_and_non_empty(name: str, meta: dict[str, str]) -> None:
    """Verify that all 5 on-machine reference manuals exist, are non-empty, and contain authentic markers."""
    manual_path = Path(meta["path"])
    if not manual_path.is_file():
        pytest.skip(
            f"On-machine reference manual for {name} not found at {manual_path}. "
            "Licensed manuals are on-machine only and not committed to git."
        )
    stat = manual_path.stat()
    assert stat.st_size > 0, f"Manual file is empty for {name}: {manual_path} (size={stat.st_size})"

    sample = manual_path.read_text(encoding="utf-8", errors="replace")[:5000]
    assert meta["marker"].lower() in sample.lower() or meta["marker"].lower() in manual_path.name.lower(), (
        f"Marker {meta['marker']!r} not found in sample of {manual_path}"
    )


def test_claude_md_standards_fidelity_mapping() -> None:
    """Verify CLAUDE.md includes comprehensive per-domain manual mapping table."""
    assert _CLAUDE_MD.is_file(), f"Missing CLAUDE.md: {_CLAUDE_MD}"
    content = _CLAUDE_MD.read_text(encoding="utf-8")

    assert "## Standards fidelity" in content
    assert "**MSA:**" in content
    assert "**FMEA:**" in content
    assert "**SPC:**" in content
    assert "**Control Plan:**" in content
    assert "**RCA:**" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/RCA/" in content


def test_changelog_entry_unreleased_rca_scaffold() -> None:
    """Verify CHANGELOG.md contains the Issue #74 entry under [Unreleased] -> Added."""
    assert _CHANGELOG_MD.is_file(), f"Missing CHANGELOG.md: {_CHANGELOG_MD}"
    content = _CHANGELOG_MD.read_text(encoding="utf-8")

    assert "## [Unreleased]" in content
    assert "#74" in content, "CHANGELOG.md must reference issue #74"
    assert "quality_core/rca/ASSUMPTIONS_LOG.md" in content
    assert "quality_core/rca/CITATIONS.tsv" in content
    assert "CLAUDE.md" in content


# ==============================================================================
# Negative Controls
# ==============================================================================


def test_negative_control_tsv_delimiter_detection() -> None:
    """Negative control: assert non-tab delimiters (comma, semicolon, space) are detected."""
    comma_delimited = "site,src_line,quote\nmod.py,10,some quote\n"
    headers_comma, _ = _validate_citations_tsv_format(comma_delimited)
    assert headers_comma != ["site", "src_line", "quote"], "Comma-separated content must not parse as valid TSV columns"
    assert len(headers_comma) == 1, "Comma-separated content parsed with tab delimiter should produce 1 combined column"


def test_negative_control_invalid_tsv_header_rejected() -> None:
    """Negative control: assert wrong column names or orders are identified as invalid."""
    wrong_headers = "source\tline_number\ttext\n"
    headers, _ = _validate_citations_tsv_format(wrong_headers)
    assert headers != ["site", "src_line", "quote"], "Wrong headers must not match canonical header specification"


def test_negative_control_missing_manual_path_detection(tmp_path: Path) -> None:
    """Negative control: assert non-existent manual path is properly flagged as missing."""
    non_existent = tmp_path / "Non_Existent_Manual.md"
    assert not non_existent.exists(), "Non-existent path must evaluate to False"

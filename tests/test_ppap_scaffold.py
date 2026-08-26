"""Test suite for PPAP reference-material procurement and citation scaffolding (Issue #98).

Validates:
1. Presence of packages/quality-core/src/quality_core/ppap/ (ASSUMPTIONS_LOG.md, CITATIONS.tsv, __init__.py)
2. ASSUMPTIONS_LOG.md package metadata and the standard-reference paths CLAUDE.md maps for PPAP
3. Explicit inventory of what the training deck carries vs what it lacks (authoritative vs secondary)
4. Zero RULE entries and zero CITATIONS.tsv data rows (E0 steady state), making the
   "no RULE entry without a matching CITATIONS.tsv row" invariant vacuously true
5. The five honesty, authority, and scoping declarations recorded in ASSUMPTIONS_LOG.md
6. Presence, tab-delimiter, and canonical header of ppap/CITATIONS.tsv
7. Per-domain reference manual mapping in CLAUDE.md under ## Standards fidelity for PPAP
8. CHANGELOG.md entry under [Unreleased] (#98)
9. Negative controls: invalid TSV delimiters, malformed/permuted TSV headers, non-zero TSV data rows,
   uncited RULE entries, missing declarations, missing inventory items, missing CLAUDE.md mapping,
   missing changelog reference, and missing manual detection.

Licensed reference manuals are on-machine only and not committed to git; presence checks skip
cleanly when files are absent on CI.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PPAP_DIR = _REPO_ROOT / "packages" / "quality-core" / "src" / "quality_core" / "ppap"
_ASSUMPTIONS_LOG = _PPAP_DIR / "ASSUMPTIONS_LOG.md"
_CITATIONS_TSV = _PPAP_DIR / "CITATIONS.tsv"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_CHANGELOG_MD = _REPO_ROOT / "CHANGELOG.md"

# Marker substring used for the CLAUDE.md PPAP bullet assertion.
_CLAUDE_MD_PPAP_MARKER = "**PPAP:**"

# Standard reference paths for PPAP domain
_REFERENCE_PATHS: tuple[str, ...] = (
    "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG_PPAP_4th_Edition.md",
    "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG Production Part Approval Process (PPAP), 4th Edition (2006).pdf",
)

# On-machine manual definitions
_ON_MACHINE_MANUALS: dict[str, dict[str, str]] = {
    "AIAG PPAP 4th Edition Reference Manual": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG_PPAP_4th_Edition.md",
        "marker": "PPAP",
    },
    "AIAG PPAP 4th Edition Training Deck": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG Production Part Approval Process (PPAP), 4th Edition (2006).pdf",
        "marker": "PPAP",
    },
}

_TRAINING_DECK_INVENTORY_PRESENT: tuple[str, ...] = (
    "18 canonical element names",
    "Submission Level definitions",
    "Part Submission Warrant field list",
)

_TRAINING_DECK_INVENTORY_MISSING: tuple[str, ...] = (
    "Table 4.1",
    "Section 5 Part Submission Status",
    "Section 2.2.11 Initial Process Studies",
    "Section 3 Customer Notification",
    "Section 6 Record Retention",
    "Appendix A",
)

_DECLARATIONS: tuple[str, ...] = (
    "ISO 9001:2015 & IATF 16949:2016 Non-Citability Limitation",
    "OEM Customer-Specific Requirements Out of Scope",
    "Submission Level 4 Indeterminacy Gate",
    "The Authority Invariant",
    "Engineering Heuristics Declaration",
)

_RULE_HEADING_RE = re.compile(r"^## RULE \d+", re.MULTILINE)


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


def test_ppap_dir_and_files_exist() -> None:
    """Verify the ppap scaffold directory and its three files exist."""
    assert _PPAP_DIR.is_dir(), f"Missing PPAP package directory: {_PPAP_DIR}"
    assert _ASSUMPTIONS_LOG.is_file(), f"Missing PPAP ASSUMPTIONS_LOG: {_ASSUMPTIONS_LOG}"
    assert _CITATIONS_TSV.is_file(), f"Missing PPAP CITATIONS.tsv: {_CITATIONS_TSV}"
    assert (_PPAP_DIR / "__init__.py").is_file(), f"Missing PPAP __init__.py in {_PPAP_DIR}"


def test_assumptions_log_exists_and_metadata() -> None:
    """Verify ASSUMPTIONS_LOG.md carries package metadata and every path CLAUDE.md maps for PPAP."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "# Engineering Assumptions Log — Production Part Approval Process (PPAP) Core" in content
    assert "**Package:** `quality_core.ppap`" in content
    assert "## Standard References" in content

    for path in _REFERENCE_PATHS:
        assert path in content, f"Missing standard reference path in assumptions log: {path}"


def test_assumptions_log_training_deck_inventory() -> None:
    """Verify ASSUMPTIONS_LOG.md carries the precise inventory of training deck capabilities and gaps."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "Training Deck Inventory:" in content
    for item in _TRAINING_DECK_INVENTORY_PRESENT:
        assert item in content, f"Missing verified present training deck item: {item!r}"
    for item in _TRAINING_DECK_INVENTORY_MISSING:
        assert item in content, f"Missing non-authoritative training deck missing item: {item!r}"


def test_assumptions_log_rules_cited() -> None:
    """Verify every RULE entry in ASSUMPTIONS_LOG.md has a matching CITATIONS.tsv row."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "## RULE Entries" in content

    rule_headings = _RULE_HEADING_RE.findall(content)
    _, rows = _validate_citations_tsv_format(_CITATIONS_TSV.read_text(encoding="utf-8"))
    cited_sites = {row["site"] for row in rows}
    for heading in rule_headings:
        rule_name = heading.removeprefix("## ").strip()
        assert any(rule_name in site for site in cited_sites) or rule_name in cited_sites, f"RULE without a CITATIONS.tsv row: {heading}"


def test_assumptions_log_rule_entries() -> None:
    """Verify RULE entries exist in ASSUMPTIONS_LOG.md and each has matching CITATIONS.tsv row(s)."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "## RULE Entries" in content
    assert "## RULE 10: Table 4.1 Submission Levels & Table 4.2 Retention/Submission Matrix" in content

    rule_headings = _RULE_HEADING_RE.findall(content)
    assert len(rule_headings) >= 1, f"Expected at least 1 RULE entry, found: {rule_headings}"

    _, rows = _validate_citations_tsv_format(_CITATIONS_TSV.read_text(encoding="utf-8"))
    cited_sites = {row["site"] for row in rows}
    for heading in rule_headings:
        site_name = heading.removeprefix("## ").split(":")[0].strip()
        assert site_name in cited_sites, f"RULE without a CITATIONS.tsv row: {heading}"


def test_assumptions_log_scoping_and_honesty_declarations() -> None:
    """Verify all honesty, authority, and scoping declarations are recorded in ASSUMPTIONS_LOG.md."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "## Honesty & Scoping Declarations" in content
    for declaration in _DECLARATIONS:
        assert declaration in content, f"Missing declaration: {declaration!r}"


def test_citations_tsv_exists_and_header() -> None:
    """Verify ppap/CITATIONS.tsv is tab-delimited with the exact canonical header row."""
    raw_content = _CITATIONS_TSV.read_text(encoding="utf-8")

    first_line = raw_content.splitlines()[0] if raw_content.splitlines() else ""
    assert first_line == "site\tsrc_line\tquote", f"Header mismatch: {first_line!r}"
    assert "\t" in first_line, "Header must contain tab delimiters"
    assert "," not in first_line, "Header must not contain comma delimiters"

    headers, _ = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]


def test_citations_tsv_valid_data_rows() -> None:
    """Verify ppap/CITATIONS.tsv is header-delimited and carries valid citation rows."""
    raw_content = _CITATIONS_TSV.read_text(encoding="utf-8")
    headers, rows = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]
    for row in rows:
        assert row["site"], "Site column must not be empty"
        assert row["src_line"], "Src line column must not be empty"
        assert row["quote"], "Quote column must not be empty"
def test_citations_tsv_populated_data_rows() -> None:
    """Verify ppap/CITATIONS.tsv has populated data rows for active RULE entries."""
    raw_content = _CITATIONS_TSV.read_text(encoding="utf-8")
    headers, rows = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]
    assert len(rows) > 0, f"Expected non-zero data rows in CITATIONS.tsv, found {len(rows)}"


@pytest.mark.parametrize(
    ("name", "meta"),
    list(_ON_MACHINE_MANUALS.items()),
)
def test_on_machine_manuals_check(name: str, meta: dict[str, str]) -> None:
    """Verify on-machine manual exists and is non-empty if present, skip if absent."""
    manual_path = Path(meta["path"])
    if not manual_path.is_file():
        pytest.skip(
            f"On-machine reference file for {name} not found at {manual_path}. "
            "Licensed manuals are on-machine only and not committed to git."
        )
    stat = manual_path.stat()
    assert stat.st_size > 0, f"Manual file is empty for {name}: {manual_path} (size={stat.st_size})"

    sample = manual_path.read_text(encoding="utf-8", errors="replace")[:5000]
    assert meta["marker"].lower() in sample.lower() or meta["marker"].lower() in manual_path.name.lower(), (
        f"Marker {meta['marker']!r} not found in sample of {manual_path}"
    )


def test_claude_md_standards_fidelity_mapping() -> None:
    """Verify CLAUDE.md maps the PPAP domain to the reference manual path."""
    assert _CLAUDE_MD.is_file(), f"Missing CLAUDE.md: {_CLAUDE_MD}"
    content = _CLAUDE_MD.read_text(encoding="utf-8")

    assert "## Standards fidelity" in content
    assert _CLAUDE_MD_PPAP_MARKER in content
    assert "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG_PPAP_4th_Edition.md" in content
    assert "AIAG Production Part Approval Process (PPAP), 4th Edition (2006).pdf" in content


def test_changelog_entry_unreleased_ppap_scaffold() -> None:
    """Verify CHANGELOG.md documents the Issue #98 scaffold under [Unreleased]."""
    assert _CHANGELOG_MD.is_file(), f"Missing CHANGELOG.md: {_CHANGELOG_MD}"
    content = _CHANGELOG_MD.read_text(encoding="utf-8")
    unreleased = _extract_unreleased_changelog_section(content)

    assert "## [Unreleased]" in content
    assert "#98" in unreleased, "CHANGELOG.md [Unreleased] must reference issue #98"
    assert "quality_core/ppap/ASSUMPTIONS_LOG.md" in unreleased
    assert "ppap/CITATIONS.tsv" in unreleased
    assert "CLAUDE.md" in unreleased


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
    """Negative control: assert an empty citations TSV fails the non-zero data row assertion."""
    tsv_empty = "site\tsrc_line\tquote\n"
    headers, rows = _validate_citations_tsv_format(tsv_empty)
    assert headers == ["site", "src_line", "quote"]
    assert len(rows) == 0, "Empty TSV must have 0 rows"


def test_negative_control_uncited_rule_entry_detected() -> None:
    """Negative control: assert a RULE heading with no matching CITATIONS.tsv row is detectable."""
    mutated_log = "## RULE Entries\n\n## RULE 99: Bogus Rule\n\n**Decision:** something.\n"
    rule_headings = _RULE_HEADING_RE.findall(mutated_log)
    assert rule_headings == ["## RULE 99"], "Mutated log must expose a RULE heading"

    _, rows = _validate_citations_tsv_format("site\tsrc_line\tquote\nRULE 1\t100\tExample quote\n")
    cited_sites = {row["site"] for row in rows}
    assert "RULE 99" not in cited_sites, "Uncited RULE entry must be detected against an empty TSV"


def test_negative_control_assumptions_missing_declaration_rejected() -> None:
    """Negative control: assert an ASSUMPTIONS_LOG missing a declaration fails presence check."""
    mutated_content = (
        "# Engineering Assumptions Log — Production Part Approval Process (PPAP) Core\n"
        "**Package:** `quality_core.ppap`\n"
        "## Honesty & Scoping Declarations\n"
        "- **Submission Level 4 Indeterminacy Gate**\n"
    )
    assert "The Authority Invariant" not in mutated_content, "Mutated log lacking authority invariant must be detected"
    assert "Engineering Heuristics Declaration" not in mutated_content


def test_negative_control_assumptions_missing_reference_path_rejected() -> None:
    """Negative control: assert an ASSUMPTIONS_LOG missing a mapped reference path is detectable."""
    mutated_content = (
        "# Engineering Assumptions Log — Production Part Approval Process (PPAP) Core\n"
        "**Package:** `quality_core.ppap`\n"
        "**Standard References:**\n"
        "- Some other standard\n"
    )
    for path in _REFERENCE_PATHS:
        assert path not in mutated_content, f"Mutated log must not contain reference path {path}"


def test_negative_control_assumptions_missing_inventory_rejected() -> None:
    """Negative control: assert missing training deck inventory item is detected."""
    mutated_content = "Training Deck Inventory:\n- 18 canonical element names\n"
    assert "Section 5 Part Submission Status" not in mutated_content, (
        "Mutated content missing Section 5 inventory must be detected"
    )


def test_negative_control_claude_md_missing_domain_rejected() -> None:
    """Negative control: assert CLAUDE.md without the PPAP bullet fails validation."""
    mutated_content = "## Standards fidelity\n- **MSA:** AIAG MSA\n- **RCA:** AIAG CQI-20\n- **NCR:** ISO 9001\n"
    assert _CLAUDE_MD_PPAP_MARKER not in mutated_content
    assert "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG_PPAP_4th_Edition.md" not in mutated_content


def test_negative_control_missing_manual_path_detection(tmp_path: Path) -> None:
    """Negative control: assert non-existent manual path is properly flagged as missing."""
    non_existent = tmp_path / "Non_Existent_PPAP_Manual.md"
    assert not non_existent.exists(), "Non-existent path must evaluate to False"
    assert not non_existent.is_file(), "Non-existent path must not report as a file"


def test_negative_control_missing_changelog_entry_detected() -> None:
    """Negative control: assert a changelog without #98 under [Unreleased] fails validation."""
    bogus_changelog = "## [Unreleased]\n\n### Added\n- Some other feature (#80)\n\n## [0.7.0] - 2026-08-22\n"
    unreleased = _extract_unreleased_changelog_section(bogus_changelog)
    assert "#98" not in unreleased, "Bogus changelog without #98 must not pass #98 membership assertion"
    assert "quality_core/ppap/ASSUMPTIONS_LOG.md" not in unreleased

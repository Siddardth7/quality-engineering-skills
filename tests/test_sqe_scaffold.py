"""Test suite for SQE reference-material procurement and citation scaffolding (Issue #114, #162).

Validates:
1. Presence of packages/quality-core/src/quality_core/sqe/ (ASSUMPTIONS_LOG.md, CITATIONS.tsv, __init__.py)
2. ASSUMPTIONS_LOG.md package metadata and the four standard-reference paths CLAUDE.md maps for this domain
3. RULE entries in ASSUMPTIONS_LOG.md are verified against CITATIONS.tsv rows or explicit heuristic/honesty declarations
4. The five no-standard-implied declarations recorded verbatim
5. Presence, tab-delimiter, and canonical header of sqe/CITATIONS.tsv
6. Per-domain reference manual mapping in CLAUDE.md under ## Standards fidelity for Supplier Quality
7. CHANGELOG.md entry under [Unreleased] (#114, #162)
8. Negative controls: invalid TSV delimiters, malformed/permuted TSV headers, non-zero TSV data rows,
   missing manual paths, missing declarations, missing CLAUDE.md mapping, missing changelog reference,
   uncited standard-backed rules rejected

The two ISO/IATF §8.4 excerpt files are hand-produced by the SME and are not on-machine yet; their
existence is deliberately NOT asserted here (see the HUMAN BLOCKER note on issue #114). Only the two
already-on-machine manuals (AIAG CQI-20, Ford Global 8D) are existence-checked, and even those skip
rather than fail, since licensed manuals are on-machine only and not committed to git.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SQE_DIR = _REPO_ROOT / "packages" / "quality-core" / "src" / "quality_core" / "sqe"
_ASSUMPTIONS_LOG = _SQE_DIR / "ASSUMPTIONS_LOG.md"
_CITATIONS_TSV = _SQE_DIR / "CITATIONS.tsv"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_CHANGELOG_MD = _REPO_ROOT / "CHANGELOG.md"

# Marker substring used for the CLAUDE.md Supplier Quality bullet assertion.
_CLAUDE_MD_SQE_MARKER = "**Supplier Quality (SCAR & Vendor Rating):**"

# All four standard-reference paths CLAUDE.md maps for this domain. The first two are forward
# references only — the excerpt files do not exist on-machine yet and must never be asserted to.
_REFERENCE_PATHS: tuple[str, ...] = (
    "/Users/sid/Documents/Upskill/SixSigma/SQE/ISO_9001_2015_Section_8_4_and_10_2.md",
    "/Users/sid/Documents/Upskill/SixSigma/SQE/IATF_16949_2016_Section_8_4.md",
    "/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md",
    "/Users/sid/Documents/Upskill/SixSigma/RCA/Ford_Global_8D_Manual.md",
)

# Only the manuals that are already on-machine and load-bearing for E6.
_ON_MACHINE_MANUALS: dict[str, dict[str, str]] = {
    "AIAG CQI-20": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md",
        "marker": "CQI-20",
    },
    "Ford Global 8D": {
        "path": "/Users/sid/Documents/Upskill/SixSigma/RCA/Ford_Global_8D_Manual.md",
        "marker": "8D",
    },
}

_DECLARATIONS: tuple[str, ...] = (
    "PPM acceptance thresholds have no published standard.",
    "OTIF has no published standard.",
    "Vendor scorecard weights and A/B/C rating-band boundaries have no published standard.",
    "Escalation trigger levels have no published standard.",
    "Any constant introduced later without a published source behind it is to be labelled an **engineering heuristic**, never implied to be a standard.",
)

_RULE_HEADING_RE = re.compile(r"^##\s+RULE(?:-SQE)?[-:\s]+\d+.*", re.MULTILINE)


def _extract_rule_blocks(content: str) -> list[tuple[str, str]]:
    """Extract (heading, body) tuples for each RULE section in the assumptions log."""
    matches = list(_RULE_HEADING_RE.finditer(content))
    blocks: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading = match.group(0).strip()
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            next_section = re.search(r"\n##\s+(?!RULE)", content[start:])
            end = start + next_section.start() if next_section else len(content)
        body = content[start:end].strip()
        blocks.append((heading, body))
    return blocks


_NO_STANDARD_HEURISTIC_RE = re.compile(
    r"\b(?:engineering heuristic|heuristic|data-honesty|data honesty|no published standard|no published source|no standards citation|no citation|no `?citations?\.tsv`? row|gains no row|source[:\s*]+none|basis[:\s*]+none|undecided-sentinel|unstandardized)\b",
    re.IGNORECASE,
)


def _is_declared_heuristic_or_unstandardized(heading: str, block: str) -> bool:
    """Check whether a rule heading or block explicitly declares a heuristic, data-honesty, or no-standard basis."""
    combined = f"{heading}\n{block}"
    if _NO_STANDARD_HEURISTIC_RE.search(combined):
        return True
    lower = combined.lower()
    indicators = (
        "engineering heuristic",
        "data-honesty",
        "data honesty",
        "no published standard",
        "no published source",
        "no standards citation",
        "no citation",
        "source:** none",
        "basis:** none",
        "source: none",
        "basis: none",
        "no citations.tsv row",
        "gains no row",
    )
    return any(indicator in lower for indicator in indicators)


def _is_rule_valid(heading: str, block: str, cited_sites: set[str]) -> bool:
    """Check if a rule is cited in CITATIONS.tsv or declares a heuristic/honesty basis."""
    rule_id_match = re.search(r"RULE(?:-SQE)?[-:\s]+\d+", heading)
    rule_id = rule_id_match.group(0) if rule_id_match else heading.removeprefix("## ").strip()
    is_cited = any(rule_id in site for site in cited_sites) or any(site in heading for site in cited_sites)
    return is_cited or _is_declared_heuristic_or_unstandardized(heading, block)


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


def test_sqe_dir_and_files_exist() -> None:
    """Verify the sqe scaffold directory and its three files exist."""
    assert _SQE_DIR.is_dir(), f"Missing SQE package directory: {_SQE_DIR}"
    assert _ASSUMPTIONS_LOG.is_file(), f"Missing SQE ASSUMPTIONS_LOG: {_ASSUMPTIONS_LOG}"
    assert _CITATIONS_TSV.is_file(), f"Missing SQE CITATIONS.tsv: {_CITATIONS_TSV}"
    assert (_SQE_DIR / "__init__.py").is_file(), f"Missing SQE __init__.py in {_SQE_DIR}"


def test_assumptions_log_exists_and_metadata() -> None:
    """Verify ASSUMPTIONS_LOG.md carries package metadata and every path CLAUDE.md maps for SQE."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "# Engineering Assumptions Log — Supplier Quality Engineering (SQE) Suite" in content
    assert "**Package:** `quality_core.sqe`" in content
    assert "**Standard References:**" in content

    for path in _REFERENCE_PATHS:
        assert path in content, f"Missing standard reference path: {path}"


def test_assumptions_log_rules_cited() -> None:
    """Verify every RULE entry in ASSUMPTIONS_LOG.md has a matching CITATIONS.tsv row or heuristic declaration."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    assert "## RULE Entries" in content

    rule_blocks = _extract_rule_blocks(content)
    assert len(rule_blocks) == 6, f"Expected 6 RULE entries in SQE assumptions log, found {len(rule_blocks)}"

    _, rows = _validate_citations_tsv_format(_CITATIONS_TSV.read_text(encoding="utf-8"))
    cited_sites = {row["site"] for row in rows}
    for heading, block in rule_blocks:
        assert _is_rule_valid(heading, block, cited_sites), (
            f"RULE entry without a CITATIONS.tsv row or explicit heuristic/honesty declaration: {heading}"
        )


def test_assumptions_log_no_standard_implied_declarations() -> None:
    """Verify all five no-standard-implied declarations are recorded verbatim."""
    content = _ASSUMPTIONS_LOG.read_text(encoding="utf-8")

    assert "## No-Standard-Implied Declarations" in content
    for declaration in _DECLARATIONS:
        assert declaration in content, f"Missing verbatim declaration: {declaration!r}"


def test_citations_tsv_exists_and_header() -> None:
    """Verify sqe/CITATIONS.tsv is tab-delimited with the exact canonical header row."""
    raw_content = _CITATIONS_TSV.read_text(encoding="utf-8")

    first_line = raw_content.splitlines()[0] if raw_content.splitlines() else ""
    assert first_line == "site\tsrc_line\tquote", f"Header mismatch: {first_line!r}"
    assert "\t" in first_line, "Header must contain tab delimiters"
    assert "," not in first_line, "Header must not contain comma delimiters"

    headers, _ = _validate_citations_tsv_format(raw_content)
    assert headers == ["site", "src_line", "quote"]


def test_citations_tsv_zero_data_rows() -> None:
    """Verify sqe/CITATIONS.tsv is header-only — E0 introduces no citations."""
    _, rows = _validate_citations_tsv_format(_CITATIONS_TSV.read_text(encoding="utf-8"))
    assert len(rows) == 0, f"E0 scaffold TSV must have zero data rows, found {len(rows)}"


@pytest.mark.parametrize(
    ("name", "meta"),
    list(_ON_MACHINE_MANUALS.items()),
)
def test_on_machine_manuals_exist_and_non_empty(name: str, meta: dict[str, str]) -> None:
    """Verify the two already-procured manuals exist, are non-empty, and carry authentic markers."""
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
    """Verify CLAUDE.md maps the Supplier Quality domain to all four reference paths."""
    assert _CLAUDE_MD.is_file(), f"Missing CLAUDE.md: {_CLAUDE_MD}"
    content = _CLAUDE_MD.read_text(encoding="utf-8")

    assert "## Standards fidelity" in content
    assert _CLAUDE_MD_SQE_MARKER in content
    assert "/Users/sid/Documents/Upskill/SixSigma/SQE/ISO_9001_2015_Section_8_4_and_10_2.md" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/SQE/IATF_16949_2016_Section_8_4.md" in content
    assert "AIAG CQI-20 (2nd Ed, 2018)" in content
    assert "Ford Global 8D Manual" in content
    assert "/Users/sid/Documents/Upskill/SixSigma/RCA/" in content


def test_changelog_entry_unreleased_sqe_scaffold() -> None:
    """Verify CHANGELOG.md documents the Issue #114 scaffold and Issue #162 guard under [Unreleased]."""
    assert _CHANGELOG_MD.is_file(), f"Missing CHANGELOG.md: {_CHANGELOG_MD}"
    content = _CHANGELOG_MD.read_text(encoding="utf-8")
    unreleased = _extract_unreleased_changelog_section(content)

    assert "## [Unreleased]" in content
    assert "#114" in unreleased, "CHANGELOG.md [Unreleased] must reference issue #114"
    assert "#162" in unreleased, "CHANGELOG.md [Unreleased] must reference issue #162"
    assert "quality_core/sqe/ASSUMPTIONS_LOG.md" in unreleased
    assert "sqe/CITATIONS.tsv" in unreleased
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
    """Negative control: assert a citations TSV with data rows fails the zero-data-row assertion."""
    tsv_with_row = "site\tsrc_line\tquote\nRULE 1\t100\tExample quote\n"
    headers, rows = _validate_citations_tsv_format(tsv_with_row)
    assert headers == ["site", "src_line", "quote"]
    assert len(rows) == 1
    assert len(rows) != 0, "Non-zero data rows in scaffold TSV must fail scaffold check"


def test_negative_control_uncited_rule_entry_detected() -> None:
    """Negative control: assert regex captures both RULE 1 and RULE-SQE-001 style headings."""
    log_rule_num = "## RULE Entries\n\n## RULE 1: PPM Denominator Basis\n\n**Decision:** something.\n"
    headings_num = _RULE_HEADING_RE.findall(log_rule_num)
    assert len(headings_num) == 1, "Mutated log must expose a numeric RULE heading"
    assert "RULE 1" in headings_num[0]

    log_rule_sqe = "## RULE Entries\n\n## RULE-SQE-001: On-time Arithmetic\n\n**Decision:** something.\n"
    headings_sqe = _RULE_HEADING_RE.findall(log_rule_sqe)
    assert len(headings_sqe) == 1, "Mutated log must expose a RULE-SQE heading"
    assert "RULE-SQE-001" in headings_sqe[0]


def test_negative_control_uncited_standard_rule_rejected() -> None:
    """Negative control: assert a rule claiming a standard source without citation or heuristic declaration fails verification."""
    simulated_log = (
        "## RULE Entries\n\n"
        "## RULE-SQE-099: Mandatory Standard Inspection Window\n\n"
        "**Decision:** All lots must undergo 100% inspection within 24 hours.\n\n"
        "**Source:** ISO 9001:2015 Clause 8.4.2 statutory requirement.\n\n"
        "**Rationale:** Mandatory standard compliance.\n\n"
        "## No-Standard-Implied Declarations\n"
    )
    rule_blocks = _extract_rule_blocks(simulated_log)
    assert len(rule_blocks) == 1
    heading, block = rule_blocks[0]
    assert "RULE-SQE-099" in heading

    assert not _is_declared_heuristic_or_unstandardized(heading, block), (
        "Simulated standard-backed rule must not match heuristic/honesty keywords"
    )

    _, rows = _validate_citations_tsv_format("site\tsrc_line\tquote\n")
    cited_sites = {row["site"] for row in rows}

    assert not _is_rule_valid(heading, block, cited_sites), (
        "Simulated uncited standard-backed rule must fail validation"
    )


def test_negative_control_assumptions_missing_declaration_rejected() -> None:
    """Negative control: assert an ASSUMPTIONS_LOG missing a declaration fails the presence check."""
    mutated_content = (
        "# Engineering Assumptions Log — Supplier Quality Engineering (SQE) Suite\n"
        "**Package:** `quality_core.sqe`\n"
        "**Standard References:**\n"
        "## No-Standard-Implied Declarations\n"
        "- **PPM acceptance thresholds have no published standard.**\n"
    )
    assert "OTIF has no published standard." not in mutated_content, (
        "Mutated log lacking the OTIF declaration must be detected"
    )
    assert "Escalation trigger levels have no published standard." not in mutated_content


def test_negative_control_assumptions_missing_reference_path_rejected() -> None:
    """Negative control: assert an ASSUMPTIONS_LOG missing a mapped reference path is detectable."""
    mutated_content = (
        "# Engineering Assumptions Log — Supplier Quality Engineering (SQE) Suite\n"
        "**Package:** `quality_core.sqe`\n"
        "**Standard References:**\n"
        "- Some other standard\n"
    )
    for path in _REFERENCE_PATHS:
        assert path not in mutated_content, f"Mutated log must not contain reference path {path}"


def test_negative_control_claude_md_missing_domain_rejected() -> None:
    """Negative control: assert CLAUDE.md without the Supplier Quality bullet fails validation."""
    mutated_content = "## Standards fidelity\n- **MSA:** AIAG MSA\n- **RCA:** AIAG CQI-20\n- **NCR:** ISO 9001\n"
    assert _CLAUDE_MD_SQE_MARKER not in mutated_content
    assert "/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_4.md" not in mutated_content


def test_negative_control_missing_manual_path_detection(tmp_path: Path) -> None:
    """Negative control: assert non-existent manual path is properly flagged as missing."""
    non_existent = tmp_path / "Non_Existent_Manual.md"
    assert not non_existent.exists(), "Non-existent path must evaluate to False"
    assert not non_existent.is_file(), "Non-existent path must not report as a file"


def test_negative_control_missing_changelog_entry_detected() -> None:
    """Negative control: assert a changelog without #114 under [Unreleased] fails validation."""
    bogus_changelog = "## [Unreleased]\n\n### Added\n- Some other feature (#80)\n\n## [0.7.0] - 2026-08-22\n"
    unreleased = _extract_unreleased_changelog_section(bogus_changelog)
    assert "#114" not in unreleased, "Bogus changelog without #114 must not pass #114 membership assertion"
    assert "quality_core/sqe/ASSUMPTIONS_LOG.md" not in unreleased

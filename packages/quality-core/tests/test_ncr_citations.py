"""
Citation integrity for Nonconformance Reporting (NCR) and Cost of Poor Quality (COPQ) documentation against on-machine manuals.

Validates that:
- CITATIONS.tsv and ASSUMPTIONS_LOG.md exist and are non-empty for both quality_core.ncr and quality_core.copq.
- No duplicate (site, quote) rows exist in either CITATIONS.tsv manifest.
- Every citation in quality_core/ncr/CITATIONS.tsv matches the primary reference text at the specified line number
  (within LINE_TOLERANCE) in ISO 9001:2015 Section 8.7 or IATF 16949:2016 Section 8.7.
- Every live blockquote in ncr/ASSUMPTIONS_LOG.md and copq/ASSUMPTIONS_LOG.md has a corresponding manifest entry.
- No unverified inline page references exist in NCR or COPQ source files.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

import pytest

_QUALITY_CORE_SRC = Path(__file__).resolve().parents[1] / "src" / "quality_core"

_NCR_DIR = _QUALITY_CORE_SRC / "ncr"
NCR_MANIFEST = _NCR_DIR / "CITATIONS.tsv"
NCR_ASSUMPTIONS_LOG = _NCR_DIR / "ASSUMPTIONS_LOG.md"

_COPQ_DIR = _QUALITY_CORE_SRC / "copq"
COPQ_MANIFEST = _COPQ_DIR / "CITATIONS.tsv"
COPQ_ASSUMPTIONS_LOG = _COPQ_DIR / "ASSUMPTIONS_LOG.md"

LINE_TOLERANCE = 2

_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

MANUAL_PATHS: dict[str, Path] = {
    "ISO_9001": Path(
        os.environ.get(
            "ISO_9001_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/ISO_9001_2015_Section_8_7.md",
        )
    ),
    "IATF_16949": Path(
        os.environ.get(
            "IATF_16949_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/IATF_16949_2016_Section_8_7.md",
        )
    ),
}


def _resolve_manual_key(site: str, src_line: int, quote: str) -> str:
    """Map an NCR citation entry to the expected manual key."""
    norm = _normalise(quote)
    if "nonconforming outputs" in norm or "documented information that" in norm:
        return "ISO_9001"
    if (
        "customer authorization" in norm
        or "suspect status" in norm
        or "risk analysis" in norm
        or "rendered unusable" in norm
    ):
        return "IATF_16949"
    raise ValueError(f"Unmapped citation: {site} at line {src_line}: {quote[:40]}...")


def _normalise(text: str) -> str:
    """Reduce text to lowercase alphanumeric words separated by single spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "").replace("​", "")
    text = _HTML_TAG.sub(" ", text)
    return _NON_ALNUM.sub(" ", text.lower()).strip()


def _load_citations(manifest_path: Path) -> list[tuple[str, int, str]]:
    if not manifest_path.exists():
        return []
    rows: list[tuple[str, int, str]] = []
    with manifest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not row.get("site") or row["site"].startswith("#") or not row.get("src_line"):
                continue
            rows.append((row["site"], int(row["src_line"]), row["quote"]))
    return rows


NCR_MANIFEST_ROWS = _load_citations(NCR_MANIFEST)
COPQ_MANIFEST_ROWS = _load_citations(COPQ_MANIFEST)


def _blockquote_blocks(markdown: str) -> list[tuple[int, str]]:
    """Return (first_line_number, text) for each contiguous `> ` blockquote block."""
    blocks: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    fenced = False
    for number, raw in enumerate(markdown.splitlines(), start=1):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if raw.startswith(">"):
            if not current:
                start = number
            current.append(raw.lstrip("> ").rstrip())
        elif current:
            blocks.append((start, " ".join(current)))
            current = []
    if current:
        blocks.append((start, " ".join(current)))
    return blocks


def _flatten_manual(manual_path: Path) -> tuple[str, list[int]]:
    """Normalise the manual into one searchable string plus a char-index -> line-number map."""
    raw_lines = manual_path.read_text(encoding="utf-8", errors="replace").split("\n")
    chunks: list[str] = []
    owners: list[int] = []
    for line_number, raw in enumerate(raw_lines, start=1):
        normalised = _normalise(raw)
        if not normalised:
            continue
        chunks.append(normalised)
        owners.extend([line_number] * (len(normalised) + 1))
    return " ".join(chunks), owners


_MANUAL_CACHE: dict[str, tuple[str, list[int]]] = {}


def _get_flattened_manual(manual_key: str) -> tuple[str, list[int]]:
    if manual_key not in _MANUAL_CACHE:
        path = MANUAL_PATHS[manual_key]
        if not path.exists():
            pytest.skip(
                f"Manual for {manual_key} not found at {path}. "
                "Licensed manuals are on-machine only and not committed to git."
            )
        _MANUAL_CACHE[manual_key] = _flatten_manual(path)
    return _MANUAL_CACHE[manual_key]


def _located_lines(flat: str, owners: list[int], quote: str) -> list[int]:
    """Every source line at which `quote` occurs in the flattened manual."""
    needle = _normalise(quote)
    assert needle, "manifest quote normalises to nothing"
    lines: list[int] = []
    start = flat.find(needle)
    while start >= 0:
        lines.append(owners[start])
        start = flat.find(needle, start + 1)
    return lines


# ==============================================================================
# Manifest Existence & Non-Duplication Tests
# ==============================================================================


def test_ncr_citations_manifest_exists() -> None:
    assert NCR_MANIFEST.exists(), f"NCR CITATIONS.tsv not found at {NCR_MANIFEST}"
    assert NCR_MANIFEST_ROWS, f"{NCR_MANIFEST} is empty — citation checks would be vacuous."


def test_copq_citations_manifest_exists() -> None:
    assert COPQ_MANIFEST.exists(), f"COPQ CITATIONS.tsv not found at {COPQ_MANIFEST}"
    assert COPQ_MANIFEST_ROWS, f"{COPQ_MANIFEST} is empty — citation checks would be vacuous."


def test_ncr_manifest_has_no_duplicate_rows() -> None:
    pairs = [(site, _normalise(quote)) for site, _, quote in NCR_MANIFEST_ROWS]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    assert not duplicates, f"duplicate (site, quote) rows in {NCR_MANIFEST}: {sorted(duplicates)}"


def test_copq_manifest_has_no_duplicate_rows() -> None:
    pairs = [(site, _normalise(quote)) for site, _, quote in COPQ_MANIFEST_ROWS]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    assert not duplicates, f"duplicate (site, quote) rows in {COPQ_MANIFEST}: {sorted(duplicates)}"


# ==============================================================================
# Verbatim Citation Line Verification Tests (NCR against on-machine markdown)
# ==============================================================================


@pytest.mark.parametrize(
    ("site", "src_line", "quote"),
    NCR_MANIFEST_ROWS,
    ids=[f"NCR:{site}:{src_line}:{_normalise(quote)[:30]}" for site, src_line, quote in NCR_MANIFEST_ROWS],
)
def test_ncr_citation_matches_manual_at_line(site: str, src_line: int, quote: str) -> None:
    manual_key = _resolve_manual_key(site, src_line, quote)
    flat, owners = _get_flattened_manual(manual_key)

    norm_quote = _normalise(quote)
    assert norm_quote, f"Empty normalized quote for {site} line {src_line}"

    found_at = _located_lines(flat, owners, quote)

    if found_at:
        assert any(abs(line - src_line) <= LINE_TOLERANCE for line in found_at), (
            f"{site}: quotation found at line(s) {found_at} in {manual_key} manual, "
            f"but manifest records {src_line} (tolerance ±{LINE_TOLERANCE}).\n"
            f"Quote: {quote!r}"
        )
    else:
        path = MANUAL_PATHS[manual_key]
        raw_lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        start_idx = max(0, src_line - 1 - LINE_TOLERANCE)
        end_idx = min(len(raw_lines), src_line + LINE_TOLERANCE + 1)
        window_text = _normalise(" ".join(raw_lines[start_idx:end_idx]))
        window_words = set(window_text.split())
        quote_words = norm_quote.split()

        assert all(w in window_words for w in quote_words), (
            f"{site}: words from quotation NOT FOUND in {manual_key} manual within ±{LINE_TOLERANCE} lines of {src_line}.\n"
            f"Quote: {quote!r}\n"
            f"Normalised: {norm_quote!r}\n"
            f"Window text: {window_text!r}"
        )


# ==============================================================================
# Assumptions Log Blockquote Manifest Synchronization Tests
# ==============================================================================


def test_every_live_quotation_in_ncr_log_has_manifest_row() -> None:
    assert NCR_ASSUMPTIONS_LOG.exists(), f"NCR ASSUMPTIONS_LOG.md not found at {NCR_ASSUMPTIONS_LOG}"
    manifest_quotes = [_normalise(quote) for _, _, quote in NCR_MANIFEST_ROWS]

    def is_backed(block: str) -> bool:
        norm_block = _normalise(block)
        return any(mq and (mq in norm_block or norm_block in mq) for mq in manifest_quotes)

    unbacked = [
        (line, text)
        for line, text in _blockquote_blocks(NCR_ASSUMPTIONS_LOG.read_text(encoding="utf-8"))
        if _normalise(text) and not is_backed(text)
    ]
    assert not unbacked, (
        "quotation(s) in NCR ASSUMPTIONS_LOG.md with no row in CITATIONS.tsv:\n"
        + "\n".join(f"  ASSUMPTIONS_LOG.md:{line}: {text[:100]!r}" for line, text in unbacked)
    )


def test_every_live_quotation_in_copq_log_has_manifest_row() -> None:
    assert COPQ_ASSUMPTIONS_LOG.exists(), f"COPQ ASSUMPTIONS_LOG.md not found at {COPQ_ASSUMPTIONS_LOG}"
    manifest_quotes = [_normalise(quote) for _, _, quote in COPQ_MANIFEST_ROWS]

    def is_backed(block: str) -> bool:
        norm_block = _normalise(block)
        return any(mq and (mq in norm_block or norm_block in mq) for mq in manifest_quotes)

    unbacked = [
        (line, text)
        for line, text in _blockquote_blocks(COPQ_ASSUMPTIONS_LOG.read_text(encoding="utf-8"))
        if _normalise(text) and not is_backed(text)
    ]
    assert not unbacked, (
        "quotation(s) in COPQ ASSUMPTIONS_LOG.md with no row in CITATIONS.tsv:\n"
        + "\n".join(f"  ASSUMPTIONS_LOG.md:{line}: {text[:100]!r}" for line, text in unbacked)
    )


# ==============================================================================
# Unverified Page References Guard
# ==============================================================================


def test_no_unverified_page_numbers_in_ncr_copq_engine_strings() -> None:
    py_files = list(_NCR_DIR.glob("*.py")) + list(_COPQ_DIR.glob("*.py"))
    assert py_files, f"No Python files found in {_NCR_DIR} or {_COPQ_DIR}"

    page_pattern = re.compile(r"\(pp?\.?\s*\d+", re.IGNORECASE)
    violations: list[str] = []

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if page_pattern.search(line):
                violations.append(f"{py_file.name}:{line_no}: {stripped}")

    assert not violations, (
        "Found unverified inline page references in NCR/COPQ engine source files:\n"
        + "\n".join(f"  {v}" for v in violations)
    )

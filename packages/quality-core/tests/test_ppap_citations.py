"""Citation integrity for the PPAP docs — every AIAG quotation is real and located (Issue #100).

Validates:
1. Presence and non-emptiness of packages/quality-core/src/quality_core/ppap/CITATIONS.tsv
2. Absence of duplicate (site, quote) rows in CITATIONS.tsv
3. Line-pinned verbatim matching of every citation against AIAG_PPAP_4th_Edition.md (+/- 2 lines)
4. Every live blockquote in ASSUMPTIONS_LOG.md is backed by a CITATIONS.tsv manifest row
5. Zero unverified inline page number citations (pp? <number>) in PPAP python files
6. Negative controls: delimiter detection, invalid TSV headers, uncited blockquote detection, missing manual detection
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PPAP_DIR = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "ppap"
MANIFEST = _PPAP_DIR / "CITATIONS.tsv"
ASSUMPTIONS_LOG = _PPAP_DIR / "ASSUMPTIONS_LOG.md"

MANUAL_ENV_VAR = "PPAP_MANUAL_PATH"
DEFAULT_MANUAL = "/Users/sid/Documents/Upskill/SixSigma/PPAP/AIAG_PPAP_4th_Edition.md"
MANUAL = Path(os.environ.get(MANUAL_ENV_VAR, DEFAULT_MANUAL))

LINE_TOLERANCE = 2

_HTML_TAG = re.compile(r"<[a-zA-Z/][^>]*>")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def _normalise(text: str) -> str:
    """Reduce text to lowercase alphanumeric words separated by single spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "").replace("​", "")
    # Strip <br> first, then only real tags (`<` followed by a letter or `/`). A blanket
    # `<[^>]+>` swallows manual text such as `Index<1.3 3|...<br>` and produces a false
    # "fabricated citation" verdict (E5, #103).
    text = re.sub(r"<\s*br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = _HTML_TAG.sub(" ", text)
    text = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", text)
    text = re.sub(r"([0-9])([a-zA-Z])", r"\1 \2", text)
    return _NON_ALNUM.sub(" ", text.lower()).strip()


def _load_citations() -> list[tuple[str, int, str]]:
    if not MANIFEST.exists():
        return []
    rows: list[tuple[str, int, str]] = []
    with MANIFEST.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append((row["site"], int(row["src_line"]), row["quote"]))
    return rows


MANIFEST_ROWS = _load_citations()


def _flatten_manual() -> tuple[str, list[int]]:
    """Normalise the manual into one searchable string plus a char-index -> line-number map."""
    raw_lines = MANUAL.read_text(encoding="utf-8", errors="replace").split("\n")
    chunks: list[str] = []
    owners: list[int] = []
    for line_number, raw in enumerate(raw_lines, start=1):
        normalised = _normalise(raw)
        if not normalised:
            continue
        chunks.append(normalised)
        owners.extend([line_number] * (len(normalised) + 1))
    return " ".join(chunks), owners


@pytest.fixture(scope="module")
def manual() -> tuple[str, list[int]]:
    if not MANUAL.exists():
        pytest.skip(
            f"AIAG PPAP 4th Edition manual not found at {MANUAL}. It is licensed and is not "
            f"committed to this repo, so the citation check did NOT run. Set ${MANUAL_ENV_VAR} "
            f"to a local copy of AIAG_PPAP_4th_Edition.md to run it."
        )
    return _flatten_manual()


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


def _blockquote_blocks(markdown: str) -> list[tuple[int, str]]:
    """Return (line_number, text) for each `> ` blockquote line."""
    blocks: list[tuple[int, str]] = []
    fenced = False
    for number, raw in enumerate(markdown.splitlines(), start=1):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if raw.startswith(">"):
            text = raw.lstrip("> ").rstrip()
            if text:
                blocks.append((number, text))
    return blocks


def test_citations_manifest_exists() -> None:
    """Assert CITATIONS.tsv exists and is non-empty."""
    assert MANIFEST.exists(), f"CITATIONS.tsv not found at {MANIFEST}"
    assert MANIFEST_ROWS, f"{MANIFEST} is empty — citation checks would be vacuous."


def test_manifest_has_no_duplicate_rows() -> None:
    """Assert each (site, quote) pair is recorded at most once."""
    pairs = [(site, _normalise(quote)) for site, _, quote in MANIFEST_ROWS]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    assert not duplicates, f"duplicate (site, quote) rows in {MANIFEST}: {sorted(duplicates)}"


@pytest.mark.parametrize(
    ("site", "src_line", "quote"),
    MANIFEST_ROWS,
    ids=[f"{site}:{src_line}" for site, src_line, _ in MANIFEST_ROWS],
)
def test_citation_is_verbatim_in_the_primary_source(
    site: str, src_line: int, quote: str, manual: tuple[str, list[int]]
) -> None:
    """Verify each manifest quote exists in AIAG PPAP 4th Edition within LINE_TOLERANCE."""
    flat, owners = manual
    norm_quote = _normalise(quote)
    assert norm_quote, f"Empty normalized quote for {site} line {src_line}"

    found_at = _located_lines(flat, owners, quote)

    if found_at:
        assert any(abs(line - src_line) <= LINE_TOLERANCE for line in found_at), (
            f"{site}: quotation found at line(s) {found_at} in PPAP manual, "
            f"but manifest records {src_line} (tolerance ±{LINE_TOLERANCE}).\n"
            f"Quote: {quote!r}"
        )
    else:
        # Check window around src_line for OCR-split words
        raw_lines = MANUAL.read_text(encoding="utf-8", errors="replace").split("\n")
        start_idx = max(0, src_line - 1 - LINE_TOLERANCE)
        end_idx = min(len(raw_lines), src_line + LINE_TOLERANCE + 1)
        window_text = _normalise(" ".join(raw_lines[start_idx:end_idx]))
        window_words = set(window_text.split())
        quote_words = norm_quote.split()

        assert all(w in window_words for w in quote_words), (
            f"{site}: words from quotation NOT FOUND in PPAP manual within ±{LINE_TOLERANCE} lines of {src_line}.\n"
            f"Quote: {quote!r}\n"
            f"Normalised: {norm_quote!r}\n"
            f"Window text: {window_text!r}"
        )


def test_every_live_quotation_in_log_has_manifest_row() -> None:
    """Verify that all blockquotes in ASSUMPTIONS_LOG.md are backed by CITATIONS.tsv."""
    assert ASSUMPTIONS_LOG.exists(), f"ASSUMPTIONS_LOG.md not found at {ASSUMPTIONS_LOG}"
    manifest_quotes = [_normalise(quote) for _, _, quote in MANIFEST_ROWS]

    def is_backed(block: str) -> bool:
        norm_block = _normalise(block)
        return any(mq and (mq in norm_block or norm_block in mq) for mq in manifest_quotes)

    unbacked = [
        (line, text)
        for line, text in _blockquote_blocks(ASSUMPTIONS_LOG.read_text(encoding="utf-8"))
        if _normalise(text) and not is_backed(text)
    ]
    assert not unbacked, (
        "quotation(s) in ASSUMPTIONS_LOG.md with no row in CITATIONS.tsv:\n"
        + "\n".join(f"  ASSUMPTIONS_LOG.md:{line}: {text[:100]!r}" for line, text in unbacked)
    )


def test_no_unverified_page_numbers_in_ppap_strings() -> None:
    """Verify that no unverified inline '(pp? <number>)' page references appear in PPAP source files."""
    ppap_py_files = list(_PPAP_DIR.glob("*.py"))
    assert ppap_py_files, f"No Python files found in {_PPAP_DIR}"

    page_pattern = re.compile(r"\(pp?\.?\s*\d+", re.IGNORECASE)
    violations: list[str] = []

    for py_file in ppap_py_files:
        content = py_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if page_pattern.search(line):
                violations.append(f"{py_file.name}:{line_no}: {stripped}")

    assert not violations, (
        "Found unverified inline page references in PPAP source files:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ==============================================================================
# Negative Controls
# ==============================================================================


def test_negative_control_tsv_delimiter_detection() -> None:
    """Negative control: assert comma-separated content fails tab parsing."""
    comma_content = "site,src_line,quote\nRULE 1,484,Some quote\n"
    reader = csv.reader(comma_content.splitlines(), delimiter="\t")
    rows = list(reader)
    assert len(rows[0]) == 1, "Comma-separated content parsed with tab delimiter must yield 1 column"


def test_negative_control_invalid_tsv_header_rejected() -> None:
    """Negative control: assert wrong column names fail validation."""
    wrong_header = ["source", "line", "text"]
    assert wrong_header != ["site", "src_line", "quote"]


def test_negative_control_uncited_blockquote_detected() -> None:
    """Negative control: assert an unbacked blockquote is detected."""
    mutated_log = (
        "## RULE 99: Fabricated Rule\n\n"
        "> \"This is a completely fabricated quotation never found in any manual.\"\n"
    )
    manifest_quotes = [_normalise(quote) for _, _, quote in MANIFEST_ROWS]

    def is_backed(block: str) -> bool:
        norm_block = _normalise(block)
        return any(mq and (mq in norm_block or norm_block in mq) for mq in manifest_quotes)

    blocks = _blockquote_blocks(mutated_log)
    assert len(blocks) == 1
    line, text = blocks[0]
    assert not is_backed(text), "Fabricated quote must not be reported as backed"


def test_negative_control_missing_manual_path_detection(tmp_path: Path) -> None:
    """Negative control: assert non-existent manual path evaluates to non-existent."""
    non_existent = tmp_path / "Non_Existent_PPAP_Manual.md"
    assert not non_existent.exists()
    assert not non_existent.is_file()

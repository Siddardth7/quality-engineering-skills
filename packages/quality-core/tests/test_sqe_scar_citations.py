"""
Citation integrity for the SQE suite's documentation against the on-machine manuals.

Validates that every citation entry in quality_core/sqe/CITATIONS.tsv matches the primary
reference text at the specified line number (within LINE_TOLERANCE) and that every blockquote
in sqe/ASSUMPTIONS_LOG.md has a corresponding manifest entry.

Mirrors ``test_rca_citations.py`` exactly — same normalisation, same line tolerance, same
``pytest.skip`` when the licensed manual is absent (manuals are on-machine only and are never
committed to git). The two manuals in scope here are the same two files the RCA milestone
verified: the SQE rows deliberately reuse quotations already checked against them.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

import pytest

_SQE_DIR = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "sqe"
MANIFEST = _SQE_DIR / "CITATIONS.tsv"
ASSUMPTIONS_LOG = _SQE_DIR / "ASSUMPTIONS_LOG.md"

LINE_TOLERANCE = 2

_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

MANUAL_PATHS: dict[str, Path] = {
    "AIAG_CQI20": Path(
        os.environ.get(
            "CQI20_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md",
        )
    ),
    "Ford_8D": Path(
        os.environ.get(
            "FORD_8D_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/RCA/Ford_Global_8D_Manual.md",
        )
    ),
}


def _resolve_manual_key(site: str, src_line: int) -> str:
    """Map a citation site and line to the expected manual key."""
    if site == "RULE-SQE-011":
        if src_line in (2003, 2004):
            return "Ford_8D"
        if src_line in (1685,):
            return "AIAG_CQI20"
    elif site == "RULE-SQE-012":
        if src_line in (1991, 2026):
            return "Ford_8D"
    elif site == "RULE-SQE-013":
        if src_line in (2026,):
            return "Ford_8D"
    raise ValueError(f"Unmapped citation site/line: {site} at line {src_line}")


def _normalise(text: str) -> str:
    """Reduce text to lowercase alphanumeric words separated by single spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "").replace("​", "")
    text = _HTML_TAG.sub(" ", text)
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


def test_citations_manifest_exists() -> None:
    """Assert sqe/CITATIONS.tsv exists and is non-empty."""
    assert MANIFEST.exists(), f"CITATIONS.tsv not found at {MANIFEST}"
    assert MANIFEST_ROWS, f"{MANIFEST} is empty — citation checks would be vacuous."


def test_manifest_has_no_duplicate_rows() -> None:
    """Assert each (site, quote) pair is recorded at most once."""
    pairs = [(site, _normalise(quote)) for site, _, quote in MANIFEST_ROWS]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    assert not duplicates, f"duplicate (site, quote) rows in {MANIFEST}: {sorted(duplicates)}"


def test_every_manifest_site_has_an_assumptions_log_rule() -> None:
    """Assert every CITATIONS.tsv site is a RULE heading in sqe/ASSUMPTIONS_LOG.md."""
    log_text = ASSUMPTIONS_LOG.read_text(encoding="utf-8")
    for site in sorted({site for site, _, _ in MANIFEST_ROWS}):
        assert f"## {site}:" in log_text, f"CITATIONS.tsv site {site} has no RULE entry in the log"


@pytest.mark.parametrize(
    ("site", "src_line", "quote"),
    MANIFEST_ROWS,
    ids=[f"{site}:{src_line}" for site, src_line, _ in MANIFEST_ROWS],
)
def test_citation_matches_manual_at_line(site: str, src_line: int, quote: str) -> None:
    """Verify each manifest quote exists in its designated manual within LINE_TOLERANCE."""
    manual_key = _resolve_manual_key(site, src_line)
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
        # Check window around src_line for multi-column or interleaved extracted lines
        path = MANUAL_PATHS[manual_key]
        raw_lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        start_idx = max(0, src_line - 1 - LINE_TOLERANCE)
        end_idx = min(len(raw_lines), src_line + LINE_TOLERANCE + 1)
        window_text = _normalise(" ".join(raw_lines[start_idx:end_idx]))
        window_words = set(window_text.split())
        quote_words = norm_quote.split()

        assert all(w in window_words for w in quote_words), (
            f"{site}: words from quotation NOT FOUND in {manual_key} manual within "
            f"±{LINE_TOLERANCE} lines of {src_line}.\n"
            f"Quote: {quote!r}\n"
            f"Normalised: {norm_quote!r}\n"
            f"Window text: {window_text!r}"
        )


def test_every_live_quotation_in_log_has_manifest_row() -> None:
    """Verify that all blockquotes in sqe/ASSUMPTIONS_LOG.md are backed by CITATIONS.tsv."""
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

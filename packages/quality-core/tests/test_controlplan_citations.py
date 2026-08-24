"""
Citation integrity for Control Plan documentation against the on-machine manual.

Validates that every citation entry in quality_core/controlplan/CITATIONS.tsv
matches the primary reference text at the specified line number (within LINE_TOLERANCE).
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

import pytest

MANUAL_ENV_VAR = "FMEA_MANUAL_PATH"
DEFAULT_MANUAL = (
    "/Users/sid/Documents/Upskill/SixSigma/FMEA/pdfcoffee.com_aiag-vda-fmea-handbook-1-version-juni-2019-englisch-pdf-free.md"
)
MANUAL = Path(os.environ.get(MANUAL_ENV_VAR, DEFAULT_MANUAL))

MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "quality_core"
    / "controlplan"
    / "CITATIONS.tsv"
)

LINE_TOLERANCE = 2

_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def _normalise(text: str) -> str:
    cleaned = _HTML_TAG.sub(" ", text)
    decomposed = unicodedata.normalize("NFKD", cleaned)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return _NON_ALNUM.sub(" ", ascii_only).strip()


def _load_citations() -> list[tuple[str, int, str]]:
    if not MANIFEST.exists():
        return []
    rows: list[tuple[str, int, str]] = []
    with MANIFEST.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append((row["site"], int(row["src_line"]), row["quote"]))
    return rows


@pytest.fixture(scope="module")
def manual_lines() -> list[str]:
    if not MANUAL.exists():
        pytest.skip(f"Manual not found at {MANUAL} (set {MANUAL_ENV_VAR})")
    return MANUAL.read_text(encoding="utf-8", errors="replace").splitlines()


def test_citations_manifest_exists() -> None:
    assert MANIFEST.exists(), f"CITATIONS.tsv not found at {MANIFEST}"


@pytest.mark.parametrize(
    ("site", "src_line", "quote"),
    _load_citations(),
)
def test_citation_matches_manual_at_line(
    site: str, src_line: int, quote: str, manual_lines: list[str]
) -> None:
    norm_quote = _normalise(quote)
    assert norm_quote, f"Empty normalized quote for {site} line {src_line}"

    # Check lines within [src_line - LINE_TOLERANCE, src_line + LINE_TOLERANCE]
    start_idx = max(0, src_line - 1 - LINE_TOLERANCE)
    end_idx = min(len(manual_lines), src_line + LINE_TOLERANCE)

    found = False
    for idx in range(start_idx, end_idx):
        # Check single line or 2-line window
        window = manual_lines[idx]
        if idx + 1 < len(manual_lines):
            window += " " + manual_lines[idx + 1]
        norm_window = _normalise(window)
        if norm_quote in norm_window:
            found = True
            break

    assert found, (
        f"Citation for {site} at line {src_line} not found within ±{LINE_TOLERANCE} lines of {MANUAL}.\n"
        f"Quote: {quote!r}\n"
        f"Normalised: {norm_quote!r}"
    )

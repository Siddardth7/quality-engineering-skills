"""
Citation integrity for Root Cause Analysis (RCA) documentation against on-machine manuals.

Validates that every citation entry in quality_core/rca/CITATIONS.tsv matches the primary
reference text at the specified line number (within LINE_TOLERANCE) and that every blockquote
in ASSUMPTIONS_LOG.md has a corresponding manifest entry.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RCA_DIR = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "rca"
MANIFEST = _RCA_DIR / "CITATIONS.tsv"
ASSUMPTIONS_LOG = _RCA_DIR / "ASSUMPTIONS_LOG.md"

LINE_TOLERANCE = 2

_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

MANUAL_PATHS: dict[str, Path] = {
    "Ishikawa": Path(
        os.environ.get(
            "ISHIKAWA_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/RCA/Kaoru_Ishikawa_Guide_to_Quality_Control.md",
        )
    ),
    "ASQ": Path(
        os.environ.get(
            "ASQ_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/RCA/ASQ_The_Quality_Toolbox_2nd_Edition.md",
        )
    ),
    "AIAG_CQI20": Path(
        os.environ.get(
            "CQI20_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md",
        )
    ),
    "Kepner_Tregoe": Path(
        os.environ.get(
            "KT_MANUAL_PATH",
            "/Users/sid/Documents/Upskill/SixSigma/RCA/Kepner_Tregoe_The_New_Rational_Manager.md",
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
    if site == "RULE 1":
        if src_line in (1300, 1405):
            return "Ishikawa"
        if src_line in (14620, 14633, 14642):
            return "ASQ"
        if src_line in (4144, 4146, 4147, 4194, 4195, 4196, 4197, 4198, 4139):
            return "AIAG_CQI20"
    elif site == "RULE 2":
        return "Kepner_Tregoe"
    elif site == "RULE 3":
        if src_line in (1768, 1771, 1774):
            return "AIAG_CQI20"
        if src_line in (2003, 2004):
            return "Ford_8D"
    elif site == "RULE 4":
        if src_line in (29531, 29533):
            return "ASQ"
        if src_line in (1991, 2026):
            return "Ford_8D"
        if src_line in (1685, 1686):
            return "AIAG_CQI20"
    elif site == "RULE 5":
        if src_line in (14637,):
            return "ASQ"
        if src_line in (4140,):
            return "AIAG_CQI20"
    elif site == "RULE-8D-D0":
        return "Ford_8D"  # src_line in (264, 536, 638)
    elif site == "RULE-8D-D1":
        return "Ford_8D"  # src_line in (270, 751, 756, 833)
    elif site == "RULE-8D-D0-001":
        return "Ford_8D"  # src_line == 653
    elif site == "RULE-8D-D0-002":
        return "Ford_8D"  # src_line == 654
    elif site == "RULE-8D-D0-003":
        return "Ford_8D"  # src_line == 539
    elif site == "RULE-8D-D1-001":
        return "AIAG_CQI20"  # src_line == 1213
    elif site == "RULE-8D-D1-002":
        return "Ford_8D"  # src_line == 825
    elif site == "RULE-8D-D1-003":
        return "Ford_8D"  # src_line == 835
    elif site == "RULE-8D-D2":
        if src_line == 1610:
            return "AIAG_CQI20"
        return "Ford_8D"  # src_line == 277
    elif site == "RULE-8D-D3":
        return "Ford_8D"  # src_line in (282, 1182)
    elif site == "RULE-8D-D4":
        return "Ford_8D"  # src_line in (293, 1310, 1313)
    elif site == "RULE-8D-D5":
        return "Ford_8D"  # src_line in (300, 1591, 1692, 1719)
    elif site == "RULE-8D-D6":
        return "Ford_8D"  # src_line in (307, 1805)
    elif site == "RULE-8D-D7":
        return "Ford_8D"  # src_line in (312, 2064)
    elif site == "RULE-8D-D8":
        return "Ford_8D"  # src_line in (318, 2147)
    elif site == "RULE-8D-GATE-CONTAINMENT":
        return "AIAG_CQI20"  # src_line == 1449
    elif site == "RULE-8D-GATE-PREVENTION":
        return "Ford_8D"  # src_line == 1729
    elif site == "RULE-8D-GATE-CLOSURE":
        return "Ford_8D"  # src_line == 1991
    elif site == "RULE-8D-SOURCE-PRIMACY":
        return "AIAG_CQI20"  # src_line == 549
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
    """Assert CITATIONS.tsv exists and is non-empty."""
    assert MANIFEST.exists(), f"CITATIONS.tsv not found at {MANIFEST}"
    assert MANIFEST_ROWS, f"{MANIFEST} is empty — citation checks would be vacuous."


def test_manifest_has_no_duplicate_rows() -> None:
    """Assert each (site, quote) pair is recorded at most once."""
    pairs = [(site, _normalise(quote)) for site, _, quote in MANIFEST_ROWS]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    assert not duplicates, f"duplicate (site, quote) rows in {MANIFEST}: {sorted(duplicates)}"


def test_every_manifest_site_has_an_assumptions_log_rule() -> None:
    """Assert every CITATIONS.tsv site is a RULE heading in rca/ASSUMPTIONS_LOG.md."""
    assert ASSUMPTIONS_LOG.exists(), f"ASSUMPTIONS_LOG.md not found at {ASSUMPTIONS_LOG}"
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
            f"{site}: words from quotation NOT FOUND in {manual_key} manual within ±{LINE_TOLERANCE} lines of {src_line}.\n"
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


def test_every_manifest_row_is_present_in_log() -> None:
    """Assert every manifest quote appears verbatim (normalised) in ASSUMPTIONS_LOG.md.

    Binds manifest -> log per row. Unlike the block-level check above (log -> manifest, per
    contiguous blockquote), this is not defeated by several quotes sharing one blockquote
    block, and it runs on every machine whether or not the licensed manuals are present.
    """
    assert ASSUMPTIONS_LOG.exists(), f"ASSUMPTIONS_LOG.md not found at {ASSUMPTIONS_LOG}"
    log_norm = _normalise(ASSUMPTIONS_LOG.read_text(encoding="utf-8"))
    missing = [
        (site, src_line, quote)
        for site, src_line, quote in MANIFEST_ROWS
        if _normalise(quote) and _normalise(quote) not in log_norm
    ]
    assert not missing, (
        "manifest quote(s) not found verbatim in ASSUMPTIONS_LOG.md — the row is unverifiable "
        "on any machine (corrupted, paraphrased, or absent from the log):\n"
        + "\n".join(f"  {site}:{line}: {quote[:80]!r}" for site, line, quote in missing)
    )


def test_no_unverified_page_numbers_in_rca_engine_strings() -> None:
    """Verify that no unverified inline '(p. <number>)' page references appear in rca engine source files."""
    rca_py_files = list(_RCA_DIR.glob("*.py"))
    assert rca_py_files, f"No Python files found in {_RCA_DIR}"

    page_pattern = re.compile(r"\(pp?\.?\s*\d+", re.IGNORECASE)
    violations: list[str] = []

    for py_file in rca_py_files:
        content = py_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if page_pattern.search(line):
                violations.append(f"{py_file.name}:{line_no}: {stripped}")

    assert not violations, (
        "Found unverified inline page references in RCA engine source files:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


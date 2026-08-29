"""Shared primitives for CITATIONS.tsv ↔ on-machine-manual verification.

This module is intentionally **not** a test module (the leading underscore keeps pytest
from collecting it). It factors the citation-audit machinery that the per-domain
``test_*_citations.py`` files and the ``test_citation_coverage.py`` meta-test share, so the
logic lives in exactly one place.

Design notes:

- **Formatting-tolerant matching** (`normalise`): markdown emphasis, `<sup>` footnote
  markup, soft hyphens, and zero-width spaces are stripped before comparison, so a licensed
  quote that carries such markup is not falsely reported as fabricated (`CLAUDE.md`).
- **Manuals are on-machine only** and never committed to git. When a manual file is absent
  the manual-match is *skipped*, never failed — the structural checks (manifest present,
  no duplicate rows, every live blockquote backed) still run everywhere, including CI.
- **"Any declared manual"** matching: several domains cite more than one licensed manual and
  the per-row manual is not recorded in the manifest. A row passes when its quote appears at
  the cited line (± ``LINE_TOLERANCE``) in *at least one* of the domain's declared manuals.
  ``src_line`` is manual-specific, so a coincidental cross-manual match at the same line is
  vanishingly unlikely; a quote absent from its true manual at the cited line still fails.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

import pytest

LINE_TOLERANCE = 2

_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

QUALITY_CORE_SRC = Path(__file__).resolve().parents[1] / "src" / "quality_core"


def manual_path(env_var: str, default: str) -> Path:
    """Resolve a manual path, honouring an env-var override (CI can point at a mount)."""
    return Path(os.environ.get(env_var, default))


def normalise(text: str) -> str:
    """Reduce text to lowercase alphanumeric words separated by single spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "").replace("​", "")
    text = _HTML_TAG.sub(" ", text)
    return _NON_ALNUM.sub(" ", text.lower()).strip()


def load_citations(manifest_path: Path) -> list[tuple[str, int, str]]:
    """Read (site, src_line, quote) rows from a CITATIONS.tsv, skipping comments/blanks."""
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


def blockquote_blocks(markdown: str) -> list[tuple[int, str]]:
    """Return (first_line_number, text) for each contiguous ``> `` blockquote block."""
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


def _flatten_manual(path: Path) -> tuple[str, list[int]]:
    """Normalise a manual into one searchable string plus a char-index → line-number map."""
    raw_lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
    chunks: list[str] = []
    owners: list[int] = []
    for line_number, raw in enumerate(raw_lines, start=1):
        normalised = normalise(raw)
        if not normalised:
            continue
        chunks.append(normalised)
        owners.extend([line_number] * (len(normalised) + 1))
    return " ".join(chunks), owners


_MANUAL_CACHE: dict[str, tuple[str, list[int]]] = {}


def _get_flattened_manual(path: Path) -> tuple[str, list[int]]:
    key = str(path)
    if key not in _MANUAL_CACHE:
        _MANUAL_CACHE[key] = _flatten_manual(path)
    return _MANUAL_CACHE[key]


def located_lines(flat: str, owners: list[int], quote: str) -> list[int]:
    """Every source line at which ``quote`` occurs in the flattened manual."""
    needle = normalise(quote)
    assert needle, "manifest quote normalises to nothing"
    lines: list[int] = []
    start = flat.find(needle)
    while start >= 0:
        lines.append(owners[start])
        start = flat.find(needle, start + 1)
    return lines


def _matches_at_line(path: Path, src_line: int, quote: str) -> bool:
    """True if ``quote`` occurs in ``path`` within ± LINE_TOLERANCE of ``src_line``."""
    flat, owners = _get_flattened_manual(path)
    found_at = located_lines(flat, owners, quote)
    if found_at:
        return any(abs(line - src_line) <= LINE_TOLERANCE for line in found_at)
    # Fallback: window match, for multi-column / interleaved extracted lines.
    raw_lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
    start_idx = max(0, src_line - 1 - LINE_TOLERANCE)
    end_idx = min(len(raw_lines), src_line + LINE_TOLERANCE + 1)
    window_words = set(normalise(" ".join(raw_lines[start_idx:end_idx])).split())
    quote_words = normalise(quote).split()
    return bool(quote_words) and all(w in window_words for w in quote_words)


def assert_quote_in_any_manual(
    site: str, src_line: int, quote: str, manuals: dict[str, Path]
) -> None:
    """Verify ``quote`` appears at ``src_line`` (± tolerance) in at least one declared manual.

    Skips when no *text* manual is on-machine (on-machine-only licensing); fails when at
    least one text manual is present but none contains the quote at the cited line.

    ``.pdf`` manuals are excluded from line-matching: reading a PDF as text yields binary
    noise, so a domain whose only on-machine sources are PDFs (e.g. COPQ) is verified by the
    structural checks, not by line-matching. Extract a ``.md`` and point the domain's
    ``*_MANUAL_PATH`` env var at it to enable line-verification.
    """
    assert normalise(quote), f"Empty normalised quote for {site} line {src_line}"
    present = {
        name: p for name, p in manuals.items() if p.exists() and p.suffix.lower() != ".pdf"
    }
    if not present:
        pytest.skip(
            "No text (.md) manual on-machine for "
            f"{site}: {sorted(str(p) for p in manuals.values())}. "
            "Licensed manuals are on-machine only and not committed to git; PDF-only "
            "sources are verified structurally, not by line-match."
        )
    if any(_matches_at_line(p, src_line, quote) for p in present.values()):
        return
    raise AssertionError(
        f"{site}: quotation NOT FOUND at line {src_line} (±{LINE_TOLERANCE}) in any present "
        f"manual {sorted(present)}.\nQuote: {quote!r}\nNormalised: {normalise(quote)!r}"
    )


def assert_no_duplicate_rows(rows: list[tuple[str, int, str]], manifest_path: Path) -> None:
    """Assert each (site, normalised-quote) pair appears at most once."""
    pairs = [(site, normalise(quote)) for site, _, quote in rows]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    assert not duplicates, f"duplicate (site, quote) rows in {manifest_path}: {sorted(duplicates)}"


def assert_blockquotes_backed(log_path: Path, rows: list[tuple[str, int, str]]) -> None:
    """Assert every live blockquote in the log is backed by a manifest row (or its inverse).

    This is the manual-independent load-bearing check: corrupting a manifest quote that backs
    a blockquote unbinds it and fails here, even when no licensed manual is on-machine.
    """
    assert log_path.exists(), f"ASSUMPTIONS_LOG.md not found at {log_path}"
    manifest_quotes = [normalise(quote) for _, _, quote in rows]

    def is_backed(block: str) -> bool:
        norm_block = normalise(block)
        return any(mq and (mq in norm_block or norm_block in mq) for mq in manifest_quotes)

    unbacked = [
        (line, text)
        for line, text in blockquote_blocks(log_path.read_text(encoding="utf-8"))
        if normalise(text) and not is_backed(text)
    ]
    assert not unbacked, (
        f"quotation(s) in {log_path.name} with no row in CITATIONS.tsv:\n"
        + "\n".join(f"  {log_path.name}:{line}: {text[:100]!r}" for line, text in unbacked)
    )


def assert_manifest_rows_present_in_log(log_path: Path, rows: list[tuple[str, int, str]]) -> None:
    """Assert every manifest quote appears verbatim (normalised) in the log text.

    This is the manual-independent negative control for a domain whose manuals cannot be
    line-matched (e.g. COPQ's PDF-only sources): corrupting *any single* manifest row makes
    that row's quote vanish from the log and fails here. Unlike ``assert_blockquotes_backed``
    (log → manifest, and per contiguous block), this binds manifest → log per row, so it is
    not defeated by several quotes sharing one contiguous blockquote block.
    """
    assert log_path.exists(), f"ASSUMPTIONS_LOG.md not found at {log_path}"
    log_norm = normalise(log_path.read_text(encoding="utf-8"))
    missing = [
        (site, src_line, quote)
        for site, src_line, quote in rows
        if normalise(quote) and normalise(quote) not in log_norm
    ]
    assert not missing, (
        f"manifest quote(s) not found verbatim in {log_path.name} — the row is unverifiable "
        "on any machine (corrupted, paraphrased, or absent from the log):\n"
        + "\n".join(f"  {site}:{ln}: {q[:80]!r}" for site, ln, q in missing)
    )


def assert_no_unverified_page_refs(dirs: list[Path]) -> None:
    """Assert no unverified inline ``(p. <n>)`` page references appear in engine source."""
    py_files: list[Path] = []
    for d in dirs:
        py_files.extend(d.glob("*.py"))
    assert py_files, f"No Python files found in {dirs}"
    page_pattern = re.compile(r"\(pp?\.?\s*\d+", re.IGNORECASE)
    violations: list[str] = []
    for py_file in py_files:
        for line_no, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            if page_pattern.search(line):
                violations.append(f"{py_file.name}:{line_no}: {line.strip()}")
    assert not violations, "unverified inline page references in engine source:\n" + "\n".join(
        f"  {v}" for v in violations
    )

"""Shared primitive for asserting a saved .xlsx cell holds a **live** formula.

Like ``_citation_audit``, this module is intentionally **not** a test module (the
leading underscore keeps pytest from collecting it) and is not shipped code — it is
a test utility every exporter suite can import:

    from _xlsx_formula_audit import assert_cell_is_formula

Why raw XML and not openpyxl: re-reading a saved workbook through openpyxl
normalises formula cells transparently (``cell.value`` is the ``"=..."`` string
either way once you round-trip), which masks the very distinction this check
exists to prove — a live ``<f>`` element (ECMA-376 / OOXML SpreadsheetML) versus a
hardcoded literal. So the workbook bytes are unzipped and the worksheet part is
parsed directly.

**Why this file exists twice.** This is a verbatim duplicate of
``packages/quality-core/tests/_xlsx_formula_audit.py``. The bare
``from _xlsx_formula_audit import ...`` the quality-core exporter suites use works only
because pytest puts ``packages/quality-core/tests/`` on ``sys.path`` for *that* package's
run; ``packages/quality-mcp/tests/`` is a different rootdir and ``quality-core/tests`` is
not an installed package, so ``test_e2e_catalog_regression.py`` (#150) cannot reach the
original. Duplicating a small, static, dependency-free helper matches this package's own
convention of duplicating fixtures across test modules rather than adding a ``conftest.py``
(see the "no conftest.py" notes in ``test_ppap_client_roundtrip.py`` /
``test_sqe_client_roundtrip.py``). Keep the two copies byte-identical apart from this note.
"""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _worksheet_part(zf: zipfile.ZipFile, sheet_name: str) -> str:
    """Resolve ``sheet_name`` to its ``xl/worksheets/*.xml`` part name.

    Goes through ``xl/workbook.xml``'s ``<sheet name=".." r:id=".."/>`` mapping and
    ``xl/_rels/workbook.xml.rels`` rather than guessing ``sheet1.xml``, so renamed,
    reordered, and XML-escaped sheet names in multi-sheet workbooks resolve.
    """
    workbook = ElementTree.fromstring(zf.read("xl/workbook.xml"))
    rel_id = None
    for sheet in workbook.iter(f"{_MAIN_NS}sheet"):
        if sheet.get("name") == sheet_name:
            rel_id = sheet.get(f"{_REL_NS}id")
            break
    assert rel_id is not None, (
        f"sheet {sheet_name!r} not found in workbook; "
        f"sheets present: {[s.get('name') for s in workbook.iter(f'{_MAIN_NS}sheet')]}"
    )

    rels = ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.iter(f"{_PKG_REL_NS}Relationship"):
        if rel.get("Id") == rel_id:
            target = (rel.get("Target") or "").lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise AssertionError(f"relationship {rel_id!r} for sheet {sheet_name!r} not found")


def assert_cell_is_formula(workbook_bytes: bytes, sheet_name: str, coord: str) -> None:
    """Assert ``coord`` (e.g. ``"B2"``) on ``sheet_name`` is a live formula cell.

    Raises ``AssertionError`` — naming the cell's actual stored content — when the
    cell is missing from the saved XML entirely (openpyxl omits never-written cells)
    or when it is present but holds a literal with no ``<f>`` child.
    """
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as zf:
        sheet_xml = zf.read(_worksheet_part(zf, sheet_name))

    for cell in ElementTree.fromstring(sheet_xml).iter(f"{_MAIN_NS}c"):
        if cell.get("r") == coord:
            assert cell.find(f"{_MAIN_NS}f") is not None, (
                f"{sheet_name}!{coord} is a literal, not a live formula: "
                f"stored value {''.join(cell.itertext())!r}"
            )
            return
    raise AssertionError(
        f"{sheet_name}!{coord} is absent from the saved worksheet XML "
        f"(openpyxl omits cells that were never written)"
    )

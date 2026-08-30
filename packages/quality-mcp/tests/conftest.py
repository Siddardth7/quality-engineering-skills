"""
conftest.py
Import-path setup for the quality-mcp test package.

Deliberately holds **no fixtures**. The established convention in this package is that test
modules duplicate their own fixtures rather than share them (see the "no conftest.py to share
fixtures" notes in ``test_ppap_client_roundtrip.py`` and ``test_sqe_client_roundtrip.py``);
that convention is unchanged.

The single line below exists for the same reason as its counterpart in
``packages/quality-core/tests/conftest.py``: the root ``pyproject.toml`` sets
``--import-mode=importlib``, which does not put a test file's own directory on ``sys.path``,
so the non-collected ``_xlsx_formula_audit`` helper next to these tests is otherwise
unimportable from ``test_e2e_catalog_regression.py`` (#150).
"""
from __future__ import annotations

import os
import sys

# Make this directory importable so the test modules can share the non-collected
# `_xlsx_formula_audit` helper regardless of pytest's import mode / rootdir.
sys.path.insert(0, os.path.dirname(__file__))

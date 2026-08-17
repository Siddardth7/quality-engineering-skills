"""
tests/test_packaging.py
Tests for quality-mcp packaging metadata and dependency contract.

Validates that quality-mcp remains a headless daemon communicating via stdio
with LLM hosts, resolving only core engineering dependencies and FastMCP,
with zero Streamlit or UI-chain packages.
"""

from __future__ import annotations

import re
from importlib.metadata import requires

_NAME_DELIMITERS = re.compile(r"[<>=!~;[ ]")


def _bare_name(requirement: str) -> str:
    return _NAME_DELIMITERS.split(requirement.strip(), maxsplit=1)[0]


def _hard_requirements() -> set[str]:
    """Distribution names quality-mcp requires with no extra."""
    return {
        _bare_name(req)
        for req in requires("quality-mcp") or []
        if "extra ==" not in req
    }


def test_mcp_hard_dependencies() -> None:
    """quality-mcp declares only FastMCP and quality-core as hard dependencies."""
    assert _hard_requirements() == {
        "mcp",
        "quality-core",
    }


def test_mcp_has_no_ui_dependencies() -> None:
    """quality-mcp must not declare or require any UI-chain packages."""
    forbidden = {"streamlit", "gitpython", "tornado", "protobuf", "pyarrow", "pydeck"}
    declared = {_bare_name(req) for req in requires("quality-mcp") or []}
    assert declared.isdisjoint(forbidden)

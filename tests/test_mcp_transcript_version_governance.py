"""Governance suite for the "Verified" JSON-RPC transcript in `docs/mcp-client-setup.md` (#239).

A document titled *Verified* has to stay verified. Section `## 4.` pastes the output of a live
`quality-mcp` session; nothing re-checks it, so it drifted — the `ping` response still claimed
`0.1.0` long after `quality_mcp.__version__` reached `1.1.0`, and the `tools/list` excerpt showed
2 of 34 tools with no marker saying so.

This suite pins the transcript to the *installed package*, never to a hardcoded literal. A check
that greps for the current version string passes vacuously the moment someone bumps
`__version__` and forgets the doc — which is the exact defect it would be written to prevent.

What is asserted:

1. Every JSON object in §4 that carries ``"server": "quality-mcp"`` alongside a ``"version"`` key
   equals the live ``quality_mcp.__version__``.
2. The `ping` block's doubly-encoded ``content[0].text`` version agrees with its
   ``structuredContent.version`` (the two-copies-of-one-value drift the original defect was).
3. §4.2's stated tool count and its flat tool-name list match a live ``tools/list`` call.
4. Negative control: the same extraction helpers, pointed at a fixture with a wrong version,
   report a mismatch.

Discriminator note — why ``"server"`` and not ``"name"``: FastMCP's ``serverInfo`` is
``{"name": "quality-mcp", "version": "<MCP SDK version>"}``. It legitimately carries the SDK
version, not the package version, so a ``"name"``-keyed discriminator would fail on *correct*
content and push someone to "fix" the doc into a falsehood. ``clientInfo`` is
``{"name": "mcp-client", ...}``. Only the `ping` payload carries a ``"server"`` key, so keying on
it hits `ping` alone — structurally, not via a line-number allowlist.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import quality_mcp
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC = _REPO_ROOT / "docs" / "mcp-client-setup.md"

_SECTION_HEADING = "## 4. Verified JSON-RPC Protocol Transcript"
_JSON_FENCE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
_TOOL_COUNT_MARKER = re.compile(r"showing 2 of (\d+) tools")
_TOOL_NAME_ITEM = re.compile(r"^\d+\. `([a-z0-9_]+)`$", re.MULTILINE)
_SERVER_NAME = "quality-mcp"


def _transcript_section(markdown_text: str) -> str:
    """Return the body of the `## 4.` transcript section, up to the next `## ` heading."""
    start = markdown_text.index(_SECTION_HEADING)
    rest = markdown_text[start + len(_SECTION_HEADING) :]
    end = rest.index("\n## ")
    return rest[:end]


def _json_blocks(section_body: str) -> Iterator[Any]:
    """Yield every parsed ```json fenced block in `section_body`."""
    for match in _JSON_FENCE.finditer(section_body):
        yield json.loads(match.group(1))


def _server_versions(node: Any) -> Iterator[str]:
    """Yield `version` values from nodes identifying themselves as the quality-mcp server.

    A dict qualifies only when it carries both `"version"` and `"server": "quality-mcp"` — the
    `ping` payload's own shape. `serverInfo` (SDK version) and `clientInfo` are walked past.
    """
    if isinstance(node, dict):
        if node.get("server") == _SERVER_NAME and "version" in node:
            yield str(node["version"])
        for value in node.values():
            yield from _server_versions(value)
    elif isinstance(node, list):
        for item in node:
            yield from _server_versions(item)


@pytest.fixture(scope="module")
def live_tool_names() -> list[str]:
    """Names of every tool a live in-process `quality-mcp` session advertises.

    A fixture, not an inline call: `anyio` clears the calling frame's trace function, so a test
    that ran the session inline would leave every statement after it uncovered.
    """

    async def _run() -> list[str]:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return [tool.name for tool in tools_result.tools]

    return asyncio.run(_run())


def test_transcript_server_versions_match_installed_package() -> None:
    """Every server-identifying `version` in §4 equals the live `quality_mcp.__version__`."""
    section = _transcript_section(_DOC.read_text(encoding="utf-8"))
    versions = [v for block in _json_blocks(section) for v in _server_versions(block)]

    # Guard against a vacuous pass if the section is emptied or the fence syntax changes.
    assert versions, f"no server-identifying version found under {_SECTION_HEADING!r}"
    assert set(versions) == {quality_mcp.__version__}, (
        f"transcript reports {sorted(set(versions))}, installed package is "
        f"{quality_mcp.__version__} — re-capture the transcript per §4.0"
    )


def test_ping_text_and_structured_versions_agree() -> None:
    """The `ping` block's doubly-encoded text version matches its `structuredContent`."""
    section = _transcript_section(_DOC.read_text(encoding="utf-8"))
    checked = 0
    for block in _json_blocks(section):
        result = block.get("result", {}) if isinstance(block, dict) else {}
        structured = result.get("structuredContent") if isinstance(result, dict) else None
        if not isinstance(structured, dict) or structured.get("server") != _SERVER_NAME:
            continue
        decoded = json.loads(result["content"][0]["text"])
        assert decoded == structured, "ping text content disagrees with structuredContent"
        checked += 1
    assert checked, "no ping tools/call block found in the transcript section"


def test_tool_catalog_marker_and_names_match_live_server(live_tool_names: list[str]) -> None:
    """§4.2's stated count and flat tool-name list match a live `tools/list` call."""
    section = _transcript_section(_DOC.read_text(encoding="utf-8"))

    marker = _TOOL_COUNT_MARKER.search(section)
    assert marker is not None, "§4.2 must state the true tool count ('showing 2 of N tools')"
    assert int(marker.group(1)) == len(live_tool_names)

    documented = _TOOL_NAME_ITEM.findall(section)
    assert documented == live_tool_names, (
        "§4.2's tool-name list differs from the live server — re-capture it per §4.0"
    )


def test_version_checker_flags_a_stale_transcript() -> None:
    """Negative control: the same helpers report a mismatch on a deliberately stale fixture."""
    stale_version = "0.0.0-not-a-real-version"
    fixture = f"""{_SECTION_HEADING}

```json
{{
  "result": {{
    "structuredContent": {{
      "status": "ok",
      "server": "{_SERVER_NAME}",
      "version": "{stale_version}"
    }}
  }}
}}
```

## 5. Troubleshooting
"""
    section = _transcript_section(fixture)
    versions = [v for block in _json_blocks(section) for v in _server_versions(block)]
    assert versions == [stale_version]
    assert set(versions) != {quality_mcp.__version__}


def test_version_checker_ignores_client_and_sdk_version_blocks() -> None:
    """Negative control: `clientInfo` and `serverInfo` are structurally out of scope.

    `serverInfo` legitimately reports the MCP SDK version and `clientInfo` the client's own —
    neither may ever be flagged, or the "fix" would write a falsehood into the doc.
    """
    fixture = f"""{_SECTION_HEADING}

```json
{{
  "params": {{"clientInfo": {{"name": "mcp-client", "version": "1.0.0"}}}},
  "result": {{
    "serverInfo": {{"name": "{_SERVER_NAME}", "version": "1.29.0"}},
    "content": [{{"type": "text", "text": "no versions here"}}]
  }}
}}
```

## 5. Troubleshooting
"""
    section = _transcript_section(fixture)
    assert [v for block in _json_blocks(section) for v in _server_versions(block)] == []

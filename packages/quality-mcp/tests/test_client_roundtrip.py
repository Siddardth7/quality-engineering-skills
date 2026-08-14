"""Integration tests proving in-process MCP client-server round-trip communication."""

from __future__ import annotations

import asyncio
import json

import quality_mcp
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_mcp.server import mcp


def test_client_session_initialization_and_tool_discovery() -> None:
    """In-process client initializes session and discovers registered ping tool."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"

            tools_result = await session.list_tools()
            tool_names = [tool.name for tool in tools_result.tools]
            assert "ping" in tool_names

            ping_tool = next(t for t in tools_result.tools if t.name == "ping")
            assert ping_tool.description is not None
            assert len(ping_tool.description) > 0
            assert "Health check" in ping_tool.description
            assert ping_tool.inputSchema is not None
            assert isinstance(ping_tool.inputSchema, dict)

    asyncio.run(_run())


def test_client_session_call_ping_success() -> None:
    """In-process client calls ping tool and receives valid structured and text responses."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            res = await session.call_tool("ping", {})

            assert res.isError is False
            expected_payload = {
                "status": "ok",
                "server": "quality-mcp",
                "version": quality_mcp.__version__,
            }
            assert res.structuredContent == expected_payload
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"
            assert json.loads(res.content[0].text) == expected_payload

    asyncio.run(_run())


def test_client_session_call_unknown_tool_negative_control() -> None:
    """In-process client calling an unknown tool returns an error result."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            res = await session.call_tool("unknown_tool_name", {})

            assert res.isError is True
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert "Unknown tool: unknown_tool_name" in res.content[0].text
            assert res.structuredContent is None

    asyncio.run(_run())

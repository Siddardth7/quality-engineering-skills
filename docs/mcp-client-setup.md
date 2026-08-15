# Model Context Protocol (MCP) Client Setup

This guide details how to configure Model Context Protocol (MCP) clients—including Claude Code, Cursor, and other MCP-compliant hosts—to communicate with `quality-mcp`.

`quality-mcp` exposes the deterministic quality engineering engines in `quality-core` (Statistical Process Control, Measurement System Analysis, FMEA risk scoring, Control Plans) as callable MCP tools over standard transports.

---

## 1. Prerequisites

Before connecting an MCP client to `quality-mcp`:

1. **Python 3.11+** installed on your system.
2. **`uv` package manager** installed (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`).
3. **Workspace dependencies installed**:
   ```bash
   uv sync --frozen
   ```
   This installs the workspace packages and registers the `quality-mcp` console script in the local `.venv`.

---

## 2. Configuration

### Automatic Discovery via `.mcp.json`

The repository root includes a standard [`.mcp.json`](../.mcp.json) configuration file:

```json
{
  "mcpServers": {
    "quality-mcp": {
      "command": "uv",
      "args": [
        "run",
        "quality-mcp"
      ]
    }
  }
}
```

MCP hosts that recognize repository-level `.mcp.json` files (such as Claude Code and Cursor) will discover and load the `quality-mcp` server automatically when opening this workspace.

---

### Claude Code Setup

Claude Code automatically detects [`.mcp.json`](../.mcp.json) in the workspace root. Alternatively, you can configure it explicitly using the Claude Code CLI or configuration files:

#### Option A: Project Configuration CLI
Run the following command from the repository root:
```bash
claude mcp add quality-mcp uv run quality-mcp
```

#### Option B: User Configuration (`~/.claude.json`)
To make `quality-mcp` available across workspaces, add the server to your global configuration with the absolute workspace directory:
```json
{
  "mcpServers": {
    "quality-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/quality-engineering-skills",
        "run",
        "quality-mcp"
      ]
    }
  }
}
```

---

### Cursor Setup

Cursor supports MCP servers configured via workspace settings or global configuration:

#### Option A: Workspace Settings (`.cursor/mcp.json`)
Create or edit `.cursor/mcp.json` in the workspace root:
```json
{
  "mcpServers": {
    "quality-mcp": {
      "command": "uv",
      "args": [
        "run",
        "quality-mcp"
      ]
    }
  }
}
```

#### Option B: Cursor Settings UI
1. Open **Cursor Settings** (`Cmd+,` / `Ctrl+,`).
2. Navigate to **Features** > **MCP**.
3. Click **+ Add New MCP Server**.
4. Configure:
   - **Name**: `quality-mcp`
   - **Type**: `command`
   - **Command**: `uv run quality-mcp` (run from the workspace root).

---

## 3. Testing and Verification

### In-Process Round-Trip Suites
The automated test suites exercise MCP client-server protocol lifecycles (`initialize`, `tools/list`, and `tools/call`) using in-process memory transports:

1. **Ping Health Check Round-Trip**:
   ```bash
   uv run pytest packages/quality-mcp/tests/test_client_roundtrip.py -v
   ```

2. **FMEA Action Priority Round-Trip**:
   ```bash
   uv run pytest packages/quality-mcp/tests/test_fmea_client_roundtrip.py -v
   ```
   Validates session handshake, tool discovery of `lookup_fmea_ap`, round-trip evaluation against 12 real-world automotive DFMEA/PFMEA failure modes across High/Medium/Low Action Priority, dual structured and serialized payload parity against `quality_core.scoring`, and protocol-level negative controls for out-of-range integer scores, non-integer types, and unknown tools.

### Coverage Gate
Run the full 100% line and branch coverage gate for `quality-mcp`:
```bash
uv run pytest packages/quality-mcp --cov=quality_mcp --cov-report=term-missing --cov-fail-under=100
```

---

## 4. Verified JSON-RPC Protocol Transcript

Below is a verified JSON-RPC 2.0 message exchange showing client initialization, tool discovery, and tool execution against `quality-mcp`.

### 4.1 Initialization (`initialize`)

**Client Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "roots": {
        "listChanged": true
      }
    },
    "clientInfo": {
      "name": "mcp-client",
      "version": "1.0.0"
    }
  }
}
```

**Server Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "prompts": {
        "listChanged": false
      },
      "resources": {
        "subscribe": false,
        "listChanged": false
      },
      "tools": {
        "listChanged": false
      }
    },
    "serverInfo": {
      "name": "quality-mcp",
      "version": "1.29.0"
    }
  }
}
```

**Client Notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

---

### 4.2 Tool Discovery (`tools/list`)

**Client Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**Server Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "ping",
        "description": "Health check endpoint confirming MCP server availability and version.",
        "inputSchema": {
          "type": "object",
          "title": "pingArguments",
          "properties": {}
        },
        "outputSchema": {
          "type": "object",
          "title": "pingDictOutput",
          "additionalProperties": {
            "type": "string"
          }
        }
      },
      {
        "name": "lookup_fmea_ap",
        "description": "Look up AIAG-VDA 2019 Action Priority and calculate RPN for an FMEA item.",
        "inputSchema": {
          "type": "object",
          "title": "lookup_fmea_apArguments",
          "properties": {
            "severity": {
              "title": "Severity",
              "description": "Severity rating (1–10 on the AIAG-VDA scale)",
              "type": "integer"
            },
            "occurrence": {
              "title": "Occurrence",
              "description": "Occurrence rating (1–10 on the AIAG-VDA scale)",
              "type": "integer"
            },
            "detection": {
              "title": "Detection",
              "description": "Detection rating (1–10 on the AIAG-VDA scale)",
              "type": "integer"
            }
          },
          "required": [
            "severity",
            "occurrence",
            "detection"
          ]
        }
      }
    ]
  }
}
```

---

### 4.3 Tool Invocation (`tools/call` -> `ping`)

**Client Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "ping",
    "arguments": {}
  }
}
```

**Server Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"status\": \"ok\",\n  \"server\": \"quality-mcp\",\n  \"version\": \"0.1.0\"\n}"
      }
    ],
    "structuredContent": {
      "status": "ok",
      "server": "quality-mcp",
      "version": "0.1.0"
    },
    "isError": false
  }
}
```

---

### 4.4 Tool Invocation (`tools/call` -> `lookup_fmea_ap` Success)

**Client Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "lookup_fmea_ap",
    "arguments": {
      "severity": 10,
      "occurrence": 4,
      "detection": 4
    }
  }
}
```

**Server Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"severity\": 10,\n  \"occurrence\": 4,\n  \"detection\": 4,\n  \"rpn\": 160,\n  \"action_priority\": \"High\"\n}"
      }
    ],
    "structuredContent": {
      "severity": 10,
      "occurrence": 4,
      "detection": 4,
      "rpn": 160,
      "action_priority": "High"
    },
    "isError": false
  }
}
```

---

### 4.5 Tool Invocation (`tools/call` -> `lookup_fmea_ap` Validation Error)

**Client Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "lookup_fmea_ap",
    "arguments": {
      "severity": 11,
      "occurrence": 5,
      "detection": 5
    }
  }
}
```

**Server Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error executing tool lookup_fmea_ap: Severity score 11 is out of range. Valid range is 1–10 (AIAG-VDA scale)."
      }
    ],
    "isError": true
  }
}
```

---

## 5. Troubleshooting

| Issue | Cause | Resolution |
|---|---|---|
| `command not found: uv` | `uv` is not installed or not in `$PATH` | Install `uv` via `curl -LsSf https://astral.sh/uv/install.sh \| sh` and ensure `~/.local/bin` (or `~/.cargo/bin`) is in your `$PATH`. |
| Server exits immediately | Missing workspace dependencies | Run `uv sync --frozen` in the repository root to synchronize the virtual environment. |
| Tool calls return unknown tool error | Tool name misspelled or not registered | Verify available tools via `tools/list` or check `packages/quality-mcp/src/quality_mcp/server.py`. |
| Working directory mismatch | Client launched `uv run` from a different folder | Provide `--directory /path/to/quality-engineering-skills` in the `args` array if launching from an external path. |

---

## Related Documentation

- [`README.md`](../README.md) — Platform overview and quickstart
- [`packages/quality-mcp/README.md`](../packages/quality-mcp/README.md) — MCP server package overview
- [`ROADMAP.md`](../ROADMAP.md) — Product roadmap and release milestones

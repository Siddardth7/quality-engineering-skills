---
name: mcp-health
description: Health check and connectivity verification for quality-mcp server and core engine bindings.
---

# MCP Platform Health & Connectivity Verification

## Overview
The `mcp-health` skill provides operational verification procedures for the Quality Platform MCP server (`quality-mcp`). It ensures that the FastMCP server instance is active, responsive, aligned with workspace version `0.1.0`, and ready to accept tool invocation requests for deterministic calculation engines.

This skill serves as the baseline connectivity check before executing downstream domain skills (e.g., FMEA, SPC, MSA, Control Plan, RCA).

## When to Use
Activate this skill in any of the following operational scenarios:
- **Session Initialization:** At the start of an AI agent session to verify MCP tool connectivity.
- **Pre-flight Checks:** Prior to running complex analytical workflows (e.g., control chart calculations, Gage R&R ANOVA analysis).
- **Diagnostic Troubleshooting:** When tool calls to `quality-mcp` time out, fail to resolve, or return unexpected transport errors.
- **Version Alignment Verification:** To confirm that the runtime server matches the workspace platform version (`0.1.0`).

## Step-by-Step Methodology
1. **Initiate Health Check Query:**
   - Formulate a connectivity check request.
   - Identify the target MCP server as `quality-mcp`.
2. **Execute Diagnostic Tool Call:**
   - Call the `ping` tool with no arguments.
   - Monitor for successful transport round-trip.
3. **Validate Response Payload:**
   - Verify `"status"` is `"ok"`.
   - Verify `"server"` matches `"quality-mcp"`.
   - Verify `"version"` aligns with platform workspace version `0.1.0`.
4. **Evaluate Readiness & Proceed:**
   - If response matches expected schema, report platform healthy and proceed to domain workflows.
   - If response indicates failure or connection error, guide user through server restart and troubleshooting procedures.

## Tool Invocations

### `ping`
- **MCP Server:** `quality-mcp`
- **Purpose:** Health check endpoint confirming MCP server availability and version.
- **Parameters:** None
- **Return Type:** `dict[str, str]`
- **Response Schema:**
  ```json
  {
    "status": "ok",
    "server": "quality-mcp",
    "version": "0.1.0"
  }
  ```
- **Example Invocation:**
  ```json
  {}
  ```

## Best Practices
- **Run Pre-flight Before Heavy Analysis:** Always verify MCP connectivity before loading large datasets for SPC or MSA analysis.
- **Never Simulate Tool Outputs:** Never fake or hallucinate a health check response. If the tool call fails, report the actual connection error.
- **Strict Invariant: No Inline Math in Prompt Context:** Always route computational tasks to deterministic `quality-core` engines via MCP tools; do not perform manual math.
- **Version Consistency:** Check that the reported server version matches the expected platform release version (`0.1.0`).

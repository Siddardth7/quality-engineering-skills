# Changelog

All notable changes to **Engine-Powered Quality Engineering Skills** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions are milestone-driven, not date-driven — see [`ROADMAP.md`](ROADMAP.md).

## [Unreleased]

### Added
- In-process MCP client-server round-trip test suite in `packages/quality-mcp/tests/test_client_roundtrip.py` verifying session initialization, tool discovery, structured `ping` execution, and protocol-level error handling (#4).
- Root workspace `.mcp.json` configuration registering `quality-mcp` for Claude Code, Cursor, and MCP-compliant AI hosts (#4).
- Client setup guide in `docs/mcp-client-setup.md` covering Claude Code/Cursor configuration, prerequisites, troubleshooting, and verified JSON-RPC protocol transcripts (#4).
- GitHub task issue template (`.github/ISSUE_TEMPLATE/task.md`), issue config disabling blank issues (`.github/ISSUE_TEMPLATE/config.yml`), and Definition of Done-enforcing PR template (`.github/pull_request_template.md`) (#5).
- FastMCP server instance (`quality-mcp`), `ping` health check tool, and `quality-mcp` console script entry point in `packages/quality-mcp` (#2).
- `packages/quality-mcp` workspace member binding `quality-core` engines to Model Context Protocol endpoints.
- Project planning documents: `Idea.md`, `ROADMAP.md` (v3.0, rescoped to 10 releases), `Execution.md` (v2.0).

### Changed
- CI gate (`.github/workflows/ci.yml`) extended with headless dependency guard and 100% line/branch coverage gate for `packages/quality-mcp` (#3).
- Branch ladder simplified to `feature → test → main` (dropped the pass-through `dev` stage).
- Repo reset from its engine-source origin: README rewritten for this project, old
  quality-platform planning docs / assets / changelog cleared (preserved in git history).

---

> **Engine source.** This project began at commit `4425b53` (2026-08-08) as a duplicate of
> [`quality-platform`](https://github.com/Siddardth7/quality-platform) `@ v0.13.0`, reused as the
> tested deterministic core (FMEA, SPC, MSA, Control Plan engines). That project's own release
> history lives in its repository and in this repo's git history prior to the reset.

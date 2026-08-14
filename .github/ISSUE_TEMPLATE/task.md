---
name: Task Issue
about: Standard engineering task issue for milestone epics
title: '[E<#>] <title>'
labels: []
assignees: ''
---

> Before starting, review the contract in [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md) and execution guidelines in [Execution.md](Execution.md).

### Metadata
- **Epic**: [e.g. `[EPIC] FastMCP Server & Health Tool (#1)`]
- **Order / Dependencies**: [e.g. `Depends on #2`, `1 of 3 in Epic`]
- **Size**: [S | M | L | XL] (see [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md#sizing-legend-issue-fields--labels))
- **Complexity**: [low | med | high]
- **Priority**: [P0 | P1 | P2]

### User Story
As a Quality Engineer, I want to [action] so that [business outcome].

### Technical Scope & Engine Location
- Skill: `skills/[domain]/[skill-name]/SKILL.md`
- Engine: `packages/quality-core/src/quality_core/[module]/`
- MCP Tool: `packages/quality-mcp/src/quality_mcp/tools/[tool_name].py`
- CI Gate: new `--cov=quality_core.[module] --cov-fail-under=100` (or `quality_mcp.tools.[module]`) job added to `.github/workflows/ci.yml`, commented in the same style as the existing 8 gates — explain *why* this surface needs its own gate, not just that it does.

### Acceptance Criteria
- [ ] Python engine math verified with 100% branch test coverage, including negative controls.
- [ ] Any new standard-body constant/threshold cited in `apps/<domain>/docs/ASSUMPTIONS_LOG.md`, verified against the licensed manual — never against a web search.
- [ ] MCP tool binding registered and verified against an actual MCP client round-trip (Claude Code / Cursor), not just a unit test.
- [ ] Canvas component rendered (from `v0.2.0` onward) and round-trips at least one edit (N/A for headless / platform setup issues).
- [ ] Dedicated `--cov-fail-under=100` CI gate added to `.github/workflows/ci.yml` (if introducing a new engine or MCP tool surface).
- [ ] Repository passes all static analysis: `uv run ruff check .` and `uv run mypy`.
- [ ] `CHANGELOG.md` updated under `[Unreleased]` in the same PR.
- [ ] Conforms to all gates in [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md).

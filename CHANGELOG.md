# Changelog

All notable changes to **Engine-Powered Quality Engineering Skills** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions are milestone-driven, not date-driven — see [`ROADMAP.md`](ROADMAP.md).

## [Unreleased]

### Added
- FastMCP tool `calculate_spc_chart` in `quality_mcp.tools.spc` wrapping `quality_core.spc` deterministic engines for Shewhart variable (`Xbar-R`, `Xbar-S`, `I-MR`) and attribute (`p`, `c`, `u`) charts, run-rule detection (Western Electric 1–8 and Nelson), and strict stability-gated capability analysis (`Cp`, `Cpk`, `Pp`, `Ppk`) (#29).
- Re-export `calculate_spc_chart` in `quality_mcp.tools`, register on `quality-mcp` FastMCP server, and export in package root (#29).
- Comprehensive unit and integration test suite in `packages/quality-mcp/tests/test_spc_tool.py` verifying worked examples, run rules, error handling, and stability gate negative controls at 100% line & branch coverage (#29).

## [0.2.0] - 2026-08-15

### Added
- Milestone 2 (`v0.2.0`) specification document in `docs/milestones/v0.2.0.md` detailing Epics E1–E6, linking issues #16 through #21 with branch names, 7 release gate criteria, verification artifacts, and Milestone 3 readiness handoff (#21).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.2.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.2.0.md` (#21).
- Extended milestone governance test suite in `tests/test_milestones_convention.py` with comprehensive traceability, branch mapping, release gate, and artifact assertions for `v0.2.0` (#21).
- Minimal single-writer FMEA visual canvas architecture in `quality_core.canvas` (`FMEACanvasRow`, `FMEACanvas` controller with deterministic scoring via `quality_core.scoring`, benchmark sample loader, edit controller, and standalone/embedded HTML renderer with Quality Platform dark theme styling) (#20).
- `render_fmea_canvas` FastMCP tool in `quality_mcp.tools.canvas` exposing styled FMEA canvas HTML rendering and risk summary metrics over Model Context Protocol endpoints (#20).
- Comprehensive test suites in `packages/quality-core/tests/test_canvas.py` and `packages/quality-mcp/tests/test_canvas_tool.py` achieving 100% line & branch coverage across `quality_core.canvas` and `quality_mcp.tools.canvas` (#20).
- Extended CI Core coverage gate in `.github/workflows/ci.yml` to include `--cov=quality_core.canvas` at 100% enforcement (#20).
- AIAG & VDA (1st Edition, 2019) FMEA reviewer skill in `skills/fmea-reviewer/SKILL.md` defining qualitative 7-Step FMEA review methodology, failure chain analysis, and deterministic Action Priority scoring via `lookup_fmea_ap` on `quality-mcp` (#19).
- Updated `skills/README.md` taxonomy table marking `fmea-reviewer` skill as Active (#19).
- Governance test suite coverage in `tests/test_skills_conventions.py` asserting `lookup_fmea_ap` tool documentation, `quality-mcp` server reference, and AIAG Action Priority citations for `fmea-reviewer` (#19).
- In-process MCP client round-trip test suite in `packages/quality-mcp/tests/test_fmea_client_roundtrip.py` validating `lookup_fmea_ap` tool discovery, real-world automotive DFMEA/PFMEA dataset evaluation across 12 diverse failure modes spanning High, Medium, and Low Action Priority, dual structured and serialized text payload parity against `quality_core.scoring`, and protocol-level negative controls for out-of-range ratings, invalid types, and unknown tools (#18).
- Updated MCP client setup guide in `docs/mcp-client-setup.md` with test instructions for `test_fmea_client_roundtrip.py` and verified JSON-RPC 2.0 protocol transcripts for `lookup_fmea_ap` tool execution and validation error exchanges (#18).
- `lookup_fmea_ap` MCP tool (`quality_mcp.tools.fmea`) exposing AIAG-VDA 2019 Action Priority and RPN risk scoring over Model Context Protocol endpoints (#16).
- `quality_mcp.tools` package namespace re-exporting `lookup_fmea_ap` (#16).
- Comprehensive test suite in `packages/quality-mcp/tests/test_fmea_tool.py` verifying direct function execution, AIAG-VDA worked examples, boundary sweeps, negative mutation controls, FastMCP tool registration, and in-process client session round-trips (#16).

### Removed
- Legacy Streamlit apps (`apps/fmea`, `apps/spc`, `apps/msa`, `apps/controlplan`, `apps/secom`) and the unified shell (`shell/`, `app.py`) — this repo is skills + `quality-mcp` + `quality-core` only. Engines are extracted into `quality-core` per milestone from the source quality-platform repo (FMEA's AP scorer already lives in `quality_core.scoring`).
- Stale root `requirements.txt` (a `uv export` of the removed Streamlit chain) and the app import-boundary / cross-app boundary tests that only applied to the removed apps.

### Changed
- CI headless dependency guard and coverage gate comments in `.github/workflows/ci.yml` updated to document the headless containment contract and confirm 100% line & branch coverage scope for `quality_mcp.tools.*` under `--cov=quality_mcp --cov-fail-under=100` (#17).
- CI gate scoped to `quality-core` + `quality-mcp`: dropped the four app coverage gates (SPC / Control Plan / MSA / SECOM) and consolidated the four per-core-submodule gates into a single core run. Each suite now runs **once** instead of the core running 5× and the apps 2× — the source of the ~1h CI time. Also dropped the non-existent `dev` branch from the CI triggers.
- Workspace scoped to `packages/*`; `mypy.ini` now type-checks only `quality_core` + `quality_mcp` (23 files vs 67).

## [0.1.0] - 2026-08-14

### Added
- Milestone documentation conventions in `docs/milestones/README.md` and Milestone 1 (`v0.1.0`) specification index in `docs/milestones/v0.1.0.md` detailing Epics E1–E4, linking issues #1 through #7, release gate criteria, and verification artifacts (#7).
- Automated milestone governance test suite in `tests/test_milestones_convention.py` enforcing SemVer naming, structural section schema, issue URL traceability, and markdown link integrity (#7).
- Summary Release Matrix link update in `ROADMAP.md` pointing `v0.1.0` to `docs/milestones/v0.1.0.md` (#7).
- In-process MCP client-server round-trip test suite in `packages/quality-mcp/tests/test_client_roundtrip.py` verifying session initialization, tool discovery, structured `ping` execution, and protocol-level error handling (#4).
- Root workspace `.mcp.json` configuration registering `quality-mcp` for Claude Code, Cursor, and MCP-compliant AI hosts (#4).
- Client setup guide in `docs/mcp-client-setup.md` covering Claude Code/Cursor configuration, prerequisites, troubleshooting, and verified JSON-RPC protocol transcripts (#4).
- GitHub task issue template (`.github/ISSUE_TEMPLATE/task.md`), issue config disabling blank issues (`.github/ISSUE_TEMPLATE/config.yml`), and Definition of Done-enforcing PR template (`.github/pull_request_template.md`) (#5).
- Top-level `skills/` directory scaffold, `skills/README.md` conventions, canonical template `skills/_template/SKILL.md`, and diagnostic health check skill `skills/mcp-health/SKILL.md` adhering to the `agentskills.io` standard (#6).
- Governance test suite `tests/test_skills_conventions.py` asserting frontmatter validity, structural sections, and zero inline calculation logic across all skills (#6).
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

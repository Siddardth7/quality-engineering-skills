# 🏛️ Milestone Documentation & Governance

> **Document Version:** 1.0  
> **Status:** Canonical Governance Specification  
> **Authority:** `CLAUDE.md`, `Execution.md`, `ROADMAP.md`, `docs/DEFINITION_OF_DONE.md`  

---

## 1. Overview & Purpose

This directory (`docs/milestones/`) is the central repository governance hub for tracking and documenting release milestones across the **Engine-Powered Quality Engineering Skills** product ladder (`v0.1.0` through `v1.0.0`).

Per [`Execution.md`](../../Execution.md) and [`ROADMAP.md`](../../ROADMAP.md), project execution is **milestone- and issue-driven, not calendar-driven**. A milestone represents a cohesive, shippable product increment containing a defined set of **Epics** and **Task Issues**. A version is marked complete only when every issue in its milestone is closed, all CI gates are green at 100% line and branch coverage, and the milestone release gate criteria are verified.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MILESTONE LIFECYCLE                               │
│                                                                             │
│  [1. Specification] ──► [2. Parallel Issues] ──► [3. CI & Surface Gates]   │
│   docs/milestones/       Branch off test:        100% line + branch cov     │
│   vX.Y.Z.md              feat/<domain>-<slug>    Static analysis (0 errors) │
│                                  │                                          │
│                                  ▼                                          │
│  [6. Tagged Release] ◄── [5. SME Review] ◄─── [4. Release Gate Verification]│
│   git tag vX.Y.Z         Promote test -> main    Live client verification / │
│   Release record         Human sign-off          TRIAL_<name>_<date>.md     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. SemVer File Naming Convention

All milestone specification documents in this directory strictly adhere to Semantic Versioning file mapping:

$$\text{File Path} = \texttt{docs/milestones/vX.Y.Z.md}$$

Where:
- `X`: Major version (incremented on breaking architectural changes or completion of the full 8-domain platform at `v1.0.0`).
- `Y`: Minor version (incremented for each new wrapped engine or net-new quality domain).
- `Z`: Patch version (incremented for maintenance or critical hotfixes).

### Canonical File Mapping
| Version | Milestone Document | Theme / Domain | Status |
| :--- | :--- | :--- | :--- |
| `v0.1.0` | [`docs/milestones/v0.1.0.md`](v0.1.0.md) | Platform Setup & MCP Foundation | Complete |
| `v0.2.0` | [`docs/milestones/v0.2.0.md`](v0.2.0.md) | FMEA Engine via MCP & Single-Writer Canvas | Complete |
| `v0.3.0` | [`docs/milestones/v0.3.0.md`](v0.3.0.md) | SPC Engine via MCP & Stability Gate | Complete |
| `v0.4.0` | [`docs/milestones/v0.4.0.md`](v0.4.0.md) | MSA Engine via MCP & Gage R&R Interaction | Complete |
| `v0.5.0` | [`docs/milestones/v0.5.0.md`](v0.5.0.md) | Control Plan Engine via MCP (4-Engine Checkpoint) | Complete |
| `v0.6.0` | [`docs/milestones/v0.6.0.md`](v0.6.0.md) | RCA Suite (5-Why, Fishbone, Is/Is-Not) | Complete |
| `v0.7.0` | [`docs/milestones/v0.7.0.md`](v0.7.0.md) | NCR & COPQ Financial Estimator | Complete |
| `v0.8.0` | `docs/milestones/v0.8.0.md` | PPAP Core (18-Element AIAG Base Standard) | Planned |
| `v0.9.0` | [`docs/milestones/v0.9.0.md`](v0.9.0.md) | Supplier SCAR & Vendor Rating | Planned |
| `v1.0.0` | `docs/milestones/v1.0.0.md` | Production Hardening & Live-Formula Exporters | Planned |

---

## 3. Structural Schema for Milestone Documents

Every milestone document (`docs/milestones/vX.Y.Z.md`) MUST conform to the standardized structural schema with five mandatory top-level sections:

```markdown
# Milestone <N>: <Theme / Title> (vX.Y.Z)

## Overview
High-level summary of the milestone goals, architectural scope, and delivery objectives.

## Epics & Issues
Structured catalog of all Epics (E1, E2, etc.) and individual task issues.
Every issue MUST link to its canonical GitHub issue URL and specify:
- Issue Title and GitHub Issue ID
- Technical Scope (Engine, MCP Tool, Skill, CI Gate)
- Feature Branch (`feat/<domain>-<slug>-<#>` based on origin/test)
- Deliverable Summary & Acceptance Criteria Status

## Release Gate Criteria
The concrete, verifiable conditions required before the milestone can be closed and released.
Must include package verification, dependency contract, test suite status, and domain-specific live gates.

## Verification Artifacts & Test Evidence
Index of test files, CI workflow steps, transcripts, and trial logs validating the deliverables.

## Retrospective & Status
Summary of completion state, lessons learned, and readiness for subsequent milestone handoff.
```

---

## 4. GitHub Issue Traceability & Standards

Every milestone document maintains strict bidirectional traceability with GitHub issues:

1. **Canonical Issue URLs**: Issue references must use the full repository URL pattern:
   `https://github.com/Siddardth7/quality-engineering-skills/issues/<num>`
2. **Branch Ladder Alignment**:
   - Feature branches branch from `origin/test`.
   - Branch naming format: `feat/<domain>-<slug>-<issue#>` (e.g. `feat/scaffold-quality-mcp-1`).
   - PR targets `test` and must pass all CI gates before squash-merging.
3. **Definition of Done**: Every issue traces to [`docs/DEFINITION_OF_DONE.md`](../DEFINITION_OF_DONE.md) and requires:
   - 100% line and branch test coverage on touched engine and MCP surfaces.
   - Zero lint (`ruff check .`) or typing (`mypy`) errors.
   - Negative control tests demonstrating load-bearing test behavior.
   - Corresponding update in [`CHANGELOG.md`](../../CHANGELOG.md) under `[Unreleased]`.

---

## 5. Milestone Release Gate & Promotion Workflow

A milestone transitions to released status following these exact steps:

1. **All Milestone Issues Closed**: Every issue in the milestone is closed with its PR merged into `test`.
2. **CI Gates Green**: The full CI matrix (`.github/workflows/ci.yml`) passes with 100% line and branch coverage on all per-surface gates.
3. **Live Gate Verification**: Domain-specific live verification (e.g. real MCP client ping round-trip for `v0.1.0`, live single-writer canvas edit for `v0.2.0`) is satisfied and documented.
4. **Changelog Roll**: [`CHANGELOG.md`](../../CHANGELOG.md) is rolled from `[Unreleased]` to the version heading (e.g., `## [0.1.0] - YYYY-MM-DD`).
5. **Version Bump**: Root `pyproject.toml` and workspace member packages (`packages/quality-core`, `packages/quality-mcp`) versions bumped in synchronization.
6. **SME Sign-Off & Promotion**: The SME reviews the integrated state and promotes `test -> main`, creating the signed Git tag `vX.Y.Z`.

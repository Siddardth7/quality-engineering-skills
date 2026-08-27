# 🧭 Quality Engineering Skills Ecosystem

Welcome to the **Quality Engineering Skills** directory. This directory contains domain-specific AI Agent skill definitions formatted according to the [agentskills.io](https://agentskills.io) open standard.

Skills provide structured workflow methodology, standard operating procedure (SOP) guidance, problem decomposition frameworks, and qualitative reasoning heuristics for manufacturing quality engineering domains.

---

## 🏛️ Architectural Triad & The Core Rule

Every skill in this ecosystem operates strictly as the qualitative prompt layer of the **Product Triad**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THE PRODUCT TRIAD                              │
├───────────────────────┬────────────────────────┬───────────────────────┤
│   1. AI Agent Skills  │  2. FastMCP Tool Layer │  3. Deterministic Core │
│ • Markdown Guidance   │ • Standard Protocols   │ • Python Math Engines │
│ • agentskills.io      │ • quality-mcp Tools    │ • 100% Branch Coverage│
│ • ISO / AIAG / VDA SOP│ • Tool Signatures & I/O│ • Cited Standards     │
└───────────────────────┴────────────────────────┴───────────────────────┘
```

### ⛔ Strict Architectural Invariant: No Math in Skills

> **LLMs operating in prompt memory hallucinate engineering math.**
> 
> Skills must **NEVER** perform raw inline mathematical calculations, statistical formula evaluation, matrix scoring, control limit derivation, or capability indexing in prompt context.
> 
> All quantitative computations, formula evaluations, statistical tests, and scoring logic belong strictly in `packages/quality-core` engines and must be accessed exclusively through FastMCP tool bindings exposed by `packages/quality-mcp`.

Skills instruct agents **what** questions to ask, **how** to structure the domain workflow, **which** FastMCP tools to invoke with validated inputs, and **how** to interpret the deterministic engine responses.

---

## 📁 Directory Structure & File Convention

Every skill resides in its own isolated directory under `skills/` with a canonical entry point named `SKILL.md`:

```
skills/
├── README.md                      # Ecosystem documentation & taxonomy (this file)
├── _template/                     # Canonical skeleton template for new skills
│   └── SKILL.md
├── mcp-health/                    # Platform connectivity & diagnostic verification
│   └── SKILL.md
├── fmea-reviewer/                 # (v0.2.0) AIAG & VDA FMEA analysis & AP matrix
│   └── SKILL.md
├── spc-control-charts/            # (v0.3.0) Statistical Process Control & WE rules
│   └── SKILL.md
├── msa-gauge-rr/                  # (v0.4.0) Crossed Gage R&R (ANOVA & Xbar-R)
│   └── SKILL.md
├── control-plan/                  # (v0.5.0) AIAG Control Plan & PFMEA Linkage
│   └── SKILL.md
└── ...
```

### Isolation from Meta-Agent Skills
- `skills/`: Quality engineering domain skills exposed to agents (Claude Code, AGY CLI, Cursor) for manufacturing engineering workflows.
- `.claude/skills/`: Internal meta-agent research and engineering workflow pipelines (e.g. `hyperresearch`).

---

## 📄 agentskills.io Format Specification

Every `SKILL.md` must begin with YAML frontmatter delimited by `---` and contain all five mandatory markdown sections.

### Required YAML Frontmatter
```yaml
---
name: skill-name-slug
description: Precise, concise summary of the skill's capability, trigger conditions, and domain scope.
---
```

### Mandatory Markdown Heading Structure
1. `## Overview` — High-level summary of the engineering domain, purpose, and standard references (AIAG, ISO, VDA, IATF).
2. `## When to Use` — Explicit trigger scenarios, prerequisites, and input data requirements.
3. `## Step-by-Step Methodology` — Procedural decomposition, phase gates, investigative questions, and qualitative reasoning heuristics.
4. `## Tool Invocations` — Exact schemas, signatures, parameters, and invocation guidance for calling `packages/quality-mcp` tools.
5. `## Best Practices` — Engineering heuristics, domain-specific guardrails, common pitfalls, and strict prohibition of inline calculation bypass.

---

## 🗺️ Skills Taxonomy & Release Roadmap

The skill catalog maps directly to the releases defined in `ROADMAP.md`:

| Release | Skill Directory | Domain / Focus | Backing MCP Tool / Core Engine | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`v0.1.0`** | `_template` | Canonical Skill Skeleton | Reference Template | Active |
| **`v0.1.0`** | `mcp-health` | Diagnostic & Connectivity Verification | `quality_mcp.server.ping` | Active |
| **`v0.2.0`** | `fmea-reviewer` | AIAG & VDA FMEA Review & AP Matrix | `quality_mcp.tools.fmea` (`quality_core.scoring.ap_matrix`) | Active |
| **`v0.3.0`** | `spc-control-charts` | SPC Charts, WE Rules 1–8, Capability | `quality_mcp.tools.spc` (`quality_core.spc`) | Active |
| **`v0.4.0`** | `msa-gauge-rr` | Crossed Gage R&R (ANOVA & Xbar-R) | `quality_mcp.tools.msa` (`quality_core.msa`) | Active |
| **`v0.5.0`** | `control-plan` | Control Plan Validation & PFMEA Linkage | `quality_mcp.tools.controlplan` (`quality_core.controlplan`) | Active |
| **`v0.6.0`** | `5why-root-cause` | Reversible 5-Why Causal Logic | `quality_mcp.tools.rca` (`quality_core.rca`) | Active |
| **`v0.6.0`** | `fishbone-analysis` | 6M Ishikawa Categorization | `quality_mcp.tools.rca` (`quality_core.rca`) | Active |
| **`v0.6.0`** | `is-is-not-scoping` | Kepner-Tregoe Problem Boundary Scoping | `quality_mcp.tools.rca` (`quality_core.rca`) | Active |
| **`v0.7.0`** | `ncr-writing` | ISO 9001 §8.7 Defect Statement & Disposition | `quality_mcp.tools.ncr` (`quality_core.ncr`) | Active |
| **`v0.7.0`** | `copq-estimator` | ASQ CSSGB PAF Cost of Poor Quality Estimator | `quality_mcp.tools.copq` (`quality_core.copq`) | Active |
| **`v0.8.0`** | `ppap-checker` | AIAG PPAP 4th Ed. 18-Element Completeness | `quality_mcp.tools.ppap` (`quality_core.ppap`) | Active |
| **`v0.9.0`** | `supplier-scar` | Supplier Corrective Action & Vendor Scorecard | `quality_mcp.tools.sqe` (`quality_core.sqe`) | Planned |
| **`v1.0.0`** | *All Skills* | Production Hardening & Live Excel Exporters | Full Platform Integration | Planned |

---

## 🛠️ Authoring a New Skill

To author a new skill:
1. Duplicate `skills/_template/` to `skills/<your-skill-name>/`.
2. Update the YAML frontmatter (`name` matching directory name slug, clear `description`).
3. Fill out all five required heading sections.
4. Ensure all quantitative calculations are routed to `packages/quality-mcp` tools.
5. Run the convention governance test suite:
   ```bash
   uv run pytest tests/test_skills_conventions.py
   ```

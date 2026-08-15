# 🗺️ Product Roadmap: Engine-Powered Quality Engineering Skills

> **Document Version:** 3.0 — rescoped after peer review (see `Peer_Review_On_Execution_And_Roadmap.md`)
> **Target:** 10 releases, `v0.1.0` → `v1.0.0`
> **Pacing:** Milestone- and issue-driven, not calendar-driven. No day/date targets appear anywhere in this document on purpose — see "How pacing works" below.
> **Companion Document:** `Execution.md`, `Idea.md`, `Peer_review_On_Idea.md`, `Peer_Review_On_Execution_And_Roadmap.md`

---

## How pacing works

Each version below is a **GitHub Milestone**. Each milestone holds a fixed set of **Epics** (one per engine/domain), each Epic a set of **Issues** in the standard format from `Execution.md`. A version ships when every issue in its milestone is closed, its CI gates are green, and it's been promoted `test → main` and tagged per the repo's branch ladder — not when a date arrives. Throughput is a function of how many agents get spun up against a milestone's open issues in parallel, which is a per-milestone call, not a schedule.

---

## Release Philosophy

Every version ships:
1. Tested Python calculation engine additions (`packages/quality-core`, 100% branch coverage on the new surface, wired into `.github/workflows/ci.yml` as its own gate — same pattern as the 8 gates already there).
2. MCP tool bindings (`packages/quality-mcp`) exposing the new engine to Claude Code / Cursor / Codex.
3. Markdown skill guidance (`agentskills.io` format).
4. Standards citations for anything new, logged in that domain's `ASSUMPTIONS_LOG.md`, verified against the licensed manual — never against a web search (per `CLAUDE.md`).

> **Extraction model (2026-08):** this repo does **not** vendor the old Streamlit apps. Each engine is extracted from the source quality-platform repo into `packages/quality-core` at *its* milestone — not all at once. Some engines are already promoted (FMEA's AP scorer is `quality_core.scoring`; SPC primitives are `quality_core.spc`); others (MSA Gage R&R, the Control Plan connector) still live in the source repo's app packages and get extracted when their version comes up. This keeps the repo — and its CI — scoped to what the current milestone actually uses.

```
v0.1.0 ──► v0.2.0 ──► v0.3.0 ──► v0.4.0 ──► v0.5.0 ──► v0.6.0 ──► v0.7.0 ──► v0.8.0 ──► v0.9.0 ──► v1.0.0
Platform    FMEA        SPC         MSA      Control     RCA        NCR &      PPAP        Supplier    Production
Setup       via MCP     via MCP     via MCP  Plan         Suite      COPQ       Core        SCAR &      Hardening
& MCP                                        via MCP                           (base)      Vendor
Server                                                                                      Rating
```

**Scope decision this roadmap makes explicit (see rationale below the matrix):** the first 5 releases wrap the 4 engines that already exist and already carry 100% test coverage — that's a reuse win, not new math. The next 4 releases each add exactly **one new domain**, one per remaining category from `Idea.md`, chosen for high ROI *and* contained standards-citation risk rather than the highest-effort item in each category. Everything else from `Idea.md` — 8D, DMAIC, APQP/DVP&R, the full ISO 9001/IATF clause bank, VDA 6.3, Poka-Yoke, and every OEM-CSR overlay (Ford, GM, Stellantis, VW, BMW) — moves to a named **v2 backlog** at the bottom of this document. Nothing is deleted from the vision; it's sequenced honestly.

---

## Summary Release Matrix

| Version | Milestone Theme | Key Deliverables | Release Gate Criteria |
| :--- | :--- | :--- | :--- |
| [**`v0.1.0`**](docs/milestones/v0.1.0.md) | **Platform Setup & MCP Foundation** | `packages/quality-mcp` workspace member (FastMCP), CI dependency-contract check extended to cover it, GitHub milestone/epic/issue templates in place, one round-trip "hello world" MCP tool proven end-to-end with Claude Code/Cursor. | New package passes `uv sync --frozen` + CI; a trivial MCP tool call succeeds from an actual MCP client, not just a unit test. |
| [**`v0.2.0`**](docs/milestones/v0.2.0.md) | **FMEA Engine via MCP** | `lookup_fmea_ap` MCP tool wrapping the existing, already-tested AP matrix logic. Skill: `/fmea-reviewer`. Minimal single-writer canvas view (read + edit, no concurrent-lock machinery) introduced here as the reference pattern for later versions. | 100% coverage gate for the new `quality_mcp.tools.fmea` surface; skill + tool verified against a real FMEA dataset; canvas renders and round-trips one edit. |
| **`v0.3.0`** | **SPC Engine via MCP** | `calculate_spc_chart` MCP tool (control limits, WE rules 1–8, $C_p/C_{pk}/P_p/P_{pk}$ with stability gate). Skill: `/spc-control-charts`. Canvas: SPC control chart view reusing the v0.2 pattern. | Coverage gate on the new MCP surface; stability-gate behavior (blocks capability claims on out-of-control data) verified with a negative control. |
| **`v0.4.0`** | **MSA Engine via MCP** | `calculate_gage_rr` MCP tool (ANOVA + Xbar-R Gage R&R, %GRR/EV/AV/PV/ndc). Skill: `/msa-gauge-rr`. Canvas: Gage R&R interaction plot view. | Coverage gate on new MCP surface; ANOVA decomposition cross-checked against the MSA engine's test fixtures (extracted from the source quality-platform repo along with the engine). |
| **`v0.5.0`** | **Control Plan Engine via MCP** | `validate_control_plan` MCP tool (PFMEA linkage + schema validation). Skill: `/control-plan`. Canvas: Control Plan matrix view. **Checkpoint**: all 4 existing engines are now MCP- and canvas-accessible — this is the natural point to confirm the wrapping pattern is solid before starting net-new domains. | Coverage gate on new MCP surface; end-to-end smoke test exercising all 4 wrapped engines through one MCP client session. |
| **`v0.6.0`** | **RCA Suite** *(Category 2 pick)* | `quality_core.rca`: reversible 5-Why validator (checks causal logic both directions, rejects superficial "operator error"), 6M Fishbone categorizer, Kepner-Tregoe Is/Is-Not scoping matrix. Skills: `/5why-root-cause`, `/fishbone-analysis`, `/is-is-not-scoping`. | New coverage gate; 5-Why validator demonstrably rejects a circular/superficial chain in a negative-control test; Fishbone exports clean structured output. |
| **`v0.7.0`** | **NCR & COPQ Estimator** *(Category 5 pick)* | `quality_core.ncr`: converts raw defect notes into ISO 9001 §8.7 objective-evidence language, recommends disposition (Scrap/Rework/Use-As-Is/Return-to-Vendor). COPQ financial estimator (scrap cost, rework hours, sorting, warranty exposure). Skill: `/ncr-writing`. | New coverage gate; COPQ formulas cited in `ASSUMPTIONS_LOG.md`; disposition logic covered by negative controls (e.g., ambiguous defect data doesn't silently pick a disposition). |
| **`v0.8.0`** | **PPAP Core (base AIAG-VDA only)** *(Category 3 pick)* | `quality_core.ppap`: 18-element completeness auditor for Submission Levels 1–5, against the **base AIAG PPAP 4th Edition standard only** — no OEM CSR overlay yet (Ford/GM/Stellantis/VW/BMW variants are v2 backlog, see below). Skill: `/ppap-checker`. | New coverage gate; completeness auditor correctly flags missing elements per level against AIAG base rules, cited in `ASSUMPTIONS_LOG.md`. |
| **`v0.9.0`** | **Supplier SCAR & Vendor Rating** *(Category 4 pick)* | `quality_core.sqe`: SCAR generator, vendor scorecard (PPM, OTIF), threshold-triggered escalation. Skill: `/supplier-scar`. Chosen over the full ISO 9001/IATF clause bank or VDA 6.3 for this slot because it's mostly business-metric arithmetic (PPM/OTIF formulas), not a large standards-citation surface — lower risk to build before the pattern is fully proven. | New coverage gate; PPM/OTIF calculators verified against known worked examples; escalation trigger covered by a negative control. |
| **`v1.0.0`** | **Production Hardening & Release** | Excel exporters (`openpyxl`, live formulas, not hardcoded values) for all 8 domains now shipped; full `ASSUMPTIONS_LOG.md` audit across every new module; end-to-end regression pass across all 8 skills. Desktop packaging (PyInstaller), sha256 audit-hash stamping, and local-LLM support are **explicitly out of scope for this v1.0** — see v2 backlog. | All 8 domains pass their CI gates simultaneously; Excel exports verified to contain live formulas, not literals; full skill catalog smoke-tested end-to-end. |

---

## Why these 4 new domains, not the other 12

`Idea.md` lists 16 skills across 5 categories. This roadmap's `v0.6`–`v0.9` slots deliberately pick the **lowest standards-citation-risk, highest-daily-use item per category**, not the highest-effort one:

- **Category 2 (Problem Solving/RCA):** RCA Suite over the 8D state machine. 8D's D3→D4 containment gate and D7 PFMEA/Control-Plan loopback are a real state machine with real integration surface against the engines shipped in `v0.2`–`v0.5` — worth doing, but it's the highest-complexity item in the whole `Idea.md` list and shouldn't be the thing that tests whether the "new domain from scratch" pattern works.
- **Category 5 (Documentation):** NCR/COPQ over Poka-Yoke. You named NCR directly; it's also lower-effort and immediately useful on its own (every shop floor writes NCRs), where Poka-Yoke's value is mostly as an FMEA Detection-score modifier — more useful once FMEA integration patterns from `v0.2` are proven out.
- **Category 3 (Product Approval):** PPAP *base standard only* over full PPAP-with-OEM-overlay, APQP, or DVP&R. Every Tier 1/2 supplier needs base PPAP completeness checking regardless of which OEM they ship to — it's the highest-leverage single item in the category. The OEM CSR variance (Ford ∇, GM Run@Rate, VDA 6.3 Formel Q, BMW ASIL linkage) is real and valuable but is exactly the kind of citation-heavy, OEM-specific work that should wait until the base pattern from `v0.8` is proven.
- **Category 4 (Auditing):** Supplier SCAR over ISO 9001/IATF full clause audit or VDA 6.3. Both of the latter are large, citation-dense standards-text surfaces (the VDA 6.3 downgrade-rule logic alone was one of the most complex items identified in the hyperresearch report review). SCAR/vendor rating delivers real supplier-quality value with a much smaller citation surface, and it directly complements the PPAP work shipped one version earlier.

---

## v2 Backlog (explicitly deferred, not dropped)

- **8D Problem Solving State Machine** — full D0–D8 workflow, containment gates, D7 PFMEA/Control-Plan loopback.
- **DMAIC & Six Sigma Engine** — hypothesis-testing suite ($t$-test, ANOVA, Chi-square, regression) on CSV datasets.
- **APQP Timing & Gate Engine + DVP&R Test Plan Engine** — 5-phase critical-path solver and DFMEA-to-test-plan mapping.
- **ISO 9001 / IATF 16949 full clause audit engine** (§4–§10 question bank, Major/Minor/OFI scoring).
- **VDA 6.3 Process Audit Engine** — P1–P7 scoring, official downgrade rules, A/B/C classification.
- **OEM Customer-Specific Requirement overlays** for PPAP and FMEA — Ford CSR, GM 1927-03/Run@Rate, Stellantis S≥8 policy, VDA 6.3/Formel Q, BMW ASIL linkage. (Base PPAP from `v0.8.0` is the foundation these overlay onto.)
- **Poka-Yoke Evaluator** — detection-level rating, FMEA Detection-score modifier.
- **Full bi-directional canvas** — cell-level focus locking, RFC 6902 JSON-Patch concurrent AI+human sync, structural-mutation-safe stable row IDs. `v0.2.0` onward ships a *minimal single-writer* canvas as the interim step; true concurrent editing is a separate, harder problem worth its own design pass before being built.
- **Desktop packaging** — PyInstaller zero-dependency binary, dynamic port discovery, `runtime.json` handshake.
- **sha256 audit-hash execution logs, HITL sign-off metadata blocks** — the compliance-trail features an auditor would ultimately want; worth building once the core engines are stable rather than alongside them.
- **Local/offline LLM provider support** (Ollama, vLLM, LM Studio) for ITAR/air-gapped environments.
- **Q-DAS AQDEF / ISO 23952 QIF shop-floor metrology parsers** — high-volume CMM ingestion; valuable but orthogonal to proving the skill/engine/MCP pattern this roadmap is built around.

---

## Definition of Done for `v1.0.0`

`v1.0.0` ships when:
1. **8 engine-powered skills** are functional, documented, and tested: FMEA, SPC, MSA, Control Plan (wrapped) + RCA Suite, NCR/COPQ, PPAP Core, Supplier SCAR (new).
2. **`packages/quality-core`** maintains 100% branch coverage across all 8 domains' new/wrapped surfaces, each with its own CI gate in `.github/workflows/ci.yml`, in the same documented style as the 8 gates already there.
3. **`packages/quality-mcp`** exposes all 8 domains' tools to Claude Code, Cursor, and Codex.
4. **Minimal canvas** (single-writer, introduced in `v0.2.0`) renders and round-trips edits for all 8 domains.
5. **Excel exporter** produces live-formula workbooks (not hardcoded values) for all 8 domains.
6. Every new standards constant/threshold is cited in its domain's `ASSUMPTIONS_LOG.md`, verified against the licensed manual.

*Roadmap rescoped and authorized for implementation.*

# Hyperresearch Prompt — Quality Engineering Skills Platform

Paste the block below into Antigravity as the hyperresearch task prompt. It's self-contained (no prior conversation context assumed).

---

## Prompt

I'm building "Engine-Powered Quality Engineering Skills" — an AI agent skill platform for manufacturing quality engineers (FMEA, SPC, MSA, Control Plan, 8D/RCA, PPAP/APQP, ISO 9001/IATF 16949/VDA 6.3 auditing). It pairs AI Agent Skills (Claude Code / Cursor / Codex compatible, markdown-based) with deterministic, unit-tested Python calculation engines, exposed to agents via an MCP server, plus an optional local bi-directional web canvas (FastAPI + WebSocket) for viewing/editing control charts, FMEA grids, and audit scorecards. It's local-first: no cloud backend, works on local CSV/Excel/JSON files. The engine layer (`packages/quality-core`) and four of the apps (FMEA, SPC, MSA, Control Plan) already exist and are production-tested against AIAG-VDA/AIAG SPC/AIAG MSA standards with 100% branch coverage.

Research and report on the following, each as its own section with cited, dated sources:

1. **Competitive landscape.** What existing tools do manufacturing/automotive quality engineers actually use today for FMEA, SPC, MSA, 8D, PPAP, and internal auditing — both commercial (Minitab, ETQ, Plex/DELMIAworks, Sphera/IQS, Fusion QMS, APIS IQ-Software, Relyence, Ford's own internal tools, etc.) and open-source/free? For each, note: pricing model, whether it's desktop/cloud/local, and the single biggest complaint users voice in reviews, forums, or case studies. I specifically want to know whether "AI-assisted quality engineering" is already being sold by an incumbent, and if so, what it does differently from a prompt-plus-verified-engine architecture.

2. **AI-in-quality-engineering prior art.** Search for any existing projects, papers, or products that combine LLMs with deterministic statistical/quality engines (not just prompt-only AI quality tools). Include the specific repo this project is inspired by — github.com/RBraga01/Quality-Engineering-Skills — and characterize exactly what it does and does not do (I believe it's markdown-only prompt skills with no code execution — confirm or correct this). Also search for "Model Context Protocol" + manufacturing, quality, or SPC to see if anyone has already built an MCP server in this space.

3. **OEM-specific requirement variance.** For PPAP and FMEA specifically, how much do the "big 5" automotive OEM customer-specific requirements (Ford CSR, GM IATF supplement, Stellantis, VW Group/VDA, BMW) actually diverge from the base AIAG-VDA/AIAG PPAP standard? I need a practical prioritization: which single OEM's variant, if built first, would cover the largest share of a typical Tier 1/Tier 2 supplier's submissions? Cite supplier-quality forums, IATF/AIAG official guidance, or published comparison tables if they exist.

4. **MCP tool-registry and distribution norms.** How do developers currently register and distribute domain-specific MCP servers so they're discoverable by Claude Code, Cursor, and other MCP-compatible clients? Is there a de facto registry, marketplace, or convention (naming, manifest format, versioning) as of 2026? What are common pitfalls people report when shipping a local-first MCP server that also needs a companion local web UI (auth model, port conflicts, packaging for non-technical users)?

5. **Local bi-directional canvas UX precedent.** Look for existing patterns (not necessarily quality-specific) where an AI chat agent and a local browser-based visual canvas stay in live two-way sync over the same session state — e.g., Jupyter widgets, Streamlit's session_state model, Observable notebooks, or newer "AI canvas" products (ChatGPT canvas, Claude artifacts with live capabilities). Specifically: how do these systems handle the human editing a value in the UI at the same moment the AI is mid-write to the same state (conflict resolution)? I need concrete architectural patterns, not just feature lists.

6. **Export/interchange expectations.** For a tool targeting quality engineers who must produce audit-ready deliverables, what file formats and interchange standards are non-negotiable (Excel with formulas intact, PDF for PSW/8D reports, specific IATF/AIAG-VDA template layouts)? Are there existing open templates I should conform export output to, rather than inventing my own layout?

7. **Shop-floor data interchange & CMM integration.** What are the de facto file formats and protocols used by shop-floor measuring equipment (Coordinate Measuring Machines / CMMs, PLC loggers, optical gages) to output raw SPC data into quality software? Research the adoption of Q-DAS AQDEF (Automotive Quality Data Exchange Format), QIF (Quality Information Framework), and standard CSV/Excel structures. What formatting expectations do quality engineers have when importing 100,000+ row measurement datasets into an SPC/Capability engine?

8. **Auditor acceptance & validation audit trail.** Have major certification bodies (TÜV, DNV, BSI, DEKRA) or IATF/AIAG published any formal stance or guidance regarding AI-assisted quality documentation (AI-assisted 8Ds, FMEAs, Control Plans)? What specific audit trail or verification mechanism (e.g. human-in-the-loop sign-off, deterministic math verification log) is required for an auditor to accept a quality deliverable generated with AI assistance?

9. **Intellectual property & on-premises LLM requirements.** What data governance and IP protection requirements do automotive OEMs and defense/aerospace suppliers enforce regarding quality data (which contains proprietary part dimensions, defect rates, and process parameters)? Are manufacturing quality teams permitted to use commercial cloud APIs (OpenAI, Anthropic) under Zero Data Retention (ZDR) agreements, or is support for local LLM runners (Ollama, vLLM, LMStudio) mandatory for enterprise adoption?

10. **Legacy RPN to 2019 Action Priority (AP) migration.** What are the documented industry friction points as Tier 1 and Tier 2 suppliers migrate legacy 4th Edition FMEAs (scored with Severity × Occurrence × Detection = RPN) to the 2019 AIAG-VDA 7-Step Action Priority (AP) matrix? Is there demand for an automated engine that ingests legacy RPN FMEAs and maps them into AIAG-VDA 2019 AP structures?

For each section, flag explicitly where sources disagree or where you found no reliable source — do not paper over gaps. Do not attempt to verify or quote exact AIAG/ISO/VDA standard text, thresholds, or numeric tables from web sources — that verification will be done separately against the licensed reference manual; for this research, treat any standard-body numeric claims you find online as unverified pointers only, and say so.

---

## Notes for whoever runs this (not part of the prompt above)

- This complements a written peer review at `Peer_review_On_Idea.md` — that review covers internal architecture gaps (MVP scope, conflict resolution, versioning policy, effort estimates); this prompt covers external/market unknowns the review can't answer from the repo alone.
- Sections 1–4 map directly to the "Questions & Discussion Points" in `Idea.md`. Sections 5–6 are additions surfaced during peer review (canvas conflict-resolution precedent, export format expectations).
- Once the report comes back, fold findings + the peer review into a revised `Idea.md` (or a new `SPEC.md`) before anything goes to `/ship`.

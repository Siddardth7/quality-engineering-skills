# Peer Review on Idea.md

> **Reviewer:** Claude (Sonnet 5), acting as secondary/peer reviewer
> **Reviewed doc:** `Idea.md` v1.0
> **Method:** Read against the actual repo state (`pyproject.toml`, `apps/`, `packages/quality-core`, `CLAUDE.md`) rather than the doc in isolation
> **Verdict:** Strong domain framing, real reuse opportunity — but the doc is a vision statement, not yet a buildable spec. Scope, sequencing, and a few architectural decisions need to be pinned down before this goes to `/ship`.

---

## What's grounded and real

- **The engine reuse story checks out.** This repo (`pyproject.toml` name `quality-platform`, version `0.13.0`) already *is* `apps/fmea`, `apps/spc`, `apps/msa`, `apps/controlplan`, `apps/secom` over `packages/quality-core`, with a 100%-branch-coverage gate per surface and an existing standards-fidelity discipline (`ASSUMPTIONS_LOG.md`, `CITATIONS.tsv`). Idea.md's Phase 1 ("refactor FMEA/SPC/MSA/Control Plan to Python+MCP") is mostly *wrapping*, not building — that's the right thing to make Phase 1.
- **The engine/prompt boundary is the correct kill shot on the RBraga01-style gap.** LLMs hallucinating $C_{pk}$ or AP ratings is a real, documented failure mode; routing math through tested `quality-core` functions instead of prompt arithmetic is the right architectural bet.
- **The standards-fidelity bar this org already enforces is an asset, not a constraint.** CLAUDE.md already bans web-search verification of AIAG/ISO quotations and requires every constant cited in `ASSUMPTIONS_LOG.md`. Idea.md doesn't restate this, but it should — because everything in Category 4 (ISO 9001, VDA 6.3) lives or dies on it.

---

## Gaps that need answers before Phase 1 starts

### 1. Relationship to the source repo is undefined
`git log` shows this repo was created via `chore: duplicate quality-platform @ v0.13.0 as the engine source` — this is a **vendored snapshot**, not a fork with a sync strategy. Idea.md never says whether `quality-engineering-skills` tracks upstream `quality-platform` fixes going forward, diverges permanently, or re-vendors periodically. If upstream fixes a Cp/Cpk bug post-fork, does it silently rot here? This needs one sentence of policy, not architecture — but it's currently zero sentences.

### 2. No MVP, no user
The doc goes straight from problem statement to a 4-layer architecture and a 16-engine index. There's no persona ("a single QE at a Tier 1 supplier doing PPAP submissions"), no single end-to-end user journey, and no explicit "smallest version that's useful." That makes the roadmap read as feature-complete-or-nothing. Recommend: pick *one* skill (FMEA is already implemented and lowest-risk) and define one paragraph of "a QE opens the canvas, edits a severity rating, sees AP recalc, asks the AI why it changed" as the walking skeleton before touching the other 15.

### 3. Effort estimates don't match the org's own quality bar
"High effort, 14 days" for the VDA 6.3 audit engine or PPAP 18-element engine undercounts the cost this repo's own CLAUDE.md imposes: 100%-branch-coverage tests, cited AIAG/VDA constants in an assumptions log, negative-control mutation testing per the pipeline's hard-won rules. Category 4 items (ISO/IATF/VDA 6.3, OEM-specific PPAP rules across Ford/GM/Stellantis/VW/BMW) are each independently citation-heavy and should be budgeted as multi-week, one-OEM-at-a-time efforts, not folded into a single 14-day gantt bar.

### 4. Bi-directional canvas has no conflict-resolution model
Section "Bi-Directional Traffic Flow" describes AI-writes and human-edits both mutating the same session JSON, but never says what happens when they race — human edits a spec limit in the browser while the AI is mid-recalculation from a skill run. This is the single most architecturally novel piece of the whole doc (everything else is CRUD over existing engines) and it's the least specified. It deserves its own mini-spec: single writer with a lock, optimistic concurrency with version stamps, or last-write-wins with a visible conflict banner.

### 5. No versioning story for the standards themselves
AIAG-VDA, VDA 6.3, and ISO 9001/IATF 16949 all get periodic revisions (the doc even names "VDA 6.3 (2023 4th Ed)" and "APQP 3rd Ed (2024)"). If a future revision changes an AP table or a downgrade rule, does the engine version the standard, or does an update silently reinterpret historical FMEAs? `quality-core`'s existing `ASSUMPTIONS_LOG.md` pattern implies "one version pinned," but Idea.md doesn't say whether multi-version support is in scope.

### 6. MCP/canvas security and auth is unaddressed
`localhost:8000` is called out as local-first (good), but an MCP server that an AI agent calls with tool-execution privileges, paired with a WebSocket-connected browser canvas, is still a local attack surface (e.g., a malicious webpage in another tab hitting `localhost:8000` via CSRF, or a compromised skill prompt driving the MCP server to overwrite session state). Even a one-line "canvas binds to loopback only, no auth token" decision should be explicit rather than implied by "local-first."

### 7. Roadmap sequencing buries the reuse advantage
Phase 1 correctly leads with already-built engines, but then Phase 2/3 commit to *net-new* domains (8D state machine, PPAP, VDA 6.3) at the same cadence as Phase 1's wrapping work, without acknowledging that Phase 2/3 have zero existing code or tests to lean on. Recommend re-cutting the roadmap so "wrap existing engine" phases and "build new engine from scratch" phases are visibly different categories of work with different confidence in the estimates.

---

## Smaller notes

- The doc's own "Questions & Discussion Points" section (OEM priority, canvas export formats, MCP registry) are good questions — they're exactly what should go to research (see the paired hyperresearch prompt) rather than being decided inline.
- Consider whether `RCA`/`8D`/`DMAIC` (Category 2) — none of which exist in the current `apps/` — are better sequenced *after* Category 4's compliance/audit engines validate the "new domain from scratch, standards-fidelity-first" workflow once on a smaller surface (e.g., the Low-effort "Is/Is-Not Scoping Engine") before attempting the High-effort 8D state machine.
- `CLAUDE.md` currently pins workspace version `0.7.0` while `pyproject.toml` says `0.13.0` — unrelated to Idea.md directly, but worth a one-line fix so future agents don't inherit a stale fact.

---

## Bottom line

Ship Phase 1 as scoped (it's low-risk, high-reuse). Before committing to Phase 2/3 as a fixed 12-week plan, resolve: source-repo relationship, one MVP user journey, realistic per-OEM/per-standard effort, a named conflict-resolution strategy for the canvas, and a standards-versioning policy. None of these invalidate the architecture — they're the difference between a vision doc and a spec `/ship` can execute against.

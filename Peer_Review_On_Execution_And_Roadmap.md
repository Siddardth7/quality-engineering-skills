# Peer Review on Execution.md & ROADMAP.md

> **Reviewer:** Claude (Sonnet 5)
> **Reviewed:** `Execution.md` v1.0, `ROADMAP.md` v2.0 (both written by Antigravity against a 90-day timeline)
> **Method:** Checked both docs against the actual repo — `.github/workflows/ci.yml`, `.claude/agents/*.md`, `.claude/commands/*.md`, `CLAUDE.md`'s branch ladder, and `packages/quality-core/pyproject.toml` — not read in isolation.
> **Context this review responds to:** you want to compress the timeline from the 90 days Antigravity planned against down to a **45-day sprint, 10 releases, roughly one every 4–5 days, v0.1.0 → v1.0.0**. That's the headline issue this review has to address, so it leads.

---

## Headline: the 90-day scope doesn't fit in 45 days — it doesn't cleanly fit in 90 either

My earlier review of `Idea.md` already flagged that Category 4 (PPAP, APQP, ISO 9001/IATF, VDA 6.3) and Category 2 (8D, RCA) items were budgeted at "Medium/High effort, 7–14 days" in a way that undercounted this repo's own quality bar — 100%-branch-coverage tests, cited AIAG/VDA constants, negative-control mutation testing per the ship pipeline's hard-won rules. `Execution.md` and `ROADMAP.md` inherited that same per-domain budget almost unchanged (8D: 10 days, RCA+Fishbone+Is/Is-Not: 10 days, PPAP: 10 days, APQP+DVP&R: 7 days, ISO/IATF: 5 days, VDA6.3+SCAR: 3 days) and built a 90-day plan on top of it. Halving the calendar to 45 days without cutting scope means every one of those already-tight windows gets cut in half again — VDA 6.3's official downgrade rules and *-question gating, or the ISO 9001/IATF clause-by-clause question bank, in 1.5–2 days each, including citation research against the licensed manual, is not achievable.

Concretely, walking the existing 90-day roadmap's own day-counts:
- Phase 1 (MCP server + canvas + metrology ingestion, wrapping 4 *already-built and tested* engines) = 25 days.
- Phase 2 (8D + RCA/Fishbone + NCR/COPQ, all **net-new** domains) = 30 days.
- Phase 3 (PPAP + APQP + ISO/IATF + VDA 6.3 + SQE, all **net-new** domains) = 25 days.
- Phase 4 (packaging, sha256 audit hashing, Excel exporters, release) = 10 days.

Phase 1 alone — the *reuse-heavy, lowest-risk* phase — already consumes more than half of a 45-day budget. There is no honest way to fit Phases 2 and 3 (8 net-new standards-fidelity-heavy domains) into whatever's left. **The choice isn't "how do we compress this plan," it's "what do we cut."**

---

## Gaps found by checking the docs against the actual repo

### 1. The ship pipeline description is missing a stage
`Execution.md` describes a **3-stage** pipeline: `research → coder → tester`. The actual repo (`.claude/agents/`, `CLAUDE.md`) runs **4 stages**: `research → coder → tester → reviewer`, and CLAUDE.md is explicit that the reviewer's read-only tool restriction "*is* the review gate; without it the gate is theatre." Dropping the reviewer stage from the execution doc isn't a cosmetic omission — if whoever runs this literally follows `Execution.md`'s pipeline description, every PR ships without the one stage this repo's own rules call load-bearing.

### 2. The branch ladder and release mechanics are wrong
`Execution.md` says: *"Protected Main Branch: Direct pushes to main are blocked"* and describes feature branches merging via PR, full stop. The actual repo runs a 4-stage ladder — `feature → test → dev → main → production` — with an explicit, named rule: **"Never merge or push to test, dev, or main. Sid is the final gate."** `/ship` only ever opens a PR into `test`; getting a version from there to a tagged `main` release requires two more human-gated steps (`/promote` test→dev, `/release` dev→main+tag), each of which needs *you* to personally review and act.

This matters directly for your "one release every 4–5 days" target: that cadence isn't just an agent-throughput question, it's a **you-availability** question. If a version's code is ship-ready on day 4 but you don't run `/promote` and `/release` until day 7, the version ships on day 7, not day 4. Neither doc's release table budgets any time for this, and it should — either by naming the promotion cadence as your commitment, or by explicitly treating `v0.x.0` as "code-complete and PR'd into `test`" (agent-controlled) separately from "tagged on `main`" (Sid-controlled), so a slip in your review time doesn't silently blow the whole roadmap.

### 3. New CI coverage gates aren't budgeted as tasks anywhere
The current `.github/workflows/ci.yml` hand-wires **8 separate `--cov-fail-under=100` gates** (4 core modules + SPC + Control Plan + MSA + SECOM), each added deliberately with a comment explaining why. `Execution.md`/`ROADMAP.md` plan **8 more net-new modules** (`eight_d`, `rca`, `ncr`, `ppap`, `apqp`, `audit`, `vda63`, `sqe`) plus a whole new `packages/quality-mcp` package — none of which appear as a CI-wiring task in either doc. Someone has to hand-edit `ci.yml` for every one of these, in the same style as the existing gates (with the same "why this gate, why 100%, what's excluded" commentary CLAUDE.md's own gates demonstrate). That's real, repeatable work per version, currently invisible in both plans.

### 4. `packages/quality-mcp` doesn't exist yet, and `FastMCP` isn't a dependency
`Execution.md` Task 1.4 says "Initialize `packages/quality-mcp` using `FastMCP`" as if it's a small item inside Day 6–15. Checked: `fastmcp` isn't in `uv.lock` today, and CI's "Core dependency contract" job specifically fails the build if a Streamlit-chain package leaks into `quality-core`'s resolved subtree — meaning whoever adds `quality-mcp` to the workspace needs to be careful it doesn't accidentally get pulled into that dependency contract, and the contract check itself may need extending to cover the new package. This is a one-line task in the doc; in practice it's "stand up a new workspace member, get its dependency tree past the same contract gate as everything else, prove it in CI" — a half-day to a day of real work, not zero.

### 5. Task 1.2 is already done
Execution.md Task 1.2: *"Isolate `packages/quality-core` into an autonomous, editable Python library with `pyproject.toml`."* Checked: `packages/quality-core/pyproject.toml` already exists, already declares `quality-core` as its own package with its own dependency list, and is already a `uv` workspace member independent of the apps. This task is zero-effort — it's a reminder that both docs were written against the *idea* of this repo rather than a fresh read of its current state, which is exactly the same failure mode my `Idea.md` review flagged for the source-repo relationship. It's a small thing on its own, but it's evidence worth weighing when trusting the rest of the day-counts.

### 6. The bi-directional canvas conflict-resolution model appears — with zero design discussion
To their credit, both docs got more specific than `Idea.md`: "field-level cell focus locks... <30ms latency... RFC 6902 JSON-Patch." That's a real answer to the gap my first review flagged. But it appears fully-formed with no discussion of *why* cell-locking was chosen over CRDTs/OT, no mention of the structural-mutation edge case (row insert/delete while a lock is held), and it's treated as a Day 16–25 sub-task inside Phase 1 alongside three other substantial features (FastAPI server, Plotly renderers, AQDEF parser). This is still the single most architecturally novel piece of the whole system and it's sized like a checkbox.

---

## What to actually do with 45 days

Don't try to save the 90-day scope by compressing it. **Cut it.** Here's a scope that's honest about what 45 days can hold, sequenced to hit a real release roughly every 4–5 days:

**Keep in the 45-day v1.0:**
- MCP server wrapping the 4 *already-tested* engines (SPC, FMEA, MSA, Control Plan) — genuinely fast, since the math and coverage already exist. This is Phase 1's actual reuse win; it doesn't need 25 days.
- A **minimal** canvas: read + single-writer edit (either the human *or* the AI is the sole writer for a given session, not concurrent), no cell-lock/CRDT machinery yet. Ship the visual/sync value now; defer true concurrent-edit conflict resolution to a v1.1+ backlog item, since it's unproven and high-risk on a compressed clock.
- **One** net-new domain, chosen as a proof-of-pattern, not the highest-value one — my `Idea.md` review already suggested the Is/Is-Not Scoping Engine (Low effort, no OEM-CSR variance, no downgrade-rule complexity) as the right pilot for "how do we do a new standards-fidelity domain end-to-end, with CI gate, citation log, and all" before betting a compressed sprint on something like VDA 6.3.
- Packaging and exporters *scoped down*: skip PyInstaller/desktop binary and sha256 audit-hash infrastructure for v1.0; ship as a `uv run` local dev tool. Desktop packaging is a real but separable milestone, not a blocker for proving the core architecture.

**Move out of the 45-day window entirely, into a named v2 backlog:**
- 8D state machine, full RCA/Fishbone suite, NCR/COPQ, PPAP (any OEM), APQP/DVP&R, ISO 9001/IATF audit engine, VDA 6.3, SQE/SCAR. All eight of these are legitimate, but each is independently a multi-day, standards-fidelity-heavy build under this repo's own bar — bundling all eight into a 45-day window guarantees either the deadline slips or the coverage/citation discipline gets quietly skipped, and the second outcome is the one this repo's CLAUDE.md exists specifically to prevent.

**Version numbering — resolve one ambiguity before locking the roadmap:** you said "10 versions, v0.1 to v1.2" in one pass and "45-day sprint" in the next; those two don't reconcile on their own (v0.1.0→v1.0.0 is 10 stops at even spacing; reaching v1.2.0 needs 12). I'd default to **v0.1.0 → v1.0.0, 10 releases, ~4.5 days apart**, treating v1.0.0 as "core platform + 4 wrapped engines + 1 new-domain pilot + minimal canvas" rather than the full 18-skill vision — but say the word if you actually meant to reserve v1.1/v1.2 as two extra post-launch versions inside the 45 days, since that changes the per-version day budget.

---

## Bottom line

Both documents are well-structured and internally consistent — the problem isn't how they're written, it's that they're the 90-day plan with a shorter deadline stapled on, and the 90-day plan itself was already flagged as optimistic for its own scope. If you want a real 45-day, 10-release cadence, the fix is scope reduction (4 wrapped engines + minimal canvas + 1 new-domain pilot = v1.0), not faster execution of the same 18-skill plan. I can rewrite `Execution.md` and `ROADMAP.md` to this reduced scope next, once you confirm the version-numbering question above.

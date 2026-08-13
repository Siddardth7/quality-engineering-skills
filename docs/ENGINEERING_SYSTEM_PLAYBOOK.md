# Engineering System Playbook

**What this is:** the working system for building **Engine-Powered Quality Engineering Skills** —
how every issue is worked, the review/coverage loop, CI, branching, releases, and the documentation
set. A **uv workspace monorepo** with **per-surface coverage gates** (not a single repo-wide floor).

**Reading order for someone new:** §1 (mental model) → [`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md)
(the contract — read it first) → [`../Execution.md`](../Execution.md) (how milestones/issues/pipeline
run) → §6 (repo scaffold) → then work issues per §4. The plan itself lives in
[`../ROADMAP.md`](../ROADMAP.md) and the vision in [`../Idea.md`](../Idea.md).

> **Relationship to `Execution.md`:** Execution.md is the *project-specific plan* (which versions,
> which domains, the ship pipeline, branch discipline). This playbook is the *general engineering
> discipline* those issues are worked under — the coverage ratchet, the per-issue Definition of Done
> loop, the separate-tester rule, and the doc taxonomy. They complement each other; where they overlap
> on process mechanics, they must agree, and CLAUDE.md is the final tie-breaker.

---

## 1. The mental model (four ideas)

1. **One issue = one change = one PR = one CHANGELOG entry.** The smallest shippable unit. No "and
   while I was in there" changes. Every branch, commit, and changelog line traces to an issue number.

2. **The Definition of Done is a contract, written once, referenced everywhere.** It lives in
   [`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md) and is mirrored as a **pinned issue**. Issue
   bodies link to it; they don't re-explain the gates.

3. **Coverage is a ratchet, never a wish.** Hard `--cov-fail-under` gates in CI, on **line AND
   branch**. Floors only move up. New code is held to 100%. This is the *learning loop*: write test →
   run coverage → fill the gap → repeat — and you are **not allowed to start the next issue** until
   the touched surface meets its gate.

4. **Small slices ship dark.** Land the deterministic/plumbing layer (tested) before the feature that
   drives it. Releases are deliberately small — 10 versions, `v0.1.0` → `v1.0.0` — so quality never
   drops from cramming.

> These matched the engine source before it was written down (per-milestone versions, one-issue
> commits, self-covered shared surfaces). The playbook names the parts that are easy to lose under
> agent throughput: branch coverage, the DoD as a pinned artifact, PR-per-issue, and the doc taxonomy.

---

## 2. The whole loop, end to end

```
   ROADMAP → MILESTONE (a version) → ISSUE → BRANCH → IMPLEMENT
                                         │
                                         ▼
     ┌──── per-issue Definition of Done gates (in order) ─────────┐
     │ 1. implement (lazy/minimal, ponytail)                      │
     │ 2. dedicated tester writes/extends the suite               │
     │ 3. COVERAGE LEARNING LOOP  ← hard stop, per-surface, +branch│
     │ 4. reviewer (read-only) → correctness verdict              │
     │ 5. /ponytail-review on the diff → delete speculative code  │
     │ 6. green suite + ruff + mypy + CHANGELOG [Unreleased] entry │
     │ 7. PR into `test` → CI gate green → squash-merge → close    │
     └────────────────────────────────────────────────────────────┘
                                         │
                   (milestone complete)  ▼
     PER-VERSION gates → roll CHANGELOG → bump version →
     (ratchet a floor if earned) → SME reviews → tag `test → main`
```

The per-issue gates are the heart of it — specified in [`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md)
and executed by the ship pipeline (`research → coder → tester → reviewer`, see §9 and `Execution.md`).

---

## 3. What makes this repo's coverage stance strict

| Topic | Convention |
|---|---|
| Layout | **uv workspace monorepo**: `packages/quality-core` + `packages/quality-mcp` + `apps/{fmea,spc,msa,controlplan,secom}` |
| Coverage gate | **per-surface** `--cov-fail-under=100` gates in CI (not one repo-wide floor) — stricter for a monorepo, so a weak module can't hide behind a strong one |
| Branch coverage | `branch = true` in `[tool.coverage.run]` — every gate reads it |
| Test import mode | `--import-mode=importlib` → shared fixtures in `conftest.py`, not sibling imports |
| DoD pin | a dedicated **pinned issue** links every issue body to the contract |
| Version SSOT | root `pyproject.toml` **and** each package's `pyproject.toml` (`quality-core`, `quality-mcp`) |
| Core dependency contract | CI fails if a UI-chain dependency (Streamlit et al.) resolves into `quality-core` — the shared core stays UI-free |

---

## 4. Working a single issue (day-to-day)

**Before code:** read [`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md) + the issue body — that's the
full context by design. If you need more, the issue is under-specified; fix the issue first. Confirm
it's on the current milestone with Size/Complexity/Priority.

**Branch** (one per issue, **off `origin/test`**): `feat|fix|chore|docs/<domain>-<slug>` (e.g.
`feat/rca-5why-validator`). Put the issue number in the commit subject, per CLAUDE.md.

**The coverage learning loop in practice:**
```bash
uv run pytest packages/quality-core --cov=quality_core.io --cov-report=term-missing   # or the surface you touched
# read the Missing column → write the test that hits the red line/branch → repeat until the floor is met
uv run ruff check . && uv run mypy
```
`show_missing = true` prints the worklist. Do not move on while the loop is red.

**Commit + PR:** conventional commits with the issue number in the subject (`feat(core): … (#35)`);
squash-merge; PR body quotes the coverage/pytest evidence; CHANGELOG entry in the same PR; CI green
required; PR targets `test`, never `main`.

---

## 5. Coverage system (the ratchet, in detail)

Config in the root `pyproject.toml`:
```toml
[tool.coverage.run]
branch = true            # mandatory — catches the missing else a 100%-line file hides

[tool.coverage.report]
show_missing = true      # uncovered lines/branches become an actionable worklist
```
The floors are enforced as **separate CI steps** (`--cov-fail-under=100`) per surface, so a weak
module can't hide behind a strong one. The authoritative list of gates is in
[`../.github/workflows/ci.yml`](../.github/workflows/ci.yml) and the table in
[`../CLAUDE.md`](../CLAUDE.md); today they are, each at **100% (line + branch)**:

- `quality_core.io`, `quality_core.schema`, `quality_core.scoring`, `quality_core.spc` (four core gates)
- the SPC, Control Plan, MSA, and SECOM app surfaces (Streamlit `pages/` and entry scripts excluded — they need a runtime)

**Every new engine module added in `v0.6`–`v0.9` (`rca`, `ncr`, `ppap`, `sqe`) and every new MCP tool
surface ships with its own gate**, added to `ci.yml` in the same commented style — this is an explicit
acceptance-criteria item on each issue, not an afterthought.

Rules that make it work: **branch coverage is non-negotiable**; **the number only goes up**; **new
modules held to 100%**; **accuracy ≠ coverage** — for standards/AI correctness keep a scorecard against
the **licensed reference manual** (never a web search), tracked like coverage and cited in the
domain's `ASSUMPTIONS_LOG.md`.

---

## 6. Repo scaffold (the files that *are* the system)

```
.
├── README.md                      # front door → links to Idea/Roadmap/Execution
├── Idea.md                        # vision + architecture + full skill/engine index
├── ROADMAP.md                     # canonical plan: 10-release ladder + v2 backlog
├── Execution.md                   # milestones, issues, ship pipeline, branch discipline
├── CHANGELOG.md                   # Keep a Changelog; [Unreleased] on top, entry per PR
├── CLAUDE.md                      # operating rules (final tie-breaker on process)
├── pyproject.toml                 # workspace + pytest + coverage ratchet (branch=true)
├── .github/workflows/ci.yml       # ruff → mypy → pytest → per-surface coverage gates
├── docs/
│   ├── DEFINITION_OF_DONE.md      # the contract → pinned issue
│   └── ENGINEERING_SYSTEM_PLAYBOOK.md   # this file
├── packages/
│   ├── quality-core/              # shared engines (schema, io, scoring, spc, …) — new modules held to 100%
│   └── quality-mcp/               # MCP tool bindings (v0.1.0+)
├── apps/{fmea,spc,msa,controlplan,secom}/   # the tested engine source (full history preserved)
└── skills/                        # agentskills.io markdown skills (added per version)
```

**CI** runs the gate on push + PR to `test` and `main` with a concurrency guard. The coverage floors
are separate CI steps (not one `fail_under`) because the monorepo has multiple surfaces with their own
bars. Keep actions on non-deprecated versions.

---

## 7. Documentation taxonomy (the part most projects miss)

Distinct **kinds** of docs, each with a job. Date-stamp the point-in-time ones; keep the living ones
undated and update in place.

| Type | Pattern | Job | Cadence |
|---|---|---|---|
| **Vision** | `Idea.md` | what we're building and why | living |
| **Roadmap** | `ROADMAP.md` | canonical plan + version ladder + backlog | living |
| **Execution** | `Execution.md` | milestones, issues, pipeline, branch discipline | living |
| **Process contract** | `DEFINITION_OF_DONE.md` | the gates; pinned issue | living |
| **Playbook** | `ENGINEERING_SYSTEM_PLAYBOOK.md` | the whole system (this file) | living |
| **Baseline** | `COVERAGE_BASELINE_<date>.md` | per-module line+branch before a gate flip (as needed) | point-in-time |
| **Audit** | `<AREA>_AUDIT_<date>.md` | defect catalog, severity-ranked, routed to issues | point-in-time |
| **Scorecard** | `<AREA>_SCORECARD_<date>.md` | accuracy baseline vs the licensed manual + reproduce command | point-in-time |
| **Trial** | `TRIAL_<name>_<date>.md` | live end-to-end run; per-version "does it work" evidence | point-in-time |
| **Assumptions log** | `apps/<app>/docs/ASSUMPTIONS_LOG.md` | every cited AIAG/ISO/VDA constant with its source | living |

**CHANGELOG.md** — Keep a Changelog + SemVer. `[Unreleased]` on top with `Added/Fixed/Changed`; every
user-visible change adds an entry **in its own PR**. At a version close the "roll" renames
`[Unreleased]` to the version+date and opens a fresh empty one (a `chore(release):` commit). Entries
are explanatory (symptom → root cause → fix), because the changelog doubles as the incident record.

---

## 8. Releases and the version ladder

- **Milestone-driven, deliberately small releases.** 10 versions, `v0.1.0` → `v1.0.0`. No calendar
  dates on the agents — a version ships when its milestone's issues are all closed and green, and the
  SME has reviewed and released it. See [`../ROADMAP.md`](../ROADMAP.md).
- **Every version = a GitHub milestone** holding its issues.
- **A release is a `chore(release):` commit/PR** that rolls the CHANGELOG and bumps the version in the
  root and each package's `pyproject.toml`. Then the flow is `test → main` with **SME sign-off**, and
  the **SME tags + pushes** on `main`. The tag is the release record.
- **Live validation gates the integration/AI versions** — a dated `TRIAL_` doc with a real
  end-to-end run is the evidence, not "it should work."

---

## 9. Agent-assisted execution (the roles that matter)

The ship pipeline (`.claude/agents/`, run by the team lead) is four distinct stages, and the
separation is the point:

| Gate | Stage / tool |
|---|---|
| 0. Spec | `research` agent — investigates domain + standards (licensed manual), writes `.pipeline/spec.md`. Never writes code. |
| 1. Implement minimally | `coder` agent — `ponytail` reflex: reuse > stdlib > native > one line > minimal new code. |
| 2. Dedicated tester | `tester` agent — writes/extends the suite; runs the coverage loop to the floor (line+branch) + negative controls. Never edits source. |
| 3. Correctness review | `reviewer` agent — **read-only by tool restriction**; SHIP / NEEDS WORK / BLOCK verdict to `.pipeline/review.md`. |
| 4. Over-engineering review | `/ponytail-review` on the diff; `/ponytail-audit` + `/ponytail-debt` at version close. |
| 5. Log | CHANGELOG entry + green CI. |

The discipline regardless of tooling: **the tester is a separate pass from the implementer, and the
review passes (correctness, then bloat) are distinct.** One agent wearing all the hats is how quality
erodes. Per CLAUDE.md: **one agent, one worktree** — parallel agents in one checkout silently clobber
each other's branch state and `.pipeline/` files.

---

## 10. One-screen checklist (pin this)

**Per issue:**
- [ ] Branch `feat|fix|chore|docs/<domain>-<slug>` off `origin/test`
- [ ] Shortest correct diff; mark shortcuts `# ponytail:`
- [ ] Separate tester writes/extends the suite
- [ ] Coverage loop: touched surface meets its floor on **line+branch** — **hard stop**
- [ ] New module/MCP surface has its own `--cov-fail-under=100` CI gate, commented in `ci.yml`
- [ ] Any new AIAG/ISO/VDA constant cited in `ASSUMPTIONS_LOG.md` (verified against the licensed manual)
- [ ] `reviewer` verdict = SHIP → then `/ponytail-review` deletes speculative code
- [ ] `ruff` + `mypy` clean, full suite green
- [ ] CHANGELOG `[Unreleased]` entry in the same PR
- [ ] PR into `test` with evidence quoted; **CI green required**; squash-merge; close issue

**Per version:**
- [ ] All milestone issues closed
- [ ] Every per-surface gate green (line+branch); ratchet a floor up if earned
- [ ] Version-diff `/code-review` + `/ponytail-audit` + `/ponytail-debt`
- [ ] Live `TRIAL_` doc where required
- [ ] Roll CHANGELOG + bump root + package `pyproject.toml` versions (`chore(release):`)
- [ ] SME reviews, releases `test → main`, **tags + pushes**

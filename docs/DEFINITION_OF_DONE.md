# Definition of Done

**This is the contract.** Every issue links here instead of re-explaining the gates. Starting an
issue = read this file + the issue body, nothing else. It is mirrored as a **pinned GitHub issue**
(the canonical DoD issue) so it's one click from the issues tab.

> Adapted for this repo (a **uv workspace monorepo** with **per-surface coverage gates**) from the
> `ENGINEERING_SYSTEM_PLAYBOOK`. The mental model and the two review passes are unchanged; the
> coverage rule is expressed against this repo's actual gates.

---

## Per-issue gates — run in order, do not skip

1. **Implement minimally.** The laziest solution that actually works: reuse what's already in the
   repo (a helper, type, or pattern) before writing new code; stdlib / native platform before a new
   dependency; the shortest *correct* diff. Fix the root cause, not the symptom. Mark every
   deliberate shortcut with a `# ponytail:` comment naming the ceiling and the upgrade path.
   Non-trivial logic (a branch, loop, parser, money/security path) leaves **one runnable check**
   behind.

2. **Dedicated tester (separate pass).** A distinct pass — a `test-automator`-style agent, not the
   implementer — writes/extends the suite for the change. For cross-module or **any audit-type**
   issue, a `qa-expert`-style pass reviews the test *strategy* (are we testing the right things,
   not just that tests exist).

3. **Coverage learning loop — THE HARD STOP.** Loop *write test → run coverage → fill the gap* until
   the touched surface meets its gate **on line AND branch** and no gate has regressed. Branch
   coverage is mandatory (`branch = true` in `pyproject.toml`). **Do not start the next issue (or
   close the version) until this is met.** The per-surface gates:

   | Surface | Gate | Command |
   |---------|------|---------|
   | Core surfaces (`quality_core.io` / `.schema` / `.scoring` / `.spc`) | **100%** line+branch | one run: `uv run pytest packages/quality-core --cov=quality_core.io --cov=quality_core.schema --cov=quality_core.scoring --cov=quality_core.spc --cov-fail-under=100` |
   | `quality-mcp` (all modules) | **100%** line+branch | `uv run pytest packages/quality-mcp --cov=quality_mcp --cov-fail-under=100` |
   | Each new engine module (`rca` / `ncr` / `ppap` / `sqe`) extracted into `quality_core` + its MCP tool surface | **100%** line+branch | folded into the core / mcp gate as the module lands (or a new `--cov-fail-under=100` gate in `ci.yml` if it warrants its own) |
   | Governance suites (`tests/`) | green | `uv run pytest tests/` |

   The legacy per-app gates (SPC / Control Plan / MSA / SECOM) were removed 2026-08 with the apps — see [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml) for the canonical current gate list.

   **New modules are held to 100%** — the floor is a minimum; a fresh module dragging a surface down
   is a fail even if the number technically survives. `show_missing = true` prints the exact
   uncovered lines/branches — that's your worklist.

   *Accuracy ≠ coverage.* For anything correctness-bearing against a reference (e.g. the FMEA AP
   table, a future AI suggester), coverage proves the code *ran*; a **scorecard** proves it's
   *right*. Keep a labeled reference + a reproduce command with an explicit bar, tracked like
   coverage. (Precedent: the AIAG-VDA AP table was verified cell-by-cell against the handbook.)

4. **Code review on the diff.** Run `/code-review`. Resolve every correctness finding before merge.

5. **Over-engineering review on the diff.** A second, distinct pass whose *only* job is to find
   bloat: reinvented stdlib, unneeded dependencies, speculative abstractions, dead flexibility
   (`/ponytail-review`). Delete anything speculative.

6. **Green + clean + logged.** Full suite green (`uv run pytest`), `uv run ruff check .` clean,
   `uv run mypy` clean, and a `CHANGELOG.md` entry under `[Unreleased]` **in the same PR**.

7. **PR + merge — and the merge type is not a preference.** One branch per issue off **`origin/test`**
   (`feat|fix|chore|docs/<domain>-<slug>`), which is also the PR target. Do **not** branch off `main`.
   Open a PR whose body says *what* and *why* and **quotes the test/coverage evidence**. CI (the gate)
   must be green to merge. Then close the issue.

   | Merge | Type | Why |
   |---|---|---|
   | feature → `test` | **Squash** | The feature branch is disposable; one clean commit per issue on `test`. |
   | `test` → `main` | **Real merge commit** (`--no-ff`) | Both are long-lived branches. |

   **Never squash between long-lived branches** (`test` → `main`). A squash rewrites the merged commits
   under a new SHA with no parent link to the originals, so git can no longer see the two branches as
   related. The merge-base stops advancing and every subsequent release re-presents already-integrated
   work as conflicts — permanently, and worse each time. (This bit hard once on the old `test`↔`dev`
   pair: the merge-base stranded at `#105` with both branches holding the *same content* under
   different SHAs, caused by four squashed promote commits — a 36-file manual repair. The
   `.gitattributes` `CHANGELOG.md merge=union` rule auto-resolves the changelog half; `--no-ff`
   prevents the rest.)

---

## Per-version gates — before any tag

- [ ] Every issue in the version milestone is closed.
- [ ] All per-surface coverage gates green on line+branch; consider **ratcheting a floor up** (never
      down) if a surface has durably climbed (e.g. SPC 95 → 96).
- [ ] Full `/code-review` of the *version* diff (not just per-issue).
- [ ] Whole-repo over-engineering audit (`/ponytail-audit`) + review the `# ponytail:` shortcut
      markers harvested this cycle (`/ponytail-debt`) — pay them down or consciously keep them.
- [ ] Live validation where the version calls for it (a dated `TRIAL_` doc with a real end-to-end
      run — required for the integration and AI versions; see the playbook §8).
- [ ] Roll `CHANGELOG.md` (`[Unreleased]` → `[x.y.z] - date`, open a fresh `[Unreleased]`) and bump
      the version in `pyproject.toml` + `packages/quality-core/pyproject.toml` — a `chore(release):`
      commit.
- [ ] **`README.md` and `ROADMAP.md` reconciled with the tree that is being tagged.** Both are
      release artifacts, not background docs — they are the first thing a reader sees and the
      easiest thing to leave behind. At minimum, check every one of these and fix what has drifted:
      - **README** — the test-count badge against the collected count, the feature/tool list against
        what actually ships, any version or coverage number, and every claim about *how* a thing is
        implemented (not merely that it exists).
      - **ROADMAP** — status line and date, the shipped-versions list, the "next release" row, and
        any phase whose plan changed during the cycle. A superseded plan must be marked cancelled
        where it appears, not silently deleted.

      Stale docs are not cosmetic. `#194` shipped a fix whose *only* defect was README and ROADMAP
      advertising an ANOVA Gage R&R the engine does not implement — the code was right and the docs
      were lying, and it took two review rounds to close. A doc claim that survives a release is
      indistinguishable from a verified one to everybody downstream.
- [ ] **Tag + push — done by the human owner, never automated.**

---

## Sizing legend (issue fields / labels)

| Field | Values |
|---|---|
| **Size** | `S` ~<0.5d · `M` ~0.5–1.5d · `L` ~2–4d · `XL` ~1wk+ |
| **Complexity** | `low` (mechanical) · `med` (design/unknowns) · `high` (research/accuracy/cross-module) |
| **Priority** | `P0` (blocker) · `P1` (core to the version) · `P2` (when free) |

> **Bootstrap exception:** a pure-doc/config change with no logic (this file; a README edit) is N/A
> for gates 2–5. State that explicitly in the issue/PR so it isn't a silent skip.

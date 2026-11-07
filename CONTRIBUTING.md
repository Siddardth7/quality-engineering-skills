# Contributing

Thanks for helping. The v1 line is stable, and new skills and domains are welcome. This page
only points to where the rules already live.

## Propose first

Open an issue using the **Task Issue** template
([`.github/ISSUE_TEMPLATE/task.md`](.github/ISSUE_TEMPLATE/task.md)). Name the epic, write the
user story and acceptance criteria, and say which on-machine reference manual the engine will
cite. Candidates already on the list are in [ROADMAP.md → Next stages](ROADMAP.md#next-stages).

## Add a skill

1. Copy [`skills/_template/`](skills/_template/) to `skills/<your-skill-name>/` and follow
   "Authoring a New Skill" in [`skills/README.md`](skills/README.md).
2. Skills hold the reasoning only. Every number comes from a deterministic engine in
   `packages/quality-core`, which is exposed through a `packages/quality-mcp` tool.
3. Cite every AIAG / ISO / VDA constant, threshold and quotation in that domain's
   `ASSUMPTIONS_LOG.md` and `CITATIONS.tsv`, checked against the licensed manual and never
   against a web search (see [CLAUDE.md → Standards fidelity](CLAUDE.md#standards-fidelity)).

## Ship it

- Branch from `origin/test` and open the PR into `test` (`feature → test → main`).
- Use conventional commits (`feat:`, `fix:`, `docs:`, `test:`, …), one logical change per commit.
- The gate must be green: `uv run ruff check .`, `uv run mypy`, `uv run pip-audit`, and both
  100% branch-coverage suites plus `tests/`. The full contract is in
  [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md).

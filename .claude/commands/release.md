---
description: Team Lead — cut a version release from `test` to `main` and tag it.
---
You are the Team Lead for Engine-Powered Quality Engineering Skills. Cut release $ARGUMENTS (e.g. v0.2.0) from `test` to `main`.

1. Confirm the version's milestone is complete: every issue in the `$ARGUMENTS` milestone is
   closed (`gh issue list --milestone "$ARGUMENTS" --state open` returns nothing).
2. Confirm the full gate is green on `test` and every coverage bar holds
   (`gh run list --branch test --limit 3`; the per-surface `--cov-fail-under=100` gates in
   `.github/workflows/ci.yml` must all pass).
3. Confirm every PR merged into `test` since the last release carried a `VERDICT: SHIP` review
   (`gh pr list --base test --state merged`).
4. Update CHANGELOG.md and the version single-source-of-truth for $ARGUMENTS (short-lived branch
   off `test`, PR'd into `test` first — `test` is protected).
5. Open a PR `test → main` (`gh pr create --base main --head test`) with the release notes.
   Do NOT merge — the SME (Sid) reviews the code and approves the release.
6. After the SME merges: tag `$ARGUMENTS` on `main` (`git tag $ARGUMENTS && git push --tags`)
   and create the GitHub release.

`main` holds tagged releases. Only `test` merges into it, at milestone boundaries, with SME sign-off.

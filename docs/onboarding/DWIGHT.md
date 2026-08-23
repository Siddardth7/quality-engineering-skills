# Onboarding — Dwight Schrute

**Who you are:** Dwight Schrute · **Claude Code** contributor. (Assistant _to_ the Regional Manager.)
**Account:** Karteek's Claude account · **Machine:** your laptop — shared dev env.
**Slack member:** `dwight_schrute` · **Workspace:** Oruborus - QE Agent (`T0BS2ESV32S`).

## 1. Build the environment
Do the master guide end-to-end first: [`../../Setup.md`](../../Setup.md) §1–§9
(prereqs, clone, reference manuals, `uv sync --frozen`, MCP server, smoke tests).

## 2. Your `.env` (secrets — never commit)
```bash
cp .env.example .env
```
Set:
```
SLACK_IDENTITY=Dwight
SLACK_BOT_TOKEN=<your xoxb- token — Sid sends it privately>
SLACK_TEAM_ID=T0BS2ESV32S
```
Then `set -a; source .env; set +a` (or add the exports to `~/.zshrc`) and restart Claude Code.

## 3. Git identity
```bash
git config user.name "Dwight Schrute (Karteek)"
git config user.email "<your-github-email>"
```
Branch off `origin/test`, never push to `test`/`main` (see CLAUDE.md branch ladder).

## 4. Verify Slack
```bash
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
```
Expect `"user":"dwight_schrute"`. You're already a member of all channels.

## 5. Every session (identity ritual — [`../../Setup.md`](../../Setup.md) §14)
1. `source .env` → `echo $SLACK_IDENTITY` shows `Dwight`.
2. Post in `#general-eng-comms`: `[Dwight] online — Claude Code. Picking up <task>.`
3. Read the channel + your milestone channel for anything addressed to you.
4. Work assigned tasks; thread per topic; hand off in Slack.

**Report to:** Michael (team lead) for scope/assignments.

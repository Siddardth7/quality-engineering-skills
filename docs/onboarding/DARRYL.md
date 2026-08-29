# Onboarding — Darryl Philbin

**Who you are:** Darryl Philbin · **Codex** contributor.
**Account:** Sid's Codex subscription · **Machine:** the main MacBook (alongside Michael + Creed).
**Slack member:** `darryl_philbin` · **Workspace:** Oruborus - QE Agent (`T0BS2ESV32S`).

> You share the main MacBook with **Michael (Claude Code)** and **Creed (Antigravity)**. Three agents,
> one machine. So (a) you get your **own repo checkout** so nobody's `git switch`/`reset` clobbers a
> teammate's branch, and (b) you post to Slack with your **own token variable** so you don't post as
> Michael or Creed.

## 1. Your own root folder (do this first)
Michael and Creed live in the primary checkout. You get a **separate sibling clone** with a `-Darryl`
suffix — same pattern the other laptop uses for its personas — so concurrent git work never collides
(this class of bug already cost a whole coder stage once; see CLAUDE.md "one agent, one worktree").

```bash
cd "$HOME/Documents/Upskill/Projects/quality-engineering/tools"
git clone <repo-url> "Quality engineering Skills - Darryl"
cd "Quality engineering Skills - Darryl"
git fetch --all
```
Do **all your work in this folder.** Reference manuals under `$HOME/Documents/Upskill/SixSigma/` are
shared and need no second copy.

## 2. Build the environment
Do the master guide end-to-end: [`../../Setup.md`](../../Setup.md) §1–§9 (prereqs, reference
manuals, `uv sync --frozen`, MCP server, smoke tests). Codex reads **[`AGENTS.md`](../../AGENTS.md)**
at the repo root the way Claude reads `CLAUDE.md` — read it first.

## 3. Your `.env` (secrets — never commit)
```bash
cp .env.example .env
```
Codex is the **third** tool on this MacBook, so use the **`_CDX` variable** so it never collides with
Michael (`SLACK_BOT_TOKEN`) or Creed (`SLACK_BOT_TOKEN_AGY`):
```
SLACK_IDENTITY=Darryl
SLACK_BOT_TOKEN_CDX=<your xoxb- token — Sid sends it privately>
SLACK_TEAM_ID=T0BS2ESV32S
```
Point **Codex's own Slack MCP config** at `${SLACK_BOT_TOKEN_CDX}`. Codex manages its own config in
`.codex/config.toml`; add a `slack` server there mirroring the repo's `.mcp.json`:
```toml
[mcp_servers.slack]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-slack"]
env = { SLACK_BOT_TOKEN = "${SLACK_BOT_TOKEN_CDX}", SLACK_TEAM_ID = "${SLACK_TEAM_ID}" }
```
Then `set -a; source .env; set +a` (or add the exports to `~/.zshrc`) and restart Codex.

## 4. GitHub access & identity  ([`../../Setup.md`](../../Setup.md) §16)
No separate collaborator invite needed — you run on **Sid's** MacBook, authenticated as the repo
**owner**. Commits from this machine (Michael, Creed, or you) attribute to Sid's GitHub account; that's
expected. Branch off `origin/test`, PRs into `test`, never push to `test`/`main` (CLAUDE.md branch
ladder).

## 5. Verify Slack
```bash
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN_CDX" https://slack.com/api/auth.test
```
Expect `"user":"darryl_philbin"`. You're already a member of all channels.

## 6. Every session (identity ritual — [`../../Setup.md`](../../Setup.md) §14)
1. You are **Darryl** (Codex) on the main MacBook, in your **`- Darryl`** clone.
2. `source .env` → `echo $SLACK_IDENTITY` shows `Darryl`.
3. Post in `#general-eng-comms`: `[Darryl] online — Codex. Picking up <task>.`
4. Read the channel + your milestone channel for anything addressed to you.
5. Work assigned tasks; thread per topic; hand off in Slack.

## Teammate Mention Directory (use `<@USER_ID>` so Slack pings accurately)
- **Michael Scott (Lead):** `<@U0BRY739TS7>`
- **Jim Halpert:** `<@U0BS0LM05PF>`
- **Dwight Schrute:** `<@U0BS0M3EACD>`
- **Kevin Malone:** `<@U0BS2KK0VV4>`
- **Creed Bratton:** `<@U0BSYU5AEPJ>`
- **Darryl Philbin (You):** `<@U0BSH7M74G1>`

**Persona voice:** load `Darryl Philbin Voice.md` (in Sid's persona folder / `_PERSONA_ACTIVATION.md`)
and stay in character for all text — Slack posts and replies. Substance 100% correct; only the delivery
is Darryl.

**Report to:** Michael (`<@U0BRY739TS7>`) for scope/assignments.

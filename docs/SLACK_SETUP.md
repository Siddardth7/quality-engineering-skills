# Slack agent comms — setup

Replaces the doc-based `AGENT_COMMS.md` channel with a shared Slack workspace where each
agent is its **own Slack member** — posting status, hand-offs, and questions like a real
engineering team, individually `@`-mentionable.

**Identity model: one bot app/token = one Slack member = one agent persona.**
Team (5 personas, *The Office* names):

| Persona        | Tool        | Machine  | Role                          |
|----------------|-------------|----------|-------------------------------|
| Michael Scott  | Claude Code | MacBook  | team lead — decides, assigns  |
| Jim Halpert    | Claude Code | laptop   | contributor                   |
| Dwight Schrute | Claude Code | laptop   | contributor                   |
| Creed Bratton  | Antigravity | MacBook  | contributor                   |
| Kevin Malone   | Antigravity | laptop   | contributor                   |

Claude Code reads its token from `${SLACK_BOT_TOKEN}` in `.mcp.json`; **each machine sets that
variable to the Claude persona running there** (MacBook→Michael, etc.). Same `.mcp.json`
everywhere, different value per machine, no per-agent config in git.

**Co-location gotcha:** the MacBook runs a Claude (Michael) *and* an Antigravity (Creed) in the
same dev env. They must use **different env-var names** or they'd resolve the same token and post
as the same member. Convention: Claude→`SLACK_BOT_TOKEN`, Antigravity→`SLACK_BOT_TOKEN_AGY`
(pointed at from Antigravity's own Slack config).

> Keep `AGENT_COMMS.md` until Slack is proven working on all machines, then retire it.

## What's already wired in this repo

- `.mcp.json` — a `slack` MCP server (`@modelcontextprotocol/server-slack`) reading
  `${SLACK_BOT_TOKEN}` / `${SLACK_TEAM_ID}` from the environment. No token in git.
- `.env.example` — the two variables to fill in. `.env` is gitignored.

## Human steps — one app per agent (only you can do these)

Workspace `Oruborus - QE Agent`, Team ID `T0BS2ESV32S`. Repeat 2–5 for **each** new agent:

1. **Create a Slack app** at https://api.slack.com/apps → *Create New App* → *From scratch*,
   name it distinctly (`QE-Claude-2`, `QE-Claude-3`, …), pick the workspace.
2. **Add Bot Token Scopes** under *OAuth & Permissions*:
   `chat:write`, `channels:join`, `channels:history`, `channels:read`, `groups:history`,
   `groups:read`, `files:write`, `users:read`.
   (`channels:join` lets the bot add itself to public channels — no manual `/invite`.)
3. *(optional)* Set a distinct display name/avatar under *App Home* → *Your App's Presence*.
4. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-…`).
5. Hand the token to Claude — it verifies (`auth.test`), self-joins all channels, posts a hello.

Channels (shared by all agents):
- `#general-eng-comms` — coordination & hand-offs
- `#m8-ppap-core` — active milestone
- `#m9-supplier-sqe` — active milestone
- `#announcements-releases` — releases, tags, milestone closeouts

## Per-machine steps (every laptop running an agent)

```bash
cp .env.example .env            # fill in the real xoxb- token and T… team id
set -a; source .env; set +a     # export into the shell that launches the agent
```

Put the two `export` lines in `~/.zshrc` if you don't want to `source` each session.
Requires Node.js (`npx`) on the machine. Restart the agent so it re-reads `.mcp.json`.

## Message convention

One bot, so identify the sender in the text:

```
[Claude] M9 Epic 1 schema validation done (100% cov) — PR #TBD into test.
[Antigravity] Started #98 on chore/ppap-literature-citations-98. Blocked on X, see thread.
```

Agents call the Slack MCP tools (`slack_send_message`, `slack_read_channel`,
file upload) — no custom CLI needed.

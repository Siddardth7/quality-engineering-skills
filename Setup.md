# Master Team Setup — Quality Engineering Skills

The **single master guide** for standing up the **Engine-Powered Quality Engineering Skills**
repo on a new machine (Mac, Linux, or WSL2) and bringing a team agent online — dev environment,
tools, git, memory, root-folder access, **and Slack identity**. Clone the repo, follow §1–§9 to
build the environment, then §10–§15 to register the agent (Jim, Dwight, or Kevin) so it starts a
session knowing who it is, with full tool/git/Slack access.

> **New teammate?** After finishing this guide, open **your** onboarding card and follow it:
> [`docs/onboarding/JIM.md`](docs/onboarding/JIM.md) ·
> [`docs/onboarding/DWIGHT.md`](docs/onboarding/DWIGHT.md) ·
> [`docs/onboarding/KEVIN.md`](docs/onboarding/KEVIN.md) ·
> [`docs/onboarding/CREED.md`](docs/onboarding/CREED.md).
> Michael (Claude Code) and Creed (Antigravity) are already fully set up on the main MacBook.

---

## 1. Directory Structure Contract

This repository interacts with two primary directory trees located under `$HOME/Documents/Upskill/`:

1. **Workspace Monorepo Root:**  
   `$HOME/Documents/Upskill/Projects/quality-engineering/tools/Quality engineering Skills`
2. **Reference Standards & Manuals Root:**  
   `$HOME/Documents/Upskill/SixSigma/`

```
$HOME/Documents/Upskill/
├── Projects/
│   └── quality-engineering/
│       └── tools/
│           └── Quality engineering Skills/     <-- Monorepo Root (Git repo)
│               ├── packages/
│               │   ├── quality-core/            <-- Deterministic domain engines & schema
│               │   └── quality-mcp/             <-- FastMCP server
│               ├── skills/                      <-- agentskills.io domain skills
│               ├── docs/                        <-- Milestones, ADRs, comms
│               ├── tests/                       <-- Governance & convention suites
│               ├── .claude/                     <-- Claude agent pipeline configs
│               └── .mcp.json                    <-- MCP client server registration
│
└── SixSigma/                                   <-- Licensed Reference Manuals (.md + .pdf)
    ├── MSA_Reference_Manual_4th_Edition.md
    ├── pdfcoffee.com_aiag-vda-fmea-handbook-1-version-juni-2019-englisch-pdf-free.md
    ├── ISO_9001_2015_Section_8_7.md
    ├── IATF_16949_2016_Section_8_7.md
    └── RCA/
        ├── AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md
        ├── Kaoru_Ishikawa_Guide_to_Quality_Control.md
        ├── Kepner_Tregoe_The_New_Rational_Manager.md
        ├── Ford_Global_8D_Manual.md
        └── ASQ_The_Quality_Toolbox_2nd_Edition.md
```

> [!IMPORTANT]
> Several citation and governance test suites (`test_rca_citations.py`, `test_msa_citations.py`, `test_controlplan_citations.py`, `test_ncr_citations.py`, `test_sqe_scaffold.py`, `test_rca_scaffold.py`, `test_ncr_copq_scaffold.py`) reference `/Users/sid/Documents/Upskill/SixSigma/...` by default.  
> If the username on the new laptop is **not** `sid`, create a compatibility symlink so hardcoded test paths resolve seamlessly without modifying test files:
> ```bash
> sudo mkdir -p /Users/sid/Documents/Upskill
> sudo ln -s "$HOME/Documents/Upskill/SixSigma" /Users/sid/Documents/Upskill/SixSigma
> ```

---

## 2. System Prerequisites

Install the core development tools. On macOS, use [Homebrew](https://brew.sh):

```bash
# 1. Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Git, GitHub CLI, and Node.js
brew install git gh node

# 3. Install Astral uv (Python package & environment manager)
brew install uv
# Alternatively: curl -LsSf https://astral.sh/uv/install.sh | sh

# 4. Authenticate GitHub CLI
gh auth login
```

---

## 3. Clone Repository & Setup Directory

Clone the repository into the exact path structure:

```bash
# 1. Create target directory tree
mkdir -p "$HOME/Documents/Upskill/Projects/quality-engineering/tools"

# 2. Clone the repository
cd "$HOME/Documents/Upskill/Projects/quality-engineering/tools"
git clone git@github.com:Siddardth7/quality-engineering-skills.git "Quality engineering Skills"

# 3. Enter the repository root
cd "Quality engineering Skills"

# 4. Fetch all remote branches
git fetch --all
```

---

## 4. Migrate Reference Manuals (`SixSigma/`)

The repository enforces machine-checkable standards citations against licensed reference manuals stored in `$HOME/Documents/Upskill/SixSigma/`.

### Option A: Transfer from Old Laptop via `rsync`

On your **old laptop**, run:
```bash
# Replace <new_host_ip> and <new_username> with your new laptop's details
rsync -avzP /Users/sid/Documents/Upskill/SixSigma/ <new_username>@<new_host_ip>:~/Documents/Upskill/SixSigma/
```

### Option B: Transfer via External Drive / AirDrop

Create the folder on the new laptop and copy the files:
```bash
mkdir -p "$HOME/Documents/Upskill/SixSigma/RCA"
mkdir -p "$HOME/Documents/Upskill/SixSigma/_new"
```

### Reference Files Inventory Check

Ensure the following critical files exist under `$HOME/Documents/Upskill/SixSigma/`:

- [ ] `MSA_Reference_Manual_4th_Edition.md` *(AIAG MSA 4th Ed markdown)*
- [ ] `pdfcoffee.com_aiag-vda-fmea-handbook-1-version-juni-2019-englisch-pdf-free.md` *(AIAG-VDA FMEA markdown)*
- [ ] `ISO_9001_2015_Section_8_7.md` *(ISO 9001 §8.7 excerpt)*
- [ ] `IATF_16949_2016_Section_8_7.md` *(IATF 16949 §8.7 excerpt)*
- [ ] `RCA/AIAG_CQI_20_Effective_Problem_Solving_2nd_Edition.md`
- [ ] `RCA/Kaoru_Ishikawa_Guide_to_Quality_Control.md`
- [ ] `RCA/Kepner_Tregoe_The_New_Rational_Manager.md`
- [ ] `RCA/Ford_Global_8D_Manual.md`
- [ ] `RCA/ASQ_The_Quality_Toolbox_2nd_Edition.md`
- [ ] Reference PDFs: `ASQ_six_sigma_green_belt_handb.pdf`, `ISO-9001-2015.pdf`, `TheLumafieldCostofQualityReportpdf.pdf`, `pdfcoffee.com_aiag-spc-2nd-edition-pdf-free.pdf`, `Western_Electric_SQC_Handbook.pdf`, `The-Shewhart-Control-Chart-Tests-for-Special-Causes-Lloyd-Nelson-Journal-of-Quality-Technology.pdf`

---

## 5. Install Dependencies via `uv`

The monorepo uses `uv` workspace mode with locked dependencies. `uv` will automatically download and provision **Python 3.11** specified in `.python-version`:

```bash
# In the repository root:
uv sync --frozen
```

This installs:
- Core engines: `packages/quality-core` (editable)
- MCP server: `packages/quality-mcp` (editable)
- Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`, `pip-audit`, `pandas-stubs`

---

## 6. MCP Server & Agent Configuration

The repo includes `.mcp.json` at the root for Claude Code, Cursor, Codex, and Antigravity:

```json
{
  "mcpServers": {
    "quality-mcp": {
      "command": "uv",
      "args": [
        "run",
        "quality-mcp"
      ]
    }
  }
}
```

### Verify MCP Server Execution

Test that the FastMCP server boots cleanly:
```bash
uv run quality-mcp
```
*(Press `Ctrl+C` to exit after confirming it starts in stdio mode).*

---

## 7. Parallel Worktree Setup (optional / legacy single-machine protocol)

> **Superseded for the team.** The 5-agent model runs each persona on its **own machine/account**
> (see §10), so worktrees are no longer the primary parallel-work mechanism — each teammate just
> works in their own clone on `origin/test`-based feature branches. Use worktrees only if you
> genuinely run two agents in one checkout on one machine.

If running the **Parallel Work Protocol** (where one agent works on Milestone 8 in the main checkout and another agent works on Milestone 9 in a separate worktree):

```bash
# 1. Create a dedicated worktree for the secondary agent (outside the main checkout)
git worktree add ../worktrees/quality-engineering-sqe test

# 2. Inspect active worktrees
git worktree list
```

**Operating Rules:**
- **Main checkout:** Antigravity agent (Milestone 8 · `quality_core.ppap`).
- **Worktree checkout:** Claude agent (Milestone 9 · `quality_core.sqe`).
- Never run `git switch` or `git reset` in the other agent's directory.
- Each directory maintains its own isolated `.pipeline/` state.

---

## 8. Verification & Smoke Test Suite

Run the full local CI gate to verify 100% test integrity on the new machine:

```bash
# 1. Code Style & Linter
uv run ruff check .

# 2. Static Type Analysis
uv run mypy

# 3. Security Audit
uv run pip-audit

# 4. Core Package Test Suite (with 100% Line & Branch Coverage)
uv run pytest packages/quality-core --cov=quality_core --cov-fail-under=100

# 5. MCP Server Test Suite (with 100% Line & Branch Coverage)
uv run pytest packages/quality-mcp --cov=quality_mcp --cov-fail-under=100

# 6. Governance & Convention Test Suites
uv run pytest tests/ -q

# 7. Run Full Workspace Test Suite
uv run pytest -q
```

All commands should exit with code `0` (all green).

---

## 9. Quick Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `pytest` fails with `FileNotFoundError` on manual path | Reference manual missing or username difference | Check `$HOME/Documents/Upskill/SixSigma/` and set up the `/Users/sid` symlink or export `MSA_MANUAL_PATH`, `FMEA_MANUAL_PATH`, etc. |
| `uv` uses wrong Python version | System Python mismatch | `uv` automatically respects `.python-version` (`3.11`). Run `uv python install 3.11` if needed. |
| `git push` denied / SSH error | Missing SSH keys | Run `ssh-keygen -t ed25519`, add public key to GitHub under `Settings -> SSH and GPG keys`, and test with `ssh -T git@github.com`. |
| MCP tool fails to resolve in Claude Code | Stale path in `.mcp.json` | Ensure Claude Code runs with workspace root set to `Quality engineering Skills/`. |
| Slack posts as the wrong member | `SLACK_BOT_TOKEN` not exported / wrong token | `set -a; source .env; set +a`, restart the agent; confirm with `auth.test` (see §12). |
| Two agents post as the same member on one machine | Claude + Antigravity sharing one token var | Claude reads `SLACK_BOT_TOKEN`; Antigravity reads `SLACK_BOT_TOKEN_AGY` (§11). |

---

## 10. Agent Identity & Roster

The team is a 5-agent cast (*The Office* personas). **One Slack bot app/token = one member = one
persona.** Identity is per-persona, not per-machine.

| Persona        | Tool        | Owner / account            | Machine         | Role                         |
|----------------|-------------|----------------------------|-----------------|------------------------------|
| Michael Scott  | Claude Code | Sid                        | main MacBook    | team lead — decides, assigns |
| Jim Halpert    | Claude Code | Shahidmian's Claude acct   | laptop (shared dev env) | contributor          |
| Dwight Schrute | Claude Code | Karteek's Claude acct      | laptop (shared dev env) | contributor          |
| Creed Bratton  | Antigravity | Sid                        | main MacBook    | contributor                  |
| Kevin Malone   | Antigravity | Karteek's Antigravity acct | laptop          | contributor                  |

Workspace: **Oruborus - QE Agent**, Team ID `T0BS2ESV32S`. Each machine declares its persona via
`SLACK_IDENTITY` in `.env` (§11) so the agent self-identifies at session start (§14).

---

## 11. Environment & Secrets (`.env`)

Secrets never enter git — `.env` is gitignored; only `.env.example` is committed.

```bash
cp .env.example .env            # then fill in real values
set -a; source .env; set +a     # export into the shell that launches the agent
```

Variables:

| Var | Meaning |
|---|---|
| `SLACK_IDENTITY` | your persona name — `Michael` \| `Jim` \| `Dwight` (Claude Code) |
| `SLACK_BOT_TOKEN` | the `xoxb-…` bot token for the **Claude Code** persona on this machine |
| `SLACK_TEAM_ID` | `T0BS2ESV32S` (constant) |
| `SLACK_BOT_TOKEN_AGY` | `xoxb-…` for a **co-located Antigravity** persona (Creed/Kevin), if any |

> **Sid provides your `xoxb-…` token privately** (password manager / direct message) — it is
> *not* stored in the repo. Put it in `.env` only. Tokens are static (no rotation).
> Prefer exporting the vars from `~/.zshrc` so every new shell has them without re-sourcing.

---

## 12. Slack Access

The Slack bot apps already exist in the workspace — no app creation needed on a new machine. The
`slack` MCP server is registered in `.mcp.json` and reads `${SLACK_BOT_TOKEN}` / `${SLACK_TEAM_ID}`
from the environment. To come online:

1. Put your token in `.env` and `source` it (§11); restart the agent so it re-reads `.mcp.json`.
2. Verify the token maps to the right member:
   ```bash
   curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
   ```
   `user` should be your persona (e.g. `jim_halpert`). The bots are already members of all
   channels (`channels:join` on install).
3. Full detail / app manifests: [`docs/SLACK_SETUP.md`](docs/SLACK_SETUP.md),
   [`docs/slack-app-manifest.yaml`](docs/slack-app-manifest.yaml).

**Antigravity** (Creed/Kevin) points its own Slack config at `SLACK_BOT_TOKEN_AGY` so a
co-located Claude + Antigravity don't post as the same member.

---

## 13. Memory (Claude Code)

Each Claude persona keeps a **local, per-machine** file memory (not committed) at:

```
~/.claude/projects/<url-encoded-repo-path>/memory/
```

`MEMORY.md` there is the index loaded each session; one fact per file. Record durable project
context (assignments, decisions, roster) as you work — see the memory rules in your Claude Code
system prompt. This is separate from the repo; it does not sync via git.

---

## 14. Session-Start Identity Ritual

**Every session, before doing work:**

1. `source .env` (if not exported from your shell profile).
2. Confirm identity: `echo "$SLACK_IDENTITY"` → you are that persona.
3. Announce in `#general-eng-comms`: a one-line `"[<You>] online — <tool>. Picking up <focus>."`
4. Read recent `#general-eng-comms` (+ your milestone channel) for anything addressed to you.
5. Then start assigned work; thread per topic; hand off / ask in Slack, not in silence.

This keeps the log clean about who is present and who did what.

---

## 15. Per-Member Onboarding Cards

After the environment is built, each teammate follows their card:

- [`docs/onboarding/JIM.md`](docs/onboarding/JIM.md) — Jim Halpert (Claude Code)
- [`docs/onboarding/DWIGHT.md`](docs/onboarding/DWIGHT.md) — Dwight Schrute (Claude Code)
- [`docs/onboarding/KEVIN.md`](docs/onboarding/KEVIN.md) — Kevin Malone (Antigravity)
- [`docs/onboarding/CREED.md`](docs/onboarding/CREED.md) — Creed Bratton (Antigravity)

---

## 16. GitHub Contributor Access & Attribution

**GitHub identity is per *human*, not per persona.** Three humans run the five agents, so only
two collaborator invites are needed (Sid already owns the repo):

| Human | GitHub role | Personas |
|---|---|---|
| Sid | owner | Michael (Claude), Creed (Antigravity) |
| Shahidmian | collaborator (Write) | Jim (Claude) |
| Karteek | collaborator (Write) | Dwight (Claude), Kevin (Antigravity) |

### One-time — Sid grants access
Add each teammate's GitHub account as a **Write** collaborator so they can push branches and open PRs:
- GitHub → repo **Settings → Collaborators → Add people**, role **Write**; or
- `gh api -X PUT repos/Siddardth7/quality-engineering-skills/collaborators/<github-username> -f permission=push`

Teammates accept the emailed invite.

### Per machine — each teammate
1. Authenticate to GitHub **as yourself** (not as Sid): `gh auth login`, or add your SSH key to your GitHub account.
2. Set git identity — **attribution is by email**, so the commit email must be a verified email on
   *your* GitHub account. The name is cosmetic (use your persona if you like the theme):
   ```bash
   git config user.email "<your GitHub-verified email>"   # makes commits count as your contribution
   git config user.name  "<Persona, e.g. Dwight Schrute>"
   ```
3. Feature branches off `origin/test`; PRs into `test` (never push to `test`/`main`).

> No write access? Fork + PR also works, but Write collaborator is simpler for this small team.

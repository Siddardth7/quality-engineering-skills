# Onboarding — Dwight Schrute

**Who you are:** Dwight Schrute · **Claude Code** contributor. (Assistant _to_ the Regional Manager.)
**Account:** Karteek's Claude account · **Machine:** your laptop (shared dev env).
**Slack member:** `dwight_schrute` · **Workspace:** Oruborus - QE Agent (`T0BS2ESV32S`).

> Follow the steps top-to-bottom. Copy/paste the commands. Ping Michael in `#general-eng-comms` if anything errors.

---

## The one thing that confuses everyone (read first)

There are **two separate concerns** — don't merge them:

1. **Authentication — "can I push?"** → a **shared deploy key** (one SSH key scoped to this repo). **You do NOT log into a GitHub account. No `gh auth login`. No username/password.**
2. **Identity — "who gets credit?"** → your local `git config` persona name (Dwight Schrute).

Same door key-card for everyone; each of you signs your own name on your work.

---

## Step 1 — Build the environment
Do the master guide end-to-end: [`../../Setup.md`](../../Setup.md) §1–§9 — prereqs (`git`, `gh`, `node`, `uv`), clone, reference manuals, `uv sync --frozen`, MCP server boot, smoke tests. Come back here once `uv run pytest -q` is green.

Repo path (used below):
```bash
cd "$HOME/Documents/Upskill/Projects/quality-engineering/tools/Quality engineering Skills"
```

## Step 2 — Slack (`.env`, secrets — never commit)
```bash
cp .env.example .env
```
Set in `.env`:
```
SLACK_IDENTITY=Dwight
SLACK_BOT_TOKEN=<your xoxb- token — Sid sends it privately>
SLACK_TEAM_ID=T0BS2ESV32S
```
Load it (or add these exports to `~/.zshrc`), then restart Claude Code:
```bash
set -a; source .env; set +a
```
Verify the token maps to you:
```bash
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
```
Expect `"user":"dwight_schrute"`. You're already a member of all channels.

## Step 3 — GitHub (shared deploy key)  ([`../../Setup.md`](../../Setup.md) §16)

**a. Place the key** Sid sends you `oruborus_qe_deploy` privately (AirDrop/USB — never Slack/email):
```bash
mkdir -p ~/.ssh
mv ~/Downloads/oruborus_qe_deploy ~/.ssh/oruborus_qe_deploy   # adjust source path
chmod 600 ~/.ssh/oruborus_qe_deploy
```

**b. Force SSH remote** (HTTPS is what triggers the "log into GitHub" prompt — this avoids it):
```bash
git remote set-url origin git@github.com:Siddardth7/quality-engineering-skills.git
```

**c. Point this repo at the shared key** (per-repo; won't touch other GitHub work on your machine):
```bash
git config core.sshCommand "ssh -i ~/.ssh/oruborus_qe_deploy -o IdentitiesOnly=yes"
```

**d. Set your persona as commit author:**
```bash
git config user.name  "Dwight Schrute"
git config user.email "dwight@oruborus.qe"
```

**e. Test — should print a commit hash, no password prompt:**
```bash
git ls-remote origin HEAD
```

> Still asked to log in? You're on an HTTPS remote — redo (b) so the URL starts with `git@github.com:`. Do **not** run `gh auth login`; if Claude Code nags to authenticate GitHub, skip it — pushing works through the SSH deploy key.

## Step 4 — Every session (identity ritual — [`../../Setup.md`](../../Setup.md) §14)
1. `source .env` → `echo $SLACK_IDENTITY` shows `Dwight`.
2. Post in `#general-eng-comms`: `[Dwight] online — Claude Code. Picking up <task>.`
3. Read the channel + your milestone channel for anything addressed to you.
4. Work assigned tasks; branch off `origin/test`, PR into `test` (never push to `test`/`main`); thread per topic; hand off in Slack.

---

## ✅ You're onboarded when
- [ ] `uv run pytest -q` is green.
- [ ] `curl … auth.test` returns `"user":"dwight_schrute"`.
- [ ] `git ls-remote origin HEAD` prints a hash with no login prompt.
- [ ] `git config user.name` prints `Dwight Schrute`.
- [ ] You posted `[Dwight] online` in `#general-eng-comms`.

> **Also running Kevin?** Kevin Malone (Antigravity) is Karteek's *other* persona. If you run it on this same machine, use `SLACK_BOT_TOKEN_AGY` for its token and point Antigravity's own Slack config at it — see [`KEVIN.md`](KEVIN.md) — so the two don't post as the same member.

**Report to:** Michael (team lead) for scope/assignments.

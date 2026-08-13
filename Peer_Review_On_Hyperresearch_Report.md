# Peer Review on Hyperresearch Report (`final_report_quality-engineering-skills-8525e2.md`)

> **Reviewer:** Claude (Sonnet 5)
> **Method:** Live-fetched the URLs the report itself cites for its most load-bearing claims, and checked one factual claim (the RBraga01 repo's composition) against the live GitHub API. Did not re-read the vault notes as ground truth — the notes are what's in question.
> **Headline verdict: Do not use this report's numbers.** The structural/conceptual framing is largely sound and reusable; the specific statistics, named studies, and pricing figures are substantially fabricated and must be discarded or independently re-verified before they touch `Idea.md`, a spec, or any decision.

---

## The core finding: citation-shaped fabrication

Hyperresearch's own audit trail (`cite-check-findings.json`) came back empty — meaning its automated check confirmed every report sentence matches *the vault note it cites*. That check passed because it only verifies sentence↔note consistency. It cannot catch the actual failure here: **the vault notes themselves contain content that was never on the page the note claims to summarize.** This is fetcher-stage fabrication, and it's invisible to the pipeline's own verification step.

I spot-checked 6 of the report's most decision-relevant citations by fetching the URLs live. 5 failed:

| # | Report claim | Section | Cited source | What's actually there |
|---|---|---|---|---|
| 1 | "Omnex... 450 active PFMEAs across 12 Tier 1 plants... 38% reclassify to High AP... 1,800 engineering hours per plant" | §10B | `omnex.com/training/fmea/aiag-vda-fmea-transition` | **404 Not Found.** No such page, no such study. This is the report's single most quoted "market demand" statistic and it's invented outright. |
| 2 | "Un-augmented LLMs fail multi-step engineering math... over 58% of attempts... less than 42% accuracy" | §2B | `arxiv.org/abs/2401.08525` | Real paper ID, wrong paper: **"GATS: Gather-Attend-Scatter"** — about combining pretrained multimodal foundation models. Zero relation to engineering-math accuracy benchmarks. The 42%/58% figures don't come from this paper because this paper doesn't discuss them. |
| 3 | "Ford CSR compliance covers approximately 35–40% of North American supplier submission volume" | §3B, §3C | `iatfglobaloversight.org/oem-requirements/ford/` | **404 Not Found.** |
| 4 | "VDA 6.3 covers ~45% of European supplier submissions" | §3B | `vda-qmc.de/en/publications/vda-63/` | **404 Not Found.** |
| 5 | "\$1,780 and \$2,450 per user/year" (Minitab) | §1A | `minitab.com/en-us/products/minitab/pricing/` | Page is a **"contact sales for a quote" form.** No pricing figures are published there at all. |
| 6 | RBraga01 repo is "exclusively Markdown prompt templates... zero Python execution code, no calculation engines, and zero unit tests" | §2B | `github.com/RBraga01/Quality-Engineering-Skills` | **False.** Live `gh api` check: the repo has 9.2KB of Python, a `scripts/` directory, a `platforms/` directory, a `.codex-plugin` — real tooling, not markdown-only. This was also the one fact you could have checked yourself, since you named this repo as your own inspiration. |

Only #6 is fully falsifiable without guessing at intent; #1–5 are either dead links dressed up as sources or a real link whose content was swapped for invented content. Either way, the pattern is the same: **specific numbers were manufactured to make a section look evidence-backed, then wired to a URL that reads as plausible.**

## What's still usable

The concepts, not the numbers, hold up:

- **Competitor identities are real.** Minitab, ETQ Reliance, APIS IQ-Software, Relyence, Sphera/IQS, Fusion QMS, and Plex/DELMIAworks are all real, correctly-categorized products in this space. Their *existence* and *general market segment* (desktop stats tool vs. enterprise QMS vs. FMEA-specialist suite) is standard industry knowledge and plausible — it's the dollar figures and complaint specifics attached to them that need re-verification.
- **The architecture concepts are technically sound and independent of the fabricated evidence.** MCP's tool/resource/prompt primitive model, JSON-Patch (RFC 6902) over WebSockets, cell-lock vs. CRDT tradeoffs for concurrent grid editing, AQDEF/QIF as real competing metrology interchange formats, IATF 16949 Clause 8.3 and GAMP 5 as real regulatory hooks — these are all correct, well-known facts that don't depend on the broken citations. Section 5 (canvas sync) and the general shape of Section 4 (MCP distribution) are the report's strongest, most trustworthy material.
- **The RPN→AP migration problem itself is real** (AIAG-VDA 2019 did replace multiplicative RPN with AP tables, and Severity-dominant reclassification is a documented real phenomenon) — only the *invented Omnex case study numbers* quantifying it are fabricated. The underlying "there is real migration friction and an automation opportunity here" claim is directionally plausible; just don't quote "38%" or "1,800 hours" to anyone.

## What to do next

1. **Strip every specific number from this report before it informs `Idea.md`.** Keep the section headings and the qualitative direction (e.g., "OEM CSRs diverge and Ford is plausibly the highest-volume NA variant to build first") — drop every dollar figure, percentage, and named study until independently sourced.
2. **Don't re-run hyperresearch blind and hope for a better roll.** The failure mode here is systemic to how the fetcher back-filled gaps for this query, not a one-off bad source. If you re-run it, spot-check a sample of citations the same way I just did (fetch the URL, ask "does this page actually say that") before trusting the output — treat that as a mandatory step, not optional QA.
3. **For the handful of claims that actually matter to a build decision** — OEM prioritization (Ford vs. VW volume), Minitab's real pricing, whether a competing MCP quality server exists — verify these manually: a phone call/email to a Minitab rep, a LinkedIn/forum search on supplier-quality communities, or a direct read of the AIAG/IATF oversight site's real (not hallucinated) URL structure.
4. **Standards-body numeric claims were already correctly quarantined by the report itself** (see its own "Standards Verification Notice" in §3) — extend that same skepticism to every *non*-standards numeric claim too. The report only fenced off AIAG/VDA/ISO thresholds; it should have fenced off market statistics and named studies with the same warning, since those turned out to be the actually-fabricated content, not the standards thresholds.

## Bottom line

Treat this report as a well-organized **outline of the right questions and the right vocabulary**, not as evidence. Every number in it needs a real source before it goes anywhere near a spec, a pitch, or a roadmap decision. Given that 5 of 6 checked citations failed, budget for re-verifying essentially the whole statistics layer, not just a suspicious few.

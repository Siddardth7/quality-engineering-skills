---
name: 8d-problem-solving
description: Ford Global 8D / AIAG CQI-20 D0-D8 report validation, closure-gate reading, single-step state transition, and themed HTML canvas rendering, routing every verdict, gate reason, closeable flag, and citation basis to validate_8d, advance_8d, and render_8d_canvas on quality-mcp and never authoring a root cause or adjudicating a gate in prompt text.
---

# 8D Problem Solving: Validated Disciplines, Cited Gates, Host-Carried State

## Overview
The `8d-problem-solving` skill guides AI agents through a Ford Global 8D / AIAG CQI-20 report from D0 to CLOSED. Three deterministic answers are produced, and every one of them is produced by a tool on `quality-mcp`, never in prompt text: a whole-report discipline sweep with its closure gates via `validate_8d`; one hypothetical adjacent state transition, allowed or refused, via `advance_8d`; and a themed HTML canvas of the already-validated report via `render_8d_canvas`. Each tool returns the core engine's own payload verbatim — no field is renamed, dropped, or added in transport — so every verdict, gate reason, and flag reported to a user is quoted from a payload, never inferred from reading the report.

**There are two `closeable` flags and they legitimately disagree.** They answer different questions and must never be substituted for each other:
1. `result["closeable"]` from `validate_8d` (and the hoisted `result["closeable"]` from `render_8d_canvas`) is the **whole-report** gate: `true` only when `gate_reasons` is empty, which includes the D3-to-D4 linked-NCR gate `PDD-8D-008`.
2. `result["d8"]["closeable"]` (`result["validation"]["d8"]["closeable"]` on the canvas tool) is **closure-evidence only**: whether the D8 closure evidence — containment, root cause, prevention — is itself complete. It can be `true` while the whole-report flag is `false`.

Whenever either is mentioned to a user, report both, distinctly labelled, and name which question each one answers. Never say "the report is closeable" on the strength of `d8.closeable`, and never say "D8 closure evidence is incomplete" on the strength of the top-level flag.

**Read the citation basis; do not make standards claims of your own.** The **Ford Global 8D Manual** is the primary source for the D0-D8 discipline labels (`RULE-8D-SOURCE-PRIMACY`), with **AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018)** supplementing where Ford 8D does not label its steps. Which of the two — if either — stands behind any individual finding or gate is a machine-readable fact in the payload, not something to be judged from wording:
- Every finding carries `citation_basis`: `"RULE"` (a `RULE-8D-*` row in `quality_core/rca/CITATIONS.tsv`, backed by an on-box manual quote), `"PDD"` (a numbered Process Design Decision in `quality_core/rca/ASSUMPTIONS_LOG.md` — this platform's own choice), or `"PLATFORM_UNCITED"` (neither).
- Every gate reason carries `rule_id`: a `RULE-8D-*` id, a `PDD-8D-*` id, or `null`.

A `PDD-8D-*` id is **never** a Ford or CQI-20 citation. The `PDD-` prefix is deliberately not `RULE-`, which is reserved for identifiers naming a `CITATIONS.tsv` row. Relay `PDD-8D-008` (D3-to-D4 linked-NCR refusal), `PDD-8D-010` (D8-to-CLOSED corrective-action-verification refusal), and `PDD-8D-013` (D7 prevention-update root-cause linkage) as this platform's own design decisions, and say so in those words. A `rule_id` of `null` or a `citation_basis` of `"PLATFORM_UNCITED"` is reported plainly as uncited — never silently dropped, and never reworded to sound backed by a standard.

Two further authority boundaries hold throughout:
1. **The team owns the root cause; this skill never authors one.** `validate_8d` returns no `d4` key at all — D4's closure-relevant answer surfaces only as a `ROOT_CAUSE_REJECTED` or `ROOT_CAUSE_EVIDENCE_MISSING` gate reason carrying `RULE-8D-GATE-CLOSURE`. Causal-chain construction and validation belong to the `5why-root-cause` skill and its `validate_5why` tool; this skill reads only the already-computed verdict the report carries.
2. **The server persists nothing.** `advance_8d` advances no state server-side: it evaluates the transition for the report passed in and returns the would-be new report inside `result["report"]`. The host must carry that dict forward into the next call, or the advance is silently lost.

This skill equips agents to:
- Read a whole 8D report's discipline verdicts and closure gates without re-deriving a single one of them.
- Distinguish a manual-backed requirement from a platform design decision from an uncited platform behaviour, by field and not by tone.
- Attempt one state transition at a time and report a refusal, with its `rule_id`, rather than routing around it.
- Delegate all validation, gate adjudication, transition evaluation, and rendering to `validate_8d`, `advance_8d`, and `render_8d_canvas` on `quality-mcp`.

## When to Use
Activate this skill in the following problem-solving scenarios:
- **8D Report Review:** Auditing a whole D0-D8 report for discipline completeness and closure readiness before a customer or internal review.
- **Closure-Gate Assessment:** Determining what is actually blocking closure of an in-progress 8D and which gate reason, with which `rule_id`, is responsible.
- **Discipline Advance Checks:** Testing whether a report may legitimately move from its current discipline to the next one.
- **Containment and Prevention Traceability:** Checking that D3 containment is verified, that the D7 prevention update declares the D4 finding it prevents, and that the D8 record is reviewed.
- **8D Canvas Reporting:** Producing a themed HTML canvas of an already-validated report for a review pack.
- **Root-Cause Handoff:** Recognising a `ROOT_CAUSE_REJECTED` gate and routing the causal work to the `5why-root-cause` skill instead of drafting a cause here.

### Input Requirements
- **Report (`report`):** The whole 8D report dictionary — `report_id`, `initiated_date`, `target_completion_date`, `closed_date`, `status` (`"OPEN"` / `"CLOSED"`), `current_discipline` (`"D0"`..`"D8"`), `root_cause_validation`, and the optional discipline records `d0` through `d8`. Pass the entire dict; the tools validate it at the trust boundary and reject a malformed report with a clean error rather than a verdict-shaped placeholder.
- **Discipline records (optional, nested in `report`):** An absent discipline is a normal in-progress state, not an error. `d3` may carry `linked_ncr_validation` (`is_valid`, `record_count`, `findings`); `d4` carries `candidate_causes_tested`, `root_cause`, and `escape_point`; `d7` carries the documentation updates whose `target` declares the D4 finding they address.
- **Transition target (`target`):** A single 8D state string — `"D0"`..`"D8"` or `"CLOSED"`. Required and non-empty for `advance_8d`. One target per call.
- **Canvas options (optional):** `theme` (`"dark"` / `"light"`), `standalone`, `title`.

### Prerequisites
- Active `quality-mcp` server connection providing `validate_8d`, `advance_8d`, and `render_8d_canvas` tools.

## Step-by-Step Methodology
Follow the 5-step 8D report methodology:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    5-STEP 8D REPORT METHODOLOGY                         │
├───────────────────────────────────┬─────────────────────────────────────┤
│ 1. Report State Intake            │ Load the caller's whole report dict │
│ 2. Whole-Report Validation        │ Execute validate_8d on MCP          │
│ 3. Single Transition Attempt      │ Execute advance_8d on MCP           │
│ 4. Carry The Report Forward       │ Reuse result["report"] verbatim     │
│ 5. Canvas & Traceable Reporting   │ Render via render_8d_canvas         │
└───────────────────────────────────┴─────────────────────────────────────┘
```

### 1. Step 1: Report State Intake
- Obtain the caller's whole 8D report dictionary and pass it unchanged. Every tool here takes the entire report, not a discipline fragment.
- Leave an unstarted discipline absent rather than inventing an empty record; an absent discipline is reported as not started, and a fabricated one changes the verdict.
- If no report exists yet, `validate_8d(report=None)` and `advance_8d(report=None, target=...)` load the platform's **benchmark sample report** so the payload shape can be explored. *Strict Invariant:* The benchmark sample is a stand-in for exploration only. Never present its `state`, `verdict`, `gate_reasons`, or either `closeable` flag to a user as their own report's status.

### 2. Step 2: Whole-Report Validation
- Invoke `validate_8d` on `quality-mcp` with the report. Read, in this order: `verdict`, `state`, `closeable`, `gate_reasons`, `d8.closeable`, then the per-discipline results `d0`, `d1`, `d2`, `d3`, `d5`, `d6`, `d7`, `d8`.
- *Strict Invariant:* Never compute, infer, or adjust a `verdict`, a `closeable` flag, or a gate reason by reading the report's own fields. All adjudication must execute through `validate_8d`, and every verdict, flag, and reason reported to a user must be quoted from its returned payload.
- *Strict Invariant:* Report both `closeable` flags, distinctly labelled — `result["closeable"]` is the whole-report gate (`PDD-8D-008` included) and `result["d8"]["closeable"]` is closure evidence only. Never substitute one for the other.
- There is **no `d4` key** in this payload, deliberately: D4 validation needs the raw 5-Why chains, which the report does not persist. Do not claim `result["d4"]` exists. D4's closure-relevant answer arrives as a `ROOT_CAUSE_REJECTED` / `ROOT_CAUSE_EVIDENCE_MISSING` gate reason with `rule_id: "RULE-8D-GATE-CLOSURE"`.
- *Strict Invariant:* Never author, draft, or suggest a root cause, an escape point, or a corrective action. Causal work is the `5why-root-cause` skill's `validate_5why`; this skill reads verdicts only.
- For every finding quoted, read its `citation_basis` and phrase accordingly: `"RULE"` — the Ford Global 8D Manual or AIAG CQI-20 requires it, cited by the named `RULE-8D-*` row; `"PDD"` — this platform's own design decision requires it, and no manual clause does; `"PLATFORM_UNCITED"` — state plainly that no citation backs this finding.

### 3. Step 3: Single Transition Attempt
- Invoke `advance_8d` on `quality-mcp` with the report and exactly **one** `target`, the adjacent next state.
- *Strict Invariant:* Never advance past a blocked gate. On `verdict: "BLOCKED"`, report every entry in `reasons` verbatim — `code`, `message`, and `rule_id` — and stop. Do not retry a different `target` to route around the gate, do not edit report fields to satisfy it, and do not tell the user the report may proceed or close when it may not.
- A non-adjacent or illegal `target` is a **normal result**, not a tool failure: `verdict: "BLOCKED"` with a single `ILLEGAL_TRANSITION` reason whose `rule_id` is `null`. Report it as an adjacency fact with no citation behind it.
- `advance_8d` evaluates only the gates belonging to the transition attempted. It is not a second opinion on `validate_8d`'s whole-report `closeable` flag, and an `ADVANCED` verdict never licenses reporting a report as closeable while `gate_reasons` is non-empty.

### 4. Step 4: Carry The Report Forward
- **The MCP server persists nothing between calls.** On `verdict: "ADVANCED"`, the advanced report exists only inside `result["report"]`.
- *Strict Invariant:* Pass `result["report"]` — verbatim, unedited — as the `report` argument of the next `validate_8d`, `advance_8d`, or `render_8d_canvas` call. A host that assumes server-side state, or that reconstructs the report by hand, silently loses the advance and reports a stale state.
- Never hand-edit a returned report to change a verdict. The only legitimate edits are the caller's own new evidence, supplied deliberately and then re-validated through `validate_8d`.

### 5. Step 5: Canvas & Traceable Reporting
- Invoke `render_8d_canvas` on `quality-mcp` with the already-obtained or already-advanced report — never with a hand-edited or re-derived one.
- The canvas performs no adjudication of its own: it calls `validate_8d` once and returns that payload unmodified under `validation`. The two flags stay at distinct paths here too — `result["closeable"]` (whole-report) and `result["validation"]["d8"]["closeable"]` (closure evidence).
- Retain every tool payload alongside the rendered canvas so each stated verdict, gate reason, and citation remains traceable to the call that produced it.

## Tool Invocations

### `validate_8d`
- **MCP Server:** `quality-mcp`
- **Purpose:** Validate a whole 8D report read-only: every discipline engine plus every closure gate. Returns the core `EightDValidationResult.to_dict()` verbatim. Computes the whole-report closure gate and the per-discipline verdicts; asserts no standard of its own beyond the `RULE-8D-*` rows the engines already cite.
- **Parameters:**
  - `report` (`dict[str, Any] | null`, optional, default `null`): The whole 8D report dictionary — `report_id`, `status`, `current_discipline`, `root_cause_validation`, and the optional `d0`-`d8` discipline records. When omitted or `null`, the benchmark sample report is loaded.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `verdict` (`string`): `"ACCEPT"`, `"WARNING"`, or `"REJECT"` over the gates and every discipline result combined.
  - `valid` (`boolean`): Whether the report is advisory-clean.
  - `state` (`string`): Current 8D state, `"D0"`..`"D8"` or `"CLOSED"`.
  - `closeable` (`boolean`): **Whole-report** closure gate — exactly `gate_reasons == []`, the D3-to-D4 linked-NCR gate (`PDD-8D-008`) included.
  - `gate_reasons` (`list[dict]`): Blocking reasons, each `{code, message, rule_id}`. `rule_id` is a `RULE-8D-*` id, a `PDD-8D-*` id, or `null`.
  - `d0`, `d1`, `d2`, `d3`, `d5`, `d6`, `d7` (`dict | null`): Per-discipline results, `null` when the discipline is not recorded. Each carries `basis`, `valid`, `verdict`, discipline-specific facts, `findings` (each with `code`, `severity`, `message`, `recommendation`, `citation_basis`), and `recommendations`.
  - `d8` (`dict`): The D8 closure result, **never `null`**, carrying its own `closeable` — the **closure-evidence-only** flag — plus `d8_recorded`, `documentation_reviewed`, `linked_five_why_verdict`, `findings`, `recommendations`.
  - **No `d4` key.** D4's closure-relevant signal is a `ROOT_CAUSE_REJECTED` / `ROOT_CAUSE_EVIDENCE_MISSING` gate reason instead.
  - `report` (`dict`): The validated report as a JSON-mode dict.

---

### `advance_8d`
- **MCP Server:** `quality-mcp`
- **Purpose:** Evaluate **one** hypothetical adjacent 8D transition against the supplied report. Returns the core `EightDTransitionResult.to_dict()` verbatim. **Stateless:** nothing is advanced server-side; the would-be new report is returned in `result["report"]` and the calling host must carry it forward.
- **Parameters:**
  - `report` (`dict[str, Any] | null`, optional, default `null`): The whole 8D report to evaluate the transition against. When omitted or `null`, the benchmark sample report is loaded.
  - `target` (`string`, required, default `""`): The target state — `"D0"`..`"D8"` or `"CLOSED"`. Must be non-empty. A non-adjacent target is a normal `BLOCKED` result, not an error.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `verdict` (`string`): `"ADVANCED"` or `"BLOCKED"`.
  - `previous_state` (`string`): State before the attempted transition.
  - `state` (`string`): Resulting state; unchanged from `previous_state` when `BLOCKED`.
  - `reasons` (`list[dict]`): Blocking reasons, each `{code, message, rule_id}`. Empty on `ADVANCED`. `rule_id` is one of the manual-backed gate ids (`RULE-8D-GATE-CONTAINMENT`, `RULE-8D-GATE-PREVENTION`, `RULE-8D-GATE-CLOSURE`), a `PDD-8D-*` id (platform decision), or `null` for `ILLEGAL_TRANSITION`.
  - `report` (`dict`): The resulting report as a JSON-mode dict — **the host must carry this forward.**

---

### `render_8d_canvas`
- **MCP Server:** `quality-mcp`
- **Purpose:** Render one already-validated 8D report as a themed HTML canvas: the closure-gate panel plus one card per discipline D0-D8. It re-adjudicates nothing — it calls `validate_8d` once and returns that payload unmodified under `validation`.
- **Parameters:**
  - `report` (`dict[str, Any] | null`, optional, default `null`): The whole 8D report to render. When omitted or `null`, the benchmark sample report is loaded.
  - `theme` (`string`, optional, default `"dark"`): Colour theme, `"dark"` or `"light"`.
  - `standalone` (`boolean`, optional, default `true`): `true` returns a standalone HTML5 document; `false` returns an embeddable container.
  - `title` (`string`, optional, default `"8D Problem Solving Canvas"`): Canvas header title. Must be non-empty.
- **Return Type:** `dict[str, Any]`
- **Return Schema:**
  - `title` (`string`): The canvas title.
  - `verdict` (`string`), `state` (`string`): Hoisted from `validation`, unchanged.
  - `closeable` (`boolean`): Hoisted **whole-report** gate. The closure-evidence-only flag is reachable **only** at `validation["d8"]["closeable"]`; the two are never collapsed onto one name.
  - `validation` (`dict`): The full `validate_8d(...)` payload, unmodified.
  - `html` (`string`): The rendered HTML string.

---

### Example 1: The Two `closeable` Flags Disagree

An 8D report at D8 whose D3 record states that its linked Nonconformance Record evidence was validated and found **invalid**. The D8 closure evidence itself is complete.

#### Step 2 Invocation — `validate_8d`
```json
{
  "name": "validate_8d",
  "arguments": {
    "report": "<the caller's whole 8D report dict, report_id 8D-2026-0042, passed unchanged>"
  }
}
```

#### Rejection Response (per-discipline results abridged; `report` echo omitted)
```json
{
  "verdict": "REJECT",
  "valid": false,
  "state": "D8",
  "closeable": false,
  "gate_reasons": [
    {
      "code": "LINKED_NCR_INVALID",
      "message": "The linked Nonconformance Record evidence is invalid: NCR-2026-311 has no disposition recorded.. Correct the linked Nonconformance Record evidence and re-record its validation outcome before advancing.",
      "rule_id": "PDD-8D-008"
    }
  ],
  "d3": {
    "basis": "Ford Global 8D / AIAG CQI-20",
    "valid": true,
    "verdict": "REJECT",
    "containment_verified": true,
    "action_count": 1,
    "linked_ncr": null,
    "linked_ncr_validation": {"is_valid": false, "record_count": 2, "findings": ["NCR-2026-311 has no disposition recorded."]},
    "findings": [
      {
        "code": "LINKED_NCR_INVALID",
        "severity": "error",
        "action_description": null,
        "message": "The linked Nonconformance Record evidence is invalid: NCR-2026-311 has no disposition recorded..",
        "recommendation": "Correct the linked Nonconformance Record(s) so they satisfy quality_core.ncr.schema.validate_ncr before this containment record can be accepted.",
        "citation_basis": "PDD"
      }
    ],
    "recommendations": ["Correct the linked Nonconformance Record(s) so they satisfy quality_core.ncr.schema.validate_ncr before this containment record can be accepted."]
  },
  "d8": {
    "basis": "Ford Global 8D / AIAG CQI-20",
    "valid": true,
    "verdict": "ACCEPT",
    "d8_recorded": true,
    "documentation_reviewed": true,
    "linked_five_why_verdict": "ACCEPT",
    "closeable": true,
    "findings": [
      {
        "code": "D8_READY",
        "severity": "info",
        "message": "D8 is recorded, its documentation is reviewed, and the whole-report closure evidence is complete.",
        "recommendation": "D8 is complete; the report may be closed.",
        "citation_basis": "PLATFORM_UNCITED"
      }
    ],
    "recommendations": ["D8 is complete; the report may be closed."]
  }
}
```

Report **both** flags, distinctly labelled, and never one in place of the other: the whole-report gate came back `closeable: false`, and the closure-evidence-only flag came back `d8.closeable: true`. Quote the returned `verdict` of `"REJECT"` and the single `gate_reasons` entry verbatim, including its `rule_id` of `"PDD-8D-008"` — and say in those words that this refusal is **this platform's own design decision, not a Ford Global 8D Manual or AIAG CQI-20 clause**, because the `PDD-` prefix says so. The D3 finding's `citation_basis` is likewise `"PDD"`; the D8 `D8_READY` finding's is `"PLATFORM_UNCITED"`, so report that one as carrying no citation at all. Do not reconcile the two flags in prose, do not average them, and do not conclude that the report is closeable because D8 is complete.

---

### Example 2: Negative Control — A Blocked Gate Is Not Routed Around

The same report, sitting at D3, attempting to advance to D4.

#### Step 3 Invocation — `advance_8d`
```json
{
  "name": "advance_8d",
  "arguments": {
    "report": "<the same whole report dict, current_discipline D3>",
    "target": "D4"
  }
}
```

#### Blocked Response (`report` echo omitted)
```json
{
  "verdict": "BLOCKED",
  "previous_state": "D3",
  "state": "D3",
  "reasons": [
    {
      "code": "LINKED_NCR_INVALID",
      "message": "The linked Nonconformance Record evidence is invalid: NCR-2026-311 has no disposition recorded.. Correct the linked Nonconformance Record evidence and re-record its validation outcome before advancing.",
      "rule_id": "PDD-8D-008"
    }
  ]
}
```

**Correct agent behaviour.** Report the returned `verdict` of `"BLOCKED"`, quote the single `reasons` entry verbatim with its `code`, `message`, and `rule_id`, state that `PDD-8D-008` is this platform's own design decision and carries no manual clause, and **ask the user to correct the linked Nonconformance Record evidence and re-record its validation outcome**. Then stop. `state` came back unchanged at `"D3"` — the report did not move.

**The behaviour this negative control rules out.** Calling `advance_8d` again with `target: "D5"` or `"CLOSED"` to get past D4; editing `d3.linked_ncr_validation.is_valid` to `true` so the gate passes; or telling the user the report may proceed because D8's evidence is complete. A gate reason is the answer, not an obstacle to work around — the correct next move is a question to the user, not another tool call with a different target.

---

### Example 3: An Uncited Refusal — `rule_id: null`

A non-adjacent target on the same report. This is a normal result, not a tool failure.

#### Invocation — `advance_8d`
```json
{
  "name": "advance_8d",
  "arguments": {
    "report": "<a whole report dict at D8>",
    "target": "D2"
  }
}
```

#### Blocked Response (`report` echo omitted)
```json
{
  "verdict": "BLOCKED",
  "previous_state": "D8",
  "state": "D8",
  "reasons": [
    {
      "code": "ILLEGAL_TRANSITION",
      "message": "Transition from D8 to D2 is not an allowed adjacent 8D step.",
      "rule_id": null
    }
  ]
}
```

Report the returned `verdict`, quote the `message`, and — because `rule_id` came back `null` — state plainly that this is the state machine's own adjacency fact with **no citation behind it**. Do not attribute it to the Ford Global 8D Manual, to AIAG CQI-20, or to any `RULE-8D-*` row: the engine reports an uncited fact as uncited, and so must the agent. `D8` transitions only to `CLOSED`; if the user needs to revisit D2, that is a question for them, not a target to keep guessing at.

## Best Practices
1. **Strict Invariant: Zero Inline Math / Zero Inline Adjudication.** Never decide a discipline `verdict`, a `closeable` flag, or a gate outcome inline from reading report fields — always delegate to `validate_8d` and quote its payload. Never decide whether a transition is allowed — always delegate to `advance_8d` and quote its `verdict` and `reasons`. **Never author, draft, or suggest a root cause, escape point, or corrective action** — D4 causal work belongs to the `5why-root-cause` skill's `validate_5why`, and this skill reads only the already-computed verdict. **Never advance past a blocked gate** — report every `gate_reasons` / `reasons` entry with its `rule_id` and stop, rather than retrying another `target` or editing the report to force a pass. **Never present a `PDD-8D-*` id or a `PLATFORM_UNCITED` finding as a Ford Global 8D or AIAG CQI-20 requirement** — read `citation_basis` and `rule_id` and phrase from those fields, not from the wording of a message.
2. **Two Closeable Flags, Two Questions.** `result["closeable"]` is the whole-report gate (`gate_reasons == []`, `PDD-8D-008` included); `result["d8"]["closeable"]` is closure evidence only. Report both, labelled, whenever either is mentioned. They disagree legitimately, and collapsing them is how a user is told a report may close when it may not.
3. **Carry The Report Forward.** The server persists no state. After any `ADVANCED` result, pass `result["report"]` verbatim into the next call. Reconstructing the report by hand, or assuming the server remembers, silently loses work.
4. **Cite By Field, Not By Tone.** `RULE-8D-*` means an on-box manual quote in `CITATIONS.tsv` — for example `RULE-8D-GATE-CONTAINMENT` behind `CONTAINMENT_NOT_VERIFIED`, `RULE-8D-GATE-PREVENTION` behind `PREVENTION_UPDATE_MISSING`, and `RULE-8D-GATE-CLOSURE` behind the root-cause closure reasons. `PDD-8D-*` means a numbered Process Design Decision in `ASSUMPTIONS_LOG.md` and no manual clause. `null` / `PLATFORM_UNCITED` means no citation exists; say so.
5. **The Benchmark Sample Is Not The User's Report.** A `report=None` call loads the platform's sample so the payload shape can be explored. Never report its state, verdict, gates, or flags as the user's own.
6. **Absent Is Not Empty, And `d4` Does Not Exist.** An unrecorded discipline comes back `null` and is reported as not started — never as a failing or empty record. `validate_8d` returns no `d4` key by design; do not claim one, and read D4's closure-relevant answer from the `ROOT_CAUSE_REJECTED` / `ROOT_CAUSE_EVIDENCE_MISSING` gate reason instead.
7. **Verbatim Reasons.** Surface each finding's and gate reason's own `message` and `recommendation` text unchanged rather than re-explaining, summarising, or softening it — the owning engine's wording is the record.

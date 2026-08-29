# Changelog

All notable changes to **Engine-Powered Quality Engineering Skills** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions are milestone-driven, not date-driven — see [`ROADMAP.md`](ROADMAP.md).

## [Unreleased]

### Added
- FMEA live-formula Excel exporter `quality_core.io.export_fmea` (`export_fmea_workbook`,
  `benchmark_fmea_dataset`), the first domain exporter built on the E1 core. The RPN column
  is the only live cell — a real `=S*O*D` formula referencing that row's own Severity /
  Occurrence / Detection cells, so editing a rating in Excel recalculates RPN instead of
  reading a stale number; its `<f>` element is proven by `assert_cell_is_formula`, with a
  hardcoded-literal build as the negative control. The Action Priority column is a
  structured lookup value from `quality_core.scoring.action_priority` (not a formula, and
  never re-derived here), and every free-text field stays inert through the unchanged
  `sanitize_cell` escaping. Column letters are derived from `FMEA_EXPORT_COLUMNS` rather
  than hand-typed, and rows export in `dataset.rows` order, never re-sorted (#142).
- Live-formula SPC Excel exporter in `quality_core.io.export_spc` (`export_spc_excel`,
  `export_spc_to_workbook`) supporting all 6 AIAG SPC Shewhart variable (`Xbar-R`, `Xbar-S`, `I-MR`)
  and attribute (`p`, `c`, `u`) control chart types with live formulas for subgroup means, ranges,
  standard deviations, moving ranges, defect proportions, rates, centerlines, and control limits;
  process capability studies (`Cp`, `Cpk`, `Pp`, `Ppk`, process mean, overall dispersion, within-subgroup
  dispersion); and run-rule violation findings and metadata tables, re-exported in `quality_core.io` (#143).
- Control Plan live-formula Excel exporter `quality_core.controlplan.export`
  (`export_controlplan_workbook`, `benchmark_controlplan_dataset`), a two-sheet workbook
  built on the E1 core. It lives in the domain package, not beside the `quality_core.io`
  primitives it consumes: `controlplan.schema` already imports `io` for the ingest
  boundary, and `io` sits structurally below every domain engine, so an exporter inside
  `io` would close that arrow into an import cycle. The matrix sheet carries every `ControlPlanRow` field as plain
  sanitized data plus two derived `"Yes"`/`"No"` display columns
  (`Sample_Plan_Placeholder`, `PFMEA_Linked`); the only live cells in the workbook are the
  three linkage roll-ups on a dedicated `Coverage` sheet, at fixed addresses that never
  move with the row count — `B2` `=COUNTA(...)` (total characteristics), `B3`
  `=COUNTIF(...,"Yes")` (linked characteristics) and `B4` `=IF(B2=0,0,B3/B2)` (coverage,
  rendered `0.0%`), whose `IF` guard is unconditional so an empty dataset shows `0` rather
  than `#DIV/0!`. "Linked" here is *declared* linkage (`source_cause_id is not None`), a
  deliberately weaker claim than `validate_pfmea_linkage`'s *validated* linkage, which
  needs a `RelationalFMEA` an exporter does not have. The `<f>` elements are proven by
  `assert_cell_is_formula`, with a hardcoded-literal build as the negative control and an
  injection-safety control showing a free-text `"="` payload stays apostrophe-escaped
  while the same workbook's roll-ups stay live and correct; recorded as RULE 4 in
  `controlplan/ASSUMPTIONS_LOG.md`, which adds no citation (elementary counting). Column
  letters are derived
  from `CONTROLPLAN_EXPORT_COLUMNS` rather than hand-typed, and rows export in
  `dataset.rows` order, never re-sorted (#145).
- Shared live-formula Excel export core in `quality_core.io`: a `Formula` marker type
  (formula string + optional number format) and `write_formula_cell()`, which write a real
  OOXML `<f>` element instead of a cached literal so exported workbooks recalculate in Excel.
  `write_table_sheet` recognises `Formula`-valued cells and writes them live; every other
  cell still goes through the unchanged `sanitize_cell` escaping, so the opt-in is the
  call site's *type*, never the data's content — an untrusted `"=1+1"` string stays
  apostrophe-prefixed inert. Ships with a reusable `tests/_xlsx_formula_audit.py`
  `<f>`-presence verifier (raw-XML, sheet resolved via `workbook.xml` rels) and its
  negative control proving it fails on a hardcoded literal (#141).
- Backfilled co-located `ASSUMPTIONS_LOG.md` standards declarations for every previously
  uncovered `quality_core` module, closing the E0 audit gap (#140): `io/` (RULE-IO-001/002 —
  `FORMULA_PREFIXES` is an OWASP CSV-injection convention, not a licensed standard),
  `schema/` (RULE-SCHEMA-001 — AIAG/VDA S/O/D placement is structural, not a scored
  constant), `canvas/` and `theme/` (presentation-only `NO-STANDARD-DECLARATION`s), plus
  co-located `scoring_ASSUMPTIONS_LOG.md` (RULE-SCORING-001..003 — AIAG-VDA 2019 Action
  Priority table, RPN, 1–10 scale) and `spc/ASSUMPTIONS_LOG.md` (RULE-SPC-001..004 —
  chart constants, WE/Nelson run-rules, capability stability gate) (#140).
- The one genuinely-missing per-domain citation test `tests/test_copq_citations.py` (COPQ had
  manifest rows but no verifying test), sharing a new non-collected `tests/_citation_audit.py`
  helper. COPQ's declared sources are PDF-only, so its rows are bound to the log per row
  (`assert_manifest_rows_present_in_log`) — corrupting any single COPQ citation fails on every
  machine, without needing a manual — while manual line-matching stays skip-safe (#140).
- Package-wide anti-vacuity meta-test `tests/test_citation_coverage.py`: every engine module
  carries an assumptions log, every non-empty `CITATIONS.tsv` is referenced by a verifying
  test, and every empty/absent manifest must carry an explicit `NO-STANDARD-DECLARATION` or
  `PROCUREMENT-GAP` token — an empty manifest can no longer pass silently (#140).
- Negative-control self-test `tests/test_citation_audit_selftest.py` proving the citation
  matcher and the log↔manifest blockquote binding are load-bearing without a licensed manual
  present: a corrupted quote, a wrong line, and an unbacked blockquote each fail (#140).
- Explicit `PROCUREMENT-GAP` declarations recording, honestly rather than by vacuity, that
  the AIAG-VDA FMEA Handbook (scoring), the AIAG SPC / WE / Nelson manuals (spc), and the
  ISO 9001 §8.4/§10.2 + IATF 16949 §8.4 excerpts (sqe) are not on-machine, so their verbatim
  citation rows are deferred to an E0 follow-up once the manuals are provisioned (#140).

### Fixed
- Repointed the stale module-docstring citation in `quality_core.spc.stability` from the
  nonexistent `docs/ASSUMPTIONS_LOG.md RULE 7` to the real `spc/ASSUMPTIONS_LOG.md
  RULE-SPC-004` (#140).

## [0.9.0] - 2026-08-28

### Added
- Finalized Milestone 9 documentation in `docs/milestones/v0.9.0.md` with complete verification artifacts, retrospective, and test evidence for Epics E0–E11 (#125).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.9.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.9.0.md` (#125).
- Updated `README.md` milestone status table marking `v0.9.0` as Completed with `docs/milestones/v0.9.0.md` link and advancing `v1.0.0` to Up Next (#125).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v0.9.0` traceability assertions across all 12 task issues (#114–#125), release gate criteria, verification artifacts, and negative mutation controls (#125).
- Synchronized workspace version bump to `0.9.0` across root `pyproject.toml`, `packages/quality-core`, `packages/quality-mcp`, and `uv.lock` (#125).
- In-process FastMCP client-server round-trip suite `packages/quality-mcp/tests/test_sqe_client_roundtrip.py` proving three-way payload parity (`structuredContent` == serialized text == direct `quality_core.sqe` engine call) across all six [E8] #122 SQE tools, session error isolation, cross-domain non-contamination against the eight previously-shipped domains, all three no-standard-implied/commercial-authority/root-cause-authorship invariants at the wire, and the chained NCR → SCAR workflow proving [E6] #120's cross-engine evidence linkage end-to-end: a validated nonconformity yields an `ISSUABLE` SCAR, and an injected-defect nonconformity yields `EVIDENCE_INVALID` with `quality_core.ncr`'s findings surfaced verbatim and the SCAR held out of `ISSUABLE`. Updates `docs/mcp-client-setup.md` with six new verified SQE JSON-RPC transcripts and an NCR → SCAR sequence diagram, and backfills the missing #107 PPAP documentation (five verified PPAP transcripts plus a Control Plan → PPAP sequence diagram) (#124).
- FastMCP tools for Supplier Quality Engineering (SQE) in `quality_mcp.tools.sqe` (`calculate_supplier_ppm`, `calculate_otif`, `calculate_vendor_scorecard`, `evaluate_escalation`, `generate_scar`, `render_sqe_canvas`), registered on `quality-mcp` server, `render_sqe_canvas` re-exported in `quality_mcp.tools.canvas` and `quality_mcp`, enforcing deterministic JSON dictionary returns, typed parameter annotations, benchmark dataset fallbacks, per-call standards-basis echoing, the no-standard-implied / commercial-authority / root-cause-authorship invariants (verified against both payloads and tool descriptions), and input type guards (#122).
- Supplier Corrective Action Request (SCAR) & Vendor Rating domain skill in `skills/supplier-scar/SKILL.md` adhering to agentskills.io standard with 5 mandatory H2 sections, a `### <tool>` block for each of the six [E8] #122 SQE tools (`calculate_supplier_ppm`, `calculate_otif`, `calculate_vendor_scorecard`, `evaluate_escalation`, `generate_scar`, `render_sqe_canvas`), two worked examples with the second a zero-receipts `INDETERMINATE` negative control, and Zero Inline Math / Zero Inline Adjudication invariants specialized for supplier quality (heuristic-labelling, commercial-authority, and root-cause-authorship) (#123).
- Extended skills governance test suite `tests/test_skills_conventions.py` with `supplier-scar` discovery, six-tool specification, heuristic-labelling, root-cause-authorship, prose-and-code zero-inline-math, and isolation assertions (#123).
- SQE vendor scorecard canvas controller and themed HTML renderer (`quality_core.canvas.sqe`) with
  evidence-preserving scorecard/escalation matrix display (#121).
- Deterministic supplier escalation tier engine in `quality_core.sqe.escalation`, exposing the full evaluated heuristic trigger set, highest-tier-wins evidence, optional explicit recurrence, and indeterminate-scorecard propagation while preserving commercial authority with people (#119).
- Deterministic vendor scorecard engine in `quality_core.sqe.scorecard` (`calculate_vendor_scorecard`, `ScorecardConfig`, `LinearScoringCurve`, `ScorecardResult`) composing the existing supplier PPM, strict-conjunction OTIF, and optional COPQ percentage-of-revenue engines, emitting A/B/C only when every positively weighted dimension is measured, never redistributing omitted or undecided weights, and labelling all configurable weights, curves, and bands as engineering heuristics with no standards citation (`sqe/ASSUMPTIONS_LOG.md` RULE-SQE-007..010) (#118).
- Deterministic supplier defect-rate engine in `quality_core.sqe.ppm` (`calculate_supplier_ppm`, `PPMConfig`, `PPMResult`) computing PPM (`defective / received × 1,000,000`) and separately-named DPMO over a `SupplierPeriod`'s in-window receipt lots, resolving empty periods, zero received quantity, undecided `defect_count`, and undated matched lots to an `INDETERMINATE` verdict with `ppm=None` (never `0.0`), and labelling the caller-overridable 1000-unit `sample_adequacy_minimum` as a declared engineering heuristic with no standards basis (#116).
- Engineering assumption entries `RULE-SQE-004` (PPM/DPMO arithmetic has no published source), `RULE-SQE-005` (`sample_adequacy_minimum` default of 1000 received units), and `RULE-SQE-006` (INDETERMINATE trigger set for supplier PPM) in `packages/quality-core/src/quality_core/sqe/ASSUMPTIONS_LOG.md`, with no new `CITATIONS.tsv` rows because the engine asserts no standard (#116).
- Scoped Milestone 10 (`v1.0.0` · Production Hardening & Release) in `docs/milestones/v1.0.0.md`: pure hardening on the full 8-domain platform — live-formula Excel exporters (a shared `quality_core.io` core plus one exporter per domain), a full `ASSUMPTIONS_LOG.md`/`CITATIONS.tsv` audit across every module, an end-to-end skill regression, and the `1.0.0` release closeout — decomposed into 12 Epics (E0–E11) filed as GitHub issues #140–#151 on milestone #11, with v0.8.0/v0.9.0 flagged as hard prerequisites and desktop packaging / sha256 audit-hash / local-LLM support held to the v2 backlog (#151).
- Linked `v1.0.0` in the `ROADMAP.md` Summary Release Matrix to `docs/milestones/v1.0.0.md` (#151).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v1.0.0` traceability assertions across all 12 task issues (#140–#151), release gate criteria, verification artifacts, ROADMAP link, and negative mutation controls (#151).
- OTIF & delivery-performance calculator `quality_core.sqe.otif` (`calculate_otif`, `OTIFConfig`, `OTIFResult`) reporting `on_time_pct`, `in_full_pct`, and a strict-conjunction `otif_pct` over one matched-delivery denominator, resolving `INDETERMINATE` for an empty period or any undecided delivery date/quantity rather than imputing one, with all five `OTIFConfig` defaults labelled as declared engineering heuristics carrying no standards citation (`sqe/ASSUMPTIONS_LOG.md` RULE-SQE-001..003) (#117).
- Deterministic SCAR generator `quality_core.sqe.scar` (`generate_scar`, `SCARConfig`, `SCARResult`, `SCARLinkageResult`, `SCARSection`) dispatching linked nonconformity evidence to `quality_core.ncr`, supplier-returned root causes to `quality_core.rca`'s reversible 5-Why validator, and cost impact to `quality_core.copq`, with verdict-affecting `EVIDENCE_VALID`/`EVIDENCE_INVALID`/`EVIDENCE_NOT_SUPPLIED`/`LINKAGE_NOT_AVAILABLE` linkage results surfaced verbatim, a `DRAFT`/`ISSUABLE`/`AWAITING_SUPPLIER_RESPONSE`/`RESPONSE_REJECTED`/`CLOSABLE`/`INDETERMINATE` status state machine, the mandatory root-cause-authorship invariant (this tool requests and validates a supplier root cause, never authors one), and a deferred-by-design, always-`LINKAGE_NOT_AVAILABLE` `vendor_scorecard` slot (the #118 scorecard is on `test`; this SCAR release defers wiring it). Adds `RULE-SQE-011/012/013` to `sqe/ASSUMPTIONS_LOG.md` and their `sqe/CITATIONS.tsv` rows, reusing sources already verified in `rca/CITATIONS.tsv` (#120).
- Reference material procurement and citation scaffold for Milestone 9 SQE suite (`packages/quality-core/src/quality_core/sqe/ASSUMPTIONS_LOG.md`, `sqe/CITATIONS.tsv`, `sqe/__init__.py`) and per-domain reference manual path mapping in `CLAUDE.md` under `## Standards fidelity` covering Supplier Quality (SCAR & Vendor Rating) — ISO 9001:2015 §8.4/§10.2, IATF 16949:2016 §8.4, AIAG CQI-20, and the Ford Global 8D Manual (#114).

### Fixed
- Graduate SQE assumptions log rule guard in `tests/test_sqe_scaffold.py` to match `RULE-SQE-` prefix headings and verify citations or explicit heuristic/honesty declarations, unifying rule section headings and label formatting across all six SQE engineering assumptions in `packages/quality-core/src/quality_core/sqe/ASSUMPTIONS_LOG.md` (#162).
- Unify operator blame and root-cause speculation detection with statement sanitization in `quality_core.ncr.nonconformance`, applying word-boundary and flexible whitespace regexes across the complete 143-combination human noun x blame verb cross-product to eliminate token-pair blame leakage in nonconformance statements (#131).
- Delimit requirement and measured evidence extraction with lookahead boundaries in `quality_core.ncr.nonconformance.write_nonconformance` to preserve decimals, tolerances, and engineering units while eliminating duplicated statement periods and narrative keyword leakage (#132).
- Enforce safety-critical disposition gate precedence over supplier-origin defects in `quality_core.ncr.recommend_disposition` per IATF 16949:2016 §8.7.1.7, preventing non-reworkable supplier defects from bypassing Material Review Board review, mandatory scrap defacing directives, and safety officer approval authority (#133).
- Fall back to dataset `revenue_base` in `quality_core.copq.estimator.estimate_copq` when `items` is passed as a `COPQDataset` (or validated dataset structure) and no explicit `revenue_base` argument is provided, narrow `items` parameter type annotation, differentiate unprovided versus zero `revenue_base` with dedicated warning/recommendation messaging, separate `title` validation into `TypeError` / `ValueError`, and emit structured warnings for conflicting alias parameter values (#134).

## [0.8.0] - 2026-08-28

### Added
- Finalized Milestone 8 documentation in `docs/milestones/v0.8.0.md` with complete verification artifacts, retrospective, and test evidence for Epics E0–E12 (#110).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.8.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.8.0.md` (#110).
- Updated `README.md` milestone status table marking `v0.8.0` as Completed with `docs/milestones/v0.8.0.md` link and advancing `v0.9.0` to Up Next (#110).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v0.8.0` traceability assertions across all 13 task issues (#98–#110), release gate criteria, verification artifacts, and negative mutation controls (#110).
- Synchronized workspace version bump to `0.8.0` across root `pyproject.toml`, `packages/quality-core`, `packages/quality-mcp`, and `uv.lock` (#110).
- In-process FastMCP client-server round-trip suite `packages/quality-mcp/tests/test_ppap_client_roundtrip.py` proving three-way payload parity (`structuredContent` == serialized text == direct `quality_core.ppap` / `quality_core.canvas.ppap` engine call) across all five [E5] #107 PPAP tools (`audit_ppap_package`, `lookup_ppap_requirement`, `validate_psw`, `assess_ppap_capability`, `render_ppap_canvas`), session error isolation asserted in both directions (in-session and against a fresh session), cross-domain non-contamination against RCA (`validate_5why`) and SPC (`calculate_spc_chart`), the Section 5 Customer Authority Invariant asserted at the wire (no serialized payload ever carries `Approved` / `Interim Approval` / `Rejected` as a verdict, and the reservation is declared rather than merely absent), and the chained Control Plan → PPAP workflow proving [E4] #105's cross-engine element linkage end-to-end in a single session: a control plan that passes `quality_core.controlplan` validation is threaded by the client into the §2.2.7 `EvidenceItem` as `evidence_valid=True` and resolves `SUBMITTED` per the Table 4.1 Level 3 code, while the same plan carrying a tolerance violation (`usl` ≤ `lsl`) fails validation, is threaded as `evidence_valid=False`, resolves `EVIDENCE_INVALID` with the controlplan engine's own findings surfaced verbatim in the §2.2.7 rationale, and drives the package to `NOT_READY` (#109).
- AIAG PPAP (4th Edition) 18-element completeness, Table 4.1 requirement lookup, Part Submission Warrant (PSW) 27-field validation, and Initial Process Study capability assessment domain skill in `skills/ppap-checker/SKILL.md` adhering to the agentskills.io standard with 5 mandatory H2 sections, worked examples, Section 5 Customer Authority Invariant enforcement, and strict Zero Inline Math / Zero Inline Adjudication routing to quality-mcp tools (#108).
- Updated `skills/README.md` taxonomy table marking `ppap-checker` as Active (#108).
- FastMCP tools for AIAG Production Part Approval Process (PPAP) 4th Edition in `quality_mcp.tools.ppap` (`audit_ppap_package`, `lookup_ppap_requirement`, `validate_psw`, `assess_ppap_capability`, `render_ppap_canvas`), registered on `quality-mcp` server, re-exported in `quality_mcp.tools.canvas` and `quality_mcp`, enforcing deterministic JSON dictionary returns, typed parameter annotations, benchmark dataset fallbacks, Section 5 Customer Authority Invariant, and input type guards (#107).
- Single-writer visual Production Part Approval Process (PPAP) canvas controller `PPAPCanvas` and `PPAPCanvasElement` dataclass in `quality_core.canvas.ppap` supporting the 18-element AIAG PPAP 4th Edition checklist, Table 4.1 Submission Levels 1–5 requirement matrix, active level column highlighting, evidence status tracking with undecided sentinel, benchmark automotive sample dataset (`SAMPLE_PPAP_ELEMENTS`, `SAMPLE_PPAP_PACKAGE`, `load_sample_ppap_canvas`), applicability and audit synchronization, dark/light themed HTML matrix rendering (`render_ppap`), and strict enforcement of the Section 5 Customer Authority Invariant (#106).
- Cross-engine element linkage engine (`packages/quality-core/src/quality_core/ppap/linkage.py`) connecting AIAG PPAP 4th Edition element requirements to underlying quality-core engines: §2.2.6 Process FMEA -> `quality_core.scoring` (Action Priority lookup with integer 1..10 bounds checking), §2.2.7 Control Plan -> `quality_core.controlplan.schema` (`ControlPlanDataset` validation), §2.2.8 Measurement System Analysis -> `quality_core.msa.gage_rr` (Gage R&R %GRR $\le 30.0\%$ and $ndc \ge 5$ acceptance bands), and §2.2.11 Initial Process Studies -> `quality_core.ppap.process_study` ($P_{pk}/C_{pk}$ capability evaluation and stability gating), with downward-only import hierarchy, zero duplicated threshold constants, verdict-affecting negative controls, and cross-edition engine composition declaration in `ASSUMPTIONS_LOG.md` (#105).
- Part Submission Warrant (PSW) 27-field form validator, field-by-field completeness auditor, conditional validation rules, blanket statement heuristics, cross-consistency checks, and customer authority invariant enforcement in `packages/quality-core/src/quality_core/ppap/psw.py` and `packages/quality-core/src/quality_core/ppap/__init__.py` (#104).
- Initial Process Studies capability gate (`packages/quality-core/src/quality_core/ppap/process_study.py`) evaluating statistical capability/performance against AIAG PPAP 4th Edition §2.2.11 acceptance criteria (Table 2.2.11.3 $P_{pk}/C_{pk}$ bands $> 1.67$, $1.33 \le \text{Index} \le 1.67$, and $< 1.33$), stability gates with Western Electric out-of-control rule detection from `quality_core.spc`, attribute data guard rejecting count/binary data from variables indices (§2.2.11.1 Note 2), sample size threshold enforcement ($n \ge 100$ readings across $\ge 25$ subgroups per §2.2.11.1 Note 5), verbatim standard-prescribed actions for all verdicts, and precomputed evaluation modes (#103).
- Deterministic 18-element completeness auditor (`quality_core.ppap.auditor.audit_ppap_package`), supplier submission readiness verdicts (`SUBMISSION_READY`, `NOT_READY`, `INDETERMINATE`), strict Section 5 Authority Invariant enforcement, zero duplicated standards data composition, and comprehensive engine and scorecard test suites (#102).
- Element-by-element applicability evaluation engine and Submission Level 4 indeterminacy gate per AIAG PPAP 4th Edition in `packages/quality-core/src/quality_core/ppap/applicability.py` and `packages/quality-core/src/quality_core/ppap/__init__.py` (#101).
- Encoded the AIAG PPAP 4th Edition (June 2006) Section 4 Table 4.1 submission levels and Table 4.2 retention/submission 18-element matrix in `quality_core.ppap.table_4_1` as immutable cited data, implemented lookup helpers (`lookup_requirement`, `requirement_legend`, `elements_required_at_level`, `submission_level_description`), documented RULE 1 in `ASSUMPTIONS_LOG.md` backed by line-pinned `CITATIONS.tsv` entries, and added unit test suite `test_table_4_1.py` and citation verification suite `test_ppap_citations.py` (#100).
- Canonical AIAG PPAP 4th Edition 18-element domain model, Submission Levels 1–5, PSW Field 18 Reason for Submission vocabulary, evidence availability states with undecided sentinel, `EvidenceItem` and `PPAPPackage` models, `PPAP_PACKAGE_SCHEMA` `TableSchema`, and `load_ppap_csv` / `validate_ppap` trust-boundary ingest helpers with column aliasing in `packages/quality-core/src/quality_core/ppap/schema.py` and `packages/quality-core/src/quality_core/ppap/__init__.py` (#99).
- Core coverage gate in `.github/workflows/ci.yml` extended with `--cov=quality_core.ppap` and verified at 100% line & branch coverage (#99).
- Canonical AIAG PPAP 4th Edition 18-element domain model, Submission Levels 1–5, PSW Field 18 Reason for Submission vocabulary, evidence availability states with undecided sentinel, `EvidenceItem` and `PPAPPackage` models, `PPAP_PACKAGE_SCHEMA` `TableSchema`, and `load_ppap_csv` / `validate_ppap` trust-boundary ingest helpers with column aliasing in `packages/quality-core/src/quality_core/ppap/schema.py` and `packages/quality-core/src/quality_core/ppap/__init__.py` (#99).
- Core coverage gate in `.github/workflows/ci.yml` extended with `--cov=quality_core.ppap` and verified at 100% line & branch coverage (#99).
- Reference material procurement and citation scaffold for Milestone 8 PPAP suite (`packages/quality-core/src/quality_core/ppap/ASSUMPTIONS_LOG.md`, `ppap/CITATIONS.tsv`, `ppap/__init__.py`) and per-domain reference manual path mapping in `CLAUDE.md` under `## Standards fidelity` covering PPAP — AIAG PPAP Reference Manual 4th Edition and training deck inventory (#98).

## [0.7.0] - 2026-08-22

### Added
- Finalized Milestone 7 documentation in `docs/milestones/v0.7.0.md` with complete verification artifacts, retrospective, and test evidence for Epics E0–E5 (#96).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.7.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.7.0.md` (#96).
- Updated `README.md` milestone status table marking `v0.7.0` as Completed with `docs/milestones/v0.7.0.md` link, advancing `v0.8.0` to Up Next, and queuing `v0.9.0–v1.0.0` (#96).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v0.7.0` traceability assertions across all 6 task issues (#91–#96), release gate criteria, verification artifacts, and negative mutation controls (#96).
- Synchronized workspace version bump to `0.7.0` across root `pyproject.toml`, `packages/quality-core`, `packages/quality-mcp`, and `uv.lock` (#96).
- Unified in-process FastMCP client-server round-trip integration test suite `packages/quality-mcp/tests/test_ncr_copq_client_roundtrip.py` validating tool discovery across all five NCR & COPQ tools (`write_ncr`, `recommend_disposition`, `render_ncr_canvas`, `estimate_copq`, `render_copq_canvas`), dual-payload parity (`structuredContent` vs JSON text), direct `quality_core.ncr` and `quality_core.copq` engine parity, session error isolation, protocol negative controls, and single-session chained workflows (`write_ncr` -> `recommend_disposition` -> `estimate_copq` -> `render_copq_canvas`) across benchmark manufacturing datasets (#95).
- Extended FastMCP server configuration tests in `packages/quality-mcp/tests/test_server.py` asserting discovery, execution, and root exports for all five NCR and COPQ tools (#95).
- Updated MCP client configuration guide `docs/mcp-client-setup.md` with Item 8 in-process round-trip test instructions, copy-verified JSON-RPC 2.0 transcripts (4.20–4.24), and an end-to-end chained NCR→COPQ sequence diagram (4.25) (#95).
- Single-writer visual Cost of Poor Quality (COPQ) canvas controller `COPQCanvas` in `quality_core.canvas.copq` supporting in-memory item CRUD, manufacturing benchmark dataset (`SAMPLE_COPQ_ITEMS`, `load_sample_copq_canvas`), summary metrics, proportional PAF distribution waterfall bar, financial Pareto cost ranking table, and responsive dark/light themed HTML rendering (`render_copq`) (#94).
- FastMCP tool `estimate_copq` in `quality_mcp.tools.copq` and `render_copq_canvas` in `quality_mcp.tools.canvas` registered on `quality-mcp` server with dual-payload structured content parity (#94).
- Cost of Poor Quality Estimator domain skill in `skills/copq-estimator/SKILL.md` adhering to agentskills.io standard with 5 mandatory H2 sections and strict Zero Inline Math enforcement (#94).
- Extended skills governance test suite `tests/test_skills_conventions.py` with `copq-estimator` discovery, tool specification, and isolation assertions (#94).
- Single-writer visual Nonconformance Report (NCR) canvas controller `NCRCanvas` in `quality_core.canvas.ncr` supporting in-memory record CRUD, benchmark automotive/machining sample dataset (`SAMPLE_NCR_RECORDS`, `load_sample_ncr_canvas`), summary metrics, and responsive dark/light themed HTML canvas card log rendering (`render_ncr`) (#93).
- FastMCP tools `write_ncr` and `recommend_disposition` in `quality_mcp.tools.ncr` and `render_ncr_canvas` in `quality_mcp.tools.canvas` registered on `quality-mcp` server with dual-payload structured content parity (#93).
- Nonconformance Reporting domain skill in `skills/ncr-writing/SKILL.md` adhering to agentskills.io standard with 5 mandatory H2 sections and Zero Inline Adjudication invariant (#93).
- Extended skills governance test suite `tests/test_skills_conventions.py` with `ncr-writing` discovery, tool specification, and isolation assertions (#93).
- Nonconformance Reporting (NCR) and Cost of Poor Quality (COPQ) schema scaffold in `quality_core.ncr` and `quality_core.copq` (`NonconformanceRecord`, `NCRDataset`, `NCR_SCHEMA`, `CostItem`, `COPQDataset`, `COPQ_SCHEMA`), ISO 9001:2015 / IATF 16949:2016 disposition vocabulary, PAF cost model taxonomy, CSV loaders (`load_ncr_csv`, `load_copq_csv`), trust-boundary validators (`validate_ncr`, `validate_copq`), and machine-checkable citation manifests (#92).
- Extended CI core coverage gate in `.github/workflows/ci.yml` with `--cov=quality_core.ncr` and `--cov=quality_core.copq` (#92).
- Reference material procurement and citation scaffold for Milestone 7 NCR and COPQ suites (`packages/quality-core/src/quality_core/ncr/ASSUMPTIONS_LOG.md`, `ncr/CITATIONS.tsv`, `packages/quality-core/src/quality_core/copq/ASSUMPTIONS_LOG.md`, and `copq/CITATIONS.tsv`) (#91).
- Per-domain reference manual path mapping in `CLAUDE.md` under `## Standards fidelity` covering Nonconformance Reporting (ISO 9001:2015 §8.7, IATF 16949:2016 §8.7) and Cost of Poor Quality (ASQ CSSGB BoK PAF model, CSSC Green Belt Manual, Lumafield Report) (#91).
- Scaffold verification and negative control test suite `tests/test_ncr_copq_scaffold.py` verifying file headers, TSV delimiter integrity, on-machine reference manual markers, CLAUDE.md mapping, and changelog traceability (#91).

## [0.6.0] - 2026-08-20

### Added
- Finalized Milestone 6 documentation in `docs/milestones/v0.6.0.md` with complete verification artifacts, retrospective, and test evidence for Epics E0–E6 (#80).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.6.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.6.0.md` (#80).
- Updated `README.md` milestone status table marking `v0.6.0` as Completed with `docs/milestones/v0.6.0.md` link and advancing `v0.7.0` to Up Next (#80).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v0.6.0` traceability assertions across all 7 task issues (#74–#80), release gate criteria, verification artifacts, and negative mutation controls (#80).
- In-process JSON-RPC FastMCP client-server round-trip integration test suite `packages/quality-mcp/tests/test_rca_client_roundtrip.py` validating dual-payload parity, real-world benchmark datasets (Sentinel-8D Pneumatic Cylinder & Ford Global 8D bearing induction), multi-method chained workflow execution across a single session without state pollution, session error isolation, and protocol negative controls (#79).
- Extended FastMCP server configuration tests in `packages/quality-mcp/tests/test_server.py` asserting discovery and direct execution of all six RCA tools (`validate_5why`, `categorize_fishbone`, `scope_is_is_not`, `render_5why_canvas`, `render_fishbone_canvas`, `render_isisnot_canvas`) (#79).
- Updated CI headless dependency guard and coverage gate documentation in `.github/workflows/ci.yml` explicitly documenting `quality_mcp.tools.rca` alongside existing domain tools (#79).
- Updated MCP client configuration guide `docs/mcp-client-setup.md` with RCA client-server round-trip test instructions, verified JSON-RPC transcripts (4.15–4.18), and multi-tool RCA chained workflow sequence diagram (4.19) (#79).
- Deterministic Kepner-Tregoe Is/Is-Not problem scoping and hypothesis synthesis engine in `quality_core.rca.is_is_not` (`scope_is_is_not`, `IsIsNotScopingResult`, `CandidateCause`) evaluating 4-dimension problem boundary completeness (WHAT, WHERE, WHEN, EXTENT), detecting missing distinctions and changes per Kepner & Tregoe (1997) Chapter 2, synthesizing candidate root-cause hypotheses per Chapter 3, and providing structured recommendations (#78).
- Single-writer visual Kepner-Tregoe Is/Is-Not canvas controller `IsIsNotCanvas` and `IsIsNotCanvasRow` in `quality_core.canvas.rca` supporting row CRUD, reference Sentinel-8D Pneumatic Cylinder benchmark dataset (`SAMPLE_IS_IS_NOT_ROWS`, `SAMPLE_IS_IS_NOT_MATRIX`), 4-dimension comparative matrix cards, and responsive dark/light themed HTML canvas rendering (#78).
- FastMCP tools `scope_is_is_not` and `render_isisnot_canvas` (with `render_is_is_not_canvas` alias) in `quality_mcp.tools.rca` and `quality_mcp.tools.canvas` registered on `quality-mcp` FastMCP server (#78).
- Kepner-Tregoe Is/Is-Not Problem Boundary Scoping domain skill in `skills/is-is-not-scoping/SKILL.md` adhering to agentskills.io standard with 5 mandatory H2 sections and Zero Inline Math / Zero Inline Adjudication invariant (#78).
- Updated `skills/README.md` taxonomy table marking `is-is-not-scoping` as Active (#78).
- Extended skills governance test suite `tests/test_skills_conventions.py` with `is-is-not-scoping` discovery, tool specification, and isolation assertions (#78).
- Deterministic 6M Fishbone (Ishikawa) categorizer and validation engine in `quality_core.rca.fishbone` (`categorize_fishbone`, `FishboneCategorizationResult`) supporting 6M taxonomy assignment (Man, Machine, Method, Material, Measurement, Environment), category alias normalization, empty branch detection (Ishikawa 1986 / AIAG CQI-20 RULE 1), duplicate cause detection, multi-category cause placement (RULE 5), and branch concentration balance auditing (#77).
- Single-writer visual 6M Fishbone canvas controller `FishboneCanvas` and `FishboneCanvasCause` in `quality_core.canvas.rca` supporting cause CRUD, reference Sentinel-8D Pneumatic Cylinder benchmark dataset (`SAMPLE_FISHBONE_CAUSES`, `SAMPLE_FISHBONE_DATASET`), 6M branch breakdown cards, and responsive dark/light themed HTML/SVG Ishikawa diagram rendering (#77).
- FastMCP tools `categorize_fishbone` and `render_fishbone_canvas` in `quality_mcp.tools.rca` and `quality_mcp.tools.canvas` registered on `quality-mcp` FastMCP server (#77).
- 6M Fishbone Cause-and-Effect domain skill in `skills/fishbone-analysis/SKILL.md` adhering to agentskills.io standard with 5 mandatory H2 sections and Zero Inline Math / Zero Inline Adjudication invariant (#77).
- Updated standards assumptions log and citation manifest in `packages/quality-core/src/quality_core/rca/` (`ASSUMPTIONS_LOG.md`, `CITATIONS.tsv`) with RULE 1 empty branch and RULE 5 multi-category placement and balance citations from Ishikawa (1986), AIAG CQI-20, and ASQ Quality Toolbox (#77).
- Deterministic 5-Why Root Cause Analysis (RCA) validator engine in `quality_core.rca.five_why` (`validate_five_why_chain`, `FiveWhyValidationResult`, `FiveWhyLinkEval`, `AntiPatternFinding`, `SystemicAssessment`) evaluating forward drill-down, reverse "therefore" logic necessity (AIAG CQI-20 RULE 3), anti-pattern detection (circular reasoning, superficial/blame-terminal operator causes per ASQ Quality Toolbox & Ford Global 8D RULE 4, premature termination, non-causal jumps), systemic classification, and reversibility scoring (#76).
- Single-writer visual 5-Why canvas controller `FiveWhyCanvas` and `FiveWhyCanvasStep` in `quality_core.canvas.rca` supporting step CRUD, benchmark Ford Global 8D bearing induction sample dataset, reverse check flow, anti-pattern badges, and dark/light themed HTML canvas rendering (#76).
- FastMCP tools `validate_5why` and `render_5why_canvas` in `quality_mcp.tools.rca` and `quality_mcp.tools.canvas` registered on `quality-mcp` FastMCP server (#76).
- Reversible 5-Why Root Cause Analysis domain skill in `skills/5why-root-cause/SKILL.md` adhering to agentskills.io standard with 5 mandatory H2 sections and Zero Inline Math / Zero Inline Adjudication invariant (#76).
- Extended standards assumptions log and citation manifest in `packages/quality-core/src/quality_core/rca/` (`ASSUMPTIONS_LOG.md`, `CITATIONS.tsv`) with RULE 4 citations from ASQ Quality Toolbox, Ford Global 8D, and AIAG CQI-20 (#76).
- Root Cause Analysis (RCA) engine scaffold and shared schema in `quality_core.rca` (`FiveWhyStep`, `FiveWhyChain`, `FIVE_WHY_SCHEMA`, `Category6M`, `FishboneCause`, `FishboneDataset`, `FISHBONE_SCHEMA`, `KTDimension`, `IsIsNotRow`, `IsIsNotMatrix`, `IS_IS_NOT_SCHEMA`) with 5-Why sequential step validation, 6M Fishbone category alias normalization, Kepner-Tregoe 4-dimension scoping, and CSV upload validation (#75).

- Standards-grounded assumptions and citation manifest in `packages/quality-core/src/quality_core/rca/` (`ASSUMPTIONS_LOG.md`, `CITATIONS.tsv`) covering Ishikawa 6M taxonomy, Kepner-Tregoe Problem Analysis, and AIAG CQI-20 / Ford G8D 5-Why logic (#75).
- Reference material procurement and citation scaffold for Milestone 6 Root Cause Analysis (RCA) suite (`packages/quality-core/src/quality_core/rca/ASSUMPTIONS_LOG.md` and `packages/quality-core/src/quality_core/rca/CITATIONS.tsv`) (#74).
- Per-domain reference manual path mapping in `CLAUDE.md` covering MSA, FMEA, SPC, Control Plan, and RCA (#74).

### Changed
- Extended CI core coverage gate in `.github/workflows/ci.yml` to include `--cov=quality_core.rca` across all 8 quality-core engine surfaces (#75).

## [0.5.0] - 2026-08-17

### Added
- Finalized Milestone 5 documentation in `docs/milestones/v0.5.0.md` with complete verification artifacts, 4-Engine Checkpoint empirical evidence, retrospective, and test evidence for Epics E1–E7 (#48).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.5.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.5.0.md` (#48).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v0.5.0` traceability assertions across all 7 task issues (#42–#48), release gate criteria, verification artifacts, and changelog verification (#48).
- Single-writer visual Control Plan matrix canvas controller `ControlPlanCanvas` and `ControlPlanCanvasRow` in `quality_core.canvas.controlplan` rendering characteristic specifications, tolerances, measurement methods, sample plans, recommended SPC charts, and reaction plans in standalone/embeddable dark-themed HTML5 artifacts with row-level validation and PFMEA orphan linkage findings highlighted (#47).
- FastMCP tool `render_controlplan_canvas` in `quality_mcp.tools.canvas` exposing Control Plan visual matrix canvas generation and validation summary metrics over Model Context Protocol endpoints (#47).
- Re-export `render_controlplan_canvas` in `quality_mcp.tools`, register on `quality-mcp` FastMCP server, and export in package root (#47).
- AIAG APQP & Control Plan (2nd Edition) domain skill in `skills/control-plan/SKILL.md` guiding Control Plan structure audits, tolerance coherence checks, PFMEA bidirectional cause linkage verification, and SPC chart selection via `validate_control_plan` on `quality-mcp` with zero inline adjudication (#46).
- Updated `skills/README.md` directory structure and taxonomy table marking `control-plan` as Active (#46).
- Extended skills governance test suite `tests/test_skills_conventions.py` with `control-plan` discovery, tool specification, and isolation assertions (#46).
- In-process JSON-RPC FastMCP client-server round-trip test suite `packages/quality-mcp/tests/test_controlplan_client_roundtrip.py` validating dual-payload parity, real-world Control Plan fixtures, PFMEA linkage, and protocol negative controls (#45).
- End-to-end Milestone 5 4-Engine Checkpoint smoke test suite `packages/quality-mcp/tests/test_four_engine_smoke.py` validating sequential execution and error isolation of all four wrapped engines (FMEA, SPC, MSA, Control Plan) in a single FastMCP client session (#45).
- Updated MCP client configuration guide `docs/mcp-client-setup.md` with verified `validate_control_plan` JSON-RPC transcripts, PFMEA linkage findings, and 4-Engine Checkpoint sequence diagram (#45).
- Dedicated packaging metadata test `packages/quality-mcp/tests/test_packaging.py` asserting headless dependencies and zero UI-chain packages in `quality-mcp` (#44).
- FastMCP tool `validate_control_plan` in `quality_mcp.tools.controlplan` wrapping `quality_core.controlplan` deterministic engines for AIAG Control Plan schema validation and bidirectional PFMEA linkage checking (#43).
- Re-export `validate_control_plan` in `quality_mcp.tools`, register on `quality-mcp` FastMCP server, and export in package root (#43).
- Comprehensive unit and integration test suite in `packages/quality-mcp/tests/test_controlplan_tool.py` achieving 100% line & branch coverage across `quality_mcp.tools.controlplan` with schema error handling, orphan linkage negative controls, and FastMCP round-trip validation (#43).
- Extracted Control Plan engine and PFMEA-linkage validator from source repository into `packages/quality-core/src/quality_core/controlplan/` (`schema.py`, `connector.py`, `ASSUMPTIONS_LOG.md`, `CITATIONS.tsv`) with AIAG APQP & Control Plan and SPC decision-tree standards fidelity (#42).
- Machine-checkable citation verification test `packages/quality-core/tests/test_controlplan_citations.py` validating citation entries against on-machine reference manual (#42).
- Comprehensive test suites `packages/quality-core/tests/test_controlplan_schema.py`, `packages/quality-core/tests/test_controlplan_connector.py`, and `packages/quality-core/tests/test_controlplan_linkage.py` enforcing 100% line & branch coverage across `quality_core.controlplan` (#42).

### Changed
- Extended CI headless dependency guard and FastMCP coverage gate documentation in `.github/workflows/ci.yml` to assert `quality_mcp.tools.controlplan` coverage and zero UI-chain dependencies (#44).
- Extended core coverage gate in `.github/workflows/ci.yml` to include `--cov=quality_core.controlplan` at 100% line & branch enforcement (#42).

## [0.4.0] - 2026-08-16

### Added
- Finalized Milestone 4 documentation in `docs/milestones/v0.4.0.md` with complete verification artifacts, retrospective, and test evidence for Epics E1–E7 (#41).
- Updated `docs/milestones/README.md` canonical mapping and `ROADMAP.md` Summary Release Matrix for `v0.4.0` (#41).
- Extended milestone governance test suite `tests/test_milestones_convention.py` with `v0.4.0` traceability assertions across all 7 task issues (#35–#41) and verification artifacts (#41).
- Single-writer visual MSA Gage R&R canvas controller `MSACanvas` and `MSACanvasMeasurement` in `quality_core.canvas.msa` rendering Operator $\times$ Part Interaction Plot and Variance Components Breakdown horizontal bar chart in standalone/embeddable dark-themed HTML5/SVG artifacts (#40).
- FastMCP tool `render_msa_canvas` in `quality_mcp.tools.canvas` exposing Gage R&R visual canvas rendering with AIAG acceptance summary KPIs and interaction status over MCP transports (#40).
- Re-export `render_msa_canvas` in `quality_mcp.tools`, register on `quality-mcp` FastMCP server, and export in package root (#40).
- AIAG MSA (4th Edition) Measurement Systems Analysis skill in `skills/msa-gauge-rr/SKILL.md` guiding crossed Gage R&R study design, blind randomized data collection, ANOVA vs Average-and-Range method selection, metric decomposition audit, and AIAG acceptance verdict interpretation via `calculate_gage_rr` on `quality-mcp` with zero inline math (#39).
- In-process MCP client round-trip integration test suite in `packages/quality-mcp/tests/test_msa_client_roundtrip.py` validating `calculate_gage_rr` across AIAG MSA 4th Edition benchmark datasets, dual-payload parity (`structuredContent` vs serialized text), exact ANOVA decomposition cross-checks against extracted reference fixtures, and protocol-level negative controls (#38).
- Updated `docs/mcp-client-setup.md` with verified JSON-RPC 2.0 message exchange transcripts for `calculate_gage_rr` ANOVA, Average-and-Range, and validation error workflows (#38).
- FastMCP tool `calculate_gage_rr` in `quality_mcp.tools.msa` wrapping `quality_core.msa` deterministic engines for AIAG MSA 4th Edition crossed Gage R&R analysis (ANOVA and Average-and-Range methods, $6\sigma$ tolerance-basis and study-basis metrics, ndc, and AIAG acceptance verdicts) (#36).
- Re-export `calculate_gage_rr` in `quality_mcp.tools`, register on `quality-mcp` FastMCP server, and export in package root (#36).
- Unit and FastMCP integration test suite in `packages/quality-mcp/tests/test_msa_tool.py` achieving 100% line & branch coverage across `quality_mcp.tools.msa` with AIAG benchmark oracle parity and structured error handling (#36).
- Extracted MSA Gage R&R engine from the source repository into `packages/quality-core/src/quality_core/msa/` (`gage_rr.py`, `schema.py`, `ASSUMPTIONS_LOG.md`, `CITATIONS.tsv`) implementing Average-and-Range and ANOVA methods with AIAG MSA 4th Edition standards fidelity (#35).
- Machine-checkable citation test suite `packages/quality-core/tests/test_msa_citations.py` validating all 78 citation entries against `/Users/sid/Documents/Upskill/SixSigma/MSA_Reference_Manual_4th_Edition.md` with line tolerance $\pm 2$ (#35).
- Comprehensive test suites `packages/quality-core/tests/test_msa_gage_rr_engine.py` and `packages/quality-core/tests/test_msa_schema.py` verifying standard AIAG benchmark datasets, hand-calculated worked examples, $6\sigma$ tolerance multipliers, ANOVA pooling & interaction tests, edge cases, and schema ingest at 100% line & branch coverage (#35).

### Changed
- CI headless dependency guard and coverage gate comments in `.github/workflows/ci.yml` updated to document the headless containment contract and confirm 100% line & branch coverage scope for `quality_mcp.tools.msa` under `--cov=quality_mcp --cov-fail-under=100` (#37).
- Extended core coverage gate in `.github/workflows/ci.yml` to include `--cov=quality_core.msa` at 100% line & branch enforcement (#35).

## [0.3.0] - 2026-08-15

### Added
- FastMCP tool `calculate_spc_chart` in `quality_mcp.tools.spc` wrapping `quality_core.spc` deterministic engines for Shewhart variable (`Xbar-R`, `Xbar-S`, `I-MR`) and attribute (`p`, `c`, `u`) charts, run-rule detection (Western Electric 1–8 and Nelson), and strict stability-gated capability analysis (`Cp`, `Cpk`, `Pp`, `Ppk`) (#29).
- Re-export `calculate_spc_chart` in `quality_mcp.tools`, register on `quality-mcp` FastMCP server, and export in package root (#29).
- Comprehensive unit and integration test suite in `packages/quality-mcp/tests/test_spc_tool.py` verifying worked examples, run rules, error handling, and stability gate negative controls at 100% line & branch coverage (#29).
- In-process MCP client round-trip integration test suite in `packages/quality-mcp/tests/test_spc_client_roundtrip.py` validating `calculate_spc_chart` across AIAG benchmark datasets, dual-payload parity (`structuredContent` vs serialized text), and strict stability-gate capability withholding over the JSON-RPC wire (#31).
- Updated `docs/mcp-client-setup.md` with verified JSON-RPC 2.0 message exchange transcripts for `calculate_spc_chart` in-control, out-of-control, and parameter validation error workflows (#31).
- AIAG SPC (4th Edition, 2005) Statistical Process Control skill in `skills/spc-control-charts/SKILL.md` guiding Shewhart chart selection (`Xbar-R`, `Xbar-S`, `I-MR`, `p`, `c`, `u`), rational subgrouping, Western Electric & Nelson run-rule violation diagnostics, and strict stability-gated capability analysis via `calculate_spc_chart` on `quality-mcp` with zero inline math (#32).
- Updated `skills/README.md` taxonomy table marking `spc-control-charts` as Active (#32).
- Extended `quality_core.canvas` with `SPCCanvas` single-writer SPC control-chart controller supporting variable (`Xbar-R`, `Xbar-S`, `I-MR`) and attribute (`p`, `c`, `u`) charts, deterministic point/subgroup editing, strict stability-gated capability analysis, and Quality Platform dark-themed HTML5/SVG canvas generation (#33).
- FastMCP tool `render_spc_canvas` in `quality_mcp.tools.canvas` registered on `quality-mcp` FastMCP server, re-exported across packages, and tested with in-process MCP client round-trip validation (#33).
- Finalized Milestone 3 (`v0.3.0`) specification document in `docs/milestones/v0.3.0.md` detailing Epics E1–E6, linking issues #29 through #34 with branch names, 7 release gate criteria, verification artifacts, and Milestone 4 readiness handoff (#34).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.3.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.3.0.md` (#34).
- Extended milestone governance test suite in `tests/test_milestones_convention.py` with comprehensive traceability, branch mapping, release gate, and artifact assertions for `v0.3.0` (#34).

### Changed
- CI headless dependency guard and coverage gate comments in `.github/workflows/ci.yml` updated to document the headless containment contract and confirm 100% line & branch coverage scope for `quality_mcp.tools.spc` under `--cov=quality_mcp --cov-fail-under=100` (#30).

## [0.2.0] - 2026-08-15

### Added
- Milestone 2 (`v0.2.0`) specification document in `docs/milestones/v0.2.0.md` detailing Epics E1–E6, linking issues #16 through #21 with branch names, 7 release gate criteria, verification artifacts, and Milestone 3 readiness handoff (#21).
- Updated `docs/milestones/README.md` canonical mapping table marking `v0.2.0` as Complete and updated `ROADMAP.md` Summary Release Matrix linking `docs/milestones/v0.2.0.md` (#21).
- Extended milestone governance test suite in `tests/test_milestones_convention.py` with comprehensive traceability, branch mapping, release gate, and artifact assertions for `v0.2.0` (#21).
- Minimal single-writer FMEA visual canvas architecture in `quality_core.canvas` (`FMEACanvasRow`, `FMEACanvas` controller with deterministic scoring via `quality_core.scoring`, benchmark sample loader, edit controller, and standalone/embedded HTML renderer with Quality Platform dark theme styling) (#20).
- `render_fmea_canvas` FastMCP tool in `quality_mcp.tools.canvas` exposing styled FMEA canvas HTML rendering and risk summary metrics over Model Context Protocol endpoints (#20).
- Comprehensive test suites in `packages/quality-core/tests/test_canvas.py` and `packages/quality-mcp/tests/test_canvas_tool.py` achieving 100% line & branch coverage across `quality_core.canvas` and `quality_mcp.tools.canvas` (#20).
- Extended CI Core coverage gate in `.github/workflows/ci.yml` to include `--cov=quality_core.canvas` at 100% enforcement (#20).
- AIAG & VDA (1st Edition, 2019) FMEA reviewer skill in `skills/fmea-reviewer/SKILL.md` defining qualitative 7-Step FMEA review methodology, failure chain analysis, and deterministic Action Priority scoring via `lookup_fmea_ap` on `quality-mcp` (#19).
- Updated `skills/README.md` taxonomy table marking `fmea-reviewer` skill as Active (#19).
- Governance test suite coverage in `tests/test_skills_conventions.py` asserting `lookup_fmea_ap` tool documentation, `quality-mcp` server reference, and AIAG Action Priority citations for `fmea-reviewer` (#19).
- In-process MCP client round-trip test suite in `packages/quality-mcp/tests/test_fmea_client_roundtrip.py` validating `lookup_fmea_ap` tool discovery, real-world automotive DFMEA/PFMEA dataset evaluation across 12 diverse failure modes spanning High, Medium, and Low Action Priority, dual structured and serialized text payload parity against `quality_core.scoring`, and protocol-level negative controls for out-of-range ratings, invalid types, and unknown tools (#18).
- Updated MCP client setup guide in `docs/mcp-client-setup.md` with test instructions for `test_fmea_client_roundtrip.py` and verified JSON-RPC 2.0 protocol transcripts for `lookup_fmea_ap` tool execution and validation error exchanges (#18).
- `lookup_fmea_ap` MCP tool (`quality_mcp.tools.fmea`) exposing AIAG-VDA 2019 Action Priority and RPN risk scoring over Model Context Protocol endpoints (#16).
- `quality_mcp.tools` package namespace re-exporting `lookup_fmea_ap` (#16).
- Comprehensive test suite in `packages/quality-mcp/tests/test_fmea_tool.py` verifying direct function execution, AIAG-VDA worked examples, boundary sweeps, negative mutation controls, FastMCP tool registration, and in-process client session round-trips (#16).

### Removed
- Legacy Streamlit apps (`apps/fmea`, `apps/spc`, `apps/msa`, `apps/controlplan`, `apps/secom`) and the unified shell (`shell/`, `app.py`) — this repo is skills + `quality-mcp` + `quality-core` only. Engines are extracted into `quality-core` per milestone from the source quality-platform repo (FMEA's AP scorer already lives in `quality_core.scoring`).
- Stale root `requirements.txt` (a `uv export` of the removed Streamlit chain) and the app import-boundary / cross-app boundary tests that only applied to the removed apps.

### Changed
- CI headless dependency guard and coverage gate comments in `.github/workflows/ci.yml` updated to document the headless containment contract and confirm 100% line & branch coverage scope for `quality_mcp.tools.*` under `--cov=quality_mcp --cov-fail-under=100` (#17).
- CI gate scoped to `quality-core` + `quality-mcp`: dropped the four app coverage gates (SPC / Control Plan / MSA / SECOM) and consolidated the four per-core-submodule gates into a single core run. Each suite now runs **once** instead of the core running 5× and the apps 2× — the source of the ~1h CI time. Also dropped the non-existent `dev` branch from the CI triggers.
- Workspace scoped to `packages/*`; `mypy.ini` now type-checks only `quality_core` + `quality_mcp` (23 files vs 67).

## [0.1.0] - 2026-08-14

### Added
- Milestone documentation conventions in `docs/milestones/README.md` and Milestone 1 (`v0.1.0`) specification index in `docs/milestones/v0.1.0.md` detailing Epics E1–E4, linking issues #1 through #7, release gate criteria, and verification artifacts (#7).
- Automated milestone governance test suite in `tests/test_milestones_convention.py` enforcing SemVer naming, structural section schema, issue URL traceability, and markdown link integrity (#7).
- Summary Release Matrix link update in `ROADMAP.md` pointing `v0.1.0` to `docs/milestones/v0.1.0.md` (#7).
- In-process MCP client-server round-trip test suite in `packages/quality-mcp/tests/test_client_roundtrip.py` verifying session initialization, tool discovery, structured `ping` execution, and protocol-level error handling (#4).
- Root workspace `.mcp.json` configuration registering `quality-mcp` for Claude Code, Cursor, and MCP-compliant AI hosts (#4).
- Client setup guide in `docs/mcp-client-setup.md` covering Claude Code/Cursor configuration, prerequisites, troubleshooting, and verified JSON-RPC protocol transcripts (#4).
- GitHub task issue template (`.github/ISSUE_TEMPLATE/task.md`), issue config disabling blank issues (`.github/ISSUE_TEMPLATE/config.yml`), and Definition of Done-enforcing PR template (`.github/pull_request_template.md`) (#5).
- Top-level `skills/` directory scaffold, `skills/README.md` conventions, canonical template `skills/_template/SKILL.md`, and diagnostic health check skill `skills/mcp-health/SKILL.md` adhering to the `agentskills.io` standard (#6).
- Governance test suite `tests/test_skills_conventions.py` asserting frontmatter validity, structural sections, and zero inline calculation logic across all skills (#6).
- FastMCP server instance (`quality-mcp`), `ping` health check tool, and `quality-mcp` console script entry point in `packages/quality-mcp` (#2).
- `packages/quality-mcp` workspace member binding `quality-core` engines to Model Context Protocol endpoints.
- Project planning documents: `Idea.md`, `ROADMAP.md` (v3.0, rescoped to 10 releases), `Execution.md` (v2.0).

### Changed
- CI gate (`.github/workflows/ci.yml`) extended with headless dependency guard and 100% line/branch coverage gate for `packages/quality-mcp` (#3).
- Branch ladder simplified to `feature → test → main` (dropped the pass-through `dev` stage).
- Repo reset from its engine-source origin: README rewritten for this project, old
  quality-platform planning docs / assets / changelog cleared (preserved in git history).

---

> **Engine source.** This project began at commit `4425b53` (2026-08-08) as a duplicate of
> [`quality-platform`](https://github.com/Siddardth7/quality-platform) `@ v0.13.0`, reused as the
> tested deterministic core (FMEA, SPC, MSA, Control Plan engines). That project's own release
> history lives in its repository and in this repo's git history prior to the reset.

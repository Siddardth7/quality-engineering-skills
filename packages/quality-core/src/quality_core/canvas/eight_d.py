"""Read-only visual canvas for a whole 8D report: D0-D8 cards plus closure-gate status.

Single-writer over already-validated engine output. ``to_html`` calls
:func:`quality_core.rca.eight_d_disciplines.validate_8d` once and renders what it returns; it
computes no verdict, no ``closeable`` flag, and no severity of its own, exactly as
``canvas/sqe.py`` renders ``ScorecardResult`` / ``EscalationResult`` without re-deriving a score.

Two presentation decisions are recorded as Process Design Decision #16 in
``rca/ASSUMPTIONS_LOG.md`` and carry no standards backing:

* the single headline "Closeable" badge is ``EightDValidationResult.closeable`` — the whole-report
  gate the state machine enforces. ``result.d8.closeable`` is the narrower closure-evidence-only
  reading and renders inside the D8 card under its own label, so a report with an invalid linked
  Nonconformance Record visibly shows the two disagreeing rather than collapsing them;
* every finding's citation basis is read from ``Finding.citation_basis`` — the engine's own field —
  and captioned through :data:`BASIS_CAPTION`. This module holds **no** ``code -> basis`` table and
  never scrapes finding prose for a rule id.

An absent discipline is an in-progress state, not an error: every D0-D8 card is always rendered,
with a "not started" empty state when its record is ``None``.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import Any, Literal

from quality_core.rca.eight_d_disciplines import (
    D0Finding,
    D0ValidationResult,
    D1Finding,
    D1ValidationResult,
    D2Finding,
    D2ValidationResult,
    D3Finding,
    D3ValidationResult,
    D4Finding,
    D5Finding,
    D5ValidationResult,
    D6Finding,
    D6ValidationResult,
    D7Finding,
    D7ValidationResult,
    D8Finding,
    D8ValidationResult,
    EightDValidationResult,
    validate_8d,
)
from quality_core.rca.eight_d_schema import (
    D0Discipline,
    D1Discipline,
    D2Discipline,
    D3Discipline,
    D4Discipline,
    D5Discipline,
    D6Discipline,
    D7Discipline,
    D8Discipline,
    EffectivenessVerification,
    EightDReport,
    validate_eight_d,
)
from quality_core.rca.five_why import FiveWhyValidationResult, validate_five_why_chain
from quality_core.theme.palette import (
    AMBER,
    BG_CARD,
    BG_PRIMARY,
    BORDER,
    DANGER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VIOLET,
)

__all__ = [
    "BASIS_CAPTION",
    "SAMPLE_EIGHT_D_REPORT",
    "EightDCanvas",
    "load_sample_eight_d_canvas",
    "render_eight_d",
]

_Finding = (
    D0Finding
    | D1Finding
    | D2Finding
    | D3Finding
    | D4Finding
    | D5Finding
    | D6Finding
    | D7Finding
    | D8Finding
)

_Result = (
    D0ValidationResult
    | D1ValidationResult
    | D2ValidationResult
    | D3ValidationResult
    | D5ValidationResult
    | D6ValidationResult
    | D7ValidationResult
    | D8ValidationResult
)

#: Plain-language caption for each ``Finding.citation_basis`` value. One source of truth for the
#: whole canvas; a platform heuristic is never captioned as a standards requirement.
BASIS_CAPTION: dict[str, str] = {
    "RULE": "Standards requirement — cited manual clause",
    "PDD": "Platform process design decision — no standards citation",
    "PLATFORM_UNCITED": "Platform heuristic — no standards citation",
}

_BASIS_COLOUR: dict[str, str] = {
    "RULE": VIOLET,
    "PDD": AMBER,
    "PLATFORM_UNCITED": TEXT_SECONDARY,
}

_VERDICT_COLOUR: dict[str, str] = {"ACCEPT": SUCCESS, "WARNING": AMBER, "REJECT": DANGER}
_SEVERITY_COLOUR: dict[str, str] = {"error": DANGER, "warning": AMBER, "info": TEXT_SECONDARY}

#: Optional per-finding context attributes; each dataclass carries at most one of them.
_CONTEXT_FIELDS = ("member_name", "action_description", "action_id", "leg_type", "artifact_type")

_COLOURS_DARK: dict[str, str] = {
    "page": BG_PRIMARY,
    "card": BG_CARD,
    "border": BORDER,
    "primary": TEXT_PRIMARY,
    "secondary": TEXT_SECONDARY,
}
_COLOURS_LIGHT: dict[str, str] = {
    "page": "#f8fafc",
    "card": "#ffffff",
    "border": "#cbd5e1",
    "primary": "#0f172a",
    "secondary": "#64748b",
}

_HEURISTIC_DISCLOSURE = (
    "Each finding and gate reason carries its own citation basis: a standards requirement names a "
    "cited manual clause, while a platform process design decision or platform heuristic carries "
    "no standards citation and must not be read as one."
)


def _text(value: object) -> str:
    """Escape one leaf value; ``None`` renders as an em dash, never the literal string 'None'."""
    if value is None:
        return "—"
    return html.escape(str(value))


def _badge(colour: str, label: str) -> str:
    return f'<span class="badge" style="color:{colour};border-color:{colour};">{_text(label)}</span>'


def _yes_no(value: bool) -> str:
    return "YES" if value else "NO"


def _flag_badge(label: str, value: bool) -> str:
    return _badge(SUCCESS if value else DANGER, f"{label}: {_yes_no(value)}")


def _rule_caption(rule_id: str | None) -> str:
    """Caption a gate reason from its ``rule_id`` prefix, never from its message prose."""
    if rule_id is None:
        return "Structural rule (state machine) — no standards or heuristic claim"
    if rule_id.startswith("RULE-"):
        return f"Standards requirement ({rule_id})"
    return f"Platform heuristic — no standards citation ({rule_id})"


def _rule_colour(rule_id: str | None) -> str:
    """A cited ``RULE-`` id is coloured as a standards requirement; anything else is not."""
    if rule_id is not None and rule_id.startswith("RULE-"):
        return _BASIS_COLOUR["RULE"]
    return _BASIS_COLOUR["PDD"]


def _verification_rows(
    prefix: str, verification: EffectivenessVerification | None
) -> list[tuple[str, str]]:
    if verification is None:
        return [(f"{prefix} verification", "—")]
    return [
        (f"{prefix} verified by", _text(verification.verified_by)),
        (f"{prefix} verified date", _text(verification.verified_date)),
        (f"{prefix} evidence", _text(verification.evidence)),
        (f"{prefix} effective", _text(verification.is_effective)),
    ]


def _d0_details(discipline: D0Discipline) -> list[tuple[str, str]]:
    return [
        ("ERA required", _text(discipline.era_required)),
        ("ERA description", _text(discipline.era_description)),
        ("ERA implemented date", _text(discipline.era_implemented_date)),
        *_verification_rows("ERA", discipline.era_verification),
    ]


def _d1_details(discipline: D1Discipline) -> list[tuple[str, str]]:
    rows = [
        ("Champion", _text(discipline.champion)),
        ("Team leader", _text(discipline.team_leader)),
        ("Team members", _text(len(discipline.members))),
    ]
    rows.extend(
        (f"Member {index}", f"{_text(member.name)} — {_text(member.role)}")
        for index, member in enumerate(discipline.members, start=1)
    )
    return rows


def _d2_details(discipline: D2Discipline) -> list[tuple[str, str]]:
    return [
        ("What is wrong", _text(discipline.what_is_wrong)),
        ("With what", _text(discipline.with_what)),
        ("Quantification", _text(discipline.quantification)),
        ("Method used", _text(discipline.method_used)),
        ("Who?", _text(discipline.w2h_who)),
        ("What?", _text(discipline.w2h_what)),
        ("When?", _text(discipline.w2h_when)),
        ("Where?", _text(discipline.w2h_where)),
        ("Why?", _text(discipline.w2h_why)),
        ("How?", _text(discipline.w2h_how)),
        ("How Many?", _text(discipline.w2h_how_many)),
    ]


def _d3_details(discipline: D3Discipline) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for index, action in enumerate(discipline.actions, start=1):
        rows.append((f"Containment {index}", _text(action.description)))
        rows.append((f"Containment {index} implemented", _text(action.implemented_date)))
        rows.extend(_verification_rows(f"Containment {index}", action.verification))
    validation = discipline.linked_ncr_validation
    if validation is None:
        rows.append(("Linked NCR validation", "not linked yet"))
    else:
        rows.append(("Linked NCR valid", _text(validation.is_valid)))
        rows.append(("Linked NCR record count", _text(validation.record_count)))
        rows.extend(
            (f"Linked NCR finding {index}", _text(finding))
            for index, finding in enumerate(validation.findings, start=1)
        )
    return rows


def _d4_details(
    discipline: D4Discipline | None, validation: FiveWhyValidationResult | None
) -> list[tuple[str, str]]:
    """Render D4 from the report itself — ``EightDValidationResult`` carries no ``d4`` result."""
    rows: list[tuple[str, str]] = []
    if discipline is None:
        rows.append(("D4 record", "not started"))
    else:
        for index, candidate in enumerate(discipline.candidate_causes_tested, start=1):
            rows.append(
                (
                    f"Candidate cause {index}",
                    f"{_text(candidate.description)} — {_text(candidate.result)}",
                )
            )
            rows.append((f"Candidate cause {index} test data", _text(candidate.test_data)))
        rows.extend(
            [
                ("Root cause", _text(discipline.root_cause.statement)),
                ("Root cause evidence", _text(discipline.root_cause.verification_evidence)),
                ("Root cause 5-Why leg", _text(discipline.root_cause.five_why_leg_type)),
                ("Root cause 5-Why verdict", _text(discipline.root_cause.five_why_verdict)),
                ("Escape point", _text(discipline.escape_point.statement)),
                ("Escape point evidence", _text(discipline.escape_point.verification_evidence)),
                ("Escape point 5-Why leg", _text(discipline.escape_point.five_why_leg_type)),
                ("Escape point 5-Why verdict", _text(discipline.escape_point.five_why_verdict)),
            ]
        )
    if validation is None:
        rows.append(("Linked 5-Why validation", "not run"))
    else:
        rows.extend(
            [
                ("Linked 5-Why verdict", _text(validation.verdict)),
                ("Linked 5-Why problem statement", _text(validation.problem_statement)),
                ("Linked 5-Why root cause", _text(validation.root_cause)),
                ("Linked 5-Why reversibility score", _text(validation.reversibility_score)),
                ("Linked 5-Why steps", _text(validation.total_steps)),
            ]
        )
    return rows


def _d5_details(discipline: D5Discipline) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for candidate in discipline.candidates:
        label = _text(candidate.action_id)
        rows.append((f"Candidate {label} target", _text(candidate.target)))
        rows.append((f"Candidate {label} description", _text(candidate.description)))
        rows.append((f"Candidate {label} selection criteria", _text(candidate.selection_criteria)))
        rows.append(
            (
                f"Candidate {label} verified free of undesirable effects",
                _text(candidate.verified_no_undesirable_effects),
            )
        )
        rows.append((f"Candidate {label} verification notes", _text(candidate.verification_notes)))
    return rows


def _d6_details(discipline: D6Discipline) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for action in discipline.implemented_actions:
        label = _text(action.corrective_action_id)
        rows.append((f"Implemented {label} date", _text(action.implemented_date)))
        rows.append((f"Implemented {label} monitoring notes", _text(action.monitoring_notes)))
        rows.extend(_verification_rows(f"Implemented {label}", action.verification))
    rows.append(
        ("Interim containment removed", _text(discipline.interim_containment_removed_date))
    )
    return rows


def _d7_details(discipline: D7Discipline) -> list[tuple[str, str]]:
    rows = [
        ("Systemic changes", _text(discipline.systemic_changes_description)),
        ("Qualifying FMEA / Control Plan update", _text(discipline.has_qualifying_update)),
        ("Root-cause-linked update", _text(discipline.has_root_cause_linked_update)),
    ]
    for index, update in enumerate(discipline.documentation_updates, start=1):
        rows.append(
            (
                f"Documentation update {index}",
                f"{_text(update.artifact_type)} — {_text(update.artifact_reference)}",
            )
        )
        rows.append((f"Documentation update {index} date", _text(update.updated_date)))
        rows.append((f"Documentation update {index} updated by", _text(update.updated_by)))
        rows.append((f"Documentation update {index} target", _text(update.target)))
    return rows


def _d8_details(discipline: D8Discipline) -> list[tuple[str, str]]:
    rows = [
        ("Team recognition notes", _text(discipline.team_recognition_notes)),
        ("Documentation reviewed", _text(discipline.documentation_reviewed)),
        ("Documentation reviewed by", _text(discipline.documentation_reviewed_by)),
        ("Documentation review date", _text(discipline.documentation_review_date)),
        ("Linked 5-Why verdict", _text(discipline.linked_five_why_verdict)),
        ("Closure approved", _text(discipline.closure_approved)),
        ("Closure approved by", _text(discipline.closure_approved_by)),
        ("Closure approved date", _text(discipline.closure_approved_date)),
    ]
    override = discipline.warning_override
    if override is None:
        rows.append(("Warning override", "—"))
    else:
        rows.append(("Warning override approved by", _text(override.approved_by)))
        rows.append(("Warning override justification", _text(override.justification)))
        rows.append(("Warning override date", _text(override.override_date)))
    return rows


def _details_html(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<div class="row"><span class="label">{_text(label)}</span>'
        f'<span class="value">{value}</span></div>'
        for label, value in rows
    )
    return f'<div class="details">{cells}</div>'


def _finding_html(finding: _Finding) -> str:
    context = [
        f"{name}: {_text(value)}"
        for name in _CONTEXT_FIELDS
        if (value := getattr(finding, name, None)) is not None
    ]
    context_html = (
        f'<div class="context">{" · ".join(context)}</div>' if context else ""
    )
    basis = finding.citation_basis
    return (
        f'<div class="finding" style="border-left-color:{_SEVERITY_COLOUR[finding.severity]};">'
        f'<div class="finding-head">{_badge(_SEVERITY_COLOUR[finding.severity], finding.severity)}'
        f"<strong>{_text(finding.code)}</strong>"
        f"{_badge(_BASIS_COLOUR[basis], BASIS_CAPTION[basis])}</div>"
        f"{context_html}"
        f'<div class="message">{_text(finding.message)}</div>'
        f'<div class="recommendation">Recommendation: {_text(finding.recommendation)}</div>'
        "</div>"
    )


def _findings_html(findings: Sequence[_Finding]) -> str:
    return "".join(_finding_html(finding) for finding in findings)


def _card(
    heading: str,
    details: list[tuple[str, str]] | None,
    result: _Result | None,
    extra: str = "",
) -> str:
    """One discipline card. ``details is None`` renders the not-started empty state."""
    verdict_badge = (
        "" if result is None else _badge(_VERDICT_COLOUR[result.verdict], f"Verdict: {result.verdict}")
    )
    body = (
        f'<div class="empty">Not started — no {_text(heading.split(" ")[0])} record on this '
        "report yet.</div>"
        if details is None
        else _details_html(details)
    )
    findings = "" if result is None else _findings_html(result.findings)
    return (
        f'<div class="card"><div class="card-head"><h3>{_text(heading)}</h3>'
        f"<div>{verdict_badge}{extra}</div></div>{body}{findings}</div>"
    )


def _gate_html(result: EightDValidationResult) -> str:
    if not result.gate_reasons:
        return (
            '<div class="empty">No blocking gate reasons — every closure gate this report is '
            "judged against passes.</div>"
        )
    return "".join(
        f'<div class="finding" style="border-left-color:{DANGER};">'
        f'<div class="finding-head">{_badge(DANGER, reason.code)}'
        f"{_badge(_rule_colour(reason.rule_id), _rule_caption(reason.rule_id))}</div>"
        f'<div class="message">{_text(reason.message)}</div></div>'
        for reason in result.gate_reasons
    )


class EightDCanvas:
    """Single-writer canvas over one already-validated ``EightDReport``."""

    def __init__(self, report: EightDReport, title: str = "8D Problem Solving Canvas") -> None:
        if not isinstance(report, EightDReport):
            raise TypeError(f"report must be an EightDReport, got {type(report).__name__}")
        if not isinstance(title, str):
            raise TypeError("title must be a non-empty string")
        if not title.strip():
            raise ValueError("title must be a non-empty string")
        self._report = report
        self._title = title.strip()

    @property
    def title(self) -> str:
        return self._title

    @property
    def report(self) -> EightDReport:
        return self._report

    @classmethod
    def load_sample(cls, title: str = "8D Problem Solving Canvas") -> EightDCanvas:
        """Build the benchmark canvas from :data:`SAMPLE_EIGHT_D_REPORT`."""
        return cls(validate_eight_d(SAMPLE_EIGHT_D_REPORT), title=title)

    def to_dict(self) -> dict[str, Any]:
        """Serialize title plus the whole ``validate_8d`` payload (which nests the report)."""
        return {"title": self._title, "validation": validate_8d(self._report).to_dict()}

    @staticmethod
    def _theme(theme: str, standalone: bool) -> tuple[bool, bool]:
        if not isinstance(theme, str) or theme.lower().strip() not in {"dark", "light"}:
            raise ValueError("theme must be 'dark' or 'light'")
        if not isinstance(standalone, bool):
            raise TypeError("standalone must be a boolean")
        return theme.lower().strip() == "dark", standalone

    def to_html(
        self, theme: Literal["dark", "light"] = "dark", standalone: bool = True
    ) -> str:
        """Render D0-D8 plus the closure-gate panel as themed HTML."""
        is_dark, standalone = self._theme(theme, standalone)
        colours = _COLOURS_DARK if is_dark else _COLOURS_LIGHT
        report = self._report
        result = validate_8d(report)

        identity = _details_html(
            [
                ("Report", _text(report.report_id)),
                ("Initiated", _text(report.initiated_date)),
                ("Target completion", _text(report.target_completion_date)),
                ("Closed", _text(report.closed_date)),
                ("Status", _text(report.status)),
                ("Current discipline", _text(report.current_discipline)),
                ("State", _text(result.state)),
            ]
        )
        header = (
            f'<div class="card"><div class="card-head"><h3>Closure gate status</h3>'
            f"<div>{_badge(_VERDICT_COLOUR[result.verdict], f'Report verdict: {result.verdict}')}"
            f"{_flag_badge('Closeable (whole report)', result.closeable)}</div></div>"
            f"{identity}{_gate_html(result)}</div>"
        )

        cards = "".join(
            (
                _card(
                    "D0 — Emergency Response Action readiness",
                    None if report.d0 is None else _d0_details(report.d0),
                    result.d0,
                ),
                _card(
                    "D1 — Team",
                    None if report.d1 is None else _d1_details(report.d1),
                    result.d1,
                ),
                _card(
                    "D2 — Problem description",
                    None if report.d2 is None else _d2_details(report.d2),
                    result.d2,
                ),
                _card(
                    "D3 — Interim containment",
                    None if report.d3 is None else _d3_details(report.d3),
                    result.d3,
                ),
                _card(
                    "D4 — Root cause and escape point",
                    None
                    if report.d4 is None and report.root_cause_validation is None
                    else _d4_details(report.d4, report.root_cause_validation),
                    None,
                ),
                _card(
                    "D5 — Permanent corrective action selection",
                    None if report.d5 is None else _d5_details(report.d5),
                    result.d5,
                ),
                _card(
                    "D6 — Implementation and validation",
                    None if report.d6 is None else _d6_details(report.d6),
                    result.d6,
                ),
                _card(
                    "D7 — Prevent recurrence",
                    None if report.d7 is None else _d7_details(report.d7),
                    result.d7,
                ),
                _card(
                    "D8 — Recognize the team and close",
                    None if report.d8 is None else _d8_details(report.d8),
                    result.d8,
                    extra=_flag_badge("D8 closure-evidence complete", result.d8.closeable),
                ),
            )
        )

        style = (
            f"<style>.eight-d-canvas h2{{margin:0 0 6px 0;}}"
            f".eight-d-canvas h3{{margin:0;font-size:15px;}}"
            f".eight-d-canvas .card{{background:{colours['card']};border:1px solid "
            f"{colours['border']};border-radius:10px;padding:16px;margin-bottom:14px;}}"
            ".eight-d-canvas .card-head{display:flex;justify-content:space-between;"
            "align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;}"
            ".eight-d-canvas .badge{display:inline-block;padding:2px 8px;margin-left:6px;"
            "border:1px solid;border-radius:6px;font-size:11px;font-weight:700;}"
            ".eight-d-canvas .details{display:grid;grid-template-columns:1fr;gap:4px;}"
            ".eight-d-canvas .row{display:flex;gap:10px;font-size:13px;}"
            f".eight-d-canvas .label{{min-width:260px;color:{colours['secondary']};}}"
            f".eight-d-canvas .value{{color:{colours['primary']};}}"
            ".eight-d-canvas .finding{border-left:3px solid;padding:8px 12px;margin-top:10px;}"
            ".eight-d-canvas .finding-head{font-size:13px;}"
            f".eight-d-canvas .message,.eight-d-canvas .recommendation,"
            f".eight-d-canvas .context{{font-size:12px;color:{colours['secondary']};"
            "margin-top:4px;}"
            f".eight-d-canvas .empty{{padding:24px;text-align:center;font-style:italic;"
            f"color:{colours['secondary']};border:1px dashed {colours['border']};"
            "border-radius:8px;}</style>"
        )

        body = (
            f'<div class="eight-d-canvas" style="font-family:Inter,Arial,sans-serif;'
            f"max-width:1200px;margin:0 auto;padding:20px;background:{colours['page']};"
            f"color:{colours['primary']};\">"
            f"<h2>{_text(self._title)}</h2>"
            f'<div style="color:{colours["secondary"]};font-size:12px;">'
            f"{_text(_HEURISTIC_DISCLOSURE)}</div>"
            f'<div style="margin-top:16px;">{header}{cards}</div>{style}</div>'
        )
        if not standalone:
            return body
        return (
            '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f"<title>{_text(self._title)}</title>"
            f"<style>body{{margin:0;background:{colours['page']};}}"
            "*{box-sizing:border-box;}</style></head>"
            f"<body>{body}</body></html>"
        )


def _sample_five_why_chain() -> list[dict[str, Any]]:
    return [
        {
            "step_number": 1,
            "why": "Why did the housing bore run undersized?",
            "because": "The boring tool offset was never re-applied after the tool change.",
        },
        {
            "step_number": 2,
            "why": "Why was the offset never re-applied?",
            "because": "The setup sheet had no offset-verification step.",
        },
        {
            "step_number": 3,
            "why": "Why did the setup sheet have no verification step?",
            "because": "The setup procedure was approved without a control-plan review.",
        },
    ]


def _sample_verification(evidence: str) -> dict[str, Any]:
    return {
        "verified_by": "Q. Engineer",
        "verified_date": "2026-01-12",
        "evidence": evidence,
        "is_effective": True,
    }


_SAMPLE_ROOT_CAUSE_VALIDATION = validate_five_why_chain(
    _sample_five_why_chain(),
    problem_statement="Bore diameter undersized with Housing 44821",
    root_cause="The setup procedure was approved without a control-plan review.",
    leg_type="occurrence",
)


#: Benchmark report: every discipline D0-D8 populated so the sample exercises the complete,
#: closeable path. Plain dict (JSON shape) apart from ``root_cause_validation``, which is a real
#: ``FiveWhyValidationResult`` built by the engine rather than a hand-written payload — the same
#: "build real engine objects" shape ``canvas/sqe.py``'s ``SAMPLE_SQE_ROWS`` uses.
SAMPLE_EIGHT_D_REPORT: dict[str, Any] = {
    "report_id": "8D-2026-0042",
    "initiated_date": "2026-01-05",
    "target_completion_date": "2026-03-01",
    "status": "OPEN",
    "current_discipline": "D8",
    "root_cause_validation": _SAMPLE_ROOT_CAUSE_VALIDATION,
    "d0": {
        "era_required": True,
        "era_description": "Sort and hold all suspect housings at the customer's dock.",
        "era_implemented_date": "2026-01-06",
        "era_verification": _sample_verification("100% re-gauge of held stock found no escapes."),
    },
    "d1": {
        "champion": "R. Ochoa (Plant Manager)",
        "team_leader": "S. Patel (Quality Engineer)",
        "members": [
            {"name": "T. Nakamura", "role": "Manufacturing Engineer"},
            {"name": "L. Fischer", "role": "Machining Supervisor"},
            {"name": "M. Adeyemi", "role": "Customer Quality"},
        ],
    },
    "d2": {
        "what_is_wrong": "Bore diameter undersized",
        "with_what": "Housing 44821",
        "quantification": "12 of 480 housings measured 0.03 mm below the lower limit.",
        "method_used": "5W2H",
        "w2h_who": "Customer incoming inspection found it; the machining cell produced it.",
        "w2h_what": "The finish bore on Housing 44821 is below the lower specification limit.",
        "w2h_when": "First seen 2026-01-05 on parts run after the 2026-01-04 tool change.",
        "w2h_where": "Operation 30, boring cell 4; the defect is on the front bore only.",
        "w2h_why": "The bore failed the 44.00 +0.05/-0.00 mm print requirement.",
        "w2h_how": "Detected at the customer's incoming gauge, after final inspection passed it.",
        "w2h_how_many": "12 of 480 (2.5%), confined to one shift.",
    },
    "d3": {
        "actions": [
            {
                "description": "100% gauge every housing at operation 30 before shipment.",
                "implemented_date": "2026-01-07",
                "verification": _sample_verification("Gauge R&R accepted; 0 escapes in 3 shifts."),
            }
        ],
        "linked_ncr_validation": {"is_valid": True, "record_count": 2, "findings": []},
    },
    "d4": {
        "candidate_causes_tested": [
            {
                "description": "Boring tool offset not re-applied after the tool change.",
                "test_data": "Offset log shows no entry for the 2026-01-04 tool change.",
                "result": "CONFIRMED",
            },
            {
                "description": "Fixture clamping force drift.",
                "test_data": "Clamp force logged within tolerance across the affected run.",
                "result": "ELIMINATED",
            },
        ],
        "root_cause": {
            "statement": "The setup procedure was approved without a control-plan review.",
            "verification_evidence": "Setup sheet revision history shows no control-plan review.",
            "five_why_leg_type": "occurrence",
            "five_why_verdict": "ACCEPT",
        },
        "escape_point": {
            "statement": "Final inspection sampled the rear bore only.",
            "verification_evidence": "Inspection instruction lists one bore of the two.",
            "five_why_leg_type": "escape",
            "five_why_verdict": "ACCEPT",
        },
    },
    "d5": {
        "candidates": [
            {
                "action_id": "PCA-RC",
                "target": "ROOT_CAUSE",
                "description": "Add an offset-verification step to the setup procedure.",
                "selection_criteria": "Lowest residual risk; no cycle-time impact.",
                "verified_no_undesirable_effects": True,
                "verification_notes": "PFMEA re-rated; detection improved with no new failure mode.",
            },
            {
                "action_id": "PCA-EP",
                "target": "ESCAPE_POINT",
                "description": "Add the front bore to the final inspection instruction.",
                "selection_criteria": "Closes the detection gap at the escape point.",
                "verified_no_undesirable_effects": True,
                "verification_notes": "Trial run confirmed no inspection bottleneck.",
            },
        ]
    },
    "d6": {
        "implemented_actions": [
            {
                "corrective_action_id": "PCA-RC",
                "implemented_date": "2026-01-20",
                "verification": _sample_verification("30 days of run data show no undersized bore."),
                "monitoring_notes": "Tracked on the cell's daily first-piece record.",
            },
            {
                "corrective_action_id": "PCA-EP",
                "implemented_date": "2026-01-20",
                "verification": _sample_verification("Audit of 5 shifts confirms both bores gauged."),
                "monitoring_notes": "Layered process audit item added.",
            },
        ],
        "interim_containment_removed_date": "2026-02-24",
    },
    "d7": {
        "systemic_changes_description": (
            "Setup approval now requires a control-plan review before release to production."
        ),
        "documentation_updates": [
            {
                "artifact_type": "CONTROL_PLAN",
                "artifact_reference": "CP-44821 rev C",
                "updated_date": "2026-02-10",
                "updated_by": "S. Patel",
                "target": "ROOT_CAUSE",
            },
            {
                "artifact_type": "FMEA",
                "artifact_reference": "PFMEA-44821 rev F",
                "updated_date": "2026-02-11",
                "updated_by": "T. Nakamura",
                "target": "ESCAPE_POINT",
            },
        ],
    },
    "d8": {
        "team_recognition_notes": "Team recognized at the February plant meeting.",
        "documentation_reviewed": True,
        "documentation_review_date": "2026-02-26",
        "documentation_reviewed_by": "R. Ochoa",
        "linked_five_why_verdict": "ACCEPT",
        "closure_approved": False,
    },
}


def load_sample_eight_d_canvas(title: str = "8D Problem Solving Canvas") -> EightDCanvas:
    """Load the reference benchmark 8D canvas."""
    return EightDCanvas.load_sample(title=title)


def render_eight_d(
    data: EightDCanvas | EightDReport | dict[str, Any] | None = None,
    theme: Literal["dark", "light"] = "dark",
    standalone: bool = True,
    title: str = "8D Problem Solving Canvas",
) -> str:
    """Render an 8D canvas, report, or report dict as themed HTML."""
    if data is None:
        canvas = EightDCanvas.load_sample(title=title)
    elif isinstance(data, EightDCanvas):
        canvas = data
    else:
        canvas = EightDCanvas(validate_eight_d(data), title=title)
    return canvas.to_html(theme=theme, standalone=standalone)

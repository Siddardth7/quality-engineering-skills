"""
rca.py
Single-writer visual 5-Why Canvas reference implementation for Quality Platform.

Provides `FiveWhyCanvasStep` and `FiveWhyCanvas` controller for managing an in-memory
5-Why causal chain with deterministic reverse "therefore" logic evaluation, anti-pattern
detection badges, systemic classification cards, sample benchmark dataset loading, step CRUD,
and theme-aligned HTML canvas rendering (dark and light palettes).

Standards References:
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 5.
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D4 & D7.
- Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
"""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from typing import Any, Literal

from quality_core.rca.five_why import (
    FiveWhyValidationResult,
    validate_five_why_chain,
)
from quality_core.rca.schema import FiveWhyChain
from quality_core.theme.palette import (
    AMBER,
    BG_CARD,
    BG_PRIMARY,
    BG_SECONDARY,
    BORDER,
    DANGER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VIOLET,
)

__all__ = [
    "SAMPLE_FIVE_WHY_STEPS",
    "FiveWhyCanvas",
    "FiveWhyCanvasStep",
    "load_sample_5why_canvas",
    "render_five_why",
]

SAMPLE_FIVE_WHY_STEPS: list[dict[str, Any]] = [
    {
        "step_number": 1,
        "why": "Why was the bearing worn out?",
        "because": "It had dried up.",
        "reverse_therefore": "Because the bearing dried up, therefore the bearing wore out.",
        "is_reversible": True,
        "systemic_classification": "TECHNICAL_PROCESS",
        "anti_pattern_badge": None,
    },
    {
        "step_number": 2,
        "why": "Why did the bearing dry out?",
        "because": "The operator did not carry out shift autonomous maintenance routines.",
        "reverse_therefore": "Because autonomous maintenance was not carried out, therefore the bearing dried up.",
        "is_reversible": True,
        "systemic_classification": "HUMAN_INDIVIDUAL",
        "anti_pattern_badge": None,
    },
    {
        "step_number": 3,
        "why": "Why did the operator not follow the maintenance routine completely?",
        "because": "He was not properly trained during the induction.",
        "reverse_therefore": "Because he was not trained during induction, therefore he did not follow maintenance routines.",
        "is_reversible": True,
        "systemic_classification": "SYSTEMIC",
        "anti_pattern_badge": None,
    },
    {
        "step_number": 4,
        "why": "Why was he not trained in the induction?",
        "because": "Its induction program lost this outside the sheet.",
        "reverse_therefore": "Because the induction program lost this outside the sheet, therefore he was not trained.",
        "is_reversible": True,
        "systemic_classification": "SYSTEMIC",
        "anti_pattern_badge": None,
    },
    {
        "step_number": 5,
        "why": "Why was this missing on the sheet?",
        "because": "The induction plan was not signed by Engineering (Systemic Root Cause).",
        "reverse_therefore": "Because the induction plan was not signed by Engineering, therefore it was missing on the sheet.",
        "is_reversible": True,
        "systemic_classification": "SYSTEMIC",
        "anti_pattern_badge": None,
    },
]

_SAMPLE_PROBLEM_STATEMENT = "Hole positions outside of tolerance on CNC drilling station"
_SAMPLE_ROOT_CAUSE = "The induction plan was not signed by Engineering"


@dataclass
class FiveWhyCanvasStep:
    """Individual step item within the 5-Why canvas.

    Enforces field validation and captures forward why/because inquiry, reverse
    bottom-up therefore statement, reversibility status, and systemic classification.
    """

    step_number: int
    why: str
    because: str
    reverse_therefore: str = ""
    is_reversible: bool = True
    systemic_classification: str = ""
    anti_pattern_badge: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.step_number, bool) or not isinstance(self.step_number, int) or self.step_number <= 0:
            raise ValueError(f"step_number must be a positive integer, got {self.step_number!r}")

        for str_field in ("why", "because"):
            val = getattr(self, str_field)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{str_field} must be a non-empty string, got {val!r}")
            setattr(self, str_field, val.strip())

        if not isinstance(self.is_reversible, bool):
            raise TypeError(f"is_reversible must be a boolean, got {type(self.is_reversible).__name__}: {self.is_reversible!r}")

        if not isinstance(self.reverse_therefore, str):
            raise TypeError(f"reverse_therefore must be a string, got {type(self.reverse_therefore).__name__}")
        self.reverse_therefore = self.reverse_therefore.strip()

        if not isinstance(self.systemic_classification, str):
            raise TypeError(f"systemic_classification must be a string, got {type(self.systemic_classification).__name__}")
        self.systemic_classification = self.systemic_classification.strip()

        if self.anti_pattern_badge is not None:
            if not isinstance(self.anti_pattern_badge, str) or not self.anti_pattern_badge.strip():
                raise ValueError("anti_pattern_badge must be a non-empty string or None")
            self.anti_pattern_badge = self.anti_pattern_badge.strip()

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the canvas step."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FiveWhyCanvasStep:
        """Construct a FiveWhyCanvasStep from a dictionary supporting snake_case or PascalCase keys."""
        if not isinstance(data, dict):
            raise TypeError(f"data must be a dictionary, got {type(data).__name__}: {data!r}")

        def get_field(*names: str, default: Any = ...) -> Any:
            for name in names:
                if name in data:
                    return data[name]
            if default is not ...:
                return default
            raise KeyError(f"Missing required field: {' / '.join(repr(n) for n in names)}")

        step_number = get_field("step_number", "StepNumber", "step", "Step", "id", "ID")
        why = get_field("why", "Why")
        because = get_field("because", "Because")
        reverse_therefore = get_field("reverse_therefore", "ReverseTherefore", default="")
        is_reversible = get_field("is_reversible", "IsReversible", default=True)
        systemic_classification = get_field("systemic_classification", "SystemicClassification", default="")
        anti_pattern_badge = get_field("anti_pattern_badge", "AntiPatternBadge", default=None)

        return cls(
            step_number=step_number,
            why=why,
            because=because,
            reverse_therefore=reverse_therefore,
            is_reversible=is_reversible,
            systemic_classification=systemic_classification,
            anti_pattern_badge=anti_pattern_badge,
        )


class FiveWhyCanvas:
    """Single-writer visual canvas controller for 5-Why Root Cause Analysis.

    Maintains an in-memory collection of ordered `FiveWhyCanvasStep`s, problem statement,
    and root cause. Provides step CRUD operations, deterministic validation via
    `quality_core.rca.five_why.validate_five_why_chain`, summary metric computation,
    and dark/light themed HTML canvas rendering.
    """

    def __init__(
        self,
        title: str = "5-Why Root Cause Analysis Canvas",
        description: str = "Reversible 5-Why Root Cause Investigation per AIAG CQI-20 & Ford Global 8D",
        problem_statement: str = "Problem Statement",
        root_cause: str | None = None,
        leg_type: str | None = None,
    ) -> None:
        if isinstance(title, bool) or not isinstance(title, str) or not title.strip():
            raise ValueError(f"title must be a non-empty string, got {title!r}")
        if isinstance(description, bool) or not isinstance(description, str):
            raise TypeError(f"description must be a string, got {description!r}")
        if isinstance(problem_statement, bool) or not isinstance(problem_statement, str) or not problem_statement.strip():
            raise ValueError(f"problem_statement must be a non-empty string, got {problem_statement!r}")

        self.title = title.strip()
        self.description = description.strip()
        self.problem_statement = problem_statement.strip()
        self.root_cause = root_cause.strip() if isinstance(root_cause, str) and root_cause.strip() else None
        self.leg_type = leg_type.strip() if isinstance(leg_type, str) and leg_type.strip() else None
        self._steps: dict[int, FiveWhyCanvasStep] = {}

    @property
    def steps(self) -> list[FiveWhyCanvasStep]:
        """Return steps sorted by step_number."""
        return sorted(self._steps.values(), key=lambda s: s.step_number)

    @property
    def rows(self) -> list[FiveWhyCanvasStep]:
        """Alias for steps to maintain unified canvas API."""
        return self.steps

    def add_step(self, step: FiveWhyCanvasStep | dict[str, Any]) -> FiveWhyCanvasStep:
        """Add or update a step in the canvas."""
        if isinstance(step, dict):
            step_obj = FiveWhyCanvasStep.from_dict(step)
        elif isinstance(step, FiveWhyCanvasStep):
            step_obj = step
        else:
            raise TypeError(f"step must be a FiveWhyCanvasStep or dict, got {type(step).__name__}: {step!r}")

        self._steps[step_obj.step_number] = step_obj
        return step_obj

    def remove_step(self, step_number: int) -> bool:
        """Remove a step by step_number. Returns True if removed, False if not found."""
        if isinstance(step_number, bool) or not isinstance(step_number, int):
            raise TypeError(f"step_number must be an integer, got {step_number!r}")
        if step_number in self._steps:
            del self._steps[step_number]
            return True
        return False

    def get_step(self, step_number: int) -> FiveWhyCanvasStep | None:
        """Retrieve a step by step_number."""
        if isinstance(step_number, bool) or not isinstance(step_number, int):
            raise TypeError(f"step_number must be an integer, got {step_number!r}")
        return self._steps.get(step_number)

    def clear_steps(self) -> None:
        """Clear all steps from the canvas."""
        self._steps.clear()

    def set_problem_statement(self, statement: str) -> None:
        """Update the top-level problem statement."""
        if isinstance(statement, bool) or not isinstance(statement, str) or not statement.strip():
            raise ValueError(f"problem_statement must be a non-empty string, got {statement!r}")
        self.problem_statement = statement.strip()

    def set_root_cause(self, root_cause: str | None) -> None:
        """Update the root cause statement."""
        if root_cause is None or (isinstance(root_cause, str) and not root_cause.strip()):
            self.root_cause = None
        elif isinstance(root_cause, str):
            self.root_cause = root_cause.strip()
        else:
            raise TypeError(f"root_cause must be a string or None, got {type(root_cause).__name__}")

    def set_leg_type(self, leg_type: str | None) -> None:
        """Update the 3-Legged 5-Why leg classification."""
        if leg_type is None or (isinstance(leg_type, str) and not leg_type.strip()):
            self.leg_type = None
        elif isinstance(leg_type, str):
            self.leg_type = leg_type.strip()
        else:
            raise TypeError(f"leg_type must be a string or None, got {type(leg_type).__name__}")

    def validate(self) -> FiveWhyValidationResult:
        """Execute deterministic 5-Why chain validation and update step metadata."""
        if not self._steps:
            raise ValueError("Canvas contains no steps to validate.")

        sorted_steps = self.steps
        raw_chain = [
            {"step_number": s.step_number, "why": s.why, "because": s.because}
            for s in sorted_steps
        ]
        result = validate_five_why_chain(
            data=raw_chain,
            problem_statement=self.problem_statement,
            root_cause=self.root_cause,
            leg_type=self.leg_type,
        )

        # Update steps with evaluated reversibility and anti-pattern badges
        ap_map: dict[int, str] = {
            ap.step_number: ap.code for ap in result.anti_patterns if ap.step_number is not None
        }
        eval_map = {e.step_number: e for e in result.link_evaluations}

        for s in sorted_steps:
            le = eval_map[s.step_number]
            s.reverse_therefore = le.reverse_statement
            s.is_reversible = le.is_reversible
            s.anti_pattern_badge = ap_map.get(s.step_number)
            if s.step_number == len(sorted_steps):
                s.systemic_classification = result.systemic_assessment.classification

        return result

    def get_summary(self) -> dict[str, Any]:
        """Compute summary validation and causal metrics across all canvas steps."""
        total_steps = len(self._steps)
        if total_steps == 0:
            return {
                "total_steps": 0,
                "valid": False,
                "verdict": "EMPTY",
                "reversibility_score": 0.0,
                "classification": "UNCLASSIFIED",
                "is_systemic": False,
                "hard_antipatterns_count": 0,
                "findings": ["Canvas contains no steps."],
                "recommendations": ["Add 5-Why steps to begin root cause investigation."],
            }

        try:
            result = self.validate()
            hard_aps = [p for p in result.anti_patterns if p.code in ("CIRCULAR_REASONING", "BLAME_TERMINAL_OPERATOR_ERROR")]
            all_findings = [p.message for p in result.anti_patterns]
            return {
                "total_steps": total_steps,
                "valid": result.valid,
                "verdict": result.verdict,
                "reversibility_score": result.reversibility_score,
                "classification": result.systemic_assessment.classification,
                "is_systemic": result.systemic_assessment.is_systemic,
                "hard_antipatterns_count": len(hard_aps),
                "findings": all_findings,
                "recommendations": result.recommendations,
            }
        except Exception as exc:
            return {
                "total_steps": total_steps,
                "valid": False,
                "verdict": "ERROR",
                "reversibility_score": 0.0,
                "classification": "ERROR",
                "is_systemic": False,
                "hard_antipatterns_count": 0,
                "findings": [str(exc)],
                "recommendations": ["Correct step numbering or field constraints to enable validation."],
            }

    @classmethod
    def load_sample(cls, title: str = "5-Why Root Cause Analysis Canvas") -> FiveWhyCanvas:
        """Load the standard reference Ford Global 8D bearing induction benchmark dataset."""
        canvas = cls(
            title=title,
            description="Reference Ford Global 8D Problem Solving Case (Bearing Induction Training System)",
            problem_statement=_SAMPLE_PROBLEM_STATEMENT,
            root_cause=_SAMPLE_ROOT_CAUSE,
            leg_type="occurrence",
        )
        for s_data in SAMPLE_FIVE_WHY_STEPS:
            canvas.add_step(s_data)
        return canvas

    def to_html(
        self,
        theme: Literal["dark", "light"] = "dark",
        standalone: bool = True,
    ) -> str:
        """Render the 5-Why canvas as themed interactive HTML.

        Parameters
        ----------
        theme : Literal["dark", "light"], default "dark"
            Color theme palette.
        standalone : bool, default True
            If True, generates a full standalone HTML5 document; if False, generates an embeddable container.

        Returns
        -------
        str
            Rendered HTML string.
        """
        if theme not in ("dark", "light"):
            raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

        summary = self.get_summary()

        if theme == "dark":
            c_bg_page = BG_PRIMARY
            c_bg_card = BG_CARD
            c_bg_subcard = BG_SECONDARY
            c_border = BORDER
            c_text_main = TEXT_PRIMARY
            c_text_muted = TEXT_SECONDARY
            c_arrow = AMBER
        else:
            c_bg_page = "#f8fafc"
            c_bg_card = "#ffffff"
            c_bg_subcard = "#f1f5f9"
            c_border = "#e2e8f0"
            c_text_main = "#0f172a"
            c_text_muted = "#64748b"
            c_arrow = "#d97706"

        escaped_title = html.escape(self.title)
        escaped_desc = html.escape(self.description)
        escaped_problem = html.escape(self.problem_statement)
        escaped_root_cause = html.escape(self.root_cause or "Not specified")

        # Verdict badge styling
        verdict = summary.get("verdict", "EMPTY")
        if verdict == "ACCEPT":
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(16,185,129,0.15);color:{SUCCESS};border:1px solid {SUCCESS};text-transform:uppercase;">Verified (ACCEPT)</span>'
        elif verdict == "WARNING":
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};text-transform:uppercase;">Warning</span>'
        elif verdict == "REJECT":
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(239,68,68,0.15);color:{DANGER};border:1px solid {DANGER};text-transform:uppercase;">Rejected</span>'
        else:
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(148,163,184,0.15);color:{c_text_muted};border:1px solid {c_text_muted};text-transform:uppercase;">{html.escape(verdict)}</span>'

        # Classification badge styling
        classification = summary.get("classification", "UNCLASSIFIED")
        if classification == "SYSTEMIC":
            class_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(139,92,246,0.15);color:{VIOLET};border:1px solid {VIOLET};">Systemic</span>'
        elif classification == "TECHNICAL_PROCESS":
            class_badge = '<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(56,189,248,0.15);color:#38bdf8;border:1px solid #38bdf8;">Technical / Process</span>'
        elif classification == "HUMAN_INDIVIDUAL":
            class_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(239,68,68,0.15);color:{DANGER};border:1px solid {DANGER};">Individual Human</span>'
        else:
            class_badge = f'<span style="color:{c_text_muted};">—</span>'

        # Step cards HTML
        step_cards_html: list[str] = []
        for step in self.steps:
            # Reversibility badge
            if step.is_reversible:
                rev_badge = f'<span style="font-size:11px;font-weight:600;color:{SUCCESS};background-color:rgba(16,185,129,0.1);padding:2px 6px;border-radius:4px;border:1px solid {SUCCESS};">Reversible</span>'
            else:
                rev_badge = f'<span style="font-size:11px;font-weight:600;color:{DANGER};background-color:rgba(239,68,68,0.1);padding:2px 6px;border-radius:4px;border:1px solid {DANGER};">Non-Reversible</span>'

            # Anti-pattern badge
            if step.anti_pattern_badge:
                ap_badge_html = f'<span style="font-size:11px;font-weight:700;color:{DANGER};background-color:rgba(239,68,68,0.15);padding:2px 8px;border-radius:4px;border:1px solid {DANGER};text-transform:uppercase;">Anti-Pattern: {html.escape(step.anti_pattern_badge)}</span>'
            else:
                ap_badge_html = ""

            # Reverse therefore display
            if step.reverse_therefore:
                therefore_html = f"""
                <div style="margin-top:10px;padding:8px 12px;background-color:{c_bg_subcard};border-radius:6px;border-left:3px solid {c_arrow};font-size:12px;color:{c_text_muted};">
                    <span style="font-weight:600;color:{c_arrow};">Reverse Check (Therefore):</span> {html.escape(step.reverse_therefore)}
                </div>
                """
            else:
                therefore_html = ""

            card = f"""
            <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:10px;padding:16px;margin-bottom:14px;transition:transform 0.15s ease;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background-color:{AMBER};color:#000000;border-radius:50%;font-size:12px;font-weight:700;">{step.step_number}</span>
                        <span style="font-weight:700;font-size:14px;color:{c_text_main};">Why Step {step.step_number}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        {ap_badge_html}
                        {rev_badge}
                    </div>
                </div>
                <div style="margin-bottom:8px;font-size:13px;">
                    <span style="font-weight:600;color:{AMBER};">Why:</span> <span style="color:{c_text_main};">{html.escape(step.why)}</span>
                </div>
                <div style="font-size:13px;">
                    <span style="font-weight:600;color:{SUCCESS};">Because:</span> <span style="color:{c_text_main};">{html.escape(step.because)}</span>
                </div>
                {therefore_html}
            </div>
            """
            step_cards_html.append(card)

        if not step_cards_html:
            empty_state = f"""
            <div style="background-color:{c_bg_card};border:1px dashed {c_border};border-radius:10px;padding:36px 20px;text-align:center;color:{c_text_muted};font-style:italic;">
                No 5-Why steps recorded in canvas. Add steps to begin root cause investigation.
            </div>
            """
            step_cards_html.append(empty_state)

        steps_joined = "".join(step_cards_html)

        # Findings / Recommendations alert box
        findings = summary.get("findings", [])
        recommendations = summary.get("recommendations", [])

        findings_list_items = "".join(f"<li>{html.escape(f)}</li>" for f in findings)
        recs_list_items = "".join(f"<li>{html.escape(r)}</li>" for r in recommendations)

        if findings_list_items or recs_list_items:
            findings_section = f"""
                <div style="font-weight:700;color:{DANGER};margin-bottom:6px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Identified Causal Findings / Anti-Patterns:</div>
                <ul style="margin:0 0 12px 0;padding-left:20px;font-size:12px;color:{c_text_muted};line-height:1.6;">
                    {findings_list_items}
                </ul>
            """ if findings_list_items else ""
            recs_section = f"""
                <div style="font-weight:700;color:{VIOLET};margin-bottom:6px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Engineering Recommendations &amp; Corrective Action:</div>
                <ul style="margin:0;padding-left:20px;font-size:12px;color:{c_text_muted};line-height:1.6;">
                    {recs_list_items}
                </ul>
            """ if recs_list_items else ""
            recs_html = f"""
            <div style="background-color:rgba(139,92,246,0.08);border:1px solid {VIOLET};border-radius:8px;padding:14px 18px;margin-top:20px;color:{c_text_main};">
                {findings_section}
                {recs_section}
            </div>
            """
        else:
            recs_html = ""


        # Leg type tag
        leg_tag_html = ""
        if self.leg_type:
            leg_tag_html = f'<span style="background-color:rgba(56,189,248,0.15);color:#38bdf8;border:1px solid #38bdf8;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;">Leg: {html.escape(self.leg_type.upper())}</span>'

        body_content = f"""
<div class="qes-five-why-canvas" style="font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background-color:{c_bg_page};color:{c_text_main};padding:24px;border-radius:12px;box-sizing:border-box;border:1px solid {c_border};">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid {c_border};">
        <div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <h2 style="margin:0;font-size:20px;font-weight:700;color:{c_text_main};">{escaped_title}</h2>
                <span style="background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;">AIAG CQI-20 &amp; Ford G8D</span>
                {leg_tag_html}
            </div>
            <p style="margin:6px 0 0 0;font-size:13px;color:{c_text_muted};">{escaped_desc}</p>
        </div>
        <div style="font-size:12px;color:{c_text_muted};text-align:right;">
            <span>Single-Writer Reference Canvas</span>
        </div>
    </div>

    <!-- Problem Statement Box -->
    <div style="background-color:{c_bg_card};border:1px solid {c_border};border-left:4px solid {AMBER};border-radius:8px;padding:12px 16px;margin-bottom:20px;">
        <div style="font-size:11px;font-weight:700;color:{AMBER};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Problem Statement / Effect:</div>
        <div style="font-size:14px;font-weight:600;color:{c_text_main};">{escaped_problem}</div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:12px;margin-bottom:24px;">
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Total Steps</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["total_steps"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Reversibility</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["reversibility_score"]:.0%}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Verdict</div>
            <div style="margin-top:6px;">{verdict_badge}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Classification</div>
            <div style="margin-top:6px;">{class_badge}</div>
        </div>
    </div>

    <!-- Causal Chain Cascade -->
    <div style="margin-bottom:20px;">
        <div style="font-size:13px;font-weight:700;color:{c_text_muted};text-transform:uppercase;margin-bottom:12px;letter-spacing:0.5px;">Causal Chain Cascade &amp; Reversible Logic:</div>
        {steps_joined}
    </div>

    <!-- Terminal Root Cause Box -->
    <div style="background-color:{c_bg_card};border:1px solid {c_border};border-left:4px solid {SUCCESS};border-radius:8px;padding:12px 16px;margin-bottom:20px;">
        <div style="font-size:11px;font-weight:700;color:{SUCCESS};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Terminal Root Cause:</div>
        <div style="font-size:14px;font-weight:600;color:{c_text_main};">{escaped_root_cause}</div>
    </div>

    {recs_html}
</div>
        """

        if not standalone:
            return body_content

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title}</title>
    <style>
        body {{
            margin: 0;
            padding: 24px;
            background-color: {c_bg_page};
            color: {c_text_main};
            font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
        }}
    </style>
</head>
<body>
{body_content}
</body>
</html>"""


def load_sample_5why_canvas(
    title: str = "5-Why Root Cause Analysis Canvas",
) -> FiveWhyCanvas:
    """Load reference benchmark 5-Why canvas."""
    return FiveWhyCanvas.load_sample(title=title)


def render_five_why(
    chain: FiveWhyChain | list[dict[str, Any]] | None = None,
    problem_statement: str = "Problem Statement",
    root_cause: str | None = None,
    leg_type: str | None = None,
    title: str = "5-Why Root Cause Analysis Canvas",
    theme: Literal["dark", "light"] = "dark",
    standalone: bool = True,
) -> str:
    """Helper function to render a 5-Why causal chain as themed HTML."""
    if chain is None:
        canvas = FiveWhyCanvas.load_sample(title=title)
    elif isinstance(chain, FiveWhyChain):
        canvas = FiveWhyCanvas(
            title=title,
            problem_statement=chain.problem_statement,
            root_cause=chain.root_cause,
            leg_type=leg_type,
        )
        for s in chain.steps:
            canvas.add_step(
                FiveWhyCanvasStep(
                    step_number=s.step_number,
                    why=s.why,
                    because=s.because,
                )
            )
    elif isinstance(chain, list):
        canvas = FiveWhyCanvas(
            title=title,
            problem_statement=problem_statement,
            root_cause=root_cause,
            leg_type=leg_type,
        )
        for item in chain:
            if isinstance(item, FiveWhyCanvasStep):
                canvas.add_step(item)
            elif isinstance(item, dict):
                canvas.add_step(item)
            else:
                raise TypeError(f"Expected FiveWhyCanvasStep or dict in chain list, got {type(item).__name__}")
    else:
        raise TypeError(f"chain must be FiveWhyChain, list of dicts, or None, got {type(chain).__name__}")


    return canvas.to_html(theme=theme, standalone=standalone)

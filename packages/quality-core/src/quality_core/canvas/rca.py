"""
rca.py
Single-writer visual 5-Why, 6M Fishbone, and Kepner-Tregoe Is/Is-Not Canvas reference implementations for Quality Platform.

Provides `FiveWhyCanvasStep`, `FiveWhyCanvas`, `FishboneCanvasCause`, `FishboneCanvas`,
`IsIsNotCanvasRow`, and `IsIsNotCanvas` controllers for managing in-memory 5-Why causal chains,
6M Fishbone (Ishikawa) cause-and-effect diagrams, and Kepner-Tregoe Is/Is-Not scoping matrices
with deterministic validation, empty branch/dimension auditing, sample benchmark datasets,
and theme-aligned HTML canvas rendering (dark and light palettes).

Standards References:
- Charles H. Kepner & Benjamin B. Tregoe, The New Rational Manager (Updated Edition, 1997), Chapters 2 & 3.
- Kaoru Ishikawa, Guide to Quality Control (2nd Revised Edition, 1986), Chapter 3.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 4, Section 5 & Section G1.
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D2, D4 & D7.
- Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
"""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

from quality_core.rca.fishbone import (
    FishboneCategorizationResult,
    categorize_fishbone,
)
from quality_core.rca.five_why import (
    FiveWhyValidationResult,
    validate_five_why_chain,
)
from quality_core.rca.is_is_not import (
    IsIsNotScopingResult,
    scope_is_is_not,
)
from quality_core.rca.schema import (
    CATEGORY_6M_ALIASES,
    CATEGORY_6M_VALUES,
    KT_DIMENSIONS,
    Category6M,
    FishboneCause,
    FishboneDataset,
    FiveWhyChain,
    IsIsNotMatrix,
    IsIsNotRow,
    KTDimension,
)
from quality_core.theme.palette import (
    AMBER,
    AMBER_DARK,
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
    "SAMPLE_FISHBONE_CAUSES",
    "SAMPLE_FISHBONE_DATASET",
    "SAMPLE_FIVE_WHY_STEPS",
    "SAMPLE_IS_IS_NOT_MATRIX",
    "SAMPLE_IS_IS_NOT_ROWS",
    "FishboneCanvas",
    "FishboneCanvasCause",
    "FiveWhyCanvas",
    "FiveWhyCanvasStep",
    "IsIsNotCanvas",
    "IsIsNotCanvasRow",
    "load_sample_5why_canvas",
    "load_sample_fishbone_canvas",
    "load_sample_is_is_not_canvas",
    "render_fishbone",
    "render_five_why",
    "render_is_is_not",
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


# ==============================================================================
# 2. 6M Fishbone (Cause-and-Effect / Ishikawa) Canvas
# ==============================================================================

_SAMPLE_FISHBONE_EFFECT = (
    "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)"
)

SAMPLE_FISHBONE_CAUSES: list[dict[str, Any]] = [
    # Man (2 causes)
    {
        "category": "Man",
        "cause": "Operator fatigue during end-of-shift assembly cycle",
        "sub_category": "Fatigue",
    },
    {
        "category": "Man",
        "cause": "Inconsistent rod seal insertion technique across shifts",
        "sub_category": "Training",
    },
    # Machine (2 causes)
    {
        "category": "Machine",
        "cause": "CNC rod turning lathe spindle runout exceeding 0.015 mm",
        "sub_category": "Tooling",
    },
    {
        "category": "Machine",
        "cause": "Pneumatic seal crimping fixture misalignment",
        "sub_category": "Equipment",
    },
    # Method (2 causes)
    {
        "category": "Method",
        "cause": "Work instruction missing torque sequence for cylinder tie-rods",
        "sub_category": "Standard Work",
    },
    {
        "category": "Method",
        "cause": "Inadequate lubrication specification for rod wiper assembly",
        "sub_category": "Process",
    },
    # Material (2 causes)
    {
        "category": "Material",
        "cause": "NBR rod seal batch hardness variation (Durometer 65 vs 75 Shore A)",
        "sub_category": "Incoming Material",
    },
    {
        "category": "Material",
        "cause": "Anodized aluminum barrel bore surface roughness out of spec",
        "sub_category": "Raw Material",
    },
    # Measurement (2 causes)
    {
        "category": "Measurement",
        "cause": "Air leakage test pressure decay gage uncalibrated (drift > 0.05 bar)",
        "sub_category": "Calibration",
    },
    {
        "category": "Measurement",
        "cause": "Dial indicator rod concentricity fixture deflection",
        "sub_category": "Gage R&R",
    },
    # Environment (2 causes)
    {
        "category": "Environment",
        "cause": "Assembly cleanroom ambient temperature fluctuation (+/- 8 deg C)",
        "sub_category": "Temperature",
    },
    {
        "category": "Environment",
        "cause": "Airborne particulate contamination in seal staging area",
        "sub_category": "Cleanliness",
    },
]

SAMPLE_FISHBONE_DATASET: dict[str, Any] = {
    "effect": _SAMPLE_FISHBONE_EFFECT,
    "causes": SAMPLE_FISHBONE_CAUSES,
}


@dataclass
class FishboneCanvasCause:
    """Individual cause item within the 6M Fishbone canvas.

    Enforces field validation and captures category (Category6M), cause description,
    optional sub-category, and duplicate flag.
    """

    category: Category6M
    cause: str
    sub_category: str | None = None
    is_duplicate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError(f"category must be a non-empty string, got {self.category!r}")
        clean_cat = self.category.strip()
        lowered = clean_cat.lower()
        if lowered in CATEGORY_6M_ALIASES:
            self.category = CATEGORY_6M_ALIASES[lowered]
        elif clean_cat in CATEGORY_6M_VALUES:
            self.category = cast(Category6M, clean_cat)
        else:
            raise ValueError(
                f"Invalid 6M category: {clean_cat!r}. Must be one of {list(CATEGORY_6M_VALUES)} or recognized alias."
            )

        if not isinstance(self.cause, str) or not self.cause.strip():
            raise ValueError(f"cause must be a non-empty string, got {self.cause!r}")
        self.cause = self.cause.strip()

        if self.sub_category is not None:
            if not isinstance(self.sub_category, str) or not self.sub_category.strip():
                self.sub_category = None
            else:
                self.sub_category = self.sub_category.strip()

        if not isinstance(self.is_duplicate, bool):
            raise TypeError(
                f"is_duplicate must be a boolean, got {type(self.is_duplicate).__name__}: {self.is_duplicate!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the canvas cause."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FishboneCanvasCause:
        """Construct a FishboneCanvasCause from a dictionary supporting snake_case or PascalCase keys."""
        if not isinstance(data, dict):
            raise TypeError(f"data must be a dictionary, got {type(data).__name__}: {data!r}")

        def get_field(*names: str, default: Any = ...) -> Any:
            for name in names:
                if name in data:
                    return data[name]
            if default is not ...:
                return default
            raise KeyError(f"Missing required field: {' / '.join(repr(n) for n in names)}")

        category = get_field("category", "Category", "branch", "Branch")
        cause = get_field("cause", "Cause", "description", "Description", "text", "Text")
        sub_category = get_field("sub_category", "SubCategory", "subcategory", "Subcategory", default=None)
        is_duplicate = get_field("is_duplicate", "IsDuplicate", default=False)

        return cls(
            category=category,
            cause=cause,
            sub_category=sub_category,
            is_duplicate=is_duplicate,
        )


class FishboneCanvas:
    """Single-writer visual canvas controller for 6M Fishbone (Ishikawa) diagrams.

    Maintains an in-memory collection of `FishboneCanvasCause`s and problem effect statement.
    Provides cause CRUD operations, deterministic categorization via
    `quality_core.rca.fishbone.categorize_fishbone`, summary metric computation,
    and dark/light themed HTML/SVG canvas rendering.
    """

    def __init__(
        self,
        title: str = "6M Fishbone Cause-and-Effect Canvas",
        description: str = "Deterministic 6M Ishikawa Cause-and-Effect Analysis per Ishikawa (1986) & AIAG CQI-20",
        effect: str = "Problem Effect",
        balance_threshold: float = 0.75,
    ) -> None:
        if isinstance(title, bool) or not isinstance(title, str) or not title.strip():
            raise ValueError(f"title must be a non-empty string, got {title!r}")
        if isinstance(description, bool) or not isinstance(description, str):
            raise TypeError(f"description must be a string, got {description!r}")
        if isinstance(effect, bool) or not isinstance(effect, str) or not effect.strip():
            raise ValueError(f"effect must be a non-empty string, got {effect!r}")
        if isinstance(balance_threshold, bool) or not isinstance(balance_threshold, (int, float)) or not (0.0 < balance_threshold <= 1.0):
            raise ValueError(f"balance_threshold must be a float between 0 and 1, got {balance_threshold!r}")

        self.title = title.strip()
        self.description = description.strip()
        self.effect = effect.strip()
        self.balance_threshold = float(balance_threshold)
        self._causes: list[FishboneCanvasCause] = []

    @property
    def causes(self) -> list[FishboneCanvasCause]:
        """Return list of causes."""
        return list(self._causes)

    @property
    def rows(self) -> list[FishboneCanvasCause]:
        """Alias for causes to maintain unified canvas API."""
        return self.causes

    def add_cause(self, cause: FishboneCanvasCause | dict[str, Any]) -> FishboneCanvasCause:
        """Add a cause to the canvas."""
        if isinstance(cause, dict):
            cause_obj = FishboneCanvasCause.from_dict(cause)
        elif isinstance(cause, FishboneCanvasCause):
            cause_obj = cause
        else:
            raise TypeError(f"cause must be a FishboneCanvasCause or dict, got {type(cause).__name__}: {cause!r}")

        self._causes.append(cause_obj)
        return cause_obj

    def remove_cause(self, index_or_cause: int | str | FishboneCanvasCause) -> bool:
        """Remove a cause by integer index, exact cause text, or object. Returns True if removed, False if not found."""
        if isinstance(index_or_cause, int) and not isinstance(index_or_cause, bool):
            if 0 <= index_or_cause < len(self._causes):
                self._causes.pop(index_or_cause)
                return True
            return False
        if isinstance(index_or_cause, str):
            target = index_or_cause.strip().lower()
            for idx, c in enumerate(self._causes):
                if c.cause.strip().lower() == target:
                    self._causes.pop(idx)
                    return True
            return False
        if isinstance(index_or_cause, FishboneCanvasCause):
            if index_or_cause in self._causes:
                self._causes.remove(index_or_cause)
                return True
            return False
        raise TypeError(f"index_or_cause must be an int, str, or FishboneCanvasCause, got {type(index_or_cause).__name__}")

    def get_causes_by_category(self, category: str) -> list[FishboneCanvasCause]:
        """Retrieve all causes belonging to a specific 6M category (normalized)."""
        if not isinstance(category, str):
            raise TypeError(f"category must be a string, got {type(category).__name__}")
        clean = category.strip().lower()
        norm_cat = CATEGORY_6M_ALIASES.get(clean, category.strip())
        return [c for c in self._causes if c.category == norm_cat]

    def clear_causes(self) -> None:
        """Clear all causes from the canvas."""
        self._causes.clear()

    def set_effect(self, effect: str) -> None:
        """Update the problem effect statement."""
        if isinstance(effect, bool) or not isinstance(effect, str) or not effect.strip():
            raise ValueError(f"effect must be a non-empty string, got {effect!r}")
        self.effect = effect.strip()

    def categorize(self) -> FishboneCategorizationResult:
        """Execute deterministic 6M categorization and update cause metadata."""
        if not self._causes:
            raise ValueError("Canvas contains no causes to categorize.")

        raw_causes = [c.to_dict() for c in self._causes]
        result = categorize_fishbone(
            data=raw_causes,
            effect_statement=self.effect,
            check_balance=True,
            balance_threshold=self.balance_threshold,
        )

        # Update is_duplicate flags on causes
        dupe_texts = {d["cause"].strip().lower() for d in result.duplicate_causes}
        for c in self._causes:
            if c.cause.strip().lower() in dupe_texts:
                c.is_duplicate = True

        return result

    def get_summary(self) -> dict[str, Any]:
        """Compute summary categorization and 6M branch metrics across all canvas causes."""
        total_causes = len(self._causes)
        if total_causes == 0:
            return {
                "total_causes": 0,
                "active_branches_count": 0,
                "empty_branches_count": 6,
                "empty_branches": list(CATEGORY_6M_VALUES),
                "branch_counts": {b: 0 for b in CATEGORY_6M_VALUES},
                "valid": False,
                "verdict": "EMPTY",
                "top_branch": None,
                "top_branch_count": 0,
                "top_branch_percentage": 0.0,
                "findings": ["Canvas contains no causes."],
                "recommendations": ["Brainstorm and populate potential causes across the 6M categories."],
            }

        try:
            result = self.categorize()
            active_branches = [b for b, count in result.branch_counts.items() if count > 0]
            top_branch_tuple = max(result.branch_counts.items(), key=lambda x: x[1]) if total_causes > 0 else (None, 0)
            top_branch_name = top_branch_tuple[0] if top_branch_tuple[1] > 0 else None
            top_branch_cnt = top_branch_tuple[1]
            top_branch_pct = (top_branch_cnt / total_causes) if total_causes > 0 else 0.0

            return {
                "total_causes": total_causes,
                "active_branches_count": len(active_branches),
                "empty_branches_count": len(result.empty_branches),
                "empty_branches": result.empty_branches,
                "branch_counts": result.branch_counts,
                "valid": result.valid,
                "verdict": result.verdict,
                "top_branch": top_branch_name,
                "top_branch_count": top_branch_cnt,
                "top_branch_percentage": top_branch_pct,
                "findings": result.warnings,
                "recommendations": result.recommendations,
            }
        except Exception as exc:
            return {
                "total_causes": total_causes,
                "active_branches_count": 0,
                "empty_branches_count": 6,
                "empty_branches": list(CATEGORY_6M_VALUES),
                "branch_counts": {b: 0 for b in CATEGORY_6M_VALUES},
                "valid": False,
                "verdict": "ERROR",
                "top_branch": None,
                "top_branch_count": 0,
                "top_branch_percentage": 0.0,
                "findings": [str(exc)],
                "recommendations": ["Correct cause categories or field constraints to enable categorization."],
            }

    @classmethod
    def load_sample(cls, title: str = "6M Fishbone Cause-and-Effect Canvas") -> FishboneCanvas:
        """Load the standard reference Sentinel-8D Pneumatic Cylinder Manufacturing Case Study."""
        canvas = cls(
            title=title,
            description="Reference Sentinel-8D Pneumatic Cylinder Manufacturing Case Study (Stroke Binding & Seal Leakage)",
            effect=_SAMPLE_FISHBONE_EFFECT,
            balance_threshold=0.75,
        )
        for c_data in SAMPLE_FISHBONE_CAUSES:
            canvas.add_cause(c_data)
        return canvas

    def to_html(
        self,
        theme: Literal["dark", "light"] = "dark",
        standalone: bool = True,
    ) -> str:
        """Render the 6M Fishbone canvas as themed interactive HTML/SVG.

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
            c_rib_color = "#475569"
        else:
            c_bg_page = "#f8fafc"
            c_bg_card = "#ffffff"
            c_bg_subcard = "#f1f5f9"
            c_border = "#e2e8f0"
            c_text_main = "#0f172a"
            c_text_muted = "#64748b"
            c_arrow = AMBER_DARK
            c_rib_color = "#94a3b8"

        escaped_title = html.escape(self.title)
        escaped_desc = html.escape(self.description)
        escaped_effect = html.escape(self.effect)

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

        # Group causes by 6M
        branch_counts = summary.get("branch_counts", {b: 0 for b in CATEGORY_6M_VALUES})
        grouped: dict[str, list[FishboneCanvasCause]] = {b: [] for b in CATEGORY_6M_VALUES}
        for c in self._causes:
            if c.category in grouped:
                grouped[c.category].append(c)

        # Top rib coordinates (Man, Machine, Method)
        # Rib 1 (Man): start (120, 60) -> spine (240, 250)
        # Rib 2 (Machine): start (330, 60) -> spine (450, 250)
        # Rib 3 (Method): start (540, 60) -> spine (660, 250)
        # Bottom rib coordinates (Material, Measurement, Environment)
        # Rib 4 (Material): start (120, 440) -> spine (240, 250)
        # Rib 5 (Measurement): start (330, 440) -> spine (450, 250)
        # Rib 6 (Environment): start (540, 440) -> spine (660, 250)

        svg_ribs_html: list[str] = []
        top_branches = [("Man", 120, 60, 240, 250), ("Machine", 330, 60, 450, 250), ("Method", 540, 60, 660, 250)]
        bottom_branches = [("Material", 120, 440, 240, 250), ("Measurement", 330, 440, 450, 250), ("Environment", 540, 440, 660, 250)]

        for branch_name, x_start, y_start, x_end, y_end in top_branches:
            cnt = branch_counts.get(branch_name, 0)
            branch_causes = grouped.get(branch_name, [])
            # Rib line
            svg_ribs_html.append(
                f'<line x1="{x_start}" y1="{y_start}" x2="{x_end}" y2="{y_end}" stroke="{c_rib_color}" stroke-width="2.5"/>'
            )
            # Label
            svg_ribs_html.append(
                f'<rect x="{x_start - 45}" y="{y_start - 30}" width="90" height="24" rx="4" fill="{c_bg_card}" stroke="{c_border}" stroke-width="1"/>'
            )
            svg_ribs_html.append(
                f'<text x="{x_start}" y="{y_start - 14}" text-anchor="middle" font-size="11" font-weight="700" fill="{c_text_main}">{branch_name.upper()} ({cnt})</text>'
            )
            # Causes horizontal branch lines
            for c_idx, cause_obj in enumerate(branch_causes[:3]):
                t = (c_idx + 1) / (min(len(branch_causes), 3) + 1)
                bx = x_start + t * (x_end - x_start)
                by = y_start + t * (y_end - y_start)
                branch_len = 65
                svg_ribs_html.append(
                    f'<line x1="{bx - branch_len}" y1="{by}" x2="{bx}" y2="{by}" stroke="{c_border}" stroke-width="1.5"/>'
                )
                escaped_c_text = html.escape(cause_obj.cause)
                short_text = html.escape(cause_obj.cause[:18] + ("…" if len(cause_obj.cause) > 18 else ""))
                svg_ribs_html.append(
                    f'<text x="{bx - branch_len - 4}" y="{by - 3}" text-anchor="end" font-size="9" fill="{c_text_muted}"><title>{escaped_c_text}</title>{short_text}</text>'
                )

        for branch_name, x_start, y_start, x_end, y_end in bottom_branches:
            cnt = branch_counts.get(branch_name, 0)
            branch_causes = grouped.get(branch_name, [])
            # Rib line
            svg_ribs_html.append(
                f'<line x1="{x_start}" y1="{y_start}" x2="{x_end}" y2="{y_end}" stroke="{c_rib_color}" stroke-width="2.5"/>'
            )
            # Label
            svg_ribs_html.append(
                f'<rect x="{x_start - 55}" y="{y_start + 8}" width="110" height="24" rx="4" fill="{c_bg_card}" stroke="{c_border}" stroke-width="1"/>'
            )
            svg_ribs_html.append(
                f'<text x="{x_start}" y="{y_start + 24}" text-anchor="middle" font-size="11" font-weight="700" fill="{c_text_main}">{branch_name.upper()} ({cnt})</text>'
            )
            # Causes horizontal branch lines
            for c_idx, cause_obj in enumerate(branch_causes[:3]):
                t = (c_idx + 1) / (min(len(branch_causes), 3) + 1)
                bx = x_start + t * (x_end - x_start)
                by = y_start + t * (y_end - y_start)
                branch_len = 65
                svg_ribs_html.append(
                    f'<line x1="{bx - branch_len}" y1="{by}" x2="{bx}" y2="{by}" stroke="{c_border}" stroke-width="1.5"/>'
                )
                escaped_c_text = html.escape(cause_obj.cause)
                short_text = html.escape(cause_obj.cause[:18] + ("…" if len(cause_obj.cause) > 18 else ""))
                svg_ribs_html.append(
                    f'<text x="{bx - branch_len - 4}" y="{by + 10}" text-anchor="end" font-size="9" fill="{c_text_muted}"><title>{escaped_c_text}</title>{short_text}</text>'
                )

        svg_content = f"""
        <svg viewBox="0 0 1000 500" width="100%" height="340" style="background-color:{c_bg_subcard};border-radius:10px;border:1px solid {c_border};">
            <defs>
                <marker id="fishbone-arrow-{theme}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="{c_arrow}"/>
                </marker>
            </defs>
            <!-- Central Spine -->
            <line x1="40" y1="250" x2="720" y2="250" stroke="{c_arrow}" stroke-width="4" marker-end="url(#fishbone-arrow-{theme})"/>

            <!-- 6M Ribs and Branches -->
            {''.join(svg_ribs_html)}

            <!-- Problem Effect Box -->
            <rect x="740" y="190" width="240" height="120" rx="10" fill="{c_bg_card}" stroke="{c_arrow}" stroke-width="2"/>
            <text x="860" y="215" text-anchor="middle" font-size="10" font-weight="700" fill="{c_arrow}" letter-spacing="0.5">PROBLEM EFFECT</text>
            <foreignObject x="748" y="222" width="224" height="80">
                <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;color:{c_text_main};text-align:center;line-height:1.3;padding:4px;overflow:hidden;text-overflow:ellipsis;">
                    {escaped_effect}
                </div>
            </foreignObject>
        </svg>
        """

        # 6M Category Breakdown Grid
        category_cards_html: list[str] = []
        for cat in CATEGORY_6M_VALUES:
            cat_causes = grouped.get(cat, [])
            cnt = len(cat_causes)
            if cnt == 0:
                body_items = f'<div style="font-size:12px;color:{c_text_muted};font-style:italic;padding:8px 0;">Empty branch (no causes listed)</div>'
                badge_bg = "rgba(239,68,68,0.1)"
                badge_color = DANGER
            else:
                items_list = []
                for c in cat_causes:
                    sub_tag = f'<span style="background-color:rgba(139,92,246,0.12);color:{VIOLET};padding:1px 5px;border-radius:3px;font-size:10px;margin-left:4px;">{html.escape(c.sub_category)}</span>' if c.sub_category else ""
                    dupe_tag = f'<span style="background-color:rgba(239,68,68,0.15);color:{DANGER};padding:1px 5px;border-radius:3px;font-size:10px;margin-left:4px;font-weight:700;">DUPLICATE</span>' if c.is_duplicate else ""
                    items_list.append(
                        f'<li style="margin-bottom:6px;font-size:12px;color:{c_text_main};line-height:1.4;">'
                        f'{html.escape(c.cause)}{sub_tag}{dupe_tag}'
                        f'</li>'
                    )
                body_items = f'<ul style="margin:6px 0 0 0;padding-left:18px;">{"".join(items_list)}</ul>'
                badge_bg = "rgba(16,185,129,0.1)"
                badge_color = SUCCESS

            card = f"""
            <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:700;font-size:13px;color:{c_text_main};">{cat}</span>
                    <span style="font-size:11px;font-weight:700;color:{badge_color};background-color:{badge_bg};padding:2px 8px;border-radius:4px;">{cnt}</span>
                </div>
                {body_items}
            </div>
            """
            category_cards_html.append(card)

        cards_grid_html = f"""
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:12px;margin-top:20px;">
            {''.join(category_cards_html)}
        </div>
        """

        # Findings / Recommendations alert box
        findings = summary.get("findings", [])
        recommendations = summary.get("recommendations", [])

        findings_list_items = "".join(f"<li>{html.escape(f)}</li>" for f in findings)
        recs_list_items = "".join(f"<li>{html.escape(r)}</li>" for r in recommendations)

        if findings_list_items or recs_list_items:
            findings_section = f"""
                <div style="font-weight:700;color:{DANGER};margin-bottom:6px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Identified 6M Branch Findings:</div>
                <ul style="margin:0 0 12px 0;padding-left:20px;font-size:12px;color:{c_text_muted};line-height:1.6;">
                    {findings_list_items}
                </ul>
            """ if findings_list_items else ""
            recs_section = f"""
                <div style="font-weight:700;color:{VIOLET};margin-bottom:6px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Engineering Recommendations:</div>
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

        top_branch_label = html.escape(f"{summary['top_branch']} ({summary['top_branch_count']})" if summary.get("top_branch") else "None")

        body_content = f"""
<div class="qes-fishbone-canvas" style="font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background-color:{c_bg_page};color:{c_text_main};padding:24px;border-radius:12px;box-sizing:border-box;border:1px solid {c_border};">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid {c_border};">
        <div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <h2 style="margin:0;font-size:20px;font-weight:700;color:{c_text_main};">{escaped_title}</h2>
                <span style="background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;">Ishikawa 6M &amp; AIAG CQI-20</span>
            </div>
            <p style="margin:6px 0 0 0;font-size:13px;color:{c_text_muted};">{escaped_desc}</p>
        </div>
        <div style="font-size:12px;color:{c_text_muted};text-align:right;">
            <span>Single-Writer Reference Canvas</span>
        </div>
    </div>

    <!-- Problem Effect Box -->
    <div style="background-color:{c_bg_card};border:1px solid {c_border};border-left:4px solid {AMBER};border-radius:8px;padding:12px 16px;margin-bottom:20px;">
        <div style="font-size:11px;font-weight:700;color:{AMBER};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Problem Statement / Failure Effect:</div>
        <div style="font-size:14px;font-weight:600;color:{c_text_main};">{escaped_effect}</div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:12px;margin-bottom:24px;">
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Total Causes</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["total_causes"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Active Branches</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["active_branches_count"]}/6</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Empty Branches</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["empty_branches_count"]}/6</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Top Branch</div>
            <div style="font-size:14px;font-weight:700;color:{c_text_main};margin-top:8px;">{top_branch_label}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Verdict</div>
            <div style="margin-top:6px;">{verdict_badge}</div>
        </div>
    </div>

    <!-- Fishbone Diagram SVG -->
    <div style="margin-bottom:20px;">
        <div style="font-size:13px;font-weight:700;color:{c_text_muted};text-transform:uppercase;margin-bottom:12px;letter-spacing:0.5px;">6M Ishikawa Cause-and-Effect Diagram:</div>
        {svg_content}
    </div>

    <!-- 6M Categories Detailed Breakdown -->
    <div style="margin-bottom:20px;">
        <div style="font-size:13px;font-weight:700;color:{c_text_muted};text-transform:uppercase;margin-bottom:12px;letter-spacing:0.5px;">6M Branch Breakdown:</div>
        {cards_grid_html}
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


def load_sample_fishbone_canvas(
    title: str = "6M Fishbone Cause-and-Effect Canvas",
) -> FishboneCanvas:
    """Load reference benchmark 6M Fishbone canvas."""
    return FishboneCanvas.load_sample(title=title)


def render_fishbone(
    causes: FishboneDataset | list[dict[str, Any]] | list[FishboneCause] | None = None,
    effect: str = "Problem Effect",
    effect_statement: str | None = None,
    title: str = "6M Fishbone Cause-and-Effect Canvas",
    theme: Literal["dark", "light"] = "dark",
    standalone: bool = True,
    balance_threshold: float = 0.75,
) -> str:
    """Helper function to render a 6M Fishbone dataset as themed HTML.

    Parameters
    ----------
    causes : FishboneDataset | list[dict[str, Any]] | list[FishboneCause] | None, optional
        Causes dataset. If None, loads the standard reference Sentinel-8D benchmark dataset.
    effect : str, default "Problem Effect"
        Problem effect statement.
    effect_statement : str | None, optional
        Optional alias for problem effect statement.
    title : str, default "6M Fishbone Cause-and-Effect Canvas"
        Canvas header title.
    theme : Literal["dark", "light"], default "dark"
        Color theme palette.
    standalone : bool, default True
        Whether to return a complete HTML document or embeddable markup.
    balance_threshold : float, default 0.75
        Threshold fraction for branch concentration balance check.

    Returns
    -------
    str
        Rendered HTML string.
    """
    eff = effect_statement if effect_statement is not None else effect

    if causes is None:
        canvas = FishboneCanvas.load_sample(title=title)
        if eff != "Problem Effect" and eff != _SAMPLE_FISHBONE_EFFECT:
            canvas.set_effect(eff)
    elif isinstance(causes, FishboneDataset):
        canvas = FishboneCanvas(
            title=title,
            effect=effect_statement or causes.effect,
            balance_threshold=balance_threshold,
        )
        for c in causes.causes:
            canvas.add_cause(
                FishboneCanvasCause(
                    category=c.category,
                    cause=c.cause,
                    sub_category=c.sub_category,
                )
            )
    elif isinstance(causes, list):
        canvas = FishboneCanvas(
            title=title,
            effect=eff,
            balance_threshold=balance_threshold,
        )
        for item in causes:
            if isinstance(item, FishboneCanvasCause):
                canvas.add_cause(item)
            elif isinstance(item, FishboneCause):
                canvas.add_cause(
                    FishboneCanvasCause(
                        category=item.category,
                        cause=item.cause,
                        sub_category=item.sub_category,
                    )
                )
            elif isinstance(item, dict):
                canvas.add_cause(item)
            else:
                raise TypeError(f"Expected FishboneCanvasCause, FishboneCause, or dict in causes list, got {type(item).__name__}")
    else:
        raise TypeError(f"causes must be FishboneDataset, list of dicts/causes, or None, got {type(causes).__name__}")

    return canvas.to_html(theme=theme, standalone=standalone)


# ==============================================================================
# 3. Kepner-Tregoe Is/Is-Not Problem Scoping Canvas
# ==============================================================================

_SAMPLE_IS_IS_NOT_PROBLEM_STATEMENT = (
    "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)"
)

SAMPLE_IS_IS_NOT_ROWS: list[dict[str, Any]] = [
    {
        "dimension": "WHAT",
        "is_data": "Pneumatic cylinder stroke binding and seal leakage requiring manual teardown rework",
        "is_not_data": "Piston rod surface defect or electrical control circuit failure",
        "distinctions": "Cylinder bottom mounting face non-parallelism and seal groove distortion",
        "changes": "Bar stock feed misalignment resulting in undersized cut blank length",
        "candidate_cause": "Undersized saw blank causes insufficient clamping depth in CNC milling fixture, leading to face distortion and seal leakage",
    },
    {
        "dimension": "WHERE",
        "is_data": "Cylinder bottom workpiece at CNC milling station (DMC 50H) hydraulic fixture",
        "is_not_data": "Piston rod CNC lathe turning station (Index G200)",
        "distinctions": "Hydraulic vice clamping standard depth requires minimum blank mass",
        "changes": "Sawing station backstop guide position adjusted without laser verification",
        "candidate_cause": "Saw backstop adjustment without verification allowed undersized blanks to enter milling fixture",
    },
    {
        "dimension": "WHEN",
        "is_data": "During post-assembly pneumatic pressure decay acceptance testing (trial run 802 units)",
        "is_not_data": "During initial raw bar stock receiving inspection or pre-machining staging",
        "distinctions": "Defect manifests only under pressurized stroke test after cylinder tie-rod torquing",
        "changes": "Production shift handover between saw operator and CNC milling operator",
        "candidate_cause": "Lack of in-line checkweigher at saw output allowed non-conforming blanks to escape to assembly",
    },
    {
        "dimension": "EXTENT",
        "is_data": "52 out of 802 units (6.48% baseline defect rate), concentrated in blanks with saw_weight < 0.540 kg (15.6% failure rate)",
        "is_not_data": "All 802 units defective (750 units passed acceptance) or uniform across all blank weights",
        "distinctions": "Failure rate increases 1.99x for each 1-sigma decrease in saw cut blank weight",
        "changes": "Sawing cut blank weight variation increased prior to milling operation",
        "candidate_cause": "Saw cut blank weight variation below 0.540 kg is the primary driver of final assembly rework",
    },
]

SAMPLE_IS_IS_NOT_MATRIX: dict[str, Any] = {
    "problem_statement": _SAMPLE_IS_IS_NOT_PROBLEM_STATEMENT,
    "rows": SAMPLE_IS_IS_NOT_ROWS,
}


@dataclass
class IsIsNotCanvasRow:
    """Individual row item within the Kepner-Tregoe Is/Is-Not scoping canvas.

    Enforces field validation across dimension (WHAT, WHERE, WHEN, EXTENT),
    IS data, IS NOT data, optional distinctions, changes, and candidate cause hypothesis.
    """

    dimension: KTDimension | str
    is_data: str
    is_not_data: str
    distinctions: str | None = None
    changes: str | None = None
    candidate_cause: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.dimension, bool) or not isinstance(self.dimension, str) or not self.dimension.strip():
            raise ValueError(f"dimension must be a non-empty string, got {self.dimension!r}")
        clean_dim = self.dimension.strip().upper()
        if clean_dim not in KT_DIMENSIONS:
            raise ValueError(
                f"Invalid Kepner-Tregoe dimension: {self.dimension!r}. Must be one of {list(KT_DIMENSIONS)}."
            )
        self.dimension = cast(KTDimension, clean_dim)

        for str_field in ("is_data", "is_not_data"):
            val = getattr(self, str_field)
            if isinstance(val, bool) or not isinstance(val, str) or not val.strip():
                raise ValueError(f"{str_field} must be a non-empty string, got {val!r}")
            setattr(self, str_field, val.strip())

        for opt_field in ("distinctions", "changes", "candidate_cause"):
            opt_val = getattr(self, opt_field)
            if opt_val is not None:
                if isinstance(opt_val, bool) or not isinstance(opt_val, str):
                    raise TypeError(f"{opt_field} must be a string or None, got {type(opt_val).__name__}")
                clean_opt = opt_val.strip()
                setattr(self, opt_field, clean_opt if clean_opt else None)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the canvas row."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IsIsNotCanvasRow:
        """Construct an IsIsNotCanvasRow from a dictionary supporting snake_case or PascalCase keys."""
        if not isinstance(data, dict):
            raise TypeError(f"data must be a dictionary, got {type(data).__name__}: {data!r}")

        def get_field(*names: str, default: Any = ...) -> Any:
            for name in names:
                if name in data:
                    return data[name]
            if default is not ...:
                return default
            raise KeyError(f"Missing required field: {' / '.join(repr(n) for n in names)}")

        dimension = get_field("dimension", "Dimension", "dim", "Dim")
        is_data = get_field("is_data", "IsData", "is", "Is")
        is_not_data = get_field("is_not_data", "IsNotData", "is_not", "IsNot")
        distinctions = get_field("distinctions", "Distinctions", "distinction", "Distinction", default=None)
        changes = get_field("changes", "Changes", "change", "Change", default=None)
        candidate_cause = get_field(
            "candidate_cause", "CandidateCause", "cause", "Cause", "hypothesis", "Hypothesis", default=None
        )

        return cls(
            dimension=dimension,
            is_data=is_data,
            is_not_data=is_not_data,
            distinctions=distinctions,
            changes=changes,
            candidate_cause=candidate_cause,
        )


class IsIsNotCanvas:
    """Single-writer visual canvas controller for Kepner-Tregoe Is/Is-Not Scoping.

    Maintains an in-memory collection of `IsIsNotCanvasRow`s across the 4 KT dimensions
    (WHAT, WHERE, WHEN, EXTENT) and problem statement. Provides row CRUD operations,
    deterministic scoping via `quality_core.rca.is_is_not.scope_is_is_not`, summary metric
    computation, and dark/light themed HTML canvas rendering.
    """

    def __init__(
        self,
        title: str = "Kepner-Tregoe Is/Is-Not Scoping Canvas",
        description: str = "Comparative Problem Boundary Scoping per Kepner & Tregoe (1997) & AIAG CQI-20",
        problem_statement: str = "Problem Statement",
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
        self._rows: dict[str, IsIsNotCanvasRow] = {}

    @property
    def rows(self) -> list[IsIsNotCanvasRow]:
        """Return rows ordered according to canonical KT_DIMENSIONS sequence."""
        order_map: dict[str, int] = {dim: idx for idx, dim in enumerate(KT_DIMENSIONS)}
        return sorted(self._rows.values(), key=lambda r: order_map.get(str(r.dimension).upper(), 99))

    def add_row(self, row: IsIsNotCanvasRow | dict[str, Any]) -> IsIsNotCanvasRow:
        """Add or update a row in the canvas."""
        if isinstance(row, dict):
            row_obj = IsIsNotCanvasRow.from_dict(row)
        elif isinstance(row, IsIsNotCanvasRow):
            row_obj = row
        else:
            raise TypeError(f"row must be an IsIsNotCanvasRow or dict, got {type(row).__name__}: {row!r}")

        dim_key = str(row_obj.dimension).upper()
        self._rows[dim_key] = row_obj
        return row_obj

    def remove_row(self, dimension_or_index: str | int | IsIsNotCanvasRow) -> bool:
        """Remove a row by dimension string, index, or row instance. Returns True if removed, False if not found."""
        if isinstance(dimension_or_index, IsIsNotCanvasRow):
            dim_key = str(dimension_or_index.dimension).upper()
            if dim_key in self._rows:
                del self._rows[dim_key]
                return True
            return False
        elif isinstance(dimension_or_index, str):
            clean = dimension_or_index.strip().upper()
            if clean in self._rows:
                del self._rows[clean]
                return True
            return False
        elif isinstance(dimension_or_index, int) and not isinstance(dimension_or_index, bool):
            current_rows = self.rows
            if 0 <= dimension_or_index < len(current_rows):
                target = current_rows[dimension_or_index]
                del self._rows[str(target.dimension).upper()]
                return True
            return False
        else:
            raise TypeError(
                f"dimension_or_index must be str, int, or IsIsNotCanvasRow, got {type(dimension_or_index).__name__}"
            )

    def get_row_by_dimension(self, dimension: str) -> IsIsNotCanvasRow | None:
        """Retrieve a row by its KT dimension."""
        if isinstance(dimension, bool) or not isinstance(dimension, str):
            raise TypeError(f"dimension must be a string, got {type(dimension).__name__}")
        return self._rows.get(dimension.strip().upper())

    def get_rows_by_dimension(self, dimension: str) -> list[IsIsNotCanvasRow]:
        """Retrieve rows matching a dimension (returns 0 or 1 item list)."""
        row = self.get_row_by_dimension(dimension)
        return [row] if row is not None else []

    def clear_rows(self) -> None:
        """Clear all rows from the canvas."""
        self._rows.clear()

    def set_problem_statement(self, statement: str) -> None:
        """Update the top-level problem statement."""
        if isinstance(statement, bool) or not isinstance(statement, str) or not statement.strip():
            raise ValueError(f"problem_statement must be a non-empty string, got {statement!r}")
        self.problem_statement = statement.strip()

    def scope(self) -> IsIsNotScopingResult:
        """Execute deterministic KT matrix scoping and update candidate cause metadata."""
        if not self._rows:
            raise ValueError("Canvas contains no rows to scope.")

        raw_rows = [r.to_dict() for r in self.rows]
        result = scope_is_is_not(
            data=raw_rows,
            problem_statement=self.problem_statement,
        )

        # Update rows with synthesized candidate causes if not already specified
        cause_map = {c["dimension"]: c["hypothesis"] for c in result.candidate_causes}
        for r in self._rows.values():
            dim_key = str(r.dimension).upper()
            if not r.candidate_cause and dim_key in cause_map:
                r.candidate_cause = cause_map[dim_key]

        return result

    def get_summary(self) -> dict[str, Any]:
        """Compute summary scoping metrics across all canvas rows."""
        total_rows = len(self._rows)
        if total_rows == 0:
            return {
                "total_rows": 0,
                "valid": False,
                "verdict": "EMPTY",
                "complete_dimensions": [],
                "missing_dimensions": list(KT_DIMENSIONS),
                "complete_dimensions_count": 0,
                "missing_dimensions_count": len(KT_DIMENSIONS),
                "candidate_causes_count": 0,
                "findings": ["Canvas contains no Is/Is-Not rows."],
                "recommendations": ["Add rows across WHAT, WHERE, WHEN, and EXTENT to begin scoping."],
            }

        try:
            result = self.scope()
            return {
                "total_rows": total_rows,
                "valid": result.valid,
                "verdict": result.verdict,
                "complete_dimensions": list(result.complete_dimensions),
                "missing_dimensions": list(result.missing_dimensions),
                "complete_dimensions_count": len(result.complete_dimensions),
                "missing_dimensions_count": len(result.missing_dimensions),
                "candidate_causes_count": len(result.candidate_causes),
                "findings": list(result.warnings),
                "recommendations": list(result.recommendations),
            }
        except Exception as exc:
            return {
                "total_rows": total_rows,
                "valid": False,
                "verdict": "ERROR",
                "complete_dimensions": [],
                "missing_dimensions": list(KT_DIMENSIONS),
                "complete_dimensions_count": 0,
                "missing_dimensions_count": len(KT_DIMENSIONS),
                "candidate_causes_count": 0,
                "findings": [str(exc)],
                "recommendations": ["Correct row dimensions or field constraints to enable scoping."],
            }

    @classmethod
    def load_sample(cls, title: str = "Kepner-Tregoe Is/Is-Not Scoping Canvas") -> IsIsNotCanvas:
        """Load the reference Sentinel-8D pneumatic cylinder manufacturing benchmark dataset."""
        canvas = cls(
            title=title,
            description="Reference Sentinel-8D Problem Solving Case (Pneumatic Cylinder Assembly Rework)",
            problem_statement=_SAMPLE_IS_IS_NOT_PROBLEM_STATEMENT,
        )
        for r_data in SAMPLE_IS_IS_NOT_ROWS:
            canvas.add_row(r_data)
        return canvas

    def to_html(
        self,
        theme: Literal["dark", "light"] = "dark",
        standalone: bool = True,
    ) -> str:
        """Render the Kepner-Tregoe Is/Is-Not canvas as themed interactive HTML.

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
            c_accent = AMBER
        else:
            c_bg_page = "#f8fafc"
            c_bg_card = "#ffffff"
            c_bg_subcard = "#f1f5f9"
            c_border = "#e2e8f0"
            c_text_main = "#0f172a"
            c_text_muted = "#64748b"
            c_accent = "#d97706"

        escaped_title = html.escape(self.title)
        escaped_desc = html.escape(self.description)
        escaped_problem = html.escape(self.problem_statement)

        # Verdict badge styling
        verdict = summary.get("verdict", "EMPTY")
        if verdict == "ACCEPT":
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(16,185,129,0.15);color:{SUCCESS};border:1px solid {SUCCESS};text-transform:uppercase;">Fully Scoped (ACCEPT)</span>'
        elif verdict == "WARNING":
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};text-transform:uppercase;">Warning (Incomplete)</span>'
        elif verdict == "REJECT":
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(239,68,68,0.15);color:{DANGER};border:1px solid {DANGER};text-transform:uppercase;">Rejected</span>'
        else:
            verdict_badge = f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(148,163,184,0.15);color:{c_text_muted};border:1px solid {c_text_muted};text-transform:uppercase;">{html.escape(verdict)}</span>'

        # Dimension color palette map
        dim_color_map = {
            "WHAT": "#38bdf8",
            "WHERE": "#a855f7",
            "WHEN": "#f59e0b",
            "EXTENT": "#f43f5e",
        }

        # Dimension cards HTML
        dimension_cards_html: list[str] = []
        for row in self.rows:
            dim_str = str(row.dimension).upper()
            dim_color = dim_color_map.get(dim_str, c_accent)
            escaped_is = html.escape(row.is_data)
            escaped_is_not = html.escape(row.is_not_data)
            escaped_dist = html.escape(row.distinctions or "—")
            escaped_chg = html.escape(row.changes or "—")

            # Candidate cause chip
            if row.candidate_cause:
                cause_html = f"""
                <div style="margin-top:12px;padding:10px 14px;background-color:{c_bg_subcard};border-radius:6px;border-left:3px solid {VIOLET};font-size:12px;color:{c_text_main};">
                    <span style="font-weight:700;color:{VIOLET};text-transform:uppercase;letter-spacing:0.5px;">Candidate Cause Hypothesis:</span> {html.escape(row.candidate_cause)}
                </div>
                """
            else:
                cause_html = ""

            card = f"""
            <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:10px;padding:18px;margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;background-color:rgba(56,189,248,0.15);color:{dim_color};border:1px solid {dim_color};">{dim_str}</span>
                        <span style="font-weight:700;font-size:14px;color:{c_text_main};">Dimension: {dim_str}</span>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:14px;margin-bottom:8px;">
                    <!-- IS Column -->
                    <div style="background-color:{c_bg_subcard};border:1px solid {c_border};border-left:3px solid {SUCCESS};border-radius:6px;padding:12px;">
                        <div style="font-size:11px;font-weight:700;color:{SUCCESS};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">IS (Observed Fact):</div>
                        <div style="font-size:13px;color:{c_text_main};line-height:1.5;">{escaped_is}</div>
                    </div>

                    <!-- IS NOT Column -->
                    <div style="background-color:{c_bg_subcard};border:1px solid {c_border};border-left:3px solid {DANGER};border-radius:6px;padding:12px;">
                        <div style="font-size:11px;font-weight:700;color:{DANGER};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">IS NOT (Could Be But Is Not):</div>
                        <div style="font-size:13px;color:{c_text_main};line-height:1.5;">{escaped_is_not}</div>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:14px;margin-top:10px;">
                    <!-- Distinctions -->
                    <div style="background-color:{c_bg_subcard};border:1px solid {c_border};border-left:3px solid {c_accent};border-radius:6px;padding:12px;">
                        <div style="font-size:11px;font-weight:700;color:{c_accent};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Distinctions (What Stands Out):</div>
                        <div style="font-size:13px;color:{c_text_muted};line-height:1.5;">{escaped_dist}</div>
                    </div>

                    <!-- Changes -->
                    <div style="background-color:{c_bg_subcard};border:1px solid {c_border};border-left:3px solid {VIOLET};border-radius:6px;padding:12px;">
                        <div style="font-size:11px;font-weight:700;color:{VIOLET};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Changes (What Changed):</div>
                        <div style="font-size:13px;color:{c_text_muted};line-height:1.5;">{escaped_chg}</div>
                    </div>
                </div>

                {cause_html}
            </div>
            """
            dimension_cards_html.append(card)

        if not dimension_cards_html:
            empty_state = f"""
            <div style="background-color:{c_bg_card};border:1px dashed {c_border};border-radius:10px;padding:36px 20px;text-align:center;color:{c_text_muted};font-style:italic;">
                No Kepner-Tregoe Is/Is-Not rows recorded in canvas. Add rows to begin problem boundary scoping.
            </div>
            """
            dimension_cards_html.append(empty_state)

        cards_joined = "".join(dimension_cards_html)

        # Findings / Recommendations alert box
        findings = summary.get("findings", [])
        recommendations = summary.get("recommendations", [])

        findings_list_items = "".join(f"<li>{html.escape(f)}</li>" for f in findings)
        recs_list_items = "".join(f"<li>{html.escape(r)}</li>" for r in recommendations)

        if findings_list_items or recs_list_items:
            findings_section = f"""
                <div style="font-weight:700;color:{DANGER};margin-bottom:6px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Identified Boundary &amp; Scoping Findings:</div>
                <ul style="margin:0 0 12px 0;padding-left:20px;font-size:12px;color:{c_text_muted};line-height:1.6;">
                    {findings_list_items}
                </ul>
            """ if findings_list_items else ""
            recs_section = f"""
                <div style="font-weight:700;color:{VIOLET};margin-bottom:6px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">Engineering Recommendations &amp; Hypothesis Testing:</div>
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

        body_content = f"""
<div class="qes-is-is-not-canvas" style="font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background-color:{c_bg_page};color:{c_text_main};padding:24px;border-radius:12px;box-sizing:border-box;border:1px solid {c_border};">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid {c_border};">
        <div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <h2 style="margin:0;font-size:20px;font-weight:700;color:{c_text_main};">{escaped_title}</h2>
                <span style="background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;">Kepner-Tregoe (1997) &amp; AIAG CQI-20</span>
            </div>
            <p style="margin:6px 0 0 0;font-size:13px;color:{c_text_muted};">{escaped_desc}</p>
        </div>
        <div style="font-size:12px;color:{c_text_muted};text-align:right;">
            <span>Single-Writer Reference Canvas</span>
        </div>
    </div>

    <!-- Problem Statement Box -->
    <div style="background-color:{c_bg_card};border:1px solid {c_border};border-left:4px solid {c_accent};border-radius:8px;padding:12px 16px;margin-bottom:20px;">
        <div style="font-size:11px;font-weight:700;color:{c_accent};text-transform:uppercase;margin-bottom:4px;letter-spacing:0.5px;">Problem Statement / Observed Deviation:</div>
        <div style="font-size:14px;font-weight:600;color:{c_text_main};">{escaped_problem}</div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:12px;margin-bottom:24px;">
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Total Dimensions</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["total_rows"]}/4</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Coverage</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["complete_dimensions_count"]}/4</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Candidate Causes</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["candidate_causes_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Verdict</div>
            <div style="margin-top:6px;">{verdict_badge}</div>
        </div>
    </div>

    <!-- 4-Dimension Comparative Matrix Grid -->
    <div style="margin-bottom:20px;">
        <div style="font-size:13px;font-weight:700;color:{c_text_muted};text-transform:uppercase;margin-bottom:12px;letter-spacing:0.5px;">4-Dimension Problem Boundary Matrix:</div>
        {cards_joined}
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


def load_sample_is_is_not_canvas(
    title: str = "Kepner-Tregoe Is/Is-Not Scoping Canvas",
) -> IsIsNotCanvas:
    """Load reference benchmark Kepner-Tregoe Is/Is-Not canvas."""
    return IsIsNotCanvas.load_sample(title=title)


def render_is_is_not(
    matrix: IsIsNotMatrix | list[dict[str, Any]] | list[IsIsNotRow] | list[IsIsNotCanvasRow] | None = None,
    problem_statement: str = "Problem Statement",
    title: str = "Kepner-Tregoe Is/Is-Not Scoping Canvas",
    theme: Literal["dark", "light"] = "dark",
    standalone: bool = True,
) -> str:
    """Helper function to render a Kepner-Tregoe Is/Is-Not scoping matrix as themed HTML.

    Parameters
    ----------
    matrix : IsIsNotMatrix | list[dict[str, Any]] | list[IsIsNotRow] | list[IsIsNotCanvasRow] | None, optional
        Matrix dataset. If None, loads the standard reference Sentinel-8D benchmark dataset.
    problem_statement : str, default "Problem Statement"
        Problem statement describing the observed deviation or defect.
    title : str, default "Kepner-Tregoe Is/Is-Not Scoping Canvas"
        Canvas header title.
    theme : Literal["dark", "light"], default "dark"
        Color theme palette.
    standalone : bool, default True
        Whether to return a complete HTML document or embeddable markup.

    Returns
    -------
    str
        Rendered HTML string.
    """
    if matrix is None:
        canvas = IsIsNotCanvas.load_sample(title=title)
        if problem_statement != "Problem Statement" and problem_statement != _SAMPLE_IS_IS_NOT_PROBLEM_STATEMENT:
            canvas.set_problem_statement(problem_statement)
    elif isinstance(matrix, IsIsNotMatrix):
        canvas = IsIsNotCanvas(
            title=title,
            problem_statement=matrix.problem_statement if problem_statement == "Problem Statement" else problem_statement,
        )
        for r in matrix.rows:
            canvas.add_row(
                IsIsNotCanvasRow(
                    dimension=r.dimension,
                    is_data=r.is_data,
                    is_not_data=r.is_not_data,
                    distinctions=r.distinctions,
                    changes=r.changes,
                )
            )
    elif isinstance(matrix, list):
        canvas = IsIsNotCanvas(
            title=title,
            problem_statement=problem_statement,
        )
        for item in matrix:
            if isinstance(item, IsIsNotCanvasRow):
                canvas.add_row(item)
            elif isinstance(item, IsIsNotRow):
                canvas.add_row(
                    IsIsNotCanvasRow(
                        dimension=item.dimension,
                        is_data=item.is_data,
                        is_not_data=item.is_not_data,
                        distinctions=item.distinctions,
                        changes=item.changes,
                    )
                )
            elif isinstance(item, dict):
                canvas.add_row(item)
            else:
                raise TypeError(f"Expected IsIsNotCanvasRow, IsIsNotRow, or dict in matrix list, got {type(item).__name__}")
    elif isinstance(matrix, dict):
        ps = matrix.get("problem_statement", problem_statement)
        canvas = IsIsNotCanvas(
            title=title,
            problem_statement=ps if problem_statement == "Problem Statement" else problem_statement,
        )
        rows_list = matrix.get("rows", [matrix])
        if not isinstance(rows_list, list):
            raise TypeError(f"Expected list for rows in dict, got {type(rows_list).__name__}")
        for item in rows_list:
            if isinstance(item, dict):
                canvas.add_row(item)
            elif isinstance(item, (IsIsNotCanvasRow, IsIsNotRow)):
                if isinstance(item, IsIsNotCanvasRow):
                    canvas.add_row(item)
                else:
                    canvas.add_row(
                        IsIsNotCanvasRow(
                            dimension=item.dimension,
                            is_data=item.is_data,
                            is_not_data=item.is_not_data,
                            distinctions=item.distinctions,
                            changes=item.changes,
                        )
                    )
            else:
                raise TypeError(f"Expected dict, IsIsNotCanvasRow, or IsIsNotRow in rows, got {type(item).__name__}")
    else:
        raise TypeError(f"matrix must be IsIsNotMatrix, list of dicts/rows, dict, or None, got {type(matrix).__name__}")

    return canvas.to_html(theme=theme, standalone=standalone)



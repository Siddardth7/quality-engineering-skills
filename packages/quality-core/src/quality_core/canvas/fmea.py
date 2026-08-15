"""
fmea.py
Single-writer visual FMEA Canvas reference implementation for Quality Platform.

Provides `FMEACanvasRow` and `FMEACanvas` controller for managing an in-memory
FMEA grid with deterministic AIAG-VDA 2019 Action Priority and RPN calculations
via `quality_core.scoring`, sample dataset loading, row editing, and theme-aligned
HTML canvas rendering.
"""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from typing import Any

from quality_core.scoring import HIGH, LOW, MEDIUM, action_priority, rpn
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


@dataclass
class FMEACanvasRow:
    """Individual row item within the FMEA canvas.

    Enforces field validation and deterministic calculation of RPN and
    AIAG-VDA 2019 Action Priority (AP) using `quality_core.scoring`.
    """

    id: int
    process_step: str
    component: str
    function: str
    failure_mode: str
    effect: str
    severity: int
    cause: str
    occurrence: int
    current_control: str
    detection: int
    rpn: int = 0
    action_priority: str = ""
    ai_candidate: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"id must be a positive integer, got {self.id!r}")

        for str_field in (
            "process_step",
            "component",
            "function",
            "failure_mode",
            "effect",
            "cause",
            "current_control",
        ):
            val = getattr(self, str_field)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{str_field} must be a non-empty string, got {val!r}")
            setattr(self, str_field, val.strip())

        for num_field in ("severity", "occurrence", "detection"):
            val = getattr(self, num_field)
            if isinstance(val, bool) or not isinstance(val, int):
                raise TypeError(f"{num_field} must be an integer, got {val!r}")
            if not 1 <= val <= 10:
                raise ValueError(f"{num_field} must be between 1 and 10, got {val!r}")

        if not isinstance(self.ai_candidate, bool):
            raise TypeError(f"ai_candidate must be a boolean, got {type(self.ai_candidate).__name__}: {self.ai_candidate!r}")

        # Deterministic scoring via quality_core.scoring
        self.rpn = rpn(self.severity, self.occurrence, self.detection)
        self.action_priority = action_priority(self.severity, self.occurrence, self.detection)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the canvas row."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FMEACanvasRow:
        """Construct an FMEACanvasRow from a dictionary supporting snake_case or PascalCase keys."""
        if not isinstance(data, dict):
            raise TypeError(f"data must be a dictionary, got {type(data).__name__}: {data!r}")

        def get_field(snake_name: str, pascal_name: str, default: Any = ...) -> Any:
            if snake_name in data:
                return data[snake_name]
            if pascal_name in data:
                return data[pascal_name]
            if default is not ...:
                return default
            raise ValueError(f"Missing required field '{snake_name}' or '{pascal_name}'")

        row_id = get_field("id", "ID")
        process_step = get_field("process_step", "Process_Step")
        component = get_field("component", "Component")
        function = get_field("function", "Function")
        failure_mode = get_field("failure_mode", "Failure_Mode")
        effect = get_field("effect", "Effect")
        severity = get_field("severity", "Severity")
        cause = get_field("cause", "Cause")
        occurrence = get_field("occurrence", "Occurrence")
        current_control = get_field("current_control", "Current_Control")
        detection = get_field("detection", "Detection")
        ai_candidate = get_field("ai_candidate", "AI_Candidate", default=False)

        return cls(
            id=row_id,
            process_step=process_step,
            component=component,
            function=function,
            failure_mode=failure_mode,
            effect=effect,
            severity=severity,
            cause=cause,
            occurrence=occurrence,
            current_control=current_control,
            detection=detection,
            ai_candidate=ai_candidate,
        )


# ---------------------------------------------------------------------------
# Reference Benchmark Dataset (Automotive Powertrain & Battery PFMEA)
# ---------------------------------------------------------------------------

SAMPLE_FMEA_ROWS: list[dict[str, Any]] = [
    {
        "id": 1,
        "process_step": "Inverter SMT Assembly",
        "component": "Traction Inverter",
        "function": "Gate driver desaturation protection",
        "failure_mode": "Gate driver desaturation during high-torque acceleration",
        "effect": "Inverter shutdown, loss of vehicle propulsion",
        "severity": 10,
        "cause": "IGBT transient overvoltage spike",
        "occurrence": 4,
        "current_control": "Automated optical inspection & functional test",
        "detection": 4,
        "ai_candidate": False,
    },
    {
        "id": 2,
        "process_step": "Brake Module Machining",
        "component": "Brake-by-Wire",
        "function": "Hydraulic pressure measurement",
        "failure_mode": "Brake-by-wire pressure transducer calibration drift",
        "effect": "Degraded pedal feel, warning indicator displayed",
        "severity": 9,
        "cause": "Piezoresistive element thermal fatigue",
        "occurrence": 5,
        "current_control": "100% End-of-line calibrated pressure sweep",
        "detection": 1,
        "ai_candidate": False,
    },
    {
        "id": 3,
        "process_step": "Pouch Cell Stacking",
        "component": "High Voltage Battery",
        "function": "Cell layer isolation",
        "failure_mode": "Li-ion pouch cell separator puncture from foreign particulate",
        "effect": "Internal cell short circuit, thermal runaway risk",
        "severity": 10,
        "cause": "Particulate contamination in cleanroom stacking cell",
        "occurrence": 6,
        "current_control": "Periodic visual inspection & particle counter",
        "detection": 8,
        "ai_candidate": True,
    },
    {
        "id": 4,
        "process_step": "Steering Sensor Assembly",
        "component": "Steering System",
        "function": "Steering angle measurement",
        "failure_mode": "Steering angle sensor CAN bus frame drop",
        "effect": "Transient loss of lane centering assist",
        "severity": 8,
        "cause": "Connector pin fretting corrosion",
        "occurrence": 3,
        "current_control": "Dual-redundant CAN bus CRC check",
        "detection": 2,
        "ai_candidate": False,
    },
    {
        "id": 5,
        "process_step": "Stator Winding",
        "component": "Traction Motor",
        "function": "Stator phase-to-phase insulation",
        "failure_mode": "Stator insulation dielectric breakdown",
        "effect": "Motor ground fault, reduced torque output",
        "severity": 8,
        "cause": "Varnish void during trickle impregnation",
        "occurrence": 7,
        "current_control": "100% In-line high-potential dielectric test",
        "detection": 1,
        "ai_candidate": False,
    },
    {
        "id": 6,
        "process_step": "Gearbox Final Assembly",
        "component": "Reduction Gearbox",
        "function": "Lubricant retention",
        "failure_mode": "Output shaft rotary oil seal extrusion",
        "effect": "Oil seepage onto underbody, non-safety effect",
        "severity": 6,
        "cause": "Seal lip deformation under thermal cycling",
        "occurrence": 4,
        "current_control": "Press-force depth monitoring",
        "detection": 3,
        "ai_candidate": False,
    },
]


class FMEACanvas:
    """Controller for the in-memory single-writer FMEA visual canvas.

    Provides deterministic risk scoring, CRUD operations, state summarization,
    and styled HTML generation adhering to the Quality Platform theme.
    """

    def __init__(
        self,
        rows: list[FMEACanvasRow | dict[str, Any]] | None = None,
        title: str = "AIAG & VDA 2019 Process FMEA Canvas",
        description: str = "Interactive single-writer visual FMEA canvas with deterministic scoring.",
    ) -> None:
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"title must be a non-empty string, got {title!r}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"description must be a non-empty string, got {description!r}")

        self.title = title.strip()
        self.description = description.strip()
        self._rows: dict[int, FMEACanvasRow] = {}

        if rows is not None:
            if not isinstance(rows, list):
                raise TypeError(f"rows must be a list, got {type(rows).__name__}: {rows!r}")
            for item in rows:
                self.add_row(item)

    @property
    def rows(self) -> list[FMEACanvasRow]:
        """Return the list of canvas rows in insertion order."""
        return list(self._rows.values())

    @classmethod
    def load_sample(
        cls,
        title: str = "AIAG & VDA 2019 Process FMEA Canvas",
        description: str = "Reference Automotive Process FMEA Canvas with Deterministic Action Priority Scoring",
    ) -> FMEACanvas:
        """Create and return an FMEACanvas populated with the reference automotive benchmark dataset."""
        canvas = cls(title=title, description=description)
        for row_dict in SAMPLE_FMEA_ROWS:
            canvas.add_row(row_dict)
        return canvas

    def get_row(self, row_id: int) -> FMEACanvasRow | None:
        """Retrieve a canvas row by its ID, or return None if not found."""
        if isinstance(row_id, bool) or not isinstance(row_id, int):
            raise TypeError(f"row_id must be an integer, got {type(row_id).__name__}: {row_id!r}")
        return self._rows.get(row_id)

    def add_row(self, row: FMEACanvasRow | dict[str, Any]) -> FMEACanvasRow:
        """Add a new row to the canvas. Raises ValueError on duplicate ID."""
        if isinstance(row, dict):
            canvas_row = FMEACanvasRow.from_dict(row)
        elif isinstance(row, FMEACanvasRow):
            canvas_row = row
        else:
            raise TypeError(f"row must be an FMEACanvasRow or dict, got {type(row).__name__}: {row!r}")

        if canvas_row.id in self._rows:
            raise ValueError(f"Row with ID {canvas_row.id} already exists in canvas.")

        self._rows[canvas_row.id] = canvas_row
        return canvas_row

    def edit_row(self, row_id: int, **updates: Any) -> FMEACanvasRow:
        """Update fields of an existing row, deterministically recalculating RPN and Action Priority."""
        if isinstance(row_id, bool) or not isinstance(row_id, int):
            raise TypeError(f"row_id must be an integer, got {type(row_id).__name__}: {row_id!r}")

        if row_id not in self._rows:
            raise KeyError(f"Row with ID {row_id} not found in canvas.")

        existing = self._rows[row_id]
        data = existing.to_dict()

        # Map updates to snake_case field names
        field_mapping: dict[str, str] = {
            "id": "id",
            "ID": "id",
            "process_step": "process_step",
            "Process_Step": "process_step",
            "component": "component",
            "Component": "component",
            "function": "function",
            "Function": "function",
            "failure_mode": "failure_mode",
            "Failure_Mode": "failure_mode",
            "effect": "effect",
            "Effect": "effect",
            "severity": "severity",
            "Severity": "severity",
            "cause": "cause",
            "Cause": "cause",
            "occurrence": "occurrence",
            "Occurrence": "occurrence",
            "current_control": "current_control",
            "Current_Control": "current_control",
            "detection": "detection",
            "Detection": "detection",
            "ai_candidate": "ai_candidate",
            "AI_Candidate": "ai_candidate",
        }

        for k, v in updates.items():
            if k in field_mapping:
                data[field_mapping[k]] = v
            else:
                raise ValueError(f"Unknown field '{k}' in row update")

        new_id = data["id"]
        if new_id != row_id and new_id in self._rows:
            raise ValueError(f"Cannot change row ID to {new_id}: ID already exists in canvas.")

        updated_row = FMEACanvasRow.from_dict(data)

        if new_id != row_id:
            del self._rows[row_id]
        self._rows[new_id] = updated_row
        return updated_row

    def delete_row(self, row_id: int) -> FMEACanvasRow:
        """Remove a row by its ID and return the deleted row."""
        if isinstance(row_id, bool) or not isinstance(row_id, int):
            raise TypeError(f"row_id must be an integer, got {type(row_id).__name__}: {row_id!r}")

        if row_id not in self._rows:
            raise KeyError(f"Row with ID {row_id} not found in canvas.")

        return self._rows.pop(row_id)

    def get_summary(self) -> dict[str, Any]:
        """Compute summary risk metrics across all rows currently in the canvas."""
        total = len(self._rows)
        high = sum(1 for r in self._rows.values() if r.action_priority == HIGH)
        med = sum(1 for r in self._rows.values() if r.action_priority == MEDIUM)
        low = sum(1 for r in self._rows.values() if r.action_priority == LOW)
        max_rpn = max((r.rpn for r in self._rows.values()), default=0)
        ai_candidates = sum(1 for r in self._rows.values() if r.ai_candidate)

        return {
            "total_rows": total,
            "high_count": high,
            "medium_count": med,
            "low_count": low,
            "max_rpn": max_rpn,
            "ai_candidate_count": ai_candidates,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return full structured state dictionary of the canvas."""
        return {
            "title": self.title,
            "description": self.description,
            "rows": [r.to_dict() for r in self.rows],
            "summary": self.get_summary(),
        }

    def to_html(self, standalone: bool = True, theme: str = "dark") -> str:
        """Render the FMEA canvas as a styled HTML view.

        Parameters
        ----------
        standalone : bool, default True
            If True, generates a full standalone HTML5 document. If False, generates
            an embeddable styled container.
        theme : str, default "dark"
            Theme palette to apply ("dark" or "light").

        Returns
        -------
        str
            Rendered HTML string.
        """
        if not isinstance(standalone, bool):
            raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
        if theme not in ("dark", "light"):
            raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

        summary = self.get_summary()

        # Theme color variables
        if theme == "dark":
            c_bg_page = BG_PRIMARY
            c_bg_card = BG_CARD
            c_bg_table_header = BG_SECONDARY
            c_border = BORDER
            c_text_main = TEXT_PRIMARY
            c_text_muted = TEXT_SECONDARY
            c_row_hover = "#242d40"
        else:
            c_bg_page = "#f8fafc"
            c_bg_card = "#ffffff"
            c_bg_table_header = "#f1f5f9"
            c_border = "#e2e8f0"
            c_text_main = "#0f172a"
            c_text_muted = "#64748b"
            c_row_hover = "#f1f5f9"

        escaped_title = html.escape(self.title)
        escaped_desc = html.escape(self.description)

        # Build table rows
        table_rows_html: list[str] = []
        for r in self.rows:
            # Action priority badge
            if r.action_priority == HIGH:
                ap_badge_bg = DANGER
                ap_badge_color = "#ffffff"
            elif r.action_priority == MEDIUM:
                ap_badge_bg = AMBER
                ap_badge_color = "#1e293b"
            else:
                ap_badge_bg = SUCCESS
                ap_badge_color = "#ffffff"

            ap_badge = (
                f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                f'font-size:11px;font-weight:700;background-color:{ap_badge_bg};color:{ap_badge_color};'
                f'letter-spacing:0.5px;">{html.escape(r.action_priority)}</span>'
            )

            # AI Candidate badge
            if r.ai_candidate:
                status_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(139, 92, 246, 0.2);'
                    f'color:{VIOLET};border:1px solid {VIOLET};">[AI Candidate]</span>'
                )
            else:
                status_badge = (
                    '<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    'font-size:11px;font-weight:500;background-color:rgba(16, 185, 129, 0.15);'
                    f'color:{SUCCESS};">Verified</span>'
                )

            row_html = f"""
            <tr style="border-bottom:1px solid {c_border};transition:background-color 0.15s ease;">
                <td style="padding:10px 12px;font-family:monospace;font-weight:600;color:{AMBER};">{r.id}</td>
                <td style="padding:10px 12px;font-weight:500;">{html.escape(r.process_step)}</td>
                <td style="padding:10px 12px;color:{c_text_muted};">{html.escape(r.component)}</td>
                <td style="padding:10px 12px;">{html.escape(r.function)}</td>
                <td style="padding:10px 12px;font-weight:500;">{html.escape(r.failure_mode)}</td>
                <td style="padding:10px 12px;color:{c_text_muted};">{html.escape(r.effect)}</td>
                <td style="padding:10px 12px;text-align:center;font-weight:600;">{r.severity}</td>
                <td style="padding:10px 12px;color:{c_text_muted};">{html.escape(r.cause)}</td>
                <td style="padding:10px 12px;text-align:center;font-weight:600;">{r.occurrence}</td>
                <td style="padding:10px 12px;color:{c_text_muted};">{html.escape(r.current_control)}</td>
                <td style="padding:10px 12px;text-align:center;font-weight:600;">{r.detection}</td>
                <td style="padding:10px 12px;text-align:center;font-family:monospace;font-weight:700;">{r.rpn}</td>
                <td style="padding:10px 12px;text-align:center;">{ap_badge}</td>
                <td style="padding:10px 12px;text-align:center;">{status_badge}</td>
            </tr>
            """
            table_rows_html.append(row_html)

        if not table_rows_html:
            empty_state = f"""
            <tr>
                <td colspan="14" style="padding:32px 16px;text-align:center;color:{c_text_muted};font-style:italic;">
                    No FMEA items recorded in canvas.
                </td>
            </tr>
            """
            table_rows_html.append(empty_state)

        rows_joined = "".join(table_rows_html)

        body_content = f"""
<div class="qes-fmea-canvas" style="font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background-color:{c_bg_page};color:{c_text_main};padding:24px;border-radius:12px;box-sizing:border-box;border:1px solid {c_border};">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid {c_border};">
        <div>
            <div style="display:flex;align-items:center;gap:10px;">
                <h2 style="margin:0;font-size:20px;font-weight:700;color:{c_text_main};">{escaped_title}</h2>
                <span style="background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;">AIAG &amp; VDA 2019</span>
            </div>
            <p style="margin:6px 0 0 0;font-size:13px;color:{c_text_muted};">{escaped_desc}</p>
        </div>
        <div style="font-size:12px;color:{c_text_muted};text-align:right;">
            <span>Single-Writer Reference Canvas</span>
        </div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:12px;margin-bottom:24px;">
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Total Items</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["total_rows"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{DANGER};text-transform:uppercase;">High AP</div>
            <div style="font-size:22px;font-weight:700;color:{DANGER};margin-top:4px;">{summary["high_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{AMBER};text-transform:uppercase;">Medium AP</div>
            <div style="font-size:22px;font-weight:700;color:{AMBER};margin-top:4px;">{summary["medium_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{SUCCESS};text-transform:uppercase;">Low AP</div>
            <div style="font-size:22px;font-weight:700;color:{SUCCESS};margin-top:4px;">{summary["low_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Max RPN</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["max_rpn"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{VIOLET};text-transform:uppercase;">AI Candidates</div>
            <div style="font-size:22px;font-weight:700;color:{VIOLET};margin-top:4px;">{summary["ai_candidate_count"]}</div>
        </div>
    </div>

    <!-- Table -->
    <div style="overflow-x:auto;border:1px solid {c_border};border-radius:8px;background-color:{c_bg_card};">
        <table style="width:100%;border-collapse:collapse;font-size:12px;text-align:left;">
            <thead>
                <tr style="background-color:{c_bg_table_header};border-bottom:2px solid {c_border};color:{c_text_muted};font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">
                    <th style="padding:10px 12px;">ID</th>
                    <th style="padding:10px 12px;">Process Step</th>
                    <th style="padding:10px 12px;">Component</th>
                    <th style="padding:10px 12px;">Function</th>
                    <th style="padding:10px 12px;">Failure Mode</th>
                    <th style="padding:10px 12px;">Effect</th>
                    <th style="padding:10px 12px;text-align:center;">S</th>
                    <th style="padding:10px 12px;">Cause</th>
                    <th style="padding:10px 12px;text-align:center;">O</th>
                    <th style="padding:10px 12px;">Current Control</th>
                    <th style="padding:10px 12px;text-align:center;">D</th>
                    <th style="padding:10px 12px;text-align:center;">RPN</th>
                    <th style="padding:10px 12px;text-align:center;">AP</th>
                    <th style="padding:10px 12px;text-align:center;">Status</th>
                </tr>
            </thead>
            <tbody>
                {rows_joined}
            </tbody>
        </table>
    </div>

    <!-- Footer Note -->
    <div style="margin-top:14px;display:flex;justify-content:space-between;align-items:center;font-size:11px;color:{c_text_muted};">
        <span>AIAG &amp; VDA FMEA Handbook (1st Ed, 2019) Section 3.5.9 Action Priority Matrix</span>
        <span>Deterministic calculation via quality_core.scoring</span>
    </div>
</div>
        """.strip()

        if not standalone:
            return body_content

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
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
        * {{
            box-sizing: border-box;
        }}
        tr:hover {{
            background-color: {c_row_hover} !important;
        }}
    </style>
</head>
<body>
{body_content}
</body>
</html>"""


def load_sample_canvas(
    title: str = "AIAG & VDA 2019 Process FMEA Canvas",
    description: str = "Reference Automotive Process FMEA Canvas with Deterministic Action Priority Scoring",
) -> FMEACanvas:
    """Convenience function to load an FMEACanvas instance with reference sample rows."""
    return FMEACanvas.load_sample(title=title, description=description)

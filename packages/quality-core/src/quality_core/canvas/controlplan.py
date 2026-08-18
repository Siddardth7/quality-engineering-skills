"""
controlplan.py
Single-writer visual Control Plan matrix canvas reference implementation for Quality Platform.

Provides `ControlPlanCanvasRow` and `ControlPlanCanvas` controller for managing an in-memory
AIAG APQP Control Plan matrix grid with deterministic tolerance checks, PFMEA linkage verification
via `quality_core.controlplan`, sample dataset loading, row editing, and theme-aligned HTML canvas rendering.
"""

from __future__ import annotations

import html
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from quality_core.controlplan.connector import validate_pfmea_linkage
from quality_core.controlplan.schema import ControlPlanDataset, ControlPlanRow
from quality_core.schema import FMEADataset, FMEARow, RelationalFMEA, flat_to_relational
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

SUPPORTED_CHARTS: tuple[str, ...] = ("I-MR", "Xbar-R", "Xbar-S", "p", "c", "u")


@dataclass
class ControlPlanCanvasRow:
    """Individual characteristic item within the Control Plan matrix canvas.

    Represents an AIAG APQP Control Plan row with specification tolerances,
    sampling frequency, measurement method, control method (SPC chart), reaction plan,
    PFMEA linkage join key (source_cause_id), and row-level validation findings.
    """

    id: int
    characteristic: str
    measurement_method: str
    sample_size: int
    frequency: str
    reaction_plan: str
    lsl: float | None = None
    usl: float | None = None
    target: float | None = None
    recommended_chart: str | None = None
    source_cause_id: str | None = None
    sample_plan_is_placeholder: bool = False
    validation_status: str = "valid"  # "valid" | "warning" | "orphan" | "placeholder" | "error"
    findings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int):
            raise TypeError(f"id must be an integer, got {self.id!r}")
        if self.id <= 0:
            raise ValueError(f"id must be a positive integer, got {self.id!r}")

        for str_field in (
            "characteristic",
            "measurement_method",
            "frequency",
            "reaction_plan",
        ):
            val = getattr(self, str_field)
            if not isinstance(val, str):
                raise TypeError(f"{str_field} must be a string, got {val!r}")
            if not val.strip():
                raise ValueError(f"{str_field} must be a non-empty string, got {val!r}")
            setattr(self, str_field, val.strip())

        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int):
            raise TypeError(f"sample_size must be an integer, got {self.sample_size!r}")
        if self.sample_size < 1:
            raise ValueError(f"sample_size must be >= 1, got {self.sample_size!r}")

        if not isinstance(self.sample_plan_is_placeholder, bool):
            raise TypeError(
                f"sample_plan_is_placeholder must be a boolean, got {type(self.sample_plan_is_placeholder).__name__}: {self.sample_plan_is_placeholder!r}"
            )

        if self.source_cause_id is not None:
            if not isinstance(self.source_cause_id, str):
                raise TypeError(f"source_cause_id must be a string or None, got {self.source_cause_id!r}")
            self.source_cause_id = self.source_cause_id.strip() or None

        for num_field in ("lsl", "usl", "target"):
            val = getattr(self, num_field)
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    raise TypeError(f"{num_field} must be a float or None, got {val!r}")
                val_float = float(val)
                if math.isnan(val_float) or math.isinf(val_float):
                    raise ValueError(f"{num_field} cannot be NaN or Inf, got {val!r}")
                setattr(self, num_field, val_float)

        if self.usl is not None and self.lsl is not None and self.usl <= self.lsl:
            raise ValueError(f"usl must be greater than lsl, got usl={self.usl} and lsl={self.lsl}")

        if self.target is not None and self.lsl is not None and self.target < self.lsl:
            raise ValueError(f"target cannot be less than lsl, got target={self.target} and lsl={self.lsl}")

        if self.target is not None and self.usl is not None and self.target > self.usl:
            raise ValueError(f"target cannot be greater than usl, got target={self.target} and usl={self.usl}")

        if self.recommended_chart is not None:
            if not isinstance(self.recommended_chart, str):
                raise TypeError(f"recommended_chart must be a string or None, got {self.recommended_chart!r}")
            chart_val = self.recommended_chart.strip()
            if chart_val not in SUPPORTED_CHARTS:
                raise ValueError(
                    f"Invalid recommended_chart '{self.recommended_chart}'. Supported: {SUPPORTED_CHARTS} or None"
                )
            self.recommended_chart = chart_val

        if not isinstance(self.findings, list):
            raise TypeError(f"findings must be a list, got {type(self.findings).__name__}: {self.findings!r}")
        if not isinstance(self.validation_status, str):
            raise TypeError(
                f"validation_status must be a string, got {type(self.validation_status).__name__}: {self.validation_status!r}"
            )

        self.findings = list(self.findings)
        if self.sample_plan_is_placeholder:
            if "Sample plan contains placeholder values." not in self.findings:
                self.findings.append("Sample plan contains placeholder values.")
            if self.validation_status == "valid":
                self.validation_status = "placeholder"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the canvas row."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlPlanCanvasRow:
        """Construct a ControlPlanCanvasRow from a dictionary supporting snake_case or PascalCase keys."""
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
        characteristic = get_field("characteristic", "Characteristic")
        measurement_method = get_field("measurement_method", "Measurement_Method")
        sample_size = get_field("sample_size", "Sample_Size")
        frequency = get_field("frequency", "Frequency")
        reaction_plan = get_field("reaction_plan", "Reaction_Plan")
        lsl = get_field("lsl", "LSL", default=None)
        usl = get_field("usl", "USL", default=None)
        target = get_field("target", "Target", default=None)
        recommended_chart = get_field("recommended_chart", "Recommended_Chart", default=None)
        if hasattr(recommended_chart, "value"):
            recommended_chart = recommended_chart.value
        source_cause_id = get_field("source_cause_id", "Source_Cause_ID", default=None)
        sample_plan_is_placeholder = get_field(
            "sample_plan_is_placeholder", "Sample_Plan_Is_Placeholder", default=False
        )
        validation_status = get_field("validation_status", "Validation_Status", default="valid")
        findings = get_field("findings", "Findings", default=None)

        return cls(
            id=row_id,
            characteristic=characteristic,
            measurement_method=measurement_method,
            sample_size=sample_size,
            frequency=frequency,
            reaction_plan=reaction_plan,
            lsl=lsl,
            usl=usl,
            target=target,
            recommended_chart=recommended_chart,
            source_cause_id=source_cause_id,
            sample_plan_is_placeholder=sample_plan_is_placeholder,
            validation_status=validation_status,
            findings=findings if findings is not None else [],
        )


# ---------------------------------------------------------------------------
# Reference Benchmark Dataset (Automotive Powertrain & Battery Control Plan)
# ---------------------------------------------------------------------------

SAMPLE_CONTROL_PLAN_ROWS: list[dict[str, Any]] = [
    {
        "id": 1,
        "characteristic": "Gate driver desaturation during high-torque acceleration",
        "measurement_method": "Automated optical inspection & functional test",
        "sample_size": 5,
        "frequency": "hourly",
        "reaction_plan": "Contain and investigate; failure effect: Inverter shutdown, loss of vehicle propulsion.",
        "lsl": None,
        "usl": None,
        "target": None,
        "recommended_chart": "Xbar-R",
        "source_cause_id": "1::1::1-C1",
        "sample_plan_is_placeholder": False,
    },
    {
        "id": 2,
        "characteristic": "Brake-by-wire pressure transducer calibration drift",
        "measurement_method": "100% End-of-line calibrated pressure sweep",
        "sample_size": 1,
        "frequency": "100% in-line",
        "reaction_plan": "Contain and investigate; failure effect: Degraded pedal feel, warning indicator displayed.",
        "lsl": 0.0,
        "usl": 100.0,
        "target": 50.0,
        "recommended_chart": "I-MR",
        "source_cause_id": "2::1::2-C1",
        "sample_plan_is_placeholder": False,
    },
    {
        "id": 3,
        "characteristic": "Li-ion pouch cell separator puncture from foreign particulate",
        "measurement_method": "Periodic visual inspection & particle counter",
        "sample_size": 10,
        "frequency": "per shift",
        "reaction_plan": "Contain and investigate; failure effect: Internal cell short circuit, thermal runaway risk.",
        "lsl": None,
        "usl": None,
        "target": None,
        "recommended_chart": "p",
        "source_cause_id": "3::1::3-C1",
        "sample_plan_is_placeholder": False,
    },
    {
        "id": 4,
        "characteristic": "Steering angle sensor CAN bus frame drop",
        "measurement_method": "Dual-redundant CAN bus CRC check",
        "sample_size": 5,
        "frequency": "per shift",
        "reaction_plan": "Contain and investigate; failure effect: Transient loss of lane centering assist.",
        "lsl": None,
        "usl": None,
        "target": None,
        "recommended_chart": "c",
        "source_cause_id": "4::1::4-C1",
        "sample_plan_is_placeholder": False,
    },
    {
        "id": 5,
        "characteristic": "Stator insulation dielectric breakdown",
        "measurement_method": "100% In-line high-potential dielectric test",
        "sample_size": 1,
        "frequency": "per batch",
        "reaction_plan": "Contain and investigate; failure effect: Motor ground fault, reduced torque output.",
        "lsl": 1500.0,
        "usl": 2500.0,
        "target": 2000.0,
        "recommended_chart": "I-MR",
        "source_cause_id": "5::1::5-C1",
        "sample_plan_is_placeholder": True,
    },
    {
        "id": 6,
        "characteristic": "Output shaft rotary oil seal extrusion",
        "measurement_method": "Press-force depth monitoring",
        "sample_size": 1,
        "frequency": "per shift",
        "reaction_plan": "Contain and investigate; failure effect: Oil seepage onto underbody, non-safety effect.",
        "lsl": None,
        "usl": None,
        "target": None,
        "recommended_chart": None,
        "source_cause_id": None,
        "sample_plan_is_placeholder": True,
    },
]


class ControlPlanCanvas:
    """Controller for the in-memory single-writer Control Plan visual matrix canvas.

    Provides single-writer CRUD operations, PFMEA bidirectional linkage validation,
    state summarization, and styled HTML matrix generation adhering to the Quality Platform theme.
    """

    def __init__(
        self,
        rows: list[ControlPlanCanvasRow | dict[str, Any]] | None = None,
        fmea: RelationalFMEA | list[dict[str, Any]] | None = None,
        title: str = "AIAG APQP Control Plan Matrix Canvas",
        description: str = "Interactive single-writer visual Control Plan canvas with validation findings.",
    ) -> None:
        if isinstance(title, bool) or not isinstance(title, str) or not title.strip():
            raise ValueError(f"title must be a non-empty string, got {title!r}")
        if isinstance(description, bool) or not isinstance(description, str) or not description.strip():
            raise ValueError(f"description must be a non-empty string, got {description!r}")

        self.title: str = title.strip()
        self.description: str = description.strip()
        self._rows: dict[int, ControlPlanCanvasRow] = {}
        self._uncovered_failure_modes: list[str] = []
        self._linkage_checked: bool = False

        if rows is not None:
            if not isinstance(rows, list):
                raise TypeError(f"rows must be a list, got {type(rows).__name__}: {rows!r}")
            for item in rows:
                self.add_row(item)

        if fmea is not None:
            self.validate_linkage(fmea)

    @property
    def rows(self) -> list[ControlPlanCanvasRow]:
        """Return the list of canvas rows in insertion order."""
        return list(self._rows.values())

    @classmethod
    def load_sample(
        cls,
        title: str = "AIAG APQP Control Plan Matrix Canvas",
        description: str = "Interactive single-writer visual Control Plan canvas with validation findings.",
    ) -> ControlPlanCanvas:
        """Create and return a ControlPlanCanvas populated with the reference benchmark dataset."""
        canvas = cls(title=title, description=description)
        for row_dict in SAMPLE_CONTROL_PLAN_ROWS:
            canvas.add_row(row_dict)
        return canvas

    def get_row(self, row_id: int) -> ControlPlanCanvasRow | None:
        """Retrieve a canvas row by its ID, or return None if not found."""
        if isinstance(row_id, bool) or not isinstance(row_id, int):
            raise TypeError(f"row_id must be an integer, got {type(row_id).__name__}: {row_id!r}")
        return self._rows.get(row_id)

    def add_row(self, row: ControlPlanCanvasRow | dict[str, Any]) -> ControlPlanCanvasRow:
        """Add a new row to the canvas. Raises ValueError on duplicate ID."""
        if isinstance(row, dict):
            canvas_row = ControlPlanCanvasRow.from_dict(row)
        elif isinstance(row, ControlPlanCanvasRow):
            canvas_row = row
        else:
            raise TypeError(f"row must be a ControlPlanCanvasRow or dict, got {type(row).__name__}: {row!r}")

        if canvas_row.id in self._rows:
            raise ValueError(f"Row with ID {canvas_row.id} already exists in canvas.")

        if canvas_row.source_cause_id is None:
            orphan_msg = f"Orphan characteristic '{canvas_row.characteristic}': missing source_cause_id."
            if orphan_msg not in canvas_row.findings:
                canvas_row.findings.insert(0, orphan_msg)
            if canvas_row.validation_status in ("valid", "placeholder", "warning"):
                canvas_row.validation_status = "orphan"

        self._rows[canvas_row.id] = canvas_row
        return canvas_row

    def edit_row(self, row_id: int, **updates: Any) -> ControlPlanCanvasRow:
        """Update fields of an existing row and re-validate."""
        if isinstance(row_id, bool) or not isinstance(row_id, int):
            raise TypeError(f"row_id must be an integer, got {type(row_id).__name__}: {row_id!r}")

        if row_id not in self._rows:
            raise KeyError(f"Row with ID {row_id} not found in canvas.")

        existing = self._rows[row_id]
        data = existing.to_dict()

        field_mapping: dict[str, str] = {
            "id": "id",
            "ID": "id",
            "characteristic": "characteristic",
            "Characteristic": "characteristic",
            "measurement_method": "measurement_method",
            "Measurement_Method": "measurement_method",
            "sample_size": "sample_size",
            "Sample_Size": "sample_size",
            "frequency": "frequency",
            "Frequency": "frequency",
            "reaction_plan": "reaction_plan",
            "Reaction_Plan": "reaction_plan",
            "lsl": "lsl",
            "LSL": "lsl",
            "usl": "usl",
            "USL": "usl",
            "target": "target",
            "Target": "target",
            "recommended_chart": "recommended_chart",
            "Recommended_Chart": "recommended_chart",
            "source_cause_id": "source_cause_id",
            "Source_Cause_ID": "source_cause_id",
            "sample_plan_is_placeholder": "sample_plan_is_placeholder",
            "Sample_Plan_Is_Placeholder": "sample_plan_is_placeholder",
            "validation_status": "validation_status",
            "Validation_Status": "validation_status",
            "findings": "findings",
            "Findings": "findings",
        }

        for k, v in updates.items():
            if k in field_mapping:
                data[field_mapping[k]] = v
            else:
                raise ValueError(f"Unknown field '{k}' in row update")

        new_id = data["id"]
        if new_id != row_id and new_id in self._rows:
            raise ValueError(f"Cannot change row ID to {new_id}: ID already exists in canvas.")

        updated_row = ControlPlanCanvasRow.from_dict(data)

        if updated_row.source_cause_id is None:
            orphan_msg = f"Orphan characteristic '{updated_row.characteristic}': missing source_cause_id."
            if orphan_msg not in updated_row.findings:
                updated_row.findings.insert(0, orphan_msg)
            if updated_row.validation_status in ("valid", "placeholder", "warning"):
                updated_row.validation_status = "orphan"

        if new_id != row_id:
            del self._rows[row_id]
        self._rows[new_id] = updated_row
        return updated_row

    def delete_row(self, row_id: int) -> ControlPlanCanvasRow:
        """Remove a row by its ID and return the deleted row."""
        if isinstance(row_id, bool) or not isinstance(row_id, int):
            raise TypeError(f"row_id must be an integer, got {type(row_id).__name__}: {row_id!r}")

        if row_id not in self._rows:
            raise KeyError(f"Row with ID {row_id} not found in canvas.")

        return self._rows.pop(row_id)

    def validate_linkage(
        self, fmea: RelationalFMEA | list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Validate bidirectional PFMEA linkage against an FMEA model or record list.

        Updates row-level validation findings, marks orphan characteristics, and
        records uncovered FMEA failure modes on the canvas controller.
        """
        if fmea is None:
            self._linkage_checked = False
            self._uncovered_failure_modes = []
            orphan_characteristics: list[str] = []
            for row in self._rows.values():
                new_findings: list[str] = []
                if row.sample_plan_is_placeholder:
                    new_findings.append("Sample plan contains placeholder values.")
                if row.source_cause_id is None:
                    orphan_msg = f"Orphan characteristic '{row.characteristic}': missing source_cause_id."
                    new_findings.insert(0, orphan_msg)
                    row.validation_status = "orphan"
                    orphan_characteristics.append(row.characteristic)
                elif row.sample_plan_is_placeholder:
                    row.validation_status = "placeholder"
                else:
                    row.validation_status = "valid"
                row.findings = new_findings

            total = len(self._rows)
            linked = total - len(orphan_characteristics)
            return {
                "valid": len(orphan_characteristics) == 0,
                "total_rows": total,
                "linked_rows": linked,
                "orphan_characteristics": orphan_characteristics,
                "uncovered_failure_modes": [],
                "findings": [f for r in self._rows.values() for f in r.findings if f.startswith("Orphan")],
            }

        self._linkage_checked = True

        if isinstance(fmea, list):
            fmea_rows = [FMEARow(**r) for r in fmea]
            fmea_dataset = FMEADataset(rows=fmea_rows)
            relational_fmea = flat_to_relational(fmea_dataset)
        elif isinstance(fmea, RelationalFMEA):
            relational_fmea = fmea
        else:
            raise TypeError(
                f"fmea must be a RelationalFMEA, list of dicts, or None, got {type(fmea).__name__}: {fmea!r}"
            )

        # Build ControlPlanDataset from current canvas rows
        cp_rows: list[ControlPlanRow] = []
        for r in self._rows.values():
            cp_rows.append(
                ControlPlanRow(
                    characteristic=r.characteristic,
                    lsl=r.lsl,
                    usl=r.usl,
                    target=r.target,
                    measurement_method=r.measurement_method,
                    sample_size=r.sample_size,
                    frequency=r.frequency,
                    recommended_chart=r.recommended_chart,  # type: ignore[arg-type]
                    reaction_plan=r.reaction_plan,
                    source_cause_id=r.source_cause_id,
                    sample_plan_is_placeholder=r.sample_plan_is_placeholder,
                )
            )

        control_plan_dataset = ControlPlanDataset(rows=cp_rows)
        linkage_res = validate_pfmea_linkage(control_plan_dataset, relational_fmea)

        orphan_set = set(linkage_res["orphan_characteristics"])
        self._uncovered_failure_modes = list(linkage_res["uncovered_failure_modes"])

        for row in self._rows.values():
            new_findings = []
            if row.sample_plan_is_placeholder:
                new_findings.append("Sample plan contains placeholder values.")

            if row.characteristic in orphan_set:
                if row.source_cause_id is None:
                    new_findings.insert(
                        0, f"Orphan characteristic '{row.characteristic}': missing source_cause_id."
                    )
                else:
                    new_findings.insert(
                        0,
                        f"Orphan characteristic '{row.characteristic}': source_cause_id "
                        f"'{row.source_cause_id}' not found in FMEA.",
                    )
                row.validation_status = "orphan"
            elif row.sample_plan_is_placeholder:
                row.validation_status = "placeholder"
            else:
                row.validation_status = "valid"

            row.findings = new_findings

        return linkage_res

    def get_summary(self) -> dict[str, Any]:
        """Compute summary validation and linkage metrics across all canvas rows."""
        total = len(self._rows)
        valid = sum(1 for r in self._rows.values() if r.validation_status == "valid")
        orphan = sum(1 for r in self._rows.values() if r.validation_status == "orphan")
        placeholder = sum(1 for r in self._rows.values() if r.validation_status == "placeholder")
        warning = sum(1 for r in self._rows.values() if r.validation_status in ("warning", "error"))
        uncovered_count = len(self._uncovered_failure_modes)
        uncovered_modes = list(self._uncovered_failure_modes)

        row_findings = [f for r in self._rows.values() for f in r.findings]
        uncovered_findings = [
            f"Uncovered FMEA failure mode '{u_fm}': no linked Control Plan row."
            for u_fm in self._uncovered_failure_modes
        ]
        all_findings = row_findings + uncovered_findings

        return {
            "total_rows": total,
            "valid_count": valid,
            "orphan_count": orphan,
            "placeholder_count": placeholder,
            "warning_count": warning,
            "uncovered_fms_count": uncovered_count,
            "uncovered_failure_modes": uncovered_modes,
            "all_findings": all_findings,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return full structured state dictionary of the canvas."""
        return {
            "title": self.title,
            "description": self.description,
            "rows": [r.to_dict() for r in self.rows],
            "summary": self.get_summary(),
            "linkage_checked": self._linkage_checked,
        }

    def to_html(self, standalone: bool = True, theme: str = "dark") -> str:
        """Render the Control Plan canvas as a styled HTML matrix view.

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

        table_rows_html: list[str] = []
        for r in self.rows:
            # Specification / Tolerance string
            if r.lsl is not None or r.usl is not None or r.target is not None:
                lsl_str = f"{r.lsl:.1f}" if r.lsl is not None else "—"
                tgt_str = f"{r.target:.1f}" if r.target is not None else "—"
                usl_str = f"{r.usl:.1f}" if r.usl is not None else "—"
                spec_display = f"[{lsl_str}, {tgt_str}, {usl_str}]"
            else:
                spec_display = "—"

            # Sample Plan string
            sample_plan_str = f"n={r.sample_size}, {html.escape(r.frequency)}"

            # Recommended Chart badge
            if r.recommended_chart:
                chart_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(56,189,248,0.15);'
                    f'color:#38bdf8;border:1px solid #38bdf8;">{html.escape(r.recommended_chart)}</span>'
                )
            else:
                chart_badge = f'<span style="color:{c_text_muted};">—</span>'

            # Source Cause Link
            if r.source_cause_id:
                cause_link_str = f'<code style="color:{c_text_muted};font-size:11px;">{html.escape(r.source_cause_id)}</code>'
            else:
                cause_link_str = f'<span style="color:{c_text_muted};">—</span>'

            # Validation Status badge
            if r.validation_status == "valid":
                status_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:500;background-color:rgba(16, 185, 129, 0.15);'
                    f'color:{SUCCESS};border:1px solid {SUCCESS};">Verified</span>'
                )
            elif r.validation_status == "orphan":
                status_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(239, 68, 68, 0.15);'
                    f'color:{DANGER};border:1px solid {DANGER};">Orphan Linkage</span>'
                )
            elif r.validation_status == "placeholder":
                status_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(245, 158, 11, 0.15);'
                    f'color:{AMBER};border:1px solid {AMBER};">Placeholder Plan</span>'
                )
            elif r.validation_status == "error":
                status_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(239, 68, 68, 0.15);'
                    f'color:{DANGER};border:1px solid {DANGER};">Tolerance Error</span>'
                )
            else:
                status_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(245, 158, 11, 0.15);'
                    f'color:{AMBER};border:1px solid {AMBER};">{html.escape(r.validation_status.title())}</span>'
                )

            row_html = f"""
            <tr style="border-bottom:1px solid {c_border};transition:background-color 0.15s ease;">
                <td style="padding:10px 12px;font-family:monospace;font-weight:600;color:{AMBER};">{r.id}</td>
                <td style="padding:10px 12px;font-weight:500;">{html.escape(r.characteristic)}</td>
                <td style="padding:10px 12px;font-family:monospace;color:{c_text_muted};">{spec_display}</td>
                <td style="padding:10px 12px;color:{c_text_muted};">{html.escape(r.measurement_method)}</td>
                <td style="padding:10px 12px;">{sample_plan_str}</td>
                <td style="padding:10px 12px;text-align:center;">{chart_badge}</td>
                <td style="padding:10px 12px;color:{c_text_muted};">{html.escape(r.reaction_plan)}</td>
                <td style="padding:10px 12px;text-align:center;">{cause_link_str}</td>
                <td style="padding:10px 12px;text-align:center;">{status_badge}</td>
            </tr>
            """
            table_rows_html.append(row_html)

        if not table_rows_html:
            empty_state = f"""
            <tr>
                <td colspan="9" style="padding:32px 16px;text-align:center;color:{c_text_muted};font-style:italic;">
                    No Control Plan items recorded in canvas.
                </td>
            </tr>
            """
            table_rows_html.append(empty_state)

        rows_joined = "".join(table_rows_html)

        # Uncovered failure modes alert
        if summary["uncovered_fms_count"] > 0:
            uncovered_list_items = "".join(
                f"<li><code>{html.escape(fm)}</code></li>" for fm in summary["uncovered_failure_modes"]
            )
            uncovered_alert_html = f"""
    <div style="background-color:rgba(139,92,246,0.1);border:1px solid {VIOLET};border-radius:8px;padding:12px 16px;margin-bottom:20px;color:{c_text_main};">
        <div style="font-weight:600;color:{VIOLET};margin-bottom:6px;font-size:13px;">Uncovered PFMEA Failure Modes ({summary["uncovered_fms_count"]} Modes Without Control Plan Monitoring):</div>
        <ul style="margin:0;padding-left:20px;font-size:12px;color:{c_text_muted};">
            {uncovered_list_items}
        </ul>
    </div>
            """
        else:
            uncovered_alert_html = ""

        body_content = f"""
<div class="qes-controlplan-canvas" style="font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background-color:{c_bg_page};color:{c_text_main};padding:24px;border-radius:12px;box-sizing:border-box;border:1px solid {c_border};">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid {c_border};">
        <div>
            <div style="display:flex;align-items:center;gap:10px;">
                <h2 style="margin:0;font-size:20px;font-weight:700;color:{c_text_main};">{escaped_title}</h2>
                <span style="background-color:rgba(245,158,11,0.15);color:{AMBER};border:1px solid {AMBER};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase;">AIAG APQP &amp; Control Plan</span>
            </div>
            <p style="margin:6px 0 0 0;font-size:13px;color:{c_text_muted};">{escaped_desc}</p>
        </div>
        <div style="font-size:12px;color:{c_text_muted};text-align:right;">
            <span>Single-Writer Reference Canvas</span>
        </div>
    </div>

    <!-- Summary KPI Cards -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:12px;margin-bottom:24px;">
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;">Total Characteristics</div>
            <div style="font-size:22px;font-weight:700;color:{c_text_main};margin-top:4px;">{summary["total_rows"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{SUCCESS};text-transform:uppercase;">Fully Verified</div>
            <div style="font-size:22px;font-weight:700;color:{SUCCESS};margin-top:4px;">{summary["valid_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{DANGER};text-transform:uppercase;">Orphan Characteristics</div>
            <div style="font-size:22px;font-weight:700;color:{DANGER};margin-top:4px;">{summary["orphan_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{AMBER};text-transform:uppercase;">Placeholder Plans</div>
            <div style="font-size:22px;font-weight:700;color:{AMBER};margin-top:4px;">{summary["placeholder_count"]}</div>
        </div>
        <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;font-weight:600;color:{VIOLET};text-transform:uppercase;">Uncovered FMEA Modes</div>
            <div style="font-size:22px;font-weight:700;color:{VIOLET};margin-top:4px;">{summary["uncovered_fms_count"]}</div>
        </div>
    </div>

    {uncovered_alert_html}

    <!-- Table -->
    <div style="overflow-x:auto;border:1px solid {c_border};border-radius:8px;background-color:{c_bg_card};">
        <table style="width:100%;border-collapse:collapse;font-size:12px;text-align:left;">
            <thead>
                <tr style="background-color:{c_bg_table_header};border-bottom:2px solid {c_border};color:{c_text_muted};font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">
                    <th style="padding:10px 12px;">ID</th>
                    <th style="padding:10px 12px;">Characteristic</th>
                    <th style="padding:10px 12px;">Specification / Tolerance</th>
                    <th style="padding:10px 12px;">Measurement Method</th>
                    <th style="padding:10px 12px;">Sample Plan</th>
                    <th style="padding:10px 12px;text-align:center;">Control Method</th>
                    <th style="padding:10px 12px;">Reaction Plan</th>
                    <th style="padding:10px 12px;text-align:center;">Source Cause Link</th>
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
        <span>AIAG APQP and Control Plan Reference Manual (2nd Ed) Section 6</span>
        <span>Deterministic computation via quality_core.controlplan</span>
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


def load_sample_controlplan_canvas(
    title: str = "AIAG APQP Control Plan Matrix Canvas",
    description: str = "Interactive single-writer visual Control Plan canvas with validation findings.",
) -> ControlPlanCanvas:
    """Convenience helper to construct and return a ControlPlanCanvas loaded with benchmark sample data."""
    return ControlPlanCanvas.load_sample(title=title, description=description)

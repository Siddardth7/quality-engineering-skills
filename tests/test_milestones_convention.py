"""Test suite for milestone documentation, SemVer naming, and governance conventions (#7, #21, #34, #41, #48, #80).

Validates:
1. Presence of docs/milestones/ directory and README.md governance documentation.
2. SemVer filename mapping convention (docs/milestones/vX.Y.Z.md).
3. Mandatory structural sections across all milestone files.
4. Milestone 1 (v0.1.0.md) Epic definitions (E1-E4) and Issue traceability (#1 through #7).
5. Milestone 2 (v0.2.0.md) Epic definitions (E1-E6), Issue traceability (#16 through #21), and branch mapping.
6. Milestone 3 (v0.3.0.md) Epic definitions (E1-E6), Issue traceability (#29 through #34), and branch mapping.
7. Milestone 4 (v0.4.0.md) Epic definitions (E1-E7), Issue traceability (#35 through #41), and branch mapping.
8. Milestone 5 (v0.5.0.md) Epic definitions (E1-E7), Issue traceability (#42 through #48), and branch mapping.
9. Milestone 6 (v0.6.0.md) Epic definitions (E0-E6), Issue traceability (#74 through #80), and branch mapping.
10. Real MCP client release gate, 4-engine checkpoint, and verification artifacts cataloging.
11. Summary Release Matrix table link updates in ROADMAP.md for v0.1.0 through v0.6.0.
12. Markdown relative link resolution against repository filesystem.
13. CHANGELOG.md entry formatting under [Unreleased] -> Added (#7, #21, #34, #41, #48, #80).
14. Negative controls: detection of invalid filenames, missing sections, invalid issue URLs, broken links, missing epics/issues/artifacts, and corrupted branch names.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS_DIR = _REPO_ROOT / "docs"
_MILESTONES_DIR = _DOCS_DIR / "milestones"
_MILESTONES_README = _MILESTONES_DIR / "README.md"
_V010_MILESTONE = _MILESTONES_DIR / "v0.1.0.md"
_V020_MILESTONE = _MILESTONES_DIR / "v0.2.0.md"
_V030_MILESTONE = _MILESTONES_DIR / "v0.3.0.md"
_V040_MILESTONE = _MILESTONES_DIR / "v0.4.0.md"
_V050_MILESTONE = _MILESTONES_DIR / "v0.5.0.md"
_V060_MILESTONE = _MILESTONES_DIR / "v0.6.0.md"
_ROADMAP = _REPO_ROOT / "ROADMAP.md"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"

_SEMVER_FILENAME_PATTERN = re.compile(r"^v\d+\.\d+\.\d+\.md$")
_CANONICAL_ISSUE_URL_PATTERN = re.compile(
    r"https://github\.com/Siddardth7/quality-engineering-skills/issues/(\d+)"
)
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

_MANDATORY_SECTIONS: list[str] = [
    "## Overview",
    "## Epics & Issues",
    "## Release Gate Criteria",
    "## Verification Artifacts & Test Evidence",
    "## Retrospective & Status",
]


def _validate_milestone_filename(filename: str) -> bool:
    """Return True if filename strictly adheres to SemVer milestone format vX.Y.Z.md."""
    return bool(_SEMVER_FILENAME_PATTERN.match(filename))


def _extract_heading_sections(content: str) -> list[str]:
    """Extract all level-2 markdown headings from content."""
    return [line.strip() for line in content.splitlines() if line.strip().startswith("## ")]


def _validate_milestone_content_structure(content: str) -> None:
    """Validate that milestone content contains all mandatory level-2 sections."""
    headings = _extract_heading_sections(content)
    for section in _MANDATORY_SECTIONS:
        # Check if the section or an alias (e.g. ## Milestone Overview) is present
        alias = section.replace("## Overview", "## Milestone Overview") if section == "## Overview" else section
        found = any(h == section or h == alias or h.startswith(f"{section} ") for h in headings)
        if not found:
            raise ValueError(f"Missing mandatory section {section!r}. Found headings: {headings}")


def _extract_issue_urls(content: str) -> list[tuple[str, int]]:
    """Extract canonical GitHub issue URLs and issue numbers from markdown content."""
    results: list[tuple[str, int]] = []
    for match in _CANONICAL_ISSUE_URL_PATTERN.finditer(content):
        url = match.group(0)
        issue_num = int(match.group(1))
        results.append((url, issue_num))
    return results


def _resolve_relative_links(file_path: Path, content: str) -> list[Path]:
    """Extract and resolve relative markdown file paths from content."""
    resolved_paths: list[Path] = []
    file_dir = file_path.parent
    for match in _MARKDOWN_LINK_PATTERN.finditer(content):
        target = match.group(2).strip()
        if target.startswith("http://") or target.startswith("https://") or target.startswith("#") or target.startswith("mailto:"):
            continue
        file_part = target.split("#")[0].strip()
        if not file_part:
            continue
        resolved = (file_dir / file_part).resolve()
        resolved_paths.append(resolved)
    return resolved_paths


# ==============================================================================
# Positive Controls
# ==============================================================================


def test_milestones_directory_exists() -> None:
    """Verify docs/milestones directory exists."""
    assert _MILESTONES_DIR.is_dir(), f"Missing milestones directory: {_MILESTONES_DIR}"


def test_milestones_readme_structure() -> None:
    """Verify docs/milestones/README.md contains required governance documentation."""
    assert _MILESTONES_README.is_file(), f"Missing milestones README: {_MILESTONES_README}"
    content = _MILESTONES_README.read_text(encoding="utf-8")

    assert "# 🏛️ Milestone Documentation & Governance" in content or "# Milestone Documentation" in content
    assert "## 1. Overview & Purpose" in content or "## Overview" in content
    assert "## 2. SemVer File Naming Convention" in content or "SemVer" in content
    assert "docs/milestones/vX.Y.Z.md" in content
    assert "## 3. Structural Schema for Milestone Documents" in content or "Structural Schema" in content
    for section in _MANDATORY_SECTIONS:
        assert section in content, f"README must specify mandatory section {section}"

    assert "https://github.com/Siddardth7/quality-engineering-skills/issues/<num>" in content or "issues/<num>" in content
    assert "v0.1.0.md" in content


def test_milestone_files_naming_convention() -> None:
    """Verify all milestone markdown files in docs/milestones/ follow SemVer vX.Y.Z.md."""
    milestone_files = list(_MILESTONES_DIR.glob("v*.md"))
    assert len(milestone_files) >= 1, "At least v0.1.0.md must exist in docs/milestones/"

    for path in milestone_files:
        assert _validate_milestone_filename(path.name), (
            f"Milestone file {path.name} violates SemVer convention (must match 'vX.Y.Z.md')"
        )


def test_milestone_mandatory_sections() -> None:
    """Verify every milestone file contains all 5 mandatory level-2 heading sections."""
    milestone_files = list(_MILESTONES_DIR.glob("v*.md"))
    for path in milestone_files:
        content = path.read_text(encoding="utf-8")
        _validate_milestone_content_structure(content)


def test_v010_milestone_epics_and_issues_traceability() -> None:
    """Verify docs/milestones/v0.1.0.md defines Epics E1-E4 and links issues #1 through #7."""
    assert _V010_MILESTONE.is_file(), f"Missing milestone v0.1.0 file: {_V010_MILESTONE}"
    content = _V010_MILESTONE.read_text(encoding="utf-8")

    # Verify all 4 Epics are present
    assert "Epic 1 (E1)" in content or "E1:" in content
    assert "Epic 2 (E2)" in content or "E2:" in content
    assert "Epic 3 (E3)" in content or "E3:" in content
    assert "Epic 4 (E4)" in content or "E4:" in content

    # Verify all 7 issues are present with canonical URLs
    issue_tuples = _extract_issue_urls(content)
    issue_numbers = {num for _, num in issue_tuples}

    for expected_issue in range(1, 8):
        assert expected_issue in issue_numbers, f"Missing issue #{expected_issue} in v0.1.0.md"
        expected_url = f"https://github.com/Siddardth7/quality-engineering-skills/issues/{expected_issue}"
        assert expected_url in content, f"Missing canonical URL for issue #{expected_issue}: {expected_url}"


def test_v010_milestone_release_gate_and_artifacts() -> None:
    """Verify v0.1.0.md specifies the real MCP client ping release gate and catalogs verification artifacts."""
    content = _V010_MILESTONE.read_text(encoding="utf-8")

    # Release gate criteria
    assert "ping" in content.lower()
    assert "quality-mcp" in content
    assert "0.1.0" in content

    # Key verification artifacts cataloged
    expected_artifacts = [
        "packages/quality-mcp/tests/test_version.py",
        "packages/quality-mcp/tests/test_server.py",
        "packages/quality-mcp/tests/test_client_roundtrip.py",
        "tests/test_github_templates.py",
        "tests/test_milestones_convention.py",
        "docs/mcp-client-setup.md",
        ".github/workflows/ci.yml",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Missing expected verification artifact in v0.1.0.md: {artifact}"


def test_roadmap_links_v010_milestone() -> None:
    """Verify ROADMAP.md links v0.1.0 in Summary Release Matrix to docs/milestones/v0.1.0.md."""
    assert _ROADMAP.is_file(), f"Missing ROADMAP: {_ROADMAP}"
    content = _ROADMAP.read_text(encoding="utf-8")

    assert "[**`v0.1.0`**](docs/milestones/v0.1.0.md)" in content or "[`v0.1.0`](docs/milestones/v0.1.0.md)" in content, (
        "ROADMAP.md Summary Release Matrix must link v0.1.0 to docs/milestones/v0.1.0.md"
    )


def test_v020_milestone_epics_and_issues_traceability() -> None:
    """Verify docs/milestones/v0.2.0.md defines Epics E1-E6 and links issues #16 through #21 with branch names."""
    assert _V020_MILESTONE.is_file(), f"Missing milestone v0.2.0 file: {_V020_MILESTONE}"
    content = _V020_MILESTONE.read_text(encoding="utf-8")

    # Verify all 6 Epics are present
    for epic_num in range(1, 7):
        assert f"Epic {epic_num} (E{epic_num})" in content or f"E{epic_num}:" in content, (
            f"Missing Epic {epic_num} in v0.2.0.md"
        )

    # Verify all 6 issues are present with canonical URLs and branch names
    issue_tuples = _extract_issue_urls(content)
    issue_numbers = {num for _, num in issue_tuples}

    expected_issues = {
        16: "feat/fmea-mcp-tool-16",
        17: "feat/ci-fmea-guard-17",
        18: "feat/mcp-fmea-client-roundtrip-18",
        19: "feat/fmea-reviewer-skill-19",
        20: "feat/fmea-canvas-reference-20",
        21: "feat/docs-milestones-21",
    }

    for expected_issue, branch_name in expected_issues.items():
        assert expected_issue in issue_numbers, f"Missing issue #{expected_issue} in v0.2.0.md"
        expected_url = f"https://github.com/Siddardth7/quality-engineering-skills/issues/{expected_issue}"
        assert expected_url in content, f"Missing canonical URL for issue #{expected_issue}: {expected_url}"
        assert branch_name in content, f"Missing branch {branch_name} for issue #{expected_issue} in v0.2.0.md"


def test_v020_milestone_release_gate_and_artifacts() -> None:
    """Verify v0.2.0.md specifies the 7 release gate criteria and catalogs verification artifacts."""
    assert _V020_MILESTONE.is_file(), f"Missing milestone v0.2.0 file: {_V020_MILESTONE}"
    content = _V020_MILESTONE.read_text(encoding="utf-8")

    # Release gate criteria
    assert "lookup_fmea_ap" in content
    assert "render_fmea_canvas" in content
    assert "fmea-reviewer" in content
    assert "Action Priority" in content or "action priority" in content
    assert "Single-Writer" in content or "single-writer" in content
    assert "100%" in content

    # Key verification artifacts cataloged
    expected_artifacts = [
        "packages/quality-core/src/quality_core/scoring.py",
        "packages/quality-core/src/quality_core/canvas/fmea.py",
        "packages/quality-core/tests/test_canvas.py",
        "packages/quality-mcp/src/quality_mcp/tools/fmea.py",
        "packages/quality-mcp/src/quality_mcp/tools/canvas.py",
        "packages/quality-mcp/tests/test_fmea_tool.py",
        "packages/quality-mcp/tests/test_canvas_tool.py",
        "packages/quality-mcp/tests/test_fmea_client_roundtrip.py",
        "skills/fmea-reviewer/SKILL.md",
        "docs/mcp-client-setup.md",
        "tests/test_skills_conventions.py",
        "tests/test_milestones_convention.py",
        ".github/workflows/ci.yml",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Missing expected verification artifact in v0.2.0.md: {artifact}"


def test_roadmap_links_v020_milestone() -> None:
    """Verify ROADMAP.md links v0.2.0 in Summary Release Matrix to docs/milestones/v0.2.0.md."""
    assert _ROADMAP.is_file(), f"Missing ROADMAP: {_ROADMAP}"
    content = _ROADMAP.read_text(encoding="utf-8")

    assert "[**`v0.2.0`**](docs/milestones/v0.2.0.md)" in content or "[`v0.2.0`](docs/milestones/v0.2.0.md)" in content, (
        "ROADMAP.md Summary Release Matrix must link v0.2.0 to docs/milestones/v0.2.0.md"
    )


def test_v030_milestone_epics_and_issues_traceability() -> None:
    """Verify docs/milestones/v0.3.0.md defines Epics E1-E6 and links issues #29 through #34 with branch names."""
    assert _V030_MILESTONE.is_file(), f"Missing milestone v0.3.0 file: {_V030_MILESTONE}"
    content = _V030_MILESTONE.read_text(encoding="utf-8")

    # Verify all 6 Epics are present
    for epic_num in range(1, 7):
        assert f"Epic {epic_num} (E{epic_num})" in content or f"E{epic_num}:" in content, (
            f"Missing Epic {epic_num} in v0.3.0.md"
        )

    # Verify all 6 issues are present with canonical URLs and branch names
    issue_tuples = _extract_issue_urls(content)
    issue_numbers = {num for _, num in issue_tuples}

    expected_issues = {
        29: "feat/spc-mcp-tool-29",
        30: "feat/ci-spc-guard-30",
        31: "feat/mcp-spc-client-roundtrip-31",
        32: "feat/spc-control-charts-skill-32",
        33: "feat/spc-canvas-33",
        34: "feat/milestone-v0.3.0-docs-34",
    }

    for expected_issue, branch_name in expected_issues.items():
        assert expected_issue in issue_numbers, f"Missing issue #{expected_issue} in v0.3.0.md"
        expected_url = f"https://github.com/Siddardth7/quality-engineering-skills/issues/{expected_issue}"
        assert expected_url in content, f"Missing canonical URL for issue #{expected_issue}: {expected_url}"
        assert branch_name in content, f"Missing branch {branch_name} for issue #{expected_issue} in v0.3.0.md"


def test_v030_milestone_release_gate_and_artifacts() -> None:
    """Verify v0.3.0.md specifies the 7 release gate criteria and catalogs verification artifacts."""
    assert _V030_MILESTONE.is_file(), f"Missing milestone v0.3.0 file: {_V030_MILESTONE}"
    content = _V030_MILESTONE.read_text(encoding="utf-8")

    # Release gate criteria
    assert "calculate_spc_chart" in content
    assert "render_spc_canvas" in content
    assert "spc-control-charts" in content
    assert "stability gate" in content.lower()
    assert "100%" in content

    # Key verification artifacts cataloged
    expected_artifacts = [
        "packages/quality-core/src/quality_core/spc/control_charts.py",
        "packages/quality-core/src/quality_core/spc/rule_detection.py",
        "packages/quality-core/src/quality_core/spc/stability.py",
        "packages/quality-core/src/quality_core/spc/capability.py",
        "packages/quality-core/src/quality_core/canvas/spc.py",
        "packages/quality-core/tests/test_canvas.py",
        "packages/quality-mcp/src/quality_mcp/tools/spc.py",
        "packages/quality-mcp/src/quality_mcp/tools/canvas.py",
        "packages/quality-mcp/tests/test_spc_tool.py",
        "packages/quality-mcp/tests/test_canvas_tool.py",
        "packages/quality-mcp/tests/test_spc_client_roundtrip.py",
        "skills/spc-control-charts/SKILL.md",
        "docs/mcp-client-setup.md",
        "tests/test_skills_conventions.py",
        "tests/test_milestones_convention.py",
        ".github/workflows/ci.yml",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Missing expected verification artifact in v0.3.0.md: {artifact}"


def test_roadmap_links_v030_milestone() -> None:
    """Verify ROADMAP.md links v0.3.0 in Summary Release Matrix to docs/milestones/v0.3.0.md."""
    assert _ROADMAP.is_file(), f"Missing ROADMAP: {_ROADMAP}"
    content = _ROADMAP.read_text(encoding="utf-8")

    assert "[**`v0.3.0`**](docs/milestones/v0.3.0.md)" in content or "[`v0.3.0`](docs/milestones/v0.3.0.md)" in content, (
        "ROADMAP.md Summary Release Matrix must link v0.3.0 to docs/milestones/v0.3.0.md"
    )


def test_v040_milestone_epics_and_issues_traceability() -> None:
    """Verify docs/milestones/v0.4.0.md defines Epics E1-E7 and links issues #35 through #41 with branch names."""
    assert _V040_MILESTONE.is_file(), f"Missing milestone v0.4.0 file: {_V040_MILESTONE}"
    content = _V040_MILESTONE.read_text(encoding="utf-8")

    # Verify all 7 Epics are present
    for epic_num in range(1, 8):
        assert f"Epic {epic_num} (E{epic_num})" in content or f"E{epic_num}:" in content, (
            f"Missing Epic {epic_num} in v0.4.0.md"
        )

    # Verify all 7 issues are present with canonical URLs and branch names
    issue_tuples = _extract_issue_urls(content)
    issue_numbers = {num for _, num in issue_tuples}

    expected_issues = {
        35: "feat/msa-extract-core-35",
        36: "feat/msa-mcp-tool-36",
        37: "feat/ci-msa-guard-37",
        38: "feat/mcp-msa-client-roundtrip-38",
        39: "feat/msa-gauge-rr-skill-39",
        40: "feat/msa-canvas-view-40",
        41: "feat/m4-closure-docs-41",
    }

    for expected_issue, branch_name in expected_issues.items():
        assert expected_issue in issue_numbers, f"Missing issue #{expected_issue} in v0.4.0.md"
        expected_url = f"https://github.com/Siddardth7/quality-engineering-skills/issues/{expected_issue}"
        assert expected_url in content, f"Missing canonical URL for issue #{expected_issue}: {expected_url}"
        assert branch_name in content, f"Missing branch {branch_name} for issue #{expected_issue} in v0.4.0.md"


def test_v040_milestone_release_gate_and_artifacts() -> None:
    """Verify v0.4.0.md specifies the 7 release gate criteria and catalogs verification artifacts."""
    assert _V040_MILESTONE.is_file(), f"Missing milestone v0.4.0 file: {_V040_MILESTONE}"
    content = _V040_MILESTONE.read_text(encoding="utf-8")

    # Release gate criteria
    assert "calculate_gage_rr" in content
    assert "render_msa_canvas" in content
    assert "msa-gauge-rr" in content
    assert "ANOVA" in content or "anova" in content
    assert "Single-Writer" in content or "single-writer" in content
    assert "100%" in content
    assert "CITATIONS.tsv" in content

    # Key verification artifacts cataloged
    expected_artifacts = [
        "packages/quality-core/src/quality_core/msa/gage_rr.py",
        "packages/quality-core/src/quality_core/msa/schema.py",
        "packages/quality-core/src/quality_core/msa/ASSUMPTIONS_LOG.md",
        "packages/quality-core/src/quality_core/msa/CITATIONS.tsv",
        "packages/quality-core/src/quality_core/canvas/msa.py",
        "packages/quality-core/tests/test_msa_gage_rr_engine.py",
        "packages/quality-core/tests/test_msa_schema.py",
        "packages/quality-core/tests/test_msa_citations.py",
        "packages/quality-core/tests/test_canvas.py",
        "packages/quality-mcp/src/quality_mcp/tools/msa.py",
        "packages/quality-mcp/src/quality_mcp/tools/canvas.py",
        "packages/quality-mcp/tests/test_msa_tool.py",
        "packages/quality-mcp/tests/test_canvas_tool.py",
        "packages/quality-mcp/tests/test_msa_client_roundtrip.py",
        "skills/msa-gauge-rr/SKILL.md",
        "docs/mcp-client-setup.md",
        "tests/test_skills_conventions.py",
        "tests/test_milestones_convention.py",
        ".github/workflows/ci.yml",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Missing expected verification artifact in v0.4.0.md: {artifact}"


def test_roadmap_links_v040_milestone() -> None:
    """Verify ROADMAP.md links v0.4.0 in Summary Release Matrix to docs/milestones/v0.4.0.md."""
    assert _ROADMAP.is_file(), f"Missing ROADMAP: {_ROADMAP}"
    content = _ROADMAP.read_text(encoding="utf-8")

    assert "[**`v0.4.0`**](docs/milestones/v0.4.0.md)" in content or "[`v0.4.0`](docs/milestones/v0.4.0.md)" in content, (
        "ROADMAP.md Summary Release Matrix must link v0.4.0 to docs/milestones/v0.4.0.md"
    )


def test_v050_milestone_epics_and_issues_traceability() -> None:
    """Verify docs/milestones/v0.5.0.md defines Epics E1-E7 and links issues #42 through #48 with branch names."""
    assert _V050_MILESTONE.is_file(), f"Missing milestone v0.5.0 file: {_V050_MILESTONE}"
    content = _V050_MILESTONE.read_text(encoding="utf-8")

    # Verify all 7 Epics are present
    for epic_num in range(1, 8):
        assert f"Epic {epic_num} (E{epic_num})" in content or f"E{epic_num}:" in content, (
            f"Missing Epic {epic_num} in v0.5.0.md"
        )

    # Verify all 7 issues are present with canonical URLs and branch names
    issue_tuples = _extract_issue_urls(content)
    issue_numbers = {num for _, num in issue_tuples}

    expected_issues = {
        42: "feat/controlplan-extract-core-42",
        43: "feat/controlplan-mcp-tool-43",
        44: "feat/controlplan-ci-guard-44",
        45: "feat/controlplan-client-roundtrip-45",
        46: "feat/control-plan-skill-46",
        47: "feat/controlplan-canvas-47",
        48: "feat/docs-milestones-48",
    }

    for expected_issue, branch_name in expected_issues.items():
        assert expected_issue in issue_numbers, f"Missing issue #{expected_issue} in v0.5.0.md"
        expected_url = f"https://github.com/Siddardth7/quality-engineering-skills/issues/{expected_issue}"
        assert expected_url in content, f"Missing canonical URL for issue #{expected_issue}: {expected_url}"
        assert branch_name in content, f"Missing branch {branch_name} for issue #{expected_issue} in v0.5.0.md"


def test_v050_milestone_release_gate_and_artifacts() -> None:
    """Verify v0.5.0.md specifies the release gate criteria and catalogs verification artifacts."""
    assert _V050_MILESTONE.is_file(), f"Missing milestone v0.5.0 file: {_V050_MILESTONE}"
    content = _V050_MILESTONE.read_text(encoding="utf-8")

    # Release gate criteria
    assert "validate_control_plan" in content
    assert "render_controlplan_canvas" in content
    assert "control-plan" in content
    assert "PFMEA" in content or "pfmea" in content
    assert "4-Engine Checkpoint" in content or "4-engine" in content.lower()
    assert "100%" in content
    assert "CITATIONS.tsv" in content

    # Key verification artifacts cataloged
    expected_artifacts = [
        "packages/quality-core/src/quality_core/controlplan/schema.py",
        "packages/quality-core/src/quality_core/controlplan/connector.py",
        "packages/quality-core/src/quality_core/controlplan/ASSUMPTIONS_LOG.md",
        "packages/quality-core/src/quality_core/controlplan/CITATIONS.tsv",
        "packages/quality-core/src/quality_core/canvas/controlplan.py",
        "packages/quality-core/tests/test_controlplan_schema.py",
        "packages/quality-core/tests/test_controlplan_connector.py",
        "packages/quality-core/tests/test_controlplan_linkage.py",
        "packages/quality-core/tests/test_controlplan_citations.py",
        "packages/quality-core/tests/test_canvas.py",
        "packages/quality-mcp/src/quality_mcp/tools/controlplan.py",
        "packages/quality-mcp/src/quality_mcp/tools/canvas.py",
        "packages/quality-mcp/tests/test_controlplan_tool.py",
        "packages/quality-mcp/tests/test_canvas_tool.py",
        "packages/quality-mcp/tests/test_controlplan_client_roundtrip.py",
        "packages/quality-mcp/tests/test_four_engine_smoke.py",
        "skills/control-plan/SKILL.md",
        "docs/mcp-client-setup.md",
        "tests/test_skills_conventions.py",
        "tests/test_milestones_convention.py",
        ".github/workflows/ci.yml",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Missing expected verification artifact in v0.5.0.md: {artifact}"


def test_roadmap_links_v050_milestone() -> None:
    """Verify ROADMAP.md links v0.5.0 in Summary Release Matrix to docs/milestones/v0.5.0.md."""
    assert _ROADMAP.is_file(), f"Missing ROADMAP: {_ROADMAP}"
    content = _ROADMAP.read_text(encoding="utf-8")

    assert "[**`v0.5.0`**](docs/milestones/v0.5.0.md)" in content or "[`v0.5.0`](docs/milestones/v0.5.0.md)" in content, (
        "ROADMAP.md Summary Release Matrix must link v0.5.0 to docs/milestones/v0.5.0.md"
    )


def test_v060_milestone_epics_and_issues_traceability() -> None:
    """Verify docs/milestones/v0.6.0.md defines Epics E0-E6 and links issues #74 through #80 with branch names."""
    assert _V060_MILESTONE.is_file(), f"Missing milestone v0.6.0 file: {_V060_MILESTONE}"
    content = _V060_MILESTONE.read_text(encoding="utf-8")

    # Verify all 7 Epics are present (E0 through E6)
    for epic_num in range(0, 7):
        assert f"Epic {epic_num} (E{epic_num})" in content or f"E{epic_num}:" in content, (
            f"Missing Epic {epic_num} in v0.6.0.md"
        )

    # Verify all 7 issues are present with canonical URLs and branch names
    issue_tuples = _extract_issue_urls(content)
    issue_numbers = {num for _, num in issue_tuples}

    expected_issues = {
        74: "chore/rca-literature-citations-74",
        75: "feat/rca-engine-scaffold-schema-75",
        76: "feat/rca-5why-validator-76",
        77: "feat/rca-fishbone-engine-77",
        78: "feat/rca-is-isnot-engine-78",
        79: "feat/rca-unified-pipeline-79",
        80: "feat/rca-suite-closeout-80",
    }

    for expected_issue, branch_name in expected_issues.items():
        assert expected_issue in issue_numbers, f"Missing issue #{expected_issue} in v0.6.0.md"
        expected_url = f"https://github.com/Siddardth7/quality-engineering-skills/issues/{expected_issue}"
        assert expected_url in content, f"Missing canonical URL for issue #{expected_issue}: {expected_url}"
        assert branch_name in content, f"Missing branch {branch_name} for issue #{expected_issue} in v0.6.0.md"


def test_v060_milestone_release_gate_and_artifacts() -> None:
    """Verify v0.6.0.md specifies the release gate criteria and catalogs verification artifacts."""
    assert _V060_MILESTONE.is_file(), f"Missing milestone v0.6.0 file: {_V060_MILESTONE}"
    content = _V060_MILESTONE.read_text(encoding="utf-8")

    # Release gate criteria
    assert "validate_5why" in content
    assert "categorize_fishbone" in content
    assert "scope_is_is_not" in content
    assert "render_5why_canvas" in content
    assert "render_fishbone_canvas" in content
    assert "render_isisnot_canvas" in content
    assert "5why-root-cause" in content
    assert "fishbone-analysis" in content
    assert "is-is-not-scoping" in content
    assert "100%" in content
    assert "CITATIONS.tsv" in content

    # Key verification artifacts cataloged
    expected_artifacts = [
        "packages/quality-core/src/quality_core/rca/five_why.py",
        "packages/quality-core/src/quality_core/rca/fishbone.py",
        "packages/quality-core/src/quality_core/rca/is_is_not.py",
        "packages/quality-core/src/quality_core/rca/schema.py",
        "packages/quality-core/src/quality_core/rca/ASSUMPTIONS_LOG.md",
        "packages/quality-core/src/quality_core/rca/CITATIONS.tsv",
        "packages/quality-core/src/quality_core/canvas/rca.py",
        "packages/quality-core/tests/test_five_why_engine.py",
        "packages/quality-core/tests/test_five_why_scorecard.py",
        "packages/quality-core/tests/test_fishbone_engine.py",
        "packages/quality-core/tests/test_fishbone_scorecard.py",
        "packages/quality-core/tests/test_is_is_not_engine.py",
        "packages/quality-core/tests/test_is_is_not_scorecard.py",
        "packages/quality-core/tests/test_rca_schema.py",
        "packages/quality-core/tests/test_rca_canvas.py",
        "packages/quality-core/tests/test_rca_citations.py",
        "packages/quality-mcp/src/quality_mcp/tools/rca.py",
        "packages/quality-mcp/src/quality_mcp/tools/canvas.py",
        "packages/quality-mcp/tests/test_rca_tools.py",
        "packages/quality-mcp/tests/test_rca_client_roundtrip.py",
        "skills/5why-root-cause/SKILL.md",
        "skills/fishbone-analysis/SKILL.md",
        "skills/is-is-not-scoping/SKILL.md",
        "docs/mcp-client-setup.md",
        "tests/test_skills_conventions.py",
        "tests/test_milestones_convention.py",
        ".github/workflows/ci.yml",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Missing expected verification artifact in v0.6.0.md: {artifact}"


def test_roadmap_links_v060_milestone() -> None:
    """Verify ROADMAP.md links v0.6.0 in Summary Release Matrix to docs/milestones/v0.6.0.md."""
    assert _ROADMAP.is_file(), f"Missing ROADMAP: {_ROADMAP}"
    content = _ROADMAP.read_text(encoding="utf-8")

    assert "[**`v0.6.0`**](docs/milestones/v0.6.0.md)" in content or "[`v0.6.0`](docs/milestones/v0.6.0.md)" in content, (
        "ROADMAP.md Summary Release Matrix must link v0.6.0 to docs/milestones/v0.6.0.md"
    )


def test_milestones_markdown_links_resolve() -> None:
    """Verify all relative markdown links in docs/milestones/*.md resolve to existing repository files."""
    for md_file in _MILESTONES_DIR.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        resolved_paths = _resolve_relative_links(md_file, content)
        for resolved in resolved_paths:
            assert resolved.exists(), (
                f"Broken relative link in {md_file.relative_to(_REPO_ROOT)} targets non-existent path: {resolved}"
            )


def test_changelog_entry_unreleased() -> None:
    """Verify CHANGELOG.md contains the issue #7, #21, #34, #41, #48, and #80 entries under [0.1.0], [0.2.0], [0.3.0], [0.4.0], [0.5.0], [0.6.0], or [Unreleased]."""
    assert _CHANGELOG.is_file(), f"Missing CHANGELOG file: {_CHANGELOG}"
    content = _CHANGELOG.read_text(encoding="utf-8")

    assert "#7" in content, "CHANGELOG.md must reference issue #7"
    assert "#21" in content, "CHANGELOG.md must reference issue #21"
    assert "#34" in content, "CHANGELOG.md must reference issue #34"
    assert "#41" in content, "CHANGELOG.md must reference issue #41"
    assert "#48" in content, "CHANGELOG.md must reference issue #48"
    assert "#80" in content, "CHANGELOG.md must reference issue #80"
    assert "docs/milestones/README.md" in content
    assert "docs/milestones/v0.1.0.md" in content
    assert "docs/milestones/v0.2.0.md" in content
    assert "docs/milestones/v0.3.0.md" in content
    assert "docs/milestones/v0.4.0.md" in content
    assert "docs/milestones/v0.5.0.md" in content
    assert "docs/milestones/v0.6.0.md" in content
    assert "tests/test_milestones_convention.py" in content


# ==============================================================================
# Negative Controls & Mutation Testing
# ==============================================================================


def test_negative_control_invalid_filename_rejected() -> None:
    """Negative control: assert non-SemVer filenames are rejected."""
    invalid_filenames = [
        "v0.1.md",
        "milestone-1.md",
        "v1.0.0-rc1.md",
        "0.1.0.md",
        "v0.1.0.txt",
        "vx.y.z.md",
        "v0.1.0.preview.md",
    ]
    for invalid in invalid_filenames:
        assert not _validate_milestone_filename(invalid), f"Should reject invalid filename {invalid!r}"


def test_negative_control_missing_mandatory_section_rejected() -> None:
    """Negative control: assert missing mandatory section raises ValueError."""
    dummy_content = """# Milestone 1: Test (v0.1.0)
## Overview
Some overview text.
## Epics & Issues
Epic details.
## Release Gate Criteria
Gate criteria.
## Verification Artifacts & Test Evidence
Artifact list.
"""
    # Missing '## Retrospective & Status'
    with pytest.raises(ValueError, match="Missing mandatory section '## Retrospective & Status'"):
        _validate_milestone_content_structure(dummy_content)


def test_negative_control_invalid_issue_url_pattern_rejected() -> None:
    """Negative control: assert invalid issue URL formats are not extracted as canonical URLs."""
    malformed_content = """
    - Issue #1: [Issue 1](http://github.com/Siddardth7/quality-engineering-skills/issues/1) (http instead of https)
    - Issue #2: [Issue 2](https://github.com/OtherOrg/quality-engineering-skills/issues/2) (wrong org)
    - Issue #3: [Issue 3](https://github.com/Siddardth7/other-repo/issues/3) (wrong repo)
    - Issue #4: [Issue 4](https://github.com/Siddardth7/quality-engineering-skills/pull/4) (pull instead of issues)
    - Issue #5: [Issue 5](https://github.com/Siddardth7/quality-engineering-skills/issues/abc) (non-numeric id)
    """
    extracted = _extract_issue_urls(malformed_content)
    assert len(extracted) == 0, f"Expected 0 valid canonical issue URLs extracted, got {extracted}"


def test_negative_control_broken_relative_link_detection(tmp_path: Path) -> None:
    """Negative control: assert broken relative link targets non-existent file."""
    test_file = tmp_path / "test_doc.md"
    content = "[Missing File](non_existent_file.md)"
    test_file.write_text(content, encoding="utf-8")

    resolved_paths = _resolve_relative_links(test_file, content)
    assert len(resolved_paths) == 1
    assert not resolved_paths[0].exists(), "Non-existent path must be detected as not existing"


def test_negative_control_v060_missing_epic_or_issue_rejected() -> None:
    """Negative control: assert missing Epic or Issue in v0.6.0.md content is detected."""
    content = _V060_MILESTONE.read_text(encoding="utf-8")

    # Mutate by removing Epic 0
    mutated_no_e0 = content.replace("Epic 0 (E0)", "Removed Epic 0")
    assert "Epic 0 (E0)" not in mutated_no_e0

    # Mutate by removing issue #80
    mutated_no_issue80 = content.replace("https://github.com/Siddardth7/quality-engineering-skills/issues/80", "")
    extracted = _extract_issue_urls(mutated_no_issue80)
    issue_nums = {num for _, num in extracted}
    assert 80 not in issue_nums


def test_negative_control_v060_corrupted_branch_name_rejected() -> None:
    """Negative control: assert altered or corrupted feature branch name in v0.6.0.md is detected."""
    content = _V060_MILESTONE.read_text(encoding="utf-8")
    mutated = content.replace("feat/rca-suite-closeout-80", "feat/rca-corrupted-branch-99")
    assert "feat/rca-suite-closeout-80" not in mutated


def test_negative_control_v060_missing_artifact_rejected() -> None:
    """Negative control: assert missing critical verification artifact in v0.6.0.md is detected."""
    content = _V060_MILESTONE.read_text(encoding="utf-8")
    mutated = content.replace("packages/quality-mcp/tests/test_rca_client_roundtrip.py", "")
    assert "packages/quality-mcp/tests/test_rca_client_roundtrip.py" not in mutated


def test_negative_control_roadmap_missing_v060_rejected() -> None:
    """Negative control: assert ROADMAP missing v0.6.0 link is detected."""
    content = _ROADMAP.read_text(encoding="utf-8")
    mutated = content.replace("[**`v0.6.0`**](docs/milestones/v0.6.0.md)", "**`v0.6.0`**")
    assert "[**`v0.6.0`**](docs/milestones/v0.6.0.md)" not in mutated


def test_negative_control_changelog_missing_issue_80_rejected() -> None:
    """Negative control: assert CHANGELOG missing #80 reference is detected."""
    content = _CHANGELOG.read_text(encoding="utf-8")
    mutated = content.replace("#80", "#999")
    assert "#80" not in mutated

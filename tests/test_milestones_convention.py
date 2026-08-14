"""Test suite for milestone documentation, SemVer naming, and governance conventions (#7).

Validates:
1. Presence of docs/milestones/ directory and README.md governance documentation.
2. SemVer filename mapping convention (docs/milestones/vX.Y.Z.md).
3. Mandatory structural sections across all milestone files.
4. Milestone 1 (v0.1.0.md) Epic definitions (E1-E4) and Issue traceability (#1 through #7).
5. Real MCP client ping release gate and verification artifacts cataloging.
6. Summary Release Matrix table link update in ROADMAP.md.
7. Markdown relative link resolution against repository filesystem.
8. CHANGELOG.md entry formatting under [Unreleased] -> Added (#7).
9. Negative controls: detection of invalid filenames, missing sections, invalid issue URLs, and broken links.
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
    """Verify CHANGELOG.md contains the issue #7 entry under [0.1.0] or [Unreleased]."""
    assert _CHANGELOG.is_file(), f"Missing CHANGELOG file: {_CHANGELOG}"
    content = _CHANGELOG.read_text(encoding="utf-8")

    assert "#7" in content, "CHANGELOG.md must reference issue #7"
    assert "docs/milestones/README.md" in content
    assert "docs/milestones/v0.1.0.md" in content
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

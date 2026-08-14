"""Test suite for GitHub templates, issue configuration, and branch ladder governance (#5).

Validates:
1. YAML frontmatter parsing in .github/ISSUE_TEMPLATE/task.md
2. Configuration syntax and blank issue suppression in .github/ISSUE_TEMPLATE/config.yml
3. Pull request template structure, 7-gate Definition of Done checklist, and evidence blocks
4. Markdown relative link resolution against repository filesystem
5. CHANGELOG.md entry formatting under [Unreleased] -> Added (#5)
6. Negative controls: absence of deprecated 'dev' branch / '/promote' references and strict boolean typing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GITHUB_DIR = _REPO_ROOT / ".github"
_TASK_TEMPLATE = _GITHUB_DIR / "ISSUE_TEMPLATE" / "task.md"
_CONFIG_YML = _GITHUB_DIR / "ISSUE_TEMPLATE" / "config.yml"
_PR_TEMPLATE = _GITHUB_DIR / "pull_request_template.md"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Lightweight deterministic YAML parser for template config files."""
    result: dict[str, Any] = {}
    lines = text.strip().splitlines()
    current_list: list[Any] | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue

        if not line.startswith(" ") and ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if not val:
                current_list = []
                result[key] = current_list
            else:
                current_list = None
                result[key] = _parse_scalar(val)
        elif line.strip().startswith("- ") and current_list is not None:
            item_content = line.strip()[2:].strip()
            if ":" in item_content:
                item_dict: dict[str, Any] = {}
                k, v = item_content.split(":", 1)
                item_dict[k.strip()] = _parse_scalar(v.strip())
                current_list.append(item_dict)
            else:
                current_list.append(_parse_scalar(item_content))
        elif line.startswith("    ") and current_list and isinstance(current_list[-1], dict):
            k, v = line.strip().split(":", 1)
            current_list[-1][k.strip()] = _parse_scalar(v.strip())

    return result


def _parse_scalar(val: str) -> Any:
    if val == "false":
        return False
    if val == "true":
        return True
    if val == "[]":
        return []
    if val in ("''", '""'):
        return ""
    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
        return val[1:-1]
    try:
        return int(val)
    except ValueError:
        return val


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract and parse YAML frontmatter and markdown body from markdown content."""
    if not content.startswith("---"):
        raise ValueError("Markdown file does not start with frontmatter delimiter '---'")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Markdown file does not contain closing frontmatter delimiter '---'")
    frontmatter_raw = parts[1]
    body = parts[2]
    return _parse_simple_yaml(frontmatter_raw), body


def test_task_issue_template_frontmatter() -> None:
    """Verify .github/ISSUE_TEMPLATE/task.md frontmatter keys and values."""
    assert _TASK_TEMPLATE.is_file(), f"Missing template file: {_TASK_TEMPLATE}"
    content = _TASK_TEMPLATE.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(content)

    assert fm.get("name") == "Task Issue", "Frontmatter 'name' must be 'Task Issue'"
    assert fm.get("about") == "Standard engineering task issue for milestone epics"
    assert fm.get("title") == "[E<#>] <title>"
    assert fm.get("labels") == []
    assert fm.get("assignees") == ""


def test_task_issue_template_body_structure() -> None:
    """Verify task issue template sections, user story, and 8 acceptance criteria items."""
    content = _TASK_TEMPLATE.read_text(encoding="utf-8")
    _, body = _parse_frontmatter(content)

    assert "[docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md)" in body
    assert "[Execution.md](Execution.md)" in body

    assert "### Metadata" in body
    assert "- **Epic**:" in body
    assert "- **Order / Dependencies**:" in body
    assert "- **Size**: [S | M | L | XL]" in body
    assert "[docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md#sizing-legend-issue-fields--labels)" in body
    assert "- **Complexity**: [low | med | high]" in body
    assert "- **Priority**: [P0 | P1 | P2]" in body

    assert "### User Story" in body
    assert "As a Quality Engineer, I want to [action] so that [business outcome]." in body

    assert "### Technical Scope & Engine Location" in body
    assert "- Skill: `skills/[domain]/[skill-name]/SKILL.md`" in body
    assert "- Engine: `packages/quality-core/src/quality_core/[module]/`" in body
    assert "- MCP Tool: `packages/quality-mcp/src/quality_mcp/tools/[tool_name].py`" in body
    assert "- CI Gate: new `--cov=quality_core.[module] --cov-fail-under=100`" in body

    assert "### Acceptance Criteria" in body
    expected_criteria = [
        "Python engine math verified with 100% branch test coverage, including negative controls.",
        "Any new standard-body constant/threshold cited in `apps/<domain>/docs/ASSUMPTIONS_LOG.md`, verified against the licensed manual — never against a web search.",
        "MCP tool binding registered and verified against an actual MCP client round-trip (Claude Code / Cursor), not just a unit test.",
        "Canvas component rendered (from `v0.2.0` onward) and round-trips at least one edit (N/A for headless / platform setup issues).",
        "Dedicated `--cov-fail-under=100` CI gate added to `.github/workflows/ci.yml` (if introducing a new engine or MCP tool surface).",
        "Repository passes all static analysis: `uv run ruff check .` and `uv run mypy`.",
        "`CHANGELOG.md` updated under `[Unreleased]` in the same PR.",
        "Conforms to all gates in [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md).",
    ]
    for criterion in expected_criteria:
        assert f"- [ ] {criterion}" in body, f"Missing acceptance criterion: {criterion}"


def test_config_yaml_structure_and_types() -> None:
    """Verify .github/ISSUE_TEMPLATE/config.yml disables blank issues and provides DoD link."""
    assert _CONFIG_YML.is_file(), f"Missing config file: {_CONFIG_YML}"
    content = _CONFIG_YML.read_text(encoding="utf-8")
    parsed = _parse_simple_yaml(content)

    assert parsed.get("blank_issues_enabled") is False
    assert isinstance(parsed.get("blank_issues_enabled"), bool), "blank_issues_enabled must be a strict boolean"

    contact_links = parsed.get("contact_links")
    assert isinstance(contact_links, list)
    assert len(contact_links) >= 1
    dod_link = contact_links[0]
    assert dod_link.get("name") == "Definition of Done Contract"
    assert dod_link.get("url") == "https://github.com/Siddardth7/quality-engineering-skills/blob/test/docs/DEFINITION_OF_DONE.md"
    assert "Read the engineering standards" in dod_link.get("about", "")


def test_pull_request_template_structure() -> None:
    """Verify pull request template contains required evidence sections, branch ladder, and 7-gate DoD checklist."""
    assert _PR_TEMPLATE.is_file(), f"Missing PR template: {_PR_TEMPLATE}"
    content = _PR_TEMPLATE.read_text(encoding="utf-8")

    assert "## Issue Link" in content
    assert "Closes #" in content

    assert "## What & Why" in content
    assert "### What changed" in content
    assert "### Why" in content

    assert "## Branch Ladder Discipline" in content
    assert "> **Branch Ladder:** `feature → test → main`" in content
    assert "> - Base branch: `origin/test`" in content
    assert "> - Target branch: `test`" in content
    assert "> - Merge discipline: **Squash merge** into `test`" in content
    assert "> - **Never merge directly into `main`**." in content

    assert "## Evidence" in content
    assert "### Test Suite & Coverage" in content
    assert "$ uv run pytest --cov" in content
    assert "### Per-Surface Coverage Gate (`--cov-fail-under=100`)" in content
    assert "$ uv run pytest <surface-path> --cov=<module> --cov-report=term-missing --cov-fail-under=100" in content
    assert "### Static Analysis" in content
    assert "$ uv run ruff check ." in content
    assert "$ uv run mypy" in content
    assert "### Negative Controls & Mutation Verification" in content

    assert "## Definition of Done Checklist" in content
    assert "[docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md)" in content
    assert "- [ ] **Gate 1 (Minimal Implementation)**:" in content
    assert "- [ ] **Gate 2 (Dedicated Tester)**:" in content
    assert "- [ ] **Gate 3 (Coverage Learning Loop)**:" in content
    assert "- [ ] **Gate 4 (Code Review)**:" in content
    assert "- [ ] **Gate 5 (Over-engineering Review)**:" in content
    assert "- [ ] **Gate 6 (Green + Clean + Logged)**:" in content
    assert "- [ ] **Gate 7 (Branch & Merge)**:" in content


def test_template_markdown_links_resolve() -> None:
    """Verify all Markdown relative links in .github/ templates point to existing repo files."""
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for template_file in [_TASK_TEMPLATE, _PR_TEMPLATE]:
        content = template_file.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            target = match.group(2)
            if target.startswith("http://") or target.startswith("https://") or target.startswith("#"):
                continue
            file_path_part = target.split("#")[0]
            resolved = _REPO_ROOT / file_path_part
            assert resolved.exists(), (
                f"Link in {template_file.relative_to(_REPO_ROOT)} targets non-existent path: {file_path_part} "
                f"(resolved to {resolved})"
            )


def test_changelog_entry_unreleased() -> None:
    """Verify CHANGELOG.md contains the issue #5 entry under [Unreleased] -> Added."""
    assert _CHANGELOG.is_file(), f"Missing CHANGELOG file: {_CHANGELOG}"
    content = _CHANGELOG.read_text(encoding="utf-8")

    assert "## [Unreleased]" in content
    unreleased_section = content.split("## [Unreleased]")[1].split("## [")[0]
    assert "### Added" in unreleased_section

    added_section = unreleased_section.split("### Added")[1].split("###")[0]
    assert "#5" in added_section, "CHANGELOG.md [Unreleased] -> Added must reference issue #5"
    assert ".github/ISSUE_TEMPLATE/task.md" in added_section
    assert ".github/ISSUE_TEMPLATE/config.yml" in added_section
    assert ".github/pull_request_template.md" in added_section


def test_negative_control_no_deprecated_branch_references() -> None:
    """Negative control: assert no deprecated 'dev' branch or '/promote' references exist in .github/ templates."""
    deprecated_patterns = [
        re.compile(r"\bdev\b", re.IGNORECASE),
        re.compile(r"/promote", re.IGNORECASE),
    ]

    for path in [_TASK_TEMPLATE, _CONFIG_YML, _PR_TEMPLATE]:
        content = path.read_text(encoding="utf-8")
        for pattern in deprecated_patterns:
            matches = pattern.findall(content)
            assert len(matches) == 0, (
                f"Found forbidden deprecated branch/command reference {pattern.pattern!r} in {path.relative_to(_REPO_ROOT)}"
            )


def test_negative_control_blank_issues_disabled() -> None:
    """Negative control: assert blank_issues_enabled is explicitly boolean False, rejecting True, string, or omission."""
    raw_content = _CONFIG_YML.read_text(encoding="utf-8")
    assert re.search(r"^blank_issues_enabled:\s*false$", raw_content, re.MULTILINE) is not None, (
        "config.yml must contain literal 'blank_issues_enabled: false'"
    )

    parsed = _parse_simple_yaml(raw_content)
    assert parsed.get("blank_issues_enabled") is False
    assert parsed.get("blank_issues_enabled") is not True
    assert parsed.get("blank_issues_enabled") != "false"

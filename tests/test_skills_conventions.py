"""Governance test suite validating skills architecture conventions (#6).

Enforces the agentskills.io frontmatter specification, standard structural sections,
repository layout rules, strict prohibition of inline calculation logic in skills,
and isolation between domain skills (`skills/`) and meta-agent skills (`.claude/skills/`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_DIR = _REPO_ROOT / "skills"
_CLAUDE_SKILLS_DIR = _REPO_ROOT / ".claude" / "skills"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Overview",
    "When to Use",
    "Step-by-Step Methodology",
    "Tool Invocations",
    "Best Practices",
)

# Pattern matching level-2 markdown headings: ## Heading Name
_H2_HEADING_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Prohibited inline mathematical calculation execution patterns in skills.
# Skills must delegate all quantitative calculations to quality-mcp tools.
_PROHIBITED_MATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"```python\s+(?:import\s+(?:numpy|scipy|math)|def\s+calculate_)", re.IGNORECASE),
    re.compile(r"(?:compute|calculate)\s+(?:the\s+)?(?:mean|stdev|cpk|ppk|rpn)\s+manually", re.IGNORECASE),
    re.compile(r"perform\s+inline\s+(?:math|calculation)", re.IGNORECASE),
)


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter delimited by '---' from markdown content.

    Returns a tuple of (frontmatter_dict, markdown_body).
    Raises ValueError if frontmatter delimiters are missing or invalid.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Document does not begin with frontmatter delimiter '---'")

    closing_idx = -1
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_idx = idx
            break

    if closing_idx == -1:
        raise ValueError("Missing closing frontmatter delimiter '---'")

    frontmatter_lines = lines[1:closing_idx]
    body_text = "\n".join(lines[closing_idx + 1:])

    data: dict[str, str] = {}
    for line in frontmatter_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            data[key] = val
        else:
            raise ValueError(f"Invalid frontmatter key-value pair: {stripped!r}")

    return data, body_text


def extract_h2_sections(body: str) -> list[str]:
    """Extract all level-2 markdown section names from document body."""
    return [match.group(1).strip() for match in _H2_HEADING_PATTERN.finditer(body)]


def detect_prohibited_calculation_logic(content: str) -> list[str]:
    """Scan content for prohibited inline calculation or execution patterns."""
    violations: list[str] = []
    for pattern in _PROHIBITED_MATH_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            violations.append(f"Matched prohibited calculation pattern: {pattern.pattern!r}")
    return violations


def validate_skill_document(content: str, expected_dir_name: str | None = None) -> dict[str, Any]:
    """Validate a skill markdown file against agentskills.io conventions.

    Raises ValueError or AssertionError on validation failure.
    """
    frontmatter, body = parse_frontmatter(content)

    name = frontmatter.get("name", "").strip()
    if not name:
        raise ValueError("Frontmatter missing or empty 'name' field")

    description = frontmatter.get("description", "").strip()
    if not description:
        raise ValueError("Frontmatter missing or empty 'description' field")

    if expected_dir_name is not None:
        if expected_dir_name == "_template":
            assert name in {"skill-template", "_template"}, (
                f"Template skill name {name!r} must be 'skill-template' or '_template'"
            )
        else:
            assert name == expected_dir_name, (
                f"Skill name {name!r} does not match directory name {expected_dir_name!r}"
            )

    sections = extract_h2_sections(body)
    missing_sections = [sec for sec in REQUIRED_SECTIONS if sec not in sections]
    if missing_sections:
        raise ValueError(f"Missing mandatory section(s): {missing_sections}")

    math_violations = detect_prohibited_calculation_logic(body)
    if math_violations:
        raise ValueError(f"Prohibited calculation logic found in skill: {math_violations}")

    return {
        "name": name,
        "description": description,
        "sections": sections,
        "body": body,
    }


def _discover_skill_directories() -> list[Path]:
    """Discover all skill directories under skills/ (excluding hidden/special directories)."""
    assert _SKILLS_DIR.exists() and _SKILLS_DIR.is_dir(), f"Skills directory not found at {_SKILLS_DIR}"
    skill_dirs = [
        d for d in sorted(_SKILLS_DIR.iterdir())
        if d.is_dir() and not d.name.startswith((".", "__"))
    ]
    return skill_dirs


# ---------------------------------------------------------------------------
# Positive Control Tests
# ---------------------------------------------------------------------------

def test_skills_readme_exists_and_documents_conventions() -> None:
    """skills/README.md must exist and document architecture, triad, and conventions."""
    readme_path = _SKILLS_DIR / "README.md"
    assert readme_path.exists(), "skills/README.md does not exist"
    content = readme_path.read_text(encoding="utf-8")

    # Invariants and conventions documented
    assert "THE PRODUCT TRIAD" in content, "README.md missing Product Triad architecture diagram"
    assert "No Math in Skills" in content or "No calculation/math logic in skills" in content
    assert "packages/quality-core" in content
    assert "packages/quality-mcp" in content
    assert "agentskills.io" in content
    for section in REQUIRED_SECTIONS:
        assert section in content, f"README.md missing documentation for section {section!r}"


def test_discoverable_skill_directories_exist() -> None:
    """At least _template, mcp-health, fmea-reviewer, spc-control-charts, msa-gauge-rr, and control-plan skill directories must exist."""
    skill_dirs = _discover_skill_directories()
    dir_names = {d.name for d in skill_dirs}
    assert "_template" in dir_names, "skills/_template directory missing"
    assert "mcp-health" in dir_names, "skills/mcp-health directory missing"
    assert "fmea-reviewer" in dir_names, "skills/fmea-reviewer directory missing"
    assert "spc-control-charts" in dir_names, "skills/spc-control-charts directory missing"
    assert "msa-gauge-rr" in dir_names, "skills/msa-gauge-rr directory missing"
    assert "control-plan" in dir_names, "skills/control-plan directory missing"


@pytest.mark.parametrize(
    "skill_dir",
    _discover_skill_directories(),
    ids=lambda d: d.name,
)
def test_each_skill_directory_has_valid_skill_md(skill_dir: Path) -> None:
    """Every skill directory must contain a valid SKILL.md satisfying all conventions."""
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists(), f"{skill_dir.name} is missing SKILL.md"

    content = skill_md.read_text(encoding="utf-8")
    result = validate_skill_document(content, expected_dir_name=skill_dir.name)

    assert result["name"], f"Empty name in {skill_md}"
    assert result["description"], f"Empty description in {skill_md}"
    assert len(result["sections"]) >= len(REQUIRED_SECTIONS)


def test_mcp_health_skill_specifies_ping_tool() -> None:
    """skills/mcp-health/SKILL.md must document the ping MCP tool."""
    mcp_health_file = _SKILLS_DIR / "mcp-health" / "SKILL.md"
    content = mcp_health_file.read_text(encoding="utf-8")
    assert "ping" in content, "mcp-health skill must document the ping tool"
    assert "quality-mcp" in content, "mcp-health skill must reference quality-mcp"
    assert "0.1.0" in content or "0.2.0" in content, "mcp-health skill must reference platform version"


def test_fmea_reviewer_skill_specifies_lookup_fmea_ap_tool() -> None:
    """skills/fmea-reviewer/SKILL.md must document lookup_fmea_ap tool and cite AIAG & Action Priority."""
    fmea_reviewer_file = _SKILLS_DIR / "fmea-reviewer" / "SKILL.md"
    assert fmea_reviewer_file.exists(), "skills/fmea-reviewer/SKILL.md does not exist"
    content = fmea_reviewer_file.read_text(encoding="utf-8")
    assert "lookup_fmea_ap" in content, "fmea-reviewer skill must document lookup_fmea_ap tool"
    assert "quality-mcp" in content, "fmea-reviewer skill must reference quality-mcp"
    assert "AIAG" in content, "fmea-reviewer skill must cite AIAG"
    assert "Action Priority" in content, "fmea-reviewer skill must cite Action Priority"


def test_spc_control_charts_skill_specifies_calculate_spc_chart_tool() -> None:
    """skills/spc-control-charts/SKILL.md must document calculate_spc_chart tool, reference quality-mcp, and cite AIAG & stability."""
    spc_file = _SKILLS_DIR / "spc-control-charts" / "SKILL.md"
    assert spc_file.exists(), "skills/spc-control-charts/SKILL.md does not exist"
    content = spc_file.read_text(encoding="utf-8")
    assert "calculate_spc_chart" in content, "spc-control-charts skill must document calculate_spc_chart tool"
    assert "quality-mcp" in content, "spc-control-charts skill must reference quality-mcp"
    assert "AIAG" in content, "spc-control-charts skill must cite AIAG"
    assert "stability" in content or "in_control" in content, "spc-control-charts skill must document stability gate rule"


def test_msa_gauge_rr_skill_specifies_calculate_gage_rr_tool() -> None:
    """skills/msa-gauge-rr/SKILL.md must document calculate_gage_rr tool, reference quality-mcp, and cite AIAG & acceptance criteria."""
    msa_file = _SKILLS_DIR / "msa-gauge-rr" / "SKILL.md"
    assert msa_file.exists(), "skills/msa-gauge-rr/SKILL.md does not exist"
    content = msa_file.read_text(encoding="utf-8")
    assert "calculate_gage_rr" in content, "msa-gauge-rr skill must document calculate_gage_rr tool"
    assert "quality-mcp" in content, "msa-gauge-rr skill must reference quality-mcp"
    assert "AIAG" in content, "msa-gauge-rr skill must cite AIAG"
    assert "ndc" in content or "Distinct Categories" in content, "msa-gauge-rr skill must document ndc metric"


def test_control_plan_skill_specifies_validate_control_plan_tool() -> None:
    """skills/control-plan/SKILL.md must document validate_control_plan tool, reference quality-mcp, and cite AIAG & PFMEA linkage."""
    control_plan_file = _SKILLS_DIR / "control-plan" / "SKILL.md"
    assert control_plan_file.exists(), "skills/control-plan/SKILL.md does not exist"
    content = control_plan_file.read_text(encoding="utf-8")
    assert "validate_control_plan" in content, "control-plan skill must document validate_control_plan tool"
    assert "quality-mcp" in content, "control-plan skill must reference quality-mcp"
    assert "AIAG" in content, "control-plan skill must cite AIAG"
    assert "linkage" in content.lower() or "pfmea" in content.lower(), "control-plan skill must mention PFMEA linkage"
    assert "source_cause_id" in content or "orphan" in content, "control-plan skill must mention source_cause_id or orphan"


def test_claude_skills_isolation() -> None:
    """.claude/skills/ must remain segregated from domain skills/."""
    if not _CLAUDE_SKILLS_DIR.exists():
        pytest.skip(".claude/skills directory not present in CI / checkout")
    # Ensure domain skill directories are not inside .claude/skills
    claude_dirs = {d.name for d in _CLAUDE_SKILLS_DIR.iterdir() if d.is_dir()}
    assert "mcp-health" not in claude_dirs, "mcp-health domain skill leaked into .claude/skills/"
    assert "_template" not in claude_dirs, "_template domain skill leaked into .claude/skills/"
    assert "fmea-reviewer" not in claude_dirs, "fmea-reviewer domain skill leaked into .claude/skills/"
    assert "spc-control-charts" not in claude_dirs, "spc-control-charts domain skill leaked into .claude/skills/"
    assert "msa-gauge-rr" not in claude_dirs, "msa-gauge-rr domain skill leaked into .claude/skills/"
    assert "control-plan" not in claude_dirs, "control-plan domain skill leaked into .claude/skills/"


# ---------------------------------------------------------------------------
# Negative Control / Mutation Tests
# ---------------------------------------------------------------------------

def test_negative_missing_opening_frontmatter_fails() -> None:
    """Document without opening '---' must fail validation."""
    bad_md = "name: foo\ndescription: bar\n---\n## Overview\n"
    with pytest.raises(ValueError, match="does not begin with frontmatter delimiter"):
        validate_skill_document(bad_md)


def test_negative_missing_closing_frontmatter_fails() -> None:
    """Document without closing '---' must fail validation."""
    bad_md = "---\nname: foo\ndescription: bar\n## Overview\n"
    with pytest.raises(ValueError, match="Missing closing frontmatter delimiter"):
        validate_skill_document(bad_md)


def test_negative_missing_name_fails() -> None:
    """Frontmatter missing 'name' must fail validation."""
    bad_md = "---\ndescription: test\n---\n## Overview\n## When to Use\n## Step-by-Step Methodology\n## Tool Invocations\n## Best Practices\n"
    with pytest.raises(ValueError, match="missing or empty 'name'"):
        validate_skill_document(bad_md)


def test_negative_empty_name_fails() -> None:
    """Frontmatter with empty 'name' must fail validation."""
    bad_md = "---\nname: \ndescription: test\n---\n## Overview\n## When to Use\n## Step-by-Step Methodology\n## Tool Invocations\n## Best Practices\n"
    with pytest.raises(ValueError, match="missing or empty 'name'"):
        validate_skill_document(bad_md)


def test_negative_missing_description_fails() -> None:
    """Frontmatter missing 'description' must fail validation."""
    bad_md = "---\nname: test-skill\n---\n## Overview\n## When to Use\n## Step-by-Step Methodology\n## Tool Invocations\n## Best Practices\n"
    with pytest.raises(ValueError, match="missing or empty 'description'"):
        validate_skill_document(bad_md)


def test_negative_mismatched_directory_name_fails() -> None:
    """Frontmatter name not matching directory name must fail validation."""
    content = "---\nname: other-skill\ndescription: test\n---\n## Overview\n## When to Use\n## Step-by-Step Methodology\n## Tool Invocations\n## Best Practices\n"
    with pytest.raises(AssertionError, match="does not match directory name"):
        validate_skill_document(content, expected_dir_name="mcp-health")


def test_negative_missing_mandatory_sections_fails() -> None:
    """Missing any mandatory section must fail validation."""
    partial_md = "---\nname: test-skill\ndescription: test\n---\n## Overview\n## When to Use\n"
    with pytest.raises(ValueError, match="Missing mandatory section"):
        validate_skill_document(partial_md)


def test_negative_prohibited_inline_math_fails() -> None:
    """Inline Python calculation blocks bypassing MCP must fail validation."""
    bad_content = (
        "---\nname: math-skill\ndescription: test\n---\n"
        "## Overview\n## When to Use\n## Step-by-Step Methodology\n## Tool Invocations\n## Best Practices\n"
        "```python\nimport numpy as np\ndef calculate_ucl(data):\n    return np.mean(data) + 3\n```\n"
    )
    with pytest.raises(ValueError, match="Prohibited calculation logic found"):
        validate_skill_document(bad_content)

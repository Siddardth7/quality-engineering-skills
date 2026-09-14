"""Governance guard on the citation gate wiring in .github/workflows/ci.yml (#246).

CI runs the citation gate STRICT: it checks out the private manuals repo and exports every
`*_MANUAL_PATH`, and there is no `ALLOW_UNVERIFIED_CITATIONS` opt-out in the workflow. A
citation gate that never ran (fork PR with no secret, swallowed checkout failure) must not
read as green. This suite pins that contract so re-adding the opt-out, deleting the fetch
step, or making it swallow failures fails CI loudly.

Negative-control note (#246): re-adding `ALLOW_UNVERIFIED_CITATIONS: "1"` to the gate step,
or deleting the `Fetch licensed reference manuals` step, must fail one of these tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The 12 licensed-manual env vars CI must export (COPQ_LUMAFIELD is deliberately NOT
# exported: no manifest row cites it and require_manual returns once one usable .md is
# present, so its absence counts toward neither summary bucket).
_EXPECTED_MANUAL_VARS = (
    "MSA_MANUAL_PATH",
    "FMEA_MANUAL_PATH",
    "PPAP_MANUAL_PATH",
    "ISHIKAWA_MANUAL_PATH",
    "ASQ_MANUAL_PATH",
    "CQI20_MANUAL_PATH",
    "KT_MANUAL_PATH",
    "FORD_8D_MANUAL_PATH",
    "ISO_9001_MANUAL_PATH",
    "IATF_16949_MANUAL_PATH",
    "COPQ_ASQ_CSSGB_MANUAL_PATH",
    "COPQ_CSSC_MANUAL_PATH",
)


def _ci_text() -> str:
    """ci.yml with YAML comments stripped.

    The workflow's own explanatory comments name `ALLOW_UNVERIFIED_CITATIONS` and
    `continue-on-error` in prose ("there is no ... opt-out", "do not add continue-on-error").
    A raw substring check is defeated by that prose. Stripping everything from an unquoted
    `#` to end of line leaves only executable YAML, so these tests bite on a real re-addition
    (a `key:` in an env block is not a comment) but not on the guidance describing it.
    """
    assert _CI_YML.is_file(), f"ci.yml not found at {_CI_YML}"
    lines = _CI_YML.read_text(encoding="utf-8").splitlines()
    stripped = [line.split("#", 1)[0] for line in lines]
    return "\n".join(stripped)


def test_no_allow_unverified_citations_opt_out() -> None:
    """The strict-mode opt-out must not appear anywhere in the workflow (#246)."""
    assert "ALLOW_UNVERIFIED_CITATIONS" not in _ci_text(), (
        "ALLOW_UNVERIFIED_CITATIONS must not be set in ci.yml — CI runs the citation gate "
        "strict; re-adding it silences the gate."
    )


def test_fetch_manuals_step_present() -> None:
    """The step that mounts the licensed manuals must exist, else the gate cannot run strict."""
    assert "Fetch licensed reference manuals" in _ci_text(), (
        "The 'Fetch licensed reference manuals' step must be present; without it strict CI "
        "would fail with missing-config for every domain."
    )


def test_fetch_step_does_not_swallow_failure() -> None:
    """No continue-on-error anywhere in the workflow — a swallowed checkout must fail the job."""
    assert "continue-on-error" not in _ci_text(), (
        "continue-on-error must not appear in ci.yml: a fork PR with no MANUALS_REPO_TOKEN "
        "must fail the fetch step, not skip past it."
    )


@pytest.mark.parametrize("var", _EXPECTED_MANUAL_VARS)
def test_all_twelve_manual_paths_exported(var: str) -> None:
    """Each of the 12 licensed-manual paths must be exported to $GITHUB_ENV."""
    text = _ci_text()
    assert f"{var}=" in text, f"{var} is not exported in ci.yml's manual-path step."
    # And it must be routed into the gate step via $GITHUB_ENV, not just mentioned.
    assert "$GITHUB_ENV" in text, "manual paths must be written to $GITHUB_ENV for the gate step."

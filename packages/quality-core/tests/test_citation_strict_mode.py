"""Anti-vacuity guards for the citation gate itself (#241, #220, #221).

`test_citation_coverage.py` already asserts that every manifest *has* a verifying test. This
module asserts the next thing down: that a verifying test which *can* run actually runs, and
that it can only be prevented from running by a real, reported condition.

Two guards, both structural (no recursive pytest run):

1. For every domain whose declared manual is genuinely present and line-matchable, the shared
   `require_manual` guard returns normally — i.e. that domain contributes zero skips. Reverting
   `require_manual` to an unconditional `pytest.skip` flips this to a failure.
2. No citation module may skip by any *other* route — no bare `pytest.skip(...)`, no
   `@pytest.mark.skip`/`skipif` — so the guard above cannot be bypassed, and no module may
   reintroduce a hardcoded per-machine manual path (the original vacuity: the suite was green
   only on the author's laptop).

COPQ needs no explicit exemption: its declared manuals are PDFs, so it never has a
"present and line-matchable" manual and guard 1 simply does not apply to it. That is the
documented structural gap, reported in its own bucket by the session summary.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import _citation_audit as ca
import pytest

# module name -> attribute holding its declared manual(s). Importing the domain module's own
# names (rather than re-deriving paths here) is what keeps this guard honest: it resolves
# exactly what the domain resolves.
CITATION_DOMAINS: dict[str, str] = {
    "test_controlplan_citations": "MANUAL",
    "test_msa_citations": "MANUAL",
    "test_ppap_citations": "MANUAL",
    "test_rca_citations": "MANUAL_PATHS",
    "test_ncr_citations": "MANUAL_PATHS",
    "test_sqe_scar_citations": "MANUAL_PATHS",
    "test_copq_citations": "MANUAL_PATHS",
}

_TESTS_DIR = Path(__file__).resolve().parent


def _declared_manuals(module_name: str, attr: str) -> dict[str, Path]:
    """The manuals a domain module declares, as `{name: path}`."""
    declared = getattr(importlib.import_module(module_name), attr)
    return declared if isinstance(declared, dict) else {module_name: declared}


@pytest.mark.parametrize(("module_name", "attr"), sorted(CITATION_DOMAINS.items()))
def test_present_manual_means_zero_skips(module_name: str, attr: str) -> None:
    """A domain whose manual is present and non-PDF must not skip its citation checks."""
    manuals = _declared_manuals(module_name, attr)
    for name, path in ca.usable_manuals(manuals).items():
        try:
            ca.require_manual(name, path)
        except (pytest.skip.Exception, pytest.fail.Exception) as exc:
            raise AssertionError(
                f"{module_name}: {name} is present at {path} but the citation guard still "
                f"refused to verify it — its rows would be silently unverified. {exc}"
            ) from exc


def _citation_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in _TESTS_DIR.glob("test_*citations*.py")}


def test_no_citation_module_skips_outside_the_shared_guard() -> None:
    """Every "manual missing" decision routes through `require_manual`, so strict mode holds."""
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, source in _citation_sources().items()
        for number, line in enumerate(source.splitlines(), start=1)
        if "pytest.skip(" in line or "pytest.mark.skip" in line
    ]
    assert not offenders, (
        "citation modules must not skip outside `_citation_audit.require_manual` — a local "
        "skip bypasses strict mode and re-opens #241:\n" + "\n".join(f"  {o}" for o in offenders)
    )


def test_no_hardcoded_machine_paths() -> None:
    """No citation module may fall back to a per-machine manual path (#241 item 2).

    A hardcoded default makes the gate vacuous: it verifies on exactly one laptop and
    silently skips everywhere else. Paths come from `*_MANUAL_PATH` env vars only.
    """
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, source in _citation_sources().items()
        for number, line in enumerate(source.splitlines(), start=1)
        if "/Users/" in line or "/home/" in line
    ]
    assert not offenders, (
        "hardcoded machine paths in citation modules — resolve manuals from *_MANUAL_PATH "
        "env vars (see .env.example) instead:\n" + "\n".join(f"  {o}" for o in offenders)
    )


def test_the_two_skip_buckets_are_distinguishable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SME ruling (#241): a PDF-only row must never look like a forgotten `*_MANUAL_PATH`.

    "Structurally unverifiable" is a documented, unfixable gap; "missing config" is an
    operator mistake someone can go and fix. Collapsing them re-hides the second inside
    the first. The session summary keys off these two markers, so they must stay distinct
    and must never both appear on one skip.
    """
    assert ca.PDF_ONLY_SKIP_MARKER != ca.MISSING_MANUAL_SKIP_MARKER

    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4 binary noise, not line-matchable")
    with pytest.raises(pytest.skip.Exception) as pdf_skip:
        ca.require_manual("COPQ-LIKE", {"PDF": pdf}, allow_pdf_only_skip=True)
    assert ca.PDF_ONLY_SKIP_MARKER in str(pdf_skip.value)
    assert ca.MISSING_MANUAL_SKIP_MARKER not in str(pdf_skip.value)

    monkeypatch.setenv(ca.ALLOW_UNVERIFIED_CITATIONS_ENV, "1")
    with pytest.raises(pytest.skip.Exception) as missing_skip:
        ca.require_manual("ABSENT", {"GONE": Path("/nonexistent/manual.md")})
    assert ca.MISSING_MANUAL_SKIP_MARKER in str(missing_skip.value)
    assert ca.PDF_ONLY_SKIP_MARKER not in str(missing_skip.value)


class _FakeReport:
    """Minimal stand-in for a pytest TestReport, shaped for the conftest summary hook."""

    def __init__(self, nodeid: str, reason: str = "", when: str = "call") -> None:
        self.nodeid = nodeid
        self.longrepr = ("f.py", 1, reason)
        self.when = when


class _FakeTerminalReporter:
    def __init__(self, stats: dict[str, list[_FakeReport]]) -> None:
        self.stats = stats
        self.lines: list[str] = []

    def write_line(self, line: str) -> None:
        self.lines.append(line)


def test_session_summary_reports_the_two_buckets_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SME ruling (#241): the summary must print PDF-only and missing-config as SEPARATE,
    separately-labelled counts.

    Behavioural, not a source grep: an earlier version of this guard scanned conftest.py for
    the label text and was defeated by the phrase surviving in a comment while the emitted
    line was collapsed -- the same under-matching failure CLAUDE.md warns about. This drives
    the real hook and reads what it actually prints.
    """
    spec = importlib.util.spec_from_file_location(
        "_citation_conftest_under_test", Path(__file__).parent / "conftest.py"
    )
    assert spec is not None and spec.loader is not None
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)

    node = "packages/quality-core/tests/test_copq_citations.py::test_row"
    reporter = _FakeTerminalReporter(
        {
            "passed": [_FakeReport(node)],
            "skipped": [
                _FakeReport(node, ca.PDF_ONLY_SKIP_MARKER),
                _FakeReport(node, ca.PDF_ONLY_SKIP_MARKER),
                _FakeReport(node, ca.MISSING_MANUAL_SKIP_MARKER),
            ],
        }
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    conftest.pytest_terminal_summary(reporter)

    out = "\n".join(reporter.lines)
    assert "structurally unverifiable (PDF-only): 2" in out, out
    assert "missing config (*_MANUAL_PATH unset or wrong): 1" in out, out
    assert "unclassified skips" not in out, out

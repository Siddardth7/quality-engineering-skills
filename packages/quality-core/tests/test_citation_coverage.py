"""Package-wide citation-coverage meta-test — the anti-vacuity guard (#140).

At v1.0.0 every `quality_core` module must carry a machine-checkable citation trail *or* an
explicit declaration that no published standard applies. This test enforces that contract
across the whole package so a module can never pass by vacuity — an empty (or absent)
`CITATIONS.tsv` with no logged declaration fails here, and a manifest with real rows but no
verifying `test_*_citations.py` fails here.

Two machine-detectable declaration tokens are recognised in an ASSUMPTIONS_LOG.md whose
manifest is empty/absent:

- ``NO-STANDARD-DECLARATION`` — no published standard governs the module (io, schema,
  canvas, theme).
- ``PROCUREMENT-GAP`` — a named standard applies but its on-machine excerpt is not yet
  procured, so verifiable rows are deferred and tracked (scoring, spc).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _citation_audit import QUALITY_CORE_SRC, load_citations

DECLARATION_TOKENS = ("NO-STANDARD-DECLARATION", "PROCUREMENT-GAP")


def _engine_dirs() -> list[Path]:
    """Every immediate subpackage of quality_core that holds engine source."""
    dirs: list[Path] = []
    for child in sorted(QUALITY_CORE_SRC.iterdir()):
        if not child.is_dir() or child.name == "__pycache__":
            continue
        if any(p.name != "__init__.py" for p in child.glob("*.py")):
            dirs.append(child)
    return dirs


def _citation_test_corpus() -> str:
    """Concatenated text of every citation test module (to check a manifest is verified)."""
    tests_dir = Path(__file__).resolve().parent
    parts = [
        p.read_text(encoding="utf-8")
        for p in tests_dir.glob("test_*citation*.py")
    ]
    return "\n".join(parts)


# (log_path, manifest_path, module_token) for every module that must be covered, including
# the co-located single-module `scoring` engine.
def _audit_targets() -> list[tuple[Path, Path, str]]:
    targets: list[tuple[Path, Path, str]] = []
    for d in _engine_dirs():
        targets.append((d / "ASSUMPTIONS_LOG.md", d / "CITATIONS.tsv", d.name))
    targets.append(
        (
            QUALITY_CORE_SRC / "scoring_ASSUMPTIONS_LOG.md",
            QUALITY_CORE_SRC / "scoring_CITATIONS.tsv",
            "scoring",
        )
    )
    return targets


AUDIT_TARGETS = _audit_targets()
CITATION_CORPUS = _citation_test_corpus()


@pytest.mark.parametrize(
    ("log_path", "manifest_path", "token"),
    AUDIT_TARGETS,
    ids=[t[2] for t in AUDIT_TARGETS],
)
def test_every_module_has_log(log_path: Path, manifest_path: Path, token: str) -> None:
    """Every engine module (and the co-located scoring engine) carries an ASSUMPTIONS_LOG.md."""
    assert log_path.exists(), (
        f"{token}: missing ASSUMPTIONS_LOG.md at {log_path}. Every quality_core module must "
        "carry an assumptions log or an explicit no-standard declaration (#140)."
    )


@pytest.mark.parametrize(
    ("log_path", "manifest_path", "token"),
    AUDIT_TARGETS,
    ids=[t[2] for t in AUDIT_TARGETS],
)
def test_manifest_is_verified_or_declared(
    log_path: Path, manifest_path: Path, token: str
) -> None:
    """A manifest with rows must have a verifying test; an empty one must be declared.

    This is the anti-vacuity core: an empty/absent CITATIONS.tsv with no logged declaration
    can no longer pass silently.
    """
    rows = load_citations(manifest_path)
    if rows:
        assert token in CITATION_CORPUS, (
            f"{token}: {manifest_path.name} has {len(rows)} citation row(s) but no "
            f"test_*_citations.py references it — its manifest would be unverified."
        )
    else:
        log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        assert any(tok in log_text for tok in DECLARATION_TOKENS), (
            f"{token}: {manifest_path.name} is empty/absent, so {log_path.name} MUST carry an "
            f"explicit declaration ({' or '.join(DECLARATION_TOKENS)}). Silent vacuity is not "
            "permitted at v1.0.0 (#140)."
        )


def test_no_manifest_with_rows_is_unverified() -> None:
    """Global sweep: every CITATIONS.tsv anywhere with rows is referenced by a citation test."""
    unverified: list[str] = []
    for manifest in QUALITY_CORE_SRC.rglob("*CITATIONS.tsv"):
        rows = load_citations(manifest)
        if not rows:
            continue
        # module token = parent dir name, or 'scoring' for the co-located manifest
        token = "scoring" if manifest.name.startswith("scoring") else manifest.parent.name
        if token not in CITATION_CORPUS:
            unverified.append(f"{token} ({manifest})")
    assert not unverified, (
        "CITATIONS.tsv manifests with rows but no verifying test_*_citations.py:\n"
        + "\n".join(f"  {u}" for u in unverified)
    )

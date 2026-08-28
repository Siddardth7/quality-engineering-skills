"""Guard the quality-core version single-source-of-truth against drift."""

import tomllib
from pathlib import Path

from quality_core import __version__


def test_version_ssot_matches_pyproject() -> None:
    """quality_core.__version__ must equal '0.8.0' and match pyproject.toml."""
    assert __version__ == "0.8.0"
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert __version__ == data["project"]["version"]

"""Workspace-root pytest plugin: load `.env` into the environment before collection.

The citation gate resolves each licensed manual from a `*_MANUAL_PATH` env var and, since
#241, has no per-machine default — so an operator who filled in `.env` but forgot
`set -a; source .env; set +a` would see every citation test FAIL rather than verify. Loading
`.env` here removes that footgun.

Why `pytest_configure` and not a fixture: several citation modules read `os.environ` at
*import* time (module-scope `MANUAL = Path(os.environ.get(...))`), which happens during
collection — after `pytest_configure`, before any fixture runs.

Real shell environment always wins: `.env` values are applied with `setdefault`, so an
explicitly exported variable (or CI's `env:` block) is never overwritten by a stale `.env`.
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path

import pytest

DOTENV_PATH = Path(__file__).resolve().parent / ".env"


def load_dotenv(env: MutableMapping[str, str], dotenv_path: Path) -> None:
    """Merge `KEY=VALUE` lines from `dotenv_path` into `env` without overwriting anything.

    ponytail: a deliberately minimal parser — this repo's `.env` is unquoted `KEY=VALUE`
    lines, `#` comments (whole-line and trailing, as `.env.example` uses on `SLACK_IDENTITY`)
    and blanks. Quoting, `export ` prefixes and multi-line values are NOT supported, because
    half-supporting them silently does the wrong thing. If `.env` ever needs that syntax, add
    the parsing then, with a test — not a dependency.
    """
    if not dotenv_path.is_file():
        return
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0]  # trailing comment: only when whitespace-separated
        env.setdefault(key.strip(), value.strip())


def pytest_configure(config: pytest.Config) -> None:
    """Load the repo-root `.env` once per session, before collection imports anything."""
    load_dotenv(os.environ, DOTENV_PATH)

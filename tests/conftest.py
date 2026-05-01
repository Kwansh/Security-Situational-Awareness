"""Test fixtures for sandbox-safe temporary directories."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path() -> Path:
    """Provide a writable temporary path inside workspace.

    This avoids platform-specific permission issues with system temp paths
    in restricted execution environments.
    """

    base = Path('.test_runs') / 'pytest_workspace_tmp'
    base.mkdir(parents=True, exist_ok=True)

    path = base / f'tmp_{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

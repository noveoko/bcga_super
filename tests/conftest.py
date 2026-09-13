import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "streamlit_app"))

# Re-export for tests that prefer importing from conftest/helpers.
from helpers import DummyOperatorParent, install_dummy_operator  # noqa: E402,F401


@pytest.fixture
def blender_executable():
    """Path to a `blender` executable, or None if not on PATH -- tests
    marked @pytest.mark.integration should skip rather than fail when
    this is unavailable (see tests/test_city_builder.py)."""
    return shutil.which("blender")


@pytest.fixture
def repo_root():
    """Absolute path to the repository root (tests/ is directly under it)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
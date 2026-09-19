"""Pytest configuration and fixtures for ExamSplit AI."""

import pytest
from pathlib import Path
import tempfile
import os

# Set Qt platform to offscreen for headless automated testing in WSL/CI
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary SQLite database path."""
    return tmp_path / "test_exam_split.db"

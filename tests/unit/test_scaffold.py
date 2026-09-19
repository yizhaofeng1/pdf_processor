"""Unit tests for project scaffold, configuration, and database schema."""

from pathlib import Path
from app.config import (
    BASE_DIR,
    DATA_DIR,
    CACHE_DIR,
    THUMBNAILS_DIR,
    PROJECTS_DIR,
    SCHEMAS_DIR,
    PROMPTS_DIR,
    ensure_data_directories,
)
from app.storage.database import init_db, get_db_connection


def test_directory_configuration():
    """Verify standard directories can be ensured and located."""
    ensure_data_directories()
    assert BASE_DIR.exists()
    assert DATA_DIR.exists()
    assert CACHE_DIR.exists()
    assert THUMBNAILS_DIR.exists()
    assert PROJECTS_DIR.exists()
    assert SCHEMAS_DIR.exists()
    assert PROMPTS_DIR.exists()


def test_database_initialization(temp_db: Path):
    """Verify SQLite database schema initializes all required tables."""
    init_db(temp_db)
    assert temp_db.exists()

    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {"projects", "pages", "questions", "question_segments", "ai_runs"}
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

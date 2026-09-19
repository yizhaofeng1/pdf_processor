"""SQLite Database connection and schema management."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from ..config import DEFAULT_DB_PATH, ensure_data_directories

INIT_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_pdf TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    page_index INTEGER NOT NULL,
    width REAL NOT NULL,
    height REAL NOT NULL,
    page_type TEXT,
    thumbnail_path TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    display_number TEXT NOT NULL,
    original_display_number TEXT,
    question_type TEXT,
    source_pdf_path TEXT,
    source_paper_title TEXT,
    confidence REAL NOT NULL,
    review_required INTEGER NOT NULL DEFAULT 0,
    selected INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    user_modified INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_segments (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    page_index INTEGER NOT NULL,
    x1 REAL NOT NULL,
    y1 REAL NOT NULL,
    x2 REAL NOT NULL,
    y2 REAL NOT NULL,
    user_modified INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT,
    input_hash TEXT,
    raw_response_path TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pages_project ON pages(project_id);
CREATE INDEX IF NOT EXISTS idx_questions_project ON questions(project_id);
CREATE INDEX IF NOT EXISTS idx_segments_question ON question_segments(question_id);
"""


@contextmanager
def get_db_connection(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional SQLite database connection."""
    ensure_data_directories()
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Migrate database schema for backwards compatibility."""
    cursor = conn.execute("PRAGMA table_info(questions)")
    existing_cols = {row["name"] for row in cursor.fetchall()}

    if "source_pdf_path" not in existing_cols:
        conn.execute("ALTER TABLE questions ADD COLUMN source_pdf_path TEXT")
    if "source_paper_title" not in existing_cols:
        conn.execute("ALTER TABLE questions ADD COLUMN source_paper_title TEXT")
    if "original_display_number" not in existing_cols:
        conn.execute("ALTER TABLE questions ADD COLUMN original_display_number TEXT")


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize database tables according to ExamSplit specification."""
    with get_db_connection(db_path) as conn:
        conn.executescript(INIT_SCHEMA_SQL)
        _migrate_db(conn)


def save_project_questions(
    project_id: str,
    questions: list,
    db_path: Path | str | None = None,
) -> None:
    """Persist analyzed questions and their segments to the database."""
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO projects (id, name, source_pdf, source_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (project_id, project_id, "", ""),
        )
        conn.execute("DELETE FROM questions WHERE project_id = ?", (project_id,))
        for q in questions:
            q_type_str = q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type or "")
            conn.execute(
                """
                INSERT INTO questions (
                    id, project_id, display_number, original_display_number, question_type,
                    source_pdf_path, source_paper_title, confidence, review_required,
                    selected, sort_order, user_modified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q.id,
                    project_id,
                    q.display_number,
                    q.original_display_number,
                    q_type_str,
                    q.source_pdf_path,
                    q.source_paper_title,
                    q.confidence,
                    1 if q.review_required else 0,
                    1 if q.selected else 0,
                    q.sort_order,
                    1 if q.user_modified else 0,
                ),
            )
            for seg in q.segments:
                conn.execute(
                    """
                    INSERT INTO question_segments (id, question_id, page_index, x1, y1, x2, y2, user_modified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        seg.id,
                        q.id,
                        seg.page_index,
                        seg.normalized_bbox[0],
                        seg.normalized_bbox[1],
                        seg.normalized_bbox[2],
                        seg.normalized_bbox[3],
                        1 if seg.user_modified else 0,
                    ),
                )


def load_project_questions(
    project_id: str,
    db_path: Path | str | None = None,
) -> list:
    """Load questions and associated segments from the database."""
    from ..models.question import Question, QuestionType
    from ..models.segment import QuestionSegment

    init_db(db_path)
    with get_db_connection(db_path) as conn:
        q_rows = conn.execute(
            "SELECT * FROM questions WHERE project_id = ? ORDER BY sort_order ASC",
            (project_id,),
        ).fetchall()
        questions = []
        for q_row in q_rows:
            q_id = q_row["id"]
            seg_rows = conn.execute(
                "SELECT * FROM question_segments WHERE question_id = ? ORDER BY page_index ASC, y1 ASC",
                (q_id,),
            ).fetchall()
            segments = [
                QuestionSegment(
                    id=s["id"],
                    question_id=q_id,
                    page_index=s["page_index"],
                    normalized_bbox=(s["x1"], s["y1"], s["x2"], s["y2"]),
                    user_modified=bool(s["user_modified"]),
                )
                for s in seg_rows
            ]
            
            keys = q_row.keys()
            q = Question(
                id=q_id,
                project_id=project_id,
                display_number=q_row["display_number"],
                original_display_number=q_row["original_display_number"] if "original_display_number" in keys else None,
                question_type=q_row["question_type"],
                source_pdf_path=q_row["source_pdf_path"] if "source_pdf_path" in keys else None,
                source_paper_title=q_row["source_paper_title"] if "source_paper_title" in keys else None,
                segments=segments,
                confidence=float(q_row["confidence"]),
                review_required=bool(q_row["review_required"]),
                selected=bool(q_row["selected"]),
                sort_order=q_row["sort_order"],
                user_modified=bool(q_row["user_modified"]),
                continuation=len(segments) > 1,
            )
            questions.append(q)
        return questions


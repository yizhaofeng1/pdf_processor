"""Unit tests for HomeView and MainWindow view switching."""

from pathlib import Path
from PySide6.QtCore import Qt

from app.ui.home_view import HomeView, DropZoneFrame
from app.ui.main_window import MainWindow
from app.storage.recent_files import get_recent_files, add_recent_file, clear_recent_files

TEST_PDF = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"


def test_home_view_initialization(qtbot):
    """Verify HomeView initializes all buttons, dropzone, and recent list."""
    home = HomeView()
    qtbot.addWidget(home)

    assert home.drop_zone is not None
    assert home.drop_zone.btn_browse is not None
    assert home.recent_list_widget is not None


def test_recent_files_tracker(tmp_path: Path, monkeypatch):
    """Verify adding, sorting, and deduplicating recent files with isolated test path."""
    test_recent_path = tmp_path / "recent_files.json"
    monkeypatch.setattr("app.storage.recent_files.RECENT_FILES_PATH", test_recent_path)

    f1 = tmp_path / "test1.pdf"
    f2 = tmp_path / "test2.pdf"
    f1.touch()
    f2.touch()

    add_recent_file(f1, page_count=5)
    add_recent_file(f2, page_count=10)

    recents = get_recent_files()
    assert len(recents) == 2
    assert recents[0]["file_path"] == str(f2.resolve())
    assert recents[0]["file_name"] == "test2.pdf"
    assert recents[0]["page_count"] == 10

    # Re-adding f1 moves it to front
    add_recent_file(f1)
    recents_updated = get_recent_files()
    assert recents_updated[0]["file_path"] == str(f1.resolve())
    assert recents_updated[0]["page_count"] == 5


def test_main_window_home_to_workbench_flow(qtbot):
    """Verify launching app without args shows HomeView, loading PDF switches to Workbench."""
    # 1. Start on Home
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.stack.currentIndex() == 0
    assert window.pdf_reader is None
    assert "欢迎使用 ExamSplit AI" in window.status_file_label.text()

    # 2. Open PDF -> Transitions to Workbench
    assert TEST_PDF.exists()
    success = window.load_pdf(TEST_PDF)
    assert success is True
    assert window.stack.currentIndex() == 1
    assert window.pdf_reader is not None
    assert window.pdf_reader.page_count == 8

    # 3. Close PDF -> Returns to Home
    window.close_pdf()
    assert window.stack.currentIndex() == 0
    assert window.pdf_reader is None

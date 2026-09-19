"""Unit tests for PySide6 main window scaffold."""

from app.ui.main_window import MainWindow


def test_main_window_creation(qtbot):
    """Verify MainWindow initializes cleanly with all panels and buttons."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert "ExamSplit AI" in window.windowTitle()
    assert window.question_list_widget is not None
    assert window.btn_select_all is not None
    assert window.btn_invert_select is not None
    assert window.btn_export is not None
    assert "已识别 0 题" in window.status_counts_label.text()

"""Integration test for MainWindow loading a PDF file."""

from pathlib import Path
from app.ui.main_window import MainWindow

TEST_PDF = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"


def test_main_window_loads_pdf(qtbot):
    """Verify MainWindow loads PDF directly via constructor and updates all status displays."""
    window = MainWindow(initial_pdf=TEST_PDF)
    qtbot.addWidget(window)

    assert "2010_math_test.pdf" in window.windowTitle()
    assert "共 8 页" in window.windowTitle()
    assert "已加载: 2010_math_test.pdf" in window.status_file_label.text()
    assert window.action_run_analysis.isEnabled() is True
    assert window.pdf_viewer._page_count == 8
    assert window.pdf_viewer.spin_page.value() == 1

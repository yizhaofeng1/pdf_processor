"""Unit tests for PDFViewerWidget navigation and zoom controls."""

from pathlib import Path
from PySide6.QtCore import Qt

from app.pdf.reader import PDFReader
from app.ui.pdf_viewer import PDFViewerWidget

TEST_PDF = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"


def test_pdf_viewer_lifecycle(qtbot):
    """Verify viewer initializes, loads reader, flips pages, and adjusts zoom."""
    viewer = PDFViewerWidget()
    qtbot.addWidget(viewer)

    # Initial empty state
    assert viewer.btn_prev.isEnabled() is False
    assert viewer.btn_next.isEnabled() is False
    assert "/ 0 页" in viewer.lbl_page_total.text()

    # Load test PDF
    with PDFReader(TEST_PDF) as reader:
        viewer.set_pdf_reader(reader)

        assert viewer._page_count == 8
        assert "/ 8 页" in viewer.lbl_page_total.text()
        assert viewer.spin_page.value() == 1
        assert viewer.btn_prev.isEnabled() is False
        assert viewer.btn_next.isEnabled() is True

        # Next page navigation
        viewer.next_page()
        assert viewer._current_page_idx == 1
        assert viewer.spin_page.value() == 2
        assert viewer.btn_prev.isEnabled() is True

        # Previous page navigation
        viewer.prev_page()
        assert viewer._current_page_idx == 0
        assert viewer.spin_page.value() == 1

        # Zoom controls
        initial_zoom = viewer.view.current_zoom
        viewer.view.apply_zoom_multiplier(1.25)
        assert viewer.view.current_zoom > initial_zoom

        viewer.view.set_zoom(1.0)
        assert viewer.view.current_zoom == 1.0
        assert viewer.lbl_zoom.text() == "100%"

        # Direct page spinbox change
        viewer.spin_page.setValue(5)
        assert viewer._current_page_idx == 4

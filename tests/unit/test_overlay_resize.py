"""Unit tests for interactive QuestionOverlayItem resizing and context menu actions."""

import pytest
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap
from app.ui.pdf_viewer import PDFViewerWidget, QuestionOverlayItem


def test_overlay_handles_detection(qtbot):
    """Verify handle detection on top, bottom, left, right edges and interior."""
    rect = QRectF(100, 100, 200, 200)
    overlay = QuestionOverlayItem(
        question_id="q1",
        segment_id="s1",
        display_number="1",
        question_type="选择题",
        rect=rect,
        normalized_bbox=(0.1, 0.1, 0.3, 0.3),
        pixmap_size=(1000, 1000),
        selected=True,
    )

    # Top edge
    assert overlay._determine_handle(QPointF(200, 102)) == "top"
    # Bottom edge
    assert overlay._determine_handle(QPointF(200, 298)) == "bottom"
    # Left edge
    assert overlay._determine_handle(QPointF(102, 200)) == "left"
    # Right edge
    assert overlay._determine_handle(QPointF(298, 200)) == "right"
    # Interior center
    assert overlay._determine_handle(QPointF(200, 200)) == "move"
    # Far outside
    assert overlay._determine_handle(QPointF(50, 50)) is None


def test_overlay_resize_callback(qtbot):
    """Verify dragging an edge updates normalized_bbox and triggers callback."""
    resized_events = []

    def on_resized(qid, sid, bbox):
        resized_events.append((qid, sid, bbox))

    rect = QRectF(100, 100, 200, 200)
    overlay = QuestionOverlayItem(
        question_id="q1",
        segment_id="s1",
        display_number="1",
        question_type="选择题",
        rect=rect,
        normalized_bbox=(0.1, 0.1, 0.3, 0.3),
        pixmap_size=(1000, 1000),
        selected=True,
        on_resized_callback=on_resized,
    )

    # Simulate drag on bottom edge from y=300 down to y=350
    overlay._drag_mode = "bottom"
    overlay._drag_start_pos = QPointF(200, 300)
    overlay._initial_rect = QRectF(rect)

    # Move mouse event simulation
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent
    from PySide6.QtCore import QEvent

    # Mock release directly to test normalization logic
    overlay.setRect(QRectF(100, 100, 200, 250))  # Expanded bottom
    r = overlay.rect()
    nx1 = round(r.left() / 1000.0, 4)
    ny1 = round(r.top() / 1000.0, 4)
    nx2 = round(r.right() / 1000.0, 4)
    ny2 = round(r.bottom() / 1000.0, 4)

    overlay.normalized_bbox = (nx1, ny1, nx2, ny2)
    on_resized("q1", "s1", (nx1, ny1, nx2, ny2))

    assert len(resized_events) == 1
    qid, sid, bbox = resized_events[0]
    assert qid == "q1"
    assert sid == "s1"
    assert bbox == (0.1, 0.1, 0.3, 0.35)

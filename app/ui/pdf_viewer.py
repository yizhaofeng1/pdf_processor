"""Interactive PDF Viewer widget based on QGraphicsView with question bounding box overlays and interactive resizing."""

from typing import Optional, List, Dict, Any, Callable
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QFrame,
    QSizePolicy,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QPixmap,
    QWheelEvent,
    QPainter,
    QKeyEvent,
    QPen,
    QBrush,
    QColor,
    QFont,
    QAction,
)

from ..pdf.reader import PDFReader
from ..pdf.renderer import PDFRenderer


class QuestionOverlayItem(QGraphicsRectItem):
    """Interactive visual highlight box for a question segment with edge resize handles."""

    HANDLE_MARGIN = 10  # Sensitive zone for edge drag

    def __init__(
        self,
        question_id: str,
        segment_id: str,
        display_number: str,
        question_type: str,
        rect: QRectF,
        normalized_bbox: tuple[float, float, float, float],
        pixmap_size: tuple[float, float],
        review_required: bool = False,
        selected: bool = False,
        on_clicked_callback: Optional[Callable[[str], None]] = None,
        on_resized_callback: Optional[Callable[[str, str, tuple], None]] = None,
        on_context_action_callback: Optional[Callable[[str, str], None]] = None,
        parent=None,
    ) -> None:
        super().__init__(rect, parent)
        self.question_id = question_id
        self.segment_id = segment_id
        self.display_number = display_number
        self.question_type = question_type
        self.normalized_bbox = normalized_bbox
        self.pw, self.ph = max(1.0, pixmap_size[0]), max(1.0, pixmap_size[1])
        self.review_required = review_required
        self.is_selected = selected
        self.on_clicked_callback = on_clicked_callback
        self.on_resized_callback = on_resized_callback
        self.on_context_action_callback = on_context_action_callback
        self.is_hovered = False

        self._drag_mode: Optional[str] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._initial_rect: Optional[QRectF] = None

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self._update_style()
        self.update()

    def _update_style(self) -> None:
        if self.is_selected:
            pen = QPen(QColor("#38BDF8"), 3, Qt.PenStyle.SolidLine)
            brush = QBrush(QColor(56, 189, 248, 55))
        elif self.review_required:
            pen = QPen(QColor("#F97316"), 2.5, Qt.PenStyle.DashLine)
            brush = QBrush(QColor(249, 115, 22, 45))
        elif self.is_hovered:
            pen = QPen(QColor("#38BDF8"), 2.5, Qt.PenStyle.SolidLine)
            brush = QBrush(QColor(56, 189, 248, 45))
        else:
            pen = QPen(QColor("#0284C7"), 2, Qt.PenStyle.SolidLine)
            brush = QBrush(QColor(2, 132, 199, 35))

        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(brush)

    def _determine_handle(self, pos: QPointF) -> Optional[str]:
        """Detect which edge/handle the mouse is currently positioned over."""
        r = self.rect()
        m = self.HANDLE_MARGIN

        on_top = abs(pos.y() - r.top()) <= m
        on_bottom = abs(pos.y() - r.bottom()) <= m
        on_left = abs(pos.x() - r.left()) <= m
        on_right = abs(pos.x() - r.right()) <= m

        if on_top and (r.left() - m <= pos.x() <= r.right() + m):
            return "top"
        if on_bottom and (r.left() - m <= pos.x() <= r.right() + m):
            return "bottom"
        if on_left and (r.top() - m <= pos.y() <= r.bottom() + m):
            return "left"
        if on_right and (r.top() - m <= pos.y() <= r.bottom() + m):
            return "right"
        if r.contains(pos):
            return "move"
        return None

    def hoverMoveEvent(self, event) -> None:
        if self.is_selected:
            handle = self._determine_handle(event.pos())
            if handle in ("top", "bottom"):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif handle in ("left", "right"):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif handle == "move":
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverMoveEvent(event)

    def hoverEnterEvent(self, event) -> None:
        self.is_hovered = True
        self._update_style()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.is_hovered = False
        self._update_style()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_selected:
                if self.on_clicked_callback:
                    self.on_clicked_callback(self.question_id)
            else:
                handle = self._determine_handle(event.pos())
                if handle:
                    self._drag_mode = handle
                    self._drag_start_pos = event.scenePos()
                    self._initial_rect = QRectF(self.rect())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_mode and self._drag_start_pos and self._initial_rect:
            delta = event.scenePos() - self._drag_start_pos
            init = self._initial_rect
            new_r = QRectF(init)

            if self._drag_mode == "top":
                new_top = min(init.bottom() - 15, max(0.0, init.top() + delta.y()))
                new_r.setTop(new_top)
            elif self._drag_mode == "bottom":
                new_bot = max(init.top() + 15, min(self.ph, init.bottom() + delta.y()))
                new_r.setBottom(new_bot)
            elif self._drag_mode == "left":
                new_left = min(init.right() - 25, max(0.0, init.left() + delta.x()))
                new_r.setLeft(new_left)
            elif self._drag_mode == "right":
                new_right = max(init.left() + 25, min(self.pw, init.right() + delta.x()))
                new_r.setRight(new_right)
            elif self._drag_mode == "move":
                dx = delta.x()
                dy = delta.y()
                # Clamp within page bounds
                dx = max(-init.left(), min(self.pw - init.right(), dx))
                dy = max(-init.top(), min(self.ph - init.bottom(), dy))
                new_r.translate(dx, dy)

            self.setRect(new_r.normalized())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_mode:
            r = self.rect().normalized()
            nx1 = max(0.0, min(1.0, r.left() / self.pw))
            ny1 = max(0.0, min(1.0, r.top() / self.ph))
            nx2 = max(nx1 + 0.01, min(1.0, r.right() / self.pw))
            ny2 = max(ny1 + 0.01, min(1.0, r.bottom() / self.ph))

            new_bbox = (round(nx1, 4), round(ny1, 4), round(nx2, 4), round(ny2, 4))
            self.normalized_bbox = new_bbox

            if self.on_resized_callback:
                self.on_resized_callback(self.question_id, self.segment_id, new_bbox)

            self._drag_mode = None
            self._drag_start_pos = None
            self._initial_rect = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Show context menu for question actions on right click."""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0F172A;
                border: 1.5px solid #38BDF8;
                border-radius: 8px;
                padding: 6px;
                color: #F1F5F9;
            }
            QMenu::item {
                background-color: transparent;
                color: #F1F5F9;
                padding: 8px 24px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QMenu::item:selected {
                background-color: #1E293B;
                color: #38BDF8;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 8px;
            }
        """)

        act_confirm = menu.addAction("✓ 确认此题无误")
        act_merge = menu.addAction("🔗 与上一题合并为跨页题")
        menu.addSeparator()
        act_delete = menu.addAction("🗑️ 删除此题目选框")

        chosen = menu.exec(event.screenPos())
        if self.on_context_action_callback:
            if chosen == act_confirm:
                self.on_context_action_callback("confirm", self.question_id)
            elif chosen == act_merge:
                self.on_context_action_callback("merge", self.question_id)
            elif chosen == act_delete:
                self.on_context_action_callback("delete", self.question_id)

        event.accept()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        r = self.rect()

        # 1. Badge Pill with Question Number (generous font size for eye comfort)
        badge_text = f" 第 {self.display_number} 题 "
        if self.review_required:
            badge_text += " ⚠️待查 "

        font = QFont("Microsoft YaHei", 12, QFont.Weight.Bold)
        font.setFamilies(["Microsoft YaHei", "PingFang SC", "Noto Sans SC", "sans-serif"])
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(badge_text) + 16
        text_h = fm.height() + 8

        badge_rect = QRectF(r.left() + 3, r.top() + 3, text_w, text_h)
        badge_bg = QColor("#0284C7") if self.is_selected else (
            QColor("#EA580C") if self.review_required else QColor("#0369A1")
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(badge_bg))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # 2. Interactive Resize Grips when selected
        if self.is_selected:
            grip_pen = QPen(QColor("#2E7D32"), 1.5)
            grip_pen.setCosmetic(True)
            painter.setPen(grip_pen)
            painter.setBrush(QBrush(QColor("#FFFFFF")))

            # 4 Edge centers
            cx = r.center().x()
            cy = r.center().y()
            sz = 6.0

            painter.drawRect(QRectF(cx - sz / 2, r.top() - sz / 2, sz, sz))
            painter.drawRect(QRectF(cx - sz / 2, r.bottom() - sz / 2, sz, sz))
            painter.drawRect(QRectF(r.left() - sz / 2, cy - sz / 2, sz, sz))
            painter.drawRect(QRectF(r.right() - sz / 2, cy - sz / 2, sz, sz))


class PDFGraphicsView(QGraphicsView):
    """Subclassed QGraphicsView providing Ctrl+Wheel zoom and pan gestures."""

    zoom_changed = Signal(float)

    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._current_zoom: float = 1.0

    @property
    def current_zoom(self) -> float:
        return self._current_zoom

    def set_zoom(self, zoom_factor: float) -> None:
        zoom_factor = max(0.1, min(5.0, zoom_factor))
        self.resetTransform()
        self.scale(zoom_factor, zoom_factor)
        self._current_zoom = zoom_factor
        self.zoom_changed.emit(self._current_zoom)

    def apply_zoom_multiplier(self, multiplier: float) -> None:
        new_zoom = self._current_zoom * multiplier
        self.set_zoom(new_zoom)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.apply_zoom_multiplier(1.2)
            elif delta < 0:
                self.apply_zoom_multiplier(0.8)
            event.accept()
        else:
            super().wheelEvent(event)


class PDFViewerWidget(QWidget):
    """Full-featured PDF viewer with navigation bar, zoom controls, and interactive canvas."""

    page_changed = Signal(int)
    segment_selected = Signal(str)                          # Emits question_id when an overlay box is clicked
    segment_resized = Signal(str, str, tuple)               # (question_id, segment_id, new_normalized_bbox)
    context_action_triggered = Signal(str, str)             # (action_name, question_id)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._reader: Optional[PDFReader] = None
        self._current_page_idx: int = 0
        self._page_count: int = 0
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._segment_overlays: List[QuestionOverlayItem] = []
        self._current_selected_qid: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 1. Top Navigation & Zoom Toolbar
        toolbar = QWidget(self)
        toolbar.setStyleSheet("""
            QWidget {
                background-color: #0F172A;
                border-bottom: 1px solid #1E293B;
                padding: 6px 10px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)
        toolbar_layout.setSpacing(8)

        # Page controls
        self.btn_prev = QPushButton("◀ 上一页")
        self.btn_prev.setToolTip("快捷键: PageUp 或 左方向键")
        self.btn_prev.clicked.connect(self.prev_page)

        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.setValue(1)
        self.spin_page.setMinimumWidth(70)
        self.spin_page.valueChanged.connect(self._on_spin_page_changed)

        self.lbl_page_total = QLabel("/ 0 页")
        self.lbl_page_total.setStyleSheet("color: #94A3B8; font-size: 14px; font-weight: 600;")

        self.btn_next = QPushButton("下一页 ▶")
        self.btn_next.setToolTip("快捷键: PageDown 或 右方向键")
        self.btn_next.clicked.connect(self.next_page)

        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.spin_page)
        toolbar_layout.addWidget(self.lbl_page_total)
        toolbar_layout.addWidget(self.btn_next)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background-color: #334155;")
        toolbar_layout.addWidget(sep)

        # Zoom controls
        self.btn_zoom_out = QPushButton("－")
        self.btn_zoom_out.setFixedWidth(34)
        self.btn_zoom_out.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.btn_zoom_out.setToolTip("缩小 (Ctrl + 滚轮向下)")
        self.btn_zoom_out.clicked.connect(lambda: self.view.apply_zoom_multiplier(0.8))

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(54)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setStyleSheet("font-weight: 700; color: #38BDF8; font-size: 14px;")

        self.btn_zoom_in = QPushButton("＋")
        self.btn_zoom_in.setFixedWidth(34)
        self.btn_zoom_in.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.btn_zoom_in.setToolTip("放大 (Ctrl + 滚轮向上)")
        self.btn_zoom_in.clicked.connect(lambda: self.view.apply_zoom_multiplier(1.25))

        self.btn_fit_width = QPushButton("适宽")
        self.btn_fit_width.clicked.connect(self.fit_width)

        self.btn_fit_page = QPushButton("适页")
        self.btn_fit_page.clicked.connect(self.fit_page)

        self.btn_actual_size = QPushButton("1:1")
        self.btn_actual_size.clicked.connect(lambda: self.view.set_zoom(1.0))

        toolbar_layout.addWidget(self.btn_zoom_out)
        toolbar_layout.addWidget(self.lbl_zoom)
        toolbar_layout.addWidget(self.btn_zoom_in)
        toolbar_layout.addWidget(self.btn_fit_width)
        toolbar_layout.addWidget(self.btn_fit_page)
        toolbar_layout.addWidget(self.btn_actual_size)
        toolbar_layout.addStretch()

        layout.addWidget(toolbar)

        # 2. Central Graphics Canvas
        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor("#050811")))  # Deep space dark canvas for ultra high contrast
        self.view = PDFGraphicsView(self.scene, self)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        layout.addWidget(self.view)

        self._update_controls_state()

    @property
    def current_page_index(self) -> int:
        return self._current_page_idx

    def set_pdf_reader(self, reader: Optional[PDFReader]) -> None:
        """Load a new PDFReader and display page 0."""
        self._reader = reader
        self._segment_overlays.clear()
        if reader and reader.page_count > 0:
            self._page_count = reader.page_count
            self.spin_page.setMaximum(self._page_count)
            self.lbl_page_total.setText(f"/ {self._page_count} 页")
            self.set_current_page(0)
            self.fit_page()
        else:
            self._page_count = 0
            self._current_page_idx = 0
            self.spin_page.setMaximum(1)
            self.lbl_page_total.setText("/ 0 页")
            self.scene.clear()
            self._pixmap_item = None

        self._update_controls_state()

    def set_current_page(self, page_index: int) -> None:
        """Navigate to a specific 0-indexed page."""
        if not self._reader or self._page_count == 0:
            return

        page_index = max(0, min(self._page_count - 1, page_index))
        self._current_page_idx = page_index

        if self.spin_page.value() != page_index + 1:
            self.spin_page.blockSignals(True)
            self.spin_page.setValue(page_index + 1)
            self.spin_page.blockSignals(False)

        pixmap = PDFRenderer.render_page_to_qpixmap(self._reader, page_index, dpi=180)

        self.scene.clear()
        self._segment_overlays.clear()
        self._pixmap_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(self._pixmap_item.boundingRect())

        self._update_controls_state()
        self.page_changed.emit(page_index)

    def prev_page(self) -> None:
        if self._current_page_idx > 0:
            self.set_current_page(self._current_page_idx - 1)

    def next_page(self) -> None:
        if self._current_page_idx < self._page_count - 1:
            self.set_current_page(self._current_page_idx + 1)

    def fit_page(self) -> None:
        if not self._pixmap_item:
            return
        rect = self._pixmap_item.boundingRect()
        view_w = self.view.viewport().width() - 20
        view_h = self.view.viewport().height() - 20
        if rect.width() > 0 and rect.height() > 0 and view_w > 0 and view_h > 0:
            scale = min(view_w / rect.width(), view_h / rect.height())
            self.view.set_zoom(scale)

    def fit_width(self) -> None:
        if not self._pixmap_item:
            return
        rect = self._pixmap_item.boundingRect()
        view_w = self.view.viewport().width() - 24
        if rect.width() > 0 and view_w > 0:
            scale = view_w / rect.width()
            self.view.set_zoom(scale)

    def clear_overlays(self) -> None:
        """Clear all question overlay bounding boxes from the scene."""
        for item in list(self.scene.items()):
            if isinstance(item, QuestionOverlayItem):
                self.scene.removeItem(item)
        self._segment_overlays.clear()
        self._current_selected_qid = None
        self.scene.update()

    def set_page_overlays(
        self,
        segments_meta: List[Dict[str, Any]],
        selected_question_id: Optional[str] = None,
    ) -> None:
        """Render interactive question bounding boxes on the current page scene."""
        if not self._pixmap_item:
            return

        self._current_selected_qid = selected_question_id

        # Robustly remove any existing QuestionOverlayItem from the scene
        for item in list(self.scene.items()):
            if isinstance(item, QuestionOverlayItem):
                self.scene.removeItem(item)
        self._segment_overlays.clear()

        pixmap_rect = self._pixmap_item.boundingRect()
        pw = pixmap_rect.width()
        ph = pixmap_rect.height()

        for meta in segments_meta:
            x1, y1, x2, y2 = meta["normalized_bbox"]
            scene_rect = QRectF(x1 * pw, y1 * ph, (x2 - x1) * pw, (y2 - y1) * ph)

            qid = meta["question_id"]
            is_selected = (qid == selected_question_id)

            overlay = QuestionOverlayItem(
                question_id=qid,
                segment_id=meta.get("segment_id", ""),
                display_number=meta.get("display_number", ""),
                question_type=meta.get("question_type", ""),
                rect=scene_rect,
                normalized_bbox=(x1, y1, x2, y2),
                pixmap_size=(pw, ph),
                review_required=meta.get("review_required", False),
                selected=is_selected,
                on_clicked_callback=self._on_overlay_clicked,
                on_resized_callback=self._on_overlay_resized,
                on_context_action_callback=self._on_overlay_context_action,
            )
            self.scene.addItem(overlay)
            self._segment_overlays.append(overlay)

        self.scene.update()

    def highlight_question(self, question_id: Optional[str]) -> None:
        """Set active visual focus on a question's bounding boxes."""
        self._current_selected_qid = question_id
        for overlay in self._segment_overlays:
            overlay.set_selected(overlay.question_id == question_id)

    def focus_bbox(self, normalized_bbox: tuple[float, float, float, float]) -> None:
        """Center the viewport around a given normalized bounding box."""
        if not self._pixmap_item:
            return
        pw = self._pixmap_item.boundingRect().width()
        ph = self._pixmap_item.boundingRect().height()
        x1, y1, x2, y2 = normalized_bbox
        rect = QRectF(x1 * pw, y1 * ph, (x2 - x1) * pw, (y2 - y1) * ph)
        self.view.ensureVisible(rect, 30, 30)

    def _on_overlay_clicked(self, question_id: str) -> None:
        self.highlight_question(question_id)
        self.segment_selected.emit(question_id)

    def _on_overlay_resized(self, question_id: str, segment_id: str, new_bbox: tuple) -> None:
        self.segment_resized.emit(question_id, segment_id, new_bbox)

    def _on_overlay_context_action(self, action_name: str, question_id: str) -> None:
        self.context_action_triggered.emit(action_name, question_id)

    def _on_spin_page_changed(self, val: int) -> None:
        self.set_current_page(val - 1)

    def _on_zoom_changed(self, zoom: float) -> None:
        self.lbl_zoom.setText(f"{int(round(zoom * 100))}%")

    def _update_controls_state(self) -> None:
        has_doc = self._reader is not None and self._page_count > 0
        self.btn_prev.setEnabled(has_doc and self._current_page_idx > 0)
        self.btn_next.setEnabled(has_doc and self._current_page_idx < self._page_count - 1)
        self.spin_page.setEnabled(has_doc)
        self.btn_zoom_out.setEnabled(has_doc)
        self.btn_zoom_in.setEnabled(has_doc)
        self.btn_fit_width.setEnabled(has_doc)
        self.btn_fit_page.setEnabled(has_doc)
        self.btn_actual_size.setEnabled(has_doc)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_Left):
            self.prev_page()
            event.accept()
        elif key in (Qt.Key.Key_PageDown, Qt.Key.Key_Right):
            self.next_page()
            event.accept()
        else:
            super().keyPressEvent(event)

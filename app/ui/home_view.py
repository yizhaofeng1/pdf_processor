"""Modern Cyber-Slate Welcome & Dashboard Home View for ExamSplit AI."""

from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QColor

from ..storage.recent_files import get_recent_files, clear_recent_files, remove_recent_file
from ..config import BASE_DIR


class RecentFileRowWidget(QFrame):
    """Rich interactive card row for a recent file entry."""

    open_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, entry: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.path_str = entry.get("file_path", "")
        self.setObjectName("recentRow")
        self.setFixedHeight(78)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#recentRow {
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 8px;
            }
            QFrame#recentRow:hover {
                background-color: #172554;
                border-color: #0284C7;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(14)

        icon_lbl = QLabel("📄")
        icon_lbl.setStyleSheet("font-size: 24px; background: transparent;")
        layout.addWidget(icon_lbl)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        name_text = entry.get("file_name", Path(self.path_str).name)
        name_lbl = QLabel(name_text)
        name_lbl.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 700; background: transparent;")
        title_row.addWidget(name_lbl)

        if entry.get("page_count"):
            p_badge = QLabel(f" {entry['page_count']} 页 ")
            p_badge.setStyleSheet("background-color: #1E293B; color: #38BDF8; font-size: 11.5px; font-weight: 600; border-radius: 4px; padding: 1px 5px;")
            title_row.addWidget(p_badge)

        if entry.get("file_size"):
            s_badge = QLabel(f" {entry['file_size']} ")
            s_badge.setStyleSheet("background-color: #1E293B; color: #94A3B8; font-size: 11.5px; border-radius: 4px; padding: 1px 5px;")
            title_row.addWidget(s_badge)

        title_row.addStretch()
        info_layout.addLayout(title_row)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)

        if entry.get("last_opened"):
            time_lbl = QLabel(f"🕒 {entry['last_opened']}")
            time_lbl.setStyleSheet("color: #64748B; font-size: 12px; background: transparent;")
            sub_row.addWidget(time_lbl)

        path_display = self.path_str
        if len(path_display) > 65:
            path_display = path_display[:30] + "..." + path_display[-32:]
        path_lbl = QLabel(path_display)
        path_lbl.setToolTip(self.path_str)
        path_lbl.setStyleSheet("color: #475569; font-size: 12px; background: transparent;")
        sub_row.addWidget(path_lbl)
        sub_row.addStretch()

        info_layout.addLayout(sub_row)
        layout.addLayout(info_layout, stretch=1)

        btn_open = QPushButton("打开试卷 ➜")
        btn_open.setFixedHeight(34)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #2563EB);
                color: #FFFFFF;
                border: 1px solid #38BDF8;
                border-radius: 6px;
                padding: 0px 16px;
                font-size: 13.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #1D4ED8);
            }
        """)
        btn_open.clicked.connect(lambda: self.open_requested.emit(self.path_str))
        layout.addWidget(btn_open)

        btn_remove = QPushButton("✕")
        btn_remove.setToolTip("从历史记录中移除")
        btn_remove.setFixedSize(28, 28)
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748B;
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #33141E;
                color: #EF4444;
            }
        """)
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.path_str))
        layout.addWidget(btn_remove)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.path_str)
        super().mousePressEvent(event)



class DropZoneFrame(QFrame):
    """Interactive drag and drop zone for PDF files with Cyber-Tech styling."""

    file_dropped = Signal(str)
    clicked_browse = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setStyleSheet("""
            QFrame#dropZone {
                border: 2px dashed #0284C7;
                border-radius: 16px;
                background-color: #0F172A;
                padding: 38px 24px;
            }
            QFrame#dropZone:hover {
                border-color: #38BDF8;
                background-color: #131E35;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        icon_label = QLabel("📥")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 56px; background: transparent;")
        layout.addWidget(icon_label)

        title_label = QLabel("将试卷 PDF 文件直接拖拽至此处")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #F8FAFC; font-size: 20px; font-weight: 700; background: transparent;")
        layout.addWidget(title_label)

        hint_label = QLabel("支持考研数学/统考真题、自命题期末卷及单双栏各类试卷 · 原生矢量无损解析")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("color: #94A3B8; font-size: 15px; background: transparent;")
        layout.addWidget(hint_label)

        btn_box = QHBoxLayout()
        btn_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_browse = QPushButton("📂 浏览本地文件并打开...")
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #2563EB);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 15.5px;
                padding: 12px 32px;
                border-radius: 8px;
                border: 1px solid #38BDF8;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #1D4ED8);
                border-color: #7DD3FC;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
        """)
        self.btn_browse.clicked.connect(self.clicked_browse.emit)
        btn_box.addWidget(self.btn_browse)

        layout.addLayout(btn_box)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".pdf"):
                self.file_dropped.emit(file_path)
                event.acceptProposedAction()
                return
        event.ignore()


class HomeView(QWidget):
    """App Home / Landing dashboard view with futuristic card layout."""

    open_pdf_requested = Signal(str)
    browse_pdf_requested = Signal()
    open_settings_requested = Signal()
    batch_import_requested = Signal()
    open_basket_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: #090D16;")

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #090D16;")
        scroll.setWidget(content_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(40, 32, 40, 36)
        layout.setSpacing(24)

        # 1. Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0F172A, stop:0.5 #1E293B, stop:1 #0F172A);
                border: 1px solid #1E293B;
                border-left: 5px solid #38BDF8;
                border-radius: 14px;
                padding: 24px 28px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setSpacing(8)

        tag_lbl = QLabel("⚡ EXAMSPLIT AI · 桌面专业版 v0.2.0")
        tag_lbl.setStyleSheet("""
            color: #38BDF8;
            font-size: 13.5px;
            font-weight: 800;
            letter-spacing: 2px;
            background: transparent;
        """)
        h_layout.addWidget(tag_lbl)

        title_lbl = QLabel("试卷 PDF 智能拆题与选题导出系统")
        title_lbl.setStyleSheet("""
            color: #FFFFFF;
            font-size: 28px;
            font-weight: 800;
            background: transparent;
        """)
        h_layout.addWidget(title_lbl)

        sub_lbl = QLabel("原生 PDF 矢量零损耗裁剪 · 多模态视觉智能定位 · A4 自由选题重排导出 · 100% 离线隐私与安全加密")
        sub_lbl.setStyleSheet("""
            color: #94A3B8;
            font-size: 15px;
            background: transparent;
        """)
        h_layout.addWidget(sub_lbl)

        layout.addWidget(header_frame)

        # 2. Interactive Drop Zone
        self.drop_zone = DropZoneFrame(self)
        self.drop_zone.clicked_browse.connect(self.browse_pdf_requested.emit)
        self.drop_zone.file_dropped.connect(self.open_pdf_requested.emit)
        layout.addWidget(self.drop_zone)

        # 3. Quick Action Bar
        quick_bar = QHBoxLayout()
        quick_bar.setSpacing(14)

        test_pdf_path = BASE_DIR / "2010_math_test.pdf"
        if test_pdf_path.exists():
            self.btn_sample_pdf = QPushButton("🧪 快速载入示例试卷 (2010 考研数学真题 8页)")
            self.btn_sample_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_sample_pdf.setStyleSheet("""
                QPushButton {
                    background-color: #131C2E;
                    color: #F8FAFC;
                    border: 1px solid #334155;
                    padding: 10px 22px;
                    border-radius: 8px;
                    font-size: 15px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1E293B;
                    border-color: #38BDF8;
                    color: #38BDF8;
                }
            """)
            self.btn_sample_pdf.clicked.connect(lambda: self.open_pdf_requested.emit(str(test_pdf_path)))
            quick_bar.addWidget(self.btn_sample_pdf)

        self.btn_batch = QPushButton("⚡ 批量导入与分析...")
        self.btn_batch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_batch.setStyleSheet("""
            QPushButton {
                background-color: #131C2E;
                color: #F8FAFC;
                border: 1px solid #334155;
                padding: 10px 22px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-color: #38BDF8;
                color: #38BDF8;
            }
        """)
        self.btn_batch.clicked.connect(self.batch_import_requested.emit)
        quick_bar.addWidget(self.btn_batch)

        self.btn_basket = QPushButton("🧺 组卷试题篮")
        self.btn_basket.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_basket.setStyleSheet("""
            QPushButton {
                background-color: #131C2E;
                color: #F8FAFC;
                border: 1px solid #334155;
                padding: 10px 22px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-color: #38BDF8;
                color: #38BDF8;
            }
        """)
        self.btn_basket.clicked.connect(self.open_basket_requested.emit)
        quick_bar.addWidget(self.btn_basket)

        self.btn_settings = QPushButton("⚙️ AI 模型与网络设置...")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #131C2E;
                color: #F8FAFC;
                border: 1px solid #334155;
                padding: 10px 22px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-color: #38BDF8;
                color: #38BDF8;
            }
        """)
        self.btn_settings.clicked.connect(self.open_settings_requested.emit)
        quick_bar.addWidget(self.btn_settings)

        quick_bar.addStretch()
        layout.addLayout(quick_bar)

        # 4. Recent Files Section
        recent_group = QFrame()
        recent_group.setStyleSheet("""
            QFrame {
                border: 1px solid #1E293B;
                border-radius: 12px;
                background-color: #0B1120;
            }
        """)
        recent_layout = QVBoxLayout(recent_group)
        recent_layout.setContentsMargins(20, 18, 20, 18)
        recent_layout.setSpacing(12)

        header_row = QHBoxLayout()
        recent_title = QLabel("🕒 最近打开的试卷历史")
        recent_title.setStyleSheet("border: none; color: #38BDF8; font-size: 17px; font-weight: 700; background: transparent;")
        header_row.addWidget(recent_title)

        header_row.addStretch()

        self.btn_clear_recent = QPushButton("🗑️ 清空历史")
        self.btn_clear_recent.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_recent.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94A3B8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 13.5px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-color: #EF4444;
                color: #F87171;
            }
        """)
        self.btn_clear_recent.clicked.connect(self._on_clear_recent)
        header_row.addWidget(self.btn_clear_recent)

        recent_layout.addLayout(header_row)

        self.recent_list_widget = QListWidget()
        self.recent_list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                border: none;
                background: transparent;
                margin-bottom: 6px;
            }
            QListWidget::item:selected {
                background: transparent;
            }
        """)
        self.recent_list_widget.itemClicked.connect(self._on_recent_item_clicked)
        self.recent_list_widget.itemDoubleClicked.connect(self._on_recent_item_clicked)
        recent_layout.addWidget(self.recent_list_widget)

        layout.addWidget(recent_group)

        # 5. Workflow Guide Cards (Tech Obsidian)
        flow_group = QFrame()
        flow_group.setStyleSheet("border: none; background: transparent;")
        flow_layout = QHBoxLayout(flow_group)
        flow_layout.setContentsMargins(0, 4, 0, 0)
        flow_layout.setSpacing(14)

        steps = [
            ("📄 1. 原生导入", "直接解析 PDF 矢量结构与高分辨率栅格图，绝不破坏修改原始文件"),
            ("🔍 2. 智能拆题", "多模态大模型视觉定位与本地规则校验，自动关联跨页题与题号"),
            ("✏️ 3. 边界微调", "交互式手柄实时拖拽缩放选框，所有 AI 结果均可人工自由修正"),
            ("🚀 4. 无损导出", "支持单题一页留白刷题与多题紧凑排版，一键生成标准印刷级 A4"),
        ]

        for step_title, step_desc in steps:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #111827;
                    border: 1px solid #1E293B;
                    border-radius: 12px;
                    padding: 18px;
                }
                QFrame:hover {
                    border-color: #38BDF8;
                    background-color: #1E293B;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setSpacing(8)

            st_lbl = QLabel(step_title)
            st_lbl.setStyleSheet("border: none; color: #38BDF8; font-size: 16px; font-weight: 700; background: transparent;")
            c_layout.addWidget(st_lbl)

            sd_lbl = QLabel(step_desc)
            sd_lbl.setWordWrap(True)
            sd_lbl.setStyleSheet("border: none; color: #94A3B8; font-size: 14px; line-height: 1.5; background: transparent;")
            c_layout.addWidget(sd_lbl)

            flow_layout.addWidget(card)

        layout.addWidget(flow_group)
        self.refresh_recent_files()

    def refresh_recent_files(self) -> None:
        self.recent_list_widget.clear()
        recent_items = get_recent_files()
        if not recent_items:
            empty_item = QListWidgetItem("暂无打开历史，请拖入或浏览选择试卷 PDF 开始使用。")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            empty_item.setForeground(QColor("#64748B"))
            self.recent_list_widget.addItem(empty_item)
            self.recent_list_widget.setFixedHeight(80)
            return

        self.recent_list_widget.setSpacing(8)
        for entry in recent_items:
            path_str = entry.get("file_path", "") if isinstance(entry, dict) else str(entry)
            p = Path(path_str)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 80))
            item.setData(Qt.ItemDataRole.UserRole, path_str)

            row_widget = RecentFileRowWidget(entry if isinstance(entry, dict) else {"file_path": path_str, "file_name": p.name}, self)
            row_widget.open_requested.connect(self.open_pdf_requested.emit)
            row_widget.remove_requested.connect(self._on_remove_recent)

            self.recent_list_widget.addItem(item)
            self.recent_list_widget.setItemWidget(item, row_widget)

        # Dynamic height to ensure no internal vertical scroll bar clipping
        row_count = len(recent_items)
        total_h = min(420, max(90, row_count * 88 + 10))
        self.recent_list_widget.setFixedHeight(total_h)

    def _on_recent_item_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if path_str and Path(path_str).exists():
            self.open_pdf_requested.emit(path_str)

    def _on_clear_recent(self) -> None:
        clear_recent_files()
        self.refresh_recent_files()

    def _on_remove_recent(self, file_path: str) -> None:
        remove_recent_file(file_path)
        self.refresh_recent_files()

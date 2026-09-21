"""MainWindow: Central desktop container for ExamSplit AI."""

from typing import Optional, List, Dict
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QStatusBar,
    QToolBar,
    QToolButton,
    QScrollArea,
    QStackedWidget,
    QMenu,
    QFrame,
    QApplication,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QIcon,
    QFont,
    QDragEnterEvent,
    QDropEvent,
    QColor,
    QBrush,
)

from ..pdf.reader import PDFReader, validate_pdf
from ..pdf.coordinate import normalized_to_pdf_rect
from ..models.question import Question, QuestionType, QuestionStatus
from ..models.segment import QuestionSegment
from ..services.detection_service import DetectionService, AnalysisWorker, BatchAnalysisWorker
from ..services.question_basket import QuestionBasket, GLOBAL_BASKET
from ..storage.key_storage import KeyStorage
from ..storage.recent_files import add_recent_file
from ..storage.database import save_project_questions, load_project_questions
from ..ai.provider_factory import ProviderFactory, PROVIDER_PRESETS
from .pdf_viewer import PDFViewerWidget
from .settings_dialog import SettingsDialog
from .home_view import HomeView
from .export_dialog import ExportDialog
from .question_basket_dialog import QuestionBasketDialog
from .batch_analysis_dialog import BatchAnalysisDialog
from .styles import MODERN_APP_STYLESHEET

QUESTION_TYPE_NAMES = {
    QuestionType.CHOICE: "选择题",
    "choice": "选择题",
    QuestionType.FILL_IN: "填空题",
    "fill_in": "填空题",
    QuestionType.SOLVE: "解答题",
    "solve": "解答题",
    QuestionType.PROOF: "证明题",
    "proof": "证明题",
    QuestionType.OTHER: "综合题",
    "other": "综合题",
    "小题": "小题",
    "大题": "大题",
    "选择题": "选择题",
    "填空题": "填空题",
    "解答题": "解答题",
    "证明题": "证明题",
    "综合题": "综合题",
}

BASKET_IN_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #991B1B, stop:1 #DC2626);
        color: #FEF2F2;
        border: 1.5px solid #F87171;
        border-radius: 10px;
        padding: 10px 18px;
        font-size: 15.5px;
        font-weight: 700;
        min-height: 44px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B91C1C, stop:1 #EF4444);
        border-color: #FCA5A5;
        color: #FFFFFF;
    }
    QPushButton:pressed {
        background-color: #7F1D1D;
    }
    QPushButton:disabled {
        background-color: #131C2E;
        color: #475569;
        border: 1px solid #1E293B;
    }
"""

BASKET_OUT_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
        color: #FFFFFF;
        border: 1.5px solid #34D399;
        border-radius: 10px;
        padding: 10px 18px;
        font-size: 15.5px;
        font-weight: 700;
        min-height: 44px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
        border-color: #6EE7B7;
        color: #FFFFFF;
    }
    QPushButton:pressed {
        background-color: #065F46;
    }
    QPushButton:disabled {
        background-color: #131C2E;
        color: #475569;
        border: 1px solid #1E293B;
    }
"""


class MainWindow(QMainWindow):
    """Main Application Window hosting Welcome Dashboard and Workbench."""

    def __init__(
        self,
        initial_pdf: Optional[str | Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ExamSplit AI —— 试卷 PDF 智能拆题与选题导出系统")
        self.resize(1340, 880)
        self.setMinimumSize(980, 660)
        self.setAcceptDrops(True)
        self.setStyleSheet(MODERN_APP_STYLESHEET)

        self.pdf_reader: Optional[PDFReader] = None
        self.opened_documents: Dict[str, PDFReader] = {}
        self.questions: List[Question] = []
        self.selected_question: Optional[Question] = None
        self.analysis_worker: Optional[AnalysisWorker] = None
        self._updating_details = False

        self._setup_menus()
        self._setup_toolbar()
        self._setup_central_ui()
        self._setup_status_bar()

        if initial_pdf:
            self.load_pdf(initial_pdf)

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开试卷 PDF(&O)...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_pdf_dialog)
        file_menu.addAction(open_action)

        batch_open_action = QAction("批量导入试卷(&B)...", self)
        batch_open_action.triggered.connect(self._on_batch_import_dialog)
        file_menu.addAction(batch_open_action)

        self.close_action = QAction("关闭当前试卷(&W)", self)
        self.close_action.setShortcut("Ctrl+W")
        self.close_action.setEnabled(False)
        self.close_action.triggered.connect(self.close_pdf)
        file_menu.addAction(self.close_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Analysis Menu
        analysis_menu = menubar.addMenu("分析(&A)")
        self.action_run_analysis = QAction("开始当前试卷分析(&R)", self)
        self.action_run_analysis.setEnabled(False)
        self.action_run_analysis.triggered.connect(self._on_run_analysis)
        analysis_menu.addAction(self.action_run_analysis)

        self.action_batch_analysis = QAction("批量后台智能分析(&M)...", self)
        self.action_batch_analysis.triggered.connect(lambda: self._on_open_batch_analysis())
        analysis_menu.addAction(self.action_batch_analysis)

        # Selection Menu
        selection_menu = menubar.addMenu("选题(&S)")
        self.action_select_all = QAction("全部选择(&A)", self)
        self.action_select_all.triggered.connect(self._on_select_all)
        selection_menu.addAction(self.action_select_all)

        self.action_invert = QAction("反向选择(&I)", self)
        self.action_invert.triggered.connect(self._on_invert_selection)
        selection_menu.addAction(self.action_invert)

        selection_menu.addSeparator()
        self.action_basket = QAction("打开组卷试题篮(&K)...", self)
        self.action_basket.triggered.connect(self._on_open_basket)
        selection_menu.addAction(self.action_basket)

        # Settings Menu
        settings_menu = menubar.addMenu("设置(&C)")
        pref_action = QAction("⚙️ API 与服务商偏好设置...", self)
        pref_action.triggered.connect(self._on_open_settings)
        settings_menu.addAction(pref_action)

        settings_menu.addSeparator()
        self.provider_switch_menu = settings_menu.addMenu("🎯 快速切换当前生效服务商")
        self._setup_provider_quick_switch_menu()

        # Help Menu
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于 ExamSplit AI(&B)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("主快捷工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.tb_home = toolbar.addAction("🏠 主页仪表盘")
        self.tb_home.triggered.connect(self.show_home)

        self.tb_open = toolbar.addAction("📂 打开试卷")
        self.tb_open.triggered.connect(self._on_open_pdf_dialog)

        self.tb_settings = toolbar.addAction("⚙️ API与服务商设置")
        self.tb_settings.triggered.connect(self._on_open_settings)

        toolbar.addSeparator()

        self.tb_analyze = toolbar.addAction("🔍 开始智能分析")
        self.tb_analyze.setEnabled(False)
        self.tb_analyze.triggered.connect(self._on_run_analysis)

        self.tb_batch = toolbar.addAction("⚡ 批量后台分析")
        self.tb_batch.triggered.connect(lambda: self._on_open_batch_analysis())

        self.tb_add_box = toolbar.addAction("➕ 新建题目选框")
        self.tb_add_box.setEnabled(False)
        self.tb_add_box.triggered.connect(self._on_add_new_question)

        toolbar.addSeparator()

        self.tb_select_all = toolbar.addAction("☑️ 全选")
        self.tb_select_all.triggered.connect(self._on_select_all)

        self.tb_invert = toolbar.addAction("🔄 反选")
        self.tb_invert.triggered.connect(self._on_invert_selection)

        toolbar.addSeparator()

        self.tb_basket = toolbar.addAction("🧺 组卷试题篮 (0)")
        self.tb_basket.triggered.connect(self._on_open_basket)
        GLOBAL_BASKET.basket_changed.connect(self._update_basket_badge)

        self.tb_export = toolbar.addAction("🚀 导出选中题目 (A4无损)")
        self.tb_export.setEnabled(False)
        self.tb_export.triggered.connect(self._on_export_clicked)
        self.btn_export = self.tb_export

        toolbar.addSeparator()
        lbl_cur_doc = QLabel(" 📑 当前试卷: ")
        lbl_cur_doc.setStyleSheet("font-weight: 700; color: #38BDF8; margin-left: 8px; font-size: 14.5px;")
        toolbar.addWidget(lbl_cur_doc)

        self.combo_active_doc = QComboBox()
        self.combo_active_doc.setMinimumWidth(220)
        self.combo_active_doc.setToolTip("点击切换当前正在编辑的试卷 (更多试卷 ▾)")
        self.combo_active_doc.currentIndexChanged.connect(self._on_active_doc_changed)
        toolbar.addWidget(self.combo_active_doc)

        # "更多功能 ▾" menu button
        self.btn_more_menu = QToolButton()
        self.btn_more_menu.setText("更多功能 ▾")
        self.btn_more_menu.setStyleSheet("""
            QToolButton {
                background: #1E293B;
                color: #38BDF8;
                border: 1.5px solid #38BDF8;
                font-weight: 700;
                padding: 6px 14px;
                border-radius: 8px;
            }
            QToolButton:hover {
                background: #0284C7;
                color: #FFFFFF;
            }
        """)
        self.btn_more_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self.btn_more_menu)
        more_menu.addAction("📂 打开试卷 PDF...", self._on_open_pdf_dialog)
        more_menu.addAction("📦 批量导入试卷...", self._on_batch_import_dialog)
        more_menu.addAction("⚡ 批量后台智能分析...", lambda: self._on_open_batch_analysis())
        more_menu.addSeparator()
        more_menu.addAction("🧺 打开组卷试题篮...", self._on_open_basket)
        more_menu.addAction("🚀 导出选中题目 (A4无损)...", self._on_export_clicked)
        more_menu.addSeparator()
        more_menu.addAction("⚙️ API 与服务商偏好设置...", self._on_open_settings)
        more_menu.addAction("🧪 本地识别实验 (VAQL)...", self._on_open_local_experiment)
        self.btn_more_menu.setMenu(more_menu)
        toolbar.addWidget(self.btn_more_menu)

    def _setup_central_ui(self) -> None:
        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        # View 0: Home / Welcome Dashboard
        self.home_view = HomeView(self)
        self.home_view.open_pdf_requested.connect(self.load_pdf)
        self.home_view.browse_pdf_requested.connect(self._on_open_pdf_dialog)
        self.home_view.open_settings_requested.connect(self._on_open_settings)
        self.home_view.batch_import_requested.connect(self._on_batch_import_dialog)
        self.home_view.open_basket_requested.connect(self._on_open_basket)
        self.stack.addWidget(self.home_view)

        # View 1: Workbench Splitter
        workbench = QWidget(self)
        wb_layout = QVBoxLayout(workbench)
        wb_layout.setContentsMargins(0, 0, 0, 0)
        wb_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, workbench)

        # 1. Left: Question Index Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)

        # Filter and Search
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索题号或题型...")
        self.search_edit.textChanged.connect(self._filter_question_list)

        self.combo_filter = QComboBox()
        self.combo_filter.setMinimumWidth(130)
        self.combo_filter.addItems(["全部题型 ▾", "选择题", "填空题", "解答题", "待复核 ⚠️", "跨页题"])
        self.combo_filter.setToolTip("题型快速筛选 (更多选项 ▾)")
        self.combo_filter.currentTextChanged.connect(self._filter_question_list)

        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.combo_filter)
        left_layout.addLayout(search_layout)

        self.question_list_widget = QListWidget()
        self.question_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.question_list_widget.customContextMenuRequested.connect(self._on_list_context_menu)
        self.question_list_widget.currentItemChanged.connect(self._on_question_selection_changed)
        self.question_list_widget.itemChanged.connect(self._on_question_item_changed)
        left_layout.addWidget(self.question_list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_invert_select = QPushButton("反选")
        self.btn_invert_select.clicked.connect(self._on_invert_selection)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_invert_select)
        left_layout.addLayout(btn_layout)

        # 2. Center: PDF Viewer Panel
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(4, 4, 4, 4)

        self.pdf_viewer = PDFViewerWidget(center_panel)
        self.pdf_viewer.page_changed.connect(self._on_page_changed)
        self.pdf_viewer.segment_selected.connect(self._on_viewer_segment_selected)
        self.pdf_viewer.segment_resized.connect(self._on_segment_resized)
        self.pdf_viewer.context_action_triggered.connect(self._on_viewer_context_action)
        center_layout.addWidget(self.pdf_viewer)

        # 3. Right: Question Details Panel (Grand & Spacious, Scrollable)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        right_panel = QWidget()
        right_panel.setMinimumWidth(350)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(14)

        detail_group = QGroupBox("当前题目详细属性")
        detail_form = QFormLayout(detail_group)
        detail_form.setContentsMargins(14, 20, 14, 16)
        detail_form.setVerticalSpacing(16)
        detail_form.setHorizontalSpacing(14)
        detail_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        detail_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.lbl_q_number = QLabel("—")
        self.lbl_q_number.setMinimumHeight(24)
        self.lbl_q_number.setStyleSheet("font-size: 18px; font-weight: 800; color: #38BDF8;")
        
        self.combo_q_type = QComboBox()
        self.combo_q_type.setObjectName("combo_q_type")
        self.combo_q_type.setFixedHeight(36)
        self.combo_q_type.setToolTip("修改此题的题型分类 (展开更多 ▾)")
        self.combo_q_type.addItems(["小题", "大题", "选择题", "填空题", "解答题", "证明题", "综合题"])
        self.combo_q_type.currentTextChanged.connect(self._on_question_type_changed)

        class _TypeAdapter:
            def __init__(self, combo: QComboBox):
                self._combo = combo
            def text(self) -> str:
                return self._combo.currentText()
            def setText(self, val: str) -> None:
                self._combo.setCurrentText(val)

        self.lbl_q_type = _TypeAdapter(self.combo_q_type)

        self.lbl_q_source_paper = QLabel("—")
        self.lbl_q_source_paper.setMinimumHeight(36)
        self.lbl_q_source_paper.setStyleSheet("""
            QLabel {
                font-size: 13.5px;
                color: #CBD5E1;
                font-weight: 500;
                background-color: #0B1120;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 6px 10px;
                line-height: 1.3;
            }
        """)
        self.lbl_q_source_paper.setWordWrap(True)

        self.lbl_q_page = QLabel("—")
        self.lbl_q_page.setMinimumHeight(24)
        self.lbl_q_page.setStyleSheet("font-size: 15px; color: #CBD5E1;")
        self.lbl_q_confidence = QLabel("—")
        self.lbl_q_confidence.setMinimumHeight(24)
        self.lbl_q_confidence.setStyleSheet("font-size: 15px; font-weight: 700; color: #34D399;")
        self.lbl_q_status = QLabel("待分析")
        self.lbl_q_status.setMinimumHeight(24)
        self.lbl_q_status.setStyleSheet("font-size: 15px; color: #94A3B8;")

        detail_form.addRow("试题题号:", self.lbl_q_number)
        detail_form.addRow("试题题型:", self.combo_q_type)
        detail_form.addRow("所属试卷:", self.lbl_q_source_paper)
        detail_form.addRow("所属页码:", self.lbl_q_page)
        detail_form.addRow("AI置信度:", self.lbl_q_confidence)
        detail_form.addRow("当前状态:", self.lbl_q_status)

        right_layout.addWidget(detail_group)

        # Warning / Consistency Alert Card (Cyber Amber)
        self.lbl_q_reasons = QLabel()
        self.lbl_q_reasons.setWordWrap(True)
        self.lbl_q_reasons.setStyleSheet("""
            QLabel {
                color: #FEF3C7;
                background-color: #78350F;
                border: 1.5px solid #F59E0B;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13.5px;
                font-weight: 600;
                line-height: 1.4;
            }
        """)
        self.lbl_q_reasons.setVisible(False)
        right_layout.addWidget(self.lbl_q_reasons)

        # Operations Card (Spacious & Atmospheric)
        ops_group = QGroupBox("题目快捷操作")
        ops_layout = QVBoxLayout(ops_group)
        ops_layout.setContentsMargins(14, 20, 14, 18)
        ops_layout.setSpacing(14)

        # 1. Primary Hero Action: Basket Toggle
        self.btn_basket_toggle = QPushButton("🧺 加入试题篮")
        self.btn_basket_toggle.setEnabled(False)
        self.btn_basket_toggle.setStyleSheet(BASKET_OUT_STYLE)
        self.btn_basket_toggle.clicked.connect(self._on_toggle_basket)
        ops_layout.addWidget(self.btn_basket_toggle)

        # 2. Secondary Actions Grid: Confirm & Merge side by side
        actions_grid = QHBoxLayout()
        actions_grid.setSpacing(10)

        self.btn_confirm_question = QPushButton("✓ 确认无误")
        self.btn_confirm_question.setProperty("success", "true")
        self.btn_confirm_question.setEnabled(False)
        self.btn_confirm_question.setFixedHeight(42)
        self.btn_confirm_question.setToolTip("确认此题目切分边界与属性正确无误")
        self.btn_confirm_question.clicked.connect(self._on_confirm_question)
        actions_grid.addWidget(self.btn_confirm_question)

        self.btn_merge_prev = QPushButton("🔗 跨页合并")
        self.btn_merge_prev.setEnabled(False)
        self.btn_merge_prev.setFixedHeight(42)
        self.btn_merge_prev.setToolTip("将本题与上一题合并为跨页大题")
        self.btn_merge_prev.clicked.connect(lambda: self._on_merge_with_previous(self.selected_question.id if self.selected_question else ""))
        actions_grid.addWidget(self.btn_merge_prev)

        ops_layout.addLayout(actions_grid)

        # 3. Danger Action: Delete
        self.btn_delete_q = QPushButton("🗑️ 删除此题目选框")
        self.btn_delete_q.setProperty("danger", "true")
        self.btn_delete_q.setEnabled(False)
        self.btn_delete_q.setFixedHeight(40)
        self.btn_delete_q.setToolTip("从试卷中删除当前选中的题目选框")
        self.btn_delete_q.clicked.connect(lambda: self._on_delete_question(self.selected_question.id if self.selected_question else ""))
        ops_layout.addWidget(self.btn_delete_q)

        right_layout.addWidget(ops_group)

        hint_card = QFrame()
        hint_card.setStyleSheet("""
            QFrame {
                background: #0F172A;
                border: 1px dashed #334155;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        h_layout = QVBoxLayout(hint_card)
        lbl_hint = QLabel("💡 <b>边界微调技巧</b>：<br>在中央视口直接拖动选中题目的 4 条边或手柄，即可高精度微调裁切范围。")
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.4;")
        h_layout.addWidget(lbl_hint)
        right_layout.addWidget(hint_card)

        right_layout.addStretch()
        right_scroll.setWidget(right_panel)

        # Add to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 6)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([260, 680, 360])

        wb_layout.addWidget(splitter)
        self.stack.addWidget(workbench)

    def _setup_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

        self.status_file_label = QLabel("欢迎使用 ExamSplit AI")
        status_bar.addWidget(self.status_file_label)

        self.status_counts_label = QLabel(" | 已识别 0 题 | 已选 0 题")
        status_bar.addWidget(self.status_counts_label)

        self.status_model_label = QLabel()
        self.status_model_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_model_label.setToolTip("点击打开 AI 模型与网关配置")
        self.status_model_label.mousePressEvent = lambda ev: self._on_open_settings()
        self._update_model_indicator()
        status_bar.addPermanentWidget(self.status_model_label)

    def _setup_provider_quick_switch_menu(self) -> None:
        """Create checkable actions for each provider preset in menubar."""
        self.provider_action_group = QActionGroup(self)
        self.provider_action_group.setExclusive(True)
        self.provider_actions: Dict[str, QAction] = {}

        for pid, preset in PROVIDER_PRESETS.items():
            action = QAction(preset["display_name"], self)
            action.setCheckable(True)
            action.setData(pid)
            action.triggered.connect(lambda checked=False, p=pid: self._on_quick_switch_provider(p))
            self.provider_action_group.addAction(action)
            self.provider_switch_menu.addAction(action)
            self.provider_actions[pid] = action

        self._sync_provider_menu()

    def _sync_provider_menu(self) -> None:
        """Synchronize checkmarks in the provider quick-switch menu with KeyStorage."""
        active_pid = KeyStorage.get_default_provider_id()
        if hasattr(self, "provider_actions"):
            for pid, act in self.provider_actions.items():
                act.setChecked(pid == active_pid)

    def _on_quick_switch_provider(self, provider_id: str) -> None:
        """Quickly switch the active default provider without opening the settings dialog."""
        KeyStorage.set_default_provider_id(provider_id)
        self._update_model_indicator()
        self._sync_provider_menu()
        preset = PROVIDER_PRESETS.get(provider_id, {})
        disp_name = preset.get("display_name", provider_id)
        cfg = KeyStorage.get_provider_config(provider_id) or {}
        has_key = bool(cfg.get("api_key"))
        key_tip = "（已配置 Key）" if has_key else "（⚠️ 尚未配置 Key，请在设置中输入）"
        self.statusBar().showMessage(f"当前生效 AI 服务商已切换为: {disp_name} {key_tip}", 4000)

    def _update_model_indicator(self) -> None:
        try:
            pid = KeyStorage.get_default_provider_id()
            cfg = KeyStorage.get_provider_config(pid) or {}
            preset = PROVIDER_PRESETS.get(pid, {})
            display_name = preset.get("display_name", pid)
            model = cfg.get("model_name") or preset.get("default_model", "")
            has_key = bool(cfg.get("api_key"))
            dot = "🟢" if has_key else "🟡"
            key_status = "已配置Key" if has_key else "未设置Key"
            self.status_model_label.setText(f"AI网关: {dot} {display_name} ({model}) [{key_status}]")
        except Exception:
            self.status_model_label.setText("AI网关: 待配置")
        self._sync_provider_menu()

    def show_home(self) -> None:
        self.stack.setCurrentIndex(0)
        self.home_view.refresh_recent_files()
        if not self.pdf_reader:
            self.setWindowTitle("ExamSplit AI —— 试卷 PDF 智能拆题与选题导出系统")
            self.status_file_label.setText("欢迎使用 ExamSplit AI")

    def show_workbench(self) -> None:
        if self.pdf_reader:
            self.stack.setCurrentIndex(1)

    def load_pdf(self, file_path: str | Path) -> bool:
        """Open and display a PDF file, caching in opened_documents and transitioning to Workbench."""
        path = Path(file_path).resolve()
        path_str = str(path)
        validation = validate_pdf(path)
        if not validation.is_valid:
            QMessageBox.critical(self, "打开 PDF 失败", validation.error_message or "文件无效")
            return False

        try:
            # If switching away from an active document with unsaved changes, save to SQLite
            if self.pdf_reader and self.questions:
                save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

            # Reuse existing reader or create new one
            if path_str in self.opened_documents:
                reader = self.opened_documents[path_str]
            else:
                reader = PDFReader(path)
                self.opened_documents[path_str] = reader

            self.pdf_reader = reader
            self.pdf_viewer.set_pdf_reader(self.pdf_reader)

            add_recent_file(path, page_count=self.pdf_reader.page_count)
            self.home_view.refresh_recent_files()

            # Update document switcher dropdown
            self._sync_doc_switcher(path_str)

            self.stack.setCurrentIndex(1)
            self.setWindowTitle(f"ExamSplit AI - {path.name} (共 {self.pdf_reader.page_count} 页)")
            self.status_file_label.setText(f"已加载: {path.name} (共 {self.pdf_reader.page_count} 页)")
            self.action_run_analysis.setEnabled(True)
            self.tb_analyze.setEnabled(True)
            self.tb_add_box.setEnabled(True)
            self.close_action.setEnabled(True)

            # Check for previously saved questions in database
            pid = self.pdf_reader.file_hash[:16]
            cached_qs = load_project_questions(pid)
            if cached_qs:
                for q in cached_qs:
                    if not q.source_pdf_path:
                        q.source_pdf_path = path_str
                    if not q.source_paper_title:
                        q.source_paper_title = path.stem
                    if not q.original_display_number:
                        q.original_display_number = q.display_number

                self.questions = cached_qs
                self._populate_question_list()
                self.statusBar().showMessage(f"已恢复已存切题记录: 共 {len(cached_qs)} 道题", 3000)
            else:
                self.questions = []
                self.question_list_widget.clear()
                self._update_counts_indicator()
                self.statusBar().showMessage(f"成功打开试卷: {path.name}，可点击【开始智能分析】", 3000)

            return True
        except Exception as e:
            QMessageBox.critical(self, "加载 PDF 错误", f"读取 PDF 出现异常: {e}")
            return False

    def close_pdf(self) -> None:
        if self.pdf_reader:
            cur_path = str(self.pdf_reader.pdf_path)
            if self.questions:
                save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

            if cur_path in self.opened_documents:
                self.opened_documents[cur_path].close()
                del self.opened_documents[cur_path]
            else:
                self.pdf_reader.close()
            self.pdf_reader = None

        # Remove from combo box
        cur_idx = self.combo_active_doc.currentIndex()
        if cur_idx >= 0:
            self.combo_active_doc.blockSignals(True)
            self.combo_active_doc.removeItem(cur_idx)
            self.combo_active_doc.blockSignals(False)

        # If there are still opened documents, switch to the first one
        if self.combo_active_doc.count() > 0:
            next_path = self.combo_active_doc.itemData(0)
            self.load_pdf(next_path)
            return

        self.questions = []
        self.selected_question = None
        self.question_list_widget.clear()
        self.pdf_viewer.set_pdf_reader(None)
        self.action_run_analysis.setEnabled(False)
        self.tb_analyze.setEnabled(False)
        self.tb_add_box.setEnabled(False)
        self.close_action.setEnabled(False)
        self._update_counts_indicator()
        self.show_home()
        self.statusBar().showMessage("已关闭当前试卷", 2000)

    def _sync_doc_switcher(self, current_path_str: str) -> None:
        self.combo_active_doc.blockSignals(True)
        idx = -1
        for i in range(self.combo_active_doc.count()):
            if self.combo_active_doc.itemData(i) == current_path_str:
                idx = i
                break

        if idx == -1:
            p = Path(current_path_str)
            self.combo_active_doc.addItem(f"📄 {p.name}", current_path_str)
            idx = self.combo_active_doc.count() - 1

        self.combo_active_doc.setCurrentIndex(idx)
        self.combo_active_doc.blockSignals(False)

    def _on_active_doc_changed(self, index: int) -> None:
        if index < 0:
            return
        path_str = self.combo_active_doc.itemData(index)
        if not path_str or (self.pdf_reader and str(self.pdf_reader.pdf_path) == path_str):
            return
        self.load_pdf(path_str)

    def _on_open_pdf_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择试卷 PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.load_pdf(file_path)

    def _on_page_changed(self, page_index: int) -> None:
        if self.pdf_reader:
            page_info = self.pdf_reader.get_page_info(page_index)
            self.statusBar().showMessage(
                f"当前第 {page_index + 1} 页 / 共 {self.pdf_reader.page_count} 页 "
                f"(尺寸: {int(page_info.width)}×{int(page_info.height)} pt, 类型: {page_info.page_type.value})",
                2000,
            )
        self._update_viewer_overlays()

    def _on_run_analysis(self) -> None:
        """Trigger question segmentation pipeline in background worker."""
        if not self.pdf_reader:
            return

        pid = KeyStorage.get_default_provider_id()
        cfg = KeyStorage.get_provider_config(pid) or {}
        has_key = bool(cfg.get("api_key"))

        provider = None
        if has_key:
            try:
                provider = ProviderFactory.get_active_provider()
            except Exception as e:
                QMessageBox.warning(self, "AI 服务商构建失败", f"初始化 {pid} 失败: {e}")
                return
        else:
            preset = PROVIDER_PRESETS.get(pid, {})
            disp_name = preset.get("display_name", pid)
            reply = QMessageBox.question(
                self,
                "API Key 未配置",
                f"当前激活的 AI 服务商【{disp_name}】尚未设置 API Key。\n\n"
                "• 点击【是】：前往设置窗口配置 API Key\n"
                "• 点击【否】：使用本地规则与文本启发式分析",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_open_settings()
                return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        total_steps = self.pdf_reader.page_count + 3
        progress_dlg = QProgressDialog("正在启动试卷切分流水线...", "取消", 0, total_steps, self)
        progress_dlg.setWindowTitle("ExamSplit AI 分析中")
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)

        self.analysis_worker = AnalysisWorker(
            reader=self.pdf_reader,
            provider=provider,
            project_id=self.pdf_reader.file_hash[:16],
            parent=self,
        )

        def on_progress(cur, tot, msg):
            progress_dlg.setMaximum(tot)
            progress_dlg.setValue(cur)
            progress_dlg.setLabelText(msg)

        def on_finished(questions: List[Question]):
            progress_dlg.close()
            for q in questions:
                if not q.source_pdf_path and self.pdf_reader:
                    q.source_pdf_path = str(self.pdf_reader.pdf_path)
                if not q.source_paper_title and self.pdf_reader:
                    q.source_paper_title = self.pdf_reader.pdf_path.stem
                if not q.original_display_number:
                    q.original_display_number = q.display_number

            self.questions = questions
            self._populate_question_list()
            QMessageBox.information(
                self,
                "分析完成",
                f"成功完成试卷智能拆题分析！\n\n"
                f"• 共识别题目: {len(questions)} 道\n"
                f"• 包含跨页题: {sum(1 for q in questions if q.continuation)} 道\n"
                f"• 待复核题目: {sum(1 for q in questions if q.review_required)} 道",
            )

        def on_error(err_msg: str):
            progress_dlg.close()
            QMessageBox.critical(self, "分析出错", f"试题切分流水线执行失败:\n{err_msg}")

        self.analysis_worker.progress.connect(on_progress)
        self.analysis_worker.finished.connect(on_finished)
        self.analysis_worker.error.connect(on_error)
        progress_dlg.canceled.connect(self.analysis_worker.terminate)

        self.analysis_worker.start()

    def _populate_question_list(self) -> None:
        """Populate the left question list widget with checkboxes and badges."""
        self.question_list_widget.blockSignals(True)
        self.question_list_widget.clear()

        for q in self.questions:
            type_name = QUESTION_TYPE_NAMES.get(q.question_type, "题目")
            if q.segments:
                pages = sorted({s.page_index + 1 for s in q.segments})
                page_str = f"P{pages[0]}-{pages[-1]}" if len(pages) > 1 else f"P{pages[0]}"
            else:
                page_str = "P?"

            badge = " ⚠️待查" if q.review_required else ""
            cont_badge = " [跨页]" if q.continuation else ""
            mod_badge = " [已调]" if q.user_modified else ""
            title = f"第 {q.display_number} 题  [{type_name}]  ({page_str}){cont_badge}{mod_badge}{badge}"

            item = QListWidgetItem(title)
            item.setCheckState(Qt.CheckState.Checked if q.selected else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, q.id)
            if q.review_required:
                item.setForeground(QBrush(QColor("#F59E0B")))
            else:
                item.setForeground(QBrush(QColor("#F1F5F9")))

            self.question_list_widget.addItem(item)

        self.question_list_widget.blockSignals(False)
        self._update_counts_indicator()
        self._update_viewer_overlays()
        self._filter_question_list()

        if self.selected_question and self.selected_question not in self.questions:
            self.selected_question = None

        if self.question_list_widget.count() > 0 and not self.selected_question:
            self.question_list_widget.setCurrentRow(0)
        elif self.question_list_widget.count() == 0:
            self._clear_detail_panel()

    def _filter_question_list(self) -> None:
        """Filter question list items based on search text and category dropdown."""
        query = self.search_edit.text().strip().lower()
        filter_cat = self.combo_filter.currentText()

        for i in range(self.question_list_widget.count()):
            item = self.question_list_widget.item(i)
            qid = item.data(Qt.ItemDataRole.UserRole)
            q = next((x for x in self.questions if x.id == qid), None)
            if not q:
                continue

            matches_search = (
                not query
                or query in q.display_number.lower()
                or query in QUESTION_TYPE_NAMES.get(q.question_type, "").lower()
            )

            matches_cat = True
            if "全部" in filter_cat:
                matches_cat = True
            elif "选择" in filter_cat:
                matches_cat = ("选择" in QUESTION_TYPE_NAMES.get(q.question_type, ""))
            elif "填空" in filter_cat:
                matches_cat = ("填空" in QUESTION_TYPE_NAMES.get(q.question_type, ""))
            elif "解答" in filter_cat:
                matches_cat = ("解答" in QUESTION_TYPE_NAMES.get(q.question_type, "") or "计算" in QUESTION_TYPE_NAMES.get(q.question_type, ""))
            elif "待复核" in filter_cat:
                matches_cat = q.review_required
            elif "跨页" in filter_cat:
                matches_cat = q.continuation

            item.setHidden(not (matches_search and matches_cat))

    def _update_viewer_overlays(self) -> None:
        """Filter segments belonging to current page and draw them on PDFViewer."""
        if not self.pdf_reader:
            return

        cur_page = self.pdf_viewer.current_page_index
        segments_meta = []
        selected_qid = self.selected_question.id if self.selected_question else None

        if self.questions:
            for q in self.questions:
                for seg in q.segments:
                    if seg.page_index == cur_page:
                        segments_meta.append({
                            "question_id": q.id,
                            "segment_id": seg.id,
                            "display_number": q.display_number,
                            "question_type": QUESTION_TYPE_NAMES.get(q.question_type, "题"),
                            "normalized_bbox": seg.normalized_bbox,
                            "review_required": q.review_required,
                        })

        self.pdf_viewer.set_page_overlays(segments_meta, selected_question_id=selected_qid)

    def _on_question_selection_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        """Handle selection change in the left question list widget."""
        if not current:
            self.selected_question = None
            self._clear_detail_panel()
            return

        qid = current.data(Qt.ItemDataRole.UserRole)
        q = next((item for item in self.questions if item.id == qid), None)
        if not q:
            return

        self._updating_details = True
        self.selected_question = q
        type_name = QUESTION_TYPE_NAMES.get(q.question_type, str(q.question_type))
        idx = self.combo_q_type.findText(type_name)
        if idx >= 0:
            self.combo_q_type.setCurrentIndex(idx)
        else:
            if q.is_large_question():
                self.combo_q_type.setCurrentText("大题")
            else:
                self.combo_q_type.setCurrentText("小题")

        self.lbl_q_number.setText(f"第 {q.display_number} 题")
        self.lbl_q_source_paper.setText(q.source_paper_title or (self.pdf_reader.pdf_path.stem if self.pdf_reader else "未知"))

        if q.segments:
            pages = sorted({s.page_index + 1 for s in q.segments})
            page_text = f"第 {pages[0]} ~ {pages[-1]} 页 (跨页题)" if len(pages) > 1 else f"第 {pages[0]} 页"
        else:
            page_text = "未知"
        self.lbl_q_page.setText(page_text)

        self.lbl_q_confidence.setText(f"{q.confidence * 100:.1f}%")
        self.lbl_q_status.setText(q.status.value if hasattr(q.status, "value") else str(q.status))

        if q.review_required:
            reasons_str = "、".join(q.reason_codes) if q.reason_codes else "结构异常或断号"
            self.lbl_q_reasons.setText(f"⚠️ 待人工复核提示: {reasons_str}")
            self.lbl_q_reasons.setVisible(True)
            self.btn_confirm_question.setEnabled(True)
        else:
            self.lbl_q_reasons.setVisible(False)
            self.btn_confirm_question.setEnabled(False)

        self.btn_merge_prev.setEnabled(self.questions.index(q) > 0)
        self.btn_delete_q.setEnabled(True)
        self._update_basket_button_state()
        self._updating_details = False

        # Synchronize viewer
        if q.segments:
            first_seg = q.segments[0]
            if first_seg.page_index != self.pdf_viewer.current_page_index:
                self.pdf_viewer.set_current_page(first_seg.page_index)
            self.pdf_viewer.focus_bbox(first_seg.normalized_bbox)
            self.pdf_viewer.highlight_question(q.id)

    def _on_viewer_segment_selected(self, question_id: str) -> None:
        """Select list item corresponding to the overlay clicked in the viewer canvas."""
        for i in range(self.question_list_widget.count()):
            item = self.question_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == question_id:
                self.question_list_widget.setCurrentItem(item)
                break

    def _on_segment_resized(self, question_id: str, segment_id: str, new_bbox: tuple) -> None:
        """Persist adjusted bounding box from interactive drag handles."""
        q = next((x for x in self.questions if x.id == question_id), None)
        if not q:
            return

        seg = next((s for s in q.segments if s.id == segment_id), None)
        if not seg:
            return

        seg.normalized_bbox = new_bbox
        seg.user_modified = True
        q.user_modified = True
        q.status = QuestionStatus.USER_MODIFIED

        # Re-calculate pdf_bbox
        if self.pdf_reader and seg.page_index < self.pdf_reader.page_count:
            p_info = self.pdf_reader.get_page_info(seg.page_index)
            p_rect = normalized_to_pdf_rect((0, 0, p_info.width, p_info.height), new_bbox)
            seg.pdf_bbox = (p_rect.x0, p_rect.y0, p_rect.x1, p_rect.y1)

        # Persist to database
        if self.pdf_reader:
            save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

        self.statusBar().showMessage(f"已微调并保存第 {q.display_number} 题切分边界", 2000)

    def _on_viewer_context_action(self, action_name: str, question_id: str) -> None:
        if action_name == "confirm":
            self._on_confirm_question()
        elif action_name == "delete":
            self._on_delete_question(question_id)
        elif action_name == "merge":
            self._on_merge_with_previous(question_id)

    def _on_list_context_menu(self, pos) -> None:
        item = self.question_list_widget.itemAt(pos)
        if not item:
            return

        qid = item.data(Qt.ItemDataRole.UserRole)
        q = next((x for x in self.questions if x.id == qid), None)
        if not q:
            return

        menu = QMenu(self)
        act_confirm = menu.addAction("✓ 确认此题无误")
        act_merge = menu.addAction("🔗 与上一题合并为跨页题")
        act_delete = menu.addAction("🗑️ 删除此题目")

        idx = self.questions.index(q)
        act_merge.setEnabled(idx > 0)

        chosen = menu.exec(self.question_list_widget.mapToGlobal(pos))
        if chosen == act_confirm:
            self._on_confirm_question()
        elif chosen == act_merge:
            self._on_merge_with_previous(qid)
        elif chosen == act_delete:
            self._on_delete_question(qid)

    def _on_confirm_question(self) -> None:
        """Confirm that the current question's boundaries and metadata are accurate."""
        if not self.selected_question:
            return

        self.selected_question.review_required = False
        self.selected_question.status = QuestionStatus.USER_CONFIRMED
        self.selected_question.reason_codes.clear()

        cur_item = self.question_list_widget.currentItem()
        if cur_item:
            type_name = QUESTION_TYPE_NAMES.get(self.selected_question.question_type, "题目")
            if self.selected_question.segments:
                pages = sorted({s.page_index + 1 for s in self.selected_question.segments})
                page_str = f"P{pages[0]}-{pages[-1]}" if len(pages) > 1 else f"P{pages[0]}"
            else:
                page_str = "P?"
            cont_badge = " [跨页]" if self.selected_question.continuation else ""
            mod_badge = " [已调]" if self.selected_question.user_modified else ""
            cur_item.setText(f"第 {self.selected_question.display_number} 题  [{type_name}]  ({page_str}){cont_badge}{mod_badge}")
            cur_item.setForeground(QBrush(QColor("#F1F5F9")))

        self.lbl_q_status.setText("USER_CONFIRMED")
        self.lbl_q_reasons.setVisible(False)
        self.btn_confirm_question.setEnabled(False)

        self._update_viewer_overlays()
        if self.pdf_reader:
            save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

        self.statusBar().showMessage(f"已确认第 {self.selected_question.display_number} 题正确无误", 2000)

    def _on_delete_question(self, question_id: str) -> None:
        """Remove question item."""
        q = next((x for x in self.questions if x.id == question_id), None)
        if not q:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除第 {q.display_number} 题选框吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.questions.remove(q)
        if self.selected_question == q:
            self.selected_question = None
            self._clear_detail_panel()

        self._populate_question_list()
        self._update_viewer_overlays()
        if not self.questions:
            self.pdf_viewer.clear_overlays()

        if self.pdf_reader:
            save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

        self.statusBar().showMessage(f"已删除第 {q.display_number} 题", 2000)

    def _on_merge_with_previous(self, question_id: str) -> None:
        """Merge current question into preceding question as continuation segment."""
        idx = next((i for i, x in enumerate(self.questions) if x.id == question_id), -1)
        if idx <= 0:
            return

        curr_q = self.questions[idx]
        prev_q = self.questions[idx - 1]

        for s in curr_q.segments:
            s.question_id = prev_q.id
            prev_q.segments.append(s)

        prev_q.continuation = True
        prev_q.user_modified = True
        self.questions.remove(curr_q)
        self.selected_question = prev_q

        self._populate_question_list()
        if self.pdf_reader:
            save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

        self.statusBar().showMessage(f"已将第 {curr_q.display_number} 题合并至第 {prev_q.display_number} 题", 2000)

    def _on_add_new_question(self) -> None:
        """Add a candidate question box on current page."""
        if not self.pdf_reader:
            return

        cur_p = self.pdf_viewer.current_page_index
        next_num = str(len(self.questions) + 1)

        new_q = Question(
            display_number=next_num,
            question_type=QuestionType.SOLVE,
            segments=[
                QuestionSegment(
                    page_index=cur_p,
                    normalized_bbox=(0.06, 0.25, 0.94, 0.55),
                    user_modified=True,
                )
            ],
            confidence=1.0,
            user_modified=True,
            status=QuestionStatus.USER_MODIFIED,
        )

        p_info = self.pdf_reader.get_page_info(cur_p)
        p_rect = normalized_to_pdf_rect((0, 0, p_info.width, p_info.height), new_q.segments[0].normalized_bbox)
        new_q.segments[0].pdf_bbox = (p_rect.x0, p_rect.y0, p_rect.x1, p_rect.y1)

        self.questions.append(new_q)
        self._populate_question_list()

        # Select new question
        for i in range(self.question_list_widget.count()):
            item = self.question_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == new_q.id:
                self.question_list_widget.setCurrentItem(item)
                break

        if self.pdf_reader:
            save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

        self.statusBar().showMessage(f"已在第 {cur_p + 1} 页新建第 {next_num} 题选框，您可拖动边缘调整大小", 3000)

    def _on_question_item_changed(self, item: QListWidgetItem) -> None:
        qid = item.data(Qt.ItemDataRole.UserRole)
        q = next((item for item in self.questions if item.id == qid), None)
        if q:
            q.selected = (item.checkState() == Qt.CheckState.Checked)
            self._update_counts_indicator()

    def _clear_detail_panel(self) -> None:
        self.lbl_q_number.setText("—")
        self.combo_q_type.blockSignals(True)
        self.combo_q_type.setCurrentIndex(0)
        self.combo_q_type.blockSignals(False)
        self.lbl_q_source_paper.setText("—")
        self.lbl_q_page.setText("—")
        self.lbl_q_confidence.setText("—")
        self.lbl_q_status.setText("待分析")
        self.lbl_q_reasons.setVisible(False)
        self.btn_confirm_question.setEnabled(False)
        self.btn_merge_prev.setEnabled(False)
        self.btn_delete_q.setEnabled(False)
        self.btn_basket_toggle.setEnabled(False)
        self.btn_basket_toggle.setText("🧺 加入试题篮")
        self.btn_basket_toggle.setStyleSheet(BASKET_OUT_STYLE)

    def _on_question_type_changed(self, text: str) -> None:
        if not self.selected_question or self._updating_details:
            return

        self.selected_question.question_type = text
        self.selected_question.user_modified = True
        self.selected_question.status = QuestionStatus.USER_MODIFIED

        cur_item = self.question_list_widget.currentItem()
        if cur_item:
            type_name = QUESTION_TYPE_NAMES.get(self.selected_question.question_type, text)
            if self.selected_question.segments:
                pages = sorted({s.page_index + 1 for s in self.selected_question.segments})
                page_str = f"P{pages[0]}-{pages[-1]}" if len(pages) > 1 else f"P{pages[0]}"
            else:
                page_str = "P?"
            cont_badge = " [跨页]" if self.selected_question.continuation else ""
            mod_badge = " [已调]" if self.selected_question.user_modified else ""
            badge = " ⚠️待查" if self.selected_question.review_required else ""
            cur_item.setText(f"第 {self.selected_question.display_number} 题  [{type_name}]  ({page_str}){cont_badge}{mod_badge}{badge}")

        self._update_viewer_overlays()
        if self.pdf_reader:
            save_project_questions(self.pdf_reader.file_hash[:16], self.questions)

        if GLOBAL_BASKET.contains(self.selected_question.id):
            GLOBAL_BASKET.add_question(self.selected_question)

        self.statusBar().showMessage(f"已将第 {self.selected_question.display_number} 题题型设为: {text}", 2000)

    def _on_toggle_basket(self) -> None:
        if not self.selected_question:
            return
        if GLOBAL_BASKET.contains(self.selected_question.id):
            GLOBAL_BASKET.remove_question(self.selected_question.id)
            self.statusBar().showMessage(f"已从试题篮移除第 {self.selected_question.display_number} 题", 2000)
        else:
            GLOBAL_BASKET.add_question(self.selected_question)
            self.statusBar().showMessage(f"已将第 {self.selected_question.display_number} 题加入试题篮", 2000)
        self._update_basket_button_state()

    def _update_basket_button_state(self) -> None:
        if not self.selected_question:
            self.btn_basket_toggle.setEnabled(False)
            self.btn_basket_toggle.setText("🧺 加入试题篮")
            self.btn_basket_toggle.setStyleSheet(BASKET_OUT_STYLE)
            return

        self.btn_basket_toggle.setEnabled(True)
        if GLOBAL_BASKET.contains(self.selected_question.id):
            self.btn_basket_toggle.setText("🧺 从试题篮移除")
            self.btn_basket_toggle.setStyleSheet(BASKET_IN_STYLE)
        else:
            self.btn_basket_toggle.setText("🧺 加入试题篮")
            self.btn_basket_toggle.setStyleSheet(BASKET_OUT_STYLE)

    def _update_basket_badge(self) -> None:
        count = GLOBAL_BASKET.count()
        self.tb_basket.setText(f"🧺 组卷试题篮 ({count})")
        if self.selected_question:
            self._update_basket_button_state()

    def _on_open_basket(self) -> None:
        dlg = QuestionBasketDialog(parent=self)
        dlg.exec()

    def _on_open_batch_analysis(self, initial_paths: Optional[List[Path]] = None) -> None:
        pid = KeyStorage.get_default_provider_id()
        cfg = KeyStorage.get_provider_config(pid) or {}
        has_key = bool(cfg.get("api_key"))

        provider = None
        if has_key:
            try:
                provider = ProviderFactory.get_active_provider()
            except Exception as e:
                logger.warning(f"Batch analysis provider creation error: {e}")

        dlg = BatchAnalysisDialog(provider=provider, initial_paths=initial_paths, parent=self)
        dlg.batch_completed.connect(self._on_batch_analysis_completed)
        dlg.exec()

    def _on_batch_analysis_completed(self, results: Dict[str, List[Question]]) -> None:
        if not results:
            return
        for pdf_path_str in results.keys():
            p = Path(pdf_path_str)
            if pdf_path_str not in self.opened_documents and p.is_file():
                try:
                    self.opened_documents[pdf_path_str] = PDFReader(p)
                    self._sync_doc_switcher(pdf_path_str)
                except Exception as e:
                    logger.warning(f"Could not open reader for {pdf_path_str}: {e}")

        if not self.pdf_reader and results:
            first_path = next(iter(results.keys()))
            self.load_pdf(first_path)

    def _on_batch_import_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择需要批量导入的试卷 PDF",
            "",
            "PDF 文件 (*.pdf);;所有文件 (*.*)",
        )
        if files:
            paths = [Path(f) for f in files]
            self._on_open_batch_analysis(initial_paths=paths)

    def _on_select_all(self) -> None:
        self.question_list_widget.blockSignals(True)
        for i in range(self.question_list_widget.count()):
            item = self.question_list_widget.item(i)
            item.setCheckState(Qt.CheckState.Checked)
        self.question_list_widget.blockSignals(False)

        for q in self.questions:
            q.selected = True
        self._update_counts_indicator()

    def _on_invert_selection(self) -> None:
        self.question_list_widget.blockSignals(True)
        for i in range(self.question_list_widget.count()):
            item = self.question_list_widget.item(i)
            new_state = (
                Qt.CheckState.Unchecked
                if item.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            item.setCheckState(new_state)
            qid = item.data(Qt.ItemDataRole.UserRole)
            q = next((x for x in self.questions if x.id == qid), None)
            if q:
                q.selected = (new_state == Qt.CheckState.Checked)

        self.question_list_widget.blockSignals(False)
        self._update_counts_indicator()

    def _update_counts_indicator(self) -> None:
        total = len(self.questions)
        selected = sum(1 for q in self.questions if q.selected)
        self.status_counts_label.setText(f" | 已识别 {total} 题 | 已选 {selected} 题")
        has_selection = selected > 0
        self.tb_export.setEnabled(has_selection)

    def _on_open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self, provider_id: str) -> None:
        KeyStorage.set_default_provider_id(provider_id)
        self._update_model_indicator()
        self._sync_provider_menu()
        preset = PROVIDER_PRESETS.get(provider_id, {})
        disp_name = preset.get("display_name", provider_id)
        self.statusBar().showMessage(f"已切换并激活 AI 服务商: {disp_name}", 4000)

    def _on_open_local_experiment(self) -> None:
        """Open the experimental local recognition and virtual address localization dialog."""
        from ..experimental.local_recognition.ui import LocalRecognitionExperimentDialog
        dlg = LocalRecognitionExperimentDialog(
            pdf_reader=self.pdf_reader,
            formal_questions=self.questions,
            parent=self,
        )
        dlg.apply_results_requested.connect(self._on_apply_experiment_questions)
        dlg.exec()

    def _on_apply_experiment_questions(self, questions: List[Question]) -> None:
        """Handle applying experimental questions to the workbench after user confirmation."""
        self.questions = questions
        self._populate_question_list()
        QMessageBox.information(
            self,
            "已应用实验结果",
            f"已成功将实验识别的 {len(questions)} 道题目载入当前工作台！\n"
            "您可以在左侧列表与中间画布中查看和手动微调题目边界。",
        )

    def _on_export_clicked(self) -> None:
        """Launch the Export Dialog to generate lossless A4 PDF."""
        if not self.pdf_reader:
            return

        selected_qs = [q for q in self.questions if q.selected]
        if not selected_qs:
            QMessageBox.warning(self, "未选题目", "请先在左侧列表中勾选至少一道要导出的试题。")
            return

        dlg = ExportDialog(self.pdf_reader.file_path, self.questions, self)
        dlg.exec()

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 ExamSplit AI",
            "ExamSplit AI —— 试卷 PDF 智能拆题与选题导出系统\n"
            "版本: v0.2.0 (全功能版)\n\n"
            "• 原生 PDF 矢量与高清图无损裁剪\n"
            "• 多模态 AI 视觉结构定位与题号跨页解析\n"
            "• 交互式边缘手柄高精微调\n"
            "• A4 单题一页与紧凑排版双模式无损输出",
        )

    # Window-wide Drag & Drop
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
                self.load_pdf(file_path)
                event.acceptProposedAction()
                return
        event.ignore()

    def closeEvent(self, event) -> None:
        for r in self.opened_documents.values():
            try:
                r.close()
            except Exception:
                pass
        if self.pdf_reader:
            try:
                self.pdf_reader.close()
            except Exception:
                pass
        super().closeEvent(event)

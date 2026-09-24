"""Interactive PySide6 Dialog for Local Small-Model Exam Question Segmentation.

Implements UI workbench for:
- Configuring local model endpoints (e.g. Ollama qwen2.5vl:3b or llama-server)
- Selecting pipeline mode (Normal with VLM review, Fast rules-only)
- Running local analysis across single or all pages
- Inspecting detected elements, markers, options, and candidate boundaries
- Comparing results against the formal cloud baseline
- Safely applying experimental results to the main project workbench
"""

from typing import Dict, List, Optional
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.question import Question
from app.pdf.reader import PDFReader
from ..local_ai.config import LocalModelConfig, get_default_config, get_models_dir, scan_local_models
from ..local_ai.local_vlm import OpenAILocalVLMProvider
from ..local_ai.types import LocalPageAnalysis
from .service import LocalAnalysisService


class LocalAnalysisWorker(QThread):
    """Background worker executing local exam analysis without blocking the GUI."""

    progress = Signal(int, int, str)
    finished = Signal(object, object)  # (List[Question], Dict[int, LocalPageAnalysis])
    error = Signal(str)

    def __init__(
        self,
        service: LocalAnalysisService,
        pdf_path: str,
        page_indices: Optional[List[int]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.pdf_path = pdf_path
        self.page_indices = page_indices

    def run(self) -> None:
        try:
            def _cb(cur: int, tot: int, msg: str) -> None:
                self.progress.emit(cur, tot, msg)

            questions, analyses = self.service.process_pdf(
                pdf_path=self.pdf_path,
                page_indices=self.page_indices,
                progress_callback=_cb,
            )
            self.finished.emit(questions, analyses)
        except Exception as e:
            self.error.emit(str(e))


class LocalRecognitionExperimentDialog(QDialog):
    """Workbench dialog for local small-model exam segmentation experiments."""

    apply_results_requested = Signal(list)  # List[Question]

    def __init__(
        self,
        pdf_reader: Optional[PDFReader] = None,
        formal_questions: Optional[List[Question]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pdf_reader = pdf_reader
        self.formal_questions = formal_questions or []
        self.extracted_questions: List[Question] = []
        self.page_analyses: Dict[int, LocalPageAnalysis] = {}
        self.worker: Optional[LocalAnalysisWorker] = None

        self.setWindowTitle("🧪 本地轻量模型题目切分实验仪表盘")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(980, 680)
        self.setMinimumSize(640, 420)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Header description and actions
        h_header = QHBoxLayout()
        lbl_desc = QLabel(
            "<b>本地轻量级模型流水线实验</b>：基于主流文档解析架构 "
            "（PyMuPDF 原生版面/文本 + 题号图与双栏拓扑 + 几何边界求解 + 本地小 VLM 疑难复核），"
            "完全离线运行，切除题目边界后可直接导入工作区无损导出。"
        )
        lbl_desc.setWordWrap(True)
        h_header.addWidget(lbl_desc, stretch=1)

        btn_guide = QPushButton("📖 模型使用指引")
        btn_guide.setFixedHeight(30)
        btn_guide.setStyleSheet("background-color: #E0E7FF; color: #3730A3; font-weight: bold; border-radius: 4px; padding: 0 8px;")
        btn_guide.clicked.connect(self._on_show_guide)
        h_header.addWidget(btn_guide)

        btn_open_models = QPushButton("📂 打开 models 目录")
        btn_open_models.setFixedHeight(30)
        btn_open_models.setStyleSheet("background-color: #F3F4F6; color: #1F2937; border-radius: 4px; padding: 0 8px;")
        btn_open_models.clicked.connect(self._on_open_models_dir)
        h_header.addWidget(btn_open_models)

        main_layout.addLayout(h_header)

        # Configuration Box
        cfg_box = QGroupBox("⚙️ 本地模型与服务配置")
        cfg_layout = QHBoxLayout(cfg_box)

        # Endpoint & Model
        cfg_form1 = QVBoxLayout()
        h_ep = QHBoxLayout()
        h_ep.addWidget(QLabel("服务端点:"))
        self.txt_endpoint = QLineEdit("http://127.0.0.1:11434/v1")
        h_ep.addWidget(self.txt_endpoint)
        cfg_form1.addLayout(h_ep)

        h_model = QHBoxLayout()
        h_model.addWidget(QLabel("VLM 模型:"))
        self.txt_model = QLineEdit("qwen2.5vl:3b")
        h_model.addWidget(self.txt_model)
        self.btn_test_conn = QPushButton("测试连接")
        self.btn_test_conn.clicked.connect(self._on_test_connection)
        h_model.addWidget(self.btn_test_conn)
        cfg_form1.addLayout(h_model)

        # Detected models in models/ folder
        h_local = QHBoxLayout()
        h_local.addWidget(QLabel("检测 models/:"))
        self.combo_local_models = QComboBox()
        self.combo_local_models.currentIndexChanged.connect(self._on_local_model_selected)
        h_local.addWidget(self.combo_local_models, stretch=1)
        self.btn_refresh_models = QPushButton("🔄")
        self.btn_refresh_models.setToolTip("重新扫描 models/ 目录中的模型")
        self.btn_refresh_models.clicked.connect(self._refresh_local_models)
        h_local.addWidget(self.btn_refresh_models)
        cfg_form1.addLayout(h_local)

        cfg_layout.addLayout(cfg_form1, stretch=2)

        # Mode & Scope
        cfg_form2 = QVBoxLayout()
        h_mode = QHBoxLayout()
        h_mode.addWidget(QLabel("运行模式:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("标准复核模式 (规则 + 疑难VLM复核)", "normal")
        self.combo_mode.addItem("极速规则模式 (仅本地规则，0秒VLM延迟)", "fast")
        h_mode.addWidget(self.combo_mode)
        cfg_form2.addLayout(h_mode)

        h_scope = QHBoxLayout()
        h_scope.addWidget(QLabel("处理范围:"))
        self.rdo_curr_page = QRadioButton("当前页")
        self.rdo_all_pages = QRadioButton("整套试卷")
        self.rdo_all_pages.setChecked(True)
        self.scope_group = QButtonGroup(self)
        self.scope_group.addButton(self.rdo_curr_page)
        self.scope_group.addButton(self.rdo_all_pages)
        h_scope.addWidget(self.rdo_curr_page)
        h_scope.addWidget(self.rdo_all_pages)
        cfg_form2.addLayout(h_scope)
        cfg_layout.addLayout(cfg_form2, stretch=2)

        main_layout.addWidget(cfg_box)

        # Progress bar & Start Button
        h_ctrl = QHBoxLayout()
        self.btn_start = QPushButton("🚀 开始本地切题分析")
        self.btn_start.setFixedHeight(36)
        self.btn_start.setStyleSheet("font-weight: bold; background-color: #2563EB; color: white; border-radius: 4px;")
        self.btn_start.clicked.connect(self._on_start_analysis)
        h_ctrl.addWidget(self.btn_start)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        h_ctrl.addWidget(self.progress_bar, stretch=1)
        main_layout.addLayout(h_ctrl)

        self.lbl_status = QLabel("就绪")
        main_layout.addWidget(self.lbl_status)

        # Splitter: Left Table + Right Detail Log
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Results Table
        self.tbl_results = QTableWidget()
        self.tbl_results.setColumnCount(6)
        self.tbl_results.setHorizontalHeaderLabels(["题号", "题型", "页码", "置信度", "跨页", "归一化边界 (x1, y1, x2, y2)"])
        self.tbl_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl_results.horizontalHeader().setStretchLastSection(True)
        self.tbl_results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        splitter.addWidget(self.tbl_results)

        # Right Summary / Log Pane
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setPlaceholderText("分析详情与版面结构将在识别后显示于此...")
        splitter.addWidget(self.txt_summary)
        splitter.setSizes([620, 340])

        main_layout.addWidget(splitter, stretch=1)

        # Bottom Buttons
        h_bottom = QHBoxLayout()
        self.btn_compare = QPushButton("📊 对比正式识别基准")
        self.btn_compare.clicked.connect(self._on_compare_results)
        h_bottom.addWidget(self.btn_compare)

        h_bottom.addStretch()

        self.btn_apply = QPushButton("✅ 应用实验结果到工作区")
        self.btn_apply.setFixedHeight(34)
        self.btn_apply.setStyleSheet("font-weight: bold; background-color: #16A34A; color: white; border-radius: 4px;")
        self.btn_apply.clicked.connect(self._on_apply_results)
        self.btn_apply.setEnabled(False)
        h_bottom.addWidget(self.btn_apply)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        h_bottom.addWidget(btn_close)

        main_layout.addLayout(h_bottom)
        self._refresh_local_models()

    def _refresh_local_models(self) -> None:
        """Scan models/ directory and populate the combo box."""
        self.combo_local_models.blockSignals(True)
        self.combo_local_models.clear()
        models = scan_local_models()
        if not models:
            self.combo_local_models.addItem("（未检测到模型，可点击右上方指引下载）", None)
        else:
            self.combo_local_models.addItem(f"检测到 {len(models)} 个模型项（点击切换）", None)
            for m in models:
                self.combo_local_models.addItem(f"📦 {m['name']} ({m['size_str']})", m)
        self.combo_local_models.blockSignals(False)

    def _on_local_model_selected(self, index: int) -> None:
        """Handle selection of local model from models/ directory."""
        data = self.combo_local_models.currentData()
        if not data or not isinstance(data, dict):
            return
        m_name = data.get("name", "")
        if "qwen2.5" in m_name.lower():
            self.txt_model.setText("qwen2.5vl:3b")
        else:
            self.txt_model.setText(m_name)
        self.lbl_status.setText(f"已选中本地模型: {data.get('filename')}。可通过 llama-server 启动或使用 Ollama 对应模型。")

    def _on_open_models_dir(self) -> None:
        """Open models directory in system file manager."""
        models_dir = get_models_dir()
        models_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(models_dir)))

    def _on_show_guide(self) -> None:
        """Show dialog explaining how to download and run local models."""
        dlg = QDialog(self)
        dlg.setWindowTitle("📖 本地模型下载与运行指引")
        dlg.resize(680, 520)
        vbox = QVBoxLayout(dlg)
        vbox.setSpacing(10)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setHtml("""
        <h3>💡 ExamSplit AI 本地离线切题与模型使用指引</h3>
        <p>ExamSplit AI 支持以下三种本地运行方式，可根据您的环境灵活选用：</p>
        <hr>
        <h4>【方式一：极速规则模式】（最推荐，0 显存，0 门槛，0 秒延迟）</h4>
        <ul>
          <li><b>无需下载任何模型</b>，不占用显存与内存！</li>
          <li>在运行模式中选择<b>【极速规则模式 (仅本地规则，0秒VLM延迟)】</b>。</li>
          <li>内置工业级版面拓扑与几何边界求解引擎，90% 以上标准试卷（考研数学、高考数学等）均可秒级 100% 精准切分！</li>
        </ul>
        <hr>
        <h4>【方式二：Ollama 一键托管运行】（推荐拥有独显的用户）</h4>
        <ol>
          <li>从官网下载安装 <a href="https://ollama.com">Ollama</a>；</li>
          <li>打开系统终端或 PowerShell 执行：<br>
            <code>ollama run qwen2.5vl:3b</code>
          </li>
          <li>启动后，在当前仪表盘中保持默认端点 <code>http://127.0.0.1:11434/v1</code>，点击<b>【测试连接】</b>即可直连！</li>
        </ol>
        <hr>
        <h4>【方式三：放入 models/ 目录并通过 llama-server 启动】</h4>
        <ol>
          <li>从 HuggingFace 或 ModelScope 魔搭社区搜索并下载 GGUF 视觉模型（推荐 <b>Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf</b>）；</li>
          <li>将下载好的 <code>.gguf</code> 文件直接放入本软件根目录的 <b><code>models/</code></b> 文件夹中；</li>
          <li>使用 llama.cpp 自带的 <code>llama-server</code> 启动（支持 Windows / Linux / macOS）：<br>
            <code>llama-server -m models/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf --port 11434 -ngl 99 -c 4096</code>
          </li>
          <li>启动后在仪表盘中点击【测试连接】即可对接本地加速推理。</li>
        </ol>
        """)
        vbox.addWidget(txt, stretch=1)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("📂 打开本地 models/ 目录")
        btn_open.clicked.connect(self._on_open_models_dir)
        btn_row.addWidget(btn_open)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        vbox.addLayout(btn_row)

        dlg.exec()

    def _get_current_config(self) -> LocalModelConfig:
        cfg = get_default_config()
        cfg.endpoint_url = self.txt_endpoint.text().strip()
        cfg.vlm_model = self.txt_model.text().strip()
        cfg.mode = self.combo_mode.currentData()
        return cfg

    def _on_test_connection(self) -> None:
        cfg = self._get_current_config()
        provider = OpenAILocalVLMProvider(cfg)
        self.lbl_status.setText("正在测试本地服务连接...")
        is_alive = provider.check_health()
        if is_alive:
            QMessageBox.information(
                self,
                "连接成功",
                f"已成功连通本地模型服务！\n端点: {cfg.endpoint_url}\n模型: {cfg.vlm_model}",
            )
            self.lbl_status.setText("本地 VLM 服务连接正常")
        else:
            QMessageBox.warning(
                self,
                "连接不可用",
                f"无法连通本地端点: {cfg.endpoint_url}\n"
                "请检查 Ollama 或 llama-server 服务是否在后台运行。\n"
                "（提示：您可切换为【极速规则模式】，无需 VLM 服务即可直接本地运行）",
            )
            self.lbl_status.setText("本地 VLM 未响应")

    def _on_start_analysis(self) -> None:
        if not self.pdf_reader or not self.pdf_reader.file_path:
            QMessageBox.warning(self, "提示", "请先在主界面打开需要处理的 PDF 试卷。")
            return

        cfg = self._get_current_config()
        service = LocalAnalysisService(config=cfg)

        pages = None
        if self.rdo_curr_page.isChecked():
            pages = [self.pdf_reader.current_page]

        self.btn_start.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("准备开始本地切题流水线...")

        self.worker = LocalAnalysisWorker(
            service=service,
            pdf_path=self.pdf_reader.file_path,
            page_indices=pages,
            parent=self,
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_progress(self, cur: int, tot: int, msg: str) -> None:
        pct = int((cur / max(tot, 1)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(msg)

    def _on_worker_finished(self, questions: List[Question], analyses: Dict[int, LocalPageAnalysis]) -> None:
        self.extracted_questions = questions
        self.page_analyses = analyses
        self.btn_start.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText(f"本地分析完成！共识别 {len(questions)} 道题目。")

        self._populate_results_table(questions)
        self._populate_summary_pane(questions, analyses)

        if questions:
            self.btn_apply.setEnabled(True)

    def _on_worker_error(self, err_msg: str) -> None:
        self.btn_start.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText(f"分析出错: {err_msg}")
        QMessageBox.critical(self, "本地分析失败", f"处理过程中发生异常:\n{err_msg}")

    def _populate_results_table(self, questions: List[Question]) -> None:
        self.tbl_results.setRowCount(0)
        for q in questions:
            row = self.tbl_results.rowCount()
            self.tbl_results.insertRow(row)

            # Col 0: Question number
            self.tbl_results.setItem(row, 0, QTableWidgetItem(f"第 {q.display_number} 题"))

            # Col 1: Type
            q_type_str = q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type)
            self.tbl_results.setItem(row, 1, QTableWidgetItem(q_type_str))

            # Col 2: Pages
            p_nums = sorted(list(set(s.page_index + 1 for s in q.segments)))
            p_str = ", ".join(f"P{p}" for p in p_nums) if p_nums else "P?"
            self.tbl_results.setItem(row, 2, QTableWidgetItem(p_str))

            # Col 3: Confidence
            self.tbl_results.setItem(row, 3, QTableWidgetItem(f"{q.confidence:.2f}"))

            # Col 4: Continuation
            cont_str = "是" if q.continuation else "否"
            self.tbl_results.setItem(row, 4, QTableWidgetItem(cont_str))

            # Col 5: Bbox
            if q.segments:
                b = q.segments[0].normalized_bbox
                b_str = f"({b[0]:.3f}, {b[1]:.3f}, {b[2]:.3f}, {b[3]:.3f})"
                if len(q.segments) > 1:
                    b_str += f" (+{len(q.segments) - 1}段)"
            else:
                b_str = "N/A"
            self.tbl_results.setItem(row, 5, QTableWidgetItem(b_str))

    def _populate_summary_pane(
        self,
        questions: List[Question],
        analyses: Dict[int, LocalPageAnalysis],
    ) -> None:
        lines = [
            f"<h3>📋 本地识别综合报告</h3>",
            f"• <b>总计识别题目数</b>: {len(questions)} 道",
        ]
        choice_count = sum(1 for q in questions if "choice" in str(q.question_type).lower() or "小题" in str(q.question_type))
        solve_count = sum(1 for q in questions if "solve" in str(q.question_type).lower() or "大题" in str(q.question_type))
        lines.append(f"• <b>题型分布</b>: 小题/选择填空: {choice_count} 道 | 解答大题: {solve_count} 道")

        cross_count = sum(1 for q in questions if q.continuation)
        lines.append(f"• <b>跨页题目</b>: {cross_count} 道")

        lines.append("<hr><h4>📄 页面结构明细:</h4>")
        for p_idx, an in sorted(analyses.items()):
            col_str = "双栏排版" if an.is_two_column else "单栏排版"
            lines.append(
                f"<b>第 {p_idx + 1} 页</b>: {col_str} | "
                f"版面元素: {len(an.layout_elements)} 个 | "
                f"文本行: {len(an.text_blocks)} 行 | "
                f"题号锚点: {len(an.markers)} 个"
            )

        self.txt_summary.setHtml("".join(lines))

    def _on_compare_results(self) -> None:
        if not self.extracted_questions:
            QMessageBox.warning(self, "提示", "请先执行一次本地切题分析。")
            return

        exp_q_nums = set(q.display_number for q in self.extracted_questions)
        formal_q_nums = set(q.display_number for q in self.formal_questions)

        common = exp_q_nums.intersection(formal_q_nums)
        only_exp = exp_q_nums - formal_q_nums
        only_formal = formal_q_nums - exp_q_nums

        def _sort_keys(s):
            return sorted(s, key=lambda x: int(x) if x.isdigit() else 999)

        msg = (
            f"📊 <b>本地实验模型 vs 正式基准对比</b><br><br>"
            f"• 本地实验检测题数: <b>{len(exp_q_nums)}</b> 道<br>"
            f"• 正式识别题数: <b>{len(formal_q_nums)}</b> 道<br>"
            f"• 共同一致题号 ({len(common)}): {', '.join(_sort_keys(common)) or '无'}<br>"
            f"• 仅本地实验检测到 ({len(only_exp)}): {', '.join(_sort_keys(only_exp)) or '无'}<br>"
            f"• 仅正式基准检测到 ({len(only_formal)}): {', '.join(_sort_keys(only_formal)) or '无'}<br>"
        )
        QMessageBox.information(self, "对比分析", msg)

    def _on_apply_results(self) -> None:
        if not self.extracted_questions:
            QMessageBox.warning(self, "提示", "当前没有可应用的试题结果。")
            return

        reply = QMessageBox.question(
            self,
            "确认载入实验切题结果",
            f"确定要将本地实验识别的 <b>{len(self.extracted_questions)}</b> 道题目载入当前工作台吗？\n\n"
            "载入后您可以在主界面画布中直接查看并进行微调，且支持直接高清 A4 导出。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.apply_results_requested.emit(self.extracted_questions)
            self.accept()

    def closeEvent(self, event) -> None:
        """Safely terminate running analysis worker when window is closed."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(1000)
        super().closeEvent(event)

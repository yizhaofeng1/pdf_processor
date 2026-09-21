"""Interactive PySide6 Dialog and Visualization for Local Recognition (VAQL) experiments."""

from typing import Optional, List, Dict, Any
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QLabel,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QRadioButton,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QFileDialog,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont

from .config import LocalVisionConfig
from .types import LocalRecognitionExperimentResult
from .service import LocalRecognitionExperimentService
from .provider import OpenAILocalVisionProvider
from .tiler import Tiler
from .page_table import VirtualPageTable
from ...pdf.reader import PDFReader
from ...models.question import Question


class ExperimentWorker(QThread):
    """Background worker executing the local VLM experiment without freezing the UI."""

    progress = Signal(int, int, str)
    finished = Signal(object)  # LocalRecognitionExperimentResult
    error = Signal(str)

    def __init__(
        self,
        service: LocalRecognitionExperimentService,
        reader: PDFReader,
        mode: str = "virtual_address",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.reader = reader
        self.mode = mode
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            def _cb(cur: int, tot: int, msg: str) -> None:
                self.progress.emit(cur, tot, msg)

            def _cancel() -> bool:
                return self._is_cancelled

            if self.mode == "direct_baseline":
                res = self.service.run_direct_baseline_pipeline(
                    reader=self.reader,
                    progress_callback=_cb,
                    cancel_check=_cancel,
                )
            else:
                res = self.service.run_virtual_address_pipeline(
                    reader=self.reader,
                    progress_callback=_cb,
                    cancel_check=_cancel,
                )

            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class LocalRecognitionExperimentDialog(QDialog):
    """Dedicated workbench dialog for configuring, executing, and evaluating local VAQL experiments."""

    # Emitted when user explicitly chooses to apply experiment results
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
        self.last_result: Optional[LocalRecognitionExperimentResult] = None
        self.worker: Optional[ExperimentWorker] = None

        self.setWindowTitle("🧪 本地识别与虚拟地址寻题实验 (VAQL) - Experimental")
        self.resize(960, 680)
        self._setup_ui()
        self._auto_detect_models()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 1. Experimental Notice Banner
        banner = QLabel(
            "⚠️ <b>实验功能声明</b>：本模块为独立实验验证模块，用于评估本地小型视觉模型结合虚拟地址分页（VAQL）的定位能力。"
            "实验结果仅用于算法测试与对比分析，<b>绝不会自动替换</b>正式云端识别结果。"
        )
        banner.setWordWrap(True)
        banner.setStyleSheet("""
            QLabel {
                background: #1E293B;
                color: #F59E0B;
                border: 1.5px solid #F59E0B;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13.5px;
            }
        """)
        layout.addWidget(banner)

        # 2. Splitter: Left Configuration, Right Results & Logs
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left: Configuration Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)

        # Endpoint & Model Group
        grp_model = QGroupBox("1. 本地模型服务配置 (OpenAI 兼容协议)")
        form_model = QFormLayout(grp_model)

        self.txt_endpoint = QLineEdit("http://127.0.0.1:11434/v1")
        self.txt_endpoint.setPlaceholderText("http://localhost:11434/v1 或 LM Studio / vLLM")
        form_model.addRow("服务地址 (Endpoint):", self.txt_endpoint)

        self.txt_api_key = QLineEdit("")
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("可选，默认不需要")
        form_model.addRow("API Key:", self.txt_api_key)

        model_row = QHBoxLayout()
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.addItems(["qwen2.5vl:3b", "llama3.2-vision:11b", "qwen2.5-vl", "minicpm-v", "custom"])
        self.combo_model.setCurrentText("qwen2.5vl:3b")
        model_row.addWidget(self.combo_model, stretch=1)

        self.btn_fetch_models = QPushButton("🔄 刷新")
        self.btn_fetch_models.clicked.connect(self._on_fetch_models)
        model_row.addWidget(self.btn_fetch_models)

        self.btn_test_conn = QPushButton("🔌 测试连接")
        self.btn_test_conn.clicked.connect(self._on_test_connection)
        model_row.addWidget(self.btn_test_conn)

        form_model.addRow("本地模型:", model_row)
        left_layout.addWidget(grp_model)

        # Algorithm Mode Group
        grp_algo = QGroupBox("2. 实验模式与参数")
        vbox_algo = QVBoxLayout(grp_algo)

        self.rb_vaql = QRadioButton("虚拟地址寻题模式 (VAQL: 粗寻址 + 局部高精精修)")
        self.rb_vaql.setChecked(True)
        self.rb_baseline = QRadioButton("直接本地整页定位 (Direct Local Baseline: 对照基准)")

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_vaql, 1)
        self.mode_group.addButton(self.rb_baseline, 2)
        vbox_algo.addWidget(self.rb_vaql)
        vbox_algo.addWidget(self.rb_baseline)

        # Grid settings
        form_grid = QFormLayout()
        grid_row = QHBoxLayout()

        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(2, 32)
        self.spin_rows.setValue(8)

        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 16)
        self.spin_cols.setValue(4)

        grid_row.addWidget(QLabel("行数:"))
        grid_row.addWidget(self.spin_rows)
        grid_row.addWidget(QLabel("列数:"))
        grid_row.addWidget(self.spin_cols)
        form_grid.addRow("虚拟网格:", grid_row)

        self.spin_neighbor = QSpinBox()
        self.spin_neighbor.setRange(0, 3)
        self.spin_neighbor.setValue(1)
        form_grid.addRow("邻域扩展半径:", self.spin_neighbor)

        self.combo_template = QComboBox()
        self.combo_template.addItem("考研数学 (16道小题+大题，2021新大纲/标准)", "kaoyan_math_16")
        self.combo_template.addItem("考研数学 (14道小题+大题，2010~2020真题)", "kaoyan_math_14")
        self.combo_template.addItem("通用试卷 (无特定先验)", "general")
        form_grid.addRow("试卷先验模板:", self.combo_template)

        self.chk_full_width = QCheckBox("通栏排版自适应 (自动扩展至整页宽度)")
        self.chk_full_width.setChecked(True)
        self.chk_full_width.setToolTip("开启后，单栏试卷候选框将自动拓展至整页宽度 (0.0~1.0)，防止选框仅占1/2宽度。")
        form_grid.addRow("通栏自适应:", self.chk_full_width)

        self.chk_local_refine = QCheckBox("启用局部高分辨率精修 (推荐)")
        self.chk_local_refine.setChecked(True)
        form_grid.addRow("局部精修:", self.chk_local_refine)

        self.chk_grid_overlay = QCheckBox("送检图片叠加网格标线 (推荐开启)")
        self.chk_grid_overlay.setChecked(True)
        self.chk_grid_overlay.setToolTip("在送给本地小模型的图像上绘制清晰的虚拟地址网格标线与标签，极大提升小模型空间寻题精度。")
        form_grid.addRow("网格叠加:", self.chk_grid_overlay)

        vbox_algo.addLayout(form_grid)
        left_layout.addWidget(grp_algo)

        # Execution Buttons
        self.btn_run = QPushButton("🚀 开始实验识别")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: #0284C7;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 15px;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #0369A1;
            }
        """)
        self.btn_run.clicked.connect(self._on_start_experiment)
        left_layout.addWidget(self.btn_run)

        self.btn_cancel = QPushButton("⏹️ 终止实验")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_experiment)
        left_layout.addWidget(self.btn_cancel)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # --- Right: Results, Metrics & Logs ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        right_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("就绪。请选择模式并点击【开始实验识别】。")
        self.lbl_status.setStyleSheet("color: #38BDF8; font-size: 13px;")
        right_layout.addWidget(self.lbl_status)

        # Results Table
        self.tbl_results = QTableWidget(0, 5)
        self.tbl_results.setHorizontalHeaderLabels(["题号", "页码", "识别模式", "置信度", "边界范围 (Normalized)"])
        self.tbl_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_results.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.tbl_results, stretch=1)

        # Metrics Log
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(160)
        self.txt_log.setStyleSheet("background: #0F172A; color: #94A3B8; font-family: monospace; font-size: 12px;")
        right_layout.addWidget(self.txt_log)

        # Bottom Action Bar
        bottom_actions = QHBoxLayout()

        self.btn_preview_grid = QPushButton("🖼️ 查看网格覆盖图")
        self.btn_preview_grid.clicked.connect(self._on_preview_grid)
        bottom_actions.addWidget(self.btn_preview_grid)

        self.btn_compare = QPushButton("📊 与正式结果对比")
        self.btn_compare.clicked.connect(self._on_compare_results)
        bottom_actions.addWidget(self.btn_compare)

        self.btn_apply = QPushButton("📥 应用实验结果到当前项目")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: #10B981;
                color: #FFFFFF;
                font-weight: 700;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.btn_apply.clicked.connect(self._on_apply_results)
        bottom_actions.addWidget(self.btn_apply)

        right_layout.addLayout(bottom_actions)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def _get_current_config(self) -> LocalVisionConfig:
        return LocalVisionConfig(
            endpoint=self.txt_endpoint.text().strip(),
            model=self.combo_model.currentText().strip(),
            api_key=self.txt_api_key.text().strip() or None,
            mode="direct_baseline" if self.rb_baseline.isChecked() else "virtual_address",
            grid_rows=self.spin_rows.value(),
            grid_columns=self.spin_cols.value(),
            neighbor_radius=self.spin_neighbor.value(),
            enable_local_refine=self.chk_local_refine.isChecked(),
            send_grid_overlay=self.chk_grid_overlay.isChecked(),
            exam_template=self.combo_template.currentData() or "kaoyan_math_16",
            full_width_layout=self.chk_full_width.isChecked(),
        )

    def _auto_detect_models(self) -> None:
        """Silently probe endpoint and populate available models if available."""
        try:
            cfg = self._get_current_config()
            provider = OpenAILocalVisionProvider(cfg)
            models = provider.fetch_available_models()
            if models:
                current = self.combo_model.currentText()
                self.combo_model.clear()
                self.combo_model.addItems(models)
                if current in models:
                    self.combo_model.setCurrentText(current)
                elif "qwen2.5vl:3b" in models:
                    self.combo_model.setCurrentText("qwen2.5vl:3b")
                elif models:
                    self.combo_model.setCurrentIndex(0)
        except Exception:
            pass

    def _on_test_connection(self) -> None:
        cfg = self._get_current_config()
        provider = OpenAILocalVisionProvider(cfg)
        self.lbl_status.setText("正在测试端点连接...")
        success, msg = provider.test_connection()
        if success:
            QMessageBox.information(self, "连接成功", msg)
            self.lbl_status.setText(f"端点正常: {msg}")
        else:
            QMessageBox.warning(self, "连接失败", msg)
            self.lbl_status.setText(f"端点连接失败: {msg}")

    def _on_fetch_models(self) -> None:
        cfg = self._get_current_config()
        provider = OpenAILocalVisionProvider(cfg)
        models = provider.fetch_available_models()
        if models:
            self.combo_model.clear()
            self.combo_model.addItems(models)
            QMessageBox.information(self, "获取成功", f"成功获取到 {len(models)} 个可用模型！")
        else:
            QMessageBox.warning(self, "提示", "未获取到模型列表，请确认端点地址是否正确或服务是否已启动。")

    def _on_start_experiment(self) -> None:
        if not self.pdf_reader:
            QMessageBox.warning(self, "提示", "当前未打开任何试卷 PDF，请先在主界面打开试卷。")
            return

        cfg = self._get_current_config()
        service = LocalRecognitionExperimentService(config=cfg)

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.txt_log.clear()
        self.tbl_results.setRowCount(0)

        self.worker = ExperimentWorker(
            service=service,
            reader=self.pdf_reader,
            mode=cfg.mode,
            parent=self,
        )

        def _on_progress(cur: int, tot: int, msg: str) -> None:
            self.progress_bar.setMaximum(tot)
            self.progress_bar.setValue(cur)
            self.lbl_status.setText(msg)
            self.txt_log.append(f"[{cur}/{tot}] {msg}")

        def _on_finished(result: LocalRecognitionExperimentResult) -> None:
            self.last_result = result
            self.btn_run.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.lbl_status.setText(f"实验完成！共识别 {len(result.segments)} 道题目。")

            self._populate_results_table(result)
            self.txt_log.append("\n" + "=" * 40)
            self.txt_log.append(f"实验完成！耗时: {result.metrics.latency_seconds} 秒")
            self.txt_log.append(f"识别题目数: {result.metrics.total_questions_detected}")
            self.txt_log.append(f"总模型调用: {result.metrics.total_calls} 次 (粗定位: {result.metrics.coarse_calls}, 局部: {result.metrics.local_calls})")

            QMessageBox.information(
                self,
                "实验完成",
                f"本地识别实验执行完毕！\n\n"
                f"• 模式: {result.run.mode}\n"
                f"• 识别题目: {len(result.segments)} 道\n"
                f"• 耗时: {result.metrics.latency_seconds:.2f} s\n"
                f"• 调用次数: {result.metrics.total_calls} 次\n\n"
                f"报告已持久化保存在:\ndata/experiments/local_recognition/runs/{result.run.run_id}/",
            )

        def _on_error(err: str) -> None:
            self.btn_run.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText(f"实验出错: {err}")
            self.txt_log.append(f"❌ 出错: {err}")
            QMessageBox.critical(self, "实验出错", f"执行过程发生异常:\n{err}")

        self.worker.progress.connect(_on_progress)
        self.worker.finished.connect(_on_finished)
        self.worker.error.connect(_on_error)
        self.worker.start()

    def _on_cancel_experiment(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.lbl_status.setText("正在取消实验...")
            self.btn_cancel.setEnabled(False)

    def _populate_results_table(self, result: LocalRecognitionExperimentResult) -> None:
        self.tbl_results.setRowCount(0)
        for seg in result.segments:
            row = self.tbl_results.rowCount()
            self.tbl_results.insertRow(row)

            self.tbl_results.setItem(row, 0, QTableWidgetItem(f"第 {seg.question_number} 题"))
            self.tbl_results.setItem(row, 1, QTableWidgetItem(f"P{seg.page_index + 1}"))
            self.tbl_results.setItem(row, 2, QTableWidgetItem(seg.source))
            self.tbl_results.setItem(row, 3, QTableWidgetItem(f"{seg.confidence:.2f}"))
            bbox_str = f"({seg.normalized_bbox[0]:.3f}, {seg.normalized_bbox[1]:.3f}, {seg.normalized_bbox[2]:.3f}, {seg.normalized_bbox[3]:.3f})"
            self.tbl_results.setItem(row, 4, QTableWidgetItem(bbox_str))

    def _on_preview_grid(self) -> None:
        """Render and save a sample grid overlay for the first page."""
        if not self.pdf_reader:
            QMessageBox.warning(self, "提示", "请先打开 PDF 试卷。")
            return

        cfg = self._get_current_config()
        p_info = self.pdf_reader.get_page_info(0)
        table = VirtualPageTable(0, (0.0, 0.0, p_info.width, p_info.height), rows=cfg.grid_rows, columns=cfg.grid_columns)

        coarse_img = Tiler.render_coarse_page(self.pdf_reader, 0, dpi=cfg.coarse_dpi)
        overlay_img = Tiler.add_grid_overlay(coarse_img, table)

        QMessageBox.information(
            self,
            "网格图已生成",
            f"第 1 页虚拟地址覆盖网格已生成在:\n{overlay_img}\n\n您可以在外部图像查看器中打开该文件进行核对。",
        )

    def _on_compare_results(self) -> None:
        """Compare local experimental results against formal baseline."""
        if not self.last_result:
            QMessageBox.warning(self, "提示", "请先运行一次实验识别。")
            return

        exp_count = len(self.last_result.segments)
        formal_count = len(self.formal_questions)

        exp_q_nums = set(s.question_number for s in self.last_result.segments)
        formal_q_nums = set(q.display_number for q in self.formal_questions)

        common = exp_q_nums.intersection(formal_q_nums)
        only_exp = exp_q_nums - formal_q_nums
        only_formal = formal_q_nums - exp_q_nums

        msg = (
            f"📊 <b>实验与正式识别结果对比</b><br><br>"
            f"• 正式识别题数: <b>{formal_count}</b> 道<br>"
            f"• 本地实验题数: <b>{exp_count}</b> 道<br>"
            f"• 共同检测到的题号 ({len(common)}): {', '.join(sorted(common)) or '无'}<br>"
            f"• 仅实验检测到 ({len(only_exp)}): {', '.join(sorted(only_exp)) or '无'}<br>"
            f"• 仅正式检测到 ({len(only_formal)}): {', '.join(sorted(only_formal)) or '无'}<br>"
        )

        QMessageBox.information(self, "对比分析", msg)

    def _on_apply_results(self) -> None:
        """Explicitly apply experiment results to formal project after user confirmation."""
        if not self.last_result or not self.last_result.segments:
            QMessageBox.warning(self, "提示", "当前没有可应用的实验结果，请先成功运行实验。")
            return

        if not self.pdf_reader:
            QMessageBox.warning(self, "提示", "未找到当前打开的试卷。")
            return

        reply = QMessageBox.question(
            self,
            "确认应用实验结果",
            "⚠️ <b>重要提示</b>：\n\n"
            "实验结果不会自动成为正式识别结果。\n"
            "点击【确定】后，将把实验得到的题目边界转换为当前项目的正式试题区域。\n\n"
            "是否继续应用？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            adapted_questions = LocalRecognitionExperimentService.apply_experiment_result_to_questions(
                self.last_result,
                self.pdf_reader,
            )
            self.apply_results_requested.emit(adapted_questions)
            self.accept()

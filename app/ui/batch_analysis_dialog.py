"""Batch Exam Paper Analysis Dialog."""

import logging
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QCheckBox,
    QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from ..models.question import Question
from ..services.detection_service import BatchAnalysisWorker
from ..services.question_basket import GLOBAL_BASKET
from ..pdf.reader import PDFReader
from ..storage.paper_template import PaperTemplateStorage
from .paper_template_dialog import PaperTemplateDialog

logger = logging.getLogger("examsplit.ui.batch_analysis")


class BatchAnalysisDialog(QDialog):
    """Dialog for importing multiple PDFs and executing batch detection in the background."""

    batch_completed = Signal(dict)  # {pdf_path: list[Question]}

    def __init__(self, provider=None, initial_paths: Optional[List[Path]] = None, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.worker: Optional[BatchAnalysisWorker] = None
        self.results: Dict[str, List[Question]] = {}
        self.pdf_paths: List[Path] = []

        self.setWindowTitle("⚡ 试卷批量后台分析")
        self.resize(860, 560)
        self._init_ui()

        if initial_paths:
            self.add_pdf_paths(initial_paths)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header info
        header_layout = QHBoxLayout()
        title_label = QLabel("📚 试卷批量导入与自动结构分析")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.chk_skip_cache = QCheckBox("跳过已有本地缓存的试卷 (已分析过的直接加载，节约AI额度)")
        self.chk_skip_cache.setChecked(True)
        header_layout.addWidget(self.chk_skip_cache)
        layout.addLayout(header_layout)

        # Template Selection Row
        tpl_layout = QHBoxLayout()
        tpl_layout.setSpacing(8)
        lbl_tpl = QLabel("📋 试卷大纲结构模板:")
        lbl_tpl.setStyleSheet("font-weight: 700; color: #E2E8F0;")
        tpl_layout.addWidget(lbl_tpl)

        self.combo_template = QComboBox()
        self.combo_template.setFixedHeight(32)
        tpl_layout.addWidget(self.combo_template, 1)

        self.btn_config_template = QPushButton("⚙️ 配置/自定义模板...")
        self.btn_config_template.setFixedHeight(32)
        self.btn_config_template.clicked.connect(self._on_config_template)
        tpl_layout.addWidget(self.btn_config_template)

        layout.addLayout(tpl_layout)
        self._refresh_templates()

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["序号", "试卷名称", "总页数", "分析状态", "题目数 / 结果"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        # Progress bars section
        progress_box = QVBoxLayout()
        progress_box.setSpacing(6)

        self.lbl_overall = QLabel("总体进度: 等待开始")
        self.bar_overall = QProgressBar()
        self.bar_overall.setRange(0, 100)
        self.bar_overall.setValue(0)
        progress_box.addWidget(self.lbl_overall)
        progress_box.addWidget(self.bar_overall)

        self.lbl_current = QLabel("当前试卷: -")
        self.bar_current = QProgressBar()
        self.bar_current.setRange(0, 100)
        self.bar_current.setValue(0)
        progress_box.addWidget(self.lbl_current)
        progress_box.addWidget(self.bar_current)

        layout.addLayout(progress_box)

        # Buttons layout
        btn_layout = QHBoxLayout()

        self.btn_add = QPushButton("➕ 添加试卷 (PDF)...")
        self.btn_add.clicked.connect(self._on_add_clicked)
        btn_layout.addWidget(self.btn_add)

        self.btn_clear = QPushButton("🗑️ 清空列表")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()

        self.btn_add_to_basket = QPushButton("🧺 将全部题目加入试题篮")
        self.btn_add_to_basket.setEnabled(False)
        self.btn_add_to_basket.clicked.connect(self._on_add_to_basket_clicked)
        btn_layout.addWidget(self.btn_add_to_basket)

        self.btn_start = QPushButton("🚀 开始批量分析")
        self.btn_start.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;"
        )
        self.btn_start.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹️ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        btn_layout.addWidget(self.btn_stop)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def add_pdf_paths(self, paths: List[Path]) -> None:
        """Add new PDF paths to the analysis queue."""
        for p in paths:
            if p not in self.pdf_paths and p.is_file() and p.suffix.lower() == ".pdf":
                self.pdf_paths.append(p)
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.pdf_paths))
        for idx, path in enumerate(self.pdf_paths):
            # Index
            it_idx = QTableWidgetItem(str(idx + 1))
            it_idx.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 0, it_idx)

            # Name
            it_name = QTableWidgetItem(path.name)
            it_name.setToolTip(str(path))
            self.table.setItem(idx, 1, it_name)

            # Page count
            page_count_str = "-"
            try:
                reader = PDFReader(path)
                page_count_str = str(reader.page_count)
                reader.close()
            except Exception:
                pass
            it_pages = QTableWidgetItem(page_count_str)
            it_pages.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 2, it_pages)

            # Status
            pdf_str = str(path)
            if pdf_str in self.results:
                status_str = "✅ 已完成"
                status_color = QColor("#16A34A")
                q_count_str = f"{len(self.results[pdf_str])} 道题"
            else:
                status_str = "⏳ 等待分析"
                status_color = QColor("#6B7280")
                q_count_str = "-"

            it_status = QTableWidgetItem(status_str)
            it_status.setForeground(QBrush(status_color))
            it_status.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 3, it_status)

            it_res = QTableWidgetItem(q_count_str)
            it_res.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 4, it_res)

    def _on_add_clicked(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择待分析的试卷 PDF 文件",
            "",
            "PDF 文件 (*.pdf);;所有文件 (*.*)",
        )
        if files:
            paths = [Path(f) for f in files]
            self.add_pdf_paths(paths)

    def _on_clear_clicked(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "正在分析中，无法清空列表！")
            return
        self.pdf_paths.clear()
        self.results.clear()
        self._refresh_table()
        self.bar_overall.setValue(0)
        self.bar_current.setValue(0)
        self.lbl_overall.setText("总体进度: 等待开始")
        self.lbl_current.setText("当前试卷: -")
        self.btn_add_to_basket.setEnabled(False)

    def _on_start_clicked(self) -> None:
        if not self.pdf_paths:
            QMessageBox.information(self, "提示", "请先添加至少一份试卷 PDF！")
            return

        self.btn_add.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.chk_skip_cache.setEnabled(False)
        self.combo_template.setEnabled(False)
        self.btn_config_template.setEnabled(False)

        tpl_key = self.combo_template.currentData()
        structure_text = PaperTemplateStorage.get_template_content(tpl_key) if tpl_key else ""
        context_hints = {}
        if structure_text:
            context_hints["paper_structure"] = structure_text

        self.worker = BatchAnalysisWorker(
            pdf_paths=self.pdf_paths,
            provider=self.provider,
            skip_cached=self.chk_skip_cache.isChecked(),
            context_hints=context_hints,
            parent=self,
        )

        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.pdf_completed.connect(self._on_pdf_completed)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.pdf_error.connect(self._on_pdf_error)
        self.worker.cancelled.connect(self._on_cancelled)

        self.worker.start()

    def _on_stop_clicked(self) -> None:
        if self.worker and self.worker.isRunning():
            self.lbl_current.setText("正在取消后台分析任务...")
            self.worker.cancel()
            self.btn_stop.setEnabled(False)

    def _on_progress_updated(
        self,
        current_pdf_name: str,
        pdf_idx: int,
        total_pdfs: int,
        page_idx: int,
        total_pages: int,
    ) -> None:
        overall_pct = int(((pdf_idx - 1) + (page_idx / max(1, total_pages))) / max(1, total_pdfs) * 100)
        self.bar_overall.setValue(min(100, max(0, overall_pct)))
        self.lbl_overall.setText(f"总体进度: 正在处理第 {pdf_idx} / {total_pdfs} 份试卷 ({overall_pct}%)")

        curr_pct = int(page_idx / max(1, total_pages) * 100)
        self.bar_current.setValue(min(100, max(0, curr_pct)))
        self.lbl_current.setText(f"当前试卷: {current_pdf_name} - 第 {page_idx} / {total_pages} 页")

        # Update row in table
        row = pdf_idx - 1
        if 0 <= row < self.table.rowCount():
            it_status = self.table.item(row, 3)
            if it_status:
                it_status.setText(f"🔄 分析中 ({page_idx}/{total_pages})")
                it_status.setForeground(QBrush(QColor("#2563EB")))

    def _on_pdf_completed(self, pdf_path_str: str, questions: List[Question]) -> None:
        self.results[pdf_path_str] = questions
        p = Path(pdf_path_str)
        try:
            row = self.pdf_paths.index(p)
            it_status = self.table.item(row, 3)
            if it_status:
                it_status.setText("✅ 已完成")
                it_status.setForeground(QBrush(QColor("#16A34A")))
            it_res = self.table.item(row, 4)
            if it_res:
                it_res.setText(f"{len(questions)} 道题")
        except ValueError:
            pass

    def _on_pdf_error(self, pdf_path_str: str, error_msg: str) -> None:
        p = Path(pdf_path_str)
        try:
            row = self.pdf_paths.index(p)
            it_status = self.table.item(row, 3)
            if it_status:
                it_status.setText("❌ 失败")
                it_status.setForeground(QBrush(QColor("#DC2626")))
            it_res = self.table.item(row, 4)
            if it_res:
                it_res.setText("错误")
                it_res.setToolTip(error_msg)
        except ValueError:
            pass

    def _on_batch_finished(self, results: Dict[str, List[Question]]) -> None:
        self.results.update(results)
        self.bar_overall.setValue(100)
        self.bar_current.setValue(100)
        self.lbl_overall.setText(f"总体进度: 批量分析全部完成！(共 {len(self.pdf_paths)} 份试卷)")
        self.lbl_current.setText("就绪")

        self.btn_add.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.chk_skip_cache.setEnabled(True)

        total_qs = sum(len(qs) for qs in self.results.values())
        if total_qs > 0:
            self.btn_add_to_basket.setEnabled(True)

        self.batch_completed.emit(self.results)
        QMessageBox.information(
            self,
            "分析完成",
            f"批量分析完成！\n已成功分析 {len(self.results)} 份试卷，共检测出 {total_qs} 道题目。",
        )

    def _on_cancelled(self) -> None:
        self.lbl_overall.setText("总体进度: 已取消")
        self.lbl_current.setText("已停止")
        self.btn_add.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.chk_skip_cache.setEnabled(True)

        total_qs = sum(len(qs) for qs in self.results.values())
        if total_qs > 0:
            self.btn_add_to_basket.setEnabled(True)

        QMessageBox.warning(self, "已取消", "批量分析任务已停止。已分析的部分题目已保留。")

    def _on_add_to_basket_clicked(self) -> None:
        count = 0
        for qs in self.results.values():
            for q in qs:
                GLOBAL_BASKET.add_question(q)
                count += 1
        QMessageBox.information(
            self,
            "试题篮",
            f"已将 {count} 道题目添加到试题篮！\n当前试题篮共有 {GLOBAL_BASKET.count()} 道题目。",
        )

    def _refresh_templates(self, selected_name: Optional[str] = None) -> None:
        self.combo_template.blockSignals(True)
        self.combo_template.clear()

        all_templates = PaperTemplateStorage.get_all_templates()
        target = selected_name or PaperTemplateStorage.get_active_template_name()

        target_idx = 0
        for idx, name in enumerate(all_templates.keys()):
            prefix = "📌 " if PaperTemplateStorage.is_builtin(name) else "⭐ "
            self.combo_template.addItem(f"{prefix}{name}", name)
            if name == target:
                target_idx = idx

        self.combo_template.setCurrentIndex(target_idx)
        self.combo_template.blockSignals(False)

    def _on_config_template(self) -> None:
        cur_tpl = self.combo_template.currentData()
        dlg = PaperTemplateDialog(current_template_name=cur_tpl, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            chosen = dlg.get_template_name()
            self._refresh_templates(selected_name=chosen)


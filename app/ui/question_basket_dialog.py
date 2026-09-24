"""QuestionBasketDialog: Modern modal dialog to manage and assemble questions collected across multiple PDFs."""

from typing import Optional, List
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QGroupBox,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ..models.question import Question
from ..services.question_basket import GLOBAL_BASKET, QuestionBasket
from .export_dialog import ExportDialog


class QuestionBasketDialog(QDialog):
    """Shopping-cart style dialog to review, re-order, renumber, and export cross-paper questions."""

    def __init__(
        self,
        basket: Optional[QuestionBasket] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.basket = basket or GLOBAL_BASKET
        self.setWindowTitle("🧺 组卷试题篮管理仪表盘")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(860, 580)
        self.setMinimumSize(580, 360)
        self.setSizeGripEnabled(True)
        self._export_window: Optional[ExportDialog] = None

        self._setup_ui()
        self._refresh_list()
        self.basket.basket_changed.connect(self._on_basket_changed)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Header Summary Card
        self.summary_card = QGroupBox("试题篮汇总")
        s_layout = QHBoxLayout(self.summary_card)
        s_layout.setContentsMargins(16, 12, 16, 12)

        self.lbl_summary = QLabel()
        self.lbl_summary.setTextFormat(Qt.TextFormat.RichText)
        s_layout.addWidget(self.lbl_summary)
        s_layout.addStretch()

        layout.addWidget(self.summary_card)

        # 2. Table of Questions
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["序号", "当前题号", "原卷题号", "题型", "来源试卷", "跨页状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # 3. Toolbar Actions
        action_layout = QHBoxLayout()

        self.btn_renumber = QPushButton("🔢 一键重排连续题号 (1, 2, 3...)")
        self.btn_renumber.setToolTip("将试题篮中的全部题目重新从第 1 题开始连续编号，原题号将作为参考微注保存")
        self.btn_renumber.clicked.connect(self._on_renumber_clicked)
        action_layout.addWidget(self.btn_renumber)

        self.btn_sort_type = QPushButton("📑 按标准题型排序 (选择 ➜ 填空 ➜ 解答)")
        self.btn_sort_type.setToolTip("自动将试题按【选择题 ➜ 填空题 ➜ 解答大题】标准试卷结构重新排布")
        self.btn_sort_type.clicked.connect(self._on_sort_type_clicked)
        action_layout.addWidget(self.btn_sort_type)

        action_layout.addStretch()

        self.btn_up = QPushButton("⬆ 上移")
        self.btn_up.clicked.connect(self._on_move_up)
        action_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton("⬇ 下移")
        self.btn_down.clicked.connect(self._on_move_down)
        action_layout.addWidget(self.btn_down)

        self.btn_remove = QPushButton("✕ 移除此题")
        self.btn_remove.clicked.connect(self._on_remove_selected)
        action_layout.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        action_layout.addWidget(self.btn_clear)

        layout.addLayout(action_layout)

        # 4. Bottom Actions
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)

        self.btn_export = QPushButton("🚀 导出试题篮全部题目 (A4无损合并)")
        self.btn_export.setProperty("primary", "true")
        self.btn_export.setStyleSheet("font-weight: bold; padding: 8px 20px;")
        self.btn_export.clicked.connect(self._on_export_clicked)
        bottom_layout.addWidget(self.btn_export)

        layout.addLayout(bottom_layout)

    def _refresh_list(self) -> None:
        """Populate the table with current basket items."""
        questions = self.basket.get_questions()
        self.table.setRowCount(len(questions))

        # Update summary text
        types_count = {}
        for q in questions:
            t = q.get_type_display_name()
            types_count[t] = types_count.get(t, 0) + 1

        types_str = "，".join(f"{k} {v} 道" for k, v in types_count.items()) or "暂无题目"
        papers_count = len(self.basket.get_grouped_by_paper())
        self.lbl_summary.setText(
            f"<span style='color: #38BDF8; font-size: 15px;'><b>试题篮总计:</b> {len(questions)} 道题目</span> "
            f"<span style='color: #94A3B8; font-size: 14px;'>（覆盖 {papers_count} 份试卷）</span><br>"
            f"<span style='color: #F8FAFC; font-size: 13.5px;'><b>题型分布:</b> {types_str}</span>"
        )

        for row, q in enumerate(questions):
            # Column 0: Index
            item_idx = QTableWidgetItem(str(row + 1))
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, item_idx)

            # Column 1: Current Display Number
            item_num = QTableWidgetItem(f"第 {q.display_number} 题")
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_num)

            # Column 2: Original Number
            orig_str = f"原第 {q.original_display_number} 题" if q.original_display_number else "-"
            item_orig = QTableWidgetItem(orig_str)
            item_orig.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_orig.setForeground(QColor("#94A3B8"))
            self.table.setItem(row, 2, item_orig)

            # Column 3: Type
            type_name = q.get_type_display_name()
            item_type = QTableWidgetItem(type_name)
            item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if q.is_large_question():
                item_type.setForeground(QColor("#F43F5E"))
            else:
                item_type.setForeground(QColor("#38BDF8"))
            self.table.setItem(row, 3, item_type)

            # Column 4: Source Paper
            paper_str = q.source_paper_title or Path(q.source_pdf_path).stem if q.source_pdf_path else "当前试卷"
            item_paper = QTableWidgetItem(paper_str)
            self.table.setItem(row, 4, item_paper)

            # Column 5: Continuation
            cont_str = f"跨 {len(q.segments)} 页" if q.continuation else "单页"
            item_cont = QTableWidgetItem(cont_str)
            item_cont.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, item_cont)

        has_items = len(questions) > 0
        self.btn_renumber.setEnabled(has_items)
        self.btn_sort_type.setEnabled(has_items)
        self.btn_clear.setEnabled(has_items)
        self.btn_export.setEnabled(has_items)

    def _on_basket_changed(self, count: int) -> None:
        self._refresh_list()

    def _on_renumber_clicked(self) -> None:
        self.basket.renumber_sequentially(start_num=1)
        self._refresh_list()

    def _on_sort_type_clicked(self) -> None:
        self.basket.sort_by_question_type()
        self._refresh_list()

    def _on_move_up(self) -> None:
        row = self.table.currentRow()
        if row > 0:
            self.basket.move_item(row, row - 1)
            self.table.selectRow(row - 1)

    def _on_move_down(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < self.basket.count() - 1:
            self.basket.move_item(row, row + 1)
            self.table.selectRow(row + 1)

    def _on_remove_selected(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < self.basket.count():
            questions = self.basket.get_questions()
            q = questions[row]
            self.basket.remove_question(q.id)

    def _on_clear_clicked(self) -> None:
        if self.basket.count() == 0:
            return
        reply = QMessageBox.question(
            self,
            "清空试题篮",
            "确定要清空试题篮中的全部题目吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.basket.clear()

    def _on_export_clicked(self) -> None:
        questions = self.basket.get_questions()
        if not questions:
            QMessageBox.warning(self, "试题篮为空", "试题篮中暂无题目，请先在试卷中勾选题目加入试题篮。")
            return

        # Use first question's source_pdf as primary source, or current active
        source_pdf = questions[0].source_pdf_path or "merged_papers.pdf"

        # Ensure all questions have selected = True for export
        for q in questions:
            q.selected = True

        if self._export_window is not None:
            self._export_window.selected_questions = questions
            self._export_window.show()
            self._export_window.raise_()
            self._export_window.activateWindow()
            return
        dlg = ExportDialog(source_pdf=source_pdf, selected_questions=questions, parent=self)
        dlg.finished.connect(lambda: setattr(self, "_export_window", None))
        self._export_window = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def closeEvent(self, event) -> None:
        if self._export_window is not None:
            try:
                self._export_window.close()
            except Exception:
                pass
        super().closeEvent(event)

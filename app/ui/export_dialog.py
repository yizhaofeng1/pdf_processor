"""ExportDialog: Modern configuration dialog for lossless PDF question export."""

from typing import List, Optional
from pathlib import Path
import os
import subprocess
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt

from ..models.question import Question, QuestionType
from ..pdf.exporter import PDFExporter, ExportMode, ExportOptions, QUESTION_TYPE_NAMES


class ExportDialog(QDialog):
    """User configuration modal for exporting selected questions."""

    def __init__(
        self,
        source_pdf: Path | str,
        selected_questions: List[Question],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.source_pdf = Path(source_pdf)
        self.selected_questions = [q for q in selected_questions if q.selected]

        self.setWindowTitle("📤 选题集 PDF 导出设置仪表盘")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(600, 520)
        self.setMinimumSize(480, 360)
        self.setSizeGripEnabled(True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(10)
        outer_layout.setContentsMargins(14, 14, 14, 14)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 4, 8, 4)

        # 1. Summary Header Card
        summary_card = QGroupBox("选中题目概览")
        s_layout = QVBoxLayout(summary_card)

        types_count = {}
        distinct_sources = set()
        for q in self.selected_questions:
            t = q.get_type_display_name() if hasattr(q, "get_type_display_name") else QUESTION_TYPE_NAMES.get(q.question_type, "综合题")
            types_count[t] = types_count.get(t, 0) + 1
            if q.source_paper_title:
                distinct_sources.add(q.source_paper_title)
            elif q.source_pdf_path:
                distinct_sources.add(Path(q.source_pdf_path).name)

        if not distinct_sources:
            distinct_sources.add(self.source_pdf.name)

        types_str = "，".join(f"{k} {v} 道" for k, v in types_count.items()) or "无"
        sources_str = "、".join(list(distinct_sources)[:3])
        if len(distinct_sources) > 3:
            sources_str += f" 等 {len(distinct_sources)} 份试卷"

        lbl_info = QLabel(
            f"<span style='color: #38BDF8; font-size: 15px;'><b>已选定:</b> {len(self.selected_questions)} 道题目</span><br>"
            f"<span style='color: #F8FAFC; font-size: 14px;'><b>题型分布:</b> {types_str}</span><br>"
            f"<span style='color: #94A3B8; font-size: 13.5px;'><b>来源试卷:</b> {sources_str}</span>"
        )
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        s_layout.addWidget(lbl_info)
        layout.addWidget(summary_card)

        # 2. Layout Mode Selection Group
        mode_group = QGroupBox("排版模式选择")
        m_layout = QVBoxLayout(mode_group)
        m_layout.setSpacing(10)

        self.btn_group_mode = QButtonGroup(self)

        # Mode A: Adaptive Flow (Recommended)
        self.radio_adaptive = QRadioButton("🎯 A4 智能试题卷排版 (推荐：小题紧凑，大题自适应留白答题区)")
        self.radio_adaptive.setChecked(True)
        lbl_adaptive_sub = QLabel("   选择/填空等小题按选框紧凑排列不浪费纸张，解答大题自动预留充裕作答/草稿空间。")
        lbl_adaptive_sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        self.btn_group_mode.addButton(self.radio_adaptive, 0)
        m_layout.addWidget(self.radio_adaptive)
        m_layout.addWidget(lbl_adaptive_sub)

        # Adaptive blank configuration sub-panel
        self.adaptive_options_widget = QWidget()
        a_layout = QHBoxLayout(self.adaptive_options_widget)
        a_layout.setContentsMargins(20, 0, 0, 6)
        a_layout.addWidget(QLabel("大题留白高度:"))
        from PySide6.QtWidgets import QSpinBox
        self.spin_blank = QSpinBox()
        self.spin_blank.setRange(60, 500)
        self.spin_blank.setSingleStep(20)
        self.spin_blank.setValue(240)
        self.spin_blank.setSuffix(" pt (约半页)")
        a_layout.addWidget(self.spin_blank)

        self.chk_answer_box = QCheckBox("绘制大题【答题区域】浅灰虚线框")
        self.chk_answer_box.setChecked(True)
        a_layout.addWidget(self.chk_answer_box)
        a_layout.addStretch()
        m_layout.addWidget(self.adaptive_options_widget)

        # Mode B: Single per page
        self.radio_single = QRadioButton("📄 A4 单题一页 (刷题留白练习模式)")
        lbl_single_sub = QLabel("   每道题占据独立 A4 页，保留大面积解题留白，适合单题突破与错题练习。")
        lbl_single_sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        self.btn_group_mode.addButton(self.radio_single, 1)
        m_layout.addWidget(self.radio_single)
        m_layout.addWidget(lbl_single_sub)

        # Mode C: Compact flow
        self.radio_compact = QRadioButton("📑 A4 全流式紧凑排版 (极限节约纸张模式)")
        lbl_compact_sub = QLabel("   所有题目在 A4 页面顺次紧凑流水排版，题目间以微细虚线分隔，极限压缩页数。")
        lbl_compact_sub.setStyleSheet("color: #94A3B8; font-size: 13px;")
        self.btn_group_mode.addButton(self.radio_compact, 2)
        m_layout.addWidget(self.radio_compact)
        m_layout.addWidget(lbl_compact_sub)

        self.radio_adaptive.toggled.connect(self._on_mode_toggled)
        layout.addWidget(mode_group)

        # 3. Document Options
        opts_group = QGroupBox("试卷信息与编号选项")
        f_layout = QFormLayout(opts_group)

        default_title = f"{self.source_pdf.stem} - 精选题集" if len(distinct_sources) == 1 else "ExamSplit AI 精选试卷集"
        self.edit_title = QLineEdit(default_title)
        f_layout.addRow("试卷标题:", self.edit_title)

        self.chk_header = QCheckBox("在页面顶部打印标题与试题编号页眉")
        self.chk_header.setChecked(True)
        f_layout.addRow("", self.chk_header)

        self.chk_footer = QCheckBox("在页面底部打印页码 (\"第 X 页 / 共 Y 页\")")
        self.chk_footer.setChecked(True)
        f_layout.addRow("", self.chk_footer)

        self.chk_divider = QCheckBox("在题目间绘制分隔虚线")
        self.chk_divider.setChecked(True)
        f_layout.addRow("", self.chk_divider)

        self.chk_renumber = QCheckBox("统一重排为连续题号 (1, 2, 3...)")
        self.chk_renumber.setChecked(len(distinct_sources) > 1)
        f_layout.addRow("", self.chk_renumber)

        self.chk_source_footnote = QCheckBox("在题目标签后微注原卷题号出处 (如: [原 2010数一·第3题])")
        self.chk_source_footnote.setChecked(True)
        f_layout.addRow("", self.chk_source_footnote)

        layout.addWidget(opts_group)

        # 4. Target Path Picker
        path_group = QGroupBox("导出保存路径")
        p_layout = QHBoxLayout(path_group)

        default_out = self.source_pdf.parent / f"{self.source_pdf.stem}_精选导出.pdf" if len(distinct_sources) == 1 else self.source_pdf.parent / "ExamSplit_跨卷选题集.pdf"
        self.edit_path = QLineEdit(str(default_out))
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self._on_browse_output)
        p_layout.addWidget(self.edit_path)
        p_layout.addWidget(self.btn_browse)

        layout.addWidget(path_group)

        layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        outer_layout.addWidget(scroll_area, stretch=1)

        # 5. Dialog Actions (Fixed at bottom)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(6, 6, 6, 0)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_export = QPushButton("🚀 立即开始导出")
        self.btn_export.setProperty("primary", "true")
        self.btn_export.clicked.connect(self._on_start_export)
        btn_layout.addWidget(self.btn_export)

        outer_layout.addLayout(btn_layout)

    def _on_mode_toggled(self) -> None:
        self.adaptive_options_widget.setVisible(self.radio_adaptive.isChecked())

    def _on_browse_output(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择导出 PDF 存储路径", self.edit_path.text(), "PDF Files (*.pdf)"
        )
        if file_path:
            self.edit_path.setText(file_path)

    def _on_start_export(self) -> None:
        out_path = Path(self.edit_path.text().strip())
        if not str(out_path):
            QMessageBox.warning(self, "路径无效", "请选择有效的导出保存路径。")
            return

        if self.radio_adaptive.isChecked():
            mode = ExportMode.ADAPTIVE_EXAM_FLOW
        elif self.radio_single.isChecked():
            mode = ExportMode.SINGLE_QUESTION_PER_PAGE
        else:
            mode = ExportMode.COMPACT_FLOW

        options = ExportOptions(
            mode=mode,
            paper_title=self.edit_title.text().strip() or "ExamSplit AI 选题集",
            show_header=self.chk_header.isChecked(),
            show_footer=self.chk_footer.isChecked(),
            show_divider=self.chk_divider.isChecked(),
            large_blank_height_pt=float(self.spin_blank.value()),
            show_answer_box=self.chk_answer_box.isChecked(),
            renumber_sequentially=self.chk_renumber.isChecked(),
            show_source_footnote=self.chk_source_footnote.isChecked(),
        )

        try:
            res_file = PDFExporter.export(
                source_pdf=self.source_pdf,
                questions=self.selected_questions,
                output_path=out_path,
                options=options,
            )

            mode_name = "智能试题卷排版" if mode == ExportMode.ADAPTIVE_EXAM_FLOW else ("单题一页" if mode == ExportMode.SINGLE_QUESTION_PER_PAGE else "紧凑流式")
            reply = QMessageBox.information(
                self,
                "导出成功",
                f"恭喜！选题集 PDF 已成功生成：\n\n"
                f"• 文件位置: {res_file.name}\n"
                f"• 包含题目: {len(self.selected_questions)} 道\n"
                f"• 排版模式: {mode_name}\n\n"
                f"是否立即打开该 PDF 查看？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._open_file(res_file)

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出试卷过程中发生异常:\n{e}")

    def _open_file(self, file_path: Path) -> None:
        """Open generated PDF in system default viewer."""
        try:
            if os.name == "posix":
                subprocess.Popen(["xdg-open", str(file_path)])
            elif os.name == "nt":
                os.startfile(str(file_path))
        except Exception:
            pass

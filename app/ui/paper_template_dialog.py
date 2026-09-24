"""PaperTemplateDialog: Modal dialog to configure, customize, and persist exam paper structure templates."""

from typing import Optional, Dict
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QTextEdit,
    QPushButton,
    QLabel,
    QGroupBox,
    QMessageBox,
    QInputDialog,
    QFrame,
)
from PySide6.QtCore import Qt, Signal

from ..storage.paper_template import PaperTemplateStorage


class PaperTemplateDialog(QDialog):
    """Dialog allowing users to pick a structure template, enter custom distributions, and save templates."""

    template_applied = Signal(str)
    CUSTOM_OPTION = "【自定义当前试卷题目结构】"

    def __init__(
        self,
        current_template_name: Optional[str] = None,
        initial_text: Optional[str] = None,
        pdf_name: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("📑 试卷结构大纲与提示词模板管理仪表盘")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(680, 500)
        self.setMinimumSize(500, 360)
        self.setSizeGripEnabled(True)

        self._pdf_name = pdf_name
        self._initial_template_name = current_template_name or PaperTemplateStorage.get_active_template_name()
        self._initial_text = initial_text

        self._setup_ui()
        self._load_templates_to_combo(selected_name=self._initial_template_name)

        if self._initial_text is not None and self._initial_text.strip():
            self.txt_structure.setPlainText(self._initial_text.strip())

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # 1. Header description card
        header_group = QGroupBox("试卷结构大纲提示词注入")
        h_layout = QVBoxLayout(header_group)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(6)

        target_info = f"当前待分析试卷: <b style='color:#38BDF8;'>{self._pdf_name}</b><br/>" if self._pdf_name else ""
        lbl_desc = QLabel(
            f"{target_info}"
            "提供试卷题型题号分布（如选择题、填空题、解答题题号范围），可将大纲结构提前注入 AI 提示词中，"
            "大幅提升小题与密集大题的题号归类与切题边界精度。"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.4;")
        h_layout.addWidget(lbl_desc)
        layout.addWidget(header_group)

        # 2. Template Selector Row
        sel_layout = QHBoxLayout()
        sel_layout.setSpacing(10)

        lbl_tpl = QLabel("选择大纲模板:")
        lbl_tpl.setStyleSheet("font-weight: 700; font-size: 13.5px; color: #E2E8F0;")
        sel_layout.addWidget(lbl_tpl)

        self.combo_template = QComboBox()
        self.combo_template.setFixedHeight(36)
        self.combo_template.currentIndexChanged.connect(self._on_template_selected)
        sel_layout.addWidget(self.combo_template, 1)

        self.btn_delete_template = QPushButton("🗑️ 删除此模板")
        self.btn_delete_template.setProperty("danger", "true")
        self.btn_delete_template.setFixedHeight(36)
        self.btn_delete_template.setEnabled(False)
        self.btn_delete_template.setToolTip("仅可删除用户自定义保存的模板，内置模板受保护")
        self.btn_delete_template.clicked.connect(self._on_delete_template)
        sel_layout.addWidget(self.btn_delete_template)

        layout.addLayout(sel_layout)

        # 3. Structure text editor
        editor_group = QGroupBox("大纲结构分布详细描述 (将作为提示词注入 AI)")
        e_layout = QVBoxLayout(editor_group)
        e_layout.setContentsMargins(14, 14, 14, 14)
        e_layout.setSpacing(10)

        self.txt_structure = QTextEdit()
        self.txt_structure.setPlaceholderText(
            "在此输入或修改当前试卷的题目分布情况。\n"
            "例如：\n"
            "第1~10题为单选题(每题5分，小题)；\n"
            "第11~16题为填空题(每题5分，小题)；\n"
            "第17~22题为解答题(计算/证明题，大题)。"
        )
        self.txt_structure.setStyleSheet("""
            QTextEdit {
                background: #0F172A;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border-color: #38BDF8;
            }
        """)
        e_layout.addWidget(self.txt_structure)

        # Save as new template row
        save_layout = QHBoxLayout()
        save_layout.addStretch()

        self.btn_save_as_template = QPushButton("💾 将当前描述保存为新模板供以后使用...")
        self.btn_save_as_template.setFixedHeight(34)
        self.btn_save_as_template.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #38BDF8;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #475569;
                color: #7DD3FC;
            }
        """)
        self.btn_save_as_template.clicked.connect(self._on_save_as_new_template)
        save_layout.addWidget(self.btn_save_as_template)

        e_layout.addLayout(save_layout)
        layout.addWidget(editor_group)

        # 4. Action Buttons (Bottom)
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        btn_box.addStretch()

        self.btn_apply = QPushButton("🚀 确定应用此大纲并开始分析")
        self.btn_apply.setFixedHeight(40)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #2563EB);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 14px;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38BDF8, stop:1 #0284C7);
            }
        """)
        self.btn_apply.clicked.connect(self._on_apply)
        btn_box.addWidget(self.btn_apply)

        layout.addLayout(btn_box)

    def _load_templates_to_combo(self, selected_name: Optional[str] = None) -> None:
        self.combo_template.blockSignals(True)
        self.combo_template.clear()

        all_templates = PaperTemplateStorage.get_all_templates()
        for name in all_templates.keys():
            if PaperTemplateStorage.is_builtin(name):
                self.combo_template.addItem(f"📌 {name}", name)
            else:
                self.combo_template.addItem(f"⭐ {name} (自定义)", name)

        self.combo_template.addItem(self.CUSTOM_OPTION, self.CUSTOM_OPTION)

        # Restore selection
        idx_to_select = 0
        if selected_name:
            for i in range(self.combo_template.count()):
                if self.combo_template.itemData(i) == selected_name:
                    idx_to_select = i
                    break

        self.combo_template.setCurrentIndex(idx_to_select)
        self.combo_template.blockSignals(False)

        self._sync_editor_with_combo()

    def _on_template_selected(self, index: int) -> None:
        self._sync_editor_with_combo()

    def _sync_editor_with_combo(self) -> None:
        tpl_key = self.combo_template.currentData()
        if not tpl_key:
            return

        if tpl_key == self.CUSTOM_OPTION:
            self.btn_delete_template.setEnabled(False)
            return

        is_builtin = PaperTemplateStorage.is_builtin(tpl_key)
        self.btn_delete_template.setEnabled(not is_builtin)

        content = PaperTemplateStorage.get_template_content(tpl_key)
        self.txt_structure.setPlainText(content)

    def _on_delete_template(self) -> None:
        tpl_key = self.combo_template.currentData()
        if not tpl_key or PaperTemplateStorage.is_builtin(tpl_key) or tpl_key == self.CUSTOM_OPTION:
            return

        confirm = QMessageBox.question(
            self,
            "删除确认",
            f"确定要删除自定义模板【{tpl_key}】吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            PaperTemplateStorage.delete_custom_template(tpl_key)
            self._load_templates_to_combo(selected_name=PaperTemplateStorage.get_active_template_name())
            QMessageBox.information(self, "删除成功", f"已成功删除模板【{tpl_key}】")

    def _on_save_as_new_template(self) -> None:
        text = self.txt_structure.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "当前题目结构描述内容为空，请先输入大纲内容再保存！")
            return

        name, ok = QInputDialog.getText(
            self,
            "保存为新模板",
            "请输入新模板名称 (例如：2024自主命题数学试卷):",
            text="自定义试卷模板",
        )
        if not ok or not name.strip():
            return

        clean_name = name.strip()
        try:
            PaperTemplateStorage.save_custom_template(clean_name, text)
            self._load_templates_to_combo(selected_name=clean_name)
            QMessageBox.information(self, "保存成功", f"模板【{clean_name}】已成功保存！\n后续在任何试卷中均可直接选取复用。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存模板出错: {e}")

    def _on_apply(self) -> None:
        tpl_key = self.combo_template.currentData()
        if tpl_key and tpl_key != self.CUSTOM_OPTION:
            PaperTemplateStorage.set_active_template_name(tpl_key)
        self.template_applied.emit(self.get_template_name())
        self.accept()

    def get_structure_text(self) -> str:
        """Get the final edited structure prompt text."""
        return self.txt_structure.toPlainText().strip()

    def get_template_name(self) -> str:
        """Get currently chosen template name."""
        return self.combo_template.currentData() or ""

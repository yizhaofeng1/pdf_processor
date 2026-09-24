"""Settings and API Gateway Management Dialog with multi-profile and custom prompt capabilities."""

from typing import Optional, List, Dict, Any
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
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal

from ..ai.provider_factory import ProviderFactory, PROVIDER_PRESETS
from ..ai.prompt_manager import PromptManager
from ..storage.key_storage import KeyStorage, mask_api_key


class ConnectionTestWorker(QThread):
    """Background worker to test API connectivity without freezing the UI."""

    finished_test = Signal(bool, str)

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: float,
        proxy: str,
    ) -> None:
        super().__init__()
        self.provider_id = provider_id
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.proxy = proxy

    def run(self) -> None:
        try:
            provider = ProviderFactory.create_provider(
                provider_id=self.provider_id,
                base_url=self.base_url,
                api_key=self.api_key,
                model_name=self.model_name,
                timeout=self.timeout,
                proxy=self.proxy,
            )
            success, message = provider.test_connection()
            self.finished_test.emit(success, message)
        except Exception as e:
            self.finished_test.emit(False, f"测试发生异常: {e}")


class ModelFetchWorker(QThread):
    """Background worker to query the API for list of available models."""

    finished_fetch = Signal(bool, list, str)

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
        timeout: float,
        proxy: str,
    ) -> None:
        super().__init__()
        self.provider_id = provider_id
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.proxy = proxy

    def run(self) -> None:
        try:
            provider = ProviderFactory.create_provider(
                provider_id=self.provider_id,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                proxy=self.proxy,
            )
            models = provider.fetch_available_models()
            if models:
                self.finished_fetch.emit(True, models, f"成功获取到 {len(models)} 个可用模型！")
            else:
                self.finished_fetch.emit(False, [], "未返回任何可用模型，请检查地址或凭据。")
        except Exception as e:
            self.finished_fetch.emit(False, [], f"获取模型列表失败: {e}")


class SettingsDialog(QDialog):
    """Dialog for managing multiple API gateway profiles, models, encrypted keys, and custom prompts."""

    settings_saved = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚙️ AI 模型与多网关配置仪表盘 (API Gateway Profiles)")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(720, 580)
        self.setMinimumSize(540, 380)
        self.setSizeGripEnabled(True)

        self._current_profile_id: str = ""
        self._is_populating_profiles: bool = False
        self._test_worker: Optional[ConnectionTestWorker] = None
        self._fetch_worker: Optional[ModelFetchWorker] = None

        self._setup_ui()
        self._load_initial_state()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(14, 14, 14, 14)
        outer_layout.setSpacing(10)

        # Scroll area for all configuration groups
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_widget = QWidget()
        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setContentsMargins(4, 4, 8, 4)
        main_layout.setSpacing(12)

        # ----------------------------------------------------
        # 1. Gateway Profile Management Section (Top)
        # ----------------------------------------------------
        prof_group = QGroupBox("网关档案选择与快捷切换 (Gateway Profiles)")
        prof_layout = QVBoxLayout(prof_group)
        prof_layout.setSpacing(10)

        sel_bar = QHBoxLayout()
        sel_bar.addWidget(QLabel("已保存网关:"))
        self.combo_profiles = QComboBox()
        self.combo_profiles.setToolTip("选择已保存的 API 网关配置档案进行切换或编辑")
        self.combo_profiles.currentIndexChanged.connect(self._on_profile_selection_changed)
        sel_bar.addWidget(self.combo_profiles, stretch=3)

        self.btn_new_profile = QPushButton("➕ 新建网关")
        self.btn_new_profile.clicked.connect(self._on_new_profile)
        sel_bar.addWidget(self.btn_new_profile)

        self.btn_delete_profile = QPushButton("🗑️ 删除此网关")
        self.btn_delete_profile.setStyleSheet("color: #F87171;")
        self.btn_delete_profile.clicked.connect(self._on_delete_profile)
        sel_bar.addWidget(self.btn_delete_profile)

        prof_layout.addLayout(sel_bar)

        # Profile Name edit line
        name_bar = QHBoxLayout()
        name_bar.addWidget(QLabel("网关备注名称:"))
        self.edit_profile_name = QLineEdit()
        self.edit_profile_name.setPlaceholderText("例如: DeepSeek 官方、硅基流动、Google Gemini 官方、本地 Ollama")
        name_bar.addWidget(self.edit_profile_name, stretch=1)
        prof_layout.addLayout(name_bar)

        main_layout.addWidget(prof_group)

        # ----------------------------------------------------
        # 2. Detailed Parameters Group
        # ----------------------------------------------------
        group = QGroupBox("服务商接口与凭据参数")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        # Provider Selector
        self.combo_provider = QComboBox()
        for pid, preset in PROVIDER_PRESETS.items():
            self.combo_provider.addItem(preset["display_name"], pid)
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("服务商类型:", self.combo_provider)

        # Description Label
        self.lbl_description = QLabel("")
        self.lbl_description.setStyleSheet("color: #94A3B8; font-size: 13px; font-style: italic;")
        self.lbl_description.setWordWrap(True)
        form.addRow("", self.lbl_description)

        # Base URL
        url_layout = QHBoxLayout()
        self.edit_base_url = QLineEdit()
        self.edit_base_url.setPlaceholderText("https://...")
        self.btn_reset_url = QPushButton("恢复默认地址")
        self.btn_reset_url.setToolTip("恢复该服务商的官方默认地址")
        self.btn_reset_url.clicked.connect(self._on_reset_url)
        url_layout.addWidget(self.edit_base_url)
        url_layout.addWidget(self.btn_reset_url)
        form.addRow("API 地址 (URL):", url_layout)

        # API Key with show/hide toggle
        key_layout = QHBoxLayout()
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_api_key.setPlaceholderText("请输入 API Key (本地 AES 绑定机器加密存储)")

        self.btn_toggle_key = QPushButton("显示")
        self.btn_toggle_key.setFixedWidth(60)
        self.btn_toggle_key.clicked.connect(self._on_toggle_key_visibility)

        key_layout.addWidget(self.edit_api_key)
        key_layout.addWidget(self.btn_toggle_key)
        form.addRow("API Key:", key_layout)

        # Encryption indicator
        enc_layout = QHBoxLayout()
        lbl_security = QLabel("🔒 密钥将使用机器绑定密钥加密存储至本地，绝不上传或泄露")
        lbl_security.setStyleSheet("color: #34D399; font-size: 12.5px; font-weight: 600;")
        enc_layout.addWidget(lbl_security)
        form.addRow("", enc_layout)

        # Model Selector with Online Fetch Button
        model_layout = QHBoxLayout()
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_model.lineEdit().setPlaceholderText("下拉选择或输入模型，例如 deepseek-chat 或 gemini-2.5-flash")
        self.combo_model.currentTextChanged.connect(self._on_model_text_changed)

        self.btn_fetch_models = QPushButton("获取模型列表")
        self.btn_fetch_models.setToolTip("从当前 API 地址在线拉取可用模型清单供选择")
        self.btn_fetch_models.clicked.connect(self._on_fetch_models)

        model_layout.addWidget(self.combo_model, stretch=1)
        model_layout.addWidget(self.btn_fetch_models)
        form.addRow("模型标识 (Model):", model_layout)

        # Timeout
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(5, 300)
        self.spin_timeout.setValue(60)
        self.spin_timeout.setSuffix(" 秒")
        form.addRow("请求超时:", self.spin_timeout)

        # Proxy with WSL2 auto-detect button
        proxy_layout = QHBoxLayout()
        self.edit_proxy = QLineEdit()
        self.edit_proxy.setPlaceholderText("例如: http://172.23.0.1:7890 (宿主机网关) 或留空")
        self.btn_auto_wsl_proxy = QPushButton("⚡ 填入宿主机代理 (172.23.0.1)")
        self.btn_auto_wsl_proxy.setToolTip("自动检测 WSL2 宿主机 Windows 网关并填入代理端口")
        self.btn_auto_wsl_proxy.clicked.connect(self._on_auto_fill_wsl_proxy)
        proxy_layout.addWidget(self.edit_proxy, stretch=2)
        proxy_layout.addWidget(self.btn_auto_wsl_proxy, stretch=1)
        form.addRow("HTTP 代理 (可选):", proxy_layout)

        # ----------------------------------------------------
        # 3. Model Custom Prompt Configuration Section
        # ----------------------------------------------------
        prompt_mode_layout = QHBoxLayout()
        self.combo_prompt_mode = QComboBox()
        self.combo_prompt_mode.addItem("✨ 内置推荐优化提示词 (DeepSeek 专属优化 / Gemini 标准版)", "builtin_optimized")
        self.combo_prompt_mode.addItem("📄 系统默认通用提示词 (Standard Template)", "default")
        self.combo_prompt_mode.addItem("✏️ 自定义专属提示词 (自由编辑与微调注入)", "custom")
        self.combo_prompt_mode.currentIndexChanged.connect(self._on_prompt_mode_changed)
        prompt_mode_layout.addWidget(self.combo_prompt_mode, stretch=2)

        self.btn_reset_prompt = QPushButton("恢复当前模型推荐提示词")
        self.btn_reset_prompt.setToolTip("将提示词重置为该模型最推荐的优化版本")
        self.btn_reset_prompt.clicked.connect(self._on_reset_prompt_clicked)
        prompt_mode_layout.addWidget(self.btn_reset_prompt, stretch=1)
        form.addRow("提示词模式:", prompt_mode_layout)

        self.text_custom_prompt = QTextEdit()
        self.text_custom_prompt.setPlaceholderText("系统提示词内容...")
        self.text_custom_prompt.setMinimumHeight(75)
        self.text_custom_prompt.setMaximumHeight(200)
        self.text_custom_prompt.setStyleSheet("font-family: monospace; font-size: 12px; line-height: 1.4;")
        form.addRow("系统提示词 (Prompt):", self.text_custom_prompt)

        # Default Active Checkbox
        self.chk_default = QCheckBox("设为当前激活生效的网关 (Active Gateway)")
        self.chk_default.setChecked(True)
        self.chk_default.setStyleSheet("font-weight: 600; color: #38BDF8;")
        form.addRow("", self.chk_default)

        main_layout.addWidget(group)

        # ----------------------------------------------------
        # 4. Connection Test Section
        # ----------------------------------------------------
        test_group = QGroupBox("连通性与模型检测")
        test_layout = QVBoxLayout(test_group)
        test_layout.setSpacing(8)

        test_bar_layout = QHBoxLayout()
        self.btn_test = QPushButton("🔍 测试当前 API 连接")
        self.btn_test.clicked.connect(self._on_test_connection)
        test_bar_layout.addWidget(self.btn_test)

        self.btn_diag_network = QPushButton("🌐 一键网络诊断")
        self.btn_diag_network.setToolTip("诊断 DNS、WSL2 网关与官方接口连通状态")
        self.btn_diag_network.clicked.connect(self._on_diagnose_network)
        test_bar_layout.addWidget(self.btn_diag_network)

        self.progress_test = QProgressBar()
        self.progress_test.setRange(0, 0)
        self.progress_test.setVisible(False)
        test_bar_layout.addWidget(self.progress_test)
        test_layout.addLayout(test_bar_layout)

        self.lbl_test_result = QLabel("点击 [测试当前 API 连接] 验证连通性，或点击 [获取模型列表] 查看可选模型。")
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setStyleSheet("color: #94A3B8; font-size: 13px;")
        test_layout.addWidget(self.lbl_test_result)

        main_layout.addWidget(test_group)
        main_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        outer_layout.addWidget(scroll_area, stretch=1)

        # ----------------------------------------------------
        # 5. Bottom Action Buttons (Fixed at dialog bottom)
        # ----------------------------------------------------
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(6, 6, 6, 0)
        self.btn_delete = QPushButton("清空此网关 Key")
        self.btn_delete.setStyleSheet("color: #d32f2f;")
        self.btn_delete.clicked.connect(self._on_delete_key)
        btn_box.addWidget(self.btn_delete)

        btn_box.addStretch()

        self.btn_save = QPushButton("💾 保存当前网关配置")
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_close)

        outer_layout.addLayout(btn_box)

    def _get_current_provider_id(self) -> str:
        return self.combo_provider.currentData()

    def _load_initial_state(self) -> None:
        """Populate profile list and load active profile."""
        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        """Reload profiles from KeyStorage and populate combo_profiles."""
        self._is_populating_profiles = True
        self.combo_profiles.clear()

        profiles = KeyStorage.get_all_profiles()
        active_id = KeyStorage.get_active_profile_id()

        target_idx = 0
        for i, (pid, p) in enumerate(profiles.items()):
            is_active = (pid == active_id)
            active_badge = " [⭐当前激活]" if is_active else ""
            model_info = f" ({p.get('model_name', '')})" if p.get("model_name") else ""
            disp_text = f"{p.get('name', '未命名网关')}{model_info}{active_badge}"
            self.combo_profiles.addItem(disp_text, pid)
            if pid == active_id:
                target_idx = i

        self._is_populating_profiles = False

        if self.combo_profiles.count() > 0:
            self.combo_profiles.setCurrentIndex(target_idx)
            selected_pid = self.combo_profiles.currentData()
            self._load_profile(selected_pid)
        else:
            self._on_new_profile()

    def _on_profile_selection_changed(self) -> None:
        if self._is_populating_profiles:
            return
        pid = self.combo_profiles.currentData()
        if pid:
            self._load_profile(pid)

    def _load_profile(self, profile_id: str) -> None:
        """Fill form fields from selected profile data."""
        self._current_profile_id = profile_id
        prof = KeyStorage.get_profile(profile_id)
        if not prof:
            return

        provider_id = prof.get("provider_id", "openai_compat")
        preset = PROVIDER_PRESETS.get(provider_id, PROVIDER_PRESETS["custom"])
        self.lbl_description.setText(preset.get("description", ""))

        self.edit_profile_name.setText(prof.get("name", ""))

        # Provider combo
        idx = self.combo_provider.findData(provider_id)
        if idx >= 0:
            self.combo_provider.blockSignals(True)
            self.combo_provider.setCurrentIndex(idx)
            self.combo_provider.blockSignals(False)

        # Base URL, API Key, Timeout, Proxy
        self.edit_base_url.setText(prof.get("base_url") or preset["default_base_url"])
        self.edit_api_key.setText(prof.get("api_key") or "")
        self.spin_timeout.setValue(int(prof.get("timeout") or 60))
        self.edit_proxy.setText(prof.get("proxy") or "")

        # Model
        model = prof.get("model_name") or preset["default_model"]
        self.combo_model.clear()
        self.combo_model.addItem(preset["default_model"])
        self.combo_model.setEditText(model)

        # Prompt mode and custom prompt
        prompt_mode = prof.get("prompt_mode", "builtin_optimized")
        idx_mode = self.combo_prompt_mode.findData(prompt_mode)
        if idx_mode >= 0:
            self.combo_prompt_mode.blockSignals(True)
            self.combo_prompt_mode.setCurrentIndex(idx_mode)
            self.combo_prompt_mode.blockSignals(False)

        custom_prompt = prof.get("custom_prompt", "")
        self._update_prompt_view(prompt_mode, custom_prompt, provider_id, model)

        # Active check
        active_id = KeyStorage.get_active_profile_id()
        self.chk_default.setChecked(profile_id == active_id)

        self.lbl_test_result.setText("点击 [测试当前 API 连接] 验证连通性，或点击 [获取模型列表] 查看可选模型。")
        self.lbl_test_result.setStyleSheet("color: #94A3B8; font-size: 13px;")

    def _on_new_profile(self) -> None:
        """Create a new blank profile template."""
        import time
        self._current_profile_id = f"prof_{int(time.time() * 1000)}"
        self.edit_profile_name.setText("新建网关配置")
        self.combo_provider.setCurrentIndex(0)  # Default OpenAI Compat / DeepSeek
        pid = self._get_current_provider_id()
        preset = PROVIDER_PRESETS.get(pid, PROVIDER_PRESETS["openai_compat"])

        self.edit_base_url.setText(preset["default_base_url"])
        self.edit_api_key.setText("")
        self.combo_model.clear()
        self.combo_model.addItem(preset["default_model"])
        self.combo_model.setEditText(preset["default_model"])
        self.spin_timeout.setValue(60)
        self.edit_proxy.setText("")
        self.combo_prompt_mode.setCurrentIndex(0)  # builtin_optimized
        self._update_prompt_view("builtin_optimized", "", pid, preset["default_model"])
        self.chk_default.setChecked(True)

    def _on_delete_profile(self) -> None:
        if not self._current_profile_id:
            return
        reply = QMessageBox.question(
            self,
            "确认删除网关",
            f"确定要永久删除网关配置【{self.edit_profile_name.text()}】吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            KeyStorage.delete_profile(self._current_profile_id)
            self._refresh_profile_list()
            QMessageBox.information(self, "已删除", "网关配置已删除。")

    def _on_provider_changed(self) -> None:
        pid = self._get_current_provider_id()
        preset = PROVIDER_PRESETS.get(pid, PROVIDER_PRESETS["custom"])
        self.lbl_description.setText(preset.get("description", ""))
        self.edit_base_url.setText(preset["default_base_url"])
        self.combo_model.clear()
        self.combo_model.addItem(preset["default_model"])
        self.combo_model.setEditText(preset["default_model"])
        mode = self.combo_prompt_mode.currentData()
        self._update_prompt_view(mode, self.text_custom_prompt.toPlainText(), pid, preset["default_model"])

    def _on_model_text_changed(self, text: str) -> None:
        mode = self.combo_prompt_mode.currentData()
        if mode == "builtin_optimized":
            pid = self._get_current_provider_id()
            self._update_prompt_view(mode, "", pid, text)

    def _on_prompt_mode_changed(self) -> None:
        mode = self.combo_prompt_mode.currentData()
        pid = self._get_current_provider_id()
        model = self.combo_model.currentText().strip()
        self._update_prompt_view(mode, self.text_custom_prompt.toPlainText(), pid, model)

    def _on_reset_prompt_clicked(self) -> None:
        pid = self._get_current_provider_id()
        model = self.combo_model.currentText().strip()
        recommended = PromptManager.get_default_prompt(f"{pid}_{model}")
        self.text_custom_prompt.setPlainText(recommended)
        self.combo_prompt_mode.setCurrentIndex(0)
        self.text_custom_prompt.setReadOnly(True)

    def _update_prompt_view(self, mode: str, custom_text: str, provider_id: str, model_name: str) -> None:
        if mode == "custom":
            self.text_custom_prompt.setReadOnly(False)
            if custom_text and custom_text.strip():
                self.text_custom_prompt.setPlainText(custom_text)
            else:
                recommended = PromptManager.get_default_prompt(f"{provider_id}_{model_name}")
                self.text_custom_prompt.setPlainText(recommended)
            self.text_custom_prompt.setStyleSheet("background-color: #1E293B; color: #F8FAFC; border: 1px solid #38BDF8;")
        elif mode == "builtin_optimized":
            self.text_custom_prompt.setReadOnly(True)
            recommended = PromptManager.get_default_prompt(f"{provider_id}_{model_name}")
            self.text_custom_prompt.setPlainText(recommended)
            self.text_custom_prompt.setStyleSheet("background-color: #0F172A; color: #94A3B8; border: 1px solid #334155;")
        else:  # default
            self.text_custom_prompt.setReadOnly(True)
            default_p = PromptManager.load_prompt("detect_markers")
            self.text_custom_prompt.setPlainText(default_p)
            self.text_custom_prompt.setStyleSheet("background-color: #0F172A; color: #94A3B8; border: 1px solid #334155;")

    def _on_reset_url(self) -> None:
        pid = self._get_current_provider_id()
        preset = PROVIDER_PRESETS.get(pid, PROVIDER_PRESETS["custom"])
        self.edit_base_url.setText(preset["default_base_url"])

    def _on_toggle_key_visibility(self) -> None:
        if self.edit_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("隐藏")
        else:
            self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("显示")

    def _on_fetch_models(self) -> None:
        """Fetch available models from the remote endpoint."""
        pid = self._get_current_provider_id()
        base_url = self.edit_base_url.text().strip()
        api_key = self.edit_api_key.text().strip()
        timeout = float(self.spin_timeout.value())
        proxy = self.edit_proxy.text().strip()

        if not api_key and "localhost" not in base_url:
            QMessageBox.warning(self, "缺少 Key", "请先输入 API Key 再获取模型列表。")
            return

        self.btn_fetch_models.setEnabled(False)
        self.progress_test.setVisible(True)
        self.lbl_test_result.setText("正在拉取可用模型列表...")
        self.lbl_test_result.setStyleSheet("color: #38BDF8;")

        self._fetch_worker = ModelFetchWorker(
            provider_id=pid,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            proxy=proxy,
        )
        self._fetch_worker.finished_fetch.connect(self._on_models_fetched)
        self._fetch_worker.start()

    def _on_models_fetched(self, success: bool, models: List[str], message: str) -> None:
        self.btn_fetch_models.setEnabled(True)
        self.progress_test.setVisible(False)

        if success and models:
            current_choice = self.combo_model.currentText()
            self.combo_model.clear()
            for m in models:
                self.combo_model.addItem(m)

            if current_choice and current_choice in models:
                self.combo_model.setCurrentText(current_choice)
            elif current_choice:
                self.combo_model.setEditText(current_choice)
            else:
                self.combo_model.setCurrentIndex(0)

            self.lbl_test_result.setText(f"✓ {message}")
            self.lbl_test_result.setStyleSheet("color: #34D399; font-weight: 700; font-size: 13.5px;")
        else:
            self.lbl_test_result.setText(f"✗ {message}")
            self.lbl_test_result.setStyleSheet("color: #F87171; font-weight: 700; font-size: 13.5px;")

    def _on_test_connection(self) -> None:
        pid = self._get_current_provider_id()
        base_url = self.edit_base_url.text().strip()
        api_key = self.edit_api_key.text().strip()
        model_name = self.combo_model.currentText().strip()
        timeout = float(self.spin_timeout.value())
        proxy = self.edit_proxy.text().strip()

        if not api_key and "localhost" not in base_url:
            QMessageBox.warning(self, "缺少 Key", "请先输入 API Key 再进行测试。")
            return

        self.btn_test.setEnabled(False)
        self.progress_test.setVisible(True)
        self.lbl_test_result.setText("正在测试连接与验证 Key...")
        self.lbl_test_result.setStyleSheet("color: #38BDF8; font-size: 13.5px;")

        self._test_worker = ConnectionTestWorker(
            provider_id=pid,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            proxy=proxy,
        )
        self._test_worker.finished_test.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success: bool, message: str) -> None:
        self.btn_test.setEnabled(True)
        self.progress_test.setVisible(False)
        if success:
            self.lbl_test_result.setText(f"✓ {message}")
            self.lbl_test_result.setStyleSheet("color: #34D399; font-weight: 700; font-size: 13.5px;")
        else:
            self.lbl_test_result.setText(f"✗ {message}")
            self.lbl_test_result.setStyleSheet("color: #F87171; font-weight: 700; font-size: 13.5px;")

    def _on_auto_fill_wsl_proxy(self) -> None:
        """Auto-detect WSL2 Windows host IP and fill in proxy field."""
        host_ip = "172.23.0.1"
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 3 and parts[1] == "00000000":
                        hex_ip = parts[2]
                        ip_bytes = [int(hex_ip[i:i+2], 16) for i in (6, 4, 2, 0)]
                        host_ip = ".".join(map(str, ip_bytes))
                        break
        except Exception:
            pass
        self.edit_proxy.setText(f"http://{host_ip}:7890")
        QMessageBox.information(
            self,
            "WSL2 宿主机代理设置提示",
            f"已自动填入宿主机代理地址：http://{host_ip}:7890\n\n"
            f"💡 关键使用注意：\n"
            f"1. 端口检查：若 Windows Clash/v2ray 使用的不是 7890 端口（例如 7897 或 10809），请将端口数字对应修改。\n"
            f"2. 局域网开关：请务必在 Windows 代理软件设置中打开【允许来自局域网的连接 / Allow LAN】！"
        )

    def _on_diagnose_network(self) -> None:
        """Quickly test network DNS and connectivity inside WSL2."""
        import socket
        results = []
        for host in ["generativelanguage.googleapis.com", "api.deepseek.com", "api.openai.com"]:
            try:
                ip = socket.gethostbyname(host)
                is_fake = ip.startswith("198.18.")
                tag = " (Fake-IP/TUN模式)" if is_fake else " (真实IP解析)"
                results.append(f"• {host} ➔ {ip}{tag}")
            except Exception as e:
                results.append(f"• {host} ➔ 解析失败: {e}")

        diag_text = "WSL2 当前网络环境诊断报告：\n\n" + "\n".join(results)
        if any("198.18." in r for r in results):
            diag_text += "\n\n💡 诊断发现：当前 DNS 返回了 198.18.x.x (Clash TUN Fake-IP)。\n若接口报错 timed out，说明 Windows 虚拟网卡未将报文转发入 TUN。\n解决方案：点击【⚡ 填入宿主机代理】并确保 Windows 代理开启【允许局域网连接】。"

        QMessageBox.information(self, "WSL2 网络环境诊断", diag_text)

    def _on_save(self) -> None:
        pid = self._get_current_provider_id()
        base_url = self.edit_base_url.text().strip()
        api_key = self.edit_api_key.text().strip()
        model_name = self.combo_model.currentText().strip()
        timeout = float(self.spin_timeout.value())
        proxy = self.edit_proxy.text().strip()
        is_default = self.chk_default.isChecked()
        prof_name = self.edit_profile_name.text().strip() or "未命名网关"

        prompt_mode = self.combo_prompt_mode.currentData() or "builtin_optimized"
        custom_prompt = self.text_custom_prompt.toPlainText().strip()

        if not model_name:
            preset = PROVIDER_PRESETS.get(pid, {})
            model_name = preset.get("default_model", "")

        profile_data = {
            "profile_id": self._current_profile_id,
            "name": prof_name,
            "provider_id": pid,
            "base_url": base_url,
            "api_key": api_key,
            "model_name": model_name,
            "timeout": timeout,
            "proxy": proxy,
            "prompt_mode": prompt_mode,
            "custom_prompt": custom_prompt,
        }

        saved_id = KeyStorage.save_profile(profile_data, set_active=is_default)
        self._current_profile_id = saved_id

        # Reload profiles combo so user sees updated name & badge
        self._refresh_profile_list()

        status_text = "【已设为当前激活生效网关】" if is_default else "【配置已保存，可随时切换】"
        QMessageBox.information(
            self,
            "保存成功",
            f"已成功加密保存网关配置【{prof_name}】！\n"
            f"当前状态: {status_text}\n"
            f"生效模型: {model_name}\n"
            f"Key 预览: {mask_api_key(api_key)}",
        )
        self.settings_saved.emit(pid)
        self.accept()

    def _on_delete_key(self) -> None:
        self.edit_api_key.setText("")
        QMessageBox.information(self, "已清空", "当前界面的 Key 已清空，点击【保存配置】即可生效。")

    def closeEvent(self, event) -> None:
        """Safely terminate any background worker threads when closing window."""
        if self._test_worker and self._test_worker.isRunning():
            self._test_worker.terminate()
            self._test_worker.wait(1000)
        if self._fetch_worker and self._fetch_worker.isRunning():
            self._fetch_worker.terminate()
            self._fetch_worker.wait(1000)
        super().closeEvent(event)

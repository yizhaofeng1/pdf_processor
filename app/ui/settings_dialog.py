"""Settings and API Gateway Management Dialog with Model Fetching capabilities."""

from typing import Optional, List
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
)
from PySide6.QtCore import Qt, QThread, Signal

from ..ai.provider_factory import ProviderFactory, PROVIDER_PRESETS
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
    """Dialog for configuring AI API gateways, Base URLs, models, and encrypted keys."""

    settings_saved = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 模型与 API 网关设置")
        self.resize(680, 600)
        self.setModal(True)

        self._test_worker: Optional[ConnectionTestWorker] = None
        self._fetch_worker: Optional[ModelFetchWorker] = None
        self._setup_ui()
        self._load_initial_state()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Provider Selection Group
        group = QGroupBox("模型服务商配置")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(12)

        # Provider Selector
        self.combo_provider = QComboBox()
        for pid, preset in PROVIDER_PRESETS.items():
            self.combo_provider.addItem(preset["display_name"], pid)
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("选择服务商:", self.combo_provider)

        # Description Label
        self.lbl_description = QLabel("")
        self.lbl_description.setStyleSheet("color: #94A3B8; font-size: 13.5px; font-style: italic;")
        self.lbl_description.setWordWrap(True)
        form.addRow("", self.lbl_description)

        # Base URL
        url_layout = QHBoxLayout()
        self.edit_base_url = QLineEdit()
        self.edit_base_url.setPlaceholderText("https://...")
        self.btn_reset_url = QPushButton("重置为默认")
        self.btn_reset_url.setToolTip("恢复该服务商的官方默认地址")
        self.btn_reset_url.clicked.connect(self._on_reset_url)
        url_layout.addWidget(self.edit_base_url)
        url_layout.addWidget(self.btn_reset_url)
        form.addRow("API 地址 (URL):", url_layout)

        # API Key with show/hide toggle
        key_layout = QHBoxLayout()
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_api_key.setPlaceholderText("请输入 API Key (保存在本地加密文件)")

        self.btn_toggle_key = QPushButton("显示")
        self.btn_toggle_key.setFixedWidth(60)
        self.btn_toggle_key.clicked.connect(self._on_toggle_key_visibility)

        key_layout.addWidget(self.edit_api_key)
        key_layout.addWidget(self.btn_toggle_key)
        form.addRow("API Key:", key_layout)

        # Encryption indicator
        enc_layout = QHBoxLayout()
        lbl_security = QLabel("🔒 密钥将使用机器绑定密钥加密存储至本地，绝不上传或泄露")
        lbl_security.setStyleSheet("color: #34D399; font-size: 13px; font-weight: 600;")
        enc_layout.addWidget(lbl_security)
        form.addRow("", enc_layout)

        # Model Selector with Online Fetch Button
        model_layout = QHBoxLayout()
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_model.lineEdit().setPlaceholderText("下拉选择或输入模型，例如 gemini-2.5-flash")

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

        # Default Provider Checkbox
        self.chk_default = QCheckBox("同时设为当前激活生效的服务商 (推荐)")
        self.chk_default.setChecked(True)
        self.chk_default.setStyleSheet("font-weight: 600; color: #38BDF8;")
        form.addRow("", self.chk_default)

        main_layout.addWidget(group)

        # 2. Connection Test Section
        test_group = QGroupBox("连通性与模型检测")
        test_layout = QVBoxLayout(test_group)
        test_layout.setSpacing(10)

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
        self.lbl_test_result.setStyleSheet("color: #94A3B8; font-size: 13.5px;")
        test_layout.addWidget(self.lbl_test_result)

        main_layout.addWidget(test_group)

        # 3. Bottom Action Buttons
        btn_box = QHBoxLayout()
        self.btn_delete = QPushButton("清空此服务商 Key")
        self.btn_delete.setStyleSheet("color: #d32f2f;")
        self.btn_delete.clicked.connect(self._on_delete_key)
        btn_box.addWidget(self.btn_delete)

        btn_box.addStretch()

        self.btn_save = QPushButton("保存配置")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_close)

        main_layout.addLayout(btn_box)

    def _get_current_provider_id(self) -> str:
        return self.combo_provider.currentData()

    def _load_initial_state(self) -> None:
        """Load default active provider and fill UI."""
        default_id = KeyStorage.get_default_provider_id()
        idx = self.combo_provider.findData(default_id)
        if idx >= 0:
            self.combo_provider.setCurrentIndex(idx)
        else:
            self._load_provider_fields(self._get_current_provider_id())

    def _on_provider_changed(self) -> None:
        pid = self._get_current_provider_id()
        self._load_provider_fields(pid)

    def _load_provider_fields(self, pid: str) -> None:
        preset = PROVIDER_PRESETS.get(pid, PROVIDER_PRESETS["custom"])
        self.lbl_description.setText(preset.get("description", ""))

        cfg = KeyStorage.get_provider_config(pid)
        all_configs = KeyStorage.get_all_configs()
        default_pid = KeyStorage.get_default_provider_id()

        saved_model = (cfg.get("model_name") if cfg else None) or preset["default_model"]

        # Populate model dropdown with preset default first
        self.combo_model.clear()
        self.combo_model.addItem(preset["default_model"])
        self.combo_model.setEditText(saved_model)
        if self.combo_model.lineEdit():
            self.combo_model.lineEdit().setPlaceholderText(f"下拉选择或输入模型，例如 {preset['default_model']}")

        if cfg:
            self.edit_base_url.setText(cfg.get("base_url") or preset["default_base_url"])
            self.edit_api_key.setText(cfg.get("api_key") or "")
            self.spin_timeout.setValue(int(cfg.get("timeout") or 60))
            self.edit_proxy.setText(cfg.get("proxy") or all_configs.get("proxy", ""))
        else:
            self.edit_base_url.setText(preset["default_base_url"])
            self.edit_api_key.setText("")
            self.spin_timeout.setValue(60)
            self.edit_proxy.setText(all_configs.get("proxy", ""))

        # Always check this by default when user edits a provider
        self.chk_default.setChecked(True)
        self.lbl_test_result.setText("点击 [测试当前 API 连接] 验证连通性，或点击 [获取模型列表] 查看可选模型。")
        self.lbl_test_result.setStyleSheet("color: #555555; font-size: 12px;")

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
        self.lbl_test_result.setStyleSheet("color: #1976d2;")

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

        if not model_name:
            preset = PROVIDER_PRESETS.get(pid, {})
            model_name = preset.get("default_model", "")

        KeyStorage.save_provider_config(
            provider_id=pid,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            proxy=proxy,
            is_default=is_default,
        )

        if is_default:
            KeyStorage.set_default_provider_id(pid)

        status_text = "【已设为当前激活生效模型】" if is_default else "【配置已保存，未激活】"
        QMessageBox.information(
            self,
            "保存成功",
            f"已成功加密保存 {self.combo_provider.currentText()} 配置！\n"
            f"当前状态: {status_text}\n"
            f"生效模型: {model_name}\n"
            f"Key 预览: {mask_api_key(api_key)}",
        )
        self.settings_saved.emit(pid)
        self.accept()

    def _on_delete_key(self) -> None:
        pid = self._get_current_provider_id()
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 {self.combo_provider.currentText()} 的保存密钥吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            KeyStorage.delete_provider_config(pid)
            self._load_provider_fields(pid)
            QMessageBox.information(self, "已清空", "已成功删除保存的配置。")

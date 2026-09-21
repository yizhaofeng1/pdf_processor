"""Unit tests for SettingsDialog UI interaction."""

from PySide6.QtWidgets import QLineEdit
from app.ui.settings_dialog import SettingsDialog
from app.storage.key_storage import KeyStorage


def test_settings_dialog_initialization(qtbot):
    """Verify dialog initializes with providers and auto-fills values."""
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert "AI 模型与 API 网关设置" in dialog.windowTitle()
    assert dialog.combo_provider.count() >= 6

    # Select deepseek
    idx = dialog.combo_provider.findData("deepseek")
    assert idx >= 0
    dialog.combo_provider.setCurrentIndex(idx)

    assert "api.deepseek.com" in dialog.edit_base_url.text()
    assert "deepseek" in dialog.combo_model.currentText()


def test_settings_dialog_toggle_password(qtbot):
    """Verify password visibility toggle button."""
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog.edit_api_key.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.btn_toggle_key.text() == "显示"

    dialog.btn_toggle_key.click()
    assert dialog.edit_api_key.echoMode() == QLineEdit.EchoMode.Normal
    assert dialog.btn_toggle_key.text() == "隐藏"

    dialog.btn_toggle_key.click()
    assert dialog.edit_api_key.echoMode() == QLineEdit.EchoMode.Password


def test_settings_dialog_save_flow(qtbot, tmp_path, monkeypatch):
    """Verify saving from UI encrypts and updates KeyStorage."""
    test_cred_file = tmp_path / "credentials.enc"
    monkeypatch.setattr("app.storage.key_storage.CREDENTIALS_FILE", test_cred_file)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None)
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    # Select custom provider
    idx = dialog.combo_provider.findData("custom")
    dialog.combo_provider.setCurrentIndex(idx)

    dialog.edit_base_url.setText("https://custom-proxy.example.com/v1")
    dialog.edit_api_key.setText("sk-custom-test-key-999")
    dialog.combo_model.setEditText("custom-vision-model")
    dialog.chk_default.setChecked(True)

    dialog._on_save()

    cfg = KeyStorage.get_provider_config("custom")
    assert cfg is not None
    assert cfg["api_key"] == "sk-custom-test-key-999"
    assert cfg["base_url"] == "https://custom-proxy.example.com/v1"
    assert cfg["model_name"] == "custom-vision-model"
    assert KeyStorage.get_default_provider_id() == "custom"

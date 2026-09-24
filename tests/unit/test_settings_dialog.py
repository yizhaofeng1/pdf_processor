"""Unit tests for SettingsDialog UI interaction and multi-profile gateway management."""

from PySide6.QtWidgets import QLineEdit
from app.ui.settings_dialog import SettingsDialog
from app.storage.key_storage import KeyStorage
from app.ai.prompt_manager import PromptManager


def test_settings_dialog_initialization(qtbot):
    """Verify dialog initializes with providers and auto-fills values."""
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert "AI 模型" in dialog.windowTitle()
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

    dialog.edit_profile_name.setText("我的自建网关")
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

    active_prof = KeyStorage.get_active_profile()
    assert active_prof is not None
    assert active_prof["name"] == "我的自建网关"


def test_multi_profile_creation_and_switching(qtbot, tmp_path, monkeypatch):
    """Verify creating and switching between multiple saved gateway profiles."""
    test_cred_file = tmp_path / "credentials.enc"
    monkeypatch.setattr("app.storage.key_storage.CREDENTIALS_FILE", test_cred_file)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None)

    # 1. Save profile 1: DeepSeek Official
    prof1 = {
        "profile_id": "prof_ds_1",
        "name": "DeepSeek 官方主力",
        "provider_id": "openai_compat",
        "base_url": "https://api.deepseek.com",
        "api_key": "sk-ds-key-111",
        "model_name": "deepseek-chat",
        "prompt_mode": "builtin_optimized",
    }
    KeyStorage.save_profile(prof1, set_active=True)

    # 2. Save profile 2: SiliconFlow DeepSeek
    prof2 = {
        "profile_id": "prof_sf_2",
        "name": "硅基流动 DeepSeek",
        "provider_id": "openai_compat",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-sf-key-222",
        "model_name": "deepseek-ai/DeepSeek-V3",
        "prompt_mode": "custom",
        "custom_prompt": "自定义专用提示词",
    }
    KeyStorage.save_profile(prof2, set_active=False)

    all_profs = KeyStorage.get_all_profiles()
    assert len(all_profs) >= 2
    assert "prof_ds_1" in all_profs
    assert "prof_sf_2" in all_profs

    # Active profile is prof_ds_1
    assert KeyStorage.get_active_profile_id() == "prof_ds_1"

    # Switch to prof_sf_2
    KeyStorage.set_active_profile_id("prof_sf_2")
    assert KeyStorage.get_active_profile_id() == "prof_sf_2"
    active = KeyStorage.get_active_profile()
    assert active["name"] == "硅基流动 DeepSeek"
    assert active["api_key"] == "sk-sf-key-222"
    assert active["custom_prompt"] == "自定义专用提示词"


def test_deepseek_prompt_routing_and_default():
    """Verify PromptManager routes to DeepSeek optimized prompt for DeepSeek models."""
    prompt_ds = PromptManager.get_default_prompt("deepseek-chat")
    assert "DeepSeek" in prompt_ds
    assert "密集排版" in prompt_ds

    prompt_gemini = PromptManager.get_default_prompt("gemini-2.5-flash")
    assert "ExamSplit Visual Analyzer" in prompt_gemini

    # Model hints routing
    sys_prompt = PromptManager.get_system_prompt("detect_markers", {"model_name": "deepseek-chat"})
    assert "DeepSeek" in sys_prompt

    # Custom prompt override
    custom_sys = PromptManager.get_system_prompt("detect_markers", {"custom_prompt": "我的完全独立提示词"})
    assert "我的完全独立提示词" in custom_sys

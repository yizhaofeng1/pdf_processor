"""Unit tests for encrypted KeyStorage module."""

import pytest
from pathlib import Path

from app.storage.key_storage import KeyStorage, mask_api_key, CREDENTIALS_FILE


def test_mask_api_key():
    """Verify masking keeps sensitive keys hidden in UI."""
    assert mask_api_key("") == ""
    assert mask_api_key("12345") == "******"
    long_key = "SAMPLE_DUMMY_KEY_ABCDEF1234567890_XYZ_EXAMPLE_9999"
    masked = mask_api_key(long_key)
    assert masked.startswith("SAMPLE")
    assert masked.endswith("9999")
    assert "..." in masked
    assert len(masked) < len(long_key)


def test_key_storage_crud(tmp_path, monkeypatch):
    """Verify encrypted save, retrieve, update, and delete operations."""
    test_cred_file = tmp_path / "credentials.enc"
    monkeypatch.setattr("app.storage.key_storage.CREDENTIALS_FILE", test_cred_file)
    test_key = "sk-test-secret-key-1234567890"

    # Save
    KeyStorage.save_provider_config(
        provider_id="test_provider",
        base_url="https://api.test.com/v1",
        api_key=test_key,
        model_name="test-model",
        timeout=45.0,
        proxy="http://127.0.0.1:10809",
        is_default=True,
    )

    # File must be encrypted binary ciphertext, not containing plain-text key
    assert CREDENTIALS_FILE.exists()
    raw_content = CREDENTIALS_FILE.read_text(errors="ignore")
    assert test_key not in raw_content

    # Load decrypted
    cfg = KeyStorage.get_provider_config("test_provider")
    assert cfg is not None
    assert cfg["api_key"] == test_key
    assert cfg["base_url"] == "https://api.test.com/v1"
    assert cfg["model_name"] == "test-model"
    assert cfg["timeout"] == 45.0
    assert cfg["proxy"] == "http://127.0.0.1:10809"

    # Default provider check
    assert KeyStorage.get_default_provider_id() == "test_provider"

    # Delete
    KeyStorage.delete_provider_config("test_provider")
    assert KeyStorage.get_provider_config("test_provider") is None

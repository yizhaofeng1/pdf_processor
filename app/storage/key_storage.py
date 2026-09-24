"""Encrypted storage for API keys and provider configurations.

AGENTS.md Compliance:
- Never save plain-text API keys in logs, SQLite, or export JSON.
- Encrypts keys at rest using machine-bound PBKDF2 + AES (Fernet).
"""

import os
import json
import base64
import getpass
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config import DATA_DIR, ensure_data_directories

logger = logging.getLogger("examsplit.security")

SALT_FILE = DATA_DIR / ".salt"
MACHINE_SECRET_FILE = DATA_DIR / ".machine_secret"
CREDENTIALS_FILE = DATA_DIR / "credentials.enc"


def _get_or_create_salt() -> bytes:
    """Read existing salt or create a secure 16-byte random salt."""
    ensure_data_directories()
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = os.urandom(16)
    SALT_FILE.write_bytes(salt)
    try:
        SALT_FILE.chmod(0o600)
    except Exception:
        pass
    return salt


def _get_or_create_machine_secret() -> bytes:
    """Read existing machine secret or create a secure 32-byte persistent secret."""
    ensure_data_directories()
    if MACHINE_SECRET_FILE.exists():
        try:
            sec = MACHINE_SECRET_FILE.read_bytes()
            if len(sec) >= 16:
                return sec
        except Exception:
            pass
    secret = os.urandom(32)
    MACHINE_SECRET_FILE.write_bytes(secret)
    try:
        MACHINE_SECRET_FILE.chmod(0o600)
    except Exception:
        pass
    return secret


def _get_cipher() -> Fernet:
    """Derive persistent machine-and-user-bound Fernet cipher."""
    salt = _get_or_create_salt()
    user = getpass.getuser()
    machine_secret = _get_or_create_machine_secret()
    secret_material = f"{user}:".encode("utf-8") + machine_secret + b":ExamSplitAI_SecureKeyStore_v2"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret_material))
    return Fernet(key)


def mask_api_key(api_key: str) -> str:
    """Return masked key for safe display in UI (e.g. 'AQ.Ab8...NCwg')."""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "******"
    return f"{api_key[:6]}...{api_key[-4:]}"


class KeyStorage:
    """Handles encrypted reading and writing of AI provider configurations."""

    @classmethod
    def _read_raw_store(cls) -> Dict[str, Any]:
        ensure_data_directories()
        if not CREDENTIALS_FILE.exists():
            return {
                "default_provider": "gemini",
                "proxy": "",
                "providers": {},
            }
        try:
            cipher = _get_cipher()
            encrypted_data = CREDENTIALS_FILE.read_bytes()
            decrypted = cipher.decrypt(encrypted_data)
            return json.loads(decrypted.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Encrypted credentials file could not be read (resetting): {e}")
            # Reset damaged or old credentials file
            initial_data = {
                "default_provider": "gemini",
                "proxy": "",
                "providers": {},
            }
            try:
                cls._write_raw_store(initial_data)
            except Exception:
                pass
            return initial_data

    @classmethod
    def _write_raw_store(cls, data: Dict[str, Any]) -> None:
        ensure_data_directories()
        cipher = _get_cipher()
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted = cipher.encrypt(payload)
        CREDENTIALS_FILE.write_bytes(encrypted)
        try:
            CREDENTIALS_FILE.chmod(0o600)
        except Exception:
            pass

    @classmethod
    def save_provider_config(
        cls,
        provider_id: str,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: float = 60.0,
        proxy: str = "",
        is_default: bool = True,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Encrypt and save configuration for a given provider (legacy compat)."""
        store = cls._read_raw_store()
        providers = store.setdefault("providers", {})
        providers[provider_id] = {
            "provider_id": provider_id,
            "base_url": base_url.strip(),
            "api_key": api_key.strip(),
            "model_name": model_name.strip(),
            "timeout": timeout,
            "proxy": proxy.strip(),
            "extra": extra or {},
        }
        if is_default or not store.get("default_provider") or bool(api_key.strip()):
            store["default_provider"] = provider_id
        if proxy:
            store["proxy"] = proxy.strip()

        # Also sync to profiles if active or matching profile exists
        cls._sync_provider_to_profile(store, provider_id, providers[provider_id], is_default)
        cls._write_raw_store(store)
        logger.info(f"Encrypted and stored configuration for provider: {provider_id}")

    @classmethod
    def _sync_provider_to_profile(cls, store: Dict[str, Any], provider_id: str, cfg: Dict[str, Any], is_active: bool) -> None:
        profiles = store.setdefault("profiles", {})
        # Find matching profile or create one
        matched_id = None
        for pid, p in profiles.items():
            if p.get("provider_id") == provider_id and p.get("base_url") == cfg.get("base_url"):
                matched_id = pid
                break
        if not matched_id:
            matched_id = f"prof_{provider_id}"
            default_name = "DeepSeek / OpenAI 兼容" if provider_id == "openai_compat" else ("Google Gemini 官方" if provider_id == "gemini" else f"网关 - {provider_id}")
            profiles[matched_id] = {
                "profile_id": matched_id,
                "name": default_name,
                "provider_id": provider_id,
                "base_url": cfg.get("base_url", ""),
                "api_key": cfg.get("api_key", ""),
                "model_name": cfg.get("model_name", ""),
                "timeout": cfg.get("timeout", 60.0),
                "proxy": cfg.get("proxy", ""),
                "prompt_mode": "builtin_optimized" if "deepseek" in (cfg.get("model_name", "") + cfg.get("base_url", "")).lower() else "default",
                "custom_prompt": "",
            }
        else:
            profiles[matched_id].update({
                "base_url": cfg.get("base_url", ""),
                "api_key": cfg.get("api_key", ""),
                "model_name": cfg.get("model_name", ""),
                "timeout": cfg.get("timeout", 60.0),
                "proxy": cfg.get("proxy", ""),
            })
        if is_active or not store.get("active_profile_id"):
            store["active_profile_id"] = matched_id

    @classmethod
    def get_all_profiles(cls) -> Dict[str, Dict[str, Any]]:
        """Retrieve all saved gateway profiles, migrating from providers if needed."""
        store = cls._read_raw_store()
        profiles = store.get("profiles", {})
        if not profiles:
            # Auto-migrate from existing legacy providers if any exist
            providers = store.get("providers", {})
            for pid, cfg in providers.items():
                cls._sync_provider_to_profile(store, pid, cfg, is_active=(store.get("default_provider") == pid))
            cls._write_raw_store(store)
            profiles = store.get("profiles", {})
        return profiles

    @classmethod
    def get_profile(cls, profile_id: str) -> Optional[Dict[str, Any]]:
        profiles = cls.get_all_profiles()
        return profiles.get(profile_id)

    @classmethod
    def get_active_profile_id(cls) -> str:
        store = cls._read_raw_store()
        profiles = store.get("profiles", {})
        active_id = store.get("active_profile_id")
        if active_id and active_id in profiles:
            return active_id
        # Fallback to first profile with key or first profile
        for pid, p in profiles.items():
            if p.get("api_key"):
                return pid
        return next(iter(profiles.keys()), "")

    @classmethod
    def set_active_profile_id(cls, profile_id: str) -> None:
        store = cls._read_raw_store()
        profiles = store.get("profiles", {})
        if profile_id in profiles:
            store["active_profile_id"] = profile_id
            prof = profiles[profile_id]
            provider_id = prof.get("provider_id", "gemini")
            store["default_provider"] = provider_id
            # Also sync into legacy provider map
            providers = store.setdefault("providers", {})
            providers[provider_id] = {
                "provider_id": provider_id,
                "base_url": prof.get("base_url", ""),
                "api_key": prof.get("api_key", ""),
                "model_name": prof.get("model_name", ""),
                "timeout": prof.get("timeout", 60.0),
                "proxy": prof.get("proxy", ""),
                "extra": prof.get("extra", {}),
            }
            cls._write_raw_store(store)
            logger.info(f"Activated gateway profile: {profile_id} ({prof.get('name')})")

    @classmethod
    def get_active_profile(cls) -> Optional[Dict[str, Any]]:
        active_id = cls.get_active_profile_id()
        if active_id:
            return cls.get_profile(active_id)
        return None

    @classmethod
    def save_profile(cls, profile_data: Dict[str, Any], set_active: bool = False) -> str:
        """Save or update a gateway profile in encrypted storage."""
        import time
        store = cls._read_raw_store()
        profiles = store.setdefault("profiles", {})
        profile_id = profile_data.get("profile_id")
        if not profile_id:
            profile_id = f"prof_{int(time.time() * 1000)}"
            profile_data["profile_id"] = profile_id

        # Clean string values
        profile_data["name"] = profile_data.get("name", "未命名网关").strip()
        profile_data["base_url"] = profile_data.get("base_url", "").strip()
        profile_data["api_key"] = profile_data.get("api_key", "").strip()
        profile_data["model_name"] = profile_data.get("model_name", "").strip()
        profile_data["proxy"] = profile_data.get("proxy", "").strip()
        profile_data["prompt_mode"] = profile_data.get("prompt_mode", "default")
        profile_data["custom_prompt"] = profile_data.get("custom_prompt", "").strip()

        profiles[profile_id] = profile_data

        # If set active or active is not set
        if set_active or not store.get("active_profile_id"):
            store["active_profile_id"] = profile_id
            provider_id = profile_data.get("provider_id", "gemini")
            store["default_provider"] = provider_id
            providers = store.setdefault("providers", {})
            providers[provider_id] = {
                "provider_id": provider_id,
                "base_url": profile_data["base_url"],
                "api_key": profile_data["api_key"],
                "model_name": profile_data["model_name"],
                "timeout": profile_data.get("timeout", 60.0),
                "proxy": profile_data["proxy"],
                "extra": profile_data.get("extra", {}),
            }

        cls._write_raw_store(store)
        logger.info(f"Saved gateway profile '{profile_data['name']}' (ID: {profile_id}, active: {store.get('active_profile_id') == profile_id})")
        return profile_id

    @classmethod
    def delete_profile(cls, profile_id: str) -> None:
        """Delete a gateway profile from storage."""
        store = cls._read_raw_store()
        profiles = store.get("profiles", {})
        if profile_id in profiles:
            del profiles[profile_id]
            if store.get("active_profile_id") == profile_id:
                store["active_profile_id"] = next(iter(profiles.keys()), "")
            cls._write_raw_store(store)
            logger.info(f"Deleted gateway profile: {profile_id}")

    @classmethod
    def get_provider_config(cls, provider_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted configuration for provider."""
        store = cls._read_raw_store()
        cfg = store.get("providers", {}).get(provider_id)
        if cfg:
            return cfg

        active_id = store.get("active_profile_id")
        if active_id and active_id in store.get("profiles", {}):
            active_prof = store["profiles"][active_id]
            if active_prof.get("provider_id") == provider_id:
                return active_prof
        return None

    @classmethod
    def get_all_configs(cls) -> Dict[str, Any]:
        """Retrieve all decrypted configs."""
        return cls._read_raw_store()

    @classmethod
    def delete_provider_config(cls, provider_id: str) -> None:
        """Remove key and configuration for provider."""
        store = cls._read_raw_store()
        if provider_id in store.get("providers", {}):
            del store["providers"][provider_id]
        # Also remove matching profiles
        profiles = store.get("profiles", {})
        to_del = [pid for pid, p in profiles.items() if p.get("provider_id") == provider_id]
        for pid in to_del:
            del profiles[pid]
        if store.get("default_provider") == provider_id:
            remaining = list(store.get("providers", {}).keys())
            store["default_provider"] = remaining[0] if remaining else ""
        if store.get("active_profile_id") in to_del:
            store["active_profile_id"] = next(iter(profiles.keys()), "")
        cls._write_raw_store(store)
        logger.info(f"Deleted configuration for provider: {provider_id}")

    @classmethod
    def get_default_provider_id(cls) -> str:
        """Get currently active provider ID, prioritizing configured providers."""
        active_prof = cls.get_active_profile()
        if active_prof and active_prof.get("provider_id"):
            return active_prof["provider_id"]

        store = cls._read_raw_store()
        default_pid = store.get("default_provider")
        providers = store.get("providers", {})

        if default_pid and default_pid in providers and providers[default_pid].get("api_key"):
            return default_pid

        for pid, cfg in providers.items():
            if cfg.get("api_key"):
                return pid

        return default_pid or "gemini"

    @classmethod
    def set_default_provider_id(cls, provider_id: str) -> None:
        store = cls._read_raw_store()
        store["default_provider"] = provider_id
        # Also switch active profile if a profile with this provider exists
        profiles = store.get("profiles", {})
        for pid, prof in profiles.items():
            if prof.get("provider_id") == provider_id:
                store["active_profile_id"] = pid
                break
        cls._write_raw_store(store)
        logger.info(f"Updated default active provider to: {provider_id}")

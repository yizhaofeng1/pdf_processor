"""Local Vision Provider: Abstract interface and OpenAI-compatible implementation for local VLMs."""

from abc import ABC, abstractmethod
from typing import Tuple, List, Optional, Dict, Any
from pathlib import Path
import base64
import json
import logging
import httpx
import re

from .config import LocalVisionConfig
from ...ai.response_parser import extract_json_block

logger = logging.getLogger("examsplit.experimental.provider")


def encode_image_base64(image_path: str | Path) -> str:
    """Encode an image file to a base64 string."""
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    return base64.b64encode(p.read_bytes()).decode("utf-8")


def _repair_truncated_json(json_str: str) -> Optional[str]:
    """Attempt to repair a truncated JSON string by closing the last complete question object and array."""
    text = json_str.strip()
    last_brace = text.rfind("}")
    if last_brace == -1:
        return None
    repaired = text[: last_brace + 1].strip().rstrip(",")
    open_brackets = repaired.count("[") - repaired.count("]")
    open_braces = repaired.count("{") - repaired.count("}")
    if open_brackets > 0:
        repaired += "\n" + "]" * open_brackets
    if open_braces > 0:
        repaired += "\n" + "}" * open_braces
    return repaired


class LocalVisionProvider(ABC):
    """Abstract interface for local vision models (Ollama, LM Studio, vLLM, etc.)."""

    def __init__(self, config: LocalVisionConfig) -> None:
        self.config = config

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Test endpoint reachability and model availability."""
        raise NotImplementedError

    @abstractmethod
    def fetch_available_models(self) -> List[str]:
        """Fetch list of available models from local endpoint."""
        raise NotImplementedError

    @abstractmethod
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Send image and prompt to local VLM and return parsed JSON dictionary."""
        raise NotImplementedError


class OpenAILocalVisionProvider(LocalVisionProvider):
    """Local provider implementation for any OpenAI-compatible Vision API endpoint."""

    def __init__(self, config: LocalVisionConfig) -> None:
        super().__init__(config)
        self.base_url = config.endpoint.rstrip("/")
        self.api_key = (config.api_key or "local").strip()
        self.model = config.model.strip()
        self.timeout = config.timeout_seconds

    def _create_client(self) -> httpx.Client:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            follow_redirects=True,
        )

    def test_connection(self) -> Tuple[bool, str]:
        """Test API connectivity and model accessibility."""
        try:
            with self._create_client() as client:
                resp = client.get("/models")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", []) if "id" in m]
                    if self.model in models:
                        return True, f"连接成功！找到指定模型: {self.model}"
                    elif any(self.model in m for m in models):
                        matching = [m for m in models if self.model in m]
                        return True, f"连接成功！匹配到模型: {', '.join(matching)}"
                    elif models:
                        return False, f"端点连接成功，但指定模型 '{self.model}' 不存在！\n当前端点已安装模型: {', '.join(models)}。\n请在下拉列表中选择正确模型（例如: '{models[0]}'）。"
                    return True, "端点连接正常！"
                else:
                    return False, f"端点响应异常 HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, f"连接失败: {e}"

    def fetch_available_models(self) -> List[str]:
        """Query /models for available model identifiers."""
        try:
            with self._create_client() as client:
                resp = client.get("/models")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", []) if "id" in m]
                    return sorted(models)
        except Exception as e:
            logger.warning(f"Failed to fetch models from {self.base_url}: {e}")
        return []

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Send vision request with automatic JSON extraction and retry on parse failure."""
        b64_image = encode_image_base64(image_path)
        img_suffix = Path(image_path).suffix.lower().replace(".", "")
        mime_type = f"image/{img_suffix}" if img_suffix in ("png", "jpeg", "jpg", "webp") else "image/png"

        messages: List[Dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        user_content: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{b64_image}",
                },
            },
        ]
        messages.append({"role": "user", "content": user_content})

        last_error = None
        raw_text = ""
        finish_reason = None

        with self._create_client() as client:
            for attempt in range(max_retries):
                try:
                    payload: Dict[str, Any] = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1,
                    }
                    num_ctx = getattr(self.config, "num_ctx", 8192)
                    if num_ctx:
                        payload["options"] = {"num_ctx": num_ctx}

                    resp = client.post("/chat/completions", json=payload)
                    if resp.status_code == 404:
                        error_detail = resp.text
                        raise RuntimeError(
                            f"本地模型服务返回 404: 模型 '{self.model}' 不存在！\n"
                            f"请检查模型名称是否输入准确（例如 Ollama 中应为 'qwen2.5vl:3b' 而非 'qwen2.5-vl'）。\n"
                            f"服务端详细信息: {error_detail}"
                        )
                    elif resp.status_code >= 400:
                        error_detail = resp.text
                        logger.error(f"Local VLM HTTP {resp.status_code} error: {error_detail}")
                        raise RuntimeError(f"Local vision API HTTP {resp.status_code}: {error_detail}")

                    resp.raise_for_status()

                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise ValueError("Model returned empty choices array")

                    raw_text = choices[0].get("message", {}).get("content", "")
                    finish_reason = choices[0].get("finish_reason")

                    # Extract and parse JSON
                    json_str = extract_json_block(raw_text)
                    try:
                        parsed = json.loads(json_str)
                    except json.JSONDecodeError as jde:
                        repaired = _repair_truncated_json(json_str)
                        if repaired:
                            try:
                                parsed = json.loads(repaired)
                                logger.info("Successfully repaired truncated JSON from VLM output")
                            except Exception:
                                raise jde
                        else:
                            raise jde

                    return parsed

                except Exception as e:
                    last_error = e
                    logger.warning(f"Local VLM call attempt {attempt + 1} failed: {e}. Raw response: {raw_text[:120]}")
                    # Do not retry on HTTP 4xx errors or if length was truncated
                    if "HTTP 4" in str(e) or finish_reason == "length":
                        break
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying VLM call (attempt {attempt + 2}/{max_retries}) with clean prompt context...")
                        # Keep messages clean (do NOT accumulate previous assistant response to avoid exceeding 4096 context window)

        raise RuntimeError(f"Local vision request failed after {max_retries} attempts: {last_error}")

"""Google Gemini Vision Provider implementation (AI Studio native REST API)."""

import time
import logging
from typing import Tuple, List
from pathlib import Path

from .base import VisionModelProvider, encode_image_base64
from .prompt_manager import PromptManager
from .response_parser import parse_exam_split_json, ModelOutputError
from ..models.ai_result import VisionAnalysisRequest, VisionAnalysisResult

logger = logging.getLogger("examsplit.ai.gemini")

DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]


class GeminiProvider(VisionModelProvider):
    """Integrates with Google AI Studio Gemini API."""

    def __init__(
        self,
        provider_id: str = "gemini",
        base_url: str = "https://generativelanguage.googleapis.com",
        api_key: str = "",
        model_name: str = "gemini-2.5-flash",
        timeout: float = 60.0,
        proxy: str = "",
    ) -> None:
        super().__init__(
            provider_id=provider_id,
            base_url=base_url or "https://generativelanguage.googleapis.com",
            api_key=api_key,
            model_name=model_name or "gemini-2.5-flash",
            timeout=timeout,
            proxy=proxy,
        )

    def _get_api_root(self) -> str:
        """Normalize base URL to ensure clean /v1beta path without malformed subpaths."""
        url = self.base_url.strip().rstrip("/")
        # If user typed official Google host or variations (including /interactions, /v1beta, etc.)
        if "generativelanguage.googleapis.com" in url:
            return "https://generativelanguage.googleapis.com/v1beta"

        # For custom proxies or reverse proxies of Gemini
        for suffix in ["/interactions", "/models", "/generateContent"]:
            if url.endswith(suffix):
                url = url[:-len(suffix)].rstrip("/")
        if url.endswith("/v1beta") or url.endswith("/v1"):
            return url
        return f"{url}/v1beta"

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        return headers

    def fetch_available_models(self) -> List[str]:
        """Query Gemini API for available models supporting content generation."""
        if not self.api_key:
            return DEFAULT_GEMINI_MODELS

        root = self._get_api_root()
        url = f"{root}/models?key={self.api_key}"

        try:
            with self.create_http_client() as client:
                resp = client.get(url, headers=self._get_headers(), timeout=min(self.timeout, 15.0))
                if resp.status_code == 200:
                    data = resp.json()
                    models = []
                    for m in data.get("models", []):
                        name = m.get("name", "").replace("models/", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods and ("gemini" in name or "gemma" in name):
                            models.append(name)
                    # Sort to bring 2.5 and flash models to top
                    models.sort(key=lambda x: ("2.5" in x or "flash" in x, x), reverse=True)
                    return models if models else DEFAULT_GEMINI_MODELS
        except Exception as e:
            logger.warning(f"Failed to fetch remote Gemini models: {e}")

        return DEFAULT_GEMINI_MODELS

    def test_connection(self) -> Tuple[bool, str]:
        """Test API connectivity using model list call."""
        if not self.api_key:
            return False, "未设置 API Key"

        start_time = time.time()
        root = self._get_api_root()
        url = f"{root}/models?key={self.api_key}"

        try:
            with self.create_http_client() as client:
                resp = client.get(url, headers=self._get_headers(), timeout=min(self.timeout, 15.0))
                elapsed_ms = int((time.time() - start_time) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    raw_models = data.get("models", [])
                    return True, f"连接成功！响应时间: {elapsed_ms}ms (检测到 {len(raw_models)} 个可用模型)"
                elif resp.status_code in (400, 403):
                    return False, f"API Key 无效或未授权 (HTTP {resp.status_code}): {resp.text[:150]}"
                else:
                    return False, f"HTTP {resp.status_code}: {resp.text[:150]}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def analyze_pages(self, request: VisionAnalysisRequest) -> VisionAnalysisResult:
        """Call Gemini Vision model with page screenshots and prompt."""
        if not self.api_key:
            raise ValueError("未配置 Gemini API Key")

        clean_model = self.model_name.replace("models/", "")
        root = self._get_api_root()
        endpoint = f"{root}/models/{clean_model}:generateContent?key={self.api_key}"

        system_prompt = PromptManager.get_system_prompt("detect_markers")

        parts: list[dict] = []
        for img_path in request.image_paths:
            b64_data = encode_image_base64(img_path)
            parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": b64_data,
                }
            })

        parts.append({
            "text": f"{system_prompt}\n\n请识别上述试卷页面中的所有独立题目与边界坐标。"
        })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

        with self.create_http_client() as client:
            resp = client.post(endpoint, headers=self._get_headers(), json=payload)
            if resp.status_code != 200:
                raise ModelOutputError(f"Gemini API 错误 (HTTP {resp.status_code}): {resp.text[:200]}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ModelOutputError(f"Gemini API 未返回有效候选结果: {resp.text[:200]}")

            content_parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = content_parts[0].get("text", "") if content_parts else ""

            return parse_exam_split_json(raw_text)

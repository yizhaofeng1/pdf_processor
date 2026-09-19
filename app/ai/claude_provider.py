"""Anthropic Claude Vision Provider implementation."""

import time
import logging
from typing import Tuple
from pathlib import Path

from .base import VisionModelProvider, encode_image_base64
from .prompt_manager import PromptManager
from .response_parser import parse_exam_split_json, ModelOutputError
from ..models.ai_result import VisionAnalysisRequest, VisionAnalysisResult

logger = logging.getLogger("examsplit.ai.claude")


class ClaudeProvider(VisionModelProvider):
    """Integrates with Anthropic Messages API."""

    def __init__(
        self,
        provider_id: str = "claude",
        base_url: str = "https://api.anthropic.com/v1",
        api_key: str = "",
        model_name: str = "claude-3-5-sonnet-20241022",
        timeout: float = 60.0,
        proxy: str = "",
    ) -> None:
        normalized_url = (base_url or "https://api.anthropic.com/v1").strip().rstrip("/")
        if "api.anthropic.com" in normalized_url and not normalized_url.endswith("/v1"):
            normalized_url = f"{normalized_url}/v1"

        super().__init__(
            provider_id=provider_id,
            base_url=normalized_url,
            api_key=api_key.strip(),
            model_name=model_name or "claude-3-5-sonnet-20241022",
            timeout=timeout,
            proxy=proxy,
        )

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def fetch_available_models(self) -> list[str]:
        """Fetch models from /models or return standard Anthropic models."""
        url = f"{self.base_url}/models"
        try:
            with self.create_http_client() as client:
                resp = client.get(url, headers=self._get_headers(), timeout=min(self.timeout, 12.0))
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                    if models:
                        return sorted(models)
        except Exception:
            pass

        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
        ]

    def test_connection(self) -> Tuple[bool, str]:
        """Test API reachability with a 1-token message test."""
        if not self.api_key:
            return False, "未设置 API Key"

        start_time = time.time()
        url = f"{self.base_url}/messages"
        headers = self._get_headers()
        payload = {
            "model": self.model_name,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }

        try:
            with self.create_http_client() as client:
                resp = client.post(url, headers=headers, json=payload, timeout=min(self.timeout, 15.0))
                elapsed_ms = int((time.time() - start_time) * 1000)

                if resp.status_code == 200:
                    return True, f"连接成功！响应时间: {elapsed_ms}ms"
                elif resp.status_code in (401, 403):
                    return False, f"认证失败 (HTTP {resp.status_code}): API Key 无效"
                else:
                    return False, f"HTTP {resp.status_code}: {resp.text[:150]}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def analyze_pages(self, request: VisionAnalysisRequest) -> VisionAnalysisResult:
        """Call Claude model with vision content block."""
        if not self.api_key:
            raise ValueError("未配置 Claude API Key")

        endpoint = f"{self.base_url}/messages"
        system_prompt = PromptManager.get_system_prompt("detect_markers")

        content_blocks: list[dict] = []
        for img_path in request.image_paths:
            b64_data = encode_image_base64(img_path)
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64_data,
                },
            })

        content_blocks.append({
            "type": "text",
            "text": "请根据给出的试卷页面图像，识别所有独立题目及其完整边界区域，严格输出标准 JSON。",
        })

        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "messages": [{"role": "user", "content": content_blocks}],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        with self.create_http_client() as client:
            resp = client.post(endpoint, headers=self._get_headers(), json=payload)
            if resp.status_code != 200:
                raise ModelOutputError(f"Claude API 请求失败 (HTTP {resp.status_code}): {resp.text[:200]}")

            data = resp.json()
            blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            return parse_exam_split_json(text)

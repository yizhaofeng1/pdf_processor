"""OpenAI-compatible Vision Provider supporting OpenAI, DeepSeek, GLM, and Custom gateways."""

import time
import logging
from typing import Tuple, Optional
from pathlib import Path

from .base import VisionModelProvider, encode_image_base64
from .prompt_manager import PromptManager
from .response_parser import parse_exam_split_json, ModelOutputError
from ..models.ai_result import VisionAnalysisRequest, VisionAnalysisResult

logger = logging.getLogger("examsplit.ai.openai_compat")


class OpenAICompatProvider(VisionModelProvider):
    """Integrates with any OpenAI-compatible Chat Completions API with vision."""

    def __init__(
        self,
        provider_id: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model_name: str = "gpt-4o",
        timeout: float = 60.0,
        proxy: str = "",
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        # Official OpenAI requires /v1
        if "api.openai.com" in normalized_url and not normalized_url.endswith("/v1"):
            normalized_url = f"{normalized_url}/v1"

        super().__init__(
            provider_id=provider_id,
            base_url=normalized_url or "https://api.openai.com/v1",
            api_key=api_key.strip(),
            model_name=model_name or "gpt-4o",
            timeout=timeout,
            proxy=proxy,
        )

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_models_endpoint(self) -> str:
        """Resolve clean /models endpoint avoiding duplicate segments."""
        url = self.base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[:-len("/chat/completions")].rstrip("/")
        if url.endswith("/models"):
            return url
        return f"{url}/models"

    def _get_chat_endpoint(self) -> str:
        """Resolve clean /chat/completions endpoint."""
        url = self.base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    def fetch_available_models(self) -> list[str]:
        """Fetch models from /models endpoint."""
        models_url = self._get_models_endpoint()
        try:
            with self.create_http_client() as client:
                resp = client.get(models_url, headers=self._get_headers(), timeout=min(self.timeout, 12.0))
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                    if models:
                        return sorted(models)
                    raise RuntimeError("远端接口返回的模型列表为空")
                else:
                    err_msg = resp.text[:200].strip()
                    raise RuntimeError(f"HTTP {resp.status_code}: {err_msg}")
        except Exception as e:
            logger.warning(f"Failed to fetch models from {models_url}: {e}")
            raise

    def test_connection(self) -> Tuple[bool, str]:
        """Test API connectivity using /models or a lightweight ping completion."""
        if not self.api_key and "localhost" not in self.base_url:
            return False, "未设置 API Key"

        start_time = time.time()
        headers = self._get_headers()

        # Try /models endpoint first
        models_url = self._get_models_endpoint()
        try:
            with self.create_http_client() as client:
                resp = client.get(models_url, headers=headers, timeout=min(self.timeout, 12.0))
                elapsed_ms = int((time.time() - start_time) * 1000)

                if resp.status_code == 200:
                    return True, f"连接成功！响应时间: {elapsed_ms}ms"
                elif resp.status_code in (401, 403):
                    return False, f"认证失败 (HTTP {resp.status_code}): API Key 无效"
                elif resp.status_code == 404:
                    # Some proxies do not implement /models; fallback to a 1-token completion test
                    ping_url = self._get_chat_endpoint()
                    ping_payload = {
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    }
                    ping_resp = client.post(ping_url, headers=headers, json=ping_payload, timeout=min(self.timeout, 15.0))
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    if ping_resp.status_code == 200:
                        return True, f"连接成功！响应时间: {elapsed_ms}ms"
                    return False, f"HTTP {ping_resp.status_code}: {ping_resp.text[:150]}"
                else:
                    return False, f"HTTP {resp.status_code}: {resp.text[:150]}"
        except Exception as e:
            return False, f"连接异常: {e}"

    def analyze_pages(self, request: VisionAnalysisRequest) -> VisionAnalysisResult:
        """Send multimodal message with image and prompt to chat completions."""
        if not self.api_key and "localhost" not in self.base_url:
            raise ValueError(f"未配置 {self.provider_id} API Key")

        endpoint = self._get_chat_endpoint()
        system_prompt = PromptManager.get_system_prompt("detect_markers", request.context_hints)

        structure_hint = (request.context_hints or {}).get("paper_structure", "").strip()
        user_prompt_text = "请根据给出的试卷页面图像，识别所有独立题目及其完整边界区域。"
        if structure_hint:
            user_prompt_text += f"\n【试卷大纲结构参考分布】：\n{structure_hint}"

        content_items: list[dict] = [
            {"type": "text", "text": user_prompt_text}
        ]


        for img_path in request.image_paths:
            b64_data = encode_image_base64(img_path)
            content_items.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_data}",
                    "detail": "high",
                },
            })

        payload: dict = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_items},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        headers = self._get_headers()

        with self.create_http_client() as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            if resp.status_code != 200:
                # If json_object is rejected by model, retry once without response_format
                if "response_format" in resp.text:
                    payload.pop("response_format", None)
                    resp = client.post(endpoint, headers=headers, json=payload)

            if resp.status_code != 200:
                raise ModelOutputError(f"API 请求失败 (HTTP {resp.status_code}): {resp.text[:200]}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise ModelOutputError("API 返回空 choices")

            raw_text = choices[0].get("message", {}).get("content", "")
            return parse_exam_split_json(raw_text)

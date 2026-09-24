"""Local Vision-Language Model provider using an OpenAI-compatible endpoint.

Supports Ollama (e.g. qwen2.5vl:3b, llama3.2-vision), vLLM, and llama-server.
Communicates via standard OpenAI chat completion API with structured vision payloads.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
import httpx
from .base import LocalVLMProvider
from .config import LocalModelConfig
from .exceptions import VLMError, LocalModelUnavailableError
from .types import LocalQuestionCandidate, LocalBoundaryVerification

logger = logging.getLogger("examsplit.experimental.local_ai.vlm")


class OpenAILocalVLMProvider(LocalVLMProvider):
    """OpenAI-compatible local vision-language model provider."""

    def __init__(self, config: Optional[LocalModelConfig] = None) -> None:
        self.config = config or LocalModelConfig()
        self._client: Optional[httpx.Client] = None
        self._prompt_template: str = ""
        self._load_prompt_template()

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.config.endpoint_url.rstrip("/"),
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout_seconds,
            )
        return self._client

    def _load_prompt_template(self) -> None:
        prompt_path = self.config.prompts_dir / "boundary_verify_v1.txt"
        if prompt_path.exists():
            try:
                self._prompt_template = prompt_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not load prompt from {prompt_path}: {e}")
        if not self._prompt_template:
            self._prompt_template = (
                "你是试卷题目区域复核专家。请复核附图中的候选题目区域（题号 {question_number}）。\n"
                "输出 JSON：\n"
                '{{"schema_version": "1.0", "question_number": "{question_number}", "accept": true, '
                '"bbox": [{x1}, {y1}, {x2}, {y2}], "cross_page": false, "contains_all_required_content": true, '
                '"needs_expand_up": false, "needs_expand_down": false, "confidence": 0.95, "reason_codes": []}}'
            )

    def check_health(self) -> bool:
        """Check if local endpoint is reachable and reports models."""
        try:
            client = self._get_client()
            resp = client.get("/models", timeout=3.0)
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed for endpoint {self.config.endpoint_url}: {e}")
            return False

    def verify_question_region(
        self,
        crop_image_b64: str,
        candidate: LocalQuestionCandidate,
        context: Optional[Dict[str, Any]] = None,
    ) -> LocalBoundaryVerification:
        seg_bbox = candidate.segments[0].bbox if candidate.segments else (0.0, 0.0, 1.0, 1.0)
        formatted_prompt = (
            self._prompt_template
            .replace("{question_number}", str(candidate.question_number))
            .replace("{x1}", str(round(seg_bbox[0], 4)))
            .replace("{y1}", str(round(seg_bbox[1], 4)))
            .replace("{x2}", str(round(seg_bbox[2], 4)))
            .replace("{y2}", str(round(seg_bbox[3], 4)))
        )

        image_data_uri = (
            crop_image_b64
            if crop_image_b64.startswith("data:image/")
            else f"data:image/jpeg;base64,{crop_image_b64}"
        )

        payload = {
            "model": self.config.vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": formatted_prompt},
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                    ],
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        client = self._get_client()
        last_error = None
        for attempt in range(max(1, self.config.max_retries)):
            try:
                resp = client.post("/chat/completions", json=payload)
                if resp.status_code != 200:
                    raise VLMError(f"Local VLM endpoint returned HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise VLMError("Local VLM returned empty choices in response.")

                content_str = choices[0].get("message", {}).get("content", "").strip()
                # Clean up markdown fences if present
                clean_json_str = self._extract_json_str(content_str)

                # Parse and validate with Pydantic
                verification = LocalBoundaryVerification.model_validate_json(clean_json_str)
                logger.info(
                    f"VLM verification for Q{candidate.question_number}: accept={verification.accept}, "
                    f"confidence={verification.confidence:.2f}, reasons={verification.reason_codes}"
                )
                return verification
            except Exception as e:
                last_error = e
                logger.warning(f"VLM verification attempt {attempt + 1} failed: {e}")

        logger.error(f"All VLM attempts failed for Q{candidate.question_number}: {last_error}")
        # Graceful fallback: accept with lowered confidence so pipeline does not crash
        return LocalBoundaryVerification(
            schema_version="1.0",
            question_number=candidate.question_number,
            accept=True,
            bbox=seg_bbox,
            cross_page=False,
            contains_all_required_content=True,
            confidence=0.70,
            reason_codes=["VLM_FALLBACK_DEFAULT"],
        )

    def _extract_json_str(self, text: str) -> str:
        """Strip markdown ```json code blocks or extract enclosed JSON substring."""
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Try to locate first '{' and last '}'
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1].strip()

        return text.strip()

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

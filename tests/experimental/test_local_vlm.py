"""Tests for local VLM provider parsing and error handling."""

from unittest.mock import MagicMock, patch
import httpx
from app.experimental.local_ai.config import LocalModelConfig
from app.experimental.local_ai.local_vlm import OpenAILocalVLMProvider
from app.experimental.local_ai.types import CandidateSegment, LocalQuestionCandidate


def test_vlm_provider_extract_json():
    """Verify markdown fences and embedded JSON are parsed accurately."""
    provider = OpenAILocalVLMProvider()

    markdown_resp = """
    这是分析结果：
    ```json
    {
        "schema_version": "1.0",
        "question_number": "1",
        "accept": true,
        "bbox": [0.05, 0.10, 0.45, 0.25],
        "cross_page": false,
        "contains_all_required_content": true,
        "needs_expand_up": false,
        "needs_expand_down": false,
        "confidence": 0.96,
        "reason_codes": []
    }
    ```
    """
    clean_json = provider._extract_json_str(markdown_resp)
    assert clean_json.startswith("{") and clean_json.endswith("}")


def test_vlm_provider_verify_success():
    """Verify verify_question_region returns valid LocalBoundaryVerification."""
    cfg = LocalModelConfig()
    provider = OpenAILocalVLMProvider(cfg)

    candidate = LocalQuestionCandidate(
        question_number="1",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.10, 0.45, 0.25))],
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"schema_version": "1.0", "question_number": "1", "accept": true, "bbox": [0.05, 0.10, 0.45, 0.25], "cross_page": false, "contains_all_required_content": true, "needs_expand_up": false, "needs_expand_down": false, "confidence": 0.95, "reason_codes": []}'
                }
            }
        ]
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        res = provider.verify_question_region("base64data", candidate)
        assert res.accept is True
        assert res.question_number == "1"
        assert res.confidence == 0.95


def test_vlm_provider_fallback_on_network_failure():
    """Verify VLM provider does not crash if local endpoint times out, returning fallback."""
    cfg = LocalModelConfig(max_retries=1)
    provider = OpenAILocalVLMProvider(cfg)

    candidate = LocalQuestionCandidate(
        question_number="2",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.30, 0.45, 0.45))],
    )

    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Server down")):
        res = provider.verify_question_region("base64data", candidate)
        assert res.accept is True
        assert "VLM_FALLBACK_DEFAULT" in res.reason_codes

"""Unit tests for AI providers, factory, prompt manager, and parser."""

import pytest
from pathlib import Path

from app.ai.provider_factory import ProviderFactory, PROVIDER_PRESETS
from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_compat_provider import OpenAICompatProvider
from app.ai.claude_provider import ClaudeProvider
from app.ai.prompt_manager import PromptManager
from app.ai.response_parser import parse_exam_split_json, ModelOutputError, extract_json_block
from app.ai.base import encode_image_base64


def test_provider_presets_coverage():
    """Verify factory includes all required mainstream providers."""
    presets = ProviderFactory.get_presets()
    expected_providers = {"gemini", "openai", "deepseek", "glm", "claude", "custom"}
    assert expected_providers.issubset(set(presets.keys()))


def test_provider_factory_instantiation():
    """Verify factory constructs appropriate concrete subclasses."""
    p_gemini = ProviderFactory.create_provider("gemini", api_key="test_gemini")
    assert isinstance(p_gemini, GeminiProvider)
    assert p_gemini.provider_id == "gemini"
    assert "generativelanguage" in p_gemini.base_url

    p_deepseek = ProviderFactory.create_provider("deepseek", api_key="test_deepseek")
    assert isinstance(p_deepseek, OpenAICompatProvider)
    assert "deepseek" in p_deepseek.base_url

    p_claude = ProviderFactory.create_provider("claude", api_key="test_claude")
    assert isinstance(p_claude, ClaudeProvider)
    assert "anthropic" in p_claude.base_url


def test_prompt_manager():
    """Verify prompt manager loads system instructions with JSON protocol."""
    prompt = PromptManager.get_system_prompt("detect_markers")
    assert "归一化坐标" in prompt
    assert "schema_version" in prompt
    assert "questions" in prompt


def test_response_parser_clean_json():
    """Verify parser parses clean JSON correctly."""
    sample = """
    {
      "schema_version": "1.0",
      "document": { "title": "2010数学试卷", "page_count": 8 },
      "questions": [
        {
          "question_id": "q1",
          "display_number": "1",
          "question_type": "choice",
          "segments": [
            { "page_index": 0, "normalized_bbox": [0.05, 0.08, 0.95, 0.20] }
          ],
          "confidence": 0.99
        }
      ]
    }
    """
    res = parse_exam_split_json(sample)
    assert res.schema_version == "1.0"
    assert len(res.questions) == 1
    q1 = res.questions[0]
    assert q1.display_number == "1"
    assert len(q1.segments) == 1
    assert q1.segments[0].normalized_bbox == (0.05, 0.08, 0.95, 0.20)


def test_response_parser_markdown_fence():
    """Verify parser extracts JSON wrapped in markdown fences with extra chatter."""
    sample = """
    好的，这是为您分析的试卷结构：
    ```json
    {
      "schema_version": "1.0",
      "questions": [
        {
          "question_id": "q17",
          "display_number": "17",
          "question_type": "solve",
          "segments": [
            { "page_index": 4, "normalized_bbox": [0.05, 0.30, 0.95, 0.85] }
          ],
          "confidence": 0.95
        }
      ]
    }
    ```
    以上是分析结果，请核对。
    """
    res = parse_exam_split_json(sample)
    assert len(res.questions) == 1
    assert res.questions[0].display_number == "17"


def test_response_parser_invalid():
    """Verify parser raises ModelOutputError on unparseable garbage."""
    with pytest.raises(ModelOutputError):
        parse_exam_split_json("这是一段纯自然语言回复，没有任何 JSON 结构。")


def test_encode_image_base64(tmp_path: Path):
    """Verify base64 encoding of images."""
    dummy_img = tmp_path / "test.png"
    dummy_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    b64_str = encode_image_base64(dummy_img)
    assert isinstance(b64_str, str)
    assert len(b64_str) > 0


def test_gemini_url_sanitization():
    """Verify Gemini provider robustly cleans base URL and avoids malformed endpoints."""
    # Test case 1: User pasted with /v1beta/interactions
    p1 = GeminiProvider(base_url="https://generativelanguage.googleapis.com/v1beta/interactions")
    assert p1._get_api_root() == "https://generativelanguage.googleapis.com/v1beta"

    # Test case 2: User entered standard root
    p2 = GeminiProvider(base_url="https://generativelanguage.googleapis.com")
    assert p2._get_api_root() == "https://generativelanguage.googleapis.com/v1beta"

    # Test case 3: User entered with trailing slash
    p3 = GeminiProvider(base_url="https://generativelanguage.googleapis.com/")
    assert p3._get_api_root() == "https://generativelanguage.googleapis.com/v1beta"

    # Test case 4: User entered with /v1beta already
    p4 = GeminiProvider(base_url="https://generativelanguage.googleapis.com/v1beta")
    assert p4._get_api_root() == "https://generativelanguage.googleapis.com/v1beta"


def test_openai_and_deepseek_url_normalization():
    """Verify OpenAI and DeepSeek endpoint normalization."""
    # OpenAI root automatically appends /v1
    p_openai = OpenAICompatProvider(base_url="https://api.openai.com")
    assert p_openai.base_url == "https://api.openai.com/v1"
    assert p_openai._get_models_endpoint() == "https://api.openai.com/v1/models"
    assert p_openai._get_chat_endpoint() == "https://api.openai.com/v1/chat/completions"

    # DeepSeek root
    p_ds = OpenAICompatProvider(provider_id="deepseek", base_url="https://api.deepseek.com")
    assert p_ds._get_models_endpoint() == "https://api.deepseek.com/models"
    assert p_ds._get_chat_endpoint() == "https://api.deepseek.com/chat/completions"

    # Custom endpoint with trailing /chat/completions
    p_custom = OpenAICompatProvider(provider_id="custom", base_url="https://custom.ai/v1/chat/completions")
    assert p_custom._get_models_endpoint() == "https://custom.ai/v1/models"
    assert p_custom._get_chat_endpoint() == "https://custom.ai/v1/chat/completions"


def test_sanitize_normalized_bbox():
    """Verify coordinate sanitizer fixes missing zero typos and inverted coordinates."""
    from app.ai.response_parser import _sanitize_normalized_bbox

    # 1. Normal valid bbox
    res = _sanitize_normalized_bbox([0.05, 0.10, 0.95, 0.30])
    assert res == (0.05, 0.10, 0.95, 0.30)

    # 2. Typo: missing leading zero e.g. 0.77 instead of 0.077 when y2 is 0.103
    res_typo = _sanitize_normalized_bbox([0.034, 0.77, 0.741, 0.103])
    assert res_typo is not None
    assert abs(res_typo[1] - 0.077) < 1e-4
    assert res_typo[3] == 0.103
    assert res_typo[1] < res_typo[3]

    # 3. Inverted y1 and y2
    res_inv = _sanitize_normalized_bbox([0.1, 0.5, 0.9, 0.2])
    assert res_inv is not None
    assert res_inv[1] == 0.2
    assert res_inv[3] == 0.5

    # 4. Tiny sliver / degenerate box
    res_deg = _sanitize_normalized_bbox([0.1, 0.2, 0.101, 0.201])
    assert res_deg is None


def test_fetch_available_models_real_error_handling(monkeypatch):
    """Verify fetch_available_models propagates real errors and does NOT return fake hardcoded models."""
    import httpx

    # 1. Test OpenAICompatProvider error propagation
    p_deepseek = ProviderFactory.create_provider("deepseek", api_key="sk-invalid")

    # Mock 401 error
    class MockResp401:
        status_code = 401
        text = "Authentication failed"

    class MockClient401:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, *args, **kwargs):
            return MockResp401()

    monkeypatch.setattr(p_deepseek, "create_http_client", lambda: MockClient401())
    with pytest.raises(RuntimeError) as exc_info:
        p_deepseek.fetch_available_models()
    assert "401" in str(exc_info.value)

    # Mock 200 success
    class MockResp200:
        status_code = 200
        def json(self):
            return {"data": [{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}]}

    class MockClient200:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, *args, **kwargs):
            return MockResp200()

    monkeypatch.setattr(p_deepseek, "create_http_client", lambda: MockClient200())
    models = p_deepseek.fetch_available_models()
    assert models == ["deepseek-chat", "deepseek-reasoner"]

    # 2. Test Gemini missing key raises error
    p_gemini = ProviderFactory.create_provider("gemini", api_key="")
    with pytest.raises(ValueError) as exc_info:
        p_gemini.fetch_available_models()
    assert "API Key" in str(exc_info.value)

    # 3. Test Claude missing key raises error
    p_claude = ProviderFactory.create_provider("claude", api_key="")
    with pytest.raises(ValueError) as exc_info:
        p_claude.fetch_available_models()
    assert "API Key" in str(exc_info.value)



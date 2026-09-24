"""Prompt management and system instructions loader."""

from pathlib import Path
from typing import Optional
from ..config import PROMPTS_DIR


class PromptManager:
    """Loads versioned prompts and formats system/user payloads."""

    @staticmethod
    def load_prompt(prompt_name: str) -> str:
        """Load text template from prompts directory."""
        path = PROMPTS_DIR / f"{prompt_name}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    @staticmethod
    def get_default_prompt(model_or_provider: str = "") -> str:
        """Return the default system prompt template for a given model or provider."""
        low = model_or_provider.lower()
        if "deepseek" in low:
            ds_path = PROMPTS_DIR / "detect_markers_deepseek.txt"
            if ds_path.exists():
                return ds_path.read_text(encoding="utf-8").strip()
        default_path = PROMPTS_DIR / "detect_markers.txt"
        return default_path.read_text(encoding="utf-8").strip()

    @classmethod
    def get_system_prompt(
        cls,
        task_type: str = "detect_markers",
        context_hints: Optional[dict[str, str]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        """Return standardized system prompt enforcing ExamSplit JSON Protocol with optional structure hints."""
        hints = context_hints or {}
        # Priority 1: explicitly passed custom_system_prompt
        # Priority 2: custom_prompt / custom_system_prompt in context_hints
        effective_custom = custom_system_prompt or hints.get("custom_prompt") or hints.get("custom_system_prompt")

        if effective_custom and effective_custom.strip():
            base_prompt = effective_custom.strip()
        else:
            model_key = f"{hints.get('provider_id', '')}_{hints.get('model_name', '')}"
            if "deepseek" in model_key.lower() or task_type == "detect_markers_deepseek":
                try:
                    base_prompt = cls.load_prompt("detect_markers_deepseek")
                except Exception:
                    base_prompt = cls.load_prompt(task_type)
            else:
                base_prompt = cls.load_prompt(task_type)

        structure_hint = hints.get("paper_structure", "").strip()
        structure_block = ""
        if structure_hint:
            structure_block = (
                f"\n\n【用户指定的本卷结构大纲分布（重要裁决依据）】：\n"
                f"{structure_hint}\n"
                f"请务必结合上述试卷题型分布大纲，准确判定各题目的题号范围、小题/大题属性与边界范围！\n"
            )

        protocol_suffix = """

【重要输出规范】：
1. 绝对不要对题目进行重新抄写、文本重写或给出答案解析。
2. 所有识别区域的坐标必须使用归一化坐标 [x1, y1, x2, y2]，取值在 0.0 ~ 1.0 之间。
3. 严格输出符合如下格式的完整 JSON 对象，严禁输出任何 Markdown 外部文字或非 JSON 字符：
{
  "schema_version": "1.0",
  "document": {
    "title": "",
    "subject": "",
    "page_count": 1
  },
  "questions": [
    {
      "question_id": "q001",
      "display_number": "1",
      "question_type": "小题", // 仅填 "小题" 或 "大题"
      "segments": [
        {
          "page_index": 0,
          "normalized_bbox": [0.05, 0.10, 0.95, 0.25]
        }
      ],
      "continuation": false,
      "confidence": 0.98,
      "review_required": false,
      "reason_codes": []
    }
  ],
  "warnings": []
}
"""
        return f"{base_prompt}{structure_block}\n{protocol_suffix}"

"""Parser and schema validator for AI responses."""

import json
import re
import logging
from typing import Dict, Any

from ..models.ai_result import VisionAnalysisResult
from ..models.question import Question, QuestionType
from ..models.segment import QuestionSegment
from ..models.document import DocumentMetadata

logger = logging.getLogger("examsplit.ai.parser")


class ModelOutputError(Exception):
    """Raised when model response cannot be parsed or validated."""
    pass


def extract_json_block(text: str) -> str:
    """Extract raw JSON from possible markdown fences or surrounding chatter."""
    text = text.strip()

    # 1. Check for markdown code fence ```json ... ```
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(fence_pattern, text, re.IGNORECASE)
    if matches:
        # Return the match with highest length (most likely to be the full object)
        candidate = max(matches, key=len).strip()
        if (candidate.startswith("{") and candidate.endswith("}")) or (
            candidate.startswith("[") and candidate.endswith("]")
        ):
            return candidate

    # 2. Look for outermost JSON object {...}
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        return text[start_brace : end_brace + 1].strip()

    return text


def _sanitize_normalized_bbox(bbox: list | tuple) -> tuple[float, float, float, float] | None:
    """Sanitize and repair common LLM floating point or inverted coordinate quirks."""
    if not bbox or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    except (ValueError, TypeError):
        return None

    # Fix common LLM typo: missing leading zero, e.g. 0.77 instead of 0.077 when y2 is 0.103
    if y1 > y2:
        if y1 > 0.4 and y2 < 0.2 and (y1 / 10.0) < y2:
            y1 = y1 / 10.0
        elif y2 > 0.4 and y1 < 0.2 and (y2 / 10.0) > y1:
            y2 = y2 / 10.0
        else:
            y1, y2 = min(y1, y2), max(y1, y2)

    if x1 > x2:
        x1, x2 = min(x1, x2), max(x1, x2)

    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    x2 = max(0.0, min(1.0, x2))
    y2 = max(0.0, min(1.0, y2))

    if (x2 - x1) < 0.005 or (y2 - y1) < 0.005:
        return None

    return (x1, y1, x2, y2)


def parse_exam_split_json(raw_text: str) -> VisionAnalysisResult:
    """Parse raw text from LLM response, extract JSON block, and validate against domain models."""
    json_str = extract_json_block(raw_text)
    try:
        data: Dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ModelOutputError(f"无法解析模型返回的 JSON 内容: {e}\n原始文本: {raw_text[:200]}")

    schema_version = data.get("schema_version", "2.0")
    doc_meta_data = data.get("document", {})
    document = DocumentMetadata(
        title=doc_meta_data.get("title", ""),
        subject=doc_meta_data.get("subject", ""),
        year=doc_meta_data.get("year"),
        page_count=doc_meta_data.get("page_count", 0),
    )

    questions: list[Question] = []
    raw_questions = data.get("questions", [])
    if not isinstance(raw_questions, list):
        raise ModelOutputError("JSON 中 'questions' 必须为数组列表")

    for idx, q_dict in enumerate(raw_questions):
        q_id = q_dict.get("question_id") or f"q_{idx + 1}"
        num_raw = str(q_dict.get("display_number") or idx + 1)
        digits = re.sub(r"[^\d]", "", num_raw)
        num = digits if digits else num_raw
        raw_type = str(q_dict.get("question_type") or "").strip()
        if "小" in raw_type or raw_type.lower() in ("choice", "fill_in", "small"):
            q_type = QuestionType.SMALL
        elif "大" in raw_type or raw_type.lower() in ("solve", "proof", "large"):
            q_type = QuestionType.LARGE
        elif raw_type:
            q_type = raw_type
        else:
            q_type = None

        # Segments parsing
        segments: list[QuestionSegment] = []
        for s_dict in q_dict.get("segments", []):
            page_idx = s_dict.get("page_index", 0)
            bbox = s_dict.get("normalized_bbox")
            sanitized = _sanitize_normalized_bbox(bbox)
            if not sanitized:
                continue

            try:
                seg = QuestionSegment(
                    question_id=q_id,
                    page_index=page_idx,
                    normalized_bbox=sanitized,
                )
                segments.append(seg)
            except Exception as e:
                logger.warning(f"Segment validation rejected bbox {bbox}: {e}")

        # Fallback: if LLM put normalized_bbox at question root instead of inside segments
        if not segments and q_dict.get("normalized_bbox"):
            sanitized = _sanitize_normalized_bbox(q_dict.get("normalized_bbox"))
            if sanitized:
                segments.append(QuestionSegment(
                    question_id=q_id,
                    page_index=0,
                    normalized_bbox=sanitized,
                ))

        # If model returned no segments or single anchor point, fallback will handle it
        q = Question(
            id=q_id,
            display_number=num,
            question_type=q_type,
            segments=segments,
            continuation=bool(q_dict.get("continuation", False)),
            confidence=float(q_dict.get("confidence", 0.95)),
            review_required=bool(q_dict.get("review_required", False)),
            reason_codes=q_dict.get("reason_codes", []),
            sort_order=idx,
        )
        questions.append(q)

    warnings = data.get("warnings", [])

    return VisionAnalysisResult(
        schema_version=schema_version,
        document=document,
        questions=questions,
        warnings=warnings,
        raw_response=raw_text,
    )

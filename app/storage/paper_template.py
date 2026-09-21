"""Exam Paper Structure Template Storage: Manages preset and custom question distributions."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from ..config import DATA_DIR

logger = logging.getLogger("examsplit.storage.paper_template")

BUILTIN_TEMPLATES: Dict[str, str] = {
    "默认 / 通用自适应 (由AI自主判断)": "",
    "2021~至今 考研数学 (一/二/三)": (
        "第1~10题为单选题(每题5分，小题)；"
        "第11~16题为填空题(每题5分，小题)；"
        "第17~22题为解答题(计算/证明题，大题)。"
    ),
    "2020及以前 考研数学 (一/二/三)": (
        "第1~8题为单选题(每题4分，小题)；"
        "第9~14题为填空题(每题4分，小题)；"
        "第15~23题为解答题(计算/证明题，大题)。"
    ),
    "新高考全国卷 (数学)": (
        "第1~8题为单项选择题(小题)；"
        "第9~12题为多项选择题(小题)；"
        "第13~16题为填空题(小题)；"
        "第17~22题为解答题(证明/计算，大题)。"
    ),
    "全国甲/乙卷 (数学)": (
        "第1~12题为单项选择题(小题)；"
        "第13~16题为填空题(小题)；"
        "第17~21题为必做解答题(大题)；"
        "第22~23题为二选一选考解答题(大题)。"
    ),
    "标准期末/综合试卷 (通用)": (
        "一、单项选择题均为小题；"
        "二、填空题均为小题；"
        "三、计算分析与证明题均为大题。"
    ),
}

TEMPLATE_FILE = DATA_DIR / "paper_templates.json"
PREFERENCE_FILE = DATA_DIR / "template_preference.json"


class PaperTemplateStorage:
    """Manages preset exam structure templates and user-defined custom templates."""

    @classmethod
    def get_builtin_templates(cls) -> Dict[str, str]:
        """Return immutable dictionary of built-in templates."""
        return dict(BUILTIN_TEMPLATES)

    @classmethod
    def get_custom_templates(cls) -> Dict[str, str]:
        """Load user-saved custom templates from disk."""
        if not TEMPLATE_FILE.exists():
            return {}
        try:
            data = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Failed to load custom templates from {TEMPLATE_FILE}: {e}")
        return {}

    @classmethod
    def get_all_templates(cls) -> Dict[str, str]:
        """Return combined dictionary of built-in and user custom templates."""
        combined = cls.get_builtin_templates()
        custom = cls.get_custom_templates()
        combined.update(custom)
        return combined

    @classmethod
    def is_builtin(cls, name: str) -> bool:
        """Check whether a template name belongs to the built-in set."""
        return name in BUILTIN_TEMPLATES

    @classmethod
    def save_custom_template(cls, name: str, content: str) -> None:
        """Save or update a custom user template."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("模板名称不能为空")
        if clean_name in BUILTIN_TEMPLATES:
            raise ValueError(f"'{clean_name}' 为系统内置模板名称，不能覆盖，请使用其他名称")

        customs = cls.get_custom_templates()
        customs[clean_name] = content.strip()

        TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE_FILE.write_text(json.dumps(customs, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved custom template '{clean_name}'.")

    @classmethod
    def delete_custom_template(cls, name: str) -> bool:
        """Delete a user-defined custom template."""
        clean_name = name.strip()
        if clean_name in BUILTIN_TEMPLATES:
            return False

        customs = cls.get_custom_templates()
        if clean_name in customs:
            del customs[clean_name]
            TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            TEMPLATE_FILE.write_text(json.dumps(customs, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"Deleted custom template '{clean_name}'.")
            return True
        return False

    @classmethod
    def get_template_content(cls, name: str) -> str:
        """Retrieve structure text by template name."""
        all_t = cls.get_all_templates()
        return all_t.get(name, "")

    @classmethod
    def get_active_template_name(cls) -> str:
        """Get the last selected active template name, defaulting to 2021考研数学."""
        default_name = "2021~至今 考研数学 (一/二/三)"
        if not PREFERENCE_FILE.exists():
            return default_name
        try:
            data = json.loads(PREFERENCE_FILE.read_text(encoding="utf-8"))
            saved = data.get("active_template")
            if saved and (saved in cls.get_all_templates() or saved == "自定义结构"):
                return saved
        except Exception:
            pass
        return default_name

    @classmethod
    def set_active_template_name(cls, name: str) -> None:
        """Persist active template selection."""
        try:
            PREFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            PREFERENCE_FILE.write_text(
                json.dumps({"active_template": name}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"Failed to save active template preference: {e}")

"""Prompt loader and builder for the VAQL experiment."""

from pathlib import Path
from typing import Dict, Any
import logging

from .config import EXPERIMENT_PROMPTS_DIR

logger = logging.getLogger("examsplit.experimental.prompt_builder")


EXAM_PRIOR_TEMPLATES: Dict[str, str] = {
    "kaoyan_math_16": (
        "【试卷先验结构（16小题+大题）】：\n"
        "• 选择题（1~10题）：独立单选题，逐题输出 1 到 10。\n"
        "• 填空题（11~16题）：独立填空题，逐题输出 11 到 16。\n"
        "• 解答题（17题起）：大题，包含小问（如 (I), (II)）。\n"
        "• 小题共 16 道，题目密集，请务必逐题完整识别，严禁跳漏！"
    ),
    "kaoyan_math_14": (
        "【试卷先验结构（14小题+大题）】：\n"
        "• 选择题（1~8题）：独立单选题，逐题输出 1 到 8。\n"
        "• 填空题（9~14题）：独立填空题，逐题输出 9 到 14。\n"
        "• 解答题（15题起）：大题，包含小问。\n"
        "• 小题共 14 道，题目密集，请务必逐题完整识别，严禁跳漏！"
    ),
    "general": (
        "【试卷先验结构】：\n"
        "本页包含独立试题，请仔细排查每一道小题与大题，严禁跳漏！"
    ),
}


class ExperimentPromptBuilder:
    """Manages versioned prompts for experimental local recognition."""

    def __init__(self, prompts_dir: Path = EXPERIMENT_PROMPTS_DIR) -> None:
        self.prompts_dir = prompts_dir
        self._cache: Dict[str, str] = {}

    def _get_prompt_template(self, filename: str) -> str:
        if filename not in self._cache:
            file_path = self.prompts_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Experiment prompt file not found: {file_path}")
            self._cache[filename] = file_path.read_text(encoding="utf-8")
        return self._cache[filename]

    def build_coarse_prompt(
        self,
        page_index: int,
        grid_rows: int = 8,
        grid_columns: int = 4,
        exam_template: str = "kaoyan_math_16",
        version: str = "v1",
    ) -> str:
        """Build coarse address localization prompt."""
        template = self._get_prompt_template(f"coarse_address_{version}.txt")
        max_row = max(0, grid_rows - 1)
        max_col = max(0, grid_columns - 1)
        prior_text = EXAM_PRIOR_TEMPLATES.get(exam_template, EXAM_PRIOR_TEMPLATES["kaoyan_math_16"])
        return (
            template.replace("{page_index:02d}", f"{page_index:02d}")
            .replace("{page_index}", str(page_index))
            .replace("{grid_rows}", str(grid_rows))
            .replace("{grid_columns}", str(grid_columns))
            .replace("{max_row:02d}", f"{max_row:02d}")
            .replace("{max_row}", str(max_row))
            .replace("{max_col:02d}", f"{max_col:02d}")
            .replace("{max_col}", str(max_col))
            .replace("{exam_structure_prior}", prior_text)
        )

    def build_local_refine_prompt(
        self,
        question_number: str,
        version: str = "v1",
    ) -> str:
        """Build local high-DPI refinement prompt."""
        template = self._get_prompt_template(f"local_refine_{version}.txt")
        return template.replace("{question_number}", str(question_number))

    def build_verify_prompt(
        self,
        q1_number: str,
        q2_number: str,
        version: str = "v1",
    ) -> str:
        """Build conflict verification prompt."""
        template = self._get_prompt_template(f"verify_{version}.txt")
        return (
            template.replace("{q1_number}", str(q1_number))
            .replace("{q2_number}", str(q2_number))
        )

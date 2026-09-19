"""Question Basket Service: Session-wide shopping-cart style problem collector for multi-PDF assembly."""

from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal

from ..models.question import Question, QuestionType


class QuestionBasket(QObject):
    """Singleton-style question basket managing selected questions across multiple exam papers."""

    # Emits current total question count when items are added/removed/cleared
    basket_changed = Signal(int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._questions: List[Question] = []
        self._question_map: Dict[str, Question] = {}

    def add_question(self, question: Question) -> bool:
        """Add or update a question in the basket. Returns True if added as new."""
        if question.id in self._question_map:
            # Update existing reference
            idx = self._questions.index(self._question_map[question.id])
            self._questions[idx] = question
            self._question_map[question.id] = question
            self.basket_changed.emit(len(self._questions))
            return False

        # Store original display number if not already saved
        if not question.original_display_number:
            question.original_display_number = question.display_number

        self._questions.append(question)
        self._question_map[question.id] = question
        self.basket_changed.emit(len(self._questions))
        return True

    def add_questions(self, questions: List[Question]) -> int:
        """Add multiple questions. Returns number of newly added questions."""
        added_count = 0
        for q in questions:
            if self.add_question(q):
                added_count += 1
        return added_count

    def remove_question(self, question_id: str) -> bool:
        """Remove a question by its ID."""
        if question_id in self._question_map:
            q = self._question_map.pop(question_id)
            if q in self._questions:
                self._questions.remove(q)
            self.basket_changed.emit(len(self._questions))
            return True
        return False

    def contains(self, question_id: str) -> bool:
        """Check if a question is in the basket."""
        return question_id in self._question_map

    def clear(self) -> None:
        """Clear all questions from the basket."""
        self._questions.clear()
        self._question_map.clear()
        self.basket_changed.emit(0)

    def get_questions(self) -> List[Question]:
        """Return a copy of all questions in current order."""
        return list(self._questions)

    def count(self) -> int:
        """Return total count of questions in the basket."""
        return len(self._questions)

    def get_grouped_by_paper(self) -> Dict[str, List[Question]]:
        """Group questions by their source paper title or filename."""
        groups: Dict[str, List[Question]] = {}
        for q in self._questions:
            paper_name = q.source_paper_title or "当前试卷"
            if paper_name not in groups:
                groups[paper_name] = []
            groups[paper_name].append(q)
        return groups

    def renumber_sequentially(self, start_num: int = 1) -> None:
        """Renumber all questions in basket sequentially (1, 2, 3...)."""
        for i, q in enumerate(self._questions):
            if not q.original_display_number:
                q.original_display_number = q.display_number
            q.display_number = str(start_num + i)
            q.sort_order = i
        self.basket_changed.emit(len(self._questions))

    def restore_original_numbers(self) -> None:
        """Restore questions to their original paper numbers."""
        for q in self._questions:
            if q.original_display_number:
                q.display_number = q.original_display_number
        self.basket_changed.emit(len(self._questions))

    def sort_by_question_type(self) -> None:
        """Sort questions by standard pedagogical exam sequence: Choice -> Fill-in -> Solve -> Proof -> Other."""
        def type_rank(q: Question) -> int:
            t = q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type or "")
            if t in ("choice", "选择题"):
                return 1
            elif t in ("fill_in", "填空题"):
                return 2
            elif q.is_small_question():
                return 3
            elif t in ("solve", "解答题", "计算题"):
                return 4
            elif t in ("proof", "证明题"):
                return 5
            elif q.is_large_question():
                return 6
            return 7

        self._questions.sort(key=type_rank)
        # Update sort_order accordingly
        for i, q in enumerate(self._questions):
            q.sort_order = i
        self.basket_changed.emit(len(self._questions))

    def move_item(self, from_index: int, to_index: int) -> None:
        """Move question position in the basket."""
        if 0 <= from_index < len(self._questions) and 0 <= to_index < len(self._questions):
            item = self._questions.pop(from_index)
            self._questions.insert(to_index, item)
            for i, q in enumerate(self._questions):
                q.sort_order = i
            self.basket_changed.emit(len(self._questions))


# Global singleton basket instance for application session
GLOBAL_BASKET = QuestionBasket()

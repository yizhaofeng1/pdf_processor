"""Unit tests for QuestionBasket service."""

import pytest
from app.models.question import Question, QuestionType
from app.models.segment import QuestionSegment
from app.services.question_basket import QuestionBasket


@pytest.fixture
def sample_questions():
    q1 = Question(
        id="q1",
        display_number="15",
        original_display_number="15",
        question_type="解答题",
        source_paper_title="2010数学真题",
        segments=[QuestionSegment(page_index=3, normalized_bbox=(0.1, 0.2, 0.9, 0.5))],
    )
    q2 = Question(
        id="q2",
        display_number="3",
        original_display_number="3",
        question_type="选择题",
        source_paper_title="2019数学真题",
        segments=[QuestionSegment(page_index=1, normalized_bbox=(0.1, 0.2, 0.9, 0.3))],
    )
    q3 = Question(
        id="q3",
        display_number="9",
        original_display_number="9",
        question_type="填空题",
        source_paper_title="2019数学真题",
        segments=[QuestionSegment(page_index=2, normalized_bbox=(0.1, 0.2, 0.9, 0.35))],
    )
    return [q1, q2, q3]


def test_question_basket_add_remove(sample_questions):
    basket = QuestionBasket()
    assert basket.count() == 0

    basket.add_question(sample_questions[0])
    assert basket.count() == 1
    assert basket.contains("q1")
    assert not basket.contains("q2")

    # Add duplicate (should update existing, not duplicate)
    basket.add_question(sample_questions[0])
    assert basket.count() == 1

    basket.add_question(sample_questions[1])
    assert basket.count() == 2

    basket.remove_question("q1")
    assert basket.count() == 1
    assert not basket.contains("q1")
    assert basket.contains("q2")

    basket.clear()
    assert basket.count() == 0


def test_question_basket_renumber(sample_questions):
    basket = QuestionBasket()
    basket.add_questions(sample_questions)  # q1 (15), q2 (3), q3 (9)

    basket.renumber_sequentially(start_num=1)
    qs = basket.get_questions()
    assert qs[0].display_number == "1"
    assert qs[0].original_display_number == "15"
    assert qs[1].display_number == "2"
    assert qs[1].original_display_number == "3"
    assert qs[2].display_number == "3"
    assert qs[2].original_display_number == "9"

    basket.restore_original_numbers()
    assert qs[0].display_number == "15"
    assert qs[1].display_number == "3"
    assert qs[2].display_number == "9"


def test_question_basket_sort_by_type(sample_questions):
    basket = QuestionBasket()
    basket.add_questions(sample_questions)  # [q1: 解答题, q2: 选择题, q3: 填空题]

    basket.sort_by_question_type()
    sorted_qs = basket.get_questions()

    # Small questions (选择题, 填空题) should come before large questions (解答题)
    assert sorted_qs[0].question_type in ["选择题", "choice"]
    assert sorted_qs[1].question_type in ["填空题", "fill_in"]
    assert sorted_qs[2].question_type in ["解答题", "solve"]


def test_question_basket_move_item(sample_questions):
    basket = QuestionBasket()
    basket.add_questions(sample_questions)  # [q1, q2, q3]

    basket.move_item(0, 2)  # Move q1 to bottom
    qs = basket.get_questions()
    assert qs[0].id == "q2"
    assert qs[1].id == "q3"
    assert qs[2].id == "q1"

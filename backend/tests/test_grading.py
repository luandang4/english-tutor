import pytest

from app.services import grading
from app.services.lessons import normalize_exercises
from tests.fake_ai import EXERCISES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  Have  Lived. ", "have lived"), ("don’t", "don't"), ("“Souvenir”!", "souvenir")],
)
def test_normalize(raw: str, expected: str) -> None:
    assert grading.normalize(raw) == expected


def test_word_count() -> None:
    assert grading.count_words("I don't like well-known places, do you?") == 7


def test_normalize_exercises_assigns_ids_and_keeps_answer_in_options() -> None:
    draft = EXERCISES[0].model_copy(update={"options": ["a suitcase", "a ticket"]})
    out = normalize_exercises([draft, EXERCISES[1]])
    assert [e["id"] for e in out] == ["e1", "e2"]
    assert "a travel plan" in out[0]["options"]
    assert out[1]["options"] == []


async def test_rule_grading_without_ai() -> None:
    mc = {"type": "multiple_choice", "answers": ["a travel plan"], "question": "q"}
    assert (await grading.grade(mc, "A travel plan", "")).is_correct
    assert not (await grading.grade(mc, "a ticket", "")).is_correct
    fb = {"type": "fill_blank", "answers": ["souvenir", "souvenirs"], "question": "q"}
    g = await grading.grade(fb, "Souvenirs", "")
    assert g.is_correct and g.graded_by == "rule"

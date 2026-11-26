from app.models.topic import Topic
from app.services.ai.prompts import grammar_lesson_prompt, new_exercises_prompt


def _exercise_prompt(section: dict) -> str:
    return new_exercises_prompt(
        skill="grammar", level="B1", title="Present simple", content={"sections": [section]}, past_questions=[]
    )


def test_grammar_prompt_asks_for_one_structure_per_row():
    prompt = grammar_lesson_prompt(
        Topic(skill="grammar", title="Present simple", title_vi="Hiện tại đơn", description_vi=""), "B1"
    )
    assert "Khẳng định" in prompt and "Phủ định" in prompt and "Nghi vấn" in prompt
    assert "never several patterns in one row" in prompt


def test_exercise_prompt_lists_formula_rows():
    section = {
        "heading": "Form",
        "formulas": [
            {"label_vi": "Khẳng định", "pattern": "S + V(s/es)", "example_en": "She works."},
            {"label_vi": "Nghi vấn", "pattern": "Do/Does + S + V?", "example_en": "Does she work?"},
        ],
    }
    assert "Form: Khẳng định: S + V(s/es); Nghi vấn: Do/Does + S + V?" in _exercise_prompt(section)


def test_exercise_prompt_keeps_old_single_formula():
    assert "Form: S + V(s/es)" in _exercise_prompt({"heading": "Form", "formula": "S + V(s/es)"})

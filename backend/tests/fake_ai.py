"""Deterministic stand-in for GeminiClient used by the test-suite."""

from typing import TypeVar

from pydantic import BaseModel

from app.schemas.ai import (
    AnswerGrade,
    CommonMistake,
    ConversationRecap,
    CriterionScore,
    ExerciseDraft,
    ExerciseSetDraft,
    GrammarExample,
    GrammarFormula,
    GrammarLessonDraft,
    GrammarSection,
    SummaryMistake,
    SummaryWord,
    TextTranslation,
    UsefulPhrase,
    VocabLessonDraft,
    VocabWord,
    WordInfo,
    WritingCorrection,
    WritingFeedback,
    WritingTaskDraft,
)

T = TypeVar("T", bound=BaseModel)

WORDS = ["itinerary", "souvenir", "boarding pass"]
MEANINGS = {"itinerary": "lịch trình", "souvenir": "quà lưu niệm", "boarding pass": "thẻ lên máy bay"}

EXERCISES = [
    ExerciseDraft(
        type="multiple_choice",
        instruction_vi="Chọn nghĩa đúng",
        question="An itinerary is…",
        options=["a travel plan", "a suitcase", "a ticket"],
        answers=["a travel plan"],
        explanation_vi="Itinerary = lịch trình.",
    ),
    ExerciseDraft(
        type="fill_blank",
        instruction_vi="Điền từ",
        question="I bought a ___ for my mum.",
        options=[],
        answers=["souvenir"],
        explanation_vi="Souvenir = quà lưu niệm.",
    ),
    ExerciseDraft(
        type="produce",
        instruction_vi="Đặt câu với 'boarding pass'",
        question="Write a sentence with 'boarding pass'.",
        options=[],
        answers=["Please show your boarding pass."],
        explanation_vi="",
    ),
]


class FakeAI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []
        self.fail_next = False

    async def generate_json(self, *, models, system, prompt, schema: type[T], temperature=0.7) -> tuple[T, str]:
        from app.services.ai.client import AIUnavailableError

        self.calls.append(schema.__name__)
        self.prompts.append(prompt)
        if self.fail_next:
            self.fail_next = False
            raise AIUnavailableError("fake outage")
        return self._build(schema, prompt), "fake-model"

    def _build(self, schema: type[BaseModel], prompt: str):  # noqa: ANN202
        if schema is ExerciseSetDraft:
            assert "do not repeat" in prompt and "An itinerary is…" in prompt  # previous questions passed on
            return ExerciseSetDraft(
                exercises=[e.model_copy(update={"question": e.question + " (v2)"}) for e in EXERCISES[:2]]
            )
        if schema is VocabLessonDraft:
            return VocabLessonDraft(
                title="Travel words",
                intro_vi="Giới thiệu",
                words=[
                    VocabWord(
                        word=w,
                        ipa="/x/",
                        part_of_speech="noun",
                        meaning_vi=MEANINGS[w],
                        definition_en="def",
                        example_en=f"An example with {w}.",
                        example_vi="ví dụ",
                        collocations=[],
                    )
                    for w in WORDS
                ],
                tips_vi=["mẹo"],
                exercises=EXERCISES,
            )
        if schema is ConversationRecap:
            return ConversationRecap(
                mistakes=[SummaryMistake(category="Thì quá khứ", wrong="I go", right="I went", explain_vi="quá khứ")],
                new_words=[
                    SummaryWord(
                        word="exhausted", meaning_vi="kiệt sức", part_of_speech="adj", example_en="I was exhausted."
                    )
                ],
                strengths_vi=["Nói câu dài hơn"],
                goals_vi=["Dùng thì quá khứ khi kể chuyện"],
                goal_comment_vi="Đã kể được về bản thân.",
            )
        if schema is WordInfo:
            word = prompt.split("word or phrase: ")[1].split("\n")[0].strip()
            return WordInfo(
                word=word,
                ipa="/fake/",
                part_of_speech="noun",
                meaning_vi=f"nghĩa của từ số {len(self.calls)}",
                definition_en="a fake definition",
                example_en=f"She found {word} by chance.",
                example_vi="Cô ấy tình cờ tìm thấy nó.",
            )
        if schema is GrammarLessonDraft:
            return GrammarLessonDraft(
                title="Present perfect",
                intro_vi="Giới thiệu",
                sections=[
                    GrammarSection(
                        heading="1. Form",
                        explanation_vi="**have/has** + V3",
                        formulas=[
                            GrammarFormula(
                                label_vi="Khẳng định", pattern="S + have/has + V3", example_en="I have eaten."
                            ),
                            GrammarFormula(
                                label_vi="Nghi vấn", pattern="Have/Has + S + V3?", example_en="Have you eaten?"
                            ),
                        ],
                        examples=[GrammarExample(en="I have eaten.", vi="Tôi đã ăn.")],
                    )
                ],
                common_mistakes=[CommonMistake(wrong="I have went", right="I have gone", explanation_vi="V3")],
                summary_vi=["Tóm tắt"],
                exercises=EXERCISES[:2],
            )
        if schema is WritingTaskDraft:
            return WritingTaskDraft(
                title="Email to a friend",
                task_type="email",
                prompt_en="Write an email to Sam about your new job.",
                prompt_vi="Viết email cho Sam.",
                requirements=["new job"],
                min_words=50,
                max_words=100,
                useful_phrases=[UsefulPhrase(phrase="How are you?", meaning_vi="Bạn khỏe không?")],
                outline_vi=["Chào hỏi"],
            )
        if schema is AnswerGrade:
            ok = "boarding pass" in prompt.split("Learner answer:")[-1].lower()
            return AnswerGrade(
                is_correct=ok, score=90 if ok else 30, feedback_vi="Nhận xét", corrected_answer="Fixed sentence."
            )
        if schema is WritingFeedback:
            return WritingFeedback(
                overall_score=0,  # recomputed server-side from criteria
                cefr_estimate="A2",
                summary_vi="Tốt",
                criteria=[
                    CriterionScore(criterion="task_achievement", score=60, comment_vi="ok"),
                    CriterionScore(criterion="coherence_cohesion", score=70, comment_vi="ok"),
                    CriterionScore(criterion="lexical_resource", score=50, comment_vi="ok"),
                    CriterionScore(criterion="grammar_accuracy", score=40, comment_vi="ok"),
                ],
                strengths_vi=["a"],
                improvements_vi=["b"],
                corrections=[
                    WritingCorrection(
                        original="I start", corrected="I started", category="grammar", explanation_vi="past"
                    ),
                    WritingCorrection(
                        original="not in text", corrected="x", category="grammar", explanation_vi="dropped"
                    ),
                ],
                improved_version="Improved.",
            )
        if schema is TextTranslation:
            if "Word or phrase:" in prompt:
                return TextTranslation(vietnamese="lịch trình", ipa="/aɪˈtɪnəˌrɛri/", part_of_speech="noun")
            return TextTranslation(vietnamese="Bản dịch tiếng Việt.", ipa="", part_of_speech="")
        raise AssertionError(f"unexpected schema {schema}")

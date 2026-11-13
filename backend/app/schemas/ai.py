"""Structured-output schemas the Gemini models must fill (passed as `response_schema`).

Kept flat and simple (no unions / dicts) so they work with Gemini's JSON-schema subset.
"""

from typing import Literal

from pydantic import BaseModel, Field

ExerciseKind = Literal["multiple_choice", "fill_blank", "rewrite", "produce"]


class ExerciseDraft(BaseModel):
    type: ExerciseKind = Field(
        description=(
            "multiple_choice: pick one option; fill_blank: one gap marked ___ in `question`; "
            "rewrite: transform the given sentence as instructed; produce: write an original sentence"
        )
    )
    instruction_vi: str = Field(description="Short instruction in Vietnamese")
    question: str = Field(description="The English prompt/sentence. For fill_blank include exactly one ___ gap")
    options: list[str] = Field(description="3-4 options for multiple_choice, otherwise empty")
    answers: list[str] = Field(
        description=(
            "Accepted answers. multiple_choice: exactly the correct option text; fill_blank: every acceptable "
            "word/phrase for the gap; rewrite/produce: one or two model answers"
        )
    )
    explanation_vi: str = Field(description="Why the answer is correct, in Vietnamese, 1-2 sentences")


class ExerciseSetDraft(BaseModel):
    exercises: list[ExerciseDraft]


class VocabWord(BaseModel):
    word: str
    ipa: str = Field(description="IPA transcription, US English, with slashes")
    part_of_speech: str = Field(description="noun / verb / adjective / adverb / phrase / phrasal verb ...")
    meaning_vi: str = Field(description="Concise Vietnamese meaning")
    definition_en: str = Field(description="Simple learner-dictionary definition in English")
    example_en: str = Field(description="Natural example sentence using the word")
    example_vi: str = Field(description="Vietnamese translation of the example")
    collocations: list[str] = Field(description="2-3 common collocations or related phrases")


class VocabLessonDraft(BaseModel):
    title: str = Field(description="Lesson title in English")
    intro_vi: str = Field(description="1-2 sentence introduction in Vietnamese")
    words: list[VocabWord]
    tips_vi: list[str] = Field(description="2-3 memorisation or usage tips in Vietnamese")
    exercises: list[ExerciseDraft]


class GrammarExample(BaseModel):
    en: str
    vi: str


class GrammarSection(BaseModel):
    heading: str = Field(description="Section heading (Vietnamese, may contain English terms)")
    explanation_vi: str = Field(description="Clear explanation in Vietnamese. Markdown allowed (bold, lists)")
    formula: str = Field(description="Structure/formula, e.g. 'S + have/has + V3'. Empty if not applicable")
    examples: list[GrammarExample]


class CommonMistake(BaseModel):
    wrong: str
    right: str
    explanation_vi: str


class GrammarLessonDraft(BaseModel):
    title: str
    intro_vi: str
    sections: list[GrammarSection]
    common_mistakes: list[CommonMistake]
    summary_vi: list[str] = Field(description="3-5 key takeaways in Vietnamese")
    exercises: list[ExerciseDraft]


class UsefulPhrase(BaseModel):
    phrase: str
    meaning_vi: str


class WritingTaskDraft(BaseModel):
    title: str
    task_type: str = Field(description="e.g. email, opinion essay, story, review, report, description")
    prompt_en: str = Field(description="The writing task as an exam-style prompt in English")
    prompt_vi: str = Field(description="Vietnamese translation/explanation of the task")
    requirements: list[str] = Field(description="3-5 concrete points the text must cover (English)")
    min_words: int
    max_words: int
    useful_phrases: list[UsefulPhrase] = Field(description="6-8 useful phrases for this task")
    outline_vi: list[str] = Field(description="Suggested paragraph-by-paragraph outline in Vietnamese")


class AnswerGrade(BaseModel):
    is_correct: bool = Field(description="True if the answer is acceptable (fully meets the task, natural English)")
    score: int = Field(description="0-100")
    feedback_vi: str = Field(description="Short feedback in Vietnamese: what is wrong/good and why")
    corrected_answer: str = Field(description="A corrected/improved version of the learner answer in English")


class CriterionScore(BaseModel):
    criterion: Literal["task_achievement", "coherence_cohesion", "lexical_resource", "grammar_accuracy"]
    score: int = Field(description="0-100")
    comment_vi: str


class WritingCorrection(BaseModel):
    original: str = Field(description="Exact substring copied from the learner's text")
    corrected: str
    category: Literal["grammar", "vocabulary", "spelling", "punctuation", "word_choice", "style", "coherence"]
    explanation_vi: str


class WritingFeedback(BaseModel):
    overall_score: int = Field(description="0-100")
    cefr_estimate: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    summary_vi: str = Field(description="2-3 sentence overall comment in Vietnamese")
    criteria: list[CriterionScore]
    strengths_vi: list[str]
    improvements_vi: list[str]
    corrections: list[WritingCorrection]
    improved_version: str = Field(description="The learner's text rewritten at a slightly higher level")

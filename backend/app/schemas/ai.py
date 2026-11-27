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


class WordInfo(BaseModel):
    """Dictionary entry for a word the learner adds to their deck by hand."""

    word: str = Field(description="The word or phrase in its dictionary form, spelling corrected")
    ipa: str = Field(description="IPA transcription, US English, with slashes")
    part_of_speech: str = Field(description="noun / verb / adjective / adverb / phrase / phrasal verb ...")
    meaning_vi: str = Field(description="Concise Vietnamese meaning (the sense used in the context, if given)")
    definition_en: str = Field(description="Simple learner-dictionary definition in English")
    example_en: str = Field(description="Natural example sentence using the word")
    example_vi: str = Field(description="Vietnamese translation of the example")


class VocabLessonDraft(BaseModel):
    title: str = Field(description="Lesson title in English")
    intro_vi: str = Field(description="1-2 sentence introduction in Vietnamese")
    words: list[VocabWord]
    tips_vi: list[str] = Field(description="2-3 memorisation or usage tips in Vietnamese")
    exercises: list[ExerciseDraft]


class GrammarExample(BaseModel):
    en: str
    vi: str


class FormRow(BaseModel):
    label_vi: str = Field(description="Row name in Vietnamese: 'Khẳng định', 'Phủ định', 'Nghi vấn', 'Trả lời ngắn'...")
    pattern: str = Field(description="ONE structure, e.g. 'S + have/has + V3'. Never join several with '|'")
    example_en: str = Field(description="One short example sentence built from this pattern")


class CompareColumn(BaseModel):
    title: str = Field(description="Name of the grammar point this column is about, e.g. 'Hiện tại đơn'")
    points_vi: list[str] = Field(description="2-4 short points in Vietnamese, same order of ideas in every column")
    example_en: str = Field(description="One example sentence for this column")


class TableRow(BaseModel):
    cells: list[str]


class GrammarBlock(BaseModel):
    """One building block of a section. Fill only the fields its `kind` uses; leave the others empty."""

    kind: Literal["text", "forms", "compare", "table", "word_list", "tip"]
    title: str = Field(
        default="",
        description="forms: exact name of the grammar point (same spelling everywhere). "
        "word_list: what the list is, e.g. 'Dấu hiệu Hiện tại đơn'. table: caption. Otherwise empty",
    )
    text_vi: str = Field(default="", description="text/tip: 1-3 sentences in Vietnamese, **bold** allowed")
    rows: list[FormRow] = Field(default=[], description="forms: one row per sentence type of ONE grammar point")
    columns: list[CompareColumn] = Field(default=[], description="compare: one column per grammar point (2-3)")
    headers: list[str] = Field(default=[], description="table: column headers")
    table_rows: list[TableRow] = Field(default=[], description="table: rows, same number of cells as headers")
    words: list[str] = Field(default=[], description="word_list: short words/phrases (signal words, verbs...)")


class GrammarSection(BaseModel):
    heading: str = Field(description="Section heading (Vietnamese, may contain English terms)")
    blocks: list[GrammarBlock] = Field(description="1-5 blocks, in reading order")
    examples: list[GrammarExample] = Field(description="2-3 example sentences with Vietnamese translation")


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


class TextTranslation(BaseModel):
    vietnamese: str = Field(description="Natural Vietnamese translation (word mode: the meaning in this context)")
    ipa: str = Field(description="Word mode: US IPA with slashes. Sentence mode: empty string")
    part_of_speech: str = Field(description="Word mode: noun / verb / adjective / ... Sentence mode: empty string")


class SummaryMistake(BaseModel):
    category: str = Field(description="Short Vietnamese error category, e.g. 'Thì quá khứ', 'Mạo từ', 'Số nhiều'")
    wrong: str = Field(description="The learner's wrong words, quoted from the transcript")
    right: str = Field(description="Corrected version")
    explain_vi: str = Field(description="One short Vietnamese reason")


class SummaryWord(BaseModel):
    word: str = Field(description="English word or short phrase taught or needed in this session")
    meaning_vi: str
    part_of_speech: str
    example_en: str = Field(description="Short example sentence using it, ideally from the session")


class ConversationRecap(BaseModel):
    mistakes: list[SummaryMistake] = Field(description="Max 5 most important real errors, grouped by type")
    new_words: list[SummaryWord] = Field(description="Max 8 useful words / phrases from this session")
    strengths_vi: list[str] = Field(description="1-2 specific things the learner did well, in Vietnamese")
    goals_vi: list[str] = Field(description="1-2 concrete goals for the next session, in Vietnamese")
    goal_comment_vi: str = Field(
        description="If a lesson goal is given: did they reach it? One Vietnamese sentence. Else empty"
    )


# ---------- sentence translation practice ----------
class SentenceItemDraft(BaseModel):
    vi: str = Field(description="One natural Vietnamese sentence for the learner to write in English")
    target_words: list[str] = Field(description="1-2 English words / phrases the English sentence must use")
    grammar_point: str = Field(
        description="Vietnamese name of the grammar point it practises, e.g. 'Hiện tại hoàn thành'"
    )
    answers: list[str] = Field(description="2-3 correct, natural English translations (different valid wordings)")
    hint_vi: str = Field(description="Short Vietnamese hint: the sentence frame / tense to use, never the full answer")
    hint_words: list[str] = Field(description="2-4 English keywords that help (not the whole sentence)")


class SentenceSetDraft(BaseModel):
    title: str = Field(description="Short Vietnamese title for this practice set")
    items: list[SentenceItemDraft] = Field(description="Exactly the requested number of sentences, easy to harder")


class SentenceError(BaseModel):
    kind: Literal["grammar", "vocabulary", "word_order", "spelling", "missing", "meaning"]
    original: str = Field(description="The wrong span copied exactly from the learner's sentence ('' if missing)")
    fix: str = Field(description="The corrected span")
    explain_vi: str = Field(description="One short Vietnamese reason, e.g. 'quá khứ: go → went'")


class SentenceGrade(BaseModel):
    verdict: Literal["correct", "almost", "wrong"] = Field(
        description="correct: right meaning and grammar (other valid wordings are correct); almost: meaning right "
        "with 1-2 small slips; wrong: meaning lost or major grammar errors"
    )
    score: int = Field(description="0-100")
    corrected: str = Field(description="The learner's sentence with only the errors fixed (keep their wording)")
    natural: str = Field(description="A natural way a native speaker would say it (may equal corrected)")
    errors: list[SentenceError] = Field(description="Every real error, max 5; empty when correct")
    target_words_used: bool = Field(description="True if every target word / phrase is used correctly")
    comment_vi: str = Field(description="One short encouraging Vietnamese comment: what was good / what to fix")

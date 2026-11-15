"""Request / response models of the HTTP API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import LEVELS, Feature, Skill
from app.core.security import password_problem

LevelCode = Literal["A1", "A2", "B1", "B2", "C1"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _strong_password(value: str) -> str:
    if problem := password_problem(value):
        raise ValueError(problem)
    return value


class RegisterIn(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    _password = field_validator("password")(_strong_password)


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    _password = field_validator("new_password")(_strong_password)


AccessStatusLiteral = Literal["admin", "active", "pending", "expired", "locked"]


class PlanBrief(BaseModel):
    code: str
    name: str
    expires_at: datetime | None = Field(description="null = never expires")


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    created_at: datetime
    is_admin: bool
    features: list[str] = Field(description="Features this user may use right now (plan + system switches)")
    view_features: list[str] = Field(default=[], description="Features whose own history the user may open")
    pending: bool = Field(description="No plan yet: waiting for an admin")
    access_status: AccessStatusLiteral = "active"
    plan: PlanBrief | None = None
    upgrade_contact: str = ""


class FeatureUsage(BaseModel):
    feature: str
    label: str
    unit: str
    used: int = Field(description="Used today")
    limit: int | None = Field(description="Daily limit incl. bonus; null = unlimited")
    used_month: int = 0
    limit_month: int | None = Field(default=None, description="Monthly limit incl. bonus; null = unlimited")


# ---------- admin ----------
class SystemSettingsIO(BaseModel):
    features_enabled: dict[str, bool]
    registration_open: bool
    upgrade_contact: str = Field(default="", max_length=300)


MAX_LIMIT = 100_000


class PlanLimit(BaseModel):
    daily: int = Field(default=0, ge=0, le=MAX_LIMIT, description="0 = unlimited")
    monthly: int = Field(default=0, ge=0, le=MAX_LIMIT, description="0 = unlimited")


class PlanIn(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,39}$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    features: list[Feature] = []
    limits: dict[Feature, PlanLimit] = {}
    max_session_minutes: int | None = Field(default=None, ge=1, le=180, description="null = server default")
    duration_days: int | None = Field(default=None, ge=1, le=3650, description="Default expiry; null = never")
    is_default_for_new: bool = False
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)
    price_label: str = Field(default="", max_length=80)
    billing_cycle: Literal["monthly", "quarterly", "yearly"] | None = None


class PlanOut(PlanIn):
    id: int
    active_users: int = 0


class SubscriptionOut(BaseModel):
    id: int
    plan_id: int
    plan_code: str
    plan_name: str
    starts_at: datetime
    expires_at: datetime | None
    status: str
    note: str
    source: str
    created_at: datetime


class SubscriptionAssign(BaseModel):
    plan_id: int
    expires_at: datetime | None = Field(default=None, description="null = never expires")
    note: str = Field(default="", max_length=500)


class GrantIn(BaseModel):
    feature: Feature
    amount: int = Field(ge=1, le=MAX_LIMIT)
    scope: Literal["day", "month"] = Field(default="month", description="Today only, or this calendar month")
    note: str = Field(default="", max_length=500)


class GrantOut(ORM):
    id: int
    feature: str
    amount: int
    period: str
    note: str
    created_at: datetime


class AdminUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    created_at: datetime
    last_login_at: datetime | None
    is_admin: bool
    is_active: bool
    access_status: AccessStatusLiteral
    features: list[str] = Field(description="Features the plan gives (admins implicitly have all)")
    subscription: SubscriptionOut | None = Field(description="Current subscription (or the expired one)")
    usage: list[FeatureUsage] = Field(description="Day / month usage against the plan's limits")
    grants: list[GrantOut] = Field(description="Bonus allowances this month")
    usage_today: dict[str, int]


class AdminUserPatch(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class FeatureTotal(BaseModel):
    feature: str
    label: str
    unit: str
    units: int
    events: int
    users: int


class UsageReport(BaseModel):
    month: str = Field(description="YYYY-MM in the app timezone")
    features: list[FeatureTotal]
    conversation_minutes: int
    pronunciation_assessments: int
    azure_free_hours: float = Field(description="Azure Speech free tier (F0): audio hours per month")
    seconds_per_assessment_estimate: int = Field(description="Assumed audio length of one assessment")
    estimated_pronunciation_hours: float = Field(description="Estimate: assessments x assumed length")


# ---------- meta / topics ----------
class Option(BaseModel):
    value: str
    label: str


class FeatureInfo(BaseModel):
    value: str
    label: str
    unit: str


class MetaOut(BaseModel):
    levels: list[Option]
    scenarios: list[Option]
    features: list[FeatureInfo]
    pronunciation_enabled: bool
    registration_open: bool


class TopicOut(ORM):
    id: int
    slug: str
    skill: Skill
    title: str
    title_vi: str
    description_vi: str
    icon: str
    is_custom: bool = False


# ---------- lessons ----------
class CustomTopicIn(BaseModel):
    """A learner's own topic instead of a preset one."""

    title: str = Field(min_length=2, max_length=120)
    request: str = Field(default="", max_length=1000, description="Extra wishes for the AI (focus, context, style)")


class TopicChoice(BaseModel):
    """Exactly one of: a preset topic id, or a custom topic."""

    topic_id: int | None = None
    custom: CustomTopicIn | None = None
    level: LevelCode = "B1"

    @model_validator(mode="after")
    def _one_topic(self) -> "TopicChoice":
        if (self.topic_id is None) == (self.custom is None):
            raise ValueError("Chọn một chủ đề có sẵn hoặc nhập chủ đề riêng.")
        return self


class LessonCreate(TopicChoice):
    skill: Literal["vocabulary", "grammar"] | None = Field(default=None, description="Required with `custom`")

    @model_validator(mode="after")
    def _skill_for_custom(self) -> "LessonCreate":
        if self.custom is not None and self.skill is None:
            raise ValueError("Cần chọn loại bài (từ vựng / ngữ pháp) cho chủ đề riêng.")
        return self


class LessonSummary(ORM):
    id: int
    skill: Skill
    level: str
    status: str
    title: str
    score: float | None
    created_at: datetime
    completed_at: datetime | None
    topic: TopicOut
    exercise_count: int = 0
    answered_count: int = 0


class ExerciseResult(BaseModel):
    answer: str
    is_correct: bool
    score: int
    feedback_vi: str
    corrected_answer: str
    answers: list[str]
    explanation_vi: str
    attempts: int


class ExerciseOut(BaseModel):
    """Public view of an exercise: answers/explanation only revealed after an attempt."""

    id: str
    type: str
    instruction_vi: str
    question: str
    options: list[str]
    result: ExerciseResult | None = None


class LessonDetail(LessonSummary):
    error: str | None
    content: dict[str, Any] | None = Field(description="Lesson body without exercises")
    exercises: list[ExerciseOut]
    in_deck: int = 0
    exercise_round: int = 1
    exercises_status: str | None = None
    exercises_error: str | None = None


class AttemptCreate(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)


class AttemptOut(BaseModel):
    exercise: ExerciseOut
    lesson_status: str
    lesson_score: float | None
    cards_added: int = 0


# ---------- vocabulary deck ----------
class CardOut(ORM):
    id: int
    word: str
    ipa: str
    part_of_speech: str
    meaning_vi: str
    definition_en: str
    example_en: str
    example_vi: str
    due_at: datetime
    reps: int
    lapses: int
    last_reviewed_at: datetime | None
    intervals: dict[str, str] = {}
    lesson_id: int | None = None
    lesson_title: str | None = None
    source: str = "lesson"
    state: Literal["new", "learning", "mature"] = "new"
    is_hard: bool = Field(default=False, description="Forgotten 4+ times")
    tips_vi: list[str] = Field(default=[], description="Memory tips of the word's lesson (hard words only)")


class DeckStats(BaseModel):
    total: int
    due: int
    new: int
    learning: int
    mature: int
    reviewed_today: int
    hard: int = 0


class ReviewCreate(BaseModel):
    rating: Literal[1, 2, 3, 4]


class DeckAddOut(BaseModel):
    added: int
    in_deck: int


# ---------- review quizzes (lesson "Kiểm tra lại" + auto-graded review sessions) ----------
QuestionKind = Literal[
    "choose_meaning", "listen_choose", "listen_type", "vi_to_en", "fill_sentence", "grammar_choice", "grammar_fill"
]
AnswerResult = Literal["correct", "near", "wrong"]
SessionMode = Literal["due", "soon", "hard", "lesson", "random"]


class QuizQuestion(BaseModel):
    """One question. The expected answer is never included; it is revealed by the answer endpoint."""

    id: str = Field(description="Opaque id, sent back with the answer")
    kind: QuestionKind
    prompt: str = Field(description="Word / meaning / sentence with ___ (empty for listening questions)")
    hint_vi: str = ""
    part_of_speech: str = ""
    options: list[str] = []
    audio_url: str | None = Field(default=None, description="Listening questions: the word's audio")
    letters: int = Field(default=0, description="Typed questions: length of the expected answer")
    first_letter: str = Field(default="", description="Typed questions: shown only when the learner asks for a hint")
    card_id: int | None = None


class QuizOut(BaseModel):
    lesson_id: int
    skill: Skill
    title: str
    questions: list[QuizQuestion]


class SessionOut(BaseModel):
    mode: SessionMode
    questions: list[QuizQuestion]
    remaining: int = Field(description="Matching cards not included in this batch (e.g. due beyond the cap)")


class AnswerIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    answer: str = Field(default="", max_length=300)
    hinted: bool = Field(default=False, description="Learner revealed the hint: a right answer counts as Hard")
    requeued: bool = Field(default=False, description="Retry of a card missed earlier in this session: no FSRS")


class WordReveal(BaseModel):
    word: str
    ipa: str = ""
    part_of_speech: str = ""
    meaning_vi: str = ""
    example_en: str = ""
    example_vi: str = ""


class AnswerOut(BaseModel):
    result: AnswerResult
    expected: str
    explanation_vi: str = ""
    word: WordReveal | None = None
    card_id: int | None = None
    rating: int | None = Field(default=None, description="FSRS rating applied; null = schedule unchanged")
    next_review_at: datetime | None = None


class QuizItemResult(BaseModel):
    question_id: str
    label: str
    expected: str
    result: AnswerResult | None = Field(description="null = not answered")


class QuizResultOut(BaseModel):
    score: float
    total: int
    correct: int
    near: int
    wrong: int
    items: list[QuizItemResult]
    next_recheck_at: datetime | None = None
    recheck_step: int = 0


class ForecastDay(BaseModel):
    date: str
    count: int


class GrammarRecheckDue(BaseModel):
    lesson_id: int
    title: str
    step: int
    due_at: datetime


class ReviewForecast(BaseModel):
    due: int
    minutes: int = Field(description="Estimated minutes for today's due cards (~20 s per card)")
    days: list[ForecastDay] = Field(description="Today and the next 6 days: cards due on each day")
    grammar: list[GrammarRecheckDue]


class LessonReviewStats(BaseModel):
    lesson_id: int
    cards: int = 0
    due: int = 0
    retention: float | None = Field(
        default=None, description="Mean FSRS retrievability (0-100) of the lesson's reviewed cards"
    )
    next_review_at: datetime | None = None
    last_quiz_score: float | None = None
    recheck_step: int = 0
    recheck_due: bool = False


class SrsSettingsIO(BaseModel):
    desired_retention: float = Field(ge=0.85, le=0.95)
    new_cards_per_day: int = Field(ge=5, le=100)


class CardCreate(BaseModel):
    """Add a word to the deck. Only `word` is required: missing meaning / IPA / example are filled by Gemini."""

    word: str = Field(min_length=1, max_length=120)
    context: str = Field(default="", max_length=500, description="Sentence where the learner met the word")
    ipa: str = Field(default="", max_length=120)
    part_of_speech: str = Field(default="", max_length=40)
    meaning_vi: str = Field(default="", max_length=500)
    definition_en: str = Field(default="", max_length=500)
    example_en: str = Field(default="", max_length=500)
    example_vi: str = Field(default="", max_length=500)


class CardAddOut(BaseModel):
    card: CardOut
    created: bool


class DueCount(BaseModel):
    due: int


# ---------- writing ----------
class WritingTaskCreate(TopicChoice):
    pass


class SubmissionOut(ORM):
    id: int
    task_id: int
    text: str
    word_count: int
    status: str
    overall_score: int | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime


class WritingTaskSummary(ORM):
    id: int
    level: str
    status: str
    title: str
    created_at: datetime
    topic: TopicOut
    best_score: int | None = None
    submission_count: int = 0


class WritingTaskDetail(WritingTaskSummary):
    prompt: dict[str, Any] | None
    error: str | None
    submissions: list[SubmissionOut]


class SubmissionCreate(BaseModel):
    text: str = Field(min_length=20, max_length=8000)


# ---------- pronunciation ----------
class PhonemeOut(BaseModel):
    phoneme: str
    score: float


class WordScoreOut(BaseModel):
    word: str
    score: float
    error_type: str
    phonemes: list[PhonemeOut]


class PronunciationOut(BaseModel):
    id: int
    reference_text: str
    recognized_text: str
    pron_score: float
    accuracy: float
    fluency: float
    completeness: float
    prosody: float | None
    words: list[WordScoreOut]


# ---------- conversations ----------
class ConversationSummary(ORM):
    id: int
    level: str
    scenario: str
    topic: str | None = None
    voice: str
    created_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    turns: int


class ConversationDetail(ConversationSummary):
    transcript: list[dict[str, Any]]


# ---------- progress ----------
class SkillProgress(BaseModel):
    skill: str
    completed: int
    in_progress: int
    average_score: float | None


class ActivityDay(BaseModel):
    date: str
    count: int


class RecentItem(BaseModel):
    kind: str
    title: str
    score: float | None
    at: datetime
    link: str


class ProgressOut(BaseModel):
    streak_days: int
    active_days_30: int
    skills: list[SkillProgress]
    deck: DeckStats
    writing_average: float | None
    conversation_minutes: int
    conversation_count: int
    pronunciation_average: float | None
    activity: list[ActivityDay]
    recent: list[RecentItem]


def level_options() -> list[Option]:
    return [Option(value=k, label=v["label"]) for k, v in LEVELS.items()]

"""ORM models. Import everything here so Alembic autogenerate sees all tables."""

from app.models.access import AppSetting, UsageEvent
from app.models.conversation import ConversationSession, LearnerMemory
from app.models.lesson import ExerciseAttempt, Lesson, LessonRecheck
from app.models.plan import Plan, Subscription, UsageGrant
from app.models.pronunciation import PronunciationAttempt
from app.models.sentence import SentenceAttempt, SentenceSet
from app.models.topic import Topic
from app.models.user import AuthSession, User
from app.models.vocab import ReviewLog, SrsSettings, VocabCard
from app.models.writing import WritingSubmission, WritingTask

__all__ = [
    "AppSetting",
    "UsageEvent",
    "AuthSession",
    "User",
    "ConversationSession",
    "LearnerMemory",
    "ExerciseAttempt",
    "Lesson",
    "LessonRecheck",
    "Plan",
    "Subscription",
    "UsageGrant",
    "PronunciationAttempt",
    "ReviewLog",
    "SentenceAttempt",
    "SentenceSet",
    "SrsSettings",
    "Topic",
    "VocabCard",
    "WritingSubmission",
    "WritingTask",
]

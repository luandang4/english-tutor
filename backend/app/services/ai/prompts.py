"""Prompt templates for lesson generation and grading (all Gemini)."""

from app.core.constants import LEARNER_PROFILE, LEVELS
from app.models.topic import Topic

TEACHER_SYSTEM = f"""You are an expert English teacher and materials writer for {LEARNER_PROFILE}.
- Content must be accurate, natural, modern English (US spelling) and appropriate for the CEFR level given.
- Vietnamese text must be natural, correct Vietnamese with full diacritics.
- Never include answers inside the question text. Keep everything self-contained.
- Output only the JSON object that matches the schema."""

GRADER_SYSTEM = f"""You are a fair, encouraging English teacher grading answers from {LEARNER_PROFILE}.
- Judge meaning, grammar and naturalness. Accept any valid alternative, not only the model answer.
- Minor capitalisation/punctuation slips do not make an answer wrong.
- Feedback is in Vietnamese with full diacritics, short and specific; quote English words as needed.
- Output only the JSON object that matches the schema."""

WRITING_GRADER_SYSTEM = f"""You are a certified English writing examiner coaching {LEARNER_PROFILE}.
Grade like a strict-but-kind examiner using four criteria (0-100 each):
task_achievement, coherence_cohesion, lexical_resource, grammar_accuracy. overall_score is their rounded mean.
- corrections: list the most important errors (max 15). `original` MUST be copied exactly from the learner text
  (a short span, not the whole sentence when avoidable) so it can be highlighted.
- improved_version keeps the learner's ideas and structure but fixes errors and upgrades language one level.
- All explanations/comments in Vietnamese with full diacritics.
- Output only the JSON object that matches the schema."""


def _level(level: str) -> str:
    return f"CEFR {level} ({LEVELS[level]['ai']})"


def _topic(topic: Topic, label: str = "Topic") -> str:
    if not topic.is_custom:
        return f"{label}: {topic.title} — {topic.focus or topic.description_vi}"
    line = f"{label} (chosen by the learner): {topic.title}"
    if topic.focus:
        line += (
            f"\nLearner's wishes: {topic.focus}\n"
            "Follow these wishes for content, context and examples, but keep the required structure, counts and "
            "level below. If the topic is not suitable for this kind of lesson, use the closest reasonable "
            "interpretation."
        )
    return line


def vocab_lesson_prompt(topic: Topic, level: str, known_words: list[str]) -> str:
    avoid = ", ".join(known_words[:150]) or "(none)"
    return f"""Create a vocabulary lesson.
{_topic(topic)}
Learner level: {_level(level)}

Requirements:
- 10 high-value words or short phrases for this topic and level (mix of nouns, verbs, adjectives, collocations).
- Avoid words the learner already has in their deck: {avoid}
- 8 exercises that practise THESE words: 3 multiple_choice (meaning or usage in context),
  3 fill_blank (sentence with one gap; answers = the target word in the right form, include valid variants),
  2 produce (ask the learner to write their own sentence using a given word; answers = 1-2 model sentences).
- Exercises must be answerable from the lesson; vary which words are tested."""


def grammar_lesson_prompt(topic: Topic, level: str) -> str:
    return f"""Create a grammar lesson.
{_topic(topic, "Grammar point")}
Learner level: {_level(level)}

Requirements:
- 2-4 sections: form, usage/meaning, signal words or contrasts as relevant. Each with a formula (if any)
  and 2-3 examples with Vietnamese translation. Explain like a good Vietnamese teacher (concise, practical).
- 3-4 common mistakes Vietnamese learners make with this point.
- 10 exercises, increasing difficulty: 4 multiple_choice, 3 fill_blank (answers = every valid form),
  2 rewrite (transform a sentence using the target structure; answers = model rewrites),
  1 produce (write an original sentence/short answer using the structure)."""


def writing_task_prompt(topic: Topic, level: str) -> str:
    return f"""Create one writing assignment.
{_topic(topic, "Task type / topic")}
Learner level: {_level(level)}

Make it realistic and specific (a concrete situation/question), with a word range suitable for the level
(A1-A2: 50-100, B1: 120-180, B2: 180-250, C1: 220-300 words)."""


def answer_grading_prompt(*, exercise: dict, answer: str, context: str) -> str:
    models = "; ".join(exercise.get("answers", [])) or "(none)"
    return f"""Lesson context: {context}
Exercise type: {exercise["type"]}
Instruction: {exercise.get("instruction_vi", "")}
Question: {exercise["question"]}
Model answer(s): {models}

Learner answer: {answer}

Grade the learner answer. For fill_blank the answer is only the word/phrase for the gap."""


def writing_grading_prompt(*, task: dict, level: str, text: str) -> str:
    reqs = "\n".join(f"- {r}" for r in task.get("requirements", []))
    return f"""Target level: {_level(level)}
Task ({task.get("task_type", "")}): {task.get("prompt_en", "")}
Required points:
{reqs}
Word range: {task.get("min_words")}-{task.get("max_words")}

Learner text:
\"\"\"
{text}
\"\"\""""


EXERCISE_MIX = {
    "vocabulary": "8 exercises: 3 multiple_choice, 3 fill_blank, 2 produce",
    "grammar": "10 exercises, increasing difficulty: 4 multiple_choice, 3 fill_blank, 2 rewrite, 1 produce",
}


def new_exercises_prompt(*, skill: str, level: str, title: str, content: dict, past_questions: list[str]) -> str:
    if skill == "vocabulary":
        words = content.get("words", [])
        lines = [f"- {w['word']} ({w.get('part_of_speech', '')}): {w.get('meaning_vi', '')}" for w in words]
        target = "Target words (practise ONLY these):\n" + "\n".join(lines)
    else:
        target = "Grammar point and its sections:\n" + "\n".join(
            f"- {s.get('heading', '')}: {s.get('formula', '')}" for s in content.get("sections", [])
        )
    past = "\n".join(f"- {q}" for q in past_questions[-60:]) or "(none)"
    return f"""Create a NEW practice set for an existing lesson the learner has already studied.
Lesson: {title}
Learner level: {_level(level)}
{target}

Requirements:
- {EXERCISE_MIX[skill]}.
- Use NEW sentences and contexts: do not repeat or paraphrase any of these previous questions:
{past}
- Slightly more challenging than a first practice (more natural contexts, fewer obvious clues),
  but still within the learner's level.
- fill_blank: exactly one ___ gap, list every acceptable answer. multiple_choice: plausible distractors."""

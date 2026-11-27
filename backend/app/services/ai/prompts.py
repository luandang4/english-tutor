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


def topic_line(topic: Topic, label: str = "Topic") -> str:
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
    avoid = ", ".join(known_words) or "(none)"
    return f"""Create a vocabulary lesson.
{topic_line(topic)}
Learner level: {_level(level)}

Requirements:
- 10 high-value words or short phrases for this topic and level (mix of nouns, verbs, adjectives, collocations).
- Every word must be NEW: do not use any word or phrase below, nor a close variant of one (other form, plural,
  same phrase with a different verb). The learner already studied them: {avoid}
- 8 exercises that practise THESE words: 3 multiple_choice (meaning or usage in context),
  3 fill_blank (sentence with one gap; answers = the target word in the right form, include valid variants),
  2 produce (ask the learner to write their own sentence using a given word; answers = 1-2 model sentences).
- Exercises must be answerable from the lesson; vary which words are tested."""


GRAMMAR_BLOCKS = """- Build every section ONLY from these blocks (the app draws each kind with a fixed layout):
  text: 1-3 sentences of explanation. No headings, tables or long lists inside text.
  forms: the structure of ONE grammar point (title = its name): rows "Khẳng định", "Phủ định", "Nghi vấn"
    (the question pattern ends with "?"), plus "Trả lời ngắn" if useful. Two tenses = two forms blocks, never
    mixed in one block. Each row has one pattern and its own short example.
  compare: differences between 2-3 grammar points, one column each, same order of ideas in every column.
  table: anything tabular (irregular verbs, spelling rules, time expressions with meanings).
  word_list: signal words, stative verbs and other plain word lists. title says what the list is, e.g.
    "Dấu hiệu Hiện tại đơn", "Động từ trạng thái".
  tip: one short note, warning or memory trick.
- Use the same name for the same grammar point in every block (e.g. always "Hiện tại đơn"); the app colours
  each point consistently. Patterns and word lists go in forms / word_list / table, never in text."""


def grammar_lesson_prompt(topic: Topic, level: str) -> str:
    return f"""Create a grammar lesson.
{topic_line(topic, "Grammar point")}
Learner level: {_level(level)}

Requirements:
- 2-5 sections (more only if the learner asked for more content, max 7), usually in this order: form, usage /
  meaning, contrasts, signal words, special cases. Explain like a good Vietnamese teacher: concise, practical.
{GRAMMAR_BLOCKS}
- 3-4 common mistakes Vietnamese learners make with this point.
- 10 exercises, increasing difficulty: 4 multiple_choice, 3 fill_blank (answers = every valid form),
  2 rewrite (transform a sentence using the target structure; answers = model rewrites),
  1 produce (write an original sentence/short answer using the structure)."""


def writing_task_prompt(topic: Topic, level: str) -> str:
    return f"""Create one writing assignment.
{topic_line(topic, "Task type / topic")}
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


def section_formulas(section: dict) -> str:
    """A section's structures as one line. Older lessons keep `formulas` rows or a single `formula` string."""
    rows = [
        {**r, "label_vi": f"{b.get('title', '')} {r.get('label_vi', '')}".strip()}
        for b in section.get("blocks", [])
        if b.get("kind") == "forms"
        for r in b.get("rows", [])
    ] or section.get("formulas")
    if rows is None:
        return section.get("formula", "")
    return "; ".join(f"{r.get('label_vi', '')}: {r.get('pattern', '')}" for r in rows)


def new_exercises_prompt(*, skill: str, level: str, title: str, content: dict, past_questions: list[str]) -> str:
    if skill == "vocabulary":
        words = content.get("words", [])
        lines = [f"- {w['word']} ({w.get('part_of_speech', '')}): {w.get('meaning_vi', '')}" for w in words]
        target = "Target words (practise ONLY these):\n" + "\n".join(lines)
    else:
        target = "Grammar point and its sections:\n" + "\n".join(
            f"- {s.get('heading', '')}: {section_formulas(s)}" for s in content.get("sections", [])
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


def word_info_prompt(word: str, context: str) -> str:
    ctx = f"\nThe learner met it in this context: {context}\nGive the meaning used in that context." if context else ""
    return f"""Write a learner-dictionary entry for the English word or phrase: {word}{ctx}
If the word is misspelled, correct it. Keep the example short (under 15 words) and natural."""


# ---------- sentence translation practice (Vietnamese -> English) ----------
SENTENCE_LENGTH = {
    "A1": "5-8 English words, present simple / can / like, the most common words",
    "A2": "7-12 English words, present / past simple, going to, present continuous",
    "B1": "10-16 English words; present perfect, past continuous, comparatives, first conditional, modals",
    "B2": "12-20 English words; passive, relative clauses, second / third conditional, reported speech",
    "C1": "15-25 English words; nuanced structures (inversion, mixed conditionals, cleft sentences), idiomatic usage",
}


def _sentence_focus(focus: dict) -> str:
    lines = []
    if focus.get("topic"):
        lines.append(focus["topic"])
    if words := focus.get("words"):
        listed = "\n".join(f"- {w['word']}: {w.get('meaning_vi', '')}" for w in words)
        lines.append(f"Target words (use each at least once across the set; 1-2 per sentence):\n{listed}")
    if grammar := focus.get("grammar"):
        lines.append("Grammar to practise (spread across the set):\n" + "\n".join(f"- {g}" for g in grammar))
    return "\n".join(lines)


def sentence_set_prompt(*, level: str, focus: dict, count: int) -> str:
    return f"""Create {count} sentences for translation practice: the learner reads a Vietnamese sentence and writes
it in English. The goal is grammar reflexes and using vocabulary in real sentences.
Learner level: {_level(level)}
{_sentence_focus(focus)}

Requirements:
- English length and grammar: {SENTENCE_LENGTH[level]}.
- The Vietnamese must sound natural (as a Vietnamese person would say it, not translated English), be about
  real adult life (work, family, plans, opinions, daily routine) and be unambiguous: show the time / tense with
  words like "hôm qua", "đã", "đang", "sẽ", "từ năm 2020" so only one English tense fits.
- Each sentence practises its target_words and one grammar_point; order from easier to harder; no two sentences
  with the same structure in a row.
- answers: 2-3 different correct, natural English versions (contractions or a synonym count as different).
- hint_vi gives the frame or tense (e.g. "S + have/has + V3 ... since ..."), never the whole answer;
  hint_words are 2-4 helpful English words."""


def sentence_grading_prompt(*, level: str, item: dict, answer: str) -> str:
    return f"""Grade the learner's English translation of a Vietnamese sentence.
Learner level: {_level(level)}
Vietnamese: {item["vi"]}
Target words to use: {", ".join(item.get("target_words", [])) or "(none)"}
Grammar point: {item.get("grammar_point", "")}
Reference answers (any other correct, natural wording is equally correct): {" | ".join(item.get("answers", []))}
Learner's English: {answer}

Rules:
- Judge meaning and grammar, not closeness to the references. A different but correct wording is "correct".
- Capitalisation and the final full stop never matter. A small spelling slip or a missing article is "almost".
- If the sentence is right but a target word is missing or misused, verdict is "almost" and say which word.
- corrected keeps the learner's own wording and applies EVERY fix listed in errors (nothing else); natural is
  how a native speaker would say it at this level.
- Explanations in Vietnamese, short, comparing with Vietnamese when it helps (e.g. "tiếng Anh bắt buộc chia
  động từ: he go → he goes")."""

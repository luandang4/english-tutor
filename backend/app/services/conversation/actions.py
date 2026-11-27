"""Quick-help buttons and app events turned into short instructions for Emma.

The browser only sends an action name; the instruction text is fixed here (whitelist), so client text is never
forwarded to the model as an instruction.
"""

from app.services.conversation.tutor import HINT_TOOL, TRANSLATE_TOOL

VARY_WORDING = (
    "Never reuse the wording of an earlier check-in in this lesson: each one must sound different "
    "(e.g. not 'Are you still there?' twice)."
)

ACTION_INSTRUCTIONS: dict[str, str] = {
    "hint": (
        "(App signal: the learner pressed the Hint button — they do not know how to answer your last question. "
        f"Use the help ladder: call {HINT_TOOL} for your last question now, then by voice reassure them, give a "
        "short example answer of your own and a sentence frame, and encourage them to try. Stay on this question.)"
    ),
    "auto_hint": (
        f"(App signal: the learner has been silent for a while after your question. First call {HINT_TOOL} for "
        "your question, without speaking. Then speak ONCE: a gentle check-in in your own words and your question "
        f"made easier (a choice between two answers). {VARY_WORDING} Do not ask a new question.)"
    ),
    "check_in": (
        "(App signal: the learner has still not answered. Check in warmly in your own words, then ask your last "
        "question again in shorter, simpler words. If you had not asked a question, ask one easy question about "
        f"the topic. {VARY_WORDING} Keep it to 2 short sentences.)"
    ),
    "silent_end": (
        "(App signal: the learner has not answered after several check-ins, and the app will end this lesson "
        "when you finish speaking. In 1-2 short sentences say kindly that you will stop here since they seem busy, "
        "that they can come back any time, and goodbye. Do not ask anything.)"
    ),
    "translate": (
        "(App signal: the learner pressed 'I don't understand'. Call "
        f"{TRANSLATE_TOOL} with what you last said and its Vietnamese translation, then say it again in simpler "
        "English, check they follow, and wait for their answer to that same message.)"
    ),
    "repeat": (
        "(App signal: the learner pressed Repeat. Say your last message again with exactly the same content, "
        "clearly. Do not add anything new.)"
    ),
    "slower": (
        "(App signal: the learner pressed Slow down. From now on speak more slowly, use shorter sentences and "
        "pause between them. Briefly acknowledge it, then say your last question again slowly.)"
    ),
}

WRAP_UP_INSTRUCTION = (
    "(App signal: about 2 minutes are left in this lesson. Finish the current exchange, then wrap up: tell the "
    "learner 2 things to remember from today (a correction or a useful phrase), and say goodbye warmly. Do not "
    "start a new topic.)"
)

WRAP_UP_BEFORE_END_S = 120  # tell Emma to wrap up this long before the session limit
MIN_ACTION_GAP_S = 2.0  # ignore button presses closer together than this


def action_instruction(action: object) -> str | None:
    """Fixed instruction for a whitelisted action name, or None for anything else."""
    return ACTION_INSTRUCTIONS.get(action) if isinstance(action, str) else None


def wrap_up_delay(max_seconds: int) -> float | None:
    """Seconds after the start at which Emma should wrap up, or None if the session is too short for it."""
    delay = max_seconds - WRAP_UP_BEFORE_END_S
    return delay if delay >= 30 else None

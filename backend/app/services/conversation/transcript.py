"""Conversation transcript: merges streamed fragments into turns and stores Emma's on-screen cards.

Saved turn shapes (ConversationSession.transcript, JSON):
  {"role": "user" | "tutor", "text", "pronunciation"?}
  {"role": "translation", "text": vietnamese, "source": english}
  {"role": "feedback", "text": better, "kind": "correction" | "upgrade", "original", "better", "explain_vi"}
  {"role": "hint", "text": question_en, "question_en", "question_vi"?, "frames": [..], "keywords": [{en, vi?}]}
"""

from typing import Any

from app.services.conversation.tools import Feedback, Hint, ToolCard, Translation

CARD_ROLES = ("translation", "feedback", "hint")


class Transcript:
    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []

    def add(self, role: str, text: str) -> None:
        if self.turns and self.turns[-1]["role"] == role and not self.turns[-1].get("closed"):
            self.turns[-1]["text"] += text
        else:
            self.turns.append({"role": role, "text": text})

    def add_translation(self, english: str, vietnamese: str) -> None:
        self.close_turn()
        self.turns.append({"role": "translation", "text": vietnamese, "source": english, "closed": True})

    def add_feedback(self, f: Feedback) -> None:
        """Feedback belongs under the learner's sentence, even if Emma already started answering."""
        card = {"role": "feedback", "text": f.better, "closed": True, **_fields(f)}
        self.turns.insert(self._after_last_user(), card)

    def add_hint(self, h: Hint) -> None:
        self.close_turn()
        self.turns.append({"role": "hint", "text": h.question_en or "Gợi ý", "closed": True, **h.fields()})

    def add_card(self, card: ToolCard) -> None:
        if isinstance(card, Translation):
            self.add_translation(card.english, card.vietnamese)
        elif isinstance(card, Feedback):
            self.add_feedback(card)
        else:
            self.add_hint(card)

    def close_turn(self) -> None:
        if self.turns:
            self.turns[-1]["closed"] = True

    def last_user_index(self) -> int:
        return next((i for i in range(len(self.turns) - 1, -1, -1) if self.turns[i]["role"] == "user"), -1)

    def attach_pronunciation(self, index: int, data: dict[str, Any]) -> None:
        if 0 <= index < len(self.turns):
            self.turns[index]["pronunciation"] = data

    def export(self) -> list[dict[str, Any]]:
        out = []
        for t in self.turns:
            if text := t["text"].strip():
                turn = {k: v for k, v in t.items() if k not in ("closed", "text") and v not in (None, "")}
                out.append({"role": t["role"], "text": text, **turn})
        return out

    def _after_last_user(self) -> int:
        """Insert position right after the last learner turn and any feedback cards already under it."""
        i = self.last_user_index()
        if i < 0:
            return len(self.turns)
        i += 1
        while i < len(self.turns) and self.turns[i]["role"] == "feedback":
            i += 1
        return i


def _fields(f: Feedback) -> dict[str, str]:
    return {"kind": f.kind, "original": f.original, "better": f.better, "explain_vi": f.explain_vi}

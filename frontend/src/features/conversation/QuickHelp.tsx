import type { LiveAction } from '../../lib/audio/live-session'

const BUTTONS: { action: LiveAction; emoji: string; label: string; title: string }[] = [
  { action: 'hint', emoji: '💡', label: 'Gợi ý', title: 'Gợi ý cách trả lời câu hỏi của Emma' },
  { action: 'translate', emoji: '🇻🇳', label: 'Không hiểu', title: 'Dịch câu vừa rồi và nói lại đơn giản hơn' },
  { action: 'repeat', emoji: '🔁', label: 'Nhắc lại', title: 'Emma nói lại câu vừa rồi' },
  { action: 'slower', emoji: '🐢', label: 'Chậm lại', title: 'Emma nói chậm và ngắn hơn' },
]

/** One-tap signals to Emma, so the learner does not need to know how to ask in English. */
export function QuickHelp({ onAction, disabled }: { onAction: (a: LiveAction) => void; disabled?: boolean }) {
  return (
    <div className="quick-help" role="group" aria-label="Trợ giúp nhanh">
      {BUTTONS.map((b) => (
        <button key={b.action} type="button" title={b.title} disabled={disabled} onClick={() => onAction(b.action)}>
          <span aria-hidden="true">{b.emoji}</span>
          <span>{b.label}</span>
        </button>
      ))}
    </div>
  )
}

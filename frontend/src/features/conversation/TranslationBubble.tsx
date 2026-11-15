/** Vietnamese translation Emma puts on screen when the learner says they did not understand her. */
export function TranslationBubble({ vietnamese, english }: { vietnamese: string; english?: string }) {
  return (
    <div className="note translation">
      <span className="note-label">🇻🇳 Dịch nghĩa</span>
      {english && <span className="note-source">“{english}”</span>}
      <p>{vietnamese}</p>
    </div>
  )
}

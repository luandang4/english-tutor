/** Vietnamese translation Emma puts on screen when the learner says they did not understand her. */
export function TranslationBubble({ vietnamese, english }: { vietnamese: string; english?: string }) {
  return (
    <div className="msg translation">
      <span className="who">🇻🇳 Dịch nghĩa</span>
      {english && <span className="source">“{english}”</span>}
      {vietnamese}
    </div>
  )
}

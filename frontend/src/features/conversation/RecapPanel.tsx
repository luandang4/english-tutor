import { useState, type ReactNode } from 'react'

import { useAddCard, useConversationRecap } from '../../api/hooks'
import type { ConversationRecap } from '../../api/types'
import { ErrorBox, Icon, SpeakButton, Spinner } from '../../components/ui'
import { scoreTone } from '../../lib/format'

/** "Buổi học hôm nay": loads (or creates) the recap of a finished session. */
export function RecapPanel({ sessionId }: { sessionId: number }) {
  const { data, error, isPending, refetch } = useConversationRecap(sessionId)
  if (isPending)
    return (
      <div className="recap recap-loading">
        <Spinner small /> Emma đang tổng kết buổi học…
      </div>
    )
  if (error) return <ErrorBox error={error} onRetry={() => refetch()} />
  return <RecapView recap={data} />
}

export function RecapView({ recap }: { recap: ConversationRecap }) {
  return (
    <section className="recap" aria-label="Tổng kết buổi học">
      <h3>📋 Buổi học hôm nay</h3>
      <div className="recap-stats">
        <span>
          <b>{recap.learner_turns}</b> lượt nói
        </span>
        <span>
          <b>{recap.learner_words}</b> từ đã nói
        </span>
        {recap.pronunciation_avg != null && (
          <span className={`tone-${scoreTone(recap.pronunciation_avg)}`}>
            <b>{recap.pronunciation_avg}</b> điểm phát âm
          </span>
        )}
      </div>

      {recap.goal_vi && (
        <p className="recap-goal">
          🎯 <b>Mục tiêu:</b> {recap.goal_vi}
          {recap.goal_comment_vi && <span className="muted"> — {recap.goal_comment_vi}</span>}
        </p>
      )}

      {recap.strengths_vi.length > 0 && (
        <RecapBlock title="👍 Bạn đã làm tốt">
          <ul>
            {recap.strengths_vi.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </RecapBlock>
      )}

      {recap.mistakes.length > 0 && (
        <RecapBlock title="✏️ Lỗi cần nhớ">
          {recap.mistakes.map((m, i) => (
            <div className="recap-mistake" key={i}>
              <span className="badge">{m.category}</span>
              <span className="wrong">✗ {m.wrong}</span>
              <span className="right">
                ✓ {m.right} <SpeakButton text={m.right} label="Nghe câu đúng" />
              </span>
              {m.explain_vi && <span className="small muted">{m.explain_vi}</span>}
            </div>
          ))}
        </RecapBlock>
      )}

      {recap.upgrades.length > 0 && (
        <RecapBlock title="✨ Câu đã nói hay hơn">
          {recap.upgrades.map((u, i) => (
            <div className="recap-mistake" key={i}>
              <span className="muted">{u.original}</span>
              <span className="right">
                → {u.better} <SpeakButton text={u.better} label="Nghe" />
              </span>
            </div>
          ))}
        </RecapBlock>
      )}

      {recap.new_words.length > 0 && (
        <RecapBlock title="📚 Từ và cụm từ mới">
          <div className="recap-words">
            {recap.new_words.map((w) => (
              <RecapWord key={w.word} word={w} />
            ))}
          </div>
        </RecapBlock>
      )}

      {recap.weak_words.length > 0 && (
        <RecapBlock title="🔊 Từ cần luyện phát âm">
          <div className="recap-chips">
            {recap.weak_words.map((w) => (
              <span className="chip" key={w.word}>
                {w.word} <span className="small tone-low">{w.score}</span> <SpeakButton text={w.word} />
              </span>
            ))}
          </div>
        </RecapBlock>
      )}

      {recap.goals_vi.length > 0 && (
        <RecapBlock title="🚀 Buổi sau">
          <ul>
            {recap.goals_vi.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
          <p className="small muted">Emma sẽ nhớ các lỗi và mục tiêu này cho buổi sau.</p>
        </RecapBlock>
      )}
    </section>
  )
}

function RecapBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="recap-block">
      <h4>{title}</h4>
      {children}
    </div>
  )
}

function RecapWord({ word }: { word: ConversationRecap['new_words'][number] }) {
  const add = useAddCard()
  const [added, setAdded] = useState(false)
  return (
    <div className="recap-word">
      <div className="spacer">
        <b>{word.word}</b> <span className="small muted">{word.part_of_speech}</span>
        <div className="small">{word.meaning_vi}</div>
      </div>
      <SpeakButton text={word.word} />
      <button
        type="button"
        className="btn sm ghost"
        disabled={added || add.isPending}
        onClick={() =>
          add.mutate(
            {
              word: word.word,
              meaning_vi: word.meaning_vi,
              part_of_speech: word.part_of_speech,
              example_en: word.example_en,
              source: 'conversation',
            },
            { onSuccess: () => setAdded(true) },
          )
        }
      >
        <Icon name={added ? 'check' : 'plus'} size={14} /> {added ? 'Đã thêm' : 'Thêm vào bộ ôn'}
      </button>
      {add.error && <span className="small tone-low">{add.error.message}</span>}
    </div>
  )
}

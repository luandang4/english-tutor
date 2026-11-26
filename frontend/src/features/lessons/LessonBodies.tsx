import { Link } from 'react-router-dom'

import type { GrammarContent, VocabContent } from '../../api/types'
import { PronounceButton } from '../../components/exercises/PronounceButton'
import { Icon, SpeakButton } from '../../components/ui'
import { SectionBlocks } from './GrammarBlocks'
import { pointPalette, sectionBlocks } from './grammarModel'

export function VocabBody({ content, lessonId }: { content: VocabContent; lessonId: number }) {
  return (
    <section className="stack" style={{ gap: 16 }}>
      <h2 className="section-title">📖 Từ mới ({content.words.length})</h2>
      <div className="grid cols-2">
        {content.words.map((w) => (
          <article key={w.word} className="card word-card">
            <div className="word-head">
              <span className="word">{w.word}</span>
              <SpeakButton text={w.word} label={`Nghe “${w.word}”`} />
              <span className="ipa">{w.ipa}</span>
              <span className="pos">{w.part_of_speech}</span>
            </div>
            <div className="meaning">{w.meaning_vi}</div>
            <div className="def">{w.definition_en}</div>
            <div className="example">
              <div className="row" style={{ gap: 4 }}>
                <span className="spacer">{w.example_en}</span>
                <SpeakButton text={w.example_en} label="Nghe câu ví dụ" />
              </div>
              <div className="vi">{w.example_vi}</div>
            </div>
            {w.collocations.length > 0 && (
              <div className="chips">
                {w.collocations.map((c) => (
                  <span className="chip" key={c}>
                    {c}
                  </span>
                ))}
              </div>
            )}
            <div className="word-actions">
              <PronounceButton text={w.word} />
              <Link
                className="btn sm"
                to={`/vocabulary/lessons/${lessonId}/write?word=${encodeURIComponent(w.word)}`}
                title="Chép lại từ và nghĩa nhiều lần"
              >
                <Icon name="pen" size={16} /> Tập viết
              </Link>
            </div>
          </article>
        ))}
      </div>
      {content.tips_vi.length > 0 && (
        <div className="card">
          <div className="card-title">
            <h3>💡 Mẹo ghi nhớ</h3>
          </div>
          <ul>
            {content.tips_vi.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export function GrammarBody({ content }: { content: GrammarContent }) {
  const palette = pointPalette(content.sections)
  return (
    <section className="stack" style={{ gap: 16 }}>
      {content.sections.map((s, i) => (
        <article key={i} className="card stack">
          <h2 className="section-title">
            <span className="exercise-num">{i + 1}</span>
            {s.heading.replace(/^\s*\d+\s*[.)]\s*/, '')}
          </h2>
          <SectionBlocks blocks={sectionBlocks(s)} palette={palette} />
          <div className="stack" style={{ gap: 8 }}>
            {s.examples.map((ex, j) => (
              <div className="example" key={j}>
                <div className="row" style={{ gap: 4 }}>
                  <span className="spacer en">{ex.en}</span>
                  <SpeakButton text={ex.en} label="Nghe câu ví dụ" />
                </div>
                <div className="vi">{ex.vi}</div>
              </div>
            ))}
          </div>
        </article>
      ))}

      {content.common_mistakes.length > 0 && (
        <article className="card stack">
          <h2 className="section-title">⚠️ Lỗi người Việt hay gặp</h2>
          {content.common_mistakes.map((m, i) => (
            <div className="mistake" key={i}>
              <span className="wrong">✗ {m.wrong}</span>
              <span className="right">✓ {m.right}</span>
              <span className="why">{m.explanation_vi}</span>
            </div>
          ))}
        </article>
      )}

      {content.summary_vi.length > 0 && (
        <article className="card">
          <div className="card-title">
            <h3>📌 Ghi nhớ nhanh</h3>
          </div>
          <ul>
            {content.summary_vi.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </article>
      )}
    </section>
  )
}

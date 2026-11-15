import { Link, useParams } from 'react-router-dom'

import { useAnswerLessonQuiz, useFinishLessonQuiz, useLesson, useStartLessonQuiz } from '../../api/hooks'
import type { QuizResult } from '../../api/types'
import { ErrorBox, Icon, Loading, PageHeader, ScoreRing, Spinner } from '../../components/ui'
import { reviewDay } from '../../lib/format'
import { QuizRunner } from './QuizRunner'
import './review.css'

const MARK = { correct: '✓', near: '≈', wrong: '✗' } as const

/** "Kiểm tra lại": quiz rebuilt from the lesson's own words / exercises. Free (no AI), any time. */
export function LessonQuizPage({ skill }: { skill: 'vocabulary' | 'grammar' }) {
  const id = Number(useParams().id)
  const lesson = useLesson(id)
  const start = useStartLessonQuiz(id)
  const answer = useAnswerLessonQuiz(id)
  const finish = useFinishLessonQuiz(id)
  const back = { to: `/${skill}/lessons/${id}`, label: 'Về bài học' }
  const title = lesson.data ? `Kiểm tra lại: ${lesson.data.title}` : 'Kiểm tra lại'

  const begin = (onlyWrong: boolean) => {
    finish.reset()
    start.mutate(onlyWrong)
  }

  let body
  if (finish.data) body = <QuizResultView result={finish.data} skill={skill} onRetry={begin} backTo={back.to} />
  else if (finish.isPending) body = <Loading label="Đang tổng kết…" />
  else if (start.data)
    body = (
      <QuizRunner
        key={start.submittedAt}
        questions={start.data.questions}
        answer={(b) => answer.mutateAsync(b)}
        retryWrong={false}
        onDone={() => finish.mutate()}
      />
    )
  else
    body = (
      <div className="card stack" style={{ maxWidth: 640, width: '100%', margin: '0 auto' }}>
        <h3>{skill === 'vocabulary' ? 'Ôn lại các từ của bài' : 'Làm lại các câu của bài'}</h3>
        <p className="muted">
          {skill === 'vocabulary'
            ? 'Khoảng 10 câu: chọn nghĩa, nghe và gõ từ, nhớ từ tiếng Anh từ nghĩa tiếng Việt, điền từ vào câu ví dụ. '
            : 'Các câu trắc nghiệm và điền từ của bài, câu bạn từng làm sai được hỏi trước. '}
          Chấm ngay, không tốn lượt AI. Từ đã có trong bộ ôn tập sẽ được cập nhật lịch ôn.
        </p>
        <div>
          <button className="btn primary" onClick={() => begin(false)} disabled={start.isPending}>
            {start.isPending ? <Spinner small /> : <Icon name="play" size={16} />} Bắt đầu
          </button>
        </div>
      </div>
    )

  return (
    <div className="page">
      <PageHeader title={title} subtitle="Bấm lúc nào cũng được, kể cả khi chưa tới hạn ôn." back={back} />
      {lesson.error && <ErrorBox error={lesson.error} />}
      {start.error && <ErrorBox error={start.error} />}
      {finish.error && <ErrorBox error={finish.error} onRetry={() => finish.mutate()} />}
      {body}
    </div>
  )
}

function QuizResultView({
  result,
  skill,
  onRetry,
  backTo,
}: {
  result: QuizResult
  skill: 'vocabulary' | 'grammar'
  onRetry: (onlyWrong: boolean) => void
  backTo: string
}) {
  const missed = result.items.filter((i) => i.result !== 'correct' && i.result !== 'near')
  return (
    <div className="quiz-wrap">
      <div className="completion">
        <ScoreRing score={result.score} size={76} />
        <div className="stack" style={{ gap: 6, flex: 1 }}>
          <h3>{result.wrong === 0 ? '🎉 Làm đúng hết!' : 'Kết quả kiểm tra'}</h3>
          <p className="muted small">
            Đúng {result.correct} · gần đúng {result.near} · sai {result.wrong} / {result.total} câu
          </p>
          {skill === 'grammar' && (
            <p className="small">
              {result.next_recheck_at
                ? `Lần kiểm tra lại tiếp theo: ${reviewDay(result.next_recheck_at)} (bước ${result.recheck_step + 1}/4).`
                : result.recheck_step >= 4
                  ? 'Bạn đã hoàn thành lịch ôn 1 – 3 – 7 – 14 ngày của bài này.'
                  : ''}
            </p>
          )}
        </div>
      </div>
      <div className="row">
        {missed.length > 0 && (
          <button className="btn primary" onClick={() => onRetry(true)}>
            <Icon name="refresh" size={16} /> {skill === 'vocabulary' ? 'Ôn lại các từ sai' : 'Làm lại các câu sai'}
          </button>
        )}
        <button className="btn" onClick={() => onRetry(false)}>
          Làm lại toàn bộ
        </button>
        <Link className="btn ghost" to={backTo}>
          Về bài học
        </Link>
      </div>
      <div className="result-list">
        {result.items.map((i) => (
          <div key={i.question_id} className="result-row">
            <span className={`result-mark ${i.result ?? 'wrong'}`}>{MARK[i.result ?? 'wrong']}</span>
            <span className="label">{i.label}</span>
            {i.result !== 'correct' && <span className="expected">{i.result == null ? 'chưa làm · ' : ''}{i.expected}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

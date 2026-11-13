import { Link, useParams } from 'react-router-dom'

import { useAddToDeck, useLesson, useRegenerateExercises, useRetryLesson } from '../../api/hooks'
import type { GrammarContent, VocabContent } from '../../api/types'
import { ExerciseCard } from '../../components/exercises/ExerciseCard'
import {
  ErrorBox,
  GeneratingState,
  Icon,
  Loading,
  AudioSourceSelect,
  PageHeader,
  ProgressBar,
  ScoreRing,
  Spinner,
  StatusBadge,
} from '../../components/ui'
import { SKILL_LABEL } from '../../lib/format'
import { GrammarBody, VocabBody } from './LessonBodies'

export function LessonPage({ skill }: { skill: 'vocabulary' | 'grammar' }) {
  const id = Number(useParams().id)
  const { data: lesson, error, isPending, refetch } = useLesson(id)
  const retry = useRetryLesson(id)
  const addToDeck = useAddToDeck(id)
  const regen = useRegenerateExercises(id)
  const back = { to: `/${skill}`, label: SKILL_LABEL[skill] }

  if (isPending) return <div className="page"><Loading /></div>
  if (error || !lesson)
    return (
      <div className="page">
        <PageHeader title="Bài học" back={back} />
        <ErrorBox error={error} onRetry={() => refetch()} />
      </div>
    )

  if (lesson.status === 'generating')
    return (
      <div className="page">
        <PageHeader title={lesson.topic.title_vi} subtitle={`${lesson.topic.title} · ${lesson.level}`} back={back} />
        <GeneratingState title={`Gemini đang soạn bài “${lesson.topic.title_vi}”`} />
      </div>
    )

  if (lesson.status === 'failed' || !lesson.content)
    return (
      <div className="page">
        <PageHeader title={lesson.topic.title_vi} back={back} />
        <div className="card stack">
          <div className="alert error">{lesson.error ?? 'Không tạo được bài học.'}</div>
          <div>
            <button className="btn primary" onClick={() => retry.mutate()} disabled={retry.isPending}>
              {retry.isPending ? <Spinner small /> : <Icon name="refresh" />} Tạo lại
            </button>
          </div>
        </div>
      </div>
    )

  const regenerating = lesson.exercises_status === 'generating' || regen.isPending
  const newRound = () => {
    const unfinished = lesson.exercises.some((e) => !e.result)
    if (unfinished && !confirm('Bộ bài tập hiện tại chưa làm xong. Vẫn tạo bộ mới?')) return
    regen.mutate()
  }
  const answered = lesson.exercises.filter((e) => e.result).length
  const total = lesson.exercises.length
  const isVocab = lesson.skill === 'vocabulary'
  const words = isVocab ? (lesson.content as VocabContent).words.length : 0

  return (
    <div className="page">
      <Link className="back-link" to={back.to}>
        <Icon name="arrowLeft" size={16} /> {back.label}
      </Link>
      <div className="card lesson-hero">
        <div className="text">
          <div className="row">
            <span className="badge level">{lesson.level}</span>
            <StatusBadge status={lesson.status} />
            <span className="small muted">
              {lesson.topic.icon} {lesson.topic.title_vi}
            </span>
          </div>
          <h1>{lesson.title}</h1>
          <p className="intro">{lesson.content.intro_vi}</p>
          <div style={{ marginTop: 14, maxWidth: 360 }}>
            <div className="row small muted" style={{ marginBottom: 6 }}>
              <span className="spacer">Bài tập</span>
              <span>
                {answered}/{total}
              </span>
            </div>
            <ProgressBar value={total ? (answered / total) * 100 : 0} />
          </div>
        </div>
        <ScoreRing score={lesson.score} size={88} label="Điểm bài học" />
      </div>

      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <AudioSourceSelect />
      </div>

      {isVocab ? <VocabBody content={lesson.content as VocabContent} /> : <GrammarBody content={lesson.content as GrammarContent} />}

      <section className="stack" style={{ gap: 14 }} id="exercises">
        <div className="row">
          <h2 className="section-title spacer">
            ✍️ Bài tập {regenerating ? '' : `(${total})`}
            {lesson.exercise_round > 1 && <span className="badge level">Vòng {lesson.exercise_round}</span>}
          </h2>
          <button className="btn sm" onClick={newRound} disabled={regenerating}>
            {regenerating ? <Spinner small /> : <Icon name="refresh" size={16} />} Tạo bài tập mới
          </button>
        </div>
        {regen.error && <ErrorBox error={regen.error} />}
        {lesson.exercises_status === 'failed' && (
          <ErrorBox error={lesson.exercises_error ?? 'Không tạo được bài tập mới.'} onRetry={() => regen.mutate()} />
        )}
        {regenerating ? (
          <GeneratingState title="Gemini đang soạn bộ bài tập mới (không trùng câu cũ)" />
        ) : (
          lesson.exercises.map((ex, i) => (
            <ExerciseCard key={`${lesson.id}-${ex.id}`} lessonId={lesson.id} exercise={ex} index={i} />
          ))
        )}
      </section>

      {lesson.status === 'completed' && !regenerating && (
        <div className="completion">
          <ScoreRing score={lesson.score} size={76} />
          <div className="stack" style={{ gap: 6, flex: 1 }}>
            <h3>🎉 Hoàn thành bài học!</h3>
            <p className="muted">
              Điểm được tính theo lần làm tốt nhất của mỗi câu. Bạn có thể làm lại câu sai, hoặc tạo bộ bài tập mới
              để luyện thêm.
            </p>
            <div className="row">
              <button
                className="btn sm primary"
                onClick={() => {
                  regen.mutate()
                  document.getElementById('exercises')?.scrollIntoView({ behavior: 'smooth' })
                }}
              >
                <Icon name="sparkle" size={16} /> Luyện thêm bộ bài tập mới
              </button>
            </div>
            {isVocab && (
              <div className="row">
                {lesson.in_deck >= words ? (
                  <>
                    <span className="small tone-good">✓ {lesson.in_deck} từ đã có trong bộ ôn tập</span>
                    <Link className="btn sm primary" to="/review">
                      <Icon name="cards" size={16} /> Ôn tập ngay
                    </Link>
                  </>
                ) : (
                  <button className="btn sm primary" onClick={() => addToDeck.mutate()} disabled={addToDeck.isPending}>
                    <Icon name="plus" size={16} /> Thêm từ vào bộ ôn tập
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      {isVocab && lesson.status === 'ready' && lesson.in_deck < words && (
        <div className="row">
          <button className="btn sm ghost" onClick={() => addToDeck.mutate()} disabled={addToDeck.isPending}>
            <Icon name="plus" size={16} /> Thêm {words} từ vào bộ ôn tập ngay
          </button>
          <span className="small muted">(tự động thêm khi bạn hoàn thành bài)</span>
        </div>
      )}
    </div>
  )
}

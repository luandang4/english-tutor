import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { useCards, useLesson } from '../../api/hooks'
import type { VocabContent } from '../../api/types'
import { AudioSourceSelect, EmptyState, ErrorBox, Loading, PageHeader } from '../../components/ui'
import type { DrillWord } from './model'
import { WriteDrill } from './WriteDrill'

const SUBTITLE = 'Chép lại từ và nghĩa nhiều lần cho thuộc cách viết. Không giới hạn số lần, không tốn lượt AI.'

/** Index of the word named in ?word=, or 0. */
function startIndex(words: DrillWord[], word: string | null): number {
  if (!word) return 0
  const i = words.findIndex((w) => w.word.toLowerCase() === word.toLowerCase())
  return i < 0 ? 0 : i
}

/** /vocabulary/lessons/:id/write: the words of one vocabulary lesson. */
export function LessonDrillPage() {
  const id = Number(useParams().id)
  const [params] = useSearchParams()
  const { data: lesson, error, isPending, refetch } = useLesson(id)
  const back = { to: `/vocabulary/lessons/${id}`, label: 'Bài học' }

  if (isPending) return <div className="page"><Loading /></div>
  if (error || !lesson)
    return (
      <div className="page">
        <PageHeader title="Tập viết" back={back} />
        <ErrorBox error={error} onRetry={() => refetch()} />
      </div>
    )
  const words = lesson.skill === 'vocabulary' && lesson.content ? (lesson.content as VocabContent).words : []
  return (
    <div className="page">
      <PageHeader title={`Tập viết · ${lesson.title}`} subtitle={SUBTITLE} back={back} actions={<AudioSourceSelect />} />
      {words.length ? (
        <WriteDrill key={lesson.id} words={words} startIndex={startIndex(words, params.get('word'))} />
      ) : (
        <EmptyState emoji="✍️" title="Bài này chưa có từ để tập viết" text="Bài học cần soạn xong trước." />
      )}
    </div>
  )
}

/** /review/write: words of the review deck (the ones filtered in the deck list, or all of them). */
export function DeckDrillPage() {
  const cards = useCards(false)
  const location = useLocation()
  const [params] = useSearchParams()
  const ids = (location.state as { ids?: number[] } | null)?.ids
  const back = { to: '/review', label: 'Ôn tập từ' }

  if (cards.isPending) return <div className="page"><Loading /></div>
  if (cards.error)
    return (
      <div className="page">
        <PageHeader title="Tập viết" back={back} />
        <ErrorBox error={cards.error} onRetry={() => cards.refetch()} />
      </div>
    )
  const picked = ids?.length ? cards.data.filter((c) => ids.includes(c.id)) : cards.data
  return (
    <div className="page">
      <PageHeader title={`Tập viết · ${picked.length} từ trong bộ ôn`} subtitle={SUBTITLE} back={back} actions={<AudioSourceSelect />} />
      {picked.length ? (
        <WriteDrill words={picked} startIndex={startIndex(picked, params.get('word'))} />
      ) : (
        <EmptyState
          emoji="🗂️"
          title="Bộ từ đang trống"
          text="Hoàn thành một bài từ vựng hoặc thêm từ vào bộ ôn trước."
          action={
            <Link className="btn primary" to="/vocabulary">
              Học từ vựng
            </Link>
          }
        />
      )}
    </div>
  )
}

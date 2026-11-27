import { useNavigate } from 'react-router-dom'

import { useCreateSentenceSet } from '../../../api/hooks'
import type { Level } from '../../../api/types'
import { Icon, Spinner } from '../../../components/ui'
import { useAccess } from '../../../lib/access'

/** Lesson page shortcut: 10 Vietnamese sentences built on this lesson's words / grammar, to write in English. */
export function PracticeSentencesButton({ lessonId, level }: { lessonId: number; level: Level }) {
  const { can } = useAccess()
  const create = useCreateSentenceSet()
  const navigate = useNavigate()
  if (!can('writing')) return null
  return (
    <button
      className="btn sm"
      disabled={create.isPending}
      title={create.error ? String(create.error) : 'AI ra 10 câu tiếng Việt dùng nội dung bài này, bạn viết lại bằng tiếng Anh'}
      onClick={() =>
        create.mutate(
          { source: 'lesson', lesson_id: lessonId, level },
          { onSuccess: (row) => navigate(`/writing/sentences/${row.id}`) },
        )
      }
    >
      {create.isPending ? <Spinner small /> : <Icon name="pen" size={16} />} Luyện viết câu
    </button>
  )
}

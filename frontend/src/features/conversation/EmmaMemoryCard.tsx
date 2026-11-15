import { useClearLearnerMemory, useLearnerMemory } from '../../api/hooks'
import { ErrorBox, Spinner } from '../../components/ui'

/** Account page: what Emma remembers between sessions (mistakes and goals only), with a reset button. */
export function EmmaMemoryCard() {
  const { data, error, isPending } = useLearnerMemory()
  const clear = useClearLearnerMemory()
  const empty = !data || (!data.mistakes.length && !data.goals.length)
  return (
    <div className="card stack">
      <div className="card-title" style={{ marginBottom: 0 }}>
        <h3>Emma ghi nhớ</h3>
      </div>
      <p className="small muted">
        Sau mỗi buổi hội thoại, Emma ghi lại lỗi bạn hay mắc và mục tiêu cho buổi sau để chú ý sửa đúng chỗ. Emma
        cũng lồng các từ đang đến hạn ôn vào câu hỏi. Không lưu thông tin cá nhân.
      </p>
      {isPending ? (
        <Spinner small />
      ) : error ? (
        <ErrorBox error={error} />
      ) : empty ? (
        <p className="small muted">Chưa có gì. Hãy nói chuyện với Emma và xem tổng kết cuối buổi.</p>
      ) : (
        <>
          {data.mistakes.length > 0 && (
            <ul className="small">
              {data.mistakes.map((m) => (
                <li key={m.category}>
                  <b>{m.category}</b> ({m.count} lần) — <s>{m.wrong}</s> → {m.right}
                </li>
              ))}
            </ul>
          )}
          {data.goals.length > 0 && <p className="small">🎯 Mục tiêu: {data.goals.join(' · ')}</p>}
          <div>
            <button
              type="button"
              className="btn sm ghost danger"
              disabled={clear.isPending}
              onClick={() => confirm('Xoá toàn bộ ghi nhớ của Emma về bạn?') && clear.mutate()}
            >
              Xoá ghi nhớ
            </button>
          </div>
        </>
      )}
    </div>
  )
}

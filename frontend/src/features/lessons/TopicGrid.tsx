import type { Topic } from '../../api/types'
import { Icon } from '../../components/ui'

export function TopicGrid(props: { topics: Topic[]; busyId?: number | null; onPick: (t: Topic) => void }) {
  return (
    <div className="grid auto">
      {props.topics.map((t) => (
        <button
          key={t.id}
          type="button"
          className="topic-card"
          disabled={props.busyId != null}
          onClick={() => props.onPick(t)}
        >
          <span className="icon" aria-hidden="true">
            {t.icon}
          </span>
          <h3>{t.title_vi}</h3>
          <span className="en-title">{t.title}</span>
          <p>{t.description_vi}</p>
          <span className="go">{props.busyId === t.id ? <span className="spinner sm" /> : <Icon name="sparkle" />}</span>
        </button>
      ))}
    </div>
  )
}

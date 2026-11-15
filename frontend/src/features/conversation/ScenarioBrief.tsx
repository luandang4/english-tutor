import type { Level, ScenarioOption } from '../../api/types'
import { SpeakButton } from '../../components/ui'

const BASIC_LEVELS: Level[] = ['A1', 'A2']
const VIETNAMESE_LEVELS: Level[] = ['A1', 'A2', 'B1'] // same rule as the hint card: B2+ is English only

const phrasesFor = (s: ScenarioOption, level: Level) =>
  BASIC_LEVELS.includes(level) ? s.phrases_basic : s.phrases_advanced

/** Useful phrases for the scenario at this level; tap to hear. */
export function PhraseList({ scenario, level }: { scenario: ScenarioOption; level: Level }) {
  const vietnamese = VIETNAMESE_LEVELS.includes(level)
  return (
    <ul className="phrase-list">
      {phrasesFor(scenario, level).map((p) => (
        <li key={p.en}>
          <SpeakButton text={p.en} label={`Nghe “${p.en}”`} />
          <span>
            <b>{p.en}</b>
            {vietnamese && <small className="muted">{p.vi}</small>}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Goal, roles and phrases shown before the session starts. */
export function ScenarioBrief({ scenario, level }: { scenario: ScenarioOption; level: Level }) {
  return (
    <div className="brief">
      <p className="brief-goal">
        <span aria-hidden="true">🎯</span> {scenario.goal_vi}
      </p>
      <p className="small muted">
        Emma: {scenario.emma_role_vi} · Bạn: {scenario.learner_role_vi}
      </p>
      <details className="brief-phrases">
        <summary>Cụm từ nên dùng ({phrasesFor(scenario, level).length})</summary>
        <PhraseList scenario={scenario} level={level} />
      </details>
    </div>
  )
}

/** In-session sheet with the scenario's phrases ("Cụm từ" button). */
export function PhraseSheet(props: { scenario: ScenarioOption; level: Level; onClose: () => void }) {
  return (
    <div className="phrase-sheet" role="dialog" aria-label="Cụm từ hữu ích">
      <div className="phrase-sheet-head">
        <b>Cụm từ hữu ích</b>
        <button type="button" className="btn sm ghost" onClick={props.onClose}>
          Đóng
        </button>
      </div>
      <p className="small muted">{props.scenario.goal_vi}</p>
      <PhraseList scenario={props.scenario} level={props.level} />
    </div>
  )
}

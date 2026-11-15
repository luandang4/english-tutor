import type { ConversationTurn } from '../../api/types'
import { FeedbackCard, type SaveFeedback } from './FeedbackCard'
import { HintCard } from './HintCard'
import { TranslationBubble } from './TranslationBubble'
import { TurnPronunciationView } from './TurnPronunciationView'
import { TutorLine } from './TutorLine'
import type { AddWord } from './WordPopover'

/** Hook points the parent may wire up (e.g. to the vocabulary deck); buttons are hidden when undefined. */
export interface TurnActions {
  onSaveFeedback?: SaveFeedback
  onAddWord?: AddWord
}

/** One transcript turn: a spoken line (learner / Emma) or one of Emma's on-screen cards. */
export function TurnView(props: { turn: ConversationTurn; done?: boolean; className?: string } & TurnActions) {
  const { turn, done = true, className = '', onSaveFeedback, onAddWord } = props
  switch (turn.role) {
    case 'translation':
      return <TranslationBubble vietnamese={turn.text} english={turn.source} />
    case 'feedback':
      return <FeedbackCard card={turn} onSave={onSaveFeedback} />
    case 'hint':
      return <HintCard card={turn} />
    case 'tutor':
      return (
        <div className={`msg tutor ${className}`}>
          <span className="who">Emma</span>
          <TutorLine text={turn.text} done={done} onAddWord={onAddWord} />
        </div>
      )
    default:
      return (
        <div className={`msg user ${className}`}>
          <span className="who">Bạn</span>
          {turn.text}
          {turn.pronunciation && <TurnPronunciationView result={turn.pronunciation} />}
        </div>
      )
  }
}

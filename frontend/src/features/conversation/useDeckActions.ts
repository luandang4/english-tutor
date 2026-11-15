import { useAddCard } from '../../api/hooks'
import type { FeedbackTurn } from '../../api/types'
import type { LookedUpWord } from './WordPopover'

function report(e: unknown) {
  alert(e instanceof Error ? e.message : 'Không thêm được vào bộ ôn tập.')
}

/** Wires Emma's cards and word lookups to the review deck (no AI call: the meaning is already known). */
export function useDeckActions() {
  const add = useAddCard()
  return {
    onSaveFeedback: (card: FeedbackTurn) =>
      void add
        .mutateAsync({
          word: card.better.slice(0, 120),
          meaning_vi: card.explain_vi || (card.kind === 'correction' ? 'Câu đúng' : 'Cách nói hay hơn'),
          definition_en: card.original ? `Instead of: ${card.original}`.slice(0, 500) : '',
          example_en: card.better.slice(0, 500),
          source: 'conversation',
        })
        .catch(report),
    onAddWord: (w: LookedUpWord) =>
      void add
        .mutateAsync({
          word: w.word,
          meaning_vi: w.meaning_vi,
          ipa: w.ipa,
          part_of_speech: w.part_of_speech,
          context: w.context,
          example_en: w.context.slice(0, 500),
          source: 'conversation',
        })
        .catch(report),
  }
}

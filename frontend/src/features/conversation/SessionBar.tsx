import { Icon } from '../../components/ui'
import type { OrbMode } from '../../orb/orb'
import { Countdown } from './Countdown'
import { FONT_LABEL, FONT_SIZES, type ConvoLayout, type FontSize } from './preferences'

const STATUS_TEXT: Record<OrbMode, string> = {
  idle: 'Đã kết thúc',
  connecting: 'Đang kết nối…',
  listening: 'Đang nghe',
  tutor: 'Đang nói',
  user: 'Đang nghe bạn',
}

/** Slim top bar of a running session: who is talking, time left, phrases, text size and layout switches. */
export function SessionBar(props: {
  mode: OrbMode
  endsAt: number | null
  layout: ConvoLayout
  onLayout: (l: ConvoLayout) => void
  fontSize: FontSize
  onFontSize: (f: FontSize) => void
  onPhrases?: () => void
}) {
  const { mode, endsAt, layout, fontSize } = props
  const nextFont = FONT_SIZES[(FONT_SIZES.indexOf(fontSize) + 1) % FONT_SIZES.length]
  return (
    <header className="convo-bar">
      <span className="bar-orb-slot" aria-hidden="true" />
      <div className="bar-who">
        <b>Emma</b>
        <span className="live-status" data-state={mode}>
          <span className="dot" />
          <span className="status-text">{STATUS_TEXT[mode]}</span>
        </span>
      </div>
      <div className="bar-tools">
        {endsAt !== null && <Countdown endsAt={endsAt} />}
        {props.onPhrases && (
          <button type="button" className="btn sm ghost bar-btn" onClick={props.onPhrases} title="Cụm từ hữu ích">
            <Icon name="list" size={16} />
            <span className="bar-btn-label">Cụm từ</span>
          </button>
        )}
        <button
          type="button"
          className="btn sm ghost bar-btn"
          onClick={() => props.onFontSize(nextFont)}
          title={`${FONT_LABEL[fontSize]} (bấm để đổi)`}
          aria-label={`Cỡ chữ: ${FONT_LABEL[fontSize]}`}
        >
          <span className={`font-glyph font-glyph-${fontSize}`}>Aa</span>
        </button>
        <button
          type="button"
          className="btn sm ghost bar-btn"
          onClick={() => props.onLayout(layout === 'overlay' ? 'corner' : 'overlay')}
          title={layout === 'overlay' ? 'Thu quả cầu lên góc' : 'Đặt quả cầu sau lời thoại'}
          aria-label="Đổi bố cục"
        >
          <Icon name="orb" size={16} />
        </button>
      </div>
    </header>
  )
}

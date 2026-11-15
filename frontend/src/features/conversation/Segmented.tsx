/** Small single-choice button group (radio semantics). */
export function Segmented<T extends string>(props: {
  label: string
  value: T
  options: { value: T; label: string; title?: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="field">
      <span>{props.label}</span>
      <div className="segmented" role="radiogroup" aria-label={props.label}>
        {props.options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={props.value === o.value}
            title={o.title}
            className={props.value === o.value ? 'on' : ''}
            onClick={() => props.onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

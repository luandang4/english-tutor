import type { Level, Meta, ScenarioOption } from '../../api/types'
import { ScenarioBrief } from './ScenarioBrief'
import { Segmented } from '../../components/ui/Segmented'
import { CUSTOM, ENHANCEMENT_OPTIONS, type ConvoPreferences } from './preferences'

/** Preset scenarios grouped by `group`, keeping the server's order. */
function groupScenarios(scenarios: ScenarioOption[]): [string, ScenarioOption[]][] {
  const groups = new Map<string, ScenarioOption[]>()
  for (const s of scenarios) groups.set(s.group, [...(groups.get(s.group) ?? []), s])
  return [...groups]
}

/** Settings chosen before a session: level, scenario (with its goal and phrases), upgrade frequency. */
export function SetupPanel(props: {
  meta: Meta | undefined
  level: Level
  setLevel: (l: Level) => void
  prefs: ConvoPreferences
}) {
  const { meta, level, setLevel, prefs } = props
  const isCustom = prefs.scenario === CUSTOM
  const preset = meta?.scenarios.find((s) => s.value === prefs.scenario)
  return (
    <div className="setup">
      <label className="field">
        Trình độ
        <select className="select" value={level} onChange={(e) => setLevel(e.target.value as Level)}>
          {meta?.levels.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Tình huống
        <select className="select" value={prefs.scenario} onChange={(e) => prefs.setScenario(e.target.value)}>
          {groupScenarios(meta?.scenarios ?? []).map(([group, items]) => (
            <optgroup key={group} label={group}>
              {items.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </optgroup>
          ))}
          <option value={CUSTOM}>✨ Tình huống của bạn…</option>
        </select>
      </label>

      {isCustom ? (
        <div className="custom-scenario">
          <label className="field">
            Chủ đề / tình huống
            <input
              className="input"
              value={prefs.customTitle}
              onChange={(e) => prefs.setCustomTitle(e.target.value)}
              maxLength={120}
              placeholder="VD: Phỏng vấn xin việc vị trí kế toán"
            />
          </label>
          <label className="field">
            Yêu cầu thêm (tuỳ chọn)
            <textarea
              className="textarea"
              rows={2}
              value={prefs.customRequest}
              onChange={(e) => prefs.setCustomRequest(e.target.value)}
              maxLength={1000}
              placeholder="VD: Emma đóng vai nhà tuyển dụng khó tính, hỏi về kinh nghiệm làm việc với Excel"
            />
          </label>
        </div>
      ) : (
        preset && <ScenarioBrief scenario={preset} level={level} />
      )}

      <Segmented
        label="Emma hướng dẫn trả lời hay hơn"
        value={prefs.enhancement}
        options={ENHANCEMENT_OPTIONS}
        onChange={prefs.setEnhancement}
      />

      <label className="toggle">
        <input type="checkbox" checked={prefs.headphones} onChange={(e) => prefs.setHeadphones(e.target.checked)} />
        <span className="switch" aria-hidden="true" />
        <span>
          Đeo tai nghe{' '}
          <small>Bật nếu đang đeo tai nghe để có thể ngắt lời Emma. Tắt thì mic tự tạm ngắt khi Emma nói.</small>
        </span>
      </label>
    </div>
  )
}

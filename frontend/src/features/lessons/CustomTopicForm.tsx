import { useState } from 'react'

import type { CustomTopic, Skill } from '../../api/types'
import { Icon, Spinner } from '../../components/ui'

const HINTS: Record<Skill, { title: string; request: string }> = {
  vocabulary: {
    title: 'VD: Phỏng vấn xin việc ngành logistics',
    request: 'VD: tập trung từ về kho bãi, vận chuyển quốc tế; ví dụ trong email công việc',
  },
  grammar: {
    title: 'VD: Câu bị động trong báo cáo công việc',
    request: 'VD: so sánh với chủ động, ví dụ về dự án phần mềm',
  },
  writing: {
    title: 'VD: Email xin nghỉ phép',
    request: 'VD: gửi cho quản lý người Nhật, giọng lịch sự, nêu lý do và người bàn giao việc',
  },
}

/** Learner's own topic + optional wishes; the AI builds the lesson / task from it. */
export function CustomTopicForm(props: { skill: Skill; busy: boolean; onSubmit: (topic: CustomTopic) => void }) {
  const [title, setTitle] = useState('')
  const [request, setRequest] = useState('')
  const hint = HINTS[props.skill]
  return (
    <form
      className="card custom-topic"
      onSubmit={(e) => {
        e.preventDefault()
        props.onSubmit({ title: title.trim(), request: request.trim() })
      }}
    >
      <div className="custom-topic-head">
        <span className="icon" aria-hidden="true">
          ✨
        </span>
        <div>
          <h3>Chủ đề của bạn</h3>
          <p className="small muted">Không thấy chủ đề phù hợp? Nhập chủ đề và yêu cầu riêng, AI sẽ soạn theo đó.</p>
        </div>
      </div>
      <label className="field">
        Chủ đề
        <input
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          minLength={2}
          maxLength={120}
          placeholder={hint.title}
        />
      </label>
      <label className="field">
        Yêu cầu thêm (tuỳ chọn)
        <textarea
          className="textarea"
          rows={2}
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          maxLength={1000}
          placeholder={hint.request}
        />
      </label>
      <div>
        <button className="btn primary" type="submit" disabled={props.busy || title.trim().length < 2}>
          {props.busy ? <Spinner small /> : <Icon name="sparkle" size={16} />} Tạo bài với chủ đề này
        </button>
      </div>
    </form>
  )
}

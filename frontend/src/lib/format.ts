import type { Criterion, ExerciseType, LessonStatus, Skill } from '../api/types'

export const SKILL_LABEL: Record<Skill, string> = {
  vocabulary: 'Từ vựng',
  grammar: 'Ngữ pháp',
  writing: 'Viết',
}

export const STATUS_LABEL: Record<LessonStatus, string> = {
  generating: 'Đang tạo…',
  ready: 'Đang học',
  completed: 'Hoàn thành',
  failed: 'Lỗi',
}

export const EXERCISE_LABEL: Record<ExerciseType, string> = {
  multiple_choice: 'Trắc nghiệm',
  fill_blank: 'Điền từ',
  rewrite: 'Viết lại câu',
  produce: 'Tự đặt câu',
}

export const CRITERION_LABEL: Record<Criterion, string> = {
  task_achievement: 'Hoàn thành yêu cầu',
  coherence_cohesion: 'Mạch lạc & liên kết',
  lexical_resource: 'Từ vựng',
  grammar_accuracy: 'Ngữ pháp',
}

export const CORRECTION_LABEL: Record<string, string> = {
  grammar: 'Ngữ pháp',
  vocabulary: 'Từ vựng',
  spelling: 'Chính tả',
  punctuation: 'Dấu câu',
  word_choice: 'Dùng từ',
  style: 'Văn phong',
  coherence: 'Mạch lạc',
}

const rtf = new Intl.RelativeTimeFormat('vi', { numeric: 'auto' })

export function timeAgo(iso: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(diff)
  if (abs < 60) return 'vừa xong'
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour')
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), 'day')
  return new Date(iso).toLocaleDateString('vi-VN')
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m ? `${m} phút ${s ? `${s} giây` : ''}`.trim() : `${s} giây`
}

export function scoreTone(score: number | null | undefined): 'good' | 'ok' | 'low' | 'none' {
  if (score == null) return 'none'
  if (score >= 80) return 'good'
  if (score >= 55) return 'ok'
  return 'low'
}

export function countWords(text: string): number {
  return (text.match(/[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*/g) ?? []).length
}

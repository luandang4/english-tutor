// DTOs mirroring backend/app/schemas/api.py and schemas/ai.py.

export type Skill = 'vocabulary' | 'grammar' | 'writing'
export type LessonStatus = 'generating' | 'ready' | 'completed' | 'failed'
export type SubmissionStatus = 'grading' | 'graded' | 'failed'
export type ExerciseType = 'multiple_choice' | 'fill_blank' | 'rewrite' | 'produce'
export type Level = 'A1' | 'A2' | 'B1' | 'B2' | 'C1'

export type Feature = 'conversation' | 'vocabulary' | 'grammar' | 'writing' | 'pronunciation'

export interface User {
  id: number
  email: string
  display_name: string
  created_at: string
  is_admin: boolean
  /** Features usable right now (admin grants + system switches). The server enforces the same rules. */
  features: Feature[]
  /** Not approved for anything yet: waiting for an admin. */
  pending: boolean
}

export interface FeatureInfo {
  value: Feature
  label: string
  unit: string
}

export interface FeatureUsage extends FeatureInfo {
  feature: Feature
  used: number
  limit: number | null
}

// ---------- admin ----------
export interface SystemSettings {
  features_enabled: Record<Feature, boolean>
  registration_open: boolean
  default_features: Feature[]
  daily_limits: Record<Feature, number>
}

export interface AdminUser {
  id: number
  email: string
  display_name: string
  created_at: string
  last_login_at: string | null
  is_admin: boolean
  is_active: boolean
  features: Feature[]
  usage_today: Partial<Record<Feature, number>>
}

export type AdminUserPatch = Partial<Pick<AdminUser, 'is_active' | 'is_admin' | 'features'>>

export interface Option {
  value: string
  label: string
}

export interface Meta {
  levels: Option[]
  scenarios: Option[]
  features: FeatureInfo[]
  pronunciation_enabled: boolean
  registration_open: boolean
}

export interface Topic {
  id: number
  slug: string
  skill: Skill
  title: string
  title_vi: string
  description_vi: string
  icon: string
  is_custom: boolean
}

/** Learner-defined topic (instead of a preset one). */
export interface CustomTopic {
  title: string
  request: string
}

export type TopicChoice = { topic_id: number; custom?: never } | { custom: CustomTopic; topic_id?: never }

// ---------- lessons ----------
export interface LessonSummary {
  id: number
  skill: Skill
  level: Level
  status: LessonStatus
  title: string
  score: number | null
  created_at: string
  completed_at: string | null
  topic: Topic
  exercise_count: number
  answered_count: number
}

export interface ExerciseResult {
  answer: string
  is_correct: boolean
  score: number
  feedback_vi: string
  corrected_answer: string
  answers: string[]
  explanation_vi: string
  attempts: number
}

export interface Exercise {
  id: string
  type: ExerciseType
  instruction_vi: string
  question: string
  options: string[]
  result: ExerciseResult | null
}

export interface VocabWord {
  word: string
  ipa: string
  part_of_speech: string
  meaning_vi: string
  definition_en: string
  example_en: string
  example_vi: string
  collocations: string[]
}

export interface VocabContent {
  title: string
  intro_vi: string
  words: VocabWord[]
  tips_vi: string[]
}

export interface GrammarSection {
  heading: string
  explanation_vi: string
  formula: string
  examples: { en: string; vi: string }[]
}

export interface GrammarContent {
  title: string
  intro_vi: string
  sections: GrammarSection[]
  common_mistakes: { wrong: string; right: string; explanation_vi: string }[]
  summary_vi: string[]
}

export interface LessonDetail extends LessonSummary {
  error: string | null
  content: VocabContent | GrammarContent | null
  exercises: Exercise[]
  in_deck: number
  exercise_round: number
  exercises_status: 'generating' | 'failed' | null
  exercises_error: string | null
}

export interface AttemptOut {
  exercise: Exercise
  lesson_status: LessonStatus
  lesson_score: number | null
  cards_added: number
}

// ---------- vocabulary deck ----------
export interface Card {
  id: number
  word: string
  ipa: string
  part_of_speech: string
  meaning_vi: string
  definition_en: string
  example_en: string
  example_vi: string
  due_at: string
  reps: number
  lapses: number
  last_reviewed_at: string | null
  intervals: Record<'1' | '2' | '3' | '4', string>
}

export interface DeckStats {
  total: number
  due: number
  new: number
  learning: number
  mature: number
  reviewed_today: number
}

// ---------- writing ----------
export interface WritingPrompt {
  title: string
  task_type: string
  prompt_en: string
  prompt_vi: string
  requirements: string[]
  min_words: number
  max_words: number
  useful_phrases: { phrase: string; meaning_vi: string }[]
  outline_vi: string[]
}

export type Criterion = 'task_achievement' | 'coherence_cohesion' | 'lexical_resource' | 'grammar_accuracy'

export interface WritingCorrection {
  original: string
  corrected: string
  category: string
  explanation_vi: string
}

export interface WritingFeedback {
  overall_score: number
  cefr_estimate: string
  summary_vi: string
  criteria: { criterion: Criterion; score: number; comment_vi: string }[]
  strengths_vi: string[]
  improvements_vi: string[]
  corrections: WritingCorrection[]
  improved_version: string
}

export interface Submission {
  id: number
  task_id: number
  text: string
  word_count: number
  status: SubmissionStatus
  overall_score: number | null
  result: WritingFeedback | null
  error: string | null
  created_at: string
}

export interface WritingTaskSummary {
  id: number
  level: Level
  status: LessonStatus
  title: string
  created_at: string
  topic: Topic
  best_score: number | null
  submission_count: number
}

export interface WritingTaskDetail extends WritingTaskSummary {
  prompt: WritingPrompt | null
  error: string | null
  submissions: Submission[]
}

// ---------- pronunciation ----------
export type PronunciationEngine = 'azure' | 'local'
export interface PronunciationResult {
  id: number
  reference_text: string
  recognized_text: string
  pron_score: number
  accuracy: number
  fluency: number | null
  completeness: number
  prosody: number | null
  /** azure = Azure Speech; local = free on-server phoneme model (an estimate). */
  engine: PronunciationEngine
  words: { word: string; score: number; error_type: string; phonemes: { phoneme: string; score: number }[] }[]
}

// ---------- conversations ----------
export interface ConversationSummary {
  id: number
  level: Level
  scenario: string
  /** Learner's own scenario title when scenario === 'custom'. */
  topic: string | null
  voice: string
  created_at: string
  ended_at: string | null
  duration_seconds: number
  turns: number
}

/** Azure pronunciation result for one spoken learner turn in a conversation. */
export interface TurnPronunciation {
  text: string
  score: number
  accuracy: number
  fluency: number | null
  prosody: number | null
  weak_words: { word: string; score: number; error_type: string }[]
  engine?: PronunciationEngine
}

export interface ConversationTurn {
  role: 'user' | 'tutor'
  text: string
  pronunciation?: TurnPronunciation
}

export interface ConversationDetail extends ConversationSummary {
  transcript: ConversationTurn[]
}

// ---------- progress ----------
export interface Progress {
  streak_days: number
  active_days_30: number
  skills: { skill: Skill; completed: number; in_progress: number; average_score: number | null }[]
  deck: DeckStats
  writing_average: number | null
  conversation_minutes: number
  conversation_count: number
  pronunciation_average: number | null
  activity: { date: string; count: number }[]
  recent: { kind: string; title: string; score: number | null; at: string; link: string }[]
}

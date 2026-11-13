import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api } from './client'
import type {
  AttemptOut,
  Card,
  ConversationDetail,
  ConversationSummary,
  DeckStats,
  LessonDetail,
  LessonSummary,
  Level,
  Meta,
  Progress,
  PronunciationResult,
  Skill,
  Submission,
  Topic,
  TopicChoice,
  User,
  WritingTaskDetail,
  WritingTaskSummary,
} from './types'

const POLL_MS = 2000

export const keys = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  topics: (skill: Skill) => ['topics', skill] as const,
  lessons: (skill: Skill) => ['lessons', skill] as const,
  lesson: (id: number) => ['lesson', id] as const,
  deckStats: ['deck', 'stats'] as const,
  cards: (due: boolean) => ['deck', 'cards', due] as const,
  writingTasks: ['writing', 'tasks'] as const,
  writingTask: (id: number) => ['writing', 'task', id] as const,
  conversations: ['conversations'] as const,
  conversation: (id: number) => ['conversation', id] as const,
  progress: ['progress'] as const,
}

// ---------- auth ----------
/** Current user, or null when signed out (401 is an expected answer here, not an error). */
export const useMe = () =>
  useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api.get<User>('/auth/me')
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: Infinity,
    retry: false,
  })

function useSignedIn() {
  const qc = useQueryClient()
  return (user: User) => {
    qc.clear() // never show the previous account's cached data
    qc.setQueryData(keys.me, user)
  }
}

export function useLogin() {
  const signedIn = useSignedIn()
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => api.post<User>('/auth/login', body),
    onSuccess: signedIn,
  })
}

export function useRegister() {
  const signedIn = useSignedIn()
  return useMutation({
    mutationFn: (body: { email: string; password: string; display_name: string }) =>
      api.post<User>('/auth/register', body),
    onSuccess: signedIn,
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    onSettled: () => {
      qc.clear()
      qc.setQueryData(keys.me, null)
    },
  })
}

export const useChangePassword = () =>
  useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) => api.post<void>('/auth/password', body),
  })

// ---------- catalog ----------
export const useMeta = () =>
  useQuery({ queryKey: keys.meta, queryFn: () => api.get<Meta>('/meta'), staleTime: Infinity })

export const useTopics = (skill: Skill) =>
  useQuery({
    queryKey: keys.topics(skill),
    queryFn: () => api.get<Topic[]>(`/topics?skill=${skill}`),
    staleTime: 5 * 60_000,
  })

// ---------- lessons ----------
export const useLessons = (skill: Skill) =>
  useQuery({
    queryKey: keys.lessons(skill),
    queryFn: () => api.get<LessonSummary[]>(`/lessons?skill=${skill}`),
    refetchInterval: (q) => (q.state.data?.some((l) => l.status === 'generating') ? POLL_MS : false),
  })

export const useLesson = (id: number) =>
  useQuery({
    queryKey: keys.lesson(id),
    queryFn: () => api.get<LessonDetail>(`/lessons/${id}`),
    refetchInterval: (q) =>
      q.state.data?.status === 'generating' || q.state.data?.exercises_status === 'generating' ? POLL_MS : false,
  })

export function useRegenerateExercises(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<LessonDetail>(`/lessons/${id}/exercises/regenerate`),
    onSuccess: (lesson) => {
      qc.setQueryData(keys.lesson(id), lesson)
      qc.invalidateQueries({ queryKey: keys.lessons(lesson.skill) })
    },
  })
}

export function useCreateLesson() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TopicChoice & { level: Level; skill?: 'vocabulary' | 'grammar' }) =>
      api.post<LessonDetail>('/lessons', body),
    onSuccess: (lesson) => {
      qc.setQueryData(keys.lesson(lesson.id), lesson)
      qc.invalidateQueries({ queryKey: keys.lessons(lesson.skill) })
    },
  })
}

export function useRetryLesson(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<LessonDetail>(`/lessons/${id}/retry`),
    onSuccess: (lesson) => qc.setQueryData(keys.lesson(id), lesson),
  })
}

export function useDeleteLesson(skill: Skill) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.del(`/lessons/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.lessons(skill) })
      qc.invalidateQueries({ queryKey: keys.progress })
    },
  })
}

export function useSubmitAttempt(lessonId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ exerciseId, answer }: { exerciseId: string; answer: string }) =>
      api.post<AttemptOut>(`/lessons/${lessonId}/exercises/${exerciseId}/attempts`, { answer }),
    onSuccess: (out) => {
      qc.setQueryData<LessonDetail>(keys.lesson(lessonId), (old) =>
        old && {
          ...old,
          status: out.lesson_status,
          score: out.lesson_score,
          exercises: old.exercises.map((e) => (e.id === out.exercise.id ? out.exercise : e)),
          answered_count: old.exercises.filter((e) => e.result || e.id === out.exercise.id).length,
          in_deck: old.in_deck + out.cards_added,
        },
      )
      if (out.cards_added) qc.invalidateQueries({ queryKey: ['deck'] })
      qc.invalidateQueries({ queryKey: keys.progress })
    },
  })
}

export function useAddToDeck(lessonId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ added: number; in_deck: number }>(`/lessons/${lessonId}/deck`),
    onSuccess: (out) => {
      qc.setQueryData<LessonDetail>(keys.lesson(lessonId), (old) => old && { ...old, in_deck: out.in_deck })
      qc.invalidateQueries({ queryKey: ['deck'] })
    },
  })
}

// ---------- vocabulary deck ----------
export const useDeckStats = () =>
  useQuery({ queryKey: keys.deckStats, queryFn: () => api.get<DeckStats>('/vocab/stats'), refetchInterval: 60_000 })

export const useCards = (due: boolean) =>
  useQuery({ queryKey: keys.cards(due), queryFn: () => api.get<Card[]>(`/vocab/cards?due=${due}`) })

export function useReviewCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rating }: { id: number; rating: 1 | 2 | 3 | 4 }) =>
      api.post<Card>(`/vocab/cards/${id}/review`, { rating }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.deckStats })
      qc.invalidateQueries({ queryKey: keys.cards(false) })
      qc.invalidateQueries({ queryKey: keys.progress })
    },
  })
}

export function useDeleteCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.del(`/vocab/cards/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deck'] }),
  })
}

// ---------- writing ----------
export const useWritingTasks = () =>
  useQuery({
    queryKey: keys.writingTasks,
    queryFn: () => api.get<WritingTaskSummary[]>('/writing/tasks'),
    refetchInterval: (q) => (q.state.data?.some((t) => t.status === 'generating') ? POLL_MS : false),
  })

export const useWritingTask = (id: number) =>
  useQuery({
    queryKey: keys.writingTask(id),
    queryFn: () => api.get<WritingTaskDetail>(`/writing/tasks/${id}`),
    refetchInterval: (q) =>
      q.state.data?.status === 'generating' || q.state.data?.submissions.some((s) => s.status === 'grading')
        ? POLL_MS
        : false,
  })

export function useCreateWritingTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TopicChoice & { level: Level }) => api.post<WritingTaskDetail>('/writing/tasks', body),
    onSuccess: (task) => {
      qc.setQueryData(keys.writingTask(task.id), task)
      qc.invalidateQueries({ queryKey: keys.writingTasks })
    },
  })
}

export function useRetryWritingTask(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<WritingTaskDetail>(`/writing/tasks/${id}/retry`),
    onSuccess: (task) => qc.setQueryData(keys.writingTask(id), task),
  })
}

export function useDeleteWritingTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.del(`/writing/tasks/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.writingTasks })
      qc.invalidateQueries({ queryKey: keys.progress })
    },
  })
}

export function useSubmitWriting(taskId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => api.post<Submission>(`/writing/tasks/${taskId}/submissions`, { text }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.writingTask(taskId) })
      qc.invalidateQueries({ queryKey: keys.writingTasks })
      qc.invalidateQueries({ queryKey: keys.progress })
    },
  })
}

export function useRegradeSubmission(taskId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.post<Submission>(`/writing/submissions/${id}/regrade`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.writingTask(taskId) }),
  })
}

// ---------- pronunciation ----------
export function useAssessPronunciation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ pcm, text, cardId }: { pcm: ArrayBuffer; text: string; cardId?: number }) => {
      const qs = new URLSearchParams({ reference_text: text })
      if (cardId) qs.set('card_id', String(cardId))
      return api.post<PronunciationResult>(`/pronunciation/assess?${qs}`, pcm)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.progress }),
  })
}

// ---------- conversations ----------
export const useConversations = () =>
  useQuery({ queryKey: keys.conversations, queryFn: () => api.get<ConversationSummary[]>('/conversations') })

export const useConversation = (id: number) =>
  useQuery({ queryKey: keys.conversation(id), queryFn: () => api.get<ConversationDetail>(`/conversations/${id}`) })

export function useDeleteConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.del(`/conversations/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.conversations }),
  })
}

// ---------- progress ----------
export const useProgress = () => useQuery({ queryKey: keys.progress, queryFn: () => api.get<Progress>('/progress') })

/** All-time count of correct written lines per word, kept in this browser (no server, no AI quota). */

const KEY = 'et.drill.counts'

export const wordKey = (word: string) => word.trim().toLowerCase()

export function readCounts(): Record<string, number> {
  try {
    const raw = localStorage.getItem(KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, number>) : {}
  } catch {
    return {}
  }
}

export function addCount(word: string): Record<string, number> {
  const counts = readCounts()
  const k = wordKey(word)
  counts[k] = (counts[k] ?? 0) + 1
  try {
    localStorage.setItem(KEY, JSON.stringify(counts))
  } catch {
    // storage full or blocked: the session count on screen still works
  }
  return counts
}

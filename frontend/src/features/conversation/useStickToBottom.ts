import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'

const NEAR_BOTTOM_PX = 80

/** Keep a scroll box pinned to its newest content (whenever the content grows), unless the reader scrolled up
 * to read older lines. Returns whether it is pinned and a function to jump back to the newest line.
 * `mounted`: the box is currently rendered (its first child is the growing content). */
export function useStickToBottom(ref: RefObject<HTMLElement | null>, mounted: boolean) {
  const [pinned, setPinned] = useState(true)
  const pinnedRef = useRef(true)

  const scrollToBottom = useCallback(() => {
    const el = ref.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    pinnedRef.current = true
    setPinned(true)
  }, [ref])

  useEffect(() => {
    const el = ref.current
    const content = el?.firstElementChild
    if (!el || !content) return
    // Content can grow between our own scroll and its (async) scroll event, so only an upward scroll unpins.
    let lastTop = el.scrollTop
    const onScroll = () => {
      const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
      const next = near || (pinnedRef.current && el.scrollTop >= lastTop)
      lastTop = el.scrollTop
      pinnedRef.current = next
      setPinned(next)
    }
    const follow = new ResizeObserver(() => {
      if (pinnedRef.current) el.scrollTop = el.scrollHeight
    })
    follow.observe(content)
    follow.observe(el)
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      follow.disconnect()
      el.removeEventListener('scroll', onScroll)
    }
  }, [ref, mounted])

  return { pinned, scrollToBottom }
}

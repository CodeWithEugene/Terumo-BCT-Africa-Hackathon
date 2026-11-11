import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { t } from '../i18n/en'
import { Button } from './States'

const KEY = 'sp:tour-step'

type Point = { x: number; y: number }
// Where the presenter dragged the card. Kept for the page view, so it survives the change of role.
let dragged: Point | null = null

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), Math.max(low, high))

/** The places the card may rest, for a card of this size. The first is the usual one. */
function corners(w: number, h: number): Point[] {
  const wide = window.innerWidth >= 768
  const left = wide ? 220 : 12 // clear of the side rail
  const right = window.innerWidth - w - (wide ? 20 : 12)
  const top = 72 // clear of the top band
  const bottom = window.innerHeight - h - (wide ? 20 : 76) // clear of the bottom bar on phones
  const all: Point[] = [
    { x: right, y: bottom }, { x: right, y: top }, { x: left, y: bottom }, { x: left, y: top },
  ]
  // On a wide screen the card may also sit over the side menu, which the tour does not need.
  if (wide) all.push({ x: 12, y: bottom }, { x: 12, y: top })
  return all
}

/**
 * Which resting place to use for a step. The card stays where it is unless it
 * would cover the part being shown; then it goes to the place that covers least.
 */
function chooseCorner(now: number, box: DOMRect, w: number, h: number): number {
  const all = corners(w, h)
  const covered = (c: Point) =>
    Math.max(0, Math.min(c.x + w, box.right) - Math.max(c.x, box.left)) *
    Math.max(0, Math.min(c.y + h, box.bottom) - Math.max(c.y, box.top))
  const current = all[now] ?? all[0]
  if (covered(current) <= 0.04 * w * h) return all[now] ? now : 0
  let best = 0
  all.forEach((c, i) => {
    if (covered(c) < covered(all[best])) best = i
  })
  return best
}

export function readTourStep(): number | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw === null ? null : Number(raw)
  } catch {
    return null
  }
}

export function writeTourStep(step: number | null): void {
  try {
    if (step === null) sessionStorage.removeItem(KEY)
    else sessionStorage.setItem(KEY, String(step))
  } catch {
    /* the tour still works for this page view */
  }
}

/**
 * The guided tour. A small card walks through the main features, moving the app
 * to each screen and outlining the part it is talking about. It never blocks
 * the app: every control still works, so a presenter can stop and click.
 * The step changes instantly (keyboard-driven changes should not animate);
 * only the card's first appearance fades in.
 */
export function Tour({
  step,
  username,
  onStep,
  onNeedUser,
}: {
  step: number
  username: string
  onStep: (step: number | null) => void
  onNeedUser: (username: string) => Promise<boolean>
}) {
  const steps = t.tour.steps
  const current = steps[Math.min(step, steps.length - 1)]
  const [box, setBox] = useState<DOMRect | null>(null)
  const [switching, setSwitching] = useState(false)
  const target = useRef<Element | null>(null)
  const card = useRef<HTMLElement | null>(null)
  const [size, setSize] = useState({ w: 320, h: 190 })
  const [manual, setManual] = useState<Point | null>(dragged)
  // The resting place is chosen once per step, after the screen has stopped moving.
  const [corner, setCorner] = useState(0)
  // A change of resting place glides from the old spot to the new one.
  const lastRect = useRef<DOMRect | null>(null)
  useLayoutEffect(() => {
    const el = card.current
    if (!el) return
    const now = el.getBoundingClientRect()
    const before = lastRect.current
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (before && !still && (before.left !== now.left || before.top !== now.top)) {
      el.animate(
        [{ transform: `translate(${before.left - now.left}px, ${before.top - now.top}px)` }, { transform: 'none' }],
        { duration: 220, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' },
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corner])
  useLayoutEffect(() => {
    lastRect.current = card.current?.getBoundingClientRect() ?? null
  })
  const sizeNow = useRef(size)
  sizeNow.current = size
  const [dragging, setDragging] = useState(false)
  const grip = useRef<{ dx: number; dy: number } | null>(null)

  // Follow the card's size, so it stays on screen when the presenter resizes it.
  useEffect(() => {
    const el = card.current
    if (!el) return
    const read = () => setSize({ w: el.offsetWidth, h: el.offsetHeight })
    read()
    const observer = new ResizeObserver(read)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const moveTo = (point: Point | null) => {
    dragged = point
    setManual(point)
  }

  const measure = useCallback(() => {
    setBox(target.current && document.contains(target.current) ? target.current.getBoundingClientRect() : null)
  }, [])

  // Go to the step's screen (signing in as the right role first), then find and show its target.
  useEffect(() => {
    let live = true
    let timer: number | undefined
    let watcher: ResizeObserver | undefined
    let settling: number | undefined
    target.current = null
    setBox(null)
    const run = async () => {
      if (current.user !== username) {
        setSwitching(true)
        const ok = await onNeedUser(current.user)
        if (!live) return
        setSwitching(false)
        if (!ok) return onStep(null)
        return // the user change re-runs this effect
      }
      if (window.location.hash !== current.route) window.location.hash = current.route
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      let tries = 0
      const find = () => {
        if (!live) return
        const found = Array.from(document.querySelectorAll(`[data-tour="${current.target}"]`)).find(
          (el) => (el as HTMLElement).offsetParent !== null,
        )
        if (found) {
          target.current = found
          // A part that fits on screen is centred. A taller one is shown from its top, under the top band.
          const show = () => {
            if (!live || !document.contains(found)) return
            const fits = found.getBoundingClientRect().height <= window.innerHeight - 160
            found.scrollIntoView({ block: fits ? 'center' : 'start', behavior: reduce ? 'auto' : 'smooth' })
          }
          const settle = () => {
            if (!live || !document.contains(found)) return
            const { w, h } = sizeNow.current
            setCorner((now) => chooseCorner(now, found.getBoundingClientRect(), w, h))
          }
          const showThenSettle = () => {
            show()
            window.clearTimeout(settling)
            settling = window.setTimeout(settle, reduce ? 80 : 650) // after the scroll has finished
          }
          showThenSettle()
          // Again whenever the part changes size, for example when its numbers finish loading.
          watcher?.disconnect()
          watcher = new ResizeObserver(() => {
            window.clearTimeout(timer)
            timer = window.setTimeout(showThenSettle, 150)
          })
          watcher.observe(found)
          measure()
        } else if (tries++ < 40) {
          timer = window.setTimeout(find, 150)
        }
      }
      timer = window.setTimeout(find, 120)
    }
    void run()
    return () => {
      live = false
      watcher?.disconnect()
      window.clearTimeout(settling)
      if (timer) window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, username])

  // Keep the outline on its target while the page scrolls or resizes.
  useEffect(() => {
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(measure)
    }
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    const interval = window.setInterval(measure, 400)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
      window.clearInterval(interval)
    }
  }, [measure])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const el = event.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return
      if (event.key === 'ArrowRight') onStep(step + 1 < steps.length ? step + 1 : null)
      if (event.key === 'ArrowLeft' && step > 0) onStep(step - 1)
      if (event.key === 'Escape') onStep(null)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [step, steps.length, onStep])

  const last = step >= steps.length - 1
  // A resting place is pinned by its top or bottom edge, so longer or shorter text never shifts that edge.
  const wide = window.innerWidth >= 768
  const resting = corners(size.w, size.h)
  const rest = resting[corner] ?? resting[0]
  const low = rest.y > window.innerHeight / 3
  const place: { left: number; top?: number; bottom?: number } = manual
    ? {
        left: clamp(manual.x, 8, window.innerWidth - size.w - 8),
        top: clamp(manual.y, 8, window.innerHeight - size.h - 8),
      }
    : { left: clamp(rest.x, 8, window.innerWidth - size.w - 8), ...(low ? { bottom: wide ? 20 : 76 } : { top: 72 }) }
  return (
    <>
      {box && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed z-40 rounded-[12px] ring-2 ring-sky-strong ring-offset-2 ring-offset-white/0"
          style={{ left: box.left - 6, top: box.top - 6, width: box.width + 12, height: box.height + 12 }}
        />
      )}
      <section
        ref={card}
        aria-label={t.tour.startShort}
        aria-live="polite"
        data-tour-card
        className={`tour-card fixed z-50 w-[20rem] max-w-[calc(100vw-1rem)] min-w-[15rem] min-h-[9rem] max-h-[80vh] resize overflow-auto rounded-card border border-ink/35 bg-white/70 p-3.5 shadow-[0_8px_30px_rgba(20,27,77,0.16)] backdrop-blur-md backdrop-saturate-150`}
        style={place}
        onPointerDownCapture={(event) => {
          // Taking hold of the resize corner pins the card where it is, so it grows from that corner.
          const rect = event.currentTarget.getBoundingClientRect()
          if (!manual && event.clientX > rect.right - 24 && event.clientY > rect.bottom - 24) moveTo({ x: rect.left, y: rect.top })
        }}
      >
        <p
          className={`-mx-1.5 -mt-1 flex touch-none items-center justify-between gap-3 rounded-md px-1.5 py-1 text-[0.6875rem] font-medium tracking-[0.08em] text-ink uppercase select-none ${dragging ? 'cursor-grabbing' : 'cursor-grab'}`}
          title={t.tour.move}
          onPointerDown={(event) => {
            const rect = card.current!.getBoundingClientRect()
            grip.current = { dx: event.clientX - rect.left, dy: event.clientY - rect.top }
            event.currentTarget.setPointerCapture(event.pointerId)
            setDragging(true)
          }}
          onPointerMove={(event) => {
            if (grip.current) moveTo({ x: event.clientX - grip.current.dx, y: event.clientY - grip.current.dy })
          }}
          onPointerUp={() => {
            grip.current = null
            setDragging(false)
          }}
          onPointerCancel={() => {
            grip.current = null
            setDragging(false)
          }}
          onDoubleClick={() => moveTo(null)}
        >
          <span className="flex items-center gap-1.5">
            <svg width="8" height="12" viewBox="0 0 8 12" aria-hidden="true" className="text-muted">
              {[1, 5, 9].map((y) => [1, 5].map((x) => <rect key={`${x}-${y}`} x={x} y={y} width="2" height="2" rx="1" fill="currentColor" />))}
            </svg>
            {t.tour.startShort} · {t.tour.of(step + 1, steps.length)}
          </span>
          <span className="h-1 w-16 overflow-hidden rounded-full bg-ink/15" aria-hidden="true">
            <span className="block h-full bg-ink" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
          </span>
        </p>
        <h2 className="mt-1.5 text-base leading-snug">{switching ? t.tour.switching : current.title}</h2>
        {!switching && <p className="mt-1 text-[0.8125rem] leading-relaxed text-ink">{current.text}</p>}
        <div className="mt-3 flex items-center gap-2">
          <Button icon={last ? 'check' : 'arrow'} onClick={() => onStep(last ? null : step + 1)} disabled={switching}>
            {last ? t.tour.finish : t.tour.next}
          </Button>
          {step > 0 && (
            <Button variant="outline" onClick={() => onStep(step - 1)} disabled={switching}>
              {t.tour.back}
            </Button>
          )}
          <Button variant="text" className="ml-auto" onClick={() => onStep(null)}>
            {t.tour.end}
          </Button>
        </div>
        <p className="mt-1.5 hidden text-[0.6875rem] text-ink/70 md:block">{t.tour.keys}</p>
      </section>
    </>
  )
}

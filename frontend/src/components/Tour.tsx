import { useCallback, useEffect, useRef, useState } from 'react'
import { t } from '../i18n/en'
import { Button } from './States'

const KEY = 'sp:tour-step'

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

  const measure = useCallback(() => {
    setBox(target.current && document.contains(target.current) ? target.current.getBoundingClientRect() : null)
  }, [])

  // Go to the step's screen (signing in as the right role first), then find and show its target.
  useEffect(() => {
    let live = true
    let timer: number | undefined
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
          found.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' })
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
        aria-label={t.tour.startShort}
        aria-live="polite"
        className="tour-card fixed inset-x-3 bottom-[4.5rem] z-50 mx-auto max-w-[30rem] rounded-card border border-ink bg-white p-4 shadow-[0_8px_30px_rgba(20,27,77,0.18)] sm:p-5 md:bottom-5 md:left-auto md:right-5 md:mx-0"
      >
        <p className="flex items-center justify-between gap-3 text-xs font-medium tracking-[0.08em] text-muted uppercase">
          <span>
            {t.tour.startShort} · {t.tour.of(step + 1, steps.length)}
          </span>
          <span className="h-1 w-24 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <span className="block h-full bg-ink" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
          </span>
        </p>
        <h2 className="mt-2 text-lg leading-snug">{switching ? t.tour.switching : current.title}</h2>
        {!switching && <p className="mt-1.5 text-sm leading-relaxed">{current.text}</p>}
        <div className="mt-4 flex items-center gap-2">
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
        <p className="mt-2 hidden text-[0.75rem] text-muted md:block">{t.tour.keys}</p>
      </section>
    </>
  )
}

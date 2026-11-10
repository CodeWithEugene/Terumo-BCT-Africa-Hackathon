import { motion, useReducedMotion } from 'framer-motion'
import type { Status } from '../types'

const fill: Record<Status, string> = {
  act: 'var(--color-fill-act)',
  watch: 'var(--color-fill-watch)',
  steady: 'var(--color-fill-steady)',
  not_held: 'var(--color-line)',
}

const SCALE_DAYS = 14

/**
 * The cover bar, drawn as a slim tube. The fill is days of cover on a 14-day
 * scale. The solid part is what holds even in a busy spell; the striped part
 * is the expected case. The tick marks the next delivery: a fill that stops
 * short of the tick is a shortage you can see without a legend.
 */
export function CoverTube({
  cover,
  worst,
  capped,
  deliveryDay,
  status,
  label,
}: {
  cover: number | null
  worst?: number | null
  capped?: boolean
  deliveryDay?: number | null
  status: Status
  label: string
}) {
  const reduce = useReducedMotion()
  const expected = Math.min(1, (capped ? SCALE_DAYS : (cover ?? 0)) / SCALE_DAYS)
  const sure = Math.min(expected, (worst ?? cover ?? 0) / SCALE_DAYS)
  const tick = deliveryDay == null ? null : Math.min(1, deliveryDay / SCALE_DAYS)
  return (
    <div className="relative pt-2 pb-1" role="img" aria-label={label}>
      <div className="relative h-3 overflow-hidden rounded-full border border-edge bg-white">
        {/* expected cover: striped, so it reads as "likely" without relying on a paler colour */}
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: `repeating-linear-gradient(135deg, ${fill[status]} 0 3px, transparent 3px 6px)` }}
          initial={{ width: reduce ? `${expected * 100}%` : 0 }}
          animate={{ width: `${expected * 100}%` }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        />
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: fill[status] }}
          initial={{ width: reduce ? `${sure * 100}%` : 0 }}
          animate={{ width: `${sure * 100}%` }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        />
        {/* a thin glass highlight along the top of the tube */}
        <div className="pointer-events-none absolute inset-x-1 top-[2px] h-px rounded-full bg-white/70" />
      </div>
      {tick !== null && (
        <div
          className="absolute top-0 bottom-0 w-px -translate-x-1/2 bg-ink"
          style={{ left: `clamp(1px, ${tick * 100}%, calc(100% - 1px))` }}
          aria-hidden="true"
        >
          <span className="absolute -top-px left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-ink" />
        </div>
      )}
    </div>
  )
}

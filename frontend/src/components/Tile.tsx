import { motion, useReducedMotion } from 'framer-motion'
import { t } from '../i18n/en'
import { coverText, cx } from '../lib/format'
import { href } from '../lib/route'
import type { Series } from '../types'
import { CoverTube } from './CoverTube'
import { Icon } from './Icon'
import { StatusBadge } from './StatusBadge'

const surface: Record<string, string> = {
  act: 'bg-act-soft border-[#f0cdc9]',
  watch: 'bg-watch-soft border-[#f1dfb4]',
  steady: 'bg-surface border-line',
  not_held: 'bg-surface border-line',
}

/** One blood group: symbol, days of cover (the main number), the cover tube, units, status. */
export function Tile({ series, index, selected }: { series: Series; index: number; selected?: boolean }) {
  const reduce = useReducedMotion()
  const { cover_days: cover, cover_capped: capped, worst_cover_days: worst } = series
  const empty = cover !== null && cover <= 0 && !capped
  const noUse = cover === null

  let big = coverText(cover, capped)
  let unit = cover !== null && !capped && Number(big) === 1 ? t.tile.dayOfCover : t.tile.daysOfCover
  let hint: string | null = null
  if (empty) {
    big = t.tile.empty
    unit = ''
    hint = t.tile.emptyHint
  } else if (noUse) {
    big = t.tile.noUse
    unit = ''
    hint = t.tile.noUseHint
  } else if (worst != null && cover !== null && !capped && cover - worst >= 0.500) {
    hint = t.tile.couldBe(coverText(worst))
  }
  const delivery = series.next_delivery
  const barLabel = t.tile.coverBar(
    empty ? t.tile.empty : noUse ? t.tile.noUse : `${big} ${unit}`.trim(),
    delivery ? t.tile.deliveryTick(delivery.label) : t.brief.noDelivery,
  )

  return (
    <motion.a
      href={href({ page: 'group', id: series.id })}
      aria-label={`${t.tile.open(series.blood_group_words)}. ${series.status_label}. ${series.status_line}`}
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.180, ease: 'easeOut', delay: reduce ? 0 : Math.min(index, 8) * 0.030 }}
      className={cx(
        'group flex min-h-[11.500rem] flex-col rounded-card border p-4 no-underline transition-colors duration-150 sm:p-5',
        surface[series.status],
        'hover:border-ink/40 focus-visible:border-ink',
        selected && 'border-ink ring-1 ring-ink',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[1.750rem] leading-none font-semibold tracking-[-0.010em] text-ink">
          {series.blood_group_label}
        </span>
        <StatusBadge status={series.status} />
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <span
          className={cx(
            'leading-[1.150] font-medium tracking-[-0.010em] text-ink',
            empty ? 'text-[2rem]' : noUse ? 'text-[1.375rem] leading-[2.9rem]' : 'text-[2.500rem]',
          )}
        >
          {big}
        </span>
        <span className="text-sm text-body">{unit}</span>
      </div>
      <p className="min-h-5 text-[0.8125rem] text-muted">{hint}</p>

      <CoverTube
        cover={cover}
        worst={worst}
        capped={capped}
        deliveryDay={delivery?.days_away}
        status={series.status}
        label={barLabel}
      />

      <div className="mt-auto flex items-end justify-between gap-2 pt-2 text-[0.8125rem] text-body">
        <span>{t.tile.onShelf(series.units_on_shelf)}</span>
        {delivery && (
          <span className="inline-flex items-center gap-1 text-muted">
            <Icon name="delivery" size={14} />
            {delivery.label}
          </span>
        )}
      </div>
      {series.decision && (
        <p className="mt-2 flex items-center gap-1.5 border-t border-ink/10 pt-2 text-[0.8125rem] font-medium text-ink">
          <Icon name="check" size={14} />
          {series.decision.summary}
        </p>
      )}
    </motion.a>
  )
}

export function TileSkeleton() {
  return (
    <div className="flex min-h-[11.500rem] animate-pulse flex-col rounded-card border border-line p-5" aria-hidden="true">
      <div className="flex justify-between">
        <div className="h-7 w-12 rounded bg-bg-alt" />
        <div className="h-5 w-16 rounded bg-bg-alt" />
      </div>
      <div className="mt-5 h-10 w-28 rounded bg-bg-alt" />
      <div className="mt-6 h-3 w-full rounded-full bg-bg-alt" />
      <div className="mt-auto h-4 w-24 rounded bg-bg-alt" />
    </div>
  )
}

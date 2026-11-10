import { useEffect, useState } from 'react'
import { DecisionBar } from '../components/DecisionBar'
import { Icon } from '../components/Icon'
import { ProjectionChart } from '../components/ProjectionChart'
import { SectionLabel } from '../components/Shell'
import { Button } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import { t } from '../i18n/en'
import { getWithCache } from '../lib/api'
import { coverText, num } from '../lib/format'
import { go, href } from '../lib/route'
import type { ModeInfo, ReasonCodes, Series } from '../types'

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ready'; series: Series; cachedAt: string | null }

function Stat({ label, value, sub }: { label: string; value: string; sub?: string | null }) {
  return (
    <div className="border-t border-line py-3">
      <dt className="text-[0.8125rem] text-muted">{label}</dt>
      <dd className="mt-0.5 text-xl font-medium text-ink">{value}</dd>
      {sub && <dd className="text-[0.8125rem] text-body">{sub}</dd>}
    </div>
  )
}

export function DetailPanel({
  id,
  asOf,
  codes,
  onDecided,
  refreshKey,
}: {
  id: string
  asOf: string
  codes: ReasonCodes | null
  onDecided: () => void
  refreshKey: number
}) {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [table, setTable] = useState(false)
  const [actual, setActual] = useState(false)

  useEffect(() => {
    let live = true
    setLoad((prev) => (prev.state === 'ready' && prev.series.id === id ? prev : { state: 'loading' }))
    getWithCache<{ series: Series } & ModeInfo>(`/api/series/${encodeURIComponent(id)}?as_of=${asOf}`)
      .then(({ data, cachedAt }) => live && setLoad({ state: 'ready', series: data.series, cachedAt }))
      .catch((e: Error) => live && setLoad({ state: 'error', message: e.message }))
    return () => {
      live = false
    }
  }, [id, asOf, refreshKey])

  useEffect(() => {
    setActual(false)
    setTable(false)
  }, [id, asOf])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && go({ page: 'brief' })
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const close = (
    <a
      href={href({ page: 'brief' })}
      className="inline-flex min-h-11 items-center gap-2 rounded-control pr-3 text-sm font-medium text-ink no-underline hover:underline"
    >
      <Icon name="back" size={18} />
      {t.common.back}
    </a>
  )

  if (load.state === 'loading') {
    return (
      <div aria-label={t.common.loading}>
        {close}
        <div className="mt-4 animate-pulse space-y-4">
          <div className="h-10 w-24 rounded bg-bg-alt" />
          <div className="h-6 w-full rounded bg-bg-alt" />
          <div className="h-56 w-full rounded-card bg-bg-alt" />
          <div className="h-24 w-full rounded-card bg-bg-alt" />
        </div>
      </div>
    )
  }
  if (load.state === 'error') {
    return (
      <div>
        {close}
        <p className="mt-6 text-lg font-semibold text-ink">{t.detail.loadError}</p>
        <p className="mt-1">{load.message}</p>
      </div>
    )
  }

  const s = load.series
  const days = s.projection ?? []
  const lowest = days.reduce((min, d) => (d.stock < min.stock ? d : min), days[0])
  const split = s.shelf_split && s.component === 'RBC' ? t.detail.split(s.shelf_split.RBC ?? 0, s.shelf_split.WB ?? 0) : null
  const coverValue =
    s.cover_days === null ? '–' : s.cover_days <= 0 ? t.tile.empty : `${coverText(s.cover_days, s.cover_capped)} ${s.cover_days === 1 ? 'day' : 'days'}`
  const coverSub =
    s.cover_days === null
      ? t.detail.coverNone
      : s.worst_cover_days != null && !s.cover_capped && s.cover_days - s.worst_cover_days >= 0.1
        ? t.detail.coverRange(`${coverText(s.worst_cover_days)} ${s.worst_cover_days === 1 ? 'day' : 'days'}`)
        : null

  return (
    <article aria-labelledby="detail-title">
      <div className="flex items-center justify-between gap-3">
        {close}
        <StatusBadge status={s.status} />
      </div>

      <header className="mt-3">
        <p className="text-[0.8125rem] text-muted">
          {s.facility_name} · {s.component_label}
        </p>
        <h2 id="detail-title" className="mt-1 text-[clamp(2.250rem,6vw,3rem)] leading-none">
          {s.blood_group_label}
        </h2>
        <p className="mt-3 text-lg leading-snug text-ink">{s.status_line}</p>
      </header>

      {s.held && (
        <>
          <dl className="mt-5 grid grid-cols-2 gap-x-6">
            <Stat label={t.detail.onShelf} value={t.common.units(s.units_on_shelf)} sub={split} />
            <Stat label={t.detail.cover} value={coverValue} sub={coverSub} />
            <Stat
              label={t.detail.nextDelivery}
              value={s.next_delivery?.label ?? '–'}
              sub={s.next_delivery ? t.detail.nextDeliveryUnits(t.common.units(s.next_delivery.usual_units), !!s.deliveries_from_supply_forecast) : null}
            />
            <Stat
              label={t.detail.use7}
              value={t.common.units(Number(num(s.expected_use_7_days)))}
              sub={s.expected_use_7_days_range[1] > 0 ? t.brief.range(s.expected_use_7_days_range[0], s.expected_use_7_days_range[1]) : null}
            />
          </dl>

          <section className="mt-6">
            <SectionLabel>{t.detail.chartTitle}</SectionLabel>
            <div className="mt-3">
              <ProjectionChart series={s} showActual={actual} />
            </div>
            <p className="mt-3 text-sm">
              {lowest && t.detail.lowest(t.common.units(Number(num(lowest.stock))), lowest.label)}{' '}
              {actual && s.actual && <span className="text-ink">{s.actual.summary}</span>}
            </p>
            <div className="mt-2 flex flex-wrap gap-x-5">
              <Button variant="text" icon="table" className="!px-0" onClick={() => setTable((v) => !v)} aria-expanded={table}>
                {table ? t.detail.hideTable : t.detail.showTable}
              </Button>
              {s.actual && s.actual.days.length > 0 && (
                <Button variant="text" icon="watch" className="!px-0" onClick={() => setActual((v) => !v)} aria-pressed={actual}>
                  {actual ? t.detail.hideActual : t.detail.showActual}
                </Button>
              )}
            </div>
            {table && (
              <div className="mt-2 overflow-x-auto rounded-control border border-line">
                <table className="w-full min-w-[26rem] text-left text-[0.8125rem]">
                  <thead className="bg-bg-alt text-ink">
                    <tr>
                      {Object.values(t.detail.table).map((h) => (
                        <th key={h} className="px-3 py-2 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {days.map((d) => (
                      <tr key={d.date} className="border-t border-line">
                        <td className="px-3 py-1.5 whitespace-nowrap text-ink">{d.label}</td>
                        <td className="px-3 py-1.5">{d.demand}</td>
                        <td className="px-3 py-1.5">{d.is_delivery_day ? `+${d.delivery}` : ''}</td>
                        <td className="px-3 py-1.5">{d.expiring > 0 ? d.expiring : ''}</td>
                        <td className="px-3 py-1.5 font-medium text-ink">{d.stock}</td>
                        <td className="px-3 py-1.5 whitespace-nowrap">
                          {d.stock_low} to {d.stock_high}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {s.reasons.length > 0 && (
            <section className="mt-6">
              <SectionLabel>{t.detail.why}</SectionLabel>
              <ul className="mt-2">
                {s.reasons.map((reason) => (
                  <li key={reason.text} className="flex gap-3 border-b border-line py-3 text-sm last:border-b-0">
                    <Icon name={reason.icon} className="mt-0.5 shrink-0 text-ink" />
                    <span>{reason.text}</span>
                  </li>
                ))}
              </ul>
              {s.forecast_compare && (
                <p className="mt-2 text-[0.8125rem] text-muted">
                  {t.detail.compare(s.forecast_compare.baseline_7_days, s.forecast_compare.model_7_days)}
                </p>
              )}
            </section>
          )}

          <section className="mt-6">
            <SectionLabel>{t.detail.suggestion}</SectionLabel>
            <div className="mt-3">
              <DecisionBar series={s} asOf={asOf} codes={codes} onDecided={onDecided} />
            </div>
          </section>

          {s.compatible_cover && (
            <section className="mt-6">
              <SectionLabel>{t.detail.compatible}</SectionLabel>
              <div className="mt-3 rounded-card border border-line p-4">
                {s.compatible_cover.groups.length === 0 ? (
                  <p className="text-sm">{t.detail.compatibleNone}</p>
                ) : (
                  <ul className="flex flex-wrap gap-x-5 gap-y-2">
                    {s.compatible_cover.groups.map((g) => (
                      <li key={g.blood_group} className="text-sm">
                        <span className="font-semibold text-ink">{g.blood_group_label}</span> {g.units}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-3 flex gap-2 border-t border-line pt-3 text-[0.8125rem] text-body">
                  <Icon name="info" size={16} className="mt-0.5 shrink-0" />
                  {s.compatible_cover.note}
                </p>
              </div>
            </section>
          )}
        </>
      )}
    </article>
  )
}

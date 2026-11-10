import { useEffect, useState } from 'react'
import { DecisionBar } from '../components/DecisionBar'
import { Icon } from '../components/Icon'
import { SectionLabel } from '../components/Shell'
import { Banner, Button, QuietState } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import { t } from '../i18n/en'
import { getWithCache } from '../lib/api'
import { coverText, cx } from '../lib/format'
import type { ModeInfo, Overview, ReasonCodes, RegionView, Status } from '../types'

const cellTone: Record<Status, string> = {
  act: 'bg-act-soft border-[#e4a7a1] text-act',
  watch: 'bg-watch-soft border-[#e3c57d] text-watch',
  steady: 'bg-white border-line text-ink',
  not_held: 'bg-bg-alt border-line text-muted',
}

export function RegionPage({
  asOf,
  codes,
  onMode,
  onOpen,
}: {
  asOf: string
  codes: ReasonCodes | null
  onMode: (m: ModeInfo) => void
  onOpen: (facilityId: string, seriesId: string) => void
}) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [view, setView] = useState<RegionView | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [cachedAt, setCachedAt] = useState<string | null>(null)
  const [donors, setDonors] = useState(60)
  const [date, setDate] = useState('')
  const [whatIf, setWhatIf] = useState<{ donors: number; date: string } | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    setWhatIf(null)
    setDate('')
  }, [asOf])

  useEffect(() => {
    let live = true
    setProblem(null)
    getWithCache<Overview>(`/api/overview?as_of=${asOf}&component=RBC`)
      .then(({ data, cachedAt: at }) => {
        if (!live) return
        setOverview(data)
        setCachedAt(at)
        if (!at) onMode(data)
      })
      .catch((e: Error) => live && setProblem(e.message))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asOf])

  useEffect(() => {
    let live = true
    const extra = whatIf ? `&extra_donors=${whatIf.donors}&extra_date=${whatIf.date}` : ''
    getWithCache<RegionView>(`/api/region?as_of=${asOf}${extra}`)
      .then(({ data }) => live && setView(data))
      .catch((e: Error) => live && setProblem(e.message))
    return () => {
      live = false
    }
  }, [asOf, whatIf, tick])

  if (problem && !overview) {
    return <QuietState title="The regional view could not be loaded." text={problem} />
  }
  const act = overview?.facilities.filter((f) => f.act > 0).length ?? 0
  const maxWeek = Math.max(1, ...(view?.weeks.map((w) => Math.max(w.expected_cleared, w.usual_cleared, w.demand)) ?? [1]))
  const lastDay = view ? new Date(new Date(view.as_of).getTime() + 27 * 86400000).toISOString().slice(0, 10) : ''

  return (
    <div>
      {cachedAt && <Banner>{t.brief.cached('earlier')}</Banner>}
      <section className="relative pb-[clamp(1.500rem,4vw,2.500rem)]">
        <div className="pointer-events-none absolute -top-10 -left-16 h-64 w-[min(34rem,90vw)] rounded-full bg-sky-soft opacity-70 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <SectionLabel>
            {t.region.label}
            {view ? ` · ${view.centre.region_name}` : ''}
          </SectionLabel>
          {overview && view ? (
            <h1 className="mt-5 max-w-[26ch] text-[clamp(1.750rem,4.500vw,3rem)] leading-[1.100]">
              {t.region.headline(act, overview.facilities.length, view.supply_change_pct)}
            </h1>
          ) : (
            <div className="mt-6 animate-pulse" aria-label={t.common.loading}>
              <div className="h-10 w-4/5 rounded bg-bg-alt" />
              <div className="mt-3 h-10 w-3/5 rounded bg-bg-alt" />
            </div>
          )}
        </div>
      </section>

      {/* The grid: hospitals down, blood groups across */}
      <section>
        <SectionLabel>{t.region.gridLabel}</SectionLabel>
        <p className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[0.8125rem] text-muted">
          <span>{t.region.gridHelp}</span>
          <span className="inline-flex items-center gap-4">
            <StatusBadge status="act" className="!text-[0.8125rem]" />
            <StatusBadge status="watch" className="!text-[0.8125rem]" />
            <StatusBadge status="steady" className="!text-[0.8125rem]" />
          </span>
        </p>
        <div className="mt-3 rounded-card border border-line">
          <div className="hidden grid-cols-[minmax(0,1fr)_repeat(8,2.750rem)] items-center gap-1.5 border-b border-line bg-bg-alt px-4 py-2 lg:grid" aria-hidden="true">
            <span className="text-[0.8125rem] font-medium text-ink">{t.top.hospital}</span>
            {(overview?.facilities[0]?.groups ?? []).map((g) => (
              <span key={g.blood_group} className="text-center text-[0.8125rem] font-semibold text-ink">
                {g.blood_group_label}
              </span>
            ))}
          </div>
          {!overview && <div className="h-64 animate-pulse bg-bg-alt" />}
          {overview?.facilities.map((f) => (
            <div key={f.facility_id} className="grid items-center gap-x-1.5 gap-y-2 border-b border-line px-3 py-3 last:border-b-0 sm:px-4 lg:grid-cols-[minmax(0,1fr)_repeat(8,2.750rem)]">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{f.name}</p>
                <p className="text-[0.8125rem] text-muted">
                  {f.act > 0 ? `${f.act} to act on` : f.watch > 0 ? `${f.watch} to watch` : 'All steady'}
                  {f.next_delivery_label ? ` · ${t.region.nextDelivery(f.next_delivery_label)}` : ''}
                </p>
              </div>
              <div className="col-span-full grid grid-cols-8 gap-1 lg:col-span-8 lg:gap-1.5">
                {f.groups.map((g) => {
                  const cover = g.cover_days === null ? '–' : g.cover_days <= 0 ? '0' : coverText(g.cover_days, g.cover_capped)
                  return (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => onOpen(f.facility_id, g.id)}
                      aria-label={`${f.name}. ${t.region.cell(g.blood_group_label, g.status_label, g.cover_days === null ? t.tile.noUse : `${cover} ${t.tile.daysOfCover}`)}`}
                      className={cx('relative flex min-h-11 flex-col items-center justify-center rounded-control border text-sm font-medium hover:border-ink focus-visible:border-ink', cellTone[g.status])}
                    >
                      <span className="text-[0.625rem] leading-none font-normal opacity-80 lg:hidden">{g.blood_group_label}</span>
                      <span className="leading-tight">{cover}</span>
                      {g.status === 'act' && <span className="absolute top-0.5 right-1 text-[0.625rem] leading-none" aria-hidden="true">!</span>}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      {view && (
        <>
          {whatIf && (
            <div className="mt-8">
              <Banner icon="info" action={<Button variant="outline" onClick={() => setWhatIf(null)}>{t.region.clear}</Button>}>
                {t.region.whatIfOn(whatIf.donors, whatIf.date)}
              </Banner>
            </div>
          )}

          {/* Supply outlook */}
          <section className="mt-10">
            <SectionLabel>{t.region.supplyLabel}</SectionLabel>
            <p className="mt-3 max-w-[72ch] text-sm">{t.region.supplyHelp(view.rates.units_per_donation, view.rates.median_testing_wait_days)}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {view.weeks.map((w) => (
                <div key={w.week} className="rounded-card border border-line p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-ink">{w.short_label}</p>
                    {w.school_break && <span className="rounded-full border border-ink/25 px-2 py-0.5 text-[0.6875rem] font-medium text-ink">{t.region.schoolBreak}</span>}
                  </div>
                  <p className="mt-2 flex items-baseline gap-2">
                    <span className="text-[2rem] leading-none font-medium text-ink">{w.expected_cleared}</span>
                    <span className="text-[0.8125rem]">{t.region.expected}</span>
                  </p>
                  <div className="relative mt-3 h-3 rounded-full border border-[#c9ced6] bg-white" role="img" aria-label={`${w.expected_cleared} ${t.region.expected}, ${t.region.usual(w.usual_cleared)}`}>
                    <div className="absolute inset-y-0 left-0 rounded-full bg-sky" style={{ width: `${(w.expected_cleared / maxWeek) * 100}%` }} />
                    <div className="absolute -top-1 -bottom-1 w-px bg-ink" style={{ left: `${(w.usual_cleared / maxWeek) * 100}%` }} />
                  </div>
                  <p className="mt-2 text-[0.8125rem] text-muted">
                    {t.region.usual(w.usual_cleared)} · need {w.demand}
                  </p>
                  <p className="mt-1 text-[0.8125rem]">{t.region.drives(w.scheduled_drives, w.expected_donors)}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Gap view */}
          <section className="mt-10">
            <SectionLabel>{t.region.gapLabel}</SectionLabel>
            <p className="mt-3 max-w-[72ch] text-sm">{t.region.gapHelp}</p>
            <div className="mt-3 overflow-hidden rounded-card border border-line">
              <div className="grid grid-cols-[3.250rem_repeat(4,minmax(0,1fr))] items-center gap-1.5 border-b border-line bg-bg-alt px-3 py-2 text-[0.75rem] font-medium text-ink sm:grid-cols-[4rem_5.500rem_repeat(4,minmax(0,1fr))] sm:px-4 sm:text-[0.8125rem]">
                <span>Group</span>
                <span className="hidden sm:block">{t.region.stockNow}</span>
                {view.weeks.map((w) => (
                  <span key={w.week} className="text-center">
                    {w.short_label.replace('Week of ', '')}
                  </span>
                ))}
              </div>
              {view.groups.map((g) => (
                <div key={g.blood_group} className="grid grid-cols-[3.250rem_repeat(4,minmax(0,1fr))] items-center gap-1.5 border-b border-line px-3 py-2 text-sm last:border-b-0 sm:grid-cols-[4rem_5.500rem_repeat(4,minmax(0,1fr))] sm:px-4">
                  <span className="font-semibold text-ink">{g.blood_group_label}</span>
                  <span className="hidden sm:block">{g.stock_now}</span>
                  {g.weeks.map((w) => (
                    <span key={w.week} className={cx('rounded-control border px-1 py-1.5 text-center text-[0.8125rem]', w.short >= 0.5 ? 'border-[#e4a7a1] bg-act-soft font-medium text-act' : 'border-transparent text-muted')}>
                      {w.short >= 0.5 ? t.region.short(Math.round(w.short)) : '–'}
                    </span>
                  ))}
                </div>
              ))}
              <div className="grid grid-cols-[3.250rem_repeat(4,minmax(0,1fr))] items-center gap-1.5 bg-bg-alt px-3 py-2 text-sm font-medium text-ink sm:grid-cols-[4rem_5.500rem_repeat(4,minmax(0,1fr))] sm:px-4">
                <span className="text-[0.75rem] sm:text-sm">All</span>
                <span className="hidden sm:block">{view.groups.reduce((n, g) => n + g.stock_now, 0)}</span>
                {view.weeks.map((w) => (
                  <span key={w.week} className="text-center text-[0.8125rem]">
                    {w.units_short > 0 ? t.region.short(w.units_short) : t.region.enough}
                  </span>
                ))}
              </div>
            </div>
            <ul className="mt-3 list-disc space-y-0.5 pl-5 text-[0.8125rem] text-muted">
              {view.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </section>

          {/* Drive suggestions */}
          <section className="mt-10">
            <SectionLabel>{t.region.suggestLabel}</SectionLabel>
            <div className="mt-3 grid gap-3 xl:grid-cols-2">
              {view.drive_suggestions.length === 0 && <QuietState title={t.brief.allSteadyTitle} text={t.region.suggestNone} />}
              {view.drive_suggestions.map((item) => (
                <article key={item.id} className="rounded-card border border-line p-4 sm:p-5">
                  <p className="text-base leading-snug text-ink">{item.text}</p>
                  {item.venue_text && (
                    <p className="mt-2 flex gap-2 text-sm">
                      <Icon name="school" size={18} className="mt-0.5 shrink-0 text-ink" />
                      {item.venue_text}
                    </p>
                  )}
                  <div className="mt-4 border-t border-line pt-4">
                    {whatIf ? (
                      <p className="text-sm text-muted">{t.region.clear} the what-if to decide on this suggestion.</p>
                    ) : (
                      <DecisionBar series={{ ...item, as_of: view.as_of }} asOf={view.as_of} codes={codes} keys={false} onDecided={() => setTick((n) => n + 1)} />
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>

          {/* What-if */}
          <section className="mt-10">
            <SectionLabel>{t.region.whatIfLabel}</SectionLabel>
            <form
              className="mt-3 flex flex-wrap items-end gap-3 rounded-card border border-line p-4 sm:p-5"
              onSubmit={(e) => {
                e.preventDefault()
                if (date && donors > 0) setWhatIf({ donors, date })
              }}
            >
              <p className="basis-full text-sm">{t.region.whatIfHelp}</p>
              <label className="grid gap-1 text-sm font-medium text-ink">
                {t.region.donors}
                <input type="number" min={1} max={2000} className="min-h-11 w-32 rounded-control border border-ink/25 px-3 font-normal" value={donors} onChange={(e) => setDonors(Number(e.target.value))} />
              </label>
              <label className="grid gap-1 text-sm font-medium text-ink">
                {t.region.date}
                <input type="date" required min={view.as_of} max={lastDay} className="min-h-11 rounded-control border border-ink/25 px-3 font-normal" value={date} onChange={(e) => setDate(e.target.value)} />
              </label>
              <Button type="submit" variant="sky" icon="arrow">
                {t.region.tryIt}
              </Button>
              {whatIf && (
                <Button variant="text" onClick={() => setWhatIf(null)}>
                  {t.region.clear}
                </Button>
              )}
            </form>
          </section>
        </>
      )}
    </div>
  )
}

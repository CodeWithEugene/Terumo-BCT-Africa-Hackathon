import { useEffect, useState } from 'react'
import { SectionLabel } from '../components/Shell'
import { QuietState } from '../components/States'
import { t } from '../i18n/en'
import { api, ApiError, getWithCache } from '../lib/api'
import { cx } from '../lib/format'
import type { ModeInfo } from '../types'

interface ForecastMetric { model: string; segment_type: string; segment: string; units_requested: number; mae: number; wape: number; wape_7day: number }
interface AlertMetric { model: string; rule: string; segment_type: string; events: number; alerts: number; recall: number; precision: number }
interface SupplyMetric { target: string; segment: string; method: string; wape: number; mae: number }
interface Accuracy extends ModeInfo {
  forecast: ForecastMetric[]
  alerts: AlertMetric[]
  supply: SupplyMetric[]
  test_period: { first: string; last: string; horizon_days: number } | null
  alert_rule_cover_days?: number
  rare_note: Record<string, string> | null
  allocation?: { policy: string; facility_id: string; name: string; units_requested: number; units_short: number; units_expired: number; short_pct: number }[]
  allocation_fact?: Record<string, string>
}

const pct = (v: number | undefined) => (v === undefined ? '–' : `${Math.round(v * 100)}`)
const day = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

function change(usual?: number, ours?: number, higherIsBetter = false): { text: string; good: boolean | null } {
  if (usual === undefined || ours === undefined || usual === 0) return { text: '', good: null }
  const diff = ((ours - usual) / usual) * 100 * (higherIsBetter ? 1 : -1)
  if (Math.abs(diff) < 0.5) return { text: t.accuracy.same, good: null }
  const shown = `${Math.abs(diff).toFixed(Math.abs(diff) < 10 ? 1 : 0)}%`
  return diff > 0 ? { text: t.accuracy.better(shown), good: true } : { text: t.accuracy.worse(shown), good: false }
}

function Compare({
  label, unit, usual, ours, usualText, oursText, higherIsBetter, suffix = '',
}: {
  label: string; unit: string; usual?: number; ours?: number; usualText: string; oursText: string; higherIsBetter?: boolean; suffix?: string
}) {
  const result = change(usual, ours, higherIsBetter)
  return (
    <section className="mt-8">
      <SectionLabel>{label}</SectionLabel>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-card border border-line p-5">
          <p className="text-sm font-medium text-ink">{t.accuracy.usual}</p>
          <p className="mt-2 text-[clamp(2.250rem,6vw,3.250rem)] leading-none font-medium tracking-[-0.010em] text-ink">
            {usual === undefined ? '–' : pct(usual)}
            <span className="text-2xl">{suffix}</span>
          </p>
          <p className="mt-1 text-[0.8125rem] text-muted">{unit}</p>
          <p className="mt-3 text-sm">{usualText}</p>
        </div>
        <div className="rounded-card border border-ink bg-sky-soft/40 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-ink">{t.accuracy.ours}</p>
            {result.text && (
              <span className={cx('rounded-full border px-3 py-0.5 text-[0.8125rem] font-medium',
                result.good === true ? 'border-steady text-steady' : result.good === false ? 'border-act text-act' : 'border-ink/30 text-ink')}>
                {result.text}
              </span>
            )}
          </div>
          <p className="mt-2 text-[clamp(2.250rem,6vw,3.250rem)] leading-none font-medium tracking-[-0.010em] text-ink">
            {ours === undefined ? '–' : pct(ours)}
            <span className="text-2xl">{suffix}</span>
          </p>
          <p className="mt-1 text-[0.8125rem] text-muted">{ours === undefined ? t.accuracy.notRun : unit}</p>
          <p className="mt-3 text-sm">{oursText}</p>
        </div>
      </div>
    </section>
  )
}

export function AccuracyPage({ onMode }: { onMode: (m: ModeInfo) => void }) {
  const [data, setData] = useState<Accuracy | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getWithCache<Accuracy>('/api/accuracy')
      .then(({ data: d }) => setData(d))
      .catch((e: Error) => setProblem(e.message))
  }, [])

  async function toggle() {
    if (!data) return
    setBusy(true)
    setProblem(null)
    try {
      const mode = await api.post<ModeInfo>('/api/fallback', { use_baseline: !data.fallback_forced })
      setData({ ...data, ...mode })
      onMode(mode)
    } catch (e) {
      setProblem((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  if (!data) return <p className={cx('text-sm', problem ? 'text-act' : 'text-muted')}>{problem ?? t.common.loading}</p>
  if (data.forecast.length === 0) return <QuietState title={t.accuracy.title} text={t.accuracy.noData} />

  const all = (model: string) => data.forecast.find((m) => m.model === model && m.segment_type === 'all')
  const supply = (method: string) => data.supply.find((m) => m.target === 'cleared' && m.segment === 'all weeks ahead' && m.method === method)
  const hasModel = data.forecast.some((m) => m.model === 'm1')
  const ours = data.alerts.find((m) => m.rule === 'ours' && m.segment_type === 'all' && m.model === (hasModel ? 'm1' : 'baseline'))
  const simple = data.alerts.find((m) => m.rule === 'simple' && m.segment_type === 'all')
  const types = data.forecast.filter((m) => m.segment_type === 'facility type' && m.model === 'baseline')
  const typeOurs = (segment: string) => data.forecast.find((m) => m.segment_type === 'facility type' && m.model === 'm1' && m.segment === segment)

  const fmt = (n: number) => Math.round(n).toLocaleString('en-GB')
  const alloc = data.allocation ?? []
  const pick = (policy: string, id: string) => alloc.find((r) => r.policy === policy && r.facility_id === id)
  const fairAll = pick('actual', 'ALL') && pick('fair', 'ALL') ? { actual: pick('actual', 'ALL')!, fair: pick('fair', 'ALL')! } : null
  const movers = alloc
    .filter((r) => r.policy === 'actual' && r.facility_id !== 'ALL')
    .map((r) => ({ name: r.name, before: r.short_pct, after: pick('fair', r.facility_id)?.short_pct ?? r.short_pct }))
    .sort((a, b) => a.after - a.before - (b.after - b.before))

  return (
    <div>
      <SectionLabel>{t.accuracy.label}</SectionLabel>
      <h1 className="mt-5 text-[clamp(1.750rem,4vw,2.500rem)] leading-[1.120]">{t.accuracy.title}</h1>
      {data.test_period && <p className="mt-3 max-w-[64ch]">{t.accuracy.lead(day(data.test_period.first), day(data.test_period.last))}</p>}

      <Compare label={t.accuracy.supplyLabel} unit={t.accuracy.supplyUnit} usual={supply('baseline')?.wape} ours={supply('model')?.wape}
        usualText={t.accuracy.supplyUsual} oursText={t.accuracy.supplyOurs} />
      <Compare label={t.accuracy.demandLabel} unit={t.accuracy.demandUnit} usual={all('baseline')?.wape_7day} ours={all('m1')?.wape_7day}
        usualText={t.accuracy.demandUsual} oursText={t.accuracy.demandOurs} />
      <Compare label={t.accuracy.alertLabel} unit={t.accuracy.alertUnit} suffix="%" higherIsBetter usual={simple?.recall} ours={ours?.recall}
        usualText={`${t.accuracy.alertUsual(data.alert_rule_cover_days ?? 3)} ${t.accuracy.alertUsualPrecision(`${pct(simple?.precision)}%`)}`}
        oursText={t.accuracy.alertOurs(`${pct(ours?.precision)}%`)} />
      <p className="mt-3 text-[0.8125rem] text-muted">{t.accuracy.shortage}</p>

      {fairAll && (
        <>
          <Compare label={t.accuracy.shareLabel} unit={t.accuracy.shareUnit} suffix="%" usual={fairAll.actual.short_pct / 100} ours={fairAll.fair.short_pct / 100}
            usualText={t.accuracy.shareUsual(fmt(fairAll.actual.units_short), fmt(fairAll.actual.units_expired))}
            oursText={t.accuracy.shareOurs(fmt(fairAll.fair.units_short), fmt(fairAll.fair.units_expired))} />
          {data.allocation_fact && (
            <p className="mt-3 max-w-[76ch] text-sm font-medium text-ink">
              {t.accuracy.shareFinding(data.allocation_fact.with_spare_elsewhere_pct, fmt(Number(data.allocation_fact.shortage_days)))}
            </p>
          )}
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {[{ title: t.accuracy.shareGain, rows: movers.slice(0, 3) }, { title: t.accuracy.shareLose, rows: movers.slice(-3).reverse() }].map((block) => (
              <div key={block.title} className="rounded-card border border-line p-4">
                <p className="text-sm font-medium text-ink">{block.title}</p>
                {block.rows.map((m) => (
                  <p key={m.name} className="mt-1.5 flex justify-between gap-3 border-t border-line pt-1.5 text-sm">
                    <span className="min-w-0 truncate">{m.name}</span>
                    <span className="shrink-0 text-ink">{m.before.toFixed(0)}% → <span className="font-medium">{m.after.toFixed(0)}%</span></span>
                  </p>
                ))}
              </div>
            ))}
          </div>
          {data.allocation_fact && (
            <p className="mt-3 max-w-[76ch] text-[0.8125rem] text-muted">
              {t.accuracy.shareCaveat(data.allocation_fact.real_not_from_shelf_pct, fairAll.actual.short_pct.toFixed(1))}
            </p>
          )}
        </>
      )}

      <section className="mt-10">
        <SectionLabel>{t.accuracy.fairLabel}</SectionLabel>
        <p className="mt-3 max-w-[64ch] text-sm">
          {t.accuracy.fairLead} {t.accuracy.demandUnit.replace(/^u/, 'U')}.
        </p>
        <div className="mt-3 rounded-card border border-line">
          <div className="hidden grid-cols-[2fr_1fr_1fr_1fr_1.2fr] gap-3 border-b border-line bg-bg-alt px-4 py-2 text-[0.8125rem] font-medium text-ink md:grid">
            {Object.values(t.accuracy.fairCols).map((c) => <span key={c}>{c}</span>)}
          </div>
          {types.map((row) => {
            const mine = typeOurs(row.segment)
            const result = change(row.wape_7day, mine?.wape_7day)
            return (
              <div key={row.segment} className="grid grid-cols-2 gap-x-3 gap-y-1 border-b border-line px-4 py-3 text-sm last:border-b-0 md:grid-cols-[2fr_1fr_1fr_1fr_1.2fr] md:items-center">
                <span className="col-span-2 font-medium text-ink md:col-span-1">{t.accuracy.facilityTypes[row.segment] ?? row.segment}</span>
                <span><span className="text-[0.8125rem] text-muted md:hidden">{t.accuracy.fairCols.units}: </span>{Math.round(row.units_requested).toLocaleString('en-GB')}</span>
                <span><span className="text-[0.8125rem] text-muted md:hidden">{t.accuracy.fairCols.usual}: </span>{pct(row.wape_7day)}</span>
                <span className="font-medium text-ink"><span className="text-[0.8125rem] font-normal text-muted md:hidden">{t.accuracy.fairCols.ours}: </span>{mine ? pct(mine.wape_7day) : '–'}</span>
                <span className={cx(result.good === true ? 'text-steady' : result.good === false ? 'text-act' : 'text-body')}>{result.text}</span>
              </div>
            )
          })}
        </div>
        {data.rare_note && (
          <p className="mt-3 max-w-[72ch] text-sm">
            {t.accuracy.rare(`${Math.round(Number(data.rare_note.rare_share) * 100)}%`, data.rare_note.in_use === 'baseline' ? '4-week average' : 'forecast model')}
          </p>
        )}
      </section>

      <section className="mt-10">
        <SectionLabel>{t.accuracy.switchLabel}</SectionLabel>
        <div className="mt-3 flex flex-col gap-4 rounded-card border border-line p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-[58ch]">
            <p className="font-medium text-ink" id="fallback-title">{t.accuracy.switchTitle}</p>
            <p className="mt-1 text-sm">{data.model_available ? t.accuracy.switchHelp : t.accuracy.switchUnavailable}</p>
          </div>
          <button type="button" role="switch" aria-checked={data.fallback_forced} aria-labelledby="fallback-title" disabled={busy || !data.model_available} onClick={toggle}
            className="flex min-h-11 shrink-0 items-center gap-3 text-sm font-medium text-ink disabled:opacity-50">
            <span className={cx('relative h-7 w-12 rounded-full border transition-colors', data.fallback_forced ? 'border-ink bg-ink' : 'border-ink/40 bg-white')}>
              <span className={cx('absolute top-0.5 h-[1.375rem] w-[1.375rem] rounded-full transition-all', data.fallback_forced ? 'left-[1.375rem] bg-white' : 'left-0.5 bg-ink')} />
            </span>
            {data.fallback_forced ? t.accuracy.switchOn : t.accuracy.switchOff}
          </button>
        </div>
        {problem && <p role="alert" className="mt-2 text-sm text-act">{problem}</p>}
      </section>
    </div>
  )
}

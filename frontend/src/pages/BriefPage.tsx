import { useCallback, useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { SectionLabel } from '../components/Shell'
import { Banner, Button, QuietState, RackArt } from '../components/States'
import { Tile, TileSkeleton } from '../components/Tile'
import { t } from '../i18n/en'
import { getWithCache } from '../lib/api'
import { cx, num, timeAgo } from '../lib/format'
import type { Brief, Component, ModeInfo } from '../types'

type Load =
  | { state: 'loading' }
  | { state: 'error'; message: string }
  | { state: 'ready'; brief: Brief; cachedAt: string | null }

export function BriefPage({
  asOf,
  facilityId,
  component,
  onComponent,
  onMode,
  selectedId,
  refreshKey,
}: {
  asOf: string
  facilityId: string
  component: Component
  onComponent: (c: Component) => void
  onMode: (m: ModeInfo) => void
  selectedId?: string
  refreshKey: number
}) {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)

  const fetchBrief = useCallback(() => {
    const path = `/api/brief?as_of=${asOf}&facility_id=${facilityId}&component=${component}`
    let live = true
    setLoad((prev) => (prev.state === 'ready' ? prev : { state: 'loading' }))
    getWithCache<Brief>(path)
      .then(({ data, cachedAt }) => {
        if (!live) return
        setLoad({ state: 'ready', brief: data, cachedAt })
        if (!cachedAt) onMode(data)
      })
      .catch((e: Error) => live && setLoad({ state: 'error', message: e.message }))
    return () => {
      live = false
    }
    // onMode is stable enough for this purpose; leaving it out avoids refetch loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asOf, facilityId, component])

  useEffect(() => fetchBrief(), [fetchBrief, attempt, refreshKey])
  useEffect(() => {
    const again = () => setAttempt((n) => n + 1)
    window.addEventListener('sp:offline-changed', again)
    return () => window.removeEventListener('sp:offline-changed', again)
  }, [])

  const brief = load.state === 'ready' ? load.brief : null
  const stale = brief !== null && (brief.as_of !== asOf || brief.component !== component || brief.facility.facility_id !== facilityId)
  const held = brief?.series.filter((s) => s.held) ?? []
  const allSteady = brief !== null && held.length > 0 && held.every((s) => s.status === 'steady')

  return (
    <div>
      {load.state === 'ready' && load.cachedAt && (
        <Banner action={<Button variant="outline" icon="retry" onClick={() => setAttempt((n) => n + 1)}>{t.brief.retry}</Button>}>
          {t.brief.cached(timeAgo(load.cachedAt))}
        </Banner>
      )}

      {/* The answer first: one plain sentence, with one soft glow behind it */}
      <section className="relative pt-2 pb-[clamp(1.500rem,4vw,3rem)]">
        <div
          className="pointer-events-none absolute -top-10 -left-16 h-64 w-[min(34rem,90vw)] rounded-full bg-sky-soft opacity-70 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative">
          <SectionLabel>
            {t.brief.label}
            {brief ? ` · ${brief.as_of_label}` : ''}
          </SectionLabel>
          {load.state === 'loading' && (
            <div className="mt-6 animate-pulse" aria-label={t.common.loading}>
              <div className="h-10 w-4/5 rounded bg-bg-alt sm:h-12" />
              <div className="mt-3 h-10 w-3/5 rounded bg-bg-alt sm:h-12" />
            </div>
          )}
          {load.state === 'error' && (
            <div className="mt-6">
              <h1 className="max-w-[22ch] text-[clamp(1.750rem,4.500vw,2.750rem)] leading-[1.120]">{t.brief.errorTitle}</h1>
              <p className="mt-3 max-w-[52ch]">
                {load.message} {t.brief.errorHelp}
              </p>
              <Button className="mt-5" icon="retry" onClick={() => setAttempt((n) => n + 1)}>
                {t.brief.retry}
              </Button>
            </div>
          )}
          {brief && (
            <div className={cx('transition-opacity duration-150', stale && 'opacity-50')} aria-live="polite">
              <h1 className="mt-5 max-w-[24ch] text-[clamp(1.750rem,4.500vw,3.250rem)] leading-[1.100]">
                <span className="font-normal text-body">{t.brief.greeting(new Date().getHours())}</span> {brief.sentence}
              </h1>
              <p className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
                {held.length > 0 && (
                  <span className="inline-flex items-center gap-1.5">
                    <Icon name="delivery" size={16} />
                    {brief.next_delivery_label ? t.brief.nextDelivery(brief.next_delivery_label) : t.brief.noDelivery}
                  </span>
                )}
                <span className="inline-flex items-center gap-1.5">
                  <Icon name="info" size={16} />
                  {brief.mode_note}
                </span>
              </p>
            </div>
          )}
        </div>
      </section>

      {/* The rack */}
      <section aria-label={t.brief.groupsLabel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="tablist" aria-label="Product" className="inline-flex rounded-control border border-line bg-bg-alt p-1">
            {(brief?.components ?? [{ component: 'RBC' as Component, label: 'Red cells', held: true }]).map((c) => (
              <button
                key={c.component}
                role="tab"
                type="button"
                aria-selected={component === c.component}
                onClick={() => onComponent(c.component)}
                className={cx(
                  'min-h-10 rounded-[6px] px-3.5 text-sm font-medium transition-colors',
                  component === c.component ? 'bg-white text-ink shadow-[0_0_0_1px_var(--color-line)]' : 'text-body hover:text-ink',
                )}
              >
                {c.label}
              </button>
            ))}
          </div>
          {brief && held.length > 0 && <p className="text-[0.8125rem] text-muted">{t.brief.attentionFirst}</p>}
        </div>

        <div className="mt-4">
          {load.state === 'loading' && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 8 }, (_, i) => (
                <TileSkeleton key={i} />
              ))}
            </div>
          )}

          {brief && held.length === 0 && (
            <div className={cx(stale && 'opacity-50')}>
              <QuietState
                art={<RackArt filled={0} />}
                title={t.brief.notHeldTitle(brief.component_label)}
                text={t.brief.notHeldText}
              />
              <div className="mt-8">
                <SectionLabel>{t.brief.expected7}</SectionLabel>
                <dl className="mt-2 grid gap-x-10 sm:grid-cols-2">
                  {brief.series.map((s) => (
                    <div key={s.id} className="flex items-baseline justify-between gap-4 border-b border-line py-3">
                      <dt className="text-lg font-semibold text-ink">{s.blood_group_label}</dt>
                      <dd className="text-right">
                        <span className="text-xl font-medium text-ink">{t.common.units(Number(num(s.expected_use_7_days)))}</span>
                        {s.expected_use_7_days_range[1] > 0 && (
                          <span className="ml-2 text-[0.8125rem] text-muted">
                            {t.brief.range(s.expected_use_7_days_range[0], s.expected_use_7_days_range[1])}
                          </span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          )}

          {brief && held.length > 0 && (
            <>
              {allSteady && (
                <div className="mb-4">
                  <QuietState title={t.brief.allSteadyTitle} text={t.brief.allSteadyText} />
                </div>
              )}
              <div className={cx('grid gap-3 md:grid-cols-2 xl:grid-cols-4', stale && 'opacity-50')}>
                {brief.series.map((s, i) => (
                  <Tile key={s.id} series={s} index={i} selected={selectedId === s.id} />
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  )
}

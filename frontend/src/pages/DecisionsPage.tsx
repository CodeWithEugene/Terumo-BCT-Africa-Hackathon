import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { SectionLabel } from '../components/Shell'
import { QuietState } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import { t } from '../i18n/en'
import { getWithCache } from '../lib/api'
import { cx } from '../lib/format'
import type { Decision, ModeInfo, User } from '../types'

type Filter = 'all' | 'accept' | 'change' | 'reject'

const actionTone: Record<string, string> = {
  accept: 'border-ink bg-ink text-white',
  change: 'border-ink bg-sky-soft text-ink',
  reject: 'border-ink/40 bg-white text-ink',
}

export function DecisionsPage({ user }: { user: User }) {
  const [items, setItems] = useState<Decision[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [hospital, setHospital] = useState('all')

  useEffect(() => {
    getWithCache<{ decisions: Decision[] } & ModeInfo>('/api/decisions')
      .then(({ data }) => setItems(data.decisions))
      .catch((e: Error) => setProblem(e.message))
  }, [])

  const shown = (items ?? []).filter(
    (d) => (filter === 'all' || d.action === filter) && (hospital === 'all' || d.facility_id === hospital),
  )
  const count = (f: Filter) => (items ?? []).filter((d) => f === 'all' || d.action === f).length

  return (
    <div>
      <SectionLabel>{t.decisions.label}</SectionLabel>
      <h1 className="mt-5 max-w-[24ch] text-[clamp(1.750rem,4vw,2.500rem)] leading-[1.120]">{t.decisions.title}</h1>
      <p className="mt-3 max-w-[56ch]">{t.decisions.lead}</p>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Filter by decision" className="flex flex-wrap gap-2">
          {(['all', 'accept', 'change', 'reject'] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={cx(
                'min-h-11 rounded-full border px-4 text-sm font-medium',
                filter === f ? 'border-ink bg-ink text-white' : 'border-ink/25 text-ink hover:border-ink',
              )}
            >
              {t.decisions[f]} <span className="opacity-70">{count(f)}</span>
            </button>
          ))}
        </div>
        {user.facilities.length > 1 && (
          <label className="ml-auto">
            <span className="sr-only">{t.top.hospital}</span>
            <select
              className="min-h-11 max-w-full rounded-control border border-ink/25 bg-white px-3 text-sm font-medium text-ink"
              value={hospital}
              onChange={(e) => setHospital(e.target.value)}
            >
              <option value="all">{t.decisions.allHospitals}</option>
              {user.facilities.map((f) => (
                <option key={f.facility_id} value={f.facility_id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="mt-5">
        {problem && <p className="text-sm text-act">{problem}</p>}
        {items === null && !problem && (
          <div className="animate-pulse space-y-3" aria-label={t.common.loading}>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-24 rounded-card bg-bg-alt" />
            ))}
          </div>
        )}
        {items !== null && shown.length === 0 && <QuietState title={t.decisions.emptyTitle} text={t.decisions.emptyText} />}
        <ul className="grid gap-3">
          {shown.map((d) => (
            <li key={d.decision_id} className={cx('rounded-card border border-line p-4 sm:p-5', d.withdrawn && 'opacity-60')}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <span className={cx('rounded-full border px-3 py-0.5 text-[0.8125rem] font-medium', actionTone[d.action])}>
                  {t.decisions[d.action]}
                </span>
                {d.withdrawn && (
                  <span className="rounded-full border border-ink/30 px-3 py-0.5 text-[0.8125rem] font-medium text-ink">
                    {t.decisions.withdrawn}
                  </span>
                )}
                <span className="text-lg font-semibold text-ink">{d.blood_group_label}</span>
                <span className="text-sm">
                  {d.suggestion_kind === 'drive' ? 'Collections' : d.component === 'RBC' ? 'Red cells' : d.component === 'FFP' ? 'Plasma' : 'Platelets'} · {d.facility_name}
                </span>
                <span className="ml-auto text-[0.8125rem] text-muted">{d.at_label}</span>
              </div>
              <dl className="mt-3 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-[0.8125rem] text-muted">{t.decisions.suggested}</dt>
                  <dd className="text-ink">
                    {t.decisions.kind[d.suggestion_kind] ?? d.suggestion_kind}:{' '}
                    {d.suggestion_kind === 'drive' ? `${d.suggested_quantity} donors` : t.common.units(d.suggested_quantity)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[0.8125rem] text-muted">{t.decisions.decided}</dt>
                  <dd className="font-medium text-ink">
                    {d.action === 'reject' ? t.decisions.reject : d.suggestion_kind === 'drive' ? `${d.final_quantity} donors` : t.common.units(d.final_quantity)}
                    <span className="font-normal text-body">
                      {' '}
                      · {d.display_name}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-[0.8125rem] text-muted">{t.decisions.seenStatus}</dt>
                  <dd className="flex flex-wrap items-center gap-x-2">
                    <StatusBadge status={d.status_seen} />
                    <span className="text-[0.8125rem] text-muted">{t.decisions.mode[d.mode] ?? d.mode}</span>
                  </dd>
                </div>
                {(d.reason_label || d.note) && (
                  <div>
                    <dt className="text-[0.8125rem] text-muted">Reason</dt>
                    <dd className="text-ink">
                      {d.reason_label}
                      {d.note && <span className="block text-body">“{d.note}”</span>}
                    </dd>
                  </div>
                )}
              </dl>
              <p className="mt-3 flex items-center gap-1.5 text-[0.8125rem] text-muted">
                <Icon name="calendar" size={14} />
                As of {d.as_of}
                {d.for_date ? `, ${t.decisions.forDate(d.for_date)}` : ''}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

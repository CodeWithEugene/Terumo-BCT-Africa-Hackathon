import { useEffect, useState, type ReactNode } from 'react'
import { SectionLabel } from '../components/Shell'
import { t } from '../i18n/en'
import { getWithCache } from '../lib/api'
import type { ModeInfo } from '../types'

interface PrivacyFacts extends ModeInfo {
  tables_used: string[]
  never_loaded: string[]
  columns_never_read: Record<string, string[]>
  roles: { role: string; label: string; sees: string; can: string }[]
  your_role: string
  your_scope: string[]
  last_central_sync: string | null
}

function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <SectionLabel>{label}</SectionLabel>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Rows({ items }: { items: string[][] }) {
  return (
    <dl className="rounded-card border border-line">
      {items.map(([term, text]) => (
        <div key={term} className="grid gap-1 border-b border-line px-4 py-3 last:border-b-0 sm:grid-cols-[12rem_1fr] sm:gap-6 sm:px-5">
          <dt className="text-sm font-medium text-ink">{term}</dt>
          <dd className="text-sm">{text}</dd>
        </div>
      ))}
    </dl>
  )
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="max-w-[76ch] space-y-2">
      {items.map((item) => (
        <li key={item} className="flex gap-3 text-sm">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky" aria-hidden="true" />
          {item}
        </li>
      ))}
    </ul>
  )
}

/** The data-flow diagram, drawn by hand in SVG. One column, so the words stay readable on a phone. */
function FlowDiagram() {
  type Step = { title: string; sub: string; kind?: 'never' | 'optional' | 'main' }
  const steps: Step[] = [
    { title: 'Donor register', sub: 'never loaded', kind: 'never' },
    { title: 'Raw files (synthetic)', sub: 'stock, requests, deliveries, drives' },
    { title: 'Pipeline', sub: 'drops person columns, scrambles unit labels' },
    { title: 'Local database', sub: 'on this device: data, decisions, audit log', kind: 'main' },
    { title: 'Forecast and stock projection', sub: 'runs on this device, no internet needed' },
    { title: 'Server', sub: 'sign-in; each role sees only its hospitals' },
    { title: 'Your browser', sub: 'keeps the last brief for offline use' },
    { title: 'Central copy (optional, one way)', sub: 'aggregates and a coded audit log only', kind: 'optional' },
  ]
  const boxH = 56
  const gap = 24
  const width = 340
  const height = steps.length * (boxH + gap) + 34
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-[24rem]" role="img" aria-labelledby="flow-title flow-desc">
      <title id="flow-title">How data moves through the tool</title>
      <desc id="flow-desc">
        The donor register is never loaded. Synthetic raw files pass through a pipeline that removes person-level columns
        into a local database. The forecast and server run on the same device. The browser keeps the last brief. An
        optional one-way copy of aggregates and a coded audit log goes from the local database to a central database.
      </desc>
      {steps.map((step, i) => {
        const y = i * (boxH + gap) + 4
        const never = step.kind === 'never'
        const optional = step.kind === 'optional'
        const arrow = i < steps.length - 1 && !never
        return (
          <g key={step.title}>
            <rect
              x="4" y={y} width={width - 8} height={boxH} rx="8"
              fill={step.kind === 'main' ? 'var(--color-sky-soft)' : 'white'}
              stroke={never ? 'var(--color-act)' : 'var(--color-ink)'}
              strokeOpacity={never ? 1 : step.kind === 'main' ? 0.6 : 0.28}
              strokeDasharray={never || optional ? '5 4' : undefined}
            />
            <text x="18" y={y + 24} fontSize="15" fontWeight="600" fill={never ? 'var(--color-act)' : 'var(--color-ink)'} textDecoration={never ? 'line-through' : undefined}>
              {step.title}
            </text>
            <text x="18" y={y + 43} fontSize="12.5" fill="var(--color-body)">{step.sub}</text>
            {arrow && (
              <path
                d={`M${width / 2} ${y + boxH + 3}v${gap - 8}m-5 -6l5 6l5 -6`}
                fill="none" stroke="var(--color-ink)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                strokeDasharray={steps[i + 1].kind === 'optional' ? '4 4' : undefined}
              />
            )}
          </g>
        )
      })}
      <text x="4" y={height - 22} fontSize="12" fill="var(--color-muted)">Dashed: only if the central copy is set up. It is sent from</text>
      <text x="4" y={height - 6} fontSize="12" fill="var(--color-muted)">the local database. Nothing goes to any third party.</text>
    </svg>
  )
}

export function PrivacyPage() {
  const [facts, setFacts] = useState<PrivacyFacts | null>(null)
  useEffect(() => {
    getWithCache<PrivacyFacts>('/api/privacy')
      .then(({ data }) => setFacts(data))
      .catch(() => undefined)
  }, [])

  return (
    <div>
      <SectionLabel>{t.privacy.label}</SectionLabel>
      <h1 data-tour="page" className="mt-5 max-w-[26ch] text-[clamp(1.750rem,4vw,2.500rem)] leading-[1.120]">{t.privacy.title}</h1>
      <p className="mt-3 max-w-[68ch]">{t.privacy.lead}</p>

      <Block label={t.privacy.useLabel}>
        <p className="max-w-[72ch] text-sm">{t.privacy.useLead}</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-card border border-line p-4 sm:p-5">
            <p className="text-sm font-medium text-ink">{t.privacy.used}</p>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {(facts?.tables_used ?? []).map((name) => (
                <li key={name} className="rounded-full bg-bg-alt px-2.5 py-1 text-[0.8125rem] text-ink">
                  {name.replace(/_/g, ' ')}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-card border border-[#f0cdc9] bg-act-soft/50 p-4 sm:p-5">
            <p className="text-sm font-medium text-ink">{t.privacy.never}</p>
            <p className="mt-2 text-sm">
              <span className="font-medium text-act line-through">donors</span> {t.privacy.neverDonors.replace(/^donors /, '')}
            </p>
            <p className="mt-3 text-sm font-medium text-ink">{t.privacy.columns}</p>
            {Object.entries(facts?.columns_never_read ?? {}).map(([table, columns]) => (
              <p key={table} className="mt-1 text-sm">
                {t.privacy.columnWords[table] ?? table}: <span className="line-through">{columns.join(', ').replace(/_/g, ' ')}</span>
              </p>
            ))}
          </div>
        </div>
      </Block>

      <Block label={t.privacy.pseudoLabel}>
        <Bullets items={t.privacy.pseudo} />
        <p className="mt-3 max-w-[76ch] text-[0.8125rem] text-muted">{t.privacy.pseudoLimit}</p>
      </Block>

      <Block label={t.privacy.rolesLabel}>
        <p className="max-w-[72ch] text-sm">{t.privacy.rolesLead}</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {(facts?.roles ?? []).map((role) => (
            <div key={role.role} className={`rounded-card border p-4 sm:p-5 ${role.role === facts?.your_role ? 'border-ink' : 'border-line'}`}>
              <p className="font-medium text-ink">{role.label}</p>
              <p className="mt-2 text-sm">
                <span className="font-medium text-ink">{t.privacy.sees}:</span> {role.sees}
              </p>
              <p className="mt-1 text-sm">
                <span className="font-medium text-ink">{t.privacy.can}:</span> {role.can}
              </p>
            </div>
          ))}
        </div>
        {facts && (
          <p className="mt-3 max-w-[76ch] text-sm">
            {t.privacy.yours(facts.your_scope.length)} {facts.your_scope.join(', ')}.
          </p>
        )}
      </Block>

      <Block label={t.privacy.storeLabel}>
        <Bullets items={t.privacy.store} />
        <p className="mt-3 text-sm font-medium text-ink">{t.privacy.lastSync(facts?.last_central_sync ?? null)}</p>
      </Block>

      <Block label={t.privacy.cookieLabel}>
        <Rows items={t.privacy.cookies} />
      </Block>

      <Block label={t.privacy.leakLabel}>
        <Rows items={t.privacy.leak} />
      </Block>

      <Block label={t.privacy.flowLabel}>
        <FlowDiagram />
      </Block>

      <Block label={t.privacy.noticeLabel}>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-card border border-line p-4 sm:p-5">
            <p className="text-sm font-medium text-ink">English</p>
            <p className="mt-2 text-sm leading-relaxed">{t.privacy.noticeEn}</p>
          </div>
          <div className="rounded-card border border-line p-4 sm:p-5" lang="sw">
            <p className="text-sm font-medium text-ink">{t.privacy.noticeSwTitle}</p>
            <p className="mt-2 text-sm leading-relaxed">{t.privacy.noticeSw}</p>
            <p className="mt-3 rounded-control bg-watch-soft px-3 py-2 text-[0.8125rem] text-watch" lang="en">
              {t.privacy.noticeSwCheck}
            </p>
          </div>
        </div>
      </Block>

      <Block label={t.privacy.nextLabel}>
        <p className="max-w-[72ch] text-sm">{t.privacy.next}</p>
      </Block>
    </div>
  )
}

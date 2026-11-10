import type { ReactNode } from 'react'
import { t } from '../i18n/en'
import { cx } from '../lib/format'
import { href, type Route } from '../lib/route'
import type { AsOfDates, ModeInfo, User } from '../types'
import { Icon } from './Icon'

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--color-primary)" />
      <rect x="6.5" y="12.5" width="19" height="7" rx="3.5" fill="none" stroke="var(--color-sky-soft)" strokeWidth="1.5" />
      <rect x="8.5" y="14.5" width="9" height="3" rx="1.5" fill="var(--color-sky)" />
      <path d="M21 10.5v11" stroke="var(--color-sky-soft)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

interface NavItem {
  page: Route['page']
  label: string
  icon: string
}

function navItems(user: User): NavItem[] {
  const items: NavItem[] = [{ page: 'brief', label: t.nav.brief, icon: 'brief' }]
  if (user.role === 'regional_officer') items.push({ page: 'region', label: t.nav.region, icon: 'region' })
  items.push(
    { page: 'decisions', label: t.nav.decisions, icon: 'decisions' },
    { page: 'accuracy', label: t.nav.accuracy, icon: 'accuracy' },
    { page: 'privacy', label: t.nav.privacy, icon: 'privacy' },
  )
  return items
}

export function ModeChip({ mode }: { mode: ModeInfo | null }) {
  if (!mode) return null
  const fallback = mode.mode === 'fallback'
  return (
    <span
      title={mode.mode_note}
      className={cx(
        'inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 text-[0.8125rem] font-medium',
        fallback ? 'border-ink/25 bg-white text-ink' : 'border-ink bg-ink text-white',
      )}
    >
      <span className={cx('h-1.5 w-1.5 rounded-full', fallback ? 'bg-watch' : 'bg-sky')} aria-hidden="true" />
      {fallback ? t.top.modeFallback : t.top.modeModel}
    </span>
  )
}

export function Shell({
  user,
  route,
  mode,
  dates,
  asOf,
  onAsOf,
  facilityId,
  onFacility,
  onSignOut,
  extra,
  panelOpen = false,
  children,
}: {
  user: User
  route: Route
  mode: ModeInfo | null
  dates: AsOfDates | null
  asOf: string
  onAsOf: (date: string) => void
  facilityId: string
  onFacility: (id: string) => void
  onSignOut: () => void
  extra?: ReactNode
  panelOpen?: boolean
  children: ReactNode
}) {
  const items = navItems(user)
  const active = route.page === 'group' ? 'brief' : route.page
  const facility = user.facilities.find((f) => f.facility_id === facilityId) ?? user.facilities[0]
  const selectClass =
    'min-h-11 w-full max-w-full rounded-control border border-ink/20 bg-white px-3 pr-8 text-sm font-medium text-ink md:w-auto'

  return (
    <div className={cx('min-h-dvh md:pl-16 xl:pl-52', panelOpen && 'xl:pr-[min(34rem,46vw)]')}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-control focus:bg-ink focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      {/* Left rail: icons on a tablet, icons with labels on a desktop */}
      <nav
        aria-label="Main"
        className="fixed inset-y-0 left-0 z-30 hidden w-16 flex-col border-r border-line bg-white md:flex xl:w-52"
      >
        <a href={href({ page: 'brief' })} className="flex h-16 items-center gap-2.5 px-[18px] no-underline xl:px-5">
          <Logo />
          <span className="hidden text-[0.9375rem] font-semibold text-ink xl:inline">{t.appName}</span>
        </a>
        <ul className="mt-3 flex flex-1 flex-col gap-1 px-2.5 xl:px-3">
          {items.map((item) => (
            <li key={item.page}>
              <a
                href={href({ page: item.page } as Route)}
                aria-current={active === item.page ? 'page' : undefined}
                title={item.label}
                className={cx(
                  'flex min-h-11 items-center justify-center gap-3 rounded-control text-sm font-medium no-underline transition-colors xl:justify-start xl:px-3',
                  active === item.page ? 'bg-ink text-white' : 'text-body hover:bg-sky-soft hover:text-ink',
                )}
              >
                <Icon name={item.icon} />
                <span className="hidden xl:inline">{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
        <div className="border-t border-line p-2.5 xl:p-3">
          <div className="hidden px-3 pb-2 xl:block">
            <p className="text-sm font-medium text-ink">{user.display_name}</p>
            <p className="text-[0.8125rem] text-muted">{user.role_label}</p>
          </div>
          <button
            type="button"
            onClick={onSignOut}
            title={t.nav.signOut}
            className="flex min-h-11 w-full items-center justify-center gap-3 rounded-control text-sm font-medium text-body hover:bg-sky-soft hover:text-ink xl:justify-start xl:px-3"
          >
            <Icon name="signout" />
            <span className="hidden xl:inline">{t.nav.signOut}</span>
          </button>
        </div>
      </nav>

      {/* Pale blue band: where you are, the date, and the mode */}
      <header className="sticky top-0 z-20 bg-sky-soft">
        <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 sm:px-6">
          <div className="flex min-w-0 flex-1 items-center gap-2.5 md:min-w-[15rem]">
            <span className="md:hidden">
              <Logo />
            </span>
            {user.facilities.length > 1 ? (
              <label className="min-w-0 flex-1 md:max-w-[22rem]">
                <span className="sr-only">{t.top.hospital}</span>
                <select className={selectClass.replace('md:w-auto', '')} value={facilityId} onChange={(e) => onFacility(e.target.value)}>
                  {user.facilities.map((f) => (
                    <option key={f.facility_id} value={f.facility_id}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <div className="min-w-0">
                <p className="truncate text-[0.9375rem] font-semibold text-ink">{facility?.name}</p>
                <p className="truncate text-[0.8125rem] text-body">
                  {facility?.county} · {facility?.region_name} region
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={onSignOut}
              aria-label={t.nav.signOut}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-ink hover:bg-white/60 md:hidden"
            >
              <Icon name="signout" />
            </button>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <label className="flex min-w-0 basis-full items-center gap-2 md:basis-auto" title={t.top.asOfHelp}>
              <span className="shrink-0 text-[0.8125rem] font-medium text-ink">{t.top.asOf}</span>
              <select className={selectClass} value={asOf} onChange={(e) => onAsOf(e.target.value)} disabled={!dates}>
                {(dates?.dates ?? [{ date: asOf, label: asOf, note: '' }]).map((d) => (
                  <option key={d.date} value={d.date}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
            {extra}
            <ModeChip mode={mode} />
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-[1120px] px-4 pt-6 pb-28 sm:px-6 md:pb-16">
        {children}
        <p className="mt-16 border-t border-line pt-4 text-[0.8125rem] text-muted">{t.syntheticNote}</p>
      </main>

      {/* Bottom bar on a phone */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="mx-auto flex max-w-md">
          {items.map((item) => (
            <li key={item.page} className="flex-1">
              <a
                href={href({ page: item.page } as Route)}
                aria-current={active === item.page ? 'page' : undefined}
                className={cx(
                  'flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[0.6875rem] font-medium no-underline',
                  active === item.page ? 'text-ink' : 'text-muted',
                )}
              >
                <span className={cx('rounded-full px-3 py-0.5', active === item.page && 'bg-sky-soft')}>
                  <Icon name={item.icon} size={22} />
                </span>
                <span className="max-w-full truncate">{item.label.replace('Data & privacy', 'Privacy').replace('Regional view', 'Region')}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}

/** Small capitalised section label with a thin rule. */
export function SectionLabel({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <h2 className="min-w-0 text-xs font-medium tracking-[0.08em] text-muted uppercase">{children}</h2>
      <span className="h-px min-w-4 flex-1 bg-line" aria-hidden="true" />
      {aside}
    </div>
  )
}

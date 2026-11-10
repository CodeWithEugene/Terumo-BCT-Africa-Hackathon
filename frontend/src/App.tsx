import { useCallback, useEffect, useState } from 'react'
import { Shell } from './components/Shell'
import { QuietState } from './components/States'
import { t } from './i18n/en'
import { api, ApiError, clearCache, getWithCache, readCache, saveCache } from './lib/api'
import { go, useRoute } from './lib/route'
import { AccuracyPage } from './pages/AccuracyPage'
import { BriefPage } from './pages/BriefPage'
import { DecisionsPage } from './pages/DecisionsPage'
import { DetailPanel } from './pages/DetailPanel'
import { RegionPage } from './pages/RegionPage'
import { SignIn } from './pages/SignIn'
import { cx } from './lib/format'
import type { AsOfDates, Component, ModeInfo, ReasonCodes, User } from './types'

type Session = { state: 'checking' } | { state: 'out' } | { state: 'in'; user: User }

export default function App() {
  const route = useRoute()
  const [session, setSession] = useState<Session>({ state: 'checking' })
  const [mode, setMode] = useState<ModeInfo | null>(null)
  const [dates, setDates] = useState<AsOfDates | null>(null)
  const [asOf, setAsOf] = useState<string>('')
  const [facilityId, setFacilityId] = useState<string>('')
  const [component, setComponent] = useState<Component>('RBC')
  const [refreshKey, setRefreshKey] = useState(0)
  const [codes, setCodes] = useState<ReasonCodes | null>(null)

  // Who is signed in? If the server cannot be reached, use the last known user so the cached brief can show.
  useEffect(() => {
    api
      .get<{ user: User } & ModeInfo>('/api/me')
      .then((d) => {
        saveCache('me', d.user)
        setSession({ state: 'in', user: d.user })
        setMode(d)
      })
      .catch((e: ApiError) => {
        const known = readCache<User>('me')
        if (e.status !== 401 && known) setSession({ state: 'in', user: known.data })
        else setSession({ state: 'out' })
      })
  }, [])

  const user = session.state === 'in' ? session.user : null

  useEffect(() => {
    if (!user) return
    setFacilityId((current) => current || user.facilities[0]?.facility_id || user.facility_id)
    getWithCache<AsOfDates>('/api/asof-dates')
      .then(({ data }) => {
        setDates(data)
        setAsOf((current) => current || data.default)
      })
      .catch(() => undefined)
    getWithCache<ReasonCodes>('/api/reason-codes')
      .then(({ data }) => setCodes(data))
      .catch(() => undefined)
  }, [user])

  const onMode = useCallback((m: ModeInfo) => setMode(m), [])

  async function signOut() {
    try {
      await api.post('/api/logout')
    } catch {
      /* signing out locally is enough when offline */
    }
    clearCache()
    setSession({ state: 'out' })
    setFacilityId('')
    setAsOf('')
    go({ page: 'brief' })
  }

  if (session.state === 'checking') {
    return <div className="grid min-h-dvh place-items-center text-sm text-muted">{t.common.loading}</div>
  }
  if (!user) {
    return (
      <SignIn
        onSignedIn={(u, m) => {
          setMode(m)
          saveCache('me', u)
          setSession({ state: 'in', user: u })
        }}
      />
    )
  }

  const ready = asOf !== '' && facilityId !== ''
  return (
    <Shell
      user={user}
      route={route}
      mode={mode}
      dates={dates}
      asOf={asOf}
      onAsOf={setAsOf}
      facilityId={facilityId}
      onFacility={setFacilityId}
      onSignOut={signOut}
      panelOpen={route.page === 'group'}
    >
      {!ready ? (
        <p className="text-sm text-muted">{t.common.loading}</p>
      ) : route.page === 'brief' || route.page === 'group' ? (
        <>
          {/* On a desktop the brief stays and the detail opens beside it. On smaller screens the detail is a full page. */}
          <div className={cx(route.page === 'group' && 'hidden xl:block')}>
            <BriefPage
              asOf={asOf}
              facilityId={facilityId}
              component={component}
              onComponent={setComponent}
              onMode={onMode}
              selectedId={route.page === 'group' ? route.id : undefined}
              refreshKey={refreshKey}
              compact={route.page === 'group'}
            />
          </div>
          {route.page === 'group' && (
            <aside
              aria-label="Blood group detail"
              className="xl:fixed xl:inset-y-0 xl:right-0 xl:z-40 xl:w-[min(34rem,46vw)] xl:overflow-y-auto xl:border-l xl:border-ink/15 xl:bg-white xl:px-7 xl:py-5"
            >
              <DetailPanel
                id={route.id}
                asOf={asOf}
                codes={codes}
                refreshKey={refreshKey}
                onDecided={() => setRefreshKey((k) => k + 1)}
              />
            </aside>
          )}
        </>
      ) : route.page === 'decisions' ? (
        <DecisionsPage user={user} />
      ) : route.page === 'region' && user.role === 'regional_officer' ? (
        <RegionPage
          asOf={asOf}
          codes={codes}
          onMode={onMode}
          onOpen={(facility, seriesId) => {
            setFacilityId(facility)
            setComponent('RBC')
            go({ page: 'group', id: seriesId })
          }}
        />
      ) : route.page === 'accuracy' ? (
        <AccuracyPage
          onMode={(m) => {
            setMode(m)
            setRefreshKey((k) => k + 1)
          }}
        />
      ) : (
        <QuietState title={t.common.comingSoon} text="" />
      )}
    </Shell>
  )
}

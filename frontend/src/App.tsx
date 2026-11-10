import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Shell } from './components/Shell'
import { readTourStep, Tour, writeTourStep } from './components/Tour'
import { QuietState } from './components/States'
import { t } from './i18n/en'
import { api, ApiError, clearCache, getWithCache, readCache, saveCache } from './lib/api'
import { go, useRoute } from './lib/route'
import { AccuracyPage } from './pages/AccuracyPage'
import { BriefPage } from './pages/BriefPage'
import { DecisionsPage } from './pages/DecisionsPage'
import { DetailPanel } from './pages/DetailPanel'
import { PrivacyPage } from './pages/PrivacyPage'
import { RegionPage } from './pages/RegionPage'
import { cx } from './lib/format'
import type { AsOfDates, Component, ModeInfo, ReasonCodes, User } from './types'

// The landing page (story, illustrations, sign-in cards) is loaded only when signed out,
// so none of its code is downloaded inside the working app.
const Landing = lazy(() => import('./pages/Landing'))

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
  const [tourStep, setTourStepState] = useState<number | null>(() => readTourStep())
  const setTourStep = useCallback((step: number | null) => {
    writeTourStep(step)
    setTourStepState(step)
  }, [])

  // Sign in to a test account without a password (used by the tour to change role).
  const demoSignIn = useCallback(async (username: string): Promise<boolean> => {
    try {
      const reply = await api.post<{ user: User } & ModeInfo>('/api/demo-login', { username })
      setMode(reply)
      saveCache('me', reply.user)
      setFacilityId(reply.user.facilities[0]?.facility_id ?? reply.user.facility_id)
      setSession({ state: 'in', user: reply.user })
      return true
    } catch {
      return false
    }
  }, [])

  // A new page starts at the top. Opening a blood group beside the brief on a wide screen does not jump.
  const page = route.page
  useEffect(() => {
    const beside = page === 'group' && window.matchMedia('(min-width: 1280px)').matches
    if (!beside && tourStep === null) window.scrollTo({ top: 0, behavior: 'instant' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

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

  // Opening a blood group by its link also selects that group's hospital, so the brief behind it matches.
  const groupId = route.page === 'group' ? route.id : null
  useEffect(() => {
    if (!user || !groupId) return
    const facility = groupId.split('|')[0]
    if (user.facilities.some((f) => f.facility_id === facility)) setFacilityId(facility)
  }, [user, groupId])

  const onMode = useCallback((m: ModeInfo) => setMode(m), [])

  async function signOut() {
    try {
      await api.post('/api/logout')
    } catch {
      /* signing out locally is enough when offline */
    }
    clearCache()
    setSession({ state: 'out' })
    setTourStep(null)
    setFacilityId('')
    setAsOf('')
    go({ page: 'brief' })
  }

  if (session.state === 'checking') {
    return <div className="grid min-h-dvh place-items-center text-sm text-muted">{t.common.loading}</div>
  }
  if (!user) {
    return (
      <Suspense fallback={<div className="grid min-h-dvh place-items-center text-sm text-muted">{t.common.loading}</div>}>
        <Landing
          onStartTour={async () => {
            if (await demoSignIn(t.tour.steps[0].user)) {
              setTourStep(0)
              window.scrollTo(0, 0)
            }
          }}
          onSignedIn={(u, m) => {
            setMode(m)
            saveCache('me', u)
            setSession({ state: 'in', user: u })
            window.scrollTo(0, 0)
          }}
        />
      </Suspense>
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
      onStartTour={() => setTourStep(0)}
    >
      {tourStep !== null && <Tour step={tourStep} username={user.username} onStep={setTourStep} onNeedUser={demoSignIn} />}
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
              className="xl:fixed xl:inset-y-0 xl:right-0 xl:z-40 xl:w-[min(34rem,46vw)] xl:overflow-y-auto xl:overscroll-contain xl:border-l xl:border-ink/15 xl:bg-white xl:px-7 xl:py-5"
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
      ) : route.page === 'privacy' ? (
        <PrivacyPage />
      ) : (
        <QuietState title={t.common.comingSoon} text="" />
      )}
    </Shell>
  )
}

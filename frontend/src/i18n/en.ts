// Every sentence a person reads lives here, so another language can be added by settings.
export const en = {
  appName: 'Sanguis Providus',
  tagline: 'Blood stock early warning',
  syntheticNote: 'Demo on synthetic data. No real hospital, donor or patient.',

  nav: {
    brief: 'Brief',
    region: 'Regional view',
    decisions: 'Decisions',
    accuracy: 'Accuracy',
    privacy: 'Data & privacy',
    signOut: 'Sign out',
  },

  signIn: {
    label: 'Sign in',
    title: 'Know which blood groups will run short, before they do.',
    lead: 'Choose a test account to see the morning brief. These accounts are for the demo only.',
    openAs: 'Open as',
    manual: 'Sign in with a name and password',
    username: 'Name',
    password: 'Password',
    submit: 'Sign in',
    wrong: 'That name and password do not match.',
    notBuilt: 'The database has not been built yet. Run "python -m backend.pipeline.build", then reload.',
    unreachable: 'Could not reach the server. Start the backend on port 8000, then reload.',
    testPassword: 'Test password',
  },

  top: {
    asOf: 'As of',
    asOfHelp: 'The data is historical. Everything after this date is hidden from the forecast.',
    hospital: 'Hospital',
    modeModel: 'Model: forecast in use',
    modeFallback: 'Fallback: using the 4-week average',
    offline: 'Offline',
  },

  brief: {
    label: 'Morning brief',
    greeting: (hour: number) => (hour < 12 ? 'Good morning.' : hour < 17 ? 'Good afternoon.' : 'Good evening.'),
    nextDelivery: (day: string) => `Next delivery: ${day}`,
    noDelivery: 'No routine delivery in the next 14 days',
    groupsLabel: 'Blood groups',
    attentionFirst: 'Groups that need attention come first.',
    cached: (when: string) => `Could not reach the server. Showing the brief last synced ${when}.`,
    retry: 'Try again',
    errorTitle: 'The brief could not be loaded.',
    errorHelp: 'Check that the server is running, then try again.',
    allSteadyTitle: 'All steady.',
    allSteadyText: 'Nothing needs you today. The next check is tomorrow morning.',
    notHeldTitle: (product: string) => `${product} are not held at this hospital.`,
    notHeldText: 'Requests are filled by delivery from the regional centre. Expected requests for the next 7 days are shown so the centre can plan.',
    expected7: 'Expected requests, next 7 days',
    range: (low: number, high: number) => `could be ${low} to ${high}`,
  },

  tile: {
    daysOfCover: 'days of cover',
    dayOfCover: 'day of cover',
    empty: 'Empty',
    emptyHint: 'nothing on the shelf',
    noUse: 'No use expected',
    noUseHint: 'in the next 14 days',
    plus: '14+',
    onShelf: (n: number) => `${n} ${n === 1 ? 'unit' : 'units'} on shelf`,
    couldBe: (d: string) => `could be ${d} if busy`,
    open: (group: string) => `Open ${group}`,
    deliveryTick: (day: string) => `Next delivery ${day}`,
    coverBar: (cover: string, delivery: string) => `Cover lasts ${cover}. ${delivery}.`,
  },

  status: { act: 'Act', watch: 'Watch', steady: 'Steady', not_held: 'Not held here' },

  common: {
    loading: 'Loading…',
    units: (n: number) => `${n} ${n === 1 ? 'unit' : 'units'}`,
    close: 'Close',
    back: 'Back to the brief',
    comingSoon: 'This page is being built.',
  },
}

export type Strings = typeof en
export const t = en

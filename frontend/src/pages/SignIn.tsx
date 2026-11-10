import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { Logo } from '../components/Shell'
import { Button } from '../components/States'
import { TubesBackdrop } from '../components/Tubes'
import { t } from '../i18n/en'
import { api, ApiError } from '../lib/api'
import type { DemoUser, User } from '../types'

export function SignIn({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [accounts, setAccounts] = useState<DemoUser[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [manual, setManual] = useState(false)
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')

  useEffect(() => {
    api
      .get<{ users: DemoUser[] }>('/api/demo-users')
      .then((d) => setAccounts(d.users))
      .catch((e: ApiError) => {
        setAccounts([])
        setProblem(e.status === 503 ? t.signIn.notBuilt : t.signIn.unreachable)
      })
  }, [])

  async function signIn(username: string, secret: string) {
    setBusy(username)
    setProblem(null)
    try {
      const reply = await api.post<{ user: User }>('/api/login', { username, password: secret })
      onSignedIn(reply.user)
    } catch (e) {
      const error = e as ApiError
      setProblem(error.status === 401 ? t.signIn.wrong : error.status === 503 ? t.signIn.notBuilt : t.signIn.unreachable)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <TubesBackdrop />
      <header className="relative bg-sky-soft">
        <div className="mx-auto flex max-w-[1120px] items-center gap-2.5 px-4 py-3 sm:px-6">
          <Logo />
          <span className="text-[0.9375rem] font-semibold text-ink">{t.appName}</span>
        </div>
      </header>

      <main className="relative mx-auto max-w-[1120px] px-4 py-[clamp(2rem,6vw,5rem)] sm:px-6">
        <div className="flex items-center gap-3">
          <p className="text-xs font-medium tracking-[0.08em] text-muted uppercase">{t.signIn.label}</p>
          <span className="h-px w-16 bg-line" aria-hidden="true" />
        </div>
        <h1 className="mt-4 max-w-[17ch] text-[clamp(2rem,5.5vw,3.5rem)] leading-[1.08]">{t.signIn.title}</h1>
        <p className="mt-4 max-w-[48ch] text-base">{t.signIn.lead}</p>

        {problem && (
          <p role="alert" className="mt-6 max-w-xl rounded-card border border-[#f0cdc9] bg-act-soft px-4 py-3 text-sm text-act">
            {problem}
          </p>
        )}

        <ul className="mt-8 grid max-w-[880px] gap-3 md:grid-cols-3">
          {accounts === null &&
            [0, 1, 2].map((i) => <li key={i} className="h-44 animate-pulse rounded-card border border-line bg-white" />)}
          {accounts?.map((account, i) => (
            <li key={account.username} className="flex flex-col rounded-card border border-line bg-white/95 p-5">
              <p className="text-xs font-medium tracking-[0.06em] text-muted uppercase">{account.role_label}</p>
              <p className="mt-2 text-lg leading-snug font-semibold text-ink">{account.facility_name}</p>
              <p className="mt-1 flex items-center gap-1.5 text-sm">
                <Icon name="user" size={16} />
                {account.display_name}
              </p>
              <p className="mt-1 mb-4 text-[0.8125rem] text-muted">
                {t.signIn.testPassword}: <code className="text-body">{account.demo_password}</code>
              </p>
              <Button
                variant={i === 2 ? 'sky' : 'primary'}
                icon="arrow"
                className="mt-auto w-full"
                disabled={busy !== null}
                onClick={() => signIn(account.username, account.demo_password)}
              >
                {busy === account.username ? t.common.loading : `${t.signIn.openAs} ${account.display_name}`}
              </Button>
            </li>
          ))}
        </ul>

        <div className="mt-6 max-w-sm">
          {!manual ? (
            <Button variant="text" className="!px-0" onClick={() => setManual(true)}>
              {t.signIn.manual}
            </Button>
          ) : (
            <form
              className="grid gap-3 rounded-card border border-line bg-white p-5"
              onSubmit={(e) => {
                e.preventDefault()
                void signIn(name, password)
              }}
            >
              <label className="grid gap-1 text-sm font-medium text-ink">
                {t.signIn.username}
                <input
                  className="min-h-11 rounded-control border border-ink/25 px-3 font-normal"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
              <label className="grid gap-1 text-sm font-medium text-ink">
                {t.signIn.password}
                <input
                  type="password"
                  className="min-h-11 rounded-control border border-ink/25 px-3 font-normal"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <Button type="submit" disabled={busy !== null}>
                {t.signIn.submit}
              </Button>
            </form>
          )}
        </div>

        <p className="mt-12 border-t border-line pt-4 text-[0.8125rem] text-muted">{t.syntheticNote}</p>
      </main>
    </div>
  )
}

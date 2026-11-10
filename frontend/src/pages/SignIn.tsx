import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { Button } from '../components/States'
import { t } from '../i18n/en'
import { api, ApiError } from '../lib/api'
import type { DemoUser, ModeInfo, User } from '../types'

export function SignInPanel({ onSignedIn }: { onSignedIn: (user: User, mode: ModeInfo) => void }) {
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

  // One tap for a test account (the server signs it in; no password reaches the browser),
  // or a name and password typed into the form.
  async function signIn(username: string, secret?: string) {
    setBusy(username)
    setProblem(null)
    try {
      const reply = secret === undefined
        ? await api.post<{ user: User } & ModeInfo>('/api/demo-login', { username })
        : await api.post<{ user: User } & ModeInfo>('/api/login', { username, password: secret })
      onSignedIn(reply.user, reply)
    } catch (e) {
      const error = e as ApiError
      setProblem(error.status === 401 ? t.signIn.wrong : error.status === 429 ? error.message : error.status === 503 ? t.signIn.notBuilt : t.signIn.unreachable)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
        {problem && (
          <p role="alert" className="mt-6 max-w-xl rounded-card border border-[#f0cdc9] bg-act-soft px-4 py-3 text-sm text-act">
            {problem}
          </p>
        )}

        <ul className="mt-8 grid max-w-[880px] gap-3 md:grid-cols-3">
          {accounts === null &&
            [0, 1, 2].map((i) => (
              <li key={i} className="flex h-44 flex-col justify-between rounded-card border border-line bg-white p-5" aria-hidden={i > 0}>
                <span className="text-sm text-muted">{i === 0 ? 'Loading the test accounts…' : ''}</span>
                <span className="h-11 animate-pulse rounded-control bg-bg-alt" />
              </li>
            ))}
          {accounts?.map((account, i) => (
            <li key={account.username} className="flex flex-col rounded-card border border-line bg-white/95 p-5">
              <p className="text-xs font-medium tracking-[0.06em] text-muted uppercase">{account.role_label}</p>
              <p className="mt-2 text-lg leading-snug font-semibold text-ink">{account.facility_name}</p>
              <p className="mt-1 flex items-center gap-1.5 text-sm">
                <Icon name="user" size={16} />
                {account.display_name}
              </p>
              <p className="mb-4" />
              <Button
                variant={i === 2 ? 'sky' : 'primary'}
                icon="arrow"
                className="mt-auto w-full"
                disabled={busy !== null}
                onClick={() => signIn(account.username)}
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

    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
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

  const dialog = useRef<HTMLDialogElement | null>(null)
  const [role, setRole] = useState<string | null>(null)
  // The roles on offer, in the order the server lists them.
  const roles = Array.from(new Map((accounts ?? []).map((a) => [a.role, a.role_label])))
  const sites = (accounts ?? []).filter((a) => a.role === role)

  function open() {
    setRole(null)
    setProblem(null)
    setManual(accounts !== null && accounts.length === 0)
    dialog.current?.showModal()
  }

  function chooseRole(chosen: string) {
    const matches = (accounts ?? []).filter((a) => a.role === chosen)
    if (matches.length === 1) void signIn(matches[0].username)
    else setRole(chosen)
  }

  const option =
    'flex min-h-11 w-full items-center gap-3 rounded-control border border-ink/20 bg-white px-4 py-3 text-left hover:border-ink hover:bg-sky-soft disabled:opacity-60'

  return (
    <div>
      <Button icon="arrow" className="mt-8" onClick={open} data-sign-in>
        {t.signIn.open}
      </Button>

      <dialog
        ref={dialog}
        aria-labelledby="sign-in-title"
        className="m-auto w-[min(28rem,calc(100vw-1.5rem))] rounded-card border border-line bg-white p-0 text-ink shadow-[0_16px_48px_rgba(20,27,77,0.22)] backdrop:bg-ink/40"
        onClick={(e) => {
          if (e.target === dialog.current) dialog.current?.close() // a click outside the box
        }}
      >
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 id="sign-in-title" className="text-xl leading-snug font-semibold">
                {manual ? t.signIn.manual : role ? t.signIn.chooseSite : t.signIn.chooseRole}
              </h2>
              {!manual && !role && <p className="mt-1 text-sm">{t.signIn.chooseRoleLead}</p>}
            </div>
            <button
              type="button"
              aria-label={t.common.close}
              className="-mt-1 -mr-2 grid size-11 shrink-0 place-items-center rounded-control hover:bg-sky-soft"
              onClick={() => dialog.current?.close()}
            >
              <Icon name="close" size={18} />
            </button>
          </div>

          {problem && (
            <p role="alert" className="mt-4 rounded-card border border-[#f0cdc9] bg-act-soft px-4 py-3 text-sm text-act">
              {problem}
            </p>
          )}

          {!manual && accounts === null && <p className="mt-5 text-sm text-muted">{t.signIn.loadingRoles}</p>}

          {!manual && !role && roles.length > 0 && (
            <ul className="mt-5 grid gap-2.5">
              {roles.map(([key, label]) => (
                <li key={key}>
                  <button type="button" className={option} disabled={busy !== null} onClick={() => chooseRole(key)}>
                    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-sky-soft">
                      <Icon name={key === 'regional_officer' ? 'region' : 'brief'} size={20} />
                    </span>
                    <span>
                      <span className="block font-semibold">{label}</span>
                      {t.signIn.roles[key] && <span className="mt-0.5 block text-sm">{t.signIn.roles[key]}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {!manual && role && (
            <>
              <ul className="mt-5 grid gap-2.5">
                {sites.map((account) => (
                  <li key={account.username}>
                    <button type="button" className={option} disabled={busy !== null} onClick={() => signIn(account.username)}>
                      <span className="font-semibold">{busy === account.username ? t.common.loading : account.facility_name}</span>
                      <span className="ml-auto"><Icon name="arrow" size={18} /></span>
                    </button>
                  </li>
                ))}
              </ul>
              <Button variant="text" icon="back" className="mt-3 !px-0" onClick={() => setRole(null)}>
                {t.signIn.otherRole}
              </Button>
            </>
          )}

          {manual ? (
            <form
              className="mt-5 grid gap-3"
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
              {roles.length > 0 && (
                <Button variant="text" icon="back" className="!px-0" onClick={() => setManual(false)}>
                  {t.signIn.otherRole}
                </Button>
              )}
            </form>
          ) : (
            <p className="mt-5 border-t border-line pt-3">
              <Button variant="text" className="!px-0" onClick={() => setManual(true)}>
                {t.signIn.manual}
              </Button>
            </p>
          )}
        </div>
      </dialog>
    </div>
  )
}

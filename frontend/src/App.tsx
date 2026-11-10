import { useEffect, useState } from 'react'

type Health = 'checking' | 'ok' | 'unreachable'

export default function App() {
  const [health, setHealth] = useState<Health>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: { status?: string }) => setHealth(d.status === 'ok' ? 'ok' : 'unreachable'))
      .catch(() => setHealth('unreachable'))
  }, [])

  const message = {
    checking: 'Checking the server…',
    ok: 'Server is running.',
    unreachable: 'Could not reach the server. Start the backend on port 8000.',
  }[health]

  return (
    <div className="min-h-dvh">
      <header className="bg-sky-soft">
        <div className="mx-auto flex max-w-[1120px] items-center px-4 py-3 sm:px-6">
          <span className="text-base font-semibold text-ink">Sanguis Providus</span>
        </div>
      </header>
      <main className="mx-auto max-w-[1120px] px-4 py-[clamp(2rem,8vw,6rem)] sm:px-6">
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-muted">
          Blood stock early warning
        </p>
        <h1 className="mt-3 max-w-[18ch] text-[clamp(2rem,6vw,3.5rem)] leading-[1.1]">
          Sanguis Providus
        </h1>
        <p className="mt-4 max-w-[52ch]">
          Shows which blood groups will run short, where, and in how many days.
        </p>
        <p className="mt-8 border-t border-line pt-4 text-sm text-muted" role="status">
          {message}
        </p>
      </main>
    </div>
  )
}

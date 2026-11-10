import { useEffect, useRef, useState } from 'react'
import { t } from '../i18n/en'
import { api, ApiError } from '../lib/api'
import { cx } from '../lib/format'
import type { Decision, ReasonCodes, Series } from '../types'
import { Icon } from './Icon'
import { Button } from './States'

type Mode = 'idle' | 'change' | 'reject'

/**
 * The suggestion and the three choices. The person decides: Accept is the
 * clearest button, Change and Reject ask for a reason inline (no pop-up),
 * and a decision can be undone for a few seconds.
 */
export function DecisionBar({
  series,
  asOf,
  codes,
  onDecided,
}: {
  series: Series
  asOf: string
  codes: ReasonCodes | null
  onDecided: () => void
}) {
  const suggestion = series.suggestion
  const [mode, setMode] = useState<Mode>('idle')
  const [quantity, setQuantity] = useState(suggestion?.quantity ?? 0)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [decision, setDecision] = useState<Decision | null>(series.decision ?? null)
  const [undoLeft, setUndoLeft] = useState(0)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    setDecision(series.decision ?? null)
    setQuantity(series.suggestion?.quantity ?? 0)
    setMode('idle')
    setReason('')
    setNote('')
    setProblem(null)
    setUndoLeft(0)
  }, [series.id, series.as_of, series.decision, series.suggestion?.quantity])

  useEffect(() => {
    if (undoLeft <= 0) return
    timer.current = window.setTimeout(() => setUndoLeft((s) => s - 1), 1000)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [undoLeft])

  async function send(action: 'accept' | 'change' | 'reject') {
    setBusy(true)
    setProblem(null)
    try {
      const reply = await api.post<{ decision: Decision; undo_seconds: number }>('/api/decisions', {
        series_id: series.id,
        as_of: asOf,
        action,
        quantity: action === 'change' ? quantity : undefined,
        reason_code: action === 'accept' ? undefined : reason || undefined,
        note: note.trim() || undefined,
      })
      setDecision(reply.decision)
      setUndoLeft(reply.undo_seconds)
      setMode('idle')
      onDecided()
    } catch (e) {
      setProblem((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  async function undo() {
    if (!decision) return
    setBusy(true)
    try {
      await api.post(`/api/decisions/${decision.decision_id}/undo`)
      setDecision(null)
      setUndoLeft(0)
      onDecided()
    } catch (e) {
      setProblem((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  // Keyboard: A accept, C change, R reject (only when nothing is being typed).
  useEffect(() => {
    if (!suggestion || decision) return
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || event.metaKey || event.ctrlKey || event.altKey) return
      const key = event.key.toLowerCase()
      if (key === 'a' && mode === 'idle' && !busy) void send('accept')
      if (key === 'c') setMode('change')
      if (key === 'r') setMode('reject')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestion, decision, mode, busy, quantity, reason, note])

  if (!suggestion) return <p className="text-sm">{t.detail.noSuggestion}</p>

  if (decision) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-ink/15 bg-bg-alt px-4 py-3" role="status">
        <p className="flex items-center gap-2 text-sm font-medium text-ink">
          <Icon name="check" size={18} />
          <span>
            {decision.summary}
            <span className="font-normal text-body">
              {' · '}
              {decision.action === 'reject' ? t.decisions.reject : t.common.units(decision.final_quantity)}
            </span>
          </span>
        </p>
        {undoLeft > 0 && (
          <Button variant="outline" onClick={undo} disabled={busy}>
            {t.detail.undo(undoLeft)}
          </Button>
        )}
        {problem && <p className="basis-full text-sm text-act">{problem}</p>}
      </div>
    )
  }

  const acceptLabel = series.action_label === 'Request approval' ? t.detail.requestApproval : t.detail.accept
  const list = mode === 'idle' ? [] : (codes?.[mode] ?? [])
  const needsNote = reason === 'other'
  const canSave =
    reason !== '' && (!needsNote || note.trim() !== '') && (mode === 'reject' || quantity !== suggestion.quantity) && !busy

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <p className="text-sm font-medium text-ink">{suggestion.title}</p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="text-[2.500rem] leading-none font-medium tracking-[-0.010em] text-ink">{suggestion.quantity}</span>
            <span className="text-sm">{suggestion.quantity === 1 ? 'unit' : 'units'}</span>
            {suggestion.kind === 'order' && <span className="text-[0.8125rem] text-muted">{t.detail.usual(suggestion.usual_quantity)}</span>}
          </p>
        </div>
        <p className="text-[0.8125rem] text-muted">{t.detail.personDecides}</p>
      </div>

      {/* The sum, never a bare number */}
      <details className="mt-3 rounded-control border border-line px-3 py-2 text-sm" open>
        <summary className="cursor-pointer font-medium text-ink">{t.detail.howWorked}</summary>
        <dl className="mt-2">
          {suggestion.parts.map((part) => (
            <div key={part.label} className="flex justify-between gap-4 border-t border-line py-1.5">
              <dt>{part.label}</dt>
              <dd className="shrink-0 font-medium text-ink">
                {part.units < 0 ? '−' : '+'}
                {Math.abs(part.units)}
              </dd>
            </div>
          ))}
          <div className="flex justify-between gap-4 border-t border-ink/30 py-1.5 text-ink">
            <dt className="font-medium">{suggestion.sum_text}</dt>
          </div>
        </dl>
      </details>
      {suggestion.needs_approval && (
        <p className="mt-3 flex gap-2 text-sm">
          <Icon name="info" size={18} className="mt-0.5 shrink-0" />
          {suggestion.needs_approval}
        </p>
      )}

      {mode === 'idle' && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button icon="check" onClick={() => send('accept')} disabled={busy} className="min-w-36 flex-1 sm:flex-none">
            {acceptLabel}
          </Button>
          <Button variant="outline" icon="edit" onClick={() => setMode('change')} disabled={busy}>
            {t.detail.change}
          </Button>
          <Button variant="text" onClick={() => setMode('reject')} disabled={busy}>
            {t.detail.reject}
          </Button>
        </div>
      )}

      {mode !== 'idle' && (
        <form
          className="mt-4 rounded-card border border-ink/20 p-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (canSave) void send(mode)
          }}
        >
          {mode === 'change' && (
            <div className="mb-4 flex items-center gap-3">
              <span className="text-sm font-medium text-ink" id="qty-label">
                {t.detail.quantity}
              </span>
              <div className="inline-flex items-center rounded-control border border-ink/30">
                <button type="button" aria-label={t.detail.fewer} className="grid h-11 w-11 place-items-center text-ink disabled:opacity-40" disabled={quantity <= 0} onClick={() => setQuantity((q) => Math.max(0, q - 1))}>
                  <Icon name="minus" size={18} />
                </button>
                <input
                  aria-labelledby="qty-label"
                  inputMode="numeric"
                  className="h-11 w-14 border-x border-ink/30 text-center text-lg font-medium text-ink"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.min(500, Math.max(0, Number(e.target.value.replace(/\D/g, '')) || 0)))}
                />
                <button type="button" aria-label={t.detail.more} className="grid h-11 w-11 place-items-center text-ink" onClick={() => setQuantity((q) => Math.min(500, q + 1))}>
                  <Icon name="plus" size={18} />
                </button>
              </div>
              <span className="text-[0.8125rem] text-muted">
                {t.detail.suggested}: {suggestion.quantity}
              </span>
            </div>
          )}
          <fieldset>
            <legend className="text-sm font-medium text-ink">{t.detail.reasonFor[mode]}</legend>
            <div className="mt-2 grid gap-1.5">
              {list.map((item) => (
                <label
                  key={item.code}
                  className={cx(
                    'flex min-h-11 cursor-pointer items-center gap-3 rounded-control border px-3 text-sm',
                    reason === item.code ? 'border-ink bg-sky-soft text-ink' : 'border-line hover:border-ink/40',
                  )}
                >
                  <input type="radio" name="reason" className="h-4 w-4 accent-[#141b4d]" checked={reason === item.code} onChange={() => setReason(item.code)} />
                  {item.label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="mt-3 grid gap-1 text-sm font-medium text-ink">
            {needsNote ? t.detail.noteRequired : t.detail.note}
            <textarea className="min-h-16 rounded-control border border-ink/25 px-3 py-2 font-normal" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="submit" disabled={!canSave}>
              {mode === 'change' ? t.detail.saveChange(quantity) : t.detail.confirmReject}
            </Button>
            <Button variant="text" onClick={() => setMode('idle')}>
              {t.detail.cancel}
            </Button>
          </div>
        </form>
      )}
      {problem && (
        <p role="alert" className="mt-3 text-sm text-act">
          {problem}
        </p>
      )}
      <p className="mt-3 hidden text-[0.8125rem] text-muted xl:block">{t.detail.keys}</p>
    </div>
  )
}

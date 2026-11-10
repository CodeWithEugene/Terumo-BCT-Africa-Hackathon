export function coverText(days: number | null, capped?: boolean): string {
  if (days === null) return '–'
  if (capped) return '14+'
  return days >= 10 ? days.toFixed(0) : days.toFixed(1)
}

export function timeAgo(iso: string): string {
  const then = new Date(iso)
  const minutes = Math.round((Date.now() - then.getTime()) / 60000)
  const clock = then.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  if (minutes < 1) return `just now (${clock})`
  if (minutes < 60) return `${minutes} min ago (${clock})`
  const sameDay = then.toDateString() === new Date().toDateString()
  return sameDay ? `today at ${clock}` : `${then.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })} at ${clock}`
}

export function num(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}
